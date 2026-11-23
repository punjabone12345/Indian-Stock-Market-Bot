"""
Forensic Side-by-Side: Daily Bar Approximation vs True 5-Minute Intraday Execution
Evaluating the EXACT SAME 30 Stocks over the EXACT SAME 4.8 Years (2022-2026, 1,180 trading sessions).
"""

import os
import glob
import numpy as np
import pandas as pd
from datetime import time

def compute_zerodha_charges(buy_val, sell_val):
    b_buy = min(20.0, buy_val * 0.0003)
    b_sell = min(20.0, sell_val * 0.0003)
    brokerage = b_buy + b_sell
    stt = sell_val * 0.00025
    exchange = (buy_val + sell_val) * 0.0000297
    sebi = (buy_val + sell_val) * 0.000001
    stamp = buy_val * 0.00003
    gst = (brokerage + exchange + sebi) * 0.18
    return brokerage + stt + exchange + sebi + stamp + gst

def load_symbol_5m(symbol):
    p_prev = f"data/stocks/{symbol}_prev.parquet"
    p_2026 = f"data/stocks/{symbol}_2026.parquet"
    dfs = []
    if os.path.exists(p_prev): dfs.append(pd.read_parquet(p_prev))
    if os.path.exists(p_2026): dfs.append(pd.read_parquet(p_2026))
    if not dfs: return None
    df = pd.concat(dfs, ignore_index=True)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df[df['Date'].dt.year >= 2021].sort_values('Date').reset_index(drop=True)
    df.set_index('Date', inplace=True)
    t_start, t_end = time(9, 15), time(15, 30)
    df_5m = df.resample('5min').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna().reset_index()
    df_5m['time'] = df_5m['Date'].dt.time
    df_5m = df_5m[(df_5m['time'] >= t_start) & (df_5m['time'] <= t_end)].reset_index(drop=True)
    df_5m['date_str'] = df_5m['Date'].dt.strftime('%Y-%m-%d')
    return df_5m

