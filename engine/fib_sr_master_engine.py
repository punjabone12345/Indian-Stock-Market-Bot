import sys
sys.path.append('engine')
import os
import glob
import pandas as pd
import numpy as np
from datetime import time
from master_quant_system import UNIVERSE_TOP30

def load_data_fast(symbols):
    print("Loading 29 stocks into fast in-memory dictionary...")
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

        # Cumulative VWAP per day
        df['Typ'] = (df['High'] + df['Low'] + df['Close']) / 3.0
        df['PV'] = df['Typ'] * df['Volume']
        df['CumPV'] = df.groupby('Date')['PV'].cumsum()
        df['CumV'] = df.groupby('Date')['Volume'].cumsum()
        df['VWAP'] = df['CumPV'] / df['CumV']

        # Daily summary for PDH, PDL, PDC, 20-day Volume MA
        daily_summary = df.groupby('Date').agg({
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }).shift(1)

        df['PDH'] = df['Date'].map(daily_summary['High'])
        df['PDL'] = df['Date'].map(daily_summary['Low'])
        df['PDC'] = df['Date'].map(daily_summary['Close'])
        df['DailyVolMA20'] = df['Date'].map(daily_summary['Volume'].rolling(20, min_periods=1).mean())

        # Pre-group by Date into a dictionary for O(1) instant access
        date_groups = {}
        for d, g in df.groupby('Date', sort=False):
            date_groups[d] = {
                'Open': g['Open'].values,
                'High': g['High'].values,
                'Low': g['Low'].values,
                'Close': g['Close'].values,
                'Volume': g['Volume'].values,
                'VWAP': g['VWAP'].values,
                'Time': g['Time'].values,
                'PDH': g['PDH'].iloc[0],
                'PDL': g['PDL'].iloc[0],
                'PDC': g['PDC'].iloc[0],
                'VolMA': g['DailyVolMA20'].iloc[0],
                'len': len(g)
            }
        stocks[s] = date_groups
        print(f"Loaded {s}: {len(date_groups)} trading days cached")
    return stocks

