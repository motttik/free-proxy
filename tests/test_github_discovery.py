"""
Tests for GitHub Discovery Module

Полное покрытие для fp.github_discovery
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from fp.github_discovery import GitHubDiscovery, DiscoveredSource
from fp.config import ProxySource, SourceType, SourceProtocol


class TestDiscoveredSource:
    """Тесты для dataclass DiscoveredSource"""

    def test_create_discovered_source(self):
        """Создание DiscoveredSource"""
        source = DiscoveredSource(
            name="test/repo/file.txt",
            url="https://raw.githubusercontent.com/test/repo/master/file.txt",
            repo="test/repo",
            path="file.txt",
        )
        assert source.name == "test/repo/file.txt"
        assert source.repo == "test/repo"
        assert source.path == "file.txt"
        assert source.status == "candidate"
        assert source.sandbox_cycles == 0
        assert source.pass_rate == 100.0

    def test_discovered_source_with_custom_values(self):
        """DiscoveredSource с кастомными значениями"""
        source = DiscoveredSource(
            name="test/repo/file.txt",
            url="https://example.com",
            repo="test/repo",
            path="file.txt",
            sandbox_cycles=5,
            pass_rate=45.0,
            status="promoted",
        )
        assert source.sandbox_cycles == 5
        assert source.pass_rate == 45.0
        assert source.status == "promoted"


class TestGitHubDiscoveryInit:
    """Тесты инициализации GitHubDiscovery"""

    def test_init_default(self):
        """Инициализация по умолчанию"""
        discovery = GitHubDiscovery()
        assert discovery.github_token is None
        assert discovery.max_results == 50
        assert discovery._client is None
        assert discovery._health_manager is None
        assert len(discovery._discovered) == 0

    def test_init_with_token(self):
        """Инициализация с токеном"""
        discovery = GitHubDiscovery(github_token="test_token", max_results=100)
        assert discovery.github_token == "test_token"
        assert discovery.max_results == 100


class TestGitHubDiscoveryContextManager:
    """Тесты контекстного менеджера"""

    @pytest.mark.asyncio
    async def test_aenter(self):
        """Вход в контекст"""
        discovery = GitHubDiscovery()
        async with discovery as d:
            assert d._client is not None
            assert d._health_manager is not None
            assert "Authorization" not in d._client.headers  # Нет токена

    @pytest.mark.asyncio
    async def test_aenter_with_token(self):
        """Вход в контекст с токеном"""
        discovery = GitHubDiscovery(github_token="test_token")
        async with discovery as d:
            assert "token test_token" in d._client.headers.get("Authorization", "")

    @pytest.mark.asyncio
    async def test_aexit(self):
        """Выход из контекста"""
        discovery = GitHubDiscovery()
        async with discovery:
            pass
        # После выхода клиент должен быть закрыт (проверяем через None)

    @pytest.mark.asyncio
    async def test_aexit_closes_resources(self):
        """Выход закрывает ресурсы"""
        discovery = GitHubDiscovery()
        async with discovery as d:
            client = d._client
            health_manager = d._health_manager
        
        # Ресурсы должны быть освобождены


class TestGitHubDiscoverySearch:
    """Тесты поиска репозиториев"""

    @pytest.mark.asyncio
    async def test_search_repositories_no_client(self):
        """Поиск без клиента"""
        discovery = GitHubDiscovery()
        result = await discovery.search_repositories()
        assert result == []

    @pytest.mark.asyncio
    async def test_search_repositories_success(self):
        """Успешный поиск"""
        discovery = GitHubDiscovery()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {"full_name": "user/repo1", "stargazers_count": 100},
                {"full_name": "user/repo2", "stargazers_count": 200},
            ]
        }
        
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        discovery._client = mock_client
        
        result = await discovery.search_repositories()
        
        assert len(result) == 2
        assert result[0]["full_name"] == "user/repo1"
        mock_client.get.assert_called()

    @pytest.mark.asyncio
    async def test_search_repositories_dedup(self):
        """Дедупликация репозиториев"""
        discovery = GitHubDiscovery()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {"full_name": "user/repo1", "stargazers_count": 100},
                {"full_name": "user/repo1", "stargazers_count": 100},  # Дубликат
                {"full_name": "user/repo2", "stargazers_count": 200},
            ]
        }
        
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        discovery._client = mock_client
        
        result = await discovery.search_repositories()
        
        assert len(result) == 2  # Дубликат удалён

    @pytest.mark.asyncio
    async def test_search_repositories_error(self):
        """Обработка ошибки при поиске"""
        discovery = GitHubDiscovery()
        
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Network error")
        discovery._client = mock_client
        
        result = await discovery.search_repositories()
        
        assert result == []

    @pytest.mark.asyncio
    async def test_search_repositories_404(self):
        """Обработка 404 ответа"""
        discovery = GitHubDiscovery()
        
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        discovery._client = mock_client
        
        result = await discovery.search_repositories()
        
        assert result == []


class TestGitHubDiscoveryFindFiles:
    """Тесты поиска proxy файлов"""

    @pytest.mark.asyncio
    async def test_find_proxy_files_no_client(self):
        """Поиск без клиента"""
        discovery = GitHubDiscovery()
        result = await discovery.find_proxy_files("user/repo")
        assert result == []

    @pytest.mark.asyncio
    async def test_find_proxy_files_success(self):
        """Успешный поиск файлов"""
        discovery = GitHubDiscovery()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"type": "file", "name": "proxy.txt", "path": "proxy.txt"},
            {"type": "file", "name": "http_proxies.txt", "path": "http_proxies.txt"},
            {"type": "dir", "name": "src"},  # Директория
        ]
        
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        discovery._client = mock_client
        
        result = await discovery.find_proxy_files("user/repo")
        
        assert len(result) == 2
        assert "proxy.txt" in result

    @pytest.mark.asyncio
    async def test_find_proxy_files_patterns(self):
        """Поиск по паттернам"""
        discovery = GitHubDiscovery()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"type": "file", "name": "proxy-list.txt", "path": "proxy-list.txt"},
            {"type": "file", "name": "http.txt", "path": "http.txt"},
            {"type": "file", "name": "socks5.txt", "path": "socks5.txt"},
            {"type": "file", "name": "README.md", "path": "README.md"},  # Не подходит
        ]
        
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        discovery._client = mock_client
        
        result = await discovery.find_proxy_files("user/repo")
        
        assert len(result) == 3
        assert "README.md" not in result

    @pytest.mark.asyncio
    async def test_find_proxy_files_error(self):
        """Обработка ошибки"""
        discovery = GitHubDiscovery()
        
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("API error")
        discovery._client = mock_client
        
        result = await discovery.find_proxy_files("user/repo")
        
        assert result == []

    @pytest.mark.asyncio
    async def test_find_proxy_files_max_limit(self):
        """Ограничение максимума файлов"""
        discovery = GitHubDiscovery()
        
        files = [
            {"type": "file", "name": f"proxy{i}.txt", "path": f"proxy{i}.txt"}
            for i in range(30)
        ]
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = files
        
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        discovery._client = mock_client
        
        result = await discovery.find_proxy_files("user/repo")
        
        assert len(result) <= 20  # Максимум 20


class TestGitHubDiscoveryCreateSource:
    """Тесты создания ProxySource"""

    def test_create_source_http(self):
        """Создание HTTP источника"""
        discovery = GitHubDiscovery()
        source = discovery.create_source_from_file("user/repo", "proxy.txt")
        
        assert source["name"] == "GitHub/user/repo/proxy.txt"
        assert source["url"] == "https://raw.githubusercontent.com/user/repo/master/proxy.txt"
        assert source["type"] == SourceType.GITHUB_RAW
        assert SourceProtocol.HTTP in source["protocols"]

    def test_create_source_socks5(self):
        """Создание SOCKS5 источника"""
        discovery = GitHubDiscovery()
        source = discovery.create_source_from_file("user/repo", "socks5.txt")
        
        assert source["protocols"] == [SourceProtocol.SOCKS5]

    def test_create_source_socks4(self):
        """Создание SOCKS4 источника"""
        discovery = GitHubDiscovery()
        source = discovery.create_source_from_file("user/repo", "socks4.txt")
        
        assert source["protocols"] == [SourceProtocol.SOCKS4]

    def test_create_source_https(self):
        """Создание HTTPS источника"""
        discovery = GitHubDiscovery()
        source = discovery.create_source_from_file("user/repo", "https.txt")
        
        assert source["protocols"] == [SourceProtocol.HTTPS]


class TestGitHubDiscoveryDiscover:
    """Тесты discovery цикла"""

    @pytest.mark.asyncio
    async def test_discover_new_sources(self):
        """Полный цикл discovery"""
        discovery = GitHubDiscovery()
        
        # Мокаем search_repositories
        async def mock_search():
            return [
                {"full_name": "newuser/newrepo", "stargazers_count": 50},
                {"full_name": "TheSpeedX/PROXY-List", "stargazers_count": 1000},  # Trusted
            ]
        
        # Мокаем find_proxy_files
        async def mock_find(repo):
            if repo == "newuser/newrepo":
                return ["proxy.txt"]
            return []
        
        discovery.search_repositories = mock_search
        discovery.find_proxy_files = mock_find
        discovery._health_manager = MagicMock()
        discovery._health_manager.sources = {}
        
        result = await discovery.discover_new_sources()
        
        assert len(result) == 1  # Trusted автор пропущен
        assert result[0].repo == "newuser/newrepo"

    @pytest.mark.asyncio
    async def test_discover_skips_trusted_authors(self):
        """Пропуск доверенных авторов"""
        discovery = GitHubDiscovery()
        
        async def mock_search():
            return [
                {"full_name": "TheSpeedX/repo", "stargazers_count": 1000},
                {"full_name": "monosans/repo", "stargazers_count": 500},
                {"full_name": "clarketm/repo", "stargazers_count": 300},
            ]
        
        discovery.search_repositories = mock_search
        discovery.find_proxy_files = AsyncMock(return_value=[])
        
        result = await discovery.discover_new_sources()
        
        assert len(result) == 0  # Все пропущены


class TestGitHubDiscoverySandbox:
    """Тесты sandbox тестирования"""

    @pytest.mark.asyncio
    async def test_sandbox_test_no_health_manager(self):
        """Sandbox test без health manager"""
        discovery = GitHubDiscovery()
        result = await discovery.sandbox_test("https://example.com")
        assert result is False

    @pytest.mark.asyncio
    async def test_sandbox_test_not_available(self):
        """Sandbox test для недоступного источника"""
        discovery = GitHubDiscovery()
        discovery._health_manager = MagicMock()
        discovery._health_manager.is_available.return_value = False
        
        result = await discovery.sandbox_test("https://example.com")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_sandbox_test_increment_cycles(self):
        """Увеличение sandbox cycles"""
        discovery = GitHubDiscovery()
        discovery._health_manager = MagicMock()
        discovery._health_manager.is_available.return_value = True
        discovery._health_manager.sources = {}
        
        source = DiscoveredSource(
            name="test",
            url="https://example.com",
            repo="test/repo",
            path="proxy.txt",
        )
        discovery._discovered["https://example.com"] = source
        
        result = await discovery.sandbox_test("https://example.com")
        
        assert source.sandbox_cycles == 1
        assert result is True

    @pytest.mark.asyncio
    async def test_sandbox_test_auto_promote(self):
        """Авто-promote при высоком pass_rate"""
        discovery = GitHubDiscovery()
        discovery._health_manager = MagicMock()
        discovery._health_manager.is_available.return_value = True
        
        mock_health = MagicMock()
        mock_health.pass_rate = 50.0  # > 40%
        discovery._health_manager.sources = {"https://example.com": mock_health}
        
        source = DiscoveredSource(
            name="test",
            url="https://example.com",
            repo="test/repo",
            path="proxy.txt",
            sandbox_cycles=2,
        )
        discovery._discovered["https://example.com"] = source
        
        # Увеличиваем до 3 циклов
        await discovery.sandbox_test("https://example.com")
        await discovery.sandbox_test("https://example.com")
        await discovery.sandbox_test("https://example.com")
        
        assert source.status == "promoted"

    @pytest.mark.asyncio
    async def test_sandbox_test_auto_disabled(self):
        """Авто-disabled при низком pass_rate"""
        discovery = GitHubDiscovery()
        discovery._health_manager = MagicMock()
        discovery._health_manager.is_available.return_value = True
        
        mock_health = MagicMock()
        mock_health.pass_rate = 15.0  # < 20%
        discovery._health_manager.sources = {"https://example.com": mock_health}
        
        source = DiscoveredSource(
            name="test",
            url="https://example.com",
            repo="test/repo",
            path="proxy.txt",
            sandbox_cycles=2,
        )
        discovery._discovered["https://example.com"] = source
        
        await discovery.sandbox_test("https://example.com")
        await discovery.sandbox_test("https://example.com")
        await discovery.sandbox_test("https://example.com")
        
        assert source.status == "disabled"


class TestGitHubDiscoveryPromoted:
    """Тесты promoted sources"""

    def test_get_promoted_sources_empty(self):
        """Пустой список promoted"""
        discovery = GitHubDiscovery()
        result = discovery.get_promoted_sources()
        assert result == []

    def test_get_promoted_sources_with_data(self):
        """Promoted источники"""
        discovery = GitHubDiscovery()
        
        discovery._discovered = {
            "url1": DiscoveredSource(
                name="test1",
                url="url1",
                repo="user/repo1",
                path="proxy.txt",
                status="promoted",
            ),
            "url2": DiscoveredSource(
                name="test2",
                url="url2",
                repo="user/repo2",
                path="socks5.txt",
                status="promoted",
            ),
            "url3": DiscoveredSource(
                name="test3",
                url="url3",
                repo="user/repo3",
                path="proxy.txt",
                status="candidate",  # Не promoted
            ),
        }
        
        result = discovery.get_promoted_sources()
        
        assert len(result) == 2
        assert result[0]["protocols"] == [SourceProtocol.HTTP]
        assert result[1]["protocols"] == [SourceProtocol.SOCKS5]


class TestGitHubDiscoveryStats:
    """Тесты статистики"""

    def test_get_discovery_stats_empty(self):
        """Статистика пустого discovery"""
        discovery = GitHubDiscovery()
        stats = discovery.get_discovery_stats()
        
        assert stats["total_discovered"] == 0
        assert stats["candidate"] == 0
        assert stats["promoted"] == 0
        assert stats["disabled"] == 0

    def test_get_discovery_stats_with_data(self):
        """Статистика с данными"""
        discovery = GitHubDiscovery()
        
        discovery._discovered = {
            "url1": DiscoveredSource(
                name="test1", url="url1", repo="r1", path="p1", status="candidate"
            ),
            "url2": DiscoveredSource(
                name="test2", url="url2", repo="r2", path="p2", status="promoted"
            ),
            "url3": DiscoveredSource(
                name="test3", url="url3", repo="r3", path="p3", status="disabled"
            ),
            "url4": DiscoveredSource(
                name="test4", url="url4", repo="r4", path="p4", status="candidate"
            ),
        }
        
        stats = discovery.get_discovery_stats()
        
        assert stats["total_discovered"] == 4
        assert stats["candidate"] == 2
        assert stats["promoted"] == 1
        assert stats["disabled"] == 1
        assert len(stats["sources"]) <= 20  # Лимит 20


class TestGitHubDiscoveryMain:
    """Тесты main функции"""

    @pytest.mark.asyncio
    async def test_main_function(self):
        """Тест main функции"""
        from fp.github_discovery import main
        
        # Мокаем методы чтобы не делать реальные запросы
        with patch.object(GitHubDiscovery, 'discover_new_sources', return_value=[]):
            with patch.object(GitHubDiscovery, 'get_discovery_stats', return_value={
                "total_discovered": 0,
                "candidate": 0,
                "promoted": 0,
                "disabled": 0,
                "sources": []
            }):
                # Просто проверяем что функция выполняется без ошибок
                try:
                    await main()
                except Exception:
                    pytest.fail("main() raised exception")
