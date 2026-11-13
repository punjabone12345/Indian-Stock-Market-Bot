import sys
sys.path.append('engine')
import os
import glob
import pandas as pd
import numpy as np
from datetime import time

# Top liquid high-beta universe
UNIVERSE = [
    'RELIANCE', 'TCS', 'HDFCBANK', 'ICICIBANK', 'INFY', 'SBIN',
    'BHARTIARTL', 'LT', 'AXISBANK', 'BAJFINANCE', 'TITAN', 'MARUTI',
    'KOTAKBANK', 'WIPRO', 'SUNPHARMA', 'TATASTEEL', 'ADANIENT', 'INDUSINDBK'
]

def load_1m_data(symbols):
    stocks = {}
    for s in symbols:
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

        # Intraday VWAP
        df['Typ'] = (df['High'] + df['Low'] + df['Close']) / 3.0
        df['PV'] = df['Typ'] * df['Volume']
        df['CumPV'] = df.groupby('Date')['PV'].cumsum()
        df['CumV'] = df.groupby('Date')['Volume'].cumsum()
        df['VWAP'] = df['CumPV'] / df['CumV']

        # Daily Trend & PDC
        daily_summary = df.groupby('Date').agg({'Close': 'last', 'Volume': 'sum'}).shift(1)
        daily_close = daily_summary['Close']
        daily_vol = daily_summary['Volume']
        daily_ema20 = daily_close.ewm(span=20, adjust=False).mean()
        daily_ema50 = daily_close.ewm(span=50, adjust=False).mean()
        df['DailyBull'] = df['Date'].map(daily_ema20 > daily_ema50)
        df['PDC'] = df['Date'].map(daily_close)
        df['DailyVolMA20'] = df['Date'].map(daily_vol.rolling(20, min_periods=1).mean())

        stocks[s] = df
        print(f"Loaded {s}: {len(df)} 1-minute candles")
    return stocks

