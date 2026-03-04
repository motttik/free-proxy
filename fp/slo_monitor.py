"""
SLO + Alerts Module

Мониторинг и алерты для Proxy Pool:
- SLO: ≥20 HOT прокси (идеал 30)
- Alert: если <10 HOT > 30 минут
- Auto-rebuild при деградации
- Prometheus-style metrics
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from fp.database import ProxyDatabase
from fp.validator import ProxyPool


@dataclass
class SLOMetrics:
    """SLO метрики"""
    timestamp: float = field(default_factory=time.time)
    hot_count: int = 0
    warm_number: int = 0
    quarantine_count: int = 0
    total_proxies: int = 0
    avg_score: float = 0.0
    checks_24h: int = 0
    success_24h: int = 0
    
    @property
    def hot_ratio(self) -> float:
        """Доля HOT прокси"""
        if self.total_proxies == 0:
            return 0.0
        return self.hot_number / self.total_proxies
    
    @property
    def success_rate_24h(self) -> float:
        """Success rate за 24ч"""
        if self.checks_24h == 0:
            return 100.0
        return (self.success_24h / self.checks_24h) * 100


@dataclass
class Alert:
    """Алерт"""
    id: str
    severity: Literal["critical", "warning", "info"]
    message: str
    timestamp: float = field(default_factory=time.time)
    resolved: bool = False
    resolved_at: float = 0.0
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "severity": self.severity,
            "message": self.message,
            "timestamp": datetime.fromtimestamp(self.timestamp).isoformat(),
            "resolved": self.resolved,
            "resolved_at": datetime.fromtimestamp(self.resolved_at).isoformat() if self.resolved_at else None,
            "metadata": self.metadata,
        }


class SLOMonitor:
    """
    SLO Monitor для Proxy Pool
    
    SLO:
    - HOT прокси: ≥20 (цель 30)
    - Alert: <10 HOT > 30 минут → critical
    - Warning: <15 HOT > 15 минут
    
    Auto-actions:
    - Rebuild HOT pool при деградации
    - Emergency recheck quarantine
    """
    
    # SLO пороги
    SLO_HOT_TARGET = 30
    SLO_HOT_MINIMUM = 20
    SLO_HOT_CRITICAL = 10
    SLO_HOT_WARNING = 15
    
    # Время для алертов
    CRITICAL_DURATION_MINUTES = 30
    WARNING_DURATION_MINUTES = 15
    
    def __init__(
        self,
        db_path: str = "~/.free-proxy/proxies.db",
        alert_path: str = "~/.free-proxy/alerts",
        check_interval_seconds: int = 60,
    ) -> None:
        self.db_path = db_path
        self.alert_path = Path(alert_path).expanduser()
        self.alert_path.mkdir(parents=True, exist_ok=True)
        self.check_interval = check_interval_seconds
        
        self._db: ProxyDatabase | None = None
        self._alerts: dict[str, Alert] = {}
        self._low_hot_start: float = 0.0
        self._running = False
    
    async def __aenter__(self) -> "SLOMonitor":
        self._db = await ProxyDatabase(self.db_path).__aenter__()
        await self._load_alerts()
        return self
    
    async def __aexit__(self, *args) -> None:
        if self._db:
            await self._db.__aexit__(*args)
        await self._save_alerts()
    
    async def _load_alerts(self) -> None:
        """Загрузить активные алерты"""
        alert_file = self.alert_path / "active_alerts.json"
        if alert_file.exists():
            with open(alert_file) as f:
                data = json.load(f)
                for alert_data in data:
                    self._alerts[alert_data["id"]] = Alert(**alert_data)
    
    async def _save_alerts(self) -> None:
        """Сохранить алерты"""
        alert_file = self.alert_path / "active_alerts.json"
        data = [alert.to_dict() for alert in self._alerts.values() if not alert.resolved]
        with open(alert_file, "w") as f:
            json.dump(data, f, indent=2)
    
    async def check_slo(self) -> tuple[SLOMetrics, list[Alert]]:
        """
        Проверить SLO и создать алерты при необходимости
        
        Returns:
            (метрики, новые алерты)
        """
        if not self._db:
            return SLOMetrics(), []
        
        # Получаем метрики
        stats = await self._db.get_stats()
        metrics = SLOMetrics(
            hot_number=stats.get("hot_count", 0),
            warm_number=stats.get("warm_number", 0),
            quarantine_count=stats.get("quarantine_count", 0),
            total_proxies=stats.get("total_proxies", 0),
            avg_score=stats.get("avg_score", 0),
            checks_24h=stats.get("checks_24h", 0),
            success_24h=stats.get("success_24h", 0),
        )
        
        new_alerts = []
        
        # Проверка SLO
        if metrics.hot_number < self.SLO_HOT_CRITICAL:
            # Critical: <10 HOT
            new_alerts.extend(await self._handle_critical(metrics))
        elif metrics.hot_number < self.SLO_HOT_WARNING:
            # Warning: <15 HOT
            new_alerts.extend(await self._handle_warning(metrics))
        elif metrics.hot_number < self.SLO_HOT_MINIMUM:
            # Info: <20 HOT
            new_alerts.extend(await self._handle_info(metrics))
        else:
            # SLO выполнено, resolvим алерты
            await self._resolve_alerts_if_slo_ok(metrics)
        
        # Сохраняем
        await self._save_alerts()
        
        return metrics, new_alerts
    
    async def _handle_critical(self, metrics: SLOMetrics) -> list[Alert]:
        """Обработка critical ситуации (<10 HOT)"""
        now = time.time()
        
        # Засекаем время низкой HOT count
        if self._low_hot_start == 0:
            self._low_hot_start = now
        
        duration_minutes = (now - self._low_hot_start) / 60
        
        alerts = []
        
        # Создаём/обновляем critical алерт
        alert_id = "hot_pool_critical"
        if alert_id not in self._alerts:
            alert = Alert(
                id=alert_id,
                severity="critical",
                message=f"HOT pool критически мал: {metrics.hot_number} прокси (цель: {self.SLO_HOT_TARGET})",
                metadata={
                    "hot_number": metrics.hot_number,
                    "target": self.SLO_HOT_TARGET,
                    "duration_minutes": duration_minutes,
                },
            )
            self._alerts[alert_id] = alert
            alerts.append(alert)
        
        # Если >30 минут → emergency actions
        if duration_minutes >= self.CRITICAL_DURATION_MINUTES:
            emergency_alert = Alert(
                id="hot_pool_emergency",
                severity="critical",
                message=f"EMERGENCY: HOT pool <10 уже {duration_minutes:.0f} минут! Требуется вмешательство.",
                metadata={
                    "hot_number": metrics.hot_number,
                    "duration_minutes": duration_minutes,
                    "action_required": "rebuild_hot_pool",
                },
            )
            if "hot_pool_emergency" not in self._alerts:
                self._alerts["hot_pool_emergency"] = emergency_alert
                alerts.append(emergency_alert)
        
        return alerts
    
    async def _handle_warning(self, metrics: SLOMetrics) -> list[Alert]:
        """Обработка warning ситуации (<15 HOT)"""
        now = time.time()
        
        if self._low_hot_start == 0:
            self._low_hot_start = now
        
        duration_minutes = (now - self._low_hot_start) / 60
        
        alerts = []
        
        # Warning алерт
        alert_id = "hot_pool_warning"
        if alert_id not in self._alerts:
            alert = Alert(
                id=alert_id,
                severity="warning",
                message=f"HOT pool мал: {metrics.hot_number} прокси (цель: {self.SLO_HOT_TARGET})",
                metadata={
                    "hot_number": metrics.hot_number,
                    "target": self.SLO_HOT_TARGET,
                    "duration_minutes": duration_minutes,
                },
            )
            self._alerts[alert_id] = alert
            alerts.append(alert)
        
        return alerts
    
    async def _handle_info(self, metrics: SLOMetrics) -> list[Alert]:
        """Info: <20 HOT (но ≥15)"""
        alert_id = "hot_pool_below_target"
        
        if alert_id not in self._alerts:
            alert = Alert(
                id=alert_id,
                severity="info",
                message=f"HOT pool ниже цели: {metrics.hot_number} прокси (цель: {self.SLO_HOT_TARGET})",
                metadata={"hot_number": metrics.hot_number},
            )
            self._alerts[alert_id] = alert
            return [alert]
        
        return []
    
    async def _resolve_alerts_if_slo_ok(self, metrics: SLOMetrics) -> None:
        """Resolvим алерты если SLO ок"""
        if metrics.hot_number >= self.SLO_HOT_MINIMUM:
            self._low_hot_start = 0
            
            # Resolvим все active алерты
            for alert in self._alerts.values():
                if not alert.resolved:
                    alert.resolved = True
                    alert.resolved_at = time.time()
    
    def get_active_alerts(self) -> list[Alert]:
        """Получить активные алерты"""
        return [a for a in self._alerts.values() if not a.resolved]
    
    def get_alert_summary(self) -> dict:
        """Краткая сводка по алертам"""
        active = self.get_active_alerts()
        
        critical = sum(1 for a in active if a.severity == "critical")
        warning = sum(1 for a in active if a.severity == "warning")
        info = sum(1 for a in active if a.severity == "info")
        
        return {
            "total": len(active),
            "critical": critical,
            "warning": warning,
            "info": info,
            "alerts": [a.to_dict() for a in active],
        }
    
    async def export_prometheus_metrics(self) -> str:
        """Экспорт метрик в Prometheus формате"""
        if not self._db:
            return ""
        
        stats = await self._db.get_stats()
        
        metrics = [
            f'free_proxy_total_proxies {stats.get("total_proxies", 0)}',
            f'free_proxy_hot_proxies {stats.get("hot_count", 0)}',
            f'free_proxy_warm_proxies {stats.get("warm_number", 0)}',
            f'free_proxy_quarantine_proxies {stats.get("quarantine_count", 0)}',
            f'free_proxy_avg_score {stats.get("avg_score", 0):.2f}',
            f'free_proxy_checks_24h_total {stats.get("checks_24h", 0)}',
            f'free_proxy_success_24h_total {stats.get("success_24h", 0)}',
            f'free_proxy_slo_hot_target {self.SLO_HOT_TARGET}',
            f'free_proxy_slo_hot_minimum {self.SLO_HOT_MINIMUM}',
        ]
        
        # Алерты
        active_alerts = self.get_active_alerts()
        metrics.append(f'free_proxy_alerts_total {len(active_alerts)}')
        metrics.append(f'free_proxy_alerts_critical {sum(1 for a in active_alerts if a.severity == "critical")}')
        metrics.append(f'free_proxy_alerts_warning {sum(1 for a in active_alerts if a.severity == "warning")}')
        
        return "\n".join(metrics) + "\n"


async def main():
    """Пример использования"""
    async with SLOMonitor() as monitor:
        print("=== SLO Check ===")
        metrics, alerts = await monitor.check_slo()
        
        print(f"HOT: {metrics.hot_number} (цель: {SLOMonitor.SLO_HOT_TARGET})")
        print(f"WARM: {metrics.warm_number}")
        print(f"Quarantine: {metrics.quarantine_count}")
        print(f"Avg Score: {metrics.avg_score:.1f}")
        
        if alerts:
            print(f"\nNew Alerts: {len(alerts)}")
            for alert in alerts:
                print(f"  [{alert.severity.upper()}] {alert.message}")
        
        print("\n=== Alert Summary ===")
        summary = monitor.get_alert_summary()
        print(f"Total: {summary['total']}")
        print(f"Critical: {summary['critical']}")
        print(f"Warning: {summary['warning']}")
        
        print("\n=== Prometheus Metrics ===")
        prom_metrics = await monitor.export_prometheus_metrics()
        print(prom_metrics)


if __name__ == "__main__":
    asyncio.run(main())
