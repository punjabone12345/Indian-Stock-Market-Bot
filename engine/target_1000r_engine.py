import sys
sys.path.append('engine')
import os
import glob
import pandas as pd
import numpy as np
from datetime import time
from master_quant_system import UNIVERSE_TOP30

def load_all_1m_data(symbols):
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

        df['Typ'] = (df['High'] + df['Low'] + df['Close']) / 3.0
        df['PV'] = df['Typ'] * df['Volume']
        df['CumPV'] = df.groupby('Date')['PV'].cumsum()
        df['CumV'] = df.groupby('Date')['Volume'].cumsum()
        df['VWAP'] = df['CumPV'] / df['CumV']

        daily_summary = df.groupby('Date').agg({'Close': 'last', 'Volume': 'sum'}).shift(1)
        daily_close = daily_summary['Close']
        daily_vol = daily_summary['Volume']
        daily_ema20 = daily_close.ewm(span=20, adjust=False).mean()
        daily_ema50 = daily_close.ewm(span=50, adjust=False).mean()
        df['DailyBull'] = df['Date'].map(daily_ema20 > daily_ema50)
        df['PDC'] = df['Date'].map(daily_close)
        df['DailyVolMA20'] = df['Date'].map(daily_vol.rolling(20, min_periods=1).mean())

        stocks[s] = df
        print(f"Loaded {s}: {len(df)} 1m candles")
    return stocks

