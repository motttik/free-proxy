"""
Free Proxy Exceptions Module

Все исключения проекта free-proxy
"""


class FreeProxyException(Exception):
    """Базовое исключение для всех ошибок free-proxy"""
    
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)


class SourceFetchError(FreeProxyException):
    """Ошибка при получении данных из источника"""
    
    def __init__(self, source_name: str, url: str, reason: str) -> None:
        message = f"Failed to fetch source '{source_name}' from {url}: {reason}"
        super().__init__(message)
        self.source_name = source_name
        self.url = url
        self.reason = reason


class ParseError(FreeProxyException):
    """Ошибка при парсинге данных"""
    
    def __init__(self, source_name: str, reason: str) -> None:
        message = f"Failed to parse source '{source_name}': {reason}"
        super().__init__(message)
        self.source_name = source_name
        self.reason = reason


class NoWorkingProxyError(FreeProxyException):
    """Не найдено рабочих прокси с заданными параметрами"""
    
    def __init__(self, filters: dict | None = None) -> None:
        filters_str = f" with filters {filters}" if filters else ""
        message = f"There are no working proxies at this time{filters_str}."
        super().__init__(message)
        self.filters = filters or {}


class ProxyValidationError(FreeProxyException):
    """Ошибка валидации прокси"""
    
    def __init__(self, proxy: str, reason: str) -> None:
        message = f"Invalid proxy '{proxy}': {reason}"
        super().__init__(message)
        self.proxy = proxy
        self.reason = reason


class ConfigurationError(FreeProxyException):
    """Ошибка конфигурации"""
    
    def __init__(self, message: str) -> None:
        super().__init__(f"Configuration error: {message}")
