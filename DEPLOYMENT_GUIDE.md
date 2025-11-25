# Руководство по развертыванию

**Версия:** 1.0  
**Дата:** 24 ноября 2024  
**Проект:** Telegram VPN Subscription Bot (Remnawave)

---

## Содержание

1. [Предварительные требования](#предварительные-требования)
2. [Развертывание через Docker](#развертывание-через-docker)
3. [Развертывание без Docker](#развертывание-без-docker)
4. [Production Checklist](#production-checklist)
5. [Мониторинг и поддержка](#мониторинг-и-поддержка)
6. [Troubleshooting](#troubleshooting)

---

## Предварительные требования

### Системные требования

**Минимальные требования:**
- CPU: 1 core
- RAM: 512 MB
- Disk: 5 GB
- OS: Linux (Ubuntu 20.04+, Debian 11+, CentOS 8+)

**Рекомендуемые для production:**
- CPU: 2+ cores
- RAM: 2 GB
- Disk: 20 GB (SSD)
- OS: Ubuntu 22.04 LTS

### Необходимое ПО

**Для Docker развертывания:**
```bash
# Docker 20.10+
docker --version

# Docker Compose 2.0+
docker compose version
```

**Для развертывания без Docker:**
```bash
# Python 3.11+
python3 --version

# PostgreSQL 14+
psql --version

# pip
pip3 --version
```

### Доступы и учетные данные

**✅ Обязательные:**
- [ ] Telegram Bot Token (от @BotFather)
- [ ] PostgreSQL database
- [ ] Remnawave Panel API URL и ключ
- [ ] Домен с HTTPS для webhooks
- [ ] Admin Telegram IDs

**⚙️ Опциональные (для платежных систем):**
- [ ] YooKassa: Shop ID и Secret Key
- [ ] CryptoPay: API Token
- [ ] FreeKassa: Merchant ID, API Key
- [ ] Telegram Stars (встроенная поддержка)
- [ ] Tribute: API Key

### Сетевые требования

**Открытые порты:**
- `8080/tcp` - Web server для webhooks (внутренний)
- `443/tcp` - HTTPS для внешних webhooks (через reverse proxy)
- `5432/tcp` - PostgreSQL (только для внутренней сети)

**Reverse Proxy (Nginx/Traefik):**
Обязателен для production для терминации SSL и проксирования на порт 8080.

---

## Развертывание через Docker

### Шаг 1: Клонирование репозитория

```bash
# Клонировать репозиторий
git clone https://github.com/machka-pasla/remnawave-tg-shop.git
cd remnawave-tg-shop

# Проверить структуру проекта
ls -la
```

**Ожидаемый вывод:**
```
drwxr-xr-x  bot/
drwxr-xr-x  config/
drwxr-xr-x  db/
drwxr-xr-x  locales/
-rw-r--r--  .env.example
-rw-r--r--  docker-compose.yml
-rw-r--r--  Dockerfile
-rw-r--r--  requirements.txt
-rw-r--r--  main.py
```

### Шаг 2: Конфигурация .env

```bash
# Создать .env из примера
cp .env.example .env

# Отредактировать конфигурацию
nano .env
```

**Минимальная конфигурация для запуска:**

```bash
# ====================================
# ОБЯЗАТЕЛЬНЫЕ ПАРАМЕТРЫ
# ====================================

# Telegram Bot
BOT_TOKEN=1234567890:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
ADMIN_IDS=123456789,987654321

# Database
POSTGRES_USER=postgres
POSTGRES_PASSWORD=CHANGE_ME_STRONG_PASSWORD_HERE
POSTGRES_HOST=remnawave-tg-shop-db
POSTGRES_PORT=5432
POSTGRES_DB=vpnbot

# Webhooks
WEBHOOK_BASE_URL=https://your-domain.com

# Panel API
PANEL_API_URL=https://panel.your-domain.com/api
PANEL_API_KEY=your_panel_api_key_here

# Языки и валюта
DEFAULT_LANGUAGE=ru
DEFAULT_CURRENCY_SYMBOL=RUB

# Поддержка
SUPPORT_LINK=https://t.me/your_support
```

**⚠️ ВАЖНО:** Измените все значения `CHANGE_ME` и placeholder'ы!

### Шаг 3: Настройка Docker Network

```bash
# Создать внешнюю сеть для Docker
docker network create remnawave-network

# Проверить создание сети
docker network ls | grep remnawave
```

**Почему внешняя сеть:**
- Позволяет другим контейнерам (Nginx, мониторинг) подключаться к боту
- Упрощает integration с существующей инфраструктурой

### Шаг 4: Запуск с docker-compose

```bash
# Запустить в фоновом режиме
docker compose up -d

# Проверить статус контейнеров
docker compose ps

# Просмотр логов
docker compose logs -f remnawave-tg-shop
```

**Ожидаемый вывод logs:**
```
remnawave-tg-shop  | INFO     Starting bot...
remnawave-tg-shop  | INFO     Database connection established
remnawave-tg-shop  | INFO     Applying migrations...
remnawave-tg-shop  | INFO     Migrations applied successfully
remnawave-tg-shop  | INFO     Starting web server on 0.0.0.0:8080
remnawave-tg-shop  | INFO     Bot started successfully
```

### Шаг 5: Применение миграций базы данных

Миграции применяются автоматически при первом запуске. Для ручного применения:

```bash
# Применить миграции вручную
docker compose exec remnawave-tg-shop python apply_migrations_auto.py

# Проверить текущую версию БД
docker compose exec remnawave-tg-shop alembic current

# Просмотреть историю миграций
docker compose exec remnawave-tg-shop alembic history
```

### Шаг 6: Проверка работоспособности

**1. Health Check endpoint:**
```bash
curl http://localhost:8080/health
```

**Ожидаемый ответ:**
```json
{"status": "ok", "timestamp": "2024-11-24T14:00:00Z"}
```

**2. Проверка контейнеров:**
```bash
docker compose ps

# Ожидается: все контейнеры в статусе "Up (healthy)"
```

**3. Проверка в Telegram:**
- Отправьте `/start` боту
- Проверьте, что получен welcome message
- Откройте админ-панель (если вы в ADMIN_IDS)

### Шаг 7: Настройка Reverse Proxy (Nginx)

**Файл:** `/etc/nginx/sites-available/vpnbot`

```nginx
# Upstream для бота
upstream vpnbot {
    server 127.0.0.1:8080;
    keepalive 32;
}

# HTTP → HTTPS redirect
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

# HTTPS server
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;

    # Webhook endpoints
    location /webhook/ {
        proxy_pass http://vpnbot;
        proxy_http_version 1.1;
        
        # Headers
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # Buffering
        proxy_buffering off;
    }

    # Health check endpoint
    location /health {
        proxy_pass http://vpnbot;
        access_log off;
    }

    # Deny all other requests
    location / {
        return 404;
    }
}
```

**Активация конфигурации:**
```bash
# Создать symlink
sudo ln -s /etc/nginx/sites-available/vpnbot /etc/nginx/sites-enabled/

# Проверить конфигурацию
sudo nginx -t

# Перезагрузить Nginx
sudo systemctl reload nginx
```

**Получить SSL сертификат (Let's Encrypt):**
```bash
# Установить certbot
sudo apt install certbot python3-certbot-nginx

# Получить сертификат
sudo certbot --nginx -d your-domain.com

# Автоматическое обновление
sudo certbot renew --dry-run
```

### Шаг 8: Проверка webhooks

```bash
# Проверить, что Telegram webhook установлен
curl https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo

# Проверить доступность webhook endpoint
curl https://your-domain.com/webhook/yookassa
# Ожидается: метод не поддерживается или 404 (это нормально для GET)
```

---

## Развертывание без Docker

### Шаг 1: Установка Python и зависимостей

```bash
# Обновить систему
sudo apt update && sudo apt upgrade -y

# Установить Python 3.11
sudo apt install software-properties-common -y
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev -y

# Проверить версию
python3.11 --version
```

### Шаг 2: Установка и настройка PostgreSQL

```bash
# Установить PostgreSQL
sudo apt install postgresql postgresql-contrib -y

# Запустить PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Создать пользователя и базу данных
sudo -u postgres psql << EOF
CREATE USER vpnbot WITH PASSWORD 'your_strong_password';
CREATE DATABASE vpnbot OWNER vpnbot;
GRANT ALL PRIVILEGES ON DATABASE vpnbot TO vpnbot;
\q
EOF

# Проверить подключение
psql -U vpnbot -d vpnbot -h localhost -c "SELECT version();"
```

### Шаг 3: Клонирование и настройка проекта

```bash
# Создать директорию для проекта
sudo mkdir -p /opt/vpnbot
sudo chown $USER:$USER /opt/vpnbot
cd /opt/vpnbot

# Клонировать репозиторий
git clone https://github.com/machka-pasla/remnawave-tg-shop.git .

# Создать виртуальное окружение
python3.11 -m venv venv

# Активировать venv
source venv/bin/activate

# Установить зависимости
pip install --upgrade pip
pip install -r requirements.txt
```

### Шаг 4: Конфигурация environment variables

```bash
# Создать .env файл
cp .env.example .env
nano .env
```

**Важные изменения для non-Docker:**
```bash
# Database (изменить host на localhost)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# Остальное аналогично Docker варианту
```

### Шаг 5: Миграции базы данных

```bash
# Активировать venv (если не активирован)
source venv/bin/activate

# Применить миграции
python apply_migrations_auto.py

# Проверить статус
alembic current
```

### Шаг 6: Создание systemd service

**Файл:** `/etc/systemd/system/vpnbot.service`

```ini
[Unit]
Description=Telegram VPN Subscription Bot
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=YOUR_USER
Group=YOUR_USER
WorkingDirectory=/opt/vpnbot
Environment="PATH=/opt/vpnbot/venv/bin"
ExecStart=/opt/vpnbot/venv/bin/python /opt/vpnbot/main.py

# Restart policy
Restart=always
RestartSec=10
StartLimitIntervalSec=0

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/vpnbot

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=vpnbot

[Install]
WantedBy=multi-user.target
```

**Активация service:**
```bash
# Заменить YOUR_USER на вашего пользователя
sudo sed -i "s/YOUR_USER/$USER/g" /etc/systemd/system/vpnbot.service

# Перезагрузить systemd
sudo systemctl daemon-reload

# Запустить service
sudo systemctl start vpnbot

# Включить автозапуск
sudo systemctl enable vpnbot

# Проверить статус
sudo systemctl status vpnbot

# Просмотр логов
sudo journalctl -u vpnbot -f
```

### Шаг 7: Настройка Nginx (аналогично Docker варианту)

См. [Шаг 7 Docker развертывания](#шаг-7-настройка-reverse-proxy-nginx)

---

## Production Checklist

### 🔒 Безопасность

- [ ] **Environment variables настроены**
  - [ ] Все секреты установлены (BOT_TOKEN, DB password, API keys)
  - [ ] Файл .env имеет права 600: `chmod 600 .env`
  - [ ] .env НЕ добавлен в git: проверить `.gitignore`

- [ ] **Database защищена**
  - [ ] Сильный пароль для PostgreSQL
  - [ ] PostgreSQL слушает только localhost (или внутреннюю сеть)
  - [ ] Firewall настроен: порт 5432 закрыт снаружи

- [ ] **HTTPS настроен**
  - [ ] SSL сертификат установлен и валидный
  - [ ] Webhook URL использует HTTPS
  - [ ] Security headers настроены в Nginx

- [ ] **Secrets rotation**
  - [ ] План ротации API ключей каждые 90 дней
  - [ ] Backup текущих секретов в безопасном хранилище

### ✅ Базы данных

- [ ] **Миграции применены**
  ```bash
  alembic current  # Должна быть latest version
  ```

- [ ] **Backup настроен**
  ```bash
  # Пример скрипта для автоматического backup
  # Добавить в cron: 0 2 * * * /opt/vpnbot/backup.sh
  ```

- [ ] **Тестовое подключение работает**
  ```bash
  psql -U vpnbot -d vpnbot -h localhost -c "SELECT 1;"
  ```

### 🏥 Health Checks

- [ ] **Health endpoint доступен**
  ```bash
  curl http://localhost:8080/health
  # Ответ: {"status": "ok"}
  ```

- [ ] **Docker health checks работают** (если используется Docker)
  ```bash
  docker compose ps
  # Ожидается: (healthy) для всех контейнеров
  ```

- [ ] **Systemd service status healthy** (если без Docker)
  ```bash
  sudo systemctl status vpnbot
  # Ожидается: Active: active (running)
  ```

### 📝 Логирование

- [ ] **Logging настроен**
  - [ ] Ротация логов включена (docker-compose.yml или logrotate)
  - [ ] Logs доступны через журнал
  - [ ] Sensitive данные маскируются

- [ ] **Log aggregation** (опционально)
  - [ ] Logs отправляются в централизованное хранилище
  - [ ] Alerting настроен на критические ошибки

### 📊 Мониторинг

- [ ] **Мониторинг запущен**
  - [ ] Health checks работают (Nginx/Docker)
  - [ ] Uptime monitoring настроен (например, UptimeRobot)
  - [ ] Resource monitoring (CPU, RAM, Disk)

- [ ] **Alerting настроен**
  - [ ] Уведомления при падении сервиса
  - [ ] Уведомления при критических ошибках
  - [ ] Contact list актуален

### 🔄 Backup & Recovery

- [ ] **Backup strategy продумана**
  - [ ] Automated PostgreSQL backups (ежедневно)
  - [ ] Retention policy определен (напр., 30 дней)
  - [ ] Backups хранятся off-site

- [ ] **Recovery tested**
  - [ ] Тестовое восстановление из backup
  - [ ] Recovery Time Objective (RTO) известен
  - [ ] Recovery Point Objective (RPO) известен

### 🚀 Performance

- [ ] **Resource limits установлены**
  - [ ] Docker memory/CPU limits (если Docker)
  - [ ] PostgreSQL connection pool настроен
  - [ ] Max connections ограничен

- [ ] **Optimization применена**
  - [ ] Connection pooling настроен
  - [ ] Indexes созданы для частых запросов
  - [ ] Cleanup tasks добавлены в cron

---

## Мониторинг и поддержка

### Логи

**Docker deployment:**
```bash
# Просмотр логов в реальном времени
docker compose logs -f remnawave-tg-shop

# Последние 100 строк логов
docker compose logs --tail=100 remnawave-tg-shop

# Логи с timestamp
docker compose logs -t remnawave-tg-shop

# Логи за последний час
docker compose logs --since 1h remnawave-tg-shop
```

**Non-Docker deployment:**
```bash
# Systemd logs
sudo journalctl -u vpnbot -f

# Последние 100 строк
sudo journalctl -u vpnbot -n 100

# Логи с фильтром по уровню
sudo journalctl -u vpnbot -p err

# Логи за период
sudo journalctl -u vpnbot --since "2024-11-24 10:00" --until "2024-11-24 12:00"
```

### Health Checks

**Manual health check:**
```bash
# Проверка web server
curl -f http://localhost:8080/health || echo "Health check failed!"

# Проверка database connection
docker compose exec remnawave-tg-shop python -c "from db.database_setup import get_session_maker; import asyncio; asyncio.run(get_session_maker())"
```

**Automated monitoring (пример с UptimeRobot):**
1. Зарегистрируйтесь на uptimerobot.com
2. Add New Monitor → HTTP(s)
3. URL: `https://your-domain.com/health`
4. Monitoring Interval: 5 minutes
5. Alert Contacts: ваш email/Telegram

### Метрики

**Disk usage:**
```bash
# Общее использование диска
df -h

# Размер базы данных
docker compose exec remnawave-tg-shop-db psql -U postgres -d vpnbot -c "SELECT pg_size_pretty(pg_database_size('vpnbot'));"

# Размер Docker volumes
docker system df -v
```

**Memory usage:**
```bash
# Общая память
free -h

# Memory по контейнерам
docker stats --no-stream
```

**Database stats:**
```bash
# Количество активных соединений
docker compose exec remnawave-tg-shop-db psql -U postgres -d vpnbot -c "SELECT count(*) FROM pg_stat_activity;"

# Размер таблиц
docker compose exec remnawave-tg-shop-db psql -U postgres -d vpnbot -c "SELECT relname, pg_size_pretty(pg_total_relation_size(relid)) FROM pg_catalog.pg_statio_user_tables ORDER BY pg_total_relation_size(relid) DESC;"
```

### Backup & Restore

**Создание backup:**
```bash
# PostgreSQL backup
docker compose exec remnawave-tg-shop-db pg_dump -U postgres vpnbot > backup_$(date +%Y%m%d_%H%M%S).sql

# Или с компрессией
docker compose exec remnawave-tg-shop-db pg_dump -U postgres vpnbot | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz
```

**Восстановление из backup:**
```bash
# Остановить бота
docker compose stop remnawave-tg-shop

# Восстановить БД
gunzip -c backup_20241124_140000.sql.gz | docker compose exec -T remnawave-tg-shop-db psql -U postgres vpnbot

# Запустить бота
docker compose start remnawave-tg-shop
```

**Automated backup script:**
```bash
#!/bin/bash
# /opt/vpnbot/backup.sh

BACKUP_DIR="/opt/backups/vpnbot"
DATE=$(date +%Y%m%d_%H%M%S)
FILENAME="vpnbot_backup_$DATE.sql.gz"

# Создать директорию
mkdir -p $BACKUP_DIR

# Backup
docker compose exec -T remnawave-tg-shop-db pg_dump -U postgres vpnbot | gzip > "$BACKUP_DIR/$FILENAME"

# Удалить backups старше 30 дней
find $BACKUP_DIR -name "vpnbot_backup_*.sql.gz" -mtime +30 -delete

echo "Backup created: $FILENAME"
```

**Добавить в crontab:**
```bash
# Открыть crontab
crontab -e

# Добавить строку (backup каждый день в 2:00 AM)
0 2 * * * /opt/vpnbot/backup.sh >> /var/log/vpnbot-backup.log 2>&1
```

---

## Troubleshooting

### Проблема: Бот не запускается

**Симптомы:**
```
Error: Failed to start bot
ConnectionError: Cannot connect to database
```

**Решение:**
```bash
# 1. Проверить, что PostgreSQL запущен
docker compose ps remnawave-tg-shop-db
# или
sudo systemctl status postgresql

# 2. Проверить логи БД
docker compose logs remnawave-tg-shop-db

# 3. Проверить connection string в .env
grep POSTGRES .env

# 4. Тестовое подключение
docker compose exec remnawave-tg-shop-db psql -U postgres -d vpnbot -c "SELECT 1;"
```

### Проблема: Webhooks не работают

**Симптомы:**
- Бот не отвечает на команды
- В логах: "Webhook verification failed"

**Решение:**
```bash
# 1. Проверить, что webhook установлен
curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo

# 2. Проверить SSL сертификат
openssl s_client -connect your-domain.com:443 -servername your-domain.com

# 3. Проверить Nginx конфигурацию
sudo nginx -t

# 4. Проверить логи Nginx
sudo tail -f /var/log/nginx/error.log

# 5. Тестовый HTTP запрос
curl -X POST https://your-domain.com/webhook/test

# 6. Пересоздать webhook
# В коде бота или вручную через API
```

### Проблема: Высокое потребление памяти

**Симптомы:**
```
OOMKilled
Memory usage: 95%
```

**Решение:**
```bash
# 1. Проверить текущее использование
docker stats --no-stream

# 2. Проверить cleanup tasks
docker compose exec remnawave-tg-shop python -c "from bot.utils.cleanup_tasks import run_all_cleanup_tasks; import asyncio; asyncio.run(run_all_cleanup_tasks(None))"

# 3. Увеличить memory limit в docker-compose.yml
# memory: 1G  # было 512M

# 4. Оптимизировать connection pool
# В db/database_setup.py уменьшить pool_size

# 5. Рестарт с очисткой
docker compose down
docker system prune -f
docker compose up -d
```

### Проблема: База данных переполнена

**Симптомы:**
```
Disk full
Database size: 15 GB
```

**Решение:**
```bash
# 1. Проверить размер таблиц
docker compose exec remnawave-tg-shop-db psql -U postgres -d vpnbot << EOF
SELECT 
  schemaname, 
  tablename, 
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 10;
EOF

# 2. Запустить cleanup tasks вручную
docker compose exec remnawave-tg-shop python -c "
from bot.utils.cleanup_tasks import run_all_cleanup_tasks
from db.database_setup import get_session_maker
import asyncio

async def main():
    session_maker = get_session_maker()
    async with session_maker() as session:
        result = await run_all_cleanup_tasks(session, log_retention_days=15, payment_archive_days=60)
        print(result)

asyncio.run(main())
"

# 3. VACUUM database
docker compose exec remnawave-tg-shop-db psql -U postgres -d vpnbot -c "VACUUM FULL ANALYZE;"
```

### Проблема: Медленные запросы

**Симптомы:**
- Response time > 2s
- Timeouts в логах

**Решение:**
```bash
# 1. Включить slow query log
docker compose exec remnawave-tg-shop-db psql -U postgres -d vpnbot << EOF
ALTER SYSTEM SET log_min_duration_statement = 1000;  -- 1 second
SELECT pg_reload_conf();
EOF

# 2. Проверить медленные запросы
docker compose exec remnawave-tg-shop-db psql -U postgres -d vpnbot -c "
SELECT query, calls, total_exec_time, mean_exec_time 
FROM pg_stat_statements 
ORDER BY mean_exec_time DESC 
LIMIT 10;
"

# 3. Добавить недостающие индексы
# Анализируется по результатам slow query log

# 4. Оптимизировать N+1 queries
# Использовать joinedload() в запросах
```

### Проблема: Не приходят платежи

**Симптомы:**
- Пользователь оплатил, но подписка не активировалась
- В логах нет webhooks от платежной системы

**Решение:**
```bash
# 1. Проверить webhook endpoints
curl https://your-domain.com/webhook/yookassa
curl https://your-domain.com/webhook/cryptopay

# 2. Проверить секреты в .env
grep YOOKASSA .env
grep CRYPTOPAY .env

# 3. Проверить логи платежных систем (в админке YooKassa/CryptoPay)

# 4. Тестовый webhook вручную
# Отправить тестовый POST запрос с payload

# 5. Проверить таблицу payments
docker compose exec remnawave-tg-shop-db psql -U postgres -d vpnbot -c "
SELECT id, user_id, amount, status, provider, created_at 
FROM payments 
ORDER BY created_at DESC 
LIMIT 10;
"
```

---

## Дополнительные ресурсы

### Полезные ссылки

- [README.md](README.md) - Основная документация проекта
- [AUDIT_REPORT.md](AUDIT_REPORT.md) - Отчет о техническом аудите
- [SECURITY_GUIDE.md](SECURITY_GUIDE.md) - Руководство по безопасности
- [MAINTENANCE_GUIDE.md](MAINTENANCE_GUIDE.md) - Руководство по поддержке
- [UPDATES_2024.md](UPDATES_2024.md) - История изменений 2024

### Команды быстрого доступа

```bash
# Перезапуск бота
docker compose restart remnawave-tg-shop

# Просмотр логов (последние 50 строк)
docker compose logs --tail=50 remnawave-tg-shop

# Shell внутри контейнера
docker compose exec remnawave-tg-shop /bin/bash

# Python REPL с контекстом бота
docker compose exec remnawave-tg-shop python

# Проверка health
curl http://localhost:8080/health

# Backup БД
docker compose exec remnawave-tg-shop-db pg_dump -U postgres vpnbot | gzip > backup.sql.gz

# Cleanup logs старше 7 дней
docker compose exec remnawave-tg-shop python -c "from bot.utils.cleanup_tasks import cleanup_old_logs; from db.database_setup import get_session_maker; import asyncio; asyncio.run(cleanup_old_logs(get_session_maker()(), days=7))"
```

---

**Версия документа:** 1.0  
**Последнее обновление:** 24 ноября 2024  
**Статус:** ФИНАЛИЗИРОВАН

*Этот документ содержит полное руководство по развертыванию проекта. Для дополнительной информации см. связанные документы.*