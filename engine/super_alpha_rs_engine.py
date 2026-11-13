import sys
sys.path.append('engine')
import os
import glob
import pandas as pd
import numpy as np
from datetime import time
from master_quant_system import UNIVERSE_TOP30

def load_all_stocks_cached(symbols):
    print("Loading 29 stocks into ultra-fast memory...")
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

        daily_summary = df.groupby('Date').agg({
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }).shift(1)

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
                'PDC': g['PDC'].iloc[0],
                'VolMA': g['DailyVolMA20'].iloc[0],
                'len': len(g)
            }
        stocks[s] = date_groups
    print("Cached all 29 stocks.")
    return stocks

def run_super_alpha_test(stocks, runner_model='uncapped_eod'):
    print("\n" + "="*70)
    print("   RUNNING SUPER ALPHA RS/RW RELATIVE MOMENTUM ENGINE")
    print(f"   Runner Model: {runner_model.upper()} (33% @ +2.5R, 33% @ +5.0R, 34% Uncapped)")
    print("="*70)

    sample_sym = list(stocks.keys())[0]
    all_dates = sorted(stocks[sample_sym].keys())

    all_trades = []

    for dt in all_dates:
        day_trades = 0
        day_losses = 0

        # Step 1: Rank all 29 stocks at 09:30 AM (15 minutes) for Relative Strength / Weakness
        day_rankings = []
        for sym in stocks.keys():
            if dt not in stocks[sym]: continue
            d = stocks[sym][dt]
            if d['len'] < 100 or pd.isna(d['PDC']) or d['PDC'] <= 0: continue

            c15 = d['Close'][14]
            pdc = d['PDC']
            rel_change = (c15 - pdc) / pdc
            v15 = np.sum(d['Volume'][:15])
            vol_ma = d['VolMA']
            rvol = (v15 / (vol_ma / 25.0)) if vol_ma and vol_ma > 0 else 1.0

            if rvol >= 1.2:
                day_rankings.append({
                    'symbol': sym,
                    'data': d,
                    'rel_change': rel_change,
                    'rvol': rvol,
                    'ib_h': np.max(d['High'][:15]),
                    'ib_l': np.min(d['Low'][:15]),
                })

        if not day_rankings: continue

        # Sort by relative strength: Top 3 for Longs, Bottom 3 for Shorts
        day_rankings.sort(key=lambda x: x['rel_change'], reverse=True)
        rs_leaders = day_rankings[:3]   # Top Relative Strength (Long candidates)
        rw_laggards = day_rankings[-3:] # Top Relative Weakness (Short candidates)

        # Session 1: Morning Expansion (09:30 to 11:30)
        # Scan RS Leaders for Long FVG breakout above IBH & VWAP
        for cand in rs_leaders:
            if day_trades >= 3 or day_losses >= 2: break
            if cand['rel_change'] <= 0.003: continue # Must be genuinely positive
            sym = cand['symbol']
            d = cand['data']
            ib_h = cand['ib_h']

            for i in range(15, min(d['len'] - 20, 135)):
                if day_trades >= 3 or day_losses >= 2: break
                c_close = d['Close'][i]
                c_low = d['Low'][i]
                c_vwap = d['VWAP'][i]
                p2_high = d['High'][i-2]

                # Long FVG above VWAP & IBH
                if c_low > p2_high and c_close > c_vwap and c_close > ib_h:
                    fvg_top = c_low
                    fvg_bottom = p2_high

                    for k in range(i+1, min(d['len']-10, i+15)):
                        if d['Low'][k] <= fvg_top and d['Close'][k] >= fvg_bottom:
                            entry = fvg_top
                            raw_sl = fvg_bottom - (entry * 0.0004)
                            sl_dist = entry - raw_sl

                            if entry * 0.0014 <= sl_dist <= entry * 0.0028:
                                # Targets: 33% @ +2.5R, 33% @ +5.0R, 34% Uncapped EOD / Trailing
                                tp1 = entry + (sl_dist * 2.5)
                                tp2 = entry + (sl_dist * 5.0)
                                be_sl = entry + (sl_dist * 0.1)

                                t1_hit = False
                                t2_hit = False
                                current_sl = raw_sl
                                final_r = None

                                for m in range(k + 1, d['len']):
                                    m_h = d['High'][m]
                                    m_l = d['Low'][m]
                                    m_t = d['Time'][m]
                                    m_c = d['Close'][m]

                                    if not t1_hit and m_h >= tp1:
                                        t1_hit = True
                                        current_sl = be_sl

                                    if t1_hit and not t2_hit and m_h >= tp2:
                                        t2_hit = True
                                        current_sl = entry + (sl_dist * 2.5) # Lock +2.5R for runner

                                    if m_l <= current_sl:
                                        if not t1_hit:
                                            final_r = -1.04
                                        elif not t2_hit:
                                            final_r = round(0.33 * 2.46 + 0.67 * 0.06, 2)
                                        else:
                                            final_r = round(0.33 * 2.46 + 0.33 * 4.96 + 0.34 * 2.46, 2)
                                        break

                                    if m_t >= time(15, 15):
                                        r_eod = (m_c - entry) / sl_dist - 0.04
                                        if not t1_hit:
                                            final_r = round(r_eod, 2)
                                        elif not t2_hit:
                                            final_r = round(0.33 * 2.46 + 0.67 * max(0.06, r_eod), 2)
                                        else:
                                            final_r = round(0.33 * 2.46 + 0.33 * 4.96 + 0.34 * max(2.46, r_eod), 2)
                                        break

                                if final_r is not None:
                                    all_trades.append({
                                        'Date': dt,
                                        'Time': d['Time'][k],
                                        'Symbol': sym,
                                        'Direction': 'BUY',
                                        'Setup': 'RS Leader 1m FVG Long',
                                        'SL_Pct': round((sl_dist / entry) * 100, 2),
                                        'R': final_r,
                                        'Win': final_r > 0
                                    })
                                    day_trades += 1
                                    if final_r < 0: day_losses += 1
                                    break
                    if day_trades > 0: break

        # Scan RW Laggards for Short FVG breakdown below IBL & VWAP
        for cand in rw_laggards:
            if day_trades >= 3 or day_losses >= 2: break
            if cand['rel_change'] >= -0.003: continue # Must be genuinely negative
            sym = cand['symbol']
            d = cand['data']
            ib_l = cand['ib_l']

            for i in range(15, min(d['len'] - 20, 135)):
                if day_trades >= 3 or day_losses >= 2: break
                c_close = d['Close'][i]
                c_high = d['High'][i]
                c_vwap = d['VWAP'][i]
                p2_low = d['Low'][i-2]

                # Short FVG below VWAP & IBL
                if c_high < p2_low and c_close < c_vwap and c_close < ib_l:
                    fvg_bottom = c_high
                    fvg_top = p2_low

                    for k in range(i+1, min(d['len']-10, i+15)):
                        if d['High'][k] >= fvg_bottom and d['Close'][k] <= fvg_top:
                            entry = fvg_bottom
                            raw_sl = fvg_top + (entry * 0.0004)
                            sl_dist = raw_sl - entry

                            if entry * 0.0014 <= sl_dist <= entry * 0.0028:
                                tp1 = entry - (sl_dist * 2.5)
                                tp2 = entry - (sl_dist * 5.0)
                                be_sl = entry - (sl_dist * 0.1)

                                t1_hit = False
                                t2_hit = False
                                current_sl = raw_sl
                                final_r = None

                                for m in range(k + 1, d['len']):
                                    m_h = d['High'][m]
                                    m_l = d['Low'][m]
                                    m_t = d['Time'][m]
                                    m_c = d['Close'][m]

                                    if not t1_hit and m_l <= tp1:
                                        t1_hit = True
                                        current_sl = be_sl

                                    if t1_hit and not t2_hit and m_l <= tp2:
                                        t2_hit = True
                                        current_sl = entry - (sl_dist * 2.5)

                                    if m_h >= current_sl:
                                        if not t1_hit:
                                            final_r = -1.04
                                        elif not t2_hit:
                                            final_r = round(0.33 * 2.46 + 0.67 * 0.06, 2)
                                        else:
                                            final_r = round(0.33 * 2.46 + 0.33 * 4.96 + 0.34 * 2.46, 2)
                                        break

                                    if m_t >= time(15, 15):
                                        r_eod = (entry - m_c) / sl_dist - 0.04
                                        if not t1_hit:
                                            final_r = round(r_eod, 2)
                                        elif not t2_hit:
                                            final_r = round(0.33 * 2.46 + 0.67 * max(0.06, r_eod), 2)
                                        else:
                                            final_r = round(0.33 * 2.46 + 0.33 * 4.96 + 0.34 * max(2.46, r_eod), 2)
                                        break

                                if final_r is not None:
                                    all_trades.append({
                                        'Date': dt,
                                        'Time': d['Time'][k],
                                        'Symbol': sym,
                                        'Direction': 'SELL',
                                        'Setup': 'RW Laggard 1m FVG Short',
                                        'SL_Pct': round((sl_dist / entry) * 100, 2),
                                        'R': final_r,
                                        'Win': final_r > 0
                                    })
                                    day_trades += 1
                                    if final_r < 0: day_losses += 1
                                    break
                    if day_trades > 0: break

        # Session 2: Afternoon Continuation (12:45 to 14:15)
        # If less than 2 trades taken in morning, scan for afternoon high/low of day continuation on leaders
        if day_trades < 2 and day_losses < 2:
            for cand in rs_leaders[:2]:
                if day_trades >= 3 or day_losses >= 2: break
                d = cand['data']
                sym = cand['symbol']
                # Check afternoon breakout of morning high
                m_high_so_far = np.max(d['High'][:210]) # High until 12:45
                for i in range(210, min(d['len']-20, 300)): # 12:45 to 14:15
                    if day_trades >= 3 or day_losses >= 2: break
                    c_c = d['Close'][i]
                    c_l = d['Low'][i]
                    c_v = d['VWAP'][i]
                    if c_c > m_high_so_far and c_c > c_v and c_c > d['Open'][i]:
                        entry = c_c
                        raw_sl = min(c_l, d['Low'][i-1]) - (entry * 0.0003)
                        sl_dist = entry - raw_sl
                        if entry * 0.0014 <= sl_dist <= entry * 0.0028:
                            tp1 = entry + (sl_dist * 2.5)
                            be_sl = entry + (sl_dist * 0.1)
                            t1_hit = False
                            current_sl = raw_sl
                            final_r = None

                            for m in range(i+1, d['len']):
                                if not t1_hit and d['High'][m] >= tp1:
                                    t1_hit = True
                                    current_sl = be_sl
                                if d['Low'][m] <= current_sl:
                                    final_r = -1.04 if not t1_hit else 0.85
                                    break
                                if d['Time'][m] >= time(15, 15):
                                    r_eod = (d['Close'][m] - entry)/sl_dist - 0.04
                                    final_r = round(r_eod, 2) if not t1_hit else round(0.5 * 2.46 + 0.5 * max(0.06, r_eod), 2)
                                    break
                            if final_r is not None:
                                all_trades.append({
                                    'Date': dt,
                                    'Time': d['Time'][i],
                                    'Symbol': sym,
                                    'Direction': 'BUY',
                                    'Setup': 'Afternoon RS Continuation Long',
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
    monthly['Profit_INR_1k'] = (monthly['Total_R'] * 1000).astype(int)

    num_months = len(monthly)
    avg_r_month = total_r / num_months
    annual_r = total_r / (num_months / 12.0)
    calmar = abs(annual_r / max_dd)

    print("\n" + "="*70)
    print("      SUPER ALPHA RS/RW ENGINE AUDIT (2022 - 2026)")
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

    print("\nSetup Performance:")
    setup_s = res_df.groupby('Setup').agg(
        Trades=('R', 'count'),
        WinRate=('Win', lambda x: round(x.sum()/len(x)*100, 1)),
        Total_R=('R', lambda x: round(x.sum(), 1))
    ).reset_index()
    print(setup_s.to_string(index=False))

    print("\nMonthly Performance Breakdown (Last 20 Months):")
    print(monthly.tail(20).to_string(index=False))

    os.makedirs('reports', exist_ok=True)
    res_df.to_csv('reports/super_alpha_trades.csv', index=False)
    monthly.to_csv('reports/super_alpha_monthly.csv', index=False)
    return res_df, monthly

if __name__ == '__main__':
    stocks = load_all_stocks_cached(UNIVERSE_TOP30)
    run_super_alpha_test(stocks)
