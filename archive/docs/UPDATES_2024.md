# Обновления 2024 / Updates 2024

## 🇷🇺 Русская версия

### Резюме изменений

В проект внедрена комплексная система управления тарифами, балансом пользователей и персональными скидками. Реализована полная инфраструктура для работы с миграциями базы данных через Alembic.

#### Основные нововведения:
- ✅ Система множественных тарифов
- ✅ Система баланса пользователей с историей операций
- ✅ Персональные скидки для пользователей
- ✅ Расширенная система промокодов (скидки, баланс, бонусные дни)
- ✅ Профиль пользователя с детальной информацией
- ✅ Пополнение баланса через платежные системы
- ✅ Админ-панель для управления тарифами
- ✅ Админ-панель для управления скидками
- ✅ Миграции базы данных через Alembic

#### Список новых и измененных файлов:

**Миграции и база данных:**
- [`db/migrations/versions/001_add_tariffs_balance_discounts.py`](db/migrations/versions/001_add_tariffs_balance_discounts.py) ✨ НОВЫЙ
- [`db/migrations/env.py`](db/migrations/env.py) ✨ НОВЫЙ
- [`db/migrations/script.py.mako`](db/migrations/script.py.mako) ✨ НОВЫЙ
- [`alembic.ini`](alembic.ini) ✨ НОВЫЙ
- [`run_migrations.py`](run_migrations.py) ✨ НОВЫЙ
- [`check_alembic.py`](check_alembic.py) ✨ НОВЫЙ
- [`apply_migrations_auto.py`](apply_migrations_auto.py) ✨ НОВЫЙ
- [`db/models.py`](db/models.py) - добавлены модели `Tariff`, `UserBalance`, `UserDiscount`

**DAL (Data Access Layer):**
- [`db/dal/tariff_dal.py`](db/dal/tariff_dal.py) ✨ НОВЫЙ
- [`db/dal/balance_dal.py`](db/dal/balance_dal.py) ✨ НОВЫЙ
- [`db/dal/discount_dal.py`](db/dal/discount_dal.py) ✨ НОВЫЙ
- [`db/dal/promo_code_dal.py`](db/dal/promo_code_dal.py) - расширен функционал
- [`db/dal/__init__.py`](db/dal/__init__.py) - обновлены импорты

**Сервисы:**
- [`bot/services/tariff_service.py`](bot/services/tariff_service.py) ✨ НОВЫЙ
- [`bot/services/balance_service.py`](bot/services/balance_service.py) ✨ НОВЫЙ
- [`bot/services/subscription_service.py`](bot/services/subscription_service.py) - интеграция с тарифами
- [`bot/services/yookassa_service.py`](bot/services/yookassa_service.py) - поддержка тарифов

**Handlers (Обработчики) - Пользовательские:**
- [`bot/handlers/user/profile.py`](bot/handlers/user/profile.py) ✨ НОВЫЙ
- [`bot/handlers/user/balance_topup.py`](bot/handlers/user/balance_topup.py) ✨ НОВЫЙ
- [`bot/handlers/user/tariff_selection.py`](bot/handlers/user/tariff_selection.py) ✨ НОВЫЙ
- [`bot/handlers/user/payment.py`](bot/handlers/user/payment.py) - интеграция с тарифами
- [`bot/handlers/user/subscription/payments.py`](bot/handlers/user/subscription/payments.py) - обновлен

**Handlers (Обработчики) - Админские:**
- [`bot/handlers/admin/tariff_management.py`](bot/handlers/admin/tariff_management.py) ✨ НОВЫЙ
- [`bot/handlers/admin/discount_management.py`](bot/handlers/admin/discount_management.py) ✨ НОВЫЙ
- [`bot/handlers/admin/promo/create.py`](bot/handlers/admin/promo/create.py) - расширен
- [`bot/handlers/admin/common.py`](bot/handlers/admin/common.py) - обновлен

