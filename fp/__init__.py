"""
Free Proxy - Получение рабочих бесплатных прокси

Поддерживает 50+ источников:
- GitHub raw списки (TXT формат)
- API endpoints (JSON/TXT)
- HTML сайты для парсинга

Протоколы: HTTP, HTTPS, SOCKS4, SOCKS5

Пример использования:

    # Синхронно
    from fp import FreeProxy
    
    proxy = FreeProxy(country_id=['US'], timeout=1.0, rand=True).get()
    print(proxy)  # http://1.2.3.4:8080
    
    # Асинхронно
    import asyncio
    from fp import AsyncFreeProxy
    
    async def main():
        proxy = await AsyncFreeProxy().get()
        print(proxy)
    
    asyncio.run(main())

CLI использование:

    fp get
    fp get -c US -t 1.0 -r
    fp get -n 10 -f json
    fp list
    fp test 1.2.3.4:8080
"""

__version__ = "2.0.0"
__author__ = "jundymek (original), Qwen Code AI (v2.0 rewrite)"
__email__ = "jundymek@gmail.com"
__license__ = "MIT"

from fp.core import FreeProxy
from fp.core_async import AsyncFreeProxy
from fp.sources.base import Proxy
from fp.errors import (
    FreeProxyException,
    NoWorkingProxyError,
    SourceFetchError,
    ParseError,
    ProxyValidationError,
)
from fp.config import (
    ALL_SOURCES,
    GITHUB_SOURCES,
    API_SOURCES,
    HTML_SOURCES,
    SourceType,
    SourceProtocol,
)

__all__ = [
    # Версия
    "__version__",
    "__author__",
    "__email__",
    "__license__",
    
    # Основные классы
    "FreeProxy",
    "AsyncFreeProxy",
    "Proxy",
    
    # Исключения
    "FreeProxyException",
    "NoWorkingProxyError",
    "SourceFetchError",
    "ParseError",
    "ProxyValidationError",
    
    # Конфигурация
    "ALL_SOURCES",
    "GITHUB_SOURCES",
    "API_SOURCES",
    "HTML_SOURCES",
    "SourceType",
    "SourceProtocol",
]
