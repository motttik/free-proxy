"""
Tests for FreeProxy

python -m pytest tests/ -v
"""

import pytest
from unittest.mock import MagicMock, patch

from fp.core import FreeProxy
from fp.core_async import AsyncFreeProxy
from fp.sources.base import Proxy, ParseResult
from fp.sources.txt_parser import TxtSourceParser
from fp.errors import FreeProxyException, NoWorkingProxyError, ProxyValidationError
from fp.config import ProxySource, SourceType, SourceProtocol


def make_test_source() -> ProxySource:
    """Создать тестовую конфигурацию источника"""
    return {
        "name": "Test",
        "url": "http://test.com",
        "type": SourceType.GITHUB_RAW,
        "protocols": [SourceProtocol.HTTP],
        "country": None,
        "update_frequency": 60,
        "timeout": 10,
        "max_retries": 3,
    }


class TestProxyModel:
    """Тесты модели Proxy"""
    
    def test_proxy_creation(self):
        proxy = Proxy(ip="1.2.3.4", port=8080, protocol="http")
        assert proxy.ip == "1.2.3.4"
        assert proxy.port == 8080
        assert proxy.protocol == "http"
    
    def test_proxy_str(self):
        proxy = Proxy(ip="1.2.3.4", port=8080, protocol="http")
        assert str(proxy) == "http://1.2.3.4:8080"
    
    def test_proxy_to_dict(self):
        proxy = Proxy(
            ip="1.2.3.4",
            port=8080,
            protocol="https",
            country="US",
            anonymity="elite",
        )
        d = proxy.to_dict()
        assert d["ip"] == "1.2.3.4"
        assert d["port"] == 8080
        assert d["protocol"] == "https"
        assert d["country"] == "US"
        assert d["anonymity"] == "elite"


class TestProxyValidation:
    """Тесты валидации прокси"""
    
    def test_validate_valid_proxy(self):
        source = make_test_source()
        parser = TxtSourceParser(source)
        assert parser.validate_proxy_string("1.2.3.4:8080") is True
        assert parser.validate_proxy_string("255.255.255.255:65535") is True
    
    def test_validate_invalid_ip(self):
        source = make_test_source()
        parser = TxtSourceParser(source)
        assert parser.validate_proxy_string("256.1.1.1:8080") is False
        assert parser.validate_proxy_string("1.2.3:8080") is False
        assert parser.validate_proxy_string("abc.def.ghi.jkl:8080") is False
    
    def test_validate_invalid_port(self):
        source = make_test_source()
        parser = TxtSourceParser(source)
        assert parser.validate_proxy_string("1.2.3.4:0") is False
        assert parser.validate_proxy_string("1.2.3.4:65536") is False
        assert parser.validate_proxy_string("1.2.3.4:abc") is False


class TestFreeProxyInit:
    """Тесты инициализации FreeProxy"""
    
    def test_default_init(self):
        fp = FreeProxy()
        assert fp.country_id is None
        assert fp.timeout == 0.5
        assert fp.random is False
        assert fp.anonym is False
        assert fp.elite is False
    
    def test_custom_init(self):
        fp = FreeProxy(
            country_id=["US", "GB"],
            timeout=1.0,
            rand=True,
            anonym=True,
            elite=True,
            https=True,
        )
        assert fp.country_id == ["US", "GB"]
        assert fp.timeout == 1.0
        assert fp.random is True
        assert fp.anonym is True
        assert fp.elite is True
        assert fp.https is True


class TestFreeProxyCriteria:
    """Тесты фильтрации прокси"""
    
    def test_matches_criteria_default(self):
        fp = FreeProxy()
        proxy = Proxy(
            ip="1.2.3.4",
            port=8080,
            protocol="http",
            country="US",
            anonymity="anonymous",
            google=True,
            https=False,
        )
        assert fp._matches_criteria(proxy) is True
    
    def test_matches_criteria_country(self):
        fp = FreeProxy(country_id=["US", "GB"])
        
        proxy_us = Proxy(ip="1.2.3.4", port=8080, protocol="http", country="US")
        proxy_de = Proxy(ip="5.6.7.8", port=8080, protocol="http", country="DE")
        
        assert fp._matches_criteria(proxy_us) is True
        assert fp._matches_criteria(proxy_de) is False
    
    def test_matches_criteria_anonym(self):
        fp = FreeProxy(anonym=True)
        
        proxy_anon = Proxy(ip="1.2.3.4", port=8080, protocol="http", anonymity="anonymous")
        proxy_elite = Proxy(ip="1.2.3.4", port=8080, protocol="http", anonymity="elite proxy")
        proxy_trans = Proxy(ip="1.2.3.4", port=8080, protocol="http", anonymity="transparent")
        
        assert fp._matches_criteria(proxy_anon) is True
        assert fp._matches_criteria(proxy_elite) is True
        assert fp._matches_criteria(proxy_trans) is False
    
    def test_matches_criteria_elite(self):
        fp = FreeProxy(elite=True)
        
        proxy_elite = Proxy(ip="1.2.3.4", port=8080, protocol="http", anonymity="elite proxy")
        proxy_anon = Proxy(ip="1.2.3.4", port=8080, protocol="http", anonymity="anonymous")
        
        assert fp._matches_criteria(proxy_elite) is True
        assert fp._matches_criteria(proxy_anon) is False


class TestAsyncFreeProxy:
    """Тесты AsyncFreeProxy"""
    
    def test_async_init(self):
        afp = AsyncFreeProxy()
        assert afp.country_id is None
        assert afp.timeout == 5.0
        assert afp.max_concurrent == 20
    
    @pytest.mark.asyncio
    async def test_async_get_raises_on_no_proxy(self):
        afp = AsyncFreeProxy()
        
        # Мокаем пустой список прокси
        async def empty_list(*args, **kwargs):
            return []
        
        afp.get_proxy_list = empty_list
        
        with pytest.raises(NoWorkingProxyError):
            await afp.get()


class TestExceptions:
    """Тесты исключений"""
    
    def test_no_working_proxy_error(self):
        error = NoWorkingProxyError({"country_id": ["US"], "timeout": 1.0})
        assert "country_id" in str(error)
    
    def test_source_fetch_error(self):
        from fp.errors import SourceFetchError
        
        error = SourceFetchError("TestSource", "http://test.com", "Connection refused")
        assert "TestSource" in str(error)
        assert "http://test.com" in str(error)
    
    def test_parse_error(self):
        from fp.errors import ParseError
        
        error = ParseError("TestSource", "Invalid HTML")
        assert "TestSource" in str(error)


class TestProxyStringParsing:
    """Тесты парсинга строк прокси"""
    
    def test_parse_simple_proxy(self):
        source = make_test_source()
        parser = TxtSourceParser(source)
        proxy = parser.parse_proxy_string("1.2.3.4:8080")
        
        assert proxy is not None
        assert proxy.ip == "1.2.3.4"
        assert proxy.port == 8080
    
    def test_parse_invalid_proxy(self):
        source = make_test_source()
        parser = TxtSourceParser(source)
        assert parser.parse_proxy_string("invalid") is None
        assert parser.parse_proxy_string("") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
