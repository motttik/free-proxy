"""
Proxy Pipeline v3.0

Полный цикл обработки прокси:
COLLECT → NORMALIZE → DEDUP → VALIDATE_FAST → VALIDATE_TARGETED → SCORE → POOL_UPDATE → REPORT
"""

import asyncio
import time
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from fp.validator import AsyncProxyValidator, ProxyMetrics, ProxyPool, ProxyValidationResult
from fp.database import ProxyDatabase
from fp.source_health import SourceHealthManager
from fp.config import ALL_SOURCES, ProxySource, SourceType
from fp.sources import get_parser

logger = logging.getLogger(__name__)


@dataclass
class NormalizedProxy:
    """Нормализованная прокси"""
    ip: str
    port: int
    protocol: str
    country: str | None = None
    anonymity: str | None = None
    source: str | None = None
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    
    def key(self) -> str:
        """Уникальный ключ для дедупа"""
        return f"{self.protocol}://{self.ip}:{self.port}"
    
    def to_proxy(self) -> tuple[str, int, str]:
        """Конвертировать в кортеж для валидатора"""
        return (self.ip, self.port, self.protocol)


@dataclass
class PipelineReport:
    """Отчёт о цикле pipeline"""
    timestamp: str = ""
    collected: int = 0
    normalized: int = 0
    deduped: int = 0
    validated_fast: int = 0
    validated_targeted: int = 0
    hot_count: int = 0
    warm_count: int = 0
    quarantine_count: int = 0
    failed: int = 0
    avg_latency: float = 0.0
    avg_score: float = 0.0
    top_fail_reasons: dict = field(default_factory=dict)
    source_stats: dict = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class ProxyPipeline:
    """
    Pipeline для обработки прокси
    
    Этапы:
    1. COLLECT - сбор из источников
    2. NORMALIZE - нормализация формата
    3. DEDUP - удаление дубликатов
    4. VALIDATE_FAST - быстрая проверка (Stage A)
    5. VALIDATE_TARGETED - боевая проверка (Stage B)
    6. SCORE - расчёт метрик
    7. POOL_UPDATE - распределение по пулам
    8. REPORT - генерация отчёта
    """
    
    def __init__(
        self,
        db_path: str = "~/.free-proxy/proxies.db",
        max_concurrent: int = 50,
        min_score_hot: float = 70,
        target_hot_proxies: int = 30,
    ) -> None:
        self.db_path = db_path
        self.max_concurrent = max_concurrent
        self.min_score_hot = min_score_hot
        self.target_hot_proxies = target_hot_proxies
        
        self._db: ProxyDatabase | None = None
        self._validator: AsyncProxyValidator | None = None
        self._health_manager: SourceHealthManager | None = None
    
    async def __aenter__(self) -> "ProxyPipeline":
        self._db = await ProxyDatabase(self.db_path).__aenter__()
        self._validator = await AsyncProxyValidator(self.max_concurrent).__aenter__()
        self._health_manager = SourceHealthManager()
        await self._health_manager.__aenter__()
        return self
    
    async def __aexit__(self, *args) -> None:
        if self._validator:
            await self._validator.__aexit__(*args)
        if self._health_manager:
            await self._health_manager.__aexit__(*args)
        if self._db:
            await self._db.__aexit__(*args)
    
    async def run_cycle(self, skip_targeted: bool = False, batch_size: int = 500) -> PipelineReport:
        """
        Запустить цикл pipeline с инкрементальной записью в БД
        """
        report = PipelineReport()
        
        # 1. COLLECT
        proxies = await self._collect(report)
        report.collected = len(proxies)
        
        # 3. DEDUP
        unique_proxies = await self._dedup(proxies)
        report.deduped = len(unique_proxies)
        
        if not unique_proxies:
            return report

        # Обработка батчами для предотвращения потери данных при таймауте
        for i in range(0, len(unique_proxies), batch_size):
            batch = unique_proxies[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1} ({len(batch)} proxies)...")
            
            # 4. VALIDATE_FAST (Stage A)
            fast_results = await self._validate_fast(batch, report)
            
            # 5. VALIDATE_TARGETED (Stage B)
            if not skip_targeted:
                # Берем только те, что прошли Stage A
                passed_a = [r for r in fast_results if r.passed]
                if passed_a:
                    targeted_results = await self._validate_targeted(passed_a, report)
                    # Объединяем результаты: те что провалили A и те что прошли/провалили B
                    failed_a = [r for r in fast_results if not r.passed]
                    batch_results = targeted_results + failed_a
                else:
                    batch_results = fast_results
            else:
                batch_results = fast_results
            
            # 6. SCORE + 7. POOL_UPDATE (Запись в БД после каждого батча!)
            await self._score_and_pool(batch_results, report)
            
            # Короткий отчет в лог после батча
            logger.info(f"Batch {i//batch_size + 1} done. HOT: {report.hot_count}, WARM: {report.warm_count}")
            
        return report
    
    async def _collect(self, report: PipelineReport) -> list[NormalizedProxy]:
        """COLLECT: Сбор из источников (асинхронный)"""
        all_proxies: list[NormalizedProxy] = []

        # Получаем доступные источники
        available = self._health_manager.get_available_sources() if self._health_manager else ALL_SOURCES

        # Используем ТОЛЬКО GitHub Raw источники (они стабильны)
        github_raw_sources = [
            s for s in available 
            if s["type"].value == "github_raw" and "TheSpeedX" in s["name"] or "monosans" in s["name"] or "clarketm" in s["name"]
        ]

        # Если GitHub источников нет, берём все доступные
        if not github_raw_sources:
            github_raw_sources = available

        # Собираем асинхронно
        for source in github_raw_sources:
            try:
                # Запускаем в executor чтобы не блокировать
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda s=source: get_parser(s).parse()
                )

                if result.success:
                    for proxy in result.proxies:
                        all_proxies.append(NormalizedProxy(
                            ip=proxy.ip,
                            port=proxy.port,
                            protocol=proxy.protocol,
                            country=proxy.country,
                            source=source["name"],
                        ))

                    # Записываем успех в health manager
                    if self._health_manager:
                        self._health_manager.record_success(source["url"], len(result.proxies))
                else:
                    if self._health_manager:
                        self._health_manager.record_failure(source["url"], "parse_error")

            except Exception as e:
                if self._health_manager:
                    self._health_manager.record_failure(source["url"], type(e).__name__)

        return all_proxies
    
    async def _dedup(self, proxies: list[NormalizedProxy]) -> list[NormalizedProxy]:
        """DEDUP: Удаление дубликатов"""
        seen: set[str] = set()
        unique: list[NormalizedProxy] = []
        
        for proxy in proxies:
            key = proxy.key()
            if key not in seen:
                seen.add(key)
                unique.append(proxy)
        
        return unique
    
    async def _validate_fast(
        self,
        proxies: list[NormalizedProxy],
        report: PipelineReport,
    ) -> list[ProxyValidationResult]:
        """VALIDATE_FAST: Stage A валидация"""
        if not self._validator:
            return []

        proxy_tuples = [p.to_proxy() for p in proxies]
        results = await self._validator.validate_multiple(proxy_tuples, skip_stage_b=True, show_progress=True)

        # Добавляем country и source из NormalizedProxy в результаты
        for i, result in enumerate(results):
            if i < len(proxies):
                result.country = proxies[i].country
                result.source = proxies[i].source

        # Считаем успешно прошедшие Stage A
        report.validated_fast += len([r for r in results if r.passed])

        # Считаем fail reasons
        for result in results:
            if not result.passed and result.error:
                error_type = "unknown"
                if "Timeout" in result.error:
                    error_type = "timeout"
                elif "Connect" in result.error or "Network" in result.error:
                    error_type = "network"
                elif "Proxy" in result.error:
                    error_type = "proxy"
                elif "IP mismatch" in result.error:
                    error_type = "ip_mismatch"
                elif "HTTP" in result.error:
                    error_type = "http_error"

                report.top_fail_reasons[error_type] = report.top_fail_reasons.get(error_type, 0) + 1

        return results
    
    async def _validate_targeted(
        self,
        passed_fast: list[ProxyValidationResult],
        report: PipelineReport,
    ) -> list[ProxyValidationResult]:
        """VALIDATE_TARGETED: Stage B валидация"""
        if not self._validator or not passed_fast:
            return []
        
        # Проверяем пачкой
        proxy_tuples = [(r.ip, r.port, r.protocol) for r in passed_fast]
        targeted_results = await self._validator.validate_multiple(proxy_tuples, skip_stage_b=False, show_progress=False)
        
        # Переносим метрики из Stage A в новые результаты
        for i, targeted in enumerate(targeted_results):
            targeted.metrics = passed_fast[i].metrics
            if not targeted.passed:
                report.top_fail_reasons["targeted_fail"] = report.top_fail_reasons.get("targeted_fail", 0) + 1
            else:
                report.validated_targeted += 1
        
        return targeted_results
    
    async def _score_and_pool(
        self,
        results: list[ProxyValidationResult],
        report: PipelineReport,
    ) -> None:
        """SCORE + POOL_UPDATE: Расчёт метрик и распределение по пулам"""
        if not self._db:
            return

        total_score = 0.0
        total_latency = 0.0

        for result in results:
            # Получаем или создаём прокси в БД
            proxy_id = await self._db.get_proxy_id(result.ip, result.port, result.protocol)

            if proxy_id is None:
                proxy_id = await self._db.add_proxy(
                    result.ip, result.port, result.protocol,
                    country=result.country,
                    source=result.ip,
                )

            if proxy_id is None:
                continue

            # Получаем текущие метрики из БД (если есть)
            db_metrics = await self._db._conn.execute(
                "SELECT latency_ms, uptime, success_rate, ban_rate, total_checks, successful_checks FROM metrics WHERE proxy_id = ?",
                (proxy_id,)
            )
            row = await db_metrics.fetchone()
            
            if row:
                # Обновляем существующие метрики
                db_latency, db_uptime, db_success, db_ban, db_total, db_success_count = row
                
                # Merge с новыми результатами
                result.metrics.latency_ms = db_latency if db_latency > 0 else result.metrics.latency_ms
                result.metrics.uptime = db_uptime
                result.metrics.success_rate = db_success
                result.metrics.ban_rate = db_ban
                result.metrics.total_checks = db_total
                result.metrics.successful_checks = db_success_count
                
                # Обновляем после текущей проверки
                result.metrics.update(
                    success=result.passed,
                    latency=result.latency_ms,
                    status_code=200 if result.passed else None,
                    is_first_check=(db_total == 0)
                )
            else:
                # Новая прокси — обновляем после первой проверки
                result.metrics.update(
                    success=result.passed,
                    latency=result.latency_ms,
                    is_first_check=True
                )

            # Расчёт score
            score = result.metrics.calculate_score()
            pool = result.metrics.get_pool()

            # Для НОВЫХ прокси (первая проверка) даём презумпцию невиновности
            # Если прокси не прошла первую проверку, всё равно даём WARM вместо QUARANTINE
            if not result.passed and result.metrics.total_checks <= 1:
                # Не отправляем в карантин после первой неудачи
                pool = ProxyPool.WARM

            # Если score высокий (≥80) → HOT, даже если Stage A не прошёл
            # Это для стабильных GitHub Raw источников
            if score >= 80:
                pool = ProxyPool.HOT

            # Обновляем БД
            await self._db.update_metrics(proxy_id, result.metrics, score)
            await self._db.update_pool(proxy_id, pool)
            await self._db.add_check_history(proxy_id, result)

            # Статистика
            total_score += score
            total_latency += result.metrics.latency_ms

            if pool == ProxyPool.HOT:
                report.hot_count += 1
            elif pool == ProxyPool.WARM:
                report.warm_count += 1
            else:
                report.quarantine_count += 1

            if not result.passed:
                report.failed += 1
        
        # Средние значения
        if len(results) > 0:
            report.avg_score = total_score / len(results)
            report.avg_latency = total_latency / len(results)
    
    async def _generate_report(self, report: PipelineReport) -> None:
        """REPORT: Генерация и сохранение отчёта"""
        report_path = Path("~/.free-proxy/reports").expanduser()
        report_path.mkdir(parents=True, exist_ok=True)
        
        # Сохраняем JSON
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = report_path / f"pipeline_{timestamp}.json"
        
        report_dict = {
            "timestamp": report.timestamp,
            "collected": report.collected,
            "normalized": report.normalized,
            "deduped": report.deduped,
            "validated_fast": report.validated_fast,
            "validated_targeted": report.validated_targeted,
            "hot_count": report.hot_count,
            "warm_count": report.warm_count,
            "quarantine_count": report.quarantine_count,
            "failed": report.failed,
            "avg_latency": round(report.avg_latency, 2),
            "avg_score": round(report.avg_score, 2),
            "top_fail_reasons": report.top_fail_reasons,
        }
        
        import json
        with open(report_file, "w") as f:
            json.dump(report_dict, f, indent=2)
        
        # Latest report
        latest_file = report_path / "latest_pipeline.json"
        with open(latest_file, "w") as f:
            json.dump(report_dict, f, indent=2)
        
        # Сохраняем health stats
        if self._health_manager:
            await self._health_manager.save_to_db()


async def main():
    """Пример использования"""
    async with ProxyPipeline(max_concurrent=30) as pipeline:
        print("=== Running Pipeline Cycle ===")
        report = await pipeline.run_cycle(skip_targeted=False)
        
        print(f"Collected: {report.collected}")
        print(f"Deduped: {report.deduped}")
        print(f"Validated Fast: {report.validated_fast}")
        print(f"Validated Targeted: {report.validated_targeted}")
        print(f"HOT: {report.hot_count}")
        print(f"WARM: {report.warm_count}")
        print(f"Quarantine: {report.quarantine_count}")
        print(f"Failed: {report.failed}")
        print(f"Avg Score: {report.avg_score:.1f}")
        print(f"Avg Latency: {report.avg_latency:.0f}ms")
        
        if report.top_fail_reasons:
            print("\nTop Fail Reasons:")
            for reason, count in sorted(report.top_fail_reasons.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"  {reason}: {count}")


if __name__ == "__main__":
    asyncio.run(main())
