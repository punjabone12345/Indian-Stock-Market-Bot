"""
Download 2.5-Year 1-Hour Intraday Data for all 194 Nifty 200 Stocks
Saves to data/nifty200_1h_cache/
"""

import os, json, ssl, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

CACHE_DIR = "data/nifty200_1h_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

daily_files = sorted(os.listdir("data/nifty200_daily_cache"))
SYMBOLS = [f.replace(".parquet", "") for f in daily_files if f.endswith(".parquet")]
print(f"Total symbols to download: {len(SYMBOLS)}")

ctx = ssl._create_unverified_context()
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

def download_symbol(sym):
    cache_path = os.path.join(CACHE_DIR, f"{sym}.parquet")
    if os.path.exists(cache_path):
        try:
            df = pd.read_parquet(cache_path)
            if len(df) > 1000:
                return sym, len(df), "CACHED"
        except Exception:
            pass

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}.NS?interval=1h&range=730d"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
            res = json.loads(r.read())['chart']['result'][0]
            ts = res['timestamp']
            quote = res['indicators']['quote'][0]
            df = pd.DataFrame({
                'Date_UTC': pd.to_datetime(ts, unit='s'),
                'Open': quote['open'], 'High': quote['high'], 'Low': quote['low'],
                'Close': quote['close'], 'Volume': quote['volume']
            }).dropna()
            
            # Convert to IST (+5:30)
            df['Date'] = df['Date_UTC'] + pd.Timedelta(hours=5, minutes=30)
            df['date_str'] = df['Date'].dt.date.astype(str)
            df['time_str'] = df['Date'].dt.time.astype(str)
            df = df.sort_values('Date').reset_index(drop=True)
            
            df.to_parquet(cache_path, index=False)
            return sym, len(df), "DOWNLOADED"
    except Exception as e:
        return sym, 0, str(e)

def run_downloads():
    t0 = time.time()
    print("Starting multi-threaded download of 194 stocks (1-hour bars, 730 days)...", flush=True)
    success = 0
    failed = 0
    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = {executor.submit(download_symbol, s): s for s in SYMBOLS}
        for f in as_completed(futures):
            sym, rows, status = f.result()
            if rows > 1000:
                success += 1
            else:
                failed += 1
                print(f"  {sym}: {status}", flush=True)

    print(f"\nDownload finished in {time.time()-t0:.1f}s. Successfully loaded {success}/{len(SYMBOLS)} stocks.", flush=True)

if __name__ == '__main__':
    run_downloads()
