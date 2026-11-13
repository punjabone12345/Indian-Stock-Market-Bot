import sys
sys.path.append('engine')
import os
import pandas as pd
import numpy as np
from datetime import time
from data_loader import load_nifty, resample_5min
from index_strategy_optimizer import load_banknifty_5m

def test_index_alpha():
    print("Loading Nifty 5m & Bank Nifty 5m...")
    nifty_5m = resample_5min(load_nifty())
    bnf_5m = load_banknifty_5m()

    indices = {'NIFTY50': nifty_5m, 'BANKNIFTY': bnf_5m}
    all_index_trades = []

    for name, df in indices.items():
        df = df.copy().sort_values('Timestamp').reset_index(drop=True)
        df['Date'] = pd.to_datetime(df['Timestamp']).dt.date
        df['Time'] = pd.to_datetime(df['Timestamp']).dt.time

        # Cumulative VWAP
        df['Typ'] = (df['High'] + df['Low'] + df['Close']) / 3.0
        df['PV'] = df['Typ'] * df['Volume']
        df['CumPV'] = df.groupby('Date')['PV'].cumsum()
        df['CumV'] = df.groupby('Date')['Volume'].cumsum()
        df['VWAP'] = df['CumPV'] / df['CumV']

        # Daily summary
        daily_summary = df.groupby('Date').agg({'High': 'max', 'Low': 'min', 'Close': 'last'}).shift(1)
        df['PDH'] = df['Date'].map(daily_summary['High'])
        df['PDL'] = df['Date'].map(daily_summary['Low'])

        for dt, g in df.groupby('Date'):
            g = g.reset_index(drop=True)
            if len(g) < 25: continue

            # Opening Range (First 15m)
            orb_h = g.iloc[:3]['High'].max()
            orb_l = g.iloc[:3]['Low'].min()
            pdl = g['PDL'].iloc[0]
            pdh = g['PDH'].iloc[0]

            # Look for trade between 09:30 and 11:30
            for i in range(3, min(len(g)-5, 25)):
                row = g.iloc[i]
                prev = g.iloc[i-1]

                # Long: Break above ORB High with Close > VWAP
                if row['Close'] > orb_h and row['Close'] > row['VWAP'] and prev['Close'] <= orb_h:
                    entry = row['Close']
                    sl = row['VWAP'] - (entry * 0.0008)
                    sl_dist = entry - sl
                    if entry * 0.0015 <= sl_dist <= entry * 0.0040:
                        tp = entry + (sl_dist * 2.5)
                        be = entry + (sl_dist * 0.1)
                        be_trig = entry + (sl_dist * 1.2)
                        
                        be_hit = False
                        final_r = None
                        for m in range(i+1, len(g)):
                            m_row = g.iloc[m]
                            if not be_hit and m_row['High'] >= be_trig:
                                be_hit = True
                                sl = max(sl, be)
                            if m_row['Low'] <= sl:
                                final_r = 0.06 if be_hit else -1.04
                                break
                            if m_row['High'] >= tp:
                                final_r = 2.46
                                break
                            if m_row['Time'] >= time(15, 15):
                                r_eod = (m_row['Close'] - entry) / sl_dist - 0.04
                                final_r = round(max(0.06, r_eod) if be_hit else r_eod, 2)
                                break
                        if final_r is not None:
                            all_index_trades.append({'Date': dt, 'Symbol': name, 'R': final_r})
                            break

                # Short: Breakdown below ORB Low with Close < VWAP
                elif row['Close'] < orb_l and row['Close'] < row['VWAP'] and prev['Close'] >= orb_l:
                    entry = row['Close']
                    sl = row['VWAP'] + (entry * 0.0008)
                    sl_dist = sl - entry
                    if entry * 0.0015 <= sl_dist <= entry * 0.0040:
                        tp = entry - (sl_dist * 2.5)
                        be = entry - (sl_dist * 0.1)
                        be_trig = entry - (sl_dist * 1.2)
                        
                        be_hit = False
                        final_r = None
                        for m in range(i+1, len(g)):
                            m_row = g.iloc[m]
                            if not be_hit and m_row['Low'] <= be_trig:
                                be_hit = True
                                sl = min(sl, be)
                            if m_row['High'] >= sl:
                                final_r = 0.06 if be_hit else -1.04
                                break
                            if m_row['Low'] <= tp:
                                final_r = 2.46
                                break
                            if m_row['Time'] >= time(15, 15):
                                r_eod = (entry - m_row['Close']) / sl_dist - 0.04
                                final_r = round(max(0.06, r_eod) if be_hit else r_eod, 2)
                                break
                        if final_r is not None:
                            all_index_trades.append({'Date': dt, 'Symbol': name, 'R': final_r})
                            break

    df_res = pd.DataFrame(all_index_trades).sort_values('Date').reset_index(drop=True)
    df_res['YM'] = pd.to_datetime(df_res['Date']).dt.to_period('M')
    tot_r = df_res['R'].sum()
    num_m = df_res['YM'].nunique()
    r_m = tot_r / num_m if num_m > 0 else 0
    cum = df_res['R'].cumsum()
    mdd = (cum - cum.cummax()).min()
    wr = (df_res['R'] > 0).mean() * 100
    print(f"\n--- INDEX RESULTS (Nifty + Bank Nifty ORB 15m) ---")
    print(f"Trades: {len(df_res)} | WinRate: {wr:.1f}% | Total R: {tot_r:+.1f}R | Monthly R: {r_m:+.1f}R/m | Max DD: {mdd:.1f}R")

if __name__ == '__main__':
    test_index_alpha()
