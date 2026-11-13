import sys
sys.path.append('engine')
import os
import pandas as pd
import numpy as np
from datetime import time
from nifty_alpha_explorer import load_nifty_fast, resample_nifty, extract_all_daily_ifvgs
from portfolio_synergy import load_bnf
from fib_sr_master_engine import load_data_fast

def test_tri_asset_10r_ensemble():
    print("="*85)
    print("   TRI-ASSET ASYMMETRIC ENSEMBLE (NIFTY + BANK NIFTY + RELIANCE)")
    print("   Timeframe: 2m | Target RRR: 1:3.5 | 1-Loss Daily Stop per Asset | Static 1R")
    print("="*85)

    nifty_1m = load_nifty_fast()
    bnf_1m = load_bnf()
    stocks = load_data_fast(['RELIANCE'])

    print("Pre-computing Nifty 2m signals...")
    nifty_2m = resample_nifty(nifty_1m, 2)
    nifty_signals = extract_all_daily_ifvgs(nifty_2m, 2)

    print("Pre-computing Bank Nifty 2m signals...")
    bnf_2m = resample_nifty(bnf_1m, 2)
    bnf_signals = extract_all_daily_ifvgs(bnf_2m, 2)

    # Simulate Nifty trades (Max 2 trades/day, 1-loss stop, RR 1:3.5)
    all_trades = []
    for dt, day_data in nifty_signals.items():
        highs, lows, closes, times, n = day_data['highs'], day_data['lows'], day_data['closes'], day_data['times'], day_data['n']
        day_t, day_l = 0, 0
        for sig in day_data['signals']:
            if day_t >= 2 or day_l >= 1 or sig['time'] >= time(14, 15): break
            entry, direction = sig['entry'], sig['dir']
            if direction == 'BUY':
                raw_sl = sig['box_min'] - 2.0
                sl_dist = max(entry - raw_sl, entry * 0.0020)
                sl = entry - sl_dist
                if sl_dist > entry * 0.0060: continue
                tp = entry + (sl_dist * 3.5)
                for m in range(sig['bar'] + 1, n):
                    if lows[m] <= sl: all_trades.append({'Date': dt, 'Asset': 'NIFTY', 'R': -1.04}); day_t += 1; day_l += 1; break
                    if highs[m] >= tp: all_trades.append({'Date': dt, 'Asset': 'NIFTY', 'R': 3.46}); day_t += 1; break
                    if times[m] >= time(15, 15): all_trades.append({'Date': dt, 'Asset': 'NIFTY', 'R': round((closes[m] - entry)/sl_dist - 0.04, 2)}); day_t += 1; break
            elif direction == 'SELL':
                raw_sl = sig['box_max'] + 2.0
                sl_dist = max(raw_sl - entry, entry * 0.0020)
                sl = entry + sl_dist
                if sl_dist > entry * 0.0060: continue
                tp = entry - (sl_dist * 3.5)
                for m in range(sig['bar'] + 1, n):
                    if highs[m] >= sl: all_trades.append({'Date': dt, 'Asset': 'NIFTY', 'R': -1.04}); day_t += 1; day_l += 1; break
                    if lows[m] <= tp: all_trades.append({'Date': dt, 'Asset': 'NIFTY', 'R': 3.46}); day_t += 1; break
                    if times[m] >= time(15, 15): all_trades.append({'Date': dt, 'Asset': 'NIFTY', 'R': round((entry - closes[m])/sl_dist - 0.04, 2)}); day_t += 1; break

    # Simulate Bank Nifty trades
    for dt, day_data in bnf_signals.items():
        highs, lows, closes, times, n = day_data['highs'], day_data['lows'], day_data['closes'], day_data['times'], day_data['n']
        day_t, day_l = 0, 0
        for sig in day_data['signals']:
            if day_t >= 2 or day_l >= 1 or sig['time'] >= time(14, 15): break
            entry, direction = sig['entry'], sig['dir']
            if direction == 'BUY':
                raw_sl = sig['box_min'] - 5.0
                sl_dist = max(entry - raw_sl, entry * 0.0020)
                sl = entry - sl_dist
                if sl_dist > entry * 0.0060: continue
                tp = entry + (sl_dist * 3.5)
                for m in range(sig['bar'] + 1, n):
                    if lows[m] <= sl: all_trades.append({'Date': dt, 'Asset': 'BANKNIFTY', 'R': -1.04}); day_t += 1; day_l += 1; break
                    if highs[m] >= tp: all_trades.append({'Date': dt, 'Asset': 'BANKNIFTY', 'R': 3.46}); day_t += 1; break
                    if times[m] >= time(15, 15): all_trades.append({'Date': dt, 'Asset': 'BANKNIFTY', 'R': round((closes[m] - entry)/sl_dist - 0.04, 2)}); day_t += 1; break
            elif direction == 'SELL':
                raw_sl = sig['box_max'] + 5.0
                sl_dist = max(raw_sl - entry, entry * 0.0020)
                sl = entry + sl_dist
                if sl_dist > entry * 0.0060: continue
                tp = entry - (sl_dist * 3.5)
                for m in range(sig['bar'] + 1, n):
                    if highs[m] >= sl: all_trades.append({'Date': dt, 'Asset': 'BANKNIFTY', 'R': -1.04}); day_t += 1; day_l += 1; break
                    if lows[m] <= tp: all_trades.append({'Date': dt, 'Asset': 'BANKNIFTY', 'R': 3.46}); day_t += 1; break
                    if times[m] >= time(15, 15): all_trades.append({'Date': dt, 'Asset': 'BANKNIFTY', 'R': round((entry - closes[m])/sl_dist - 0.04, 2)}); day_t += 1; break

    # Simulate Reliance trades (FVG Catalyst 1:3.5)
    rel_dates = sorted(stocks['RELIANCE'].keys())
    for dt in rel_dates:
        d = stocks['RELIANCE'][dt]
        if d['len'] < 100 or pd.isna(d['PDC']) or d['PDC'] <= 0: continue
        ib_h = np.max(d['High'][:15])
        day_t, day_l = 0, 0
        for i in range(15, min(d['len'] - 15, 160)):
            if day_t >= 2 or day_l >= 1: break
            c_c, c_low, p2_h, c_vwap = d['Close'][i], d['Low'][i], d['High'][i-2], d['VWAP'][i]
            if c_low > p2_h and c_c > c_vwap and c_c > ib_h:
                entry = c_c
                raw_sl = min(p2_h, c_vwap) - (entry * 0.0004)
                sl_dist = max(entry - raw_sl, entry * 0.0020)
                sl = entry - sl_dist
                if sl_dist <= entry * 0.0045:
                    tp = entry + (sl_dist * 3.5)
                    for m in range(i + 1, d['len']):
                        if d['Low'][m] <= sl: all_trades.append({'Date': dt, 'Asset': 'RELIANCE', 'R': -1.04}); day_t += 1; day_l += 1; break
                        if d['High'][m] >= tp: all_trades.append({'Date': dt, 'Asset': 'RELIANCE', 'R': 3.46}); day_t += 1; break
                        if d['Time'][m] >= time(15, 15): all_trades.append({'Date': dt, 'Asset': 'RELIANCE', 'R': round((d['Close'][m] - entry)/sl_dist - 0.04, 2)}); day_t += 1; break

    df = pd.DataFrame(all_trades).sort_values('Date').reset_index(drop=True)
    df['Date'] = pd.to_datetime(df['Date'])
    df['YM'] = df['Date'].dt.to_period('M')

    tot_trades = len(df)
    tot_r = df['R'].sum()
    num_m = df['YM'].nunique()
    r_m = tot_r / num_m
    cum = df['R'].cumsum()
    max_dd = (cum - cum.cummax()).min()
    wr = (df['R'] > 0).mean() * 100
    pf = df[df['R'] > 0]['R'].sum() / abs(df[df['R'] < 0]['R'].sum())

    print("\n" + "="*70)
    print("   TRI-ASSET 1:3.5 ENSEMBLE RESULTS (49 MONTHS)")
    print("="*70)
    print(f"Total Trades Taken   : {tot_trades} (~{tot_trades/num_m:.1f} trades/month)")
    print(f"Overall Win Rate     : {wr:.1f}%")
    print(f"Profit Factor        : {pf:.2f}")
    print(f"TOTAL REALIZED R     : {tot_r:+.1f} R")
    print(f"AVERAGE MONTHLY R    : {r_m:+.2f} R / month")
    print(f"MAXIMUM DRAWDOWN     : {max_dd:.1f} R")
    print("="*70)

if __name__ == '__main__':
    test_tri_asset_10r_ensemble()
