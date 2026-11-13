import sys
sys.path.append('engine')
import os
import pandas as pd
import numpy as np
from datetime import time
from fib_sr_master_engine import load_data_fast
from master_quant_system import UNIVERSE_TOP30

def test_asymmetric_engine(stocks):
    print("="*75)
    print("   TESTING INSTITUTIONAL ASYMMETRIC LOSS MANAGEMENT (STATIC 1R)")
    print("   Rules: Early BE @ +0.8R | Time-Stall Exit (15m) | Runner to +2.8R | 1 Loss Stop")
    print("="*75)

    sample_sym = list(stocks.keys())[0]
    all_dates = sorted(stocks[sample_sym].keys())
    print(f"Total Trading Days: {len(all_dates)}")

    configs = [
        # (name, be_trig, time_stall_bars, tp1_r, tp2_r, max_trades, rvol_thresh)
        ("Asymmetric Setup 1 (BE @ +0.8R, Stall 15m, TP 2.0R/3.5R, RVOL 1.6x)", 0.8, 15, 2.0, 3.5, 3, 1.6),
        ("Asymmetric Setup 2 (BE @ +0.9R, Stall 20m, TP 2.2R/4.0R, RVOL 1.6x)", 0.9, 20, 2.2, 4.0, 3, 1.6),
        ("Asymmetric Setup 3 (BE @ +0.7R, Stall 12m, TP 1.8R/3.0R, RVOL 1.5x)", 0.7, 12, 1.8, 3.0, 3, 1.5),
        ("Asymmetric Setup 4 (BE @ +1.0R, Stall 25m, TP 2.5R/4.5R, RVOL 1.8x)", 1.0, 25, 2.5, 4.5, 2, 1.8),
        ("Asymmetric Setup 5 (BE @ +0.8R, Stall 15m, TP 2.2R/3.8R, 4 Trades/day)", 0.8, 15, 2.2, 3.8, 4, 1.5),
    ]

    for cfg_name, be_trig_r, stall_bars, tp1_r, tp2_r, max_trades, rvol_min in configs:
        trades = []

        for dt in all_dates:
            day_trades = 0
            day_losses = 0

            # Scan top catalyst stocks
            cands = []
            for sym in stocks.keys():
                if dt not in stocks[sym]: continue
                d = stocks[sym][dt]
                if d['len'] < 100 or pd.isna(d['PDC']) or d['PDC'] <= 0: continue

                pdc = d['PDC']
                o15 = d['Open'][0]
                gap_pct = (o15 - pdc) / pdc
                v15 = np.sum(d['Volume'][:15])
                vol_ma = d['VolMA']
                rvol = (v15 / (vol_ma / 25.0)) if vol_ma and vol_ma > 0 else 1.0

                if rvol >= rvol_min:
                    c15 = d['Close'][14]
                    vwap15 = d['VWAP'][14]
                    if c15 > vwap15 and gap_pct > -0.005:
                        cands.append(('BUY', sym, d, np.max(d['High'][:15]), np.min(d['Low'][:15]), rvol * 2.0 + gap_pct * 100))
                    elif c15 < vwap15 and gap_pct < 0.005:
                        cands.append(('SELL', sym, d, np.max(d['High'][:15]), np.min(d['Low'][:15]), rvol * 2.0 - gap_pct * 100))

            cands.sort(key=lambda x: x[5], reverse=True)

            for side, sym, d, ib_h, ib_l, score in cands[:6]:
                if day_trades >= max_trades or day_losses >= 1: break

                # Scan from 09:30 to 12:30 (bars 15 to 195)
                for i in range(15, min(d['len'] - 25, 195)):
                    if day_trades >= max_trades or day_losses >= 1: break
                    c_c = d['Close'][i]
                    c_vwap = d['VWAP'][i]

                    if side == 'BUY' and c_c > ib_h and c_c > c_vwap and d['High'][i] > d['High'][i-1]:
                        # Momentum Breakout entry at Close of candle i
                        entry = c_c
                        raw_sl = min(d['Low'][i], c_vwap) - (entry * 0.0004)
                        sl_dist = entry - raw_sl

                        if entry * 0.0014 <= sl_dist <= entry * 0.0035:
                            # Valid trade
                            tp1 = entry + (sl_dist * tp1_r)
                            tp2 = entry + (sl_dist * tp2_r)
                            be_trig = entry + (sl_dist * be_trig_r)
                            be_sl = entry + (sl_dist * 0.06)

                            be_hit = False
                            t1_hit = False
                            current_sl = raw_sl
                            final_r = None

                            for m in range(i + 1, d['len']):
                                m_h = d['High'][m]
                                m_l = d['Low'][m]
                                m_c = d['Close'][m]
                                m_t = d['Time'][m]
                                bars_in_trade = m - i

                                # 1. Breakeven Trigger
                                if not be_hit and m_h >= be_trig:
                                    be_hit = True
                                    current_sl = max(current_sl, be_sl)

                                # 2. Target 1
                                if not t1_hit and m_h >= tp1:
                                    t1_hit = True
                                    current_sl = max(current_sl, entry + (sl_dist * 1.0))

                                # 3. Stop loss hit
                                if m_l <= current_sl:
                                    if not be_hit:
                                        final_r = -1.04
                                    elif not t1_hit:
                                        final_r = 0.02
                                    else:
                                        final_r = round(0.5 * (tp1_r - 0.04) + 0.5 * 0.96, 2)
                                    break

                                # 4. Target 2 hit
                                if t1_hit and m_h >= tp2:
                                    final_r = round(0.5 * (tp1_r - 0.04) + 0.5 * (tp2_r - 0.04), 2)
                                    break

                                # 5. Time-Stall Protection: If after stall_bars still < +0.4R, exit early
                                if not be_hit and not t1_hit and bars_in_trade >= stall_bars:
                                    cur_r = (m_c - entry) / sl_dist
                                    if cur_r < 0.4:
                                        final_r = round(cur_r - 0.04, 2)
                                        break

                                # 6. EOD Square-off
                                if m_t >= time(15, 15):
                                    cur_r = (m_c - entry) / sl_dist - 0.04
                                    if not be_hit: final_r = round(cur_r, 2)
                                    elif not t1_hit: final_r = round(max(0.02, cur_r), 2)
                                    else: final_r = round(0.5 * (tp1_r - 0.04) + 0.5 * max(0.96, cur_r), 2)
                                    break

                            if final_r is not None:
                                trades.append({'Date': dt, 'Symbol': sym, 'Side': 'BUY', 'R': final_r})
                                day_trades += 1
                                if final_r <= -0.5: day_losses += 1
                                break

                    elif side == 'SELL' and c_c < ib_l and c_c < c_vwap and d['Low'][i] < d['Low'][i-1]:
                        entry = c_c
                        raw_sl = max(d['High'][i], c_vwap) + (entry * 0.0004)
                        sl_dist = raw_sl - entry

                        if entry * 0.0014 <= sl_dist <= entry * 0.0035:
                            tp1 = entry - (sl_dist * tp1_r)
                            tp2 = entry - (sl_dist * tp2_r)
                            be_trig = entry - (sl_dist * be_trig_r)
                            be_sl = entry - (sl_dist * 0.06)

                            be_hit = False
                            t1_hit = False
                            current_sl = raw_sl
                            final_r = None

                            for m in range(i + 1, d['len']):
                                m_h = d['High'][m]
                                m_l = d['Low'][m]
                                m_c = d['Close'][m]
                                m_t = d['Time'][m]
                                bars_in_trade = m - i

                                if not be_hit and m_l <= be_trig:
                                    be_hit = True
                                    current_sl = min(current_sl, be_sl)

                                if not t1_hit and m_l <= tp1:
                                    t1_hit = True
                                    current_sl = min(current_sl, entry - (sl_dist * 1.0))

                                if m_h >= current_sl:
                                    if not be_hit:
                                        final_r = -1.04
                                    elif not t1_hit:
                                        final_r = 0.02
                                    else:
                                        final_r = round(0.5 * (tp1_r - 0.04) + 0.5 * 0.96, 2)
                                    break

                                if t1_hit and m_l <= tp2:
                                    final_r = round(0.5 * (tp1_r - 0.04) + 0.5 * (tp2_r - 0.04), 2)
                                    break

                                if not be_hit and not t1_hit and bars_in_trade >= stall_bars:
                                    cur_r = (entry - m_c) / sl_dist
                                    if cur_r < 0.4:
                                        final_r = round(cur_r - 0.04, 2)
                                        break

                                if m_t >= time(15, 15):
                                    cur_r = (entry - m_c) / sl_dist - 0.04
                                    if not be_hit: final_r = round(cur_r, 2)
                                    elif not t1_hit: final_r = round(max(0.02, cur_r), 2)
                                    else: final_r = round(0.5 * (tp1_r - 0.04) + 0.5 * max(0.96, cur_r), 2)
                                    break

                            if final_r is not None:
                                trades.append({'Date': dt, 'Symbol': sym, 'Side': 'SELL', 'R': final_r})
                                day_trades += 1
                                if final_r <= -0.5: day_losses += 1
                                break

        df_t = pd.DataFrame(trades)
        if len(df_t) == 0:
            print(f"[{cfg_name}]: No trades taken")
            continue

        total_r = df_t['R'].sum()
        df_t['YM'] = pd.to_datetime(df_t['Date']).dt.to_period('M')
        num_m = df_t['YM'].nunique()
        r_per_m = total_r / num_m if num_m > 0 else 0
        cum = df_t['R'].cumsum()
        max_dd = (cum - cum.cummax()).min()
        win_rate = (df_t['R'] > 0).mean() * 100
        full_losses = (df_t['R'] < -0.8).mean() * 100
        scratches = ((df_t['R'] >= -0.2) & (df_t['R'] <= 0.2)).mean() * 100
        avg_loss = df_t[df_t['R'] < 0]['R'].mean()
        avg_win = df_t[df_t['R'] > 0]['R'].mean()

        print(f"\n---> {cfg_name}")
        print(f"     Trades: {len(df_t)} | WinRate: {win_rate:.1f}% | Avg Win: {avg_win:+.2f}R | Avg Loss: {avg_loss:.2f}R")
        print(f"     Full Losses (< -0.8R): {full_losses:.1f}% | Scratches: {scratches:.1f}%")
        print(f"     Total R: {total_r:+.1f}R | Monthly R: {r_per_m:+.1f}R/m | Max DD: {max_dd:.1f}R")

if __name__ == '__main__':
    stocks = load_data_fast(UNIVERSE_TOP30)
    test_asymmetric_engine(stocks)
