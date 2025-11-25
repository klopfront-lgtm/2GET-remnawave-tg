# Rate Limiting Middleware Guide

## Обзор

Rate Limiting Middleware защищает Telegram-бота от спама, злоупотреблений и DDoS атак путем ограничения количества запросов от одного пользователя в единицу времени.

## Проблемы, которые решает

### 1. **Защита от спама**
- Блокирует пользователей, отправляющих слишком много запросов
- Предотвращает перегрузку сервера
- Улучшает пользовательский опыт для законных пользователей

### 2. **Защита от DDoS атак**
- Ограничивает воздействие вредоносных пользователей
- Автоматическая временная блокировка
- Distributed rate limiting с Redis

### 3. **Справедливое использование ресурсов**
- Равномерное распределение ресурсов между пользователями
- Предотвращение монополизации ресурсов
- Улучшенная стабильность бота

## Архитектура

### Компоненты

```
bot/middlewares/
└── rate_limit_middleware.py
    ├── RateLimitConfig          # Конфигурация
    ├── InMemoryRateLimiter      # In-memory rate limiter (fallback)
    ├── RedisRateLimiter         # Redis-based (distributed)
    └── RateLimitMiddleware      # Aiogram middleware
```

### Два режима работы

#### 1. **In-Memory Mode** (по умолчанию)
- Хранение лимитов в памяти процесса
- Подходит для single-instance deployment
- Не требует Redis
- Данные теряются при перезапуске

#### 2. **Redis Mode** (рекомендуется для production)
- Distributed rate limiting через Redis
- Поддержка multi-instance deployment
- Персистентные данные
- Лучшая производительность

## Установка и настройка

### Шаг 1: Конфигурация в .env

```env
# Enable Rate Limiting
RATE_LIMIT_ENABLED=True

# Rate Limit Settings
RATE_LIMIT_MAX_REQUESTS=20        # Max 20 requests
RATE_LIMIT_TIME_WINDOW=60         # Per 60 seconds
RATE_LIMIT_BAN_DURATION=300       # Ban for 5 minutes if exceeded
RATE_LIMIT_ADMIN_EXEMPT=True      # Admins are exempt

# Redis (optional, but recommended)
REDIS_ENABLED=True
REDIS_HOST=localhost
REDIS_PORT=6379
```

### Шаг 2: Автоматическая интеграция

Rate Limiting Middleware автоматически регистрируется в `dispatcher_controller.py` если `RATE_LIMIT_ENABLED=True`.

## Параметры конфигурации

### RATE_LIMIT_MAX_REQUESTS
**Описание:** Максимальное количество запросов в временном окне  
**По умолчанию:** 20  
**Рекомендации:**
- Обычные боты: 20-30
- Высоконагруженные боты: 50-100
- Строгий режим: 10-15

### RATE_LIMIT_TIME_WINDOW
**Описание:** Размер временного окна в секундах  
**По умолчанию:** 60  
**Рекомендации:**
- Короткое окно (30s): Строгий контроль
- Среднее окно (60s): Баланс
- Длинное окно (120s): Мягкий контроль

### RATE_LIMIT_BAN_DURATION
**Описание:** Длительность временной блокировки при превышении лимита  
**По умолчанию:** 300 (5 минут)  
**Особые значения:**
- `0`: Без блокировки, только ограничение запросов
- `300`: 5 минут (рекомендуется)
- `600`: 10 минут (строгий режим)
- `1800`: 30 минут (очень строгий)

### RATE_LIMIT_ADMIN_EXEMPT
**Описание:** Освободить администраторов от rate limiting  
**По умолчанию:** True  
**Рекомендации:** Всегда оставляйте True для удобства администрирования

## Принцип работы

### Sliding Window Algorithm

Rate limiting использует алгоритм скользящего окна (sliding window):

```
Time Window = 60 seconds
Max Requests = 20

Timeline:
0s  -------- 20s -------- 40s -------- 60s -------- 80s
|            |            |            |            |
10 req       8 req        5 req        10 req       blocked!
                                       (25 total in window)
```

### Процесс обработки запроса

1. **Извлечение user_id** из Update/Message/CallbackQuery
2. **Проверка исключений**: Пропуск админов если ADMIN_EXEMPT=True
3. **Проверка бана**: Если пользователь временно заблокирован
4. **Подсчет запросов**: Сколько запросов в текущем окне
5. **Принятие решения**:
   - Если < MAX_REQUESTS: Разрешить запрос
   - Если >= MAX_REQUESTS: Заблокировать + Временный бан

### In-Memory Implementation

```python
class InMemoryRateLimiter:
    def __init__(self):
        self._requests = {}      # {user_id: deque([timestamp1, timestamp2, ...])}
        self._banned = {}        # {user_id: ban_until_timestamp}
    
    async def check_limit(self, user_id: int):
        # 1. Check if banned
        # 2. Remove old requests outside window
        # 3. Count remaining requests
        # 4. Decide: allow or block
```

### Redis Implementation

```python
class RedisRateLimiter:
    async def check_limit(self, user_id: int):
        # Redis Sorted Set: ZADD rate_limit:123:requests timestamp timestamp
        # Remove old: ZREMRANGEBYSCORE ... 0 cutoff_time
        # Count: ZCARD rate_limit:123:requests
        # Ban if exceeded: SETEX rate_limit:123:banned duration timestamp
```

## Примеры использования

### Базовая настройка (20 req/min)

```env
RATE_LIMIT_ENABLED=True
RATE_LIMIT_MAX_REQUESTS=20
RATE_LIMIT_TIME_WINDOW=60
RATE_LIMIT_BAN_DURATION=300
```

