# Руководство по миграциям базы данных

## Что было сделано

### 1. Инициализирован Alembic
Создана полная инфраструктура для работы с миграциями базы данных:

- ✅ [`alembic.ini`](alembic.ini:1) - конфигурационный файл Alembic
- ✅ [`db/migrations/env.py`](db/migrations/env.py:1) - скрипт окружения с подключением к базе данных
- ✅ [`db/migrations/script.py.mako`](db/migrations/script.py.mako:1) - шаблон для новых миграций
- ✅ [`db/migrations/versions/`](db/migrations/versions/) - директория для файлов миграций

### 2. Создана миграция для новых таблиц
Файл: [`db/migrations/versions/001_add_tariffs_balance_discounts.py`](db/migrations/versions/001_add_tariffs_balance_discounts.py:1)

Эта миграция добавляет:

#### Таблица `tariffs` (Тарифы)
- `id` - уникальный идентификатор
- `name` - название тарифа
- `description` - описание
- `price` - цена
- `currency` - валюта (по умолчанию RUB)
- `duration_days` - длительность в днях
- `traffic_limit_bytes` - лимит трафика в байтах
- `device_limit` - лимит устройств
- `speed_limit_mbps` - ограничение скорости
- `is_active` - активен ли тариф
- `is_default` - является ли тарифом по умолчанию

#### Таблица `user_balances` (История операций с балансом)
- `id` - уникальный идентификатор операции
- `user_id` - ID пользователя (внешний ключ)
- `amount` - сумма операции
- `currency` - валюта
- `operation_type` - тип операции (deposit, withdrawal, payment, refund, bonus)
- `description` - описание операции
- `created_at` - время создания

#### Таблица `user_discounts` (Персональные скидки)
- `id` - уникальный идентификатор
- `user_id` - ID пользователя (внешний ключ)
- `discount_percentage` - процент скидки
- `tariff_id` - ID тарифа (опционально, если null - применяется ко всем)
- `is_active` - активна ли скидка
- `created_at` - время создания

#### Изменения в существующих таблицах
- Добавлена колонка `tariff_id` в таблицу `subscriptions` (внешний ключ на `tariffs`)

### 3. Созданы вспомогательные скрипты

#### [`run_migrations.py`](run_migrations.py:1)
Скрипт для удобного применения миграций:
```bash
python run_migrations.py
```

#### [`check_alembic.py`](check_alembic.py:1)
Проверка установки необходимых зависимостей:
```bash
python check_alembic.py
```

## Как применить миграции

### Вариант 1: Через Python скрипт (рекомендуется)
```bash
python run_migrations.py
```

### Вариант 2: Через Alembic напрямую
```bash
alembic upgrade head
```

### Вариант 3: В Docker контейнере
```bash
docker exec remnawave-tg-shop python run_migrations.py
```

Или:
```bash
docker-compose exec remnawave-tg-shop alembic upgrade head
```

## После применения миграций

После успешного применения миграций будут созданы три новые таблицы:
- `tariffs`
- `user_balances`
- `user_discounts`

А также будет добавлена колонка `tariff_id` в таблицу `subscriptions`.

## Проверка статуса миграций

Посмотреть текущую версию базы данных:
```bash
alembic current
```

Посмотреть историю миграций:
```bash
alembic history --verbose
```

## Откат миграции (если потребуется)

Откатить последнюю миграцию:
```bash
alembic downgrade -1
```

Откатить все миграции:
```bash
alembic downgrade base
```

## Создание новых миграций в будущем

### Автоматическая генерация
После изменения моделей в [`db/models.py`](db/models.py:1):
```bash
alembic revision --autogenerate -m "описание изменений"
```

### Ручное создание
```bash
alembic revision -m "описание изменений"
```

## Требования

Убедитесь, что установлены все зависимости из [`requirements.txt`](requirements.txt:1):
```bash
pip install -r requirements.txt
```

## Важные замечания

1. **Резервная копия**: Перед применением миграций на продакшене рекомендуется создать резервную копию базы данных
2. **Переменные окружения**: Убедитесь, что файл `.env` содержит корректные параметры подключения к базе данных
3. **Права доступа**: Пользователь базы данных должен иметь права на создание таблиц и индексов

## Связанные файлы

- Модели: [`db/models.py`](db/models.py:1)
- DAL для тарифов: [`db/dal/tariff_dal.py`](db/dal/tariff_dal.py:1)
- DAL для баланса: [`db/dal/balance_dal.py`](db/dal/balance_dal.py:1)
- Настройки БД: [`db/database_setup.py`](db/database_setup.py:1)
- Конфигурация: [`config/settings.py`](config/settings.py:1)