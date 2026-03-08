# 🔄 Plan рефакторинга Free Proxy v4.0

## 📊 Анализ текущей архитектуры

### Текущая структура (v3.x)
```
fp/
├── __init__.py           # 70+ импортов всего
├── core.py               # 405 строк - синхронная логика
├── core_async.py         # 328 строк - асинхронная логика (дублирование!)
├── cli.py                # 755 строк - монолит
├── manager.py            # 491 строка - смешанная ответственность
├── database.py           # 511 строк
├── validator.py          # 395 строк
├── pipeline.py           # 483 строки
├── source_manager.py     # 367 строк
├── source_health.py      # 322 строки
├── slo_monitor.py        # 356 строк
├── scheduler.py          # 241 строка
├── github_discovery.py   # 362 строки
├── smoke.py              # 300 строк
└── checkers/
    ├── sync_checker.py   # 177 строк
    └── async_checker.py  # 229 строк
```

### Проблемы архитектуры

1. **Дублирование кода**: `core.py` ↔ `core_async.py` (~60% дублирования)
2. **Монолитный CLI**: 755 строк в одном файле
3. **Нарушение Single Responsibility**: `manager.py` - сбор, проверка, scoring, ротация
4. **Отсутствие единого API**: пользователи должны импортировать多个 классов
5. **Глобальное состояние**: импорты в `__init__.py` могут вызывать side effects

---

## 🎯 Цели рефакторинга (v4.0)

### 1. Устранение дублирования
**Решение**: Единая асинхронная база + синхронная обёртка

```python
# Новый подход
class BaseProxy:
    """Асинхронная базовая реализация"""
    async def get_proxy(...) -> Proxy: ...

class FreeProxy(BaseProxy):
    """Синхронный фасад для обратной совместимости"""
    def get_proxy(...) -> Proxy:
        return asyncio.run(self._async_get_proxy(...))
```

### 2. Модуляризация CLI
**Решение**: Разделение по командам

```
fp/
└── cli/
    ├── __init__.py       # Точка входа
    ├── app.py            # Основное приложение Typer
    ├── commands/
    │   ├── get.py        # fp get
    │   ├── list.py       # fp list
    │   ├── test.py       # fp test
    │   ├── op.py         # fp op (operator commands)
    │   └── config.py     # fp config
    └── utils.py          # Утилиты (таблицы, цвета)
```

### 3. Разделение ответственности
**Решение**: Паттерн Strategy + Dependency Injection

```python
# Новый ProxyManager
class ProxyManager:
    def __init__(
        self,
        collector: ProxyCollector,
        validator: ProxyValidator,
        scorer: ProxyScorer,
        storage: ProxyStorage,
        rotator: ProxyRotator,
    ):
        self.collector = collector
        self.validator = validator
        self.scorer = scorer
        self.storage = storage
        self.rotator = rotator
    
    async def get_proxy(self) -> Proxy:
        # Только оркестрация
        proxy = await self.collector.collect()
        result = await self.validator.validate(proxy)
        score = self.scorer.calculate(result)
        await self.storage.save(proxy, score)
        return self.rotator.select(score)
```

### 4. Единый API
**Решение**: Facade паттерн

```python
# Пользовательский API
from fp import FreeProxy

# Простой случай
proxy = FreeProxy().get()

# Продвинутый случай с кастомной конфигурацией
from fp import FreeProxyConfig

config = FreeProxyConfig(
    countries=['US', 'DE'],
    timeout=2.0,
    min_score=80,
    cache_ttl=600,
)
proxy = FreeProxy(config=config).get()
```

### 5. Lazy импорты
**Решение**: `__getattr__` для отложенной загрузки

```python
# __init__.py
def __getattr__(name):
    if name == "FreeProxy":
        from fp.core import FreeProxy
        return FreeProxy
    # ...
```

---

## 📐 Новая архитектура

### Структура проекта v4.0

```
fp/
├── __init__.py           # Lazy импорты, __version__
├── config.py             # Конфигурация (dataclasses)
├── types.py              # Типы (Proxy, ProxyMetrics, etc.)
├── errors.py             # Исключения
│
├── api/                  # Публичный API
│   ├── __init__.py
│   ├── sync.py           # Синхронный API
│   └── async.py          # Асинхронный API
│
├── core/                 # Ядро
│   ├── __init__.py
│   ├── base.py           # Базовый класс (async)
│   ├── collector.py      # Сбор прокси
│   ├── validator.py      # Валидация
│   ├── scorer.py         # Scoring
│   ├── rotator.py        # Ротация
│   └── facade.py         # FreeProxy facade
│
├── storage/              # Хранение
│   ├── __init__.py
│   ├── base.py           # Abstract Storage
│   ├── sqlite.py         # SQLite реализация
│   └── memory.py         # In-memory для тестов
│
├── sources/              # Источники
│   ├── __init__.py
│   ├── base.py           # Abstract Source
│   ├── github.py
│   ├── api.py
│   └── html.py
│
├── checkers/             # Проверка
│   ├── __init__.py
│   ├── base.py
│   ├── http.py
│   └── socks.py
│
├── cli/                  # CLI
│   ├── __init__.py
│   ├── app.py
│   ├── commands/
│   │   ├── get.py
│   │   ├── list.py
│   │   ├── test.py
│   │   └── op.py
│   └── utils.py
│
├── services/             # Сервисы
│   ├── __init__.py
│   ├── scheduler.py      # Планировщик
│   ├── health.py         # Health monitoring
│   └── slo.py            # SLO monitoring
│
└── utils/                # Утилиты
    ├── __init__.py
    ├── logging.py
    └── helpers.py
```

---

## 🚀 План миграции

### Этап 1: Подготовка (v3.2)
- [ ] Добавить `DeprecationWarning` для старого API
- [ ] Создать новую структуру папок
- [ ] Перенести типы в `types.py`

### Этап 2: Рефакторинг ядра (v3.3)
- [ ] Создать `core/base.py` с async реализацией
- [ ] Обернуть в синхронный фасад
- [ ] Обновить тесты

### Этап 3: Модуляризация CLI (v3.4)
- [ ] Разделить `cli.py` на модули
- [ ] Добавить подкоманды
- [ ] Протестировать

### Этап 4: Разделение ответственности (v4.0)
- [ ] Выделить `Collector`, `Validator`, `Scorer`
- [ ] Внедрить Dependency Injection
- [ ] Обновить документацию

### Этап 5: Публикация (v4.0.0)
- [ ] Обновить README
- [ ] Написать migration guide
- [ ] Опубликовать на PyPI

---

## 📈 Ожидаемые улучшения

| Метрика | До | После |
|---------|-----|-------|
| Строк в CLI | 755 | ~100 на модуль |
| Дублирование кода | 60% | <10% |
| Время инициализации | 500ms | 50ms (lazy) |
| Покрытие тестами | 32% | 80%+ |
| Размер `__init__.py` | 120 строк | 30 строк |

---

## ✅ Чек-лист для каждого модуля

- [ ] Единая ответственность (SRP)
- [ ] Dependency Injection
- [ ] Type hints для всех параметров
- [ ] Docstrings с примерами
- [ ] Юнит-тесты >80% coverage
- [ ] Логирование через `logging.getLogger(__name__)`
- [ ] Обработка ошибок с конкретными исключениями
- [ ] Async/await для I/O операций

---

## 📚 Референсы

Лучшие практики из:
1. **ProxyGather** - streaming pipeline, anti-bot evasion
2. **ProxyManager** - асинхронное ядро, scoring система
3. **httpx** - современный async HTTP клиент
4. **typer** - структура CLI приложений
