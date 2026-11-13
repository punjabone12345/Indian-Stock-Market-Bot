import os
import glob
import pandas as pd
import numpy as np
import datetime
from datetime import time

def load_stock_data(symbol):
    f_prev = f'data/stocks/{symbol}_prev.parquet'
    f_2026 = f'data/stocks/{symbol}_2026.parquet'
    dfs = []
    if os.path.exists(f_prev):
        d1 = pd.read_parquet(f_prev)
        d1['Timestamp'] = pd.to_datetime(d1['Date'])
        d1 = d1[d1['Timestamp'] >= '2022-10-01']
        dfs.append(d1[['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']])
    if os.path.exists(f_2026):
        d2 = pd.read_parquet(f_2026)
        d2['Timestamp'] = pd.to_datetime(d2['Date'])
        dfs.append(d2[['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']])
    if not dfs: return None
    df = pd.concat(dfs).sort_values('Timestamp').drop_duplicates('Timestamp').reset_index(drop=True)
    df['Time'] = df['Timestamp'].dt.time
    df = df[(df['Time'] >= time(9, 15)) & (df['Time'] <= time(15, 29))].copy()
    return df

def load_nifty_5m():
    from nifty_alpha_explorer import load_nifty_fast, resample_nifty
    df_1m = load_nifty_fast()
    df_5m = resample_nifty(df_1m, 5)
    
    # Calculate Nifty EMAs
    df_5m['EMA9'] = df_5m.groupby('Date')['Close'].transform(lambda x: x.ewm(span=9, adjust=False).mean())
    df_5m['EMA21'] = df_5m.groupby('Date')['Close'].transform(lambda x: x.ewm(span=21, adjust=False).mean())
    
    # Nifty Trend State: +1 Bullish, -1 Bearish, 0 Neutral
    df_5m['Nifty_Trend'] = 0
    df_5m.loc[(df_5m['Close'] > df_5m['EMA21']) & (df_5m['EMA9'] > df_5m['EMA21']), 'Nifty_Trend'] = 1
    df_5m.loc[(df_5m['Close'] < df_5m['EMA21']) & (df_5m['EMA9'] < df_5m['EMA21']), 'Nifty_Trend'] = -1
    return df_5m[['Timestamp', 'Date', 'Time', 'Close', 'EMA9', 'EMA21', 'Nifty_Trend']]

if __name__ == '__main__':
    print("Testing data loading...")
    nifty_5m = load_nifty_5m()
    print(f"Nifty 5m rows: {len(nifty_5m)}")
    print(nifty_5m.tail())
    
    rel = load_stock_data('RELIANCE')
    print(f"Reliance 1m rows: {len(rel)}")
