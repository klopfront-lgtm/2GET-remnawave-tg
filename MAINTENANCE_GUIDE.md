# Руководство по поддержке

**Версия:** 1.0  
**Дата:** 24 ноября 2024  
**Проект:** Telegram VPN Subscription Bot (Remnawave)

---

## Содержание

1. [Регулярные задачи](#регулярные-задачи)
2. [Cleanup задачи](#cleanup-задачи)
3. [Обновление зависимостей](#обновление-зависимостей)
4. [Мониторинг](#мониторинг)
5. [Backup и восстановление](#backup-и-восстановление)
6. [Troubleshooting](#troubleshooting)
7. [Performance Tuning](#performance-tuning)

---

## Регулярные задачи

### Ежедневные задачи

#### 1. Проверка логов (5-10 минут)

```bash
# Docker deployment
docker compose logs --tail=100 --since 24h remnawave-tg-shop | grep -i error

# Non-Docker deployment
sudo journalctl -u vpnbot --since "24 hours ago" -p err

# Критические ошибки для проверки:
# - Database connection errors
# - Payment processing failures
# - Panel API timeouts
# - Memory/resource issues
```

**Что искать:**
- ❌ Повторяющиеся ошибки
- ⚠️ WARNING сообщения о ресурсах
- 🔴 Критические исключения
- 💰 Ошибки обработки платежей

**Действия при обнаружении проблем:**
```bash
# Если ошибки БД
docker compose restart remnawave-tg-shop-db

# Если memory issues
docker stats --no-stream
# Проверить, не превышены ли лимиты

# Если payment errors
# Проверить webhooks и API keys
curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo
```

#### 2. Проверка мониторинга (2-3 минуты)

```bash
# Health check
curl http://localhost:8080/health
# Ожидается: {"status": "ok"}

# Docker container status
docker compose ps
# Все должны быть "Up (healthy)"

# Database connections
docker compose exec remnawave-tg-shop-db psql -U postgres -d vpnbot -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';"
# Должно быть < pool_size (20)
```

#### 3. Проверка disk space (1 минута)

```bash
# Общее использование
df -h

# Docker volumes
docker system df -v

# Database size
docker compose exec remnawave-tg-shop-db psql -U postgres -d vpnbot -c "SELECT pg_size_pretty(pg_database_size('vpnbot'));"

# Если использование > 80%, запустить cleanup
```

**Alerting thresholds:**
- Disk usage > 80% - ⚠️ warning
- Disk usage > 90% - 🔴 critical
- DB size > 10GB - ⚠️ warning (запустить cleanup)

---

### Еженедельные задачи

#### 1. Backup verification (10-15 минут)

```bash
# Проверить, что backups создаются
ls -lh /opt/backups/vpnbot/
# Должно быть минимум 7 backup файлов (по одному на день)

# Проверить размер последнего backup
LATEST_BACKUP=$(ls -t /opt/backups/vpnbot/*.sql.gz | head -1)
ls -lh $LATEST_BACKUP

# Тестовое восстановление (на тестовой БД)
# ВАЖНО: Делать только на тестовой БД!
gunzip -c $LATEST_BACKUP | psql -U postgres -d vpnbot_test
```

**Что проверять:**
- ✅ Backups создаются ежедневно
- ✅ Размер backup адекватный (не 0 байт)
- ✅ Backup можно распаковать
- ✅ Тестовое восстановление успешно

#### 2. Security audit (15-20 минут)

```bash
# Проверка зависимостей на уязвимости
cd /opt/vpnbot
source venv/bin/activate
pip-audit

# Альтернатива
safety check --json

# Проверка кода на security issues
bandit -r bot/ -f json -o security-report.json

# Проверить результаты
cat security-report.json | jq '.results[] | select(.issue_severity == "HIGH")'
```

**Действия при обнаружении уязвимостей:**
1. Оценить критичность (CVSS score)
2. Проверить, есть ли patch
3. Обновить пакет
4. Тестировать
5. Deploy обновление

#### 3. Cleanup старых данных (5-10 минут)

```bash
# Запустить cleanup tasks
docker compose exec remnawave-tg-shop python -c "
from bot.utils.cleanup_tasks import run_all_cleanup_tasks
from db.database_setup import get_session_maker
import asyncio

async def main():
    session_maker = get_session_maker()
    async with session_maker() as session:
        result = await run_all_cleanup_tasks(
            session, 
            log_retention_days=30,
            payment_archive_days=90
        )
        print(f'Cleaned {result[\"total_cleaned\"]} records')

asyncio.run(main())
"

# Проверить размер БД после cleanup
docker compose exec remnawave-tg-shop-db psql -U postgres -d vpnbot -c "SELECT pg_size_pretty(pg_database_size('vpnbot'));"
```

#### 4. Review важных метрик (10 минут)

```bash
# Активные пользователи за неделю
docker compose exec remnawave-tg-shop-db psql -U postgres -d vpnbot << EOF
SELECT COUNT(DISTINCT user_id) as active_users
FROM message_logs
WHERE timestamp > NOW() - INTERVAL '7 days';
EOF

# Новые подписки за неделю
docker compose exec remnawave-tg-shop-db psql -U postgres -d vpnbot << EOF
SELECT COUNT(*) as new_subscriptions
FROM subscriptions
WHERE created_at > NOW() - INTERVAL '7 days';
EOF

# Успешные платежи за неделю
docker compose exec remnawave-tg-shop-db psql -U postgres -d vpnbot << EOF
SELECT COUNT(*) as successful_payments, SUM(amount) as total_revenue
FROM payments
WHERE status = 'succeeded' 
AND created_at > NOW() - INTERVAL '7 days';
EOF
```

---

### Ежемесячные задачи

#### 1. Полный security audit (30-60 минут)

```bash
# 1. Обновить все dev tools
pip install --upgrade pip-audit safety bandit

# 2. Полная проверка
pip-audit
safety check
bandit -r bot/ -ll

# 3. Проверить SSL сертификаты
openssl s_client -connect your-domain.com:443 -servername your-domain.com | openssl x509 -noout -dates

# 4. Review access logs
sudo grep "401\|403\|404\|500" /var/log/nginx/access.log | tail -100

# 5. Проверить failed login attempts (если есть admin panel)
```

#### 2. Dependency updates (60-90 минут)

См. раздел [Обновление зависимостей](#обновление-зависимостей)

#### 3. Database maintenance (30-45 минут)

```bash
# 1. ANALYZE для обновления статистики
docker compose exec remnawave-tg-shop-db psql -U postgres -d vpnbot -c "ANALYZE VERBOSE;"

# 2. VACUUM для очистки dead tuples
docker compose exec remnawave-tg-shop-db psql -U postgres -d vpnbot -c "VACUUM VERBOSE;"

# 3. REINDEX для оптимизации индексов
docker compose exec remnawave-tg-shop-db psql -U postgres -d vpnbot -c "REINDEX DATABASE vpnbot;"

# 4. Проверить bloat
docker compose exec remnawave-tg-shop-db psql -U postgres -d vpnbot << EOF
SELECT
  schemaname, tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) AS external_size
FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 10;
EOF
```

#### 4. Performance review (45-60 минут)

```bash
# 1. Медленные запросы за месяц
docker compose exec remnawave-tg-shop-db psql -U postgres -d vpnbot << EOF
SELECT 
  query,
  calls,
  total_exec_time / 1000 as total_seconds,
  mean_exec_time / 1000 as mean_seconds,
  max_exec_time / 1000 as max_seconds
FROM pg_stat_statements
WHERE mean_exec_time > 100  -- Медленнее 100ms
ORDER BY mean_exec_time DESC
LIMIT 20;
EOF

# 2. Cache hit ratio (должен быть > 95%)
docker compose exec remnawave-tg-shop-db psql -U postgres -d vpnbot << EOF
SELECT 
  sum(heap_blks_read) as heap_read,
  sum(heap_blks_hit) as heap_hit,
  sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read)) * 100 as cache_hit_ratio
FROM pg_statio_user_tables;
EOF

# 3. Index usage
docker compose exec remnawave-tg-shop-db psql -U postgres -d vpnbot << EOF
SELECT
  schemaname,
  tablename,
  indexname,
  idx_scan as index_scans
FROM pg_stat_user_indexes
ORDER BY idx_scan ASC;
EOF

# Если idx_scan = 0 для индекса, возможно он не используется
```

---

## Cleanup задачи

### Использование bot/utils/cleanup_tasks.py

**Файл:** [`bot/utils/cleanup_tasks.py`](bot/utils/cleanup_tasks.py)

#### Доступные функции

```python
# 1. Удалить старые логи
async def cleanup_old_logs(session: AsyncSession, days: int = 30) -> int

# 2. Удалить истекшие промокоды
async def cleanup_expired_promo_codes(session: AsyncSession) -> int

# 3. Архивировать старые платежи
async def cleanup_old_payments(session: AsyncSession, days: int = 90) -> int

# 4. Запустить все cleanup задачи
async def run_all_cleanup_tasks(
    session: AsyncSession,
    log_retention_days: int = 30,
    payment_archive_days: int = 90
) -> dict
```

#### Ручной запуск

```bash
# Docker
docker compose exec remnawave-tg-shop python -c "
from bot.utils.cleanup_tasks import run_all_cleanup_tasks
from db.database_setup import get_session_maker
import asyncio

async def main():
    session_maker = get_session_maker()
    async with session_maker() as session:
        stats = await run_all_cleanup_tasks(session)
        print(f'Cleanup completed:')
        print(f'  - Logs deleted: {stats[\"logs_deleted\"]}')
        print(f'  - Promo codes deleted: {stats[\"promo_codes_deleted\"]}')
        print(f'  - Payments archived: {stats[\"payments_archived\"]}')
        print(f'  - Total: {stats[\"total_cleaned\"]}')

asyncio.run(main())
"

# Non-Docker
cd /opt/vpnbot
source venv/bin/activate
python -c "..." # same as above
```

### Настройка cron jobs

**Файл:** `/etc/cron.d/vpnbot-cleanup`

```bash
# Cleanup logs daily at 3:00 AM
0 3 * * * root docker compose -f /opt/vpnbot/docker-compose.yml exec -T remnawave-tg-shop python -c "from bot.utils.cleanup_tasks import cleanup_old_logs; from db.database_setup import get_session_maker; import asyncio; asyncio.run(cleanup_old_logs(get_session_maker()(), days=30))" >> /var/log/vpnbot-cleanup.log 2>&1

# Full cleanup weekly on Sunday at 4:00 AM
0 4 * * 0 root docker compose -f /opt/vpnbot/docker-compose.yml exec -T remnawave-tg-shop python -c "from bot.utils.cleanup_tasks import run_all_cleanup_tasks; from db.database_setup import get_session_maker; import asyncio; asyncio.run(run_all_cleanup_tasks(get_session_maker()(), log_retention_days=30, payment_archive_days=90))" >> /var/log/vpnbot-cleanup.log 2>&1

# Database VACUUM monthly on 1st at 5:00 AM
0 5 1 * * root docker compose -f /opt/vpnbot exec -T remnawave-tg-shop-db psql -U postgres -d vpnbot -c "VACUUM ANALYZE;" >> /var/log/vpnbot-vacuum.log 2>&1
```

### Мониторинг размера БД

```bash
#!/bin/bash
# /opt/vpnbot/scripts/check_db_size.sh

# Получить размер БД в байтах
DB_SIZE=$(docker compose exec -T remnawave-tg-shop-db psql -U postgres -d vpnbot -t -c "SELECT pg_database_size('vpnbot');")

# Порог в байтах (10GB)
THRESHOLD=$((10 * 1024 * 1024 * 1024))

if [ "$DB_SIZE" -gt "$THRESHOLD" ]; then
    echo "WARNING: Database size ($DB_SIZE bytes) exceeds threshold ($THRESHOLD bytes)"
    echo "Running cleanup tasks..."
    
    docker compose exec -T remnawave-tg-shop python -c "
from bot.utils.cleanup_tasks import run_all_cleanup_tasks
from db.database_setup import get_session_maker
import asyncio
asyncio.run(run_all_cleanup_tasks(get_session_maker()(), log_retention_days=15, payment_archive_days=60))
"
else
    echo "Database size OK: $DB_SIZE bytes"
fi
```

**Добавить в cron:**
```bash
# Check DB size daily at 6:00 AM
0 6 * * * /opt/vpnbot/scripts/check_db_size.sh >> /var/log/vpnbot-dbsize.log 2>&1
```

---

## Обновление зависимостей

### Проверка security advisories

```bash
# 1. Проверить уязвимости
pip-audit

# 2. Проверить устаревшие пакеты
pip list --outdated

# 3. Проверить через safety
safety check --json

# 4. GitHub Security Alerts
# Проверить на GitHub: Settings → Security → Dependabot alerts
```

### Процесс обновления

#### Шаг 1: Подготовка

```bash
# 1. Создать backup
./backup.sh

# 2. Создать ветку для обновлений
git checkout -b updates-$(date +%Y%m%d)

# 3. Записать текущие версии
pip freeze > requirements.old.txt
```

#### Шаг 2: Обновление в dev окружении

```bash
# 1. Создать dev environment
python3.11 -m venv venv-test
source venv-test/bin/activate

# 2. Установить текущие зависимости
pip install -r requirements.txt

# 3. Обновить конкретный пакет
pip install --upgrade package_name

# 4. Или обновить все (ОСТОРОЖНО!)
pip install --upgrade -r requirements.txt

# 5. Сохранить новые версии
pip freeze > requirements.new.txt

# 6. Сравнить
diff requirements.old.txt requirements.new.txt
```

#### Шаг 3: Тестирование

```bash
# 1. Запустить unit tests
pytest

# 2. Запустить с новыми зависимостями
python main.py

# 3. Проверить основные функции
# - Регистрация
# - Оплата
# - Admin панель

# 4. Проверить логи на ошибки
tail -f logs/bot.log | grep -i error
```

#### Шаг 4: Deployment

```bash
# 1. Commit changes
git add requirements.txt
git commit -m "Update dependencies: $(date +%Y-%m-%d)

- Updated package1 from x.x.x to y.y.y (security fix)
- Updated package2 from x.x.x to y.y.y (bug fixes)
"

# 2. Merge в main (через PR)
git push origin updates-$(date +%Y%m%d)

# 3. Deploy на production
docker compose pull
docker compose up -d --build

# 4. Проверить health
curl http://localhost:8080/health

# 5. Мониторить логи 30 минут
docker compose logs -f remnawave-tg-shop
```

#### Шаг 5: Rollback (if needed)

```bash
# 1. Вернуться на предыдущую версию
git revert HEAD

# 2. Rebuild с старыми зависимостями
docker compose up -d --build

# 3. Restore backup (если нужно)
gunzip -c backup_YYYYMMDD.sql.gz | docker compose exec -T remnawave-tg-shop-db psql -U postgres -d vpnbot
```

### Критерии для обновления

**Обязательно обновить:**
- 🔴 Critical security vulnerabilities (CVSS ≥ 9.0)
- 🟠 High security vulnerabilities (CVSS ≥ 7.0)

**Рекомендуется обновить:**
- 🟡 Medium security vulnerabilities (CVSS 4.0-6.9)
- 🔵 Major version updates с важными features
- 🟢 Bug fixes affecting used functionality

**Можно отложить:**
- Minor version updates
- Patch updates без security fixes
- Dependencies не используемые напрямую

---

## Мониторинг

### Key Performance Indicators (KPIs)

#### 1. System Health

```bash
# CPU usage
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}"

# Memory usage
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}"

# Disk I/O
iostat -x 1 5

# Network
iftop -i eth0
```

**Thresholds:**
- CPU > 80% sustained - ⚠️ warning
- Memory > 90% - 🔴 critical
- Disk I/O wait > 50% - ⚠️ warning

#### 2. Application Metrics

```bash
# Active users (last 24h)
docker compose exec remnawave-tg-shop-db psql -U postgres -d vpnbot << EOF
SELECT COUNT(DISTINCT user_id) FROM message_logs 
WHERE timestamp > NOW() - INTERVAL '24 hours';
EOF

# Active subscriptions
docker compose exec remnawave-tg-shop-db psql -U postgres -d vpnbot << EOF
SELECT COUNT(*) FROM subscriptions 
WHERE is_active = true AND end_date > NOW();
EOF

# Pending payments
docker compose exec remnawave-tg-shop-db psql -U postgres -d vpnbot << EOF
SELECT COUNT(*) FROM payments 
WHERE status = 'pending';
EOF
```

#### 3. Database Performance

```bash
# Connection count
docker compose exec remnawave-tg-shop-db psql -U postgres -d vpnbot << EOF
SELECT 
  count(*) as total_connections,
  sum(case when state = 'active' then 1 else 0 end) as active,
  sum(case when state = 'idle' then 1 else 0 end) as idle
FROM pg_stat_activity
WHERE datname = 'vpnbot';
EOF

# Long running queries
docker compose exec remnawave-tg-shop-db psql -U postgres -d vpnbot << EOF
SELECT 
  pid,
  now() - query_start as duration,
  state,
  query
FROM pg_stat_activity
WHERE state != 'idle'
AND query_start < now() - interval '1 minute'
ORDER BY duration DESC;
EOF
```

### Alerting Setup

#### Simple Email Alerts

```bash
#!/bin/bash
# /opt/vpnbot/scripts/health_check.sh

HEALTH_URL="http://localhost:8080/health"
EMAIL="admin@example.com"

# Check health endpoint
if ! curl -f -s "$HEALTH_URL" > /dev/null; then
    echo "ALERT: vpnbot health check failed at $(date)" | mail -s "VPNBot Down" "$EMAIL"
    
    # Try to restart
    docker compose restart remnawave-tg-shop
fi
```

**Cron:**
```bash
*/5 * * * * /opt/vpnbot/scripts/health_check.sh
```

#### Advanced Monitoring (Prometheus + Grafana)

**Coming soon in roadmap**

---

## Backup и восстановление

### Automated Backup Script

**Файл:** `/opt/vpnbot/backup.sh`

```bash
#!/bin/bash
# Automated backup script for vpnbot

set -e  # Exit on error

# Configuration
BACKUP_DIR="/opt/backups/vpnbot"
RETENTION_DAYS=30
DATE=$(date +%Y%m%d_%H%M%S)
FILENAME="vpnbot_backup_$DATE.sql.gz"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup database
echo "Starting backup at $(date)"
docker compose exec -T remnawave-tg-shop-db pg_dump -U postgres vpnbot | gzip > "$BACKUP_DIR/$FILENAME"

# Verify backup
if [ -f "$BACKUP_DIR/$FILENAME" ]; then
    SIZE=$(du -h "$BACKUP_DIR/$FILENAME" | cut -f1)
    echo "Backup created: $FILENAME ($SIZE)"
else
    echo "ERROR: Backup failed!"
    exit 1
fi

# Remove old backups
find "$BACKUP_DIR" -name "vpnbot_backup_*.sql.gz" -mtime +$RETENTION_DAYS -delete
echo "Removed backups older than $RETENTION_DAYS days"

# Optional: Upload to S3/Cloud Storage
# aws s3 cp "$BACKUP_DIR/$FILENAME" s3://my-backups/vpnbot/

echo "Backup completed at $(date)"
```

**Permissions:**
```bash
chmod +x /opt/vpnbot/backup.sh
```

**Cron schedule:**
```bash
# Daily backup at 2:00 AM
0 2 * * * /opt/vpnbot/backup.sh >> /var/log/vpnbot-backup.log 2>&1
```

### Восстановление из backup

```bash
# 1. Список доступных backups
ls -lh /opt/backups/vpnbot/

# 2. Выбрать backup для восстановления
BACKUP_FILE="/opt/backups/vpnbot/vpnbot_backup_20241124_020000.sql.gz"

# 3. Остановить бота
docker compose stop remnawave-tg-shop

# 4. Создать backup текущей БД (на случай)
docker compose exec -T remnawave-tg-shop-db pg_dump -U postgres vpnbot | gzip > /tmp/pre_restore_backup.sql.gz

# 5. Очистить БД
docker compose exec -T remnawave-tg-shop-db psql -U postgres -d vpnbot << EOF
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL ON SCHEMA public TO public;
EOF

# 6. Восстановить из backup
gunzip -c "$BACKUP" | docker compose exec -T remnawave-tg-shop-db psql -U postgres -d vpnbot

# 7. Запустить бота
docker compose start remnawave-tg-shop

# 8. Проверить health
curl http://localhost:8080/health

# 9. Проверить данные
docker compose exec remnawave-tg-shop-db psql -U postgres -d vpnbot -c "SELECT COUNT(*) FROM users;"
```

### Point-in-Time Recovery

Для настройки PITR см. документацию PostgreSQL: [PostgreSQL PITR](https://www.postgresql.org/docs/current/continuous-archiving.html)

---

## Troubleshooting

### Common Issues and Solutions

#### Issue 1: High Memory Usage

**Symptoms:**
```
Memory usage: 95%+
OOMKilled events in docker logs
```

**Diagnosis:**
```bash
# Check memory usage
docker stats --no-stream

# Check processes using most memory
docker compose exec remnawave-tg-shop ps aux --sort=-%mem | head

# Check for memory leaks
# ... analyze over time
```

**Solutions:**

1. **Increase memory limit:**
```yaml
# docker-compose.yml
deploy:
  resources:
    limits:
      memory: 1G  # Was: 512M
```

2. **Run cleanup tasks:**
```bash
docker compose exec remnawave-tg-shop python -c "from bot.utils.cleanup_tasks import run_all_cleanup_tasks; ..."
```

3. **Optimize connection pool:**
```python
# db/database_setup.py
engine = create_async_engine(
    DATABASE_URL,
    pool_size=15,  # Reduce from 20
    max_overflow=5,  # Reduce from 10
)
```

4. **Restart service:**
```bash
docker compose restart remnawave-tg-shop
```

---

#### Issue 2: Slow Queries

**Symptoms:**
```
Response time > 2s
Timeouts in logs
```

**Diagnosis:**
```bash
# Enable slow query log
docker compose exec remnawave-tg-shop-db psql -U postgres << EOF
ALTER SYSTEM SET log_min_duration_statement = 1000;  -- 1 second
SELECT pg_reload_conf();
EOF

# Check slow queries
docker compose logs remnawave-tg-shop-db | grep "duration:"

# Check pg_stat_statements
docker compose exec remnawave-tg-shop-db psql -U postgres -d vpnbot << EOF
SELECT query, calls, total_exec_time, mean_exec_time 
FROM pg_stat_statements 
ORDER BY mean_exec_time DESC 
LIMIT 10;
EOF
```

**Solutions:**

1. **Add missing indexes:**
```sql
-- Example: index on subscriptions
CREATE INDEX idx_subscriptions_user_active 
ON subscriptions(user_id, is_active);

CREATE INDEX idx_payments_user_status 
ON payments(user_id, status);
```

2. **Optimize queries:**
```python
# Use joinedload для eager loading
from sqlalchemy.orm import joinedload

subs = await session.execute(
    select(Subscription)
    .options(joinedload(Subscription.user))
    .options(joinedload(Subscription.tariff))
)
```

3. **Run ANALYZE:**
```bash
docker compose exec remnawave-tg-shop-db psql -U postgres -d vpnbot -c "ANALYZE;"
```

---

#### Issue 3: Webhook Failures

**Symptoms:**
```
Payments not processed
"Webhook verification failed" in logs
```

**Diagnosis:**
```bash
# Check webhook info
curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo

# Check Nginx logs
sudo tail -f /var/log/nginx/error.log

# Test webhook endpoint
curl -X POST https://your-domain.com/webhook/yookassa

# Check SSL certificate
openssl s_client -connect your-domain.com:443
```

**Solutions:**

1. **Verify webhook signature secrets:**
```bash
# Check .env
grep WEBHOOK .env
grep SECRET .env
```

2. **Restart Nginx:**
```bash
sudo nginx -t
sudo systemctl restart nginx
```

3. **Re-register webhook:**
```bash
# Telegram webhook
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://your-domain.com/<TOKEN>"
```

---

## Performance Tuning

### Database Optimization

#### 1. Index Optimization

```sql
-- Check unused indexes
SELECT
  schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0 AND indexname NOT LIKE '%_pkey';

-- Check missing indexes (suggestions)
SELECT 
  relname as table,
  seq_scan,
  idx_scan,
  seq_scan - idx_scan as seq_minus_idx
FROM pg_stat_user_tables
WHERE seq_scan - idx_scan > 0
ORDER BY seq_scan - idx_scan DESC
LIMIT 10;
```

#### 2. Query Optimization

```bash
# Enable query logging
docker compose exec remnawave-tg-shop-db psql -U postgres << EOF
ALTER SYSTEM SET log_statement = 'all';
ALTER SYSTEM SET log_duration = on;
SELECT pg_reload_conf();
EOF

# Analyze slow queries
# Review logs and optimize
```

#### 3. Connection Pooling Tuning

```python
# db/database_setup.py

# For low traffic (< 100 concurrent users)
pool_size=10
max_overflow=5

# For medium traffic (100-500 concurrent users)
pool_size=20
max_overflow=10

# For high traffic (500+ concurrent users)
pool_size=30
max_overflow=20
```

### Application Optimization

#### 1. Caching Strategy

```python
# Implement Redis caching for:
# - Tariffs (rarely change)
# - User settings (frequently read)
# - Statistics (expensive queries)

from redis import asyncio as aioredis

redis = aioredis.from_url("redis://localhost")

# Example
async def get_tariff(tariff_id: int):
    # Try cache first
    cached = await redis.get(f"tariff:{tariff_id}")
    if cached:
        return json.loads(cached)
    
    # Query DB
    tariff = await tariff_dal.get_tariff_by_id(session, tariff_id)
    
    # Cache for 1 hour
    await redis.setex(
        f"tariff:{tariff_id}",
        3600,
        json.dumps(tariff)
    )
    
    return tariff
```

#### 2. Async Optimization

```python
# Use asyncio.gather для параллельных операций
import asyncio

# Bad
user = await get_user(user_id)
subscription = await get_subscription(user_id)
payments = await get_payments(user_id)

# Good
user, subscription, payments = await asyncio.gather(
    get_user(user_id),
    get_subscription(user_id),
    get_payments(user_id)
)
```

---

## Дополнительные ресурсы

### Полезные команды

```bash
# === DOCKER ===

# Restart service
docker compose restart remnawave-tg-shop

# View logs
docker compose logs -f --tail=100 remnawave-tg-shop

# Shell access
docker compose exec remnawave-tg-shop /bin/bash

# Python REPL
docker compose exec remnawave-tg-shop python

# === DATABASE ===

# psql access
docker compose exec remnawave-tg-shop-db psql -U postgres -d vpnbot

# Backup
docker compose exec -T remnawave-tg-shop-db pg_dump -U postgres vpnbot | gzip > backup.sql.gz

# Restore
gunzip -c backup.sql.gz | docker compose exec -T remnawave-tg-shop-db psql -U postgres -d vpnbot

# === MONITORING ===

# Health check
curl http://localhost:8080/health

# Stats
docker stats --no-stream

# Disk usage
df -h
docker system df -v
```

### Связанная документация

- [AUDIT_REPORT.md](AUDIT_REPORT.md) - Отчет о техническом аудите
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - Руководство по развертыванию
- [SECURITY_GUIDE.md](SECURITY_GUIDE.md) - Руководство по безопасности
- [FIXES_CHANGELOG.md](FIXES_CHANGELOG.md) - Changelog исправлений

---

**Версия документа:** 1.0  
**Последнее обновление:** 24 ноября 2024  
**Статус:** ФИНАЛИЗИРОВАН

*Этот документ содержит полное руководство по поддержке и обслуживанию проекта. Регулярно обновляйте процедуры в соответствии с изменениями в системе.*