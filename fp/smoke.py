"""
Smoke Test Module

E2E проверка реальной работоспособности прокси
"""

import asyncio
import sys
import time
from typing import Optional

import aiohttp


async def check_proxy_real(
    proxy_url: str,
    test_url: str = "https://httpbin.org/ip",
    timeout: float = 10.0,
) -> tuple[bool, Optional[str], Optional[float]]:
    """
    Реальная проверка прокси через запрос к тестовому URL
    
    Returns:
        (success, error_reason, latency_ms)
    """
    start = time.perf_counter()
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                test_url,
                proxy=proxy_url,
                timeout=aiohttp.ClientTimeout(total=timeout),
                ssl=False,
            ) as response:
                latency_ms = (time.perf_counter() - start) * 1000
                
                if response.status == 200:
                    data = await response.json()
                    if "origin" in data:
                        return True, None, latency_ms
                    else:
                        return False, "invalid_response", latency_ms
                else:
                    return False, f"http_{response.status}", latency_ms
                    
    except asyncio.TimeoutError:
        return False, "timeout", None
    except aiohttp.ClientConnectorError as e:
        return False, "connect_error", None
    except aiohttp.ClientSSLError as e:
        return False, "ssl_error", None
    except Exception as e:
        return False, "unknown", None


async def smoke_test(
    n: int = 10,
    test_url: str = "https://httpbin.org/ip",
    timeout: float = 10.0,
    use_quarantine: bool = False,
) -> dict:
    """
    Smoke test для прокси
    
    Args:
        n: Количество прокси для проверки
        test_url: URL для проверки
        timeout: Таймаут в секундах
        use_quarantine: Использовать ли quarantine прокси
    
    Returns:
        dict с результатами
    """
    from fp.database import ProxyDatabase
    
    results = {
        "total": n,
        "success": 0,
        "failed": 0,
        "ratio": 0.0,
        "fail_reasons": {},
        "latencies": [],
        "details": [],
    }
    
    async with ProxyDatabase() as db:
        for i in range(n):
            # Получаем свежую прокси с проверкой TTL и fail_streak
            proxy = await _get_fresh_proxy(db, use_quarantine)
            
            if not proxy:
                results["details"].append({
                    "attempt": i + 1,
                    "success": False,
                    "reason": "no_proxy_available",
                })
                results["failed"] += 1
                results["fail_reasons"]["no_proxy_available"] = \
                    results["fail_reasons"].get("no_proxy_available", 0) + 1
                continue
            
            proxy_url = f"{proxy['protocol']}://{proxy['ip']}:{proxy['port']}"
            success, reason, latency = await check_proxy_real(proxy_url, test_url, timeout)
            
            if success:
                results["success"] += 1
                results["latencies"].append(latency)
                results["details"].append({
                    "attempt": i + 1,
                    "proxy": proxy_url,
                    "success": True,
                    "latency_ms": round(latency, 2),
                })
            else:
                results["failed"] += 1
                results["fail_reasons"][reason] = \
                    results["fail_reasons"].get(reason, 0) + 1
                results["details"].append({
                    "attempt": i + 1,
                    "proxy": proxy_url,
                    "success": False,
                    "reason": reason,
                })
    
    results["ratio"] = results["success"] / n if n > 0 else 0.0
    
    return results


async def _get_fresh_proxy(db, use_quarantine: bool = False) -> dict | None:
    """
    Получить свежую прокси с проверкой TTL и fail_streak
    
    Критерии:
    - HOT: last_live_check за последние 30 мин
    - WARM: last_live_check за последние 60 мин
    - fail_streak < 3
    """
    import time
    import random
    
    now = time.time()
    hot_ttl_seconds = 30 * 60  # 30 минут
    warm_ttl_seconds = 60 * 60  # 60 минут
    
    # Сначала HOT (свежие live-check)
    cursor = await db._conn.execute("""
        SELECT p.ip, p.port, p.protocol, p.country, p.source,
               m.score, m.latency_ms, m.uptime, p.last_live_check, p.fail_streak
        FROM proxies p
        JOIN metrics m ON p.id = m.proxy_id
        WHERE p.pool = 'hot'
          AND p.last_live_check IS NOT NULL
          AND (strftime('%s', 'now') - p.last_live_check) < ?
          AND (p.fail_streak < 3)
        ORDER BY m.score DESC, p.last_live_check DESC
        LIMIT 50
    """, (hot_ttl_seconds,))
    
    rows = await cursor.fetchall()
    if rows:
        row = random.choice(rows)
        return {
            "ip": row[0], "port": row[1], "protocol": row[2], "country": row[3],
            "source": row[4], "score": row[5], "latency_ms": row[6], "uptime": row[7],
            "last_live_check": row[8], "fail_streak": row[9]
        }
    
    # Потом WARM (но с недавней проверкой)
    cursor = await db._conn.execute("""
        SELECT p.ip, p.port, p.protocol, p.country, p.source,
               m.score, m.latency_ms, m.uptime, p.last_live_check, p.fail_streak
        FROM proxies p
        JOIN metrics m ON p.id = m.proxy_id
        WHERE p.pool = 'warm'
          AND p.last_live_check IS NOT NULL
          AND (strftime('%s', 'now') - p.last_live_check) < ?
          AND (p.fail_streak < 3)
        ORDER BY m.score DESC, p.last_live_check DESC
        LIMIT 50
    """, (warm_ttl_seconds,))
    
    rows = await cursor.fetchall()
    if rows:
        row = random.choice(rows)
        return {
            "ip": row[0], "port": row[1], "protocol": row[2], "country": row[3],
            "source": row[4], "score": row[5], "latency_ms": row[6], "uptime": row[7],
            "last_live_check": row[8], "fail_streak": row[9]
        }
    
    # Quarantine (если разрешено)
    if use_quarantine:
        cursor = await db._conn.execute("""
            SELECT p.ip, p.port, p.protocol, p.country, p.source,
                   m.score, m.latency_ms, m.uptime, p.last_live_check, p.fail_streak
            FROM proxies p
            JOIN metrics m ON p.id = m.proxy_id
            WHERE p.pool = 'quarantine'
              AND (p.fail_streak < 3)
            ORDER BY m.score DESC, p.last_live_check DESC
            LIMIT 20
        """)

        rows = await cursor.fetchall()
        if rows:
            row = random.choice(rows)
            return {
                "ip": row[0], "port": row[1], "protocol": row[2], "country": row[3],
                "source": row[4], "score": row[5], "latency_ms": row[6], "uptime": row[7],
                "last_live_check": row[8], "fail_streak": row[9]
            }

    # FALLBACK: если нет fresh proxies, брать top score из HOT/WARM
    # Это нужно для degraded mode когда last_live_check не проставлен
    cursor = await db._conn.execute("""
        SELECT p.ip, p.port, p.protocol, p.country, p.source,
               m.score, m.latency_ms, m.uptime, p.last_live_check, p.fail_streak
        FROM proxies p
        JOIN metrics m ON p.id = m.proxy_id
        WHERE p.pool IN ('hot', 'warm')
          AND (p.fail_streak < 3)
        ORDER BY m.score DESC
        LIMIT 50
    """)

    rows = await cursor.fetchall()
    if rows:
        row = random.choice(rows)
        return {
            "ip": row[0], "port": row[1], "protocol": row[2], "country": row[3],
            "source": row[4], "score": row[5], "latency_ms": row[6], "uptime": row[7],
            "last_live_check": row[8], "fail_streak": row[9]
        }

    return None