def run_1000r_engine(stocks):
    print("\n" + "="*70)
    print("   EXECUTING 1000R INSTITUTIONAL PRECISION ENGINE (TOP 29 STOCKS)")
    print("   Target: ~20-25R / Month (~1000R in 4 Years)")
    print("   NO Monthly Circuit Breaker (Continuous Trading)")
    print("   Micro-Structure 0.15%-0.25% Structural Stops + Asymmetric Runners")
    print("="*70)

    sample_sym = list(stocks.keys())[0]
    all_dates = sorted(stocks[sample_sym]['Date'].unique())

    all_trades = []

    for dt in all_dates:
        # Step 1: Scan all 29 stocks for relative volume & momentum
        day_candidates = []
        for sym, df_1m in stocks.items():
            g = df_1m[df_1m['Date'] == dt].reset_index(drop=True)
            if len(g) < 100 or pd.isna(g['PDC'].iloc[0]) or pd.isna(g['DailyBull'].iloc[0]): continue

            first15 = g.iloc[:15]
            pdc = g['PDC'].iloc[0]
            gap_pct = abs(g.iloc[0]['Open'] - pdc) / pdc
            day_vol_ma = g['DailyVolMA20'].iloc[0]
            m15_vol = first15['Volume'].sum()
            vol_ratio = (m15_vol / (day_vol_ma / 25.0)) if day_vol_ma > 0 else 1.0

            # Active threshold to ensure ~2.5 - 3 trades/day
            if vol_ratio >= 1.2 or gap_pct >= 0.004:
                score = vol_ratio * 1.5 + (gap_pct * 100)
                day_candidates.append({
                    'symbol': sym,
                    'df': g,
                    'score': score,
                    'is_bull': g['DailyBull'].iloc[0],
                    'ib_h': first15['High'].max(),
                    'ib_l': first15['Low'].min()
                })

        day_candidates.sort(key=lambda x: x['score'], reverse=True)
        # Monitor top 8 active momentum candidates
        top_picks = day_candidates[:8]
        if not top_picks: continue

        day_trades = 0
        day_losses = 0

        for pick in top_picks:
            if day_trades >= 3 or day_losses >= 2: break
            sym = pick['symbol']
            g = pick['df']
            is_bull = pick['is_bull']
            ib_h = pick['ib_h']
            ib_l = pick['ib_l']

            for i in range(15, min(len(g)-15, 110)): # 09:30 to 11:05 AM
                if day_trades >= 3 or day_losses >= 2: break
                
                c1 = g.iloc[i-2]
                c2 = g.iloc[i-1]
                c3 = g.iloc[i]

                # LONG SETUP: Bullish FVG & MSS above VWAP
                if is_bull and c3['Low'] > c1['High'] and c3['Close'] > c3['VWAP'] and c3['Close'] > ib_h:
                    fvg_top = c3['Low']
                    fvg_bottom = c1['High']

                    for k in range(i+1, min(len(g)-5, i+20)):
                        rk = g.iloc[k]
                        if rk['Low'] <= fvg_top and rk['Close'] >= fvg_bottom:
                            entry = fvg_top
                            raw_sl = fvg_bottom - (entry * 0.0005)
                            sl_dist = entry - raw_sl
                            
                            if sl_dist < entry * 0.0015: sl_dist = entry * 0.0015; raw_sl = entry - sl_dist
                            if sl_dist > entry * 0.0035: sl_dist = entry * 0.0035; raw_sl = entry - sl_dist

                            # Targets: 50% at +2.5R, 50% at +5.0R with Breakeven
                            tp1 = entry + (sl_dist * 2.5)
                            tp2 = entry + (sl_dist * 5.0)
                            be_sl = entry + (sl_dist * 0.1)

                            t1_hit = False
                            current_sl = raw_sl
                            final_r = None

                            for m in range(k+1, len(g)):
                                cm = g.iloc[m]
                                if not t1_hit and cm['High'] >= tp1:
                                    t1_hit = True
                                    current_sl = be_sl

                                if cm['Low'] <= current_sl:
                                    final_r = -1.04 if not t1_hit else round(0.5 * 2.46 + 0.5 * 0.06, 2)
                                    break

                                if t1_hit and cm['High'] >= tp2:
                                    final_r = round(0.5 * 2.46 + 0.5 * 4.96, 2)
                                    break

                                if cm['Time'] >= time(15, 15):
                                    r_eod = (cm['Close'] - entry)/sl_dist - 0.04
                                    final_r = round(r_eod, 2) if not t1_hit else round(0.5 * 2.46 + 0.5 * max(0.06, r_eod), 2)
                                    break

                            if final_r is not None:
                                all_trades.append({
                                    'Date': dt,
                                    'Time': rk['Time'],
                                    'Symbol': sym,
                                    'Direction': 'BUY',
                                    'Setup': 'Precision FVG Long',
                                    'SL_Pct': round((sl_dist/entry)*100, 2),
                                    'R': final_r,
                                    'Win': final_r > 0
                                })
                                day_trades += 1
                                if final_r < 0: day_losses += 1
                                break
                    if day_trades > 0: break

                # SHORT SETUP: Bearish FVG & MSS below VWAP
                elif (not is_bull) and c3['High'] < c1['Low'] and c3['Close'] < c3['VWAP'] and c3['Close'] < ib_l:
                    fvg_bottom = c3['High']
                    fvg_top = c1['Low']

                    for k in range(i+1, min(len(g)-5, i+20)):
                        rk = g.iloc[k]
                        if rk['High'] >= fvg_bottom and rk['Close'] <= fvg_top:
                            entry = fvg_bottom
                            raw_sl = fvg_top + (entry * 0.0005)
                            sl_dist = raw_sl - entry
                            
                            if sl_dist < entry * 0.0015: sl_dist = entry * 0.0015; raw_sl = entry + sl_dist
                            if sl_dist > entry * 0.0035: sl_dist = entry * 0.0035; raw_sl = entry + sl_dist

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
                                    final_r = -1.04 if not t1_hit else round(0.5 * 2.46 + 0.5 * 0.06, 2)
                                    break

                                if t1_hit and cm['Low'] <= tp2:
                                    final_r = round(0.5 * 2.46 + 0.5 * 4.96, 2)
                                    break

                                if cm['Time'] >= time(15, 15):
                                    r_eod = (entry - cm['Close'])/sl_dist - 0.04
                                    final_r = round(r_eod, 2) if not t1_hit else round(0.5 * 2.46 + 0.5 * max(0.06, r_eod), 2)
                                    break

                            if final_r is not None:
                                all_trades.append({
                                    'Date': dt,
                                    'Time': rk['Time'],
                                    'Symbol': sym,
                                    'Direction': 'SELL',
                                    'Setup': 'Precision FVG Short',
                                    'SL_Pct': round((sl_dist/entry)*100, 2),
                                    'R': final_r,
                                    'Win': final_r > 0
                                })
                                day_trades += 1
                                if final_r < 0: day_losses += 1
                                break
                    if day_trades > 0: break

    res_df = pd.DataFrame(all_trades).sort_values(['Date', 'Time']).reset_index(drop=True)
    print(f"\nTotal 1000R Engine Trades Executed: {len(res_df)}")

    # NO MONTHLY CIRCUIT BREAKER - CONTINUOUS TRADING
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
    monthly['Profit_INR_1k'] = (monthly['Total_R'] * 1000).astype(int)

    num_months = len(monthly)
    avg_r_month = total_r / num_months
    annual_r = total_r / (num_months / 12.0)
    calmar = abs(annual_r / max_dd)

    print("\n" + "="*70)
    print("      FINAL 1000R PRECISION ENGINE AUDIT (2022 - 2026)")
    print("="*70)
    print(f"Horizon               : October 2022 to November 2026 ({num_months} Months)")
    print(f"Total Trades Taken    : {total_trades} (~{round(total_trades/num_months, 1)} trades/month, ~{round(total_trades/(num_months*21), 1)} trades/day)")
    print(f"Average SL Distance   : {res_df['SL_Pct'].mean():.2f}%")
    print(f"Overall Win Rate      : {win_rate:.1f}%")
    print(f"Average Win (R)       : +{avg_win:.2f}R")
    print(f"Average Loss (R)      : -{avg_loss:.2f}R")
    print(f"Profit Factor         : {pf:.2f}")
    print(f"TOTAL REALIZED RETURN : +{total_r:.1f}R  (₹{int(total_r * 1000):,} @ ₹1k risk/trade)")
    print(f"AVERAGE RETURN / MONTH: +{avg_r_month:.1f}R  (₹{int(avg_r_month * 1000):,}/month)")
    print(f"Maximum Portfolio DD  : {max_dd:.1f}R")
    print(f"Calmar Ratio          : {calmar:.2f}")
    print(f"Profitable Months     : {(monthly['Total_R'] > 0).sum()} / {num_months}")
    print("="*70)

    print("\nMonthly Performance Breakdown (Last 20 Months):")
    print(monthly.tail(20).to_string(index=False))

    os.makedirs('reports', exist_ok=True)
    res_df.to_csv('reports/engine_1000r_trades.csv', index=False)
    monthly.to_csv('reports/engine_1000r_monthly.csv', index=False)

if __name__ == '__main__':
    stocks = load_all_1m_data(UNIVERSE_TOP30)
    run_1000r_engine(stocks)
