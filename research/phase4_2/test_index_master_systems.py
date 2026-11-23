"""
MASTER QUANTITATIVE RESEARCH: NIFTY 50 & BANK NIFTY INTRADAY SYSTEMS (2022 - 2026)
Dataset:
- NIFTY 50 1-minute tick aggregates (2022 - 2026)
- BANK NIFTY 1-minute tick aggregates (2022 - 2026)
Sizing: Static Rs 1,000 Risk per trade (1R) on Rs 1,00,000 Capital (Zero Compounding)
Cost Model: Exact Zerodha Index Intraday / Futures:
- Brokerage: Rs 20 per executed order (Rs 40 round-trip)
- STT: 0.02% on sell turnover
- Exchange: 0.0019% on buy and sell turnover
- SEBI: 0.0001% on buy and sell turnover
- Stamp Duty: 0.002% on buy turnover
- GST: 18% on (Brokerage + Exchange + SEBI)
- Slippage: 0.02% on entry and exit
Execution: Strictly Point-in-Time, Next-Bar Execution (Zero Look-Ahead).
"""

import os, glob, time
import numpy as np
import pandas as pd
from datetime import time as dtime

def compute_index_charges(buy_val, sell_val):
    brokerage = 40.0 # Rs 20 buy + Rs 20 sell
    stt = sell_val * 0.00020 # 0.02% on sell
    exchange = (buy_val + sell_val) * 0.000019 # 0.0019%
    sebi = (buy_val + sell_val) * 0.000001 # 0.0001%
    stamp = buy_val * 0.00002 # 0.002% on buy
    gst = (brokerage + exchange + sebi) * 0.18
    return brokerage + stt + exchange + sebi + stamp + gst

def load_nifty50_5m():
    t0 = time.time()
    files = sorted(glob.glob("data/nifty50/NIFTY50_1min_*.csv") + glob.glob("data/nifty50/2026/*.csv"))
    dfs = []
    for f in files:
        df = pd.read_csv(f)
        df['Date'] = pd.to_datetime(df['Timestamp'])
        dfs.append(df[['Date', 'Open', 'High', 'Low', 'Close']])
    full_df = pd.concat(dfs, ignore_index=True).sort_values('Date').reset_index(drop=True)
    full_df = full_df[(full_df['Date'] >= '2022-01-01') & (full_df['Date'] <= '2026-10-31 15:30:00')]
    full_df.set_index('Date', inplace=True)
    
    # Resample to 5m
    df_5m = full_df.resample('5min').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna().reset_index()
    df_5m['time'] = df_5m['Date'].dt.time
    df_5m = df_5m[(df_5m['time'] >= dtime(9,15)) & (df_5m['time'] <= dtime(15,30))].reset_index(drop=True)
    df_5m['date_str'] = df_5m['Date'].dt.strftime('%Y-%m-%d')
    df_5m['time_str'] = df_5m['Date'].dt.strftime('%H:%M:%S')
    
    # Approximate VWAP using typical price cumulative average per day (volume proxy)
    df_5m['typ'] = (df_5m['High'] + df_5m['Low'] + df_5m['Close']) / 3.0
    df_5m['vwap'] = df_5m.groupby('date_str')['typ'].cumsum() / (df_5m.groupby('date_str').cumcount() + 1)
    
    # Group by date
    days_dict = {}
    for d_str, grp in df_5m.groupby('date_str'):
        if len(grp) < 25: continue
        days_dict[d_str] = {
            'open': grp['Open'].values,
            'high': grp['High'].values,
            'low': grp['Low'].values,
            'close': grp['Close'].values,
            'vwap': grp['vwap'].values,
            'time_str': grp['time_str'].values,
            'n_bars': len(grp)
        }
    print(f"Loaded Nifty 50: {len(days_dict)} trading dates in {time.time()-t0:.1f}s.", flush=True)
    return days_dict

