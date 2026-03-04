# 🚀 Free Proxy v3.1 — Complete Release Notes

**Версия:** 3.1.0 (Production Ready)  
**Дата:** 04.03.2026  
**Статус:** ✅ MVP готов к релизу  
**Цель:** 20-30 HOT прокси гарантированно

---

## 📋 Реализованные Функции

### ✅ SLO + Alerts

**Модуль:** `fp/slo_monitor.py`

**SLO Цели:**
- HOT прокси: ≥20 (цель 30)
- Alert: <10 HOT > 30 минут → **CRITICAL**
- Warning: <15 HOT > 15 минут → **WARNING**

**Auto-Actions:**
- Emergency rebuild при critical >30 мин
- Auto-recheck quarantine
- Prometheus metrics export

**Использование:**
```python
from fp import SLOMonitor

async with SLOMonitor() as monitor:
    metrics, alerts = await monitor.check_slo()
    
    print(f"HOT: {metrics.hot_number}")
    print(f"Alerts: {monitor.get_alert_summary()}")
    
    # Prometheus format
    prom = await monitor.export_prometheus_metrics()
```

---

### ✅ Operator CLI

**Команды:** `fp op *`

```bash
# Pool status
fp op status

# Source health
fp op source-health

# SLO alerts
fp op alerts

# Rebuild HOT pool
fp op rebuild-hot -l 100

# Explain proxy
fp op explain 8.219.97.248 80

# Run pipeline
fp op run-pipeline
```

---

### ✅ GitHub Auto-Discovery

**Модуль:** `fp/github_discovery.py`

**Функции:**
- GitHub API search по proxy-list паттернам
- Поиск файлов: `proxy*.txt`, `http*.txt`, `socks*.txt`
- Sandbox test (3 цикла) для candidate sources
- Auto-promote при pass_rate > 40%
- Auto-disable при pass_rate < 20%
- Trusted authors whitelist

**Использование:**
```python
from fp import GitHubDiscovery

async with GitHubDiscovery() as discovery:
    discovered = await discovery.discover_new_sources()
    print(f"New sources: {len(discovered)}")
    
    # Sandbox test
    for source in discovered:
        await discovery.sandbox_test(source.url)
    
    # Get promoted
    promoted = discovery.get_promoted_sources()
```

---

## 🔄 Полный Pipeline

```
COLLECT → NORMALIZE → DEDUP → VALIDATE_FAST → VALIDATE_TARGETED → SCORE → POOL_UPDATE → REPORT
```

### Этапы:

1. **COLLECT** (53 источника)
   - Core sources (проверенные)
   - Candidate sources (новые)
   - GitHub discovered

2. **NORMALIZE**
   - Формат: `scheme://ip:port`
   - protocol, country, source

3. **DEDUP**
   - Удаление дубликатов по `ip:port:protocol`

4. **VALIDATE_FAST** (Stage A)
   - httpbin.org/ip
   - latency < 2s
   - status == 200
   - IP match

5. **VALIDATE_TARGETED** (Stage B)
   - OZON/WB/Avito/Google
   - HEAD запросы
   - ≥2 успешных из 4

6. **SCORE** (0-100)
   ```
   score = 0.3*uptime + 0.25*latency + 0.3*success - 0.15*ban_rate
   ```

7. **POOL_UPDATE**
   - HOT: score ≥ 80
   - WARM: score 50-79
   - QUARANTINE: score < 50

8. **REPORT**
   - JSON отчёт
   - Top fail reasons
   - Source stats

---

## 📊 Метрики

| Метрика | Значение |
|---------|----------|
| **Тестов** | 41 passed (100%) |
| **Coverage** | 33% |
| **Модулей** | 10 (v3.1) |
| **Строк кода** | ~3300 |
| **Источников** | 53 + auto-discovery |
| **HOT прокси (цель)** | 20-30 |

---

## 🎯 Гарантия 20-30 HOT Прокси

### Как достигается:

1. **53 источника** (GitHub, API, HTML)
2. **Auto-discovery** новых источников
3. **2-этапная валидация** (Stage A + B)
4. **Score-система** (0-100)
5. **Source Health** (auto-disable плохих)
6. **SLO Monitoring** (alerts при <10 HOT)
7. **Auto-rebuild** quarantine пула

### Pipeline цикл:

```python
from fp import ProxyPipeline, SLOMonitor

async def ensure_hot_proxies():
    async with ProxyPipeline(max_concurrent=50) as pipeline:
        # Запускаем цикл
        report = await pipeline.run_cycle()
        
        # Проверяем SLO
        async with SLOMonitor() as slo:
            metrics, alerts = await slo.check_slo()
            
            if metrics.hot_number < 20:
                # Emergency rebuild
                await pipeline.run_cycle(skip_targeted=False)
```

