"""
APScheduler for Proxy Maintenance

Планировщик для:
- Recheck quarantine прокси (каждый час)
- Cleanup старой истории (ежедневно)
- Recheck disabled источников (каждые 24ч)
- Генерация отчётов (ежечасно)
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from fp.database import ProxyDatabase
from fp.manager import ProxyManager

logger = logging.getLogger(__name__)


class ProxyScheduler:
    """
    Планировщик задач для Proxy Manager
    """
    
    def __init__(
        self,
        db_path: str = "~/.free-proxy/proxies.db",
        max_concurrent: int = 50,
        report_path: str = "~/.free-proxy/reports",
    ) -> None:
        self.db_path = db_path
        self.max_concurrent = max_concurrent
        self.report_path = Path(report_path).expanduser()
        
        self._scheduler = AsyncIOScheduler(
            timezone="UTC",
            job_defaults={
                "coalesce": True,
                "max_instances": 1,
                "misfire_grace_time": 60,
            },
        )
        
        self._manager: ProxyManager | None = None
        self._running = False
    
    async def start(self) -> None:
        """Запустить планировщик"""
        logger.info("Starting Proxy Scheduler...")
        
        # Открываем менеджер
        self._manager = ProxyManager(
            db_path=self.db_path,
            max_concurrent=self.max_concurrent,
            report_path=self.report_path,
        )
        await self._manager.__aenter__()
        
        # Задачи
        
        # 1. Recheck quarantine прокси (каждый час)
        self._scheduler.add_job(
            self._refresh_quarantine,
            IntervalTrigger(hours=1),
            id="refresh_quarantine",
            name="Recheck quarantine proxies",
            replace_existing=True,
        )
        
        # 2. Cleanup старой истории (ежедневно в 03:00 UTC)
        self._scheduler.add_job(
            self._cleanup_history,
            CronTrigger(hour=3, minute=0),
            id="cleanup_history",
            name="Cleanup old check history",
            replace_existing=True,
        )
        
        # 3. Hourly report (каждый час в 00 минут)
        self._scheduler.add_job(
            self._hourly_report,
            CronTrigger(minute=0),
            id="hourly_report",
            name="Generate hourly report",
            replace_existing=True,
        )
        
        # 4. Recheck disabled источников (каждые 24ч)
        self._scheduler.add_job(
            self._recheck_disabled_sources,
            IntervalTrigger(hours=24),
            id="recheck_sources",
            name="Recheck disabled sources",
            replace_existing=True,
        )
        
        # Запускаем планировщик
        self._scheduler.start()
        self._running = True
        
        logger.info("Proxy Scheduler started")
        
        # Держим запущенным
        try:
            # В asyncio режиме просто держим задачу
            while self._running:
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            await self.stop()
    
    async def stop(self) -> None:
        """Остановить планировщик"""
        logger.info("Stopping Proxy Scheduler...")
        
        self._running = False
        
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
        
        if self._manager:
            await self._manager.__aexit__(None, None, None)
        
        logger.info("Proxy Scheduler stopped")
    
    async def _refresh_quarantine(self) -> None:
        """Recheck прокси из карантина"""
        logger.info("Task: Refreshing quarantine proxies...")
        
        if not self._manager:
            return
        
        try:
            report = await self._manager.refresh_quarantine(limit=50)
            logger.info(
                f"Quarantine recheck: {report['total']} total, "
                f"{report['upgraded']} upgraded, {report['still_bad']} still bad"
            )
        except Exception as e:
            logger.error(f"Error in refresh_quarantine: {e}")
    
    async def _cleanup_history(self) -> None:
        """Очистка старой истории"""
        logger.info("Task: Cleaning up old history...")
        
        if not self._manager or not self._manager._db:
            return
        
        try:
            deleted = await self._manager._db.cleanup_old_history(days=7)
            logger.info(f"Deleted {deleted} old check history records")
        except Exception as e:
            logger.error(f"Error in cleanup_history: {e}")
    
    async def _hourly_report(self) -> None:
        """Генерация ежечасного отчёта"""
        logger.info("Task: Generating hourly report...")
        
        if not self._manager:
            return
        
        try:
            stats = await self._manager.get_stats()
            
            report = {
                "timestamp": datetime.now().isoformat(),
                "type": "hourly_stats",
                **stats,
            }
            
            # Сохраняем отчёт
            await self._manager._save_report(report)
            
            logger.info(
                f"Hourly report: {stats['total_proxies']} total, "
                f"{stats['hot_count']} hot, {stats['warm_count']} warm, "
                f"{stats['quarantine_count']} quarantine, "
                f"avg score: {stats['avg_score']:.1f}"
            )
        except Exception as e:
            logger.error(f"Error in hourly_report: {e}")
    
    async def _recheck_disabled_sources(self) -> None:
        """Recheck отключенных источников"""
        logger.info("Task: Rechecking disabled sources...")
        
        # TODO: Реализовать когда будет SourceManager
        # Пока просто лог
        logger.info("Source recheck not yet implemented")


async def main():
    """Пример использования"""
    import signal
    import sys
    
    scheduler = ProxyScheduler()
    
    # Обработка сигналов
    def signal_handler(sig, frame):
        logger.info("Received shutdown signal")
        asyncio.create_task(scheduler.stop())
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Запуск
    await scheduler.start()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    asyncio.run(main())
