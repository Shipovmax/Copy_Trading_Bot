"""
Все данные сохраняются локально (config.json)
"""

import logging
import httpx
import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler, JobQueue
)
from telegram.constants import ParseMode
import ccxt
import numpy as np
import asyncio
from datetime import datetime
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# КОНФИГУРАЦИЯ И ХРАНЕНИЕ ДАННЫХ
# ============================================================================

CONFIG_FILE = 'user_configs.json'

def load_configs():
    """Загрузить конфигурации пользователей с диска"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_configs(configs):
    """Сохранить конфигурации пользователей на диск"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(configs, f, indent=2, ensure_ascii=False)

class BotState:
    """Класс для хранения состояния бота"""
    def __init__(self):
        self.user_configs = load_configs()
        self.user_data = {}
        self.monitoring = {}
        self.last_signals = {}
        
        # Список основных торговых пар
        self.TOP_PAIRS = [
            'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT',
            'ADA/USDT', 'AVAX/USDT', 'DOT/USDT', 'DOGE/USDT', 'MATIC/USDT',
            'LINK/USDT', 'UNI/USDT', 'PEPE/USDT', 'LTC/USDT', 'BCH/USDT',
            'ARB/USDT', 'OP/USDT', 'ICP/USDT', 'FIL/USDT', 'XLM/USDT'
        ]
        
        # Доступные таймфреймы для анализа
        self.TIMEFRAMES = {
            '1m': ('1 минута', 30),
            '5m': ('5 минут', 60),
            '15m': ('15 минут', 96),
            '1h': ('1 час', 168),
            '4h': ('4 часа', 90),
            '1d': ('1 день', 365)
        }

state = BotState()

# ============================================================================
# ИНТЕГРАЦИЯ С PERPLEXITY AI
# ============================================================================

async def ask_perplexity(question: str, user_id: int = None) -> str:
    """Запрос к Perplexity AI API"""
    config = state.user_configs.get(str(user_id), {}) if user_id else {}
    api_key = config.get('perplexity_key')
    
    if not api_key or api_key == "":
        return "Perplexity API ключ не добавлен. Добавь в [API -> Perplexity]"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.perplexity.ai/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": "sonar-mini",
                    "messages": [{"role": "user", "content": question}],
                    "temperature": 0.5,
                    "max_tokens": 400,
                },
                timeout=15
            )
            if response.status_code == 200:
                data = response.json()
                return data['choices'][0]['message']['content']
            else:
                logger.error(f"Perplexity error: {response.status_code}")
                return f"Ошибка API: {response.status_code}"
    except Exception as e:
        logger.error(f"Perplexity request failed: {e}")
        return f"AI недоступен: {str(e)[:50]}"

# ============================================================================
# ТЕХНИЧЕСКИЙ АНАЛИЗ
# ============================================================================

