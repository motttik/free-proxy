"""
Tests for Parser Modules

Полное покрытие для:
- fp.sources.api_parser
- fp.sources.html_parser
- fp.sources.txt_parser
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from fp.sources.api_parser import ApiSourceParser
from fp.sources.html_parser import HtmlSourceParser
from fp.sources.txt_parser import TxtSourceParser
from fp.sources.base import ParseResult, Proxy
from fp.config import ProxySource, SourceType, SourceProtocol
from fp.errors import SourceFetchError, ParseError


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def api_source():
    """Создание тестового API источника"""
    return ProxySource(
        name="Test API",
        url="https://api.example.com/proxies",
        type=SourceType.API_JSON,
        protocols=[SourceProtocol.HTTP],
        country=None,
        update_frequency=60,
        timeout=10,
        max_retries=3,
    )


@pytest.fixture
def html_source():
    """Создание тестового HTML источника"""
    return ProxySource(
        name="Test HTML",
        url="https://sslproxies.org/",
        type=SourceType.HTML_TABLE,
        protocols=[SourceProtocol.HTTP, SourceProtocol.HTTPS],
        country=None,
        update_frequency=10,
        timeout=15,
        max_retries=3,
    )


@pytest.fixture
def txt_source():
    """Создание тестового TXT источника"""
    return ProxySource(
        name="Test TXT",
        url="https://raw.githubusercontent.com/test/proxy.txt",
        type=SourceType.GITHUB_RAW,
        protocols=[SourceProtocol.HTTP],
        country=None,
        update_frequency=60,
        timeout=10,
        max_retries=3,
    )


# ============================================================================
# API SOURCE PARSER TESTS
# ============================================================================

class TestApiSourceParserInit:
    """Тесты инициализации ApiSourceParser"""

    def test_init_correct_type(self, api_source):
        """Инициализация с правильным типом"""
        parser = ApiSourceParser(api_source)
        assert parser.source == api_source
        assert parser._cache is None

    def test_init_wrong_type(self):
        """Инициализация с неправильным типом"""
        source = ProxySource(
            name="Test",
            url="https://example.com",
            type=SourceType.HTML_TABLE,
            protocols=[SourceProtocol.HTTP],
            country=None,
            update_frequency=60,
            timeout=10,
            max_retries=3,
        )
        
        with pytest.warns(None):
            parser = ApiSourceParser(source)
            assert parser.source == source


class TestApiSourceParserParse:
    """Тесты парсинга API"""

    def test_parse_cached(self, api_source):
        """Парсинг из кэша"""
        parser = ApiSourceParser(api_source)
        
        cached_result = ParseResult(
            proxies=[Proxy(ip="1.1.1.1", port=8080, protocol="http")],
            source_name="Test API",
            success=True,
        )
        parser._cache = cached_result
        parser._cache_time = datetime.now()
        
        with patch.object(parser, 'is_fresh', return_value=True), \
             patch.object(parser, 'get_cached', return_value=cached_result):
            
            result = parser.parse()
        
        assert result.success is True
        assert len(result.proxies) == 1

    def test_parse_success(self, api_source):
        """Успешный парсинг"""
        parser = ApiSourceParser(api_source)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"ip": "1.1.1.1", "port": 8080, "country": "US"},
                {"ip": "2.2.2.2", "port": 3128, "country": "DE"},
            ]
        }
        
        with patch('fp.sources.api_parser.requests.get', return_value=mock_response), \
             patch.object(parser, 'is_fresh', return_value=False):
            
            result = parser.parse()
        
        assert result.success is True
        assert len(result.proxies) == 2
        assert result.proxies[0].ip == "1.1.1.1"

    def test_parse_timeout(self, api_source):
        """Timeout при парсинге"""
        parser = ApiSourceParser(api_source)
        
        with patch('fp.sources.api_parser.requests.get', side_effect=TimeoutError()), \
             patch.object(parser, 'is_fresh', return_value=False):
            
            with pytest.raises(SourceFetchError) as exc_info:
                parser.parse()
            
            assert "Timeout" in str(exc_info.value)

    def test_parse_connection_error(self, api_source):
        """Ошибка подключения"""
        parser = ApiSourceParser(api_source)
        
        with patch('fp.sources.api_parser.requests.get', side_effect=ConnectionError()), \
             patch.object(parser, 'is_fresh', return_value=False):
            
            with pytest.raises(SourceFetchError):
                parser.parse()

    def test_parse_json_error(self, api_source):
        """Ошибка парсинга JSON"""
        parser = ApiSourceParser(api_source)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        
        with patch('fp.sources.api_parser.requests.get', return_value=mock_response), \
             patch.object(parser, 'is_fresh', return_value=False):
            
            with pytest.raises(ParseError):
                parser.parse()

    def test_parse_empty_data(self, api_source):
        """Пустые данные"""
        parser = ApiSourceParser(api_source)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        
        with patch('fp.sources.api_parser.requests.get', return_value=mock_response), \
             patch.object(parser, 'is_fresh', return_value=False):
            
            with pytest.raises(ParseError) as exc_info:
                parser.parse()
            
            assert "No valid proxies" in str(exc_info.value)

    def test_parse_alternative_format(self):
        """Альтернативный формат JSON"""
        source = ProxySource(
            name="Test API",
            url="https://api.example.com/proxies",
            type=SourceType.API_JSON,
            protocols=[SourceProtocol.HTTP],
            country=None,
            update_frequency=60,
            timeout=10,
            max_retries=3,
        )
        parser = ApiSourceParser(source)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"ip": "1.1.1.1", "port": 8080},
            {"proxy": "2.2.2.2", "port": 3128},  # Альтернативное поле
        ]
        
        with patch('fp.sources.api_parser.requests.get', return_value=mock_response), \
             patch.object(parser, 'is_fresh', return_value=False):
            
            result = parser.parse()
        
        assert result.success is True
        assert len(result.proxies) == 2


class TestApiSourceParserCache:
    """Тесты кэширования API парсера"""

    def test_set_cache(self, api_source):
        """Установка кэша"""
        parser = ApiSourceParser(api_source)
        
        result = ParseResult(
            proxies=[Proxy(ip="1.1.1.1", port=8080, protocol="http")],
            source_name="Test API",
        )
        
        parser._set_cache(result)
        
        assert parser._cache == result
        assert parser._cache_time is not None


# ============================================================================
# HTML SOURCE PARSER TESTS
# ============================================================================

class TestHtmlSourceParserInit:
    """Тесты инициализации HtmlSourceParser"""

    def test_init_correct_type(self, html_source):
        """Инициализация с правильным типом"""
        parser = HtmlSourceParser(html_source)
        assert parser.source == html_source
        assert parser._xpath is not None

    def test_detect_xpath_sslproxies(self):
        """Определение XPath для sslproxies"""
        source = ProxySource(
            name="SSLProxies",
            url="https://www.sslproxies.org/",
            type=SourceType.HTML_TABLE,
            protocols=[SourceProtocol.HTTP],
            country=None,
            update_frequency=10,
            timeout=15,
            max_retries=3,
        )
        parser = HtmlSourceParser(source)
        assert parser._xpath == HtmlSourceParser.XPATHS["proxylisttable"]

    def test_detect_xpath_spys(self):
        """Определение XPath для spys.one"""
        source = ProxySource(
            name="Spys.one",
            url="https://spys.one/proxy/",
            type=SourceType.HTML_TABLE,
            protocols=[SourceProtocol.HTTP],
            country=None,
            update_frequency=30,
            timeout=20,
            max_retries=3,
        )
        parser = HtmlSourceParser(source)
        assert parser._xpath == HtmlSourceParser.XPATHS["spys"]

    def test_detect_xpath_geonode(self):
        """Определение XPath для geonode"""
        source = ProxySource(
            name="Geonode",
            url="https://geonode.com/free-proxy-list/",
            type=SourceType.HTML_TABLE,
            protocols=[SourceProtocol.HTTP],
            country=None,
            update_frequency=60,
            timeout=20,
            max_retries=3,
        )
        parser = HtmlSourceParser(source)
        assert parser._xpath == HtmlSourceParser.XPATHS["geonode"]


class TestHtmlSourceParserParse:
    """Тесты парсинга HTML"""

    def test_parse_cached(self, html_source):
        """Парсинг из кэша"""
        parser = HtmlSourceParser(html_source)
        
        cached_result = ParseResult(
            proxies=[Proxy(ip="1.1.1.1", port=8080, protocol="http")],
            source_name="Test HTML",
            success=True,
        )
        parser._cache = cached_result
        
        with patch.object(parser, 'is_fresh', return_value=True), \
             patch.object(parser, 'get_cached', return_value=cached_result):
            
            result = parser.parse()
        
        assert result.success is True

    def test_parse_success(self, html_source):
        """Успешный парсинг"""
        parser = HtmlSourceParser(html_source)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"""
        <html>
            <table id="proxylisttable">
                <tr>
                    <td>1.1.1.1</td>
                    <td>8080</td>
                    <td>US</td>
                    <td>United States</td>
                    <td>elite</td>
                    <td>yes</td>
                    <td>yes</td>
                </tr>
            </table>
        </html>
        """
        
        with patch('fp.sources.html_parser.requests.get', return_value=mock_response), \
             patch.object(parser, 'is_fresh', return_value=False):
            
            result = parser.parse()
        
        assert result.success is True
        assert len(result.proxies) == 1
        assert result.proxies[0].ip == "1.1.1.1"

    def test_parse_timeout(self, html_source):
        """Timeout при парсинге"""
        parser = HtmlSourceParser(html_source)
        
        with patch('fp.sources.html_parser.requests.get', side_effect=TimeoutError()), \
             patch.object(parser, 'is_fresh', return_value=False):
            
            with pytest.raises(SourceFetchError):
                parser.parse()

    def test_parse_html_error(self, html_source):
        """Ошибка парсинга HTML"""
        parser = HtmlSourceParser(html_source)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"<html>Invalid HTML"
        
        with patch('fp.sources.html_parser.requests.get', return_value=mock_response), \
             patch.object(parser, 'is_fresh', return_value=False):
            
            with pytest.raises(ParseError):
                parser.parse()

    def test_parse_no_table(self, html_source):
        """Таблица не найдена"""
        parser = HtmlSourceParser(html_source)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"<html><body>No table</body></html>"
        
        with patch('fp.sources.html_parser.requests.get', return_value=mock_response), \
             patch.object(parser, 'is_fresh', return_value=False):
            
            with pytest.raises(ParseError) as exc_info:
                parser.parse()
            
            assert "No proxy rows found" in str(exc_info.value)

    def test_parse_fallback_xpath(self, html_source):
        """Fallback XPath"""
        parser = HtmlSourceParser(html_source)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"""
        <html>
            <table id="list">
                <tr>
                    <td>1.1.1.1</td>
                    <td>8080</td>
                    <td>US</td>
                    <td>United States</td>
                    <td>elite</td>
                    <td>yes</td>
                    <td>yes</td>
                </tr>
            </table>
        </html>
        """
        
        # Первый XPath не находит, fallback находит
        with patch('fp.sources.html_parser.requests.get', return_value=mock_response), \
             patch.object(parser, 'is_fresh', return_value=False):
            
            result = parser.parse()
        
        assert result.success is True


class TestHtmlSourceParserParseRow:
    """Тесты парсинга строки таблицы"""

    def test_parse_row_success(self, html_source):
        """Успешный парсинг строки"""
        parser = HtmlSourceParser(html_source)
        
        from lxml import html as lh
        
        html_str = """
        <tr>
            <td>1.1.1.1</td>
            <td>8080</td>
            <td>US</td>
            <td>United States</td>
            <td>elite</td>
            <td>yes</td>
            <td>yes</td>
        </tr>
        """
        tr = lh.fromstring(html_str)
        
        proxy = parser._parse_row(tr)
        
        assert proxy is not None
        assert proxy.ip == "1.1.1.1"
        assert proxy.port == 8080
        assert proxy.country == "US"
        assert proxy.protocol == "https"  # https = yes

    def test_parse_row_invalid_ip(self, html_source):
        """Невалидный IP"""
        parser = HtmlSourceParser(html_source)
        
        from lxml import html as lh
        
        html_str = """
        <tr>
            <td>invalid</td>
            <td>8080</td>
            <td>US</td>
            <td>United States</td>
            <td>elite</td>
            <td>yes</td>
            <td>yes</td>
        </tr>
        """
        tr = lh.fromstring(html_str)
        
        proxy = parser._parse_row(tr)
        
        assert proxy is None

    def test_parse_row_few_columns(self, html_source):
        """Мало колонок"""
        parser = HtmlSourceParser(html_source)
        
        from lxml import html as lh
        
        html_str = """
        <tr>
            <td>1.1.1.1</td>
            <td>8080</td>
        </tr>
        """
        tr = lh.fromstring(html_str)
        
        proxy = parser._parse_row(tr)
        
        assert proxy is None


# ============================================================================
# TXT SOURCE PARSER TESTS
# ============================================================================

class TestTxtSourceParserInit:
    """Тесты инициализации TxtSourceParser"""

    def test_init_correct_type(self, txt_source):
        """Инициализация с правильным типом"""
        parser = TxtSourceParser(txt_source)
        assert parser.source == txt_source

    def test_init_api_text_type(self):
        """Инициализация с API_TEXT типом"""
        source = ProxySource(
            name="Test API Text",
            url="https://api.proxyscrape.com/",
            type=SourceType.API_TEXT,
            protocols=[SourceProtocol.HTTP],
            country=None,
            update_frequency=15,
            timeout=15,
            max_retries=3,
        )
        parser = TxtSourceParser(source)
        assert parser.source == source


class TestTxtSourceParserParse:
    """Тесты парсинга TXT"""

    def test_parse_cached(self, txt_source):
        """Парсинг из кэша"""
        parser = TxtSourceParser(txt_source)
        
        cached_result = ParseResult(
            proxies=[Proxy(ip="1.1.1.1", port=8080, protocol="http")],
            source_name="Test TXT",
            success=True,
        )
        parser._cache = cached_result
        
        with patch.object(parser, 'is_fresh', return_value=True), \
             patch.object(parser, 'get_cached', return_value=cached_result):
            
            result = parser.parse()
        
        assert result.success is True

    def test_parse_success(self, txt_source):
        """Успешный парсинг"""
        parser = TxtSourceParser(txt_source)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "1.1.1.1:8080\n2.2.2.2:3128\n3.3.3.3:80\n"
        
        with patch('fp.sources.txt_parser.requests.get', return_value=mock_response), \
             patch.object(parser, 'is_fresh', return_value=False):
            
            result = parser.parse()
        
        assert result.success is True
        assert len(result.proxies) == 3

    def test_parse_with_comments(self, txt_source):
        """Парсинг с комментариями"""
        parser = TxtSourceParser(txt_source)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "# Comment\n1.1.1.1:8080\n# Another comment\n2.2.2.2:3128\n"
        
        with patch('fp.sources.txt_parser.requests.get', return_value=mock_response), \
             patch.object(parser, 'is_fresh', return_value=False):
            
            result = parser.parse()
        
        assert result.success is True
        assert len(result.proxies) == 2  # Комментарии пропущены

    def test_parse_empty_lines(self, txt_source):
        """Парсинг с пустыми строками"""
        parser = TxtSourceParser(txt_source)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "1.1.1.1:8080\n\n2.2.2.2:3128\n\n"
        
        with patch('fp.sources.txt_parser.requests.get', return_value=mock_response), \
             patch.object(parser, 'is_fresh', return_value=False):
            
            result = parser.parse()
        
        assert result.success is True
        assert len(result.proxies) == 2

    def test_parse_timeout(self, txt_source):
        """Timeout при парсинге"""
        parser = TxtSourceParser(txt_source)
        
        with patch('fp.sources.txt_parser.requests.get', side_effect=TimeoutError()), \
             patch.object(parser, 'is_fresh', return_value=False):
            
            with pytest.raises(SourceFetchError):
                parser.parse()

    def test_parse_connection_error(self, txt_source):
        """Ошибка подключения"""
        parser = TxtSourceParser(txt_source)
        
        with patch('fp.sources.txt_parser.requests.get', side_effect=ConnectionError()), \
             patch.object(parser, 'is_fresh', return_value=False):
            
            with pytest.raises(SourceFetchError):
                parser.parse()

    def test_parse_empty_response(self, txt_source):
        """Пустой ответ"""
        parser = TxtSourceParser(txt_source)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = ""
        
        with patch('fp.sources.txt_parser.requests.get', return_value=mock_response), \
             patch.object(parser, 'is_fresh', return_value=False):
            
            with pytest.raises(ParseError):
                parser.parse()

    def test_parse_invalid_proxies(self, txt_source):
        """Невалидные прокси"""
        parser = TxtSourceParser(txt_source)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "invalid\nnoport\n999.999.999.999:8080\n"
        
        with patch('fp.sources.txt_parser.requests.get', return_value=mock_response), \
             patch.object(parser, 'is_fresh', return_value=False):
            
            with pytest.raises(ParseError):
                parser.parse()


class TestTxtSourceParserParseLine:
    """Тесты парсинга строки"""

    def test_parse_line_success(self):
        """Успешный парсинг строки"""
        result = TxtSourceParser.parse_line("1.1.1.1:8080")
        
        assert result is not None
        assert result == ("1.1.1.1", 8080)

    def test_parse_line_empty(self):
        """Пустая строка"""
        result = TxtSourceParser.parse_line("")
        assert result is None

    def test_parse_line_comment(self):
        """Строка-комментарий"""
        result = TxtSourceParser.parse_line("# comment")
        assert result is None

    def test_parse_line_no_colon(self):
        """Нет двоеточия"""
        result = TxtSourceParser.parse_line("1.1.1.1")
        assert result is None

    def test_parse_line_multiple_colons(self):
        """Много двоеточий"""
        result = TxtSourceParser.parse_line("1.1.1.1:8080:extra")
        assert result is None

    def test_parse_line_invalid_port(self):
        """Невалидный порт"""
        result = TxtSourceParser.parse_line("1.1.1.1:abc")
        assert result is None

    def test_parse_line_port_out_of_range(self):
        """Порт вне диапазона"""
        result = TxtSourceParser.parse_line("1.1.1.1:70000")
        assert result is None

    def test_parse_line_invalid_ip(self):
        """Невалидный IP"""
        result = TxtSourceParser.parse_line("999.999.999.999:8080")
        assert result is None

    def test_parse_line_ip_wrong_format(self):
        """IP неправильного формата"""
        result = TxtSourceParser.parse_line("1.1.1:8080")
        assert result is None


# ============================================================================
# BASE SOURCE PARSER TESTS
# ============================================================================

class TestBaseSourceParser:
    """Тесты базового парсера"""

    def test_validate_proxy_string_success(self, txt_source):
        """Валидация успешной строки"""
        parser = TxtSourceParser(txt_source)
        
        assert parser.validate_proxy_string("1.1.1.1:8080") is True
        assert parser.validate_proxy_string("255.255.255.255:65535") is True

    def test_validate_proxy_string_no_colon(self, txt_source):
        """Нет двоеточия"""
        parser = TxtSourceParser(txt_source)
        assert parser.validate_proxy_string("1.1.1.1") is False

    def test_validate_proxy_string_multiple_colons(self, txt_source):
        """Много двоеточий"""
        parser = TxtSourceParser(txt_source)
        assert parser.validate_proxy_string("1.1.1.1:8080:extra") is False

    def test_validate_proxy_string_invalid_ip(self, txt_source):
        """Невалидный IP"""
        parser = TxtSourceParser(txt_source)
        assert parser.validate_proxy_string("999.999.999.999:8080") is False

    def test_validate_proxy_string_invalid_port(self, txt_source):
        """Невалидный порт"""
        parser = TxtSourceParser(txt_source)
        assert parser.validate_proxy_string("1.1.1.1:abc") is False

    def test_validate_proxy_string_port_zero(self, txt_source):
        """Порт 0"""
        parser = TxtSourceParser(txt_source)
        assert parser.validate_proxy_string("1.1.1.1:0") is False

    def test_validate_proxy_string_port_too_high(self, txt_source):
        """Порт слишком высокий"""
        parser = TxtSourceParser(txt_source)
        assert parser.validate_proxy_string("1.1.1.1:70000") is False

    def test_parse_proxy_string_success(self, txt_source):
        """Успешный парсинг строки"""
        parser = TxtSourceParser(txt_source)
        
        proxy = parser.parse_proxy_string("1.1.1.1:8080")
        
        assert proxy is not None
        assert proxy.ip == "1.1.1.1"
        assert proxy.port == 8080
        assert proxy.protocol == "http"

    def test_parse_proxy_string_invalid(self, txt_source):
        """Невалидная строка"""
        parser = TxtSourceParser(txt_source)
        
        proxy = parser.parse_proxy_string("invalid")
        
        assert proxy is None

    def test_get_freshness_none(self, txt_source):
        """Freshness без кэша"""
        parser = TxtSourceParser(txt_source)
        
        freshness = parser.get_freshness()
        
        assert freshness is None

    def test_is_fresh_false_no_cache(self, txt_source):
        """Не свежий без кэша"""
        parser = TxtSourceParser(txt_source)
        
        assert parser.is_fresh() is False

    def test_get_cached_none(self, txt_source):
        """Пустой кэш"""
        parser = TxtSourceParser(txt_source)
        
        assert parser.get_cached() is None


# ============================================================================
# PROXY MODEL TESTS
# ============================================================================

class TestProxyModel:
    """Тесты модели Proxy"""

    def test_create_proxy_minimal(self):
        """Минимальная прокси"""
        proxy = Proxy(ip="1.1.1.1", port=8080, protocol="http")
        
        assert proxy.ip == "1.1.1.1"
        assert proxy.port == 8080
        assert proxy.protocol == "http"
        assert proxy.country is None
        assert proxy.anonymity is None
        assert proxy.source is None

    def test_create_proxy_full(self):
        """Полная прокси"""
        proxy = Proxy(
            ip="1.1.1.1",
            port=8080,
            protocol="https",
            country="US",
            anonymity="elite",
            google=True,
            https=True,
            source="Test Source",
        )
        
        assert proxy.country == "US"
        assert proxy.anonymity == "elite"
        assert proxy.google is True
        assert proxy.https is True
        assert proxy.source == "Test Source"

    def test_proxy_str(self):
        """Строковое представление"""
        proxy = Proxy(ip="1.1.1.1", port=8080, protocol="http")
        
        assert str(proxy) == "http://1.1.1.1:8080"

    def test_proxy_to_dict(self):
        """Конвертация в dict"""
        proxy = Proxy(
            ip="1.1.1.1",
            port=8080,
            protocol="http",
            country="US",
            anonymity="elite",
        )
        
        result = proxy.to_dict()
        
        assert result["ip"] == "1.1.1.1"
        assert result["port"] == 8080
        assert result["protocol"] == "http"
        assert result["country"] == "US"
        assert result["anonymity"] == "elite"


# ============================================================================
# PARSERESULT MODEL TESTS
# ============================================================================

class TestParseResultModel:
    """Тесты модели ParseResult"""

    def test_create_result_success(self):
        """Успешный результат"""
        result = ParseResult(
            proxies=[Proxy(ip="1.1.1.1", port=8080, protocol="http")],
            source_name="Test Source",
            success=True,
        )
        
        assert result.success is True
        assert result.count == 1
        assert result.error is None

    def test_create_result_failure(self):
        """Неудачный результат"""
        result = ParseResult(
            proxies=[],
            source_name="Test Source",
            success=False,
            error="No proxies found",
        )
        
        assert result.success is False
        assert result.count == 0
        assert result.error == "No proxies found"

    def test_result_to_dict(self):
        """Конвертация в dict"""
        result = ParseResult(
            proxies=[Proxy(ip="1.1.1.1", port=8080, protocol="http")],
            source_name="Test Source",
            success=True,
        )
        
        d = result.to_dict()
        
        assert d["success"] is True
        assert d["count"] == 1
        assert "proxies" in d
        assert "parsed_at" in d
