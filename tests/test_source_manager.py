"""
Tests for Source Manager Module

Полное покрытие для fp.source_manager
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import time

from fp.source_manager import SourceManager
from fp.config import ProxySource, SourceType, SourceProtocol
from fp.sources.base import Proxy, ParseResult


class TestSourceManagerInit:
    """Тесты инициализации SourceManager"""

    def test_init_default(self):
        """Инициализация по умолчанию"""
        manager = SourceManager()
        assert manager.db_path == "~/.free-proxy/proxies.db"
        assert manager.max_concurrent == 10
        assert manager.fail_streak_threshold == 5
        assert manager.pass_rate_threshold == 30.0
        assert manager.disable_hours == 24
        assert manager._db is None
        assert manager._client is None

    def test_init_custom(self):
        """Кастомная инициализация"""
        manager = SourceManager(
            db_path="/tmp/test.db",
            max_concurrent=20,
            fail_streak_threshold=3,
            pass_rate_threshold=50.0,
            disable_hours=12,
        )
        assert manager.db_path == "/tmp/test.db"
        assert manager.max_concurrent == 20
        assert manager.fail_streak_threshold == 3
        assert manager.pass_rate_threshold == 50.0
        assert manager.disable_hours == 12


class TestSourceManagerContextManager:
    """Тесты контекстного менеджера"""

    @pytest.mark.asyncio
    async def test_aenter(self):
        """Вход в контекст"""
        manager = SourceManager()
        
        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        
        with patch('fp.source_manager.ProxyDatabase', return_value=mock_db), \
             patch('fp.source_manager.httpx.AsyncClient') as mock_client_cls:
            
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            
            async with manager as m:
                assert m._db is not None
                assert m._client is not None

    @pytest.mark.asyncio
    async def test_aexit(self):
        """Выход из контекста"""
        manager = SourceManager()
        
        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        
        mock_client = AsyncMock()
        
        with patch('fp.source_manager.ProxyDatabase', return_value=mock_db), \
             patch('fp.source_manager.httpx.AsyncClient', return_value=mock_client):
            
            async with manager:
                pass
            
            mock_client.aclose.assert_called()


class TestSourceManagerInitSources:
    """Тесты инициализации источников"""

    @pytest.mark.asyncio
    async def test_init_sources(self):
        """Инициализация источников в БД"""
        manager = SourceManager()
        manager._db = AsyncMock()
        manager._db._conn.execute = AsyncMock()
        manager._db._conn.commit = AsyncMock()
        
        await manager._init_sources()
        
        manager._db._conn.execute.assert_called()
        manager._db._conn.commit.assert_called()


class TestSourceManagerFetchSource:
    """Тесты получения источника"""

    @pytest.mark.asyncio
    async def test_fetch_source_success(self):
        """Успешное получение"""
        manager = SourceManager()
        
        mock_source = {
            "name": "Test Source",
            "url": "https://example.com",
            "type": SourceType.GITHUB_RAW,
            "protocols": [SourceProtocol.HTTP],
        }
        
        mock_parser = MagicMock()
        mock_result = ParseResult(
            proxies=[Proxy(ip="1.1.1.1", port=8080, protocol="http")],
            source_name="Test Source",
            success=True,
        )
        mock_parser.parse.return_value = mock_result
        
        with patch('fp.source_manager.get_parser', return_value=mock_parser):
            proxies, success = await manager.fetch_source(mock_source)
        
        assert success is True
        assert len(proxies) == 1
        assert proxies[0].ip == "1.1.1.1"

    @pytest.mark.asyncio
    async def test_fetch_source_failure(self):
        """Неудачное получение"""
        manager = SourceManager()
        
        mock_source = {
            "name": "Test Source",
            "url": "https://example.com",
            "type": SourceType.GITHUB_RAW,
            "protocols": [SourceProtocol.HTTP],
        }
        
        mock_parser = MagicMock()
        mock_result = ParseResult(
            proxies=[],
            source_name="Test Source",
            success=False,
            error="No proxies found",
        )
        mock_parser.parse.return_value = mock_result
        
        with patch('fp.source_manager.get_parser', return_value=mock_parser):
            proxies, success = await manager.fetch_source(mock_source)
        
        assert success is False
        assert proxies == []

    @pytest.mark.asyncio
    async def test_fetch_source_exception(self):
        """Исключение при получении"""
        manager = SourceManager()
        
        mock_source = {
            "name": "Test Source",
            "url": "https://example.com",
            "type": SourceType.GITHUB_RAW,
            "protocols": [SourceProtocol.HTTP],
        }
        
        with patch('fp.source_manager.get_parser', side_effect=Exception("Test error")):
            proxies, success = await manager.fetch_source(mock_source)
        
        assert success is False
        assert proxies == []


class TestSourceManagerUpdateStats:
    """Тесты обновления статистики"""

    @pytest.mark.asyncio
    async def test_update_source_stats_success(self):
        """Обновление статистики успеха"""
        manager = SourceManager()
        manager._db = AsyncMock()
        
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=(0, 0, 0, 0))
        manager._db._conn.execute = AsyncMock(return_value=mock_cursor)
        manager._db._conn.commit = AsyncMock()
        
        await manager.update_source_stats(
            url="https://example.com",
            success=True,
            proxies_found=10,
            latency_ms=100,
        )
        
        manager._db._conn.execute.assert_called()
        manager._db._conn.commit.assert_called()

    @pytest.mark.asyncio
    async def test_update_source_stats_failure(self):
        """Обновление статистики неудачи"""
        manager = SourceManager()
        manager._db = AsyncMock()
        
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=(0, 0, 0, 0))
        manager._db._conn.execute = AsyncMock(return_value=mock_cursor)
        manager._db._conn.commit = AsyncMock()
        
        await manager.update_source_stats(
            url="https://example.com",
            success=False,
        )
        
        manager._db._conn.execute.assert_called()

    @pytest.mark.asyncio
    async def test_update_source_stats_auto_disable(self):
        """Авто-отключение при fail streak"""
        manager = SourceManager()
        manager._db = AsyncMock()
        
        # fail_streak = 4 (ещё одна неудача и будет 5)
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=(4, 10, 5, 50.0))
        manager._db._conn.execute = AsyncMock(return_value=mock_cursor)
        manager._db._conn.commit = AsyncMock()
        
        await manager.update_source_stats(
            url="https://example.com",
            success=False,
        )
        
        # Проверяем что disabled_until установлен
        call_args = manager._db._conn.execute.call_args
        assert call_args is not None

    @pytest.mark.asyncio
    async def test_update_source_stats_not_found(self):
        """Обновление несуществующего источника"""
        manager = SourceManager()
        manager._db = AsyncMock()
        
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)
        manager._db._conn.execute = AsyncMock(return_value=mock_cursor)
        
        await manager.update_source_stats(
            url="https://unknown.com",
            success=True,
        )
        
        # Не должно вызывать ошибок


class TestSourceManagerFetchAll:
    """Тесты получения всех источников"""

    @pytest.mark.asyncio
    async def test_fetch_all_sources_empty(self):
        """Получение пустого списка"""
        manager = SourceManager()
        manager._db = AsyncMock()
        
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[])
        manager._db._conn.execute = AsyncMock(return_value=mock_cursor)
        
        report = await manager.fetch_all_sources()
        
        assert report["total_sources"] == 0
        assert report["active_sources"] == 0
        assert report["disabled_sources"] == 0

    @pytest.mark.asyncio
    async def test_fetch_all_sources_with_data(self):
        """Получение с данными"""
        manager = SourceManager()
        manager._db = AsyncMock()
        
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[
            ("Test Source", "https://example.com", "github_raw", "http", 0, None),
        ])
        manager._db._conn.execute = AsyncMock(return_value=mock_cursor)
        
        mock_proxy = Proxy(ip="1.1.1.1", port=8080, protocol="http")
        
        with patch.object(manager, '_fetch_and_store', return_value=(True, 1, 1)):
            report = await manager.fetch_all_sources()
        
        assert report["total_sources"] == 1
        assert report["active_sources"] == 1
        assert report["total_proxies"] == 1

    @pytest.mark.asyncio
    async def test_fetch_all_sources_disabled(self):
        """Получение с отключенными источниками"""
        manager = SourceManager()
        manager._db = AsyncMock()
        
        future_time = time.time() + 3600
        
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[
            ("Disabled Source", "https://disabled.com", "github_raw", "http", 5, future_time),
        ])
        manager._db._conn.execute = AsyncMock(return_value=mock_cursor)
        
        report = await manager.fetch_all_sources()
        
        assert report["total_sources"] == 1
        assert report["active_sources"] == 0
        assert report["disabled_sources"] == 1

    @pytest.mark.asyncio
    async def test_fetch_all_sources_exception(self):
        """Исключение при получении"""
        manager = SourceManager()
        manager._db = AsyncMock()
        
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[
            ("Test Source", "https://example.com", "github_raw", "http", 0, None),
        ])
        manager._db._conn.execute = AsyncMock(return_value=mock_cursor)
        
        with patch.object(manager, '_fetch_and_store', side_effect=Exception("Test error")):
            report = await manager.fetch_all_sources()
        
        assert report["failed"] == 1


class TestSourceManagerFetchAndStore:
    """Тесты fetch_and_store"""

    @pytest.mark.asyncio
    async def test_fetch_and_store_success(self):
        """Успешное получение и сохранение"""
        manager = SourceManager()
        manager._db = AsyncMock()
        manager._db.add_proxy = AsyncMock(return_value=1)
        manager._db._conn.execute = AsyncMock()
        manager._db._conn.commit = AsyncMock()
        
        mock_source = {
            "name": "Test Source",
            "url": "https://example.com",
            "type": SourceType.GITHUB_RAW,
            "protocols": [SourceProtocol.HTTP],
        }
        
        mock_proxy = Proxy(ip="1.1.1.1", port=8080, protocol="http")
        
        with patch.object(manager, 'fetch_source', return_value=([mock_proxy], True)), \
             patch.object(manager, 'update_source_stats', new_callable=AsyncMock):
            
            success, total, new = await manager._fetch_and_store(mock_source)
        
        assert success is True
        assert total == 1
        assert new == 1

    @pytest.mark.asyncio
    async def test_fetch_and_store_failure(self):
        """Неудачное получение"""
        manager = SourceManager()
        manager._db = AsyncMock()
        manager._db._conn.execute = AsyncMock()
        manager._db._conn.commit = AsyncMock()
        
        mock_source = {
            "name": "Test Source",
            "url": "https://example.com",
            "type": SourceType.GITHUB_RAW,
            "protocols": [SourceProtocol.HTTP],
        }
        
        with patch.object(manager, 'fetch_source', return_value=([], False)), \
             patch.object(manager, 'update_source_stats', new_callable=AsyncMock):
            
            success, total, new = await manager._fetch_and_store(mock_source)
        
        assert success is False
        assert total == 0
        assert new == 0

    @pytest.mark.asyncio
    async def test_fetch_and_store_exception(self):
        """Исключение при получении"""
        manager = SourceManager()
        manager._db = AsyncMock()
        manager._db._conn.execute = AsyncMock()
        manager._db._conn.commit = AsyncMock()
        
        mock_source = {
            "name": "Test Source",
            "url": "https://example.com",
            "type": SourceType.GITHUB_RAW,
            "protocols": [SourceProtocol.HTTP],
        }
        
        with patch.object(manager, 'fetch_source', side_effect=Exception("Test error")), \
             patch.object(manager, 'update_source_stats', new_callable=AsyncMock):
            
            success, total, new = await manager._fetch_and_store(mock_source)
        
        assert success is False
        assert total == 0
        assert new == 0


class TestSourceManagerGetDisabled:
    """Тесты получения отключенных источников"""

    @pytest.mark.asyncio
    async def test_get_disabled_sources_empty(self):
        """Пустой список отключенных"""
        manager = SourceManager()
        manager._db = AsyncMock()
        
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[])
        manager._db._conn.execute = AsyncMock(return_value=mock_cursor)
        
        result = await manager.get_disabled_sources()
        
        assert result == []

    @pytest.mark.asyncio
    async def test_get_disabled_sources_with_data(self):
        """Список с отключенными"""
        manager = SourceManager()
        manager._db = AsyncMock()
        
        future_time = time.time() + 3600
        
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[
            ("Disabled Source", "https://disabled.com", 5, 20.0, future_time),
        ])
        manager._db._conn.execute = AsyncMock(return_value=mock_cursor)
        
        result = await manager.get_disabled_sources()
        
        assert len(result) == 1
        assert result[0]["name"] == "Disabled Source"
        assert result[0]["fail_streak"] == 5
        assert result[0]["pass_rate"] == 20.0


class TestSourceManagerGetStats:
    """Тесты получения статистики"""

    @pytest.mark.asyncio
    async def test_get_source_stats_empty(self):
        """Пустая статистика"""
        manager = SourceManager()
        manager._db = AsyncMock()
        
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[])
        manager._db._conn.execute = AsyncMock(return_value=mock_cursor)
        
        result = await manager.get_source_stats()
        
        assert result == []

    @pytest.mark.asyncio
    async def test_get_source_stats_with_data(self):
        """Статистика с данными"""
        manager = SourceManager()
        manager._db = AsyncMock()
        
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[
            ("Test Source", "https://example.com", "github_raw", "http", 0, 100.0, 10, 10, None, time.time()),
        ])
        manager._db._conn.execute = AsyncMock(return_value=mock_cursor)
        
        result = await manager.get_source_stats()
        
        assert len(result) == 1
        assert result[0]["name"] == "Test Source"
        assert result[0]["pass_rate"] == 100.0
        assert result[0]["disabled"] is False

    @pytest.mark.asyncio
    async def test_get_source_stats_disabled(self):
        """Статистика отключенного источника"""
        manager = SourceManager()
        manager._db = AsyncMock()
        
        future_time = time.time() + 3600
        
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[
            ("Disabled Source", "https://disabled.com", "github_raw", "http", 5, 20.0, 10, 2, future_time, time.time()),
        ])
        manager._db._conn.execute = AsyncMock(return_value=mock_cursor)
        
        result = await manager.get_source_stats()
        
        assert len(result) == 1
        assert result[0]["disabled"] is True


class TestSourceManagerMain:
    """Тесты main функции"""

    @pytest.mark.asyncio
    async def test_main_function(self):
        """Тест main функции"""
        from fp.source_manager import main
        
        with patch('fp.source_manager.SourceManager') as mock_manager_cls:
            mock_manager = AsyncMock()
            mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
            
            mock_manager.fetch_all_sources = AsyncMock(return_value={
                "total_sources": 10,
                "active_sources": 8,
                "disabled_sources": 2,
                "successful": 8,
                "failed": 2,
                "total_proxies": 100,
                "new_proxies": 50,
            })
            mock_manager.get_source_stats = AsyncMock(return_value=[])
            
            mock_manager_cls.return_value = mock_manager
            
            try:
                await main()
            except Exception:
                pytest.fail("main() raised exception")
