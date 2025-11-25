#!/bin/bash

# ============================================
# Интерактивная установка Remnawave Bot
# для Ubuntu 24.04 с Docker
# ============================================

set -e  # Exit on error

echo "======================================"
echo "Remnawave Bot - Интерактивная установка"
echo "======================================"
echo ""

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функции
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

print_header() {
    echo ""
    echo "======================================"
    echo "$1"
    echo "======================================"
}

# Функция для ввода с проверкой
input_with_validation() {
    local prompt="$1"
    local var_name="$2"
    local validation_regex="$3"
    local error_message="$4"
    local default_value="$5"
    
    while true; do
        if [ -n "$default_value" ]; then
            read -p "$prompt [$default_value]: " input
            if [ -z "$input" ]; then
                input="$default_value"
            fi
        else
            read -p "$prompt: " input
        fi
        
        if [ -z "$input" ]; then
            print_error "Это поле обязательно для заполнения!"
            continue
        fi
        
        if [ -n "$validation_regex" ] && ! echo "$input" | grep -qE "$validation_regex"; then
            print_error "$error_message"
            continue
        fi
        
        eval "$var_name='$input'"
        break
    done
}

# Функция для ввода с подтверждением
input_with_confirmation() {
    local prompt="$1"
    local var_name="$2"
    local confirmation_prompt="$3"
    
    while true; do
        read -p "$prompt: " input
        if [ -z "$input" ]; then
            print_error "Это поле обязательно для заполнения!"
            continue
        fi
        
        read -p "$confirmation_prompt ['$input']: " confirmation
        if [ -z "$confirmation" ]; then
            confirmation="$input"
        fi
        
        if [ "$input" != "$confirmation" ]; then
            print_error "Значения не совпадают! Попробуйте еще раз."
            continue
        fi
        
        eval "$var_name='$input'"
        break
    done
}

# Функция для выбора да/нет
ask_yes_no() {
    local prompt="$1"
    local default="$2"
    
    while true; do
        if [ "$default" = "yes" ]; then
            read -p "$prompt [Y/n]: " answer
            answer=${answer:-y}
        elif [ "$default" = "no" ]; then
            read -p "$prompt [y/N]: " answer
            answer=${answer:-n}
        else
            read -p "$prompt [y/n]: " answer
        fi
        
        case $answer in
            [Yy]|[Yy][Ee][Ss]) return 0 ;;
            [Nn]|[Nn][Oo]) return 1 ;;
            *) print_error "Пожалуйста, введите 'y' или 'n'" ;;
        esac
    done
}

# Проверка что запущено от root
if [ "$EUID" -ne 0 ]; then 
    print_error "Пожалуйста, запустите скрипт от root: sudo ./interactive-install.sh"
    exit 1
fi

print_success "Запущено от root"

# ============================================
# ШАГ 1: Обновление системы
# ============================================
print_header "Шаг 1/12: Обновление системы"
print_info "Обновление пакетов системы..."
apt update -qq
apt upgrade -y -qq
apt install -y ca-certificates curl gnupg lsb-release git nano ufw
print_success "Система обновлена"

# ============================================
# ШАГ 2: Установка Docker
# ============================================
print_header "Шаг 2/12: Установка Docker"

if command -v docker &> /dev/null; then
    print_warning "Docker уже установлен, пропускаем..."
else
    print_info "Установка Docker..."
    mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    apt update -qq
    apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable docker
    systemctl start docker
    print_success "Docker установлен"
fi

DOCKER_VERSION=$(docker --version)
print_info "Docker версия: $DOCKER_VERSION"

# ============================================
# ШАГ 3: Настройка Firewall
# ============================================
print_header "Шаг 3/12: Настройка Firewall"
print_info "Настройка UFW firewall..."
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
echo "y" | ufw enable
print_success "Firewall настроен (порты 22, 80, 443 открыты)"

# ============================================
# ШАГ 4: Сбор базовой информации о боте
# ============================================
print_header "Шаг 4/12: Настройка Telegram Bot"

print_info "Давайте настроим вашего Telegram бота. Вам понадобятся:"
print_info "1. Токен бота (получите у @BotFather)"
print_info "2. Ваш Telegram ID (можно узнать у @userinfobot)"
print_info ""

# Ввод токена бота
input_with_validation "Введите токен вашего бота" "BOT_TOKEN" '^[0-9]+:[A-Za-z0-9_-]+$' "Неверный формат токена. Токен должен выглядеть как: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz"

