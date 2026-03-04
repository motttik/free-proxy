# 🚀 Инструкция по пушу на GitHub

Репозиторий создан: **https://github.com/motttik/free-proxy**

## Команды для пуша

```bash
cd /mnt/Storage/linux/VSCode/Projects/05_Tools/free-proxy

# 1. Настроить remote (если не настроен)
git remote set-url origin https://github.com/motttik/free-proxy.git

# Или через SSH (если настроен):
# git remote set-url origin git@github.com:motttik/free-proxy.git

# 2. Проверить статус
git status

# 3. Посмотреть логи
git log --oneline -5

# 4. Сделать пуш
git push -u origin master

# Если ветка называется main:
# git push -u origin main

# 5. Пуш с тегами
git push origin master --tags
```

## Если есть конфликт

```bash
# Получить изменения из remote
git fetch origin

# Слить с локальной веткой
git merge origin/main --allow-unrelated-histories

# Или сделать rebase
git rebase origin/main

# После разрешения конфликтов:
git push -u origin master
```

## Альтернатива: Создать новый репозиторий локально

```bash
# Удалить старый remote
git remote remove origin

# Добавить новый
git remote add origin https://github.com/motttik/free-proxy.git

# Пуш
git push -u origin master
```

## Проверка после пуша

1. Открой https://github.com/motttik/free-proxy
2. Проверь что файлы на месте
3. Проверь что README отображается
4. Создай релиз с тегом v2.0.0

---

**GitHub Actions** автоматически запустится после пуша и выполнит:
- ✅ Lint (ruff, mypy)
- ✅ Tests (pytest с матрицей Python 3.8-3.12)
- ✅ Build (wheel + sdist)
- ✅ Docker build

**При создании тега v2.0.0** автоматически опубликует на PyPI!
