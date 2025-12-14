"""
telegram_notifier.py - отправка уведомлений в Telegram
"""

import requests
import asyncio
from loguru import logger
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


class TelegramNotifier:
    def __init__(self):
        self.bot_token = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
    
    async def send_message(self, text, parse_mode='HTML'):
        """Отправить сообщение в Telegram"""
        try:
            if 'YOUR_BOT_TOKEN' in self.bot_token or 'YOUR_CHAT_ID' in self.chat_id:
                logger.warning("⚠️  Telegram not configured, skipping notification")
                return False
            
            url = f"{self.base_url}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': text,
                'parse_mode': parse_mode
            }
            
            response = requests.post(url, json=data)
            
            if response.status_code == 200:
                logger.info("✅ Telegram notification sent")
                return True
            else:
                logger.error(f"❌ Failed to send Telegram notification: {response.text}")
                return False
        
        except Exception as e:
            logger.error(f"❌ Error sending Telegram message: {e}")
            return False
    
    async def notify_trade_opened(self, trader_name, symbol, side, amount, price):
        """Уведомление об открытии сделки"""
        emoji_side = '📈' if side.lower() == 'buy' else '📉'
        
        message = f"""
{emoji_side} <b>Trade Opened!</b>

👤 Trader: <b>{trader_name}</b>
📊 Symbol: <code>{symbol}</code>
📍 Side: <b>{side.upper()}</b>
💰 Amount: <code>{amount}</code>
🎯 Price: <code>${price}</code>

⏰ Time: <i>Now</i>
        """
        
        await self.send_message(message)
    
    async def notify_trade_closed(self, symbol, profit_loss, profit_percent):
        """Уведомление о закрытии сделки"""
        emoji_pnl = '✅' if profit_loss > 0 else '❌'
        
        message = f"""
{emoji_pnl} <b>Trade Closed!</b>

📊 Symbol: <code>{symbol}</code>
💵 P&L: <code>${profit_loss:.2f}</code>
📈 Profit %: <code>{profit_percent:.2f}%</code>
        """
        
        await self.send_message(message)
    
    async def notify_stats(self, total_trades, wins, losses, avg_profit, total_pnl):
        """Уведомление со статистикой"""
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        message = f"""
📊 <b>Bot Statistics</b>

Total Trades: <code>{total_trades}</code>
Wins: <code>{wins}</code> ✅
Losses: <code>{losses}</code> ❌
Win Rate: <code>{win_rate:.1f}%</code>

📈 Avg Profit: <code>{avg_profit:.2f}%</code>
💰 Total P&L: <code>${total_pnl:.2f}</code>
        """
        
        await self.send_message(message)
    
    async def notify_error(self, error_message):
        """Уведомление об ошибке"""
        message = f"""
⚠️ <b>Bot Error</b>

❌ <code>{error_message}</code>

Please check the logs for more details.
        """
        
        await self.send_message(message)


async def main():
    """Тестирование"""
    notifier = TelegramNotifier()
    
    print("\n" + "="*60)
    print("📬 TELEGRAM NOTIFIER TEST")
    print("="*60)
    
    await notifier.notify_trade_opened(
        trader_name='CryptoMaster',
        symbol='BTC/USDT',
        side='buy',
        amount=0.05,
        price=97500
    )
    
    print("✅ Notification sent (check Telegram)")


if __name__ == '__main__':
    asyncio.run(main())
