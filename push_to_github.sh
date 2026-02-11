#!/bin/bash

# Скрипт для отправки кода на GitHub

cd "/Users/aleksandrbojko/Documents/LAppka (перед деплоем, копия мак)"

echo "📤 Отправка проекта на GitHub..."
echo ""

# Проверить, есть ли remote
if git remote get-url origin &>/dev/null; then
    echo "✅ Remote уже настроен:"
    git remote -v
    echo ""
else
    echo "🔗 Привязка к GitHub репозиторию..."
    if git remote add origin https://github.com/bagladin/LAppka.git 2>/dev/null; then
        echo "✅ Remote добавлен"
    else
        echo "⚠️  Remote уже существует, обновляю URL..."
        git remote set-url origin https://github.com/bagladin/LAppka.git
        echo "✅ Remote обновлен"
    fi
    echo ""
fi

# Показать текущую ветку
echo "🌿 Текущая ветка: $(git branch --show-current)"
echo ""

# Отправить код
echo "📤 Отправка кода на GitHub..."
echo "⚠️  Если попросит аутентификацию:"
echo "   - Username: bagladin"
echo "   - Password: используйте Personal Access Token (не пароль!)"
echo ""

git push -u origin main

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Успешно! Проект размещен на GitHub:"
    echo "   https://github.com/bagladin/LAppka"
else
    echo ""
    echo "❌ Ошибка при отправке. Возможные причины:"
    echo "   1. Репозиторий еще не создан на GitHub"
    echo "   2. Неверные учетные данные"
    echo "   3. Нужен Personal Access Token вместо пароля"
    echo ""
    echo "Создайте токен: GitHub → Settings → Developer settings"
    echo "→ Personal access tokens → Tokens (classic) → Generate new token"
fi
