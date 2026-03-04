"""
Proxy Manager v3.0

Полный цикл:
COLLECT → VALIDATE A → VALIDATE B → SCORE → ROTATE → REPORT
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Literal

from fp.validator import AsyncProxyValidator, ProxyMetrics, ProxyPool, ProxyValidationResult, ValidationStage
from fp.database import ProxyDatabase


class ProxyManager:
    """
    Менеджер прокси с полным циклом валидации
    """
    
    def __init__(
        self,
        db_path: str = "~/.free-proxy/proxies.db",
        max_concurrent: int = 50,
        report_path: str = "~/.free-proxy/reports",
    ) -> None:
        self.db_path = db_path
        self.max_concurrent = max_concurrent
        self.report_path = Path(report_path).expanduser()
        self.report_path.mkdir(parents=True, exist_ok=True)
        
        self._db: ProxyDatabase | None = None
        self._validator: AsyncProxyValidator | None = None
    
    async def __aenter__(self) -> "ProxyManager":
        self._db = await ProxyDatabase(self.db_path).__aenter__()
        self._validator = await AsyncProxyValidator(self.max_concurrent).__aenter__()
        return self
    
    async def __aexit__(self, *args) -> None:
        if self._validator:
            await self._validator.__aexit__(*args)
        if self._db:
            await self._db.__aexit__(*args)
    
    async def collect_and_validate(
        self,
        proxies: list[tuple[str, int, str]],
        skip_stage_b: bool = False,
        batch_size: int = 100,
    ) -> dict:
        """
        COLLECT → VALIDATE цикл
        
        Args:
            proxies: Список (ip, port, protocol)
            skip_stage_b: Только Stage A
            batch_size: Размер батча для обработки
        
        Returns:
            Отчёт о валидации
        """
        assert self._db is not None
        assert self._validator is not None
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "total": len(proxies),
            "new": 0,
            "existing": 0,
            "passed_a": 0,
            "passed_b": 0,
            "failed": 0,
            "hot": 0,
            "warm": 0,
            "quarantine": 0,
            "avg_latency": 0,
            "avg_score": 0,
            "errors": {},
        }
        
        total_latency = 0.0
        total_score = 0.0
        
        # Обработка батчами
        for i in range(0, len(proxies), batch_size):
            batch = proxies[i:i + batch_size]
            
            # Валидация
            results = await self._validator.validate_multiple(
                batch,
                skip_stage_b=skip_stage_b,
                show_progress=False,
            )
            
            # Обработка результатов
            for result in results:
                # Добавляем/обновляем прокси в БД
                proxy_id = await self._db.get_proxy_id(result.ip, result.port, result.protocol)
                
                if proxy_id is None:
                    proxy_id = await self._db.add_proxy(
                        result.ip, result.port, result.protocol,
                        source="collected",
                    )
                    if proxy_id > 0:
                        report["new"] += 1
                    else:
                        report["existing"] += 1
                        proxy_id = await self._db.get_proxy_id(result.ip, result.port, result.protocol)
                else:
                    report["existing"] += 1
                
                if proxy_id is None:
                    continue
                
                # Статистика по Stage A
                if result.stage in (ValidationStage.PASSED, ValidationStage.STAGE_A):
                    if result.passed:
                        report["passed_a"] += 1
                
                # Статистика по Stage B
                if result.stage == ValidationStage.STAGE_B:
                    if result.passed:
                        report["passed_b"] += 1
                    else:
                        report["failed"] += 1
                
                if not result.passed:
                    # Считаем ошибку
                    error_type = "unknown"
                    if result.error:
                        if "Timeout" in result.error:
                            error_type = "timeout"
                        elif "Connect" in result.error:
                            error_type = "connect"
                        elif "Proxy" in result.error:
                            error_type = "proxy"
                        elif "IP mismatch" in result.error:
                            error_type = "ip_mismatch"
                        else:
                            error_type = "other"
                    
                    report["errors"][error_type] = report["errors"].get(error_type, 0) + 1
                    
                    # Добавляем в карантин
                    await self._db.update_pool(proxy_id, ProxyPool.QUARANTINE)
                    report["quarantine"] += 1
                else:
                    # Определяем пул по score
                    score = result.metrics.calculate_score()
                    pool = result.metrics.get_pool()
                    
                    await self._db.update_metrics(proxy_id, result.metrics, score)
                    await self._db.update_pool(proxy_id, pool)
                    
                    if pool == ProxyPool.HOT:
                        report["hot"] += 1
                    elif pool == ProxyPool.WARM:
                        report["warm"] += 1
                    else:
                        report["quarantine"] += 1
                    
                    total_latency += result.metrics.latency_ms
                    total_score += score
                
                # Добавляем в историю
                await self._db.add_check_history(proxy_id, result)
        
        # Средние значения
        passed_count = report["hot"] + report["warm"]
        if passed_count > 0:
            report["avg_latency"] = round(total_latency / passed_count, 2)
            report["avg_score"] = round(total_score / passed_count, 2)
        
        # Сохраняем отчёт
        await self._save_report(report)
        
        return report
    
    async def refresh_quarantine(self, limit: int = 50) -> dict:
        """
        Recheck прокси из карантина
        
        Args:
            limit: Максимум прокси для проверки
        
        Returns:
            Отчёт о recheck
        """
        assert self._db is not None
        assert self._validator is not None
        
        # Получаем прокси из карантина
        quarantine = await self._db.get_quarantine_proxies(limit=limit)
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "type": "quarantine_recheck",
            "total": len(quarantine),
            "upgraded": 0,
            "still_bad": 0,
        }
        
        for proxy in quarantine:
            result = await self._validator.validate_full(
                proxy["ip"], proxy["port"], proxy["protocol"],
                skip_stage_b=True,
            )
            
            proxy_id = await self._db.get_proxy_id(proxy["ip"], proxy["port"], proxy["protocol"])
            
            if proxy_id is None:
                continue
            
            if result.passed:
                score = result.metrics.calculate_score()
                pool = result.metrics.get_pool()
                
                await self._db.update_metrics(proxy_id, result.metrics, score)
                await self._db.update_pool(proxy_id, pool)
                
                if pool != ProxyPool.QUARANTINE:
                    report["upgraded"] += 1
                else:
                    report["still_bad"] += 1
            else:
                report["still_bad"] += 1
            
            await self._db.add_check_history(proxy_id, result)
        
        await self._save_report(report)
        
        return report
    
    async def get_proxy(
        self,
        country: str | None = None,
        protocol: str | None = None,
        min_score: float = 50,
        use_quarantine: bool = False,
    ) -> dict | None:
        """
        Получить рабочую прокси
        
        Приоритет: HOT → WARM → QUARANTINE (если use_quarantine=True)
        
        Args:
            country: Код страны
            protocol: Протокол
            min_score: Минимальный score
            use_quarantine: Использовать ли карантин
        
        Returns:
            Прокси dict или None
        """
        assert self._db is not None
        
        # Сначала HOT
        hot = await self._db.get_hot_proxies(limit=10)
        
        for proxy in hot:
            if proxy["score"] >= min_score:
                if country and proxy["country"] != country:
                    continue
                if protocol and proxy["protocol"] != protocol:
                    continue
                return proxy
        
        # Потом WARM
        warm = await self._db.get_warm_proxies(limit=10)
        
        for proxy in warm:
            if proxy["score"] >= min_score:
                if country and proxy["country"] != country:
                    continue
                if protocol and proxy["protocol"] != protocol:
                    continue
                return proxy
        
        # Quarantine (если разрешено)
        if use_quarantine:
            quarantine = await self._db.get_quarantine_proxies(limit=10)
            
            for proxy in quarantine:
                if proxy["score"] >= min_score:
                    if country and proxy["country"] != country:
                        continue
                    if protocol and proxy["protocol"] != protocol:
                        continue
                    return proxy
        
        return None
    
    async def get_stats(self) -> dict:
        """Получить статистику"""
        assert self._db is not None
        
        return await self._db.get_stats()
    
    async def _save_report(self, report: dict) -> None:
        """Сохранить отчёт в JSON"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.report_path / f"report_{timestamp}.json"
        
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2, default=str)
        
        # Обновляем последний отчёт
        latest_file = self.report_path / "latest.json"
        with open(latest_file, "w") as f:
            json.dump(report, f, indent=2, default=str)


async def main():
    """Пример использования"""
    async with ProxyManager(max_concurrent=20) as manager:
        # Тестовые прокси
        test_proxies = [
            ("8.219.97.248", 80, "http"),
            ("185.199.229.156", 443, "https"),
            ("51.158.166.92", 8811, "http"),
        ]
        
        print("=== COLLECT → VALIDATE ===")
        report = await manager.collect_and_validate(test_proxies, skip_stage_b=False)
        print(json.dumps(report, indent=2))
        
        print("\n=== STATS ===")
        stats = await manager.get_stats()
        print(json.dumps(stats, indent=2))
        
        print("\n=== GET PROXY ===")
        proxy = await manager.get_proxy(min_score=50)
        if proxy:
            print(f"Got proxy: {proxy['protocol']}://{proxy['ip']}:{proxy['port']}")
            print(f"  Score: {proxy['score']:.1f}")
            print(f"  Country: {proxy['country']}")
        else:
            print("No suitable proxy found")


if __name__ == "__main__":
    asyncio.run(main())