def run_precision_backtest(stocks):
    print("\n" + "="*70)
    print("   RUNNING PRECISION MICRO-STRUCTURE PRICE ACTION ENGINE (4 YEARS)")
    print("   Released: 0.50% Minimum SL Floor -> Precision 0.18%-0.25% Invalidation")
    print("   Released: Trade-Every-Day -> High-Expansion Catalyst Days Only")
    print("="*70)

    sample_sym = list(stocks.keys())[0]
    all_dates = sorted(stocks[sample_sym]['Date'].unique())

    all_trades = []

    for dt in all_dates:
        # Step 1: Scan for stocks with genuine Catalyst / Expansion Volume (RVOL >= 1.6x OR Gap >= 0.8%)
        day_candidates = []
        for sym, df_1m in stocks.items():
            g = df_1m[df_1m['Date'] == dt].reset_index(drop=True)
            if len(g) < 100 or pd.isna(g['PDC'].iloc[0]) or pd.isna(g['DailyBull'].iloc[0]): continue

            # Opening 15 minutes (candles 0 to 14)
            first15 = g.iloc[:15]
            pdc = g['PDC'].iloc[0]
            gap_pct = abs(g.iloc[0]['Open'] - pdc) / pdc
            
            # Opening volume vs daily average
            day_vol_ma = g['DailyVolMA20'].iloc[0]
            m15_vol = first15['Volume'].sum()
            vol_ratio = (m15_vol / (day_vol_ma / 25.0)) if day_vol_ma > 0 else 1.0

            if vol_ratio >= 1.6 or gap_pct >= 0.008:
                score = vol_ratio * 2.0 + (gap_pct * 100)
                day_candidates.append({
                    'symbol': sym,
                    'df': g,
                    'score': score,
                    'is_bull': g['DailyBull'].iloc[0],
                    'ib_h': first15['High'].max(),
                    'ib_l': first15['Low'].min()
                })

        # Rank and pick Top 3 highest-conviction catalyst stocks of the day
        day_candidates.sort(key=lambda x: x['score'], reverse=True)
        top_picks = day_candidates[:3]

        if not top_picks:
            continue

        day_trades = 0
        day_losses = 0

        for pick in top_picks:
            if day_trades >= 2 or day_losses >= 2: break
            sym = pick['symbol']
            g = pick['df']
            is_bull = pick['is_bull']
            ib_h = pick['ib_h']
            ib_l = pick['ib_l']

            # Scan 1-minute candles between 09:30 and 11:00 AM (candles 15 to 105)
            for i in range(15, min(len(g)-15, 105)):
                if day_trades >= 2 or day_losses >= 2: break
                row = g.iloc[i]

                # ============================================================
                # SETUP: MICRO-STRUCTURE DISPLACEMENT & FVG RETEST ENTRY
                # ============================================================
                # Condition: Bullish Displacement creates a 1m FVG
                # Candle i-2, i-1, i:
                c1 = g.iloc[i-2]
                c2 = g.iloc[i-1] # Displacement candle
                c3 = g.iloc[i]   # FVG validation candle

                # LONG FVG: c3.Low > c1.High (Unmitigated Fair Value Gap)
                if is_bull and c3['Low'] > c1['High'] and c3['Close'] > c3['VWAP'] and c3['Close'] > ib_h:
                    fvg_top = c3['Low']
                    fvg_bottom = c1['High']
                    fvg_size = fvg_top - fvg_bottom

                    # Look for retest of FVG in subsequent candles (within next 15 mins)
                    for k in range(i+1, min(len(g)-5, i+20)):
                        rk = g.iloc[k]
                        # Retest condition: Price dips into the FVG (Low <= fvg_top) and bounces
                        if rk['Low'] <= fvg_top and rk['Close'] >= fvg_bottom:
                            entry = fvg_top
                            # Precision structural stop-loss: Just below the FVG bottom + 0.05%
                            raw_sl = fvg_bottom - (entry * 0.0005)
                            sl_dist = entry - raw_sl
                            
                            # Micro-structure SL limits: between 0.15% and 0.35%
                            if sl_dist < entry * 0.0015:
                                sl_dist = entry * 0.0015
                                raw_sl = entry - sl_dist
                            if sl_dist > entry * 0.0035:
                                sl_dist = entry * 0.0035
                                raw_sl = entry - sl_dist

                            # Asymmetric Targets:
                            # Target 1: +2.5R (Exit 50%, Move SL to Breakeven +0.1R)
                            # Target 2: +5.0R (Exit remaining 50%)
                            tp1 = entry + (sl_dist * 2.5)
                            tp2 = entry + (sl_dist * 5.0)
                            be_sl = entry + (sl_dist * 0.1)

                            t1_hit = False
                            current_sl = raw_sl
                            final_r = None

                            for m in range(k+1, len(g)):
                                cm = g.iloc[m]

                                # Check Target 1 (+2.5R)
                                if not t1_hit and cm['High'] >= tp1:
                                    t1_hit = True
                                    current_sl = be_sl # Locked at breakeven

                                # Check Stop Loss
                                if cm['Low'] <= current_sl:
                                    if not t1_hit:
                                        final_r = -1.04 # 1R loss + slippage
                                    else:
                                        final_r = round(0.5 * 2.46 + 0.5 * 0.06, 2) # +1.26R net profit!
                                    break

                                # Check Target 2 (+5.0R)
                                if t1_hit and cm['High'] >= tp2:
                                    final_r = round(0.5 * 2.46 + 0.5 * 4.96, 2) # +3.71R net profit!
                                    break

                                # EOD 15:15 PM Square-off
                                if cm['Time'] >= time(15, 15):
                                    r_eod = (cm['Close'] - entry)/sl_dist - 0.04
                                    if not t1_hit:
                                        final_r = round(r_eod, 2)
                                    else:
                                        final_r = round(0.5 * 2.46 + 0.5 * max(0.06, r_eod), 2)
                                    break

                            if final_r is not None:
                                all_trades.append({
                                    'Date': dt,
                                    'Time': rk['Time'],
                                    'Symbol': sym,
                                    'Direction': 'BUY',
                                    'Setup': 'Precision FVG Retest Long',
                                    'SL_Pct': round((sl_dist/entry)*100, 2),
                                    'R': final_r,
                                    'Win': final_r > 0
                                })
                                day_trades += 1
                                if final_r < 0: day_losses += 1
                                break
                    if day_trades > 0: break

                # SHORT FVG: c3.High < c1.Low (Bearish Fair Value Gap)
                elif (not is_bull) and c3['High'] < c1['Low'] and c3['Close'] < c3['VWAP'] and c3['Close'] < ib_l:
                    fvg_bottom = c3['High']
                    fvg_top = c1['Low']

                    for k in range(i+1, min(len(g)-5, i+20)):
                        rk = g.iloc[k]
                        if rk['High'] >= fvg_bottom and rk['Close'] <= fvg_top:
                            entry = fvg_bottom
                            raw_sl = fvg_top + (entry * 0.0005)
                            sl_dist = raw_sl - entry
                            
                            if sl_dist < entry * 0.0015:
                                sl_dist = entry * 0.0015
                                raw_sl = entry + sl_dist
                            if sl_dist > entry * 0.0035:
                                sl_dist = entry * 0.0035
                                raw_sl = entry + sl_dist

                            tp1 = entry - (sl_dist * 2.5)
                            tp2 = entry - (sl_dist * 5.0)
                            be_sl = entry - (sl_dist * 0.1)

                            t1_hit = False
                            current_sl = raw_sl
                            final_r = None

                            for m in range(k+1, len(g)):
                                cm = g.iloc[m]

                                if not t1_hit and cm['Low'] <= tp1:
                                    t1_hit = True
                                    current_sl = be_sl

                                if cm['High'] >= current_sl:
                                    if not t1_hit:
                                        final_r = -1.04
                                    else:
                                        final_r = round(0.5 * 2.46 + 0.5 * 0.06, 2)
                                    break

                                if t1_hit and cm['Low'] <= tp2:
                                    final_r = round(0.5 * 2.46 + 0.5 * 4.96, 2)
                                    break

                                if cm['Time'] >= time(15, 15):
                                    r_eod = (entry - cm['Close'])/sl_dist - 0.04
                                    if not t1_hit:
                                        final_r = round(r_eod, 2)
                                    else:
                                        final_r = round(0.5 * 2.46 + 0.5 * max(0.06, r_eod), 2)
                                    break

                            if final_r is not None:
                                all_trades.append({
                                    'Date': dt,
                                    'Time': rk['Time'],
                                    'Symbol': sym,
                                    'Direction': 'SELL',
                                    'Setup': 'Precision FVG Retest Short',
                                    'SL_Pct': round((sl_dist/entry)*100, 2),
                                    'R': final_r,
                                    'Win': final_r > 0
                                })
                                day_trades += 1
                                if final_r < 0: day_losses += 1
                                break
                    if day_trades > 0: break

    raw_df = pd.DataFrame(all_trades).sort_values(['Date', 'Time']).reset_index(drop=True)
    print(f"\nTotal Precision Trades Executed: {len(raw_df)}")

    # Apply Prop-Desk Circuit Breakers:
    # 1. Monthly Loss Cap: Max -4.0R in any calendar month
    # 2. De-leveraging: If current drawdown from peak > 3.0R, position size scales to 0.5R
    raw_df['YM'] = pd.to_datetime(raw_df['Date']).dt.to_period('M')

    managed = []
    cum_r = 0.0
    peak_r = 0.0

    for ym, m_group in raw_df.groupby('YM'):
        m_r = 0.0
        for _, t in m_group.iterrows():
            if m_r <= -4.0:
                continue # Monthly circuit breaker

            dd = cum_r - peak_r
            risk_mult = 0.5 if dd <= -3.0 else 1.0
            actual_r = round(t['R'] * risk_mult, 2)

            m_r += actual_r
            cum_r += actual_r
            if cum_r > peak_r:
                peak_r = cum_r

            managed.append({
                'Date': t['Date'],
                'Time': t['Time'],
                'Symbol': t['Symbol'],
                'Direction': t['Direction'],
                'Setup': t['Setup'],
                'SL_Pct': t['SL_Pct'],
                'R': actual_r,
                'Win': actual_r > 0,
                'YM': ym
            })

    m_df = pd.DataFrame(managed)
    print(f"Final Managed Trades Count: {len(m_df)}")

    total_trades = len(m_df)
    wins = m_df[m_df['R'] > 0]
    losses = m_df[m_df['R'] < 0]
    win_rate = (len(wins) / total_trades) * 100
    total_r = m_df['R'].sum()
    avg_win = wins['R'].mean()
    avg_loss = abs(losses['R'].mean())
    pf = wins['R'].sum() / abs(losses['R'].sum())

    cum_series = m_df['R'].cumsum()
    max_dd = (cum_series - cum_series.cummax()).min()

    monthly = m_df.groupby('YM').agg(
        Trades=('R', 'count'),
        Wins=('Win', 'sum'),
        Total_R=('R', 'sum')
    ).reset_index()
    monthly['WinRate'] = round(monthly['Wins'] / monthly['Trades'] * 100, 1)
    monthly['Total_R'] = round(monthly['Total_R'], 1)
    monthly['Profit_INR_1k'] = (monthly['Total_R'] * 1000).astype(int)

    num_months = len(monthly)
    avg_r_month = total_r / num_months
    annual_r = total_r / (num_months / 12.0)
    calmar = abs(annual_r / max_dd)

    print("\n" + "="*70)
    print("      PRECISION MICRO-STRUCTURE PRICE ACTION FINAL AUDIT")
    print("="*70)
    print(f"Horizon               : October 2022 to November 2026 ({num_months} Months)")
    print(f"Total Trades Taken    : {total_trades} (~{round(total_trades/num_months, 1)} trades/month, ~{round(total_trades/(num_months*21), 1)} trades/day)")
    print(f"Average SL Distance   : {m_df['SL_Pct'].mean():.2f}%")
    print(f"Overall Win Rate      : {win_rate:.1f}%")
    print(f"Average Win (R)       : +{avg_win:.2f}R")
    print(f"Average Loss (R)      : -{avg_loss:.2f}R")
    print(f"Profit Factor         : {pf:.2f}")
    print(f"Total Realized Return : +{total_r:.1f}R  (₹{int(total_r * 1000):,} @ ₹1k risk/trade)")
    print(f"Average Return / Month: +{avg_r_month:.1f}R")
    print(f"Maximum Portfolio DD  : {max_dd:.1f}R")
    print(f"Calmar Ratio          : {calmar:.2f}")
    print(f"Profitable Months     : {(monthly['Total_R'] > 0).sum()} / {num_months}")
    print("="*70)

    print("\nSample Monthly Performance (Last 15 Months):")
    print(monthly.tail(15).to_string(index=False))

    os.makedirs('reports', exist_ok=True)
    m_df.to_csv('reports/precision_price_action_trades.csv', index=False)
    monthly.to_csv('reports/precision_price_action_monthly.csv', index=False)

if __name__ == '__main__':
    stocks = load_1m_data(UNIVERSE)
    run_precision_backtest(stocks)
