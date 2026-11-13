import sys
sys.path.append('engine')
import os
import pandas as pd
import numpy as np
from datetime import time
from nifty_alpha_explorer import load_nifty_fast
from nifty_aligned_ema_atr_sweep import load_stock_data, get_nifty_trend_series, resample_and_calc_indicators
from generate_pure_equity_audit import backtest_equity_detailed

print("Loading Nifty 50 macro trend...")
nifty_1m = load_nifty_fast()
nifty_trend = get_nifty_trend_series(nifty_1m, tf_min=5)

# Candidate top stocks to load
candidate_syms = ['RELIANCE', 'ITC', 'MARUTI', 'TATASTEEL', 'SUNPHARMA', 'LT', 'ADANIENT', 'INFY', 'TATAMOTORS', 'TCS', 'ULTRACEMCO']
cached_trades = {}

for sym in candidate_syms:
    print(f"Pre-calculating trades for {sym}...")
    df_1m = load_stock_data(sym)
    df_5m = resample_and_calc_indicators(df_1m, 5)
    t = backtest_equity_detailed(df_5m, nifty_trend, sym, target_rr=3.0)
    cached_trades[sym] = t

# Define baskets to compare
baskets = {
    'Previous 6-Stock Basket (Rel, Mar, Sun, TataMot, TCS, TataStl)': 
        ['RELIANCE', 'MARUTI', 'SUNPHARMA', 'TATAMOTORS', 'TCS', 'TATASTEEL'],
    'Elite Top 5 Champions (Rel, ITC, Mar, TataStl, Sun)': 
        ['RELIANCE', 'ITC', 'MARUTI', 'TATASTEEL', 'SUNPHARMA'],
    'Elite Top 6 Champions A (Rel, ITC, Mar, TataStl, Sun, LT)': 
        ['RELIANCE', 'ITC', 'MARUTI', 'TATASTEEL', 'SUNPHARMA', 'LT'],
    'Elite Top 6 Champions B (Rel, ITC, Mar, TataStl, Sun, AdaniEnt)': 
        ['RELIANCE', 'ITC', 'MARUTI', 'TATASTEEL', 'SUNPHARMA', 'ADANIENT'],
    'Elite Top 6 Champions C (Rel, ITC, Mar, TataStl, Sun, INFY)': 
        ['RELIANCE', 'ITC', 'MARUTI', 'TATASTEEL', 'SUNPHARMA', 'INFY'],
    'Titan 7-Stock Super Basket (Rel, ITC, Mar, TataStl, Sun, LT, AdaniEnt)': 
        ['RELIANCE', 'ITC', 'MARUTI', 'TATASTEEL', 'SUNPHARMA', 'LT', 'ADANIENT']
}

basket_results = []

for b_name, sym_list in baskets.items():
    combined_trades = []
    for s in sym_list:
        combined_trades.extend(cached_trades[s])
        
    df = pd.DataFrame(combined_trades).sort_values(['Date', 'EntryTime']).reset_index(drop=True)
    df['Date'] = pd.to_datetime(df['Date'])
    df['YM'] = df['Date'].dt.to_period('M')
    
    tot_trades = len(df)
    tot_r = df['R'].sum()
    num_m = df['YM'].nunique()
    r_m = tot_r / num_m
    wr = (df['R'] > 0).mean() * 100
    cum = df['R'].cumsum()
    max_dd = (cum - cum.cummax()).min()
    wins = df[df['R'] > 0]['R'].sum()
    losses = abs(df[df['R'] < 0]['R'].sum())
    pf = wins / losses
    calmar = (r_m * 12) / abs(max_dd)
    
    # Calculate Max Concurrent Positions
    df['EntryDateTime'] = pd.to_datetime(df['Date'].astype(str) + ' ' + df['EntryTime'].astype(str))
    df['ExitDateTime'] = pd.to_datetime(df['Date'].astype(str) + ' ' + df['ExitTime'].astype(str))
    events = []
    for idx, r in df.iterrows():
        events.append({'Time': r['EntryDateTime'], 'Type': 'ENTER'})
        events.append({'Time': r['ExitDateTime'], 'Type': 'EXIT'})
    df_ev = pd.DataFrame(events).sort_values(['Time', 'Type'], ascending=[True, False]).reset_index(drop=True)
    c_open, max_open = 0, 0
    for idx, ev in df_ev.iterrows():
        if ev['Type'] == 'ENTER': c_open += 1
        else: c_open -= 1
        if c_open > max_open: max_open = c_open
        
    basket_results.append({
        'Basket_Name': b_name,
        'Num_Stocks': len(sym_list),
        'Trades': tot_trades,
        'WinRate': round(wr, 2),
        'Total_Net_R': round(tot_r, 1),
        'Monthly_R': round(r_m, 2),
        'Max_DD': round(max_dd, 1),
        'ProfitFactor': round(pf, 2),
        'Calmar': round(calmar, 2),
        'Peak_Open_Pos': max_open
    })

df_baskets = pd.DataFrame(basket_results).sort_values('Total_Net_R', ascending=False)
print("\n" + "="*95)
print("             PORTFOLIO OPTIMIZATION: TOP RETURNING BASKET COMPARISON")
print("="*95)
print(df_baskets.to_string(index=False))
