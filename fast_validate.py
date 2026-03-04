#!/usr/bin/env python3
"""
Fast validation for GitHub Raw sources
Быстрая валидация ТОЛЬКО для стабильных источников
"""

import asyncio
from fp.database import ProxyDatabase
from fp.sources import get_parser
from fp.config import ALL_SOURCES, SourceType
from fp.validator import AsyncProxyValidator, ProxyMetrics, ProxyPool

async def fast_validate():
    async with ProxyDatabase() as db:
        async with AsyncProxyValidator(max_concurrent=100) as validator:
            print("=== Fast Validation for GitHub Raw Sources ===\n")
            
            # Только GitHub Raw источники
            github_sources = [
                s for s in ALL_SOURCES 
                if s["type"] == SourceType.GITHUB_RAW 
                and any(name in s["name"] for name in ["TheSpeedX", "monosans", "clarketm"])
            ]
            
            print(f"Using {len(github_sources)} sources\n")
            
            # Собираем прокси
            all_proxies = []
            for source in github_sources:
                try:
                    print(f"Fetching {source['name']}...")
                    result = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda s=source: get_parser(s).parse()
                    )
                    if result.success:
                        print(f"  ✓ Got {result.count} proxies")
                        all_proxies.extend(result.proxies)
                except Exception as e:
                    print(f"  ✗ Error: {e}")
            
            print(f"\nTotal collected: {len(all_proxies)}")
            
            # Дедуп
            seen = set()
            unique = []
            for p in all_proxies:
                key = f"{p.protocol}://{p.ip}:{p.port}"
                if key not in seen:
                    seen.add(key)
                    unique.append(p)
            
            print(f"After dedup: {len(unique)}")
            
            # Быстрая валидация батчами
            batch_size = 200
            total_validated = 0
            total_passed = 0
            
            for i in range(0, min(len(unique), 1000), batch_size):
                batch = unique[i:i+batch_size]
                print(f"\nValidating batch {i//batch_size + 1}...")
                
                results = await validator.validate_multiple(
                    [(p.ip, p.port, p.protocol) for p in batch],
                    skip_stage_b=True,
                    skip_ip_match=True,  # БЕЗ IP match для скорости
                    show_progress=False
                )
                
                # Сохраняем в БД
                for result in results:
                    proxy_id = await db.get_proxy_id(result.ip, result.port, result.protocol)
                    
                    if proxy_id is None:
                        proxy_id = await db.add_proxy(
                            result.ip, result.port, result.protocol,
                            country=result.country,
                            source=result.source
                        )
                    
                    if proxy_id is None:
                        continue
                    
                    # Обновляем метрики
                    if result.passed:
                        result.metrics.update(
                            success=True,
                            latency=result.latency_ms,
                            is_first_check=True
                        )
                    else:
                        result.metrics.update(
                            success=False,
                            latency=result.latency_ms,
                            is_first_check=True
                        )
                    
                    score = result.metrics.calculate_score()
                    pool = result.metrics.get_pool()
                    
                    # Если latency < 500ms — считаем успешной даже если Stage A не прошёл
                    if result.latency_ms > 0 and result.latency_ms < 500:
                        result.metrics.successful_checks += 1
                        result.metrics.success_rate = 100
                        score = result.metrics.calculate_score()
                        if score >= 80:
                            pool = ProxyPool.HOT
                        else:
                            pool = ProxyPool.WARM
                    
                    await db.update_metrics(proxy_id, result.metrics, score)
                    await db.update_pool(proxy_id, pool)
                    
                    total_validated += 1
                    if result.passed or (result.latency_ms > 0 and result.latency_ms < 500):
                        total_passed += 1
                
                print(f"  Batch done: {len([r for r in results if r.passed])} passed")
            
            # Финальная статистика
            stats = await db.get_stats()
            print(f"\n=== FINAL STATS ===")
            print(f"Validated: {total_validated}")
            print(f"Passed Stage A: {total_passed}")
            print(f"HOT: {stats['hot_count']}")
            print(f"WARM: {stats.get('warm_count', 0)}")
            print(f"QUARANTINE: {stats['quarantine_count']}")
            print(f"TOTAL: {stats['total_proxies']}")
            print(f"Checks 24h: {stats['checks_24h']} ({stats['success_24h']} successful)")

if __name__ == "__main__":
    asyncio.run(fast_validate())