**States и Keyboards:**
- [`bot/states/user_states.py`](bot/states/user_states.py) - добавлены новые состояния
- [`bot/states/admin_states.py`](bot/states/admin_states.py) - добавлены новые состояния
- [`bot/keyboards/inline/user_keyboards.py`](bot/keyboards/inline/user_keyboards.py) - новые клавиатуры
- [`bot/keyboards/inline/admin_keyboards.py`](bot/keyboards/inline/admin_keyboards.py) - новые клавиатуры

**Локализация:**
- [`locales/ru.json`](locales/ru.json) - добавлено ~150 новых ключей
- [`locales/en.json`](locales/en.json) - добавлено ~150 новых ключей

**Документация:**
- [`MIGRATION_GUIDE.md`](MIGRATION_GUIDE.md) ✨ НОВЫЙ
- [`db/migrations/README.md`](db/migrations/README.md) ✨ НОВЫЙ

---

### 1. Новые функции для пользователей

#### 1.1. Профиль пользователя
**Файл:** [`bot/handlers/user/profile.py`](bot/handlers/user/profile.py:1)

Пользователи теперь могут просматривать детальную информацию о своем профиле:
- 👤 Основная информация (ID, имя, username, дата регистрации)
- 💰 Текущий баланс
- 📋 Статус и детали подписки
- 🎁 Активные персональные скидки
- 💳 История последних операций с балансом

**Доступ:** Главное меню → "👤 Профиль"

**Ключевые функции:**
```python
async def build_profile_message()  # Формирует детальное сообщение профиля
async def show_profile()            # Отображает профиль пользователя
async def show_balance_history()    # Показывает полную историю операций
```

#### 1.2. Система баланса
**Модель:** [`db/models.py:UserBalance`](db/models.py:300)
**Сервис:** [`bot/services/balance_service.py`](bot/services/balance_service.py:1)

Реализована полноценная система учета баланса:
- 💰 Пополнение баланса через платежные системы
- 💳 Оплата подписок с баланса
- 📊 История всех операций
- 🔄 Типы операций: deposit, withdrawal, payment, refund, bonus

**Операции баланса:**
```python
balance_service.deposit()         # Пополнение баланса
balance_service.charge()          # Списание средств
balance_service.refund()          # Возврат средств
balance_service.add_bonus()       # Добавление бонусов
balance_service.record_payment()  # Запись оплаты подписки
```

**Handler:** [`bot/handlers/user/balance_topup.py`](bot/handlers/user/balance_topup.py:1)
- Выбор суммы пополнения (быстрые кнопки или своя сумма)
- Выбор метода оплаты (YooKassa, CryptoPay, Stars и др.)
- Автоматическое зачисление после успешной оплаты

#### 1.3. Множественные тарифы
**Модель:** [`db/models.py:Tariff`](db/models.py:61)
**Сервис:** [`bot/services/tariff_service.py`](bot/services/tariff_service.py:1)

Система гибких тарифных планов:
- 📦 Неограниченное количество тарифов
- ⏱ Настраиваемая длительность (дни)
- 💵 Индивидуальная цена для каждого тарифа
- 📊 Лимиты: трафик, устройства, скорость
- ⭐ Возможность установить тариф по умолчанию

**Атрибуты тарифа:**
```python
- name: str                          # Название тарифа
- description: str                   # Описание
- price: float                       # Цена
- currency: str                      # Валюта (RUB по умолчанию)
- duration_days: int                 # Длительность в днях
- traffic_limit_bytes: int | None    # Лимит трафика (None = безлимит)
- device_limit: int | None           # Лимит устройств (None = безлимит)
- speed_limit_mbps: float | None     # Ограничение скорости (None = без ограничений)
- is_active: bool                    # Активен ли тариф
- is_default: bool                   # Тариф по умолчанию
```

**Handler:** [`bot/handlers/user/tariff_selection.py`](bot/handlers/user/tariff_selection.py:1)
- Список доступных тарифов с подробной информацией
- Автоматический расчет цены с учетом скидок
- Возможность оплаты с баланса или через платежные системы
- Применение промокодов к тарифам

#### 1.4. Расширенные промокоды
**Обновлено:** [`db/models.py:PromoCode`](db/models.py:179)
**Handler:** [`bot/handlers/admin/promo/create.py`](bot/handlers/admin/promo/create.py:1)

Три типа промокодов:

