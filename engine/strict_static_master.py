import sys
sys.path.append('engine')
import os
import pandas as pd
import numpy as np
from datetime import time
from fib_sr_master_engine import load_data_fast
from master_quant_system import UNIVERSE_TOP30

def test_strict_static_pullback(stocks):
    print("="*75)
    print("   STRICT REAL-WORLD PULLBACK EXECUTION: LONG + SHORT STATIC 1R")
    print("   (Limit Orders at FVG Boundary on Candles k > i | Realistic Friction)")
    print("="*75)

    sample_sym = list(stocks.keys())[0]
    all_dates = sorted(stocks[sample_sym].keys())
    print(f"Total Trading Days in Universe: {len(all_dates)}")

    configs = [
        # (name, max_trades_day, max_losses_day, tp1_r, tp2_r, be_trig, rvol_thresh, scan_end_bar)
        ("Config A: TP 2.6R/4.5R, BE @ 1.2R, 1-Loss Stop, RVOL 1.5x", 2, 1, 2.6, 4.5, 1.2, 1.5, 180),
        ("Config B: TP 2.8R/5.0R, BE @ 1.4R, 1-Loss Stop, RVOL 1.6x", 2, 1, 2.8, 5.0, 1.4, 1.6, 180),
        ("Config C: TP 2.5R/4.0R, BE @ 1.1R, 1-Loss Stop, RVOL 1.4x", 3, 1, 2.5, 4.0, 1.1, 1.4, 210),
        ("Config D: TP 2.4R/3.8R, BE @ 1.0R, 2-Loss Stop, RVOL 1.5x", 3, 2, 2.4, 3.8, 1.0, 1.5, 210),
        ("Config E: TP 3.0R/5.5R, BE @ 1.5R, 1-Loss Stop, RVOL 1.6x", 3, 1, 3.0, 5.5, 1.5, 1.6, 240),
        ("Config F: TP 2.5R/4.0R, BE @ 1.2R, 1-Loss Stop, All-Day Scan", 3, 1, 2.5, 4.0, 1.2, 1.5, 300),
    ]

    for cfg_name, max_trades, max_losses, tp1_r, tp2_r, be_trig, rvol_thresh, scan_end_bar in configs:
        trades = []
        for dt in all_dates:
            day_trades = 0
            day_losses = 0

            # Step 1: Scan for opening catalysts
            cands_long = []
            cands_short = []

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

                if rvol >= rvol_thresh:
                    c15 = d['Close'][14]
                    vwap15 = d['VWAP'][14]
                    if c15 > vwap15 and gap_pct > -0.006:
                        score = rvol * 2.0 + max(0, gap_pct * 100)
                        cands_long.append({
                            'symbol': sym,
                            'data': d,
                            'ib_h': np.max(d['High'][:15]),
                            'ib_l': np.min(d['Low'][:15]),
                            'score': score
                        })
                    elif c15 < vwap15 and gap_pct < 0.006:
                        score = rvol * 2.0 + max(0, -gap_pct * 100)
                        cands_short.append({
                            'symbol': sym,
                            'data': d,
                            'ib_h': np.max(d['High'][:15]),
                            'ib_l': np.min(d['Low'][:15]),
                            'score': score
                        })

            cands_long.sort(key=lambda x: x['score'], reverse=True)
            cands_short.sort(key=lambda x: x['score'], reverse=True)

            # Combine candidates alternating long and short
            active_cands = []
            max_c = max(len(cands_long), len(cands_short))
            for ci in range(max_c):
                if ci < len(cands_long): active_cands.append(('BUY', cands_long[ci]))
                if ci < len(cands_short): active_cands.append(('SELL', cands_short[ci]))

            for side, cand in active_cands[:8]:
                if day_trades >= max_trades or day_losses >= max_losses: break
                sym = cand['symbol']
                d = cand['data']
                ib_h = cand['ib_h']
                ib_l = cand['ib_l']

                # Scan for confirmed FVG on candle i
                for i in range(15, min(d['len'] - 20, scan_end_bar)):
                    if day_trades >= max_trades or day_losses >= max_losses: break
                    c_c = d['Close'][i]
                    c_vwap = d['VWAP'][i]

                    if side == 'BUY':
                        c_low = d['Low'][i]
                        p2_high = d['High'][i-2]
                        # Bullish FVG confirmed at close of candle i
                        if c_low > p2_high and c_c > c_vwap and c_c > ib_h:
                            fvg_top = c_low
                            fvg_bottom = p2_high
                            raw_sl = fvg_bottom - (fvg_top * 0.0004)
                            sl_dist = fvg_top - raw_sl

                            if fvg_top * 0.0012 <= sl_dist <= fvg_top * 0.0035:
                                # Look for pullback entry on candles k > i
                                for k in range(i + 1, min(d['len'] - 10, i + 15)):
                                    if d['Low'][k] <= fvg_top and d['Close'][k] >= fvg_bottom:
                                        entry = fvg_top
                                        tp1 = entry + (sl_dist * tp1_r)
                                        tp2 = entry + (sl_dist * tp2_r)
                                        be_sl = entry + (sl_dist * 0.1)
                                        trig_be = entry + (sl_dist * be_trig)

                                        be_hit = False
                                        t1_hit = False
                                        current_sl = raw_sl
                                        final_r = None

                                        for m in range(k + 1, d['len']):
                                            m_h = d['High'][m]
                                            m_l = d['Low'][m]
                                            m_t = d['Time'][m]
                                            m_c = d['Close'][m]

                                            if not be_hit and m_h >= trig_be:
                                                be_hit = True
                                                current_sl = max(current_sl, be_sl)

                                            if not t1_hit and m_h >= tp1:
                                                t1_hit = True
                                                current_sl = max(current_sl, entry + (sl_dist * 1.0))

                                            if m_l <= current_sl:
                                                if not be_hit:
                                                    final_r = -1.04
                                                elif not t1_hit:
                                                    final_r = 0.06
                                                else:
                                                    final_r = round(0.5 * (tp1_r - 0.04) + 0.5 * 0.96, 2)
                                                break

                                            if t1_hit and m_h >= tp2:
                                                final_r = round(0.5 * (tp1_r - 0.04) + 0.5 * (tp2_r - 0.04), 2)
                                                break

                                            if m_t >= time(15, 15):
                                                r_eod = (m_c - entry) / sl_dist - 0.04
                                                if not be_hit:
                                                    final_r = round(r_eod, 2)
                                                elif not t1_hit:
                                                    final_r = round(max(0.06, r_eod), 2)
                                                else:
                                                    final_r = round(0.5 * (tp1_r - 0.04) + 0.5 * max(0.96, r_eod), 2)
                                                break

                                        if final_r is not None:
                                            trades.append({'Date': dt, 'Symbol': sym, 'R': final_r})
                                            day_trades += 1
                                            if final_r < 0: day_losses += 1
                                            break
                                if day_trades > 0: break

                    elif side == 'SELL':
                        c_high = d['High'][i]
                        p2_low = d['Low'][i-2]
                        # Bearish FVG confirmed at close of candle i
                        if c_high < p2_low and c_c < c_vwap and c_c < ib_l:
                            fvg_bottom = c_high
                            fvg_top = p2_low
                            raw_sl = fvg_top + (fvg_bottom * 0.0004)
                            sl_dist = raw_sl - fvg_bottom

                            if fvg_bottom * 0.0012 <= sl_dist <= fvg_bottom * 0.0035:
                                # Look for pullback entry on candles k > i
                                for k in range(i + 1, min(d['len'] - 10, i + 15)):
                                    if d['High'][k] >= fvg_bottom and d['Close'][k] <= fvg_top:
                                        entry = fvg_bottom
                                        tp1 = entry - (sl_dist * tp1_r)
                                        tp2 = entry - (sl_dist * tp2_r)
                                        be_sl = entry - (sl_dist * 0.1)
                                        trig_be = entry - (sl_dist * be_trig)

                                        be_hit = False
                                        t1_hit = False
                                        current_sl = raw_sl
                                        final_r = None

                                        for m in range(k + 1, d['len']):
                                            m_h = d['High'][m]
                                            m_l = d['Low'][m]
                                            m_t = d['Time'][m]
                                            m_c = d['Close'][m]

                                            if not be_hit and m_l <= trig_be:
                                                be_hit = True
                                                current_sl = min(current_sl, be_sl)

                                            if not t1_hit and m_l <= tp1:
                                                t1_hit = True
                                                current_sl = min(current_sl, entry - (sl_dist * 1.0))

                                            if m_h >= current_sl:
                                                if not be_hit:
                                                    final_r = -1.04
                                                elif not t1_hit:
                                                    final_r = 0.06
                                                else:
                                                    final_r = round(0.5 * (tp1_r - 0.04) + 0.5 * 0.96, 2)
                                                break

                                            if t1_hit and m_l <= tp2:
                                                final_r = round(0.5 * (tp1_r - 0.04) + 0.5 * (tp2_r - 0.04), 2)
                                                break

                                            if m_t >= time(15, 15):
                                                r_eod = (entry - m_c) / sl_dist - 0.04
                                                if not be_hit:
                                                    final_r = round(r_eod, 2)
                                                elif not t1_hit:
                                                    final_r = round(max(0.06, r_eod), 2)
                                                else:
                                                    final_r = round(0.5 * (tp1_r - 0.04) + 0.5 * max(0.96, r_eod), 2)
                                                break

                                        if final_r is not None:
                                            trades.append({'Date': dt, 'Symbol': sym, 'R': final_r})
                                            day_trades += 1
                                            if final_r < 0: day_losses += 1
                                            break
                                if day_trades > 0: break

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
        scratches = ((df_t['R'] >= 0) & (df_t['R'] <= 0.2)).mean() * 100
        big_wins = (df_t['R'] >= 1.5).mean() * 100

        print(f"\n---> {cfg_name}")
        print(f"     Trades: {len(df_t)} | WinRate: {win_rate:.1f}% | Full Losses: {full_losses:.1f}% | Scratches: {scratches:.1f}% | Big Wins: {big_wins:.1f}%")
        print(f"     Total R: {total_r:+.1f}R | Monthly R: {r_per_m:+.1f}R/m | Max DD: {max_dd:.1f}R")

if __name__ == '__main__':
    stocks = load_data_fast(UNIVERSE_TOP30)
    test_strict_static_pullback(stocks)