class Analyzer:
    """Класс для технического анализа торговых пар"""
    def __init__(self, exchange):
        self.exchange = exchange
    
    def analyze(self, symbol: str, timeframe: str = '1h') -> dict:
        """Основной метод анализа торговой пары"""
        try:
            limit = state.TIMEFRAMES.get(timeframe, ('1h', 100))[1]
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            closes = np.array([x[4] for x in ohlcv])
            
            rsi = self.calc_rsi(closes)
            macd, signal, _ = self.calc_macd(closes)
            ma20 = self.calc_ma(closes, 20)
            ma50 = self.calc_ma(closes, 50)
            ma200 = self.calc_ma(closes, 200)
            
            price = float(closes[-1])
            signal_type = self.get_signal(rsi, macd, signal, ma20, ma50, ma200)
            
            return {
                'symbol': symbol,
                'price': price,
                'rsi': float(rsi),
                'macd': float(macd),
                'signal': float(signal),
                'ma20': float(ma20),
                'ma50': float(ma50),
                'ma200': float(ma200),
                'signal_type': signal_type,
                'timeframe': timeframe,
                'timeframe_name': state.TIMEFRAMES[timeframe][0]
            }
        except Exception as e:
            logger.error(f"Analysis error {symbol}: {e}")
            return None
    
    def calc_rsi(self, closes, period=14):
        """Расчет индикатора RSI"""
        if len(closes) < period:
            return 50
        deltas = np.diff(closes)
        seed = deltas[:period+1]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        rs = up / down if down != 0 else 0
        rsi = 100 - (100 / (1 + rs))
        for i in range(period, len(deltas)):
            delta = deltas[i]
            if delta > 0:
                up = (up * (period - 1) + delta) / period
                down = (down * (period - 1)) / period
            else:
                up = (up * (period - 1)) / period
                down = (down * (period - 1) - delta) / period
            rs = up / down if down != 0 else 0
            rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calc_macd(self, closes):
        """Расчет индикатора MACD"""
        if len(closes) < 26:
            return 0, 0, 0
        ema12 = self._ema(closes, 12)
        ema26 = self._ema(closes, 26)
        macd = ema12 - ema26
        signal = self._ema(macd, 9)
        histogram = macd - signal
        return macd[-1], signal[-1], histogram[-1]
    
    def calc_ma(self, closes, period):
        """Расчет скользящей средней"""
        if len(closes) < period:
            return closes[-1]
        return np.mean(closes[-period:])
    
    def _ema(self, data, period):
        """Расчет экспоненциальной скользящей средней"""
        ema = np.zeros_like(data)
        ema[0] = data[0]
        multiplier = 2 / (period + 1)
        for i in range(1, len(data)):
            ema[i] = (data[i] - ema[i-1]) * multiplier + ema[i-1]
        return ema
    
    def get_signal(self, rsi, macd, signal, ma20, ma50, ma200):
        """Определение торгового сигнала на основе индикаторов"""
        score = 0
        if rsi < 30:
            score += 2
        elif rsi > 70:
            score -= 2
        if macd > signal:
            score += 1
        else:
            score -= 1
        if ma20 > ma50 > ma200:
            score += 1
        if score >= 2:
            return 'BUY'
        elif score <= -2:
            return 'SELL'
        else:
            return 'HOLD'

# ============================================================================
# РАБОТА С БАЛАНСОМ
# ============================================================================

def get_exchange(user_id):
    """Получить объект биржи с ключами пользователя"""
    config = state.user_configs.get(str(user_id), {})
    try:
        if config.get('api_key'):
            return ccxt.okx({
                'apiKey': config.get('api_key'),
                'secret': config.get('secret_key'),
                'password': config.get('passphrase'),
                'sandbox': config.get('sandbox_mode', True),
                'enableRateLimit': True
            })
        else:
            return ccxt.okx({'sandbox': True, 'enableRateLimit': True})
    except Exception as e:
        logger.error(f"Exchange init error: {e}")
        return ccxt.okx({'sandbox': True, 'enableRateLimit': True})

async def fetch_balance(user_id: int, account_type: str = 'spot'):
    """Получить баланс с OKX (спот/маржин/фьючерс)"""
    try:
        exchange = get_exchange(user_id)
        config = state.user_configs.get(str(user_id), {})
        
        if not config.get('api_key'):
            return {'total_usdt': 0, 'coins': [], 'account_type': account_type}
        
        balance = exchange.fetch_balance()
        
        total_usdt = 0
        coins = []
        
        for currency, info in balance.items():
            if not isinstance(info, dict):
                continue
            if currency in ['free', 'used', 'total']:
                continue
                
            try:
                free = float(info.get('free', 0)) if info.get('free') else 0
                used = float(info.get('used', 0)) if info.get('used') else 0
                total_amount = free + used
                
                if total_amount > 0.000001:
                    if currency == 'USDT':
                        total_usdt = total_amount
                    
                    coins.append({
                        'symbol': currency,
                        'free': free,
                        'used': used,
                        'total': total_amount
                    })
            except (ValueError, TypeError):
                continue
        
        coins = sorted(coins, key=lambda x: x['total'], reverse=True)[:20]
        
        logger.info(f"Balance: USDT={total_usdt:.2f}, coins={len(coins)}")
        
        return {
            'total_usdt': float(total_usdt),
            'coins': coins,
            'account_type': account_type
        }
            
    except Exception as e:
        logger.error(f"Balance error: {e}")
        return {'total_usdt': 0, 'coins': [], 'account_type': account_type}

