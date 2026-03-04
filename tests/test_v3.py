"""
Tests for Free Proxy v3.0

Tests for:
- AsyncProxyValidator (2-stage validation)
- ProxyMetrics (score calculation)
- ProxyDatabase (SQLite storage)
- ProxyManager (full cycle)
"""

import asyncio
import pytest
import time

from fp.validator import (
    AsyncProxyValidator,
    ProxyMetrics,
    ProxyPool,
    ProxyValidationResult,
    ValidationStage,
)
from fp.database import ProxyDatabase
from fp.manager import ProxyManager


# =============================================================================
# ProxyMetrics Tests
# =============================================================================

class TestProxyMetrics:
    """Тесты метрик прокси"""
    
    def test_default_metrics(self):
        metrics = ProxyMetrics()
        assert metrics.uptime == 100.0
        assert metrics.success_rate == 100.0
        assert metrics.ban_rate == 0.0
        assert metrics.total_checks == 0
    
    def test_score_calculation_default(self):
        metrics = ProxyMetrics()
        score = metrics.calculate_score()
        assert score == 85.0  # Default: 100 uptime, 100 latency score, 100 success, 0 ban
    
    def test_score_after_update(self):
        metrics = ProxyMetrics()
        
        # 5 успешных проверок
        for _ in range(5):
            metrics.update(success=True, latency=100, status_code=200)
        
        score = metrics.calculate_score()
        assert 70 <= score <= 100  # Должен быть высоким
    
    def test_score_after_failures(self):
        metrics = ProxyMetrics()
        
        # 5 неудачных проверок
        for _ in range(5):
            metrics.update(success=False, latency=5000, status_code=None)
        
        score = metrics.calculate_score()
        assert score < 50  # Должен быть низким
    
    def test_ban_rate_update(self):
        metrics = ProxyMetrics()
        
        # 403 ошибки
        for _ in range(3):
            metrics.update(success=False, latency=100, status_code=403)
        
        assert metrics.ban_rate > 0
        assert metrics.ban_rate <= 100
    
    def test_pool_assignment_hot(self):
        metrics = ProxyMetrics()
        metrics.update(success=True, latency=50, status_code=200)
        
        pool = metrics.get_pool()
        assert pool == ProxyPool.HOT  # score >= 80
    
    def test_pool_assignment_quarantine(self):
        metrics = ProxyMetrics()
        
        # Много неудач
        for _ in range(10):
            metrics.update(success=False, latency=10000, status_code=None)
        
        pool = metrics.get_pool()
        assert pool == ProxyPool.QUARANTINE  # score < 50


# =============================================================================
# AsyncProxyValidator Tests
# =============================================================================

class TestAsyncProxyValidator:
    """Тесты валидатора"""
    
    @pytest.mark.asyncio
    async def test_validator_context_manager(self):
        async with AsyncProxyValidator(max_concurrent=10) as validator:
            assert validator._client is not None
    
    @pytest.mark.asyncio
    async def test_stage_a_timeout(self):
        """Stage A должен таймаутиться на нерабочей прокси"""
        async with AsyncProxyValidator(max_concurrent=5) as validator:
            result = await validator.validate_stage_a("1.2.3.4", 1, "http")
            
            assert result.stage == ValidationStage.STAGE_A
            assert not result.passed
            assert "error" in result.error.lower() or "timeout" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_invalid_port(self):
        """Невалидный порт должен возвращать ошибку"""
        async with AsyncProxyValidator(max_concurrent=5) as validator:
            result = await validator.validate_stage_a("8.219.97.248", 99999, "http")
            
            assert not result.passed


# =============================================================================
# ProxyDatabase Tests
# =============================================================================

