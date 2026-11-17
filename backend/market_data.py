import urllib.request
import ssl
import json
import time
from datetime import datetime
try:
    from ist_time import now_ist_str
except ImportError:
    from backend.ist_time import now_ist_str

# 14 Top Liquid Champion Instruments (Backtested 4.8 Years with Dynamic Risk Governor)
CHAMPION_14_INSTRUMENTS = {
    'RELIANCE': {'ticker': 'RELIANCE.NS', 'name': 'Reliance Industries', 'sector': 'Energy', 'baseline': 1344.80},
    'INDUSINDBK': {'ticker': 'INDUSINDBK.NS', 'name': 'IndusInd Bank', 'sector': 'Banking & Finance', 'baseline': 914.55},
    'LT': {'ticker': 'LT.NS', 'name': 'Larsen & Toubro', 'sector': 'Infrastructure', 'baseline': 4140.00},
    'ADANIENT': {'ticker': 'ADANIENT.NS', 'name': 'Adani Enterprises', 'sector': 'Diversified Conglomerate', 'baseline': 2659.00},
    'TATAMOTORS': {'ticker': 'TMCV.NS', 'alt_ticker': 'TMPV.NS', 'name': 'Tata Motors Limited', 'sector': 'Automobiles', 'baseline': 428.25},
    'SUNPHARMA': {'ticker': 'SUNPHARMA.NS', 'name': 'Sun Pharmaceutical Ind', 'sector': 'Healthcare & Pharma', 'baseline': 1867.50},
    'WIPRO': {'ticker': 'WIPRO.NS', 'name': 'Wipro Limited', 'sector': 'IT & Software', 'baseline': 193.54},
    'JSWSTEEL': {'ticker': 'JSWSTEEL.NS', 'name': 'JSW Steel Ltd', 'sector': 'Metals & Mining', 'baseline': 1334.60},
    'TATASTEEL': {'ticker': 'TATASTEEL.NS', 'name': 'Tata Steel Ltd', 'sector': 'Metals & Mining', 'baseline': 182.26},
    'BAJFINANCE': {'ticker': 'BAJFINANCE.NS', 'name': 'Bajaj Finance Ltd', 'sector': 'NBFC & Lending', 'baseline': 1110.00},
    'SBIN': {'ticker': 'SBIN.NS', 'name': 'State Bank of India', 'sector': 'Public Sector Banking', 'baseline': 1090.50},
    'ONGC': {'ticker': 'ONGC.NS', 'name': 'Oil & Natural Gas Corp', 'sector': 'Energy & Utilities', 'baseline': 226.99},
    'TCS': {'ticker': 'TCS.NS', 'name': 'Tata Consultancy Services', 'sector': 'IT Services', 'baseline': 2405.00},
    'MARUTI': {'ticker': 'MARUTI.NS', 'name': 'Maruti Suzuki India', 'sector': 'Automobiles', 'baseline': 12571.00},
    'NIFTY50': {'ticker': '^NSEI', 'name': 'Nifty 50 Benchmark', 'sector': 'Macro Index', 'baseline': 25291.10}
}

# Alias for legacy compatibility
CROWN_6_INSTRUMENTS = CHAMPION_14_INSTRUMENTS

DEFAULT_BASELINES = {sym: info['baseline'] for sym, info in CHAMPION_14_INSTRUMENTS.items()}

