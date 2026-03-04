# 🚀 Free Proxy v3.0 — MVP Release Notes

**Версия:** 3.0.0 (Production Ready MVP)  
**Дата:** 04.03.2026  
**Статус:** ✅ Готово к релизу

---

## 📋 Реализованные Фазы

### ✅ Phase 1: 2-Этапная Валидация

**Файл:** `fp/validator.py`

```python
from fp import AsyncProxyValidator

async with AsyncProxyValidator(max_concurrent=50) as validator:
    # Stage A: Быстрая проверка (httpbin, latency, timeout)
    result = await validator.validate_stage_a("8.219.97.248", 80, "http")
    
    # Stage B: Боевая проверка (OZON, WB, Avito, Google)
    result = await validator.validate_stage_b("8.219.97.248", 80, "http")
    
    # Полная валидация
    result = await validator.validate_full("8.219.97.248", 80, "http")
```

**Критерии:**
- ✅ Stage A: httpbin.org/ip, latency < 2s, status == 200, IP match
- ✅ Stage B: HEAD запросы к 4 доменам, ≥2 успешных
- ✅ Timeout: 2s (Stage A), 5s (Stage B)

---

### ✅ Phase 2: Score-Система (0-100)

**Файл:** `fp/validator.py` (ProxyMetrics)

**Формула:**
```python
score = 0.3*uptime + 0.25*latency_score + 0.3*success_rate - 0.15*ban_rate

где:
- latency_score = max(0, 100 - latency_ms/20)
- uptime = (recent_success / recent_total) * 100
- success_rate = (successful_checks / total_checks) * 100
- ban_rate = накопленный % 403/429 ошибок
```

**Метрики:**
- latency_ms (EMA)
- uptime (%)
- success_rate (%)
- ban_rate (%)
- total_checks
- successful_checks
- failed_checks

---

### ✅ Phase 3: Source Health

**Файл:** `fp/source_manager.py`

**Функции:**
- ✅ Fail streak tracking (счётчик неудач)
- ✅ Auto-disable при fail_streak > 5
- ✅ Disabled на 24ч
- ✅ Recheck после 24ч
- ✅ Pass rate calculation
- ✅ Логирование причин отвалов

---

### ✅ Phase 4: Пулы (Hot/Warm/Quarantine)

**Файл:** `fp/validator.py` (ProxyPool)

```python
class ProxyPool(str, Enum):
    HOT = "hot"          # score 80-100
    WARM = "warm"        # score 50-79
    QUARANTINE = "quarantine"  # score 0-49
```

**Стратегия выдачи:**
1. Сначала HOT пул
2. Если пуст → WARM
3. Если `use_quarantine=True` → QUARANTINE

---

### ✅ Phase 5: Инфраструктура

**Файлы:**
- `fp/database.py` — SQLite хранилище
- `fp/manager.py` — ProxyManager (полный цикл)
- `fp/scheduler.py` — APScheduler планировщик

**SQLite Таблицы:**
- `proxies` — IP, port, protocol, country, source, pool
- `metrics` — latency, uptime, success_rate, ban_rate, score
- `check_history` — история проверок (rolling 7 дней)
- `sources` — статистика источников
- `banlist` — чёрный список IP

**WAL режим** для конкурентности.

---

### ✅ Phase 6: Метрики + JSON Reports

**Формат отчёта:**
```json
{
  "timestamp": "2026-03-04T15:30:00",
  "total": 100,
  "new": 25,
  "existing": 75,
  "passed_a": 80,
  "passed_b": 65,
  "failed": 20,
  "hot": 45,
  "warm": 20,
  "quarantine": 35,
  "avg_latency": 234.5,
  "avg_score": 72.3,
  "errors": {
    "timeout": 12,
    "connect": 5,
    "ip_mismatch": 3
  }
}
```

**Отчёты:**
- Ежечасный: `~/.free-proxy/reports/latest.json`
- История: `~/.free-proxy/reports/report_YYYYMMDD_HHMMSS.json`

---

### ✅ Phase 7: Auto-Discovery (Частично)

**Реализовано:**
- ✅ SourceManager fetches from 53 sources
- ✅ Pass rate tracking
- ✅ Auto-disable при pass_rate < 30%

**TODO (v3.1):**
- GitHub API поиск новых proxy-list
- Sandbox test для новых источников
- Auto-promote при pass_rate > 40%

---

### ✅ Phase 8: Инкрементальный Refresh (Частично)

**Реализовано:**
- ✅ Quarantine recheck каждый час (50 прокси)
- ✅ History cleanup > 7 дней
- ✅ Ban list support

**TODO (v3.1):**
- Приоритет старым прокси при валидации
- ASN lookup для группировки

---

## 📊 Архитектура v3.0

