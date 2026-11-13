import sys
sys.path.append('engine')
import os
import pandas as pd
import numpy as np
import datetime
from datetime import time
from nifty_alpha_explorer import load_nifty_fast, resample_nifty
from portfolio_synergy import load_bnf
from nifty_aligned_ema_atr_sweep import load_stock_data, get_nifty_trend_series, resample_and_calc_indicators, backtest_ema_atr_pullback

def test_top_basket_allocations():
    print("Loading Nifty 50...")
    nifty_1m = load_nifty_fast()
    nifty_trend = get_nifty_trend_series(nifty_1m, tf_min=5)
    
    # Pick top diversified champions across sectors:
    # Reliance (Energy), Maruti (Auto), SunPharma (Pharma), TataMotors (Auto), TCS (IT), BankNifty (Banking)
    basket = ['RELIANCE', 'MARUTI', 'SUNPHARMA', 'TATAMOTORS', 'TCS', 'BANKNIFTY']
    
    trades_by_stock = {}
    for sym in basket:
        print(f"Loading and backtesting {sym}...")
        df_1m = load_bnf() if sym == 'BANKNIFTY' else load_stock_data(sym)
        df_5m = resample_and_calc_indicators(df_1m, tf_min=5)
        # Test 1:3.0 RR
        t = backtest_ema_atr_pullback(df_5m, nifty_trend, sym, target_rr=3.0)
        trades_by_stock[sym] = t
        
        df_t = pd.DataFrame(t)
        df_t['Date'] = pd.to_datetime(df_t['Date'])
        df_t['YM'] = df_t['Date'].dt.to_period('M')
        tot_r = df_t['R'].sum()
        r_m = tot_r / df_t['YM'].nunique()
        cum = df_t['R'].cumsum()
        max_dd = (cum - cum.cummax()).min()
        print(f"  {sym:12s} => Trades: {len(df_t)} | Total R: {tot_r:+.1f} | Monthly R: {r_m:+.2f} R/mo | Max DD: {max_dd:.1f} R")

    # Combine all trades
    all_trades = []
    for sym, t_list in trades_by_stock.items():
        all_trades.extend(t_list)
        
    df_all = pd.DataFrame(all_trades).sort_values(['Date', 'Time']).reset_index(drop=True)
    df_all['Date'] = pd.to_datetime(df_all['Date'])
    
    print("\n" + "="*85)
    print("         DIVERSIFIED TOP BASKET PORTFOLIO BACKTEST")
    print("="*85)
    
    # Mode 1: Pure Unconstrained Execution (Every stock trades independently with its own 1-loss stop)
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
    
    print("\n--- MODE 1: INDEPENDENT ASSET EXECUTION (No Cross-Asset Lockout) ---")
    print(f"Total Trades: {len(df_all)} across {num_m} months")
    print(f"Win Rate: {wr:.1f}% | Profit Factor: {pf:.2f}")
    print(f"Total Cumulative Return: {tot_r:+.1f} R")
    print(f"AVERAGE MONTHLY RETURN:  {r_m:+.2f} R / MONTH")
    print(f"MAXIMUM DRAWDOWN:        {max_dd:.1f} R")
    print(f"Calmar Ratio:            {(r_m * 12) / abs(max_dd):.2f}")
    
    # Mode 2: Portfolio Daily Stop (Max 2 Losses / Day Across Portfolio)
    for max_l in [2, 3, 4]:
        filtered = []
        for dt, grp in df_all.groupby('Date'):
            dl = 0
            for idx, r in grp.iterrows():
                if dl >= max_l: break
                filtered.append(r)
                if r['R'] < 0: dl += 1
                
        df_p = pd.DataFrame(filtered)
        tot_r_p = df_p['R'].sum()
        r_m_p = tot_r_p / num_m
        cum_p = df_p['R'].cumsum()
        max_dd_p = (cum_p - cum_p.cummax()).min()
        wr_p = (df_p['R'] > 0).mean() * 100
        wins_p = df_p[df_p['R'] > 0]['R'].sum()
        losses_p = abs(df_p[df_p['R'] < 0]['R'].sum())
        pf_p = wins_p / losses_p
        
        print(f"\n--- MODE 2: PORTFOLIO STOP (Max {max_l} Portfolio Losses/Day) ---")
        print(f"Trades: {len(df_p)} | WR: {wr_p:.1f}% | Profit Factor: {pf_p:.2f}")
        print(f"Total Return: {tot_r_p:+.1f} R | Monthly Return: {r_m_p:+.2f} R/month | Max DD: {max_dd_p:.1f} R")

    # Mode 3: Test adding 2 more high-alpha stocks (Adani Enterprises + Tata Steel) to cross 20+ R/mo
    print("\n" + "="*85)
    print("         EXPANDING BASKET TO 8 STOCKS TO HIT 20+ R / MONTH")
    print("="*85)
    for extra in ['ADANIENT', 'TATASTEEL']:
        df_1m = load_stock_data(extra)
        df_5m = resample_and_calc_indicators(df_1m, tf_min=5)
        t = backtest_ema_atr_pullback(df_5m, nifty_trend, extra, target_rr=3.0)
        trades_by_stock[extra] = t
        
    all_trades_8 = []
    for sym, t_list in trades_by_stock.items():
        all_trades_8.extend(t_list)
    df_8 = pd.DataFrame(all_trades_8).sort_values(['Date', 'Time']).reset_index(drop=True)
    df_8['Date'] = pd.to_datetime(df_8['Date'])
    df_8['YM'] = df_8['Date'].dt.to_period('M')
    
    tot_r_8 = df_8['R'].sum()
    r_m_8 = tot_r_8 / num_m
    cum_8 = df_8['R'].cumsum()
    max_dd_8 = (cum_8 - cum_8.cummax()).min()
    wr_8 = (df_8['R'] > 0).mean() * 100
    wins_8 = df_8[df_8['R'] > 0]['R'].sum()
    losses_8 = abs(df_8[df_8['R'] < 0]['R'].sum())
    pf_8 = wins_8 / losses_8
    
    print("\n--- 8-STOCK BASKET INDEPENDENT EXECUTION ---")
    print(f"Total Trades: {len(df_8)} across {num_m} months")
    print(f"Win Rate: {wr_8:.1f}% | Profit Factor: {pf_8:.2f}")
    print(f"Total Cumulative Return: {tot_r_8:+.1f} R")
    print(f"AVERAGE MONTHLY RETURN:  {r_m_8:+.2f} R / MONTH")
    print(f"MAXIMUM DRAWDOWN:        {max_dd_8:.1f} R")

    # Mode 4: Portfolio Stop on 8 stocks
    for max_l in [2, 3, 4]:
        filtered = []
        for dt, grp in df_8.groupby('Date'):
            dl = 0
            for idx, r in grp.iterrows():
                if dl >= max_l: break
                filtered.append(r)
                if r['R'] < 0: dl += 1
                
        df_p = pd.DataFrame(filtered)
        tot_r_p = df_p['R'].sum()
        r_m_p = tot_r_p / num_m
        cum_p = df_p['R'].cumsum()
        max_dd_p = (cum_p - cum_p.cummax()).min()
        wr_p = (df_p['R'] > 0).mean() * 100
        wins_p = df_p[df_p['R'] > 0]['R'].sum()
        losses_p = abs(df_p[df_p['R'] < 0]['R'].sum())
        pf_p = wins_p / losses_p
        
        print(f"MaxLoss={max_l} => Trades: {len(df_p)} | WR: {wr_p:.1f}% | Monthly: {r_m_p:+.2f} R/mo | Max DD: {max_dd_p:.1f} R | PF: {pf_p:.2f}")

if __name__ == '__main__':
    test_top_basket_allocations()
