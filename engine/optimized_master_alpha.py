import sys
sys.path.append('engine')
import os
import pandas as pd
import numpy as np
from datetime import time
from fib_sr_master_engine import load_data_fast
from master_quant_system import UNIVERSE_TOP30

def run_optimized_alpha(stocks):
    sample_sym = list(stocks.keys())[0]
    all_dates = sorted(stocks[sample_sym].keys())

    all_trades = []

    for dt in all_dates:
        day_trades = 0
        day_losses = 0

        # Scan for high relative volume expansion leaders
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

            # Strong institutional presence filter
            if rvol >= 1.5 and rng_pct >= 0.006:
                # Is daily trend aligned?
                pdc = d['PDC']
                is_bull_trend = c15 > pdc and c15 > d['VWAP'][14]
                is_bear_trend = c15 < pdc and c15 < d['VWAP'][14]

                candidates.append({
                    'symbol': sym,
                    'data': d,
                    'ib_h': h15,
                    'ib_l': l15,
                    'is_bull': is_bull_trend,
                    'is_bear': is_bear_trend,
                    'score': rvol * 2.0 + (rng_pct * 100)
                })

        candidates.sort(key=lambda x: x['score'], reverse=True)

        for cand in candidates[:4]:
            if day_trades >= 3 or day_losses >= 2: break
            sym = cand['symbol']
            d = cand['data']
            ib_h = cand['ib_h']
            ib_l = cand['ib_l']
            is_bull = cand['is_bull']
            is_bear = cand['is_bear']

            for i in range(15, min(d['len'] - 20, 180)):
                if day_trades >= 3 or day_losses >= 2: break

                c_open = d['Open'][i]
                c_high = d['High'][i]
                c_low = d['Low'][i]
                c_close = d['Close'][i]
                c_vwap = d['VWAP'][i]

                p1_high = d['High'][i-1]
                p1_low = d['Low'][i-1]
                p2_high = d['High'][i-2]
                p2_low = d['Low'][i-2]

                trade_signal = None

                # LONG: High-Conviction Bullish 1m FVG + Above VWAP & Break of IBH
                if is_bull and c_low > p2_high and c_close > c_vwap and c_close > ib_h:
                    fvg_top = c_low
                    fvg_bottom = p2_high
                    for k in range(i+1, min(d['len']-10, i+15)):
                        if d['Low'][k] <= fvg_top and d['Close'][k] >= fvg_bottom:
                            entry = fvg_top
                            raw_sl = fvg_bottom - (entry * 0.0004)
                            sl_dist = entry - raw_sl
                            if entry * 0.0014 <= sl_dist <= entry * 0.0030:
                                trade_signal = {
                                    'direction': 'BUY',
                                    'setup': 'Alpha Bullish FVG',
                                    'entry': entry,
                                    'sl': raw_sl,
                                    'sl_dist': sl_dist,
                                    'k': k
                                }
                            break

                # SHORT: High-Conviction VWAP Rejection + Breakdown below IBL
                elif is_bear and p1_high >= c_vwap and c_close < c_vwap and c_close < c_open and c_close < ib_l:
                    entry = c_close
                    raw_sl = max(c_high, p1_high) + (entry * 0.0004)
                    sl_dist = raw_sl - entry
                    if entry * 0.0014 <= sl_dist <= entry * 0.0030:
                        trade_signal = {
                            'direction': 'SELL',
                            'setup': 'Alpha Bearish VWAP Breakdown',
                            'entry': entry,
                            'sl': raw_sl,
                            'sl_dist': sl_dist,
                            'k': i
                        }

                if trade_signal:
                    entry = trade_signal['entry']
                    raw_sl = trade_signal['sl']
                    sl_dist = trade_signal['sl_dist']
                    direction = trade_signal['direction']
                    setup_name = trade_signal['setup']
                    start_idx = trade_signal['k']

                    # Targets: Scale 50% at +2.5R, Runner at +5.0R with Breakeven (+0.1R)
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
    annual_r = total_r / (num_months / 12.0)
    calmar = abs(annual_r / max_dd)

    print("\n" + "="*70)
    print("      OPTIMIZED MASTER ALPHA ENGINE AUDIT (2022 - 2026)")
    print("="*70)
    print(f"Horizon               : October 2022 to November 2026 ({num_months} Months)")
    print(f"Total Trades Taken    : {total_trades} (~{round(total_trades/num_months, 1)} trades/month)")
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

    res_df.to_csv('reports/optimized_alpha_trades.csv', index=False)
    monthly.to_csv('reports/optimized_alpha_monthly.csv', index=False)

if __name__ == '__main__':
    stocks = load_data_fast(UNIVERSE_TOP30)
    run_optimized_alpha(stocks)
