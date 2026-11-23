"""
AUDIT VWAP PULLBACK RETEST EXECUTION REALISM (2022 - 2026)
Tests 3 execution models:
Model 1: Original Audit Engine (Entry = bar['vwap'] if Low <= vwap and Close >= vwap)
Model 2: Next Bar Open (Confirmed Close >= vwap, enter next bar Open + 0.03% slippage)
Model 3: Next Bar Limit at VWAP (Confirmed Close >= vwap, place limit at VWAP on next bar)
"""

import os, glob
import numpy as np
import pandas as pd
from datetime import time as dtime

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
    df = df[(df['Date'] >= '2021-11-01') & (df['Date'] <= '2026-10-31')].sort_values('Date').reset_index(drop=True)
    df.set_index('Date', inplace=True)
    t_start, t_end = dtime(9, 15), dtime(15, 30)
    df_5m = df.resample('5min').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna().reset_index()
    df_5m['time'] = df_5m['Date'].dt.time
    df_5m = df_5m[(df_5m['time'] >= t_start) & (df_5m['time'] <= t_end)].reset_index(drop=True)
    df_5m['date_str'] = df_5m['Date'].dt.strftime('%Y-%m-%d')
    df_5m['time_str'] = df_5m['Date'].dt.strftime('%H:%M:%S')
    
    df_5m['typ'] = (df_5m['High'] + df_5m['Low'] + df_5m['Close']) / 3.0
    df_5m['pv'] = df_5m['typ'] * df_5m['Volume']
    df_5m['cum_pv'] = df_5m.groupby('date_str')['pv'].cumsum()
    df_5m['cum_vol'] = df_5m.groupby('date_str')['Volume'].cumsum()
    df_5m['vwap'] = np.where(df_5m['cum_vol'] > 0, df_5m['cum_pv'] / df_5m['cum_vol'], df_5m['Close'])
    return df_5m

