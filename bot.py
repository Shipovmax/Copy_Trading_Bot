"""
All data is stored locally in user_configs.json.
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

# Logging configuration
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
# CONFIGURATION AND DATA STORAGE
# ============================================================================

CONFIG_FILE = 'user_configs.json'

def load_configs():
    """Load user configurations from disk."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_configs(configs):
    """Save user configurations to disk."""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(configs, f, indent=2, ensure_ascii=False)

class BotState:
    """Container for bot state."""
    def __init__(self):
        self.user_configs = load_configs()
        self.user_data = {}
        self.monitoring = {}
        self.last_signals = {}
        
        # List of primary trading pairs
        self.TOP_PAIRS = [
            'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT',
            'ADA/USDT', 'AVAX/USDT', 'DOT/USDT', 'DOGE/USDT', 'MATIC/USDT',
            'LINK/USDT', 'UNI/USDT', 'PEPE/USDT', 'LTC/USDT', 'BCH/USDT',
            'ARB/USDT', 'OP/USDT', 'ICP/USDT', 'FIL/USDT', 'XLM/USDT'
        ]
        
        # Available analysis timeframes
        self.TIMEFRAMES = {
            '1m': ('1 minute', 30),
            '5m': ('5 minutes', 60),
            '15m': ('15 minutes', 96),
            '1h': ('1 hour', 168),
            '4h': ('4 hours', 90),
            '1d': ('1 day', 365)
        }

state = BotState()

# ============================================================================
# PERPLEXITY AI INTEGRATION
# ============================================================================

async def ask_perplexity(question: str, user_id: int = None) -> str:
    """Send a request to the Perplexity AI API."""
    config = state.user_configs.get(str(user_id), {}) if user_id else {}
    api_key = config.get('perplexity_key')
    
    if not api_key or api_key == "":
        return "Perplexity API key is not configured. Add it in [API -> Perplexity]."
    
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
                return f"API error: {response.status_code}"
    except Exception as e:
        logger.error(f"Perplexity request failed: {e}")
        return f"AI unavailable: {str(e)[:50]}"

# ============================================================================
# TECHNICAL ANALYSIS
# ============================================================================

class Analyzer:
    """Technical analysis for trading pairs."""
    def __init__(self, exchange):
        self.exchange = exchange
    
    def analyze(self, symbol: str, timeframe: str = '1h') -> dict:
        """Run analysis for a trading pair."""
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
        """Calculate the RSI indicator."""
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
        """Calculate the MACD indicator."""
        if len(closes) < 26:
            return 0, 0, 0
        ema12 = self._ema(closes, 12)
        ema26 = self._ema(closes, 26)
        macd = ema12 - ema26
        signal = self._ema(macd, 9)
        histogram = macd - signal
        return macd[-1], signal[-1], histogram[-1]
    
    def calc_ma(self, closes, period):
        """Calculate a moving average."""
        if len(closes) < period:
            return closes[-1]
        return np.mean(closes[-period:])
    
    def _ema(self, data, period):
        """Calculate an exponential moving average."""
        ema = np.zeros_like(data)
        ema[0] = data[0]
        multiplier = 2 / (period + 1)
        for i in range(1, len(data)):
            ema[i] = (data[i] - ema[i-1]) * multiplier + ema[i-1]
        return ema
    
    def get_signal(self, rsi, macd, signal, ma20, ma50, ma200):
        """Determine a trading signal based on indicators."""
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
# BALANCE HANDLING
# ============================================================================

