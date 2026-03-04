# 🚀 Инструкция по публикации на GitHub

## Локальная проверка

```bash
cd /mnt/Storage/linux/VSCode/Projects/05_Tools/free-proxy

# Активировать окружение
source .venv/bin/activate

# Запустить тесты
pytest -v

# Проверить CLI
fp --help
fp get -n 3

# Проверить импорт
python -c "from fp import FreeProxy; print('OK')"
```

## Публикация на GitHub

### Вариант 1: Через HTTPS

```bash
# Настроить git (если не настроен)
git config --global user.name "Ваше Имя"
git config --global user.email "your@email.com"

# Пуш с токеном
git remote set-url origin https://YOUR_TOKEN@github.com/YOUR_USERNAME/free-proxy.git
git push origin master --tags
```

### Вариант 2: Через SSH

```bash
# Настроить SSH ключ (если не настроен)
ssh-keygen -t ed25519 -C "your@email.com"
# Добавить публичный ключ в GitHub Settings → SSH Keys

# Пуш
git remote set-url origin git@github.com:YOUR_USERNAME/free-proxy.git
git push origin master --tags
```

### Вариант 3: Через GitHub Desktop

1. Откройте репозиторий в GitHub Desktop
2. Нажмите "Push origin"
3. Теги будут отправлены автоматически

## Публикация на PyPI

### Подготовка

```bash
# Установить build
pip install build twine

# Собрать пакет
python -m build

# Проверить dist/
ls -la dist/
# free_proxy-2.0.0-py3-none-any.whl
# free_proxy-2.0.0.tar.gz
```

### Публикация

```bash
# TestPyPI (тестирование)
twine upload --repository testpypi dist/*

# PyPI (продакшен)
twine upload dist/*
```

### Через GitHub Actions

Автоматическая публикация происходит при создании тега:

1. Создайте релиз на GitHub с тегом `v2.0.0`
2. GitHub Actions автоматически опубликует на PyPI

## Проверка после публикации

### PyPI

```bash
# Установить из PyPI
pip install free-proxy --upgrade

# Проверить версию
python -c "from fp import __version__; print(__version__)"
```

### Docker

```bash
# Собрать образ
docker build -t free-proxy:2.0.0 .

# Запустить
docker run --rm free-proxy get -n 5
```

## Чек-лист публикации

- [ ] Все тесты проходят (`pytest -v`)
- [ ] CLI работает (`fp --help`)
- [ ] README обновлён
- [ ] CHANGELOG обновлён
- [ ] Версия в `fp/__init__.py` обновлена
- [ ] Тег создан (`git tag v2.0.0`)
- [ ] Пуш на GitHub выполнен
- [ ] PyPI публикация выполнена
- [ ] Docker образ собран

## Ссылки

- **GitHub:** https://github.com/jundymek/free-proxy
- **PyPI:** https://pypi.org/project/free-proxy/
- **Issues:** https://github.com/jundymek/free-proxy/issues