### Строгая настройка (10 req/min, 10 min ban)

```env
RATE_LIMIT_ENABLED=True
RATE_LIMIT_MAX_REQUESTS=10
RATE_LIMIT_TIME_WINDOW=60
RATE_LIMIT_BAN_DURATION=600
```

### Мягкая настройка (50 req/2min)

```env
RATE_LIMIT_ENABLED=True
RATE_LIMIT_MAX_REQUESTS=50
RATE_LIMIT_TIME_WINDOW=120
RATE_LIMIT_BAN_DURATION=0  # No ban, just throttle
```

### VIP боты (без ограничений)

```env
RATE_LIMIT_ENABLED=False
```

## Мониторинг

### Логи

Rate limiting автоматически логирует события:

```
WARNING: Rate limit exceeded for user 123456. Retry after: 300s
WARNING: Rate limit: User 123456 temporarily banned for 300s. Requests: 25 in 60s window
INFO: Rate limit (Redis): Reset for user 123456
```

### Мониторинг Redis

```bash
# Просмотр активных rate limit ключей
redis-cli --scan --pattern "rate_limit:*"

# Просмотр конкретного пользователя
redis-cli ZRANGE rate_limit:123456:requests 0 -1 WITHSCORES

# Количество заблокированных пользователей
redis-cli --scan --pattern "rate_limit:*:banned" | wc -l
```

### Метрики для мониторинга

1. **Количество заблокированных запросов** (counter)
2. **Количество временных банов** (counter)
3. **Топ спамеров** (user_ids с наибольшим количеством блокировок)
4. **Среднее количество запросов на пользователя** (gauge)

## Admin команды

### Reset Rate Limit для пользователя

Добавьте admin команду для сброса лимитов:

```python
@router.message(Command("reset_limit"), AdminFilter())
async def reset_rate_limit_cmd(message: Message, command: CommandObject):
    """Admin command to reset rate limit for user."""
    if not command.args:
        await message.answer("Usage: /reset_limit <user_id>")
        return
    
    try:
        user_id = int(command.args)
        
        # Get rate limit middleware
        rate_limit_mw = None
        for mw in message.bot.dispatcher.update.outer_middleware:
            if isinstance(mw, RateLimitMiddleware):
                rate_limit_mw = mw
                break
        
        if rate_limit_mw:
            await rate_limit_mw.reset_user_limit(user_id)
            await message.answer(f"✅ Rate limit reset for user {user_id}")
        else:
            await message.answer("❌ Rate limiting is not enabled")
            
    except ValueError:
        await message.answer("❌ Invalid user_id format")
```

## Troubleshooting

### Проблема: Legitimate users getting blocked

**Причина:** Слишком низкий MAX_REQUESTS или TIME_WINDOW  
**Решение:**
```env
RATE_LIMIT_MAX_REQUESTS=30  # Increase
RATE_LIMIT_TIME_WINDOW=120  # Increase window
```

### Проблема: Спамеры не блокируются

**Причина:** Слишком высокий MAX_REQUESTS  
**Решение:**
```env
RATE_LIMIT_MAX_REQUESTS=15  # Decrease
RATE_LIMIT_BAN_DURATION=600  # Increase ban
```

### Проблема: Rate limits not working across instances

**Причина:** Используется In-Memory mode  
**Решение:** Включите Redis mode:
```env
REDIS_ENABLED=True
REDIS_HOST=your-redis-host
```

### Проблема: Redis connection errors

**Решение:** Middleware автоматически fallback на In-Memory mode:
```
ERROR: Rate limiting: Failed to create Redis limiter, using In-Memory
```

## Best Practices

1. ✅ **Всегда включайте Rate Limiting в production**
2. ✅ **Используйте Redis mode для multi-instance**
3. ✅ **Освобождайте админов от лимитов** (ADMIN_EXEMPT=True)
4. ✅ **Мониторьте логи на спам активность**
5. ✅ **Настраивайте лимиты под ваш use case**
6. ✅ **Тестируйте настройки перед production**
7. ❌ **Не делайте лимиты слишком строгими**
8. ❌ **Не забывайте про легитимных активных пользователей**

## Производительность

### In-Memory Mode
- **Latency:** ~0.1ms
- **Memory:** O(n) где n = количество активных пользователей
- **Scalability:** Single instance only

### Redis Mode
- **Latency:** ~1-2ms (локальный Redis)
- **Memory:** O(n) в Redis
- **Scalability:** Multi-instance support

### Оптимизация

1. **Используйте локальный Redis** для минимальной latency
2. **Настройте connection pooling** (уже включен)
3. **Мониторьте Redis memory usage**
4. **Используйте TTL для автоматической очистки**

## Интеграция с другими компонентами

### С BanCheckMiddleware

Rate Limit работает до BanCheckMiddleware:
```python
# Order matters!
dp.update.outer_middleware(RateLimitMiddleware(...))  # First
dp.update.outer_middleware(BanCheckMiddleware(...))   # Second
```

### С Monitoring Service

```python
# Track rate limit metrics
monitoring.increment("rate_limit.blocked.total")
monitoring.increment(f"rate_limit.blocked.user.{user_id}")
```

### С Admin Panel

Добавьте раздел для просмотра заблокированных пользователей и статистики rate limiting.

## Заключение

Rate Limiting Middleware - критически важное улучшение для защиты бота от злоупотреблений. Правильная настройка обеспечивает баланс между защитой и пользовательским опытом.

**Статус:** ✅ Реализовано в фазе 1 архитектурных улучшений  
**Дата:** 2024-11-24  
**Версия:** 1.0.0