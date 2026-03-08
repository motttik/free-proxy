"""
Core FreeProxy Module

Основной класс FreeProxy с расширенным функционалом
"""

import logging
import random
from datetime import datetime
from typing import Literal

from fp.config import (
    ALL_SOURCES,
    GITHUB_SOURCES,
    API_SOURCES,
    HTML_SOURCES,
    ProxySource,
    SourceProtocol,
    SourceType,
)
from fp.sources import get_parser, Proxy, ParseResult
from fp.sources.base import BaseSourceParser
from fp.checkers.sync_checker import SyncProxyChecker
from fp.checkers.async_checker import AsyncProxyChecker
from fp.errors import FreeProxyException, NoWorkingProxyError, SourceFetchError, ParseError

logger = logging.getLogger(__name__)


class FreeProxy:
    """
    FreeProxy - получение рабочих бесплатных прокси
    
    Поддерживает 50+ источников:
    - GitHub raw списки (TXT формат)
    - API endpoints (JSON/TXT)
    - HTML сайты для парсинга
    
    Протоколы: HTTP, HTTPS, SOCKS4, SOCKS5
    
    Пример использования:
        from fp import FreeProxy
        
        # Синхронно
        proxy = FreeProxy(country_id=['US'], timeout=1.0, rand=True).get()
        print(proxy)  # http://1.2.3.4:8080
        
        # Асинхронно
        import asyncio
        from fp import AsyncFreeProxy
        
        async def main():
            proxy = await AsyncFreeProxy().get()
            print(proxy)
        
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
        Инициализация FreeProxy
        
        Args:
            country_id: список кодов стран (['US', 'GB', 'DE'], None = все)
            timeout: таймаут проверки прокси в секундах
            rand: перемешать прокси перед проверкой
            anonym: только анонимные прокси
            elite: только элитные прокси (включает anonym=True)
            google: только прокси с поддержкой Google (None = все)
            https: только HTTPS прокси (для HTTP/HTTPS источников)
            protocol: предпочтительный протокол (http/https/socks4/socks5)
            url: URL для проверки работоспособности
            max_concurrent: макс. количество одновременных проверок
            cache_ttl: время жизни кэша в секундах
            log_level: уровень логирования (DEBUG/INFO/WARNING/ERROR)
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
        self._checker = SyncProxyChecker(
            test_url=url,
            timeout=timeout,
        )
        
        # Кэш
        self._proxy_cache: list[Proxy] = []
        self._cache_time: datetime | None = None
        self._sources: list[BaseSourceParser] = []
        
        # Инициализация источников
        self._init_sources()
    
    def _init_sources(self) -> None:
        """Инициализировать парсеры источников"""
        # Фильтруем источники по протоколу если указан
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
        
        # Создаем парсеры
        self._sources = []
        for source in sources:
            try:
                parser = get_parser(source)
                self._sources.append(parser)
            except Exception as e:
                logger.warning(f"Не удалось создать парсер для {source['name']}: {e}")
        
        logger.info(f"Инициализировано {len(self._sources)} источников")
    
    def get_proxy_list(self, repeat: bool = False) -> list[str]:
        """
        Получить список всех прокси из источников
        
        Args:
            repeat: использовать fallback источники если основные не работают
            
        Returns:
            список строк вида "http://IP:PORT"
        """
        proxies: list[Proxy] = []
        
        # Определяем порядок источников
        sources = self._get_source_order(repeat)
        
        for parser in sources:
            try:
                result = parser.parse()
                
                if result.success:
                    # Фильтруем по критериям
                    filtered = [p for p in result.proxies if self._matches_criteria(p)]
                    proxies.extend(filtered)
                    logger.debug(f"[{parser.source['name']}] Добавлено {len(filtered)} прокси")
                    
            except (SourceFetchError, ParseError) as e:
                logger.warning(f"Не удалось получить прокси из {parser.source['name']}: {e}")
                continue
        
        # Конвертируем в строки
        proxy_strings = [str(p) for p in proxies]
        
        # Перемешиваем если нужно
        if self.random:
            random.shuffle(proxy_strings)
        
        return proxy_strings
    
    def _get_source_order(self, repeat: bool) -> list[BaseSourceParser]:
        """
        Определить порядок источников
        
        Args:
            repeat: fallback режим
            
        Returns:
            список парсеров в нужном порядке
        """
        if repeat:
            # Fallback: все источники
            return self._sources
        
        # Приоритет: GitHub raw → API → HTML
        github = [s for s in self._sources if s.source["type"] == SourceType.GITHUB_RAW]
        api = [s for s in self._sources if s.source["type"] in (SourceType.API_TEXT, SourceType.API_JSON)]
        html = [s for s in self._sources if s.source["type"] == SourceType.HTML_TABLE]
        
        # Для country_id US/GB приоритет соответствующим источникам
        if self.country_id == ["US"]:
            us_sources = [s for s in html if "us-proxy" in s.source["url"].lower()]
            return us_sources + github + api + [s for s in html if s not in us_sources]
        
        if self.country_id == ["GB"]:
            gb_sources = [s for s in html if "uk-proxy" in s.source["url"].lower()]
            return gb_sources + github + api + [s for s in html if s not in gb_sources]
        
        return github + api + html
    
    def _matches_criteria(self, proxy: Proxy) -> bool:
        """
        Проверить, соответствует ли прокси критериям фильтрации
        
        Args:
            proxy: прокси для проверки
            
        Returns:
            True если соответствует
        """
        # Страна
        if self.country_id and proxy.country:
            if proxy.country not in self.country_id:
                return False
        
        # Анонимность
        if self.anonym and proxy.anonymity:
            if proxy.anonymity not in ("anonymous", "elite", "elite proxy"):
                return False
        
        # Элитность
        if self.elite and proxy.anonymity:
            if "elite" not in proxy.anonymity:
                return False
        
        # Google
        if self.google is not None and proxy.google is not None:
            if proxy.google != self.google:
                return False
        
        # HTTPS
        if self.https and proxy.https is not None:
            if not proxy.https:
                return False
        
        return True
    
    def get(self, repeat: bool = False, count: int = 1) -> str | list[str]:
        """
        Получить рабочую(ие) прокси(и)
        
        Args:
            repeat: использовать fallback источники
            count: количество прокси для возврата (1 = одна строка, >1 = список)
            
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
            
            working = self._proxy_cache[:count] if count > 1 else [self._proxy_cache[0]] if self._proxy_cache else []
            
            if working:
                if count == 1:
                    return str(working[0])
                return [str(p) for p in working]
        
        # Получаем список прокси
        proxy_strings = self.get_proxy_list(repeat)
        
        if not proxy_strings:
            # Fallback: если не найдено, пробуем repeat=True
            if not repeat:
                return self.get(repeat=True, count=count)
            raise NoWorkingProxyError({
                "country_id": self.country_id,
                "timeout": self.timeout,
                "protocol": self.protocol,
            })
        
        # Конвертируем обратно в Proxy для проверки
        proxies_to_check: list[Proxy] = []
        for proxy_str in proxy_strings:
            try:
                # Парсим строку обратно
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
        
        # Проверяем прокси
        logger.info(f"Проверка {len(proxies_to_check)} прокси...")
        
        working_proxies: list[Proxy] = []
        
        for i, proxy in enumerate(proxies_to_check, 1):
            logger.info(f"Проверка {i}/{len(proxies_to_check)}: {proxy}")
            
            if self._checker.check(proxy):
                logger.info(f"✓ Рабочая: {proxy}")
                working_proxies.append(proxy)
                
                if count == 1:
                    # Сохраняем в кэш
                    self._proxy_cache = working_proxies
                    self._cache_time = datetime.now()
                    return str(proxy)
                
                if len(working_proxies) >= count:
                    break
        
        if not working_proxies:
            # Fallback
            if not repeat:
                return self.get(repeat=True, count=count)
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
        
        return [str(p) for p in working_proxies]
    
    def _is_cache_valid(self) -> bool:
        """Проверить актуальность кэша"""
        if not self._cache_time or not self._proxy_cache:
            return False
        
        age = (datetime.now() - self._cache_time).total_seconds()
        return age < self.cache_ttl
    
    def clear_cache(self) -> None:
        """Очистить кэш"""
        self._proxy_cache = []
        self._cache_time = None
        logger.debug("Кэш очищен")
    
    def get_all_sources(self) -> list[dict]:
        """
        Получить информацию обо всех источниках
        
        Returns:
            список словарей с информацией об источниках
        """
        return [
            {
                "name": s.source["name"],
                "url": s.source["url"],
                "type": s.source["type"].value,
                "protocols": [p.value for p in s.source["protocols"]],
                "country": s.source["country"],
                "update_frequency": s.source["update_frequency"],
            }
            for s in self._sources
        ]


# Импортируем асинхронную версию если доступна
try:
    from fp.core_async import AsyncFreeProxy
except ImportError:
    AsyncFreeProxy = None  # type: ignore