def load_banknifty_5m():
    t0 = time.time()
    bn = pd.read_csv("data/banknifty/banknifty_1m.csv")
    bn['Date_parsed'] = pd.to_datetime(bn['Date'] + ' ' + bn['Time'], format='%d-%m-%Y %H:%M:%S')
    bn = bn[(bn['Date_parsed'] >= '2022-01-01') & (bn['Date_parsed'] <= '2026-10-31 15:30:00')].sort_values('Date_parsed').reset_index(drop=True)
    bn.set_index('Date_parsed', inplace=True)
    
    # Resample to 5m
    df_5m = bn.resample('5min').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna().reset_index()
    df_5m['time'] = df_5m['Date_parsed'].dt.time
    df_5m = df_5m[(df_5m['time'] >= dtime(9,15)) & (df_5m['time'] <= dtime(15,30))].reset_index(drop=True)
    df_5m['date_str'] = df_5m['Date_parsed'].dt.strftime('%Y-%m-%d')
    df_5m['time_str'] = df_5m['Date_parsed'].dt.strftime('%H:%M:%S')
    
    df_5m['typ'] = (df_5m['High'] + df_5m['Low'] + df_5m['Close']) / 3.0
    df_5m['vwap'] = df_5m.groupby('date_str')['typ'].cumsum() / (df_5m.groupby('date_str').cumcount() + 1)
    
    days_dict = {}
    for d_str, grp in df_5m.groupby('date_str'):
        if len(grp) < 25: continue
        days_dict[d_str] = {
            'open': grp['Open'].values,
            'high': grp['High'].values,
            'low': grp['Low'].values,
            'close': grp['Close'].values,
            'vwap': grp['vwap'].values,
            'time_str': grp['time_str'].values,
            'n_bars': len(grp)
        }
    print(f"Loaded Bank Nifty: {len(days_dict)} trading dates in {time.time()-t0:.1f}s.", flush=True)
    return days_dict

def simulate_index_strategy(name, generate_signal_fn, days_dict, risk_cash=1000.0):
    trades = []
    dates = sorted(list(days_dict.keys()))
    
    for d in dates:
        day = days_dict[d]
        sig = generate_signal_fn(day)
        if not sig: continue
        
        side = sig['side']
        b_in = sig['entry_bar']
        entry_p = sig['entry_p']
        sl_p = sig['sl_p']
        t1_p = sig['t1_p']
        t2_p = sig['t2_p']
        risk_pts = abs(entry_p - sl_p)
        if risk_pts <= 0: continue
        
        # Sizing: risk_cash = Rs 1,000 (1R)
        shares = risk_cash / risk_pts
        s_t1 = shares * 0.5
        s_run = shares * 0.5
        
        t1_hit = False
        exit_p1 = 0.0
        exit_pr = 0.0
        highs = day['high']
        lows = day['low']
        closes = day['close']
        n_bars = day['n_bars']
        curr_sl = sl_p
        
        for j in range(b_in + 1, n_bars):
            h, l, c = highs[j], lows[j], closes[j]
            if side == 'BUY':
                if l <= curr_sl:
                    if not t1_hit: exit_p1, exit_pr = curr_sl, curr_sl
                    else: exit_pr = curr_sl
                    break
                if not t1_hit and h >= t1_p:
                    t1_hit = True
                    exit_p1 = t1_p
                    curr_sl = entry_p # move to BE
                if t1_hit and h >= t2_p:
                    exit_pr = t2_p
                    break
                if j >= 72 or j == n_bars - 1:
                    if not t1_hit: exit_p1 = c
                    exit_pr = c
                    break
            else: # SELL SIDE
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
                if j >= 72 or j == n_bars - 1:
                    if not t1_hit: exit_p1 = c
                    exit_pr = c
                    break
                    
        # Apply slippage (0.02%)
        if side == 'BUY':
            exit_p1 = exit_p1 * (1.0 - 0.0002)
            exit_pr = exit_pr * (1.0 - 0.0002)
            buy_val = shares * entry_p
            sell_val = (s_t1 * exit_p1) + (s_run * exit_pr)
            gross_pnl = sell_val - buy_val
        else:
            exit_p1 = exit_p1 * (1.0 + 0.0002)
            exit_pr = exit_pr * (1.0 + 0.0002)
            sell_val = shares * entry_p
            buy_val = (s_t1 * exit_p1) + (s_run * exit_pr)
            gross_pnl = sell_val - buy_val
            
        fee = compute_index_charges(buy_val, sell_val)
        net_pnl = gross_pnl - fee
        trades.append({
            'date': d, 'year': int(d[:4]), 'side': side,
            'gross_pnl': gross_pnl, 'fee': fee, 'net_pnl': net_pnl,
            'R': net_pnl / risk_cash
        })
        
    df_t = pd.DataFrame(trades)
    if len(df_t) == 0:
        print(f"[{name}] 0 trades.")
        return
        
    df_t['ym'] = pd.to_datetime(df_t['date']).dt.to_period('M')
    n_mo = df_t['ym'].nunique()
    tot_pnl = df_t['net_pnl'].sum()
    wins = df_t[df_t['net_pnl'] > 0]
    wr = len(wins) / len(df_t) * 100.0
    gw = wins['net_pnl'].sum()
    gl = abs(df_t[df_t['net_pnl'] <= 0]['net_pnl'].sum())
    pf = gw / gl if gl > 0 else 0.0
    
    df_t['cum'] = df_t['net_pnl'].cumsum()
    df_t['peak'] = df_t['cum'].cummax()
    max_dd = abs((df_t['cum'] - df_t['peak']).min()) / 100000.0 * 100.0
    y_pnl = df_t.groupby('year')['net_pnl'].sum().to_dict()
    
    print("="*85)
    print(f"INDEX STRATEGY: {name}")
    print(f"  Trades: {len(df_t)} ({len(df_t)/n_mo:.1f}/mo) | Win Rate: {wr:5.2f}% | Profit Factor: {pf:4.2f}")
    print(f"  Total Net PnL: Rs {tot_pnl:+10,.0f} (+{tot_pnl/1000:.1f}R) | Avg Monthly Return: {tot_pnl/100000/n_mo*100:+5.2f}% / month")
    print(f"  Max Drawdown: {max_dd:5.2f}%")
    print(f"  Yearly Breakdown: { {y: int(v) for y, v in y_pnl.items()} }\n", flush=True)