def print_report(results: dict) -> None:
    """Вывести отчёт"""
    print("\n=== SMOKE TEST REPORT ===\n")
    print(f"Total attempts: {results['total']}")
    print(f"Success: {results['success']}")
    print(f"Failed: {results['failed']}")
    print(f"Success Ratio: {results['ratio']:.2f}")
    
    if results["latencies"]:
        avg_latency = sum(results["latencies"]) / len(results["latencies"])
        min_latency = min(results["latencies"])
        max_latency = max(results["latencies"])
        print(f"Avg Latency: {avg_latency:.0f}ms (min: {min_latency:.0f}ms, max: {max_latency:.0f}ms)")
    
    if results["fail_reasons"]:
        print("\nTop Fail Reasons:")
        sorted_reasons = sorted(
            results["fail_reasons"].items(),
            key=lambda x: x[1],
            reverse=True
        )
        for reason, count in sorted_reasons[:5]:
            print(f"  {reason}: {count}")
    
    # Root cause analysis если ratio < 0.3
    if results["ratio"] < 0.3:
        print("\n=== ROOT CAUSE ANALYSIS ===")
        
        if results["fail_reasons"].get("timeout", 0) > results["failed"] * 0.5:
            print("  ⚠️  Most proxies are timing out (>50% timeout)")
            print("     → Proxies are too slow or dead")
            print("     → Recommendation: increase timeout or refresh proxy pool")
        
        if results["fail_reasons"].get("connect_error", 0) > results["failed"] * 0.3:
            print("  ⚠️  Many connection errors (>30%)")
            print("     → Proxies are unreachable")
            print("     → Recommendation: rebuild HOT pool with live-check")
        
        if results["fail_reasons"].get("ssl_error", 0) > results["failed"] * 0.2:
            print("  ⚠️  SSL/TLS handshake failures (>20%)")
            print("     → Proxies don't support HTTPS")
            print("     → Recommendation: filter for HTTPS-only proxies")
        
        if results["fail_reasons"].get("no_proxy_available", 0) > 0:
            print("  ⚠️  Not enough proxies in HOT/WARM pools")
            print("     → Recommendation: run 'python quick_collect.py' to refresh")
            print("     → Or use fallback mode: smoke test will use top-score proxies")

        # Applied filters info
        print("\n=== APPLIED FILTERS ===")
        print("  - HOT pool: last_live_check < 30 min (TTL: 30 min)")
        print("  - WARM pool: last_live_check < 60 min (TTL: 60 min)")
        print("  - fail_streak < 3")
        print("  - Fallback: use top-score if no fresh proxies")
    
    print("\n=== RESULT ===")
    if results["ratio"] >= 0.3:
        print("✅ PASS (ratio >= 0.3)")
    else:
        print("❌ FAIL (ratio < 0.3)")


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="E2E Smoke Test")
    parser.add_argument("--n", type=int, default=10, help="Number of proxies to test")
    parser.add_argument("--url", type=str, default="https://httpbin.org/ip", help="Test URL")
    parser.add_argument("--timeout", type=float, default=10.0, help="Timeout in seconds")
    parser.add_argument("--use-quarantine", action="store_true", help="Use quarantine proxies")
    
    args = parser.parse_args()
    
    results = await smoke_test(
        n=args.n,
        test_url=args.url,
        timeout=args.timeout,
        use_quarantine=args.use_quarantine,
    )
    
    print_report(results)
    
    # Exit code
    sys.exit(0 if results["ratio"] >= 0.3 else 1)


if __name__ == "__main__":
    asyncio.run(main())
