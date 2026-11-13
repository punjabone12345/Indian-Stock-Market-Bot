import sys
sys.path.append('engine')
import os
import pandas as pd
import numpy as np
from datetime import time
from fib_sr_master_engine import load_data_fast
from master_quant_system import UNIVERSE_TOP30

def run_scaled_option_a(stocks, max_trades_per_day=2):
    print("\n" + "="*70)
    print(f"   RUNNING SCALED OPTION A (PRECISION FVG + RVOL >= 1.6x)")
    print(f"   Max Trades Per Day: {max_trades_per_day} | Universe: 29 Stocks")
    print("   ALL SLIPPAGE & COMMISSIONS ALREADY DEDUCTED (0.04R PER TRADE)")
    print("="*70)

    sample_sym = list(stocks.keys())[0]
    all_dates = sorted(stocks[sample_sym].keys())

    all_trades = []

    for dt in all_dates:
        day_trades = 0
        day_losses = 0

        # Scan all 29 stocks for high catalyst expansion (RVOL >= 1.6x OR Gap >= 0.8%)
        day_candidates = []
        for sym in stocks.keys():
            if dt not in stocks[sym]: continue
            d = stocks[sym][dt]
            if d['len'] < 100 or pd.isna(d['PDC']) or d['PDC'] <= 0: continue

            # Opening 15 minutes
            pdc = d['PDC']
            o15 = d['Open'][0]
            gap_pct = abs(o15 - pdc) / pdc
            v15 = np.sum(d['Volume'][:15])
            vol_ma = d['VolMA']
            rvol = (v15 / (vol_ma / 25.0)) if vol_ma and vol_ma > 0 else 1.0

            if rvol >= 1.6 or gap_pct >= 0.008:
                score = rvol * 2.0 + (gap_pct * 100)
                day_candidates.append({
                    'symbol': sym,
                    'data': d,
                    'ib_h': np.max(d['High'][:15]),
                    'ib_l': np.min(d['Low'][:15]),
                    'score': score
                })

        day_candidates.sort(key=lambda x: x['score'], reverse=True)

        # Monitor top 4 catalyst candidates
        for cand in day_candidates[:4]:
            if day_trades >= max_trades_per_day or day_losses >= 2: break
            sym = cand['symbol']
            d = cand['data']
            ib_h = cand['ib_h']

            for i in range(15, min(d['len'] - 15, 120)): # 09:30 to 11:15 AM
                if day_trades >= max_trades_per_day or day_losses >= 2: break

                c_close = d['Close'][i]
                c_low = d['Low'][i]
                c_vwap = d['VWAP'][i]
                p2_high = d['High'][i-2]

                # High-Conviction Bullish FVG above VWAP & IBH
                if c_low > p2_high and c_close > c_vwap and c_close > ib_h:
                    fvg_top = c_low
                    fvg_bottom = p2_high

                    for k in range(i+1, min(d['len']-10, i+15)):
                        if d['Low'][k] <= fvg_top and d['Close'][k] >= fvg_bottom:
                            entry = fvg_top
                            raw_sl = fvg_bottom - (entry * 0.0004)
                            sl_dist = entry - raw_sl

                            if entry * 0.0014 <= sl_dist <= entry * 0.0030:
                                # Targets: 50% @ +2.5R, 50% @ +5.0R (with BE trailing +0.1R)
                                tp1 = entry + (sl_dist * 2.5)
                                tp2 = entry + (sl_dist * 5.0)
                                be_sl = entry + (sl_dist * 0.1)

                                t1_hit = False
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

                                if final_r is not None:
                                    all_trades.append({
                                        'Date': dt,
                                        'Time': d['Time'][k],
                                        'Symbol': sym,
                                        'Direction': 'BUY',
                                        'Setup': 'Precision FVG Long',
                                        'SL_Pct': round((sl_dist / entry) * 100, 2),
                                        'R': final_r,
                                        'Win': final_r > 0
                                    })
                                    day_trades += 1
                                    if final_r < 0: day_losses += 1
                                    break
                    # If this symbol took a trade, move to next pick
                    if day_trades > 0 and len([t for t in all_trades if t['Date'] == dt and t['Symbol'] == sym]) > 0:
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
    print("      SCALED OPTION A QUANT AUDIT (2022 - 2026)")
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
    res_df.to_csv('reports/scaled_option_a_trades.csv', index=False)
    monthly.to_csv('reports/scaled_option_a_monthly.csv', index=False)

if __name__ == '__main__':
    stocks = load_data_fast(UNIVERSE_TOP30)
    run_scaled_option_a(stocks, max_trades_per_day=2)