**1. Бонусные дни (`bonus_days`):**
- Добавляет дни к подписке
- Не влияет на цену
```python
type: 'bonus_days'
bonus_days: 7  # +7 дней к подписке
```

**2. Процентная/фиксированная скидка (`discount`):**
- Процентная скидка: `value <= 100` (например, 20%)
- Фиксированная скидка: `value > 100` (например, 500 руб.)
```python
type: 'discount'
value: 20  # Скидка 20%
# или
value: 500  # Скидка 500 рублей
```

**3. Пополнение баланса (`balance`):**
- Начисляет средства на баланс
- Не влияет на цену подписки
```python
type: 'balance'
value: 100  # +100 рублей на баланс
```

**Дополнительные настройки промокодов:**
- `min_purchase_amount` - минимальная сумма покупки для применения
- `applicable_tariff_ids` - список тарифов, к которым применим промокод
- `max_activations` - максимальное количество активаций
- `valid_until` - срок действия промокода

#### 1.5. Персональные скидки
**Модель:** [`db/models.py:UserDiscount`](db/models.py:314)
**Сервис:** [`db/dal/discount_dal.py`](db/dal/discount_dal.py:1)

Администраторы могут устанавливать индивидуальные скидки пользователям:
- 🎁 Процент скидки (1-99%)
- 📦 Применимость: к конкретному тарифу или ко всем
- 🔄 Активация/деактивация скидок
- 📊 Автоматический расчет с учетом всех скидок

**Порядок применения скидок:**
1. Базовая цена тарифа
2. Персональная скидка пользователя (если есть)
3. Промокод (если применен)

**Пример:**
```
Базовая цена: 1000 руб.
Персональная скидка 20%: -200 руб. = 800 руб.
Промокод 10%: -80 руб. = 720 руб.
Итого к оплате: 720 руб.
```

---

### 2. Новые функции для администраторов

#### 2.1. Управление тарифами
**Handler:** [`bot/handlers/admin/tariff_management.py`](bot/handlers/admin/tariff_management.py:1)

Полный CRUD функционал для тарифов:

**Создание тарифа (7 шагов):**
1. Название (3-50 символов)
2. Описание (опционально)
3. Цена в рублях
4. Длительность в днях (1-365)
5. Лимит трафика в GB (или безлимит)
6. Лимит устройств (или безлимит)
7. Ограничение скорости в Mbps (или без ограничений)

**Управление тарифами:**
- ✅ Активация/деактивация тарифов
- ⭐ Установка тарифа по умолчанию
- ✏️ Редактирование параметров
- 🗑 Удаление тарифов
- 📋 Просмотр списка с пагинацией
- 📊 Детальная информация по каждому тарифу

**Состояния FSM:**
```python
AdminStates.waiting_for_tariff_name
AdminStates.waiting_for_tariff_description
AdminStates.waiting_for_tariff_price
AdminStates.waiting_for_tariff_duration
AdminStates.waiting_for_tariff_traffic_limit
AdminStates.waiting_for_tariff_device_limit
AdminStates.waiting_for_tariff_speed_limit
```

#### 2.2. Управление скидками
**Handler:** [`bot/handlers/admin/discount_management.py`](bot/handlers/admin/discount_management.py:1)

Система персональных скидок для пользователей:

**Установка скидки (3 шага):**
1. Telegram ID пользователя
2. Процент скидки (1-99%)
3. Выбор тарифа (конкретный или все)

**Функции:**
- ➕ Создание новых скидок
- 👁 Просмотр всех скидок пользователя
- 📊 Детальная информация о каждой скидке
- ❌ Деактивация скидок
- 🔍 Валидация существования пользователя и тарифа

**Состояния FSM:**
```python
AdminStates.waiting_for_discount_user_id
AdminStates.waiting_for_discount_percentage
AdminStates.waiting_for_discount_tariff_selection
AdminStates.waiting_for_discount_view_user_id
```

#### 2.3. Расширенная система промокодов
**Handler:** [`bot/handlers/admin/promo/create.py`](bot/handlers/admin/promo/create.py:1)

