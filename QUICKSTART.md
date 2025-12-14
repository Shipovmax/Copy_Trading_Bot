# 🤖 Copy Trading Bot для OKX - ПОЛНАЯ ИНСТРУКЦИЯ ЗАПУСКА

## ⚡ Быстрый Старт (5 минут)

### 1️⃣ Клонируй репо или скачай файлы:
```bash
git clone https://github.com/your-repo/copy-trading-bot
cd copy-trading-bot
```

### 2️⃣ Установи зависимости:
```bash
# macOS/Linux
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Windows
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 3️⃣ Создай .env файл:
```bash
# Скопируй пример
cp .env.example .env

# Отредактируй .env с ТВОИМИ ключами OKX и Telegram
nano .env  # или открой в любом редакторе
```

### 4️⃣ Запусти бота:
```bash
python main.py
```

**Готово!** 🎉 Бот начнёт сканировать топ-трейдеров и копировать их позиции.

---

## 📋 СТРУКТУРА ПРОЕКТА

```
copy-trading-bot/
├── main.py                  # 🎯 ГЛАВНЫЙ ФАЙЛ (запуск отсюда)
├── config.py                # ⚙️  Конфиг и параметры
├── trader_scanner.py        # 🔍 Поиск топ-трейдеров
├── copy_executor.py         # 📋 Исполнение ордеров
├── telegram_notifier.py     # 📬 Уведомления в Telegram
├── database.py              # 💾 Логирование в SQLite
├── requirements.txt         # 📦 Зависимости Python
├── .env.example             # 📝 Пример конфига
└── logs/                    # 📂 Логи бота
```

---

## 🔑 Как получить OKX API ключи?

### Шаг 1: Зайди на OKX
1. Открой [OKX.com](https://www.okx.com)
2. Залогинься в свой аккаунт
3. Нажми на иконку профиля → Account Settings

### Шаг 2: Создай API ключ
1. Слева выбери "API" или "API Management"
2. Нажми "Create API Key"
3. Выбери тип: **Read-Only** (безопаснее!)
4. Укажи IP адреса (можешь оставить пусто для тестирования)

### Шаг 3: Скопируй ключи
Тебе нужны три строки:
- **API Key** - основной ключ
- **Secret Key** - секретный ключ
- **Passphrase** - пароль

Положи их в `.env` файл:
```env
OKX_API_KEY=abc123def456...
OKX_SECRET_KEY=xyz789qwe...
OKX_PASSPHRASE=MyPassword123
```

---

## 📱 Как настроить Telegram уведомления?

### Шаг 1: Создай Telegram бота
1. Открой Telegram и найди @BotFather
2. Напиши `/start`
3. Напиши `/newbot`
4. Назови бота (например: `MyCopyTradingBot`)
5. BotFather выдаст **Bot Token** - скопируй его

### Шаг 2: Узнай свой Chat ID
1. Напиши своему боту что-нибудь (любое сообщение)
2. Перейди на: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Замени `<YOUR_BOT_TOKEN>` на токен из шага 1
3. В ответе найди `"id"` - это твой Chat ID

### Шаг 3: Добавь в .env
```env
TELEGRAM_BOT_TOKEN=1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcd_e
TELEGRAM_CHAT_ID=123456789
```

---

## ⚙️ ПАРАМЕТРЫ КОНФИГА

### Основные параметры для новичков:

```env
# Сколько копировать от позиции трейдера (начни с 0.05 = 5%)
COPY_RATIO=0.05

# Копируем только трейдеров с ROI выше этого (сначала высокий порог)
MIN_TRADER_ROI=150

# Минимум дней активности (вкидывай от 90 дней)
MIN_TRADER_DAYS=90

# На сколько % устанавливаем стоп-лосс
STOP_LOSS_PERCENT=5.0

# ВАЖНО: включи Paper Trading для первого теста!
PAPER_TRADING=True
```

---

## 🚀 СТРАТЕГИЯ ИСПОЛЬЗОВАНИЯ

### Неделя 1: ТЕСТИРОВАНИЕ
```env
PAPER_TRADING=True           # Только логирование, без денег
COPY_RATIO=0.05              # 5% от позиции
MIN_TRADER_ROI=200           # Только лучшие (200%+ ROI)
```

**Что смотреть:**
- Открываются ли ордеры?
- Приходят ли уведомления в Telegram?
- Логируются ли сделки в БД?

### Неделя 2: ПЕРЕХОД НА РЕАЛ (опционально)
```env
PAPER_TRADING=False          # РЕАЛЬНАЯ ТОРГОВЛЯ!
COPY_RATIO=0.05              # Начни с малого
MIN_TRADER_ROI=150           # Чуть повыше, но не экстрим
MIN_BALANCE=500              # Минимум $500 на счёте
```

**Первый депозит:** $500–1000 USDT

### Месяц 2+: МАСШТАБИРОВАНИЕ
```env
COPY_RATIO=0.1               # Увеличили до 10%
MIN_TRADER_ROI=100           # Добавили больше трейдеров
MAX_TRADERS=10               # Копируем до 10 трейдеров
```

---

## 📊 ЧТО СМОТРЕТЬ В ЛОГАХ

Когда запустишь бота, посмотри в консоль:

```
✅ Database initialized successfully
🔍 Scanning top traders on OKX...
✅ Found 5 qualified traders
  1. CryptoMaster - ROI: 245.5%, Trades: 156, Days: 120
  2. BitcoinGuy - ROI: 189.3%, Trades: 89, Days: 95
  ...
