# 🚀 Инструкция по быстрой установке VPS Telegram Monitor Bot

Данная система позволяет моментально получать уведомления в Telegram при сбое любого контейнера, базы данных или системных ресурсов, а также интерактивно проверять их состояние по кнопке.

---

## 📋 Шаг 1. Подготовка Telegram-бота

1. Откройте Telegram и найдите бота **[@BotFather](https://t.me/BotFather)**.
2. Отправьте команду `/newbot` и следуйте инструкциям для создания бота.
3. Скопируйте полученный **Bot Token** (например: `7123456789:AAE...`).
4. Узнайте свой **Chat ID**: напишите боту **[@userinfobot](https://t.me/userinfobot)**. Скопируйте числовой ID (например: `123456789`).

---

## 📦 Шаг 2. Развёртывание на VPS

Подключитесь к вашему VPS по SSH и выполните команды:

```bash
# 1. Создайте директорию для бота
mkdir -p /opt/vps-monitor
cd /opt/vps-monitor

# 2. Скопируйте файлы vps_monitor.py и config.json.example в /opt/vps-monitor
```

---

## ⚙️ Шаг 3. Настройка `config.json`

Создайте файл `config.json` в папе `/opt/vps-monitor`:

```bash
cp config.json.example config.json
nano config.json
```

Укажите ваш **Bot Token** и **Chat ID**, а также задайте понятные русские имена контейнерам:

```json
{
  "telegram": {
    "bot_token": "7123456789:AAE...",
    "allowed_chat_ids": [123456789]
  },
  "settings": {
    "check_interval_seconds": 30,
    "notify_on_recovery": true
  },
  "containers": [
    {
      "id": "postgres",
      "name": "🗄️ База Данных PostgreSQL",
      "category": "БД"
    },
    {
      "id": "main_tg_bot",
      "name": "🤖 Основной ТГ Бот",
      "category": "Боты"
    },
    {
      "id": "partner_tg_bot",
      "name": "🤝 Партнёрский ТГ Бот",
      "category": "Боты"
    }
  ]
}
```

> 💡 **Как узнать имена контейнеров в Docker?**
> Выполните команду `docker ps` на сервере. В столбце `NAMES` будут указаны имена контейнеров для поля `"id"`.

---

## 🧪 Шаг 4. Проверка работы

Запустите тестовую отправку в Telegram:

```bash
python3 vps_monitor.py --test
```
Вам должно прийти сообщение: `🧪 VPS Monitor Bot подключен и работает!`.

---

## ⚙️ Шаг 5. Автозапуск через Systemd (Фоновый режим)

Чтобы бот работал 24/7 и запускался сам при перезагрузке сервера:

```bash
# Скопируйте юнит службы
cp vps-monitor.service /etc/systemd/system/

# Перезагрузите конфигурацию systemd и активируйте службу
systemctl daemon-reload
systemctl enable --now vps-monitor

# Проверьте статус
systemctl status vps-monitor
```

---

## 📲 Как пользоваться в Telegram

1. Зайдите в ваш Telegram-бот и нажмите `/start`.
2. Нажмите главную кнопку **`📊 Проверить состояние`**.
3. В появившемся меню вам доступны кнопки:
   - **`🌐 ПРОВЕРИТЬ ВСЕ КОНТЕЙНЕРЫ`** — полный отчёт о RAM/CPU, всех контейнерах и базах данных.
   - Кнопки конкретных контейнеров (например, **`🟢 🗄️ База Данных PostgreSQL`**) — быстрый статус конкретного контейнера.
   - При сбое любого контейнера бот **сразу пришлёт 🚨 АЛЕРТ** в чат!
