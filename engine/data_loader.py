import os
import glob
import pandas as pd
import numpy as np
from datetime import datetime, time

def _clean_cols(df):
    if 'Volume' not in df.columns:
        df['Volume'] = 1
    return df[['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']]

def load_nifty():
    dfs = []
    # 2022 (from Oct 1)
    df22 = pd.read_csv('data/nifty50/NIFTY50_1min_2022.csv')
    df22['Timestamp'] = pd.to_datetime(df22['Timestamp'])
    df22 = df22[df22['Timestamp'] >= '2022-10-01']
    dfs.append(_clean_cols(df22))

    # 2023, 2024, 2025
    for yr in ['2023', '2024', '2025']:
        p = f'data/nifty50/NIFTY50_1min_{yr}.csv'
        if os.path.exists(p):
            d = pd.read_csv(p)
            d['Timestamp'] = pd.to_datetime(d['Timestamp'])
            dfs.append(_clean_cols(d))

    # 2026
    for m in sorted(glob.glob('data/nifty50/2026/*.csv')):
        d = pd.read_csv(m)
        d['Timestamp'] = pd.to_datetime(d['Timestamp'])
        dfs.append(_clean_cols(d))

    df = pd.concat(dfs).sort_values('Timestamp').reset_index(drop=True)
    df['Symbol'] = 'NIFTY50'
    df['IsIndex'] = True
    return df

def load_stock(symbol):
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
    if not dfs:
        return None
    df = pd.concat(dfs).sort_values('Timestamp').drop_duplicates('Timestamp').reset_index(drop=True)
    df['Symbol'] = symbol
    df['IsIndex'] = False
    return df

def resample_5min(df_1m):
    # Resample to 5-minute OHLCV
    df_1m = df_1m.set_index('Timestamp')
    agg_dict = {
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum',
        'Symbol': 'first',
        'IsIndex': 'first'
    }
    df_5m = df_1m.resample('5min', origin='start_day').agg(agg_dict).dropna().reset_index()
    # Filter to Indian market hours: 09:15 to 15:30
    df_5m['Time'] = df_5m['Timestamp'].dt.time
    df_5m['Date'] = df_5m['Timestamp'].dt.date
    df_5m = df_5m[(df_5m['Time'] >= time(9, 15)) & (df_5m['Time'] <= time(15, 30))].copy()
    return df_5m

if __name__ == '__main__':
    print('Testing data loaders...')
    nifty = load_nifty()
    print('Nifty 1m shape:', nifty.shape)
    nifty_5m = resample_5min(nifty)
    print('Nifty 5m shape:', nifty_5m.shape)
    print(nifty_5m.head(3))
    
    rel = load_stock('RELIANCE')
    print('Reliance 1m shape:', rel.shape)
    rel_5m = resample_5min(rel)
    print('Reliance 5m shape:', rel_5m.shape)
