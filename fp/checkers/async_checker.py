"""
Async Proxy Checker Module

Асинхронная проверка прокси с использованием aiohttp
Быстрая проверка множества прокси параллельно
"""

import asyncio
import logging
from typing import Protocol

import aiohttp
from aiohttp import ClientError, ClientTimeout, ServerDisconnectedError

from fp.sources.base import Proxy
from fp.errors import ProxyValidationError

logger = logging.getLogger(__name__)


class AsyncProxyChecker:
    """
    Асинхронный проверщик прокси
    
    Использует aiohttp для параллельной проверки множества прокси
    """
    
    DEFAULT_TEST_URL = "https://httpbin.org/ip"
    DEFAULT_TIMEOUT = 5.0
    DEFAULT_MAX_CONCURRENT = 20
    
    def __init__(
        self,
        test_url: str | None = None,
        timeout: float | None = None,
        max_concurrent: int | None = None,
    ) -> None:
        """
        Инициализация проверщика
        
        Args:
            test_url: URL для проверки
            timeout: таймаут подключения в секундах
            max_concurrent: макс. количество одновременных проверок
        """
        self.test_url = test_url or self.DEFAULT_TEST_URL
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self.max_concurrent = max_concurrent or self.DEFAULT_MAX_CONCURRENT
        
        # Semaphore для ограничения параллелизма
        self._semaphore: asyncio.Semaphore | None = None
    
    async def check(self, proxy: Proxy, session: aiohttp.ClientSession) -> bool:
        """
        Проверить прокси на работоспособность
        
        Args:
            proxy: прокси для проверки
            session: aiohttp сессия
            
        Returns:
            True если прокси работает
        """
        proxy_url = self._get_proxy_url(proxy)
        
        try:
            async with self._semaphore:  # type: ignore
                timeout = ClientTimeout(total=self.timeout)
                
                async with session.get(
                    self.test_url,
                    proxy=proxy_url,
                    timeout=timeout,
                    allow_redirects=False,
                ) as response:
                    # Проверяем статус
                    if response.status != 200:
                        logger.debug(f"[{proxy}] HTTP {response.status}")
                        return False
                    
                    # Проверяем IP
                    try:
                        data = await response.json()
                        response_ip = data.get("origin", "").split(",")[0].strip()
                        
                        if response_ip and response_ip != proxy.ip:
                            logger.debug(f"[{proxy}] IP mismatch: {response_ip} != {proxy.ip}")
                            return False
                            
                    except Exception:
                        pass
                    
                    logger.debug(f"[{proxy}] OK")
                    return True
                    
        except asyncio.TimeoutError:
            logger.debug(f"[{proxy}] Timeout")
            return False
            
        except ServerDisconnectedError:
            logger.debug(f"[{proxy}] Server disconnected")
            return False
            
        except ClientError as e:
            logger.debug(f"[{proxy}] Client error: {type(e).__name__}")
            return False
        
        except Exception as e:
            logger.debug(f"[{proxy}] Unexpected error: {type(e).__name__}")
            return False
    
    async def check_multiple(
        self,
        proxies: list[Proxy],
        stop_on_first: bool = False,
        show_progress: bool = False,
    ) -> list[Proxy]:
        """
        Проверить несколько прокси параллельно
        
        Args:
            proxies: список прокси для проверки
            stop_on_first: остановиться после первого рабочего
            show_progress: показывать прогресс
            
        Returns:
            список рабочих прокси
        """
        self._semaphore = asyncio.Semaphore(self.max_concurrent)
        
        working: list[Proxy] = []
        checked = 0
        total = len(proxies)
        
        # Создаем сессию
        connector = aiohttp.TCPConnector(limit=self.max_concurrent)
        async with aiohttp.ClientSession(connector=connector) as session:
            # Создаем задачи
            tasks = [self.check(proxy, session) for proxy in proxies]
            
            # Выполняем с прогрессом или без
            if show_progress:
                try:
                    from tqdm import tqdm
                    
                    with tqdm(total=total, desc="Проверка прокси") as pbar:
                        for coro in asyncio.as_completed(tasks):
                            result = await coro
                            proxy = proxies[checked]
                            
                            if result:
                                working.append(proxy)
                                
                                if stop_on_first:
                                    logger.info(f"Найдена рабочая прокси: {proxy}")
                                    return working
                            
                            checked += 1
                            pbar.update(1)
                            
                except ImportError:
                    # tqdm не установлен, без прогресса
                    working = await self._run_tasks(tasks, proxies, stop_on_first)
            else:
                working = await self._run_tasks(tasks, proxies, stop_on_first)
        
        return working
    
    async def _run_tasks(
        self,
        tasks: list,
        proxies: list[Proxy],
        stop_on_first: bool,
    ) -> list[Proxy]:
        """Выполнить задачи проверки"""
        working: list[Proxy] = []
        
        for i, coro in enumerate(asyncio.as_completed(tasks)):
            result = await coro
            proxy = proxies[i]
            
            if result:
                working.append(proxy)
                
                if stop_on_first:
                    return working
        
        return working
    
    def _get_proxy_url(self, proxy: Proxy) -> str:
        """
        Получить URL прокси для aiohttp
        
        Args:
            proxy: прокси
            
        Returns:
            URL вида "http://ip:port" или "socks5://ip:port"
        """
        protocol = proxy.protocol.lower()
        
        # aiohttp поддерживает socks через aiohttp-socks
        if protocol.startswith("socks"):
            return f"{protocol}://{proxy.ip}:{proxy.port}"
        
        return f"http://{proxy.ip}:{proxy.port}"
    
    async def quick_check(
        self,
        ip: str,
        port: int,
        protocol: str = "http",
    ) -> bool:
        """
        Быстрая проверка прокси по IP:PORT
        
        Args:
            ip: IP адрес
            port: порт
            protocol: протокол
            
        Returns:
            True если прокси работает
        """
        proxy = Proxy(ip=ip, port=port, protocol=protocol)
        
        connector = aiohttp.TCPConnector(limit=1)
        async with aiohttp.ClientSession(connector=connector) as session:
            return await self.check(proxy, session)
