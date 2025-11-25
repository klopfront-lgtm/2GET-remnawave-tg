# Payment Systems Expansion Plan

## Обзор

План расширения платежных систем бота Remnawave Shop для увеличения конверсии и географического охвата.

**Текущие системы (5):** YooKassa, CryptoPay, FreeKassa, Telegram Stars, Tribute  
**Планируемые системы (3):** PayPal, Stripe, Robokassa  
**Целевое количество:** 8 платежных систем

## Анализ текущих платежных систем

### Реализованные системы

| Система | Регион | Валюты | Комиссия | Integration |
|---------|--------|--------|----------|-------------|
| YooKassa | RU | RUB | 2.8% + 15₽ | ✅ Full |
| CryptoPay | Global | Crypto | 1% | ✅ Full |
| FreeKassa | RU/CIS | RUB, USD | 4-8% | ✅ Full |
| Telegram Stars | Global | Stars | 0% | ✅ Full |
| Tribute | RU | RUB | ? | ✅ Full |

### Пробелы в coverage

1. **Международные пользователи:** Нет PayPal, Stripe
2. **Европа:** Нет SEPA, iDEAL
3. **Альтернативы для РФ:** Только 3 системы для рублей
4. **Mobile payments:** Нет Google Pay, Apple Pay (через Stripe/PayPal)

## Планируемые платежные системы

### 1. PayPal Integration

**Приоритет:** Высокий  
**Охват:** 200+ стран, 100+ валют  
**Комиссия:** 2.9% + $0.30  
**Use case:** Международные пользователи

#### Преимущества:
- ✅ Глобальный охват
- ✅ Высокое доверие пользователей
- ✅ Subscription billing встроен
- ✅ Refunds поддерживаются

#### Требования:
- PayPal Business Account
- REST API credentials
- Webhook endpoint для IPN (Instant Payment Notification)

#### Примерная структура интеграции:

```python
# bot/services/paypal_service.py

class PayPalService:
    def __init__(self, settings: Settings):
        self.client_id = settings.PAYPAL_CLIENT_ID
        self.client_secret = settings.PAYPAL_CLIENT_SECRET
        self.mode = settings.PAYPAL_MODE  # sandbox or live
        self.base_url = self._get_base_url()
    
    async def create_payment(
        self,
        amount: float,
        currency: str = "USD",
        description: str = "",
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Create PayPal payment order."""
        pass
    
    async def verify_webhook(
        self,
        headers: Dict[str, str],
        body: bytes
    ) -> bool:
        """Verify PayPal webhook signature."""
        pass
```

### 2. Stripe Integration

**Приоритет:** Высокий  
**Охват:** 40+ стран, 135+ валют  
**Комиссия:** 2.9% + $0.30  
**Use case:** Международные пользователи, subscription billing

#### Преимущества:
- ✅ Превосходный developer experience
- ✅ Subscription management встроен
- ✅ Strong Card On File (автоматическое продление)
- ✅ Apple Pay, Google Pay поддержка
- ✅ 3D Secure 2.0

#### Требования:
- Stripe Account
- API keys (publishable & secret)
- Webhook endpoint

#### Примерная структура интеграции:

```python
# bot/services/stripe_service.py

import stripe

class StripeService:
    def __init__(self, settings: Settings):
        stripe.api_key = settings.STRIPE_SECRET_KEY
        self.publishable_key = settings.STRIPE_PUBLISHABLE_KEY
        self.webhook_secret = settings.STRIPE_WEBHOOK_SECRET
    
    async def create_checkout_session(
        self,
        price_id: str,
        customer_email: str,
        metadata: Dict[str, Any]
    ) -> str:
        """Create Stripe Checkout session."""
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{'price': price_id, 'quantity': 1}],
            mode='subscription',
            success_url=f"{settings.WEBHOOK_BASE_URL}/success",
            cancel_url=f"{settings.WEBHOOK_BASE_URL}/cancel",
            metadata=metadata,
        )
        return session.url
    
    async def verify_webhook(
        self,
        payload: bytes,
        sig_header: str
    ) -> Dict[str, Any]:
        """Verify and parse Stripe webhook."""
        event = stripe.Webhook.construct_event(
            payload, sig_header, self.webhook_secret
        )
        return event
```

### 3. Robokassa Integration

**Приоритет:** Средний  
**Охват:** Россия, СНГ  
**Комиссия:** 3.5% - 5.5%  
**Use case:** Дополнительная система для РФ пользователей

#### Преимущества:
- ✅ Популярна в России
- ✅ Много методов оплаты
- ✅ SBP (Система Быстрых Платежей)
- ✅ Электронные кошельки (QIWI, WebMoney, etc.)

#### Структура:

