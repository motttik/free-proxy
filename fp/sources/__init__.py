"""
Sources Package

Парсеры для всех типов источников прокси
"""

from fp.sources.base import BaseSourceParser, Proxy, ParseResult
from fp.sources.txt_parser import TxtSourceParser
from fp.sources.html_parser import HtmlSourceParser
from fp.sources.api_parser import ApiSourceParser

from fp.config import SourceType, ProxySource


def get_parser(source: ProxySource) -> BaseSourceParser:
    """
    Фабричная функция для получения парсера
    
    Args:
        source: конфигурация источника
        
    Returns:
        соответствующий парсер
        
    Raises:
        ValueError: если тип источника не поддерживается
    """
    source_type = source["type"]
    
    if source_type == SourceType.GITHUB_RAW or source_type == SourceType.API_TEXT:
        return TxtSourceParser(source)
    elif source_type == SourceType.HTML_TABLE:
        return HtmlSourceParser(source)
    elif source_type == SourceType.API_JSON:
        return ApiSourceParser(source)
    else:
        raise ValueError(f"Unsupported source type: {source_type}")


__all__ = [
    "BaseSourceParser",
    "Proxy",
    "ParseResult",
    "TxtSourceParser",
    "HtmlSourceParser",
    "ApiSourceParser",
    "get_parser",
]
