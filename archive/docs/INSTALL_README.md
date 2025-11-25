# 🚀 Установка Remnawave Bot на Ubuntu 24.04

## ⚡ Самый быстрый способ (5 минут)

### Что нужно:
1. ✅ Сервер Ubuntu 24.04 (2GB RAM минимум)
2. ✅ Домен (например: bot.example.com) → A-запись на IP сервера
3. ✅ Токен бота от @BotFather
4. ✅ Ваш Telegram ID от @userinfobot

---

## 🎯 Установка за 4 команды

```bash
# 1. Скачать проект
git clone https://github.com/YOUR_REPO/remnawave-tg-shop-main.git
cd remnawave-tg-shop-main

# 2. Настроить .env
cp .env.example .env
nano .env
# Измените: BOT_TOKEN, ADMIN_IDS, WEBHOOK_BASE_URL, POSTGRES_PASSWORD

# 3. Запустить автоустановку
chmod +x install.sh
sudo ./install.sh

# 4. Готово! Проверьте бота в Telegram
```

**Всё!** Бот установлен с Docker, PostgreSQL, Redis, Nginx и SSL!

---

## 📋 Что включено

- ✅ **PostgreSQL 17** - база данных
- ✅ **Redis 7** - FSM storage + кэш
- ✅ **Nginx** - reverse proxy
- ✅ **SSL сертификат** - через acme.sh (автообновление)
- ✅ **Docker Compose** - легкое управление
- ✅ **Health checks** - автоматический мониторинг
- ✅ **Resource limits** - защита от перегрузки
- ✅ **Rate limiting** - защита от спама (20 req/min)
- ✅ **Graceful shutdown** - корректное завершение
- ✅ **Auto-restart** - перезапуск при сбоях

---

## 📚 Подробные инструкции

### Для новичков (с объяснениями):
📖 [`INSTALLATION_FOR_BEGINNERS.md`](INSTALLATION_FOR_BEGINNERS.md)

### Пошаговое руководство (детальное):
📖 [`UBUNTU_DOCKER_INSTALLATION.md`](UBUNTU_DOCKER_INSTALLATION.md)

---

## 🛠️ Управление ботом

```bash
# Логи
docker logs -f remnawave-bot

# Перезапуск
docker restart remnawave-bot

# Остановка всех сервисов
docker compose -f docker-compose.production.yml down

# Запуск всех сервисов
docker compose -f docker-compose.production.yml up -d

# Статус
docker ps
```

---

## 🔄 Обновление бота

```bash
cd ~/remnawave-tg-shop-main
git pull
docker compose -f docker-compose.production.yml up -d --build
```

---

## 🔒 Получение SSL (отдельно, если нужно)

```bash
chmod +x get-ssl.sh
./get-ssl.sh bot.yourdomain.com your@email.com
```

**Автообновление:** acme.sh обновит сертификат автоматически через 90 дней

---

## ⚠️ Troubleshooting

### Бот не отвечает?
```bash
# Проверить логи
docker logs --tail 50 remnawave-bot | grep ERROR

# Проверить webhook (замените TOKEN)
curl https://api.telegram.org/botTOKEN/getWebhookInfo

# Перезапустить
docker restart remnawave-bot
```

### SSL не работает?
```bash
# Проверить DNS
nslookup bot.yourdomain.com

# Получить сертификат заново
./get-ssl.sh bot.yourdomain.com your@email.com

# Проверить nginx
docker logs remnawave-nginx
```

### Полный список проблем:
См. [`UBUNTU_DOCKER_INSTALLATION.md`](UBUNTU_DOCKER_INSTALLATION.md) раздел "Troubleshooting"

---

## 💾 Резервное копирование

### Создать бэкап вручную:
```bash
# PostgreSQL
docker exec remnawave-db pg_dump -U postgres postgres > backup.sql

# Redis
docker exec remnawave-redis redis-cli save
docker cp remnawave-redis:/data/dump.rdb backup-redis.rdb

# .env
cp .env .env.backup
```

### Настроить автоматические бэкапы:
```bash
# См. UBUNTU_DOCKER_INSTALLATION.md раздел "Настроить автоматические бэкапы"
```

---

## 📊 Мониторинг

```bash
# Использование ресурсов
docker stats

# Здоровье сервисов
docker ps --format "table {{.Names}}\t{{.Status}}"

# Логи всех сервисов
docker compose -f docker-compose.production.yml logs -f
```

---

## 🆘 Помощь

1. **Прочитайте документацию:**
   - [`INSTALLATION_FOR_BEGINNERS.md`](INSTALLATION_FOR_BEGINNERS.md) - для новичков
   - [`UBUNTU_DOCKER_INSTALLATION.md`](UBUNTU_DOCKER_INSTALLATION.md) - детальная

2. **Создайте Issue на GitHub** с:
   - Описанием проблемы
   - Логами: `docker logs remnawave-bot > logs.txt`
   - Версией: `docker --version`

---

## 🎉 После установки

1. ✅ Откройте бота в Telegram
2. ✅ Отправьте `/start`
3. ✅ Настройте платежные системы в .env
4. ✅ Протестируйте все функции
5. ✅ Настройте автобэкапы (cron)
6. ✅ Мониторьте логи первые дни

---

## 📖 Полная документация

- 🏠 [README_ARCHITECTURAL_IMPROVEMENTS.md](README_ARCHITECTURAL_IMPROVEMENTS.md) - Обзор улучшений
- 📊 [ARCHITECTURE_IMPROVEMENTS_COMPLETE.md](ARCHITECTURE_IMPROVEMENTS_COMPLETE.md) - Полный отчет
- 📚 [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md) - Индекс всех документов

---

**Разработано:** Kilo Code Architecture Team  
**Дата:** 2024-11-24  
**Версия:** 2.0.0 Production Ready  
**Сложность:** ⭐ Очень легко (с автоустановкой)

**🎊 Удачной установки!** 🎊