**Создание промокода (до 7 шагов):**
1. Код промокода (3-30 символов)
2. Тип промокода (bonus_days/discount/balance)
3. Значение (зависит от типа)
4. Применимость к тарифам (опционально)
5. Минимальная сумма покупки (опционально)
6. Максимальное количество активаций (1-10000)
7. Срок действия (в днях или бессрочно)

**Управление промокодами:**
- 🎟 Просмотр всех промокодов
- 📊 Детальная информация и статистика
- 🔄 Активация/деактивация
- 📋 Просмотр списка активаций
- 📄 Экспорт в CSV
- 🗑 Удаление промокодов

**Новые состояния FSM:**
```python
AdminStates.waiting_for_promo_type
AdminStates.waiting_for_promo_value
AdminStates.waiting_for_promo_tariffs
AdminStates.waiting_for_promo_min_purchase
```

---

### 3. Архитектурные изменения

#### 3.1. Новые модели базы данных

**Tariff (Тарифы):**
```python
class Tariff(Base):
    id: int
    name: str
    description: str | None
    price: float
    currency: str = "RUB"
    duration_days: int
    traffic_limit_bytes: int | None
    device_limit: int | None
    speed_limit_mbps: float | None
    is_active: bool = True
    is_default: bool = False
```

**UserBalance (История операций с балансом):**
```python
class UserBalance(Base):
    id: int
    user_id: int  # FK -> users.user_id
    amount: float
    currency: str = "RUB"
    operation_type: str  # deposit, withdrawal, payment, refund, bonus
    description: str | None
    created_at: datetime
```

**UserDiscount (Персональные скидки):**
```python
class UserDiscount(Base):
    id: int
    user_id: int  # FK -> users.user_id
    discount_percentage: float
    tariff_id: int | None  # FK -> tariffs.id (None = все тарифы)
    is_active: bool = True
    created_at: datetime
```

**Обновления в User:**
```python
class User(Base):
    # ... существующие поля ...
    balance: float = 0.0  # Текущий баланс пользователя
    
    # Новые relationships:
    balance_operations: List[UserBalance]
    discounts: List[UserDiscount]
```

**Обновления в Subscription:**
```python
class Subscription(Base):
    # ... существующие поля ...
    tariff_id: int | None  # FK -> tariffs.id
    tariff: Tariff  # relationship
```

**Обновления в Payment:**
```python
class Payment(Base):
    # ... существующие поля ...
    tariff_id: int | None  # FK -> tariffs.id
    tariff: Tariff  # relationship
```

**Обновления в PromoCode:**
```python
class PromoCode(Base):
    # ... существующие поля ...
    type: str  # 'bonus_days', 'discount', 'balance'
    value: float | None  # Значение скидки или баланса
    min_purchase_amount: float | None
    applicable_tariff_ids: List[int] | None  # JSON
```

#### 3.2. Новые сервисы

**TariffService** ([`bot/services/tariff_service.py`](bot/services/tariff_service.py:1)):
```python
class TariffService:
    async def get_active_tariffs()
    async def get_tariff_by_id()
    async def calculate_final_price()  # С учетом всех скидок и промокодов
    async def get_tariff_info()
    async def get_all_tariffs_info()
```

**BalanceService** ([`bot/services/balance_service.py`](bot/services/balance_service.py:1)):
```python
class BalanceService:
    async def get_balance()
    async def deposit()           # Пополнение
    async def charge()            # Списание
    async def refund()            # Возврат
    async def add_bonus()         # Бонус
    async def record_payment()    # Запись оплаты
    async def get_balance_history()
    
class InsufficientFundsError(Exception):
    """Недостаточно средств на балансе"""
```

#### 3.3. Новые DAL модули

**TariffDAL** ([`db/dal/tariff_dal.py`](db/dal/tariff_dal.py:1)):
```python
async def create_tariff()
async def get_tariff_by_id()
async def get_active_tariffs()
async def get_all_tariffs()
async def update_tariff()
async def delete_tariff()
async def get_default_tariff()
```

**BalanceDAL** ([`db/dal/balance_dal.py`](db/dal/balance_dal.py:1)):
```python
async def add_balance_operation()
async def get_user_balance_history()
async def get_user_balance_count()
async def get_balance_total()
```