class TestProxyDatabase:
    """Тесты базы данных"""
    
    @pytest.mark.asyncio
    async def test_db_context_manager(self, tmp_path):
        db_path = tmp_path / "test.db"
        async with ProxyDatabase(str(db_path)) as db:
            assert db._conn is not None
    
    @pytest.mark.asyncio
    async def test_add_proxy(self, tmp_path):
        db_path = tmp_path / "test.db"
        async with ProxyDatabase(str(db_path)) as db:
            proxy_id = await db.add_proxy("8.219.97.248", 80, "http", "ID")
            assert proxy_id > 0
    
    @pytest.mark.asyncio
    async def test_add_duplicate_proxy(self, tmp_path):
        db_path = tmp_path / "test.db"
        async with ProxyDatabase(str(db_path)) as db:
            # Первый раз
            proxy_id1 = await db.add_proxy("8.219.97.248", 80, "http", "ID")
            assert proxy_id1 > 0
            
            # Второй раз (должен вернуть -1)
            proxy_id2 = await db.add_proxy("8.219.97.248", 80, "http", "ID")
            assert proxy_id2 == -1
    
    @pytest.mark.asyncio
    async def test_update_metrics(self, tmp_path):
        db_path = tmp_path / "test.db"
        async with ProxyDatabase(str(db_path)) as db:
            proxy_id = await db.add_proxy("8.219.97.248", 80, "http", "ID")
            
            metrics = ProxyMetrics()
            metrics.update(success=True, latency=100, status_code=200)
            
            score = metrics.calculate_score()
            await db.update_metrics(proxy_id, metrics, score)
    
    @pytest.mark.asyncio
    async def test_get_proxy_by_pool(self, tmp_path):
        db_path = tmp_path / "test.db"
        async with ProxyDatabase(str(db_path)) as db:
            # Добавляем прокси
            proxy_id = await db.add_proxy("8.219.97.248", 80, "http", "ID")
            
            # Получаем из warm (по умолчанию)
            proxies = await db.get_proxy_by_pool(ProxyPool.WARM)
            assert len(proxies) > 0
            assert proxies[0]["ip"] == "8.219.97.248"
    
    @pytest.mark.asyncio
    async def test_banlist(self, tmp_path):
        db_path = tmp_path / "test.db"
        async with ProxyDatabase(str(db_path)) as db:
            # Добавляем в бан-лист
            await db.add_to_banlist("1.2.3.4", reason="test")
            
            # Проверяем
            assert await db.is_banned("1.2.3.4")
            assert not await db.is_banned("8.219.97.248")
    
    @pytest.mark.asyncio
    async def test_get_stats(self, tmp_path):
        db_path = tmp_path / "test.db"
        async with ProxyDatabase(str(db_path)) as db:
            # Добавляем прокси
            await db.add_proxy("8.219.97.248", 80, "http", "ID")
            
            stats = await db.get_stats()
            
            assert stats["total_proxies"] == 1
            assert "warm_count" in stats
            assert "avg_score" in stats


# =============================================================================
# ProxyManager Tests
# =============================================================================

class TestProxyManager:
    """Тесты менеджера"""
    
    @pytest.mark.asyncio
    async def test_manager_context_manager(self, tmp_path):
        db_path = tmp_path / "test.db"
        async with ProxyManager(db_path=str(db_path)) as manager:
            assert manager._db is not None
            assert manager._validator is not None
    
    @pytest.mark.asyncio
    async def test_collect_and_validate(self, tmp_path):
        db_path = tmp_path / "test.db"
        async with ProxyManager(db_path=str(db_path)) as manager:
            # Тестовые прокси (рабочие и нет)
            proxies = [
                ("8.219.97.248", 80, "http"),  # Может работать
                ("1.2.3.4", 1, "http"),  # Точно не работает
            ]
            
            report = await manager.collect_and_validate(proxies, skip_stage_b=True)
            
            assert report["total"] == 2
            assert "passed_a" in report
            assert "failed" in report
            assert "errors" in report
    
    @pytest.mark.asyncio
    async def test_get_proxy(self, tmp_path):
        db_path = tmp_path / "test.db"
        async with ProxyManager(db_path=str(db_path)) as manager:
            # Добавляем прокси
            proxies = [("8.219.97.248", 80, "http")]
            await manager.collect_and_validate(proxies, skip_stage_b=True)
            
            # Получаем
            proxy = await manager.get_proxy(min_score=0)  # Любой
            
            # Может быть None если прокси не прошла
            # assert proxy is not None  # Не гарантируется
    
    @pytest.mark.asyncio
    async def test_get_stats(self, tmp_path):
        db_path = tmp_path / "test.db"
        async with ProxyManager(db_path=str(db_path)) as manager:
            stats = await manager.get_stats()
            
            assert "total_proxies" in stats
            assert "hot_count" in stats
            assert "warm_count" in stats
            assert "quarantine_count" in stats


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Интеграционные тесты"""
    
    @pytest.mark.asyncio
    async def test_full_cycle(self, tmp_path):
        """Полный цикл: collect → validate → score → get"""
        db_path = tmp_path / "test.db"
        
        async with ProxyManager(db_path=str(db_path)) as manager:
            # 1. Collect & Validate
            proxies = [
                ("8.219.97.248", 80, "http"),
                ("1.2.3.4", 1, "http"),
            ]
            
            report = await manager.collect_and_validate(proxies, skip_stage_b=True)
            
            # 2. Check report
            assert report["total"] == 2
            
            # 3. Get stats
            stats = await manager.get_stats()
            assert stats["total_proxies"] >= 1
            
            # 4. Try to get proxy
            proxy = await manager.get_proxy(min_score=0)
            # Proxy may or may not be available depending on validation results


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
