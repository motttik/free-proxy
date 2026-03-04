"""
TXT Source Parser Module

Парсер для TXT файлов (GitHub raw и другие text-источники)
Формат: IP:PORT (одна строка = один прокси)
"""

import logging
from typing import TYPE_CHECKING

import requests
from requests.exceptions import RequestException, Timeout, ConnectionError

from fp.config import ProxySource, SourceType
from fp.sources.base import BaseSourceParser, ParseResult, Proxy
from fp.errors import SourceFetchError, ParseError

if TYPE_CHECKING:
    from fp.config import SourceProtocol

logger = logging.getLogger(__name__)


class TxtSourceParser(BaseSourceParser):
    """
    Парсер для TXT файлов с прокси
    
    Ожидает формат:
    ```
    1.2.3.4:8080
    5.6.7.8:3128
    ...
    ```
    """
    
    def __init__(self, source: ProxySource) -> None:
        super().__init__(source)
        
        if source["type"] != SourceType.GITHUB_RAW and source["type"] != SourceType.API_TEXT:
            logger.warning(
                f"TxtSourceParser инициализирован для источника типа {source['type']}, "
                f"ожидался GITHUB_RAW или API_TEXT"
            )
    
    def parse(self) -> ParseResult:
        """
        Скачать и распарсить TXT файл с прокси
        
        Returns:
            ParseResult со списком прокси
        """
        # Проверяем кэш
        if self.is_fresh(self.source["timeout"] * 60):  # TTL = timeout * 60
            cached = self.get_cached()
            if cached:
                logger.debug(f"Использую кэш для {self.source['name']}")
                return cached
        
        result = ParseResult(source_name=self.source["name"])
        
        try:
            # Скачиваем файл
            logger.info(f"Загрузка {self.source['name']} из {self.source['url']}")
            response = requests.get(
                self.source["url"],
                timeout=self.source["timeout"],
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
            )
            response.raise_for_status()
            
        except Timeout as e:
            error_msg = f"Timeout after {self.source['timeout']}s"
            logger.error(f"[{self.source['name']}] {error_msg}")
            result.success = False
            result.error = error_msg
            self._set_cache(result)
            raise SourceFetchError(self.source["name"], self.source["url"], error_msg) from e
            
        except ConnectionError as e:
            error_msg = f"Connection error: {str(e)}"
            logger.error(f"[{self.source['name']}] {error_msg}")
            result.success = False
            result.error = error_msg
            self._set_cache(result)
            raise SourceFetchError(self.source["name"], self.source["url"], error_msg) from e
            
        except RequestException as e:
            error_msg = f"Request failed: {str(e)}"
            logger.error(f"[{self.source['name']}] {error_msg}")
            result.success = False
            result.error = error_msg
            self._set_cache(result)
            raise SourceFetchError(self.source["name"], self.source["url"], error_msg) from e
        
        # Парсим строки
        content = response.text
        lines = content.strip().split("\n")
        
        proxies: list[Proxy] = []
        parsed_count = 0
        invalid_count = 0
        
        for line in lines:
            line = line.strip()
            
            # Пропускаем пустые строки и комментарии
            if not line or line.startswith("#"):
                continue
            
            # Пытаемся распарсить
            proxy = self.parse_proxy_string(line)
            
            if proxy:
                # Устанавливаем протокол из конфига
                if self.source["protocols"]:
                    proxy.protocol = self.source["protocols"][0].value
                proxy.source = self.source["name"]
                proxies.append(proxy)
                parsed_count += 1
            else:
                invalid_count += 1
                logger.debug(f"[{self.source['name']}] Невалидная строка: {line}")
        
        result.proxies = proxies
        result.success = len(proxies) > 0
        
        if invalid_count > 0:
            logger.debug(
                f"[{self.source['name']}] Распаршено {parsed_count} прокси, "
                f"пропущено {invalid_count} невалидных строк"
            )
        
        if not result.success:
            result.error = "No valid proxies found in response"
            self._set_cache(result)
            raise ParseError(self.source["name"], result.error)
        
        logger.info(f"[{self.source['name']}] Найдено {parsed_count} прокси")
        
        self._set_cache(result)
        return result
    
    @staticmethod
    def parse_line(line: str) -> tuple[str, int] | None:
        """
        Статический метод для парсинга одной строки
        
        Args:
            line: строка вида "IP:PORT"
            
        Returns:
            кортеж (ip, port) или None
        """
        line = line.strip()
        
        if not line or line.startswith("#"):
            return None
        
        if ":" not in line:
            return None
        
        parts = line.split(":")
        if len(parts) != 2:
            return None
        
        ip, port_str = parts
        
        try:
            port = int(port_str)
            if port < 1 or port > 65535:
                return None
        except ValueError:
            return None
        
        # Базовая валидация IP
        ip_parts = ip.split(".")
        if len(ip_parts) != 4:
            return None
        
        try:
            for part in ip_parts:
                num = int(part)
                if num < 0 or num > 255:
                    return None
        except ValueError:
            return None
        
        return (ip, port)