# Ввод ID администратора
input_with_validation "Введите ваш Telegram ID" "ADMIN_IDS" '^[0-9]+$' "ID должен содержать только цифры"

print_success "Настройки бота сохранены"

# ============================================
# ШАГ 5: Настройка домена
# ============================================
print_header "Шаг 5/12: Настройка домена"

print_info "Введите домен, который будет использоваться для бота:"
print_info "Пример: bot.yourdomain.com"
print_info ""

input_with_validation "Введите домен для бота" "DOMAIN" '^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$' "Неверный формат домена. Пример: bot.yourdomain.com"

# Формирование URL
WEBHOOK_BASE_URL="https://$DOMAIN"
print_info "Webhook URL: $WEBHOOK_BASE_URL"

print_success "Домен настроен"

# ============================================
# ШАГ 6: Настройка базы данных
# ============================================
print_header "Шаг 6/12: Настройка базы данных"

print_info "Настройка PostgreSQL..."
print_info "Рекомендуется использовать сложный пароль"

# Ввод пароля БД
input_with_confirmation "Введите пароль для PostgreSQL" "POSTGRES_PASSWORD" "Подтвердите пароль PostgreSQL"

print_success "Пароль базы данных установлен"

# ============================================
# ШАГ 7: Настройка платежных систем
# ============================================
print_header "Шаг 7/12: Настройка платежных систем"

print_info "Выберите платежные системы, которые хотите использовать:"

# YooKassa
if ask_yes_no "Включить YooKassa?" "yes"; then
    YOOKASSA_ENABLED=True
    input_with_validation "Введите YooKassa Shop ID" "YOOKASSA_SHOP_ID" '^[0-9]+$' "Shop ID должен содержать только цифры"
    input_with_validation "Введите YooKassa Secret Key" "YOOKASSA_SECRET_KEY" '^[A-Za-z0-9_-]+$' "Неверный формат ключа"
    input_with_validation "Введите email для чеков" "YOOKASSA_DEFAULT_RECEIPT_EMAIL" '^[^@]+@[^@]+\.[^@]+$' "Неверный формат email"
    print_success "YooKassa настроен"
else
    YOOKASSA_ENABLED=False
fi

# CryptoPay
if ask_yes_no "Включить CryptoPay?" "yes"; then
    CRYPTOPAY_ENABLED=True
    input_with_validation "Введите CryptoPay токен" "CRYPTOPAY_TOKEN" '^[0-9]+:[A-Za-z0-9_-]+$' "Неверный формат токена"
    print_success "CryptoPay настроен"
else
    CRYPTOPAY_ENABLED=False
fi

# Telegram Stars
if ask_yes_no "Включить Telegram Stars?" "yes"; then
    STARS_ENABLED=True
    print_success "Telegram Stars включен"
else
    STARS_ENABLED=False
fi

# FreeKassa
if ask_yes_no "Включить FreeKassa?" "no"; then
    FREEKASSA_ENABLED=True
    print_info "FreeKassa включен (настройте позже в .env файле)"
else
    FREEKASSA_ENABLED=False
fi

print_success "Платежные системы настроены"

# ============================================
# ШАГ 8: Настройка VPN Panel
# ============================================
print_header "Шаг 8/12: Настройка VPN Panel"

print_info "Введите данные для подключения к VPN панели:"

input_with_validation "Введите URL VPN панели" "PANEL_API_URL" '^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}' "Неверный URL. Пример: https://panel.yourdomain.com"
input_with_validation "Введите API ключ панели" "PANEL_API_KEY" '^[A-Za-z0-9._-]+$' "Неверный формат API ключа"

print_success "VPN Panel настроена"

# ============================================
# ШАГ 9: Настройка канала и поддержки
# ============================================
print_header "Шаг 9/12: Настройка канала и поддержки"

# Канал
if ask_yes_no "Требовать подписку на канал?" "yes"; then
    input_with_validation "Введите ID канала" "REQUIRED_CHANNEL_ID" '^-?[0-9]+$' "ID канала должен быть числом (может начинаться с -100)"
    input_with_validation "Введите ссылку на канал" "REQUIRED_CHANNEL_LINK" '^https://t\.me/[^/]+$' "Неверная ссылка. Пример: https://t.me/yourchannel"
    print_success "Канал настроен"
