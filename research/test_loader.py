import os, glob, time
import pandas as pd
import numpy as np

symbols = [
    'ADANIENT', 'AXISBANK', 'BAJFINANCE', 'BHARTIARTL', 'COALINDIA', 
    'GRASIM', 'HCLTECH', 'HDFCBANK', 'HINDUNILVR', 'ICICIBANK', 
    'INDUSINDBK', 'INFY', 'ITC', 'JSWSTEEL', 'KOTAKBANK', 
    'LT', 'MARUTI', 'NTPC', 'ONGC', 'POWERGRID', 
    'RELIANCE', 'SBIN', 'SUNPHARMA', 'TATAMOTORS', 'TATASTEEL', 
    'TCS', 'TECHM', 'TITAN', 'ULTRACEMCO', 'WIPRO'
]

print("Testing loading of symbols...", flush=True)
for sym in symbols:
    t0 = time.time()
    p_prev = f"data/stocks/{sym}_prev.parquet"
    p_2026 = f"data/stocks/{sym}_2026.parquet"
    if not os.path.exists(p_prev):
        print(f"Missing {sym}_prev.parquet", flush=True)
        continue
    df_prev = pd.read_parquet(p_prev)
    t_load = time.time() - t0
    print(f"Loaded {sym}: {len(df_prev)} rows in {t_load:.2f}s", flush=True)