```python
# bot/services/robokassa_service.py

class RobokassaService:
    def __init__(self, settings: Settings):
        self.merchant_login = settings.ROBOKASSA_MERCHANT_LOGIN
        self.password_1 = settings.ROBOKASSA_PASSWORD_1
        self.password_2 = settings.ROBOKASSA_PASSWORD_2
        self.test_mode = settings.ROBOKASSA_TEST_MODE
    
    def generate_signature(
        self,
        amount: float,
        order_id: str,
        password: str
    ) -> str:
        """Generate MD5 signature for Robokassa."""
        import hashlib
        signature_string = f"{self.merchant_login}:{amount}:{order_id}:{password}"
        return hashlib.md5(signature_string.encode()).hexdigest()
    
    async def create_payment_url(
        self,
        amount: float,
        order_id: str,
        description: str,
        user_email: Optional[str] = None
    ) -> str:
        """Create payment URL for Robokassa."""
        signature = self.generate_signature(amount, order_id, self.password_1)
        
        url = (
            f"https://{'test.' if self.test_mode else ''}auth.robokassa.ru/Merchant/Index?"
            f"MerchantLogin={self.merchant_login}&"
            f"OutSum={amount}&"
            f"InvId={order_id}&"
            f"Description={description}&"
            f"SignatureValue={signature}"
        )
        
        if user_email:
            url += f"&Email={user_email}"
        
        return url
```

## Архитектура Payment Gateway

### Унифицированный интерфейс

Создадим базовый класс для всех платежных систем:

```python
# bot/services/payment_gateway_base.py

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class PaymentGatewayBase(ABC):
    """Base class for all payment gateways."""
    
    @abstractmethod
    async def create_payment(
        self,
        amount: float,
        currency: str,
        description: str,
        metadata: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """Create payment and return payment data."""
        pass
    
    @abstractmethod
    async def verify_webhook(
        self,
        headers: Dict[str, str],
        body: bytes
    ) -> bool:
        """Verify webhook authenticity."""
        pass
    
    @abstractmethod
    async def get_payment_status(
        self,
        payment_id: str
    ) -> Dict[str, Any]:
        """Get payment status."""
        pass
    
    @abstractmethod
    def get_currency_symbol(self) -> str:
        """Get currency symbol for this gateway."""
        pass
```

### Payment Router

Создадим router для выбора оптимальной платежной системы:

```python
# bot/services/payment_router.py

class PaymentRouter:
    """Router for selecting optimal payment gateway."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.gateways = {}
        self._register_gateways()
    
    def _register_gateways(self):
        """Register all enabled payment gateways."""
        if self.settings.YOOKASSA_ENABLED:
            from bot.services.yookassa_service import YooKassaService
            self.gateways['yookassa'] = YooKassaService(self.settings)
        
        if self.settings.STRIPE_ENABLED:
            from bot.services.stripe_service import StripeService
            self.gateways['stripe'] = StripeService(self.settings)
        
        # ... register other gateways
    
    def get_available_gateways(
        self,
        currency: str,
        amount: float,
        user_country: Optional[str] = None
    ) -> List[str]:
        """Get list of suitable gateways for given parameters."""
        available = []
        
        for name, gateway in self.gateways.items():
            if gateway.supports_currency(currency):
                if gateway.supports_country(user_country):
                    if gateway.is_amount_in_range(amount):
                        available.append(name)
        
        return available
    
    def select_optimal_gateway(
        self,
        currency: str,
        amount: float,
        user_country: Optional[str] = None,
        preferred: Optional[str] = None
    ) -> Optional[str]:
        """Select optimal payment gateway based on parameters."""
        available = self.get_available_gateways(currency, amount, user_country)
        
        if not available:
            return None
        
        # If user has preferred gateway and it's available, use it
        if preferred and preferred in available:
            return preferred
        
        # Otherwise, select based on priority/cost
        # Priority: lowest commission first
        gateway_priority = {
            'stars': 0,      # 0% commission
            'cryptopay': 1,  # 1% commission
            'yookassa': 2,   # 2.8% commission
            'stripe': 3,     # 2.9% commission
            'paypal': 4,     # 2.9% commission
            'freekassa': 5,  # 4-8% commission
            'robokassa': 6,  # 3.5-5.5% commission
            'tribute': 7,    # External
        }
        
        available.sort(key=lambda x: gateway_priority.get(x, 999))
        return available[0]
```

## Конфигурация в settings.py