else
    REQUIRED_CHANNEL_ID=""
    REQUIRED_CHANNEL_LINK=""
fi

# Поддержка
input_with_validation "Введите ссылку на поддержку" "SUPPORT_LINK" '^https://t\.me/[^/]+$' "Неверная ссылка. Пример: https://t.me/support"

print_success "Поддержка настроена"

# ============================================
# ШАГ 10: Создание .env файла
# ============================================
print_header "Шаг 10/12: Создание конфигурации"

print_info "Создание файла .env с вашими настройками..."

# Создание .env файла
cat > .env << EOF
# ====================================================================================================
# TELEGRAM BOT CONFIGURATION
# ====================================================================================================
BOT_TOKEN=$BOT_TOKEN
ADMIN_IDS=$ADMIN_IDS

# ====================================================================================================
# DATABASE CONFIGURATION
# ====================================================================================================
POSTGRES_USER=postgres
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
POSTGRES_HOST=remnawave-tg-shop-db
POSTGRES_PORT=5432
POSTGRES_DB=postgres

# ====================================================================================================
# LOCALIZATION & DISPLAY
# ====================================================================================================
DEFAULT_LANGUAGE="ru"
DEFAULT_CURRENCY_SYMBOL="RUB"

# ====================================================================================================
# EXTERNAL LINKS & UI
# ====================================================================================================
SUPPORT_LINK=$SUPPORT_LINK
SERVER_STATUS_URL=https://status.yourdomain.tld/status/your_service
TERMS_OF_SERVICE_URL=https://example.com/tos
SUBSCRIPTION_MINI_APP_URL=
START_COMMAND_DESCRIPTION=
DISABLE_WELCOME_MESSAGE=
MY_DEVICES_SECTION_ENABLED=False
USER_HWID_DEVICE_LIMIT=0

# ====================================================================================================
# REQUIRED CHANNEL SUBSCRIPTION
# ====================================================================================================
REQUIRED_CHANNEL_ID=$REQUIRED_CHANNEL_ID
REQUIRED_CHANNEL_LINK=$REQUIRED_CHANNEL_LINK

# ====================================================================================================
# WEBHOOK CONFIGURATION
# ====================================================================================================
WEBHOOK_BASE_URL=$WEBHOOK_BASE_URL

# ====================================================================================================
# PAYMENT METHODS TOGGLES
# ====================================================================================================
YOOKASSA_ENABLED=$YOOKASSA_ENABLED
FREEKASSA_ENABLED=$FREEKASSA_ENABLED
STARS_ENABLED=$STARS_ENABLED
TRIBUTE_ENABLED=False
CRYPTOPAY_ENABLED=$CRYPTOPAY_ENABLED

# ====================================================================================================
# YOOKASSA PAYMENT GATEWAY
# ====================================================================================================
YOOKASSA_SHOP_ID=$YOOKASSA_SHOP_ID
YOOKASSA_SECRET_KEY=$YOOKASSA_SECRET_KEY
YOOKASSA_RETURN_URL=https://t.me/gettestvpn_bot
YOOKASSA_DEFAULT_RECEIPT_EMAIL=$YOOKASSA_DEFAULT_RECEIPT_EMAIL
YOOKASSA_VAT_CODE=1
YOOKASSA_AUTOPAYMENTS_ENABLED=False
YOOKASSA_AUTOPAYMENTS_REQUIRE_CARD_BINDING=True

# ====================================================================================================
# CRYPTOPAY (CRYPTOBOT) PAYMENT GATEWAY
# ====================================================================================================
CRYPTOPAY_TOKEN=$CRYPTOPAY_TOKEN
CRYPTOPAY_NETWORK=mainnet
CRYPTOPAY_CURRENCY_TYPE=fiat
CRYPTOPAY_ASSET=RUB

# ====================================================================================================
# SUBSCRIPTION TARIFFS & PRICING
# ====================================================================================================
1_MONTH_ENABLED=True
RUB_PRICE_1_MONTH=150
STARS_PRICE_1_MONTH=150
TRIBUTE_LINK_1_MONTH=

3_MONTHS_ENABLED=True
RUB_PRICE_3_MONTHS=300
STARS_PRICE_3_MONTHS=300
TRIBUTE_LINK_3_MONTHS=

6_MONTHS_ENABLED=True
RUB_PRICE_6_MONTHS=500
STARS_PRICE_6_MONTHS=500
TRIBUTE_LINK