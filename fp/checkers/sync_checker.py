"""
Sync Proxy Checker Module

Синхронная проверка прокси (для обратной совместимости)
"""

import logging
import socket
from typing import Protocol

import requests
from requests.exceptions import RequestException, Timeout, ConnectionError, ProxyError

from fp.sources.base import Proxy
from fp.errors import ProxyValidationError

logger = logging.getLogger(__name__)


class SyncProxyChecker:
    """
    Синхронный проверщик прокси
    
    Проверяет работоспособность прокси подключением к тестовому URL
    """
    
    DEFAULT_TEST_URL = "https://httpbin.org/ip"
    DEFAULT_TIMEOUT = 5.0
    
    def __init__(
        self,
        test_url: str | None = None,
        timeout: float | None = None,
        check_google: bool = False,
    ) -> None:
        """
        Инициализация проверщика
        
        Args:
            test_url: URL для проверки (по умолчанию httpbin.org/ip)
            timeout: таймаут подключения в секундах
            check_google: проверять поддержку Google (устаревший параметр)
        """
        self.test_url = test_url or self.DEFAULT_TEST_URL
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self.check_google = check_google
        
        # Сессия для переиспользования соединений
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })
    
    def check(self, proxy: Proxy) -> bool:
        """
        Проверить прокси на работоспособность
        
        Args:
            proxy: прокси для проверки
            
        Returns:
            True если прокси работает
        """
        proxy_url = self._get_proxy_url(proxy)
        
        try:
            response = self._session.get(
                self.test_url,
                proxies={proxy.protocol: proxy_url},
                timeout=self.timeout,
                stream=True,
            )
            
            # Проверяем, что ответ успешный
            if response.status_code != 200:
                logger.debug(f"[{proxy}] HTTP {response.status_code}")
                return False
            
            # Проверяем, что IP совпадает с прокси
            try:
                data = response.json()
                response_ip = data.get("origin", "").split(",")[0].strip()
                
                if response_ip and response_ip != proxy.ip:
                    logger.debug(f"[{proxy}] IP mismatch: {response_ip} != {proxy.ip}")
                    return False
                    
            except Exception:
                # Если не удалось распарсить JSON, считаем что OK
                pass
            
            logger.debug(f"[{proxy}] OK")
            return True
            
        except Timeout:
            logger.debug(f"[{proxy}] Timeout")
            return False
            
        except ConnectionError as e:
            logger.debug(f"[{proxy}] Connection error: {e}")
            return False
            
        except ProxyError as e:
            logger.debug(f"[{proxy}] Proxy error: {e}")
            return False
            
        except RequestException as e:
            logger.debug(f"[{proxy}] Request error: {e}")
            return False
        
        except Exception as e:
            logger.debug(f"[{proxy}] Unexpected error: {e}")
            return False
    
    def check_multiple(
        self,
        proxies: list[Proxy],
        max_concurrent: int = 1,
        stop_on_first: bool = False,
    ) -> list[Proxy]:
        """
        Проверить несколько прокси
        
        Args:
            proxies: список прокси для проверки
            max_concurrent: макс. количество одновременных проверок (не используется в sync версии)
            stop_on_first: остановиться после первого рабочего
            
        Returns:
            список рабочих прокси
        """
        working: list[Proxy] = []
        
        for i, proxy in enumerate(proxies, 1):
            logger.info(f"Проверка прокси {i}/{len(proxies)}: {proxy}")
            
            if self.check(proxy):
                working.append(proxy)
                
                if stop_on_first:
                    logger.info(f"Найдена рабочая прокси: {proxy}")
                    break
        
        return working
    
    def _get_proxy_url(self, proxy: Proxy) -> str:
        """
        Получить URL прокси для requests
        
        Args:
            proxy: прокси
            
        Returns:
            URL вида "http://ip:port" или "socks5://ip:port"
        """
        protocol = proxy.protocol.lower()
        
        # requests поддерживает socks через urllib3
        if protocol.startswith("socks"):
            return f"{protocol}://{proxy.ip}:{proxy.port}"
        
        return f"http://{proxy.ip}:{proxy.port}"
    
    def quick_check(self, ip: str, port: int, protocol: str = "http") -> bool:
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
        return self.check(proxy)
    
    def __del__(self) -> None:
        """Закрыть сессию при уничтожении"""
        if hasattr(self, "_session"):
            self._session.close()