def main():
    nifty_days = load_nifty50_5m()
    banknifty_days = load_banknifty_5m()
    
    # -------------------------------------------------------------
    # 1. NIFTY 50: 15-MINUTE ORB BREAKOUT (CLOSE CONFIRMED)
    # -------------------------------------------------------------
    def sig_nifty_orb15(day):
        highs, lows, closes, opens, vwap = day['high'], day['low'], day['close'], day['open'], day['vwap']
        if day['n_bars'] < 25: return None
        h15 = np.max(highs[:3])
        l15 = np.min(lows[:3])
        m15 = (h15 + l15) / 2.0
        
        for b_i in range(3, min(15, day['n_bars'] - 6)):
            if closes[b_i] > h15 and closes[b_i] > vwap[b_i]:
                entry_p = opens[b_i + 1] * (1.0 + 0.0002)
                risk_pts = max(15.0, min(50.0, abs(entry_p - m15)))
                return {
                    'side': 'BUY', 'entry_bar': b_i + 1, 'entry_p': entry_p,
                    'sl_p': entry_p - risk_pts,
                    't1_p': entry_p + (1.8 * risk_pts), 't2_p': entry_p + (3.0 * risk_pts)
                }
            elif closes[b_i] < l15 and closes[b_i] < vwap[b_i]:
                entry_p = opens[b_i + 1] * (1.0 - 0.0002)
                risk_pts = max(15.0, min(50.0, abs(m15 - entry_p)))
                return {
                    'side': 'SELL', 'entry_bar': b_i + 1, 'entry_p': entry_p,
                    'sl_p': entry_p + risk_pts,
                    't1_p': entry_p - (1.8 * risk_pts), 't2_p': entry_p - (3.0 * risk_pts)
                }
        return None
        
    simulate_index_strategy("1. NIFTY 50: 15-MIN ORB BREAKOUT", sig_nifty_orb15, nifty_days)
    
    # -------------------------------------------------------------
    # 2. NIFTY 50: 30-MINUTE ORB BREAKOUT (CLOSE CONFIRMED)
    # -------------------------------------------------------------
    def sig_nifty_orb30(day):
        highs, lows, closes, opens, vwap = day['high'], day['low'], day['close'], day['open'], day['vwap']
        if day['n_bars'] < 25: return None
        h30 = np.max(highs[:6])
        l30 = np.min(lows[:6])
        m30 = (h30 + l30) / 2.0
        
        for b_i in range(6, min(18, day['n_bars'] - 6)):
            if closes[b_i] > h30 and closes[b_i] > vwap[b_i]:
                entry_p = opens[b_i + 1] * (1.0 + 0.0002)
                risk_pts = max(20.0, min(60.0, abs(entry_p - m30)))
                return {
                    'side': 'BUY', 'entry_bar': b_i + 1, 'entry_p': entry_p,
                    'sl_p': entry_p - risk_pts,
                    't1_p': entry_p + (2.0 * risk_pts), 't2_p': entry_p + (3.5 * risk_pts)
                }
            elif closes[b_i] < l30 and closes[b_i] < vwap[b_i]:
                entry_p = opens[b_i + 1] * (1.0 - 0.0002)
                risk_pts = max(20.0, min(60.0, abs(m30 - entry_p)))
                return {
                    'side': 'SELL', 'entry_bar': b_i + 1, 'entry_p': entry_p,
                    'sl_p': entry_p + risk_pts,
                    't1_p': entry_p - (2.0 * risk_pts), 't2_p': entry_p - (3.5 * risk_pts)
                }
        return None
        
    simulate_index_strategy("2. NIFTY 50: 30-MIN ORB BREAKOUT", sig_nifty_orb30, nifty_days)
    
    # -------------------------------------------------------------
    # 3. NIFTY 50: VWAP PULLBACK RETEST (10:00 - 11:45 AM)
    # -------------------------------------------------------------
    def sig_nifty_vwap(day):
        highs, lows, closes, opens, vwap = day['high'], day['low'], day['close'], day['open'], day['vwap']
        if day['n_bars'] < 30: return None
        morn_dir = 'BULL' if closes[8] > opens[0] else 'BEAR' # Trend established by 10:00 AM
        
        for b_i in range(9, min(30, day['n_bars'] - 6)):
            if morn_dir == 'BULL':
                if lows[b_i] <= vwap[b_i] and closes[b_i] >= vwap[b_i]:
                    entry_p = opens[b_i + 1] * (1.0 + 0.0002)
                    risk_pts = 25.0 # Fixed 25 pts stop on Nifty
                    return {
                        'side': 'BUY', 'entry_bar': b_i + 1, 'entry_p': entry_p,
                        'sl_p': entry_p - risk_pts,
                        't1_p': entry_p + (2.0 * risk_pts), 't2_p': entry_p + (3.5 * risk_pts)
                    }
            else:
                if highs[b_i] >= vwap[b_i] and closes[b_i] <= vwap[b_i]:
                    entry_p = opens[b_i + 1] * (1.0 - 0.0002)
                    risk_pts = 25.0
                    return {
                        'side': 'SELL', 'entry_bar': b_i + 1, 'entry_p': entry_p,
                        'sl_p': entry_p + risk_pts,
                        't1_p': entry_p - (2.0 * risk_pts), 't2_p': entry_p - (3.5 * risk_pts)
                    }
        return None
        
    simulate_index_strategy("3. NIFTY 50: VWAP PULLBACK RETEST", sig_nifty_vwap, nifty_days)
    
    # -------------------------------------------------------------
    # 4. BANK NIFTY: 15-MINUTE ORB BREAKOUT
    # -------------------------------------------------------------
    def sig_bn_orb15(day):
        highs, lows, closes, opens, vwap = day['high'], day['low'], day['close'], day['open'], day['vwap']
        if day['n_bars'] < 25: return None
        h15 = np.max(highs[:3])
        l15 = np.min(lows[:3])
        m15 = (h15 + l15) / 2.0
        
        for b_i in range(3, min(15, day['n_bars'] - 6)):
            if closes[b_i] > h15 and closes[b_i] > vwap[b_i]:
                entry_p = opens[b_i + 1] * (1.0 + 0.0002)
                risk_pts = max(60.0, min(180.0, abs(entry_p - m15)))
                return {
                    'side': 'BUY', 'entry_bar': b_i + 1, 'entry_p': entry_p,
                    'sl_p': entry_p - risk_pts,
                    't1_p': entry_p + (1.8 * risk_pts), 't2_p': entry_p + (3.0 * risk_pts)
                }
            elif closes[b_i] < l15 and closes[b_i] < vwap[b_i]:
                entry_p = opens[b_i + 1] * (1.0 - 0.0002)
                risk_pts = max(60.0, min(180.0, abs(m15 - entry_p)))
                return {
                    'side': 'SELL', 'entry_bar': b_i + 1, 'entry_p': entry_p,
                    'sl_p': entry_p + risk_pts,
                    't1_p': entry_p - (1.8 * risk_pts), 't2_p': entry_p - (3.0 * risk_pts)
                }
        return None
        
    simulate_index_strategy("4. BANK NIFTY: 15-MIN ORB BREAKOUT", sig_bn_orb15, banknifty_days)
    
    # -------------------------------------------------------------
    # 5. BANK NIFTY: 30-MINUTE ORB BREAKOUT
    # -------------------------------------------------------------
    def sig_bn_orb30(day):
        highs, lows, closes, opens, vwap = day['high'], day['low'], day['close'], day['open'], day['vwap']
        if day['n_bars'] < 25: return None
        h30 = np.max(highs[:6])
        l30 = np.min(lows[:6])
        m30 = (h30 + l30) / 2.0
        
        for b_i in range(6, min(18, day['n_bars'] - 6)):
            if closes[b_i] > h30 and closes[b_i] > vwap[b_i]:
                entry_p = opens[b_i + 1] * (1.0 + 0.0002)
                risk_pts = max(80.0, min(220.0, abs(entry_p - m30)))
                return {
                    'side': 'BUY', 'entry_bar': b_i + 1, 'entry_p': entry_p,
                    'sl_p': entry_p - risk_pts,
                    't1_p': entry_p + (2.0 * risk_pts), 't2_p': entry_p + (3.5 * risk_pts)
                }
            elif closes[b_i] < l30 and closes[b_i] < vwap[b_i]:
                entry_p = opens[b_i + 1] * (1.0 - 0.0002)
                risk_pts = max(80.0, min(220.0, abs(m30 - entry_p)))
                return {
                    'side': 'SELL', 'entry_bar': b_i + 1, 'entry_p': entry_p,
                    'sl_p': entry_p + risk_pts,
                    't1_p': entry_p - (2.0 * risk_pts), 't2_p': entry_p - (3.5 * risk_pts)
                }
        return None
        
    simulate_index_strategy("5. BANK NIFTY: 30-MIN ORB BREAKOUT", sig_bn_orb30, banknifty_days)
    
    # -------------------------------------------------------------
    # 6. BANK NIFTY: VWAP PULLBACK RETEST (10:00 - 11:45 AM)
    # -------------------------------------------------------------
    def sig_bn_vwap(day):
        highs, lows, closes, opens, vwap = day['high'], day['low'], day['close'], day['open'], day['vwap']
        if day['n_bars'] < 30: return None
        morn_dir = 'BULL' if closes[8] > opens[0] else 'BEAR'
        
        for b_i in range(9, min(30, day['n_bars'] - 6)):
            if morn_dir == 'BULL':
                if lows[b_i] <= vwap[b_i] and closes[b_i] >= vwap[b_i]:
                    entry_p = opens[b_i + 1] * (1.0 + 0.0002)
                    risk_pts = 75.0 # Fixed 75 pts stop on Bank Nifty
                    return {
                        'side': 'BUY', 'entry_bar': b_i + 1, 'entry_p': entry_p,
                        'sl_p': entry_p - risk_pts,
                        't1_p': entry_p + (2.0 * risk_pts), 't2_p': entry_p + (3.5 * risk_pts)
                    }
            else:
                if highs[b_i] >= vwap[b_i] and closes[b_i] <= vwap[b_i]:
                    entry_p = opens[b_i + 1] * (1.0 - 0.0002)
                    risk_pts = 75.0
                    return {
                        'side': 'SELL', 'entry_bar': b_i + 1, 'entry_p': entry_p,
                        'sl_p': entry_p + risk_pts,
                        't1_p': entry_p - (2.0 * risk_pts), 't2_p': entry_p - (3.5 * risk_pts)
                    }
        return None
        
    simulate_index_strategy("6. BANK NIFTY: VWAP PULLBACK RETEST", sig_bn_vwap, banknifty_days)

if __name__ == '__main__':
    main()
