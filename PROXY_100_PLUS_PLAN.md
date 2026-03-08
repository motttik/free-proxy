# 🎯 План достижения 100+ рабочих прокси

## 📊 Текущая ситуация

**Проблема**: Пользователь сообщает о недостаточном количестве рабочих прокси (<100)

**Анализ**:
- 53 источника в конфигурации
- Не все источники активны
- Некоторые источники требуют browser automation
- Нет автоматического обновления списков

---

## 🔍 Анализ источников (по категориям)

### 1. GitHub Raw (17 источников) - ✅ Стабильные
**Доступность**: 95%+  
**Обновление**: каждые 30-60 мин  
**Проблема**: Некоторые репозитории удалены/закрыты

**Топ источников**:
1. TheSpeedX/PROXY-List (http, socks4, socks5) - ✅
2. monosans/proxy-list - ✅
3. clarketm/proxy-list - ⚠️ Иногда недоступен
4. JetKai/proxy-list - ❌ Удален
5. ShiftyTR/Proxy-List - ⚠️ Редко обновляется

### 2. API Endpoints (9 источников) - ⚠️ Средняя стабильность
**Доступность**: 70-80%  
**Проблема**: Rate limiting, CORS

**Топ источников**:
1. ProxyScrape API - ✅
2. ProxyList Download API - ✅
3. OpenProxy Space API - ⚠️ Rate limit

### 3. HTML Sites (7 источников) - ❌ Нестабильные
**Доступность**: 50-60%  
**Проблема**: Требуется browser automation, капчи

**Топ источников**:
1. sslproxies.org - ⚠️ Капча
2. us-proxy.org - ⚠️ Капча
3. free-proxy-list.net - ❌ Блокирует скраперы
4. spys.one - ❌ Сложная защита

---

## 💡 Решения для увеличения количества прокси

### Решение 1: Добавить новые источники (+30-50 прокси)

#### Новые GitHub источники:
```python
# miyukii-chan/ProxyList
{
    "name": "miyukii-chan HTTP",
    "url": "https://raw.githubusercontent.com/miyukii-chan/ProxyList/main/http.txt",
    "type": SourceType.GITHUB_RAW,
    "protocols": [SourceProtocol.HTTP, SourceProtocol.HTTPS],
},

# roosterkid/openproxylist
{
    "name": "roosterkid HTTP",
    "url": "https://raw.githubusercontent.com/roosterkid/openproxylist/main/proxies/http.txt",
    "type": SourceType.GITHUB_RAW,
    "protocols": [SourceProtocol.HTTP, SourceProtocol.HTTPS],
},

# ZeroDot1/ProxyList
{
    "name": "ZeroDot1 HTTP",
    "url": "https://raw.githubusercontent.com/ZeroDot1/ProxyList/main/http.txt",
    "type": SourceType.GITHUB_RAW,
    "protocols": [SourceProtocol.HTTP],
},
```

#### Новые API:
```python
# ProxyDB API
{
    "name": "ProxyDB",
    "url": "https://proxydb.net/api/proxies",
    "type": SourceType.API_JSON,
    "protocols": [SourceProtocol.HTTP, SourceProtocol.HTTPS],
},

# Geonode API
{
    "name": "Geonode Free",
    "url": "https://proxylist.geonode.com/api/proxy-list",
    "type": SourceType.API_JSON,
    "protocols": [SourceProtocol.HTTP, SourceProtocol.HTTPS],
},
```

### Решение 2: Улучшить валидацию (+20-30% рабочих)

**Текущая проблема**: Строгая валидация отбрасывает рабочие прокси

**Предложения**:
1. **Двухуровневая валидация**:
   - Stage A: Быстрая проверка (IP + порт)
   - Stage B: Полная проверка (реальный запрос)

2. **Grace period для новых прокси**:
   - Не отбрасывать после первой неудачи
   - Давать 3 попытки перед баном

3. **Адаптивный таймаут**:
   - Для SOCKS: 10 сек
   - Для HTTP: 5 сек
   - Для HTTPS: 8 сек

### Решение 3: Автоматическое обновление (+50% доступности)

**GitHub Actions workflow**:
```yaml
name: Update Proxy Lists

on:
  schedule:
    - cron: '*/30 * * * *'  # Каждые 30 минут
  workflow_dispatch:

jobs:
  update-proxies:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Run proxy collector
        run: |
          python -m fp.cli get -n 1000 -f json > proxies.json
      
      - name: Commit updated proxies
        run: |
          git add proxies.json
          git commit -m "chore: update proxy list [skip ci]"
          git push
```

### Решение 4: Умный scoring (+40% качества)

**Формула scoring**:
```python
score = (
    0.30 * uptime_rate +      # Процент успешных проверок
    0.25 * latency_score +    # Обратная задержка (1000 / (latency + 1))
    0.25 * success_rate +     # Процент успешных запросов
    0.20 * freshness_score    # Время с последней проверки
)
```

**Пороги**:
- HOT (80-100): Использовать в первую очередь
- WARM (50-79): Резервные прокси
- QUARANTINE (0-49): На перепроверку

---

## 📈 Ожидаемые результаты

| Решение | Дополнительные прокси | Время реализации |
|---------|----------------------|------------------|
| Новые источники | +50-80 | 1 день |
| Улучшение валидации | +20-30% | 2 дня |
| Авто-обновление | +50% доступность | 1 день |
| Умный scoring | +40% качества | 2 дня |
| **ИТОГО** | **150-200+** | **6 дней** |

---

## 🚀 Приоритетный план (MVP за 1 день)

### Шаг 1: Добавить 10 новых GitHub источников
```bash
# Файл: fp/config.py
# Добавить в GITHUB_SOURCES:
- miyukii-chan/ProxyList
- roosterkid/openproxylist
- ZeroDot1/ProxyList
- TheBlaCkCoDeR/proxy-list
- obroslab/proxy-list
- ...
```

### Шаг 2: Увеличить таймауты
```python
# fp/core.py
timeout=5.0  # было 0.5
```

### Шаг 3: Grace period для новых прокси
```python
# fp/validator.py
if proxy.check_count < 3:
    # Давать шанс новым прокси
    min_score = 30  # вместо 50
```

### Шаг 4: Кэширование результатов
```python
# fp/core.py
cache_ttl=600  # 10 минут вместо 5
```

---

## 🎯 Конкретные метрики

**Цель**: 100+ рабочих прокси

**Метрики**:
- [ ] 50+ HOT прокси (score 80-100)
- [ ] 30+ WARM прокси (score 50-79)
- [ ] <20 QUARANTINE прокси
- [ ] Средняя задержка <500ms
- [ ] Uptime >80%

---

## 📝 Чек-лист реализации

- [ ] Добавить 10 новых GitHub источников
- [ ] Увеличить default timeout до 5.0
- [ ] Реализовать grace period для новых прокси
- [ ] Настроить кэширование на 10 минут
- [ ] Запустить тестовый сбор прокси
- [ ] Проверить количество рабочих
- [ ] При необходимости добавить еще источники

---

**Автор**: motttik  
**Дата**: 2026-03-08  
**Цель**: 100+ рабочих прокси к v3.1
