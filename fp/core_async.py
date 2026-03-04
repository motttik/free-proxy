"""
Async FreeProxy Module

Асинхронная версия FreeProxy с использованием aiohttp
"""

import asyncio
import logging
import random
from datetime import datetime
from typing import Literal

from fp.config import (
    ALL_SOURCES,
    ProxySource,
    SourceProtocol,
    SourceType,
)
from fp.sources import get_parser, Proxy
from fp.checkers.async_checker import AsyncProxyChecker
from fp.errors import NoWorkingProxyError, SourceFetchError, ParseError

logger = logging.getLogger(__name__)


class AsyncFreeProxy:
    """
    AsyncFreeProxy - асинхронное получение рабочих бесплатных прокси
    
    Использует aiohttp для быстрой параллельной проверки прокси.
    Проверяет 100 прокси за ~10 секунд вместо ~50 секунд.
    
    Пример использования:
        import asyncio
        from fp import AsyncFreeProxy
        
        async def main():
            # Получить одну прокси
            proxy = await AsyncFreeProxy().get()
            print(proxy)
            
            # Получить 10 прокси
            proxies = await AsyncFreeProxy().get(count=10)
            print(proxies)
        
        asyncio.run(main())
    """
    
    def __init__(
        self,
        country_id: list[str] | None = None,
        timeout: float = 5.0,
        rand: bool = False,
        anonym: bool = False,
        elite: bool = False,
        google: bool | None = None,
        https: bool = False,
        protocol: Literal["http", "https", "socks4", "socks5"] | None = None,
        url: str = "https://httpbin.org/ip",
        max_concurrent: int = 20,
        cache_ttl: int = 300,
        log_level: str = "WARNING",
    ) -> None:
        """
        Инициализация AsyncFreeProxy
        
        Args:
            country_id: список кодов стран (['US', 'GB', 'DE'], None = все)
            timeout: таймаут проверки прокси в секундах
            rand: перемешать прокси перед проверкой
            anonym: только анонимные прокси
            elite: только элитные прокси (включает anonym=True)
            google: только прокси с поддержкой Google (None = все)
            https: только HTTPS прокси
            protocol: предпочтительный протокол (http/https/socks4/socks5)
            url: URL для проверки работоспособности
            max_concurrent: макс. количество одновременных проверок
            cache_ttl: время жизни кэша в секундах
            log_level: уровень логирования
        """
        # Параметры фильтрации
        self.country_id = country_id
        self.timeout = timeout
        self.random = rand
        self.anonym = anonym
        self.elite = elite
        self.google = google
        self.https = https
        self.protocol = protocol
        self.test_url = url
        
        # Параметры проверки
        self.max_concurrent = max_concurrent
        self.cache_ttl = cache_ttl
        
        # Настройка логирования
        logging.basicConfig(
            level=getattr(logging, log_level.upper(), logging.WARNING),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        
        # Инициализация чекера
        self._checker = AsyncProxyChecker(
            test_url=url,
            timeout=timeout,
            max_concurrent=max_concurrent,
        )
        
        # Кэш
        self._proxy_cache: list[Proxy] = []
        self._cache_time: datetime | None = None
        self._sources: list = []
        
        # Инициализация источников
        self._init_sources()
    
    def _init_sources(self) -> None:
        """Инициализировать парсеры источников"""
        sources = ALL_SOURCES
        
        if self.protocol:
            protocol_map = {
                "http": SourceProtocol.HTTP,
                "https": SourceProtocol.HTTPS,
                "socks4": SourceProtocol.SOCKS4,
                "socks5": SourceProtocol.SOCKS5,
            }
            target_protocol = protocol_map.get(self.protocol)
            
            if target_protocol:
                sources = [
                    s for s in sources
                    if target_protocol in s["protocols"]
                ]
        
        self._sources = []
        for source in sources:
            try:
                parser = get_parser(source)
                self._sources.append(parser)
            except Exception as e:
                logger.warning(f"Не удалось создать парсер для {source['name']}: {e}")
        
        logger.info(f"Инициализировано {len(self._sources)} источников")
    
    def _get_source_order(self, repeat: bool) -> list:
        """Определить порядок источников"""
        if repeat:
            return self._sources
        
        github = [s for s in self._sources if s.source["type"] == SourceType.GITHUB_RAW]
        api = [s for s in self._sources if s.source["type"] in (SourceType.API_TEXT, SourceType.API_JSON)]
        html = [s for s in self._sources if s.source["type"] == SourceType.HTML_TABLE]
        
        return github + api + html
    
    def _matches_criteria(self, proxy: Proxy) -> bool:
        """Проверить соответствие прокси критериям"""
        if self.country_id and proxy.country:
            if proxy.country not in self.country_id:
                return False
        
        if self.anonym and proxy.anonymity:
            if proxy.anonymity not in ("anonymous", "elite", "elite proxy"):
                return False
        
        if self.elite and proxy.anonymity:
            if "elite" not in proxy.anonymity:
                return False
        
        if self.google is not None and proxy.google is not None:
            if proxy.google != self.google:
                return False
        
        if self.https and proxy.https is not None:
            if not proxy.https:
                return False
        
        return True
    
    async def get_proxy_list(self, repeat: bool = False) -> list[str]:
        """
        Получить список всех прокси из источников
        
        Args:
            repeat: использовать fallback источники
            
        Returns:
            список строк вида "http://IP:PORT"
        """
        proxies: list[Proxy] = []
        sources = self._get_source_order(repeat)
        
        for parser in sources:
            try:
                result = parser.parse()
                
                if result.success:
                    filtered = [p for p in result.proxies if self._matches_criteria(p)]
                    proxies.extend(filtered)
                    logger.debug(f"[{parser.source['name']}] Добавлено {len(filtered)} прокси")
                    
            except (SourceFetchError, ParseError) as e:
                logger.warning(f"Не удалось получить прокси из {parser.source['name']}: {e}")
                continue
        
        proxy_strings = [str(p) for p in proxies]
        
        if self.random:
            random.shuffle(proxy_strings)
        
        return proxy_strings
    
    def _is_cache_valid(self) -> bool:
        """Проверить актуальность кэша"""
        if not self._cache_time or not self._proxy_cache:
            return False
        
        age = (datetime.now() - self._cache_time).total_seconds()
        return age < self.cache_ttl
    
    async def get(self, repeat: bool = False, count: int = 1, show_progress: bool = False) -> str | list[str]:
        """
        Получить рабочую(ие) прокси(и)
        
        Args:
            repeat: использовать fallback источники
            count: количество прокси для возврата
            show_progress: показывать прогресс проверки
            
        Returns:
            строка "http://IP:PORT" или список строк
            
        Raises:
            NoWorkingProxyError: если не найдено рабочих прокси
        """
        # Проверяем кэш
        if self._is_cache_valid():
            logger.debug("Использую кэш рабочих прокси")
            if self.random:
                random.shuffle(self._proxy_cache)
            
            if count == 1 and self._proxy_cache:
                return str(self._proxy_cache[0])
            elif count > 1:
                return [str(p) for p in self._proxy_cache[:count]]
        
        # Получаем список прокси
        proxy_strings = await self.get_proxy_list(repeat)
        
        if not proxy_strings:
            if not repeat:
                return await self.get(repeat=True, count=count, show_progress=show_progress)
            raise NoWorkingProxyError({
                "country_id": self.country_id,
                "timeout": self.timeout,
                "protocol": self.protocol,
            })
        
        # Конвертируем в Proxy для проверки
        proxies_to_check: list[Proxy] = []
        for proxy_str in proxy_strings:
            try:
                if "://" in proxy_str:
                    protocol, rest = proxy_str.split("://", 1)
                else:
                    protocol = "http"
                    rest = proxy_str
                
                ip, port_str = rest.rsplit(":", 1)
                
                proxy = Proxy(
                    ip=ip,
                    port=int(port_str),
                    protocol=protocol,
                )
                proxies_to_check.append(proxy)
                
            except Exception as e:
                logger.debug(f"Не удалось распарсить {proxy_str}: {e}")
                continue
        
        # Асинхронная проверка
        logger.info(f"Асинхронная проверка {len(proxies_to_check)} прокси...")
        
        working_proxies = await self._checker.check_multiple(
            proxies_to_check,
            stop_on_first=(count == 1),
            show_progress=show_progress,
        )
        
        if not working_proxies:
            if not repeat:
                return await self.get(repeat=True, count=count, show_progress=show_progress)
            raise NoWorkingProxyError({
                "country_id": self.country_id,
                "timeout": self.timeout,
                "protocol": self.protocol,
            })
        
        # Сохраняем в кэш
        self._proxy_cache = working_proxies
        self._cache_time = datetime.now()
        
        if count == 1:
            return str(working_proxies[0])
        
        return [str(p) for p in working_proxies[:count]]
    
    def clear_cache(self) -> None:
        """Очистить кэш"""
        self._proxy_cache = []
        self._cache_time = None
        logger.debug("Кэш очищен")
    
    async def check_proxy(self, ip: str, port: int, protocol: str = "http") -> bool:
        """
        Быстро проверить одну прокси
        
        Args:
            ip: IP адрес
            port: порт
            protocol: протокол
            
        Returns:
            True если прокси работает
        """
        return await self._checker.quick_check(ip, port, protocol)
