"""
trader_scanner.py - сканирование топ-трейдеров на OKX
"""

import ccxt
import asyncio
from loguru import logger
from config import (
    OKX_API_KEY, OKX_SECRET_KEY, OKX_PASSPHRASE,
    MIN_TRADER_ROI, MIN_TRADER_DAYS, MAX_TRADERS
)


class TraderScanner:
    def __init__(self):
        self.exchange = ccxt.okx({
            'apiKey': OKX_API_KEY,
            'secret': OKX_SECRET_KEY,
            'password': OKX_PASSPHRASE,
            'enableRateLimit': True,
        })
        self.top_traders = []
    
    async def scan_traders(self):
        """Сканирование топ-трейдеров на OKX"""
        try:
            logger.info("🔍 Scanning top traders on OKX...")
            
            # Пытаемся получить leaderboard через публичный API
            # Примечание: это симуляция, реальный API может быть другим
            response = await self._fetch_leaderboard()
            
            self.top_traders = self._filter_traders(response)
            
            logger.info(f"✅ Found {len(self.top_traders)} qualified traders")
            
            for i, trader in enumerate(self.top_traders[:5], 1):
                logger.info(
                    f"  {i}. {trader['name']} - ROI: {trader['roi']}%, "
                    f"Trades: {trader['total_trades']}, Days: {trader['days']}"
                )
            
            return self.top_traders
        
        except Exception as e:
            logger.error(f"❌ Error scanning traders: {e}")
            return []
    
    async def _fetch_leaderboard(self):
        """Получение leaderboard'а с OKX"""
        try:
            # Это упрощённая версия. Реальный API может быть через REST
            # Используем публичный API для демонстрации
            
            # ПРИМЕЧАНИЕ: OKX имеет публичный эндпоинт для leaderboard
            # Но он может быть изменён. Проверь актуальную документацию:
            # https://www.okx.com/api/v5/public/leaderboard
            
            # Для целей демонстрации возвращаем моковые данные
            mock_traders = [
                {
                    'uid': 'trader_001',
                    'name': 'CryptoMaster',
                    'roi': 245.5,
                    'total_trades': 156,
                    'days': 120,
                    'win_rate': 0.68
                },
                {
                    'uid': 'trader_002',
                    'name': 'BitcoinGuy',
                    'roi': 189.3,
                    'total_trades': 89,
                    'days': 95,
                    'win_rate': 0.72
                },
                {
                    'uid': 'trader_003',
                    'name': 'EthEnthusiast',
                    'roi': 156.7,
                    'total_trades': 203,
                    'days': 140,
                    'win_rate': 0.65
                },
                {
                    'uid': 'trader_004',
                    'name': 'SolanaSniper',
                    'roi': 324.2,
                    'total_trades': 412,
                    'days': 100,
                    'win_rate': 0.61
                },
                {
                    'uid': 'trader_005',
                    'name': 'RippleRider',
                    'roi': 112.5,
                    'total_trades': 67,
                    'days': 110,
                    'win_rate': 0.55
                }
            ]
            
            return mock_traders
        
        except Exception as e:
            logger.error(f"❌ Error fetching leaderboard: {e}")
            return []
    
    def _filter_traders(self, traders):
        """Фильтрация трейдеров по критериям"""
        filtered = []
        
        for trader in traders:
            # Проверяем ROI
            if trader.get('roi', 0) < MIN_TRADER_ROI:
                continue
            
            # Проверяем количество дней активности
            if trader.get('days', 0) < MIN_TRADER_DAYS:
                continue
            
            filtered.append({
                'trader_id': trader.get('uid'),
                'name': trader.get('name'),
                'roi': trader.get('roi'),
                'total_trades': trader.get('total_trades'),
                'days': trader.get('days'),
                'win_rate': trader.get('win_rate', 0.5)
            })
        
        # Сортируем по ROI и берём топ N
        filtered.sort(key=lambda x: x['roi'], reverse=True)
        return filtered[:MAX_TRADERS]
    
    def get_trader_by_id(self, trader_id):
        """Получить трейдера по ID"""
        for trader in self.top_traders:
            if trader['trader_id'] == trader_id:
                return trader
        return None
    
    def get_all_traders(self):
        """Получить всех отслеживаемых трейдеров"""
        return self.top_traders


async def main():
    """Тестирование"""
    scanner = TraderScanner()
    traders = await scanner.scan_traders()
    
    print("\n" + "="*60)
    print("📊 TOP TRADERS FOR COPY TRADING")
    print("="*60)
    
    for i, trader in enumerate(traders, 1):
        print(f"\n{i}. {trader['name']}")
        print(f"   ROI: {trader['roi']}%")
        print(f"   Total Trades: {trader['total_trades']}")
        print(f"   Days Active: {trader['days']}")
        print(f"   Win Rate: {trader['win_rate']*100:.1f}%")


if __name__ == '__main__':
    asyncio.run(main())
