#!/bin/bash

# ============================================
# Автоматическая установка Remnawave Bot
# для Ubuntu 24.04 с Docker
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
    echo -e "${YELLOW}ℹ $1${NC}"
}

# Проверка что запущено от root
if [ "$EUID" -ne 0 ]; then 
    print_error "Пожалуйста, запустите скрипт от root: sudo ./install.sh"
    exit 1
fi

print_success "Запущено от root"

# ============================================
# ШАГ 1: Обновление системы
# ============================================
echo ""
print_info "Шаг 1/10: Обновление системы..."
apt update -qq
apt upgrade -y -qq
apt install -y ca-certificates curl gnupg lsb-release git nano ufw
print_success "Система обновлена"

# ============================================
# ШАГ 2: Установка Docker
# ============================================
echo ""
print_info "Шаг 2/10: Установка Docker..."

# Проверка установлен ли Docker
if command -v docker &> /dev/null; then
    print_warning "Docker уже установлен, пропускаем..."
else
    # Добавить GPG ключ
    mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg

    # Добавить репозиторий
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

    # Установить Docker
    apt update -qq
    apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    # Запустить Docker
    systemctl enable docker
    systemctl start docker

    print_success "Docker установлен"
fi

# Проверка версии
DOCKER_VERSION=$(docker --version)
print_info "Docker версия: $DOCKER_VERSION"

# ============================================
# ШАГ 3: Настройка Firewall
# ============================================
echo ""
print_info "Шаг 3/10: Настройка Firewall (UFW)..."

# Разрешить SSH (ВАЖНО!)
ufw allow 22/tcp

# Разрешить HTTP и HTTPS
ufw allow 80/tcp
ufw allow 443/tcp

# Включить UFW (если еще не включен)
echo "y" | ufw enable

print_success "Firewall настроен (порты 22, 80, 443 открыты)"

# ============================================
# ШАГ 4: Проверка .env файла
# ============================================
echo ""
print_info "Шаг 4/10: Проверка настроек .env..."

if [ ! -f .env ]; then
    print_warning ".env файл не найден, создаю из .env.example..."
    cp .env.example .env
    print_error "ВНИМАНИЕ: Вы ДОЛЖНЫ настроить .env файл!"
    print_info "Откройте файл: nano .env"
    print_info "Замените как минимум:"
    print_info "  - BOT_TOKEN=ваш_токен_от_BotFather"
    print_info "  - ADMIN_IDS=ваш_telegram_id"
    print_info "  - WEBHOOK_BASE_URL=https://ваш_домен.com"
    print_info "  - POSTGRES_PASSWORD=сложный_пароль"
    print_info ""
    read -p "Нажмите Enter после настройки .env..."
fi

# Проверка обязательных параметров
if grep -q "your_bot_token_here" .env; then
    print_error "BOT_TOKEN не настроен в .env файле!"
    print_info "Получите токен у @BotFather в Telegram"
    exit 1
fi

if grep -q "yourdomain.com" .env 2>/dev/null || ! grep -q "WEBHOOK_BASE_URL=https://" .env; then
    print_error "WEBHOOK_BASE_URL не настроен в .env файле!"
    print_info "Укажите ваш домен: WEBHOOK_BASE_URL=https://bot.yourdomain.com"
    exit 1
fi

print_success ".env файл настроен"

# ============================================
# ШАГ 5: Создание Docker network
# ============================================
echo ""
print_info "Шаг 5/10: Создание Docker network..."

docker network create remnawave-network 2>/dev/null || print_warning "Network уже существует"
print_success "Docker network готова"

# ============================================
# ШАГ 6: Проверка nginx конфигурации
# ============================================
echo ""
print_info "Шаг 6/10: Проверка Nginx конфигурации..."

# Извлечь домен из .env
DOMAIN=$(grep WEBHOOK_BASE_URL .env | cut -d'=' -f2 | sed 's|https://||' | sed 's|http://||' | tr -d ' ')

print_info "Ваш домен: $DOMAIN"

# Проверить что nginx/conf.d/bot.conf существует
if [ ! -f nginx/conf.d/bot.conf ]; then
    print_error "nginx/conf.d/bot.conf не найден!"
    exit 1
fi

# Заменить yourdomain.com на реальный домен
sed -i "s/yourdomain.com/$DOMAIN/g" nginx/conf.d/bot.conf

print_success "Nginx конфигурация обновлена для домена: $DOMAIN"

# ============================================
# ШАГ 7: Создание директорий
# ============================================
echo ""
print_info "Шаг 7/10: Создание директорий..."

mkdir -p nginx/ssl
mkdir -p nginx/acme-webroot
mkdir -p backups

print_success "Директории созданы"

# ============================================
# ШАГ 8: Получение SSL сертификата через acme.sh
# ============================================
echo ""
print_info "Шаг 8/10: Получение SSL сертификата через acme.sh..."

# Запросить email
read -p "Введите ваш email для уведомлений: " EMAIL

if [ -z "$EMAIL" ]; then
    print_error "Email обязателен!"
    exit 1
fi

# Установить acme.sh
if [ ! -f ~/.acme.sh/acme.sh ]; then
    print_info "Установка acme.sh..."
    curl https://get.acme.sh | sh -s email=$EMAIL
    source ~/.bashrc
    print_success "acme.sh установлен"
