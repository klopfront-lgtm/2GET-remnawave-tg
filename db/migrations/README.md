# Alembic Migrations

Эта директория содержит миграции базы данных Alembic для проекта.

## Структура

- `env.py` - конфигурация окружения Alembic
- `script.py.mako` - шаблон для новых файлов миграций
- `versions/` - директория с файлами миграций

## Использование

### Создание новой миграции

Автоматическая генерация на основе изменений в моделях:
```bash
alembic revision --autogenerate -m "описание изменений"
```

Создание пустой миграции:
```bash
alembic revision -m "описание изменений"
```

### Применение миграций

Применить все миграции:
```bash
alembic upgrade head
```

Или использовать Python скрипт:
```bash
python run_migrations.py
```

### Откат миграций

Откатить последнюю миграцию:
```bash
alembic downgrade -1
```

Откатить все миграции:
```bash
alembic downgrade base
```

### Просмотр истории

Посмотреть текущую версию:
```bash
alembic current
```

Посмотреть историю миграций:
```bash
alembic history
```

## Текущие миграции

### 001_add_tariffs_balance_discounts

Добавляет таблицы для новой функциональности тарифов, баланса и скидок:

- **tariffs** - тарифные планы с ценами, лимитами и характеристиками
- **user_balances** - история операций с балансом пользователей
- **user_discounts** - персональные скидки пользователей на тарифы

Также добавляет связь `tariff_id` в таблицу `subscriptions`.

## Docker

Для запуска миграций в Docker контейнере:

```bash
docker exec remnawave-tg-shop python run_migrations.py
```

Или:
```bash
docker-compose exec remnawave-tg-shop alembic upgrade head