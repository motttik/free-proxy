# 🔧 DB Migration Fix Report

**Дата:** 2026-03-04  
**Коммит:** 5d26df0  
**Статус:** ✅ FIXED

---

## Summary

Исправлена критическая ошибка БД-миграции:

**Проблема:**
```
OperationalError: no such column: last_live_check
```

**Причина:**
- `_create_tables()` создавал индекс на `last_live_check`
- Но колонка не существовала в существующих БД
- Порядок был неправильный: таблицы → индексы → миграции

**Решение:**
1. Добавлены helper функции `_column_exists()` и `_table_exists()`
2. Исправлен порядок: **таблицы → миграции → индексы**
3. Условное создание индексов (только если колонка существует)
4. Миграция проверяет существование таблицы перед ALTER TABLE

---

## Changed Files

| Файл | Изменения |
|------|-----------|
| `fp/database.py` | +_column_exists(), +_table_exists(), fixed __aenter__ order |
| `tests/test_db_migration.py` | Новые regression тесты |

---

## Migration Notes

**Автоматическая миграция при старте:**

```python
async def __aenter__(self) -> "ProxyDatabase":
    # 1. Базовые таблицы
    await self._create_tables()
    # 2. Миграции (добавляем колонки)
    await self._run_migrations()
    # 3. Индексы (только если колонки существуют)
    if await self._column_exists("proxies", "last_live_check"):
        await self._conn.execute("CREATE INDEX IF NOT EXISTS idx_proxy_last_live_check ...")
```

**Миграции:**
- `last_live_check REAL` — добавляется если нет
- `last_check REAL` — добавляется если нет
- `fail_streak INTEGER DEFAULT 0` — добавляется если нет
- `avg_latency REAL DEFAULT 0` в sources — добавляется если нет

**Безопасность:**
- Проверка существования таблицы перед ALTER
- Проверка существования колонки перед CREATE INDEX
- Обратная совместимость сохранена

---

## Test Outputs

### До фикса:
```
fp op status -> OperationalError: no such column: last_live_check
```

### После фикса:
```
============================== 41 passed in 6.84s ==============================

$ fp op status
Proxy Pool Status
┏━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━┳━━━━━━━━┓
┃ Pool       ┃ Count ┃ Target ┃ Status ┃
┡━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━╇━━━━━━━━┩
│ HOT        │   664 │     30 │ ✓ OK   │
│ WARM       │   336 │      - │ ✓      │
│ QUARANTINE │     0 │      - │ ✓      │
└────────────┴───────┴────────┴────────┘
```

---

## Regression Tests

**Новый тест:** `tests/test_db_migration.py`

```python
@pytest.mark.asyncio
async def test_old_database_without_last_live_check():
    """
    Сценарий: старая БД без last_live_check
    Ожидание: инициализация проходит без падения
    """
```

**Проверка:**
- Старая БД без колонок → миграция добавляет
- Индексы создаются только после миграции
- `fp op status` работает без ошибок

---

## Verification Commands

```bash
cd /mnt/Storage/linux/VSCode/Projects/05_Tools/free-proxy
source .venv/bin/activate

# 1. Unit tests
pytest -q
# Ожидается: 41 passed

# 2. Smoke
fp op status
# Ожидается: HOT > 0, без ошибок

# 3. Regression test
pytest tests/test_db_migration.py -v
# Ожидается: 3 passed
```

---

## Remaining Risks

| Риск | Статус |
|------|--------|
| OperationalError | ✅ FIXED |
| Migration order | ✅ FIXED |
| Index on non-existent column | ✅ FIXED |
| Existing databases | ✅ Tested |

---

**Статус:** ✅ ГОТОВО К PRODUCTION
