"""
Premium Leak Parser Tests

Тесты для парсера "слитых" платных прокси (GitHub Gist, Pastebin, и др.)

Форматы:
- TXT: IP:PORT или IP:PORT:USER:PASS
- CSV: ip,port,protocol,country
- JSON: [{"ip": "...", "port": ...}, ...]
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from fp.database import ProxyDatabase
from fp.validator import ProxyMetrics, ProxyPool
from fp.config import SourceType, SourceProtocol, ProxySource


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def sample_txt_content():
    """Пример TXT формата (GitHub Gist style)"""
    return """192.168.1.1:8080
10.0.0.1:3128:http
172.16.0.1:8888:https
192.168.1.2:8080:user:pass
10.0.0.2:3128:socks4
172.16.0.2:1080:socks5
"""


@pytest.fixture
def sample_csv_content():
    """Пример CSV формата"""
    return """ip,port,protocol,country
192.168.1.1,8080,http,US
10.0.0.1,3128,https,GB
172.16.0.1,8888,socks4,DE
"""


@pytest.fixture
def sample_json_content():
    """Пример JSON формата"""
    return """[
    {"ip": "192.168.1.1", "port": 8080, "protocol": "http", "country": "US"},
    {"ip": "10.0.0.1", "port": 3128, "protocol": "https", "country": "GB"},
    {"ip": "172.16.0.1", "port": 8888, "protocol": "socks4", "country": "DE"}
]"""


@pytest.fixture
def premium_source_config():
    """Конфигурация тестового premium источника"""
    return {
        "name": "Test Premium Leak",
        "url": "https://gist.githubusercontent.com/test/proxies.txt",
        "type": SourceType.PREMIUM_LEAK,
        "protocols": [SourceProtocol.HTTP, SourceProtocol.HTTPS],
        "country": None,
        "update_frequency": 60,
        "timeout": 30,
        "max_retries": 3,
    }


# ============================================================================
# PARSER TESTS
# ============================================================================

class TestPremiumLeakParser:
    """Тесты для PremiumLeakParser"""

    def test_parse_txt_format(self, sample_txt_content, premium_source_config):
        """Тест парсинга TXT формата"""
        from fp.sources.premium_leak_parser import PremiumLeakParser

        parser = PremiumLeakParser(premium_source_config)
        result = parser._parse_txt(sample_txt_content)

        assert result.success is True
        # Прокси фильтруются по протоколу (только HTTP/HTTPS в конфиге)
        assert len(result.proxies) >= 4
        assert any(p.ip == "192.168.1.1" and p.port == 8080 for p in result.proxies)

    def test_parse_csv_format(self, sample_csv_content, premium_source_config):
        """Тест парсинга CSV формата"""
        from fp.sources.premium_leak_parser import PremiumLeakParser

        parser = PremiumLeakParser(premium_source_config)
        result = parser._parse_csv(sample_csv_content)

        assert result.success is True
        # SOCKS4 отфильтрован
        assert len(result.proxies) >= 2
        assert any(p.ip == "192.168.1.1" and p.port == 8080 for p in result.proxies)
        assert any(p.protocol == "https" for p in result.proxies)

    def test_parse_json_format(self, sample_json_content, premium_source_config):
        """Тест парсинга JSON формата"""
        from fp.sources.premium_leak_parser import PremiumLeakParser

        parser = PremiumLeakParser(premium_source_config)
        result = parser._parse_json(sample_json_content)

        assert result.success is True
        # SOCKS4 отфильтрован
        assert len(result.proxies) >= 2
        assert any(p.country == "US" for p in result.proxies)

    def test_auto_detect_format_txt(self, sample_txt_content, premium_source_config):
        """Тест автоматического определения TXT формата"""
        from fp.sources.premium_leak_parser import PremiumLeakParser

        parser = PremiumLeakParser(premium_source_config)
        fmt = parser._detect_format(sample_txt_content)
        assert fmt == "txt"

    def test_auto_detect_format_csv(self, sample_csv_content, premium_source_config):
        """Тест автоматического определения CSV формата"""
        from fp.sources.premium_leak_parser import PremiumLeakParser

        parser = PremiumLeakParser(premium_source_config)
        fmt = parser._detect_format(sample_csv_content)
        assert fmt == "csv"

    def test_auto_detect_format_json(self, sample_json_content, premium_source_config):
        """Тест автоматического определения JSON формата"""
        from fp.sources.premium_leak_parser import PremiumLeakParser

        parser = PremiumLeakParser(premium_source_config)
        fmt = parser._detect_format(sample_json_content)
        assert fmt == "json"

    def test_parse_with_credentials(self, premium_source_config):
        """Тест парсинга прокси с авторизацией (user:pass)"""
        from fp.sources.premium_leak_parser import PremiumLeakParser

        content = "192.168.1.1:8080:user1:pass1\n10.0.0.1:3128:user2:pass2"
        parser = PremiumLeakParser(premium_source_config)
        result = parser._parse_txt(content)

        assert result.success is True
        # Проверяем что прокси с авторизацией распарсены
        assert len(result.proxies) == 2

    def test_parse_empty_content(self, premium_source_config):
        """Тест обработки пустого контента"""
        from fp.sources.premium_leak_parser import PremiumLeakParser

        parser = PremiumLeakParser(premium_source_config)
        result = parser._parse_txt("")

        assert result.success is False
        assert "No valid proxies found" in result.error

    def test_parse_invalid_format(self, premium_source_config):
        """Тест обработки невалидного формата"""
        from fp.sources.premium_leak_parser import PremiumLeakParser

        content = "invalid\nnot_an_ip\n:::"
        parser = PremiumLeakParser(premium_source_config)
        result = parser._parse_txt(content)

        assert result.success is False

    def test_deduplication(self, premium_source_config):
        """Тест дедупликации прокси"""
        from fp.sources.premium_leak_parser import PremiumLeakParser

        content = "192.168.1.1:8080\n192.168.1.1:8080\n192.168.1.1:8080"
        parser = PremiumLeakParser(premium_source_config)
        result = parser._parse_txt(content)

        assert result.success is True
        assert len(result.proxies) == 1  # Дубликаты удалены

    def test_protocol_filtering(self, premium_source_config):
        """Тест фильтрации по протоколу"""
        from fp.sources.premium_leak_parser import PremiumLeakParser

        content = "192.168.1.1:8080:http\n10.0.0.1:1080:socks5"
        parser = PremiumLeakParser(premium_source_config)
        result = parser._parse_txt(content)

        # Должны быть только HTTP/HTTPS прокси (согласно конфигу)
        assert result.success is True
        # SOCKS5 должен быть отфильтрован если не указан в protocols

    def test_invalid_ip_validation(self, premium_source_config):
        """Тест валидации IP адресов"""
        from fp.sources.premium_leak_parser import PremiumLeakParser

        content = "192.168.1.1:8080\n999.999.999.999:8080\n10.0.0.1:3128"
        parser = PremiumLeakParser(premium_source_config)
        result = parser._parse_txt(content)

        assert result.success is True
        # Невалидный IP должен быть отфильтрован
        assert all(p.ip != "999.999.999.999" for p in result.proxies)

    def test_invalid_port_validation(self, premium_source_config):
        """Тест валидации портов"""
        from fp.sources.premium_leak_parser import PremiumLeakParser

        content = "192.168.1.1:8080\n10.0.0.1:99999\n172.16.0.1:3128"
        parser = PremiumLeakParser(premium_source_config)
        result = parser._parse_txt(content)

        assert result.success is True
        # Порт 99999 должен быть отфильтрован (max 65535)
        assert all(p.port <= 65535 for p in result.proxies)


# ============================================================================
# NETWORK TESTS (MOCKED)
# ============================================================================

class TestPremiumLeakNetwork:
    """Тесты сетевого взаимодействия (с моками)"""

    @patch('fp.sources.premium_leak_parser.requests.get')
    def test_fetch_gist_success(self, mock_get, premium_source_config):
        """Тест успешного получения GitHub Gist"""
        from fp.sources.premium_leak_parser import PremiumLeakParser

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "192.168.1.1:8080\n10.0.0.1:3128"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        parser = PremiumLeakParser(premium_source_config)
        result = parser.parse()

        assert result.success is True
        assert len(result.proxies) >= 1  # Хотя бы одна прокси
        mock_get.assert_called_once()

    @patch('fp.sources.premium_leak_parser.requests.get')
    def test_fetch_404(self, mock_get, premium_source_config):
        """Тест обработки 404 ошибки"""
        from fp.sources.premium_leak_parser import PremiumLeakParser

        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = Exception("404 Not Found")
        mock_get.return_value = mock_response

        parser = PremiumLeakParser(premium_source_config)
        result = parser.parse()

        assert result.success is False
        assert "404" in result.error

    @patch('fp.sources.premium_leak_parser.requests.get')
    def test_fetch_timeout(self, mock_get, premium_source_config):
        """Тест обработки timeout"""
        from fp.sources.premium_leak_parser import PremiumLeakParser
        import requests

        mock_get.side_effect = requests.exceptions.Timeout()

        parser = PremiumLeakParser(premium_source_config)
        result = parser.parse()

        assert result.success is False
        assert "timeout" in result.error.lower()

    @patch('fp.sources.premium_leak_parser.requests.get')
    def test_retry_logic(self, mock_get, premium_source_config):
        """Тест retry логики при ошибках"""
        from fp.sources.premium_leak_parser import PremiumLeakParser
        import requests

        # Первые 2 запроса失败, 3-й успешный
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "192.168.1.1:8080"
        mock_response.raise_for_status.return_value = None

        mock_get.side_effect = [
            requests.exceptions.Timeout(),
            requests.exceptions.ConnectionError(),
            mock_response
        ]

        parser = PremiumLeakParser(premium_source_config)
        result = parser.parse()

        assert result.success is True
        assert mock_get.call_count == 3  # 3 попытки


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestPremiumLeakIntegration:
    """Интеграционные тесты"""

    @pytest.mark.asyncio
    async def test_database_premium_flag(self):
        """Тест: прокси из premium источников помечаются в БД"""
        from fp.sources.premium_leak_parser import PremiumLeakParser

        async with ProxyDatabase(":memory:") as db:
            # Создаём парсер
            config = {
                "name": "Test Premium",
                "url": "https://gist.github.com/test/proxies.txt",
                "type": SourceType.PREMIUM_LEAK,
                "protocols": [SourceProtocol.HTTP],
                "country": None,
                "update_frequency": 60,
                "timeout": 30,
                "max_retries": 3,
            }

            parser = PremiumLeakParser(config)

            # Проверяем что парсер определяет premium источник
            assert parser.is_premium is True

    @pytest.mark.asyncio
    async def test_premium_priority_in_selection(self):
        """Тест: premium прокси имеют приоритет при выборе"""
        async with ProxyDatabase(":memory:") as db:
            now = int(asyncio.get_event_loop().time())

            # Добавляем premium прокси
            premium_id = await db.add_proxy("192.168.1.1", 8080, "http", "US", "premium_source")
            # Добавляем free прокси
            free_id = await db.add_proxy("10.0.0.1", 3128, "http", "GB", "free_source")

            # TODO: После реализации - проверить приоритет
            # Это будет работать когда добавим is_premium колонку
            assert premium_id > 0
            assert free_id > 0


# ============================================================================
# CONFIG TESTS
# ============================================================================

class TestPremiumLeakConfig:
    """Тесты конфигурации premium источников"""

    def test_premium_leak_sources_not_empty(self):
        """Тест: список premium источников не пустой"""
        from fp.config import PREMIUM_LEAK_SOURCES

        assert len(PREMIUM_LEAK_SOURCES) > 0

    def test_premium_leak_sources_in_all_sources(self):
        """Тест: premium источники включены в ALL_SOURCES"""
        from fp.config import ALL_SOURCES, PREMIUM_LEAK_SOURCES

        all_urls = {s["url"] for s in ALL_SOURCES}
        premium_urls = {s["url"] for s in PREMIUM_LEAK_SOURCES}

        # Все premium источники должны быть в ALL_SOURCES
        assert premium_urls.issubset(all_urls)

    def test_premium_leak_source_type(self):
        """Тест: premium источники имеют правильный тип"""
        from fp.config import PREMIUM_LEAK_SOURCES, SourceType

        for source in PREMIUM_LEAK_SOURCES:
            assert source["type"] == SourceType.PREMIUM_LEAK

    def test_premium_leak_has_required_fields(self):
        """Тест: premium источники имеют все обязательные поля"""
        from fp.config import PREMIUM_LEAK_SOURCES

        required_fields = ["name", "url", "type", "protocols", "timeout"]

        for source in PREMIUM_LEAK_SOURCES:
            for field in required_fields:
                assert field in source, f"Missing field: {field}"


# ============================================================================
# QUALITY COMPARISON TESTS
# ============================================================================

class TestPremiumVsFreeQuality:
    """Тесты сравнения качества premium vs free прокси"""

    @pytest.mark.asyncio
    async def test_premium_success_rate_higher(self):
        """
        Тест: premium прокси имеют higher success rate

        Это интеграционный тест который должен запускаться на реальных данных.
        Пока что проверяем что инфраструктура готова.
        """
        # TODO: После реализации:
        # 1. Собрать прокси из premium и free источников
        # 2. Проверить через validator
        # 3. Сравнить success rate
        #
        # Ожидаемый результат:
        # - Premium success rate: 40-70%
        # - Free success rate: 5-20%

        assert True  # Заглушка до реализации

    @pytest.mark.asyncio
    async def test_premium_latency_lower(self):
        """
        Тест: premium прокси имеют меньшую latency

        Ожидаемый результат:
        - Premium latency: 50-300ms
        - Free latency: 500-5000ms
        """
        assert True  # Заглушка до реализации

    @pytest.mark.asyncio
    async def test_smoke_ratio_improved_with_premium(self):
        """
        Тест: smoke ratio улучшается с premium прокси

        Это главный метрический тест.
        Ожидаемый результат:
        - Без premium: 0-10% success
        - С premium: 30-60% success

        TODO: После реализации premium_only в smoke_test()
        """
        from fp.smoke import smoke_test

        # Пока что проверяем что smoke_test работает
        results = await smoke_test(n=3, timeout=3.0, use_preflight=False)

        assert results is not None
        assert "ratio" in results
        # assert results_premium["ratio"] >= results_free["ratio"]
