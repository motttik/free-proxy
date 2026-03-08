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

# Lazy imports для улучшения производительности
def __getattr__(name):
    """Отложенная загрузка модулей"""
    if name == "__version__":
        return __version__
    if name == "__author__":
        return __author__
    if name == "__email__":
        return __email__
    if name == "__license__":
        return __license__
    
    if name == "FreeProxy":
        from fp.core import FreeProxy
        return FreeProxy
    if name == "AsyncFreeProxy":
        from fp.core_async import AsyncFreeProxy
        return AsyncFreeProxy
    if name == "Proxy":
        from fp.sources.base import Proxy
        return Proxy
    
    if name == "ProxyManager":
        from fp.manager import ProxyManager
        return ProxyManager
    if name == "ProxyDatabase":
        from fp.database import ProxyDatabase
        return ProxyDatabase
    if name == "AsyncProxyValidator":
        from fp.validator import AsyncProxyValidator
        return AsyncProxyValidator
    if name == "ProxyMetrics":
        from fp.validator import ProxyMetrics
        return ProxyMetrics
    if name == "ProxyPool":
        from fp.validator import ProxyPool
        return ProxyPool
    if name == "ProxyValidationResult":
        from fp.validator import ProxyValidationResult
        return ProxyValidationResult
    if name == "ValidationStage":
        from fp.validator import ValidationStage
        return ValidationStage
    
    if name == "ProxyScheduler":
        from fp.scheduler import ProxyScheduler
        return ProxyScheduler
    if name == "SourceManager":
        from fp.source_manager import SourceManager
        return SourceManager
    if name == "SourceHealthManager":
        from fp.source_health import SourceHealthManager
        return SourceHealthManager
    if name == "ProxyPipeline":
        from fp.pipeline import ProxyPipeline
        return ProxyPipeline
    if name == "PipelineReport":
        from fp.pipeline import PipelineReport
        return PipelineReport
    if name == "NormalizedProxy":
        from fp.pipeline import NormalizedProxy
        return NormalizedProxy
    
    if name == "SLOMonitor":
        from fp.slo_monitor import SLOMonitor
        return SLOMonitor
    if name == "SLOMetrics":
        from fp.slo_monitor import SLOMetrics
        return SLOMetrics
    if name == "Alert":
        from fp.slo_monitor import Alert
        return Alert
    
    if name == "GitHubDiscovery":
        from fp.github_discovery import GitHubDiscovery
        return GitHubDiscovery
    if name == "DiscoveredSource":
        from fp.github_discovery import DiscoveredSource
        return DiscoveredSource
    
    if name == "FreeProxyException":
        from fp.errors import FreeProxyException
        return FreeProxyException
    if name == "NoWorkingProxyError":
        from fp.errors import NoWorkingProxyError
        return NoWorkingProxyError
    if name == "SourceFetchError":
        from fp.errors import SourceFetchError
        return SourceFetchError
    if name == "ParseError":
        from fp.errors import ParseError
        return ParseError
    if name == "ProxyValidationError":
        from fp.errors import ProxyValidationError
        return ProxyValidationError
    
    if name == "ALL_SOURCES":
        from fp.config import ALL_SOURCES
        return ALL_SOURCES
    if name == "GITHUB_SOURCES":
        from fp.config import GITHUB_SOURCES
        return GITHUB_SOURCES
    if name == "API_SOURCES":
        from fp.config import API_SOURCES
        return API_SOURCES
    if name == "HTML_SOURCES":
        from fp.config import HTML_SOURCES
        return HTML_SOURCES
    if name == "SourceType":
        from fp.config import SourceType
        return SourceType
    if name == "SourceProtocol":
        from fp.config import SourceProtocol
        return SourceProtocol
    
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Для совместимости с IDE и статическими анализаторами
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
    "ProxyScheduler",
    "SourceManager",
    "SourceHealthManager",
    "ProxyPipeline",
    "PipelineReport",
    "NormalizedProxy",
    "SLOMonitor",
    "SLOMetrics",
    "Alert",
    "GitHubDiscovery",
    "DiscoveredSource",

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
