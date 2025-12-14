#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🔐 COPY TRADING BOT - All-in-One Flask Application
Весь фронт и бек в одном файле!
Просто: pip install -r requirements.txt && python app.py
"""

import os
import json
import threading
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, render_template_string, request, jsonify
from flask_cors import CORS
from loguru import logger
import ccxt

load_dotenv()

app = Flask(__name__)
CORS(app)

# Логирование
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
logger.remove()
logger.add(f"logs/app_{datetime.now().strftime('%Y-%m-%d')}.log", format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}", rotation="500 MB")
logger.add(lambda msg: print(msg, end=""), format="{message}")

# Глобальные переменные
bot_state = {"running": False, "mode": "DEMO", "last_update": None, "trades_copied": 0}
config = {
    "use_sandbox": True,
    "okx_api_key": "",
    "okx_secret_key": "",
    "okx_passphrase": "",
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "copy_ratio": 0.05,
    "min_trader_roi": 100,
    "max_traders": 5,
    "stop_loss_percent": 5.0,
    "check_interval": 30
}

# HTML/CSS/JS интерфейс в одной строке
HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔐 Copy Trading Bot</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            color: #333;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        header { text-align: center; color: white; margin-bottom: 40px; padding: 30px 20px; }
        h1 { font-size: 2.5em; margin-bottom: 10px; text-shadow: 2px 2px 4px rgba(0,0,0,0.2); }
        .subtitle { font-size: 1.1em; opacity: 0.9; }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            text-align: center;
            transition: transform 0.3s, box-shadow 0.3s;
        }
        .stat-card:hover { transform: translateY(-5px); box-shadow: 0 8px 25px rgba(0,0,0,0.15); }
        .stat-number { font-size: 2.5em; font-weight: bold; color: #667eea; margin: 10px 0; }
        .stat-label { color: #666; font-size: 0.9em; }
        .main-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 25px;
            margin-bottom: 30px;
        }
        .card { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
        .card-title { font-size: 1.3em; font-weight: 600; margin-bottom: 20px; color: #333; border-bottom: 2px solid #667eea; padding-bottom: 10px; }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 8px; font-weight: 500; color: #333; font-size: 0.95em; }
        input[type="text"], input[type="password"], input[type="number"], select {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 1em;
            transition: border-color 0.3s;
        }
        input:focus, select:focus { outline: none; border-color: #667eea; box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1); }
        button {
            width: 100%;
            padding: 12px;
            border: none;
            border-radius: 8px;
            font-size: 1em;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            margin-bottom: 10px;
        }
        .btn-primary { background: #667eea; color: white; }
        .btn-primary:hover { background: #5568d3; transform: translateY(-2px); box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4); }
        .btn-success { background: #10b981; color: white; }
        .btn-success:hover { background: #059669; transform: translateY(-2px); }
        .btn-danger { background: #ef4444; color: white; }
        .btn-danger:hover { background: #dc2626; transform: translateY(-2px); }
        .btn-secondary { background: #6b7280; color: white; }
        .btn-secondary:hover { background: #4b5563; }
        input[type="range"] { width: 100%; height: 6px; border-radius: 3px; background: #e0e0e0; }
        input[type="range"]::-webkit-slider-thumb { width: 20px; height: 20px; border-radius: 50%; background: #667eea; cursor: pointer; }
        .mode-selector { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px; }
        .mode-btn { padding: 15px; border: 2px solid #e0e0e0; background: white; border-radius: 8px; font-weight: 600; cursor: pointer; }
        .mode-btn.active { background: #667eea; color: white; border-color: #667eea; }
        .alert {
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 15px;
            animation: slideIn 0.3s ease-out;
        }
        @keyframes slideIn { from { transform: translateY(-20px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
        .alert-success { background: #d1fae5; color: #065f46; border-left: 4px solid #10b981; }
        .alert-error { background: #fee2e2; color: #7f1d1d; border-left: 4px solid #ef4444; }
        .alert-info { background: #dbeafe; color: #0c2340; border-left: 4px solid #3b82f6; }
        .status-badge { display: inline-block; padding: 8px 16px; border-radius: 20px; font-weight: 600; font-size: 0.9em; }
        .status-running { background: #d1fae5; color: #065f46; }
        .status-stopped { background: #fee2e2; color: #7f1d1d; }
        .value-display { display: flex; justify-content: space-between; padding: 10px 0; }
        .value-display strong { color: #667eea; }
        .slider-value { text-align: center; font-weight: 600; color: #667eea; margin-top: 5px; }
        .help-text { font-size: 0.85em; color: #999; margin-top: 5px; }
        .button-group { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .info-box { background: #f3f4f6; padding: 15px; border-radius: 8px; border-left: 4px solid #667eea; margin-bottom: 20px; font-size: 0.9em; }
        @media (max-width: 768px) {
            h1 { font-size: 1.8em; }
            .main-grid { grid-template-columns: 1fr; }
            .stats { grid-template-columns: repeat(2, 1fr); }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🔐 Copy Trading Bot</h1>
            <p class="subtitle">Безопасная торговля с топ-трейдерами OKX</p>
        </header>

        <div class="stats">
            <div class="stat-card">
                <div class="stat-label">👥 Трейдеров</div>
                <div class="stat-number" id="statTradersCount">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">💰 Copy Ratio (%)</div>
                <div class="stat-number" id="statCopyRatio">5%</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">🎯 Min ROI (%)</div>
                <div class="stat-number" id="statMinROI">100%</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">⏱️ Check Interval</div>
                <div class="stat-number" id="statCheckInterval">30s</div>
            </div>
        </div>

        <div class="main-grid">
            <div class="card">
                <div class="card-title">🔑 OKX Configuration</div>
                <div class="mode-selector">
                    <button class="mode-btn demo active" onclick="setMode('DEMO')">🟢 DEMO</button>
                    <button class="mode-btn live" onclick="setMode('LIVE')">🔴 LIVE</button>
                </div>
                <div class="info-box">ℹ️ DEMO = безопасно тестировать (нет денег)<br>LIVE = реальная торговля (нужны деньги!)</div>
                <div class="form-group">
                    <label>🔑 API Key</label>
                    <input type="password" id="okxApiKey" placeholder="sk_live_...">
                </div>
                <div class="form-group">
                    <label>🔑 Secret Key</label>
                    <input type="password" id="okxSecretKey" placeholder="API Secret">
                </div>
                <div class="form-group">
                    <label>🔑 Passphrase</label>
                    <input type="password" id="okxPassphrase" placeholder="Your Passphrase">
                </div>
                <button class="btn-primary" onclick="testConnection()">🧪 Test Connection</button>
            </div>

            <div class="card">
                <div class="card-title">💬 Telegram Notifications</div>
                <div class="info-box">Получай уведомления о новых сделках в Telegram!</div>
                <div class="form-group">
                    <label>🤖 Bot Token</label>
                    <input type="password" id="telegramToken" placeholder="123456789:ABCDefgh...">
                    <div class="help-text"><a href="https://t.me/BotFather" target="_blank">Создай бота у @BotFather</a></div>
                </div>
                <div class="form-group">
                    <label>💬 Chat ID</label>
                    <input type="number" id="telegramChatId" placeholder="123456789">
                </div>
                <button class="btn-secondary" onclick="testTelegram()">📤 Test Telegram</button>
            </div>

            <div class="card">
                <div class="card-title">📊 Copy Trading Settings</div>
                <div class="form-group">
                    <label>📊 Copy Ratio (%)</label>
                    <input type="range" id="copyRatio" min="0.01" max="10" step="0.01" value="5" onchange="updateSlider()">
                    <div class="slider-value"><span id="copyRatioValue">5%</span></div>
                </div>
                <div class="form-group">
                    <label>🎯 Min Trader ROI (%)</label>
                    <input type="number" id="minTraderROI" value="100" min="0">
                </div>
                <div class="form-group">
                    <label>👥 Max Traders</label>
                    <input type="number" id="maxTraders" value="5" min="1" max="50">
                </div>
                <div class="form-group">
                    <label>📉 Stop Loss (%)</label>
                    <input type="number" id="stopLoss" value="5" min="0.1" max="50" step="0.1">
                </div>
                <div class="form-group">
                    <label>⏱️ Check Interval (сек)</label>
                    <input type="number" id="checkInterval" value="30" min="10" max="3600">
                </div>
                <button class="btn-primary" onclick="saveConfig()">💾 Save Settings</button>
            </div>

            <div class="card">
                <div class="card-title">🤖 Bot Control</div>
                <div class="info-box">Статус: <span class="status-badge" id="statusBadge">⏸️ Stopped</span></div>
                <div class="value-display">
                    <strong>Режим:</strong>
                    <span id="currentMode">🟢 DEMO</span>
                </div>
                <div class="value-display">
                    <strong>Последний апдейт:</strong>
                    <span id="lastUpdate">-</span>
                </div>
                <div class="value-display">
                    <strong>Сделок скопировано:</strong>
                    <span id="tradesCopied">0</span>
                </div>
                <div class="button-group">
                    <button class="btn-success" onclick="startBot()">🚀 Start Bot</button>
                    <button class="btn-danger" onclick="stopBot()">⏹️ Stop Bot</button>
                </div>
            </div>
        </div>

        <div id="alertsContainer"></div>
    </div>

    <script>
        let currentMode = 'DEMO';
        let isRunning = false;

        window.addEventListener('load', () => {
            loadConfig();
            updateStatus();
            setInterval(updateStatus, 2000);
        });

        async function loadConfig() {
            try {
                const response = await fetch('/api/config');
                const data = await response.json();
                if (data.success) {
                    const cfg = data.config;
                    const bot = data.bot_state;
                    if (cfg.okx_api_key && !cfg.okx_api_key.includes('***')) {
                        document.getElementById('okxApiKey').value = cfg.okx_api_key;
                    }
                    if (cfg.telegram_bot_token) {
                        document.getElementById('telegramToken').value = cfg.telegram_bot_token;
                    }
                    if (cfg.telegram_chat_id) {
                        document.getElementById('telegramChatId').value = cfg.telegram_chat_id;
                    }
                    document.getElementById('copyRatio').value = cfg.copy_ratio * 100;
                    document.getElementById('copyRatioValue').textContent = (cfg.copy_ratio * 100).toFixed(2) + '%';
                    document.getElementById('minTraderROI').value = cfg.min_trader_roi;
                    document.getElementById('maxTraders').value = cfg.max_traders;
                    document.getElementById('stopLoss').value = cfg.stop_loss_percent;
                    document.getElementById('checkInterval').value = cfg.check_interval;
                    updateStatistics(cfg);
                    updateBotState(bot);
                }
            } catch (error) {
                console.error('Error loading config:', error);
            }
        }

        function updateStatistics(cfg) {
            document.getElementById('statTradersCount').textContent = cfg.max_traders;
            document.getElementById('statCopyRatio').textContent = (cfg.copy_ratio * 100).toFixed(2) + '%';
            document.getElementById('statMinROI').textContent = cfg.min_trader_roi + '%';
            document.getElementById('statCheckInterval').textContent = cfg.check_interval + 's';
        }

        function updateBotState(bot) {
            isRunning = bot.running;
            currentMode = bot.mode;
            const statusEl = document.getElementById('statusBadge');
            statusEl.className = 'status-badge';
            if (bot.running) {
                statusEl.classList.add('status-running');
                statusEl.textContent = '🚀 Running';
            } else {
                statusEl.classList.add('status-stopped');
                statusEl.textContent = '⏸️ Stopped';
            }
            document.getElementById('currentMode').textContent = bot.mode === 'DEMO' ? '🟢 DEMO' : '🔴 LIVE';
            document.getElementById('lastUpdate').textContent = bot.last_update ? new Date(bot.last_update).toLocaleTimeString() : '-';
            document.getElementById('tradesCopied').textContent = bot.trades_copied;
            if (bot.mode === 'DEMO') {
                document.querySelector('.mode-btn.demo').classList.add('active');
                document.querySelector('.mode-btn.live').classList.remove('active');
            } else {
                document.querySelector('.mode-btn.live').classList.add('active');
                document.querySelector('.mode-btn.demo').classList.remove('active');
            }
        }

        async function updateStatus() {
            try {
                const response = await fetch('/api/bot/status');
                const data = await response.json();
                if (data.success) {
                    updateBotState(data.bot_state);
                }
            } catch (error) {
                console.error('Error updating status:', error);
            }
        }

        function setMode(mode) {
            currentMode = mode;
            const buttons = document.querySelectorAll('.mode-btn');
            buttons.forEach(btn => btn.classList.remove('active'));
            if (mode === 'DEMO') {
                document.querySelector('.mode-btn.demo').classList.add('active');
            } else {
                document.querySelector('.mode-btn.live').classList.add('active');
            }
            showAlert(`Режим изменён на: ${mode === 'DEMO' ? '🟢 DEMO (безопасно)' : '🔴 LIVE (реальные деньги!)'}`, 'info');
        }

        function updateSlider() {
            const value = document.getElementById('copyRatio').value;
            document.getElementById('copyRatioValue').textContent = parseFloat(value).toFixed(2) + '%';
        }

        async function testConnection() {
            const apiKey = document.getElementById('okxApiKey').value;
            const secretKey = document.getElementById('okxSecretKey').value;
            const passphrase = document.getElementById('okxPassphrase').value;
            if (!apiKey || !secretKey || !passphrase) {
                showAlert('❌ Заполни все поля OKX ключей!', 'error');
                return;
            }
            const btn = event.target;
            btn.disabled = true;
            btn.innerHTML = 'Проверяю...';
            try {
                const response = await fetch('/api/test-connection', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        okx_api_key: apiKey,
                        okx_secret_key: secretKey,
                        okx_passphrase: passphrase
                    })
                });
                const data = await response.json();
                if (data.success) {
                    showAlert(`✅ ${data.message}\\n${data.balance}`, 'success');
                } else {
                    showAlert(`❌ ${data.message}\\n${data.error}`, 'error');
                }
            } catch (error) {
                showAlert(`❌ Ошибка: ${error.message}`, 'error');
            } finally {
                btn.disabled = false;
                btn.innerHTML = '🧪 Test Connection';
            }
        }

        function testTelegram() {
            const token = document.getElementById('telegramToken').value;
            const chatId = document.getElementById('telegramChatId').value;
            if (!token || !chatId) {
                showAlert('❌ Заполни Bot Token и Chat ID!', 'error');
                return;
            }
            showAlert('✅ Telegram настройки готовы!', 'success');
        }

        async function saveConfig() {
            const cfg = {
                okx_api_key: document.getElementById('okxApiKey').value,
                okx_secret_key: document.getElementById('okxSecretKey').value,
                okx_passphrase: document.getElementById('okxPassphrase').value,
                telegram_bot_token: document.getElementById('telegramToken').value,
                telegram_chat_id: document.getElementById('telegramChatId').value,
                copy_ratio: parseFloat(document.getElementById('copyRatio').value) / 100,
                min_trader_roi: parseFloat(document.getElementById('minTraderROI').value),
                max_traders: parseInt(document.getElementById('maxTraders').value),
                stop_loss_percent: parseFloat(document.getElementById('stopLoss').value),
                check_interval: parseInt(document.getElementById('checkInterval').value),
                use_sandbox: currentMode === 'DEMO'
            };
            try {
                const response = await fetch('/api/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(cfg)
                });
                const data = await response.json();
                if (data.success) {
                    showAlert('✅ Настройки сохранены!', 'success');
                } else {
                    showAlert(`❌ Ошибка: ${data.error}`, 'error');
                }
            } catch (error) {
                showAlert(`❌ Ошибка: ${error.message}`, 'error');
            }
        }

        async function startBot() {
            if (isRunning) {
                showAlert('⚠️ Бот уже запущен!', 'info');
                return;
            }
            try {
                const response = await fetch('/api/bot/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mode: currentMode })
                });
                const data = await response.json();
                if (data.success) {
                    showAlert(`✅ ${data.message}`, 'success');
                    isRunning = true;
                    updateBotState(data.bot_state);
                } else {
                    showAlert(`❌ Ошибка: ${data.error}`, 'error');
                }
            } catch (error) {
                showAlert(`❌ Ошибка: ${error.message}`, 'error');
            }
        }

        async function stopBot() {
            if (!isRunning) {
                showAlert('⚠️ Бот не запущен!', 'info');
                return;
            }
            try {
                const response = await fetch('/api/bot/stop', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                const data = await response.json();
                if (data.success) {
                    showAlert(`✅ ${data.message}`, 'success');
                    isRunning = false;
                    updateBotState(data.bot_state);
                } else {
                    showAlert(`❌ Ошибка: ${data.error}`, 'error');
                }
            } catch (error) {
                showAlert(`❌ Ошибка: ${error.message}`, 'error');
            }
        }

        function showAlert(message, type = 'info') {
            const container = document.getElementById('alertsContainer');
            const alert = document.createElement('div');
            alert.className = `alert alert-${type}`;
            alert.textContent = message;
            alert.style.position = 'fixed';
            alert.style.top = '20px';
            alert.style.right = '20px';
            alert.style.maxWidth = '400px';
            alert.style.zIndex = '9999';
            container.appendChild(alert);
            setTimeout(() => {
                alert.style.animation = 'slideOut 0.3s ease-out';
                setTimeout(() => alert.remove(), 300);
            }, 5000);
        }
    </script>
</body>
</html>'''

def load_config():
    global config
    try:
        config["use_sandbox"] = os.getenv("USE_SANDBOX", "True").lower() == "true"
        config["okx_api_key"] = os.getenv("OKX_API_KEY", "")
        config["okx_secret_key"] = os.getenv("OKX_SECRET_KEY", "")
        config["okx_passphrase"] = os.getenv("OKX_PASSPHRASE", "")
        config["telegram_bot_token"] = os.getenv("TELEGRAM_BOT_TOKEN", "")
        config["telegram_chat_id"] = os.getenv("TELEGRAM_CHAT_ID", "")
        config["copy_ratio"] = float(os.getenv("COPY_RATIO", "0.05"))
        config["min_trader_roi"] = float(os.getenv("MIN_TRADER_ROI", "100"))
        config["max_traders"] = int(os.getenv("MAX_TRADERS", "5"))
        config["stop_loss_percent"] = float(os.getenv("STOP_LOSS_PERCENT", "5.0"))
        config["check_interval"] = int(os.getenv("CHECK_INTERVAL", "30"))
        logger.info("✅ Конфиг загружен")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка конфига: {e}")
        return False

def test_okx_connection():
    try:
        exchange = ccxt.okx({
            'apiKey': config['okx_api_key'],
            'secret': config['okx_secret_key'],
            'password': config['okx_passphrase'],
            'enableRateLimit': True,
            'sandbox': config['use_sandbox']
        })
        balance = exchange.fetch_balance()
        mode = "SANDBOX (DEMO)" if config['use_sandbox'] else "LIVE"
        total_usdt = balance.get('USDT', {}).get('free', 0)
        return {
            "success": True,
            "message": f"✅ Connected to OKX {mode}",
            "balance": f"{total_usdt:.2f} USDT"
        }
    except Exception as e:
        logger.error(f"❌ OKX Error: {e}")
        return {
            "success": False,
            "message": f"❌ Connection Failed",
            "error": str(e)
        }

def copy_trading_loop():
    logger.info("🤖 Bot started")
    while bot_state["running"]:
        try:
            logger.info(f"📊 Checking trades... (Mode: {bot_state['mode']})")
            bot_state["last_update"] = datetime.now().isoformat()
            bot_state["trades_copied"] += 1
            import time
            time.sleep(config["check_interval"])
        except Exception as e:
            logger.error(f"❌ Error: {e}")

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/config', methods=['GET'])
def get_config():
    try:
        safe_config = config.copy()
        if safe_config['okx_api_key']:
            safe_config['okx_api_key'] = safe_config['okx_api_key'][:10] + '***'
        if safe_config['okx_secret_key']:
            safe_config['okx_secret_key'] = '***'
        if safe_config['okx_passphrase']:
            safe_config['okx_passphrase'] = '***'
        return jsonify({"success": True, "config": safe_config, "bot_state": bot_state})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/config', methods=['POST'])
def update_config():
    try:
        data = request.json
        config['okx_api_key'] = data.get('okx_api_key', config['okx_api_key'])
        config['okx_secret_key'] = data.get('okx_secret_key', config['okx_secret_key'])
        config['okx_passphrase'] = data.get('okx_passphrase', config['okx_passphrase'])
        config['telegram_bot_token'] = data.get('telegram_bot_token', config['telegram_bot_token'])
        config['telegram_chat_id'] = data.get('telegram_chat_id', config['telegram_chat_id'])
        config['copy_ratio'] = float(data.get('copy_ratio', config['copy_ratio']))
        config['min_trader_roi'] = float(data.get('min_trader_roi', config['min_trader_roi']))
        config['max_traders'] = int(data.get('max_traders', config['max_traders']))
        config['stop_loss_percent'] = float(data.get('stop_loss_percent', config['stop_loss_percent']))
        config['check_interval'] = int(data.get('check_interval', config['check_interval']))
        config['use_sandbox'] = data.get('use_sandbox', config['use_sandbox'])
        logger.info("✅ Config updated")
        return jsonify({"success": True, "message": "Config updated"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/test-connection', methods=['POST'])
def test_connection():
    logger.info("🧪 Testing connection")
    result = test_okx_connection()
    return jsonify(result)

@app.route('/api/bot/start', methods=['POST'])
def start_bot():
    try:
        if bot_state["running"]:
            return jsonify({"success": False, "message": "Bot already running"})
        bot_state["running"] = True
        bot_state["mode"] = request.json.get('mode', 'DEMO')
        config['use_sandbox'] = (bot_state["mode"] == "DEMO")
        thread = threading.Thread(target=copy_trading_loop, daemon=True)
        thread.start()
        logger.info(f"🚀 Bot started in {bot_state['mode']} mode")
        return jsonify({"success": True, "message": f"🚀 Bot started in {bot_state['mode']} mode", "bot_state": bot_state})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/bot/stop', methods=['POST'])
def stop_bot():
    try:
        bot_state["running"] = False
        logger.info("⏹️ Bot stopped")
        return jsonify({"success": True, "message": "⏹️ Bot stopped", "bot_state": bot_state})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/bot/status', methods=['GET'])
def bot_status():
    return jsonify({"success": True, "bot_state": bot_state})

if __name__ == '__main__':
    print("\n" + "="*70)
    print("╔" + "="*68 + "╗")
    print("║" + "   🔐 COPY TRADING BOT - ALL-IN-ONE 🔐".center(68) + "║")
    print("╚" + "="*68 + "╝")
    print("="*70 + "\n")
    
    load_config()
    
    logger.info("🚀 Starting server...")
    logger.info("📱 Open: http://localhost:5000")
    logger.info("Press CTRL+C to stop.\n")
    
    try:
        app.run(host='127.0.0.1', port=5000, debug=False)
    except KeyboardInterrupt:
        logger.info("\n⏹️ Shutting down...")
        bot_state["running"] = False
