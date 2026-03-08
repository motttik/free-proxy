#!/usr/bin/env python3
"""Quick rebuild of proxy pools based on score"""

import asyncio
import time
from fp.database import ProxyDatabase

async def rebuild():
    async with ProxyDatabase() as db:
        # Получаем все прокси
        stats = await db.get_stats()
        print(f"Before: HOT={stats['hot_count']}, WARM={stats.get('warm_count', 0)}, Q={stats['quarantine_count']}")

        # Получаем прокси с высоким score из карантина
        cursor = await db._conn.execute("""
            SELECT p.id, p.ip, p.port, p.protocol, m.score
            FROM proxies p
            JOIN metrics m ON p.id = m.proxy_id
            WHERE p.pool = 'quarantine' AND m.score >= 50
            LIMIT 500
        """)
        rows = await cursor.fetchall()

        print(f"Found {len(rows)} proxies with score >= 50")

        # Обновляем пулы
        hot_count = 0
        warm_count = 0
        now = int(time.time())
        for row in rows:
            proxy_id, ip, port, protocol, score = row
            if score >= 80:
                await db.update_pool(proxy_id, 'hot')
                # Проставляем last_live_check при обновлении пула
                await db._conn.execute("""
                    UPDATE proxies SET last_live_check = ?, last_check = ? WHERE id = ?
                """, (now, now, proxy_id))
                hot_count += 1
            elif score >= 50:
                await db.update_pool(proxy_id, 'warm')
                # Проставляем last_live_check при обновлении пула
                await db._conn.execute("""
                    UPDATE proxies SET last_live_check = ?, last_check = ? WHERE id = ?
                """, (now, now, proxy_id))
                warm_count += 1

        await db._conn.commit()
        print(f"Upgraded: HOT={hot_count}, WARM={warm_count}")

        # Финальная статистика
        stats = await db.get_stats()
        print(f"After: HOT={stats['hot_count']}, WARM={stats.get('warm_count', 0)}, Q={stats['quarantine_count']}")

if __name__ == "__main__":
    asyncio.run(rebuild())
