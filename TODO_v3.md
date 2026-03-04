# 🚀 Free Proxy v3.0 — План Доработки

**Версия:** 3.0.0 (Production Ready)  
**Дата:** 04.03.2026  
**Приоритет:** Критичные улучшения для production использования

---

## 📋 Обратная Связь (Кратко)

### Текущие Проблемы
- ❌ Много дохлых источников (404/таймауты) → шум
- ❌ Нет нормального score прокси (жив/не жив — мало)
- ❌ Нет авто-выключения плохих источников
- ❌ Проверка "работает" ≠ "работает на OZON/WB/Avito"

### Требуемые Улучшения
1. **2-этапная валидация** (быстрая + боевая)
2. **Score-система** (0-100: uptime, latency, ban-rate, success-rate)
3. **Source health** (fail streak → auto-disable)
4. **Пулы** (hot / warm / quarantine)

---

## 🎯 Архитектура v3.0

```
┌─────────────────────────────────────────────────────────────────┐
│                    COLLECT (Источники)                          │
│  53 источника → Quality Gate → Sandbox Test → Auto-Promote     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                  VALIDATE A (Быстрая)                           │
│  httpbin/ip → latency < 2s → status == 200 → IP match          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                  VALIDATE B (Боевая)                            │
│  OZON / WB / Avito → мягкий тест (HEAD, timeout 5s)            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    SCORE (0-100)                                │
│  uptime + latency + success_rate - ban_rate → pool assignment  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    POOLS                                        │
│  HOT (80-100) → WARM (50-79) → QUARANTINE (0-49)               │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    ROTATE + REPORT                              │
│  JSON/Prometheus → Grafana → Auto-disable по threshold         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 Phase 1: 2-Этапная Валидация

### 1.1 Быстрая Валидация (Validate A)

| Задача | Приоритет | Время | DoD |
|--------|-----------|-------|-----|
| 1.1.1 Создать `AsyncValidator` класс с httpx | Critical | 2ч | Класс с async методами `quick_check()` |
| 1.1.2 Реализовать проверку httpbin.org/ip | Critical | 1ч | IP прокси == response.origin |
| 1.1.3 Замер latency (connect + response time) | Critical | 1ч | latency в мс, сохраняется в Proxy.score |
| 1.1.4 Timeout < 2s для быстрой проверки | Critical | 0.5ч | Параметр `quick_timeout=2.0` |
| 1.1.5 Статус код == 200 | Critical | 0.5ч | Отсев 4xx/5xx |

**Критерии прохождения:**
- latency < 2000ms
- status == 200
- IP match (прокси IP == response IP)

### 1.2 Боевая Валидация (Validate B)

| Задача | Приоритет | Время | DoD |
|--------|-----------|-------|-----|
| 1.2.1 Создать список целевых доменов | High | 1ч | ['ozon.ru', 'wildberries.ru', 'avito.ru', 'google.com'] |
| 1.2.2 HEAD запрос с timeout 5s | High | 2ч | Метод `target_check(domains)` |
| 1.2.3 Мягкий тест (не валить на 4xx) | High | 1ч | 4xx = warning, 5xx/timeout = fail |
| 1.2.4 Сохранение результатов по доменам | Medium | 1ч | `proxy.target_results = {'ozon': True, ...}` |

**Критерии прохождения:**
- ≥2 из 4 доменов доступны
- Нет 5xx ошибок
- Timeout < 5s

---

## 📊 Phase 2: Score-Система (0-100)

### 2.1 Метрики

| Задача | Приоритет | Время | DoD |
|--------|-----------|-------|-----|
| 2.1.1 Uptime (% успешных проверок) | Critical | 2ч | `uptime = success / total * 100` |
| 2.1.2 Latency score (0-100) | Critical | 1ч | `latency_score = max(0, 100 - latency_ms/20)` |
| 2.1.3 Success rate (% рабочих проверок) | Critical | 1ч | `success_rate = recent_success / recent_total` |
| 2.1.4 Ban rate (% блокировок) | High | 2ч | `ban_rate = 403/429_count / total` |
| 2.1.5 Формула общего score | Critical | 1ч | `score = 0.3*uptime + 0.25*latency + 0.3*success - 0.15*ban` |

### 2.2 Хранение Истории

| Задача | Приоритет | Время | DoD |
|--------|-----------|-------|-----|
| 2.2.1 SQLite для score history | Critical | 3ч | Таблица `proxy_scores(ip, port, score, timestamp, metrics)` |
| 2.2.2 Rolling window (последние 100 проверок) | High | 2ч | Хранить только последние N записей |
| 2.2.3 Age-out старых записей (>24ч) | Medium | 1ч | Cron job для очистки |

---

## 🏥 Phase 3: Source Health

### 3.1 Fail Streak Tracking

| Задача | Приоритет | Время | DoD |
|--------|-----------|-------|-----|
| 3.1.1 Счётчик неудач источника | Critical | 2ч | `source.fail_streak` в БД |
| 3.1.2 Threshold N=5 для auto-disable | Critical | 1ч | При 5 неудачах → disable |
| 3.1.3 Auto-disable на 24ч | Critical | 2ч | `disabled_until = now + 24h` |
| 3.1.4 Recheck после 24ч | High | 2ч | Cron job → enable + test |

### 3.2 Quality Gate для Источников

| Задача | Приоритет | Время | DoD |
|--------|-----------|-------|-----|
| 3.2.1 Pass-rate threshold (≥30%) | Critical | 2ч | Если < 30% рабочих → disable |
| 3.2.2 Логирование причин отвалов | High | 1ч | 404/timeout/DNS/parse_error |
| 3.2.3 Daily report по источникам | Medium | 2ч | JSON отчёт: источник → pass-rate → статус |

---

## 🏊 Phase 4: Пулы (Hot / Warm / Quarantine)

### 4.1 Классификация

| Задача | Приоритет | Время | DoD |
|--------|-----------|-------|-----|
| 4.1.1 Hot pool (score 80-100) | Critical | 2ч | Приоритетная выдача |
| 4.1.2 Warm pool (score 50-79) | Critical | 2ч | Резерв, если hot пуст |
| 4.1.3 Quarantine pool (score 0-49) | Critical | 2ч | Не выдавать, recheck через 1ч |
| 4.1.4 Auto-rotate между пулами | High | 3ч | При изменении score → move pool |

### 4.2 Стратегия Выдачи

| Задача | Приоритет | Время | DoD |
|--------|-----------|-------|-----|
| 4.2.1 Сначала hot, потом warm | Critical | 1ч | Логика `get()` с приоритетом |
| 4.2.2 Quarantine skip по умолчанию | Critical | 1ч | Флаг `use_quarantine=False` |
| 4.2.3 Round-robin внутри пула | Medium | 2ч | Избегать повторений |

---

## ⚙️ Phase 5: Инфраструктура

### 5.1 Async + HTTPx/Aiohttp

| Задача | Приоритет | Время | DoD |
|--------|-----------|-------|-----|
| 5.1.1 Миграция на httpx (async) | Critical | 4ч | Все запросы через httpx.AsyncClient |
| 5.1.2 Concurrent проверки (semaphore) | Critical | 2ч | `max_concurrent=50` |
| 5.1.3 Retry logic (exponential backoff) | High | 2ч | 3 retry, 1s→2s→4s delay |

### 5.2 SQLite/Redis для State

| Задача | Приоритет | Время | DoD |
|--------|-----------|-------|-----|
| 5.2.1 SQLite схема (proxies, scores, sources) | Critical | 4ч | 3 таблицы + индексы |
| 5.2.2 Connection pool | High | 2ч | `sqlite3.connect(..., check_same_thread=False)` |
| 5.2.3 Redis (опционально для кэша) | Low | 3ч | Кэш последних проверок |

### 5.3 APScheduler/Cron

| Задача | Приоритет | Время | DoD |
|--------|-----------|-------|-----|
| 5.3.1 Cron для recheck quarantine | High | 2ч | Каждые 1ч → recheck |
| 5.3.2 Daily cleanup (>24ч записи) | Medium | 1ч | Каждые 24ч → DELETE |
| 5.3.3 Hourly source health check | High | 2ч | Проверка disabled источников |

---

## 📈 Phase 6: Метрики + Отчёты

### 6.1 JSON Reports

| Задача | Приоритет | Время | DoD |
|--------|-----------|-------|-----|
| 6.1.1 Ежечасный отчёт | Critical | 3ч | `{total, live, hot_count, warm_count, quarantine_count}` |
| 6.1.2 Топ причин отвалов | High | 2ч | `{timeout: 45, 404: 30, dns: 15, ...}` |
| 6.1.3 Топ источников по pass-rate | Medium | 2ч | `[{source, pass_rate, fail_streak}, ...]` |

### 6.2 Prometheus + Grafana (Опционально)

| Задача | Приоритет | Время | DoD |
|--------|-----------|-------|-----|
| 6.2.1 Prometheus metrics endpoint | Low | 4ч | `/metrics` с proxy_stats |
| 6.2.2 Grafana dashboard template | Low | 3ч | JSON dashboard для импорта |

---

## 🔍 Phase 7: Автоматическое Увеличение Источников

### 7.1 Daily Source Discovery

| Задача | Приоритет | Время | DoD |
|--------|-----------|-------|-----|
| 7.1.1 GitHub API поиск (proxy-list) | High | 3ч | Поиск по `proxy-list`, `free-proxy` |
| 7.1.2 Паттерны для raw.githubusercontent | High | 2ч | `**/proxy*.txt`, `**/http.txt` |
| 7.1.3 Автоматическое добавление в конфиг | Medium | 2ч | Новый источник → `config.py` |

### 7.2 Sandbox Test

| Задача | Приоритет | Время | DoD |
|--------|-----------|-------|-----|
| 7.2.1 2-3 цикла тестирования | Critical | 3ч | Новый источник → sandbox на 2 цикла |
| 7.2.2 Pass-rate threshold для promote | Critical | 2ч | ≥40% → auto-promote |
| 7.2.3 Auto-disable если < 20% | Critical | 2ч | < 20% → disable + лог |

---

## 🔄 Phase 8: "Пиздатый" Процесс

### 8.1 Железный Цикл

```
COLLECT → VALIDATE A → VALIDATE B → SCORE → ROTATE → REPORT
```

| Задача | Приоритет | Время | DoD |
|--------|-----------|-------|-----|
| 8.1.1 Конечный автомат для прокси | Critical | 4ч | States: new→validating_a→validating_b→hot/warm/quarantine |
| 8.1.2 Короткий отчёт каждую итерацию | Critical | 2ч | `Новых: X, Живых: Y, Отвалов: Z (причины)` |
| 8.1.3 Логирование каждого этапа | High | 2ч | DEBUG логи для отладки |

### 8.2 Инкрементальный Refresh

| Задача | Приоритет | Время | DoD |
|--------|-----------|-------|-----|
| 8.2.1 Не валидировать всё каждый цикл | High | 3ч | Проверять 1/N пула за цикл |
| 8.2.2 Приоритет старым прокси | Medium | 2ч | Сначала те, что давно не проверялись |
| 8.2.3 Дедуп новых прокси | Critical | 2ч | Проверка по `(ip, port)` перед добавлением |

### 8.3 Бан-лист Плохих ASN/IP

| Задача | Приоритет | Время | DoD |
|--------|-----------|-------|-----|
| 8.3.1 Чёрный список IP | High | 2ч | `ban_list = set(ip1, ip2, ...)` |
| 8.3.2 ASN lookup для группировки | Low | 4ч | Если ASN плохой → бан всей подсети |
| 8.3.3 Быстрая проверка перед валидацией | High | 1ч | Если в бан-листе → skip |

---

## 📅 Timeline

| Неделя | Фазы | Задачи | Часы |
|--------|------|--------|------|
| 1 | Phase 1 + 2.1 | 2-этапная валидация + базовые метрики | 16ч |
| 2 | Phase 2.2 + 3 | Score history + Source health | 20ч |
| 3 | Phase 4 + 5.1 | Пулы + Async миграция | 18ч |
| 4 | Phase 5.2 + 6 | SQLite + Reports | 16ч |
| 5 | Phase 7 | Auto-discovery источников | 12ч |
| 6 | Phase 8 + тесты | Инкрементальный refresh + финальные тесты | 14ч |

**Итого:** ~96 часов (12 рабочих дней)

---

## 🎯 Критерии Готовности v3.0

- [ ] Все Critical задачи выполнены
- [ ] 2-этапная валидация работает
- [ ] Score-система считает uptime/latency/ban-rate
- [ ] Auto-disable источников при fail streak > 5
- [ ] 3 пула (hot/warm/quarantine) работают
- [ ] SQLite хранит историю score
- [ ] JSON отчёты каждый час
- [ ] GitHub API ищет новые источники
- [ ] Покрытие тестов ≥ 70%
- [ ] CI/CD pipeline зелёный

---

## 📝 Примечания

### Важные Решения
1. **SQLite вместо Redis** — проще для деплоя, достаточно для ~10K прокси
2. **HTTPx вместо Aiohttp** — единый клиент для sync/async
3. **APScheduler вместо cron** — кроссплатформенно, легче тестировать

### Риски
1. **GitHub API rate limit** — кэшировать результаты, использовать токен
2. **SQLite locking** — использовать WAL режим, connection pool
3. **Async complexity** — тщательно тестировать, добавить таймауты

### Будущие Улучшения (v4.0)
- WebSocket для real-time метрик
- REST API для управления пулами
- Веб-интерфейс (Grafana-like dashboard)
- Поддержка платных прокси (Bright Data, Oxylabs)

---

**Документ готов к реализации. Приступаю к Phase 1 по команде!** 🚀