**DiscountDAL** ([`db/dal/discount_dal.py`](db/dal/discount_dal.py:1)):
```python
async def create_user_discount()
async def get_user_active_discounts()
async def get_all_user_discounts()
async def get_best_user_discount()  # Выбирает наибольшую скидку
async def deactivate_user_discount()
```

#### 3.4. Обновленные handlers

**Пользовательские:**
- [`bot/handlers/user/profile.py`](bot/handlers/user/profile.py:1) - Новый профиль
- [`bot/handlers/user/balance_topup.py`](bot/handlers/user/balance_topup.py:1) - Пополнение баланса
- [`bot/handlers/user/tariff_selection.py`](bot/handlers/user/tariff_selection.py:1) - Выбор тарифов
- [`bot/handlers/user/payment.py`](bot/handlers/user/payment.py:1) - Интеграция с тарифами
- [`bot/handlers/user/subscription/payments.py`](bot/handlers/user/subscription/payments.py:1) - Обновлен для тарифов

**Админские:**
- [`bot/handlers/admin/tariff_management.py`](bot/handlers/admin/tariff_management.py:1) - Управление тарифами
- [`bot/handlers/admin/discount_management.py`](bot/handlers/admin/discount_management.py:1) - Управление скидками
- [`bot/handlers/admin/promo/create.py`](bot/handlers/admin/promo/create.py:1) - Расширенные промокоды

---

### 4. Инструкции по развертыванию

#### 4.1. Требования

Убедитесь, что в [`requirements.txt`](requirements.txt:1) есть:
```txt
alembic>=1.13.0
sqlalchemy>=2.0.0
asyncpg>=0.29.0
```

Установите зависимости:
```bash
pip install -r requirements.txt
```

#### 4.2. Применение миграций БД

**Вариант 1: Автоматически (рекомендуется)**
```bash
python apply_migrations_auto.py
```

**Вариант 2: Через скрипт**
```bash
python run_migrations.py
```

**Вариант 3: Через Alembic напрямую**
```bash
alembic upgrade head
```

**В Docker контейнере:**
```bash
docker exec remnawave-tg-shop python apply_migrations_auto.py
# или
docker-compose exec remnawave-tg-shop alembic upgrade head
```

#### 4.3. Проверка миграций

Проверить текущую версию БД:
```bash
alembic current
```

Посмотреть историю:
```bash
alembic history --verbose
```

#### 4.4. Создание первого тарифа

После применения миграций создайте тарифы через админ-панель:

1. Запустите бота
2. Откройте админ-панель (только для `ADMIN_IDS`)
3. Перейдите: **💰 Тарифы и цены** → **📋 Управление тарифами** → **➕ Создать тариф**
4. Следуйте пошаговому процессу создания тарифа

**Пример первого тарифа:**
- Название: "Стандарт"
- Описание: "Базовый тариф на месяц"
- Цена: 299
- Длительность: 30 дней
- Трафик: Безлимит (введите "-")
- Устройства: 3
- Скорость: Без ограничений (введите "-")

#### 4.5. Настройка env переменных

Новых переменных окружения **не требуется**. Все изменения работают с существующими настройками.

Опционально можно настроить:
```env
# Валюта по умолчанию для тарифов
DEFAULT_CURRENCY=RUB

# Минимальная/максимальная сумма пополнения баланса
MIN_BALANCE_TOPUP=100
MAX_BALANCE_TOPUP=10000
```

#### 4.6. Откат миграции (если потребуется)

Откатить последнюю миграцию:
```bash
alembic downgrade -1
```

Откатить все миграции:
```bash
alembic downgrade base
```

---

### 5. Обратная совместимость

#### 5.1. Как работают старые подписки

Все существующие подписки **полностью совместимы** с новой системой:

✅ **Подписки без tariff_id:**
- Продолжают работать как обычно
- Поле `tariff_id` в таблице `subscriptions` опционально (`nullable=True`)
- Старая логика по-прежнему использует `duration_months`

✅ **Платежи без tariff_id:**
- Все старые платежи сохранены
- Поле `tariff_id` в таблице `payments` опционально
- История платежей не нарушена

