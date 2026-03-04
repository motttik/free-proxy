"""
SQLite Database for Proxy Storage

Хранение:
- Прокси (ip, port, protocol, country)
- Метрики (score, latency, uptime, ban_rate)
- Источники (url, fail_streak, disabled_until)
- История проверок
"""

import asyncio
import json
import time
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

import aiosqlite

from fp.validator import ProxyMetrics, ProxyPool, ProxyValidationResult


class ProxyDatabase:
    """
    Асинхронная SQLite база для хранения прокси
    """
    
    def __init__(self, db_path: str = "~/.free-proxy/proxies.db") -> None:
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: aiosqlite.Connection | None = None
    
    async def __aenter__(self) -> "ProxyDatabase":
        self._conn = await aiosqlite.connect(
            str(self.db_path),
            timeout=30.0,
        )
        # WAL режим для лучшей конкурентности
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA synchronous=NORMAL")
        await self._conn.execute("PRAGMA cache_size=10000")
        await self._conn.execute("PRAGMA temp_store=MEMORY")
        await self._create_tables()
        await self._run_migrations()
        return self
    
    async def __aexit__(self, *args) -> None:
        if self._conn:
            await self._conn.close()
    
    async def _run_migrations(self) -> None:
        """Простая миграция БД"""
        assert self._conn is not None

        # Миграция 1: avg_latency в sources
        cursor = await self._conn.execute("PRAGMA table_info(sources)")
        columns = [row[1] for row in await cursor.fetchall()]

        if "avg_latency" not in columns:
            await self._conn.execute("ALTER TABLE sources ADD COLUMN avg_latency REAL DEFAULT 0")
            await self._conn.commit()
        
        # Миграция 2: health contract поля в proxies
        cursor = await self._conn.execute("PRAGMA table_info(proxies)")
        columns = [row[1] for row in await cursor.fetchall()]
        
        if "last_live_check" not in columns:
            await self._conn.execute("ALTER TABLE proxies ADD COLUMN last_live_check REAL")
            await self._conn.commit()
        
        if "last_check" not in columns:
            await self._conn.execute("ALTER TABLE proxies ADD COLUMN last_check REAL")
            await self._conn.commit()
        
        if "fail_streak" not in columns:
            await self._conn.execute("ALTER TABLE proxies ADD COLUMN fail_streak INTEGER DEFAULT 0")
            await self._conn.commit()

    async def _create_tables(self) -> None:
        """Создать таблицы"""
        assert self._conn is not None

        # Таблица прокси
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS proxies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip TEXT NOT NULL,
                port INTEGER NOT NULL,
                protocol TEXT NOT NULL DEFAULT 'http',
                country TEXT,
                source TEXT,
                pool TEXT DEFAULT 'warm',
                created_at REAL DEFAULT (strftime('%s', 'now')),
                updated_at REAL DEFAULT (strftime('%s', 'now')),
                last_live_check REAL,
                last_check REAL,
                fail_streak INTEGER DEFAULT 0,
                UNIQUE(ip, port, protocol)
            )
        """)
        
        # Индексы для быстрого поиска
        await self._conn.execute("CREATE INDEX IF NOT EXISTS idx_proxy_ip ON proxies(ip)")
        await self._conn.execute("CREATE INDEX IF NOT EXISTS idx_proxy_pool ON proxies(pool)")
        await self._conn.execute("CREATE INDEX IF NOT EXISTS idx_proxy_country ON proxies(country)")
        await self._conn.execute("CREATE INDEX IF NOT EXISTS idx_proxy_last_live_check ON proxies(last_live_check DESC)")
        
        # Таблица метрик
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proxy_id INTEGER NOT NULL,
                latency_ms REAL DEFAULT 0,
                uptime REAL DEFAULT 100,
                success_rate REAL DEFAULT 100,
                ban_rate REAL DEFAULT 0,
                total_checks INTEGER DEFAULT 0,
                successful_checks INTEGER DEFAULT 0,
                failed_checks INTEGER DEFAULT 0,
                last_check REAL,
                last_success REAL,
                score REAL DEFAULT 0,
                created_at REAL DEFAULT (strftime('%s', 'now')),
                FOREIGN KEY (proxy_id) REFERENCES proxies(id) ON DELETE CASCADE,
                UNIQUE(proxy_id)
            )
        """)
        
        # Таблица истории проверок
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS check_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proxy_id INTEGER NOT NULL,
                success INTEGER NOT NULL,
                latency_ms REAL,
                status_code INTEGER,
                error TEXT,
                stage TEXT,
                target_results TEXT,
                checked_at REAL DEFAULT (strftime('%s', 'now')),
                FOREIGN KEY (proxy_id) REFERENCES proxies(id) ON DELETE CASCADE
            )
        """)
        
        # Индекс для истории (последние проверки)
        await self._conn.execute("CREATE INDEX IF NOT EXISTS idx_history_time ON check_history(checked_at DESC)")
        
        # Таблица источников
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                type TEXT NOT NULL,
                protocols TEXT,
                fail_streak INTEGER DEFAULT 0,
                pass_rate REAL DEFAULT 100,
                total_fetches INTEGER DEFAULT 0,
                successful_fetches INTEGER DEFAULT 0,
                avg_latency REAL DEFAULT 0,
                disabled_until REAL,
                last_check REAL,
                created_at REAL DEFAULT (strftime('%s', 'now'))
            )
        """)
        
        # Таблица бан-листа
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS banlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip TEXT NOT NULL UNIQUE,
                reason TEXT,
                asn TEXT,
                created_at REAL DEFAULT (strftime('%s', 'now'))
            )
        """)
        
        await self._conn.commit()
    
    async def add_proxy(
        self,
        ip: str,
        port: int,
        protocol: str = "http",
        country: str | None = None,
        source: str | None = None,
    ) -> int:
        """
        Добавить прокси
        
        Returns:
            proxy_id или -1 если уже существует
        """
        assert self._conn is not None
        
        # Проверка на бан-лист
        is_banned = await self._conn.execute(
            "SELECT 1 FROM banlist WHERE ip = ?", (ip,)
        )
        if await is_banned.fetchone():
            return -1
        
        try:
            cursor = await self._conn.execute(
                """
                INSERT OR IGNORE INTO proxies (ip, port, protocol, country, source)
                VALUES (?, ?, ?, ?, ?)
                """,
                (ip, port, protocol, country, source),
            )
            await self._conn.commit()
            
            if cursor.rowcount == 0:
                return -1  # Уже существует
            
            proxy_id = cursor.lastrowid
            
            # Создаём пустую метрику
            await self._conn.execute(
                "INSERT INTO metrics (proxy_id) VALUES (?)", (proxy_id,)
            )
            await self._conn.commit()
            
            return proxy_id
            
        except aiosqlite.IntegrityError:
            return -1
    
    async def update_metrics(
        self,
        proxy_id: int,
        metrics: ProxyMetrics,
        score: float,
    ) -> None:
        """Обновить метрики прокси"""
        assert self._conn is not None
        
        await self._conn.execute(
            """
            UPDATE metrics SET
                latency_ms = ?,
                uptime = ?,
                success_rate = ?,
                ban_rate = ?,
                total_checks = ?,
                successful_checks = ?,
                failed_checks = ?,
                last_check = ?,
                last_success = ?,
                score = ?
            WHERE proxy_id = ?
            """,
            (
                metrics.latency_ms,
                metrics.uptime,
                metrics.success_rate,
                metrics.ban_rate,
                metrics.total_checks,
                metrics.successful_checks,
                metrics.failed_checks,
                metrics.last_check,
                metrics.last_success,
                score,
                proxy_id,
            ),
        )
        await self._conn.commit()
    
    async def update_pool(self, proxy_id: int, pool: ProxyPool) -> None:
        """Обновить пул прокси"""
        assert self._conn is not None

        await self._conn.execute(
            "UPDATE proxies SET pool = ?, updated_at = strftime('%s', 'now') WHERE id = ?",
            (pool.value, proxy_id),
        )
        await self._conn.commit()
    
    async def update_health_on_success(self, proxy_id: int) -> None:
        """Обновить health после успешной проверки"""
        assert self._conn is not None
        
        now = time.time()
        await self._conn.execute(
            """
            UPDATE proxies SET
                last_live_check = ?,
                last_check = ?,
                fail_streak = 0
            WHERE id = ?
            """,
            (now, now, proxy_id),
        )
        await self._conn.commit()
    
    async def update_health_on_fail(self, proxy_id: int) -> None:
        """Обновить health после неудачной проверки"""
        assert self._conn is not None
        
        now = time.time()
        await self._conn.execute(
            """
            UPDATE proxies SET
                last_check = ?,
                fail_streak = fail_streak + 1
            WHERE id = ?
            """,
            (now, proxy_id),
        )
        await self._conn.commit()
    
    async def is_proxy_fresh(
        self,
        proxy_id: int,
        pool: str,
        hot_ttl_minutes: int = 15,
        warm_ttl_minutes: int = 45,
    ) -> bool:
        """
        Проверить, не устарела ли прокси
        
        Args:
            proxy_id: ID прокси
            pool: Текущий пул (hot/warm)
            hot_ttl_minutes: TTL для HOT
            warm_ttl_minutes: TTL для WARM
        
        Returns:
            True если прокси свежая
        """
        assert self._conn is not None
        
        cursor = await self._conn.execute(
            "SELECT last_live_check FROM proxies WHERE id = ?",
            (proxy_id,),
        )
        row = await cursor.fetchone()
        
        if not row or not row[0]:
            return False
        
        ttl = hot_ttl_minutes if pool == "hot" else warm_ttl_minutes
        age_minutes = (time.time() - row[0]) / 60
        
        return age_minutes < ttl
    
    async def add_check_history(
        self,
        proxy_id: int,
        result: ProxyValidationResult,
    ) -> None:
        """Добавить запись в историю проверок"""
        assert self._conn is not None

        # success = 1 если metrics.successful_checks > 0 ИЛИ result.passed
        success = 1 if (result.metrics.successful_checks > 0 or result.passed) else 0

        await self._conn.execute(
            """
            INSERT INTO check_history (proxy_id, success, latency_ms, status_code, error, stage, target_results)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                proxy_id,
                success,
                result.latency_ms,
                None,
                result.error,
                result.stage.value,
                json.dumps(result.target_results),
            ),
        )
        await self._conn.commit()
    
    async def get_proxy_by_pool(
        self,
        pool: ProxyPool,
        limit: int = 100,
        country: str | None = None,
        protocol: str | None = None,
    ) -> list[dict]:
        """Получить прокси из пула"""
        assert self._conn is not None
        
        query = """
            SELECT p.ip, p.port, p.protocol, p.country, p.source, m.score, m.latency_ms
            FROM proxies p
            JOIN metrics m ON p.id = m.proxy_id
            WHERE p.pool = ?
        """
        params = [pool.value]
        
        if country:
            query += " AND p.country = ?"
            params.append(country)
        
        if protocol:
            query += " AND p.protocol = ?"
            params.append(protocol)
        
        query += " ORDER BY m.score DESC, m.last_check ASC LIMIT ?"
        params.append(limit)
        
        cursor = await self._conn.execute(query, params)
        rows = await cursor.fetchall()
        
        return [
            {
                "ip": row[0],
                "port": row[1],
                "protocol": row[2],
                "country": row[3],
                "source": row[4],
                "score": row[5],
                "latency_ms": row[6],
            }
            for row in rows
        ]
    
    async def get_hot_proxies(self, limit: int = 100) -> list[dict]:
        """Получить прокси из HOT пула"""
        return await self.get_proxy_by_pool(ProxyPool.HOT, limit)
    
    async def get_warm_proxies(self, limit: int = 100) -> list[dict]:
        """Получить прокси из WARM пула"""
        return await self.get_proxy_by_pool(ProxyPool.WARM, limit)
    
    async def get_quarantine_proxies(self, limit: int = 100) -> list[dict]:
        """Получить прокси из QUARANTINE пула"""
        return await self.get_proxy_by_pool(ProxyPool.QUARANTINE, limit)
    
    async def get_proxy_id(self, ip: str, port: int, protocol: str = "http") -> int | None:
        """Получить ID прокси по IP:PORT"""
        assert self._conn is not None
        
        cursor = await self._conn.execute(
            "SELECT id FROM proxies WHERE ip = ? AND port = ? AND protocol = ?",
            (ip, port, protocol),
        )
        row = await cursor.fetchone()
        return row[0] if row else None
    
    async def cleanup_old_history(self, days: int = 7) -> int:
        """Удалить старую историю проверок"""
        assert self._conn is not None
        
        cutoff = time.time() - (days * 24 * 60 * 60)
        
        cursor = await self._conn.execute(
            "DELETE FROM check_history WHERE checked_at < ?", (cutoff,)
        )
        await self._conn.commit()
        
        return cursor.rowcount
    
    async def add_to_banlist(self, ip: str, reason: str = "", asn: str | None = None) -> None:
        """Добавить IP в бан-лист"""
        assert self._conn is not None
        
        await self._conn.execute(
            "INSERT OR IGNORE INTO banlist (ip, reason, asn) VALUES (?, ?, ?)",
            (ip, reason, asn),
        )
        await self._conn.commit()
    
    async def is_banned(self, ip: str) -> bool:
        """Проверить, есть ли IP в бан-листе"""
        assert self._conn is not None
        
        cursor = await self._conn.execute("SELECT 1 FROM banlist WHERE ip = ?", (ip,))
        return await cursor.fetchone() is not None
    
    async def get_stats(self) -> dict:
        """Получить статистику по базе"""
        assert self._conn is not None
        
        stats = {}
        
        # Общее количество прокси
        cursor = await self._conn.execute("SELECT COUNT(*) FROM proxies")
        stats["total_proxies"] = (await cursor.fetchone())[0]
        
        # По пулам
        for pool in ProxyPool:
            cursor = await self._conn.execute(
                "SELECT COUNT(*) FROM proxies WHERE pool = ?", (pool.value,)
            )
            stats[f"{pool.value}_count"] = (await cursor.fetchone())[0]
        
        # Средний score
        cursor = await self._conn.execute("SELECT AVG(score) FROM metrics")
        stats["avg_score"] = (await cursor.fetchone())[0] or 0
        
        # История за 24ч
        cutoff = time.time() - (24 * 60 * 60)
        cursor = await self._conn.execute(
            "SELECT COUNT(*), SUM(success) FROM check_history WHERE checked_at > ?",
            (cutoff,),
        )
        row = await cursor.fetchone()
        stats["checks_24h"] = row[0] or 0
        stats["success_24h"] = row[1] or 0
        
        # Бан-лист
        cursor = await self._conn.execute("SELECT COUNT(*) FROM banlist")
        stats["banlist_count"] = (await cursor.fetchone())[0]
        
        return stats


async def main():
    """Пример использования"""
    async with ProxyDatabase() as db:
        # Добавить прокси
        proxy_id = await db.add_proxy("8.219.97.248", 80, "http", "ID", "test_source")
        print(f"Added proxy ID: {proxy_id}")
        
        # Получить статистику
        stats = await db.get_stats()
        print(f"Stats: {json.dumps(stats, indent=2)}")


if __name__ == "__main__":
    asyncio.run(main())
