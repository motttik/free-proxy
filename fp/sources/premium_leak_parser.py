"""
Premium Leak Parser

Парсер для "слитых" платных прокси из GitHub Gist, Pastebin и других источников.

Поддерживаемые форматы:
- TXT: IP:PORT или IP:PORT:USER:PASS
- CSV: ip,port,protocol,country
- JSON: [{"ip": "...", "port": ...}, ...]

Особенности:
- Автоматическое определение формата
- Валидация IP/порт
- Дедупликация
- Поддержка прокси с авторизацией
"""

import re
import json
import logging
from typing import Optional, List, Tuple
from dataclasses import dataclass

import requests

from fp.sources.base import BaseSourceParser, ParseResult, Proxy
from fp.config import ProxySource, SourceProtocol

logger = logging.getLogger(__name__)


@dataclass
class ProxyWithCredentials(Proxy):
    """Прокси с авторизацией"""
    username: Optional[str] = None
    password: Optional[str] = None


class PremiumLeakParser(BaseSourceParser):
    """
    Парсер премиум прокси из слитых источников

    Поддерживает:
    - GitHub Gist (raw URLs)
    - Pastebin (raw URLs)
    - Другие текстовые хостинги
    """

    def __init__(self, source: ProxySource):
        super().__init__(source)
        self.is_premium = True  # Флаг premium источника
        self.max_retries = source.get("max_retries", 3)
        self.timeout = source.get("timeout", 30)

    def parse(self) -> ParseResult:
        """
        Получить и распарсить прокси из источника

        Returns:
            ParseResult с найденными прокси
        """
        try:
            # Fetch контента с retry logic
            content = self._fetch_with_retry()

            if not content or not content.strip():
                return ParseResult(
                    success=False,
                    error="Empty content received",
                    proxies=[],
                    
                )

            # Определяем формат
            fmt = self._detect_format(content)

            # Парсим в зависимости от формата
            if fmt == "txt":
                return self._parse_txt(content)
            elif fmt == "csv":
                return self._parse_csv(content)
            elif fmt == "json":
                return self._parse_json(content)
            else:
                return ParseResult(
                    success=False,
                    error=f"Unknown format: {fmt}",
                    proxies=[],
                    
                )

        except requests.exceptions.Timeout:
            logger.error(f"[{self.source['name']}] Request timeout")
            return ParseResult(
                success=False,
                error="Request timeout",
                proxies=[],
                
            )
        except requests.exceptions.ConnectionError as e:
            logger.error(f"[{self.source['name']}] Connection error: {e}")
            return ParseResult(
                success=False,
                error=f"Connection error: {e}",
                proxies=[],
                
            )
        except Exception as e:
            logger.error(f"[{self.source['name']}] Parse error: {e}")
            return ParseResult(
                success=False,
                error=f"Parse error: {e}",
                proxies=[],
                
            )

    def _fetch_with_retry(self) -> str:
        """Получить контент с retry logic"""
        last_error = None

        for attempt in range(self.max_retries):
            try:
                response = requests.get(
                    self.source["url"],
                    timeout=self.timeout,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    },
                )
                response.raise_for_status()
                return response.text

            except requests.exceptions.Timeout:
                last_error = "timeout"
                logger.warning(f"[{self.source['name']}] Timeout (attempt {attempt + 1}/{self.max_retries})")

            except requests.exceptions.ConnectionError:
                last_error = "connection_error"
                logger.warning(f"[{self.source['name']}] Connection error (attempt {attempt + 1}/{self.max_retries})")

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    logger.error(f"[{self.source['name']}] 404 Not Found")
                    raise  # 404 не retry-им
                last_error = f"http_{e.response.status_code}"
                logger.warning(f"[{self.source['name']}] HTTP {e.response.status_code} (attempt {attempt + 1}/{self.max_retries})")

            except Exception as e:
                last_error = str(e)
                logger.warning(f"[{self.source['name']}] Error: {e} (attempt {attempt + 1}/{self.max_retries})")

            # Backoff перед следующей попыткой
            if attempt < self.max_retries - 1:
                import time
                time.sleep(2 ** attempt)  # Exponential backoff

        raise requests.exceptions.RequestException(f"Failed after {self.max_retries} attempts: {last_error}")

    def _detect_format(self, content: str) -> str:
        """
        Автоматически определить формат контента

        Returns:
            "txt", "csv", или "json"
        """
        content = content.strip()

        # JSON: начинается с [ или {
        if content.startswith("[") or content.startswith("{"):
            try:
                json.loads(content)
                return "json"
            except json.JSONDecodeError:
                pass

        # CSV: есть заголовок с запятыми
        first_line = content.split("\n")[0].strip()
        if "," in first_line and any(h in first_line.lower() for h in ["ip", "port", "protocol", "country"]):
            return "csv"

        # TXT: по умолчанию
        return "txt"

    def _parse_txt(self, content: str) -> ParseResult:
        """
        Парсинг TXT формата

        Форматы:
        - IP:PORT
        - IP:PORT:PROTOCOL
        - IP:PORT:USER:PASS
        - IP:PORT:PROTOCOL:USER:PASS
        """
        proxies = []
        seen = set()

        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split(":")
            if len(parts) < 2:
                continue

            try:
                ip = parts[0].strip()
                port = int(parts[1].strip())

                # Валидация
                if not self._is_valid_ip(ip):
                    continue
                if not self._is_valid_port(port):
                    continue

                # Определяем протокол и авторизацию
                protocol = "http"  # по умолчанию
                username = None
                password = None

                if len(parts) >= 3:
                    third = parts[2].strip().lower()
                    if third in ("http", "https", "socks4", "socks5"):
                        protocol = third
                    elif third and not third.isdigit():
                        # Это username
                        username = third
                        if len(parts) >= 4:
                            password = parts[3].strip()

                if len(parts) >= 4 and username is None:
                    fourth = parts[3].strip().lower()
                    if fourth in ("http", "https", "socks4", "socks5"):
                        protocol = fourth
                    elif len(parts) >= 5:
                        username = parts[3].strip()
                        password = parts[4].strip()

                # Проверка на дубликаты
                key = f"{ip}:{port}"
                if key in seen:
                    continue
                seen.add(key)

                # Проверка протокола
                if not self._matches_protocol(protocol):
                    continue

                proxy = Proxy(
                    ip=ip,
                    port=port,
                    protocol=protocol,
                    country=None,
                    source=self.source["name"],
                    anonymity=None,
                    https=(protocol == "https"),
                    google=None,
                )

                proxies.append(proxy)

            except (ValueError, IndexError):
                continue

        if not proxies:
            return ParseResult(
                success=False,
                error="No valid proxies found in response",
                proxies=[],
            )

        return ParseResult(
            success=True,
            error=None,
            proxies=proxies,
        )

    def _parse_csv(self, content: str) -> ParseResult:
        """
        Парсинг CSV формата

        Ожидаемые колонки: ip,port,protocol,country
        """
        proxies = []
        seen = set()
        lines = content.strip().split("\n")

        if len(lines) < 2:
            return ParseResult(
                success=False,
                error="CSV must have header and at least one data row",
                proxies=[],
                
            )

        # Парсим заголовок
        header = [h.strip().lower() for h in lines[0].split(",")]

        try:
            ip_idx = header.index("ip")
            port_idx = header.index("port")
            protocol_idx = header.index("protocol") if "protocol" in header else None
            country_idx = header.index("country") if "country" in header else None
        except ValueError as e:
            return ParseResult(
                success=False,
                error=f"Missing required CSV columns: {e}",
                proxies=[],
                
            )

        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue

            parts = [p.strip() for p in line.split(",")]
            if len(parts) <= max(ip_idx, port_idx):
                continue

            try:
                ip = parts[ip_idx]
                port = int(parts[port_idx])

                # Валидация
                if not self._is_valid_ip(ip):
                    continue
                if not self._is_valid_port(port):
                    continue

                # Протокол
                protocol = "http"
                if protocol_idx is not None and len(parts) > protocol_idx:
                    protocol = parts[protocol_idx].strip().lower()

                # Страна
                country = None
                if country_idx is not None and len(parts) > country_idx:
                    country = parts[country_idx].strip()

                # Проверка на дубликаты
                key = f"{ip}:{port}"
                if key in seen:
                    continue
                seen.add(key)

                # Проверка протокола
                if not self._matches_protocol(protocol):
                    continue

                proxy = Proxy(
                    ip=ip,
                    port=port,
                    protocol=protocol,
                    country=country,
                    source=self.source["name"],
                    anonymity=None,
                    https=(protocol == "https"),
                    google=None,
                    
                )

                proxies.append(proxy)

            except (ValueError, IndexError):
                continue

        if not proxies:
            return ParseResult(
                success=False,
                error="No valid proxies found in CSV",
                proxies=[],
                
            )

        return ParseResult(
            success=True,
            error=None,
            proxies=proxies,
            
        )

    def _parse_json(self, content: str) -> ParseResult:
        """
        Парсинг JSON формата

        Ожидаемый формат:
        [
            {"ip": "1.2.3.4", "port": 8080, "protocol": "http", "country": "US"},
            ...
        ]
        """
        proxies = []
        seen = set()

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            return ParseResult(
                success=False,
                error=f"Invalid JSON: {e}",
                proxies=[],
                
            )

        if not isinstance(data, list):
            data = [data]

        for item in data:
            if not isinstance(item, dict):
                continue

            try:
                ip = item.get("ip", "")
                port = item.get("port")
                protocol = item.get("protocol", "http").lower()
                country = item.get("country")

                if not ip or not port:
                    continue

                port = int(port)

                # Валидация
                if not self._is_valid_ip(ip):
                    continue
                if not self._is_valid_port(port):
                    continue

                # Проверка на дубликаты
                key = f"{ip}:{port}"
                if key in seen:
                    continue
                seen.add(key)

                # Проверка протокола
                if not self._matches_protocol(protocol):
                    continue

                proxy = Proxy(
                    ip=ip,
                    port=port,
                    protocol=protocol,
                    country=country,
                    source=self.source["name"],
                    anonymity=None,
                    https=(protocol == "https"),
                    google=None,
                    
                )

                proxies.append(proxy)

            except (ValueError, TypeError):
                continue

        if not proxies:
            return ParseResult(
                success=False,
                error="No valid proxies found in JSON",
                proxies=[],
                
            )

        return ParseResult(
            success=True,
            error=None,
            proxies=proxies,
            
        )

    def _is_valid_ip(self, ip: str) -> bool:
        """Проверить валидность IP адреса"""
        # IPv4 pattern
        ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        if not re.match(ipv4_pattern, ip):
            return False

        # Проверка октетов
        octets = ip.split(".")
        for octet in octets:
            if not (0 <= int(octet) <= 255):
                return False

        return True

    def _is_valid_port(self, port: int) -> bool:
        """Проверить валидность порта"""
        return 1 <= port <= 65535

    def _matches_protocol(self, protocol: str) -> bool:
        """Проверить соответствует ли протокол конфигурации"""
        if not protocol:
            return True

        protocol = protocol.lower()
        allowed = [p.value.lower() for p in self.source.get("protocols", [])]

        if not allowed:
            return True

        return protocol in allowed
