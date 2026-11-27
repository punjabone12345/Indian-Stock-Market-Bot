import urllib.request
import ssl
import json
import time
import concurrent.futures
from datetime import datetime
try:
    from ist_time import now_ist_str
except ImportError:
    from backend.ist_time import now_ist_str

# 29 Liquid NSE Mega-Cap Universe (Velocity Compounder Strategy)
MEGACAP_29_INSTRUMENTS = {
    'RELIANCE': {'ticker': 'RELIANCE.NS', 'name': 'Reliance Industries', 'sector': 'Energy', 'baseline': 1344.80, 'vol_45m_base': 1696232},
    'TCS': {'ticker': 'TCS.NS', 'name': 'Tata Consultancy Services', 'sector': 'IT Services', 'baseline': 2465.00, 'vol_45m_base': 638405},
    'HDFCBANK': {'ticker': 'HDFCBANK.NS', 'name': 'HDFC Bank Ltd', 'sector': 'Banking', 'baseline': 1740.00, 'vol_45m_base': 3636200},
    'ICICIBANK': {'ticker': 'ICICIBANK.NS', 'name': 'ICICI Bank Ltd', 'sector': 'Banking', 'baseline': 1397.00, 'vol_45m_base': 1210653},
    'SBIN': {'ticker': 'SBIN.NS', 'name': 'State Bank of India', 'sector': 'Banking', 'baseline': 962.60, 'vol_45m_base': 1052733},
    'INFY': {'ticker': 'INFY.NS', 'name': 'Infosys Limited', 'sector': 'IT Services', 'baseline': 1850.00, 'vol_45m_base': 1553132},
    'LT': {'ticker': 'LT.NS', 'name': 'Larsen & Toubro', 'sector': 'Infrastructure', 'baseline': 3627.10, 'vol_45m_base': 207550},
    'TATASTEEL': {'ticker': 'TATASTEEL.NS', 'name': 'Tata Steel Ltd', 'sector': 'Metals & Mining', 'baseline': 175.50, 'vol_45m_base': 2859123},
    'BAJFINANCE': {'ticker': 'BAJFINANCE.NS', 'name': 'Bajaj Finance Ltd', 'sector': 'NBFC & Lending', 'baseline': 6850.00, 'vol_45m_base': 933491},
    'MARUTI': {'ticker': 'MARUTI.NS', 'name': 'Maruti Suzuki India', 'sector': 'Automobiles', 'baseline': 11489.00, 'vol_45m_base': 54981},
    'BHARTIARTL': {'ticker': 'BHARTIARTL.NS', 'name': 'Bharti Airtel Ltd', 'sector': 'Telecommunications', 'baseline': 1905.00, 'vol_45m_base': 963095},
    'WIPRO': {'ticker': 'WIPRO.NS', 'name': 'Wipro Limited', 'sector': 'IT Services', 'baseline': 550.00, 'vol_45m_base': 3051102},
    'GRASIM': {'ticker': 'GRASIM.NS', 'name': 'Grasim Industries', 'sector': 'Materials & Cement', 'baseline': 2920.00, 'vol_45m_base': 60865},
    'SUNPHARMA': {'ticker': 'SUNPHARMA.NS', 'name': 'Sun Pharmaceutical Ind', 'sector': 'Healthcare & Pharma', 'baseline': 1758.80, 'vol_45m_base': 194366},
    'INDUSINDBK': {'ticker': 'INDUSINDBK.NS', 'name': 'IndusInd Bank', 'sector': 'Banking', 'baseline': 877.00, 'vol_45m_base': 327069},
    'TECHM': {'ticker': 'TECHM.NS', 'name': 'Tech Mahindra Ltd', 'sector': 'IT Services', 'baseline': 1790.00, 'vol_45m_base': 417024},
    'HCLTECH': {'ticker': 'HCLTECH.NS', 'name': 'HCL Technologies', 'sector': 'IT Services', 'baseline': 1820.00, 'vol_45m_base': 538785},
    'KOTAKBANK': {'ticker': 'KOTAKBANK.NS', 'name': 'Kotak Mahindra Bank', 'sector': 'Banking', 'baseline': 1750.00, 'vol_45m_base': 2978953},
    'AXISBANK': {'ticker': 'AXISBANK.NS', 'name': 'Axis Bank Ltd', 'sector': 'Banking', 'baseline': 1290.00, 'vol_45m_base': 804924},
    'ONGC': {'ticker': 'ONGC.NS', 'name': 'Oil & Natural Gas Corp', 'sector': 'Energy', 'baseline': 222.00, 'vol_45m_base': 1243422},
    'NTPC': {'ticker': 'NTPC.NS', 'name': 'NTPC Limited', 'sector': 'Utilities & Power', 'baseline': 315.15, 'vol_45m_base': 1034843},
    'POWERGRID': {'ticker': 'POWERGRID.NS', 'name': 'Power Grid Corp', 'sector': 'Utilities & Power', 'baseline': 250.45, 'vol_45m_base': 1247003},
    'COALINDIA': {'ticker': 'COALINDIA.NS', 'name': 'Coal India Ltd', 'sector': 'Mining & Energy', 'baseline': 417.20, 'vol_45m_base': 804629},
    'JSWSTEEL': {'ticker': 'JSWSTEEL.NS', 'name': 'JSW Steel Ltd', 'sector': 'Metals & Mining', 'baseline': 1216.30, 'vol_45m_base': 201143},
    'ITC': {'ticker': 'ITC.NS', 'name': 'ITC Limited', 'sector': 'FMCG', 'baseline': 470.00, 'vol_45m_base': 2387108},
    'HINDUNILVR': {'ticker': 'HINDUNILVR.NS', 'name': 'Hindustan Unilever', 'sector': 'FMCG', 'baseline': 2420.00, 'vol_45m_base': 177814},
    'TITAN': {'ticker': 'TITAN.NS', 'name': 'Titan Company Ltd', 'sector': 'Consumer Discretionary', 'baseline': 3444.80, 'vol_45m_base': 104890},
    'ADANIENT': {'ticker': 'ADANIENT.NS', 'name': 'Adani Enterprises', 'sector': 'Diversified Conglomerate', 'baseline': 2692.00, 'vol_45m_base': 180763},
    'ULTRACEMCO': {'ticker': 'ULTRACEMCO.NS', 'name': 'UltraTech Cement', 'sector': 'Materials & Cement', 'baseline': 10907.00, 'vol_45m_base': 34902},
    'NIFTY50': {'ticker': '^NSEI', 'name': 'Nifty 50 Benchmark', 'sector': 'Macro Index', 'baseline': 24350.00, 'vol_45m_base': 1000000}
}