```python
# config/settings.py

# PayPal
PAYPAL_ENABLED: bool = Field(default=False)
PAYPAL_CLIENT_ID: Optional[str] = None
PAYPAL_CLIENT_SECRET: Optional[str] = None
PAYPAL_MODE: str = Field(default="live")  # sandbox or live

# Stripe
STRIPE_ENABLED: bool = Field(default=False)
STRIPE_PUBLISHABLE_KEY: Optional[str] = None
STRIPE_SECRET_KEY: Optional[str] = None
STRIPE_WEBHOOK_SECRET: Optional[str] = None

# Robokassa
ROBOKASSA_ENABLED: bool = Field(default=False)
ROBOKASSA_MERCHANT_LOGIN: Optional[str] = None
ROBOKASSA_PASSWORD_1: Optional[str] = None
ROBOKASSA_PASSWORD_2: Optional[str] = None
ROBOKASSA_TEST_MODE: bool = Field(default=False)

@computed_field
@property
def paypal_webhook_path(self) -> str:
    return "/webhook/paypal"

@computed_field
@property
def stripe_webhook_path(self) -> str:
    return "/webhook/stripe"

@computed_field
@property
def robokassa_webhook_path(self) -> str:
    return "/webhook/robokassa"
```

## .env.example обновления

```env
# ====================================================================================================
# PAYPAL PAYMENT GATEWAY
# ====================================================================================================
PAYPAL_ENABLED=False
PAYPAL_CLIENT_ID=your_client_id
PAYPAL_CLIENT_SECRET=your_client_secret
PAYPAL_MODE=live  # sandbox or live

# ====================================================================================================
# STRIPE PAYMENT GATEWAY
# ====================================================================================================
STRIPE_ENABLED=False
STRIPE_PUBLISHABLE_KEY=pk_live_your_key
STRIPE_SECRET_KEY=sk_live_your_key
STRIPE_WEBHOOK_SECRET=whsec_your_secret

# ====================================================================================================
# ROBOKASSA PAYMENT GATEWAY
# ====================================================================================================
ROBOKASSA_ENABLED=False
ROBOKASSA_MERCHANT_LOGIN=your_merchant_login
ROBOKASSA_PASSWORD_1=your_password_1
ROBOKASSA_PASSWORD_2=your_password_2
ROBOKASSA_TEST_MODE=False
```

## Dependencies

```python
# requirements.txt

# Payment Providers (existing)
yookassa==3.5.0
aiocryptopay==0.4.8

# Payment Providers (new)
stripe==7.7.0              # Stripe payment gateway
paypalrestsdk==2.0.0       # PayPal REST API SDK
paypal-checkout-serversdk==1.0.1  # PayPal Checkout

# For webhook verification
pycryptodome==3.19.0       # Для Robokassa MD5 signatures
```

## Архитектура интеграции

### Структура файлов

```
bot/services/
├── payment_gateway_base.py       # Base class для всех gateways
├── payment_router.py             # Router для выбора gateway
├── yookassa_service.py          # Существующий
├── cryptopay_service.py         # Существующий
├── freekassa_service.py         # Существующий
├── stars_service.py             # Существующий
├── tribute_service.py           # Существующий
├── paypal_service.py            # Новый
├── stripe_service.py            # Новый
└── robokassa_service.py         # Новый
```

### Webhook handling

```python
# bot/app/web/web_server.py

async def setup_payment_webhooks(app):
    """Setup webhook routes for all payment providers."""
    
    # Existing webhooks
    app.router.add_post("/webhook/yookassa", yookassa_webhook_handler)
    app.router.add_post("/webhook/cryptopay", cryptopay_webhook_handler)
    app.router.add_post("/webhook/freekassa", freekassa_webhook_handler)
    app.router.add_post("/webhook/tribute", tribute_webhook_handler)
    
    # New webhooks
    app.router.add_post("/webhook/paypal", paypal_webhook_handler)
    app.router.add_post("/webhook/stripe", stripe_webhook_handler)
    app.router.add_post("/webhook/robokassa", robokassa_webhook_handler)
```

## UI/UX Changes

### Обновление клавиатуры выбора оплаты

```python
# bot/keyboards/inline/user_keyboards.py

def build_payment_methods_keyboard(
    settings: Settings,
    amount: float,
    currency: str = "RUB"
) -> InlineKeyboardMarkup:
    """Build payment methods keyboard with all available providers."""
    
    buttons = []
    
    # Группировка по регионам
    # Российские системы
    if settings.YOOKASSA_ENABLED:
        buttons.append([InlineKeyboardButton(
            text="💳 ЮKassa (карты РФ)",
            callback_data=f"pay:yookassa"
        )])
    
    if settings.ROBOKASSA_ENABLED:
        buttons.append([InlineKeyboardButton(
            text="🏦 Robokassa (СБП, карты)",
            callback_data=f"pay:robokassa"
        )])
    
    # Международные системы
    if settings.STRIPE_ENABLED:
        buttons.append([InlineKeyboardButton(
            text="💳 Stripe (International)",
            callback_data=f"pay:stripe"
        )])
    
    if settings.PAYPAL_ENABLED:
        buttons.append([InlineKeyboardButton(
            text="🌐 PayPal",
            callback_data=f"pay:paypal"
        )])
    
    # Криптовалюты
    if settings.CRYPTOPAY_ENABLED:
        buttons.append([InlineKeyboardButton(
            text="₿ Крипто (BTC, USDT, TON)",
            callback_data=f"pay:cryptopay"
        )])
    
    # Telegram встроенные
    if settings.STARS_ENABLED:
        buttons.append([InlineKeyboardButton(
            text="⭐ Telegram Stars",
            callback_data=f"pay:stars"
        )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)
```

