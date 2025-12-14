"""
main.py - главный файл для запуска Copy Trading Bot
"""

import asyncio
import sys
import os
from datetime import datetime
from loguru import logger
from config import (
    CHECK_INTERVAL, LOG_DIR, LOG_LEVEL, PAPER_TRADING, 
    DEBUG_MODE, MIN_BALANCE, MAX_DRAWDOWN
)
from trader_scanner import TraderScanner
from copy_executor import CopyExecutor
from telegram_notifier import TelegramNotifier
from database import TradeDatabase


# ============================================================================
# ЛОГИРОВАНИЕ
# ============================================================================

os.makedirs(LOG_DIR, exist_ok=True)

logger.remove()  # Удаляем дефолтный хендлер
logger.add(
    sys.stdout,
    format="<level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level=LOG_LEVEL
)
logger.add(
    os.path.join(LOG_DIR, "bot_{time:YYYY-MM-DD}.log"),
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
    level="DEBUG",
    rotation="00:00"
)


# ============================================================================
# ГЛАВНЫЙ БОТ
# ============================================================================

class CopyTradingBot:
    def __init__(self):
        self.scanner = TraderScanner()
        self.executor = CopyExecutor()
        self.notifier = TelegramNotifier()
        self.db = TradeDatabase()
        self.is_running = False
        self.traders = []
        self.start_time = datetime.now()
    
    async def start(self):
        """Запуск бота"""
        logger.info("🚀 Copy Trading Bot Starting...")
        logger.info(f"📝 Paper Trading: {PAPER_TRADING}")
        logger.info(f"🔍 Scanning interval: {CHECK_INTERVAL}s")
        
        self.is_running = True
        
        try:
            # Начальное сканирование трейдеров
            await self.refresh_traders()
            
            # Главный цикл
            while self.is_running:
                try:
                    await self.monitor_traders()
                    await asyncio.sleep(CHECK_INTERVAL)
                
                except KeyboardInterrupt:
                    logger.info("⏹️  Bot stopped by user")
                    break
                except Exception as e:
                    logger.error(f"❌ Error in main loop: {e}")
                    await self.notifier.notify_error(str(e))
                    await asyncio.sleep(CHECK_INTERVAL)
        
        finally:
            await self.shutdown()
    
    async def refresh_traders(self):
        """Обновление списка топ-трейдеров"""
        logger.info("🔄 Refreshing trader list...")
        
        self.traders = await self.scanner.scan_traders()
        
        # Добавляем трейдеров в БД
        for trader in self.traders:
            self.db.add_trader(trader)
        
        logger.info(f"✅ Now tracking {len(self.traders)} traders")
    
    async def monitor_traders(self):
        """Мониторинг позиций трейдеров"""
        for trader in self.traders:
            try:
                # Получаем открытые позиции трейдера (симулируем)
                positions = await self._get_trader_positions(trader)
                
                for pos in positions:
                    # Проверяем, не копировали ли уже эту позицию
                    if not self._is_position_copied(pos):
                        # Копируем позицию
                        await self._copy_position(trader, pos)
            
            except Exception as e:
                logger.error(f"❌ Error monitoring trader {trader['name']}: {e}")
    
    async def _get_trader_positions(self, trader):
        """Получить позиции трейдера (симуляция)"""
        # В реальности это должно быть получено через API OKX
        # Сейчас это симуляция для демонстрации
        
        positions = [
            {
                'symbol': 'BTC/USDT',
                'side': 'buy',
                'amount': 0.1,
                'price': 97500,
                'timestamp': datetime.now()
            },
            {
                'symbol': 'ETH/USDT',
                'side': 'buy',
                'amount': 1.0,
                'price': 3150,
                'timestamp': datetime.now()
            }
        ]
        
        return positions
    
    def _is_position_copied(self, position):
        """Проверка, была ли позиция уже скопирована"""
        # Получаем открытые сделки из БД
        # Если позиция уже скопирована, возвращаем True
        return False  # Для демонстрации всегда копируем
    
    async def _copy_position(self, trader, position):
        """Копирование позиции"""
        logger.info(
            f"📋 Copying position: {trader['name']} - {position['symbol']} "
            f"{position['side']} {position['amount']}"
        )
        
        # Исполняем копи-ордер
        order_id = await self.executor.execute_copy_order(
            trader_id=trader['trader_id'],
            trader_name=trader['name'],
            symbol=position['symbol'],
            side=position['side'],
            amount=position['amount'],
            price=position['price']
        )
        
        if order_id:
            # Отправляем уведомление
            await self.notifier.notify_trade_opened(
                trader_name=trader['name'],
                symbol=position['symbol'],
                side=position['side'],
                amount=position['amount'] * 0.05,  # COPY_RATIO
                price=position['price']
            )
    
    async def get_stats(self):
        """Получить статистику бота"""
        stats = self.db.get_stats()
        
        uptime = datetime.now() - self.start_time
        uptime_str = f"{uptime.days}d {uptime.seconds//3600}h {(uptime.seconds//60)%60}m"
        
        return {
            **stats,
            'uptime': uptime_str,
            'traders_tracked': len(self.traders),
            'paper_trading': PAPER_TRADING
        }
    
    async def print_stats(self):
        """Вывести статистику"""
        stats = await self.get_stats()
        
        logger.info("\n" + "="*60)
        logger.info("📊 BOT STATISTICS")
        logger.info("="*60)
        logger.info(f"  Uptime: {stats['uptime']}")
        logger.info(f"  Traders Tracked: {stats['traders_tracked']}")
        logger.info(f"  Total Trades: {stats['total_trades']}")
        logger.info(f"  Wins: {stats['wins']} | Losses: {stats['losses']}")
        logger.info(f"  Avg Profit: {stats['avg_profit']:.2f}%")
        logger.info(f"  Total P&L: ${stats['total_pnl']:.2f}")
        logger.info(f"  Paper Trading: {stats['paper_trading']}")
        logger.info("="*60 + "\n")
    
    async def shutdown(self):
        """Остановка бота"""
        logger.info("⏹️  Shutting down bot...")
        self.is_running = False
        
        await self.print_stats()
        
        logger.info("✅ Bot stopped")


# ============================================================================
# ТОЧКА ВХОДА
# ============================================================================

async def main():
    """Главная функция"""
    
    # Проверка конфига
    from config import OKX_API_KEY
    if OKX_API_KEY == 'YOUR_API_KEY_HERE':
        logger.warning("⚠️  WARNING: OKX API keys not configured!")
        logger.warning("   Please set environment variables or edit .env file:")
        logger.warning("   OKX_API_KEY, OKX_SECRET_KEY, OKX_PASSPHRASE")
        logger.warning("\n   Running in PAPER TRADING mode (no real trades)")
    
    bot = CopyTradingBot()
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    # Запуск
    print("""
╔══════════════════════════════════════════════════════════════╗
║         🤖 COPY TRADING BOT FOR OKX 🤖                      ║
║                                                              ║
║  Copy the best traders and earn passive income              ║
║  Disclaimer: This is for educational purposes only          ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    asyncio.run(main())
