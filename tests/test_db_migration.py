"""
Regression Tests for Database Migration

Тесты для проверки backward-compatible миграции:
- Старая БД без last_live_check
- Миграция добавляет колонки
- Индексы создаются только после миграции
"""

import asyncio
import pytest
import tempfile
import os
import aiosqlite
from pathlib import Path

from fp.database import ProxyDatabase


class TestDatabaseMigration:
    """Тесты миграции БД"""
    
    @pytest.mark.asyncio
    async def test_old_database_without_last_live_check(self):
        """
        Сценарий: старая БД без last_live_check
        Ожидание: инициализация проходит без падения
        """
        # Создаём временную БД
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        try:
            # Создаём "старую" БД без новых колонок
            async with aiosqlite.connect(db_path) as conn:
                await conn.execute("""
                    CREATE TABLE proxies (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ip TEXT NOT NULL,
                        port INTEGER NOT NULL,
                        protocol TEXT NOT NULL DEFAULT 'http',
                        country TEXT,
                        source TEXT,
                        pool TEXT DEFAULT 'warm',
                        created_at REAL DEFAULT (strftime('%s', 'now')),
                        updated_at REAL DEFAULT (strftime('%s', 'now')),
                        UNIQUE(ip, port, protocol)
                    )
                """)
                await conn.commit()
            
            # Проверяем что last_live_check отсутствует
            async with aiosqlite.connect(db_path) as conn:
                cursor = await conn.execute("PRAGMA table_info(proxies)")
                columns = [row[1] for row in await cursor.fetchall()]
                assert "last_live_check" not in columns
            
            # Инициализируем ProxyDatabase — должно работать без падения
            async with ProxyDatabase(db_path) as db:
                # Проверяем что миграция добавила колонки
                assert await db._column_exists("proxies", "last_live_check")
                assert await db._column_exists("proxies", "last_check")
                assert await db._column_exists("proxies", "fail_streak")
                
                # Проверяем что индекс создан
                cursor = await db._conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_proxy_last_live_check'"
                )
                index = await cursor.fetchone()
                assert index is not None
        
        finally:
            # Cleanup
            if os.path.exists(db_path):
                os.unlink(db_path)
    
    @pytest.mark.asyncio
    async def test_column_exists_helper(self):
        """Тест helper функции column_exists"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        try:
            async with ProxyDatabase(db_path) as db:
                # Проверяем существующие колонки
                assert await db._column_exists("proxies", "ip")
                assert await db._column_exists("proxies", "port")
                
                # Проверяем несуществующие колонки
                assert not await db._column_exists("proxies", "nonexistent_column")
        
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)
    
    @pytest.mark.asyncio
    async def test_migration_order(self):
        """
        Тест порядка миграции:
        1. Сначала миграции (добавление колонок)
        2. Потом таблицы/индексы
        """
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        try:
            # Создаём "старую" БД
            async with aiosqlite.connect(db_path) as conn:
                await conn.execute("""
                    CREATE TABLE proxies (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ip TEXT NOT NULL,
                        port INTEGER NOT NULL,
                        protocol TEXT NOT NULL DEFAULT 'http',
                        pool TEXT DEFAULT 'warm'
                    )
                """)
                await conn.commit()
            
            # Инициализация должна работать
            async with ProxyDatabase(db_path) as db:
                # Миграция должна добавить колонки
                assert await db._column_exists("proxies", "last_live_check")
                
                # Индекс должен быть создан
                cursor = await db._conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_proxy_last_live_check'"
                )
                index = await cursor.fetchone()
                assert index is not None
        
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
