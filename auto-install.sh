#!/bin/bash

# ============================================
# Автоматическая установка Remnawave Bot
# для Ubuntu 24.04 с Docker и автоматическим SSL
# ============================================

set -e  # Exit on error

echo "======================================"
echo "Remnawave Bot - Автоматическая установка"
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

# Проверка что запущено от root
if [ "$EUID" -ne 0 ]; then 
    print_error "Пожалуйста, запустите скрипт от root: sudo ./auto-install.sh"
    exit 1
fi

print_success "Запущено от root"

# ============================================
# ШАГ 1: Проверка .env файла
# ============================================
print_header "Шаг 1/8: Проверка конфигурации"

if [ ! -f .env ]; then
    print_error ".env файл не найден!"
    print_info "Сначала настройте .env файл:"
    print_info "1. Скопируйте пример: cp .env.example .env"
    print_info "2. Отредактируйте файл: nano .env"
    print_info "3. Укажите как минимум:"
    print_info "   - BOT_TOKEN=ваш_токен_от_BotFather"
    print_info "   - ADMIN_IDS=ваш_telegram_id"
    print_info "   - WEBHOOK_BASE_URL=https://ваш_домен.com"
    print_info "   - POSTGRES_PASSWORD=сложный_пароль"
    print_info "   - PANEL_API_URL=http://адрес_панели/api"
    print_info "   - PANEL_API_KEY=ваш_api_ключ"
    echo ""
    print_info "После настройки .env файла запустите скрипт снова"
    exit 1
fi

# Проверка обязательных параметров
MISSING_PARAMS=()

if grep -q "your_bot_token_here" .env; then
    MISSING_PARAMS+=("BOT_TOKEN")
fi

if grep -q "yourdomain.com" .env 2>/dev/null || ! grep -q "WEBHOOK_BASE_URL=https://" .env; then
    MISSING_PARAMS+=("WEBHOOK_BASE_URL")
fi

if grep -q "your_panel_api_url" .env; then
    MISSING_PARAMS+=("PANEL_API_URL")
fi

if grep -q "your_panel_api_key" .env; then
    MISSING_PARAMS+=("PANEL_API_KEY")
fi

