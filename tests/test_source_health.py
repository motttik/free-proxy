"""
Tests for Source Health Module

Полное покрытие для fp.source_health
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import time

from fp.source_health import SourceHealthManager, SourceHealth
from fp.config import ProxySource, SourceType, SourceProtocol, ALL_SOURCES


class TestSourceHealth:
    """Тесты для SourceHealth dataclass"""

    def test_create_source_health(self):
        """Создание SourceHealth"""
        health = SourceHealth(
            name="Test Source",
            url="https://example.com",
        )
        assert health.name == "Test Source"
        assert health.url == "https://example.com"
        assert health.fail_streak == 0
        assert health.success_streak == 0
        assert health.total_fetches == 0
        assert health.successful_fetches == 0
        assert health.pass_rate == 100.0
        assert health.disabled_until == 0.0

    def test_is_disabled_false(self):
        """Проверка is_disabled когда не отключен"""
        health = SourceHealth(name="Test", url="https://example.com")
        assert health.is_disabled() is False

    def test_is_disabled_true(self):
        """Проверка is_disabled когда отключен"""
        health = SourceHealth(
            name="Test",
            url="https://example.com",
            disabled_until=time.time() + 3600,  # Через час
        )
        assert health.is_disabled() is True

    def test_can_recheck(self):
        """Проверка can_recheck"""
        health = SourceHealth(name="Test", url="https://example.com")
        assert health.can_recheck() is True

    def test_can_recheck_disabled(self):
        """Проверка can_recheck когда отключен"""
        health = SourceHealth(
            name="Test",
            url="https://example.com",
            disabled_until=time.time() + 3600,
        )
        assert health.can_recheck() is False

    def test_record_success(self):
        """Запись успеха"""
        health = SourceHealth(name="Test", url="https://example.com")
        
        health.record_success(latency_ms=100)
        
        assert health.total_fetches == 1
        assert health.successful_fetches == 1
        assert health.success_streak == 1
        assert health.fail_streak == 0
        assert health.last_success > 0
        assert health.pass_rate == 100.0
        assert health.avg_latency > 0

    def test_record_success_multiple(self):
        """Несколько успехов"""
        health = SourceHealth(name="Test", url="https://example.com")
        
        health.record_success(latency_ms=100)
        health.record_success(latency_ms=200)
        health.record_success(latency_ms=50)
        
        assert health.total_fetches == 3
        assert health.successful_fetches == 3
        assert health.success_streak == 3
        assert health.pass_rate == 100.0

    def test_record_failure(self):
        """Запись неудачи"""
        health = SourceHealth(name="Test", url="https://example.com")
        
        health.record_failure("timeout")
        
        assert health.total_fetches == 1
        assert health.successful_fetches == 0
        assert health.fail_streak == 1
        assert health.success_streak == 0
        assert health.last_failure > 0
        assert health.pass_rate == 0.0
        assert "timeout" in health.error_counts

    def test_record_failure_multiple(self):
        """Несколько неудач"""
        health = SourceHealth(name="Test", url="https://example.com")
        
        health.record_failure("timeout")
        health.record_failure("connection_error")
        health.record_failure("timeout")
        
        assert health.total_fetches == 3
        assert health.fail_streak == 3
        assert health.error_counts["timeout"] == 2
        assert health.error_counts["connection_error"] == 1

    def test_get_top_errors(self):
        """Получение топ ошибок"""
        health = SourceHealth(name="Test", url="https://example.com")
        
        health.record_failure("timeout")
        health.record_failure("timeout")
        health.record_failure("timeout")
        health.record_failure("connection_error")
        health.record_failure("connection_error")
        health.record_failure("parse_error")
        
        top = health.get_top_errors(limit=2)
        
        assert len(top) == 2
        assert top[0] == ("timeout", 3)
        assert top[1] == ("connection_error", 2)

    def test_get_top_errors_empty(self):
        """Пустой список ошибок"""
        health = SourceHealth(name="Test", url="https://example.com")
        
        top = health.get_top_errors()
        
        assert top == []


class TestSourceHealthManagerInit:
    """Тесты инициализации SourceHealthManager"""

    def test_init_default(self):
        """Инициализация по умолчанию"""
        manager = SourceHealthManager()
        assert manager._db is None
        assert len(manager.sources) > 0  # Инициализировано из ALL_SOURCES

    def test_init_creates_all_sources(self):
        """Создание health для всех источников"""
        manager = SourceHealthManager()
        
        for source in ALL_SOURCES:
            assert source["url"] in manager.sources


class TestSourceHealthManagerContextManager:
    """Тесты контекстного менеджера"""

    @pytest.mark.asyncio
    async def test_aenter(self):
        """Вход в контекст"""
        manager = SourceHealthManager()
        
        with patch('fp.source_health.ProxyDatabase') as mock_db_cls:
            mock_db = AsyncMock()
            mock_db.__aenter__ = AsyncMock(return_value=mock_db)
            mock_db_cls.return_value = mock_db
            
            async with manager as m:
                assert m._db is not None

    @pytest.mark.asyncio
    async def test_aexit(self):
        """Выход из контекста"""
        manager = SourceHealthManager()
        
        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        
        with patch('fp.source_health.ProxyDatabase', return_value=mock_db):
            async with manager:
                pass


class TestSourceHealthManagerLoadSave:
    """Тесты загрузки/сохранения"""

    @pytest.mark.asyncio
    async def test_load_from_db_empty(self):
        """Загрузка из пустой БД"""
        manager = SourceHealthManager()
        manager._db = AsyncMock()
        
        mock_cursor = AsyncMock()
        mock_cursor.__aiter__.return_value = []
        manager._db._conn.execute.return_value = mock_cursor
        
        await manager._load_from_db()
        
        # Health должен остаться с дефолтными значениями

    @pytest.mark.asyncio
    async def test_load_from_db_with_data(self):
        """Загрузка с данными"""
        manager = SourceHealthManager()
        manager._db = AsyncMock()
        
        test_url = list(manager.sources.keys())[0]
        
        mock_cursor = AsyncMock()
        mock_cursor.__aiter__.return_value = [
            (test_url, 3, 50.0, time.time() + 3600, 10, 5, 150.0),
        ]
        manager._db._conn.execute.return_value = mock_cursor
        
        await manager._load_from_db()
        
        health = manager.sources[test_url]
        assert health.fail_streak == 3
        assert health.pass_rate == 50.0
        assert health.disabled_until > 0

    @pytest.mark.asyncio
    async def test_save_to_db(self):
        """Сохранение в БД"""
        manager = SourceHealthManager()
        manager._db = AsyncMock()
        manager._db._conn.execute = AsyncMock()
        manager._db._conn.commit = AsyncMock()
        
        await manager.save_to_db()
        
        manager._db._conn.execute.assert_called()
        manager._db._conn.commit.assert_called()


class TestSourceHealthManagerRecord:
    """Тесты записи успехов/неудач"""

    def test_record_success(self):
        """Запись успеха"""
        manager = SourceHealthManager()
        
        test_url = list(manager.sources.keys())[0]
        manager.record_success(test_url, latency_ms=100)
        
        health = manager.sources[test_url]
        assert health.successful_fetches == 1
        assert health.fail_streak == 0

    def test_record_success_unknown_url(self):
        """Запись успеха для неизвестного URL"""
        manager = SourceHealthManager()
        
        # Не должно вызывать ошибок
        manager.record_success("https://unknown.com", latency_ms=100)

    def test_record_success_auto_enable(self):
        """Авто-включение при успехе"""
        manager = SourceHealthManager()
        
        test_url = list(manager.sources.keys())[0]
        manager.sources[test_url].disabled_until = time.time() + 3600
        
        manager.record_success(test_url)
        
        # Если fail_streak стал 0, disabled_until должен сброситься
        health = manager.sources[test_url]
        if health.fail_streak == 0:
            assert health.disabled_until == 0

    def test_record_failure(self):
        """Запись неудачи"""
        manager = SourceHealthManager()
        
        test_url = list(manager.sources.keys())[0]
        manager.record_failure(test_url, "timeout")
        
        health = manager.sources[test_url]
        assert health.fail_streak == 1
        assert "timeout" in health.error_counts

    def test_record_failure_unknown_url(self):
        """Запись неудачи для неизвестного URL"""
        manager = SourceHealthManager()
        
        # Не должно вызывать ошибок
        manager.record_failure("https://unknown.com", "timeout")

    def test_record_failure_auto_disable_fail_streak(self):
        """Авто-отключение при fail streak"""
        manager = SourceHealthManager()
        
        test_url = list(manager.sources.keys())[0]
        
        # 5 неудач должны вызвать отключение
        for _ in range(5):
            manager.record_failure(test_url, "timeout")
        
        health = manager.sources[test_url]
        assert health.fail_streak == 5
        assert health.is_disabled() is True

    def test_record_failure_auto_disable_pass_rate(self):
        """Авто-отключение при низком pass_rate"""
        manager = SourceHealthManager()
        
        test_url = list(manager.sources.keys())[0]
        
        # Создаём низкий pass_rate
        for _ in range(10):
            manager.record_failure(test_url, "timeout")
        
        health = manager.sources[test_url]
        assert health.pass_rate == 0.0
        assert health.is_disabled() is True


class TestSourceHealthManagerAvailability:
    """Тесты доступности источников"""

    def test_is_available_true(self):
        """Источник доступен"""
        manager = SourceHealthManager()
        
        test_url = list(manager.sources.keys())[0]
        
        assert manager.is_available(test_url) is True

    def test_is_available_false_disabled(self):
        """Источник отключен"""
        manager = SourceHealthManager()
        
        test_url = list(manager.sources.keys())[0]
        manager.sources[test_url].disabled_until = time.time() + 3600
        
        assert manager.is_available(test_url) is False

    def test_is_available_unknown_url(self):
        """Неизвестный URL"""
        manager = SourceHealthManager()
        
        assert manager.is_available("https://unknown.com") is False

    def test_get_available_sources(self):
        """Получение доступных источников"""
        manager = SourceHealthManager()
        
        # Отключаем один источник
        test_url = list(manager.sources.keys())[0]
        manager.sources[test_url].disabled_until = time.time() + 3600
        
        available = manager.get_available_sources()
        
        # Все кроме отключенного
        assert len(available) == len(ALL_SOURCES) - 1
        assert test_url not in [s["url"] for s in available]

    def test_get_disabled_sources(self):
        """Получение отключенных источников"""
        manager = SourceHealthManager()
        
        test_url = list(manager.sources.keys())[0]
        manager.sources[test_url].disabled_until = time.time() + 3600
        manager.sources[test_url].fail_streak = 5
        manager.sources[test_url].pass_rate = 20.0
        
        disabled = manager.get_disabled_sources()
        
        assert len(disabled) == 1
        assert disabled[0]["name"] == manager.sources[test_url].name
        assert disabled[0]["fail_streak"] == 5
        assert disabled[0]["pass_rate"] == 20.0


class TestSourceHealthManagerStats:
    """Тесты статистики"""

    def test_get_stats(self):
        """Получение статистики"""
        manager = SourceHealthManager()
        
        # Отключаем несколько источников
        urls = list(manager.sources.keys())
        manager.sources[urls[0]].disabled_until = time.time() + 3600
        manager.sources[urls[1]].disabled_until = time.time() + 3600
        
        stats = manager.get_stats()
        
        assert stats["total_sources"] == len(ALL_SOURCES)
        assert stats["available"] == len(ALL_SOURCES) - 2
        assert stats["disabled"] == 2
        assert "avg_pass_rate" in stats
        assert "top_errors" in stats

    def test_get_stats_empty(self):
        """Статистика пустого менеджера"""
        manager = SourceHealthManager()
        manager.sources = {}
        
        stats = manager.get_stats()
        
        assert stats["total_sources"] == 0
        assert stats["available"] == 0
        assert stats["disabled"] == 0
        assert stats["avg_pass_rate"] == 0


class TestSourceHealthManagerRecheck:
    """Тесты перепроверки"""

    @pytest.mark.asyncio
    async def test_recheck_disabled(self):
        """Перепроверка отключенных"""
        manager = SourceHealthManager()
        
        test_url = list(manager.sources.keys())[0]
        past_time = time.time() - 3600  # Час назад (уже прошло)
        manager.sources[test_url].disabled_until = past_time
        
        report = await manager.recheck_disabled()
        
        assert report["rechecked"] >= 1
        assert report["enabled"] >= 1
        assert not manager.sources[test_url].is_disabled()

    @pytest.mark.asyncio
    async def test_recheck_disabled_not_yet(self):
        """Перепроверка когда ещё не время"""
        manager = SourceHealthManager()
        
        test_url = list(manager.sources.keys())[0]
        future_time = time.time() + 3600  # Через час
        manager.sources[test_url].disabled_until = future_time
        
        report = await manager.recheck_disabled()
        
        assert report["rechecked"] == 0
        assert report["enabled"] == 0


class TestSourceHealthManagerCoreCandidates:
    """Тесты core/candidate источников"""

    def test_get_core_sources(self):
        """Получение core источников"""
        manager = SourceHealthManager()
        
        test_url = list(manager.sources.keys())[0]
        manager.sources[test_url].pass_rate = 60.0  # >= 50%
        manager.sources[test_url].fail_streak = 1  # < 3
        
        core = manager.get_core_sources()
        
        # Должен включать источник с хорошими метриками
        assert any(s["url"] == test_url for s in core)

    def test_get_core_sources_low_pass_rate(self):
        """Core с низким pass_rate"""
        manager = SourceHealthManager()
        
        test_url = list(manager.sources.keys())[0]
        manager.sources[test_url].pass_rate = 30.0  # < 50%
        manager.sources[test_url].fail_streak = 1
        
        core = manager.get_core_sources()
        
        assert not any(s["url"] == test_url for s in core)

    def test_get_core_sources_high_fail_streak(self):
        """Core с высоким fail_streak"""
        manager = SourceHealthManager()
        
        test_url = list(manager.sources.keys())[0]
        manager.sources[test_url].pass_rate = 60.0
        manager.sources[test_url].fail_streak = 5  # >= 3
        
        core = manager.get_core_sources()
        
        assert not any(s["url"] == test_url for s in core)

    def test_get_candidate_sources(self):
        """Получение candidate источников"""
        manager = SourceHealthManager()
        
        test_url = list(manager.sources.keys())[0]
        manager.sources[test_url].pass_rate = 30.0  # < 50%
        
        candidates = manager.get_candidate_sources()
        
        # Должен включать источник с низким pass_rate
        assert any(s["url"] == test_url for s in candidates)

    def test_get_candidate_sources_few_fetches(self):
        """Candidate с малым количеством fetches"""
        manager = SourceHealthManager()
        
        test_url = list(manager.sources.keys())[0]
        manager.sources[test_url].pass_rate = 80.0  # >= 50%
        manager.sources[test_url].total_fetches = 5  # < 10
        
        candidates = manager.get_candidate_sources()
        
        # Должен включать источник с малым количеством fetches
        assert any(s["url"] == test_url for s in candidates)


class TestSourceHealthManagerConstants:
    """Тесты констант"""

    def test_constants(self):
        """Проверка констант"""
        manager = SourceHealthManager()
        
        assert manager.FAIL_STREAK_THRESHOLD == 5
        assert manager.PASS_RATE_THRESHOLD == 30.0
        assert manager.DISABLE_HOURS == 24
        assert manager.SANDBOX_CYCLES == 3


class TestSourceHealthManagerMain:
    """Тесты main функции"""

    @pytest.mark.asyncio
    async def test_main_function(self):
        """Тест main функции"""
        from fp.source_health import main
        
        with patch('fp.source_health.SourceHealthManager') as mock_manager_cls:
            mock_manager = AsyncMock()
            mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
            
            mock_manager.get_stats = MagicMock(return_value={
                "total_sources": 10,
                "available": 8,
                "disabled": 2,
                "avg_pass_rate": 75.0,
                "top_errors": [],
            })
            mock_manager.get_disabled_sources = MagicMock(return_value=[])
            
            mock_manager_cls.return_value = mock_manager
            
            try:
                await main()
            except Exception:
                pytest.fail("main() raised exception")
