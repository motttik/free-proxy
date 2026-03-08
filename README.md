# 🌐 Free Proxy v2.0

**Получение рабочих бесплатных прокси с 50+ источников**

[![Version](https://img.shields.io/pypi/v/free-proxy.svg)](https://pypi.org/project/free-proxy/)
[![Python Versions](https://img.shields.io/pypi/pyversions/free-proxy.svg)](https://pypi.org/project/free-proxy/)
[![License](https://img.shields.io/pypi/l/free-proxy.svg)](https://github.com/motttik/free-proxy/blob/master/LICENSE)

[![CI/CD](https://github.com/motttik/free-proxy/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/motttik/free-proxy/actions/workflows/ci-cd.yml)

---

## 🚀 Быстрый старт

```bash
# Установка
pip install free-proxy

# Использование в Python
from fp import FreeProxy

proxy = FreeProxy(country_id=['US'], timeout=1.0, rand=True).get()
print(proxy)  # http://1.2.3.4:8080

# CLI использование
fp get
fp get -c US -t 1.0 -r
fp get -n 10 -f json
```

---

## 📦 Возможности v2.0

### ✨ Новое в версии 2.0

- **56+ источников** прокси (GitHub, API, HTML, Premium Leak)
- **SOCKS4/SOCKS5** поддержка
- **Асинхронный режим** (проверка 100 прокси за ~10 сек)
- **CLI интерфейс** с автодополнением
- **Кэширование** результатов
- **Type hints** для лучшей IDE поддержки
- **Docker** образы
- **CI/CD** с GitHub Actions

### 🔧 Протоколы

| Протокол | Поддержка | Источников |
|----------|-----------|------------|
| HTTP | ✅ | 35+ |
| HTTPS | ✅ | 35+ |
| SOCKS4 | ✅ | 15+ |
| SOCKS5 | ✅ | 15+ |

---

## 📖 Установка

### Базовая установка

```bash
pip install free-proxy
```

### С дополнительными возможностями

```bash
# SOCKS поддержка
pip install free-proxy[socks]

# Прогресс-бар для async
pip install free-proxy[progress]

# Для разработки
pip install free-proxy[dev]
```

### Docker

```bash
# Pull
docker pull ghcr.io/motttik/free-proxy:latest

# Run
docker run --rm free-proxy get -n 5
```

---

## 💡 Примеры использования

### Базовое

```python
from fp import FreeProxy

# Получить одну прокси
proxy = FreeProxy().get()
print(proxy)

# Получить 10 прокси
proxies = FreeProxy(rand=True).get(count=10)
print(proxies)
```

### Фильтры

```python
# Прокси из конкретных стран
proxy = FreeProxy(country_id=['US', 'GB', 'DE']).get()

# Только элитные
proxy = FreeProxy(elite=True).get()

# Только анонимные
proxy = FreeProxy(anonym=True).get()

# Только HTTPS
proxy = FreeProxy(https=True).get()

# Случайный выбор
proxy = FreeProxy(rand=True, timeout=2.0).get()
```

### Асинхронный режим

```python
import asyncio
from fp import AsyncFreeProxy

async def main():
    # Быстрая проверка (100 прокси за ~10 сек)
    proxy = await AsyncFreeProxy().get()
    print(proxy)

    # 20 прокси с прогресс-баром
    proxies = await AsyncFreeProxy().get(count=20, show_progress=True)
    print(proxies)

asyncio.run(main())
```

### CLI

```bash
# Получить прокси
fp get
fp get -c US -t 1.0 -r

# Получить 10 прокси в JSON
fp get -n 10 -f json

# Список источников
fp list
fp sources -p socks5

# Проверить прокси
fp test 1.2.3.4:8080
```

### Selenium интеграция

```python
from fp import FreeProxy
from selenium import webdriver

proxy = FreeProxy().get()
proxy_server = proxy.replace('http://', '')

options = webdriver.ChromeOptions()
options.add_argument(f'--proxy-server={proxy_server}')

driver = webdriver.Chrome(options=options)
driver.get('https://httpbin.org/ip')
```

---

## 📚 API Документация

### FreeProxy Класс

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| `country_id` | `list[str]` | `None` | Список кодов стран (['US', 'GB']) |
| `timeout` | `float` | `0.5` | Таймаут проверки в секундах |
| `rand` | `bool` | `False` | Перемешать прокси перед проверкой |
| `anonym` | `bool` | `False` | Только анонимные прокси |
| `elite` | `bool` | `False` | Только элитные прокси |
| `google` | `bool` | `None` | Только с поддержкой Google |
| `https` | `bool` | `False` | Только HTTPS прокси |
| `protocol` | `str` | `None` | http/https/socks4/socks5 |
| `url` | `str` | `httpbin.org/ip` | URL для проверки |
| `max_concurrent` | `int` | `20` | Макс. одновременных проверок |
| `cache_ttl` | `int` | `300` | Время жизни кэша (сек) |

### Методы

```python
# Получить прокси
proxy = FreeProxy().get()              # str
proxies = FreeProxy().get(count=10)    # list[str]

# Получить список всех прокси
proxy_list = FreeProxy().get_proxy_list()  # list[str]

# Очистить кэш
FreeProxy().clear_cache()

# Получить источники
sources = FreeProxy().get_all_sources()  # list[dict]
```

---

## 🌍 Источники (56+)

### GitHub Raw (17 источников)

- TheSpeedX/PROXY-List (http, socks4, socks5)
- monosans/proxy-list (http, socks4, socks5)
- clarketm/proxy-list
- Sunny9577/proxy-scraper
- JetKai/proxy-list
- ShiftyTR/Proxy-List (http, https, socks4, socks5)

### API (9 источников)

- ProxyScrape API (http, socks4, socks5)
- ProxyList Download API (http, socks4, socks5)
- OpenProxy Space API

### HTML Сайты (7 источников)

- sslproxies.org
- us-proxy.org
- free-proxy-list.net
- free-proxy-list.net/uk-proxy.html

### 💎 Premium Leak (3+ источника)

"Слитые" платные прокси из GitHub Gist, Pastebin и других источников.

- GitHub Gist - Premium Proxy Lists
- Pastebin - Datacenter Proxies
- GitHub Gist - Residential Proxies

**Преимущества:**
- Качество: 60-90% uptime (vs 10-30% у бесплатных)
- Latency: 50-300ms (vs 500-5000ms у бесплатных)
- Success rate: 40-70% (vs 5-20% у бесплатных)

**⚠️ Предупреждение:** Некоторые источники могут нарушать ToS сервисов. Используйте на свой страх и риск.

---

## 🧪 Тесты

```bash
# Установка зависимостей
pip install -r requirements-dev.txt

# Запуск тестов
pytest -v

# С покрытием
pytest -v --cov=fp

# Конкретный тест
pytest tests/test_proxy.py::TestProxyModel -v

# Smoke тесты (E2E проверка реальных прокси)
pytest tests/test_smoke.py -v
```

---

## 🐳 Docker

```bash
# Сборка
docker build -t free-proxy .

# Запуск
docker run --rm free-proxy get -n 5

# Development
docker-compose run test
docker-compose run shell
```

---

## 📊 Сравнение версий

| Функция | v1.x | v2.0 |
|---------|------|------|
| Источников | 4 | **53** |
| Протоколы | HTTP/HTTPS | **HTTP/HTTPS/SOCKS4/SOCKS5** |
| Проверка | ~50 сек (100 шт) | **~10 сек** (async) |
| CLI | ❌ | ✅ typer |
| Type hints | ❌ | ✅ Python 3.8+ |
| Кэширование | ❌ | ✅ TTL |
| Docker | ❌ | ✅ multi-stage |
| CI/CD | ❌ | ✅ GitHub Actions |

---

## 🤝 Вклад

```bash
# Fork и clone
git clone https://github.com/motttik/free-proxy.git
cd free-proxy

# Виртуальное окружение
python -m venv .venv
source .venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Внесение изменений
git checkout -b feature/my-feature

# Тесты
pytest -v

# Smoke тест (E2E проверка реальных прокси)
# Базовый: preflight OFF (быстрее для бесплатных прокси)
python scripts/smoke_runner.py --n 10 --timeout 8

# Smoke тест с preflight (для быстрых/платных прокси)
python scripts/smoke_runner.py --n 10 --timeout 5 --preflight

# Smoke тест без adaptive timeout
python scripts/smoke_runner.py --n 10 --timeout 8 --no-adaptive-timeout

# Smoke тесты (pytest)
pytest tests/test_smoke.py -v

# Быстрая коллекция прокси для тестов (обновляет last_live_check)
python quick_collect.py

# Пересборка пулов из карантина
python rebuild_pools.py

# Проверка БД (last_live_check)
python -c "
import asyncio
from fp.database import ProxyDatabase
async def check():
    async with ProxyDatabase() as db:
        cursor = await db._conn.execute('SELECT COUNT(*) FROM proxies WHERE last_live_check IS NOT NULL')
        print(f'last_live_check NOT NULL: {(await cursor.fetchone())[0]}')
        stats = await db.get_stats()
        print(f'HOT: {stats[\"hot_count\"]}, WARM: {stats.get(\"warm_count\", 0)}, TOTAL: {stats[\"total_proxies\"]}')
asyncio.run(check())
"

# Commit
git commit -m "feat: add my feature"
git push origin feature/my-feature
```

---

## 📝 Changelog

### v2.0.0 (2026-03-04)

**Полная переработка проекта**

- ✨ 56+ источников прокси
- ✨ SOCKS4/SOCKS5 поддержка
- ✨ AsyncFreeProxy класс
- ✨ CLI интерфейс (typer)
- ✨ Кэширование результатов
- ✨ Type hints
- ✨ Docker образы
- ✨ CI/CD pipeline

### v1.1.3 (2024-11-07)

- Добавлен параметр `url`

[Полный changelog](CHANGELOG.md)

---

## ⚠️ Disclaimer

Автор не несёт ответственности за последствия использования данного ПО.
Пользователи несут полную ответственность за свои действия.

Бесплатные прокси могут быть нестабильными и небезопасными.
Не используйте для конфиденциальных данных.

---

## 📄 License

[MIT License](LICENSE)

```
Copyright (c) 2019-2026 motttik

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction...
```

---

## 👥 Автор

**motttik**

---

## 📞 Контакты

- **GitHub:** https://github.com/motttik/free-proxy
- **PyPI:** https://pypi.org/project/free-proxy/
- **Issues:** https://github.com/motttik/free-proxy/issues

---

**Made with ❤️ by motttik**