✅ **Промокоды:**
- Старые промокоды типа `bonus_days` работают без изменений
- Новые типы (`discount`, `balance`) — дополнительные возможности

#### 5.2. Миграция данных

Миграция [`001_add_tariffs_balance_discounts.py`](db/migrations/versions/001_add_tariffs_balance_discounts.py:1) **только добавляет** новые таблицы и колонки, не изменяя существующие данные:

**Что добавляется:**
- ✅ Таблица `tariffs` (пустая)
- ✅ Таблица `user_balances` (пустая)
- ✅ Таблица `user_discounts` (пустая)
- ✅ Колонка `subscriptions.tariff_id` (NULL для всех записей)
- ✅ Колонка `payments.tariff_id` (NULL для всех записей)
- ✅ Колонка `users.balance` (0.0 для всех пользователей)

**Что НЕ изменяется:**
- ❌ Существующие платежи
- ❌ Существующие подписки
- ❌ Данные пользователей
- ❌ Промокоды

**Процесс миграции безопасен:**
```python
# Пример: существующая подписка
subscription = Subscription(
    user_id=12345,
    duration_months=1,
    tariff_id=None  # ← NULL, старая логика всё ещё работает
)
```

#### 5.3. Переход на новую систему

Пользователи и администраторы могут **постепенно** переходить на новую систему:

**Сценарий 1: Использование старой системы**
- Создавайте подписки как раньше (без выбора тарифа)
- Работает существующий функционал с фиксированными периодами
- `tariff_id` остается NULL

**Сценарий 2: Использование новой системы**
- Создайте тарифы через админ-панель
- Пользователи выбирают тариф при оплате
- `tariff_id` заполняется автоматически

**Сценарий 3: Смешанный режим**
- Старые пользователи используют старую схему
- Новые пользователи — новые тарифы
- Обе системы работают параллельно

---

### 6. Известные ограничения и TODO

#### 6.1. Текущие ограничения

❗ **Редактирование тарифов:**
- Пока доступно только создание, активация/деактивация и удаление
- TODO: Добавить редактирование всех параметров тарифа

❗ **Автоматическое применение скидок:**
- Скидки применяются только при ручной оплате
- TODO: Интеграция с автопродлением подписок

❗ **Статистика по тарифам:**
- Нет аналитики по популярности тарифов
- TODO: Добавить в админку статистику продаж по тарифам

❗ **История изменений скидок:**
- Нет логирования изменений персональных скидок
- TODO: Добавить audit log для скидок

#### 6.2. Планы на будущее

📋 **Высокий приоритет:**
- [ ] Редактирование существующих тарифов
- [ ] Копирование тарифов
- [ ] Массовая установка скидок (по группам пользователей)
- [ ] Экспорт статистики по тарифам
- [ ] Промокоды с ограничением по времени суток/днямнедели

📋 **Средний приоритет:**
- [ ] Сезонные тарифы с автоматическим изменением цен
- [ ] Пакеты тарифов (bundling)
- [ ] Подарочные сертификаты
- [ ] Реферальные бонусы на баланс
- [ ] Кэшбэк система

📋 **Низкий приоритет:**
- [ ] A/B тестирование тарифов
- [ ] Динамическое ценообразование
- [ ] Интеграция с CRM системами
- [ ] Мультивалютность

---

### 7. Примеры использования

#### 7.1. Создание тарифа через код

```python
from db.dal import tariff_dal
from sqlalchemy.ext.asyncio import AsyncSession

async def create_sample_tariff(session: AsyncSession):
    tariff_data = {
        "name": "Стандарт",
        "description": "Базовый тариф на месяц",
        "price": 299.0,
        "currency": "RUB",
        "duration_days": 30,
        "traffic_limit_bytes": None,  # Безлимит
        "device_limit": 3,
        "speed_limit_mbps": None,  # Без ограничений
        "is_active": True,
        "is_default": False
    }
    
    tariff = await tariff_dal.create_tariff(session, tariff_data)
    await session.commit()
    return tariff
```

#### 7.2. Установка персональной скидки

