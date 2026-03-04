#!/usr/bin/env python3
"""
E2E Smoke Test

Проверка реальной работоспособности прокси:
1. Берёт N прокси через ProxyManager.get_proxy(use_quarantine=False)
2. Проверяет реальным GET к указанному URL через proxy
3. Считает success ratio + top fail reasons

Цель: success ratio >= 0.3
"""

import asyncio
import sys
import time
import aiohttp
from typing import Optional
from fp import ProxyManager


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
    results = {
        "total": n,
        "success": 0,
        "failed": 0,
        "ratio": 0.0,
        "fail_reasons": {},
        "latencies": [],
        "details": [],
    }
    
    async with ProxyManager() as manager:
        for i in range(n):
            proxy = await manager.get_proxy(use_quarantine=use_quarantine)
            
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


def print_report(results: dict) -> None:
    """Вывести отчёт"""
    print("\n=== SMOKE TEST REPORT ===\n")
    print(f"Total attempts: {results['total']}")
    print(f"Success: {results['success']}")
    print(f"Failed: {results['failed']}")
    print(f"Success Ratio: {results['ratio']:.2f}")
    
    if results["latencies"]:
        avg_latency = sum(results["latencies"]) / len(results["latencies"])
        print(f"Avg Latency: {avg_latency:.0f}ms")
    
    if results["fail_reasons"]:
        print("\nTop Fail Reasons:")
        sorted_reasons = sorted(
            results["fail_reasons"].items(),
            key=lambda x: x[1],
            reverse=True
        )
        for reason, count in sorted_reasons[:5]:
            print(f"  {reason}: {count}")
    
    print("\n=== RESULT ===")
    if results["ratio"] >= 0.3:
        print("✅ PASS (ratio >= 0.3)")
    else:
        print("❌ FAIL (ratio < 0.3)")
        print("\nRoot cause analysis:")
        if "connect_error" in results["fail_reasons"]:
            print("  - Most proxies are unreachable (connect_error)")
        if "timeout" in results["fail_reasons"]:
            print("  - Proxies timing out (too slow or dead)")
        if "ssl_error" in results["fail_reasons"]:
            print("  - SSL/TLS handshake failures")
        if "no_proxy_available" in results["fail_reasons"]:
            print("  - Not enough proxies in HOT/WARM pools")


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
