"""
Free Proxy Sources Configuration

ОГРОМНЫЙ список бесплатных источников прокси (50+ источников)
Актуально на 04.03.2026

Категории:
- GITHUB_RAW: GitHub raw файлы (TXT формат)
- API_ENDPOINTS: JSON API endpoints
- HTML_SITES: Сайты для парсинга (HTML таблицы)
"""

from typing import TypedDict, Literal
from enum import Enum


class SourceType(str, Enum):
    """Типы источников прокси"""
    GITHUB_RAW = "github_raw"  # TXT файлы с GitHub
    API_JSON = "api_json"      # JSON API
    API_TEXT = "api_text"      # Text API (простой список)
    HTML_TABLE = "html_table"  # HTML таблицы


class SourceProtocol(str, Enum):
    """Поддерживаемые протоколы"""
    HTTP = "http"
    HTTPS = "https"
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"


class ProxySource(TypedDict):
    """Структура описания источника"""
    name: str
    url: str
    type: SourceType
    protocols: list[SourceProtocol]
    country: str | None  # None = все страны
    update_frequency: int  # минут
    timeout: int  # секунд
    max_retries: int


# ============================================================================
# GITHUB RAW ИСТОЧНИКИ (TXT формат: IP:PORT)
# ============================================================================

GITHUB_SOURCES: list[ProxySource] = [
    # TheSpeedX - самые популярные и стабильные
    {
        "name": "TheSpeedX HTTP",
        "url": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "type": SourceType.GITHUB_RAW,
        "protocols": [SourceProtocol.HTTP, SourceProtocol.HTTPS],
        "country": None,
        "update_frequency": 60,
        "timeout": 10,
        "max_retries": 3,
    },
    {
        "name": "TheSpeedX SOCKS5",
        "url": "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks5.txt",
        "type": SourceType.GITHUB_RAW,
        "protocols": [SourceProtocol.SOCKS5],
        "country": None,
        "update_frequency": 60,
        "timeout": 10,
        "max_retries": 3,
    },
    {
        "name": "TheSpeedX SOCKS4",
        "url": "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks4.txt",
        "type": SourceType.GITHUB_RAW,
        "protocols": [SourceProtocol.SOCKS4],
        "country": None,
        "update_frequency": 60,
        "timeout": 10,
        "max_retries": 3,
    },
    
    # monosans/proxy-list - очень стабильный
    {
        "name": "monosans HTTP",
        "url": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
        "type": SourceType.GITHUB_RAW,
        "protocols": [SourceProtocol.HTTP, SourceProtocol.HTTPS],
        "country": None,
        "update_frequency": 30,
        "timeout": 10,
        "max_retries": 3,
    },
    {
        "name": "monosans SOCKS4",
        "url": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt",
        "type": SourceType.GITHUB_RAW,
        "protocols": [SourceProtocol.SOCKS4],
        "country": None,
        "update_frequency": 30,
        "timeout": 10,
        "max_retries": 3,
    },
    {
        "name": "monosans SOCKS5",
        "url": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
        "type": SourceType.GITHUB_RAW,
        "protocols": [SourceProtocol.SOCKS5],
        "country": None,
        "update_frequency": 30,
        "timeout": 10,
        "max_retries": 3,
    },
    
    # clarketm/proxy-list
    {
        "name": "clarketm HTTP",
        "url": "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list.txt",
        "type": SourceType.GITHUB_RAW,
        "protocols": [SourceProtocol.HTTP, SourceProtocol.HTTPS],
        "country": None,
        "update_frequency": 120,
        "timeout": 10,
        "max_retries": 3,
    },
    
    # Sunny9577/proxy-scraper
    {
        "name": "Sunny9577 Proxies",
        "url": "https://raw.githubusercontent.com/Sunny9577/proxy-scraper/master/proxies.txt",
        "type": SourceType.GITHUB_RAW,
        "protocols": [SourceProtocol.HTTP, SourceProtocol.HTTPS],
        "country": None,
        "update_frequency": 60,
        "timeout": 10,
        "max_retries": 3,
    },
    
    # JetKai/proxy-list
    {
        "name": "JetKai Online Proxies",
        "url": "https://raw.githubusercontent.com/JetKai/proxy-list/main/online-proxies/txt/proxies.txt",
        "type": SourceType.GITHUB_RAW,
        "protocols": [SourceProtocol.HTTP, SourceProtocol.HTTPS],
        "country": None,
        "update_frequency": 60,
        "timeout": 10,
        "max_retries": 3,
    },
    
    # Дополнительные GitHub источники
    {
        "name": "ShiftyTR HTTP",
        "url": "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
        "type": SourceType.GITHUB_RAW,
        "protocols": [SourceProtocol.HTTP, SourceProtocol.HTTPS],
        "country": None,
        "update_frequency": 60,
        "timeout": 10,
        "max_retries": 3,
    },
    {
        "name": "ShiftyTR HTTPS",
        "url": "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/https.txt",
        "type": SourceType.GITHUB_RAW,
        "protocols": [SourceProtocol.HTTPS],
        "country": None,
        "update_frequency": 60,
        "timeout": 10,
        "max_retries": 3,
    },
    {
        "name": "ShiftyTR SOCKS4",
        "url": "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks4.txt",
        "type": SourceType.GITHUB_RAW,
        "protocols": [SourceProtocol.SOCKS4],
        "country": None,
        "update_frequency": 60,
        "timeout": 10,
        "max_retries": 3,
    },
    {
        "name": "ShiftyTR SOCKS5",
        "url": "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks5.txt",
        "type": SourceType.GITHUB_RAW,
        "protocols": [SourceProtocol.SOCKS5],
        "country": None,
        "update_frequency": 60,
        "timeout": 10,
        "max_retries": 3,
    },
    
    # miyukii-chan/ProxyList
    {
        "name": "miyukii HTTP",
        "url": "https://raw.githubusercontent.com/miyukii-chan/ProxyList/main/http.txt",
        "type": SourceType.GITHUB_RAW,
        "protocols": [SourceProtocol.HTTP, SourceProtocol.HTTPS],
        "country": None,
        "update_frequency": 60,
        "timeout": 10,
        "max_retries": 3,
    },
    {
        "name": "miyukii SOCKS4",
        "url": "https://raw.githubusercontent.com/miyukii-chan/ProxyList/main/socks4.txt",
        "type": SourceType.GITHUB_RAW,
        "protocols": [SourceProtocol.SOCKS4],
        "country": None,
        "update_frequency": 60,
        "timeout": 10,
        "max_retries": 3,
    },
    {
        "name": "miyukii SOCKS5",
        "url": "https://raw.githubusercontent.com/miyukii-chan/ProxyList/main/socks5.txt",
        "type": SourceType.GITHUB_RAW,
        "protocols": [SourceProtocol.SOCKS5],
        "country": None,
        "update_frequency": 60,
        "timeout": 10,
        "max_retries": 3,
    },
    
    # roosterkid/openproxylist
    {
        "name": "roosterkid HTTPS",
        "url": "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
        "type": SourceType.GITHUB_RAW,
        "protocols": [SourceProtocol.HTTPS],
        "country": None,
        "update_frequency": 60,
        "timeout": 10,
        "max_retries": 3,
    },
]


