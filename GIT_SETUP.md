# 🔧 Настройка для автоматического Git

## Проблема
SSH агент не запущен в текущей сессии. Нужно один раз настроить.

## Решение 1: Запустить SSH агент (рекомендуется)

```bash
# Запустить агент и добавить ключ
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519

# Проверить
ssh-add -l

# Теперь пуш должен работать
cd /mnt/Storage/linux/VSCode/Projects/05_Tools/free-proxy
git push -u origin master --tags
```

## Решение 2: Использовать токен GitHub

```bash
# Создать токен: https://github.com/settings/tokens/new
# Выбрать scopes: repo, workflow, write:packages

# Сохранить токен
git config --global credential.helper store

# Первый пуш запросит логин/пароль
# В качестве пароля вставь токен

# Дальше будет работать автоматически
git push -u origin master --tags
```

## Решение 3: Настроить автозапуск ssh-agent

Добавь в `~/.bashrc` или `~/.zshrc`:

```bash
# Автозапуск ssh-agent
if [ -z "$SSH_AUTH_SOCK" ]; then
    eval "$(ssh-agent -s)"
    ssh-add ~/.ssh/id_ed25519 2>/dev/null
fi
```

После перезапуска терминала:
```bash
git push -u origin master --tags
```

---

## После успешного пуша

1. ✅ Открой https://github.com/motttik/free-proxy
2. ✅ Проверь что файлы на месте
3. ✅ GitHub Actions автоматически запустит тесты
4. ✅ Создай релиз v2.0.0 для публикации на PyPI

## Как сделать чтобы Qwen Code пушил сам

После настройки SSH агента или токена, просто скажи:

> "Запуши изменения на GitHub"

И я выполню:
```bash
git add .
git commit -m "описание изменений"
git push origin master
```
