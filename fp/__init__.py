"""
Free Proxy v3.0 - Получение рабочих бесплатных прокси

Поддерживает 53 источника:
- GitHub raw списки (TXT формат)
- API endpoints (JSON/TXT)
- HTML сайты для парсинга

Протоколы: HTTP, HTTPS, SOCKS4, SOCKS5

v3.0 Новые возможности:
- 2-этапная валидация (Stage A + Stage B)
- Score-система (0-100)
- Пулы (HOT/WARM/QUARANTINE)
- SQLite хранение
- Async валидация

Пример использования:

    # Синхронно
    from fp import FreeProxy
    
    proxy = FreeProxy(country_id=['US'], timeout=1.0, rand=True).get()
    print(proxy)  # http://1.2.3.4:8080
    
    # Асинхронно v3.0
    import asyncio
    from fp import ProxyManager
    
    async def main():
        async with ProxyManager() as manager:
            proxy = await manager.get_proxy(min_score=50)
            print(proxy)
    
    asyncio.run(main())

CLI использование:

    fp get
    fp get -c US -t 1.0 -r
    fp get -n 10 -f json
    fp list
    fp test 1.2.3.4:8080
"""

__version__ = "3.0.0"
__author__ = "motttik"
__email__ = "motttik@users.noreply.github.com"
__license__ = "MIT"

from fp.core import FreeProxy
from fp.core_async import AsyncFreeProxy
from fp.sources.base import Proxy
from fp.validator import (
    AsyncProxyValidator,
    ProxyMetrics,
    ProxyPool,
    ProxyValidationResult,
    ValidationStage,
)
from fp.database import ProxyDatabase
from fp.manager import ProxyManager
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
    
    # v2.0 Классы
    "FreeProxy",
    "AsyncFreeProxy",
    "Proxy",
    
    # v3.0 Классы
    "ProxyManager",
    "ProxyDatabase",
    "AsyncProxyValidator",
    "ProxyMetrics",
    "ProxyPool",
    "ProxyValidationResult",
    "ValidationStage",
    
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
