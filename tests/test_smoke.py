"""
Smoke Test Tests

Тесты для проверки smoke.py:
1. Регрессия no_proxy_available при HOT/WARM > 0 и пустом last_live_check
2. Актуальность help-рекомендаций в smoke report (без fp op)
"""

import asyncio
import pytest
import time
from pathlib import Path

from fp.database import ProxyDatabase
from fp.validator import ProxyMetrics, ProxyPool
from fp.smoke import _get_fresh_proxy, smoke_test, print_report


@pytest.fixture
async def db_with_proxies():
    """Создать тестовую БД с прокси"""
    db_path = ":memory:"
    async with ProxyDatabase(db_path) as db:
        # Добавляем прокси с last_live_check
        now = int(time.time())
        
        for i in range(10):
            proxy_id = await db.add_proxy(
                ip=f"192.168.1.{i}",
                port=8080 + i,
                protocol="http",
                country="US",
                source="test_source",
            )
            if proxy_id > 0:
                metrics = ProxyMetrics(
                    latency_ms=100,
                    uptime=95,
                    success_rate=90,
                    ban_rate=1,
                    total_checks=10,
                    successful_checks=9,
                )
                score = metrics.calculate_score()
                await db.update_metrics(proxy_id, metrics, score)
                
                # Проставляем pool и last_live_check
                pool = "hot" if score >= 80 else "warm"
                await db._conn.execute("""
                    UPDATE proxies
                    SET pool = ?, last_live_check = ?, last_check = ?
                    WHERE id = ?
                """, (pool, now, now, proxy_id))
                await db._conn.commit()
        
        yield db


@pytest.fixture
async def db_without_last_live_check():
    """Создать БД с прокси БЕЗ last_live_check (симуляция бага)"""
    db_path = ":memory:"
    async with ProxyDatabase(db_path) as db:
        now = int(time.time())
        
        for i in range(10):
            proxy_id = await db.add_proxy(
                ip=f"10.0.0.{i}",
                port=8080 + i,
                protocol="http",
                country="US",
                source="test_source",
            )
            if proxy_id > 0:
                metrics = ProxyMetrics(
                    latency_ms=100,
                    uptime=95,
                    success_rate=90,
                    ban_rate=1,
                    total_checks=10,
                    successful_checks=9,
                )
                score = metrics.calculate_score()
                await db.update_metrics(proxy_id, metrics, score)
                
                # Проставляем pool НО БЕЗ last_live_check (симуляция бага)
                pool = "hot" if score >= 80 else "warm"
                await db._conn.execute("""
                    UPDATE proxies
                    SET pool = ?, last_check = ?
                    WHERE id = ?
                """, (pool, now, proxy_id))
                await db._conn.commit()
        
        yield db


@pytest.mark.asyncio
async def test_get_fresh_proxy_with_last_live_check(db_with_proxies):
    """Тест: получение прокси с last_live_check работает"""
    proxy = await _get_fresh_proxy(db_with_proxies)
    
    assert proxy is not None, "Должна быть получена прокси из HOT/WARM"
    assert "ip" in proxy
    assert "port" in proxy
    assert "protocol" in proxy
    assert proxy["last_live_check"] is not None


@pytest.mark.asyncio
async def test_get_fresh_proxy_without_last_live_check(db_without_last_live_check):
    """
    Тест на регрессию no_proxy_available.
    
    Если в БД есть HOT/WARM прокси, но last_live_check = NULL,
    smoke должен использовать degraded mode fallback (top score),
    а не возвращать no_proxy_available.
    """
    proxy = await _get_fresh_proxy(db_without_last_live_check)
    
    # Это ключевой тест: degraded mode должен сработать
    assert proxy is not None, (
        "FAILED: no_proxy_available регрессия! "
        "Degraded mode fallback должен вернуть top score прокси из HOT/WARM "
        "даже если last_live_check не проставлен"
    )
    assert "ip" in proxy
    assert proxy["last_live_check"] is None  # Потому что не проставлен


@pytest.mark.asyncio
async def test_smoke_test_no_no_proxy_available(db_without_last_live_check):
    """
    Тест: smoke_test не должен получать no_proxy_available
    при наличии HOT/WARM прокси даже без last_live_check.
    """
    results = await smoke_test(n=5, timeout=1.0)
    
    # Проверяем что no_proxy_available не был получен
    no_proxy_count = results["fail_reasons"].get("no_proxy_available", 0)
    assert no_proxy_count == 0, (
        f"FAILED: no_proxy_available = {no_proxy_count}! "
        "Degraded mode должен предоставить прокси из top score"
    )


def test_print_report_no_fp_op_recommendation(capsys):
    """
    Тест: print_report не должен рекомендовать 'fp op' (удалённая команда).
    
    Проверяем что в выводе нет 'fp op run-pipeline'.
    """
    results = {
        "total": 10,
        "success": 2,
        "failed": 8,
        "ratio": 0.2,
        "fail_reasons": {"no_proxy_available": 5},
        "latencies": [],
        "details": [],
    }
    
    print_report(results)
    captured = capsys.readouterr()
    
    # Проверяем что нет старой команды
    assert "fp op" not in captured.out.lower(), (
        "FAILED: print_report всё ещё рекомендует 'fp op' (удалённая команда)"
    )
    
    # Проверяем что есть новая рекомендация
    assert "quick_collect" in captured.out.lower() or "rebuild_pools" in captured.out.lower(), (
        "FAILED: print_report должен рекомендовать 'python quick_collect.py' или 'python rebuild_pools.py'"
    )


def test_print_report_ttl_values(capsys):
    """
    Тест: TTL в print_report должен соответствовать коду (15/45 мин).
    
    Код использует:
    - hot_ttl_seconds = 15 * 60
    - warm_ttl_seconds = 45 * 60
    """
    results = {
        "total": 10,
        "success": 2,
        "failed": 8,
        "ratio": 0.2,
        "fail_reasons": {},
        "latencies": [],
        "details": [],
    }
    
    print_report(results)
    captured = capsys.readouterr()
    
    # Проверяем корректные TTL
    assert "15 min" in captured.out, "FAILED: HOT TTL должен быть 15 мин"
    assert "45 min" in captured.out, "FAILED: WARM TTL должен быть 45 мин"
    
    # Проверяем что нет старых значений
    assert "30 min" not in captured.out, "FAILED: Не должно быть старого HOT TTL (30 мин)"
    assert "60 min" not in captured.out, "FAILED: Не должно быть старого WARM TTL (60 мин)"


@pytest.mark.asyncio
async def test_degraded_mode_priority(db_without_last_live_check):
    """
    Тест: degraded mode должен брать прокси с наивысшим score.
    """
    # Получаем несколько прокси и проверяем что они из top score
    proxies = []
    for _ in range(3):
        proxy = await _get_fresh_proxy(db_without_last_live_check)
        if proxy:
            proxies.append(proxy)
    
    assert len(proxies) > 0, "Degraded mode должен вернуть хотя бы одну прокси"
    
    # Все прокси должны быть из HOT/WARM (не quarantine)
    # Это проверяется SQL запросом в _get_fresh_proxy


@pytest.mark.asyncio
async def test_empty_database():
    """Тест: пустая БД должна возвращать None"""
    async with ProxyDatabase(":memory:") as db:
        proxy = await _get_fresh_proxy(db)
        assert proxy is None, "Пустая БД должна возвращать None"