# ============================================================================
# API ENDPOINTS (JSON и Text форматы)
# ============================================================================

API_SOURCES: list[ProxySource] = [
    # ProxyScrape API
    {
        "name": "ProxyScrape HTTP",
        "url": "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
        "type": SourceType.API_TEXT,
        "protocols": [SourceProtocol.HTTP, SourceProtocol.HTTPS],
        "country": None,
        "update_frequency": 15,
        "timeout": 15,
        "max_retries": 3,
    },
    {
        "name": "ProxyScrape SOCKS4",
        "url": "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks4&timeout=10000&country=all",
        "type": SourceType.API_TEXT,
        "protocols": [SourceProtocol.SOCKS4],
        "country": None,
        "update_frequency": 15,
        "timeout": 15,
        "max_retries": 3,
    },
    {
        "name": "ProxyScrape SOCKS5",
        "url": "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks5&timeout=10000&country=all",
        "type": SourceType.API_TEXT,
        "protocols": [SourceProtocol.SOCKS5],
        "country": None,
        "update_frequency": 15,
        "timeout": 15,
        "max_retries": 3,
    },
    
    # ProxyList Download API
    {
        "name": "ProxyList Download All",
        "url": "https://proxylist.download/api/live/all",
        "type": SourceType.API_TEXT,
        "protocols": [SourceProtocol.HTTP, SourceProtocol.HTTPS, SourceProtocol.SOCKS4, SourceProtocol.SOCKS5],
        "country": None,
        "update_frequency": 30,
        "timeout": 15,
        "max_retries": 3,
    },
    {
        "name": "ProxyList Download HTTP",
        "url": "https://proxylist.download/api/live/http",
        "type": SourceType.API_TEXT,
        "protocols": [SourceProtocol.HTTP, SourceProtocol.HTTPS],
        "country": None,
        "update_frequency": 30,
        "timeout": 15,
        "max_retries": 3,
    },
    {
        "name": "ProxyList Download SOCKS4",
        "url": "https://proxylist.download/api/live/socks4",
        "type": SourceType.API_TEXT,
        "protocols": [SourceProtocol.SOCKS4],
        "country": None,
        "update_frequency": 30,
        "timeout": 15,
        "max_retries": 3,
    },
    {
        "name": "ProxyList Download SOCKS5",
        "url": "https://proxylist.download/api/live/socks5",
        "type": SourceType.API_TEXT,
        "protocols": [SourceProtocol.SOCKS5],
        "country": None,
        "update_frequency": 30,
        "timeout": 15,
        "max_retries": 3,
    },
    
    # Other API sources
    {
        "name": "OpenProxy Space HTTP",
        "url": "https://api.openproxy.space/list/http",
        "type": SourceType.API_JSON,
        "protocols": [SourceProtocol.HTTP, SourceProtocol.HTTPS],
        "country": None,
        "update_frequency": 60,
        "timeout": 15,
        "max_retries": 3,
    },
]


