import os
import pandas as pd
import numpy as np
from datetime import time
from nifty_3m_ifvg_master import load_and_resample_nifty_3m, detect_ifvg_signals_for_day

def generate_optimal_nifty_ifvg_report():
    df_3m = load_and_resample_nifty_3m()
    dates = sorted(df_3m['Date'].unique())
    grouped = {d: g.reset_index(drop=True) for d, g in df_3m.groupby('Date')}

    # Optimal Strategy Parameters:
    # Asset: NIFTY 50
    # Timeframe: 3-Minute
    # Core Setup: First 3m IFVG of the Day (with Wick-Out handling)
    # SL: Formation Extreme (Box Max for Short, Box Min for Long) + 2 pts buffer, with Min SL = 0.20%
    # TP: 1:2.5 Risk-to-Reward
    # Trailing: Optional / EOD Square-off at 15:15 IST

    trades = []
    for dt in dates:
        day_df = grouped[dt]
        signals = detect_ifvg_signals_for_day(day_df, min_gap_pts=3.0)
        if not signals: continue

        sig = signals[0] # First IFVG of the day
        bar_idx = sig['signal_bar']
        direction = sig['direction']
        entry = sig['entry_price']

        if direction == 'BUY':
            raw_sl = sig['fvg_box_min'] - 2.0
            sl_dist = entry - raw_sl
            min_sl_dist = entry * 0.0020
            if sl_dist < min_sl_dist:
                sl_dist = min_sl_dist
                sl = entry - sl_dist
            else:
                sl = raw_sl

            if sl_dist > entry * 0.0060: continue
            tp = entry + (sl_dist * 2.5)

        elif direction == 'SELL':
            raw_sl = sig['fvg_box_max'] + 2.0
            sl_dist = raw_sl - entry
            min_sl_dist = entry * 0.0020
            if sl_dist < min_sl_dist:
                sl_dist = min_sl_dist
                sl = entry + sl_dist
            else:
                sl = raw_sl

            if sl_dist > entry * 0.0060: continue
            tp = entry - (sl_dist * 2.5)

        final_r = None
        highs = day_df['High'].values
        lows = day_df['Low'].values
        closes = day_df['Close'].values
        times = day_df['Time'].values

        for m in range(bar_idx + 1, len(day_df)):
            m_h = highs[m]
            m_l = lows[m]
            m_c = closes[m]
            m_t = times[m]

            if direction == 'BUY':
                if m_l <= sl:
                    final_r = -1.04 # 1R loss + 0.04R friction
                    break
                if m_h >= tp:
                    final_r = 2.46 # 2.5R win - 0.04R friction
                    break
                if m_t >= time(15, 15):
                    final_r = round((m_c - entry) / sl_dist - 0.04, 2)
                    break

            elif direction == 'SELL':
                if m_h >= sl:
                    final_r = -1.04
                    break
                if m_l <= tp:
                    final_r = 2.46
                    break
                if m_t >= time(15, 15):
                    final_r = round((entry - m_c) / sl_dist - 0.04, 2)
                    break

        if final_r is not None:
            trades.append({
                'Date': dt,
                'Time': sig['time'].strftime('%H:%M'),
                'Direction': direction,
                'Entry': round(entry, 2),
                'SL': round(sl, 2),
                'TP': round(tp, 2),
                'SL_Points': round(sl_dist, 1),
                'SL_Pct': round(sl_dist / entry * 100, 2),
                'R': final_r,
                'Win': final_r > 0
            })

    df = pd.DataFrame(trades)
    df['Date'] = pd.to_datetime(df['Date'])
    df['Year'] = df['Date'].dt.year
    df['YM'] = df['Date'].dt.to_period('M')

    # Year by year
    yearly = df.groupby('Year').agg(
        Trades=('R', 'count'),
        Wins=('Win', 'sum'),
        Total_R=('R', 'sum')
    ).reset_index()
    yearly['WinRate'] = round(yearly['Wins'] / yearly['Trades'] * 100, 1)
    yearly['Total_R'] = round(yearly['Total_R'], 1)

    # Monthly summary
    monthly = df.groupby('YM').agg(
        Trades=('R', 'count'),
        Wins=('Win', 'sum'),
        Total_R=('R', 'sum')
    ).reset_index()
    monthly['WinRate'] = round(monthly['Wins'] / monthly['Trades'] * 100, 1)
    monthly['Total_R'] = round(monthly['Total_R'], 1)

    tot_trades = len(df)
    tot_r = df['R'].sum()
    wr = (df['R'] > 0).mean() * 100
    cum = df['R'].cumsum()
    max_dd = (cum - cum.cummax()).min()
    pf = df[df['R'] > 0]['R'].sum() / abs(df[df['R'] < 0]['R'].sum())
    avg_win = df[df['R'] > 0]['R'].mean()
    avg_loss = abs(df[df['R'] < 0]['R'].mean())

    print("\n" + "="*70)
    print("   OPTIMAL NIFTY 3M IFVG STRATEGY PERFORMANCE AUDIT (2022-2026)")
    print("="*70)
    print(f"Total Trades Taken   : {tot_trades} (1 trade per trading day)")
    print(f"Overall Win Rate     : {wr:.1f}%")
    print(f"Average Win          : +{avg_win:.2f}R")
    print(f"Average Loss         : -{avg_loss:.2f}R")
    print(f"Profit Factor        : {pf:.2f}")
    print(f"TOTAL REALIZED R     : {tot_r:+.1f}R")
    print(f"Average Monthly R    : {tot_r / len(monthly):+.2f}R / month")
    print(f"Maximum Drawdown     : {max_dd:.1f}R")
    print(f"Average SL Points    : {df['SL_Points'].mean():.1f} pts ({df['SL_Pct'].mean():.2f}%)")
    print("="*70)

    print("\nYearly Breakdown:")
    print(yearly.to_string(index=False))

    print("\nRecent 12 Months Breakdown:")
    print(monthly.tail(12).to_string(index=False))

    df.to_csv('reports/nifty_3m_ifvg_trades.csv', index=False)
    monthly.to_csv('reports/nifty_3m_ifvg_monthly.csv', index=False)

if __name__ == '__main__':
    generate_optimal_nifty_ifvg_report()