if [ ${#MISSING_PARAMS[@]} -gt 0 ]; then
    print_error "Не настроены обязательные параметры в .env:"
    for param in "${MISSING_PARAMS[@]}"; do
        print_error "  - $param"
    done
    print_info "Отредактируйте .env файл и запустите скрипт снова"
    exit 1
fi

print_success ".env файл настроен правильно"

# Извлечение домена из .env
DOMAIN=$(grep WEBHOOK_BASE_URL .env | cut -d'=' -f2 | sed 's|https://||' | sed 's|http://||' | tr -d ' ')
print_info "Обнаружен домен: $DOMAIN"

# ============================================
# ШАГ 2: Обновление системы
# ============================================
print_header "Шаг 2/8: Обновление системы"
print_info "Обновление пакетов системы..."
apt update -qq
apt upgrade -y -qq
apt install -y ca-certificates curl gnupg lsb-release git nano ufw
print_success "Система обновлена"

# ============================================
# ШАГ 3: Установка Docker
# ============================================
print_header "Шаг 3/8: Установка Docker"

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
# ШАГ 4: Настройка Firewall
# ============================================
print_header "Шаг 4/8: Настройка Firewall"
print_info "Настройка UFW firewall..."
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
echo "y" | ufw enable
print_success "Firewall настроен (порты 22, 80, 443 открыты)"

# ============================================
# ШАГ 5: Создание директорий и настройка конфигов
# ============================================
print_header "Шаг 5/8: Подготовка конфигурации"

# Создание директорий
mkdir -p nginx/ssl
mkdir -p nginx/acme-webroot
mkdir -p backups

# Обновление nginx конфигурации
print_info "Обновление Nginx конфигурации для домена: $DOMAIN"
sed -i "s/yourdomain.com/$DOMAIN/g" nginx/conf.d/bot.conf

print_success "Директории созданы, Nginx конфигурация обновлена"

# ============================================
# ШАГ 6: Получение SSL сертификата через acme.sh
# ============================================
print_header "Шаг 6/8: Получение SSL сертификата"

# Запрос email для SSL
read -p "Введите ваш email для SSL уведомлений: " EMAIL

if [ -z "$EMAIL" ]; then
    print_error "Email обязателен для SSL сертификата!"
    exit 1
fi

# Установка acme.sh
if [ ! -f ~/.acme.sh/acme.sh ]; then
    print_info "Установка acme.sh..."
    curl https://get.acme.sh | sh -s email=$EMAIL
    source ~/.bashrc
    print_success "acme.sh установлен"
fi

ACME_SH="$HOME/.acme.sh/acme.sh"

# Запуск nginx для HTTP-01 challenge
print_info "Запуск Nginx для проверки домена..."
docker compose -f docker-compose.production.yml up -d nginx

sleep 10

# Проверка доступности домена
print_info "Проверка доступности домена $DOMAIN..."
if ! curl -s -o /dev/null -w "%{http_code}" http://$DOMAIN/.well-known/acme-challenge/test | grep -q "404"; then
    print_error "Домен $DOMAIN недоступен!"
    print_info "Убедитесь что:"
    print_info "  1. Домен указывает на IP этого сервера"
    print_info "  2. DNS записи настроены правильно"
    print_info "  3. Порт 80 открыт"
    print_info ""
    read -p "Продолжить без SSL? (y/N): " CONTINUE
    if [ "$CONTINUE" != "y" ]; then
        docker compose -f docker-compose.production.yml down nginx
        exit 1
    fi
    SSL_ENABLED=false
else
    # Выпуск сертификата
    print_info "Получение SSL сертификата для $DOMAIN..."
    
    if $ACME_SH --issue \
      -d $DOMAIN \
      --webroot ./nginx/acme-webroot \
      --server letsencrypt \
      --keylength 4096; then
        
        print_success "Сертификат получен!"
        
        # Установка сертификата
        print_info "Установка сертификата..."
        mkdir -p ./nginx/ssl/$DOMAIN
        
        $ACME_SH --install-cert -d $DOMAIN \
          --key-file ./nginx/ssl/$DOMAIN/$DOMAIN.key \
          --fullchain-file ./nginx/ssl/$DOMAIN/fullchain.cer \
          --ca-file ./nginx/ssl/$DOMAIN/ca.cer \
          --reloadcmd "docker exec remnawave-nginx nginx -s reload"
        
        chmod 644 ./nginx/ssl/$DOMAIN/*
        print_success "Сертификат установлен!"
        SSL_ENABLED=true
        
    else
        print_error "Не удалось получить сертификат"
        print_warning "Возможные причины:"
        print_warning "  1. Домен $DOMAIN не указывает на этот сервер"
        print_warning "  2. Порт 80 заблокирован"
        print_warning "  3. Домен еще не пропагировался"
        print_info ""
        read -p "Продолжить без SSL? (y/N): " CONTINUE
        if [ "$CONTINUE" != "y" ]; then
            docker compose -f docker-compose.production.yml down nginx
            exit 1
        fi
        SSL_ENABLED=false
    fi
fi

# Остановка nginx (будет перезапущен на шаге 7)
docker compose -f docker-compose.production.yml down nginx

# ============================================
# ШАГ 7: Запуск всех сервисов
# ============================================
print_header "Шаг 7/8: Запуск сервисов"

# Создание Docker network
docker network create remnawave-network 2>/dev/null || print_warning "Network уже существует"

# Сборка и запуск
print_info "Сборка Docker образов..."
docker compose -f docker-compose.production.yml build

print_info "Запуск всех сервисов..."
docker compose -f docker-compose.production.yml up -d

print_success "Все сервисы запущены"

# Ожидание инициализации
print_info "Ожидание инициализации сервисов (30 секунд)..."
sleep 30

# ============================================
# ШАГ 8: Применение миграций и финальная проверка
# ============================================
print_header "Шаг 8/8: Финальная настройка"

# Применение миграций
print_info "Применение миграций базы данных..."
sleep 10

if docker exec remnawave-bot alembic upgrade head; then
    print_success "Миграции применены"
else
    print_warning "Не удалось применить миграции (может потребоваться повтор позже)"
fi

# Проверка статуса
print_info "Проверка статуса контейнеров..."
RUNNING_CONTAINERS=$(docker ps --format "{{.Names}}" | wc -l)

if [ $RUNNING_CONTAINERS -ge 4 ]; then
    print_success "Все контейнеры запущены ($RUNNING_CONTAINERS)"
    docker ps --format "table {{.Names}}\t{{.Status}}"
else
    print_error "Не все контейнеры запущены (ожидалось 4-5, запущено: $RUNNING_CONTAINERS)"
    print_info "Проверьте логи: docker compose -f docker-compose.production.yml logs"
fi

# Проверка webhook
echo ""
print_info "Проверка доступности webhook..."
if [ "$SSL_ENABLED" = true ]; then
    if curl -k -s https://$DOMAIN/health | grep -q "ok"; then
        print_success "Webhook доступен по HTTPS"
    else
        print_warning "Webhook пока недоступен (может потребоваться время)"
    fi
else
    if curl -s -o /dev/null -w "%{http_code}" http://$DOMAIN/health | grep -q "200"; then
        print_success "Webhook доступен по HTTP"
    else
        print_warning "Webhook пока недоступен (может потребоваться время)"
    fi
fi

# ============================================
# ФИНАЛ: Вывод информации
# ============================================
echo ""
echo "======================================"
print_success "Установка завершена!"
echo "======================================"
echo ""

if [ "$SSL_ENABLED" = true ]; then
    print_info "Ваш бот установлен и работает по HTTPS:"
    print_info "  URL: https://$DOMAIN"
else
    print_warning "SSL сертификат не установлен!"
    print_info "Ваш бот работает по HTTP:"
    print_info "  URL: http://$DOMAIN"
    print_info ""
    print_info "Для получения SSL сертификата позже:"
    print_info "  ./get-ssl.sh $DOMAIN $EMAIL"
fi

echo ""
print_info "Проверьте бота в Telegram - отправьте ему /start"
echo ""
print_info "Полезные команды:"
print_info "  Логи бота:       docker logs -f remnawave-bot"
print_info "  Перезапуск:      docker restart remnawave-bot"
print_info "  Остановка:       docker compose -f docker-compose.production.yml down"
print_info "  Запуск:          docker compose -f docker-compose.production.yml up -d"
echo ""

if [ "$SSL_ENABLED" = true ]; then
    print_info "SSL сертификат будет автоматически обновляться через acme.sh"
    print_info "Проверить список: ~/.acme.sh/acme.sh --list"
fi

echo ""
print_warning "ВАЖНО: Сохраните в безопасном месте:"
print_warning "  - Файл .env (содержит секреты)"
if [ "$SSL_ENABLED" = true ]; then
    print_warning "  - Сертификаты в nginx/ssl/$DOMAIN/"
fi
echo ""
print_success "Готово! Ваш бот работает! 🎉"
echo ""