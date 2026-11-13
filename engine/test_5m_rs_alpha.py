import sys
sys.path.append('engine')
import os
import pandas as pd
import numpy as np
from datetime import time
from master_quant_system import UNIVERSE_TOP30

def test_5m_rs_system():
    print("Testing 5-Minute High-Conviction RS Momentum System (Long-Only + Uncapped Trailing)...")
    stocks = {}
    for s in UNIVERSE_TOP30:
        f_prev = f'data/stocks/{s}_prev.parquet'
        f_2026 = f'data/stocks/{s}_2026.parquet'
        dfs = []
        if os.path.exists(f_prev):
            d1 = pd.read_parquet(f_prev)
            d1['Timestamp'] = pd.to_datetime(d1['Date'])
            d1 = d1[d1['Timestamp'] >= '2022-10-01']
            dfs.append(d1[['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']])
        if os.path.exists(f_2026):
            d2 = pd.read_parquet(f_2026)
            d2['Timestamp'] = pd.to_datetime(d2['Date'])
            dfs.append(d2[['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']])
        if not dfs: continue

        df = pd.concat(dfs).sort_values('Timestamp').drop_duplicates('Timestamp').reset_index(drop=True)
        df['Time'] = df['Timestamp'].dt.time
        df['Date'] = df['Timestamp'].dt.date
        df = df[(df['Time'] >= time(9, 15)) & (df['Time'] <= time(15, 30))].copy()

        # Resample to 5m
        df.set_index('Timestamp', inplace=True)
        df_5m = df.groupby('Date').resample('5min', origin='start').agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }).dropna().reset_index()

        df_5m['Time'] = df_5m['Timestamp'].dt.time
        df_5m['Typ'] = (df_5m['High'] + df_5m['Low'] + df_5m['Close']) / 3.0
        df_5m['PV'] = df_5m['Typ'] * df_5m['Volume']
        df_5m['CumPV'] = df_5m.groupby('Date')['PV'].cumsum()
        df_5m['CumV'] = df_5m.groupby('Date')['Volume'].cumsum()
        df_5m['VWAP'] = df_5m['CumPV'] / df_5m['CumV']

        daily_summary = df_5m.groupby('Date').agg({
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }).shift(1)

        df_5m['PDC'] = df_5m['Date'].map(daily_summary['Close'])
        df_5m['DailyVolMA20'] = df_5m['Date'].map(daily_summary['Volume'].rolling(20, min_periods=1).mean())

        date_groups = {}
        for d, g in df_5m.groupby('Date', sort=False):
            date_groups[d] = {
                'Open': g['Open'].values,
                'High': g['High'].values,
                'Low': g['Low'].values,
                'Close': g['Close'].values,
                'Volume': g['Volume'].values,
                'VWAP': g['VWAP'].values,
                'Time': g['Time'].values,
                'PDC': g['PDC'].iloc[0],
                'VolMA': g['DailyVolMA20'].iloc[0],
                'len': len(g)
            }
        stocks[s] = date_groups

    sample_sym = list(stocks.keys())[0]
    all_dates = sorted(stocks[sample_sym].keys())

    all_trades = []

    for dt in all_dates:
        day_trades = 0
        day_losses = 0

        # Scan for Top 3 Relative Strength Leaders at 09:30 (first 3 5m candles)
        rs_candidates = []
        for sym in stocks.keys():
            if dt not in stocks[sym]: continue
            d = stocks[sym][dt]
            if d['len'] < 20 or pd.isna(d['PDC']) or d['PDC'] <= 0: continue

            c3 = d['Close'][2] # 09:30 close
            pdc = d['PDC']
            rel_gain = (c3 - pdc) / pdc
            v3 = np.sum(d['Volume'][:3])
            vol_ma = d['VolMA']
            rvol = (v3 / (vol_ma / 25.0)) if vol_ma and vol_ma > 0 else 1.0

            # Only strong bullish momentum leaders
            if rel_gain >= 0.005 and rvol >= 1.3:
                rs_candidates.append({
                    'symbol': sym,
                    'data': d,
                    'rel_gain': rel_gain,
                    'rvol': rvol,
                    'ib_h': np.max(d['High'][:3]),
                    'ib_l': np.min(d['Low'][:3]),
                    'score': rvol * 2.0 + (rel_gain * 100)
                })

        rs_candidates.sort(key=lambda x: x['score'], reverse=True)

        for cand in rs_candidates[:3]:
            if day_trades >= 3 or day_losses >= 2: break
            sym = cand['symbol']
            d = cand['data']
            ib_h = cand['ib_h']

            # Look for 5m Breakout or 5m Pullback to VWAP
            for i in range(3, min(d['len'] - 4, 30)): # 09:30 to 11:45 AM
                if day_trades >= 3 or day_losses >= 2: break
                c_close = d['Close'][i]
                c_low = d['Low'][i]
                c_open = d['Open'][i]
                c_vwap = d['VWAP'][i]

                # Setup: 5m Candle closes above IBH and above VWAP
                if c_close > ib_h and c_close > c_vwap and c_close > c_open:
                    entry = c_close
                    raw_sl = max(c_vwap, d['Low'][i-1], d['Open'][i]) - (entry * 0.0005)
                    sl_dist = entry - raw_sl

                    if entry * 0.0018 <= sl_dist <= entry * 0.0040:
                        # Asymmetric Targets: 50% at +2.5R, 50% runner to +6.0R or EOD
                        tp1 = entry + (sl_dist * 2.5)
                        tp2 = entry + (sl_dist * 6.0)
                        be_sl = entry + (sl_dist * 0.1)

                        t1_hit = False
                        current_sl = raw_sl
                        final_r = None

                        for m in range(i + 1, d['len']):
                            m_h = d['High'][m]
                            m_l = d['Low'][m]
                            m_t = d['Time'][m]
                            m_c = d['Close'][m]

                            if not t1_hit and m_h >= tp1:
                                t1_hit = True
                                current_sl = be_sl

                            if m_l <= current_sl:
                                final_r = -1.04 if not t1_hit else round(0.5 * 2.46 + 0.5 * 0.06, 2)
                                break

                            if t1_hit and m_h >= tp2:
                                final_r = round(0.5 * 2.46 + 0.5 * 5.96, 2)
                                break

                            if m_t >= time(15, 15):
                                r_eod = (m_c - entry) / sl_dist - 0.04
                                final_r = round(r_eod, 2) if not t1_hit else round(0.5 * 2.46 + 0.5 * max(0.06, r_eod), 2)
                                break

                        if final_r is not None:
                            all_trades.append({
                                'Date': dt,
                                'Time': d['Time'][i],
                                'Symbol': sym,
                                'Direction': 'BUY',
                                'SL_Pct': round((sl_dist / entry) * 100, 2),
                                'R': final_r,
                                'Win': final_r > 0
                            })
                            day_trades += 1
                            if final_r < 0: day_losses += 1
                            break

    res_df = pd.DataFrame(all_trades).sort_values(['Date', 'Time']).reset_index(drop=True)
    res_df['YM'] = pd.to_datetime(res_df['Date']).dt.to_period('M')

    total_trades = len(res_df)
    wins = res_df[res_df['R'] > 0]
    losses = res_df[res_df['R'] < 0]
    win_rate = (len(wins) / total_trades) * 100
    total_r = res_df['R'].sum()
    avg_win = wins['R'].mean()
    avg_loss = abs(losses['R'].mean())
    pf = wins['R'].sum() / abs(losses['R'].sum())

    cum_series = res_df['R'].cumsum()
    max_dd = (cum_series - cum_series.cummax()).min()

    monthly = res_df.groupby('YM').agg(
        Trades=('R', 'count'),
        Wins=('Win', 'sum'),
        Total_R=('R', 'sum')
    ).reset_index()
    monthly['WinRate'] = round(monthly['Wins'] / monthly['Trades'] * 100, 1)
    monthly['Total_R'] = round(monthly['Total_R'], 1)

    num_months = len(monthly)
    avg_r_month = total_r / num_months

    print("\n" + "="*70)
    print("      5-MINUTE RS MOMENTUM SYSTEM AUDIT (2022 - 2026)")
    print("="*70)
    print(f"Horizon               : October 2022 to November 2026 ({num_months} Months)")
    print(f"Total Trades Taken    : {total_trades} (~{round(total_trades/num_months, 1)} trades/month)")
    print(f"Average SL Distance   : {res_df['SL_Pct'].mean():.2f}%")
    print(f"Overall Win Rate      : {win_rate:.1f}%")
    print(f"Average Win (R)       : +{avg_win:.2f}R")
    print(f"Average Loss (R)      : -{avg_loss:.2f}R")
    print(f"Profit Factor         : {pf:.2f}")
    print(f"TOTAL REALIZED RETURN : +{total_r:.1f}R")
    print(f"AVERAGE RETURN / MONTH: +{avg_r_month:.1f}R")
    print(f"Maximum Portfolio DD  : {max_dd:.1f}R")
    print("="*70)

if __name__ == '__main__':
    test_5m_rs_system()
