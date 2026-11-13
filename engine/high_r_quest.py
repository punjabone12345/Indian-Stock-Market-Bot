import sys
sys.path.append('engine')
import os
import pandas as pd
import numpy as np
from datetime import time
from data_loader import resample_5min
from master_quant_system import UNIVERSE_TOP30, load_universe_data

def test_high_expectancy_setups(stocks):
    print("\n" + "="*70)
    print("   RESEARCHING HIGH-EXPECTANCY ARCHITECTURES (TARGET: 25R/MONTH)")
    print("="*70)

    sample_sym = list(stocks.keys())[0]
    all_dates = sorted(stocks[sample_sym]['Date'].unique())

    # Test Setup: Opening Drive & 5-Min Inside Bar Expansion
    # In strong daily trends, when a stock has gap + volume, the first 5-min pause (Inside Bar)
    # offers an explosive entry with a tight structural stop and 1:2.5 R:R!
    
    trades = []
    for dt in all_dates:
        for sym, df_5m in stocks.items():
            g = df_5m[df_5m['Date'] == dt].reset_index(drop=True)
            if len(g) < 25 or pd.isna(g['PDC'].iloc[0]) or pd.isna(g['DailyBull'].iloc[0]): continue

            pdc = g['PDC'].iloc[0]
            gap_pct = (g.iloc[0]['Open'] - pdc) / pdc
            is_bull = g['DailyBull'].iloc[0]

            # Scan between 09:20 and 11:00 AM (candles 1 to 20)
            for i in range(1, min(len(g)-5, 18)):
                c1 = g.iloc[i-1] # Mother bar
                c2 = g.iloc[i]   # Current bar

                # Check if c2 is an Inside Bar (High < c1.High and Low > c1.Low)
                is_inside = (c2['High'] <= c1['High'] * 1.0005) and (c2['Low'] >= c1['Low'] * 0.9995)
                
                # Check BULLISH INSIDE BAR BREAKOUT:
                # Stock is in Daily Bull trend, Price > VWAP, Gap > 0
                if is_bull and is_inside and c2['Close'] > c2['VWAP'] and gap_pct > -0.002:
                    # Entry on breakout of mother bar high in subsequent candle
                    if i + 1 >= len(g): continue
                    c3 = g.iloc[i+1]
                    if c3['High'] > c1['High']:
                        entry = c1['High']
                        # SL below the inside bar low
                        sl = c2['Low'] - (entry * 0.0005)
                        sl_dist = entry - sl
                        if sl_dist < entry * 0.0050: # Enforce 0.50% min SL
                            sl_dist = entry * 0.0050
                            sl = entry - sl_dist
                            
                        tp = entry + (sl_dist * 2.5) # 1:2.5 R:R

                        # Forward simulate
                        for j in range(i+2, len(g)):
                            c = g.iloc[j]
                            if c['Low'] <= sl:
                                trades.append({'Date': dt, 'Time': c3['Time'], 'Symbol': sym, 'R': -1.04, 'Win': False})
                                break
                            if c['High'] >= tp:
                                trades.append({'Date': dt, 'Time': c3['Time'], 'Symbol': sym, 'R': 2.46, 'Win': True})
                                break
                            if c['Time'] >= time(15, 15):
                                r_eod = round((c['Close'] - entry)/sl_dist - 0.04, 2)
                                trades.append({'Date': dt, 'Time': c3['Time'], 'Symbol': sym, 'R': r_eod, 'Win': r_eod > 0})
                                break
                        break

                # Check BEARISH INSIDE BAR BREAKOUT:
                elif (not is_bull) and is_inside and c2['Close'] < c2['VWAP'] and gap_pct < 0.002:
                    if i + 1 >= len(g): continue
                    c3 = g.iloc[i+1]
                    if c3['Low'] < c1['Low']:
                        entry = c1['Low']
                        sl = c2['High'] + (entry * 0.0005)
                        sl_dist = sl - entry
                        if sl_dist < entry * 0.0050:
                            sl_dist = entry * 0.0050
                            sl = entry + sl_dist
                            
                        tp = entry - (sl_dist * 2.5)

                        for j in range(i+2, len(g)):
                            c = g.iloc[j]
                            if c['High'] >= sl:
                                trades.append({'Date': dt, 'Time': c3['Time'], 'Symbol': sym, 'R': -1.04, 'Win': False})
                                break
                            if c['Low'] <= tp:
                                trades.append({'Date': dt, 'Time': c3['Time'], 'Symbol': sym, 'R': 2.46, 'Win': True})
                                break
                            if c['Time'] >= time(15, 15):
                                r_eod = round((entry - c['Close'])/sl_dist - 0.04, 2)
                                trades.append({'Date': dt, 'Time': c3['Time'], 'Symbol': sym, 'R': r_eod, 'Win': r_eod > 0})
                                break
                        break

    res_df = pd.DataFrame(trades).sort_values(['Date', 'Time']).reset_index(drop=True)
    print(f"Total Raw Trades: {len(res_df)}")

    # Apply Portfolio Selection: Max 3 quality trades/day, circuit breaker 2 losses/day
    filtered = []
    for dt, g in res_df.groupby('Date'):
        cnt = 0
        losses = 0
        for _, t in g.iterrows():
            if cnt >= 3 or losses >= 2: break
            filtered.append(t)
            cnt += 1
            if t['R'] < 0: losses += 1

    f_df = pd.DataFrame(filtered)
    print(f"Portfolio Filtered Trades: {len(f_df)}")

    # Metrics
    total_trades = len(f_df)
    wins = f_df[f_df['R'] > 0]
    losses = f_df[f_df['R'] < 0]
    win_rate = (len(wins) / total_trades) * 100
    total_r = f_df['R'].sum()
    avg_win = wins['R'].mean()
    avg_loss = abs(losses['R'].mean())
    pf = wins['R'].sum() / abs(losses['R'].sum())

    cum_series = f_df['R'].cumsum()
    max_dd = (cum_series - cum_series.cummax()).min()

    f_df['YM'] = pd.to_datetime(f_df['Date']).dt.to_period('M')
    monthly = f_df.groupby('YM')['R'].sum()
    num_months = len(monthly)
    avg_r_month = total_r / num_months

    print("\n" + "="*70)
    print(f"Total Trades        : {total_trades} (~{round(total_trades/num_months, 1)} trades/month)")
    print(f"Win Rate            : {win_rate:.1f}%")
    print(f"Average Win (R)     : +{avg_win:.2f}R")
    print(f"Average Loss (R)    : -{avg_loss:.2f}R")
    print(f"Profit Factor       : {pf:.2f}")
    print(f"Total Return (R)    : +{total_r:.1f}R")
    print(f"Average Return/Month: +{avg_r_month:.1f}R")
    print(f"Maximum Drawdown    : {max_dd:.1f}R")
    print(f"Profitable Months   : {(monthly > 0).sum()} / {num_months}")
    print("="*70)

    print("\nSample Monthly Results:")
    print(monthly.tail(12))

if __name__ == '__main__':
    stocks = load_universe_data(UNIVERSE_TOP30)
    test_high_expectancy_setups(stocks)
