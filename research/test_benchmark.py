import os, glob, time
from datetime import time as dtime
import pandas as pd
import numpy as np

def load_symbol_5m(symbol):
    p_prev = f"data/stocks/{symbol}_prev.parquet"
    p_2026 = f"data/stocks/{symbol}_2026.parquet"
    dfs = []
    if os.path.exists(p_prev): dfs.append(pd.read_parquet(p_prev))
    if os.path.exists(p_2026): dfs.append(pd.read_parquet(p_2026))
    if not dfs: return None
    df = pd.concat(dfs, ignore_index=True)
    df['Date'] = pd.to_datetime(df['Date'])
    # Window: 2021-11-01 to 2026-10-31
    df = df[(df['Date'] >= '2021-11-01') & (df['Date'] <= '2026-10-31')].sort_values('Date').reset_index(drop=True)
    df.set_index('Date', inplace=True)
    t_start, t_end = dtime(9, 15), dtime(15, 30)
    df_5m = df.resample('5min').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna().reset_index()
    df_5m['time'] = df_5m['Date'].dt.time
    df_5m = df_5m[(df_5m['time'] >= t_start) & (df_5m['time'] <= t_end)].reset_index(drop=True)
    df_5m['date_str'] = df_5m['Date'].dt.strftime('%Y-%m-%d')
    
    # Vectorized indicator computation on full symbol DataFrame
    df_5m['typ'] = (df_5m['High'] + df_5m['Low'] + df_5m['Close']) / 3.0
    df_5m['pv'] = df_5m['typ'] * df_5m['Volume']
    df_5m['cum_pv'] = df_5m.groupby('date_str')['pv'].cumsum()
    df_5m['cum_vol'] = df_5m.groupby('date_str')['Volume'].cumsum()
    df_5m['vwap'] = np.where(df_5m['cum_vol'] > 0, df_5m['cum_pv'] / df_5m['cum_vol'], df_5m['Close'])
    
    df_5m['ema9'] = df_5m['Close'].ewm(span=9, adjust=False).mean()
    df_5m['ema21'] = df_5m['Close'].ewm(span=21, adjust=False).mean()
    
    return df_5m

t0 = time.time()
print("Benchmarking 1 symbol: RELIANCE...", flush=True)
df = load_symbol_5m('RELIANCE')
print(f"Loaded RELIANCE 5m: {len(df)} rows in {time.time()-t0:.2f}s", flush=True)

t1 = time.time()
grouped = df.groupby('date_str')
days = {}
or_vols = []
prev_close = None
for d_str, d_df in grouped:
    d_df = d_df.reset_index(drop=True)
    if len(d_df) < 25:
        if len(d_df) > 0: prev_close = d_df.iloc[-1]['Close']
        continue
    c15 = d_df.iloc[0:3]
    open_15m = c15.iloc[0]['Open']
    high_15m = c15['High'].max()
    low_15m = c15['Low'].min()
    close_15m = c15.iloc[-1]['Close']
    vol_15m = c15['Volume'].sum()
    range_15m = high_15m - low_15m
    gap_pct = (close_15m - prev_close) / prev_close * 100.0 if prev_close else 0.0
    rvol = vol_15m / np.mean(or_vols[-20:]) if len(or_vols) >= 10 and np.mean(or_vols[-20:]) > 0 else 1.0
    or_vols.append(vol_15m)
    prev_close = d_df.iloc[-1]['Close']
    days[d_str] = len(d_df)

print(f"Grouped {len(days)} days in {time.time()-t1:.2f}s", flush=True)
