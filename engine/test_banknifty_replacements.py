import sys
sys.path.append('engine')
import os
import pandas as pd
import numpy as np
from datetime import time
from nifty_alpha_explorer import load_nifty_fast
from nifty_aligned_ema_atr_sweep import load_stock_data, get_nifty_trend_series, resample_and_calc_indicators, backtest_ema_atr_pullback

print("Loading Nifty 50 for Macro Trend...")
nifty_1m = load_nifty_fast()
nifty_trend = get_nifty_trend_series(nifty_1m, tf_min=5)

# The 5 Core Anchor Stocks
core_stocks = ['RELIANCE', 'MARUTI', 'SUNPHARMA', 'TATAMOTORS', 'TCS']
core_trades = {}
for s in core_stocks:
    print(f"Loading {s}...")
    d = load_stock_data(s)
    df_5m = resample_and_calc_indicators(d, 5)
    core_trades[s] = backtest_ema_atr_pullback(df_5m, nifty_trend, s, target_rr=3.0)

# Potential Replacements for Bank Nifty
candidates = ['TATASTEEL', 'LT', 'ADANIENT', 'INFY', 'BAJFINANCE', 'SBIN']
candidate_results = []

for cand in candidates:
    print(f"Evaluating Replacement: {cand}...")
    d = load_stock_data(cand)
    df_5m = resample_and_calc_indicators(d, 5)
    t_cand = backtest_ema_atr_pullback(df_5m, nifty_trend, cand, target_rr=3.0)
    
    # Combine 5 Core + Candidate
    basket_trades = []
    for s in core_stocks:
        basket_trades.extend(core_trades[s])
    basket_trades.extend(t_cand)
    
    df_all = pd.DataFrame(basket_trades).sort_values(['Date', 'Time']).reset_index(drop=True)
    df_all['Date'] = pd.to_datetime(df_all['Date'])
    df_all['YM'] = df_all['Date'].dt.to_period('M')
    
    tot_r = df_all['R'].sum()
    num_m = df_all['YM'].nunique()
    r_m = tot_r / num_m
    cum = df_all['R'].cumsum()
    max_dd = (cum - cum.cummax()).min()
    wr = (df_all['R'] > 0).mean() * 100
    wins = df_all[df_all['R'] > 0]['R'].sum()
    losses = abs(df_all[df_all['R'] < 0]['R'].sum())
    pf = wins / losses
    calmar = (r_m * 12) / abs(max_dd)
    
    # Calculate Cand stats alone
    df_c = pd.DataFrame(t_cand)
    tot_r_c = df_c['R'].sum()
    wr_c = (df_c['R'] > 0).mean() * 100
    cum_c = df_c['R'].cumsum()
    dd_c = (cum_c - cum_c.cummax()).min()
    
    candidate_results.append({
        'Replacement_Stock': cand,
        'Stock_Alone_R': round(tot_r_c, 1),
        'Stock_Alone_WR': round(wr_c, 1),
        'Stock_Alone_DD': round(dd_c, 1),
        'Total_Basket_Trades': len(df_all),
        'Basket_WinRate': round(wr, 2),
        'Basket_Total_R': round(tot_r, 1),
        'Basket_Monthly_R': round(r_m, 2),
        'Basket_Max_DD': round(max_dd, 1),
        'Basket_PF': round(pf, 2),
        'Basket_Calmar': round(calmar, 2)
    })

df_res = pd.DataFrame(candidate_results).sort_values('Basket_Total_R', ascending=False)
print("\n" + "="*85)
print("             REPLACING BANK NIFTY: CANDIDATE COMPARISON TABLE")
print("="*85)
print(df_res.to_string(index=False))
