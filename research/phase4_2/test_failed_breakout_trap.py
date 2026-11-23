"""
TEST NIFTY & BANK NIFTY FAILED BREAKOUT MEAN REVERSION (2022 - 2026)
Logic:
1. Establish 15-minute Opening Range (09:15 to 09:30).
2. Trap Identification:
   - Bull Trap: Candle pushes above High15, but then closes back below High15!
     -> Enter SHORT at next bar Open (+0.02% slippage).
     -> Stop Loss: 15 pts above the candle high.
     -> Target: 15-min Opening Range Low (mean reversion).
   - Bear Trap: Candle dips below Low15, but then closes back above Low15!
     -> Enter LONG at next bar Open (-0.02% slippage).
     -> Stop Loss: 15 pts below the candle low.
     -> Target: 15-min Opening Range High (mean reversion).
3. Exact Zerodha Index Charges.
"""

import os, glob, time
import numpy as np
import pandas as pd
from datetime import time as dtime

def compute_index_charges(buy_val, sell_val):
    brokerage = 40.0
    stt = sell_val * 0.00020
    exchange = (buy_val + sell_val) * 0.000019
    sebi = (buy_val + sell_val) * 0.000001
    stamp = buy_val * 0.00002
    gst = (brokerage + exchange + sebi) * 0.18
    return brokerage + stt + exchange + sebi + stamp + gst

def load_data():
    # NIFTY 50
    files = sorted(glob.glob("data/nifty50/NIFTY50_1min_*.csv") + glob.glob("data/nifty50/2026/*.csv"))
    dfs = [pd.read_csv(f)[['Timestamp', 'Open', 'High', 'Low', 'Close']] for f in files]
    nifty = pd.concat(dfs, ignore_index=True)
    nifty['Date'] = pd.to_datetime(nifty['Timestamp'])
    nifty = nifty[(nifty['Date'] >= '2022-01-01') & (nifty['Date'] <= '2026-10-31 15:30:00')].sort_values('Date').reset_index(drop=True)
    nifty.set_index('Date', inplace=True)
    n5m = nifty.resample('5min').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna().reset_index()
    n5m['date_str'] = n5m['Date'].dt.strftime('%Y-%m-%d')
    n_days = {d: grp.reset_index(drop=True) for d, grp in n5m.groupby('date_str') if len(grp) >= 25}
    
    # BANK NIFTY
    bn = pd.read_csv("data/banknifty/banknifty_1m.csv")
    bn['Date_parsed'] = pd.to_datetime(bn['Date'] + ' ' + bn['Time'], format='%d-%m-%Y %H:%M:%S')
    bn = bn[(bn['Date_parsed'] >= '2022-01-01') & (bn['Date_parsed'] <= '2026-10-31 15:30:00')].sort_values('Date_parsed').reset_index(drop=True)
    bn.set_index('Date_parsed', inplace=True)
    bn5m = bn.resample('5min').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna().reset_index()
    bn5m['date_str'] = bn5m['Date_parsed'].dt.strftime('%Y-%m-%d')
    bn_days = {d: grp.reset_index(drop=True) for d, grp in bn5m.groupby('date_str') if len(grp) >= 25}
    
    return n_days, bn_days

def test_failed_breakout(name, days_dict, stop_buffer=15.0, min_risk=15.0, max_risk=60.0):
    trades = []
    risk_cash = 1000.0
    
    for d, df in days_dict.items():
        opens = df['Open'].values
        highs = df['High'].values
        lows = df['Low'].values
        closes = df['Close'].values
        n_bars = len(df)
        
        h15 = np.max(highs[:3])
        l15 = np.min(lows[:3])
        
        sig = None
        for b_i in range(3, min(20, n_bars - 6)):
            # Bull Trap: High pushed above H15, but Close < H15
            if highs[b_i] > h15 and closes[b_i] < h15:
                entry_p = opens[b_i + 1] * (1.0 - 0.0002)
                sl_p = highs[b_i] + stop_buffer
                risk_pts = max(min_risk, min(max_risk, abs(sl_p - entry_p)))
                sig = {
                    'side': 'SELL', 'b_idx': b_i + 1, 'entry_p': entry_p,
                    'sl_p': entry_p + risk_pts, 'target_p': l15
                }
                break
            # Bear Trap: Low pushed below L15, but Close > L15
            elif lows[b_i] < l15 and closes[b_i] > l15:
                entry_p = opens[b_i + 1] * (1.0 + 0.0002)
                sl_p = lows[b_i] - stop_buffer
                risk_pts = max(min_risk, min(max_risk, abs(entry_p - sl_p)))
                sig = {
                    'side': 'BUY', 'b_idx': b_i + 1, 'entry_p': entry_p,
                    'sl_p': entry_p - risk_pts, 'target_p': h15
                }
                break
                
        if not sig: continue
        
        side = sig['side']
        b_in = sig['b_idx']
        entry_p = sig['entry_p']
        sl_p = sig['sl_p']
        target_p = sig['target_p']
        risk_pts = abs(entry_p - sl_p)
        shares = risk_cash / risk_pts
        
        exit_p = 0.0
        for j in range(b_in + 1, n_bars):
            h, l, c = highs[j], lows[j], closes[j]
            if side == 'BUY':
                if l <= sl_p:
                    exit_p = sl_p; break
                if h >= target_p:
                    exit_p = target_p; break
                if j >= 72 or j == n_bars - 1:
                    exit_p = c; break
            else:
                if h >= sl_p:
                    exit_p = sl_p; break
                if l <= target_p:
                    exit_p = target_p; break
                if j >= 72 or j == n_bars - 1:
                    exit_p = c; break
                    
        if side == 'BUY':
            exit_p = exit_p * (1.0 - 0.0002)
            buy_val = shares * entry_p
            sell_val = shares * exit_p
        else:
            exit_p = exit_p * (1.0 + 0.0002)
            sell_val = shares * entry_p
            buy_val = shares * exit_p
            
        fee = compute_index_charges(buy_val, sell_val)
        net_pnl = (sell_val - buy_val) - fee
        trades.append({'date': d, 'year': int(d[:4]), 'net_pnl': net_pnl, 'R': net_pnl / risk_cash})
        
    df_t = pd.DataFrame(trades)
    if len(df_t) == 0: return
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
    print(f"FAILED BREAKOUT (TRAP FADE) STRATEGY: {name}")
    print(f"  Trades: {len(df_t)} ({len(df_t)/n_mo:.1f}/mo) | Win Rate: {wr:5.2f}% | Profit Factor: {pf:4.2f}")
    print(f"  Total Net PnL: Rs {tot_pnl:+10,.0f} (+{tot_pnl/1000:.1f}R) | Avg Monthly Return: {tot_pnl/100000/n_mo*100:+5.2f}% / month")
    print(f"  Max Drawdown: {max_dd:5.2f}%")
    print(f"  Yearly Breakdown: { {y: int(v) for y, v in y_pnl.items()} }\n", flush=True)

def main():
    n_days, bn_days = load_data()
    test_failed_breakout("NIFTY 50: FAILED BREAKOUT REVERSAL", n_days, stop_buffer=10.0, min_risk=15.0, max_risk=50.0)
    test_failed_breakout("BANK NIFTY: FAILED BREAKOUT REVERSAL", bn_days, stop_buffer=30.0, min_risk=50.0, max_risk=150.0)

if __name__ == '__main__':
    main()
