import sys
sys.path.append('engine')
import os
import pandas as pd
import numpy as np
from datetime import time
from nifty_alpha_explorer import load_nifty_fast, resample_nifty, extract_all_daily_ifvgs

def load_bnf():
    bnf_df = pd.read_csv('data/banknifty/banknifty_1m.csv')
    bnf_df['Timestamp'] = pd.to_datetime(bnf_df['Date'] + ' ' + bnf_df['Time'], format='%d-%m-%Y %H:%M:%S', errors='coerce')
    bnf_df = bnf_df[bnf_df['Timestamp'] >= '2022-10-01'].sort_values('Timestamp').drop_duplicates('Timestamp').reset_index(drop=True)
    bnf_df['Time'] = bnf_df['Timestamp'].dt.time
    bnf_df['Volume'] = 1
    bnf_df = bnf_df[(bnf_df['Time'] >= time(9, 15)) & (bnf_df['Time'] <= time(15, 29))].copy()
    return bnf_df

def run_portfolio_synergy():
    print("="*85)
    print("   TESTING MULTI-ASSET INDEX + EQUITIES ENSEMBLE (STATIC 1R)")
    print("   Target: >= 10 R / Month | Max DD <= 10 R")
    print("="*85)

    nifty_1m = load_nifty_fast()
    bnf_1m = load_bnf()

    # Asset 1: Nifty 2m IFVG (2 trades, 1-loss stop, RR 1:3.0)
    print("Pre-computing Nifty 2m...")
    nifty_2m = resample_nifty(nifty_1m, 2)
    nifty_signals = extract_all_daily_ifvgs(nifty_2m, 2)

    # Asset 2: Bank Nifty 3m IFVG (2 trades, 1-loss stop, RR 1:3.0)
    print("Pre-computing Bank Nifty 3m...")
    bnf_3m = resample_nifty(bnf_1m, 3)
    bnf_signals = extract_all_daily_ifvgs(bnf_3m, 3)

    # Evaluate Nifty trades
    trades_nifty = []
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
                tp = entry + (sl_dist * 3.0)
                for m in range(sig['bar'] + 1, n):
                    if lows[m] <= sl:
                        trades_nifty.append({'Date': dt, 'Asset': 'NIFTY', 'R': -1.04}); day_t += 1; day_l += 1; break
                    if highs[m] >= tp:
                        trades_nifty.append({'Date': dt, 'Asset': 'NIFTY', 'R': 2.96}); day_t += 1; break
                    if times[m] >= time(15, 15):
                        trades_nifty.append({'Date': dt, 'Asset': 'NIFTY', 'R': round((closes[m] - entry)/sl_dist - 0.04, 2)}); day_t += 1; break
            elif direction == 'SELL':
                raw_sl = sig['box_max'] + 2.0
                sl_dist = max(raw_sl - entry, entry * 0.0020)
                sl = entry + sl_dist
                if sl_dist > entry * 0.0060: continue
                tp = entry - (sl_dist * 3.0)
                for m in range(sig['bar'] + 1, n):
                    if highs[m] >= sl:
                        trades_nifty.append({'Date': dt, 'Asset': 'NIFTY', 'R': -1.04}); day_t += 1; day_l += 1; break
                    if lows[m] <= tp:
                        trades_nifty.append({'Date': dt, 'Asset': 'NIFTY', 'R': 2.96}); day_t += 1; break
                    if times[m] >= time(15, 15):
                        trades_nifty.append({'Date': dt, 'Asset': 'NIFTY', 'R': round((entry - closes[m])/sl_dist - 0.04, 2)}); day_t += 1; break

    # Evaluate Bank Nifty trades
    trades_bnf = []
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
                tp = entry + (sl_dist * 3.0)
                for m in range(sig['bar'] + 1, n):
                    if lows[m] <= sl:
                        trades_bnf.append({'Date': dt, 'Asset': 'BANKNIFTY', 'R': -1.04}); day_t += 1; day_l += 1; break
                    if highs[m] >= tp:
                        trades_bnf.append({'Date': dt, 'Asset': 'BANKNIFTY', 'R': 2.96}); day_t += 1; break
                    if times[m] >= time(15, 15):
                        trades_bnf.append({'Date': dt, 'Asset': 'BANKNIFTY', 'R': round((closes[m] - entry)/sl_dist - 0.04, 2)}); day_t += 1; break
            elif direction == 'SELL':
                raw_sl = sig['box_max'] + 5.0
                sl_dist = max(raw_sl - entry, entry * 0.0020)
                sl = entry + sl_dist
                if sl_dist > entry * 0.0060: continue
                tp = entry - (sl_dist * 3.0)
                for m in range(sig['bar'] + 1, n):
                    if highs[m] >= sl:
                        trades_bnf.append({'Date': dt, 'Asset': 'BANKNIFTY', 'R': -1.04}); day_t += 1; day_l += 1; break
                    if lows[m] <= tp:
                        trades_bnf.append({'Date': dt, 'Asset': 'BANKNIFTY', 'R': 2.96}); day_t += 1; break
                    if times[m] >= time(15, 15):
                        trades_bnf.append({'Date': dt, 'Asset': 'BANKNIFTY', 'R': round((entry - closes[m])/sl_dist - 0.04, 2)}); day_t += 1; break

    df_n = pd.DataFrame(trades_nifty)
    df_b = pd.DataFrame(trades_bnf)
    df_comb = pd.concat([df_n, df_b]).sort_values('Date').reset_index(drop=True)
    df_comb['Date'] = pd.to_datetime(df_comb['Date'])
    df_comb['YM'] = df_comb['Date'].dt.to_period('M')

    tot_r = df_comb['R'].sum()
    num_m = df_comb['YM'].nunique()
    r_m = tot_r / num_m
    cum = df_comb['R'].cumsum()
    max_dd = (cum - cum.cummax()).min()
    wr = (df_comb['R'] > 0).mean() * 100
    pf = df_comb[df_comb['R'] > 0]['R'].sum() / abs(df_comb[df_comb['R'] < 0]['R'].sum())

    print(f"\n--- DUAL INDEX RESULTS (NIFTY + BANK NIFTY 1:3.0 IFVG) ---")
    print(f"Total Trades Taken   : {len(df_comb)} (~{len(df_comb)/num_m:.1f} trades/month)")
    print(f"Win Rate             : {wr:.1f}%")
    print(f"Profit Factor        : {pf:.2f}")
    print(f"Total Realized Return: {tot_r:+.1f}R")
    print(f"Average Monthly R    : {r_m:+.2f}R / month")
    print(f"Maximum Drawdown     : {max_dd:.1f}R")

if __name__ == '__main__':
    run_portfolio_synergy()
