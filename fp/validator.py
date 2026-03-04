"""
Free Proxy v3.0 - Advanced Proxy Validator with 2-Stage Validation

2-этапная валидация:
- Stage A: Быстрая проверка (httpbin, latency, timeout)
- Stage B: Боевая проверка (целевые домены: OZON, WB, Avito)
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Literal
from enum import Enum

import httpx


class ValidationStage(str, Enum):
    """Этапы валидации"""
    PENDING = "pending"
    STAGE_A = "stage_a"
    STAGE_B = "stage_b"
    PASSED = "passed"
    FAILED = "failed"


class ProxyPool(str, Enum):
    """Пулы прокси"""
    HOT = "hot"  # score 80-100
    WARM = "warm"  # score 50-79
    QUARANTINE = "quarantine"  # score 0-49


@dataclass
class ProxyMetrics:
    """Метрики прокси"""
    latency_ms: float = 0.0
    uptime: float = 100.0
    success_rate: float = 100.0
    ban_rate: float = 0.0
    total_checks: int = 0
    successful_checks: int = 0
    failed_checks: int = 0
    last_check: float = field(default_factory=time.time)
    last_success: float = 0.0
    
    def calculate_score(self) -> float:
        """
        Расчёт общего score (0-100)
        
        Формула:
        score = 0.3*uptime + 0.25*latency_score + 0.3*success_rate - 0.15*ban_rate
        
        latency_score = max(0, 100 - latency_ms/20)
        """
        latency_score = max(0, 100 - self.latency_ms / 20)
        
        score = (
            0.30 * self.uptime +
            0.25 * latency_score +
            0.30 * self.success_rate -
            0.15 * self.ban_rate
        )
        
        return max(0, min(100, score))
    
    def get_pool(self) -> ProxyPool:
        """Определить пул по score"""
        score = self.calculate_score()
        
        if score >= 80:
            return ProxyPool.HOT
        elif score >= 50:
            return ProxyPool.WARM
        else:
            return ProxyPool.QUARANTINE
    
    def update(self, success: bool, latency: float, status_code: int | None = None) -> None:
        """Обновить метрики после проверки"""
        self.total_checks += 1
        self.last_check = time.time()
        
        if success:
            self.successful_checks += 1
            self.last_success = time.time()
        else:
            self.failed_checks += 1
        
        # Обновляем success_rate (скользящее среднее)
        if self.total_checks > 0:
            self.success_rate = (self.successful_checks / self.total_checks) * 100
        
        # Обновляем ban_rate (403/429 считаем баном)
        if status_code and status_code in (403, 429, 401):
            self.ban_rate = min(100, self.ban_rate + 5)
        
        # Обновляем latency (exponential moving average)
        self.latency_ms = (self.latency_ms * 0.7) + (latency * 0.3)
        
        # Обновляем uptime (последние 10 проверок)
        recent_window = min(10, self.total_checks)
        recent_success = min(self.successful_checks, recent_window)
        self.uptime = (recent_success / recent_window) * 100 if recent_window > 0 else 100


@dataclass
class ProxyValidationResult:
    """Результат валидации"""
    ip: str
    port: int
    protocol: str
    stage: ValidationStage
    passed: bool
    latency_ms: float = 0.0
    error: str | None = None
    target_results: dict = field(default_factory=dict)
    metrics: ProxyMetrics = field(default_factory=ProxyMetrics)
    
    def __str__(self) -> str:
        status = "✓" if self.passed else "✗"
        return f"{status} {self.protocol}://{self.ip}:{self.port} [{self.stage.value}] {self.latency_ms:.0f}ms"


class AsyncProxyValidator:
    """
    Асинхронный валидатор прокси с 2-этапной проверкой
    """
    
    # Целевые домены для Stage B
    TARGET_DOMAINS = [
        "https://www.ozon.ru",
        "https://www.wildberries.ru",
        "https://www.avito.ru",
        "https://www.google.com",
    ]
    
    # Таймауты
    STAGE_A_TIMEOUT = 2.0
    STAGE_B_TIMEOUT = 5.0
    
    def __init__(
        self,
        max_concurrent: int = 50,
        stage_a_url: str = "https://httpbin.org/ip",
    ) -> None:
        self.max_concurrent = max_concurrent
        self.stage_a_url = stage_a_url
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._client: httpx.AsyncClient | None = None
    
    async def __aenter__(self) -> "AsyncProxyValidator":
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=5.0,
                read=10.0,
                write=5.0,
                pool=10.0,
            ),
            limits=httpx.Limits(max_keepalive_connections=100, max_connections=200),
            follow_redirects=False,
        )
        return self
    
    async def __aexit__(self, *args) -> None:
        if self._client:
            await self._client.aclose()
    
    async def validate_stage_a(
        self,
        ip: str,
        port: int,
        protocol: str = "http",
    ) -> ProxyValidationResult:
        """
        Stage A: Быстрая валидация
        
        - Проверка httpbin.org/ip
        - Замер latency
        - Timeout < 2s
        - Status == 200
        - IP match
        """
        proxy_url = f"{protocol}://{ip}:{port}"
        result = ProxyValidationResult(
            ip=ip, port=port, protocol=protocol,
            stage=ValidationStage.STAGE_A, passed=False
        )
        
        async with self._semaphore:
            start_time = time.perf_counter()
            
            try:
                response = await self._client.get(
                    self.stage_a_url,
                    proxy=proxy_url,
                    timeout=self.STAGE_A_TIMEOUT,
                )
                
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                
                # Проверка статуса
                if response.status_code != 200:
                    result.error = f"HTTP {response.status_code}"
                    result.metrics.update(success=False, latency=elapsed_ms, status_code=response.status_code)
                    return result
                
                # Проверка IP
                try:
                    data = response.json()
                    response_ip = data.get("origin", "").split(",")[0].strip()
                    
                    if response_ip != ip:
                        result.error = f"IP mismatch: {response_ip} != {ip}"
                        result.metrics.update(success=False, latency=elapsed_ms, status_code=200)
                        return result
                        
                except Exception as e:
                    result.error = f"JSON parse error: {e}"
                    result.metrics.update(success=False, latency=elapsed_ms, status_code=200)
                    return result
                
                # Успех
                result.passed = True
                result.latency_ms = elapsed_ms
                result.metrics.update(success=True, latency=elapsed_ms, status_code=200)
                
            except httpx.TimeoutException:
                result.error = f"Timeout >{self.STAGE_A_TIMEOUT}s"
                result.metrics.update(success=False, latency=10000, status_code=None)
                
            except httpx.ConnectError as e:
                result.error = f"Connect error: {e}"
                result.metrics.update(success=False, latency=10000, status_code=None)
                
            except httpx.ProxyError as e:
                result.error = f"Proxy error: {e}"
                result.metrics.update(success=False, latency=10000, status_code=None)
                
            except Exception as e:
                result.error = f"Unexpected error: {e}"
                result.metrics.update(success=False, latency=10000, status_code=None)
        
        return result
    
    async def validate_stage_b(
        self,
        ip: str,
        port: int,
        protocol: str = "http",
    ) -> ProxyValidationResult:
        """
        Stage B: Боевая валидация
        
        - HEAD запросы к целевым доменам
        - Timeout < 5s
        - Мягкий тест (4xx = warning, 5xx = fail)
        - Требуется ≥2 из 4 доменов
        """
        proxy_url = f"{protocol}://{ip}:{port}"
        result = ProxyValidationResult(
            ip=ip, port=port, protocol=protocol,
            stage=ValidationStage.STAGE_B, passed=False
        )
        
        target_results = {}
        successful = 0
        total_latency = 0.0
        
        async with self._semaphore:
            for domain in self.TARGET_DOMAINS:
                start_time = time.perf_counter()
                
                try:
                    response = await self._client.head(
                        domain,
                        proxy=proxy_url,
                        timeout=self.STAGE_B_TIMEOUT,
                    )
                    
                    elapsed_ms = (time.perf_counter() - start_time) * 1000
                    total_latency += elapsed_ms
                    
                    # 2xx = успех
                    if 200 <= response.status_code < 300:
                        target_results[domain] = {"status": "ok", "code": response.status_code, "latency": elapsed_ms}
                        successful += 1
                    
                    # 4xx = warning (считаем как успех для мягкого теста)
                    elif 400 <= response.status_code < 500:
                        target_results[domain] = {"status": "warning", "code": response.status_code, "latency": elapsed_ms}
                        successful += 1
                    
                    # 5xx = fail
                    elif response.status_code >= 500:
                        target_results[domain] = {"status": "fail", "code": response.status_code, "latency": elapsed_ms}
                    
                except httpx.TimeoutException:
                    target_results[domain] = {"status": "timeout", "code": None, "latency": 5000}
                    
                except httpx.ConnectError:
                    target_results[domain] = {"status": "connect_error", "code": None, "latency": 5000}
                    
                except Exception as e:
                    target_results[domain] = {"status": "error", "error": str(e), "latency": 5000}
        
        # Средняя latency
        avg_latency = total_latency / len(self.TARGET_DOMAINS) if total_latency > 0 else 0
        
        result.target_results = target_results
        result.latency_ms = avg_latency
        
        # Требуем ≥2 успешных домена
        if successful >= 2:
            result.passed = True
            result.metrics.update(success=True, latency=avg_latency)
        else:
            result.error = f"Only {successful}/{len(self.TARGET_DOMAINS)} targets accessible"
            result.metrics.update(success=False, latency=avg_latency)
        
        return result
    
    async def validate_full(
        self,
        ip: str,
        port: int,
        protocol: str = "http",
        skip_stage_b: bool = False,
    ) -> ProxyValidationResult:
        """
        Полная 2-этапная валидация
        
        Args:
            skip_stage_b: Если True, только Stage A
        
        Returns:
            ProxyValidationResult с полным результатом
        """
        # Stage A
        result_a = await self.validate_stage_a(ip, port, protocol)
        
        if not result_a.passed:
            return result_a
        
        # Stage B (если нужен)
        if not skip_stage_b:
            result_b = await self.validate_stage_b(ip, port, protocol)
            
            # Объединяем результаты
            result_a.latency_ms = (result_a.latency_ms + result_b.latency_ms) / 2
            result_b.metrics = result_a.metrics  # Сохраняем историю метрик
            
            if result_b.passed:
                result_b.stage = ValidationStage.PASSED
            else:
                result_b.stage = ValidationStage.FAILED
            
            return result_b
        
        # Только Stage A
        if result_a.passed:
            result_a.stage = ValidationStage.PASSED
        else:
            result_a.stage = ValidationStage.FAILED
        
        return result_a
    
    async def validate_multiple(
        self,
        proxies: list[tuple[str, int, str]],
        skip_stage_b: bool = False,
        show_progress: bool = False,
    ) -> list[ProxyValidationResult]:
        """
        Валидировать несколько прокси
        
        Args:
            proxies: Список кортежей (ip, port, protocol)
            skip_stage_b: Только Stage A
            show_progress: Показывать прогресс
        
        Returns:
            Список результатов
        """
        tasks = [
            self.validate_full(ip, port, protocol, skip_stage_b)
            for ip, port, protocol in proxies
        ]
        
        results = []
        
        if show_progress:
            try:
                from tqdm.asyncio import tqdm_asyncio
                results = await tqdm_asyncio.gather(*tasks, desc="Validation", unit="proxy")
            except ImportError:
                # Без прогресса
                results = await asyncio.gather(*tasks)
        else:
            results = await asyncio.gather(*tasks)
        
        return results


async def main():
    """Пример использования"""
    test_proxies = [
        ("8.219.97.248", 80, "http"),
        ("185.199.229.156", 443, "https"),
    ]
    
    async with AsyncProxyValidator(max_concurrent=10) as validator:
        print("=== Stage A Only ===")
        results = await validator.validate_multiple(test_proxies, skip_stage_b=True, show_progress=True)
        
        for r in results:
            print(r)
            if r.passed:
                print(f"  Score: {r.metrics.calculate_score():.1f}")
                print(f"  Pool: {r.metrics.get_pool().value}")
        
        print("\n=== Full Validation (Stage A + B) ===")
        results = await validator.validate_multiple(test_proxies, skip_stage_b=False, show_progress=True)
        
        for r in results:
            print(r)
            if r.passed:
                print(f"  Targets: {sum(1 for v in r.target_results.values() if v.get('status') in ('ok', 'warning'))}/{len(validator.TARGET_DOMAINS)}")
                print(f"  Score: {r.metrics.calculate_score():.1f}")
                print(f"  Pool: {r.metrics.get_pool().value}")


if __name__ == "__main__":
    asyncio.run(main())
