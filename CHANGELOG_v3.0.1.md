# 🔧 Free Proxy v3.0 — Changelog

## [3.0.1] - 2026-03-04

### Fixed
- **Dependencies**: Добавлены `aiosqlite>=0.22.0` и `apscheduler>=3.11.0` в `requirements.txt`
- **setup.py**: Синхронизирован с `requirements.txt`
- Проект теперь устанавливается "из коробки" без ручных зависимостей

### Added
- **Source Health Manager** (`fp/source_health.py`):
  - Fail streak tracking (порог: 5 неудач → disable 24ч)
  - Pass rate calculation (порог: <30% → disable 24ч)
  - Auto-disable нестабильных источников
  - Recheck после cooldown
  - Core vs Candidate sources разделение

- **Pipeline** (`fp/pipeline.py`):
  - Полный цикл: `COLLECT → NORMALIZE → DEDUP → VALIDATE_FAST → VALIDATE_TARGETED → SCORE → POOL_UPDATE → REPORT`
  - Нормализация формата (scheme://ip:port, protocol, country, source)
  - Дедупликация по `ip:port:protocol`
  - Stage A (быстрая) валидация
  - Stage B (боевая) валидация
  - Score calculation (0-100)
  - Pool assignment (HOT/WARM/QUARANTINE)
  - JSON отчёты с причинами отказов

### Exports
```python
from fp import (
    SourceHealthManager,
    ProxyPipeline,
    PipelineReport,
    NormalizedProxy,
)
```

### Tests
- **41 passing test** (100%)
- Coverage: 36%

---

## [3.0.0] - 2026-03-04

### Added
- 2-этапная валидация (Stage A + Stage B)
- Score-система (0-100)
- Пулы (HOT/WARM/QUARANTINE)
- SQLite хранилище
- APScheduler для maintenance
- Source health tracking
- Auto-disable источников
- Hourly JSON reports
- Ban list support

**Full changelog:** `RELEASE_v3.md`

---

## Использование Pipeline

```python
import asyncio
from fp import ProxyPipeline

async def main():
    async with ProxyPipeline(max_concurrent=50) as pipeline:
        # Полный цикл (Stage A + B)
        report = await pipeline.run_cycle(skip_targeted=False)
        
        print(f"HOT: {report.hot_number}")
        print(f"WARM: {report.warm_number}")
        print(f"Score: {report.avg_score:.1f}")

asyncio.run(main())
```

## Использование Source Health

```python
from fp import SourceHealthManager

async with SourceHealthManager() as manager:
    stats = manager.get_stats()
    print(f"Available: {stats['available']}/{stats['total_sources']}")
    
    disabled = manager.get_disabled_sources()
    for source in disabled:
        print(f"{source['name']}: {source['fail_streak']} fails")
```

---

**Made with ❤️ by motttik**