---

## 🛠️ CLI Примеры

### Pool Status
```bash
$ fp op status

Proxy Pool Status

┏────────────┳━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━┓
┃ Pool       ┃ Count ┃ Target ┃ Status     ┃
┡────────────╇━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━┩
│ HOT        │    25 │     30 │ ✓ OK       │
│ WARM       │    45 │      - │ ✓          │
│ QUARANTINE │    30 │      - │ ✓          │
│ TOTAL      │   100 │      - │ ✓          │
└────────────┴───────┴────────┴────────────┘

Avg Score: 72.5
Checks 24h: 5678 (4321 successful)
Banlist: 89 IPs
```

### Source Health
```bash
$ fp op source-health

Source Health

Total: 53 | Available: 45 | Disabled: 8
Avg Pass Rate: 68.5%

Top Errors:
  timeout: 145
  connect: 89
  parse_error: 34

Disabled Sources:
┏━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Name             ┃ Fail Streak ┃ Pass Rate  ┃ Until      ┃
┡━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ BadSource1       │           8 │      15.2% │ 2026-03-05 │
│ BadSource2       │           6 │      22.1% │ 2026-03-05 │
└──────────────────┴─────────────┴────────────┴────────────┘
```

### Explain Proxy
```bash
$ fp op explain 8.219.97.248 80

Proxy 8.219.97.248:80

Pool: 🟢 HOT
Score: 85.3/100

┏━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┓
┃ Metric         ┃ Value       ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━┩
│ Latency        │ 234ms       │
│ Uptime         │ 95.2%       │
│ Success Rate   │ 92.1%       │
│ Ban Rate       │ 2.3%        │
└────────────────┴─────────────┘

Explanation:
✓ High score, reliable proxy
```

---

## 📦 Зависимости

```txt
# Core
lxml>=5.3.0
requests>=2.32.3

# Async
aiohttp>=3.9.0
httpx>=0.26.0

# CLI
typer>=0.9.0
rich>=13.0.0
pyyaml>=6.0

# Database (v3.0)
aiosqlite>=0.22.0

# Scheduler (v3.0)
apscheduler>=3.11.0
```

---

## 🧪 Тесты

```bash
# Все тесты
pytest tests/ -v

# С покрытием
pytest tests/ -v --cov=fp

# Конкретный модуль
pytest tests/test_v3.py::TestProxyMetrics -v
```

**Результат:** 41 passing tests (100%)

---

## 📈 Архитектура

```
┌─────────────────────────────────────────────────────────┐
│                    COLLECT                              │
│  53 источника + GitHub Discovery                        │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│                  NORMALIZE + DEDUP                      │
│  ip:port:protocol unique                                │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│             VALIDATE_FAST (Stage A)                     │
│  httpbin, latency < 2s, IP match                        │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│            VALIDATE_TARGETED (Stage B)                  │
│  OZON/WB/Avito/Google, ≥2/4                             │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│                    SCORE (0-100)                        │
│  uptime + latency + success - ban_rate                  │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│              POOLS (HOT/WARM/QUARANTINE)                │
│  HOT ≥80, WARM 50-79, QUARANTINE <50                    │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│                 SLO MONITOR                             │
│  ≥20 HOT (цель 30), alerts при <10                     │
└─────────────────────────────────────────────────────────┘
```

---

## 🎯 Критерии Готовности

- [x] 2-этапная валидация работает
- [x] Score-система (0-100)
- [x] Source Health + auto-disable
- [x] 3 пула (HOT/WARM/QUARANTINE)
- [x] SQLite хранение
- [x] SLO monitoring + alerts
- [x] Operator CLI (6 команд)
- [x] GitHub auto-discovery
- [x] JSON отчёты
- [x] Тесты (41 passed)

---

## 🚀 Быстрый Старт

```python
import asyncio
from fp import ProxyPipeline, SLOMonitor

async def main():
    async with ProxyPipeline(max_concurrent=50) as pipeline:
        # Запуск цикла
        report = await pipeline.run_cycle()
        
        print(f"HOT: {report.hot_number}")
        print(f"Score: {report.avg_score:.1f}")
        
        # Проверка SLO
        async with SLOMonitor() as slo:
            metrics, alerts = await slo.check_slo()
            
            if metrics.hot_number < 20:
                print("⚠️  SLO violation! Rebuilding...")
                await pipeline.run_cycle()

asyncio.run(main())
```

---

**Made with ❤️ by motttik**
