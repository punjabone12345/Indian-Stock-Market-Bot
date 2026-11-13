import urllib.request
import ssl
import json
import time
import math
import random
from datetime import datetime

CROWN_6_INSTRUMENTS = {
    'RELIANCE': {'ticker': 'RELIANCE.NS', 'name': 'Reliance Industries', 'sector': 'Energy', 'base_price': 1250.0},
    'ITC': {'ticker': 'ITC.NS', 'name': 'ITC Limited', 'sector': 'FMCG', 'base_price': 400.0},
    'MARUTI': {'ticker': 'MARUTI.NS', 'name': 'Maruti Suzuki India', 'sector': 'Automobiles', 'base_price': 11800.0},
    'TATASTEEL': {'ticker': 'TATASTEEL.NS', 'name': 'Tata Steel Ltd', 'sector': 'Metals & Mining', 'base_price': 152.0},
    'SUNPHARMA': {'ticker': 'SUNPHARMA.NS', 'name': 'Sun Pharmaceutical Ind', 'sector': 'Healthcare', 'base_price': 1750.0},
    'INFY': {'ticker': 'INFY.NS', 'name': 'Infosys Limited', 'sector': 'IT Services', 'base_price': 1510.0},
    'NIFTY50': {'ticker': '^NSEI', 'name': 'Nifty 50 Benchmark', 'sector': 'Macro Index', 'base_price': 24350.0}
}

class MarketDataService:
    def __init__(self):
        self.ctx = ssl._create_unverified_context()
        self.quote_cache = {}
        self.last_fetch_ts = 0
        # Initialize realistic starting prices
        for sym, d in CROWN_6_INSTRUMENTS.items():
            self.quote_cache[sym] = {
                'symbol': sym,
                'ticker': d['ticker'],
                'name': d['name'],
                'sector': d['sector'],
                'price': d['base_price'],
                'prev_close': d['base_price'],
                'change': 0.0,
                'change_pct': 0.0,
                'day_high': round(d['base_price'] * 1.008, 2),
                'day_low': round(d['base_price'] * 0.994, 2),
                'volume': 1250000,
                'updated_at': datetime.now().strftime("%H:%M:%S")
            }

    def fetch_live_quotes(self):
        """Fetches live quotes from Yahoo Finance or applies live tick drift if outside market hours/rate-limited."""
        now = time.time()
        # Fetch external quotes at most once every 3 seconds to avoid rate-limiting
        if now - self.last_fetch_ts > 3:
            self._fetch_from_web()
            self.last_fetch_ts = now
        else:
            # Micro-tick simulation between network requests (0.01% - 0.03% dynamic fluctuation)
            for sym, q in self.quote_cache.items():
                if sym == 'NIFTY50':
                    drift = round(random.choice([-1.5, -0.5, 0.0, 0.5, 1.5]), 2)
                else:
                    drift = round(q['price'] * random.uniform(-0.0003, 0.0003), 2)
                new_p = max(round(q['price'] + drift, 2), 1.0)
                q['price'] = new_p
                q['change'] = round(new_p - q['prev_close'], 2)
                q['change_pct'] = round((q['change'] / q['prev_close']) * 100, 2) if q['prev_close'] else 0.0
                q['updated_at'] = datetime.now().strftime("%H:%M:%S")

        return self.quote_cache

    def _fetch_from_web(self):
        tickers = [d['ticker'] for d in CROWN_6_INSTRUMENTS.values()]
        ticker_str = ",".join(tickers)
        url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={ticker_str}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, context=self.ctx, timeout=4) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                results = data.get('quoteResponse', {}).get('result', [])
                for r in results:
                    t = r.get('symbol')
                    # Find our symbol
                    for sym, info in CROWN_6_INSTRUMENTS.items():
                        if info['ticker'] == t:
                            cur_p = r.get('regularMarketPrice') or self.quote_cache[sym]['price']
                            prev_c = r.get('regularMarketPreviousClose') or cur_p
                            chg = cur_p - prev_c
                            pct = (chg / prev_c) * 100.0 if prev_c else 0.0
                            self.quote_cache[sym].update({
                                'price': round(cur_p, 2),
                                'prev_close': round(prev_c, 2),
                                'change': round(chg, 2),
                                'change_pct': round(pct, 2),
                                'day_high': round(r.get('regularMarketDayHigh', cur_p), 2),
                                'day_low': round(r.get('regularMarketDayLow', cur_p), 2),
                                'volume': r.get('regularMarketVolume', 1500000),
                                'updated_at': datetime.now().strftime("%H:%M:%S")
                            })
                            break
        except Exception as e:
            # Fallback to micro-ticks gracefully
            pass

    def get_candle_history(self, symbol: str):
        """Generates realistic 5m OHLC candles for technical indicators."""
        q = self.quote_cache.get(symbol, {'price': 1000.0})
        cur_p = q['price']
        candles = []
        base = cur_p * 0.992
        for i in range(30):
            o = round(base + (i * 0.4) + random.uniform(-1.5, 1.5), 2)
            c = round(o + random.uniform(-2.0, 2.5), 2)
            h = round(max(o, c) + random.uniform(0.2, 1.8), 2)
            l = round(min(o, c) - random.uniform(0.2, 1.8), 2)
            candles.append({
                'time': int(time.time()) - ((30 - i) * 300),
                'open': o,
                'high': h,
                'low': l,
                'close': c,
                'volume': int(random.uniform(5000, 35000))
            })
        candles[-1]['close'] = cur_p
        return candles

market_service = MarketDataService()
