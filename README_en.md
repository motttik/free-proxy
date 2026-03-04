# 🌐 Free Proxy v2.0

**Get working free proxies from 50+ sources**

[![Version](https://img.shields.io/pypi/v/free-proxy.svg)](https://pypi.org/project/free-proxy/)
[![Python Versions](https://img.shields.io/pypi/pyversions/free-proxy.svg)](https://pypi.org/project/free-proxy/)
[![License](https://img.shields.io/pypi/l/free-proxy.svg)](https://github.com/motttik/free-proxy/blob/master/LICENSE)
[![Downloads](https://pepy.tech/badge/free-proxy)](https://pepy.tech/project/free-proxy)

[![CI/CD](https://github.com/motttik/free-proxy/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/motttik/free-proxy/actions/workflows/ci-cd.yml)

---

## 🚀 Quick Start

```bash
# Installation
pip install free-proxy

# Python usage
from fp import FreeProxy

proxy = FreeProxy(country_id=['US'], timeout=1.0, rand=True).get()
print(proxy)  # http://1.2.3.4:8080

# CLI usage
fp get
fp get -c US -t 1.0 -r
fp get -n 10 -f json
```

---

## 📦 Features v2.0

### ✨ What's New in 2.0

- **53 proxy sources** (GitHub, API, HTML sites)
- **SOCKS4/SOCKS5** support
- **Async mode** (check 100 proxies in ~10 sec)
- **CLI interface** with autocomplete
- **Caching** with TTL
- **Type hints** for better IDE support
- **Docker** images
- **CI/CD** with GitHub Actions

### 🔧 Protocols

| Protocol | Support | Sources |
|----------|---------|---------|
| HTTP | ✅ | 35+ |
| HTTPS | ✅ | 35+ |
| SOCKS4 | ✅ | 15+ |
| SOCKS5 | ✅ | 15+ |

---

## 📖 Installation

### Basic

```bash
pip install free-proxy
```

### With Extras

```bash
# SOCKS support
pip install free-proxy[socks]

# Progress bar for async
pip install free-proxy[progress]

# For development
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

## 💡 Usage Examples

### Basic

```python
from fp import FreeProxy

# Get one proxy
proxy = FreeProxy().get()
print(proxy)

# Get 10 proxies
proxies = FreeProxy(rand=True).get(count=10)
print(proxies)
```

### Filters

```python
# Proxies from specific countries
proxy = FreeProxy(country_id=['US', 'GB', 'DE']).get()

# Only elite proxies
proxy = FreeProxy(elite=True).get()

# Only anonymous
proxy = FreeProxy(anonym=True).get()

# Only HTTPS
proxy = FreeProxy(https=True).get()

# Random selection
proxy = FreeProxy(rand=True, timeout=2.0).get()
```

### Async Mode

```python
import asyncio
from fp import AsyncFreeProxy

async def main():
    # Fast check (100 proxies in ~10 sec)
    proxy = await AsyncFreeProxy().get()
    print(proxy)

    # 20 proxies with progress bar
    proxies = await AsyncFreeProxy().get(count=20, show_progress=True)
    print(proxies)

asyncio.run(main())
```

### CLI

```bash
# Get proxy
fp get
fp get -c US -t 1.0 -r

# Get 10 proxies in JSON
fp get -n 10 -f json

# List sources
fp list
fp sources -p socks5

# Test proxy
fp test 1.2.3.4:8080
```

### Selenium Integration

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

## 📚 API Documentation

### FreeProxy Class

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `country_id` | `list[str]` | `None` | Country codes (['US', 'GB']) |
| `timeout` | `float` | `0.5` | Check timeout in seconds |
| `rand` | `bool` | `False` | Shuffle proxies before checking |
| `anonym` | `bool` | `False` | Only anonymous proxies |
| `elite` | `bool` | `False` | Only elite proxies |
| `google` | `bool` | `None` | Only Google-supporting proxies |
| `https` | `bool` | `False` | Only HTTPS proxies |
| `protocol` | `str` | `None` | http/https/socks4/socks5 |
| `url` | `str` | `httpbin.org/ip` | Test URL |
| `max_concurrent` | `int` | `20` | Max concurrent checks |
| `cache_ttl` | `int` | `300` | Cache TTL in seconds |

### Methods

```python
# Get proxy
proxy = FreeProxy().get()              # str
proxies = FreeProxy().get(count=10)    # list[str]

# Get all proxies
proxy_list = FreeProxy().get_proxy_list()  # list[str]

# Clear cache
FreeProxy().clear_cache()

# Get sources
sources = FreeProxy().get_all_sources()  # list[dict]
```

---

## 🌍 Sources (53)

### GitHub Raw (17 sources)

- TheSpeedX/PROXY-List (http, socks4, socks5)
- monosans/proxy-list (http, socks4, socks5)
- clarketm/proxy-list
- Sunny9577/proxy-scraper
- JetKai/proxy-list
- ShiftyTR/Proxy-List (http, https, socks4, socks5)
- miyukii-chan/ProxyList
- roosterkid/openproxylist

### API (9 sources)

- ProxyScrape API (http, socks4, socks5)
- ProxyList Download API (http, socks4, socks5)
- OpenProxy Space API

### HTML Sites (7 sources)

- sslproxies.org
- us-proxy.org
- free-proxy-list.net
- free-proxy-list.net/uk-proxy.html
- spys.one
- spys.one/socks
- geonode.com

---

## 🧪 Testing

```bash
# Install dependencies
pip install -r requirements-dev.txt

# Run tests
pytest -v

# With coverage
pytest -v --cov=fp

# Specific test
pytest tests/test_proxy.py::TestProxyModel -v
```

---

## 🐳 Docker

```bash
# Build
docker build -t free-proxy .

# Run
docker run --rm free-proxy get -n 5

# Development
docker-compose run test
docker-compose run shell
```

---

## 📊 Version Comparison

| Feature | v1.x | v2.0 |
|---------|------|------|
| Sources | 4 | **53** |
| Protocols | HTTP/HTTPS | **HTTP/HTTPS/SOCKS4/SOCKS5** |
| Check Speed | ~50 sec (100) | **~10 sec** (async) |
| CLI | ❌ | ✅ typer |
| Type hints | ❌ | ✅ Python 3.8+ |
| Caching | ❌ | ✅ TTL |
| Docker | ❌ | ✅ multi-stage |
| CI/CD | ❌ | ✅ GitHub Actions |

---

## 🤝 Contributing

```bash
# Fork and clone
git clone https://github.com/motttik/free-proxy.git
cd free-proxy

# Virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Make changes
git checkout -b feature/my-feature

# Tests
pytest -v

# Commit
git commit -m "feat: add my feature"
git push origin feature/my-feature
```

---

## 📝 Changelog

### v2.0.0 (2026-03-04)

**Complete project rewrite**

- ✨ 53 proxy sources
- ✨ SOCKS4/SOCKS5 support
- ✨ AsyncFreeProxy class
- ✨ CLI interface (typer)
- ✨ Caching with TTL
- ✨ Type hints
- ✨ Docker images
- ✨ CI/CD pipeline

### v1.1.3 (2024-11-07)

- Added `url` parameter

[Full changelog](CHANGELOG.md)

---

## ⚠️ Disclaimer

The author is not responsible for any consequences resulting from the use of this software.
Users are solely responsible for their actions.

Free proxies may be unstable and insecure.
Do not use for sensitive data.

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

## 👥 Author

**motttik**

---

## 📞 Contacts

- **GitHub:** https://github.com/motttik/free-proxy
- **PyPI:** https://pypi.org/project/free-proxy/
- **Issues:** https://github.com/motttik/free-proxy/issues

---

**Made with ❤️ by motttik**
