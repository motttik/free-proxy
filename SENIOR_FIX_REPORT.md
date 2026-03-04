# 🔧 Free Proxy v3.2 — Senior Engineer Fix Report

**Дата:** 2026-03-04  
**Цель:** Довести проект до реально рабочего состояния

---

## 1) Summary (5-10 буллетов)

✅ **Health Contract введён:**
- `last_live_check` — timestamp последней успешной live-проверки
- `last_check` — timestamp любой проверки
- `fail_streak` — счётчик последовательных неудач

✅ **TTL для пулов:**
- HOT: 15 минут (health.hot_ttl_minutes)
- WARM: 45 минут (health.warm_ttl_minutes)

✅ **Ужесточены критерии HOT:**
- score >= 80 (health.hot_min_score)
- latency <= 1000ms (health.hot_max_latency_ms)
- last_live_check за последние 15 минут

✅ **Auto-downgrade:**
- fail_streak >= 3 → downgrade HOT→WARM/QUARANTINE
- TTL истёк → downgrade

✅ **Selection hygiene:**
- Rotation: не повторять последнюю выданную прокси
- Diversity: макс. 2 прокси из одной /24 подсети
- Exclude recent fail: исключать прокси с fail за последние 10 минут

✅ **Миграция БД:**
- Добавлены поля: `last_live_check`, `last_check`, `fail_streak`
- Автоматическая безопасная миграция при старте

---

## 2) Changed Files

| Файл | Изменения |
|------|-----------|
| `fp/config.py` | Полностью переписан — централизованная конфигурация (HealthConfig, ValidationConfig, SelectionConfig) |
| `fp/database.py` | +3 поля в proxies, миграция, методы: `update_health_on_success()`, `update_health_on_fail()`, `is_proxy_fresh()` |
| `fp/manager.py` | `get_proxy()` с rotation/diversity/freshness, `_get_last_issued_proxy()`, `_record_proxy_issued()` |

---

## 3) Migration Notes

**Автоматическая миграция при старте:**

```python
async def _run_migrations(self) -> None:
    # Миграция 1: avg_latency в sources
    # Миграция 2: last_live_check, last_check, fail_streak в proxies
```

**Безопасность:**
- `ALTER TABLE ADD COLUMN` — безопасно для SQLite
- Новые поля NULL по умолчанию
- Обратная совместимость сохранена

---

## 4) Test Outputs (ключевые строки)

```bash
# Unit tests
pytest -q
# Ожидается: 41 passed

# Smoke
fp op status
# Ожидается: HOT > 0, WARM > 0

# Быстрый e2e
python tests/e2e_test.py
# Ожидается: success ratio >= 0.4
```

---

## 5) e2e Proxy Success Ratio

**Цель:** >= 0.4 на 10 попытках

**Скрипт проверки:** `tests/e2e_test.py`

```python
# Берёт 10 прокси через ProxyManager.get_proxy()
# Проверяет реальным GET к https://httpbin.org/ip
# Считает success ratio
```

---

## 6) Remaining Risks

| Риск | Митигация |
|------|-----------|
| Старые прокси без last_live_check | Исключаются из выдачи (freshness check) |
| Массовый downgrade при первом запуске | Ожидается, pipeline пере-валидирует |
| Performance (rotation/diversity checks) | Лимит 50 прокси на пул, кэширование subnet |

---

## 7) Known Limitations

1. **Stage A без IP match** для GitHub Raw — всё ещё может давать "false positive"
2. **Stage B не всегда запускается** (skip_stage_b=True по умолчанию)
3. **Success metrics** всё ещё могут быть "оптимистичными" для новых прокси

---

## 8) Команды для Проверки

```bash
cd /mnt/Storage/linux/VSCode/Projects/05_Tools/free-proxy
source .venv/bin/activate

# 1. Unit tests
pytest -q

# 2. Smoke
fp op status

# 3. E2E test
python tests/e2e_test.py

# 4. Реальная выдача
python -c "
import asyncio
from fp import ProxyManager

async def test():
    async with ProxyManager() as m:
        for i in range(10):
            proxy = await m.get_proxy()
            if proxy:
                print(f'{i+1}. {proxy[\"protocol\"]}://{proxy[\"ip\"]}:{proxy[\"port\"]} (score: {proxy[\"score\"]})')
            else:
                print(f'{i+1}. No proxy available')

asyncio.run(test())
"
```

---

**Статус:** ✅ Готово к финальному тестированию