def get_exchange(user_id):
    """Return an exchange instance using the user's credentials."""
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
    """Fetch the OKX balance for the selected account type."""
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
# MAIN MENU
# ============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /start command and show the main menu."""
    user_id = update.effective_user.id
    
    if str(user_id) not in state.user_data:
        state.user_data[str(user_id)] = {
            'selected_pairs': [],
            'timeframe': '1h',
            'signal_pairs': ['BTC/USDT', 'ETH/USDT', 'BNB/USDT'],
            'signal_interval': 5
        }
    
    keyboard = [
        [InlineKeyboardButton('Analysis', callback_data='analyze'), InlineKeyboardButton('Balance', callback_data='balance')],
        [InlineKeyboardButton('Signals', callback_data='signals'), InlineKeyboardButton('Timeframe', callback_data='timeframe')],
        [InlineKeyboardButton('API', callback_data='api'), InlineKeyboardButton('AI', callback_data='ai')],
        [InlineKeyboardButton('Help', callback_data='help')],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = """COPY TRADING BOT PRO

Analysis + AI + Balance + Signals

Choose an action:"""
    
    if update.message:
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    else:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

# ============================================================================
# BALANCE MANAGEMENT
# ============================================================================

async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the user's balance."""
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text('Loading balance...', parse_mode=ParseMode.HTML)
    
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
    
    message = f"""BALANCE ({account_type.upper()})

Total USDT: {total_str}
Coins: {len(coins)}

Assets:
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
                message += f"{symbol:8s} {free_str:>12s} | Orders: {used_str}\n"
            else:
                message += f"{symbol:8s} {free_str:>12s}\n"
    else:
        message += "No assets\n"
    
    config = state.user_configs.get(str(user_id), {})
    api_status = '✅' if config.get('api_key') else '❌'
    message += f"\nOKX API: {api_status}"
    
    keyboard = [
        [InlineKeyboardButton('Accounts', callback_data='account_type'), InlineKeyboardButton('Refresh', callback_data='balance')],
        [InlineKeyboardButton('Back', callback_data='back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

async def show_account_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show account type selection."""
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    current = state.user_data.get(str(user_id), {}).get('account_type', 'spot')
    
    keyboard = [
        [InlineKeyboardButton(f"{'✅' if current == 'spot' else '◾'} Spot (trading)", callback_data='at_spot')],
        [InlineKeyboardButton(f"{'✅' if current == 'margin' else '◾'} Margin", callback_data='at_margin')],
        [InlineKeyboardButton(f"{'✅' if current == 'futures' else '◾'} Futures", callback_data='at_futures')],
        [InlineKeyboardButton('Back', callback_data='balance')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = f"""ACCOUNT TYPE

Current: {current.upper()}

Choose:"""
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

async def set_account_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set the account type."""
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    account_type = query.data.replace('at_', '')
    state.user_data[str(user_id)]['account_type'] = account_type
    
    await query.answer(f'{account_type.upper()} account', show_alert=True)
    await show_balance(update, context)

# ============================================================================
# AI-ASSISTED ANALYSIS
# ============================================================================

async def show_pairs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show pair selection for analysis."""
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
    
    keyboard.append([InlineKeyboardButton('ANALYZE', callback_data='do_analyze')])
    keyboard.append([InlineKeyboardButton('Back', callback_data='back')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    selected = len(state.user_data[str(user_id)]['selected_pairs'])
    message = f"""PAIR SELECTION

Selected: {selected}

Tap a pair:"""
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

async def toggle_pair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle pair selection."""
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
    """Analyze the selected pairs."""
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    selected = state.user_data[str(user_id)]['selected_pairs']
    timeframe = state.user_data[str(user_id)]['timeframe']
    
    if not selected:
        await query.answer('Select at least one pair.', show_alert=True)
        return
    
    await query.edit_message_text('Running analysis + AI...', parse_mode=ParseMode.HTML)
    
    exchange = get_exchange(user_id)
    analyzer = Analyzer(exchange)
    results = []
    
    for pair in selected:
        analysis = analyzer.analyze(pair, timeframe)
        if analysis:
            results.append(analysis)
        await asyncio.sleep(0.1)
    
    message = f"""RESULTS

Timeframe: {state.TIMEFRAMES[timeframe][0]}
Pairs: {len(results)}

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
    
    # AI analysis
    if results and pairs_text:
        question = (
            f"Analyze these crypto signals on the {state.TIMEFRAMES[timeframe][0]} timeframe:\n"
            + "\n".join(pairs_text) +
            "\n\nProvide a concise, smart conclusion in 2-3 sentences: what is better to buy or sell right now? "
            "Answer in English."
        )
        ai_response = await ask_perplexity(question, user_id)
        message += f"""
AI ANALYSIS:
{ai_response}
"""
    
    keyboard = [
        [InlineKeyboardButton('New analysis', callback_data='analyze')],
        [InlineKeyboardButton('Main menu', callback_data='back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

# ============================================================================
# AUTOMATED SIGNALS
# ============================================================================

async def show_signals_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the signals management menu."""
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
    status = 'ON' if monitoring_enabled else 'OFF'
    
    signal_pairs = state.user_data[user_id_str].get('signal_pairs', [])
    signal_interval = state.user_data[user_id_str].get('signal_interval', 5)
    
    keyboard = [
        [InlineKeyboardButton(f'Toggle ({status})', callback_data='toggle_signals')],
        [InlineKeyboardButton(f'Interval ({signal_interval}m)', callback_data='signal_interval')],
        [InlineKeyboardButton(f'Pairs ({len(signal_pairs)})', callback_data='signal_pairs')],
        [InlineKeyboardButton('Back', callback_data='back')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = f"""AUTO SIGNALS

Status: {status}
Interval: {signal_interval} minutes
Pairs: {len(signal_pairs)}

Receive BUY / SELL signals automatically."""
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

async def toggle_signals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enable or disable automated signals."""
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    user_id_str = str(user_id)
    current = state.monitoring.get(user_id_str, False)
    state.monitoring[user_id_str] = not current
    
    if state.monitoring[user_id_str]:
        await query.answer('Signals enabled', show_alert=True)
    else:
        await query.answer('Signals disabled', show_alert=True)
    
    await show_signals_menu(update, context)

async def show_signal_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show signal interval selection."""
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    current = state.user_data[str(user_id)].get('signal_interval', 5)
    
    keyboard = [
        [InlineKeyboardButton(f"{'✅' if current == 5 else '◾'} 5 minutes", callback_data='si_5')],
        [InlineKeyboardButton(f"{'✅' if current == 15 else '◾'} 15 minutes", callback_data='si_15')],
        [InlineKeyboardButton(f"{'✅' if current == 30 else '◾'} 30 minutes", callback_data='si_30')],
        [InlineKeyboardButton(f"{'✅' if current == 60 else '◾'} 1 hour", callback_data='si_60')],
        [InlineKeyboardButton('Main menu', callback_data='back')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = f"""SIGNAL INTERVAL

Current: {current} minutes

Choose an interval:"""
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

async def set_signal_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set the signal check interval."""
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    interval = int(query.data.replace('si_', ''))
    state.user_data[str(user_id)]['signal_interval'] = interval
    
    await query.answer(f'Interval: {interval} minutes', show_alert=True)
    await show_signals_menu(update, context)

async def show_signal_pairs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show pair selection for automated signals."""
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
    
    keyboard.append([InlineKeyboardButton('Main menu', callback_data='back')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    selected = len(state.user_data[str(user_id)]['signal_pairs'])
    message = f"""SIGNAL PAIRS

Selected: {selected}

Tap a pair:"""
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

async def toggle_signal_pair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle signal pair selection."""
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
# TIMEFRAME MANAGEMENT
# ============================================================================

async def show_timeframes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show timeframe selection for analysis."""
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
    
    keyboard.append([InlineKeyboardButton('Back', callback_data='back')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = f"""TIMEFRAME

Current: {state.TIMEFRAMES[current_tf][0]}

Choose:"""
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

async def select_timeframe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Select a timeframe."""
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    tf = query.data.replace('tf_', '')
    state.user_data[str(user_id)]['timeframe'] = tf
    
    await query.answer(f'{state.TIMEFRAMES[tf][0]}', show_alert=True)
    await show_timeframes(update, context)

# ============================================================================
# API KEY MANAGEMENT
# ============================================================================

# ConversationHandler states
WAITING_API_KEY, WAITING_SECRET, WAITING_PASSPHRASE, WAITING_PERPLEXITY = range(4)

async def show_api(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the API management menu."""
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
        [InlineKeyboardButton(f'{okx_status} Check OKX', callback_data='check_api')],
        [InlineKeyboardButton('Main menu', callback_data='back')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = f"""API MANAGEMENT

OKX: {okx_status}
• API: {'✅' if config.get('api_key') else '❌'}
• Secret: {'✅' if config.get('secret_key') else '❌'}
• Pass: {'✅' if config.get('passphrase') else '❌'}

Perplexity: {perplexity_status}
• Key: {'✅' if config.get('perplexity_key') else '❌'}"""
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

async def add_api_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompt for the OKX API key."""
    query = update.callback_query
    await query.answer()
    
    keyboard = [[InlineKeyboardButton('Cancel', callback_data='api')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "Enter the OKX API Key:\n\n(send it as plain text)",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    return WAITING_API_KEY

async def receive_api_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive and save the OKX API key."""
    user_id = update.effective_user.id
    user_id_str = str(user_id)
    api_key = update.message.text.strip()
    
    if user_id_str not in state.user_configs:
        state.user_configs[user_id_str] = {}
    
    state.user_configs[user_id_str]['api_key'] = api_key
    save_configs(state.user_configs)
    
    keyboard = [[InlineKeyboardButton('API menu', callback_data='api')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"API Key saved.\n\n{api_key[:25]}...\n\nEnter the Secret Key in the next message or return to the menu.",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    
    return ConversationHandler.END

async def add_secret_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompt for the OKX Secret Key."""
    query = update.callback_query
    await query.answer()
    
    keyboard = [[InlineKeyboardButton('Cancel', callback_data='api')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "Enter the OKX Secret Key:\n\n(send it as plain text)",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    return WAITING_SECRET

async def receive_secret_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive and save the OKX Secret Key."""
    user_id = update.effective_user.id
    user_id_str = str(user_id)
    secret_key = update.message.text.strip()
    
    if user_id_str not in state.user_configs:
        state.user_configs[user_id_str] = {}
    
    state.user_configs[user_id_str]['secret_key'] = secret_key
    save_configs(state.user_configs)
    
    keyboard = [[InlineKeyboardButton('API menu', callback_data='api')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Secret Key saved.\n\n{secret_key[:25]}...\n\nEnter the Passphrase or return to the menu.",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    
    return ConversationHandler.END

async def add_passphrase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompt for the OKX Passphrase."""
    query = update.callback_query
    await query.answer()
    
    keyboard = [[InlineKeyboardButton('Cancel', callback_data='api')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "Enter the OKX Passphrase:\n\n(send it as plain text)",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    return WAITING_PASSPHRASE

async def receive_passphrase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive and save the OKX Passphrase."""
    user_id = update.effective_user.id
    user_id_str = str(user_id)
    passphrase = update.message.text.strip()
    
    if user_id_str not in state.user_configs:
        state.user_configs[user_id_str] = {}
    
    state.user_configs[user_id_str]['passphrase'] = passphrase
    save_configs(state.user_configs)
    
    keyboard = [[InlineKeyboardButton('API menu', callback_data='api')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Passphrase saved.\n\n{passphrase}\n\nSetup is complete. Return to the menu.",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    
    return ConversationHandler.END

async def add_perplexity_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompt for the Perplexity API key."""
    query = update.callback_query
    await query.answer()
    
    keyboard = [[InlineKeyboardButton('Cancel', callback_data='api')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "Enter the Perplexity API Key:\n\n"
        "Get it at https://www.perplexity.ai/api/\n"
        "(send it as plain text: ppl_...)",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    return WAITING_PERPLEXITY

async def receive_perplexity_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive and save the Perplexity API key."""
    user_id = update.effective_user.id
    user_id_str = str(user_id)
    perplexity_key = update.message.text.strip()
    
    if user_id_str not in state.user_configs:
        state.user_configs[user_id_str] = {}
    
    state.user_configs[user_id_str]['perplexity_key'] = perplexity_key
    save_configs(state.user_configs)
    
    keyboard = [[InlineKeyboardButton('API menu', callback_data='api')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Perplexity API Key saved.\n\n{perplexity_key[:30]}...\n\nDone. AI is now available.",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    
    return ConversationHandler.END

async def check_api_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check the OKX API connection."""
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    config = state.user_configs.get(str(user_id), {})
    
    if not config.get('api_key'):
        await query.answer('Add the API Key first.', show_alert=True)
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
        await query.answer('OKX API connected.', show_alert=True)
    except Exception as e:
        await query.answer(f'Error: {str(e)[:50]}', show_alert=True)

# ============================================================================
# AI ASSISTANT
# ============================================================================

async def show_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the AI assistant menu."""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton('What to buy?', callback_data='ai_buy'), InlineKeyboardButton('Indicators', callback_data='ai_indicators')],
        [InlineKeyboardButton('Strategy', callback_data='ai_strategy'), InlineKeyboardButton('Risk', callback_data='ai_risk')],
        [InlineKeyboardButton('Main menu', callback_data='back')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = """AI ASSISTANT

Ask Perplexity:"""
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

async def ai_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle AI assistant questions."""
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    questions = {
        'ai_buy': "Which top 5 crypto coins are the best to buy right now for short-term trading on the 1-hour timeframe? Keep it brief and explain why.",
        'ai_indicators': "Explain in one page what RSI, MACD, and Moving Averages (MA) are, and how to use them together in crypto trading.",
        'ai_strategy': "Describe the best crypto trading strategies for a beginner on the 1h timeframe. Give 3-4 specific tips.",
        'ai_risk': "How should risk be managed correctly in crypto trading? Give specific advice about stop loss and position sizing."
    }
    
    question = questions.get(query.data)
    if not question:
        return
    
    await query.edit_message_text('AI is thinking...', parse_mode=ParseMode.HTML)
    
    response = await ask_perplexity(question, user_id)
    
    keyboard = [
        [InlineKeyboardButton('Another question', callback_data='ai')],
        [InlineKeyboardButton('Main menu', callback_data='back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = f"""AI RESPONSE:

{response}
"""
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

# ============================================================================
# HELP
# ============================================================================

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the help screen."""
    query = update.callback_query
    await query.answer()
    
    message = """HELP

Analysis
Select pairs to receive technical analysis and AI insights

Balance
View your USDT balance and all coins on OKX

Signals
Automatic BUY / SELL notifications

Timeframe
Choose the analysis interval (1m, 5m, 15m, 1h, 4h, 1d)

API
Add your OKX and Perplexity keys

AI
Ask questions to the Perplexity assistant

Signals:
BUY - Buy
SELL - Sell
HOLD - Wait

All data is stored in user_configs.json"""
    
    keyboard = [[InlineKeyboardButton('Main menu', callback_data='back')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

# ============================================================================
# NAVIGATION
# ============================================================================

async def back_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return to the main menu."""
    query = update.callback_query
    await query.answer()
    await start(update, context)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main callback button handler."""
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
    """Error handler."""
    logger.error(f'Error: {context.error}')

# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """Start the bot."""
    TOKEN = input('TELEGRAM_BOT_TOKEN: ').strip()
    
    logger.info('='*70)
    logger.info('COPY TRADING BOT PRO - FINAL RELEASE')
    logger.info('Analysis + Perplexity + Balance + Signals')
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
    
    logger.info('Bot started.')
    logger.info('Use /start in Telegram to begin.')
    logger.info(f'Data is stored in {CONFIG_FILE}')
    
    app.run_polling()

if __name__ == '__main__':
    main()
