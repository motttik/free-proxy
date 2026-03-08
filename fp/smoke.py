"""
Smoke Test Module

E2E проверка реальной работоспособности прокси

v2.1: Preflight validation, improved scoring, adaptive timeout
"""

import asyncio
import sys
import time
from typing import Optional, Literal

import aiohttp


# ============================================================================
# CONFIGURATION
# ============================================================================

PREFLIGHT_CONFIG = {
    "enabled": True,
    "candidate_pool_size": 30,  # Сколько кандидатов брать для preflight
    "timeout": 3.0,  # Короткий timeout для preflight
    "test_url": "http://httpbin.org/ip",  # Легкий URL для preflight
    "max_concurrent": 10,  # Ограничить параллелизм для скорости
}

ADAPTIVE_TIMEOUT_CONFIG = {
    "phase1_timeout": 3.0,  # Первая фаза
    "phase2_timeout": 6.0,  # Вторая фаза для promising proxy
    "retry_on_timeout": True,
}


# ============================================================================
# CORE FUNCTIONS
# ============================================================================

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


async def preflight_check(
    proxy_url: str,
    test_url: str = "http://httpbin.org/ip",
    timeout: float = 2.5,
) -> tuple[bool, Optional[str], Optional[float]]:
    """
    Быстрая preflight проверка прокси

    Использует короткий timeout и легкий URL для отсечения заведомо мёртвых прокси.

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
                allow_redirects=False,
            ) as response:
                latency_ms = (time.perf_counter() - start) * 1000

                # Для preflight считаем успехом любой ответ 2xx/3xx
                if response.status < 400:
                    return True, None, latency_ms
                else:
                    return False, f"http_{response.status}", latency_ms

    except asyncio.TimeoutError:
        return False, "timeout", None
    except aiohttp.ClientConnectorError:
        return False, "connect_error", None
    except aiohttp.ClientSSLError:
        return False, "ssl_error", None
    except Exception:
        return False, "unknown", None


async def run_preflight_validation(
    db,
    candidate_count: int = 50,
    timeout: float = 2.5,
    test_url: str = "http://httpbin.org/ip",
    max_concurrent: int = 10,
) -> tuple[list[dict], dict]:
    """
    Preflight валидация кандидатов

    Берёт top кандидатов из HOT/WARM, быстро проверяет их и возвращает только живые.

    Returns:
        (список прошедших preflight, статистика)
    """
    stats = {
        "candidates_total": 0,
        "candidates_checked": 0,
        "candidates_passed": 0,
        "candidates_failed": 0,
        "fail_reasons": {},
    }

    # Получаем кандидатов
    cursor = await db._conn.execute("""
        SELECT p.ip, p.port, p.protocol, p.country, p.source,
               m.score, m.latency_ms, m.uptime, p.last_live_check, p.fail_streak
        FROM proxies p
        JOIN metrics m ON p.id = m.proxy_id
        WHERE p.pool IN ('hot', 'warm')
          AND (p.fail_streak < 3)
        ORDER BY m.score DESC, m.latency_ms ASC, p.last_live_check DESC
        LIMIT ?
    """, (candidate_count,))

    rows = await cursor.fetchall()
    stats["candidates_total"] = len(rows)

    if not rows:
        return [], stats

    # Semaphore для ограничения параллелизма
    semaphore = asyncio.Semaphore(max_concurrent)

    # Проверяем с ограничением параллелизма
    async def check_candidate(row) -> tuple[dict, bool, Optional[str]]:
        proxy_data = {
            "ip": row[0], "port": row[1], "protocol": row[2], "country": row[3],
            "source": row[4], "score": row[5], "latency_ms": row[6], "uptime": row[7],
            "last_live_check": row[8], "fail_streak": row[9]
        }
        proxy_url = f"{proxy_data['protocol']}://{proxy_data['ip']}:{proxy_data['port']}"
        async with semaphore:
            success, reason, _ = await preflight_check(proxy_url, test_url, timeout)
        return proxy_data, success, reason

    tasks = [check_candidate(row) for row in rows]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    passed = []
    for result in results:
        if isinstance(result, Exception):
            stats["candidates_failed"] += 1
            reason = "exception"
            stats["fail_reasons"][reason] = stats["fail_reasons"].get(reason, 0) + 1
        else:
            proxy_data, success, reason = result
            stats["candidates_checked"] += 1
            if success:
                passed.append(proxy_data)
                stats["candidates_passed"] += 1
            else:
                stats["candidates_failed"] += 1
                stats["fail_reasons"][reason] = stats["fail_reasons"].get(reason, 0) + 1

    return passed, stats


async def smoke_test(
    n: int = 10,
    test_url: str = "https://httpbin.org/ip",
    timeout: float = 10.0,
    use_quarantine: bool = False,
    use_preflight: bool = True,
    adaptive_timeout: bool = True,
) -> dict:
    """
    Smoke test для прокси с preflight validation и adaptive timeout

    Args:
        n: Количество прокси для проверки
        test_url: URL для проверки
        timeout: Базовый таймаут в секундах
        use_quarantine: Использовать ли quarantine прокси
        use_preflight: Использовать ли preflight валидацию
        adaptive_timeout: Использовать ли адаптивный timeout

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
        "preflight_stats": None,
        "mode": "fresh",  # fresh / degraded / preflight-degraded
    }

    async with ProxyDatabase() as db:
        # Preflight validation
        preflight_passed = []
        if use_preflight:
            preflight_passed, preflight_stats = await run_preflight_validation(
                db,
                candidate_count=PREFLIGHT_CONFIG["candidate_pool_size"],
                timeout=PREFLIGHT_CONFIG["timeout"],
                test_url=PREFLIGHT_CONFIG["test_url"],
                max_concurrent=PREFLIGHT_CONFIG.get("max_concurrent", 10),
            )
            results["preflight_stats"] = preflight_stats

            if preflight_passed:
                results["mode"] = "preflight"
            else:
                results["mode"] = "preflight-degraded"

        # Основной smoke test
        for i in range(n):
            # Получаем прокси: сначала из preflight, потом fallback
            if preflight_passed:
                proxy = preflight_passed[i % len(preflight_passed)]
            else:
                proxy = await _get_fresh_proxy(db, use_quarantine)
                if proxy:
                    results["mode"] = "degraded" if results["mode"] == "preflight-degraded" else "fresh"

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

            # Адаптивный timeout: фаза 1 + фаза 2 для timeout
            current_timeout = timeout
            success, reason, latency = await check_proxy_real(proxy_url, test_url, current_timeout)

            # Retry с увеличенным timeout если был timeout и включён adaptive
            if not success and reason == "timeout" and adaptive_timeout and ADAPTIVE_TIMEOUT_CONFIG["retry_on_timeout"]:
                retry_timeout = ADAPTIVE_TIMEOUT_CONFIG["phase2_timeout"]
                success, reason, latency = await check_proxy_real(proxy_url, test_url, retry_timeout)

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
    Получить свежую прокси с улучшенной фильтрацией

    Критерии (приоритет):
    1. HOT: last_live_check за последние 15 мин, fail_streak < 3
    2. WARM: last_live_check за последние 45 мин, fail_streak < 3
    3. HOT/WARM top score (degraded mode), fail_streak < 3
    4. Quarantine (если разрешено), fail_streak < 3

    Приоритет внутри пула:
    - Меньше fail_streak
    - Свежее last_live_check
    - Ниже latency_ms
    - Выше score
    """
    import random

    now = time.time()
    hot_ttl_seconds = 15 * 60  # 15 минут
    warm_ttl_seconds = 45 * 60  # 45 минут

    # Сначала HOT (свежие live-check)
    # Приоритет: fail_streak ASC, last_live_check DESC, latency_ms ASC, score DESC
    cursor = await db._conn.execute("""
        SELECT p.ip, p.port, p.protocol, p.country, p.source,
               m.score, m.latency_ms, m.uptime, p.last_live_check, p.fail_streak
        FROM proxies p
        JOIN metrics m ON p.id = m.proxy_id
        WHERE p.pool = 'hot'
          AND p.last_live_check IS NOT NULL
          AND (strftime('%s', 'now') - p.last_live_check) < ?
          AND (p.fail_streak < 3)
        ORDER BY p.fail_streak ASC, m.score DESC, p.last_live_check DESC, m.latency_ms ASC
        LIMIT 50
    """, (hot_ttl_seconds,))

    rows = await cursor.fetchall()
    if rows:
        # Берём топ-5 и случайно выбираем (баланс между лучшим и разнообразием)
        top_candidates = rows[:5]
        row = random.choice(top_candidates)
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
        ORDER BY p.fail_streak ASC, m.score DESC, p.last_live_check DESC, m.latency_ms ASC
        LIMIT 50
    """, (warm_ttl_seconds,))

    rows = await cursor.fetchall()
    if rows:
        top_candidates = rows[:5]
        row = random.choice(top_candidates)
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
            ORDER BY m.score DESC, p.fail_streak ASC
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
        ORDER BY m.score DESC, p.fail_streak ASC, m.latency_ms ASC
        LIMIT 50
    """)

    rows = await cursor.fetchall()
    if rows:
        top_candidates = rows[:5]
        row = random.choice(top_candidates)
        return {
            "ip": row[0], "port": row[1], "protocol": row[2], "country": row[3],
            "source": row[4], "score": row[5], "latency_ms": row[6], "uptime": row[7],
            "last_live_check": row[8], "fail_streak": row[9]
        }

    return None


def print_report(results: dict) -> None:
    """Вывести отчёт с полной телеметрией"""
    print("\n=== SMOKE TEST REPORT ===\n")
    print(f"Total attempts: {results['total']}")
    print(f"Success: {results['success']}")
    print(f"Failed: {results['failed']}")
    print(f"Success Ratio: {results['ratio']:.2f}")
    print(f"Mode: {results.get('mode', 'unknown')}")

    if results["latencies"]:
        avg_latency = sum(results["latencies"]) / len(results["latencies"])
        min_latency = min(results["latencies"])
        max_latency = max(results["latencies"])
        print(f"Avg Latency: {avg_latency:.0f}ms (min: {min_latency:.0f}ms, max: {max_latency:.0f}ms)")

    # Preflight статистика
    if results.get("preflight_stats"):
        ps = results["preflight_stats"]
        print("\n=== PREFLIGHT VALIDATION ===")
        print(f"  Candidates total: {ps.get('candidates_total', 0)}")
        print(f"  Candidates checked: {ps.get('candidates_checked', 0)}")
        print(f"  Candidates passed: {ps.get('candidates_passed', 0)}")
        print(f"  Candidates failed: {ps.get('candidates_failed', 0)}")
        if ps.get('fail_reasons'):
            print("  Preflight fail reasons:")
            for reason, count in ps['fail_reasons'].items():
                print(f"    {reason}: {count}")

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
            print("     → Or rebuild pools: python rebuild_pools.py")

        # Applied filters info
        print("\n=== APPLIED FILTERS ===")
        print("  - HOT pool: last_live_check < 15 min (TTL: 15 min)")
        print("  - WARM pool: last_live_check < 45 min (TTL: 45 min)")
        print("  - fail_streak < 3")
        print("  - Preflight: enabled (timeout 2.5s, httpbin.org/ip)")
        print("  - Adaptive timeout: enabled (3s → 6s retry)")
        print("  - Fallback: use top-score if no fresh proxies (degraded mode)")

    print("\n=== RESULT ===")
    if results["ratio"] >= 0.3:
        print("✅ PASS (ratio >= 0.3)")
    else:
        print("❌ FAIL (ratio < 0.3)")


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="E2E Smoke Test v2.1")
    parser.add_argument("--n", type=int, default=10, help="Number of proxies to test")
    parser.add_argument("--url", type=str, default="https://httpbin.org/ip", help="Test URL")
    parser.add_argument("--timeout", type=float, default=10.0, help="Timeout in seconds")
    parser.add_argument("--use-quarantine", action="store_true", help="Use quarantine proxies")
    parser.add_argument("--no-preflight", action="store_true", help="Disable preflight validation")
    parser.add_argument("--no-adaptive-timeout", action="store_true", help="Disable adaptive timeout")

    args = parser.parse_args()

    results = await smoke_test(
        n=args.n,
        test_url=args.url,
        timeout=args.timeout,
        use_quarantine=args.use_quarantine,
        use_preflight=not args.no_preflight,
        adaptive_timeout=not args.no_adaptive_timeout,
    )

    print_report(results)

    # Exit code
    sys.exit(0 if results["ratio"] >= 0.3 else 1)


if __name__ == "__main__":
    asyncio.run(main())
