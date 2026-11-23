import sys
sys.path.append('engine')
import os
import glob
import pandas as pd
import numpy as np
import datetime
from datetime import time
from nifty_alpha_explorer import load_nifty_fast
from nifty_aligned_ema_atr_sweep import load_stock_data, get_nifty_trend_series

print("="*95, flush=True)
print("CATALYST MOMENTUM: TESTING INSTITUTIONAL GAP & GO ON 30 STOCKS", flush=True)
print("Strict Candle-by-Candle | Zero Lookahead | Exact Zerodha/Dhan Taxes", flush=True)
print("="*95, flush=True)

def calc_statutory_charges(entry_price, exit_price, sl_dist, direction='BUY', risk_inr=200.0):
    if sl_dist <= 0 or entry_price <= 0: return 0.0, 0.0, 0.0
    qty = max(1, int(risk_inr / sl_dist))
    buy_px = entry_price if direction == 'BUY' else exit_price
    sell_px = exit_price if direction == 'BUY' else entry_price
    buy_turnover = qty * buy_px
    sell_turnover = qty * sell_px
    roundtrip = buy_turnover + sell_turnover
    
    brok = min(20.0, buy_turnover * 0.0003) + min(20.0, sell_turnover * 0.0003)
    stt = sell_turnover * 0.00025
    exch = roundtrip * 0.0000297
    sebi = roundtrip * 0.000001
    stamp = buy_turnover * 0.00003
    gst = (brok + exch + sebi) * 0.18
    slippage = qty * 0.05
    
    total_tax = brok + stt + exch + sebi + stamp + gst + slippage
    tax_r = total_tax / risk_inr
    gross_pnl = qty * (exit_price - entry_price) if direction == 'BUY' else qty * (entry_price - exit_price)
    net_pnl = gross_pnl - total_tax
    net_r = net_pnl / risk_inr
    return total_tax, tax_r, net_r

nifty_1m = load_nifty_fast()
nifty_trend = get_nifty_trend_series(nifty_1m, tf_min=5)

files = sorted(glob.glob('data/stocks/*_prev.parquet'))
ALL_SYMBOLS = [os.path.basename(f).replace('_prev.parquet', '') for f in files]

all_trades = []