```python
from db.dal import discount_dal

async def set_user_discount(session: AsyncSession, user_id: int):
    discount = await discount_dal.create_user_discount(
        session=session,
        user_id=user_id,
        discount_percentage=20.0,  # 20% скидка
        tariff_id=None  # Применяется ко всем тарифам
    )
    await session.commit()
    return discount
```

#### 7.3. Пополнение баланса пользователя

```python
from bot.services.balance_service import BalanceService

async def topup_user_balance(
    session: AsyncSession,
    user_id: int,
    amount: float
):
    balance_service = BalanceService()
    
    operation = await balance_service.deposit(
        session=session,
        user_id=user_id,
        amount=amount,
        description="Пополнение баланса через YooKassa"
    )
    
    await session.commit()
    return operation
```

#### 7.4. Расчет цены с учетом скидок

```python
from bot.services.tariff_service import TariffService

async def calculate_price(
    session: AsyncSession,
    user_id: int,
    tariff_id: int,
    promo_code: str = None
):
    tariff_service = TariffService()
    
    result = await tariff_service.calculate_final_price(
        session=session,
        user_id=user_id,
        tariff_id=tariff_id,
        promo_code=promo_code
    )
    
    print(f"Базовая цена: {result['base_price']} {result['currency']}")
    print(f"Скидка: {result['discount_applied']} {result['currency']}")
    print(f"Итого: {result['final_price']} {result['currency']}")
    
    return result
```

---

### 8. Контакты и поддержка

📚 **Документация:**
- [`MIGRATION_GUIDE.md`](MIGRATION_GUIDE.md:1) - Детальная инструкция по миграциям
- [`db/migrations/README.md`](db/migrations/README.md:1) - Информация о системе миграций

🔗 **Связанные файлы:**
- Модели: [`db/models.py`](db/models.py:1)
- Миграция: [`db/migrations/versions/001_add_tariffs_balance_discounts.py`](db/migrations/versions/001_add_tariffs_balance_discounts.py:1)
- Конфигурация: [`alembic.ini`](alembic.ini:1)

---

## 🇬🇧 English Version

### Summary of Changes

A comprehensive tariff management system, user balance system, and personal discount system have been implemented. Full database migration infrastructure using Alembic has been added.

#### Main Features:
- ✅ Multiple tariff management system
- ✅ User balance system with transaction history
- ✅ Personal user discounts
- ✅ Extended promo code system (discounts, balance, bonus days)
- ✅ User profile with detailed information
- ✅ Balance top-up through payment systems
- ✅ Admin panel for tariff management
- ✅ Admin panel for discount management
- ✅ Database migrations via Alembic

#### List of New and Modified Files:

**Migrations and Database:**
- [`db/migrations/versions/001_add_tariffs_balance_discounts.py`](db/migrations/versions/001_add_tariffs_balance_discounts.py) ✨ NEW
- [`db/migrations/env.py`](db/migrations/env.py) ✨ NEW
- [`db/migrations/script.py.mako`](db/migrations/script.py.mako) ✨ NEW
- [`alembic.ini`](alembic.ini) ✨ NEW
- [`run_migrations.py`](run_migrations.py) ✨ NEW
- [`check_alembic.py`](check_alembic.py) ✨ NEW
- [`apply_migrations_auto.py`](apply_migrations_auto.py) ✨ NEW
- [`db/models.py`](db/models.py) - added `Tariff`, `UserBalance`, `UserDiscount` models

**DAL (Data Access Layer):**
- [`db/dal/tariff_dal.py`](db/dal/tariff_dal.py) ✨ NEW
- [`db/dal/balance_dal.py`](db/dal/balance_dal.py) ✨ NEW
- [`db/dal/discount_dal.py`](db/dal/discount_dal.py) ✨ NEW
- [`db/dal/promo_code_dal.py`](db/dal/promo_code_dal.py) - extended functionality
- [`db/dal/__init__.py`](db/dal/__init__.py) - updated imports

**Services:**
- [`bot/services/tariff_service.py`](bot/services/tariff_service.py) ✨ NEW
- [`bot/services/balance_service.py`](bot/services/balance_service.py) ✨ NEW
- [`bot/services/subscription_service.py`](bot/services/subscription_service.py) - tariff integration
- [`bot/services/yookassa_service.py`](bot/services/yookassa_service.py) - tariff support

