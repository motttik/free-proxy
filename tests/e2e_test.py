#!/usr/bin/env python3
"""
E2E Proxy Test

Проверка реальной работоспособности прокси:
1. Берёт 10 прокси через ProxyManager.get_proxy()
2. Проверяет реальным GET к https://httpbin.org/ip через proxy
3. Считает success ratio

Цель: success ratio >= 0.4
"""

import asyncio
import aiohttp
from fp import ProxyManager


async def check_proxy_real(proxy: dict, timeout: float = 10.0) -> bool:
    """
    Реальная проверка прокси через запрос к httpbin.org/ip
    
    Returns:
        True если прокси работает
    """
    proxy_url = f"{proxy['protocol']}://{proxy['ip']}:{proxy['port']}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://httpbin.org/ip",
                proxy=proxy_url,
                timeout=aiohttp.ClientTimeout(total=timeout),
                ssl=False,
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return "origin" in data
    except Exception as e:
        return False
    
    return False


async def main():
    print("=== E2E Proxy Test ===\n")
    print("Берём 10 прокси через ProxyManager.get_proxy()...")
    print("Проверяем реальным GET к https://httpbin.org/ip\n")
    
    async with ProxyManager() as manager:
        success = 0
        failed = 0
        
        for i in range(10):
            proxy = await manager.get_proxy(use_quarantine=False)
            
            if not proxy:
                print(f"{i+1}. ❌ No proxy available")
                failed += 1
                continue
            
            # Реальная проверка
            is_working = await check_proxy_real(proxy)
            
            if is_working:
                print(f"{i+1}. ✓ {proxy['protocol']}://{proxy['ip']}:{proxy['port']} (score: {proxy['score']}, latency: {proxy['latency_ms']:.0f}ms)")
                success += 1
            else:
                print(f"{i+1}. ✗ {proxy['protocol']}://{proxy['ip']}:{proxy['port']} (FAILED)")
                failed += 1
        
        # Итоги
        ratio = success / 10
        
        print(f"\n=== RESULTS ===")
        print(f"Success: {success}/10")
        print(f"Failed: {failed}/10")
        print(f"Success Ratio: {ratio:.2f}")
        
        if ratio >= 0.4:
            print(f"\n✅ PASS (ratio >= 0.4)")
        else:
            print(f"\n❌ FAIL (ratio < 0.4)")
        
        return ratio


if __name__ == "__main__":
    ratio = asyncio.run(main())
    exit(0 if ratio >= 0.4 else 1)
