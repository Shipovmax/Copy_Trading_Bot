"""
config.py - конфигурация для Copy Trading Bot
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# OKX API КЛЮЧИ (ЗАПОЛНИ СВОИМИ)
# ============================================================================
OKX_API_KEY = os.getenv('OKX_API_KEY', 'YOUR_API_KEY_HERE')
OKX_SECRET_KEY = os.getenv('OKX_SECRET_KEY', 'YOUR_SECRET_KEY_HERE')
OKX_PASSPHRASE = os.getenv('OKX_PASSPHRASE', 'YOUR_PASSPHRASE_HERE')

# ============================================================================
# TELEGRAM УВЕДОМЛЕНИЯ
# ============================================================================
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', 'YOUR_CHAT_ID_HERE')

# ============================================================================
# ПАРАМЕТРЫ КОПИ-ТРЕЙДИНГА
# ============================================================================

# Коэффициент копирования (0.05 = копируем 5% от позиции трейдера)
# Начни с 0.05, затем увеличивай до 0.1
COPY_RATIO = float(os.getenv('COPY_RATIO', '0.05'))

# Минимальный ROI трейдера для копирования (в процентах)
MIN_TRADER_ROI = float(os.getenv('MIN_TRADER_ROI', '100'))

# Минимальное количество дней активности трейдера
MIN_TRADER_DAYS = int(os.getenv('MIN_TRADER_DAYS', '90'))

# Максимальное количество копируемых трейдеров
MAX_TRADERS = int(os.getenv('MAX_TRADERS', '5'))

# Интервал проверки новых позиций (в секундах)
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '30'))

# ============================================================================
# УПРАВЛЕНИЕ РИСКАМИ
# ============================================================================

# Стоп-лосс (в процентах от входной цены)
STOP_LOSS_PERCENT = float(os.getenv('STOP_LOSS_PERCENT', '5.0'))

# Максимальная просадка депо перед остановкой бота (в процентах)
MAX_DRAWDOWN = float(os.getenv('MAX_DRAWDOWN', '15.0'))

# Максимальное количество одновременных позиций
MAX_OPEN_POSITIONS = int(os.getenv('MAX_OPEN_POSITIONS', '10'))

# Минимальный баланс для торговли (в USDT)
MIN_BALANCE = float(os.getenv('MIN_BALANCE', '100.0'))

# ============================================================================
# ТОРГОВЫЕ ПАРЫ (какие пары копировать)
# ============================================================================

# Если пусто = копируем все пары, если заполнено = только эти
ALLOWED_PAIRS = [
    'BTC/USDT',
    'ETH/USDT',
    'SOL/USDT',
    'XRP/USDT',
    'ADA/USDT',
]

# Пары, которые НЕ копируем (чёрный список)
EXCLUDED_PAIRS = [
    'USDT/USDC',  # Stablecoin pairs
    'BUSD/USDT',
]

# ============================================================================
# ЛОГИРОВАНИЕ
# ============================================================================

# Папка для логов
LOG_DIR = os.getenv('LOG_DIR', './logs')

# Уровень логирования (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# ============================================================================
# БД
# ============================================================================

# Путь к SQLite базе
DB_PATH = os.getenv('DB_PATH', './data/trades.db')

# ============================================================================
# РЕЖИМЫ
# ============================================================================

# PAPER TRADING: если True = не реальные деньги, только логирование
PAPER_TRADING = os.getenv('PAPER_TRADING', 'True').lower() == 'true'

# DEBUG режим: подробное логирование
DEBUG_MODE = os.getenv('DEBUG_MODE', 'False').lower() == 'true'

# ============================================================================
# ФИЛЬТРЫ ТРЕЙДЕРОВ
# ============================================================================

# Копируем трейдеров только с положительным ROI за последний месяц
MIN_MONTHLY_ROI = float(os.getenv('MIN_MONTHLY_ROI', '5.0'))

# Максимальная волатильность стратегии трейдера (%)
MAX_STRATEGY_VOLATILITY = float(os.getenv('MAX_STRATEGY_VOLATILITY', '30.0'))

# Минимальное количество успешных трейдов
MIN_SUCCESSFUL_TRADES = int(os.getenv('MIN_SUCCESSFUL_TRADES', '10'))

# ============================================================================
# ВЫВОД КОНФИГА (для отладки)
# ============================================================================

if __name__ == '__main__':
    print("📋 Copy Trading Bot Configuration:")
    print(f"  OKX API Key: {'✅ Set' if OKX_API_KEY != 'YOUR_API_KEY_HERE' else '❌ Not Set'}")
    print(f"  Telegram Bot: {'✅ Set' if TELEGRAM_BOT_TOKEN != 'YOUR_BOT_TOKEN_HERE' else '❌ Not Set'}")
    print(f"  Copy Ratio: {COPY_RATIO}x")
    print(f"  Min ROI: {MIN_TRADER_ROI}%")
    print(f"  Max Traders: {MAX_TRADERS}")
    print(f"  Stop Loss: {STOP_LOSS_PERCENT}%")
    print(f"  Paper Trading: {PAPER_TRADING}")
