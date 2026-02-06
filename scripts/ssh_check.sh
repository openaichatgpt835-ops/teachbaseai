#!/bin/bash
# Скрипт проверки SSH подключения к серверу
# Использование: ./scripts/ssh_check.sh [SERVER]

SERVER=${1:-"root@SERVER"}

echo "Проверка SSH подключения к $SERVER..."
echo ""

# Проверка доступности хоста
if ssh -o ConnectTimeout=5 -o BatchMode=yes "$SERVER" "echo 'SSH connection OK'" 2>/dev/null; then
    echo "✅ SSH подключение успешно"
    
    # Проверка Docker
    if ssh "$SERVER" "command -v docker >/dev/null 2>&1"; then
        DOCKER_VERSION=$(ssh "$SERVER" "docker --version")
        echo "✅ Docker установлен: $DOCKER_VERSION"
    else
        echo "❌ Docker не установлен"
    fi
    
    # Проверка Docker Compose
    if ssh "$SERVER" "docker compose version >/dev/null 2>&1"; then
        COMPOSE_VERSION=$(ssh "$SERVER" "docker compose version")
        echo "✅ Docker Compose установлен: $COMPOSE_VERSION"
    else
        echo "❌ Docker Compose не установлен"
    fi
    
    # Проверка директорий
    if ssh "$SERVER" "test -d /opt/knowledge-app"; then
        echo "✅ /opt/knowledge-app существует"
    else
        echo "⚠️  /opt/knowledge-app не существует"
    fi
    
    if ssh "$SERVER" "test -d /opt/supabase"; then
        echo "✅ /opt/supabase существует"
    else
        echo "⚠️  /opt/supabase не существует"
    fi
else
    echo "❌ Не удалось подключиться по SSH"
    echo "Проверьте:"
    echo "  - SSH ключи/настройки"
    echo "  - Адрес сервера: $SERVER"
    echo "  - Доступность сервера"
    exit 1
fi