class MarketDataService:
    def __init__(self):
        self.ctx = ssl._create_unverified_context()
        self.quote_cache = {}
        self.candle_cache = {}
        self.last_fetch_ts = 0

    def fetch_live_quotes(self):
        now = time.time()
        # Fetch from Yahoo v8 chart every 3 seconds
        if now - self.last_fetch_ts > 3 or not self.quote_cache:
            self._fetch_all_from_v8()
            self.last_fetch_ts = now
        return self.quote_cache

    def _fetch_all_from_v8(self):
        for sym, info in CHAMPION_14_INSTRUMENTS.items():
            ticker = info['ticker']
            base_p = info['baseline']
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=5m&range=1d"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
            try:
                with urllib.request.urlopen(req, context=self.ctx, timeout=6) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                    res = data['chart']['result'][0]
                    meta = res['meta']
                    timestamps = res.get('timestamp', [])
                    indicators = res['indicators']['quote'][0]

                    opens = indicators.get('open', [])
                    highs = indicators.get('high', [])
                    lows = indicators.get('low', [])
                    closes = indicators.get('close', [])
                    volumes = indicators.get('volume', [])

                    candles = []
                    for i in range(len(timestamps)):
                        if (opens[i] is not None and highs[i] is not None and 
                            lows[i] is not None and closes[i] is not None):
                            candles.append({
                                'time': timestamps[i],
                                'open': round(opens[i], 2),
                                'high': round(highs[i], 2),
                                'low': round(lows[i], 2),
                                'close': round(closes[i], 2),
                                'volume': volumes[i] if (volumes and volumes[i] is not None) else 0
                            })
                    self.candle_cache[sym] = candles

                    cur_p = meta.get('regularMarketPrice') or (candles[-1]['close'] if candles else base_p)
                    prev_c = meta.get('chartPreviousClose') or cur_p
                    chg = cur_p - prev_c
                    chg_pct = (chg / prev_c) * 100.0 if prev_c else 0.0
                    d_high = meta.get('regularMarketDayHigh') or cur_p
                    d_low = meta.get('regularMarketDayLow') or cur_p
                    vol = meta.get('regularMarketVolume') or 0

                    self.quote_cache[sym] = {
                        'symbol': sym,
                        'ticker': ticker,
                        'name': info['name'],
                        'sector': info['sector'],
                        'price': round(float(cur_p), 2),
                        'prev_close': round(float(prev_c), 2),
                        'change': round(float(chg), 2),
                        'change_pct': round(float(chg_pct), 2),
                        'day_high': round(float(d_high), 2),
                        'day_low': round(float(d_low), 2),
                        'volume': int(vol),
                        'updated_at': now_ist_str("%H:%M:%S")
                    }
            except Exception as e:
                # Fallback to alternate ticker if provided (e.g. TMPV for TATAMOTORS)
                alt_ticker = info.get('alt_ticker')
                if alt_ticker:
                    try:
                        url_alt = f"https://query1.finance.yahoo.com/v8/finance/chart/{alt_ticker}?interval=5m&range=1d"
                        req_alt = urllib.request.Request(url_alt, headers={'User-Agent': 'Mozilla/5.0'})
                        with urllib.request.urlopen(req_alt, context=self.ctx, timeout=5) as resp_alt:
                            data_alt = json.loads(resp_alt.read().decode('utf-8'))
                            meta_alt = data_alt['chart']['result'][0]['meta']
                            cur_p = meta_alt.get('regularMarketPrice') or base_p
                            prev_c = meta_alt.get('chartPreviousClose') or cur_p
                            self.quote_cache[sym] = {
                                'symbol': sym,
                                'ticker': alt_ticker,
                                'name': info['name'],
                                'sector': info['sector'],
                                'price': round(float(cur_p), 2),
                                'prev_close': round(float(prev_c), 2),
                                'change': round(float(cur_p - prev_c), 2),
                                'change_pct': round(float(((cur_p - prev_c)/prev_c)*100.0), 2) if prev_c else 0.0,
                                'day_high': round(float(meta_alt.get('regularMarketDayHigh') or cur_p), 2),
                                'day_low': round(float(meta_alt.get('regularMarketDayLow') or cur_p), 2),
                                'volume': int(meta_alt.get('regularMarketVolume') or 0),
                                'updated_at': now_ist_str("%H:%M:%S")
                            }
                            continue
                    except Exception:
                        pass

                # Keep existing cache or use real baseline
                if sym not in self.quote_cache:
                    self.quote_cache[sym] = {
                        'symbol': sym,
                        'ticker': ticker,
                        'name': info['name'],
                        'sector': info['sector'],
                        'price': base_p,
                        'prev_close': base_p,
                        'change': 0.0,
                        'change_pct': 0.0,
                        'day_high': base_p,
                        'day_low': base_p,
                        'volume': 0,
                        'updated_at': now_ist_str("%H:%M:%S")
                    }

    def get_candle_history(self, symbol: str):
        if symbol in self.candle_cache and len(self.candle_cache[symbol]) >= 5:
            return self.candle_cache[symbol]
        
        # Trigger fetch if not present
        self._fetch_all_from_v8()
        return self.candle_cache.get(symbol, [])

market_service = MarketDataService()
