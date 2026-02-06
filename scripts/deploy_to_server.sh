#!/bin/bash
# Скрипт деплоя на сервер
# Использование: ./scripts/deploy_to_server.sh [SERVER]

SERVER=${1:-"root@SERVER"}
REMOTE_DIR="/opt/knowledge-app"

echo "Деплой на сервер $SERVER:$REMOTE_DIR"
echo ""

# Проверка существования директории на сервере
if ! ssh "$SERVER" "test -d $REMOTE_DIR"; then
    echo "Создание директории $REMOTE_DIR..."
    ssh "$SERVER" "mkdir -p $REMOTE_DIR/n8n/data"
fi

echo "Копирование файлов..."

# Копирование docker-compose.yml
scp docker-compose.yml "$SERVER:$REMOTE_DIR/"
echo "✅ docker-compose.yml скопирован"

# Копирование .env.example
scp .env.example "$SERVER:$REMOTE_DIR/"
echo "✅ .env.example скопирован"

# Копирование backend директории
rsync -avz --exclude '__pycache__' --exclude '*.pyc' --exclude '.pytest_cache' \
    backend/ "$SERVER:$REMOTE_DIR/backend/"
echo "✅ backend/ скопирован"

echo ""
echo "✅ Деплой завершен"
echo ""
echo "Следующие шаги:"
echo "1. На сервере создать .env из .env.example:"
echo "   ssh $SERVER 'cd $REMOTE_DIR && cp .env.example .env'"
echo "2. Отредактировать .env и вставить реальные значения"
echo "3. Запустить сервисы:"
echo "   ssh $SERVER 'cd $REMOTE_DIR && docker compose up -d --build'"