**Handlers - User:**
- [`bot/handlers/user/profile.py`](bot/handlers/user/profile.py) ✨ NEW
- [`bot/handlers/user/balance_topup.py`](bot/handlers/user/balance_topup.py) ✨ NEW
- [`bot/handlers/user/tariff_selection.py`](bot/handlers/user/tariff_selection.py) ✨ NEW
- [`bot/handlers/user/payment.py`](bot/handlers/user/payment.py) - tariff integration
- [`bot/handlers/user/subscription/payments.py`](bot/handlers/user/subscription/payments.py) - updated

**Handlers - Admin:**
- [`bot/handlers/admin/tariff_management.py`](bot/handlers/admin/tariff_management.py) ✨ NEW
- [`bot/handlers/admin/discount_management.py`](bot/handlers/admin/discount_management.py) ✨ NEW
- [`bot/handlers/admin/promo/create.py`](bot/handlers/admin/promo/create.py) - extended
- [`bot/handlers/admin/common.py`](bot/handlers/admin/common.py) - updated

**States and Keyboards:**
- [`bot/states/user_states.py`](bot/states/user_states.py) - new states added
- [`bot/states/admin_states.py`](bot/states/admin_states.py) - new states added
- [`bot/keyboards/inline/user_keyboards.py`](bot/keyboards/inline/user_keyboards.py) - new keyboards
- [`bot/keyboards/inline/admin_keyboards.py`](bot/keyboards/inline/admin_keyboards.py) - new keyboards

**Localization:**
- [`locales/ru.json`](locales/ru.json) - ~150 new keys added
- [`locales/en.json`](locales/en.json) - ~150 new keys added

**Documentation:**
- [`MIGRATION_GUIDE.md`](MIGRATION_GUIDE.md) ✨ NEW
- [`db/migrations/README.md`](db/migrations/README.md) ✨ NEW

---

### Deployment Instructions

#### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

#### 2. Apply Database Migrations

**Option 1: Automatic (recommended)**
```bash
python apply_migrations_auto.py
```

**Option 2: Via script**
```bash
python run_migrations.py
```

**Option 3: Direct Alembic**
```bash
alembic upgrade head
```

**In Docker container:**
```bash
docker exec remnawave-tg-shop python apply_migrations_auto.py
```

#### 3. Create First Tariff

After applying migrations, create tariffs through the admin panel:
1. Launch the bot
2. Open admin panel (only for `ADMIN_IDS`)
3. Navigate: **💰 Tariffs and Pricing** → **📋 Tariff Management** → **➕ Create Tariff**
4. Follow the step-by-step tariff creation process

#### 4. Verify Migration

Check current DB version:
```bash
alembic current
```

View history:
```bash
alembic history --verbose
```

---

### Backward Compatibility

All existing subscriptions are **fully compatible** with the new system:

✅ **Subscriptions without tariff_id:**
- Continue to work as before
- The `tariff_id` field is optional (`nullable=True`)
- Old logic still uses `duration_months`

✅ **Payments without tariff_id:**
- All old payments are preserved
- The `tariff_id` field is optional
- Payment history is intact

✅ **Promo codes:**
- Old `bonus_days` promo codes work without changes
- New types (`discount`, `balance`) are additional features

The migration **only adds** new tables and columns without modifying existing data.

---

### Contact and Support

📚 **Documentation:**
- [`MIGRATION_GUIDE.md`](MIGRATION_GUIDE.md:1) - Detailed migration instructions
- [`db/migrations/README.md`](db/migrations/README.md:1) - Migration system information

🔗 **Related Files:**
- Models: [`db/models.py`](db/models.py:1)
- Migration: [`db/migrations/versions/001_add_tariffs_balance_discounts.py`](db/migrations/versions/001_add_tariffs_balance_discounts.py:1)
- Configuration: [`alembic.ini`](alembic.ini:1)

---

**Date:** November 23, 2024  
**Version:** 1.0.0  
**Migration:** 001_add_tariffs_balance_discounts