def main():
    symbols = [
        'ADANIENT', 'AXISBANK', 'BAJFINANCE', 'BHARTIARTL', 'COALINDIA', 
        'GRASIM', 'HCLTECH', 'HDFCBANK', 'HINDUNILVR', 'ICICIBANK', 
        'INDUSINDBK', 'INFY', 'ITC', 'JSWSTEEL', 'KOTAKBANK', 
        'LT', 'MARUTI', 'NTPC', 'ONGC', 'POWERGRID', 
        'RELIANCE', 'SBIN', 'SUNPHARMA', 'TATAMOTORS', 'TATASTEEL', 
        'TCS', 'TECHM', 'TITAN', 'ULTRACEMCO', 'WIPRO'
    ]
    
    print("Loading 30 symbols...", flush=True)
    symbol_days = {}
    all_dates = set()
    
    for sym in symbols:
        df = load_symbol_5m(sym)
        if df is None: continue
        symbol_days[sym] = {}
        grouped = df.groupby('date_str')
        prev_close = None
        or_vols = []
        
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
            
            day_high = d_df['High'].max()
            day_low = d_df['Low'].min()
            day_close = d_df.iloc[-1]['Close']
            
            prev_close = day_close
            
            if int(d_str[:4]) >= 2022:
                all_dates.add(d_str)
                symbol_days[sym][d_str] = {
                    'df_5m': d_df,
                    'open_15m': open_15m,
                    'high_15m': high_15m,
                    'low_15m': low_15m,
                    'mid_15m': (high_15m + low_15m) / 2.0,
                    'close_15m': close_15m,
                    'range_15m': range_15m,
                    'gap_pct': gap_pct,
                    'rvol': rvol,
                    'day_high': day_high,
                    'day_low': day_low,
                    'day_close': day_close
                }
                
    sorted_dates = sorted(list(all_dates))
    print(f"Total dates evaluated: {len(sorted_dates)} trading sessions across 30 mega-cap stocks.", flush=True)
    
    # -----------------------------------------------------------------
    # SIMULATION 1: DAILY BAR APPROXIMATION (What standard backtests do)
    # -----------------------------------------------------------------
    trades_daily = []
    risk_cash = 1000.0
    
    for date_str in sorted_dates:
        candidates = []
        for sym, d_dict in symbol_days.items():
            if date_str not in d_dict: continue
            info = d_dict[date_str]
            gap_pct = info['gap_pct']
            rvol = info['rvol']
            if abs(gap_pct) < 1.0 or rvol < 2.0: continue
            
            entry_p = info['close_15m']
            mid_p = info['mid_15m']
            sl_dist = max(entry_p * 0.0035, min(entry_p * 0.0085, abs(entry_p - mid_p)))
            score = rvol * (1.0 + abs(gap_pct))
            
            if gap_pct >= 1.0:
                candidates.append({
                    'symbol': sym, 'side': 'BUY', 'entry_p': entry_p, 'sl_p': entry_p - sl_dist,
                    'risk_pts': sl_dist, 'day_high': info['day_high'], 'day_low': info['day_low'],
                    'day_close': info['day_close'], 'score': score
                })
            elif gap_pct <= -1.0:
                candidates.append({
                    'symbol': sym, 'side': 'SELL', 'entry_p': entry_p, 'sl_p': entry_p + sl_dist,
                    'risk_pts': sl_dist, 'day_high': info['day_high'], 'day_low': info['day_low'],
                    'day_close': info['day_close'], 'score': score
                })
                
        if not candidates: continue
        candidates.sort(key=lambda x: -x['score'])
        trade = candidates[0]
        
        entry_p = trade['entry_p']
        sl_p = trade['sl_p']
        risk_pts = trade['risk_pts']
        h_p = trade['day_high']
        l_p = trade['day_low']
        c_p = trade['day_close']
        
        shares = int(risk_cash / risk_pts)
        if shares < 1: shares = 1
        s_t1 = int(shares * 0.50)
        s_run = shares - s_t1
        if s_t1 < 1: s_t1 = 1
        
        t1_p = entry_p + (2.5 * risk_pts) if trade['side'] == 'BUY' else entry_p - (2.5 * risk_pts)
        t2_p = entry_p + (4.5 * risk_pts) if trade['side'] == 'BUY' else entry_p - (4.5 * risk_pts)
        
        if trade['side'] == 'BUY':
            if l_p <= sl_p: exit_p1, exit_pr = sl_p, sl_p
            else:
                if h_p >= t1_p:
                    exit_p1 = t1_p
                    exit_pr = t2_p if h_p >= t2_p else c_p
                else: exit_p1, exit_pr = c_p, c_p
            p1 = s_t1 * (exit_p1 - entry_p)
            f1 = compute_zerodha_charges(s_t1 * entry_p, s_t1 * exit_p1)
            pr = s_run * (exit_pr - entry_p) if s_run > 0 else 0
            fr = compute_zerodha_charges(s_run * entry_p, s_run * exit_pr) if s_run > 0 else 0
        else:
            if h_p >= sl_p: exit_p1, exit_pr = sl_p, sl_p
            else:
                if l_p <= t1_p:
                    exit_p1 = t1_p
                    exit_pr = t2_p if l_p <= t2_p else c_p
                else: exit_p1, exit_pr = c_p, c_p
            p1 = s_t1 * (entry_p - exit_p1)
            f1 = compute_zerodha_charges(s_t1 * exit_p1, s_t1 * entry_p)
            pr = s_run * (entry_p - exit_pr) if s_run > 0 else 0
            fr = compute_zerodha_charges(s_run * exit_pr, s_run * entry_p) if s_run > 0 else 0
            
        net_pnl = p1 + pr - f1 - fr
        trades_daily.append({'ret_pct': net_pnl / 1000.0, 'year': int(date_str[:4])})
        
    df_d = pd.DataFrame(trades_daily)
    print(f"\n[METHOD 1: DAILY BAR APPROXIMATION] Total Trades: {len(df_d)} | Win Rate: {(df_d['ret_pct'] > 0).mean()*100:.2f}% | Total Net: {df_d['ret_pct'].sum():+.2f}%")
    print(df_d.groupby('year')['ret_pct'].agg(trades='count', win_rate=lambda x: (x > 0).mean()*100, total_ret='sum'))
    
    # -----------------------------------------------------------------
    # SIMULATION 2: TRUE 5-MINUTE BAR-BY-BAR (100% Real Intraday Sequence)
    # -----------------------------------------------------------------
    trades_5m = []
    for date_str in sorted_dates:
        candidates = []
        for sym, d_dict in symbol_days.items():
            if date_str not in d_dict: continue
            info = d_dict[date_str]
            gap_pct = info['gap_pct']
            rvol = info['rvol']
            if abs(gap_pct) < 1.0 or rvol < 2.0: continue
            
            entry_p = info['close_15m']
            mid_p = info['mid_15m']
            sl_dist = max(entry_p * 0.0035, min(entry_p * 0.0085, abs(entry_p - mid_p)))
            score = rvol * (1.0 + abs(gap_pct))
            
            if gap_pct >= 1.0:
                candidates.append({
                    'symbol': sym, 'side': 'BUY', 'entry_p': entry_p, 'sl_p': entry_p - sl_dist,
                    'risk_pts': sl_dist, 'df_5m': info['df_5m'], 'score': score
                })
            elif gap_pct <= -1.0:
                candidates.append({
                    'symbol': sym, 'side': 'SELL', 'entry_p': entry_p, 'sl_p': entry_p + sl_dist,
                    'risk_pts': sl_dist, 'df_5m': info['df_5m'], 'score': score
                })
                
        if not candidates: continue
        candidates.sort(key=lambda x: -x['score'])
        trade = candidates[0]
        
        entry_p = trade['entry_p']
        sl_p = trade['sl_p']
        risk_pts = trade['risk_pts']
        d_df = trade['df_5m']
        side = trade['side']
        
        shares = int(risk_cash / risk_pts)
        if shares < 1: shares = 1
        s_t1 = int(shares * 0.50)
        s_run = shares - s_t1
        if s_t1 < 1: s_t1 = 1
        
        t1_p = entry_p + (2.5 * risk_pts) if side == 'BUY' else entry_p - (2.5 * risk_pts)
        t2_p = entry_p + (4.5 * risk_pts) if side == 'BUY' else entry_p - (4.5 * risk_pts)
        
        t1_hit = False
        curr_sl = sl_p
        exit_p1, exit_pr = 0.0, 0.0
        
        # Exact Bar-by-bar sequence starting at bar 3 (09:30 AM)
        for j in range(3, len(d_df)):
            bar = d_df.iloc[j]
            h, l, c = bar['High'], bar['Low'], bar['Close']
            
            if side == 'BUY':
                if l <= curr_sl:
                    if not t1_hit: exit_p1, exit_pr = curr_sl, curr_sl
                    else: exit_pr = curr_sl
                    break
                if not t1_hit and h >= t1_p:
                    t1_hit = True
                    exit_p1 = t1_p
                    curr_sl = entry_p # Move SL to BE
                if t1_hit and h >= t2_p:
                    exit_pr = t2_p
                    break
                if j == len(d_df) - 1 or j >= 72:
                    if not t1_hit: exit_p1 = c
                    exit_pr = c
                    break
            else:
                if h >= curr_sl:
                    if not t1_hit: exit_p1, exit_pr = curr_sl, curr_sl
                    else: exit_pr = curr_sl
                    break
                if not t1_hit and l <= t1_p:
                    t1_hit = True
                    exit_p1 = t1_p
                    curr_sl = entry_p
                if t1_hit and l <= t2_p:
                    exit_pr = t2_p
                    break
                if j == len(d_df) - 1 or j >= 72:
                    if not t1_hit: exit_p1 = c
                    exit_pr = c
                    break
                    
        if side == 'BUY':
            p1 = s_t1 * (exit_p1 - entry_p)
            f1 = compute_zerodha_charges(s_t1 * entry_p, s_t1 * exit_p1)
            pr = s_run * (exit_pr - entry_p) if s_run > 0 else 0
            fr = compute_zerodha_charges(s_run * entry_p, s_run * exit_pr) if s_run > 0 else 0
        else:
            p1 = s_t1 * (entry_p - exit_p1)
            f1 = compute_zerodha_charges(s_t1 * exit_p1, s_t1 * entry_p)
            pr = s_run * (entry_p - exit_pr) if s_run > 0 else 0
            fr = compute_zerodha_charges(s_run * exit_pr, s_run * entry_p) if s_run > 0 else 0
            
        net_pnl = p1 + pr - f1 - fr
        trades_5m.append({'ret_pct': net_pnl / 1000.0, 'year': int(date_str[:4])})
        
    df_5 = pd.DataFrame(trades_5m)
    print(f"\n[METHOD 2: TRUE 5-MINUTE INTRADAY SEQUENCE] Total Trades: {len(df_5)} | Win Rate: {(df_5['ret_pct'] > 0).mean()*100:.2f}% | Total Net: {df_5['ret_pct'].sum():+.2f}%")
    print(df_5.groupby('year')['ret_pct'].agg(trades='count', win_rate=lambda x: (x > 0).mean()*100, total_ret='sum'))

if __name__ == '__main__':
    main()
