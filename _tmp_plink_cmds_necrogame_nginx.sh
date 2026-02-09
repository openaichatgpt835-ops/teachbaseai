set -e
cat > /etc/nginx/sites-available/necrogame.ru <<'NGINX'
# Host nginx config для necrogame.ru
# Разместить в /etc/nginx/sites-available/necrogame.ru
# Публично: /health, /api/health, /api/v1/bitrix/* (HTTPS)
# Админка НЕ публикуется (доступ через SSH-туннель localhost:3000)

server {
    server_name necrogame.ru www.necrogame.ru;
    listen 443 ssl;
    ssl_certificate /etc/letsencrypt/live/necrogame.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/necrogame.ru/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    client_max_body_size 500M;

    location = /health {
        proxy_pass http://127.0.0.1:8080/health;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location = /api/health {
        proxy_pass http://127.0.0.1:8080/health;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location = /ready {
        proxy_pass http://127.0.0.1:8080/ready;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Каноника: /v1/bitrix/* (event URLs в imbot.register)
    location ^~ /v1/bitrix/ {
        proxy_pass http://127.0.0.1:8080/v1/bitrix/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
        proxy_connect_timeout 10s;
        proxy_send_timeout 60s;
    }

    location ^~ /v1/telegram/ {
        proxy_pass http://127.0.0.1:8080/v1/telegram/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
        proxy_connect_timeout 10s;
        proxy_send_timeout 60s;
    }

    location ^~ /api/v1/bitrix/ {
        rewrite ^/api(.*)$ $1 break;
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
        proxy_connect_timeout 10s;
        proxy_send_timeout 60s;
    }

    location ^~ /iframe/ {
        proxy_pass http://127.0.0.1:8080/iframe/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        add_header Cache-Control "no-store, no-cache, must-revalidate, proxy-revalidate";
        expires off;
    }

    location = /api/version {
        proxy_pass http://127.0.0.1:8080/health;
        proxy_set_header Host $host;
    }

    location / {
        proxy_pass http://127.0.0.1:8080/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 80;
    server_name necrogame.ru www.necrogame.ru;
    if ($host = www.necrogame.ru) {
        return 301 https://$host$request_uri;
    }
    if ($host = necrogame.ru) {
        return 301 https://$host$request_uri;
    }
    return 404;
}

NGINX
nginx -t
systemctl reload nginx
