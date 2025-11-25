# Redis FSM Storage Migration Guide

## Обзор

Redis FSM Storage обеспечивает персистентное хранение состояний пользователей в Telegram-боте. В отличие от MemoryStorage, который теряет все данные при перезапуске бота, Redis сохраняет состояния между перезапусками.

## Преимущества Redis FSM Storage

### 1. **Персистентность**
- Состояния сохраняются при перезапуске бота
- Пользователи не теряют прогресс в multi-step диалогах
- Критично для production окружения

### 2. **Горизонтальное масштабирование**
- Поддержка нескольких инстансов бота
- Общее состояние между всеми инстансами
- Load balancing friendly

### 3. **Автоматический TTL**
- Автоматическое удаление expired состояний
- Эффективное использование памяти
- Конфигурируемое время жизни

### 4. **Лучшая производительность**
- Оптимизированное управление памятью
- Эффективное хранение больших объемов данных
- Меньшая нагрузка на основной сервер

## Установка и настройка

### Шаг 1: Установка зависимостей

Redis клиент уже добавлен в `requirements.txt`:

```bash
pip install -r requirements.txt
```

### Шаг 2: Установка Redis Server

**Docker (рекомендуется):**
```bash
docker run -d --name redis \
  -p 6379:6379 \
  redis:7-alpine
```

**Docker Compose:**
```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes

volumes:
  redis_data:
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

### Шаг 3: Конфигурация в .env

```env
# Enable Redis FSM Storage
REDIS_ENABLED=True
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=         # Оставьте пустым если auth не включен
REDIS_FSM_DB=0         # База данных для FSM
REDIS_CACHE_DB=1       # База данных для кэширования
REDIS_FSM_STATE_TTL=3600    # 1 час
REDIS_FSM_DATA_TTL=3600     # 1 час
```

### Шаг 4: Проверка подключения

```bash
# Проверьте что Redis запущен
redis-cli ping
# Ожидаемый ответ: PONG

# Проверьте версию
redis-cli --version
```

## Архитектура реализации

### Структура файлов

```
bot/
└── storage/
    ├── __init__.py           # Экспорт модулей
    └── redis_storage.py      # Redis FSM Storage factory
```

### Компоненты

#### 1. RedisStorageFactory (`bot/storage/redis_storage.py`)

Фабричный класс для создания и управления Redis storage:

```python
from bot.storage.redis_storage import RedisStorageFactory

# Создание storage
storage = await RedisStorageFactory.create_storage(
    redis_host="localhost",
    redis_port=6379,
    redis_db=0,
    state_ttl=3600,
)

# Проверка подключения
is_connected = RedisStorageFactory.is_connected()

# Закрытие подключения
await RedisStorageFactory.close()
```

#### 2. Storage Factory Function

Автоматическое создание storage из настроек:

```python
from bot.storage import create_redis_storage_from_settings

storage = await create_redis_storage_from_settings(settings)
```

#### 3. Интеграция в Dispatcher

Storage автоматически создается в `bot/app/controllers/dispatcher_controller.py`:

```python
async def create_storage(settings: Settings) -> BaseStorage:
    if settings.REDIS_ENABLED:
        # Попытка создать RedisStorage
        storage = await create_redis_storage_from_settings(settings)
    else:
        # Fallback на MemoryStorage
        storage = MemoryStorage()
    return storage
```

## Миграция с MemoryStorage

### Безопасная миграция

1. **Включите Redis постепенно:**
```env
# Сначала запустите с Redis disabled
REDIS_ENABLED=False

# После тестирования включите
REDIS_ENABLED=True
```

2. **Fallback механизм:**
Если Redis недоступен, бот автоматически использует MemoryStorage:

```python
try:
    storage = await create_redis_storage_from_settings(settings)
except Exception as e:
    logging.error(f"Redis unavailable, using MemoryStorage: {e}")
    storage = MemoryStorage()
```

3. **Мониторинг:**
Проверьте логи для подтверждения успешного подключения:

```
INFO: FSM Storage: Using RedisStorage (persistent state)
INFO: RedisStorage: Connected to Redis at localhost:6379, DB=0
```

## Конфигурация Production

### Redis с паролем

```env
REDIS_ENABLED=True
REDIS_HOST=your-redis-host.com
REDIS_PORT=6379
REDIS_PASSWORD=your_strong_password_here
```

### Redis Cluster (для high availability)

Для Redis Cluster потребуется расширенная конфигурация в `redis_storage.py`:

```python
from redis.asyncio.cluster import RedisCluster