# Aliases for backward compatibility
CHAMPION_14_INSTRUMENTS = MEGACAP_29_INSTRUMENTS
CROWN_6_INSTRUMENTS = MEGACAP_29_INSTRUMENTS

DEFAULT_BASELINES = {sym: info['baseline'] for sym, info in MEGACAP_29_INSTRUMENTS.items()}

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

    def _fetch_single_symbol(self, sym, info):
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
                vol = meta.get('regularMarketVolume') or sum(c['volume'] for c in candles)

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
                    'vol_45m_base': info['vol_45m_base'],
                    'updated_at': now_ist_str("%H:%M:%S")
                }
        except Exception as e:
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
                    'vol_45m_base': info['vol_45m_base'],
                    'updated_at': now_ist_str("%H:%M:%S")
                }

    def _fetch_all_from_v8(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(self._fetch_single_symbol, sym, info) for sym, info in MEGACAP_29_INSTRUMENTS.items()]
            concurrent.futures.wait(futures, timeout=10)

    def get_candle_history(self, symbol: str):
        if symbol in self.candle_cache and len(self.candle_cache[symbol]) >= 5:
            return self.candle_cache[symbol]
        
        # Trigger fetch if not present
        self._fetch_all_from_v8()
        return self.candle_cache.get(symbol, [])

market_service = MarketDataService()