🚀 Copy Trading Bot Starting...
📝 Paper Trading: True
🔍 Scanning interval: 30s
```

**Это хороший знак!** Бот работает.

---

## ❌ ЧАСТЫЕ ОШИБКИ

### 1. "ModuleNotFoundError: No module named 'ccxt'"
**Решение:** Забыл установить зависимости
```bash
pip install -r requirements.txt
```

### 2. "OKX API keys not configured!"
**Решение:** Заполнил .env с неправильными ключами
```bash
# Проверь:
# 1. Скопировал ли правильные ключи с OKX?
# 2. Правильно ли вставил в .env?
# 3. Нет ли пробелов в начале/конце?
```

### 3. "Telegram not configured, skipping notification"
**Решение:** Неправильный Bot Token или Chat ID
```bash
# Проверь:
# 1. Создал ли бота у @BotFather?
# 2. Правильный ли Bot Token?
# 3. Правильный ли Chat ID?
# 4. Отправил ли боту хотя бы одно сообщение?
```

### 4. "Paper trading mode" - сделки не копируются
**Решение:** Это нормально! `PAPER_TRADING=True` = тестирование без денег.
Если хочешь реальные ордеры, поменяй:
```env
PAPER_TRADING=False
```

---

## 💡 СОВЕТЫ ДЛЯ ПРОФИ

### 1. Запусти в фоне (на сервере/VPS):
```bash
# Используй screen или tmux
screen -S copybot
python main.py

# Выход: Ctrl+A, D
# Возврат: screen -r copybot
```

### 2. Анализируй логи:
```bash
# Смотри последний лог
tail -f logs/bot_2025-12-14.log

# Ищи ошибки
grep "ERROR" logs/bot_*.log

# Считай сделки
grep "Trade Opened" logs/bot_*.log | wc -l
```

### 3. Получай статистику:
```python
# Запусти в Python
from database import TradeDatabase
db = TradeDatabase()
stats = db.get_stats()
print(stats)
```

---

## 📞 ПОДДЕРЖКА И ОТЛАДКА

### Включи DEBUG режим:
```env
DEBUG_MODE=True
LOG_LEVEL=DEBUG
```

Это выведет ОЧЕНЬ много информации - полезно для отладки.

### Проверь подключение к OKX:
```python
import ccxt

exchange = ccxt.okx({
    'apiKey': 'YOUR_KEY',
    'secret': 'YOUR_SECRET',
    'password': 'YOUR_PASS'
})

# Проверь баланс
balance = exchange.fetch_balance()
print(balance)
```

---

## ⚠️ ДИСКЛЕЙМЕР

⚠️ **ВАЖНО:**
- Это образовательный проект
- Торговля - высокий риск
- Топ-трейдеры ТОЖЕ иногда ошибаются
- Начни с PAPER TRADING ($0 реальных денег)
- Никогда не вкладывай больше, чем можешь потерять
- Всегда используй стоп-лоссы
- Не работает как "печатный станок"

**По твоей ответственности:** если потеряешь деньги, это не моя вина. 😅

---

## 🎯 СЛЕДУЮЩИЕ ШАГИ

1. ✅ Установи зависимости
2. ✅ Создай OKX API ключи
3. ✅ Создай Telegram бота
4. ✅ Заполни .env
5. ✅ Запусти в PAPER TRADING
6. ✅ Смотри логи неделю
7. ✅ Если всё круто → переходи на РЕАЛЬНУЮ ТОРГОВЛЮ с малыми суммами

---

## 📖 ССЫЛКИ

- [OKX API Docs](https://www.okx.com/docs-v5/en)
- [CCXT Library](https://github.com/ccxt/ccxt)
- [Telegram Bot API](https://core.telegram.org/bots)
- [Python asyncio](https://docs.python.org/3/library/asyncio.html)

---

**Удачи! 🚀** 

Если что-то непонятно - читай комментарии в коде, там всё расписано подробно.
