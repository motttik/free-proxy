"""
Base Source Parser Module

Абстрактный базовый класс для всех парсеров источников
"""

from abc import ABC, abstractmethod
from typing import Protocol
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from fp.config import ProxySource, SourceType


@dataclass
class Proxy:
    """Модель прокси"""
    ip: str
    port: int
    protocol: str
    country: str | None = None
    anonymity: str | None = None  # elite, anonymous, transparent
    google: bool | None = None
    https: bool | None = None
    last_checked: datetime | None = None
    source: str | None = None
    
    def __str__(self) -> str:
        return f"{self.protocol}://{self.ip}:{self.port}"
    
    def to_dict(self) -> dict:
        """Конвертация в словарь"""
        return {
            "ip": self.ip,
            "port": self.port,
            "protocol": self.protocol,
            "country": self.country,
            "anonymity": self.anonymity,
            "google": self.google,
            "https": self.https,
            "last_checked": self.last_checked.isoformat() if self.last_checked else None,
            "source": self.source,
        }


@dataclass
class ParseResult:
    """Результат парсинга источника"""
    proxies: list[Proxy] = field(default_factory=list)
    source_name: str = ""
    parsed_at: datetime = field(default_factory=datetime.now)
    success: bool = True
    error: str | None = None
    
    @property
    def count(self) -> int:
        return len(self.proxies)
    
    def to_dict(self) -> dict:
        return {
            "proxies": [p.to_dict() for p in self.proxies],
            "source_name": self.source_name,
            "parsed_at": self.parsed_at.isoformat(),
            "success": self.success,
            "error": self.error,
            "count": self.count,
        }


class BaseSourceParser(ABC):
    """
    Абстрактный базовый класс для парсеров источников
    
    Все парсеры должны реализовать метод parse()
    """
    
    def __init__(self, source: ProxySource) -> None:
        self.source = source
        self._cache: ParseResult | None = None
        self._cache_time: datetime | None = None
    
    @abstractmethod
    def parse(self) -> ParseResult:
        """
        Распарсить источник и вернуть список прокси
        
        Returns:
            ParseResult с списком прокси
        """
        pass
    
    def get_freshness(self) -> timedelta | None:
        """
        Получить время с последнего успешного парсинга
        
        Returns:
            timedelta или None если не парсилось
        """
        if self._cache_time is None:
            return None
        return datetime.now() - self._cache_time
    
    def is_fresh(self, ttl_seconds: int = 300) -> bool:
        """
        Проверить, актуален ли кэш
        
        Args:
            ttl_seconds: время жизни кэша в секундах
            
        Returns:
            True если кэш актуален
        """
        if self._cache_time is None:
            return False
        age = (datetime.now() - self._cache_time).total_seconds()
        return age < ttl_seconds
    
    def get_cached(self) -> ParseResult | None:
        """Получить закэшированный результат"""
        return self._cache
    
    def _set_cache(self, result: ParseResult) -> None:
        """Сохранить результат в кэш"""
        self._cache = result
        self._cache_time = datetime.now()
    
    def validate_proxy_string(self, proxy_str: str) -> bool:
        """
        Быстрая валидация строки прокси формата IP:PORT
        
        Args:
            proxy_str: строка вида "1.2.3.4:8080"
            
        Returns:
            True если формат корректен
        """
        if not proxy_str or ":" not in proxy_str:
            return False
        
        parts = proxy_str.strip().split(":")
        if len(parts) != 2:
            return False
        
        ip, port_str = parts
        
        # Валидация IP (базовая)
        ip_parts = ip.split(".")
        if len(ip_parts) != 4:
            return False
        
        try:
            for part in ip_parts:
                num = int(part)
                if num < 0 or num > 255:
                    return False
        except ValueError:
            return False
        
        # Валидация порта
        try:
            port = int(port_str)
            if port < 1 or port > 65535:
                return False
        except ValueError:
            return False
        
        return True
    
    def parse_proxy_string(self, proxy_str: str) -> Proxy | None:
        """
        Распарсить строку прокси в объект Proxy
        
        Args:
            proxy_str: строка вида "1.2.3.4:8080"
            
        Returns:
            Proxy или None если не удалось распарсить
        """
        if not self.validate_proxy_string(proxy_str):
            return None
        
        proxy_str = proxy_str.strip()
        ip, port_str = proxy_str.split(":")
        
        # Определяем протокол из конфига источника
        protocol = self.source["protocols"][0].value if self.source["protocols"] else "http"
        
        return Proxy(
            ip=ip,
            port=int(port_str),
            protocol=protocol,
            source=self.source["name"],
        )