# ============================================================================
# ГЛАВНОЕ МЕНЮ
# ============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start (главное меню)"""
    user_id = update.effective_user.id
    
    if str(user_id) not in state.user_data:
        state.user_data[str(user_id)] = {
            'selected_pairs': [],
            'timeframe': '1h',
            'signal_pairs': ['BTC/USDT', 'ETH/USDT', 'BNB/USDT'],
            'signal_interval': 5
        }
    
    keyboard = [
        [InlineKeyboardButton('Анализ', callback_data='analyze'), InlineKeyboardButton('Баланс', callback_data='balance')],
        [InlineKeyboardButton('Сигналы', callback_data='signals'), InlineKeyboardButton('Таймфрейм', callback_data='timeframe')],
        [InlineKeyboardButton('API', callback_data='api'), InlineKeyboardButton('AI', callback_data='ai')],
        [InlineKeyboardButton('Помощь', callback_data='help')],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = """COPY TRADING BOT PRO

Анализ + AI + Баланс + Сигналы

Выбери действие:"""
    
    if update.message:
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    else:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

# ============================================================================
# УПРАВЛЕНИЕ БАЛАНСОМ
# ============================================================================

async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать баланс пользователя"""
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text('Загружаю баланс...', parse_mode=ParseMode.HTML)
    
    account_type = state.user_data.get(str(user_id), {}).get('account_type', 'spot')
    balance_data = await fetch_balance(user_id, account_type)
    total = balance_data['total_usdt']
    coins = balance_data['coins']
    
    if total > 0.01:
        total_str = f"${total:,.2f}"
    elif total > 0:
        total_str = f"${total:.8f}".rstrip('0').rstrip('.')
    else:
        total_str = "$0.00"
    
    message = f"""БАЛАНС ({account_type.upper()})

Total USDT: {total_str}
Монет: {len(coins)}

Активы:
"""
    
    if coins:
        for coin in coins:
            symbol = coin['symbol']
            free = coin['free']
            used = coin['used']
            
            if free > 1:
                free_str = f"{free:,.2f}"
            elif free > 0:
                free_str = f"{free:.8f}".rstrip('0').rstrip('.')
            else:
                free_str = "0"
            
            if used > 0.00000001:
                used_str = f"{used:.8f}".rstrip('0').rstrip('.')
                message += f"{symbol:8s} {free_str:>12s} | Ордеры: {used_str}\n"
            else:
                message += f"{symbol:8s} {free_str:>12s}\n"
    else:
        message += "Нет активов\n"
    
    config = state.user_configs.get(str(user_id), {})
    api_status = '✅' if config.get('api_key') else '❌'
    message += f"\nOKX API: {api_status}"
    
    keyboard = [
        [InlineKeyboardButton('Счета', callback_data='account_type'), InlineKeyboardButton('Обновить', callback_data='balance')],
        [InlineKeyboardButton('Назад', callback_data='back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

async def show_account_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор типа счета"""
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    current = state.user_data.get(str(user_id), {}).get('account_type', 'spot')
    
    keyboard = [
        [InlineKeyboardButton(f"{'✅' if current == 'spot' else '◾'} Спот (trading)", callback_data='at_spot')],
        [InlineKeyboardButton(f"{'✅' if current == 'margin' else '◾'} Маржин", callback_data='at_margin')],
        [InlineKeyboardButton(f"{'✅' if current == 'futures' else '◾'} Фьючерс", callback_data='at_futures')],
        [InlineKeyboardButton('Назад', callback_data='balance')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = f"""ТИП СЧЕТА

Текущий: {current.upper()}

Выбери:"""
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

async def set_account_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установить тип счета"""
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    account_type = query.data.replace('at_', '')
    state.user_data[str(user_id)]['account_type'] = account_type
    
    await query.answer(f'{account_type.upper()} счет', show_alert=True)
    await show_balance(update, context)

# ============================================================================
# АНАЛИЗ С ИСПОЛЬЗОВАНИЕМ AI
# ============================================================================

async def show_pairs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор пар для анализа"""
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    keyboard = []
    for i in range(0, len(state.TOP_PAIRS), 2):
        row = []
        for j in range(2):
            if i + j < len(state.TOP_PAIRS):
                pair = state.TOP_PAIRS[i + j]
                is_selected = pair in state.user_data[str(user_id)]['selected_pairs']
                symbol = '✅' if is_selected else '◾'
                row.append(InlineKeyboardButton(
                    f"{symbol} {pair.split('/')[0]}",
                    callback_data=f"pair_{pair}"
                ))
        if row:
            keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton('АНАЛИЗИРОВАТЬ', callback_data='do_analyze')])
    keyboard.append([InlineKeyboardButton('Назад', callback_data='back')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    selected = len(state.user_data[str(user_id)]['selected_pairs'])
    message = f"""ВЫБОР ПАР

Выбрано: {selected}

Нажми на пару:"""
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

async def toggle_pair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбрать/снять выбор пары"""
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    pair = query.data.replace('pair_', '')
    pairs = state.user_data[str(user_id)]['selected_pairs']
    
    if pair in pairs:
        pairs.remove(pair)
    else:
        pairs.append(pair)
    
    await show_pairs(update, context)

async def do_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Провести анализ выбранных пар"""
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    selected = state.user_data[str(user_id)]['selected_pairs']
    timeframe = state.user_data[str(user_id)]['timeframe']
    
    if not selected:
        await query.answer('Выбери пары!', show_alert=True)
        return
    
    await query.edit_message_text('Анализирую + AI...', parse_mode=ParseMode.HTML)
    
    exchange = get_exchange(user_id)
    analyzer = Analyzer(exchange)
    results = []
    
    for pair in selected:
        analysis = analyzer.analyze(pair, timeframe)
        if analysis:
            results.append(analysis)
        await asyncio.sleep(0.1)
    
    message = f"""РЕЗУЛЬТАТЫ

Таймфрейм: {state.TIMEFRAMES[timeframe][0]}
Пар: {len(results)}

"""
    
    pairs_text = []
    
    for r in results:
        rsi_status = "⚠️" if r['rsi'] > 70 else "📌" if r['rsi'] < 30 else "✅"
        message += f"""{r['symbol']}
${r['price']:.2f} | RSI: {r['rsi']:.0f}{rsi_status}
MACD: {r['macd']:.2f}
{r['signal_type']}

"""
        pairs_text.append(f"{r['symbol']} (RSI:{r['rsi']:.0f}) -> {r['signal_type']}")
    
    # AI анализ
    if results and pairs_text:
        question = (
            f"Проанализируй эти сигналы крипто на таймфрейме {state.TIMEFRAMES[timeframe][0]}:\n"
            + "\n".join(pairs_text) +
            "\n\nДай умный краткий вывод (2-3 предложения): что сейчас лучше покупать/продавать? "
            "Ответь по-русски."
        )
        ai_response = await ask_perplexity(question, user_id)
        message += f"""
AI АНАЛИЗ:
{ai_response}
"""
    
    keyboard = [
        [InlineKeyboardButton('Новый анализ', callback_data='analyze')],
        [InlineKeyboardButton('В меню', callback_data='back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

# ============================================================================
# АВТОМАТИЧЕСКИЕ СИГНАЛЫ
# ============================================================================

async def show_signals_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню управления сигналами"""
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    user_id_str = str(user_id)
    if user_id_str not in state.user_data:
        state.user_data[user_id_str] = {
            'selected_pairs': [],
            'timeframe': '1h',
            'signal_pairs': ['BTC/USDT', 'ETH/USDT', 'BNB/USDT'],
            'signal_interval': 5
        }
    
    monitoring_enabled = state.monitoring.get(user_id_str, False)
    status = 'ВКЛ' if monitoring_enabled else 'ВЫКЛ'
    
    signal_pairs = state.user_data[user_id_str].get('signal_pairs', [])
    signal_interval = state.user_data[user_id_str].get('signal_interval', 5)
    
    keyboard = [
        [InlineKeyboardButton(f'Включить/Выключить ({status})', callback_data='toggle_signals')],
        [InlineKeyboardButton(f'Интервал ({signal_interval}м)', callback_data='signal_interval')],
        [InlineKeyboardButton(f'Пары ({len(signal_pairs)})', callback_data='signal_pairs')],
        [InlineKeyboardButton('Назад', callback_data='back')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = f"""АВТОСИГНАЛЫ

Статус: {status}
Интервал: {signal_interval} минут
Пар: {len(signal_pairs)}

Получай BUY / SELL сигналы автоматически!"""
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

async def toggle_signals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Включить/выключить автоматические сигналы"""
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    user_id_str = str(user_id)
    current = state.monitoring.get(user_id_str, False)
    state.monitoring[user_id_str] = not current
    
    if state.monitoring[user_id_str]:
        await query.answer('Сигналы ВКЛЮЧЕНЫ', show_alert=True)
    else:
        await query.answer('Сигналы ВЫКЛЮЧЕНЫ', show_alert=True)
    
    await show_signals_menu(update, context)

async def show_signal_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор интервала проверки сигналов"""
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    current = state.user_data[str(user_id)].get('signal_interval', 5)
    
    keyboard = [
        [InlineKeyboardButton(f"{'✅' if current == 5 else '◾'} 5 минут", callback_data='si_5')],
        [InlineKeyboardButton(f"{'✅' if current == 15 else '◾'} 15 минут", callback_data='si_15')],
        [InlineKeyboardButton(f"{'✅' if current == 30 else '◾'} 30 минут", callback_data='si_30')],
        [InlineKeyboardButton(f"{'✅' if current == 60 else '◾'} 1 час", callback_data='si_60')],
        [InlineKeyboardButton('В меню', callback_data='back')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = f"""ИНТЕРВАЛ СИГНАЛОВ

Текущий: {current} минут

Выбери интервал:"""
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

async def set_signal_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установить интервал проверки сигналов"""
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    interval = int(query.data.replace('si_', ''))
    state.user_data[str(user_id)]['signal_interval'] = interval
    
    await query.answer(f'Интервал {interval} минут', show_alert=True)
    await show_signals_menu(update, context)

async def show_signal_pairs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор пар для автоматических сигналов"""
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    keyboard = []
    for i in range(0, len(state.TOP_PAIRS), 2):
        row = []
        for j in range(2):
            if i + j < len(state.TOP_PAIRS):
                pair = state.TOP_PAIRS[i + j]
                is_selected = pair in state.user_data[str(user_id)]['signal_pairs']
                symbol = '✅' if is_selected else '◾'
                row.append(InlineKeyboardButton(
                    f"{symbol} {pair.split('/')[0]}",
                    callback_data=f"sigpair_{pair}"
                ))
        if row:
            keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton('В меню', callback_data='back')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    selected = len(state.user_data[str(user_id)]['signal_pairs'])
    message = f"""ПАРЫ ДЛЯ СИГНАЛОВ

Выбрано: {selected}

Нажми на пару:"""
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

async def toggle_signal_pair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбрать/снять выбор пары для сигналов"""
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    pair = query.data.replace('sigpair_', '')
    pairs = state.user_data[str(user_id)]['signal_pairs']
    
    if pair in pairs:
        pairs.remove(pair)
    else:
        pairs.append(pair)
    
    await show_signal_pairs(update, context)

# ============================================================================
# УПРАВЛЕНИЕ ТАЙМФРЕЙМОМ
# ============================================================================

async def show_timeframes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор таймфрейма для анализа"""
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    current_tf = state.user_data[str(user_id)]['timeframe']
    
    keyboard = []
    for tf_key, (tf_name, _) in state.TIMEFRAMES.items():
        is_selected = '✅' if tf_key == current_tf else '◾'
        keyboard.append([InlineKeyboardButton(
            f"{is_selected} {tf_name}",
            callback_data=f"tf_{tf_key}"
        )])
    
    keyboard.append([InlineKeyboardButton('Назад', callback_data='back')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = f"""ТАЙМФРЕЙМ

Текущий: {state.TIMEFRAMES[current_tf][0]}

Выбери:"""
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

async def select_timeframe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбрать таймфрейм"""
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    tf = query.data.replace('tf_', '')
    state.user_data[str(user_id)]['timeframe'] = tf
    
    await query.answer(f'{state.TIMEFRAMES[tf][0]}', show_alert=True)
    await show_timeframes(update, context)

# ============================================================================
# УПРАВЛЕНИЕ API КЛЮЧАМИ
# ============================================================================

# Состояния для ConversationHandler
WAITING_API_KEY, WAITING_SECRET, WAITING_PASSPHRASE, WAITING_PERPLEXITY = range(4)

async def show_api(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню управления API ключами"""
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    config = state.user_configs.get(str(user_id), {})
    okx_status = '✅' if config.get('api_key') else '❌'
    perplexity_status = '✅' if config.get('perplexity_key') else '❌'
    
    keyboard = [
        [InlineKeyboardButton('OKX API Key', callback_data='add_api')],
        [InlineKeyboardButton('OKX Secret', callback_data='add_secret')],
        [InlineKeyboardButton('OKX Passphrase', callback_data='add_pass')],
        [InlineKeyboardButton(f'Perplexity {perplexity_status}', callback_data='add_perplexity')],
        [InlineKeyboardButton(f'{okx_status} Проверить OKX', callback_data='check_api')],
        [InlineKeyboardButton('В меню', callback_data='back')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = f"""API УПРАВЛЕНИЕ

OKX: {okx_status}
• API: {'✅' if config.get('api_key') else '❌'}
• Secret: {'✅' if config.get('secret_key') else '❌'}
• Pass: {'✅' if config.get('passphrase') else '❌'}

Perplexity: {perplexity_status}
• Key: {'✅' if config.get('perplexity_key') else '❌'}"""
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

async def add_api_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить API Key OKX"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [[InlineKeyboardButton('Отмена', callback_data='api')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "Введи OKX API Key:\n\n(отправь текстом)",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    return WAITING_API_KEY

async def receive_api_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить и сохранить API Key OKX"""
    user_id = update.effective_user.id
    user_id_str = str(user_id)
    api_key = update.message.text.strip()
    
    if user_id_str not in state.user_configs:
        state.user_configs[user_id_str] = {}
    
    state.user_configs[user_id_str]['api_key'] = api_key
    save_configs(state.user_configs)
    
    keyboard = [[InlineKeyboardButton('API меню', callback_data='api')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"API Key сохранен!\n\n{api_key[:25]}...\n\nВведи Secret Key в следующем сообщении или вернись в меню",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    
    return ConversationHandler.END

async def add_secret_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить Secret Key OKX"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [[InlineKeyboardButton('Отмена', callback_data='api')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "Введи OKX Secret Key:\n\n(отправь текстом)",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    return WAITING_SECRET

async def receive_secret_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить и сохранить Secret Key OKX"""
    user_id = update.effective_user.id
    user_id_str = str(user_id)
    secret_key = update.message.text.strip()
    
    if user_id_str not in state.user_configs:
        state.user_configs[user_id_str] = {}
    
    state.user_configs[user_id_str]['secret_key'] = secret_key
    save_configs(state.user_configs)
    
    keyboard = [[InlineKeyboardButton('API меню', callback_data='api')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Secret Key сохранен!\n\n{secret_key[:25]}...\n\nВведи Passphrase или вернись в меню",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    
    return ConversationHandler.END

async def add_passphrase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить Passphrase OKX"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [[InlineKeyboardButton('Отмена', callback_data='api')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "Введи OKX Passphrase:\n\n(отправь текстом)",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    return WAITING_PASSPHRASE

async def receive_passphrase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить и сохранить Passphrase OKX"""
    user_id = update.effective_user.id
    user_id_str = str(user_id)
    passphrase = update.message.text.strip()
    
    if user_id_str not in state.user_configs:
        state.user_configs[user_id_str] = {}
    
    state.user_configs[user_id_str]['passphrase'] = passphrase
    save_configs(state.user_configs)
    
    keyboard = [[InlineKeyboardButton('API меню', callback_data='api')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Passphrase сохранен!\n\n{passphrase}\n\nВсе готово! Возвращайся в меню",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    
    return ConversationHandler.END

async def add_perplexity_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить API ключ Perplexity"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [[InlineKeyboardButton('Отмена', callback_data='api')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "Введи Perplexity API Key:\n\n"
        "Получи на https://www.perplexity.ai/api/\n"
        "(отправь текстом: ppl_...)",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    return WAITING_PERPLEXITY

async def receive_perplexity_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить и сохранить API ключ Perplexity"""
    user_id = update.effective_user.id
    user_id_str = str(user_id)
    perplexity_key = update.message.text.strip()
    
    if user_id_str not in state.user_configs:
        state.user_configs[user_id_str] = {}
    
    state.user_configs[user_id_str]['perplexity_key'] = perplexity_key
    save_configs(state.user_configs)
    
    keyboard = [[InlineKeyboardButton('API меню', callback_data='api')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Perplexity API Key сохранен!\n\n{perplexity_key[:30]}...\n\nГотово! Теперь AI будет работать",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    
    return ConversationHandler.END

async def check_api_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверить подключение к OKX API"""
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    config = state.user_configs.get(str(user_id), {})
    
    if not config.get('api_key'):
        await query.answer('Добавь API Key!', show_alert=True)
        return
    
    try:
        exchange = ccxt.okx({
            'apiKey': config.get('api_key'),
            'secret': config.get('secret_key'),
            'password': config.get('passphrase'),
            'sandbox': config.get('sandbox_mode', True),
            'enableRateLimit': True
        })
        balance = exchange.fetch_balance()
        await query.answer('OKX API подключен!', show_alert=True)
    except Exception as e:
        await query.answer(f'Ошибка: {str(e)[:50]}', show_alert=True)

# ============================================================================
# AI ПОМОЩНИК
# ============================================================================

async def show_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню AI помощника"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton('Что покупать?', callback_data='ai_buy'), InlineKeyboardButton('Индикаторы', callback_data='ai_indicators')],
        [InlineKeyboardButton('Стратегия', callback_data='ai_strategy'), InlineKeyboardButton('Риски', callback_data='ai_risk')],
        [InlineKeyboardButton('В меню', callback_data='back')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = """AI ПОМОЩНИК

Спроси Perplexity:"""
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

async def ai_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка AI вопросов"""
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    questions = {
        'ai_buy': "Какие топ-5 крипто монет лучше всего купить прямо сейчас в краткосрочной торговле на 1 час? Дай кратко с объяснением.",
        'ai_indicators': "Объясни на одной странице: RSI, MACD, Moving Averages (MA) и как их использовать вместе в торговле крипто?",
        'ai_strategy': "Расскажи лучшие стратегии торговли крипто для новичка на таймфрейме 1h. Дай 3-4 конкретных совета.",
        'ai_risk': "Как правильно управлять риском в трейдинге крипто? Дай конкретные советы о stop loss и размере позиции."
    }
    
    question = questions.get(query.data)
    if not question:
        return
    
    await query.edit_message_text('AI думает...', parse_mode=ParseMode.HTML)
    
    response = await ask_perplexity(question, user_id)
    
    keyboard = [
        [InlineKeyboardButton('Еще вопрос', callback_data='ai')],
        [InlineKeyboardButton('В меню', callback_data='back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = f"""ОТВЕТ AI:

{response}
"""
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

# ============================================================================
# СПРАВКА
# ============================================================================

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать справку"""
    query = update.callback_query
    await query.answer()
    
    message = """СПРАВКА

Анализировать
Выбери пары -> получи техан + AI анализ

Баланс
Твой баланс USDT и все монеты на OKX

Сигналы
Автоматические уведомления BUY / SELL

Таймфрейм
Выбери время анализа (1m, 5m, 15m, 1h, 4h, 1d)

API
Добавь ключи OKX и Perplexity

AI
Вопросы помощнику Perplexity

Сигналы:
BUY - Покупай!
SELL - Продавай!
HOLD - Жди

Все данные сохраняются в config.json"""
    
    keyboard = [[InlineKeyboardButton('В меню', callback_data='back')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

# ============================================================================
# НАВИГАЦИЯ
# ============================================================================

async def back_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное меню"""
    query = update.callback_query
    await query.answer()
    await start(update, context)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Основной обработчик callback кнопок"""
    query = update.callback_query
    
    handlers = {
        'analyze': show_pairs,
        'balance': show_balance,
        'account_type': show_account_type,
        'signals': show_signals_menu,
        'toggle_signals': toggle_signals,
        'signal_interval': show_signal_interval,
        'signal_pairs': show_signal_pairs,
        'timeframe': show_timeframes,
        'api': show_api,
        'add_api': add_api_key,
        'add_secret': add_secret_key,
        'add_pass': add_passphrase,
        'add_perplexity': add_perplexity_key,
        'check_api': check_api_status,
        'ai': show_ai,
        'help': show_help,
        'back': back_handler,
    }
    
    if query.data.startswith('pair_'):
        await toggle_pair(update, context)
    elif query.data == 'do_analyze':
        await do_analyze(update, context)
    elif query.data.startswith('tf_'):
        await select_timeframe(update, context)
    elif query.data.startswith('si_'):
        await set_signal_interval(update, context)
    elif query.data.startswith('sigpair_'):
        await toggle_signal_pair(update, context)
    elif query.data.startswith('at_'):
        await set_account_type(update, context)
    elif query.data.startswith('ai_'):
        await ai_handler(update, context)
    elif query.data in handlers:
        await handlers[query.data](update, context)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f'Error: {context.error}')

# ============================================================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================================================

def main():
    """Основная функция запуска бота"""
    TOKEN = input('TELEGRAM_BOT_TOKEN: ').strip()
    
    logger.info('='*70)
    logger.info('COPY TRADING BOT PRO - FINAL RELEASE')
    logger.info('Анализ + Perplexity + Баланс + Сигналы')
    logger.info('='*70)
    
    app = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(add_api_key, pattern='^add_api$'),
            CallbackQueryHandler(add_secret_key, pattern='^add_secret$'),
            CallbackQueryHandler(add_passphrase, pattern='^add_pass$'),
            CallbackQueryHandler(add_perplexity_key, pattern='^add_perplexity$'),
        ],
        states={
            WAITING_API_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_api_key)],
            WAITING_SECRET: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_secret_key)],
            WAITING_PASSPHRASE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_passphrase)],
            WAITING_PERPLEXITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_perplexity_key)],
        },
        fallbacks=[CommandHandler('start', start)],
    )
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_error_handler(error_handler)
    
    logger.info('Бот запущен!')
    logger.info('/start в Telegram для начала')
    logger.info(f'Данные сохраняются в {CONFIG_FILE}')
    
    app.run_polling()

if __name__ == '__main__':
    main()