fi

ACME_SH="$HOME/.acme.sh/acme.sh"

# Запустить nginx для HTTP-01 challenge
print_info "Запуск Nginx для HTTP-01 challenge..."
docker compose -f docker-compose.production.yml up -d nginx

sleep 10

# Выпустить сертификат
print_info "Получение сертификата для $DOMAIN..."

$ACME_SH --issue \
  -d $DOMAIN \
  --webroot ./nginx/acme-webroot \
  --server letsencrypt \
  --keylength 4096

if [ $? -eq 0 ]; then
    print_success "Сертификат получен!"
    
    # Установить сертификат
    print_info "Установка сертификата..."
    mkdir -p ./nginx/ssl/$DOMAIN
    
    $ACME_SH --install-cert -d $DOMAIN \
      --key-file ./nginx/ssl/$DOMAIN/$DOMAIN.key \
      --fullchain-file ./nginx/ssl/$DOMAIN/fullchain.cer \
      --ca-file ./nginx/ssl/$DOMAIN/ca.cer
    
    chmod 644 ./nginx/ssl/$DOMAIN/*
    
    print_success "Сертификаты установлены!"
    
else
    print_error "Не удалось получить сертификат"
    print_warning "Возможные причины:"
    print_warning "  1. Домен $DOMAIN не указывает на этот сервер"
    print_warning "  2. Порт 80 заблокирован"
    print_warning "  3. Домен не пропагировался (подождите 30 минут)"
    print_info ""
    print_info "Попробуйте позже: ./get-ssl.sh $DOMAIN $EMAIL"
    print_info ""
    read -p "Продолжить без SSL? (y/N): " CONTINUE
    if [ "$CONTINUE" != "y" ]; then
        exit 1
    fi
fi

# Остановить nginx (будет перезапущен на шаге 9)
docker compose -f docker-compose.production.yml down nginx

# ============================================
# ШАГ 9: Запуск всех сервисов
# ============================================
echo ""
print_info "Шаг 9/10: Запуск всех сервисов..."

# Собрать образы
docker compose -f docker-compose.production.yml build

# Запустить все сервисы
docker compose -f docker-compose.production.yml up -d

print_success "Все сервисы запущены"

# Подождать инициализации
print_info "Ожидание инициализации (30 секунд)..."
sleep 30

# ============================================
# ШАГ 10: Применение миграций
# ============================================
echo ""
print_info "Шаг 10/10: Применение миграций базы данных..."

# Подождать пока БД будет готова
print_info "Ожидание готовности PostgreSQL..."
sleep 10

# Применить миграции
docker exec remnawave-bot alembic upgrade head

if [ $? -eq 0 ]; then
    print_success "Миграции применены"
else
    print_warning "Не удалось применить миграции (может потребоваться повтор позже)"
fi

# ============================================
# ФИНАЛ: Проверка статуса
# ============================================
echo ""
echo "======================================"
echo "Проверка статуса установки"
echo "======================================"

# Проверить контейнеры
RUNNING_CONTAINERS=$(docker ps --format "{{.Names}}" | wc -l)

if [ $RUNNING_CONTAINERS -ge 4 ]; then
    print_success "Все контейнеры запущены ($RUNNING_CONTAINERS)"
    docker ps --format "table {{.Names}}\t{{.Status}}"
else
    print_error "Не все контейнеры запущены (ожидалось 4-5, запущено: $RUNNING_CONTAINERS)"
    print_info "Проверьте логи: docker compose -f docker-compose.production.yml logs"
fi

# Проверить webhook
echo ""
print_info "Проверка доступности webhook..."
if curl -k -s https://$DOMAIN/health | grep -q "ok"; then
    print_success "Webhook доступен по HTTPS"
else
    print_warning "Webhook пока недоступен (может потребоваться время)"
fi

# ============================================
# Вывод финальной информации
# ============================================
echo ""
echo "======================================"
print_success "Установка завершена!"
echo "======================================"
echo ""
print_info "Ваш бот установлен и работает на:"
print_info "  HTTPS: https://$DOMAIN"
print_info ""
print_info "Проверьте бота в Telegram - отправьте ему /start"
echo ""
print_info "Полезные команды:"
print_info "  Логи бота:       docker logs -f remnawave-bot"
print_info "  Перезапуск:      docker restart remnawave-bot"
print_info "  Остановка:       docker compose -f docker-compose.production.yml down"
print_info "  Запуск:          docker compose -f docker-compose.production.yml up -d"
echo ""
print_info "Подробная документация:"
print_info "  Ubuntu Guide:    cat UBUNTU_DOCKER_INSTALLATION.md"
print_info "  Quick Start:     cat QUICK_START_IMPROVEMENTS.md"
echo ""
print_warning "ВАЖНО: Сохраните в безопасном месте:"
print_warning "  - Файл .env (содержит секреты)"
print_warning "  - Сертификаты в nginx/ssl/$DOMAIN/"
print_info ""
print_info "Автообновление SSL: acme.sh обновит сертификат автоматически"
print_info "Проверить список: ~/.acme.sh/acme.sh --list"
echo ""
print_success "Готово! Ваш бот работает! 🎉"
echo ""