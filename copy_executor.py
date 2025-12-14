"""
copy_executor.py - исполнение копи-ордеров
"""

import ccxt
import asyncio
from loguru import logger
from config import (
    OKX_API_KEY, OKX_SECRET_KEY, OKX_PASSPHRASE,
    COPY_RATIO, ALLOWED_PAIRS, EXCLUDED_PAIRS, PAPER_TRADING
)
from database import TradeDatabase


class CopyExecutor:
    def __init__(self):
        self.exchange = ccxt.okx({
            'apiKey': OKX_API_KEY,
            'secret': OKX_SECRET_KEY,
            'password': OKX_PASSPHRASE,
            'enableRateLimit': True,
        })
        self.db = TradeDatabase()
        self.paper_trading = PAPER_TRADING
        self.active_trades = {}
    
    async def execute_copy_order(self, trader_id, trader_name, symbol, side, amount, price):
        """Исполнение копи-ордера"""
        try:
            # Проверяем фильтры пар
            if not self._is_valid_pair(symbol):
                logger.warning(f"⚠️  Pair {symbol} is excluded from trading")
                return None
            
            # Вычисляем объём для копирования
            copy_amount = amount * COPY_RATIO
            
            logger.info(
                f"📋 Executing copy order: {symbol} {side.upper()} "
                f"(Trader: {trader_name}, Amount: {copy_amount}, Price: {price})"
            )
            
            if self.paper_trading:
                # PAPER TRADING - только логирование, без реальных денег
                order_id = f"PAPER_{symbol}_{side}_{int(asyncio.get_event_loop().time())}"
                
                trade_data = {
                    'trader_id': trader_id,
                    'trader_name': trader_name,
                    'symbol': symbol,
                    'side': side,
                    'entry_price': price,
                    'entry_amount': amount,
                    'copy_amount': copy_amount,
                    'stop_loss': self._calculate_stop_loss(side, price)
                }
                
                trade_id = self.db.log_trade(trade_data)
                self.active_trades[order_id] = trade_id
                
                logger.info(f"✅ PAPER TRADE: Order ID {order_id} (DB ID: {trade_id})")
                return order_id
            
            else:
                # REAL TRADING - исполнение настоящих ордеров
                if side.lower() == 'buy':
                    order = self.exchange.create_market_buy_order(symbol, copy_amount)
                else:
                    order = self.exchange.create_market_sell_order(symbol, copy_amount)
                
                order_id = order.get('id')
                
                # Логируем в БД
                trade_data = {
                    'trader_id': trader_id,
                    'trader_name': trader_name,
                    'symbol': symbol,
                    'side': side,
                    'entry_price': price,
                    'entry_amount': amount,
                    'copy_amount': copy_amount,
                    'stop_loss': self._calculate_stop_loss(side, price)
                }
                
                trade_id = self.db.log_trade(trade_data)
                self.active_trades[order_id] = trade_id
                
                logger.info(f"✅ REAL ORDER: {symbol} {side} {copy_amount} (Order ID: {order_id})")
                return order_id
        
        except Exception as e:
            logger.error(f"❌ Error executing order: {e}")
            return None
    
    def _is_valid_pair(self, symbol):
        """Проверка валидности пары"""
        if symbol in EXCLUDED_PAIRS:
            return False
        
        if ALLOWED_PAIRS and symbol not in ALLOWED_PAIRS:
            return False
        
        return True
    
    def _calculate_stop_loss(self, side, entry_price):
        """Расчёт стоп-лосса"""
        from config import STOP_LOSS_PERCENT
        
        if side.lower() == 'buy':
            # Для лонга стоп-лосс ниже
            return entry_price * (1 - STOP_LOSS_PERCENT / 100)
        else:
            # Для шорта стоп-лосс выше
            return entry_price * (1 + STOP_LOSS_PERCENT / 100)
    
    async def get_balance(self):
        """Получить баланс аккаунта"""
        try:
            balance = self.exchange.fetch_balance()
            return balance.get('total', {})
        except Exception as e:
            logger.error(f"❌ Error fetching balance: {e}")
            return {}
    
    async def get_order_status(self, order_id):
        """Получить статус ордера"""
        try:
            # Примечание: нужно знать символ для получения статуса
            order = self.exchange.fetch_order(order_id)
            return order
        except Exception as e:
            logger.error(f"❌ Error fetching order status: {e}")
            return None


async def main():
    """Тестирование"""
    executor = CopyExecutor()
    
    print("\n" + "="*60)
    print("📊 COPY EXECUTOR TEST")
    print("="*60)
    
    # Тест: копируем позицию топ-трейдера
    order_id = await executor.execute_copy_order(
        trader_id='trader_001',
        trader_name='CryptoMaster',
        symbol='BTC/USDT',
        side='buy',
        amount=0.1,  # Оригинальная позиция: 0.1 BTC
        price=97500
    )
    
    print(f"\n✅ Order created: {order_id}")
    
    # Получаем баланс
    balance = await executor.get_balance()
    print(f"\n💰 Account Balance: {balance}")


if __name__ == '__main__':
    asyncio.run(main())
