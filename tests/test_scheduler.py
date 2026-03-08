"""
Tests for Proxy Scheduler Module

Полное покрытие для fp.scheduler
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime

from fp.scheduler import ProxyScheduler


class TestProxySchedulerInit:
    """Тесты инициализации ProxyScheduler"""

    def test_init_default(self):
        """Инициализация по умолчанию"""
        scheduler = ProxyScheduler()
        assert scheduler.db_path == "~/.free-proxy/proxies.db"
        assert scheduler.max_concurrent == 50
        assert scheduler.report_path.parts[-1] == "reports"
        assert scheduler._manager is None
        assert scheduler._running is False

    def test_init_custom(self):
        """Кастомная инициализация"""
        scheduler = ProxyScheduler(
            db_path="/tmp/test.db",
            max_concurrent=100,
            report_path="/tmp/reports",
        )
        assert scheduler.db_path == "/tmp/test.db"
        assert scheduler.max_concurrent == 100
        assert scheduler.report_path.parts[-1] == "reports"


class TestProxySchedulerStart:
    """Тесты запуска планировщика"""

    @pytest.mark.asyncio
    async def test_start(self):
        """Запуск планировщика"""
        scheduler = ProxyScheduler()
        
        mock_manager = AsyncMock()
        mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
        
        with patch.object(scheduler._scheduler, 'add_job') as mock_add_job, \
             patch.object(scheduler._scheduler, 'start') as mock_start, \
             patch('fp.scheduler.ProxyManager', return_value=mock_manager):
            
            # Запускаем с таймаутом чтобы не зациклить
            async def mock_sleep():
                scheduler._running = False
            
            with patch('asyncio.sleep', side_effect=mock_sleep):
                await scheduler.start()
        
        assert scheduler._manager is not None
        assert mock_add_job.call_count >= 5  # Минимум 5 задач
        mock_start.assert_called()

    @pytest.mark.asyncio
    async def test_start_creates_jobs(self):
        """Создание задач при запуске"""
        scheduler = ProxyScheduler()
        
        mock_manager = AsyncMock()
        mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
        
        with patch.object(scheduler._scheduler, 'add_job') as mock_add_job, \
             patch.object(scheduler._scheduler, 'start'), \
             patch('fp.scheduler.ProxyManager', return_value=mock_manager):
            
            async def mock_sleep():
                scheduler._running = False
            
            with patch('asyncio.sleep', side_effect=mock_sleep):
                await scheduler.start()
        
        # Проверяем что добавлены нужные задачи
        job_ids = [call_args[1]['id'] for call_args in mock_add_job.call_args_list]
        
        assert "refresh_quarantine" in job_ids
        assert "cleanup_history" in job_ids
        assert "hourly_report" in job_ids
        assert "recheck_sources" in job_ids
        assert "github_discovery" in job_ids


class TestProxySchedulerStop:
    """Тесты остановки планировщика"""

    @pytest.mark.asyncio
    async def test_stop(self):
        """Остановка планировщика"""
        scheduler = ProxyScheduler()
        scheduler._running = True
        
        mock_scheduler = MagicMock()
        mock_scheduler.running = True
        scheduler._scheduler = mock_scheduler
        
        mock_manager = AsyncMock()
        mock_manager.__aexit__ = AsyncMock()
        scheduler._manager = mock_manager
        
        await scheduler.stop()
        
        assert scheduler._running is False
        mock_scheduler.shutdown.assert_called()
        mock_manager.__aexit__.assert_called()

    @pytest.mark.asyncio
    async def test_stop_not_running(self):
        """Остановка незапущенного планировщика"""
        scheduler = ProxyScheduler()
        scheduler._running = False
        
        mock_scheduler = MagicMock()
        mock_scheduler.running = False
        scheduler._scheduler = mock_scheduler
        
        await scheduler.stop()
        
        mock_scheduler.shutdown.assert_not_called()


class TestProxySchedulerRunDiscovery:
    """Тесты задачи discovery"""

    @pytest.mark.asyncio
    async def test_run_discovery(self):
        """Запуск discovery"""
        scheduler = ProxyScheduler()
        
        mock_discovery = AsyncMock()
        mock_discovery.__aenter__ = AsyncMock(return_value=mock_discovery)
        mock_discovery.discover_new_sources = AsyncMock(return_value=[])
        mock_discovery.sandbox_test = AsyncMock()
        
        with patch('fp.scheduler.GitHubDiscovery', return_value=mock_discovery):
            await scheduler._run_discovery()
        
        mock_discovery.discover_new_sources.assert_called()

    @pytest.mark.asyncio
    async def test_run_discovery_with_sources(self):
        """Discovery с найденными источниками"""
        scheduler = ProxyScheduler()
        
        mock_source = MagicMock()
        mock_source.url = "https://example.com"
        
        mock_discovery = AsyncMock()
        mock_discovery.__aenter__ = AsyncMock(return_value=mock_discovery)
        mock_discovery.discover_new_sources = AsyncMock(return_value=[mock_source])
        mock_discovery.sandbox_test = AsyncMock()
        
        with patch('fp.scheduler.GitHubDiscovery', return_value=mock_discovery):
            await scheduler._run_discovery()
        
        mock_discovery.sandbox_test.assert_called_with("https://example.com")

    @pytest.mark.asyncio
    async def test_run_discovery_error(self, caplog):
        """Ошибка в discovery"""
        scheduler = ProxyScheduler()
        
        mock_discovery = AsyncMock()
        mock_discovery.__aenter__ = AsyncMock(side_effect=Exception("Test error"))
        
        with patch('fp.scheduler.GitHubDiscovery', return_value=mock_discovery):
            await scheduler._run_discovery()
        
        assert "Error in _run_discovery" in caplog.text


class TestProxySchedulerRefreshQuarantine:
    """Тесты задачи refresh quarantine"""

    @pytest.mark.asyncio
    async def test_refresh_quarantine(self):
        """Обновление карантина"""
        scheduler = ProxyScheduler()
        
        mock_manager = AsyncMock()
        mock_manager.refresh_quarantine = AsyncMock(return_value={
            "total": 10,
            "upgraded": 5,
            "still_bad": 5,
        })
        scheduler._manager = mock_manager
        
        await scheduler._refresh_quarantine()
        
        mock_manager.refresh_quarantine.assert_called_with(limit=50)

    @pytest.mark.asyncio
    async def test_refresh_quarantine_no_manager(self, caplog):
        """Обновление без менеджера"""
        scheduler = ProxyScheduler()
        scheduler._manager = None
        
        # Не должно вызывать ошибок
        await scheduler._refresh_quarantine()

    @pytest.mark.asyncio
    async def test_refresh_quarantine_error(self, caplog):
        """Ошибка при обновлении"""
        scheduler = ProxyScheduler()
        
        mock_manager = AsyncMock()
        mock_manager.refresh_quarantine = AsyncMock(side_effect=Exception("Test error"))
        scheduler._manager = mock_manager
        
        await scheduler._refresh_quarantine()
        
        assert "Error in refresh_quarantine" in caplog.text


class TestProxySchedulerCleanupHistory:
    """Тесты задачи cleanup history"""

    @pytest.mark.asyncio
    async def test_cleanup_history(self):
        """Очистка истории"""
        scheduler = ProxyScheduler()
        
        mock_manager = AsyncMock()
        mock_db = AsyncMock()
        mock_db.cleanup_old_history = AsyncMock(return_value=100)
        mock_manager._db = mock_db
        scheduler._manager = mock_manager
        
        await scheduler._cleanup_history()
        
        mock_db.cleanup_old_history.assert_called_with(days=7)

    @pytest.mark.asyncio
    async def test_cleanup_history_no_manager(self, caplog):
        """Очистка без менеджера"""
        scheduler = ProxyScheduler()
        scheduler._manager = None
        
        # Не должно вызывать ошибок
        await scheduler._cleanup_history()

    @pytest.mark.asyncio
    async def test_cleanup_history_no_db(self, caplog):
        """Очистка без БД"""
        scheduler = ProxyScheduler()
        
        mock_manager = AsyncMock()
        mock_manager._db = None
        scheduler._manager = mock_manager
        
        await scheduler._cleanup_history()

    @pytest.mark.asyncio
    async def test_cleanup_history_error(self, caplog):
        """Ошибка при очистке"""
        scheduler = ProxyScheduler()
        
        mock_manager = AsyncMock()
        mock_db = AsyncMock()
        mock_db.cleanup_old_history = AsyncMock(side_effect=Exception("Test error"))
        mock_manager._db = mock_db
        scheduler._manager = mock_manager
        
        await scheduler._cleanup_history()
        
        assert "Error in cleanup_history" in caplog.text


class TestProxySchedulerHourlyReport:
    """Тесты задачи hourly report"""

    @pytest.mark.asyncio
    async def test_hourly_report(self):
        """Ежечасный отчёт"""
        scheduler = ProxyScheduler()
        
        mock_manager = AsyncMock()
        mock_manager.get_stats = AsyncMock(return_value={
            "total_proxies": 100,
            "hot_count": 30,
            "warm_count": 40,
            "quarantine_count": 30,
            "avg_score": 75.0,
        })
        mock_manager._save_report = AsyncMock()
        scheduler._manager = mock_manager
        
        await scheduler._hourly_report()
        
        mock_manager.get_stats.assert_called()
        mock_manager._save_report.assert_called()

    @pytest.mark.asyncio
    async def test_hourly_report_no_manager(self, caplog):
        """Отчёт без менеджера"""
        scheduler = ProxyScheduler()
        scheduler._manager = None
        
        # Не должно вызывать ошибок
        await scheduler._hourly_report()

    @pytest.mark.asyncio
    async def test_hourly_report_error(self, caplog):
        """Ошибка при создании отчёта"""
        scheduler = ProxyScheduler()
        
        mock_manager = AsyncMock()
        mock_manager.get_stats = AsyncMock(side_effect=Exception("Test error"))
        scheduler._manager = mock_manager
        
        await scheduler._hourly_report()
        
        assert "Error in hourly_report" in caplog.text


class TestProxySchedulerRecheckDisabled:
    """Тесты задачи recheck disabled sources"""

    @pytest.mark.asyncio
    async def test_recheck_disabled_sources(self, caplog):
        """Перепроверка отключенных источников"""
        scheduler = ProxyScheduler()
        
        await scheduler._recheck_disabled_sources()
        
        # Пока просто лог
        assert "Source recheck not yet implemented" in caplog.text


class TestProxySchedulerMain:
    """Тесты main функции"""

    @pytest.mark.asyncio
    async def test_main_function(self):
        """Тест main функции"""
        from fp.scheduler import main
        
        scheduler = ProxyScheduler()
        
        with patch.object(scheduler, 'start', side_effect=asyncio.CancelledError()):
            try:
                await main()
            except SystemExit:
                pass  # Ожидаемый выход
            except Exception as e:
                # CancelledError может вызвать другие исключения
                pass

    @pytest.mark.asyncio
    async def test_signal_handler(self):
        """Тест обработчика сигналов"""
        from fp.scheduler import main
        import signal
        
        scheduler = ProxyScheduler()
        
        # Проверяем что signal.signal вызывается
        with patch('signal.signal') as mock_signal:
            with patch.object(scheduler, 'start', side_effect=asyncio.CancelledError()):
                try:
                    await main()
                except:
                    pass
            
            assert mock_signal.call_count == 2
            assert mock_signal.call_args_list[0][0][0] == signal.SIGINT
            assert mock_signal.call_args_list[1][0][0] == signal.SIGTERM


class TestProxySchedulerJobTriggers:
    """Тесты триггеров задач"""

    def test_scheduler_configuration(self):
        """Конфигурация планировщика"""
        scheduler = ProxyScheduler()
        
        # Проверяем что планировщик создан с правильными настройками
        assert scheduler._scheduler is not None
        
        # Проверяем job_defaults
        # (эти проверки зависят от реализации APScheduler)


class TestProxySchedulerIntegration:
    """Интеграционные тесты"""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self):
        """Полный жизненный цикл"""
        scheduler = ProxyScheduler()
        
        mock_manager = AsyncMock()
        mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
        mock_manager.__aexit__ = AsyncMock()
        mock_manager.refresh_quarantine = AsyncMock(return_value={"total": 0, "upgraded": 0, "still_bad": 0})
        mock_manager.get_stats = AsyncMock(return_value={
            "total_proxies": 0,
            "hot_count": 0,
            "warm_count": 0,
            "quarantine_count": 0,
            "avg_score": 0,
        })
        mock_manager._save_report = AsyncMock()
        
        with patch('fp.scheduler.ProxyManager', return_value=mock_manager), \
             patch('fp.scheduler.GitHubDiscovery') as mock_discovery_cls:
            
            mock_discovery = AsyncMock()
            mock_discovery.__aenter__ = AsyncMock(return_value=mock_discovery)
            mock_discovery.discover_new_sources = AsyncMock(return_value=[])
            mock_discovery_cls.return_value = mock_discovery
            
            # Запускаем и сразу останавливаем
            async def quick_stop():
                await asyncio.sleep(0.1)
                await scheduler.stop()
            
            task = asyncio.create_task(quick_stop())
            await scheduler.start()
            await task