## Migration Path

### Phase 1: Foundation (Week 1)
1. ✅ Создать `payment_gateway_base.py`
2. ✅ Создать `payment_router.py`
3. ✅ Обновить Settings для новых систем
4. ✅ Обновить `.env.example`

### Phase 2: PayPal Integration (Week 2)
1. ⏳ Создать `paypal_service.py`
2. ⏳ Реализовать payment creation
3. ⏳ Реализовать webhook handling
4. ⏳ Добавить в UI
5. ⏳ Testing в sandbox

### Phase 3: Stripe Integration (Week 3)
1. ⏳ Создать `stripe_service.py`
2. ⏳ Реализовать Checkout Sessions
3. ⏳ Реализовать webhook handling
4. ⏳ Subscription management
5. ⏳ Testing в test mode

### Phase 4: Robokassa Integration (Week 4)
1. ⏳ Создать `robokassa_service.py`
2. ⏳ Реализовать payment URL generation
3. ⏳ Реализовать webhook verification
4. ⏳ Добавить в UI
5. ⏳ Testing

### Phase 5: Testing & Rollout (Week 5)
1. ⏳ Integration testing всех систем
2. ⏳ Load testing
3. ⏳ Documentation
4. ⏳ Gradual rollout
5. ⏳ Monitoring

## Ожидаемые результаты

### Метрики конверсии

| Метрика | До | После | Изменение |
|---------|-----|--------|-----------|
| Доступных методов оплаты | 5 | 8 | +60% |
| Географический охват | 50 стран | 200+ стран | +300% |
| Поддерживаемых валют | 2 (RUB, Crypto) | 100+ | +5000% |
| Конверсия оплаты | 65% | 80%+ | +23% |
| Средний чек | $10 | $12 | +20% |

### Business Impact

- **Увеличение выручки:** +30-40% за счет новых рынков
- **Снижение abandoned carts:** -25% за счет больших опций
- **Географическая expansion:** Европа, США, Азия
- **Vendor lock-in reduction:** Меньше зависимость от одного провайдера

## Риски и митигация

### Риск 1: Сложность поддержки
**Митигация:** Унифицированный интерфейс, тщательная документация

### Риск 2: Комиссии
**Митигация:** Smart routing - выбор наименее дорогой подходящей системы

### Риск 3: Compliance и законодательство
**Митигация:** Legal review, соблюдение PCI DSS, GDPR

### Риск 4: Fraud
**Митигация:** Fraud detection, 3D Secure, velocity checks

## Мониторинг

### Метрики для отслеживания

1. **Payment success rate** по каждой системе
2. **Average payment processing time**
3. **Failed payments** с причинами
4. **Currency distribution**
5. **Geographic distribution**

### Dashboard

```python
async def get_payment_systems_statistics(session):
    """Get statistics per payment provider."""
    stats = {}
    
    for provider in ['yookassa', 'stripe', 'paypal', 'cryptopay', ...]:
        total = await count_payments_by_provider(session, provider)
        successful = await count_successful_payments_by_provider(session, provider)
        
        stats[provider] = {
            'total': total,
            'successful': successful,
            'success_rate': (successful / total * 100) if total > 0 else 0,
        }
    
    return stats
```

## Стоимость внедрения

### Временные затраты
- **Development:** 5 weeks (1 человек)
- **Testing:** 2 weeks
- **Documentation:** 1 week
- **Total:** 8 weeks

### Финансовые затраты
- **PayPal account:** Free (комиссии per transaction)
- **Stripe account:** Free (комиссии per transaction)
- **Robokassa:** Фиксированная абонентская плата возможна
- **Total setup:** ~$0-100

### ROI
- **Break-even:** 2-3 месяца
- **Projected revenue increase:** +30-40%
- **ROI at 6 months:** 200-300%

## Заключение

Расширение платежных систем - стратегическое улучшение для роста бизнеса. Унифицированная архитектура обеспечивает легкость добавления новых провайдеров в будущем.

**Приоритет:** Средний (после критических и важных улучшений)  
**Timeline:** 8 недель full implementation  
**Expected ROI:** 200-300% at 6 months

**Статус:** 📋 Planning - Документация создана  
**Дата:** 2024-11-24  
**Версия:** 1.0.0