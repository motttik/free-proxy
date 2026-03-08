"""
Tests for Checker Modules

Полное покрытие для:
- fp.checkers.async_checker
- fp.checkers.sync_checker
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock

from fp.checkers.async_checker import AsyncProxyChecker
from fp.checkers.sync_checker import SyncProxyChecker
from fp.sources.base import Proxy


# ============================================================================
# ASYNC PROXY CHECKER TESTS
# ============================================================================

class TestAsyncProxyCheckerInit:
    """Тесты инициализации AsyncProxyChecker"""

    def test_init_default(self):
        """Инициализация по умолчанию"""
        checker = AsyncProxyChecker()
        assert checker.test_url == "https://httpbin.org/ip"
        assert checker.timeout == 5.0
        assert checker.max_concurrent == 20
        assert checker._semaphore is None

    def test_init_custom(self):
        """Кастомная инициализация"""
        checker = AsyncProxyChecker(
            test_url="https://example.com",
            timeout=10.0,
            max_concurrent=50,
        )
        assert checker.test_url == "https://example.com"
        assert checker.timeout == 10.0
        assert checker.max_concurrent == 50


class TestAsyncProxyCheckerCheck:
    """Тесты проверки прокси"""

    @pytest.mark.asyncio
    async def test_check_success(self):
        """Успешная проверка"""
        checker = AsyncProxyChecker()
        checker._semaphore = AsyncMock()
        checker._semaphore.__aenter__ = AsyncMock()
        checker._semaphore.__aexit__ = AsyncMock()
        
        proxy = Proxy(ip="1.1.1.1", port=8080, protocol="http")
        
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"origin": "1.1.1.1"})
        
        mock_session.get = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock()
        
        result = await checker.check(proxy, mock_session)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_check_http_error(self):
        """HTTP ошибка"""
        checker = AsyncProxyChecker()
        checker._semaphore = MagicMock()
        checker._semaphore.__aenter__ = AsyncMock()
        checker._semaphore.__aexit__ = AsyncMock()
        
        proxy = Proxy(ip="1.1.1.1", port=8080, protocol="http")
        
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 500
        
        mock_session.get = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock()
        
        result = await checker.check(proxy, mock_session)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_check_ip_mismatch(self):
        """Несовпадение IP"""
        checker = AsyncProxyChecker()
        checker._semaphore = MagicMock()
        checker._semaphore.__aenter__ = AsyncMock()
        checker._semaphore.__aexit__ = AsyncMock()
        
        proxy = Proxy(ip="1.1.1.1", port=8080, protocol="http")
        
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"origin": "2.2.2.2"})  # Другой IP
        
        mock_session.get = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock()
        
        result = await checker.check(proxy, mock_session)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_check_timeout(self):
        """Timeout"""
        checker = AsyncProxyChecker()
        checker._semaphore = MagicMock()
        checker._semaphore.__aenter__ = AsyncMock()
        checker._semaphore.__aexit__ = AsyncMock()
        
        proxy = Proxy(ip="1.1.1.1", port=8080, protocol="http")
        
        mock_session = AsyncMock()
        mock_session.get.side_effect = asyncio.TimeoutError()
        
        result = await checker.check(proxy, mock_session)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_check_server_disconnected(self):
        """Сервер разорвал соединение"""
        checker = AsyncProxyChecker()
        checker._semaphore = MagicMock()
        checker._semaphore.__aenter__ = AsyncMock()
        checker._semaphore.__aexit__ = AsyncMock()
        
        proxy = Proxy(ip="1.1.1.1", port=8080, protocol="http")
        
        mock_session = AsyncMock()
        
        from aiohttp import ServerDisconnectedError
        mock_session.get.side_effect = ServerDisconnectedError()
        
        result = await checker.check(proxy, mock_session)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_check_client_error(self):
        """Client ошибка"""
        checker = AsyncProxyChecker()
        checker._semaphore = MagicMock()
        checker._semaphore.__aenter__ = AsyncMock()
        checker._semaphore.__aexit__ = AsyncMock()
        
        proxy = Proxy(ip="1.1.1.1", port=8080, protocol="http")
        
        mock_session = AsyncMock()
        
        from aiohttp import ClientError
        mock_session.get.side_effect = ClientError()
        
        result = await checker.check(proxy, mock_session)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_check_json_parse_error(self):
        """Ошибка парсинга JSON"""
        checker = AsyncProxyChecker()
        checker._semaphore = MagicMock()
        checker._semaphore.__aenter__ = AsyncMock()
        checker._semaphore.__aexit__ = AsyncMock()
        
        proxy = Proxy(ip="1.1.1.1", port=8080, protocol="http")
        
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(side_effect=ValueError("Invalid JSON"))
        
        mock_session.get = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock()
        
        # При ошибке парсинга JSON считается что OK
        result = await checker.check(proxy, mock_session)
        
        assert result is True


class TestAsyncProxyCheckerCheckMultiple:
    """Тесты множественной проверки"""

    @pytest.mark.asyncio
    async def test_check_multiple_empty(self):
        """Пустой список"""
        checker = AsyncProxyChecker()
        
        result = await checker.check_multiple([])
        
        assert result == []

    @pytest.mark.asyncio
    async def test_check_multiple_success(self):
        """Успешная проверка нескольких"""
        checker = AsyncProxyChecker()
        
        proxies = [
            Proxy(ip="1.1.1.1", port=8080, protocol="http"),
            Proxy(ip="2.2.2.2", port=3128, protocol="http"),
        ]
        
        async def mock_check(proxy, session):
            return True
        
        checker.check = mock_check
        checker._semaphore = MagicMock()
        checker._semaphore.__aenter__ = AsyncMock()
        checker._semaphore.__aexit__ = AsyncMock()
        
        result = await checker.check_multiple(proxies)
        
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_check_multiple_stop_on_first(self):
        """Остановка на первом успешном"""
        checker = AsyncProxyChecker()
        
        proxies = [
            Proxy(ip="1.1.1.1", port=8080, protocol="http"),
            Proxy(ip="2.2.2.2", port=3128, protocol="http"),
            Proxy(ip="3.3.3.3", port=80, protocol="http"),
        ]
        
        async def mock_check(proxy, session):
            return proxy.ip == "1.1.1.1"  # Только первый успешный
        
        checker.check = mock_check
        checker._semaphore = MagicMock()
        checker._semaphore.__aenter__ = AsyncMock()
        checker._semaphore.__aexit__ = AsyncMock()
        
        result = await checker.check_multiple(proxies, stop_on_first=True)
        
        assert len(result) == 1
        assert result[0].ip == "1.1.1.1"

    @pytest.mark.asyncio
    async def test_check_multiple_all_fail(self):
        """Все прокси не работают"""
        checker = AsyncProxyChecker()
        
        proxies = [
            Proxy(ip="1.1.1.1", port=8080, protocol="http"),
            Proxy(ip="2.2.2.2", port=3128, protocol="http"),
        ]
        
        async def mock_check(proxy, session):
            return False
        
        checker.check = mock_check
        checker._semaphore = MagicMock()
        checker._semaphore.__aenter__ = AsyncMock()
        checker._semaphore.__aexit__ = AsyncMock()
        
        result = await checker.check_multiple(proxies)
        
        assert result == []

    @pytest.mark.asyncio
    async def test_check_multiple_with_progress(self):
        """Проверка с прогрессом"""
        checker = AsyncProxyChecker()
        
        proxies = [
            Proxy(ip="1.1.1.1", port=8080, protocol="http"),
        ]
        
        async def mock_check(proxy, session):
            return True
        
        checker.check = mock_check
        checker._semaphore = MagicMock()
        checker._semaphore.__aenter__ = AsyncMock()
        checker._semaphore.__aexit__ = AsyncMock()
        
        # tqdm может быть не установлен
        result = await checker.check_multiple(proxies, show_progress=True)
        
        assert len(result) == 1


class TestAsyncProxyCheckerGetProxyUrl:
    """Тесты получения proxy URL"""

    def test_get_proxy_url_http(self):
        """HTTP прокси"""
        checker = AsyncProxyChecker()
        proxy = Proxy(ip="1.1.1.1", port=8080, protocol="http")
        
        url = checker._get_proxy_url(proxy)
        
        assert url == "http://1.1.1.1:8080"

    def test_get_proxy_url_https(self):
        """HTTPS прокси"""
        checker = AsyncProxyChecker()
        proxy = Proxy(ip="1.1.1.1", port=8080, protocol="https")
        
        url = checker._get_proxy_url(proxy)
        
        assert url == "https://1.1.1.1:8080"

    def test_get_proxy_url_socks4(self):
        """SOCKS4 прокси"""
        checker = AsyncProxyChecker()
        proxy = Proxy(ip="1.1.1.1", port=1080, protocol="socks4")
        
        url = checker._get_proxy_url(proxy)
        
        assert url == "socks4://1.1.1.1:1080"

    def test_get_proxy_url_socks5(self):
        """SOCKS5 прокси"""
        checker = AsyncProxyChecker()
        proxy = Proxy(ip="1.1.1.1", port=1080, protocol="socks5")
        
        url = checker._get_proxy_url(proxy)
        
        assert url == "socks5://1.1.1.1:1080"


class TestAsyncProxyCheckerQuickCheck:
    """Тесты быстрой проверки"""

    @pytest.mark.asyncio
    async def test_quick_check_success(self):
        """Успешная быстрая проверка"""
        checker = AsyncProxyChecker()
        
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"origin": "1.1.1.1"})
        
        mock_session.get = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock()
        
        mock_connector = MagicMock()
        mock_connector.__aenter__ = AsyncMock(return_value=mock_connector)
        mock_connector.__aexit__ = AsyncMock()
        
        with patch('fp.checkers.async_checker.aiohttp.ClientSession', return_value=mock_session), \
             patch('fp.checkers.async_checker.aiohttp.TCPConnector', return_value=mock_connector):
            
            # Мокаем check метод
            checker.check = AsyncMock(return_value=True)
            
            result = await checker.quick_check("1.1.1.1", 8080, "http")
        
        assert result is True

    @pytest.mark.asyncio
    async def test_quick_check_failure(self):
        """Неудачная быстрая проверка"""
        checker = AsyncProxyChecker()
        
        mock_session = AsyncMock()
        
        with patch('fp.checkers.async_checker.aiohttp.ClientSession', return_value=mock_session), \
             patch('fp.checkers.async_checker.aiohttp.TCPConnector'):
            
            checker.check = AsyncMock(return_value=False)
            
            result = await checker.quick_check("1.1.1.1", 8080, "http")
        
        assert result is False


# ============================================================================
# SYNC PROXY CHECKER TESTS
# ============================================================================

class TestSyncProxyCheckerInit:
    """Тесты инициализации SyncProxyChecker"""

    def test_init_default(self):
        """Инициализация по умолчанию"""
        checker = SyncProxyChecker()
        assert checker.test_url == "https://httpbin.org/ip"
        assert checker.timeout == 5.0
        assert checker.check_google is False
        assert checker._session is not None

    def test_init_custom(self):
        """Кастомная инициализация"""
        checker = SyncProxyChecker(
            test_url="https://example.com",
            timeout=10.0,
            check_google=True,
        )
        assert checker.test_url == "https://example.com"
        assert checker.timeout == 10.0
        assert checker.check_google is True

    def test_init_creates_session(self):
        """Создание сессии"""
        checker = SyncProxyChecker()
        assert checker._session is not None

    def test_del_closes_session(self):
        """Закрытие сессии при удалении"""
        checker = SyncProxyChecker()
        session = checker._session
        
        checker.__del__()
        
        # Сессия должна быть закрыта
        assert session.close.called or not checker._session


class TestSyncProxyCheckerCheck:
    """Тесты проверки прокси"""

    def test_check_success(self):
        """Успешная проверка"""
        checker = SyncProxyChecker()
        
        proxy = Proxy(ip="1.1.1.1", port=8080, protocol="http")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"origin": "1.1.1.1"}
        
        checker._session.get = MagicMock(return_value=mock_response)
        
        result = checker.check(proxy)
        
        assert result is True

    def test_check_http_error(self):
        """HTTP ошибка"""
        checker = SyncProxyChecker()
        
        proxy = Proxy(ip="1.1.1.1", port=8080, protocol="http")
        
        mock_response = MagicMock()
        mock_response.status_code = 500
        
        checker._session.get = MagicMock(return_value=mock_response)
        
        result = checker.check(proxy)
        
        assert result is False

    def test_check_ip_mismatch(self):
        """Несовпадение IP"""
        checker = SyncProxyChecker()
        
        proxy = Proxy(ip="1.1.1.1", port=8080, protocol="http")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"origin": "2.2.2.2"}
        
        checker._session.get = MagicMock(return_value=mock_response)
        
        result = checker.check(proxy)
        
        assert result is False

    def test_check_timeout(self):
        """Timeout"""
        checker = SyncProxyChecker()
        
        proxy = Proxy(ip="1.1.1.1", port=8080, protocol="http")
        
        from requests.exceptions import Timeout
        checker._session.get = MagicMock(side_effect=Timeout())
        
        result = checker.check(proxy)
        
        assert result is False

    def test_check_connection_error(self):
        """Ошибка подключения"""
        checker = SyncProxyChecker()
        
        proxy = Proxy(ip="1.1.1.1", port=8080, protocol="http")
        
        from requests.exceptions import ConnectionError
        checker._session.get = MagicMock(side_effect=ConnectionError())
        
        result = checker.check(proxy)
        
        assert result is False

    def test_check_proxy_error(self):
        """Proxy ошибка"""
        checker = SyncProxyChecker()
        
        proxy = Proxy(ip="1.1.1.1", port=8080, protocol="http")
        
        from requests.exceptions import ProxyError
        checker._session.get = MagicMock(side_effect=ProxyError())
        
        result = checker.check(proxy)
        
        assert result is False

    def test_check_json_parse_error(self):
        """Ошибка парсинга JSON"""
        checker = SyncProxyChecker()
        
        proxy = Proxy(ip="1.1.1.1", port=8080, protocol="http")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        
        checker._session.get = MagicMock(return_value=mock_response)
        
        # При ошибке парсинга JSON считается что OK
        result = checker.check(proxy)
        
        assert result is True


class TestSyncProxyCheckerCheckMultiple:
    """Тесты множественной проверки"""

    def test_check_multiple_empty(self):
        """Пустой список"""
        checker = SyncProxyChecker()
        
        result = checker.check_multiple([])
        
        assert result == []

    def test_check_multiple_success(self):
        """Успешная проверка нескольких"""
        checker = SyncProxyChecker()
        
        proxies = [
            Proxy(ip="1.1.1.1", port=8080, protocol="http"),
            Proxy(ip="2.2.2.2", port=3128, protocol="http"),
        ]
        
        checker.check = MagicMock(return_value=True)
        
        result = checker.check_multiple(proxies)
        
        assert len(result) == 2

    def test_check_multiple_stop_on_first(self):
        """Остановка на первом успешном"""
        checker = SyncProxyChecker()
        
        proxies = [
            Proxy(ip="1.1.1.1", port=8080, protocol="http"),
            Proxy(ip="2.2.2.2", port=3128, protocol="http"),
            Proxy(ip="3.3.3.3", port=80, protocol="http"),
        ]
        
        def mock_check(proxy):
            return proxy.ip == "1.1.1.1"
        
        checker.check = mock_check
        
        result = checker.check_multiple(proxies, stop_on_first=True)
        
        assert len(result) == 1
        assert result[0].ip == "1.1.1.1"

    def test_check_multiple_all_fail(self):
        """Все прокси не работают"""
        checker = SyncProxyChecker()
        
        proxies = [
            Proxy(ip="1.1.1.1", port=8080, protocol="http"),
            Proxy(ip="2.2.2.2", port=3128, protocol="http"),
        ]
        
        checker.check = MagicMock(return_value=False)
        
        result = checker.check_multiple(proxies)
        
        assert result == []


class TestSyncProxyCheckerGetProxyUrl:
    """Тесты получения proxy URL"""

    def test_get_proxy_url_http(self):
        """HTTP прокси"""
        checker = SyncProxyChecker()
        proxy = Proxy(ip="1.1.1.1", port=8080, protocol="http")
        
        url = checker._get_proxy_url(proxy)
        
        assert url == "http://1.1.1.1:8080"

    def test_get_proxy_url_socks4(self):
        """SOCKS4 прокси"""
        checker = SyncProxyChecker()
        proxy = Proxy(ip="1.1.1.1", port=1080, protocol="socks4")
        
        url = checker._get_proxy_url(proxy)
        
        assert url == "socks4://1.1.1.1:1080"

    def test_get_proxy_url_socks5(self):
        """SOCKS5 прокси"""
        checker = SyncProxyChecker()
        proxy = Proxy(ip="1.1.1.1", port=1080, protocol="socks5")
        
        url = checker._get_proxy_url(proxy)
        
        assert url == "socks5://1.1.1.1:1080"


class TestSyncProxyCheckerQuickCheck:
    """Тесты быстрой проверки"""

    def test_quick_check_success(self):
        """Успешная быстрая проверка"""
        checker = SyncProxyChecker()
        checker.check = MagicMock(return_value=True)
        
        result = checker.quick_check("1.1.1.1", 8080, "http")
        
        assert result is True

    def test_quick_check_failure(self):
        """Неудачная быстрая проверка"""
        checker = SyncProxyChecker()
        checker.check = MagicMock(return_value=False)
        
        result = checker.quick_check("1.1.1.1", 8080, "http")
        
        assert result is False


# ============================================================================
# IMPORT TESTS
# ============================================================================

class TestCheckerImports:
    """Тесты импортов"""

    def test_import_async_checker(self):
        """Импорт AsyncProxyChecker"""
        from fp.checkers.async_checker import AsyncProxyChecker
        assert AsyncProxyChecker is not None

    def test_import_sync_checker(self):
        """Импорт SyncProxyChecker"""
        from fp.checkers.sync_checker import SyncProxyChecker
        assert SyncProxyChecker is not None

    def test_import_checkers_init(self):
        """Импорт из __init__"""
        from fp.checkers import AsyncProxyChecker, SyncProxyChecker
        assert AsyncProxyChecker is not None
        assert SyncProxyChecker is not None
