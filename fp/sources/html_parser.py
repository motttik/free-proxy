"""
HTML Source Parser Module

Парсер для HTML таблиц с прокси (sslproxies.org, us-proxy.org, etc.)
"""

import logging
from typing import TYPE_CHECKING

import requests
from requests.exceptions import RequestException, Timeout, ConnectionError
from lxml import html as lh

from fp.config import ProxySource, SourceType
from fp.sources.base import BaseSourceParser, ParseResult, Proxy
from fp.errors import SourceFetchError, ParseError

if TYPE_CHECKING:
    from fp.config import SourceProtocol

logger = logging.getLogger(__name__)


class HtmlSourceParser(BaseSourceParser):
    """
    Парсер для HTML таблиц с прокси
    
    Поддерживает сайты:
    - sslproxies.org (//*[@id="proxylisttable"])
    - us-proxy.org (//*[@id="proxylisttable"])
    - free-proxy-list.net (//*[@id="proxylisttable"])
    - spys.one (сложная структура)
    """
    
    # XPath для разных сайтов
    XPATHS = {
        "proxylisttable": '//*[@id="proxylisttable"]//tr[td]',
        "list": '//*[@id="list"]//tr[td]',  # fallback для старых версий
        "spys": '//table[@class="proxy_list"]//tr[td]',
        "geonode": '//table[@id="proxylisttable"]//tr[td]',
    }
    
    def __init__(self, source: ProxySource) -> None:
        super().__init__(source)
        
        if source["type"] != SourceType.HTML_TABLE:
            logger.warning(
                f"HtmlSourceParser инициализирован для источника типа {source['type']}, "
                f"ожидался HTML_TABLE"
            )
        
        # Определяем XPath на основе URL
        self._xpath = self._detect_xpath(source["url"])
    
    def _detect_xpath(self, url: str) -> str:
        """Определить XPath на основе URL"""
        url_lower = url.lower()
        
        if "spys.one" in url_lower:
            return self.XPATHS["spys"]
        elif "geonode" in url_lower:
            return self.XPATHS["geonode"]
        else:
            # Основной XPath для proxylist сайтов
            return self.XPATHS["proxylisttable"]
    
    def parse(self) -> ParseResult:
        """
        Скачать и распарсить HTML таблицу с прокси
        
        Returns:
            ParseResult со списком прокси
        """
        # Проверяем кэш
        if self.is_fresh(self.source["timeout"] * 6):  # TTL = timeout * 6
            cached = self.get_cached()
            if cached:
                logger.debug(f"Использую кэш для {self.source['name']}")
                return cached
        
        result = ParseResult(source_name=self.source["name"])
        
        try:
            # Скачиваем страницу
            logger.info(f"Загрузка {self.source['name']} из {self.source['url']}")
            response = requests.get(
                self.source["url"],
                timeout=self.source["timeout"],
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
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
        
        # Парсим HTML
        try:
            doc = lh.fromstring(response.content)
        except Exception as e:
            error_msg = f"HTML parse error: {str(e)}"
            logger.error(f"[{self.source['name']}] {error_msg}")
            result.success = False
            result.error = error_msg
            self._set_cache(result)
            raise ParseError(self.source["name"], error_msg) from e
        
        # Находим таблицу
        try:
            tr_elements = doc.xpath(self._xpath)
        except Exception as e:
            error_msg = f"XPath error: {str(e)}"
            logger.error(f"[{self.source['name']}] {error_msg}")
            result.success = False
            result.error = error_msg
            self._set_cache(result)
            raise ParseError(self.source["name"], error_msg) from e
        
        if not tr_elements:
            # Пробуем fallback XPath
            if self._xpath != self.XPATHS["list"]:
                logger.warning(f"[{self.source['name']}] Основной XPath не нашёл элементов, пробую fallback")
                try:
                    tr_elements = doc.xpath(self.XPATHS["list"])
                except Exception:
                    pass
        
        if not tr_elements:
            error_msg = "No proxy rows found in HTML table"
            logger.error(f"[{self.source['name']}] {error_msg}")
            result.success = False
            result.error = error_msg
            self._set_cache(result)
            raise ParseError(self.source["name"], error_msg)
        
        # Парсим строки
        proxies: list[Proxy] = []
        
        for tr in tr_elements:
            try:
                proxy = self._parse_row(tr)
                if proxy:
                    proxy.source = self.source["name"]
                    proxies.append(proxy)
            except Exception as e:
                logger.debug(f"[{self.source['name']}] Ошибка парсинга строки: {e}")
                continue
        
        result.proxies = proxies
        result.success = len(proxies) > 0
        
        if not result.success:
            result.error = "No valid proxies found in HTML table"
            self._set_cache(result)
            raise ParseError(self.source["name"], result.error)
        
        logger.info(f"[{self.source['name']}] Найдено {len(proxies)} прокси")
        
        self._set_cache(result)
        return result
    
    def _parse_row(self, tr) -> Proxy | None:
        """
        Распарсить одну строку таблицы
        
        Args:
            tr: lxml элемент строки таблицы
            
        Returns:
            Proxy или None
        """
        try:
            tds = tr.xpath("td")
            
            if len(tds) < 7:
                return None
            
            # Стандартная структура таблицы:
            # 0: IP Address
            # 1: Port
            # 2: Code (country)
            # 3: Country
            # 4: Anonymity
            # 5: Google
            # 6: Https
            # 7: Last Checked
            
            ip = tds[0].text_content().strip()
            port_str = tds[1].text_content().strip()
            country_code = tds[2].text_content().strip() if len(tds) > 2 else None
            country = tds[3].text_content().strip() if len(tds) > 3 else None
            anonymity = tds[4].text_content().strip().lower() if len(tds) > 4 else None
            google_str = tds[5].text_content().strip().lower() if len(tds) > 5 else None
            https_str = tds[6].text_content().strip().lower() if len(tds) > 6 else None
            
            # Валидация IP и порта
            if not self.validate_proxy_string(f"{ip}:{port_str}"):
                return None
            
            port = int(port_str)
            
            # Определяем протокол
            protocol = "https" if https_str == "yes" else "http"
            
            # Google поддержка
            google = google_str == "yes" if google_str else None
            
            # HTTPS поддержка
            https = https_str == "yes" if https_str else None
            
            return Proxy(
                ip=ip,
                port=port,
                protocol=protocol,
                country=country_code,
                anonymity=anonymity,
                google=google,
                https=https,
            )
            
        except Exception as e:
            logger.debug(f"Ошибка парсинга строки: {e}")
            return None
