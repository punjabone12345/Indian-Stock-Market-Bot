import sys
sys.path.append('engine')
import os
import glob
import pandas as pd
import numpy as np
from datetime import time
from data_loader import load_nifty, load_stock, resample_5min

def test_mean_reversion_vwap_extremes(df_5m, is_index=False):
    """
    Hypothesis: Reversion to VWAP from extreme deviations (2.0+ ATR / 2.5 StdDev)
    with RSI / pin bar confirmation.
    """
    df = df_5m.copy().sort_values('Timestamp').reset_index(drop=True)
    df['Typ'] = (df['High'] + df['Low'] + df['Close']) / 3.0
    df['PV'] = df['Typ'] * df['Volume']
    df['CumPV'] = df.groupby('Date')['PV'].cumsum()
    df['CumV'] = df.groupby('Date')['Volume'].cumsum()
    df['VWAP'] = df['CumPV'] / df['CumV']

    # Standard deviation from VWAP
    df['Diff2'] = (df['Close'] - df['VWAP'])**2
    df['CumDiff2'] = df.groupby('Date')['Diff2'].cumsum()
    df['Count'] = df.groupby('Date').cumcount() + 1
    df['VWAP_Std'] = np.sqrt(df['CumDiff2'] / df['Count'])
    df['Upper2'] = df['VWAP'] + (2.0 * df['VWAP_Std'])
    df['Lower2'] = df['VWAP'] - (2.0 * df['VWAP_Std'])

    # 14-period RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / (loss + 1e-9)
    df['RSI'] = 100 - (100 / (1 + rs))

    min_sl_pct = 0.0025 if is_index else 0.0050

    trades = []
    for dt, g in df.groupby('Date'):
        g = g.reset_index(drop=True)
        if len(g) < 25: continue
        
        traded = False
        for i in range(5, min(len(g)-5, 50)): # 09:40 to 13:30
            row = g.iloc[i]
            prev = g.iloc[i-1]
            
            # LONG Reversion: Price stretched below Lower2 band + RSI oversold (< 25) + Bullish reversal wick
            if prev['Low'] < prev['Lower2'] and row['Close'] > row['Open'] and row['RSI'] < 30:
                entry = row['Close']
                target = row['VWAP']
                raw_sl = min(row['Low'], prev['Low']) - (entry * 0.001)
                sl_dist = entry - raw_sl
                if sl_dist < entry * min_sl_pct:
                    sl_dist = entry * min_sl_pct
                    raw_sl = entry - sl_dist
                
                # Ensure reward to VWAP is at least 1.5x risk
                reward = target - entry
                if reward < sl_dist * 1.5:
                    continue
                    
                tp = entry + min(reward, sl_dist * 2.5)

                for j in range(i+1, len(g)):
                    c = g.iloc[j]
                    if c['Low'] <= raw_sl:
                        trades.append({'Date': dt, 'R': -1.04, 'Win': False, 'Type': 'Long'})
                        traded = True; break
                    if c['High'] >= tp:
                        r_win = round((tp - entry)/sl_dist - 0.04, 2)
                        trades.append({'Date': dt, 'R': r_win, 'Win': True, 'Type': 'Long'})
                        traded = True; break
                    if c['Time'] >= time(15, 15):
                        r_eod = round((c['Close'] - entry)/sl_dist - 0.04, 2)
                        trades.append({'Date': dt, 'R': r_eod, 'Win': r_eod > 0, 'Type': 'Long'})
                        traded = True; break
                if traded: break

            # SHORT Reversion: Price stretched above Upper2 band + RSI overbought (> 75) + Bearish reversal wick
            elif prev['High'] > prev['Upper2'] and row['Close'] < row['Open'] and row['RSI'] > 70:
                entry = row['Close']
                target = row['VWAP']
                raw_sl = max(row['High'], prev['High']) + (entry * 0.001)
                sl_dist = raw_sl - entry
                if sl_dist < entry * min_sl_pct:
                    sl_dist = entry * min_sl_pct
                    raw_sl = entry + sl_dist

                reward = entry - target
                if reward < sl_dist * 1.5:
                    continue
                    
                tp = entry - min(reward, sl_dist * 2.5)

                for j in range(i+1, len(g)):
                    c = g.iloc[j]
                    if c['High'] >= raw_sl:
                        trades.append({'Date': dt, 'R': -1.04, 'Win': False, 'Type': 'Short'})
                        traded = True; break
                    if c['Low'] <= tp:
                        r_win = round((entry - tp)/sl_dist - 0.04, 2)
                        trades.append({'Date': dt, 'R': r_win, 'Win': True, 'Type': 'Short'})
                        traded = True; break
                    if c['Time'] >= time(15, 15):
                        r_eod = round((entry - c['Close'])/sl_dist - 0.04, 2)
                        trades.append({'Date': dt, 'R': r_eod, 'Win': r_eod > 0, 'Type': 'Short'})
                        traded = True; break
                if traded: break

    return pd.DataFrame(trades)

if __name__ == '__main__':
    print('Testing Mean Reversion from VWAP Extremes on Nifty...')
    nifty = resample_5min(load_nifty())
    res = test_mean_reversion_vwap_extremes(nifty, is_index=True)
    if len(res) > 0:
        win_rate = res['Win'].mean() * 100
        cum_r = res['R'].cumsum()
        max_dd = (cum_r - cum_r.cummax()).min()
        print('Trades:', len(res), 'Win Rate:', round(win_rate, 1), '% Total R:', round(res['R'].sum(), 1), 'Max DD:', round(max_dd, 1), 'R')
