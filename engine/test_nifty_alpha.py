import sys
sys.path.append('engine')
import os
import pandas as pd
import numpy as np
from datetime import time
from nifty_alpha_explorer import load_nifty_fast

print("="*80)
print("TESTING NIFTY 50 INDEX 15-MIN TREND ALPHA (2022-2026)")
print("Strict Candle-by-Candle | Zero Lookahead | Exact Zerodha Tariff")
print("="*80)

def calc_nifty_charges(entry, exit_px, sl_dist, direction='BUY', risk_inr=500.0):
    # Nifty lot size is 50 (or 25/75 depending on year, but in terms of index futures):
    # For index futures: Brokerage = 20 flat buy + 20 sell = Rs 40
    # STT = 0.02% on sell side (or 0.0125%)
    # Exchange = 0.0019%
    # GST = 18% on (brokerage + exchange)
    # Stamp duty = 0.002% on buy
    # Slippage = 0.5 index points
    qty = max(1, int(risk_inr / sl_dist))
    turnover_buy = qty * entry
    turnover_sell = qty * exit_px
    roundtrip = turnover_buy + turnover_sell
    
    brok = 40.0
    stt = turnover_sell * 0.0002
    exch = roundtrip * 0.000019
    sebi = roundtrip * 0.000001
    stamp = turnover_buy * 0.00002
    gst = (brok + exch + sebi) * 0.18
    slippage = qty * 0.5
    
    total_tax = brok + stt + exch + sebi + stamp + gst + slippage
    gross_pnl = qty * (exit_px - entry) if direction == 'BUY' else qty * (entry - exit_px)
    net_pnl = gross_pnl - total_tax
    net_r = net_pnl / risk_inr
    return total_tax, net_r

nifty_1m = load_nifty_fast()
df_15m = nifty_1m.set_index('Timestamp').resample('15min', origin='start_day', offset='15min').agg({
    'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'
}).dropna().reset_index()

df_15m['Date'] = df_15m['Timestamp'].dt.date
df_15m['Time'] = df_15m['Timestamp'].dt.time

df_15m['EMA9'] = df_15m['Close'].ewm(span=9, adjust=False).mean()
df_15m['EMA21'] = df_15m['Close'].ewm(span=21, adjust=False).mean()

# ATR
tr1 = df_15m['High'] - df_15m['Low']
tr2 = (df_15m['High'] - df_15m['Close'].shift()).abs()
tr3 = (df_15m['Low'] - df_15m['Close'].shift()).abs()
df_15m['ATR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14, min_periods=1).mean()

print(f"Total 15m Nifty bars: {len(df_15m)}")

# Test 15-min Trend Pullback on Nifty
trades = []
active_pos = None

for i in range(25, len(df_15m)):
    row = df_15m.iloc[i]
    prev = df_15m.iloc[i-1]
    t = row['Time']
    dt = row['Date']
    
    if active_pos is not None:
        h = row['High']; l = row['Low']; c = row['Close']
        exit_px = None
        
        if active_pos['dir'] == 'BUY':
            if l <= active_pos['sl']:
                exit_px = active_pos['sl']
                reason = 'SL'
            elif h >= active_pos['tp']:
                exit_px = active_pos['tp']
                reason = 'TP'
            elif t >= time(15, 15):
                exit_px = c
                reason = 'EOD'
        else:
            if h >= active_pos['sl']:
                exit_px = active_pos['sl']
                reason = 'SL'
            elif l <= active_pos['tp']:
                exit_px = active_pos['tp']
                reason = 'TP'
            elif t >= time(15, 15):
                exit_px = c
                reason = 'EOD'
                
        if exit_px is not None:
            tax, net_r = calc_nifty_charges(active_pos['entry'], exit_px, active_pos['sl_dist'], active_pos['dir'], 500.0)
            trades.append({
                'Date': dt, 'Time': active_pos['time'], 'Dir': active_pos['dir'],
                'Net_R': net_r, 'Reason': reason
            })
            active_pos = None
        continue
        
    if t < time(9, 30) or t > time(14, 30):
        continue
        
    # Long Trend
    if prev['Close'] > prev['EMA9'] and prev['EMA9'] > prev['EMA21']:
        # Pullback touch of EMA9
        if row['Low'] <= row['EMA9'] and row['Close'] > row['EMA9'] and row['Close'] > row['Open']:
            entry = row['Close']
            sl_dist = max(entry - row['Low'], row['ATR'] * 1.0, 20.0)
            sl = entry - sl_dist
            tp = entry + sl_dist * 2.0
            active_pos = {'entry': entry, 'sl': sl, 'tp': tp, 'sl_dist': sl_dist, 'dir': 'BUY', 'time': t}
            
    # Short Trend
    elif prev['Close'] < prev['EMA9'] and prev['EMA9'] < prev['EMA21']:
        if row['High'] >= row['EMA9'] and row['Close'] < row['EMA9'] and row['Close'] < row['Open']:
            entry = row['Close']
            sl_dist = max(row['High'] - entry, row['ATR'] * 1.0, 20.0)
            sl = entry + sl_dist
            tp = entry - sl_dist * 2.0
            active_pos = {'entry': entry, 'sl': sl, 'tp': tp, 'sl_dist': sl_dist, 'dir': 'SELL', 'time': t}

df_t = pd.DataFrame(trades)
if len(df_t) > 0:
    df_t['Date'] = pd.to_datetime(df_t['Date'])
    df_t['YM'] = df_t['Date'].dt.to_period('M')
    n_mo = df_t['YM'].nunique()
    tot_r = df_t['Net_R'].sum()
    wins = df_t[df_t['Net_R'] > 0]
    wr = len(wins) / len(df_t) * 100
    gw = wins['Net_R'].sum()
    gl = abs(df_t[df_t['Net_R'] <= 0]['Net_R'].sum())
    pf = gw / gl if gl > 0 else 99
    print(f"\nNIFTY 15M TREND RESULTS (2022-2026):")
    print(f"Total Trades: {len(df_t)} (~{len(df_t)/n_mo:.1f} trades/month)")
    print(f"Win Rate: {wr:.1f}%")
    print(f"Profit Factor: {pf:.2f}")
    print(f"Total Net R: {tot_r:+.1f} R")
    print(f"Monthly Net R: {tot_r/n_mo:+.2f} R/mo")
