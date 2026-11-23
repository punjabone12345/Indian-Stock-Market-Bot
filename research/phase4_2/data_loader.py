"""
DATA LOADER & RESAMPLER FOR 4+ YEAR MASTER BACKTEST (2022-2026)
Loads continuous 1-minute data for top 29 liquid mega-caps, pre-computes Daily, 15m, and 5m bars,
and caches them for instant backtesting across all quantitative concepts.
"""
import os
import glob
import pandas as pd
import numpy as np
from datetime import time

CACHE_DIR = "data/master_cache_2022_2026"

def prepare_master_data():
    os.makedirs(CACHE_DIR, exist_ok=True)
    
    symbols = [
        'RELIANCE', 'TCS', 'HDFCBANK', 'ICICIBANK', 'INFY', 'SBIN',
        'BHARTIARTL', 'LT', 'AXISBANK', 'BAJFINANCE', 'TITAN', 'MARUTI',
        'KOTAKBANK', 'WIPRO', 'SUNPHARMA', 'TATASTEEL', 'ADANIENT', 'INDUSINDBK',
        'COALINDIA', 'GRASIM', 'HCLTECH', 'HINDUNILVR', 'ITC', 'JSWSTEEL',
        'NTPC', 'ONGC', 'POWERGRID', 'TECHM', 'ULTRACEMCO'
    ]
    
    print(f"Checking master cache for {len(symbols)} symbols...")
    missing = []
    for s in symbols:
        cache_f = os.path.join(CACHE_DIR, f"{s}_5m.parquet")
        if not os.path.exists(cache_f):
            missing.append(s)
            
    if not missing:
        print("Master cache is already complete. All symbols ready.")
        return symbols
        
    print(f"Building master cache for {len(missing)} missing symbols...")
    for s in missing:
        f_prev = f'data/stocks/{s}_prev.parquet'
        f_2026 = f'data/stocks/{s}_2026.parquet'
        dfs = []
        if os.path.exists(f_prev):
            d1 = pd.read_parquet(f_prev)
            d1['Timestamp'] = pd.to_datetime(d1['Date'])
            d1 = d1[d1['Timestamp'] >= '2022-01-01']
            dfs.append(d1[['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']])
        if os.path.exists(f_2026):
            d2 = pd.read_parquet(f_2026)
            d2['Timestamp'] = pd.to_datetime(d2['Date'])
            dfs.append(d2[['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']])
            
        if not dfs:
            print(f"Warning: No data for {s}")
            continue
            
        df = pd.concat(dfs).sort_values('Timestamp').drop_duplicates('Timestamp').reset_index(drop=True)
        df['Time'] = df['Timestamp'].dt.time
        df['Date'] = df['Timestamp'].dt.date
        df = df[(df['Time'] >= time(9, 15)) & (df['Time'] <= time(15, 30))].copy()
        
        # Save 1-minute cleaned
        df.to_parquet(os.path.join(CACHE_DIR, f"{s}_1m.parquet"))
        
        # Aggregate to 5-minute
        df.set_index('Timestamp', inplace=True)
        agg_dict = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}
        df_5m = df.resample('5min', origin='start_day').agg(agg_dict).dropna().reset_index()
        df_5m['Time'] = df_5m['Timestamp'].dt.time
        df_5m['Date'] = df_5m['Timestamp'].dt.date
        df_5m = df_5m[(df_5m['Time'] >= time(9, 15)) & (df_5m['Time'] <= time(15, 30))].copy()
        
        # Calculate VWAP on 5m
        df_5m['Typ'] = (df_5m['High'] + df_5m['Low'] + df_5m['Close']) / 3.0
        df_5m['PV'] = df_5m['Typ'] * df_5m['Volume']
        df_5m['CumPV'] = df_5m.groupby('Date')['PV'].cumsum()
        df_5m['CumV'] = df_5m.groupby('Date')['Volume'].cumsum()
        df_5m['VWAP'] = df_5m['CumPV'] / df_5m['CumV']
        
        # Save 5-minute
        df_5m.to_parquet(os.path.join(CACHE_DIR, f"{s}_5m.parquet"))
        
        # Aggregate to 15-minute
        df_15m = df.resample('15min', origin='start_day').agg(agg_dict).dropna().reset_index()
        df_15m['Time'] = df_15m['Timestamp'].dt.time
        df_15m['Date'] = df_15m['Timestamp'].dt.date
        df_15m = df_15m[(df_15m['Time'] >= time(9, 15)) & (df_15m['Time'] <= time(15, 30))].copy()
        df_15m.to_parquet(os.path.join(CACHE_DIR, f"{s}_15m.parquet"))
        
        # Aggregate to Daily
        df_daily = df.resample('1D').agg(agg_dict).dropna().reset_index()
        df_daily['Date'] = df_daily['Timestamp'].dt.date
        df_daily.to_parquet(os.path.join(CACHE_DIR, f"{s}_daily.parquet"))
        
        print(f"Processed {s}: {len(df_5m)} 5m bars, {len(df_15m)} 15m bars, {len(df_daily)} daily bars.")
        
    return symbols

if __name__ == '__main__':
    prepare_master_data()