def run_fib_sr_backtest(stocks):
    print("\n" + "="*70)
    print("   RUNNING FIBONACCI RETRACEMENT (OTE) + S/R CONFLUENCE ENGINE")
    print("   4 Years (Oct 2022 - Nov 2026) across Top 29 Liquid NSE Stocks")
    print("="*70)

    sample_sym = list(stocks.keys())[0]
    all_dates = sorted(stocks[sample_sym].keys())

    all_trades = []

    for dt in all_dates:
        day_trades = 0
        day_losses = 0

        # Scan all 29 stocks for candidates on day dt
        candidates = []
        for sym in stocks.keys():
            if dt not in stocks[sym]: continue
            day_data = stocks[sym][dt]
            if day_data['len'] < 100 or pd.isna(day_data['PDC']): continue

            # Evaluate morning impulse (09:15 - 09:45, first 30 1m candles)
            opens = day_data['Open'][:30]
            highs = day_data['High'][:30]
            lows = day_data['Low'][:30]
            closes = day_data['Close'][:30]
            vols = day_data['Volume'][:30]

            m_open = opens[0]
            m_high = np.max(highs)
            m_low = np.min(lows)
            m_close = closes[-1]
            m_rng = (m_high - m_low) / m_open

            # Check relative volume in first 30 mins
            vol_sum = np.sum(vols)
            vol_ma = day_data['VolMA']
            rvol = (vol_sum / (vol_ma / 12.0)) if vol_ma and vol_ma > 0 else 1.0

            if m_rng >= 0.006 and rvol >= 1.2:
                # Impulse direction
                is_bull = m_close > m_open and m_close > day_data['VWAP'][29]
                is_bear = m_close < m_open and m_close < day_data['VWAP'][29]

                candidates.append({
                    'symbol': sym,
                    'data': day_data,
                    'is_bull': is_bull,
                    'is_bear': is_bear,
                    'impulse_h': m_high,
                    'impulse_l': m_low,
                    'impulse_range': m_high - m_low,
                    'score': rvol * 2.0 + (m_rng * 100)
                })

        candidates.sort(key=lambda x: x['score'], reverse=True)

        # Monitor top 5 catalyst leaders for the day
        for cand in candidates[:5]:
            if day_trades >= 3 or day_losses >= 2: break
            sym = cand['symbol']
            d = cand['data']
            is_bull = cand['is_bull']
            is_bear = cand['is_bear']
            imp_h = cand['impulse_h']
            imp_l = cand['impulse_l']
            rng = cand['impulse_range']

            pdh = d['PDH']
            pdl = d['PDL']
            pdc = d['PDC']

            # Setup 1: Bullish Golden Pocket Retracement (61.8% - 78.6% Fib + S/R Support)
            if is_bull and rng > 0:
                fib_50 = imp_h - (0.50 * rng)
                fib_618 = imp_h - (0.618 * rng)
                fib_786 = imp_h - (0.786 * rng)

                # Look for entry between 09:45 (candle 30) and 12:00 (candle 165)
                for i in range(30, min(d['len'] - 20, 165)):
                    if day_trades >= 3 or day_losses >= 2: break
                    c_low = d['Low'][i]
                    c_high = d['High'][i]
                    c_close = d['Close'][i]
                    c_vwap = d['VWAP'][i]

                    # Confluence: Pulls into 61.8% - 78.6% Fib Zone AND above VWAP or near PDH/PDC
                    has_sr_confluence = (c_low <= fib_618 and c_close >= fib_786) and (c_close >= c_vwap or (not pd.isna(pdh) and abs(c_low - pdh)/c_low < 0.003))

                    if has_sr_confluence and c_close > d['Open'][i]: # Bullish rejection
                        entry = c_close
                        raw_sl = min(fib_786, imp_l) - (entry * 0.0004)
                        sl_dist = entry - raw_sl

                        # Micro-structure floor & cap
                        if sl_dist < entry * 0.0015: sl_dist = entry * 0.0015; raw_sl = entry - sl_dist
                        if sl_dist > entry * 0.0035: sl_dist = entry * 0.0035; raw_sl = entry - sl_dist

                        # Asymmetric Targets:
                        # TP1: 100% Swing High (Impulse Top) = +2.5R to +3.0R (Scale 50% & SL to BE)
                        # TP2: 161.8% Fib Extension = +5.0R (Runner)
                        tp1 = entry + (sl_dist * 2.5)
                        tp2 = entry + (sl_dist * 5.0)
                        be_sl = entry + (sl_dist * 0.1)

                        t1_hit = False
                        current_sl = raw_sl
                        final_r = None

                        for m in range(i + 1, d['len']):
                            m_high = d['High'][m]
                            m_low = d['Low'][m]
                            m_time = d['Time'][m]

                            if not t1_hit and m_high >= tp1:
                                t1_hit = True
                                current_sl = be_sl

                            if m_low <= current_sl:
                                final_r = -1.04 if not t1_hit else round(0.5 * 2.46 + 0.5 * 0.06, 2)
                                break

                            if t1_hit and m_high >= tp2:
                                final_r = round(0.5 * 2.46 + 0.5 * 4.96, 2)
                                break

                            if m_time >= time(15, 15):
                                r_eod = (d['Close'][m] - entry) / sl_dist - 0.04
                                final_r = round(r_eod, 2) if not t1_hit else round(0.5 * 2.46 + 0.5 * max(0.06, r_eod), 2)
                                break

                        if final_r is not None:
                            all_trades.append({
                                'Date': dt,
                                'Time': d['Time'][i],
                                'Symbol': sym,
                                'Direction': 'BUY',
                                'Setup': 'Fib 61.8% Golden Retest + Support',
                                'SL_Pct': round((sl_dist / entry) * 100, 2),
                                'R': final_r,
                                'Win': final_r > 0
                            })
                            day_trades += 1
                            if final_r < 0: day_losses += 1
                            break

            # Setup 2: Bearish Golden Pocket Retracement (61.8% - 78.6% Fib + S/R Resistance)
            elif is_bear and rng > 0:
                fib_50 = imp_l + (0.50 * rng)
                fib_618 = imp_l + (0.618 * rng)
                fib_786 = imp_l + (0.786 * rng)

                for i in range(30, min(d['len'] - 20, 165)):
                    if day_trades >= 3 or day_losses >= 2: break
                    c_low = d['Low'][i]
                    c_high = d['High'][i]
                    c_close = d['Close'][i]
                    c_vwap = d['VWAP'][i]

                    has_sr_confluence = (c_high >= fib_618 and c_close <= fib_786) and (c_close <= c_vwap or (not pd.isna(pdl) and abs(c_high - pdl)/c_high < 0.003))

                    if has_sr_confluence and c_close < d['Open'][i]:
                        entry = c_close
                        raw_sl = max(fib_786, imp_h) + (entry * 0.0004)
                        sl_dist = raw_sl - entry

                        if sl_dist < entry * 0.0015: sl_dist = entry * 0.0015; raw_sl = entry + sl_dist
                        if sl_dist > entry * 0.0035: sl_dist = entry * 0.0035; raw_sl = entry + sl_dist

                        tp1 = entry - (sl_dist * 2.5)
                        tp2 = entry - (sl_dist * 5.0)
                        be_sl = entry - (sl_dist * 0.1)

                        t1_hit = False
                        current_sl = raw_sl
                        final_r = None

                        for m in range(i + 1, d['len']):
                            m_high = d['High'][m]
                            m_low = d['Low'][m]
                            m_time = d['Time'][m]

                            if not t1_hit and m_low <= tp1:
                                t1_hit = True
                                current_sl = be_sl

                            if m_high >= current_sl:
                                final_r = -1.04 if not t1_hit else round(0.5 * 2.46 + 0.5 * 0.06, 2)
                                break

                            if t1_hit and m_low <= tp2:
                                final_r = round(0.5 * 2.46 + 0.5 * 4.96, 2)
                                break

                            if m_time >= time(15, 15):
                                r_eod = (entry - d['Close'][m]) / sl_dist - 0.04
                                final_r = round(r_eod, 2) if not t1_hit else round(0.5 * 2.46 + 0.5 * max(0.06, r_eod), 2)
                                break

                        if final_r is not None:
                            all_trades.append({
                                'Date': dt,
                                'Time': d['Time'][i],
                                'Symbol': sym,
                                'Direction': 'SELL',
                                'Setup': 'Fib 61.8% Golden Retest + Resistance',
                                'SL_Pct': round((sl_dist / entry) * 100, 2),
                                'R': final_r,
                                'Win': final_r > 0
                            })
                            day_trades += 1
                            if final_r < 0: day_losses += 1
                            break

    df_res = pd.DataFrame(all_trades).sort_values(['Date', 'Time']).reset_index(drop=True)
    print(f"\nTotal Fibonacci + S/R Trades Executed: {len(df_res)}")

    df_res['YM'] = pd.to_datetime(df_res['Date']).dt.to_period('M')
    total_trades = len(df_res)
    wins = df_res[df_res['R'] > 0]
    losses = df_res[df_res['R'] < 0]
    win_rate = (len(wins) / total_trades) * 100
    total_r = df_res['R'].sum()
    avg_win = wins['R'].mean()
    avg_loss = abs(losses['R'].mean())
    pf = wins['R'].sum() / abs(losses['R'].sum())

    cum_series = df_res['R'].cumsum()
    max_dd = (cum_series - cum_series.cummax()).min()

    monthly = df_res.groupby('YM').agg(
        Trades=('R', 'count'),
        Wins=('Win', 'sum'),
        Total_R=('R', 'sum')
    ).reset_index()
    monthly['WinRate'] = round(monthly['Wins'] / monthly['Trades'] * 100, 1)
    monthly['Total_R'] = round(monthly['Total_R'], 1)

    num_months = len(monthly)
    avg_r_month = total_r / num_months
    annual_r = total_r / (num_months / 12.0)
    calmar = abs(annual_r / max_dd)

    print("\n" + "="*70)
    print("      FIBONACCI RETRACEMENT (OTE) + S/R AUDIT (2022 - 2026)")
    print("="*70)
    print(f"Horizon               : October 2022 to November 2026 ({num_months} Months)")
    print(f"Total Trades Taken    : {total_trades} (~{round(total_trades/num_months, 1)} trades/month, ~{round(total_trades/(num_months*21), 1)} trades/day)")
    print(f"Average SL Distance   : {df_res['SL_Pct'].mean():.2f}%")
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

    df_res.to_csv('reports/fib_sr_trades.csv', index=False)
    monthly.to_csv('reports/fib_sr_monthly.csv', index=False)
    return df_res, monthly

if __name__ == '__main__':
    stocks = load_data_fast(UNIVERSE_TOP30)
    run_fib_sr_backtest(stocks)