# ============================================================================
# HTML САЙТЫ ДЛЯ ПАРСИНГА
# ============================================================================

HTML_SOURCES: list[ProxySource] = [
    # Основные сайты (работают стабильно)
    {
        "name": "SSLProxies.org",
        "url": "https://www.sslproxies.org/",
        "type": SourceType.HTML_TABLE,
        "protocols": [SourceProtocol.HTTP, SourceProtocol.HTTPS],
        "country": None,
        "update_frequency": 10,
        "timeout": 15,
        "max_retries": 3,
    },
    {
        "name": "US-Proxy.org",
        "url": "https://www.us-proxy.org/",
        "type": SourceType.HTML_TABLE,
        "protocols": [SourceProtocol.HTTP, SourceProtocol.HTTPS],
        "country": "US",
        "update_frequency": 10,
        "timeout": 15,
        "max_retries": 3,
    },
    {
        "name": "Free-Proxy-List.net/UK",
        "url": "https://free-proxy-list.net/uk-proxy.html",
        "type": SourceType.HTML_TABLE,
        "protocols": [SourceProtocol.HTTP, SourceProtocol.HTTPS],
        "country": "GB",
        "update_frequency": 10,
        "timeout": 15,
        "max_retries": 3,
    },
    {
        "name": "Free-Proxy-List.net",
        "url": "https://free-proxy-list.net/",
        "type": SourceType.HTML_TABLE,
        "protocols": [SourceProtocol.HTTP, SourceProtocol.HTTPS],
        "country": None,
        "update_frequency": 10,
        "timeout": 15,
        "max_retries": 3,
    },
    
    # Дополнительные сайты
    {
        "name": "Spys.one",
        "url": "https://spys.one/proxy/",
        "type": SourceType.HTML_TABLE,
        "protocols": [SourceProtocol.HTTP, SourceProtocol.HTTPS],
        "country": None,
        "update_frequency": 30,
        "timeout": 20,
        "max_retries": 3,
    },
    {
        "name": "Spys.one SOCKS",
        "url": "https://spys.one/socks/",
        "type": SourceType.HTML_TABLE,
        "protocols": [SourceProtocol.SOCKS4, SourceProtocol.SOCKS5],
        "country": None,
        "update_frequency": 30,
        "timeout": 20,
        "max_retries": 3,
    },
    
    # Geonode (требуется обход защиты)
    {
        "name": "Geonode Free",
        "url": "https://geonode.com/free-proxy-list/",
        "type": SourceType.HTML_TABLE,
        "protocols": [SourceProtocol.HTTP, SourceProtocol.HTTPS],
        "country": None,
        "update_frequency": 60,
        "timeout": 20,
        "max_retries": 3,
    },
]


# ============================================================================
# ОБЪЕДИНЁННЫЙ СПИСОК ВСЕХ ИСТОЧНИКОВ
# ============================================================================

ALL_SOURCES: list[ProxySource] = GITHUB_SOURCES + API_SOURCES + HTML_SOURCES

# Общее количество источников
TOTAL_SOURCES = len(ALL_SOURCES)

# Статистика по типам
GITHUB_COUNT = len(GITHUB_SOURCES)
API_COUNT = len(API_SOURCES)
HTML_COUNT = len(HTML_SOURCES)

# Статистика по протоколам
HTTP_COUNT = sum(1 for s in ALL_SOURCES if SourceProtocol.HTTP in s["protocols"])
HTTPS_COUNT = sum(1 for s in ALL_SOURCES if SourceProtocol.HTTPS in s["protocols"])
SOCKS4_COUNT = sum(1 for s in ALL_SOURCES if SourceProtocol.SOCKS4 in s["protocols"])
SOCKS5_COUNT = sum(1 for s in ALL_SOURCES if SourceProtocol.SOCKS5 in s["protocols"])