def run_test():
    symbols = [
        'ADANIENT', 'AXISBANK', 'BAJFINANCE', 'BHARTIARTL', 'COALINDIA', 
        'GRASIM', 'HCLTECH', 'HDFCBANK', 'HINDUNILVR', 'ICICIBANK', 
        'INDUSINDBK', 'INFY', 'ITC', 'JSWSTEEL', 'KOTAKBANK', 
        'LT', 'MARUTI', 'NTPC', 'ONGC', 'POWERGRID', 
        'RELIANCE', 'SBIN', 'SUNPHARMA', 'TATAMOTORS', 'TATASTEEL', 
        'TCS', 'TECHM', 'TITAN', 'ULTRACEMCO', 'WIPRO'
    ]
    
    print("Loading data for 30 stocks...", flush=True)
    symbol_days = {}
    all_dates = set()
    
    for sym in symbols:
        df = load_symbol_5m(sym)
        if df is None: continue
        symbol_days[sym] = {}
        grouped = df.groupby('date_str')
        or_vols = []
        for d_str, d_df in grouped:
            d_df = d_df.reset_index(drop=True)
            if len(d_df) < 25: continue
            c15 = d_df.iloc[0:3]
            open_15m = c15.iloc[0]['Open']
            high_15m = c15['High'].max()
            low_15m = c15['Low'].min()
            close_15m = c15.iloc[-1]['Close']
            vol_15m = c15['Volume'].sum()
            rvol = vol_15m / np.mean(or_vols[-20:]) if len(or_vols) >= 10 and np.mean(or_vols[-20:]) > 0 else 1.0
            or_vols.append(vol_15m)
            
            if int(d_str[:4]) >= 2022 and d_str <= '2026-10-31':
                all_dates.add(d_str)
                symbol_days[sym][d_str] = {
                    'df': d_df, 'open_15m': open_15m, 'high_15m': high_15m, 'low_15m': low_15m,
                    'mid_15m': (high_15m + low_15m) / 2.0, 'close_15m': close_15m, 'rvol': rvol
                }
                
    sorted_dates = sorted(list(all_dates))
    print(f"Loaded {len(sorted_dates)} trading dates.", flush=True)
    
    for exec_mode in ['ORIGINAL_VWAP', 'NEXT_BAR_OPEN']:
        trades = []
        risk_cash = 1000.0
        
        for d in sorted_dates:
            candidates = []
            for sym, d_dict in symbol_days.items():
                if d not in d_dict: continue
                info = d_dict[d]
                d_df = info['df']
                m15 = info['mid_15m']
                rvol = info['rvol']
                if rvol < 1.5: continue
                
                side = 'BUY' if info['close_15m'] > info['open_15m'] else 'SELL'
                
                for b_i in range(3, min(18, len(d_df) - 6)):
                    bar = d_df.iloc[b_i]
                    if side == 'BUY':
                        if bar['Low'] <= bar['vwap'] and bar['Close'] >= bar['vwap']:
                            if exec_mode == 'ORIGINAL_VWAP':
                                entry_p = bar['vwap']
                                b_enter = b_i
                            else:
                                if b_i + 1 >= len(d_df): break
                                entry_p = d_df.iloc[b_i + 1]['Open'] * (1.0 + 0.0003)
                                b_enter = b_i + 1
                                
                            risk_pts = max(entry_p * 0.0035, min(entry_p * 0.010, abs(entry_p - m15)))
                            candidates.append({
                                'sym': sym, 'side': 'BUY', 'b_idx': b_enter, 'entry_p': entry_p,
                                'sl_p': entry_p - risk_pts, 'risk_pts': risk_pts, 'score': rvol * 1.2,
                                'df': d_df
                            })
                            break
                    else:
                        if bar['High'] >= bar['vwap'] and bar['Close'] <= bar['vwap']:
                            if exec_mode == 'ORIGINAL_VWAP':
                                entry_p = bar['vwap']
                                b_enter = b_i
                            else:
                                if b_i + 1 >= len(d_df): break
                                entry_p = d_df.iloc[b_i + 1]['Open'] * (1.0 - 0.0003)
                                b_enter = b_i + 1
                                
                            risk_pts = max(entry_p * 0.0035, min(entry_p * 0.010, abs(m15 - entry_p)))
                            candidates.append({
                                'sym': sym, 'side': 'SELL', 'b_idx': b_enter, 'entry_p': entry_p,
                                'sl_p': entry_p + risk_pts, 'risk_pts': risk_pts, 'score': rvol * 1.2,
                                'df': d_df
                            })
                            break
                            
            if not candidates: continue
            candidates.sort(key=lambda x: -x['score'])
            t = candidates[0]
            
            entry_p, sl_p, risk_pts, d_df, side, b_idx = t['entry_p'], t['sl_p'], t['risk_pts'], t['df'], t['side'], t['b_idx']
            shares = int(risk_cash / risk_pts)
            if shares < 1: shares = 1
            s_t1 = int(shares * 0.50)
            s_run = shares - s_t1
            if s_t1 < 1: s_t1 = 1
            
            t1_p = entry_p + (2.0 * risk_pts) if side == 'BUY' else entry_p - (2.0 * risk_pts)
            t2_p = entry_p + (3.5 * risk_pts) if side == 'BUY' else entry_p - (3.5 * risk_pts)
            
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
                    if t1_hit and l <= t2_p:
                        exit_pr = t2_p
                        break
                    if j == len(d_df) - 1 or j >= 72:
                        if not t1_hit: exit_p1 = c
                        exit_pr = c
                        break
                        
            if side == 'BUY':
                gp1 = s_t1 * (exit_p1 - entry_p)
                gpr = s_run * (exit_pr - entry_p) if s_run > 0 else 0
                fee1 = compute_zerodha_charges(s_t1 * entry_p, s_t1 * exit_p1)
                feer = compute_zerodha_charges(s_run * entry_p, s_run * exit_pr) if s_run > 0 else 0
            else:
                gp1 = s_t1 * (entry_p - exit_p1)
                gpr = s_run * (entry_p - exit_pr) if s_run > 0 else 0
                fee1 = compute_zerodha_charges(s_t1 * exit_p1, s_t1 * entry_p)
                feer = compute_zerodha_charges(s_run * exit_pr, s_run * entry_p) if s_run > 0 else 0
                
            npnl = gp1 + gpr - fee1 - feer
            trades.append({'date': d, 'year': int(d[:4]), 'net_pnl': npnl, 'R': npnl / 1000.0})
            
        df_t = pd.DataFrame(trades)
        wins = df_t[df_t['net_pnl'] > 0]
        wr = len(wins) / len(df_t) * 100.0
        gp = wins['net_pnl'].sum()
        gl = abs(df_t[df_t['net_pnl'] <= 0]['net_pnl'].sum())
        pf = gp / gl if gl > 0 else 0.0
        tot_pnl = df_t['net_pnl'].sum()
        df_t['ym'] = pd.to_datetime(df_t['date']).dt.to_period('M')
        n_mo = df_t['ym'].nunique()
        df_t['cum'] = df_t['net_pnl'].cumsum()
        df_t['peak'] = df_t['cum'].cummax()
        max_dd = abs((df_t['cum'] - df_t['peak']).min()) / 100000.0 * 100.0
        y_pnl = df_t.groupby('year')['net_pnl'].sum().to_dict()
        
        print("="*85)
        print(f"[EXECUTION AUDIT: {exec_mode}]")
        print(f"  Trades: {len(df_t)} ({len(df_t)/n_mo:.1f}/mo) | WR: {wr:.2f}% | PF: {pf:.2f}")
        print(f"  Net PnL: Rs {tot_pnl:+10,.2f} (+{tot_pnl/1000:.1f}R) | Avg Mo Return: {tot_pnl/100000/n_mo*100:+5.2f}% / month")
        print(f"  Max DD: {max_dd:.2f}%")
        print(f"  Yearly: { {y: int(v) for y, v in y_pnl.items()} }\n", flush=True)

if __name__ == '__main__':
    run_test()
