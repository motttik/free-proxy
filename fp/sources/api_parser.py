"""
API Source Parser Module

Парсер для JSON API endpoints
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


class ApiSourceParser(BaseSourceParser):
    """
    Парсер для JSON API с прокси
    
    Поддерживает:
    - api.openproxy.space/list/http (JSON)
    """
    
    def __init__(self, source: ProxySource) -> None:
        super().__init__(source)

        if source["type"] != SourceType.API_JSON:
            logger.warning(
                f"ApiSourceParser инициализирован для источника типа {source['type']}, "
                f"ожидался API_JSON"
            )
    
    def parse(self) -> ParseResult:
        """
        Скачать и распарсить JSON API с прокси
        
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
            # Скачиваем JSON
            logger.info(f"Загрузка {self.source['name']} из {self.source['url']}")
            response = requests.get(
                self.source["url"],
                timeout=self.source["timeout"],
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json",
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
        
        # Парсим JSON
        try:
            data = response.json()
        except Exception as e:
            error_msg = f"JSON parse error: {str(e)}"
            logger.error(f"[{self.source['name']}] {error_msg}")
            result.success = False
            result.error = error_msg
            self._set_cache(result)
            raise ParseError(self.source["name"], error_msg) from e
        
        # Парсим прокси из JSON
        proxies: list[Proxy] = []
        
        try:
            # Формат OpenProxy.space: {"data": [{"ip": "...", "port": ...}, ...]}
            if "data" in data and isinstance(data["data"], list):
                for item in data["data"]:
                    if isinstance(item, dict):
                        ip = item.get("ip")
                        port = item.get("port")
                        
                        if ip and port:
                            try:
                                proxy = Proxy(
                                    ip=str(ip),
                                    port=int(port),
                                    protocol=self.source["protocols"][0].value if self.source["protocols"] else "http",
                                    country=item.get("country"),
                                    source=self.source["name"],
                                )
                                proxies.append(proxy)
                            except (ValueError, TypeError):
                                continue
            
            # Альтернативный формат: прямой список
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        ip = item.get("ip") or item.get("proxy")
                        port = item.get("port")
                        
                        if ip and port:
                            try:
                                proxy = Proxy(
                                    ip=str(ip),
                                    port=int(port),
                                    protocol=self.source["protocols"][0].value if self.source["protocols"] else "http",
                                    source=self.source["name"],
                                )
                                proxies.append(proxy)
                            except (ValueError, TypeError):
                                continue
            
        except Exception as e:
            logger.error(f"[{self.source['name']}] Ошибка парсинга JSON данных: {e}")
        
        result.proxies = proxies
        result.success = len(proxies) > 0
        
        if not result.success:
            result.error = "No valid proxies found in JSON response"
            self._set_cache(result)
            raise ParseError(self.source["name"], result.error)
        
        logger.info(f"[{self.source['name']}] Найдено {len(proxies)} прокси")
        
        self._set_cache(result)
        return result
