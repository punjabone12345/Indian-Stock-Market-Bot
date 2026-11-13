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
    print("All stocks loaded into memory.")
    return stocks

def run_multi_concept_backtest(stocks):
    print("\n" + "="*70)
    print("   RUNNING MULTI-CONCEPT INSTITUTIONAL PRICE ACTION ENGINE (4 YEARS)")
    print("   Concepts: 1. S/R Liquidity Sweeps (Reversal)")
    print("             2. VWAP & Dynamic Support Pullback (Trend Continuation)")
    print("             3. 1m FVG Micro-Structure Invalidation")
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
            d = stocks[sym][dt]
            if d['len'] < 100 or pd.isna(d['PDC']): continue

            # Opening 15m stats
            o15 = d['Open'][0]
            h15 = np.max(d['High'][:15])
            l15 = np.min(d['Low'][:15])
            c15 = d['Close'][14]
            v15 = np.sum(d['Volume'][:15])

            vol_ma = d['VolMA']
            rvol = (v15 / (vol_ma / 25.0)) if vol_ma and vol_ma > 0 else 1.0
            rng_pct = (h15 - l15) / o15

            if rvol >= 1.2 or rng_pct >= 0.005:
                candidates.append({
                    'symbol': sym,
                    'data': d,
                    'ib_h': h15,
                    'ib_l': l15,
                    'rvol': rvol,
                    'score': rvol * 1.5 + (rng_pct * 100)
                })

        candidates.sort(key=lambda x: x['score'], reverse=True)

        for cand in candidates[:6]:
            if day_trades >= 3 or day_losses >= 2: break
            sym = cand['symbol']
            d = cand['data']
            ib_h = cand['ib_h']
            ib_l = cand['ib_l']
            pdh = d['PDH']
            pdl = d['PDL']

            # Iterate intraday candles between 09:30 (idx 15) and 13:30 (idx 255)
            for i in range(15, min(d['len'] - 20, 255)):
                if day_trades >= 3 or day_losses >= 2: break

                c_open = d['Open'][i]
                c_high = d['High'][i]
                c_low = d['Low'][i]
                c_close = d['Close'][i]
                c_vwap = d['VWAP'][i]
                c_vol = d['Volume'][i]

                p1_high = d['High'][i-1]
                p1_low = d['Low'][i-1]
                p1_close = d['Close'][i-1]
                p2_high = d['High'][i-2]
                p2_low = d['Low'][i-2]

                trade_signal = None

                # SETUP 1: S/R LIQUIDITY SWEEP (Institutional Stop-Hunt & Reversal)
                # Sweep PDH or IBH: Price pierces high, but aggressively closes back below
                if not pd.isna(pdh) and c_high > pdh and c_close < pdh and c_close < c_open:
                    entry = c_close
                    raw_sl = c_high + (entry * 0.0003)
                    sl_dist = raw_sl - entry
                    if entry * 0.0012 <= sl_dist <= entry * 0.0030:
                        trade_signal = {
                            'direction': 'SELL',
                            'setup': 'PDH Liquidity Sweep Short',
                            'entry': entry,
                            'sl': raw_sl,
                            'sl_dist': sl_dist
                        }
                # Sweep PDL or IBL: Price pierces low, but reclaims and closes green
                elif not pd.isna(pdl) and c_low < pdl and c_close > pdl and c_close > c_open:
                    entry = c_close
                    raw_sl = c_low - (entry * 0.0003)
                    sl_dist = entry - raw_sl
                    if entry * 0.0012 <= sl_dist <= entry * 0.0030:
                        trade_signal = {
                            'direction': 'BUY',
                            'setup': 'PDL Liquidity Sweep Long',
                            'entry': entry,
                            'sl': raw_sl,
                            'sl_dist': sl_dist
                        }

                # SETUP 2: VWAP DYNAMIC SUPPORT / RESISTANCE PULLBACK (Trend Continuation)
                if not trade_signal and i > 25:
                    # Bullish VWAP Bounce: Price pulls back to touch VWAP and prints a bullish rejection candle
                    if p1_low <= c_vwap and c_close > c_vwap and c_close > c_open and c_close > p1_high:
                        entry = c_close
                        raw_sl = min(c_low, p1_low) - (entry * 0.0003)
                        sl_dist = entry - raw_sl
                        if entry * 0.0012 <= sl_dist <= entry * 0.0028:
                            trade_signal = {
                                'direction': 'BUY',
                                'setup': 'VWAP Dynamic Support Bounce Long',
                                'entry': entry,
                                'sl': raw_sl,
                                'sl_dist': sl_dist
                            }
                    # Bearish VWAP Rejection: Price tests VWAP from below and prints a bearish rejection candle
                    elif p1_high >= c_vwap and c_close < c_vwap and c_close < c_open and c_close < p1_low:
                        entry = c_close
                        raw_sl = max(c_high, p1_high) + (entry * 0.0003)
                        sl_dist = raw_sl - entry
                        if entry * 0.0012 <= sl_dist <= entry * 0.0028:
                            trade_signal = {
                                'direction': 'SELL',
                                'setup': 'VWAP Dynamic Resistance Rejection Short',
                                'entry': entry,
                                'sl': raw_sl,
                                'sl_dist': sl_dist
                            }

                # SETUP 3: 1-MIN FAIR VALUE GAP (FVG) CONTINUATION
                if not trade_signal and i > 15:
                    if c_low > p2_high and c_close > c_vwap and c_close > ib_h:
                        fvg_top = c_low
                        fvg_bottom = p2_high
                        # Check re-test in next 10 candles
                        for k in range(i+1, min(d['len']-10, i+12)):
                            rk_low = d['Low'][k]
                            rk_close = d['Close'][k]
                            if rk_low <= fvg_top and rk_close >= fvg_bottom:
                                entry = fvg_top
                                raw_sl = fvg_bottom - (entry * 0.0004)
                                sl_dist = entry - raw_sl
                                if entry * 0.0015 <= sl_dist <= entry * 0.0035:
                                    trade_signal = {
                                        'direction': 'BUY',
                                        'setup': '1m FVG Institutional Long',
                                        'entry': entry,
                                        'sl': raw_sl,
                                        'sl_dist': sl_dist,
                                        'start_k': k
                                    }
                                break

                # Execute Trade Simulation if signal matched
                if trade_signal:
                    entry = trade_signal['entry']
                    raw_sl = trade_signal['sl']
                    sl_dist = trade_signal['sl_dist']
                    direction = trade_signal['direction']
                    setup_name = trade_signal['setup']
                    start_idx = trade_signal.get('start_k', i)

                    # Asymmetric Targets: 50% at +2.5R, 50% at +5.0R with Breakeven (+0.1R)
                    if direction == 'BUY':
                        tp1 = entry + (sl_dist * 2.5)
                        tp2 = entry + (sl_dist * 5.0)
                        be_sl = entry + (sl_dist * 0.1)
                    else:
                        tp1 = entry - (sl_dist * 2.5)
                        tp2 = entry - (sl_dist * 5.0)
                        be_sl = entry - (sl_dist * 0.1)

                    t1_hit = False
                    current_sl = raw_sl
                    final_r = None

                    for m in range(start_idx + 1, d['len']):
                        m_h = d['High'][m]
                        m_l = d['Low'][m]
                        m_t = d['Time'][m]
                        m_c = d['Close'][m]

                        if direction == 'BUY':
                            if not t1_hit and m_h >= tp1:
                                t1_hit = True
                                current_sl = be_sl

                            if m_l <= current_sl:
                                final_r = -1.04 if not t1_hit else round(0.5 * 2.46 + 0.5 * 0.06, 2)
                                break

                            if t1_hit and m_h >= tp2:
                                final_r = round(0.5 * 2.46 + 0.5 * 4.96, 2)
                                break

                            if m_t >= time(15, 15):
                                r_eod = (m_c - entry) / sl_dist - 0.04
                                final_r = round(r_eod, 2) if not t1_hit else round(0.5 * 2.46 + 0.5 * max(0.06, r_eod), 2)
                                break
                        else:
                            if not t1_hit and m_l <= tp1:
                                t1_hit = True
                                current_sl = be_sl

                            if m_h >= current_sl:
                                final_r = -1.04 if not t1_hit else round(0.5 * 2.46 + 0.5 * 0.06, 2)
                                break

                            if t1_hit and m_l <= tp2:
                                final_r = round(0.5 * 2.46 + 0.5 * 4.96, 2)
                                break

                            if m_t >= time(15, 15):
                                r_eod = (entry - m_c) / sl_dist - 0.04
                                final_r = round(r_eod, 2) if not t1_hit else round(0.5 * 2.46 + 0.5 * max(0.06, r_eod), 2)
                                break

                    if final_r is not None:
                        all_trades.append({
                            'Date': dt,
                            'Time': d['Time'][start_idx],
                            'Symbol': sym,
                            'Direction': direction,
                            'Setup': setup_name,
                            'SL_Pct': round((sl_dist / entry) * 100, 2),
                            'R': final_r,
                            'Win': final_r > 0
                        })
                        day_trades += 1
                        if final_r < 0: day_losses += 1
                        break # Break candle loop for this stock

    res_df = pd.DataFrame(all_trades).sort_values(['Date', 'Time']).reset_index(drop=True)
    print(f"\nTotal Multi-Concept Trades Executed: {len(res_df)}")

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
    print("      MULTI-CONCEPT QUANT PRICE ACTION AUDIT (2022 - 2026)")
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

    print("\nSetup Breakdown Performance:")
    setup_summary = res_df.groupby('Setup').agg(
        Trades=('R', 'count'),
        WinRate=('Win', lambda x: round(x.sum()/len(x)*100, 1)),
        Total_R=('R', lambda x: round(x.sum(), 1))
    ).reset_index()
    print(setup_summary.to_string(index=False))

    print("\nMonthly Performance Breakdown (Last 20 Months):")
    print(monthly.tail(20).to_string(index=False))

    os.makedirs('reports', exist_ok=True)
    res_df.to_csv('reports/multi_concept_trades.csv', index=False)
    monthly.to_csv('reports/multi_concept_monthly.csv', index=False)
    return res_df, monthly

if __name__ == '__main__':
    stocks = load_data_fast(UNIVERSE_TOP30)
    run_multi_concept_backtest(stocks)
