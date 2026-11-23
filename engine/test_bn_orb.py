import sys
import pandas as pd
import numpy as np
from datetime import time

print("="*80)
print("TESTING BANK NIFTY ORB & MOMENTUM (2020-2024)")
print("Strict Candle-by-Candle | Zero Lookahead | Exact Futures Tariff")
print("="*80)

def calc_bn_charges(entry, exit_px, sl_dist, direction='BUY', risk_inr=1000.0):
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
    slippage = qty * 1.5 # 1.5 points slippage
    
    total_tax = brok + stt + exch + sebi + stamp + gst + slippage
    gross_pnl = qty * (exit_px - entry) if direction == 'BUY' else qty * (entry - exit_px)
    net_pnl = gross_pnl - total_tax
    net_r = net_pnl / risk_inr
    return total_tax, net_r

df_bn = pd.read_csv('data/banknifty/banknifty_5m_2015_2024.csv')
df_bn['Date'] = pd.to_datetime(df_bn['Date'], format='%d-%m-%Y')
df_bn = df_bn[df_bn['Date'] >= '2020-01-01'].copy()
df_bn['Time'] = pd.to_datetime(df_bn['Time'], format='%H:%M:%S').dt.time
df_bn = df_bn.sort_values(['Date', 'Time']).reset_index(drop=True)

# 15m Resample
df_15m = df_bn.set_index(pd.to_datetime(df_bn['Date'].astype(str) + ' ' + df_bn['Time'].astype(str))).resample('15min', origin='start_day', offset='15min').agg({
    'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'
}).dropna().reset_index()

df_15m['Date'] = df_15m['index'].dt.date
df_15m['Time'] = df_15m['index'].dt.time

first_bars = df_15m[df_15m['Time'] == time(9, 15)].groupby('Date').agg({'High':'first', 'Low':'first', 'Open':'first', 'Close':'last'})
df_15m['OR_H'] = df_15m['Date'].map(first_bars['High'])
df_15m['OR_L'] = df_15m['Date'].map(first_bars['Low'])

trades = []
for dt, day_df in df_15m.groupby('Date'):
    if len(day_df) < 10: continue
    
    or_h = day_df['OR_H'].values[0]
    or_l = day_df['OR_L'].values[0]
    if pd.isna(or_h) or pd.isna(or_l): continue
    
    opens = day_df['Open'].values
    highs = day_df['High'].values
    lows = day_df['Low'].values
    closes = day_df['Close'].values
    times = day_df['Time'].values
    n = len(day_df)
    
    active_pos = None
    day_trades = 0
    
    for i in range(1, n):
        if active_pos is not None:
            h = highs[i]; l = lows[i]; c = closes[i]; t = times[i]
            exit_px = None; reason = None
            
            if active_pos['dir'] == 'BUY':
                if l <= active_pos['sl']:
                    exit_px = active_pos['sl']; reason = 'SL'
                elif h >= active_pos['tp']:
                    exit_px = active_pos['tp']; reason = 'TP'
                elif t >= time(15, 15):
                    exit_px = c; reason = 'EOD'
            else:
                if h >= active_pos['sl']:
                    exit_px = active_pos['sl']; reason = 'SL'
                elif l <= active_pos['tp']:
                    exit_px = active_pos['tp']; reason = 'TP'
                elif t >= time(15, 15):
                    exit_px = c; reason = 'EOD'
                    
            if exit_px is not None:
                tax, net_r = calc_bn_charges(active_pos['entry'], exit_px, active_pos['sl_dist'], active_pos['dir'], 1000.0)
                trades.append({
                    'Date': dt, 'Time': active_pos['time'], 'Dir': active_pos['dir'],
                    'Net_R': net_r, 'Reason': reason
                })
                active_pos = None
            continue
            
        if day_trades >= 1: continue
        if times[i] < time(9, 30) or times[i] > time(11, 30): continue
        
        # BUY: Bar closes above OR_H
        if closes[i] > or_h and opens[i] <= or_h and closes[i] > opens[i]:
            entry = closes[i]
            sl_dist = max(entry - (or_h + or_l)/2.0, 50.0)
            if sl_dist > 250.0: continue
            sl = entry - sl_dist
            tp = entry + sl_dist * 2.0
            active_pos = {'entry': entry, 'sl': sl, 'tp': tp, 'sl_dist': sl_dist, 'dir': 'BUY', 'time': times[i]}
            day_trades += 1
        # SELL: Bar closes below OR_L
        elif closes[i] < or_l and opens[i] >= or_l and closes[i] < opens[i]:
            entry = closes[i]
            sl_dist = max((or_h + or_l)/2.0 - entry, 50.0)
            if sl_dist > 250.0: continue
            sl = entry + sl_dist
            tp = entry - sl_dist * 2.0
            active_pos = {'entry': entry, 'sl': sl, 'tp': tp, 'sl_dist': sl_dist, 'dir': 'SELL', 'time': times[i]}
            day_trades += 1

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
    daily = df_t.groupby('Date')['Net_R'].sum()
    max_dd = (daily.cumsum() - daily.cumsum().cummax()).min()
    print(f"\nBANK NIFTY ORB (2020-2024):")
    print(f"Total Trades: {len(df_t)} (~{len(df_t)/n_mo:.1f} trades/month)")
    print(f"Win Rate: {wr:.1f}%")
    print(f"Profit Factor: {pf:.2f}")
    print(f"Total Net R: {tot_r:+.1f} R")
    print(f"Monthly Net R: {tot_r/n_mo:+.2f} R/mo")
    print(f"Max Drawdown: {max_dd:.1f} R")
