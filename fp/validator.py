"""
Free Proxy v3.1 - High Performance Proxy Validator
Uses aiohttp for mass validation with persistent sessions and SOCKS support.
"""

import asyncio
import time
import logging
import json
from dataclasses import dataclass, field
from typing import Literal
from enum import Enum

import aiohttp
try:
    from aiohttp_socks import ProxyConnector
    HAS_SOCKS = True
except ImportError:
    HAS_SOCKS = False

logger = logging.getLogger(__name__)

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
        
        Формула с учётом количества проверок:
        - Мало проверок (<5) → более мягкая оценка
        - Много проверок (≥5) → полная формула
        """
        latency_score = max(0, 100 - self.latency_ms / 20)
        
        # Если мало проверок, даём "кредит доверия"
        if self.total_checks < 3:
            # Для новых прокси используем оптимистичную оценку
            base_score = 70  # Базовый score для новых
            latency_bonus = latency_score * 0.25
            return max(50, min(85, base_score + latency_bonus))
        
        # Стандартная формула для проверенных прокси
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
    
    def update(self, success: bool, latency: float, status_code: int | None = None, is_first_check: bool = False) -> None:
        """
        Обновить метрики после проверки
        
        Args:
            success: Успешна ли проверка
            latency: Задержка в мс
            status_code: HTTP статус код
            is_first_check: Это первая проверка прокси?
        """
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

        # Обновляем latency (EMA)
        if latency > 0:
            self.latency_ms = (self.latency_ms * 0.7) + (latency * 0.3)

        # Обновляем uptime (последние 10 проверок)
        recent_window = min(10, self.total_checks)
        recent_success = min(self.successful_checks, recent_window)
        self.uptime = (recent_success / recent_window) * 100 if recent_window > 0 else 100
        
        # ПРЕЗУМПЦИЯ НЕВИНОВНОСТИ для новых прокси
        # Если это первая проверка и она неудачна, не обнуляем uptime/success_rate полностью
        if is_first_check and not success:
            self.uptime = max(self.uptime, 50)  # Минимум 50% для первой проверки
            self.success_rate = max(self.success_rate, 50)  # Минимум 50%


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
    Высокопроизводительный асинхронный валидатор прокси
    """
    
    # Целевые домены для Stage B (микс нейтральных и боевых)
    TARGET_DOMAINS = [
        "http://www.google.com",
        "http://www.ozon.ru",
        "http://www.wildberries.ru",
        "http://www.avito.ru",
    ]
    
    # Таймауты
    STAGE_A_TIMEOUT = 3.0
    STAGE_B_TIMEOUT = 7.0
    
    def __init__(
        self,
        max_concurrent: int = 200,
        stage_a_url: str = "http://icanhazip.com",
    ) -> None:
        self.max_concurrent = max_concurrent
        self.stage_a_url = stage_a_url
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._session: aiohttp.ClientSession | None = None
    
    async def __aenter__(self) -> "AsyncProxyValidator":
        self._session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=self.max_concurrent, ssl=False),
            timeout=aiohttp.ClientTimeout(total=self.STAGE_B_TIMEOUT + 5),
            headers={"User-Agent": "FreeProxy/3.1"}
        )
        return self
    
    async def __aexit__(self, *args) -> None:
        if self._session:
            await self._session.close()
    
    def _get_proxy_url(self, protocol: str, ip: str, port: int) -> str:
        return f"{protocol}://{ip}:{port}"

    async def validate_stage_a(
        self,
        ip: str,
        port: int,
        protocol: str = "http",
    ) -> ProxyValidationResult:
        """
        Stage A: Быстрая валидация
        """
        proxy_url = self._get_proxy_url(protocol, ip, port)
        result = ProxyValidationResult(
            ip=ip, port=port, protocol=protocol,
            stage=ValidationStage.STAGE_A, passed=False
        )
        
        async with self._semaphore:
            if not self._session:
                result.error = "Session not initialized"
                return result

            start_time = time.perf_counter()
            try:
                if protocol.startswith("socks"):
                    if not HAS_SOCKS:
                        result.error = "SOCKS support not installed"
                        return result
                    connector = ProxyConnector.from_url(proxy_url, ssl=False)
                    async with aiohttp.ClientSession(connector=connector) as s:
                        async with s.get(self.stage_a_url, timeout=self.STAGE_A_TIMEOUT) as response:
                            status = response.status
                            data = await response.json()
                else:
                    async with self._session.get(self.stage_a_url, proxy=proxy_url, timeout=self.STAGE_A_TIMEOUT) as response:
                        status = response.status
                        data = await response.json()
                
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                
                if status != 200:
                    result.error = f"HTTP {status}"
                    result.metrics.update(success=False, latency=elapsed_ms, status_code=status)
                    return result
                
                # icanhazip возвращает просто строку с IP
                response_ip = (await response.text()).strip()
                if response_ip != ip:
                    result.error = f"IP mismatch: {response_ip} != {ip}"
                    result.metrics.update(success=False, latency=elapsed_ms, status_code=200)
                    return result
                
                result.passed = True
                result.latency_ms = elapsed_ms
                result.metrics.update(success=True, latency=elapsed_ms, status_code=200)
                
            except asyncio.TimeoutError:
                result.error = "Timeout"
                result.metrics.update(success=False, latency=self.STAGE_A_TIMEOUT * 1000)
            except Exception as e:
                result.error = f"Error: {type(e).__name__}"
                result.metrics.update(success=False, latency=5000)
        
        return result

    async def validate_stage_b(
        self,
        ip: str,
        port: int,
        protocol: str = "http",
    ) -> ProxyValidationResult:
        """
        Stage B: Боевая валидация
        """
        proxy_url = self._get_proxy_url(protocol, ip, port)
        result = ProxyValidationResult(
            ip=ip, port=port, protocol=protocol,
            stage=ValidationStage.STAGE_B, passed=False
        )
        
        target_results = {}
        successful = 0
        total_latency = 0.0
        
        async with self._semaphore:
            if not self._session:
                return result

            if protocol.startswith("socks"):
                if not HAS_SOCKS:
                    result.error = "SOCKS support not installed"
                    return result
                connector = ProxyConnector.from_url(proxy_url, ssl=False)
                session_to_use = aiohttp.ClientSession(connector=connector)
            else:
                session_to_use = self._session

            try:
                for domain in self.TARGET_DOMAINS:
                    start_time = time.perf_counter()
                    try:
                        get_kwargs = {"timeout": self.STAGE_B_TIMEOUT}
                        if not protocol.startswith("socks"):
                            get_kwargs["proxy"] = proxy_url

                        async with session_to_use.head(domain, **get_kwargs) as response:
                            elapsed_ms = (time.perf_counter() - start_time) * 1000
                            total_latency += elapsed_ms
                            if response.status < 500:
                                target_results[domain] = {"status": "ok", "code": response.status, "latency": elapsed_ms}
                                successful += 1
                            else:
                                target_results[domain] = {"status": "fail", "code": response.status, "latency": elapsed_ms}
                    except Exception:
                        target_results[domain] = {"status": "error", "latency": self.STAGE_B_TIMEOUT * 1000}
                
                if protocol.startswith("socks"):
                    await session_to_use.close()

            except Exception as e:
                result.error = f"Client error: {str(e)}"
                return result
        
        avg_latency = total_latency / len(self.TARGET_DOMAINS) if total_latency > 0 else 0
        result.target_results = target_results
        result.latency_ms = avg_latency
        
        if successful >= 1:
            result.passed = True
            result.metrics.update(success=True, latency=avg_latency)
        else:
            result.error = f"Targets not accessible (0/{len(self.TARGET_DOMAINS)})"
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
        """
        result_a = await self.validate_stage_a(ip, port, protocol)
        if not result_a.passed:
            return result_a
        
        if not skip_stage_b:
            result_b = await self.validate_stage_b(ip, port, protocol)
            result_a.latency_ms = (result_a.latency_ms + result_b.latency_ms) / 2
            result_b.metrics = result_a.metrics
            result_b.stage = ValidationStage.PASSED if result_b.passed else ValidationStage.FAILED
            return result_b
        
        result_a.stage = ValidationStage.PASSED if result_a.passed else ValidationStage.FAILED
        return result_a
    
    async def validate_multiple(
        self,
        proxies: list[tuple[str, int, str]],
        skip_stage_b: bool = False,
        show_progress: bool = False,
    ) -> list[ProxyValidationResult]:
        """
        Валидировать несколько прокси
        """
        tasks = [
            self.validate_full(ip, port, protocol, skip_stage_b)
            for ip, port, protocol in proxies
        ]
        
        if show_progress:
            try:
                from tqdm.asyncio import tqdm_asyncio
                return await tqdm_asyncio.gather(*tasks, desc="Validation", unit="proxy")
            except ImportError:
                return await asyncio.gather(*tasks)
        
        return await asyncio.gather(*tasks)
