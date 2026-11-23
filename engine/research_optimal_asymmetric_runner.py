"""
Optimal Asymmetric Runner Engine for Pure NSE Cash Equities
Testing Multi-Target Scaling on A+ High Conviction Setups
Goal: Maximize Net R per trade after exact Zerodha statutory tariffs.
"""

import os
import glob
import numpy as np
import pandas as pd
from datetime import datetime

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
    prev_file = f"data/stocks/{symbol}_prev.parquet"
    curr_file = f"data/stocks/{symbol}_2026.parquet"
    dfs = []
    if os.path.exists(prev_file):
        dfs.append(pd.read_parquet(prev_file))
    if os.path.exists(curr_file):
        dfs.append(pd.read_parquet(curr_file))
    if not dfs:
        return None
        
    df = pd.concat(dfs, ignore_index=True)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df[df['Date'].dt.year >= 2021].sort_values('Date').reset_index(drop=True)
    df.set_index('Date', inplace=True)
    
    t_start = datetime.strptime("09:15", "%H:%M").time()
    t_end = datetime.strptime("15:30", "%H:%M").time()
    
    df_5m = df.resample('5min').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }).dropna().reset_index()
    
    df_5m['time'] = df_5m['Date'].dt.time
    df_5m = df_5m[(df_5m['time'] >= t_start) & (df_5m['time'] <= t_end)].reset_index(drop=True)
    df_5m['date_str'] = df_5m['Date'].dt.strftime('%Y-%m-%d')
    return df_5m

