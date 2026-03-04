"""
Source Health Manager

Автоматическое управление здоровьем источников:
- Fail streak tracking
- Auto-disable при N неудачах
- Pass rate calculation
- Cooldown и recheck
- Source promotion/demotion
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal

from fp.config import ALL_SOURCES, ProxySource, SourceType
from fp.database import ProxyDatabase


@dataclass
class SourceHealth:
    """Статистика источника"""
    name: str
    url: str
    fail_streak: int = 0
    success_streak: int = 0
    total_fetches: int = 0
    successful_fetches: int = 0
    pass_rate: float = 100.0
    last_success: float = 0.0
    last_failure: float = 0.0
    disabled_until: float = 0.0
    avg_latency: float = 0.0
    error_counts: dict = field(default_factory=dict)
    
    def is_disabled(self) -> bool:
        """Проверить, отключён ли источник"""
        return time.time() < self.disabled_until
    
    def can_recheck(self) -> bool:
        """Можно ли сделать recheck"""
        return not self.is_disabled()
    
    def record_success(self, latency_ms: float = 0) -> None:
        """Записать успешную проверку"""
        self.total_fetches += 1
        self.successful_fetches += 1
        self.success_streak += 1
        self.fail_streak = 0
        self.last_success = time.time()
        self.pass_rate = (self.successful_fetches / self.total_fetches) * 100
        
        # EMA latency
        self.avg_latency = (self.avg_latency * 0.7) + (latency_ms * 0.3)
    
    def record_failure(self, error_type: str) -> None:
        """Записать неудачную проверку"""
        self.total_fetches += 1
        self.fail_streak += 1
        self.success_streak = 0
        self.last_failure = time.time()
        self.pass_rate = (self.successful_fetches / self.total_fetches) * 100
        
        # Считаем ошибки
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
    
    def get_top_errors(self, limit: int = 3) -> list[tuple[str, int]]:
        """Топ ошибок"""
        sorted_errors = sorted(self.error_counts.items(), key=lambda x: x[1], reverse=True)
        return sorted_errors[:limit]


class SourceHealthManager:
    """
    Менеджер здоровья источников
    
    Правила:
    - fail_streak >= 5 → disable на 24ч
    - pass_rate < 30% → disable на 24ч
    - После disable → recheck через 24ч
    - Candidate sources → sandbox test перед promotion
    """
    
    # Пороги
    FAIL_STREAK_THRESHOLD = 5
    PASS_RATE_THRESHOLD = 30.0  # %
    DISABLE_HOURS = 24
    SANDBOX_CYCLES = 3  # Для candidate sources
    
    def __init__(self) -> None:
        self.sources: dict[str, SourceHealth] = {}
        self._db: ProxyDatabase | None = None
        
        # Инициализация
        for source in ALL_SOURCES:
            self.sources[source["url"]] = SourceHealth(
                name=source["name"],
                url=source["url"],
            )
    
    async def __aenter__(self) -> "SourceHealthManager":
        self._db = await ProxyDatabase().__aenter__()
        await self._load_from_db()
        return self
    
    async def __aexit__(self, *args) -> None:
        if self._db:
            await self._db.__aexit__(*args)
    
    async def _load_from_db(self) -> None:
        """Загрузить статистику из БД"""
        if not self._db:
            return
        
        stats = await self._db._conn.execute(
            """
            SELECT url, fail_streak, pass_rate, disabled_until, 
                   total_fetches, successful_fetches, avg_latency
            FROM sources
            """,
        )
        
        async for row in stats:
            url = row[0]
            if url in self.sources:
                health = self.sources[url]
                health.fail_streak = row[1] or 0
                health.pass_rate = row[2] or 100
                health.disabled_until = row[3] or 0
                health.total_fetches = row[4] or 0
                health.successful_fetches = row[5] or 0
                health.avg_latency = row[6] or 0
    
    async def save_to_db(self) -> None:
        """Сохранить статистику в БД"""
        if not self._db:
            return
        
        for url, health in self.sources.items():
            await self._db._conn.execute(
                """
                INSERT OR REPLACE INTO sources 
                (url, name, type, protocols, fail_streak, pass_rate, 
                 disabled_until, total_fetches, successful_fetches, avg_latency)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    url, health.name, "unknown", "",
                    health.fail_streak, health.pass_rate,
                    health.disabled_until if health.disabled_until > 0 else None,
                    health.total_fetches, health.successful_fetches,
                    health.avg_latency,
                ),
            )
        
        await self._db._conn.commit()
    
    def record_success(self, url: str, latency_ms: float = 0) -> None:
        """Записать успех"""
        if url not in self.sources:
            return
        
        health = self.sources[url]
        health.record_success(latency_ms)
        
        # Проверка на auto-enable
        if health.is_disabled() and health.fail_streak == 0:
            health.disabled_until = 0  # Enable immediately
    
    def record_failure(self, url: str, error_type: str) -> None:
        """Записать неудачу"""
        if url not in self.sources:
            return
        
        health = self.sources[url]
        health.record_failure(error_type)
        
        # Проверка на auto-disable
        if not health.is_disabled():
            if health.fail_streak >= self.FAIL_STREAK_THRESHOLD:
                health.disabled_until = time.time() + (self.DISABLE_HOURS * 3600)
            elif health.pass_rate < self.PASS_RATE_THRESHOLD:
                health.disabled_until = time.time() + (self.DISABLE_HOURS * 3600)
    
    def is_available(self, url: str) -> bool:
        """Проверить доступность источника"""
        if url not in self.sources:
            return False
        
        return self.sources[url].can_recheck()
    
    def get_available_sources(self) -> list[ProxySource]:
        """Получить доступные источники"""
        available = []
        
        for source in ALL_SOURCES:
            if self.is_available(source["url"]):
                available.append(source)
        
        return available
    
    def get_disabled_sources(self) -> list[dict]:
        """Получить отключенные источники"""
        disabled = []
        now = time.time()
        
        for url, health in self.sources.items():
            if health.is_disabled():
                disabled.append({
                    "name": health.name,
                    "url": url,
                    "fail_streak": health.fail_streak,
                    "pass_rate": health.pass_rate,
                    "disabled_until": datetime.fromtimestamp(health.disabled_until).isoformat(),
                    "top_errors": health.get_top_errors(),
                })
        
        return sorted(disabled, key=lambda x: x["disabled_until"])
    
    def get_stats(self) -> dict:
        """Получить общую статистику"""
        total = len(self.sources)
        available = sum(1 for h in self.sources.values() if h.can_recheck())
        disabled = total - available
        
        avg_pass_rate = (
            sum(h.pass_rate for h in self.sources.values()) / total
            if total > 0 else 0
        )
        
        # Топ ошибок
        all_errors: dict = {}
        for health in self.sources.values():
            for error, count in health.error_counts.items():
                all_errors[error] = all_errors.get(error, 0) + count
        
        top_errors = sorted(all_errors.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            "total_sources": total,
            "available": available,
            "disabled": disabled,
            "avg_pass_rate": round(avg_pass_rate, 2),
            "top_errors": top_errors,
        }
    
    async def recheck_disabled(self) -> dict:
        """Recheck отключенных источников"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "rechecked": 0,
            "enabled": 0,
            "still_disabled": 0,
        }
        
        now = time.time()
        
        for url, health in self.sources.items():
            if health.is_disabled() and health.disabled_until <= now:
                report["rechecked"] += 1
                
                # Пробуем сделать быстрый test
                # (в реальности здесь будет вызов parser.parse() с таймаутом)
                # Для демо просто сбрасываем fail streak
                health.fail_streak = 0
                health.disabled_until = 0
                
                report["enabled"] += 1
        
        return report
    
    def get_core_sources(self) -> list[ProxySource]:
        """Получить core (проверенные) источники"""
        core = []
        
        for source in ALL_SOURCES:
            health = self.sources.get(source["url"])
            if not health:
                continue
            
            # Core: pass_rate >= 50% и fail_streak < 3
            if health.pass_rate >= 50 and health.fail_streak < 3:
                core.append(source)
        
        return core
    
    def get_candidate_sources(self) -> list[ProxySource]:
        """Получить candidate (новые/сомнительные) источники"""
        candidates = []
        
        for source in ALL_SOURCES:
            health = self.sources.get(source["url"])
            if not health:
                continue
            
            # Candidate: pass_rate < 50% или мало данных
            if health.pass_rate < 50 or health.total_fetches < 10:
                candidates.append(source)
        
        return candidates


async def main():
    """Пример использования"""
    async with SourceHealthManager() as manager:
        print("=== Source Stats ===")
        stats = manager.get_stats()
        print(f"Total: {stats['total_sources']}")
        print(f"Available: {stats['available']}")
        print(f"Disabled: {stats['disabled']}")
        print(f"Avg pass rate: {stats['avg_pass_rate']}%")
        
        print("\n=== Top Errors ===")
        for error, count in stats["top_errors"]:
            print(f"  {error}: {count}")
        
        print("\n=== Disabled Sources ===")
        disabled = manager.get_disabled_sources()
        for source in disabled[:5]:
            print(f"  {source['name']}: {source['fail_streak']} fails, {source['pass_rate']:.1f}%")


if __name__ == "__main__":
    asyncio.run(main())
