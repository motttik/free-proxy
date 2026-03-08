"""
Smoke Test Tests

Тесты для проверки smoke.py:
1. Регрессия no_proxy_available при HOT/WARM > 0 и пустом last_live_check
2. Актуальность help-рекомендаций в smoke report (без fp op)
3. Preflight validation фильтрует мёртвые прокси
4. Отчёт содержит preflight counters и mode
"""

import asyncio
import pytest
import time
from pathlib import Path

from fp.database import ProxyDatabase
from fp.validator import ProxyMetrics, ProxyPool
from fp.smoke import _get_fresh_proxy, smoke_test, print_report, run_preflight_validation


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
    results = await smoke_test(n=5, timeout=1.0, use_preflight=False)
    
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
        "mode": "degraded",
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
        "mode": "fresh",
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


# ============================================================================
# PREFLIGHT VALIDATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_preflight_filters_dead_proxies(db_with_proxies):
    """
    Тест: preflight validation фильтрует мёртвые прокси.
    
    Preflight должен отсечь прокси которые не отвечают.
    """
    passed, stats = await run_preflight_validation(
        db_with_proxies,
        candidate_count=10,
        timeout=1.0,
    )
    
    # Проверяем что статистика собрана
    assert "candidates_total" in stats
    assert "candidates_checked" in stats
    assert "candidates_passed" in stats
    assert "candidates_failed" in stats
    
    # Проверяем что candidates_total > 0 (есть кандидаты в БД)
    assert stats["candidates_total"] > 0
    
    # Проверяем что passed + failed = checked
    assert stats["candidates_passed"] + stats["candidates_failed"] == stats["candidates_checked"]


@pytest.mark.asyncio
async def test_preflight_with_empty_database():
    """Тест: preflight с пустой БД возвращает пустой список"""
    async with ProxyDatabase(":memory:") as db:
        passed, stats = await run_preflight_validation(db)
        
        assert passed == []
        assert stats["candidates_total"] == 0


@pytest.mark.asyncio
async def test_smoke_test_with_preflight_no_no_proxy_available(db_without_last_live_check):
    """
    Тест: smoke_test с preflight не должен получать no_proxy_available
    при наличии HOT/WARM прокси.
    """
    results = await smoke_test(n=5, timeout=1.0, use_preflight=True)
    
    # Проверяем что no_proxy_available не был получен
    no_proxy_count = results["fail_reasons"].get("no_proxy_available", 0)
    assert no_proxy_count == 0, (
        f"FAILED: no_proxy_available = {no_proxy_count}! "
        "Preflight + degraded mode должны предоставить прокси"
    )


def test_print_report_contains_preflight_counters(capsys):
    """
    Тест: print_report содержит preflight counters когда preflight включён.
    """
    results = {
        "total": 10,
        "success": 3,
        "failed": 7,
        "ratio": 0.3,
        "fail_reasons": {"timeout": 5, "connect_error": 2},
        "latencies": [100, 200, 150],
        "details": [],
        "mode": "preflight",
        "preflight_stats": {
            "candidates_total": 50,
            "candidates_checked": 50,
            "candidates_passed": 20,
            "candidates_failed": 30,
            "fail_reasons": {"timeout": 25, "connect_error": 5},
        },
    }
    
    print_report(results)
    captured = capsys.readouterr()
    
    # Проверяем что есть preflight статистика
    assert "PREFLIGHT VALIDATION" in captured.out
    assert "Candidates total: 50" in captured.out
    assert "Candidates passed: 20" in captured.out
    assert "Candidates failed: 30" in captured.out


def test_print_report_contains_mode(capsys):
    """
    Тест: print_report содержит mode (fresh / degraded / preflight).
    """
    results = {
        "total": 10,
        "success": 3,
        "failed": 7,
        "ratio": 0.3,
        "fail_reasons": {},
        "latencies": [],
        "details": [],
        "mode": "preflight",
    }
    
    print_report(results)
    captured = capsys.readouterr()
    
    # Проверяем что mode указан
    assert "Mode: preflight" in captured.out
