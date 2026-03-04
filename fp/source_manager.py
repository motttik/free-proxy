"""
Source Manager

Управление источниками прокси:
- Fetch прокси из источников
- Fail streak tracking
- Auto-disable при fail streak > N
- Pass rate calculation
- Auto-promote/discover новых источников
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Literal

import httpx

from fp.config import ALL_SOURCES, ProxySource, SourceType
from fp.sources import get_parser
from fp.sources.base import Proxy
from fp.database import ProxyDatabase


class SourceManager:
    """
    Менеджер источников прокси
    """
    
    def __init__(
        self,
        db_path: str = "~/.free-proxy/proxies.db",
        max_concurrent: int = 10,
        fail_streak_threshold: int = 5,
        pass_rate_threshold: float = 30.0,
        disable_hours: int = 24,
    ) -> None:
        self.db_path = db_path
        self.max_concurrent = max_concurrent
        self.fail_streak_threshold = fail_streak_threshold
        self.pass_rate_threshold = pass_rate_threshold
        self.disable_hours = disable_hours
        
        self._db: ProxyDatabase | None = None
        self._client: httpx.AsyncClient | None = None
    
    async def __aenter__(self) -> "SourceManager":
        self._db = await ProxyDatabase(self.db_path).__aenter__()
        self._client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
        )
        
        # Инициализация источников в БД
        await self._init_sources()
        
        return self
    
    async def __aexit__(self, *args) -> None:
        if self._client:
            await self._client.aclose()
        if self._db:
            await self._db.__aexit__(*args)
    
    async def _init_sources(self) -> None:
        """Инициализировать источники в БД"""
        assert self._db is not None
        
        for source in ALL_SOURCES:
            protocols = ",".join(p.value for p in source["protocols"])
            
            try:
                await self._db._conn.execute(
                    """
                    INSERT OR IGNORE INTO sources 
                    (name, url, type, protocols, fail_streak, pass_rate, total_fetches, successful_fetches)
                    VALUES (?, ?, ?, ?, 0, 100, 0, 0)
                    """,
                    (source["name"], source["url"], source["type"].value, protocols),
                )
            except Exception:
                pass
        
        await self._db._conn.commit()
    
    async def fetch_source(self, source: ProxySource) -> tuple[list[Proxy], bool]:
        """
        Получить прокси из источника
        
        Returns:
            (список прокси, успех)
        """
        try:
            parser = get_parser(source)
            result = parser.parse()
            
            if result.success:
                return result.proxies, True
            else:
                return [], False
                
        except Exception as e:
            return [], False
    
    async def update_source_stats(
        self,
        url: str,
        success: bool,
        proxies_found: int = 0,
    ) -> None:
        """Обновить статистику источника"""
        assert self._db is not None
        
        # Получаем текущие stats
        cursor = await self._db._conn.execute(
            "SELECT fail_streak, total_fetches, successful_fetches FROM sources WHERE url = ?",
            (url,),
        )
        row = await cursor.fetchone()
        
        if not row:
            return
        
        fail_streak, total_fetches, successful_fetches = row
        
        # Обновляем
        if success:
            fail_streak = 0
            successful_fetches += 1
        else:
            fail_streak += 1
        
        total_fetches += 1
        
        # Pass rate
        pass_rate = (successful_fetches / total_fetches * 100) if total_fetches > 0 else 0
        
        # Disabled until если fail streak > threshold
        disabled_until = None
        if fail_streak >= self.fail_streak_threshold:
            disabled_until = time.time() + (self.disable_hours * 60 * 60)
        
        await self._db._conn.execute(
            """
            UPDATE sources SET
                fail_streak = ?,
                total_fetches = ?,
                successful_fetches = ?,
                pass_rate = ?,
                disabled_until = ?,
                last_check = strftime('%s', 'now')
            WHERE url = ?
            """,
            (fail_streak, total_fetches, successful_fetches, pass_rate, disabled_until, url),
        )
        await self._db._conn.commit()
    
    async def fetch_all_sources(self) -> dict:
        """
        Получить прокси из всех активных источников
        
        Returns:
            Отчёт о сборе
        """
        assert self._db is not None
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_sources": 0,
            "active_sources": 0,
            "disabled_sources": 0,
            "successful": 0,
            "failed": 0,
            "total_proxies": 0,
            "new_proxies": 0,
            "sources": [],
        }
        
        # Получаем все источники
        cursor = await self._db._conn.execute(
            "SELECT name, url, type, protocols, fail_streak, disabled_until FROM sources",
        )
        rows = await cursor.fetchall()
        
        now = time.time()
        tasks = []
        source_info = []
        
        for row in rows:
            name, url, type_, protocols, fail_streak, disabled_until = row
            
            report["total_sources"] += 1
            
            # Проверка disabled
            if disabled_until and disabled_until > now:
                report["disabled_sources"] += 1
                continue
            
            report["active_sources"] += 1
            
            # Создаём ProxySource
            source = ProxySource(
                name=name,
                url=url,
                type=SourceType(type_),
                protocols=[type(protocols.split(",")[0])],  # Упрощённо
                country=None,
                update_frequency=60,
                timeout=30,
                max_retries=3,
            )
            
            tasks.append(self._fetch_and_store(source))
            source_info.append(name)
        
        # Выполняем параллельно
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    report["failed"] += 1
                    report["sources"].append({
                        "name": source_info[i],
                        "success": False,
                        "error": str(result),
                    })
                else:
                    success, proxies, new = result
                    report["total_proxies"] += proxies
                    report["new_proxies"] += new
                    
                    if success:
                        report["successful"] += 1
                    else:
                        report["failed"] += 1
                    
                    report["sources"].append({
                        "name": source_info[i],
                        "success": success,
                        "proxies": proxies,
                    })
        
        return report
    
    async def _fetch_and_store(self, source: ProxySource) -> tuple[bool, int, int]:
        """
        Получить прокси из источника и сохранить в БД
        
        Returns:
            (success, total_proxies, new_proxies)
        """
        assert self._db is not None
        
        try:
            proxies, success = await self.fetch_source(source)
            
            # Обновляем статистику источника
            await self.update_source_stats(source["url"], success, len(proxies))
            
            if not success or not proxies:
                return False, 0, 0
            
            # Сохраняем прокси
            new_count = 0
            for proxy in proxies:
                proxy_id = await self._db.add_proxy(
                    proxy.ip,
                    proxy.port,
                    proxy.protocol,
                    country=proxy.country,
                    source=source["name"],
                )
                if proxy_id > 0:
                    new_count += 1
            
            return True, len(proxies), new_count
            
        except Exception as e:
            await self.update_source_stats(source["url"], False, 0)
            return False, 0, 0
    
    async def get_disabled_sources(self) -> list[dict]:
        """Получить список отключенных источников"""
        assert self._db is not None
        
        now = time.time()
        
        cursor = await self._db._conn.execute(
            """
            SELECT name, url, fail_streak, pass_rate, disabled_until
            FROM sources
            WHERE disabled_until IS NOT NULL AND disabled_until > ?
            ORDER BY disabled_until ASC
            """,
            (now,),
        )
        
        rows = await cursor.fetchall()
        
        return [
            {
                "name": row[0],
                "url": row[1],
                "fail_streak": row[2],
                "pass_rate": row[3],
                "disabled_until": datetime.fromtimestamp(row[4]).isoformat(),
            }
            for row in rows
        ]
    
    async def get_source_stats(self) -> list[dict]:
        """Получить статистику по всем источникам"""
        assert self._db is not None
        
        cursor = await self._db._conn.execute(
            """
            SELECT name, url, type, protocols, fail_streak, pass_rate, 
                   total_fetches, successful_fetches, disabled_until, last_check
            FROM sources
            ORDER BY pass_rate DESC
            """,
        )
        
        rows = await cursor.fetchall()
        
        return [
            {
                "name": row[0],
                "url": row[1],
                "type": row[2],
                "protocols": row[3],
                "fail_streak": row[4],
                "pass_rate": row[5],
                "total_fetches": row[6],
                "successful_fetches": row[7],
                "disabled": row[8] is not None and row[8] > time.time(),
                "disabled_until": datetime.fromtimestamp(row[8]).isoformat() if row[8] else None,
                "last_check": datetime.fromtimestamp(row[9]).isoformat() if row[9] else None,
            }
            for row in rows
        ]


async def main():
    """Пример использования"""
    async with SourceManager() as manager:
        print("=== Fetch All Sources ===")
        report = await manager.fetch_all_sources()
        print(f"Total sources: {report['total_sources']}")
        print(f"Active: {report['active_sources']}")
        print(f"Disabled: {report['disabled_sources']}")
        print(f"Successful: {report['successful']}")
        print(f"Failed: {report['failed']}")
        print(f"Total proxies: {report['total_proxies']}")
        print(f"New proxies: {report['new_proxies']}")
        
        print("\n=== Source Stats ===")
        stats = await manager.get_source_stats()
        for source in stats[:10]:  # Топ 10
            status = "🔴" if source["disabled"] else "🟢"
            print(f"{status} {source['name']}: {source['pass_rate']:.1f}% pass rate")


if __name__ == "__main__":
    asyncio.run(main())
