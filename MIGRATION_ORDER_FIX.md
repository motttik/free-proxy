# 🔧 Migration Order Fix Report

**Дата:** 2026-03-04  
**Коммит:** 8f00d83  
**Статус:** ✅ FIXED

---

## Summary

Исправлена последняя регрессия БД-миграции:

**Проблема:**
```
sqlite3.OperationalError: no such column: country
Point: CREATE INDEX idx_proxy_country ON proxies(country)
```

**Причина:**
- Индекс создавался ДО миграции добавляющей колонку `country`
- Legacy БД могут не иметь колонку `country`

**Решение:**
1. `_run_migrations()` теперь запускается **ДО** `_create_tables()`
2. Добавлена миграция #3: `country` колонка для legacy БД
3. Создание индекса защищено через `_column_exists()` check

---

## Changed Files

| Файл | Изменения |
|------|-----------|
| `fp/database.py` | +_column_exists(), migration order fix, country migration |

---

## Migration Order

**Правильный порядок:**

```python
async def __aenter__(self) -> "ProxyDatabase":
    # 1. Сначала миграции (добавляем недостающие колонки)
    await self._run_migrations()
    # 2. Затем таблицы/индексы
    await self._create_tables()
```

**Миграции:**
1. `last_live_check REAL` — добавляется если нет
2. `last_check REAL` — добавляется если нет
3. `fail_streak INTEGER DEFAULT 0` — добавляется если нет
4. `avg_latency REAL DEFAULT 0` в sources — добавляется если нет
5. **`country TEXT` в proxies** — добавляется если нет (NEW!)

**Защищённое создание индексов:**
```python
# Индекс на country только если колонка существует
if await self._column_exists("proxies", "country"):
    await self._conn.execute("CREATE INDEX IF NOT EXISTS idx_proxy_country ...")
```

---

## Test Outputs

### До фикса:
```
============================== 1 failed, 43 passed ==============================
Fail: test_migration_order — OperationalError: no such column: country
```

### После фикса:
```
============================== 44 passed in 8.38s ==============================

$ fp op status
Proxy Pool Status
┏━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━┳━━━━━━━━┓
┃ Pool       ┃ Count ┃ Target ┃ Status ┃
┡━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━╇━━━━━━━━┩
│ HOT        │   664 │     30 │ ✓ OK   │
│ WARM       │   336 │      - │ ✓      │
└────────────┴───────┴────────┴────────┘
```

---

## Functions Modified in fp/database.py

| Функция | Изменения |
|---------|-----------|
| `__aenter__()` | Порядок: migrations → tables (было наоборот) |
| `_column_exists()` | **NEW** — проверка существования колонки |
| `_run_migrations()` | +Миграция #3: country column |
| `_create_tables()` | Protected index creation с column_exists check |

---

## Verification Commands

```bash
cd /mnt/Storage/linux/VSCode/Projects/05_Tools/free-proxy
source .venv/bin/activate

# 1. Unit tests
pytest -q
# Ожидается: 44 passed

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
| OperationalError: country | ✅ FIXED |
| Migration order | ✅ FIXED |
| Index on non-existent column | ✅ FIXED |
| Legacy databases | ✅ Tested |

---

**Статус:** ✅ ГОТОВО К PRODUCTION

**GitHub:** https://github.com/motttik/free-proxy  
**Последний коммит:** `8f00d83`
