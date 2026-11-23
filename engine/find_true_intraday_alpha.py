"""
Find the TRUE Intraday Alpha Engine on 4.8 Years of 5-Minute Bars (30 Stocks)
Testing:
1. Entry Trigger: 09:30 close vs Break of 15m High/Low vs Pullback to VWAP
2. Stop Loss: 50% midpoint vs 15m Low vs Breakout Candle Low
3. Targets: 1.5R/2.5R vs 2.0R/3.5R vs Trailing EMA
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
    
    print("Pre-loading 30 symbols...", flush=True)
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
            prev_close = d_df.iloc[-1]['Close']
            
            # Compute intraday VWAP
            typ = (d_df['High'] + d_df['Low'] + d_df['Close']) / 3.0
            cum_pv = (typ * d_df['Volume']).cumsum()
            cum_vol = d_df['Volume'].cumsum()
            d_df['vwap'] = np.where(cum_vol > 0, cum_pv / cum_vol, d_df['Close'])
            
            if int(d_str[:4]) >= 2022:
                all_dates.add(d_str)
                symbol_days[sym][d_str] = {
                    'df': d_df,
                    'high_15m': high_15m,
                    'low_15m': low_15m,
                    'mid_15m': (high_15m + low_15m) / 2.0,
                    'close_15m': close_15m,
                    'range_15m': range_15m,
                    'gap_pct': gap_pct,
                    'rvol': rvol
                }
                
    sorted_dates = sorted(list(all_dates))
    print(f"Loaded {len(sorted_dates)} trading dates.", flush=True)
    
    # Test matrix of configurations:
    configs = [
        # (entry_type, sl_type, t1_r, t2_r, move_be)
        ('09:30_CLOSE', 'MIDPOINT', 2.0, 3.5, True),
        ('BREAKOUT_CLOSE', 'MIDPOINT', 2.0, 3.5, True),
        ('BREAKOUT_CLOSE', 'RANGE_LOW', 1.5, 2.5, False),
        ('BREAKOUT_CLOSE', 'MIDPOINT', 1.5, 2.5, False),
        ('BREAKOUT_CLOSE', 'VWAP', 1.5, 3.0, False),
        ('VWAP_PULLBACK', 'MIDPOINT', 2.0, 3.5, False),
    ]
    
    for cfg in configs:
        e_type, sl_type, t1_r, t2_r, move_be = cfg
        trades = []
        risk_cash = 1000.0
        
        for date_str in sorted_dates:
            candidates = []
            for sym, d_dict in symbol_days.items():
                if date_str not in d_dict: continue
                info = d_dict[date_str]
                gap_pct = info['gap_pct']
                rvol = info['rvol']
                h15 = info['high_15m']
                l15 = info['low_15m']
                m15 = info['mid_15m']
                c15 = info['close_15m']
                d_df = info['df']
                
                if abs(gap_pct) < 1.0 or rvol < 2.0: continue
                score = rvol * (1.0 + abs(gap_pct))
                
                if e_type == '09:30_CLOSE':
                    entry_p = c15
                    raw_sl = m15 if sl_type == 'MIDPOINT' else l15
                    if gap_pct >= 1.0:
                        risk_pts = max(entry_p * 0.0035, min(entry_p * 0.010, entry_p - raw_sl))
                        candidates.append({'symbol': sym, 'side': 'BUY', 'b_idx': 2, 'entry_p': entry_p, 'sl_p': entry_p - risk_pts, 'risk_pts': risk_pts, 'score': score, 'df': d_df})
                    else:
                        risk_pts = max(entry_p * 0.0035, min(entry_p * 0.010, raw_sl - entry_p))
                        candidates.append({'symbol': sym, 'side': 'SELL', 'b_idx': 2, 'entry_p': entry_p, 'sl_p': entry_p + risk_pts, 'risk_pts': risk_pts, 'score': score, 'df': d_df})
                elif e_type == 'BREAKOUT_CLOSE':
                    if gap_pct >= 1.0:
                        for b_i in range(3, min(14, len(d_df) - 6)):
                            bar = d_df.iloc[b_i]
                            if bar['Close'] > h15 and bar['Close'] > bar['vwap']:
                                entry_p = bar['Close']
                                if sl_type == 'MIDPOINT': raw_sl = m15
                                elif sl_type == 'RANGE_LOW': raw_sl = l15
                                elif sl_type == 'VWAP': raw_sl = bar['vwap']
                                risk_pts = max(entry_p * 0.0035, min(entry_p * 0.010, entry_p - raw_sl))
                                candidates.append({'symbol': sym, 'side': 'BUY', 'b_idx': b_i, 'entry_p': entry_p, 'sl_p': entry_p - risk_pts, 'risk_pts': risk_pts, 'score': score, 'df': d_df})
                                break
                    elif gap_pct <= -1.0:
                        for b_i in range(3, min(14, len(d_df) - 6)):
                            bar = d_df.iloc[b_i]
                            if bar['Close'] < l15 and bar['Close'] < bar['vwap']:
                                entry_p = bar['Close']
                                if sl_type == 'MIDPOINT': raw_sl = m15
                                elif sl_type == 'RANGE_LOW': raw_sl = h15
                                elif sl_type == 'VWAP': raw_sl = bar['vwap']
                                risk_pts = max(entry_p * 0.0035, min(entry_p * 0.010, raw_sl - entry_p))
                                candidates.append({'symbol': sym, 'side': 'SELL', 'b_idx': b_i, 'entry_p': entry_p, 'sl_p': entry_p + risk_pts, 'risk_pts': risk_pts, 'score': score, 'df': d_df})
                                break
                elif e_type == 'VWAP_PULLBACK':
                    # Wait for gap, then enter on touch of VWAP
                    if gap_pct >= 1.0:
                        for b_i in range(3, min(18, len(d_df) - 6)):
                            bar = d_df.iloc[b_i]
                            if bar['Low'] <= bar['vwap'] and bar['Close'] >= bar['vwap']:
                                entry_p = bar['vwap']
                                raw_sl = l15
                                risk_pts = max(entry_p * 0.0035, min(entry_p * 0.010, entry_p - raw_sl))
                                candidates.append({'symbol': sym, 'side': 'BUY', 'b_idx': b_i, 'entry_p': entry_p, 'sl_p': entry_p - risk_pts, 'risk_pts': risk_pts, 'score': score, 'df': d_df})
                                break
                    elif gap_pct <= -1.0:
                        for b_i in range(3, min(18, len(d_df) - 6)):
                            bar = d_df.iloc[b_i]
                            if bar['High'] >= bar['vwap'] and bar['Close'] <= bar['vwap']:
                                entry_p = bar['vwap']
                                raw_sl = h15
                                risk_pts = max(entry_p * 0.0035, min(entry_p * 0.010, raw_sl - entry_p))
                                candidates.append({'symbol': sym, 'side': 'SELL', 'b_idx': b_i, 'entry_p': entry_p, 'sl_p': entry_p + risk_pts, 'risk_pts': risk_pts, 'score': score, 'df': d_df})
                                break
                                
            if not candidates: continue
            candidates.sort(key=lambda x: -x['score'])
            t = candidates[0]
            
            entry_p = t['entry_p']
            sl_p = t['sl_p']
            risk_pts = t['risk_pts']
            d_df = t['df']
            side = t['side']
            b_idx = t['b_idx']
            
            shares = int(risk_cash / risk_pts)
            if shares < 1: shares = 1
            s_t1 = int(shares * 0.50)
            s_run = shares - s_t1
            if s_t1 < 1: s_t1 = 1
            
            t1_p = entry_p + (t1_r * risk_pts) if side == 'BUY' else entry_p - (t1_r * risk_pts)
            t2_p = entry_p + (t2_r * risk_pts) if side == 'BUY' else entry_p - (t2_r * risk_pts)
            
            t1_hit = False
            curr_sl = sl_p
            exit_p1, exit_pr = 0.0, 0.0
            
            for j in range(b_idx + 1, len(d_df)):
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
                        if move_be: curr_sl = entry_p
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
                        if move_be: curr_sl = entry_p
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
            trades.append({'ret_pct': net_pnl / 1000.0, 'year': int(date_str[:4])})
            
        df_res = pd.DataFrame(trades)
        total_ret = df_res['ret_pct'].sum()
        win_rate = (df_res['ret_pct'] > 0).mean() * 100.0
        wins = df_res[df_res['ret_pct'] > 0]
        losses = df_res[df_res['ret_pct'] <= 0]
        gw = wins['ret_pct'].sum()
        gl = abs(losses['ret_pct'].sum())
        pf = gw / gl if gl > 0 else 999.0
        
        df_res['cum'] = df_res['ret_pct'].cumsum()
        df_res['peak'] = df_res['cum'].cummax()
        df_res['dd'] = df_res['cum'] - df_res['peak']
        max_dd = df_res['dd'].min()
        
        print(f"\nCFG: Entry={e_type} | SL={sl_type} | T1={t1_r}R | T2={t2_r}R | MoveBE={move_be}:")
        print(f"  Trades: {len(df_res)} | WinRate: {win_rate:.2f}% | PF: {pf:.2f} | Net: {total_ret:+.2f}% | MaxDD: {max_dd:.2f}%")

if __name__ == '__main__':
    main()
