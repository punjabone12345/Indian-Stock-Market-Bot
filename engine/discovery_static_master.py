import sys
sys.path.append('engine')
import os
import pandas as pd
import numpy as np
from datetime import time
from fib_sr_master_engine import load_data_fast
from master_quant_system import UNIVERSE_TOP30

def test_static_strategies(stocks):
    print("="*75)
    print("   DISCOVERY: STATIC 1R MASTER STRATEGIES FOR 20+ R/MONTH & < 10R DD")
    print("="*75)

    sample_sym = list(stocks.keys())[0]
    all_dates = sorted(stocks[sample_sym].keys())
    print(f"Total Trading Days in Universe: {len(all_dates)}")

    # We will test multiple configurations
    configs = [
        # (name, max_trades_day, max_losses_day, tp1_r, tp2_r, be_trigger_r, rvol_min, allow_short)
        ("Base Long+Short (TP 2.5R, BE @ 1.2R)", 2, 1, 2.5, 4.0, 1.2, 1.5, True),
        ("High-Conviction Long+Short (TP 2.8R, BE @ 1.4R, 1 loss stop)", 2, 1, 2.8, 4.5, 1.4, 1.8, True),
        ("Aggressive 3-Trades Long+Short (TP 2.6R, BE @ 1.2R, 1 loss stop)", 3, 1, 2.6, 4.2, 1.2, 1.5, True),
        ("Ultra-Selective (RVOL >= 2.0x, TP 3.0R, BE @ 1.5R, 1 loss stop)", 2, 1, 3.0, 5.0, 1.5, 2.0, True),
        ("Multi-Trade 4/day (TP 2.5R, BE @ 1.0R, 1 loss stop)", 4, 1, 2.5, 4.0, 1.0, 1.4, True),
        ("Multi-Trade 3/day (TP 2.2R, BE @ 1.0R, 2 losses stop)", 3, 2, 2.2, 3.5, 1.0, 1.5, True),
    ]

    for cfg_name, max_trades, max_losses, tp1_r, tp2_r, be_trig, rvol_thresh, allow_short in configs:
        trades = []
        for dt in all_dates:
            day_trades = 0
            day_losses = 0

            # Step 1: Scan for catalysts
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
                    # Check first 15m trend
                    c15 = d['Close'][14]
                    vwap15 = d['VWAP'][14]
                    if c15 > vwap15 and gap_pct > -0.005:
                        score = rvol * 2.0 + max(0, gap_pct * 100)
                        cands_long.append({
                            'symbol': sym,
                            'data': d,
                            'ib_h': np.max(d['High'][:15]),
                            'ib_l': np.min(d['Low'][:15]),
                            'score': score
                        })
                    elif allow_short and c15 < vwap15 and gap_pct < 0.005:
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

            # Combine candidates alternating long/short
            active_cands = []
            max_c = max(len(cands_long), len(cands_short))
            for ci in range(max_c):
                if ci < len(cands_long): active_cands.append(('BUY', cands_long[ci]))
                if ci < len(cands_short): active_cands.append(('SELL', cands_short[ci]))

            for side, cand in active_cands[:6]:
                if day_trades >= max_trades or day_losses >= max_losses: break
                sym = cand['symbol']
                d = cand['data']
                ib_h = cand['ib_h']
                ib_l = cand['ib_l']

                for i in range(15, min(d['len'] - 15, 180)): # 09:30 to 12:15 PM
                    if day_trades >= max_trades or day_losses >= max_losses: break
                    c_c = d['Close'][i]
                    c_vwap = d['VWAP'][i]

                    if side == 'BUY':
                        c_low = d['Low'][i]
                        p2_high = d['High'][i-2]
                        # Bullish FVG above VWAP
                        if c_low > p2_high and c_c > c_vwap and c_c > ib_h:
                            entry = c_low
                            raw_sl = p2_high - (entry * 0.0004)
                            sl_dist = entry - raw_sl

                            if entry * 0.0012 <= sl_dist <= entry * 0.0035:
                                tp1 = entry + (sl_dist * tp1_r)
                                tp2 = entry + (sl_dist * tp2_r)
                                be_sl = entry + (sl_dist * 0.1)
                                trig_be = entry + (sl_dist * be_trig)

                                be_hit = False
                                t1_hit = False
                                current_sl = raw_sl
                                final_r = None

                                for m in range(i + 1, d['len']):
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

                    elif side == 'SELL':
                        c_high = d['High'][i]
                        p2_low = d['Low'][i-2]
                        # Bearish FVG below VWAP & IB Low
                        if c_high < p2_low and c_c < c_vwap and c_c < ib_l:
                            entry = c_high
                            raw_sl = p2_low + (entry * 0.0004)
                            sl_dist = raw_sl - entry

                            if entry * 0.0012 <= sl_dist <= entry * 0.0035:
                                tp1 = entry - (sl_dist * tp1_r)
                                tp2 = entry - (sl_dist * tp2_r)
                                be_sl = entry - (sl_dist * 0.1)
                                trig_be = entry - (sl_dist * be_trig)

                                be_hit = False
                                t1_hit = False
                                current_sl = raw_sl
                                final_r = None

                                for m in range(i + 1, d['len']):
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
        scratches = ((df_t['R'] >= 0) & (df_t['R'] <= 0.2)).mean() * 100
        big_wins = (df_t['R'] >= 1.5).mean() * 100
        full_losses = (df_t['R'] < -0.8).mean() * 100

        print(f"\n---> {cfg_name}")
        print(f"     Trades: {len(df_t)} | WinRate: {win_rate:.1f}% | Full Losses: {full_losses:.1f}% | Scratches: {scratches:.1f}% | Big Wins: {big_wins:.1f}%")
        print(f"     Total R: {total_r:+.1f}R | Monthly R: {r_per_m:+.1f}R/m | Max DD: {max_dd:.1f}R")

if __name__ == '__main__':
    stocks = load_data_fast(UNIVERSE_TOP30)
    test_static_strategies(stocks)