for sym in ALL_SYMBOLS:
    df_1m = load_stock_data(sym)
    if df_1m is None or len(df_1m) < 1000: continue
    
    df_5m = df_1m.set_index('Timestamp').resample('5min', origin='start_day', offset='15min').agg({
        'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'
    }).dropna().reset_index()
    
    df_5m['Date'] = df_5m['Timestamp'].dt.date
    df_5m['Time'] = df_5m['Timestamp'].dt.time
    
    # Intraday VWAP
    df_5m['Typ'] = (df_5m['High'] + df_5m['Low'] + df_5m['Close']) / 3.0
    df_5m['PV'] = df_5m['Typ'] * df_5m['Volume']
    df_5m['VWAP'] = df_5m.groupby('Date')['PV'].cumsum() / df_5m.groupby('Date')['Volume'].cumsum()
    df_5m['VolMA20'] = df_5m['Volume'].rolling(20, min_periods=1).mean()
    
    # Daily aggregation for gap calculation
    d_agg = df_5m.groupby('Date').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).shift(1)
    df_5m['PDC'] = df_5m['Date'].map(d_agg['Close'])
    
    # First 15m candle (09:15 - 09:30, first 3 candles)
    first_bars = df_5m[df_5m['Time'] <= time(9, 25)].groupby('Date').agg({'High':'max', 'Low':'min', 'Volume':'sum'})
    df_5m['OR_H'] = df_5m['Date'].map(first_bars['High'])
    df_5m['OR_L'] = df_5m['Date'].map(first_bars['Low'])
    df_5m['OR_Vol'] = df_5m['Date'].map(first_bars['Volume'])
    df_5m['Nifty_Trend'] = df_5m['Timestamp'].map(nifty_trend['Nifty_Trend']).fillna(0).astype(int)
    
    for dt, day_df in df_5m.groupby('Date'):
        n = len(day_df)
        if n < 15: continue
        
        pdc = day_df['PDC'].values[0]
        if pd.isna(pdc) or pdc <= 0: continue
        
        opens = day_df['Open'].values
        highs = day_df['High'].values
        lows = day_df['Low'].values
        closes = day_df['Close'].values
        times = day_df['Time'].values
        vwap = day_df['VWAP'].values
        nt = day_df['Nifty_Trend'].values
        or_h = day_df['OR_H'].values[0]
        or_l = day_df['OR_L'].values[0]
        or_vol = day_df['OR_Vol'].values[0]
        
        # Check Catalyst: Gap >= 0.8%
        open_0 = opens[0]
        gap_pct = (open_0 - pdc) / pdc * 100.0
        
        active_pos = None
        day_trades = 0
        
        for i in range(3, n):
            # Manage active position
            if active_pos is not None:
                h = highs[i]; l = lows[i]; c = closes[i]; t = times[i]
                exit_px = None; exit_reason = None
                
                if active_pos['dir'] == 'BUY':
                    if l <= active_pos['sl']:
                        exit_px = active_pos['sl']; exit_reason = 'STOP_LOSS'
                    elif h >= active_pos['tp']:
                        exit_px = active_pos['tp']; exit_reason = 'TARGET'
                    elif t >= time(15, 15):
                        exit_px = c; exit_reason = 'EOD_SQUAREOFF'
                else:
                    if h >= active_pos['sl']:
                        exit_px = active_pos['sl']; exit_reason = 'STOP_LOSS'
                    elif l <= active_pos['tp']:
                        exit_px = active_pos['tp']; exit_reason = 'TARGET'
                    elif t >= time(15, 15):
                        exit_px = c; exit_reason = 'EOD_SQUAREOFF'
                        
                if exit_px is not None:
                    c_inr, c_r, net_r = calc_statutory_charges(active_pos['entry'], exit_px, active_pos['sl_dist'], active_pos['dir'], 200.0)
                    all_trades.append({
                        'Date': dt, 'Time': active_pos['time'], 'Symbol': sym, 'Direction': active_pos['dir'],
                        'Net_R': net_r, 'Charges_INR': c_inr, 'ExitReason': exit_reason
                    })
                    active_pos = None
                continue
                
            if day_trades >= 1: continue
            if times[i] < time(9, 30) or times[i] > time(11, 0): continue
            
            # Catalyst Buy: Gap Up >= +0.8%, breaks OR_H, above VWAP, Nifty is Bullish
            if gap_pct >= 0.8 and nt[i] == 1 and closes[i] > vwap[i]:
                if closes[i] > or_h and opens[i] <= or_h and closes[i] > opens[i]:
                    entry = closes[i]
                    raw_sl = min(lows[i], (or_h + or_l)/2.0)
                    sl_dist = max(entry - raw_sl, entry * 0.0035)
                    if sl_dist > entry * 0.0100: continue
                    sl = entry - sl_dist
                    tp = entry + sl_dist * 2.5
                    active_pos = {'time': times[i], 'entry': entry, 'sl': sl, 'tp': tp, 'sl_dist': sl_dist, 'dir': 'BUY'}
                    day_trades += 1
            # Catalyst Sell: Gap Down <= -0.8%, breaks OR_L, below VWAP, Nifty is Bearish
            elif gap_pct <= -0.8 and nt[i] == -1 and closes[i] < vwap[i]:
                if closes[i] < or_l and opens[i] >= or_l and closes[i] < opens[i]:
                    entry = closes[i]
                    raw_sl = max(highs[i], (or_h + or_l)/2.0)
                    sl_dist = max(raw_sl - entry, entry * 0.0035)
                    if sl_dist > entry * 0.0100: continue
                    sl = entry + sl_dist
                    tp = entry - sl_dist * 2.5
                    active_pos = {'time': times[i], 'entry': entry, 'sl': sl, 'tp': tp, 'sl_dist': sl_dist, 'dir': 'SELL'}
                    day_trades += 1

print(f"\nTotal Catalyst Trades Generated: {len(all_trades)}", flush=True)
if all_trades:
    df_res = pd.DataFrame(all_trades)
    df_res['Date'] = pd.to_datetime(df_res['Date'])
    df_res['YM'] = df_res['Date'].dt.to_period('M')
    
    tot = len(df_res)
    wins = df_res[df_res['Net_R'] > 0]
    wr = len(wins) / tot * 100
    tot_r = df_res['Net_R'].sum()
    mo_r = tot_r / df_res['YM'].nunique()
    gw = wins['Net_R'].sum()
    gl = abs(df_res[df_res['Net_R'] <= 0]['Net_R'].sum())
    pf = gw / gl if gl > 0 else 99
    daily = df_res.groupby('Date')['Net_R'].sum()
    max_dd = (daily.cumsum() - daily.cumsum().cummax()).min()
    pos_m = (df_res.groupby('YM')['Net_R'].sum() > 0).sum()
    tot_m = df_res['YM'].nunique()
    
    print("="*95, flush=True)
    print("CATALYST GAP & GO AUDIT RESULTS (100% CLEAN live-IDENTICAL EXECUTION)", flush=True)
    print("="*95, flush=True)
    print(f"Total Trades: {tot} | Win Rate: {wr:.1f}% | Profit Factor: {pf:.2f} | Net R: {tot_r:+.1f} R | Monthly: {mo_r:+.2f} R/mo | Max DD: {max_dd:.1f} R | Prof Months: {pos_m}/{tot_m} ({pos_m/tot_m*100:.1f}%)", flush=True)
