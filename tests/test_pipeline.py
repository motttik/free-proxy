"""
Tests for Proxy Pipeline Module (FIXED)

Полное покрытие для fp.pipeline
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from fp.pipeline import ProxyPipeline, NormalizedProxy, PipelineReport
from fp.config import ProxySource, SourceType, SourceProtocol


class TestNormalizedProxy:
    """Тесты для NormalizedProxy"""

    def test_create_proxy(self):
        """Создание прокси"""
        proxy = NormalizedProxy(
            ip="1.2.3.4",
            port=8080,
            protocol="http",
            country="US",
            source="test_source",
        )
        assert proxy.ip == "1.2.3.4"
        assert proxy.port == 8080
        assert proxy.protocol == "http"
        assert proxy.country == "US"
        assert proxy.source == "test_source"

    def test_proxy_key(self):
        """Уникальный ключ прокси"""
        proxy1 = NormalizedProxy(ip="1.1.1.1", port=8080, protocol="http")
        proxy2 = NormalizedProxy(ip="1.1.1.1", port=8080, protocol="http")
        proxy3 = NormalizedProxy(ip="1.1.1.1", port=8081, protocol="http")
        
        assert proxy1.key() == proxy2.key()
        assert proxy1.key() != proxy3.key()
        assert proxy1.key() == "http://1.1.1.1:8080"

    def test_to_proxy(self):
        """Конвертация в кортеж"""
        proxy = NormalizedProxy(ip="1.1.1.1", port=8080, protocol="http")
        result = proxy.to_proxy()
        assert result == ("1.1.1.1", 8080, "http")

    def test_default_values(self):
        """Значения по умолчанию"""
        proxy = NormalizedProxy(ip="1.1.1.1", port=8080, protocol="http")
        assert proxy.country is None
        assert proxy.anonymity is None
        assert proxy.source is None
        assert proxy.first_seen > 0
        assert proxy.last_seen > 0


class TestPipelineReport:
    """Тесты для PipelineReport"""

    def test_create_report_auto_timestamp(self):
        """Создание отчёта с авто-timestamp"""
        report = PipelineReport()
        assert report.timestamp != ""
        assert "T" in report.timestamp  # ISO формат

    def test_create_report_custom_timestamp(self):
        """Создание отчёта с кастомным timestamp"""
        report = PipelineReport(timestamp="2024-01-01T00:00:00")
        assert report.timestamp == "2024-01-01T00:00:00"

    def test_report_default_values(self):
        """Значения по умолчанию"""
        report = PipelineReport()
        assert report.collected == 0
        assert report.normalized == 0
        assert report.deduped == 0
        assert report.validated_fast == 0
        assert report.validated_targeted == 0
        assert report.hot_count == 0
        assert report.warm_count == 0
        assert report.quarantine_count == 0
        assert report.failed == 0
        assert report.avg_latency == 0.0
        assert report.avg_score == 0.0
        assert report.top_fail_reasons == {}
        assert report.source_stats == {}


class TestProxyPipelineInit:
    """Тесты инициализации ProxyPipeline"""

    def test_init_default(self):
        """Инициализация по умолчанию"""
        pipeline = ProxyPipeline()
        assert pipeline.db_path == "~/.free-proxy/proxies.db"
        assert pipeline.max_concurrent == 50
        assert pipeline.min_score_hot == 70
        assert pipeline.target_hot_proxies == 30
        assert pipeline._db is None
        assert pipeline._validator is None
        assert pipeline._health_manager is None

    def test_init_custom(self):
        """Кастомная инициализация"""
        pipeline = ProxyPipeline(
            db_path="/tmp/test.db",
            max_concurrent=100,
            min_score_hot=80,
            target_hot_proxies=50,
        )
        assert pipeline.db_path == "/tmp/test.db"
        assert pipeline.max_concurrent == 100
        assert pipeline.min_score_hot == 80
        assert pipeline.target_hot_proxies == 50


class TestProxyPipelineContextManager:
    """Тесты контекстного менеджера"""

    @pytest.mark.asyncio
    async def test_aenter(self):
        """Вход в контекст"""
        pipeline = ProxyPipeline()
        
        with patch('fp.pipeline.ProxyDatabase') as mock_db_cls, \
             patch('fp.pipeline.AsyncProxyValidator') as mock_validator_cls, \
             patch('fp.pipeline.SourceHealthManager') as mock_health_cls:
            
            mock_db = AsyncMock()
            mock_db.__aenter__ = AsyncMock(return_value=mock_db)
            mock_db_cls.return_value = mock_db
            
            mock_validator = AsyncMock()
            mock_validator.__aenter__ = AsyncMock(return_value=mock_validator)
            mock_validator_cls.return_value = mock_validator
            
            mock_health = AsyncMock()
            mock_health.__aenter__ = AsyncMock(return_value=mock_health)
            mock_health_cls.return_value = mock_health
            
            async with pipeline as p:
                assert p._db is not None
                assert p._validator is not None
                assert p._health_manager is not None

    @pytest.mark.asyncio
    async def test_aexit(self):
        """Выход из контекста"""
        pipeline = ProxyPipeline()
        
        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        
        mock_validator = AsyncMock()
        mock_validator.__aenter__ = AsyncMock(return_value=mock_validator)
        
        mock_health = AsyncMock()
        mock_health.__aenter__ = AsyncMock(return_value=mock_health)
        
        with patch('fp.pipeline.ProxyDatabase', return_value=mock_db), \
             patch('fp.pipeline.AsyncProxyValidator', return_value=mock_validator), \
             patch('fp.pipeline.SourceHealthManager', return_value=mock_health):
            
            async with pipeline:
                pass
            
            mock_validator.__aexit__.assert_called()
            mock_health.__aexit__.assert_called()
            mock_db.__aexit__.assert_called()


class TestProxyPipelineDedup:
    """Тесты дедупликации"""

    @pytest.mark.asyncio
    async def test_dedup_empty(self):
        """Дедупликация пустого списка"""
        pipeline = ProxyPipeline()
        result = await pipeline._dedup([])
        assert result == []

    @pytest.mark.asyncio
    async def test_dedup_no_duplicates(self):
        """Дедупликация без дубликатов"""
        pipeline = ProxyPipeline()
        
        proxies = [
            NormalizedProxy(ip="1.1.1.1", port=8080, protocol="http"),
            NormalizedProxy(ip="2.2.2.2", port=8080, protocol="http"),
            NormalizedProxy(ip="3.3.3.3", port=8080, protocol="http"),
        ]
        
        result = await pipeline._dedup(proxies)
        
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_dedup_with_duplicates(self):
        """Дедупликация с дубликатами"""
        pipeline = ProxyPipeline()
        
        proxies = [
            NormalizedProxy(ip="1.1.1.1", port=8080, protocol="http"),
            NormalizedProxy(ip="1.1.1.1", port=8080, protocol="http"),  # Дубликат
            NormalizedProxy(ip="2.2.2.2", port=8080, protocol="http"),
            NormalizedProxy(ip="1.1.1.1", port=8080, protocol="http"),  # Дубликат
        ]
        
        result = await pipeline._dedup(proxies)
        
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_dedup_different_protocols(self):
        """Разные протоколы - разные ключи"""
        pipeline = ProxyPipeline()
        
        proxies = [
            NormalizedProxy(ip="1.1.1.1", port=8080, protocol="http"),
            NormalizedProxy(ip="1.1.1.1", port=8080, protocol="https"),
        ]
        
        result = await pipeline._dedup(proxies)
        
        assert len(result) == 2  # Разные протоколы


class TestProxyPipelineValidateFast:
    """Тесты быстрой валидации"""

    @pytest.mark.asyncio
    async def test_validate_fast_no_validator(self):
        """Валидация без валидатора"""
        pipeline = ProxyPipeline()
        proxies = [NormalizedProxy(ip="1.1.1.1", port=8080, protocol="http")]
        
        result = await pipeline._validate_fast(proxies, PipelineReport())
        
        assert result == []

    @pytest.mark.asyncio
    async def test_validate_fast_github_raw(self):
        """Валидация GitHub Raw прокси"""
        pipeline = ProxyPipeline()
        pipeline._validator = AsyncMock()
        
        mock_result = MagicMock()
        mock_result.passed = True
        mock_result.country = None
        mock_result.source = None
        
        pipeline._validator.validate_multiple = AsyncMock(return_value=[mock_result])
        
        proxies = [
            NormalizedProxy(
                ip="1.1.1.1",
                port=8080,
                protocol="http",
                source="TheSpeedX HTTP",
            )
        ]
        
        report = PipelineReport()
        result = await pipeline._validate_fast(proxies, report)
        
        assert len(result) == 1
        # GitHub Raw валидируется без IP match
        pipeline._validator.validate_multiple.assert_called_with(
            [("1.1.1.1", 8080, "http")],
            skip_stage_b=True,
            skip_ip_match=True,
            show_progress=False,
        )

    @pytest.mark.asyncio
    async def test_validate_fast_other_sources(self):
        """Валидация других источников"""
        pipeline = ProxyPipeline()
        pipeline._validator = AsyncMock()
        
        mock_result = MagicMock()
        mock_result.passed = True
        mock_result.country = None
        mock_result.source = None
        
        pipeline._validator.validate_multiple = AsyncMock(return_value=[mock_result])
        
        proxies = [
            NormalizedProxy(
                ip="1.1.1.1",
                port=8080,
                protocol="http",
                source="Unknown Source",
            )
        ]
        
        report = PipelineReport()
        result = await pipeline._validate_fast(proxies, report)
        
        assert len(result) == 1
        # Другие источники валидируются с IP match
        pipeline._validator.validate_multiple.assert_called_with(
            [("1.1.1.1", 8080, "http")],
            skip_stage_b=True,
            skip_ip_match=False,
            show_progress=False,
        )

    @pytest.mark.asyncio
    async def test_validate_fast_fail_reasons(self):
        """Подсчёт причин ошибок"""
        pipeline = ProxyPipeline()
        pipeline._validator = AsyncMock()
        
        mock_result_passed = MagicMock()
        mock_result_passed.passed = True
        mock_result_passed.error = None
        
        mock_result_timeout = MagicMock()
        mock_result_timeout.passed = False
        mock_result_timeout.error = "Timeout error"
        
        mock_result_network = MagicMock()
        mock_result_network.passed = False
        mock_result_network.error = "Network error"
        
        pipeline._validator.validate_multiple = AsyncMock(
            return_value=[mock_result_passed, mock_result_timeout, mock_result_network]
        )
        
        proxies = [
            NormalizedProxy(ip="1.1.1.1", port=8080, protocol="http", source="Unknown"),
            NormalizedProxy(ip="2.2.2.2", port=8080, protocol="http", source="Unknown"),
            NormalizedProxy(ip="3.3.3.3", port=8080, protocol="http", source="Unknown"),
        ]
        
        report = PipelineReport()
        result = await pipeline._validate_fast(proxies, report)
        
        assert "timeout" in report.top_fail_reasons
        assert "network" in report.top_fail_reasons


class TestProxyPipelineValidateTargeted:
    """Тесты целевой валидации"""

    @pytest.mark.asyncio
    async def test_validate_targeted_no_validator(self):
        """Валидация без валидатора"""
        pipeline = ProxyPipeline()
        result = await pipeline._validate_targeted([], PipelineReport())
        assert result == []

    @pytest.mark.asyncio
    async def test_validate_targeted_empty_list(self):
        """Валидация пустого списка"""
        pipeline = ProxyPipeline()
        pipeline._validator = AsyncMock()
        
        result = await pipeline._validate_targeted([], PipelineReport())
        
        assert result == []

    @pytest.mark.asyncio
    async def test_validate_targeted_success(self):
        """Успешная валидация"""
        pipeline = ProxyPipeline()
        pipeline._validator = AsyncMock()
        
        mock_result = MagicMock()
        mock_result.passed = True
        mock_result.metrics = None
        
        pipeline._validator.validate_multiple = AsyncMock(return_value=[mock_result])
        
        passed_fast = [
            MagicMock(ip="1.1.1.1", port=8080, protocol="http", metrics=MagicMock()),
        ]
        
        report = PipelineReport()
        result = await pipeline._validate_targeted(passed_fast, report)
        
        assert len(result) == 1
        assert report.validated_targeted == 1

    @pytest.mark.asyncio
    async def test_validate_targeted_failures(self):
        """Валидация с ошибками"""
        pipeline = ProxyPipeline()
        pipeline._validator = AsyncMock()
        
        mock_result_fail = MagicMock()
        mock_result_fail.passed = False
        
        pipeline._validator.validate_multiple = AsyncMock(return_value=[mock_result_fail])
        
        passed_fast = [
            MagicMock(ip="1.1.1.1", port=8080, protocol="http", metrics=MagicMock()),
        ]
        
        report = PipelineReport()
        result = await pipeline._validate_targeted(passed_fast, report)
        
        assert "targeted_fail" in report.top_fail_reasons


class TestProxyPipelineScoreAndPool:
    """Тесты расчёта score и распределения по пулам"""

    @pytest.mark.asyncio
    async def test_score_and_pool_no_db(self):
        """Расчёт без БД"""
        pipeline = ProxyPipeline()
        results = [MagicMock()]
        
        # Не должно вызывать ошибок
        await pipeline._score_and_pool(results, PipelineReport())

    @pytest.mark.asyncio
    async def test_score_and_pool_new_proxy(self):
        """Расчёт для новой прокси"""
        pipeline = ProxyPipeline()
        pipeline._db = AsyncMock()
        
        # Мок БД
        pipeline._db.get_proxy_id = AsyncMock(return_value=None)
        pipeline._db.add_proxy = AsyncMock(return_value=1)
        pipeline._db._conn = AsyncMock()
        
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)
        pipeline._db._conn.execute = AsyncMock(return_value=mock_cursor)
        
        pipeline._db.update_metrics = AsyncMock()
        pipeline._db.update_pool = AsyncMock()
        pipeline._db.add_check_history = AsyncMock()
        
        mock_result = MagicMock()
        mock_result.ip = "1.1.1.1"
        mock_result.port = 8080
        mock_result.protocol = "http"
        mock_result.country = "US"
        mock_result.source = "TheSpeedX"
        mock_result.passed = True
        mock_result.latency_ms = 100
        mock_result.metrics.calculate_score.return_value = 85
        mock_result.metrics.get_pool.return_value = "hot"
        mock_result.metrics.latency_ms = 100
        mock_result.metrics.total_checks = 0
        mock_result.metrics.update = MagicMock()
        
        report = PipelineReport()
        await pipeline._score_and_pool([mock_result], report)
        
        assert report.hot_count == 1

    @pytest.mark.asyncio
    async def test_score_and_pool_existing_proxy(self):
        """Расчёт для существующей прокси"""
        pipeline = ProxyPipeline()
        pipeline._db = AsyncMock()
        
        pipeline._db.get_proxy_id = AsyncMock(return_value=1)
        pipeline._db._conn = AsyncMock()
        
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=(50, 0.9, 95, 0.01, 10, 9))
        pipeline._db._conn.execute = AsyncMock(return_value=mock_cursor)
        
        pipeline._db.update_metrics = AsyncMock()
        pipeline._db.update_pool = AsyncMock()
        pipeline._db.add_check_history = AsyncMock()
        
        mock_result = MagicMock()
        mock_result.ip = "1.1.1.1"
        mock_result.port = 8080
        mock_result.protocol = "http"
        mock_result.passed = True
        mock_result.latency_ms = 100
        mock_result.metrics.calculate_score.return_value = 90
        mock_result.metrics.get_pool.return_value = "hot"
        mock_result.metrics.latency_ms = 100
        mock_result.metrics.total_checks = 10
        mock_result.metrics.update = MagicMock()
        
        report = PipelineReport()
        await pipeline._score_and_pool([mock_result], report)
        
        assert report.hot_count == 1

    @pytest.mark.asyncio
    async def test_score_and_pool_warm_pool(self):
        """Расчёт для WARM пула"""
        pipeline = ProxyPipeline()
        pipeline._db = AsyncMock()
        
        pipeline._db.get_proxy_id = AsyncMock(return_value=1)
        pipeline._db._conn = AsyncMock()
        
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)
        pipeline._db._conn.execute = AsyncMock(return_value=mock_cursor)
        
        pipeline._db.update_metrics = AsyncMock()
        pipeline._db.update_pool = AsyncMock()
        pipeline._db.add_check_history = AsyncMock()
        
        mock_result = MagicMock()
        mock_result.ip = "1.1.1.1"
        mock_result.port = 8080
        mock_result.protocol = "http"
        mock_result.passed = False
        mock_result.latency_ms = 200
        mock_result.metrics.calculate_score.return_value = 60
        mock_result.metrics.get_pool.return_value = "warm"
        mock_result.metrics.latency_ms = 200
        mock_result.metrics.total_checks = 0
        mock_result.metrics.update = MagicMock()
        
        report = PipelineReport()
        await pipeline._score_and_pool([mock_result], report)
        
        assert report.warm_count == 1

    @pytest.mark.asyncio
    async def test_score_and_pool_quarantine_presumption(self):
        """Презумпция невиновности для новых прокси"""
        pipeline = ProxyPipeline()
        pipeline._db = AsyncMock()
        
        pipeline._db.get_proxy_id = AsyncMock(return_value=1)
        pipeline._db._conn = AsyncMock()
        
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)
        pipeline._db._conn.execute = AsyncMock(return_value=mock_cursor)
        
        pipeline._db.update_metrics = AsyncMock()
        pipeline._db.update_pool = AsyncMock()
        pipeline._db.add_check_history = AsyncMock()
        
        mock_result = MagicMock()
        mock_result.ip = "1.1.1.1"
        mock_result.port = 8080
        mock_result.protocol = "http"
        mock_result.passed = False
        mock_result.latency_ms = 200
        mock_result.metrics.calculate_score.return_value = 40
        mock_result.metrics.get_pool.return_value = "quarantine"
        mock_result.metrics.latency_ms = 200
        mock_result.metrics.total_checks = 1
        mock_result.metrics.update = MagicMock()
        
        report = PipelineReport()
        await pipeline._score_and_pool([mock_result], report)
        
        # Новая прокси не должна идти в карантин после первой неудачи
        assert report.quarantine_count == 0
        assert report.warm_count == 1

    @pytest.mark.asyncio
    async def test_score_and_pool_high_score_override(self):
        """Высокий score переопределяет пул"""
        pipeline = ProxyPipeline()
        pipeline._db = AsyncMock()
        
        pipeline._db.get_proxy_id = AsyncMock(return_value=1)
        pipeline._db._conn = AsyncMock()
        
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)
        pipeline._db._conn.execute = AsyncMock(return_value=mock_cursor)
        
        pipeline._db.update_metrics = AsyncMock()
        pipeline._db.update_pool = AsyncMock()
        pipeline._db.add_check_history = AsyncMock()
        
        mock_result = MagicMock()
        mock_result.ip = "1.1.1.1"
        mock_result.port = 8080
        mock_result.protocol = "http"
        mock_result.passed = False
        mock_result.latency_ms = 200
        mock_result.metrics.calculate_score.return_value = 85  # >= 80
        mock_result.metrics.get_pool.return_value = "warm"
        mock_result.metrics.latency_ms = 200
        mock_result.metrics.total_checks = 5
        mock_result.metrics.update = MagicMock()
        
        report = PipelineReport()
        await pipeline._score_and_pool([mock_result], report)
        
        # Высокий score должен переопределить пул до HOT
        assert report.hot_count == 1


class TestProxyPipelineRunCycle:
    """Тесты полного цикла pipeline"""

    @pytest.mark.asyncio
    async def test_run_cycle_empty(self):
        """Пустой цикл"""
        pipeline = ProxyPipeline()
        
        pipeline._collect = AsyncMock(return_value=[])
        pipeline._dedup = AsyncMock(return_value=[])
        
        report = await pipeline.run_cycle()
        
        assert report.collected == 0
        assert report.deduped == 0

    @pytest.mark.asyncio
    async def test_run_cycle_with_data(self):
        """Цикл с данными"""
        pipeline = ProxyPipeline()
        
        proxies = [NormalizedProxy(ip="1.1.1.1", port=8080, protocol="http")]
        
        mock_result = MagicMock()
        mock_result.passed = True
        mock_result.latency_ms = 100
        mock_result.metrics.calculate_score.return_value = 85
        mock_result.metrics.get_pool.return_value = "hot"
        mock_result.metrics.latency_ms = 100
        mock_result.metrics.total_checks = 0
        mock_result.metrics.update = MagicMock()
        
        pipeline._collect = AsyncMock(return_value=proxies)
        pipeline._dedup = AsyncMock(return_value=proxies)
        pipeline._validate_fast = AsyncMock(return_value=[mock_result])
        pipeline._validate_targeted = AsyncMock(return_value=[mock_result])
        pipeline._score_and_pool = AsyncMock()
        
        report = await pipeline.run_cycle()
        
        assert report.collected == 1
        assert report.deduped == 1

    @pytest.mark.asyncio
    async def test_run_cycle_skip_targeted(self):
        """Цикл с пропуском targeted"""
        pipeline = ProxyPipeline()
        
        proxies = [NormalizedProxy(ip="1.1.1.1", port=8080, protocol="http")]
        
        mock_result = MagicMock()
        mock_result.passed = True
        
        pipeline._collect = AsyncMock(return_value=proxies)
        pipeline._dedup = AsyncMock(return_value=proxies)
        pipeline._validate_fast = AsyncMock(return_value=[mock_result])
        pipeline._validate_targeted = AsyncMock(return_value=[])
        pipeline._score_and_pool = AsyncMock()
        
        report = await pipeline.run_cycle(skip_targeted=True)
        
        pipeline._validate_targeted.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_cycle_batch_processing(self):
        """Обработка батчами"""
        pipeline = ProxyPipeline()
        pipeline.batch_size = 100
        
        proxies = [
            NormalizedProxy(ip=f"1.1.1.{i}", port=8080, protocol="http")
            for i in range(250)
        ]
        
        mock_result = MagicMock()
        mock_result.passed = True
        mock_result.metrics.calculate_score.return_value = 85
        mock_result.metrics.get_pool.return_value = "hot"
        mock_result.metrics.latency_ms = 100
        mock_result.metrics.total_checks = 0
        mock_result.metrics.update = MagicMock()
        
        pipeline._collect = AsyncMock(return_value=proxies)
        pipeline._dedup = AsyncMock(return_value=proxies)
        pipeline._validate_fast = AsyncMock(return_value=[mock_result] * len(proxies))
        pipeline._validate_targeted = AsyncMock(return_value=[mock_result] * len(proxies))
        pipeline._score_and_pool = AsyncMock()
        
        report = await pipeline.run_cycle(batch_size=100)
        
        assert report.collected == 250
        # Должно быть 3 батча (100, 100, 50)
        assert pipeline._score_and_pool.call_count == 3


class TestProxyPipelineCollect:
    """Тесты сбора прокси"""

    @pytest.mark.asyncio
    async def test_collect_no_health_manager(self):
        """Сбор без health manager"""
        pipeline = ProxyPipeline()
        pipeline._health_manager = MagicMock()
        pipeline._health_manager.get_available_sources.return_value = []  # Нет источников
        report = PipelineReport()

        result = await pipeline._collect(report)

        assert result == []

    @pytest.mark.asyncio
    async def test_collect_with_health_manager(self):
        """Сбор с health manager"""
        pipeline = ProxyPipeline()
        pipeline._health_manager = MagicMock()

        mock_source = {
            "name": "TheSpeedX HTTP",
            "url": "https://example.com",
            "type": SourceType.GITHUB_RAW,
        }
        pipeline._health_manager.get_available_sources.return_value = [mock_source]

        mock_parser = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.proxies = [
            MagicMock(ip="1.1.1.1", port=8080, protocol="http", country="US"),
        ]
        mock_parser.parse.return_value = mock_result

        with patch('fp.pipeline.get_parser', return_value=mock_parser):
            result = await pipeline._collect(report)

            assert len(result) == 1
            assert result[0].ip == "1.1.1.1"

    @pytest.mark.asyncio
    async def test_collect_parse_error(self):
        """Ошибка парсинга"""
        pipeline = ProxyPipeline()
        pipeline._health_manager = MagicMock()

        mock_source = {
            "name": "Test Source",
            "url": "https://example.com",
            "type": SourceType.GITHUB_RAW,
        }
        pipeline._health_manager.get_available_sources.return_value = [mock_source]

        mock_parser = MagicMock()
        mock_result = MagicMock()
        mock_result.success = False
        mock_parser.parse.return_value = mock_result

        with patch('fp.pipeline.get_parser', return_value=mock_parser):
            result = await pipeline._collect(PipelineReport())

            assert result == []


class TestProxyPipelineGenerateReport:
    """Тесты генерации отчёта"""

    @pytest.mark.asyncio
    async def test_generate_report_no_db(self):
        """Генерация без БД"""
        pipeline = ProxyPipeline()
        report = PipelineReport()
        
        # Не должно вызывать ошибок
        await pipeline._generate_report(report)

    @pytest.mark.asyncio
    async def test_generate_report_with_db(self):
        """Генерация с БД"""
        pipeline = ProxyPipeline()
        pipeline._db = AsyncMock()
        pipeline._health_manager = AsyncMock()
        pipeline._health_manager.save_to_db = AsyncMock()
        
        report = PipelineReport(
            collected=100,
            deduped=80,
            validated_fast=60,
            hot_count=30,
            warm_count=20,
            quarantine_count=10,
            avg_score=75.5,
            avg_latency=150.0,
        )
        
        with patch('fp.pipeline.Path') as mock_path:
            mock_path.return_value.expanduser.return_value = MagicMock()
            mock_path.return_value.expanduser().mkdir = MagicMock()
            
            with patch('builtins.open'):
                with patch('json.dump'):
                    await pipeline._generate_report(report)


class TestProxyPipelineMain:
    """Тесты main функции"""

    @pytest.mark.asyncio
    async def test_main_function(self):
        """Тест main функции"""
        from fp.pipeline import main
        
        with patch('fp.pipeline.ProxyPipeline') as mock_pipeline_cls:
            mock_pipeline = AsyncMock()
            mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
            
            mock_report = MagicMock()
            mock_report.collected = 0
            mock_report.deduped = 0
            mock_report.validated_fast = 0
            mock_report.validated_targeted = 0
            mock_report.hot_count = 0
            mock_report.warm_count = 0
            mock_report.quarantine_count = 0
            mock_report.failed = 0
            mock_report.avg_score = 0.0
            mock_report.avg_latency = 0.0
            mock_report.top_fail_reasons = {}
            
            mock_pipeline.run_cycle = AsyncMock(return_value=mock_report)
            mock_pipeline_cls.return_value = mock_pipeline
            
            try:
                await main()
            except Exception:
                pytest.fail("main() raised exception")