cluster_nodes = [
    {"host": "node1.redis.com", "port": 6379},
    {"host": "node2.redis.com", "port": 6379},
    {"host": "node3.redis.com", "port": 6379},
]
redis_client = RedisCluster(startup_nodes=cluster_nodes)
```

### TTL настройки

**Рекомендуемые значения:**

- **Быстрые операции** (регистрация, оплата): `state_ttl=600` (10 минут)
- **Стандартные диалоги**: `state_ttl=3600` (1 час)
- **Длительные процессы**: `state_ttl=86400` (24 часа)

```env
REDIS_FSM_STATE_TTL=3600  # Состояние живет 1 час
REDIS_FSM_DATA_TTL=3600   # Данные живут 1 час
```

## Мониторинг и обслуживание

### Проверка использования памяти

```bash
redis-cli info memory
```

### Мониторинг ключей FSM

```bash
# Посмотреть все FSM ключи
redis-cli --scan --pattern "fsm:*"

# Количество активных состояний
redis-cli dbsize
```

### Очистка expired ключей

Redis автоматически удаляет expired ключи, но можно форсировать:

```bash
redis-cli FLUSHDB  # Очистить текущую DB (осторожно!)
```

## Troubleshooting

### Проблема: Redis connection refused

**Решение:**
```bash
# Убедитесь что Redis запущен
sudo systemctl status redis-server

# Проверьте порт
sudo netstat -tulpn | grep 6379

# Попробуйте подключиться
redis-cli ping
```

### Проблема: Slow performance

**Решение:**
1. Проверьте TTL значения (слишком большие?)
2. Мониторьте `redis-cli monitor`
3. Включите Redis persistence: `appendonly yes`

### Проблема: Memory limit reached

**Решение:**
```bash
# В redis.conf установите maxmemory
maxmemory 256mb
maxmemory-policy allkeys-lru  # Удалять least recently used keys
```

## Тестирование

### Проверка персистентности

1. Начните диалог с ботом (например, регистрацию)
2. Перезапустите бота
3. Продолжите диалог - состояние должно сохраниться

### Проверка TTL

```python
import asyncio
from bot.storage import RedisStorageFactory

async def test_ttl():
    storage = await RedisStorageFactory.create_storage(state_ttl=10)
    # Установите состояние
    await storage.set_state(chat_id=123, user_id=456, state="test")
    # Подождите 15 секунд
    await asyncio.sleep(15)
    # Состояние должно быть None (expired)
    state = await storage.get_state(chat_id=123, user_id=456)
    print(f"State after TTL: {state}")  # None

asyncio.run(test_ttl())
```

## Best Practices

1. **Используйте Redis в production:** Всегда включайте Redis для production окружения
2. **Настройте TTL разумно:** Не слишком долго (память) и не слишком коротко (UX)
3. **Мониторьте Redis:** Настройте алерты на память и доступность
4. **Используйте отдельные DB:** FSM в DB 0, кэш в DB 1, сессии в DB 2 и т.д.
5. **Включите persistence:** Redis должен иметь AOF или RDB для сохранения данных
6. **Настройте backup:** Регулярное резервное копирование Redis данных

## Производительность

### Бенчмарки

**MemoryStorage:**
- Set/Get state: ~0.001ms (в памяти)
- Persistence: Нет
- Multi-instance: Нет

**RedisStorage:**
- Set/Get state: ~1-2ms (сеть + Redis)
- Persistence: Да
- Multi-instance: Да

### Оптимизация

1. **Используйте локальный Redis** когда возможно (меньше latency)
2. **Connection pooling** уже включен в реализации
3. **Pipeline операции** для batch operations (будущая оптимизация)

## Заключение

Redis FSM Storage - критически важное улучшение для production окружения. Оно обеспечивает надежность, масштабируемость и лучший пользовательский опыт.

**Статус:** ✅ Реализовано в фазе 1 архитектурных улучшений  
**Дата:** 2024-11-24  
**Версия:** 1.0.0