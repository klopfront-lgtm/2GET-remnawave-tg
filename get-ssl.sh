#!/bin/bash

# ============================================
# Получение SSL сертификата через acme.sh
# ============================================

set -e

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_error() { echo -e "${RED}✗ $1${NC}"; }
print_info() { echo -e "${YELLOW}ℹ $1${NC}"; }

# Проверка аргументов
if [ $# -lt 2 ]; then
    print_error "Использование: ./get-ssl.sh ДОМЕН EMAIL"
    print_info "Пример: ./get-ssl.sh bot.example.com admin@example.com"
    exit 1
fi

DOMAIN=$1
EMAIL=$2

print_info "Получение SSL сертификата для: $DOMAIN"
print_info "Email для уведомлений: $EMAIL"

# Создать директории
mkdir -p nginx/ssl
mkdir -p nginx/acme-webroot

# Установить acme.sh если не установлен
if [ ! -f ~/.acme.sh/acme.sh ]; then
    print_info "Установка acme.sh..."
    curl https://get.acme.sh | sh -s email=$EMAIL
    print_success "acme.sh установлен"
fi

# acme.sh путь
ACME_SH="$HOME/.acme.sh/acme.sh"

# Проверить что домен доступен
print_info "Проверка доступности домена..."
if ! curl -s -o /dev/null -w "%{http_code}" http://$DOMAIN/.well-known/acme-challenge/test | grep -q "404"; then
    print_error "Домен $DOMAIN недоступен или nginx не настроен"
    print_info "Убедитесь что:"
    print_info "  1. Домен указывает на IP сервера (проверьте: nslookup $DOMAIN)"
    print_info "  2. Nginx запущен: docker ps | grep nginx"
    print_info "  3. Порт 80 открыт: sudo ufw status"
    exit 1
fi

# Выпустить сертификат
print_info "Получение сертификата от Let's Encrypt..."

$ACME_SH --issue \
  -d $DOMAIN \
  --webroot ./nginx/acme-webroot \
  --server letsencrypt \
  --keylength 4096

if [ $? -ne 0 ]; then
    print_error "Не удалось получить сертификат"
    print_info "Возможные причины:"
    print_info "  1. Домен не указывает на этот сервер"
    print_info "  2. Firewall блокирует порт 80"
    print_info "  3. Nginx не проксирует /.well-known/acme-challenge/"
    exit 1
fi

print_success "Сертификат получен!"

# Установить сертификаты в nginx/ssl
print_info "Установка сертификатов в nginx/ssl/$DOMAIN/..."

$ACME_SH --install-cert -d $DOMAIN \
  --key-file ./nginx/ssl/$DOMAIN/$DOMAIN.key \
  --fullchain-file ./nginx/ssl/$DOMAIN/fullchain.cer \
  --ca-file ./nginx/ssl/$DOMAIN/ca.cer \
  --reloadcmd "docker exec remnawave-nginx nginx -s reload"

if [ $? -eq 0 ]; then
    print_success "Сертификаты установлены в nginx/ssl/$DOMAIN/"
else
    print_error "Не удалось установить сертификаты"
    
    # Попробовать вручную скопировать
    print_info "Копирование сертификатов вручную..."
    mkdir -p ./nginx/ssl/$DOMAIN
    cp ~/.acme.sh/$DOMAIN/$DOMAIN.key ./nginx/ssl/$DOMAIN/
    cp ~/.acme.sh/$DOMAIN/fullchain.cer ./nginx/ssl/$DOMAIN/
    cp ~/.acme.sh/$DOMAIN/ca.cer ./nginx/ssl/$DOMAIN/
    print_success "Сертификаты скопированы вручную"
fi

# Проверить что файлы созданы
if [ -f "./nginx/ssl/$DOMAIN/fullchain.cer" ] && [ -f "./nginx/ssl/$DOMAIN/$DOMAIN.key" ]; then
    print_success "Сертификаты на месте:"
    ls -lh ./nginx/ssl/$DOMAIN/
else
    print_error "Сертификаты не найдены!"
    exit 1
fi

# Перезапустить nginx
print_info "Перезапуск Nginx..."
docker restart remnawave-nginx

sleep 3

# Проверить SSL
print_info "Проверка SSL..."
if curl -ksI https://$DOMAIN | grep -q "200 OK"; then
    print_success "SSL работает! https://$DOMAIN доступен"
else
    print_error "SSL не работает, проверьте nginx логи:"
    print_info "docker logs remnawave-nginx"
fi

echo ""
print_success "Готово! SSL сертификат установлен для $DOMAIN"
print_info ""
print_info "Сертификат будет автоматически обновляться через acme.sh"
print_info "Проверьте: $ACME_SH --list"
print_info ""
print_info "Для ручного обновления:"
print_info "  $ACME_SH --renew -d $DOMAIN --force"
print_info ""