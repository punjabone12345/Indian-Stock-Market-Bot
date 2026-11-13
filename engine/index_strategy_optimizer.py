import sys
sys.path.append('engine')
import os
import pandas as pd
import numpy as np
from datetime import time
from data_loader import load_nifty, resample_5min

def load_banknifty_5m():
    df = pd.read_csv('data/banknifty/banknifty_1m.csv')
    df['Timestamp'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], format='%d-%m-%Y %H:%M:%S', errors='coerce')
    df = df[df['Timestamp'] >= '2022-10-01'].copy()
    df['Volume'] = 1 # Index tick data
    df['Symbol'] = 'BANKNIFTY'
    df['IsIndex'] = True
    df_5m = resample_5min(df[['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume', 'Symbol', 'IsIndex']])
    return df_5m

def run_tests():
    print("Loading Nifty 5m...")
    nifty_5m = resample_5min(load_nifty())
    print("Loading Bank Nifty 5m...")
    bnf_5m = load_banknifty_5m()

    indices = {'NIFTY50': nifty_5m, 'BANKNIFTY': bnf_5m}

    # Evaluate different Target R:R and filters on Index
    for name, df in indices.items():
        print(f"\n==================== {name} ====================")
        df = df.copy().sort_values('Timestamp').reset_index(drop=True)
        
        # Indicators
        df['Typ'] = (df['High'] + df['Low'] + df['Close']) / 3.0
        df['PV'] = df['Typ'] * df['Volume']
        df['CumPV'] = df.groupby('Date')['PV'].cumsum()
        df['CumV'] = df.groupby('Date')['Volume'].cumsum()
        df['VWAP'] = df['CumPV'] / df['CumV']
        df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
        df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
        df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()

        # Previous day levels
        daily_summary = df.groupby('Date').agg({'High': 'max', 'Low': 'min', 'Close': 'last'})
        daily_summary = daily_summary.shift(1).rename(columns={'High': 'PDH', 'Low': 'PDL', 'Close': 'PDC'})
        df = df.merge(daily_summary, on='Date', how='left')

        for target_rr in [1.5, 2.0, 2.5, 3.0]:
            trades = []
            for dt, g in df.groupby('Date'):
                g = g.reset_index(drop=True)
                if len(g) < 25: continue

                first3 = g.iloc[:3]
                orb_h = first3['High'].max()
                orb_l = first3['Low'].min()
                orb_rng = orb_h - orb_l
                
                pdh = g['PDH'].iloc[0]
                pdl = g['PDL'].iloc[0]

                # Max 1 trade per day per index
                traded = False

                for i in range(3, min(len(g)-5, 20)): # 09:30 to 10:50 AM
                    row = g.iloc[i]
                    prev = g.iloc[i-1]

                    # Setup A: Bullish Liquidity Sweep of PDL / ORB Low
                    sweep_low = (prev['Low'] < orb_l or row['Low'] < orb_l) and row['Close'] > orb_l
                    if pd.notna(pdl):
                        sweep_low = sweep_low or ((prev['Low'] < pdl or row['Low'] < pdl) and row['Close'] > pdl)

                    if sweep_low and row['Close'] > row['Open'] and row['Close'] > row['EMA9']:
                        entry = row['Close']
                        sl = min(row['Low'], prev['Low']) - (entry * 0.0005)
                        sl_dist = entry - sl
                        if sl_dist < entry * 0.0025: sl_dist = entry * 0.0025; sl = entry - sl_dist
                        tp = entry + (sl_dist * target_rr)

                        for j in range(i+1, len(g)):
                            c = g.iloc[j]
                            if c['Low'] <= sl:
                                trades.append({'R': -1.04, 'Win': False, 'Date': dt})
                                traded = True; break
                            if c['High'] >= tp:
                                trades.append({'R': target_rr - 0.04, 'Win': True, 'Date': dt})
                                traded = True; break
                            if c['Time'] >= time(15, 15):
                                r_eod = round((c['Close'] - entry)/sl_dist - 0.04, 2)
                                trades.append({'R': r_eod, 'Win': r_eod > 0, 'Date': dt})
                                traded = True; break
                        if traded: break

                    # Setup B: Bearish Liquidity Sweep of PDH / ORB High
                    sweep_high = (prev['High'] > orb_h or row['High'] > orb_h) and row['Close'] < orb_h
                    if pd.notna(pdh):
                        sweep_high = sweep_high or ((prev['High'] > pdh or row['High'] > pdh) and row['Close'] < pdh)

                    if sweep_high and row['Close'] < row['Open'] and row['Close'] < row['EMA9']:
                        entry = row['Close']
                        sl = max(row['High'], prev['High']) + (entry * 0.0005)
                        sl_dist = sl - entry
                        if sl_dist < entry * 0.0025: sl_dist = entry * 0.0025; sl = entry + sl_dist
                        tp = entry - (sl_dist * target_rr)

                        for j in range(i+1, len(g)):
                            c = g.iloc[j]
                            if c['High'] >= sl:
                                trades.append({'R': -1.04, 'Win': False, 'Date': dt})
                                traded = True; break
                            if c['Low'] <= tp:
                                trades.append({'R': target_rr - 0.04, 'Win': True, 'Date': dt})
                                traded = True; break
                            if c['Time'] >= time(15, 15):
                                r_eod = round((entry - c['Close'])/sl_dist - 0.04, 2)
                                trades.append({'R': r_eod, 'Win': r_eod > 0, 'Date': dt})
                                traded = True; break
                        if traded: break

            res = pd.DataFrame(trades)
            if len(res) > 0:
                cum_r = res['R'].cumsum()
                max_dd = (cum_r - cum_r.cummax()).min()
                win_rate = res['Win'].mean() * 100
                total_r = res['R'].sum()
                avg_win = res[res['R'] > 0]['R'].mean()
                avg_loss = abs(res[res['R'] < 0]['R'].mean())
                print(f"Target {target_rr}R: Trades={len(res)}, WinRate={win_rate:.1f}%, Total_R={total_r:.1f}R, Max_DD={max_dd:.1f}R, AvgWin={avg_win:.2f}R, AvgLoss={avg_loss:.2f}R")

if __name__ == '__main__':
    run_tests()