```
┌─────────────────────────────────────────────────────────┐
│                    COLLECT                              │
│  SourceManager → 53 источника → Quality Gate           │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│                  VALIDATE A                             │
│  AsyncProxyValidator → httpbin/ip → latency < 2s       │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│                  VALIDATE B                             │
│  OZON / WB / Avito / Google → HEAD → ≥2 успешных       │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│                    SCORE                                │
│  ProxyMetrics → score (0-100) → pool assignment        │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│                    POOLS                                │
│  HOT (80-100) → WARM (50-79) → QUARANTINE (0-49)       │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│              SCHEDULER (APScheduler)                    │
│  Hourly: quarantine recheck, reports                   │
│  Daily: history cleanup, source recheck                │
└─────────────────────────────────────────────────────────┘
```

---

## 🚀 Быстрый Старт v3.0

### Async Mode (Рекомендуется)

```python
import asyncio
from fp import ProxyManager

async def main():
    async with ProxyManager(max_concurrent=50) as manager:
        # Сбор и валидация
        proxies = [
            ("8.219.97.248", 80, "http"),
            ("185.199.229.156", 443, "https"),
        ]
        
        report = await manager.collect_and_validate(proxies)
        print(f"Passed: {report['passed_a']}/{report['total']}")
        
        # Получить прокси
        proxy = await manager.get_proxy(min_score=50)
        if proxy:
            print(f"Got: {proxy['protocol']}://{proxy['ip']}:{proxy['port']}")
            print(f"Score: {proxy['score']:.1f}")

asyncio.run(main())
```

### Scheduler (Фоновый режим)

```python
import asyncio
from fp import ProxyScheduler

async def main():
    scheduler = ProxyScheduler(
        db_path="~/.free-proxy/proxies.db",
        max_concurrent=50,
    )
    
    await scheduler.start()  # Запуск на постоянную основу

asyncio.run(main())
```

### CLI (v2.0, обратно совместим)

```bash
fp get
fp get -c US -t 1.0 -r
fp get -n 10 -f json
```

---

## 📈 Метрики и Мониторинг

### Stats

```python
async with ProxyManager() as manager:
    stats = await manager.get_stats()
    
    # {
    #   "total_proxies": 1234,
    #   "hot_count": 456,
    #   "warm_count": 567,
    #   "quarantine_count": 211,
    #   "avg_score": 68.5,
    #   "checks_24h": 5678,
    #   "success_24h": 4321,
    #   "banlist_count": 89
    # }
```

### Source Stats

```python
async with SourceManager() as manager:
    sources = await manager.get_source_stats()
    
    for source in sources:
        status = "🔴" if source["disabled"] else "🟢"
        print(f"{status} {source['name']}: {source['pass_rate']:.1f}%")
```

---

## 🧪 Тесты

```bash
# Запустить все тесты
pytest tests/ -v

# Только v3.0 тесты
pytest tests/test_v3.py -v

# С покрытием
pytest tests/ -v --cov=fp
```

**Результат:** 22 passing tests (100%)

---

## 📦 Зависимости

```txt
lxml>=5.3.0
requests>=2.32.3
aiohttp>=3.9.0
httpx>=0.26.0
typer>=0.9.0
rich>=13.0.0
pyyaml>=6.0
aiosqlite>=0.22.0
apscheduler>=3.11.0
```

---

## ⚠️ Известные Ограничения

1. **GitHub API auto-discovery** — отложено на v3.1
2. **ASN lookup** — отложено на v3.1
3. **Prometheus metrics** — опционально, не реализовано
4. **Web UI** — не в scope MVP

---

## 🎯 Критерии Готовности MVP

- [x] 2-этапная валидация работает
- [x] Score-система считает (0-100)
- [x] Auto-disable источников при fail streak > 5
- [x] 3 пула (hot/warm/quarantine) работают
- [x] SQLite хранит историю
- [x] JSON отчёты каждый час
- [x] APScheduler выполняет maintenance
- [x] Тесты проходят (22/22)
- [x] CI/CD pipeline зелёный

---

## 📝 Changelog

### v3.0.0 (2026-03-04)

**Полная переработка архитектуры**

- ✨ 2-этапная валидация (Stage A + Stage B)
- ✨ Score-система (0-100)
- ✨ Пулы (HOT/WARM/QUARANTINE)
- ✨ SQLite хранилище
- ✨ APScheduler для maintenance
- ✨ Source health tracking
- ✨ Auto-disable источников
- ✨ Hourly JSON reports
- ✨ Ban list support

**Новые модули:**
- `fp/validator.py` — AsyncProxyValidator
- `fp/database.py` — ProxyDatabase
- `fp/manager.py` — ProxyManager
- `fp/scheduler.py` — ProxyScheduler
- `fp/source_manager.py` — SourceManager

**Тесты:** 22 passing

---

**Made with ❤️ by motttik**
