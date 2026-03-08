"""
Tests for SLO Monitor Module

Полное покрытие для fp.slo_monitor
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import time

from fp.slo_monitor import SLOMonitor, SLOMetrics, Alert


class TestSLOMetrics:
    """Тесты для SLOMetrics"""

    def test_create_metrics_default(self):
        """Создание метрик по умолчанию"""
        metrics = SLOMetrics()
        assert metrics.hot_number == 0
        assert metrics.warm_count == 0
        assert metrics.quarantine_count == 0
        assert metrics.total_proxies == 0
        assert metrics.avg_score == 0.0
        assert metrics.checks_24h == 0
        assert metrics.success_24h == 0
        assert metrics.timestamp > 0

    def test_create_metrics_custom(self):
        """Создание метрик с кастомными значениями"""
        metrics = SLOMetrics(
            hot_count=30,
            warm_count=50,
            quarantine_count=20,
            total_proxies=100,
            avg_score=75.5,
            checks_24h=1000,
            success_24h=950,
        )
        assert metrics.hot_count == 30
        assert metrics.warm_count == 50
        assert metrics.quarantine_count == 20
        assert metrics.total_proxies == 100
        assert metrics.avg_score == 75.5

    def test_hot_ratio(self):
        """Расчёт hot_ratio"""
        metrics = SLOMetrics(hot_count=30, total_proxies=100)
        assert metrics.hot_ratio == 0.3

    def test_hot_ratio_zero_total(self):
        """Hot ratio при нулевом total"""
        metrics = SLOMetrics(hot_count=30, total_proxies=0)
        assert metrics.hot_ratio == 0.0

    def test_success_rate_24h(self):
        """Расчёт success_rate_24h"""
        metrics = SLOMetrics(checks_24h=1000, success_24h=950)
        assert metrics.success_rate_24h == 95.0

    def test_success_rate_24h_zero_checks(self):
        """Success rate при нулевых проверках"""
        metrics = SLOMetrics(checks_24h=0, success_24h=0)
        assert metrics.success_rate_24h == 100.0


class TestAlert:
    """Тесты для Alert"""

    def test_create_alert(self):
        """Создание алерта"""
        alert = Alert(
            id="test_alert",
            severity="critical",
            message="Test message",
        )
        assert alert.id == "test_alert"
        assert alert.severity == "critical"
        assert alert.message == "Test message"
        assert alert.resolved is False
        assert alert.resolved_at == 0.0
        assert alert.timestamp > 0

    def test_create_alert_with_metadata(self):
        """Создание алерта с метаданными"""
        alert = Alert(
            id="test_alert",
            severity="warning",
            message="Test message",
            metadata={"hot_count": 5, "target": 30},
        )
        assert alert.metadata == {"hot_count": 5, "target": 30}

    def test_alert_to_dict(self):
        """Конвертация в dict"""
        alert = Alert(
            id="test_alert",
            severity="info",
            message="Test message",
            metadata={"key": "value"},
        )
        
        result = alert.to_dict()
        
        assert result["id"] == "test_alert"
        assert result["severity"] == "info"
        assert result["message"] == "Test message"
        assert result["metadata"] == {"key": "value"}
        assert result["resolved"] is False
        assert "timestamp" in result

    def test_alert_to_dict_resolved(self):
        """Конвертация resolved алерта"""
        alert = Alert(
            id="test_alert",
            severity="warning",
            message="Test message",
            resolved=True,
            resolved_at=1234567890.0,
        )
        
        result = alert.to_dict()
        
        assert result["resolved"] is True
        assert result["resolved_at"] is not None


class TestSLOMonitorInit:
    """Тесты инициализации SLOMonitor"""

    def test_init_default(self):
        """Инициализация по умолчанию"""
        monitor = SLOMonitor()
        assert monitor.db_path == "~/.free-proxy/proxies.db"
        assert monitor.alert_path.parts[-1] == "alerts"
        assert monitor.check_interval == 60
        assert monitor._db is None
        assert len(monitor._alerts) == 0
        assert monitor._low_hot_start == 0.0
        assert monitor._running is False

    def test_init_custom(self):
        """Кастомная инициализация"""
        monitor = SLOMonitor(
            db_path="/tmp/test.db",
            alert_path="/tmp/alerts",
            check_interval_seconds=30,
        )
        assert monitor.db_path == "/tmp/test.db"
        assert monitor.check_interval == 30


class TestSLOMonitorContextManager:
    """Тесты контекстного менеджера"""

    @pytest.mark.asyncio
    async def test_aenter(self):
        """Вход в контекст"""
        monitor = SLOMonitor()
        
        with patch('fp.slo_monitor.ProxyDatabase') as mock_db_cls:
            mock_db = AsyncMock()
            mock_db.__aenter__ = AsyncMock(return_value=mock_db)
            mock_db_cls.return_value = mock_db
            
            with patch.object(monitor, '_load_alerts', new_callable=AsyncMock):
                async with monitor as m:
                    assert m._db is not None

    @pytest.mark.asyncio
    async def test_aexit(self):
        """Выход из контекста"""
        monitor = SLOMonitor()
        
        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        
        with patch('fp.slo_monitor.ProxyDatabase', return_value=mock_db), \
             patch.object(monitor, '_load_alerts', new_callable=AsyncMock), \
             patch.object(monitor, '_save_alerts', new_callable=AsyncMock):
            
            async with monitor:
                pass
            
            monitor._save_alerts.assert_called()


class TestSLOMonitorAlerts:
    """Тесты управления алертами"""

    @pytest.mark.asyncio
    async def test_load_alerts_empty(self):
        """Загрузка пустых алертов"""
        monitor = SLOMonitor()
        
        with patch('pathlib.Path.exists', return_value=False):
            await monitor._load_alerts()
        
        assert len(monitor._alerts) == 0

    @pytest.mark.asyncio
    async def test_load_alerts_with_file(self):
        """Загрузка алертов из файла"""
        monitor = SLOMonitor()
        
        mock_data = [
            {
                "id": "test_alert",
                "severity": "critical",
                "message": "Test message",
                "timestamp": time.time(),
                "resolved": False,
                "resolved_at": 0.0,
                "metadata": {},
            }
        ]
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('builtins.open'), \
             patch('json.load', return_value=mock_data):
            
            await monitor._load_alerts()
        
        assert len(monitor._alerts) == 1
        assert "test_alert" in monitor._alerts

    @pytest.mark.asyncio
    async def test_save_alerts(self):
        """Сохранение алертов"""
        monitor = SLOMonitor()
        monitor._alerts = {
            "active": Alert(
                id="active",
                severity="critical",
                message="Active alert",
                resolved=False,
            ),
            "resolved": Alert(
                id="resolved",
                severity="warning",
                message="Resolved alert",
                resolved=True,
            ),
        }
        
        mock_file = MagicMock()
        
        with patch('builtins.open', return_value=mock_file), \
             patch('json.dump') as mock_dump:
            
            await monitor._save_alerts()
        
        mock_dump.assert_called()
        # Должен сохранить только активный алерт
        saved_data = mock_dump.call_args[0][0]
        assert len(saved_data) == 1


class TestSLOMonitorCheckSLO:
    """Тесты проверки SLO"""

    @pytest.mark.asyncio
    async def test_check_slo_no_db(self):
        """Проверка без БД"""
        monitor = SLOMonitor()
        
        metrics, alerts = await monitor.check_slo()
        
        assert isinstance(metrics, SLOMetrics)
        assert alerts == []

    @pytest.mark.asyncio
    async def test_check_slo_ok(self):
        """SLO в норме"""
        monitor = SLOMonitor()
        monitor._db = AsyncMock()
        
        monitor._db.get_stats = AsyncMock(return_value={
            "hot_count": 35,  # >= SLO_HOT_MINIMUM (20)
            "warm_count": 40,
            "quarantine_count": 25,
            "total_proxies": 100,
            "avg_score": 75.0,
            "checks_24h": 0,
            "success_24h": 0,
        })
        
        metrics, alerts = await monitor.check_slo()
        
        assert metrics.hot_count == 35
        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_check_slo_critical(self):
        """Critical SLO (<10 HOT)"""
        monitor = SLOMonitor()
        monitor._db = AsyncMock()
        
        monitor._db.get_stats = AsyncMock(return_value={
            "hot_count": 5,  # < SLO_HOT_CRITICAL (10)
            "warm_count": 40,
            "quarantine_count": 55,
            "total_proxies": 100,
            "avg_score": 50.0,
            "checks_24h": 0,
            "success_24h": 0,
        })
        
        with patch.object(monitor, '_save_alerts', new_callable=AsyncMock):
            metrics, alerts = await monitor.check_slo()
        
        assert metrics.hot_count == 5
        assert len(alerts) >= 1
        assert any(a.severity == "critical" for a in alerts)

    @pytest.mark.asyncio
    async def test_check_slo_warning(self):
        """Warning SLO (<15 HOT)"""
        monitor = SLOMonitor()
        monitor._db = AsyncMock()
        
        monitor._db.get_stats = AsyncMock(return_value={
            "hot_count": 12,  # < SLO_HOT_WARNING (15) но >= SLO_HOT_CRITICAL (10)
            "warm_count": 40,
            "quarantine_count": 48,
            "total_proxies": 100,
            "avg_score": 60.0,
            "checks_24h": 0,
            "success_24h": 0,
        })
        
        with patch.object(monitor, '_save_alerts', new_callable=AsyncMock):
            metrics, alerts = await monitor.check_slo()
        
        assert metrics.hot_count == 12
        assert any(a.severity == "warning" for a in alerts)

    @pytest.mark.asyncio
    async def test_check_slo_info(self):
        """Info SLO (<20 HOT)"""
        monitor = SLOMonitor()
        monitor._db = AsyncMock()
        
        monitor._db.get_stats = AsyncMock(return_value={
            "hot_count": 18,  # < SLO_HOT_MINIMUM (20) но >= SLO_HOT_WARNING (15)
            "warm_count": 40,
            "quarantine_count": 42,
            "total_proxies": 100,
            "avg_score": 65.0,
            "checks_24h": 0,
            "success_24h": 0,
        })
        
        with patch.object(monitor, '_save_alerts', new_callable=AsyncMock):
            metrics, alerts = await monitor.check_slo()
        
        assert metrics.hot_count == 18
        assert any(a.severity == "info" for a in alerts)


class TestSLOMonitorHandleCritical:
    """Тесты обработки critical ситуации"""

    @pytest.mark.asyncio
    async def test_handle_critical_new_alert(self):
        """Создание нового critical алерта"""
        monitor = SLOMonitor()
        
        metrics = SLOMetrics(hot_count=5, total_proxies=100)
        
        alerts = await monitor._handle_critical(metrics)
        
        assert len(alerts) >= 1
        assert "hot_pool_critical" in monitor._alerts

    @pytest.mark.asyncio
    async def test_handle_critical_emergency(self):
        """Emergency алерт после 30 минут"""
        monitor = SLOMonitor()
        monitor._low_hot_start = time.time() - (35 * 60)  # 35 минут назад
        
        metrics = SLOMetrics(hot_count=5, total_proxies=100)
        
        # Сначала создаём critical алерт
        monitor._alerts["hot_pool_critical"] = Alert(
            id="hot_pool_critical",
            severity="critical",
            message="Critical",
        )
        
        alerts = await monitor._handle_critical(metrics)
        
        assert "hot_pool_emergency" in monitor._alerts


class TestSLOMonitorHandleWarning:
    """Тесты обработки warning ситуации"""

    @pytest.mark.asyncio
    async def test_handle_warning_new_alert(self):
        """Создание нового warning алерта"""
        monitor = SLOMonitor()
        
        metrics = SLOMetrics(hot_count=12, total_proxies=100)
        
        alerts = await monitor._handle_warning(metrics)
        
        assert len(alerts) >= 1
        assert "hot_pool_warning" in monitor._alerts


class TestSLOMonitorHandleInfo:
    """Тесты обработки info ситуации"""

    @pytest.mark.asyncio
    async def test_handle_info_new_alert(self):
        """Создание нового info алерта"""
        monitor = SLOMonitor()
        
        metrics = SLOMetrics(hot_count=18, total_proxies=100)
        
        alerts = await monitor._handle_info(metrics)
        
        assert len(alerts) == 1
        assert "hot_pool_below_target" in monitor._alerts


class TestSLOMonitorResolveAlerts:
    """Тесты разрешения алертов"""

    @pytest.mark.asyncio
    async def test_resolve_alerts_if_slo_ok(self):
        """Разрешение алертов при восстановлении SLO"""
        monitor = SLOMonitor()
        
        # Создаём активные алерты
        monitor._alerts = {
            "alert1": Alert(id="alert1", severity="warning", message="Test"),
            "alert2": Alert(id="alert2", severity="critical", message="Test"),
        }
        
        metrics = SLOMetrics(hot_count=30, total_proxies=100)  # >= SLO_HOT_MINIMUM
        
        await monitor._resolve_alerts_if_slo_ok(metrics)
        
        assert monitor._low_hot_start == 0
        assert all(a.resolved for a in monitor._alerts.values())

    @pytest.mark.asyncio
    async def test_resolve_alerts_if_slo_not_ok(self):
        """Алерты не разрешаются если SLO не ок"""
        monitor = SLOMonitor()
        
        monitor._alerts = {
            "alert1": Alert(id="alert1", severity="warning", message="Test"),
        }
        
        metrics = SLOMetrics(hot_count=15, total_proxies=100)  # < SLO_HOT_MINIMUM
        
        await monitor._resolve_alerts_if_slo_ok(metrics)
        
        assert not monitor._alerts["alert1"].resolved


class TestSLOMonitorGetAlerts:
    """Тесты получения алертов"""

    def test_get_active_alerts(self):
        """Получение активных алертов"""
        monitor = SLOMonitor()
        monitor._alerts = {
            "active": Alert(id="active", severity="critical", message="Active", resolved=False),
            "resolved": Alert(id="resolved", severity="warning", message="Resolved", resolved=True),
        }
        
        active = monitor.get_active_alerts()
        
        assert len(active) == 1
        assert active[0].id == "active"

    def test_get_alert_summary(self):
        """Получение сводки алертов"""
        monitor = SLOMonitor()
        monitor._alerts = {
            "critical1": Alert(id="critical1", severity="critical", message="C1", resolved=False),
            "critical2": Alert(id="critical2", severity="critical", message="C2", resolved=False),
            "warning1": Alert(id="warning1", severity="warning", message="W1", resolved=False),
            "info1": Alert(id="info1", severity="info", message="I1", resolved=False),
            "resolved1": Alert(id="resolved1", severity="critical", message="R1", resolved=True),
        }
        
        summary = monitor.get_alert_summary()
        
        assert summary["total"] == 4  # Только активные
        assert summary["critical"] == 2
        assert summary["warning"] == 1
        assert summary["info"] == 1
        assert len(summary["alerts"]) == 4


class TestSLOMonitorPrometheus:
    """Тесты Prometheus метрик"""

    @pytest.mark.asyncio
    async def test_export_prometheus_metrics_no_db(self):
        """Экспорт без БД"""
        monitor = SLOMonitor()
        
        result = await monitor.export_prometheus_metrics()
        
        assert result == ""

    @pytest.mark.asyncio
    async def test_export_prometheus_metrics(self):
        """Экспорт Prometheus метрик"""
        monitor = SLOMonitor()
        monitor._db = AsyncMock()
        
        monitor._db.get_stats = AsyncMock(return_value={
            "total_proxies": 100,
            "hot_count": 30,
            "warm_count": 40,
            "quarantine_count": 30,
            "avg_score": 75.5,
            "checks_24h": 1000,
            "success_24h": 950,
        })
        
        result = await monitor.export_prometheus_metrics()
        
        assert "free_proxy_total_proxies 100" in result
        assert "free_proxy_hot_proxies 30" in result
        assert "free_proxy_warm_proxies 40" in result
        assert "free_proxy_quarantine_proxies 30" in result
        assert "free_proxy_avg_score 75.50" in result
        assert "free_proxy_slo_hot_target 30" in result
        assert "free_proxy_slo_hot_minimum 20" in result

    @pytest.mark.asyncio
    async def test_export_prometheus_metrics_with_alerts(self):
        """Экспорт с алертами"""
        monitor = SLOMonitor()
        monitor._db = AsyncMock()
        
        monitor._db.get_stats = AsyncMock(return_value={
            "total_proxies": 100,
            "hot_count": 5,
            "warm_count": 40,
            "quarantine_count": 55,
            "avg_score": 50.0,
            "checks_24h": 0,
            "success_24h": 0,
        })
        
        monitor._alerts = {
            "critical1": Alert(id="critical1", severity="critical", message="C1", resolved=False),
            "warning1": Alert(id="warning1", severity="warning", message="W1", resolved=False),
        }
        
        result = await monitor.export_prometheus_metrics()
        
        assert "free_proxy_alerts_total 2" in result
        assert "free_proxy_alerts_critical 1" in result
        assert "free_proxy_alerts_warning 1" in result


class TestSLOMonitorConstants:
    """Тесты констант SLO"""

    def test_slo_constants(self):
        """Проверка констант SLO"""
        assert SLOMonitor.SLO_HOT_TARGET == 30
        assert SLOMonitor.SLO_HOT_MINIMUM == 20
        assert SLOMonitor.SLO_HOT_CRITICAL == 10
        assert SLOMonitor.SLO_HOT_WARNING == 15
        assert SLOMonitor.CRITICAL_DURATION_MINUTES == 30
        assert SLOMonitor.WARNING_DURATION_MINUTES == 15


class TestSLOMonitorMain:
    """Тесты main функции"""

    @pytest.mark.asyncio
    async def test_main_function(self):
        """Тест main функции"""
        from fp.slo_monitor import main
        
        with patch('fp.slo_monitor.SLOMonitor') as mock_monitor_cls:
            mock_monitor = AsyncMock()
            mock_monitor.__aenter__ = AsyncMock(return_value=mock_monitor)
            
            mock_metrics = SLOMetrics(hot_count=30, warm_count=40, quarantine_count=30, avg_score=75.0)
            mock_monitor.check_slo = AsyncMock(return_value=(mock_metrics, []))
            mock_monitor.get_alert_summary = MagicMock(return_value={"total": 0, "critical": 0, "warning": 0})
            mock_monitor.export_prometheus_metrics = AsyncMock(return_value="")
            
            mock_monitor_cls.return_value = mock_monitor
            
            try:
                await main()
            except Exception:
                pytest.fail("main() raised exception")