def test_runner_variation(t1_pct=0.30, t1_r=2.0, t2_pct=0.30, t2_r=4.0, run_pct=0.40):
    symbols = [
        'ADANIENT', 'AXISBANK', 'BAJFINANCE', 'BHARTIARTL', 'COALINDIA', 
        'GRASIM', 'HCLTECH', 'HDFCBANK', 'HINDUNILVR', 'ICICIBANK', 
        'INDUSINDBK', 'INFY', 'ITC', 'JSWSTEEL', 'KOTAKBANK', 
        'LT', 'MARUTI', 'NTPC', 'ONGC', 'POWERGRID', 
        'RELIANCE', 'SBIN', 'SUNPHARMA', 'TATAMOTORS', 'TATASTEEL', 
        'TCS', 'TECHM', 'TITAN', 'ULTRACEMCO', 'WIPRO'
    ]
    
    all_dates = set()
    symbol_days = {}
    
    for sym in symbols:
        df = load_symbol_5m(sym)
        if df is None or len(df) == 0:
            continue
            
        symbol_days[sym] = {}
        grouped = df.groupby('date_str')
        prev_close = None
        or_vols = []
        closes_20 = []
        
        for d_str, d_df in grouped:
            d_df = d_df.reset_index(drop=True)
            if len(d_df) < 25:
                if len(d_df) > 0:
                    prev_close = d_df.iloc[-1]['Close']
                continue
                
            open_p = d_df.iloc[0]['Open']
            close_p = d_df.iloc[-1]['Close']
            
            # OR (first 3 bars)
            or_bars = d_df.iloc[0:3]
            or_h = or_bars['High'].max()
            or_l = or_bars['Low'].min()
            or_v = or_bars['Volume'].sum()
            
            gap_pct = 0.0
            if prev_close is not None and prev_close > 0:
                gap_pct = (open_p - prev_close) / prev_close * 100.0
                
            rvol = 1.0
            if len(or_vols) >= 10:
                avg_v = np.mean(or_vols[-20:])
                if avg_v > 0:
                    rvol = or_v / avg_v
            or_vols.append(or_v)
            
            bo20_l = False
            bo20_s = False
            if len(closes_20) >= 20:
                r20 = closes_20[-20:]
                if open_p > max(r20): bo20_l = True
                if open_p < min(r20): bo20_s = True
            closes_20.append(close_p)
            prev_close = close_p
            
            typ = (d_df['High'] + d_df['Low'] + d_df['Close']) / 3.0
            cum_pv = (typ * d_df['Volume']).cumsum()
            cum_vol = d_df['Volume'].cumsum()
            vwap = np.where(cum_vol > 0, cum_pv / cum_vol, d_df['Close'])
            ema9 = d_df['Close'].ewm(span=9, adjust=False).mean().values
            d_df['vwap'] = vwap
            d_df['ema9'] = ema9
            
            year = int(d_str[:4])
            if year >= 2022:
                all_dates.add(d_str)
                symbol_days[sym][d_str] = {
                    'df': d_df,
                    'or_h': or_h,
                    'or_l': or_l,
                    'or_mid': (or_h + or_l) / 2.0,
                    'gap_pct': gap_pct,
                    'rvol': rvol,
                    'bo20_l': bo20_l,
                    'bo20_s': bo20_s
                }
                
    sorted_dates = sorted(list(all_dates))
    trades = []
    
    for date_str in sorted_dates:
        candidates = []
        for sym, d_dict in symbol_days.items():
            if date_str not in d_dict: continue
            day_info = d_dict[date_str]
            d_df = day_info['df']
            or_h = day_info['or_h']
            or_l = day_info['or_l']
            or_mid = day_info['or_mid']
            gap_pct = day_info['gap_pct']
            rvol = day_info['rvol']
            bo20_l = day_info['bo20_l']
            bo20_s = day_info['bo20_s']
            
            long_cat = (gap_pct >= 0.5 and rvol >= 1.8) or (rvol >= 2.5 and gap_pct >= 0.2) or (bo20_l and rvol >= 1.5)
            short_cat = (gap_pct <= -0.5 and rvol >= 1.8) or (rvol >= 2.5 and gap_pct <= -0.2) or (bo20_s and rvol >= 1.5)
            if not long_cat and not short_cat: continue
            
            for b_i in range(3, min(16, len(d_df) - 6)):
                bar = d_df.iloc[b_i]
                b_c = bar['Close']
                b_h = bar['High']
                b_l = bar['Low']
                vwap_v = bar['vwap']
                
                if long_cat and (b_c > or_h) and (b_c > vwap_v):
                    c_range = b_h - b_l
                    if c_range > 0 and (b_h - b_c) / c_range > 0.25: continue
                    raw_stop = max(or_mid, b_l)
                    if (b_c - raw_stop) / b_c < 0.0030: raw_stop = b_c * (1.0 - 0.0030)
                    if (b_c - raw_stop) / b_c > 0.0085: raw_stop = b_c * (1.0 - 0.0085)
                    risk_pts = b_c - raw_stop
                    if risk_pts <= 0: continue
                    score = rvol * (1.0 + abs(gap_pct))
                    candidates.append({
                        'symbol': sym,
                        'side': 'BUY',
                        'bar_idx': b_i,
                        'entry_price': b_c,
                        'stop_loss': raw_stop,
                        'risk_pts': risk_pts,
                        'score': score,
                        'df': d_df
                    })
                    break
                    
                elif short_cat and (b_c < or_l) and (b_c < vwap_v):
                    c_range = b_h - b_l
                    if c_range > 0 and (b_c - b_l) / c_range > 0.25: continue
                    raw_stop = min(or_mid, b_h)
                    if (raw_stop - b_c) / b_c < 0.0030: raw_stop = b_c * (1.0 + 0.0030)
                    if (raw_stop - b_c) / b_c > 0.0085: raw_stop = b_c * (1.0 + 0.0085)
                    risk_pts = raw_stop - b_c
                    if risk_pts <= 0: continue
                    score = rvol * (1.0 + abs(gap_pct))
                    candidates.append({
                        'symbol': sym,
                        'side': 'SELL',
                        'bar_idx': b_i,
                        'entry_price': b_c,
                        'stop_loss': raw_stop,
                        'risk_pts': risk_pts,
                        'score': score,
                        'df': d_df
                    })
                    break
                    
        if not candidates: continue
        # Take ONLY #1 Trade of the day
        candidates.sort(key=lambda x: -x['score'])
        trade = candidates[0]
        
        sym = trade['symbol']
        side = trade['side']
        entry_p = trade['entry_price']
        sl = trade['stop_loss']
        risk_pts = trade['risk_pts']
        d_df = trade['df']
        b_idx = trade['bar_idx']
        
        # 1% risk = Rs 1,000 on Rs 1,00,000
        shares = int(1000.0 / risk_pts)
        if shares < 1: shares = 1
        
        s1 = int(shares * t1_pct)
        s2 = int(shares * t2_pct)
        sr = shares - s1 - s2
        if s1 < 1: s1 = 1
        
        t1_p = entry_p + (t1_r * risk_pts) if side == 'BUY' else entry_p - (t1_r * risk_pts)
        t2_p = entry_p + (t2_r * risk_pts) if side == 'BUY' else entry_p - (t2_r * risk_pts)
        
        t1_hit, t2_hit = False, False
        curr_sl = sl
        exit_p1, exit_p2, exit_pr = 0.0, 0.0, 0.0
        
        if side == 'BUY':
            for j in range(b_idx + 1, len(d_df)):
                f_bar = d_df.iloc[j]
                f_h, f_l, f_c = f_bar['High'], f_bar['Low'], f_bar['Close']
                ema_v = f_bar['ema9']
                
                if f_l <= curr_sl:
                    if not t1_hit:
                        exit_p1, exit_p2, exit_pr = curr_sl, curr_sl, curr_sl
                    elif not t2_hit:
                        exit_p2, exit_pr = curr_sl, curr_sl
                    else:
                        exit_pr = curr_sl
                    break
                    
                if not t1_hit and f_h >= t1_p:
                    t1_hit = True
                    exit_p1 = t1_p
                    curr_sl = entry_p # BE
                    
                if t1_hit and not t2_hit and f_h >= t2_p:
                    t2_hit = True
                    exit_p2 = t2_p
                    curr_sl = entry_p + (1.5 * risk_pts)
                    
                if t2_hit and j >= 45:
                    if f_c < ema_v:
                        exit_pr = f_c
                        break
                        
                if j == len(d_df) - 1 or j >= 72:
                    if not t1_hit: exit_p1 = f_c
                    if not t2_hit: exit_p2 = f_c
                    exit_pr = f_c
                    break
                    
            p1 = s1 * (exit_p1 - entry_p)
            f1 = compute_zerodha_charges(s1 * entry_p, s1 * exit_p1)
            p2 = s2 * (exit_p2 - entry_p) if s2 > 0 else 0
            f2 = compute_zerodha_charges(s2 * entry_p, s2 * exit_p2) if s2 > 0 else 0
            pr = sr * (exit_pr - entry_p) if sr > 0 else 0
            fr = compute_zerodha_charges(sr * entry_p, sr * exit_pr) if sr > 0 else 0
            
        else: # SHORT
            for j in range(b_idx + 1, len(d_df)):
                f_bar = d_df.iloc[j]
                f_h, f_l, f_c = f_bar['High'], f_bar['Low'], f_bar['Close']
                ema_v = f_bar['ema9']
                
                if f_h >= curr_sl:
                    if not t1_hit:
                        exit_p1, exit_p2, exit_pr = curr_sl, curr_sl, curr_sl
                    elif not t2_hit:
                        exit_p2, exit_pr = curr_sl, curr_sl
                    else:
                        exit_pr = curr_sl
                    break
                    
                if not t1_hit and f_l <= t1_p:
                    t1_hit = True
                    exit_p1 = t1_p
                    curr_sl = entry_p
                    
                if t1_hit and not t2_hit and f_l <= t2_p:
                    t2_hit = True
                    exit_p2 = t2_p
                    curr_sl = entry_p - (1.5 * risk_pts)
                    
                if t2_hit and j >= 45:
                    if f_c > ema_v:
                        exit_pr = f_c
                        break
                        
                if j == len(d_df) - 1 or j >= 72:
                    if not t1_hit: exit_p1 = f_c
                    if not t2_hit: exit_p2 = f_c
                    exit_pr = f_c
                    break
                    
            p1 = s1 * (entry_p - exit_p1)
            f1 = compute_zerodha_charges(s1 * exit_p1, s1 * entry_p)
            p2 = s2 * (entry_p - exit_p2) if s2 > 0 else 0
            f2 = compute_zerodha_charges(s2 * exit_p2, s2 * entry_p) if s2 > 0 else 0
            pr = sr * (entry_p - exit_pr) if sr > 0 else 0
            fr = compute_zerodha_charges(sr * exit_p2, sr * entry_p) if sr > 0 else 0
            
        gross_pnl = p1 + p2 + pr
        fee = f1 + f2 + fr
        net_pnl = gross_pnl - fee
        net_r = net_pnl / 1000.0
        trades.append({'date': date_str, 'net_r': net_r, 'fee': fee, 'net_pnl': net_pnl})
        
    df_trades = pd.DataFrame(trades)
    df_trades['month'] = pd.to_datetime(df_trades['date']).dt.to_period('M')
    n_months = df_trades['month'].nunique()
    wins = df_trades[df_trades['net_r'] > 0]
    losses = df_trades[df_trades['net_r'] <= 0]
    win_rate = len(wins) / len(df_trades) * 100.0 if len(df_trades) > 0 else 0
    total_net_r = df_trades['net_r'].sum()
    monthly_r = total_net_r / max(1, n_months)
    
    df_trades['cum_r'] = df_trades['net_r'].cumsum()
    df_trades['peak_r'] = df_trades['cum_r'].cummax()
    df_trades['dd_r'] = df_trades['cum_r'] - df_trades['peak_r']
    max_dd_r = df_trades['dd_r'].min()
    
    gross_win = wins['net_pnl'].sum()
    gross_loss = abs(losses['net_pnl'].sum())
    profit_factor = gross_win / gross_loss if gross_loss > 0 else 999.0
    
    print(f"Config [{t1_pct*100:.0f}%@{t1_r}R | {t2_pct*100:.0f}%@{t2_r}R | {run_pct*100:.0f}%@Run]:", flush=True)
    print(f"  Trades: {len(df_trades)} ({len(df_trades)/n_months:.1f}/mo) | Win Rate: {win_rate:.2f}% | PF: {profit_factor:.2f}", flush=True)
    print(f"  Total Return: {total_net_r:+.2f}% (+{total_net_r:.2f} R) | Monthly: {monthly_r:+.2f}% / mo | Max DD: {max_dd_r:.2f}%\n", flush=True)

if __name__ == '__main__':
    print("Testing Asymmetric Scaling Variations for NSE Cash Equities...\n")
    test_runner_variation(t1_pct=0.40, t1_r=2.0, t2_pct=0.30, t2_r=3.5, run_pct=0.30)
    test_runner_variation(t1_pct=0.30, t1_r=2.0, t2_pct=0.30, t2_r=4.0, run_pct=0.40)
    test_runner_variation(t1_pct=0.25, t1_r=2.5, t2_pct=0.25, t2_r=5.0, run_pct=0.50)
