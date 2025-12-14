"""
database.py - работа с SQLite базой для логирования сделок
"""

import sqlite3
import os
from datetime import datetime
from loguru import logger
from config import DB_PATH

# Создаём папку для БД если её нет
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

class TradeDatabase:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Инициализация базы данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Таблица скопированных сделок
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                trader_id TEXT NOT NULL,
                trader_name TEXT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                entry_price REAL,
                entry_amount REAL,
                copy_amount REAL,
                stop_loss REAL,
                status TEXT DEFAULT 'open',
                exit_price REAL,
                profit_loss REAL,
                profit_percent REAL,
                exit_time DATETIME,
                notes TEXT
            )
        ''')
        
        # Таблица для отслеживания трейдеров
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS traders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trader_id TEXT UNIQUE NOT NULL,
                trader_name TEXT,
                roi REAL,
                total_trades INTEGER,
                active_positions INTEGER,
                last_checked DATETIME,
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        
        # Таблица для статистики бота
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                total_trades_copied INTEGER,
                successful_trades INTEGER,
                failed_trades INTEGER,
                total_pnl REAL,
                balance REAL,
                drawdown_percent REAL
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("✅ Database initialized successfully")
    
    def log_trade(self, trade_data):
        """Логирование новой сделки"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO trades (
                trader_id, trader_name, symbol, side, entry_price,
                entry_amount, copy_amount, stop_loss, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade_data.get('trader_id'),
            trade_data.get('trader_name'),
            trade_data.get('symbol'),
            trade_data.get('side'),
            trade_data.get('entry_price'),
            trade_data.get('entry_amount'),
            trade_data.get('copy_amount'),
            trade_data.get('stop_loss'),
            'open'
        ))
        
        conn.commit()
        trade_id = cursor.lastrowid
        conn.close()
        
        logger.info(f"📝 Trade logged: {trade_data['symbol']} {trade_data['side']} (ID: {trade_id})")
        return trade_id
    
    def close_trade(self, trade_id, exit_price, profit_loss, profit_percent):
        """Закрытие сделки с результатом"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE trades 
            SET status = ?, exit_price = ?, profit_loss = ?, profit_percent = ?, exit_time = ?
            WHERE id = ?
        ''', ('closed', exit_price, profit_loss, profit_percent, datetime.now(), trade_id))
        
        conn.commit()
        conn.close()
        
        emoji = '✅' if profit_loss > 0 else '❌'
        logger.info(f"{emoji} Trade closed (ID: {trade_id}): {profit_percent:.2f}%")
    
    def add_trader(self, trader_data):
        """Добавление трейдера в отслеживание"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO traders (
                    trader_id, trader_name, roi, total_trades, active_positions, last_checked, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                trader_data.get('trader_id'),
                trader_data.get('trader_name'),
                trader_data.get('roi'),
                trader_data.get('total_trades'),
                trader_data.get('active_positions', 0),
                datetime.now(),
                1
            ))
            
            conn.commit()
            logger.info(f"👤 Trader added: {trader_data['trader_name']} (ROI: {trader_data['roi']}%)")
        except Exception as e:
            logger.error(f"❌ Error adding trader: {e}")
        finally:
            conn.close()
    
    def get_all_open_trades(self):
        """Получить все открытые сделки"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM trades WHERE status = ?', ('open',))
        trades = cursor.fetchall()
        conn.close()
        
        return trades
    
    def get_stats(self):
        """Получить статистику бота"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN profit_loss < 0 THEN 1 ELSE 0 END) as losses,
                AVG(profit_percent) as avg_profit_percent,
                SUM(profit_loss) as total_pnl
            FROM trades WHERE status = ?
        ''', ('closed',))
        
        stats = cursor.fetchone()
        conn.close()
        
        return {
            'total_trades': stats[0] or 0,
            'wins': stats[1] or 0,
            'losses': stats[2] or 0,
            'avg_profit': stats[3] or 0,
            'total_pnl': stats[4] or 0
        }


if __name__ == '__main__':
    db = TradeDatabase()
    
    # Тестирование
    test_trade = {
        'trader_id': 'trader_123',
        'trader_name': 'TopTrader',
        'symbol': 'BTC/USDT',
        'side': 'buy',
        'entry_price': 97500,
        'entry_amount': 1.0,
        'copy_amount': 0.05,
        'stop_loss': 92625
    }
    
    trade_id = db.log_trade(test_trade)
    print(f"✅ Test trade logged with ID: {trade_id}")
