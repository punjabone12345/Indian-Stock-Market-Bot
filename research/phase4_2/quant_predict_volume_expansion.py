"""
QUANT RESEARCH: CAN WE PREDICT INTRADAY VOLUME EXPANSION AT 09:15 AM?
Test 194 Nifty 200 stocks (1,193 days, 2022-2026):
Can point-in-time variables known at 09:15 AM predict whether today will be an institutional trend day (RVOL >= 2.0x / Range >= 3%)?
"""

import os, glob
import numpy as np
import pandas as pd

def analyze_predictive_features():
    files = glob.glob("data/nifty200_daily_cache/*.parquet")
    print(f"Loading {len(files)} stocks...", flush=True)
    
    rows = []
    for f in files:
        sym = os.path.basename(f).replace(".parquet", "")
        df = pd.read_parquet(f).sort_values('Date').reset_index(drop=True)
        if len(df) < 60: continue
        
        df['Date'] = pd.to_datetime(df['Date'])
        df['date_str'] = df['Date'].dt.strftime('%Y-%m-%d')
        
        # Target: Is today an institutional momentum day?
        # 1. Total volume >= 2.0x normal
        # 2. Daily range >= 3.0%
        # 3. Closed in direction of gap
        df['vol_20avg'] = df['Volume'].rolling(20).mean().shift(1)
        df['today_rvol'] = df['Volume'] / np.where(df['vol_20avg'] > 0, df['vol_20avg'], df['Volume'])
        df['prev_close'] = df['Close'].shift(1)
        df['today_gap'] = (df['Open'] - df['prev_close']) / df['prev_close'] * 100.0
        df['today_range'] = (df['High'] - df['Low']) / df['prev_close'] * 100.0
        df['today_return'] = (df['Close'] - df['Open']) / df['Open'] * 100.0
        
        # Target: Success for Long (Gap >= 1% and today_return >= 1.5% and today_range >= 2.5%)
        df['target_long_win'] = ((df['today_gap'] >= 1.0) & (df['today_return'] >= 1.5) & (df['High'] >= df['Open'] * 1.025)).astype(int)
        
        # Point-in-time features known at 09:15 AM:
        # F1: Gap magnitude
        # F2: Yesterday RVOL
        df['prev_rvol'] = df['today_rvol'].shift(1)
        # F3: Yesterday range vs ATR
        tr1 = df['High'] - df['Low']
        tr2 = (df['High'] - df['Close'].shift(1)).abs()
        tr3 = (df['Low'] - df['Close'].shift(1)).abs()
        df['atr14'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14).mean().shift(1)
        df['atr_pct'] = df['atr14'] / df['prev_close'] * 100.0
        # F4: Yesterday candle position (Close - Low) / (High - Low)
        prev_rng = df['High'].shift(1) - df['Low'].shift(1)
        df['prev_close_pos'] = (df['Close'].shift(1) - df['Low'].shift(1)) / np.where(prev_rng > 0, prev_rng, 1.0)
        # F5: 5-day momentum
        df['mom5d'] = (df['prev_close'] - df['Close'].shift(6)) / df['Close'].shift(6) * 100.0
        # F6: 20-day High proximity
        df['high20d'] = df['High'].rolling(20).max().shift(1)
        df['dist_high20d'] = (df['Open'] - df['high20d']) / df['high20d'] * 100.0
        # F7: 3-day volume trend
        df['vol_trend3d'] = df['Volume'].shift(1) / np.where(df['Volume'].shift(4) > 0, df['Volume'].shift(4), 1.0)
        # F8: Average Daily Turnover (Cr)
        df['turnover_cr'] = (df['vol_20avg'] * df['prev_close']) / 1e7
        
        # Filter to 2022 - 2026
        mask = (df['Date'].dt.year >= 2022) & (df['date_str'] <= '2026-10-31')
        sub = df[mask][['date_str', 'today_gap', 'today_rvol', 'today_range', 'today_return', 'target_long_win',
                        'prev_rvol', 'atr_pct', 'prev_close_pos', 'mom5d', 'dist_high20d', 'vol_trend3d', 'turnover_cr']]
        sub['symbol'] = sym
        rows.append(sub)
        
    df_all = pd.concat(rows, ignore_index=True).dropna()
    print(f"Total stock-day observations: {len(df_all):,}")
    
    # Filter to Gaps >= 1.2%
    gaps = df_all[df_all['today_gap'] >= 1.2].copy()
    print(f"Observations with Gap >= 1.2%: {len(gaps):,}")
    base_rate = gaps['target_long_win'].mean() * 100.0
    print(f"Base rate of Long Winner (return >= 1.5% & range >= 2.5%): {base_rate:.2f}%\n")
    
    # Evaluate features conditional on Gap >= 1.2%
    print("--- FEATURE ANALYSIS FOR MORNING GAPS ---")
    
    # 1. 20-Day High Breakout (dist_high20d >= 0)
    b1 = gaps[gaps['dist_high20d'] >= 0]
    print(f"Open >= 20-Day High: {len(b1)} cases | Win Rate: {b1['target_long_win'].mean()*100:.2f}% | Avg Day Return: {b1['today_return'].mean():+.2f}%")
    
    # 2. Yesterday Closed Strong (prev_close_pos >= 0.8)
    b2 = gaps[gaps['prev_close_pos'] >= 0.8]
    print(f"Yesterday Close near High (>=0.8): {len(b2)} cases | Win Rate: {b2['target_long_win'].mean()*100:.2f}% | Avg Day Return: {b2['today_return'].mean():+.2f}%")
    
    # 3. Yesterday RVOL >= 1.5x
    b3 = gaps[gaps['prev_rvol'] >= 1.5]
    print(f"Yesterday RVOL >= 1.5x: {len(b3)} cases | Win Rate: {b3['target_long_win'].mean()*100:.2f}% | Avg Day Return: {b3['today_return'].mean():+.2f}%")
    
    # 4. Strong 5-day Momentum (mom5d >= 5%)
    b4 = gaps[gaps['mom5d'] >= 5.0]
    print(f"5-Day Momentum >= 5%: {len(b4)} cases | Win Rate: {b4['target_long_win'].mean()*100:.2f}% | Avg Day Return: {b4['today_return'].mean():+.2f}%")
    
    # 5. High ATR (> 2.5%)
    b5 = gaps[gaps['atr_pct'] >= 2.5]
    print(f"High ATR (>=2.5%): {len(b5)} cases | Win Rate: {b5['target_long_win'].mean()*100:.2f}% | Avg Day Return: {b5['today_return'].mean():+.2f}%")
    
    # 6. Combined Super-Setup:
    # Gap >= 1.5% + Open >= 20d High + ATR >= 2.0% + prev_close_pos >= 0.7
    b_comb = gaps[(gaps['today_gap'] >= 1.5) & (gaps['dist_high20d'] >= 0) & (gaps['atr_pct'] >= 2.0) & (gaps['prev_close_pos'] >= 0.7)]
    print(f"\nCOMBINED SUPER-SETUP (Gap>=1.5% + 20d High Break + ATR>=2% + Strong Close):")
    print(f"  Count: {len(b_comb)} ({len(b_comb)/58:.1f}/mo) | Win Rate: {b_comb['target_long_win'].mean()*100:.2f}% | Avg Day Return: {b_comb['today_return'].mean():+.2f}%")

if __name__ == '__main__':
    analyze_predictive_features()
