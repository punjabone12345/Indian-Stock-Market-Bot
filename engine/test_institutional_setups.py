import sys
sys.path.append('engine')
import os
import pandas as pd
import numpy as np
from datetime import time
from fib_sr_master_engine import load_data_fast
from master_quant_system import UNIVERSE_TOP30

def test_institutional_setups(stocks):
    print("="*75)
    print("   QUANT TESTING REAL INSTITUTIONAL PRICE ACTION SETUPS (STATIC 1R)")
    print("="*75)

    sample_sym = list(stocks.keys())[0]
    all_dates = sorted(stocks[sample_sym].keys())
    print(f"Total Trading Days: {len(all_dates)}")

    # -------------------------------------------------------------
    # SETUP 1: INSTITUTIONAL VWAP PULLBACK & REJECTION
    # Morning trend established (> VWAP + RVOL >= 1.5x), pulls back to VWAP
    # Rejection candle at VWAP -> Enter on reversal candle break
    # -------------------------------------------------------------
    vwap_trades = []
    for dt in all_dates:
        day_loss = 0
        for sym in stocks.keys():
            if day_loss >= 1: break
            if dt not in stocks[sym]: continue
            d = stocks[sym][dt]
            if d['len'] < 120 or pd.isna(d['PDC']): continue

            # Check morning impulse (09:15 - 10:00)
            v45 = np.sum(d['Volume'][:45])
            vol_ma = d['VolMA']
            rvol = (v45 / (vol_ma * (45/375.0))) if vol_ma and vol_ma > 0 else 1.0
            if rvol < 1.4: continue

            # Bullish trend check: High between 09:15-10:00 > PDC + 0.5%
            morning_high = np.max(d['High'][:45])
            morning_low = np.min(d['Low'][:45])
            pdc = d['PDC']

            # Scan for VWAP touch & bounce between 10:00 and 13:00 (bars 45 to 225)
            # LONG VWAP BOUNCE
            if morning_high > pdc * 1.005:
                for i in range(45, min(d['len'] - 20, 225)):
                    if day_loss >= 1: break
                    c_low = d['Low'][i]
                    c_high = d['High'][i]
                    c_close = d['Close'][i]
                    c_vwap = d['VWAP'][i]

                    # Touch VWAP (Low <= VWAP <= High) and close above VWAP (Bullish rejection)
                    if c_low <= c_vwap <= c_high and c_close > c_vwap:
                        # Entry on break of this rejection candle's high on next candle
                        entry = c_high + (c_high * 0.0002)
                        sl = min(c_low, c_vwap) - (c_high * 0.0004)
                        sl_dist = entry - sl

                        if c_high * 0.0012 <= sl_dist <= c_high * 0.0035:
                            # Check next candle triggers entry
                            if i + 1 < d['len'] and d['High'][i+1] >= entry:
                                # Trade triggered!
                                tp1 = entry + (sl_dist * 2.5)
                                tp2 = entry + (sl_dist * 4.5)
                                be_trig = entry + (sl_dist * 1.2)
                                be_sl = entry + (sl_dist * 0.1)

                                be_hit = False
                                t1_hit = False
                                current_sl = sl
                                final_r = None

                                for m in range(i + 2, d['len']):
                                    m_h = d['High'][m]
                                    m_l = d['Low'][m]
                                    m_t = d['Time'][m]
                                    m_c = d['Close'][m]

                                    if not be_hit and m_h >= be_trig:
                                        be_hit = True
                                        current_sl = max(current_sl, be_sl)
                                    if not t1_hit and m_h >= tp1:
                                        t1_hit = True
                                        current_sl = max(current_sl, entry + sl_dist)

                                    if m_l <= current_sl:
                                        if not be_hit: final_r = -1.04
                                        elif not t1_hit: final_r = 0.06
                                        else: final_r = round(0.5 * 2.46 + 0.5 * 0.96, 2)
                                        break

                                    if t1_hit and m_h >= tp2:
                                        final_r = round(0.5 * 2.46 + 0.5 * 4.46, 2)
                                        break

                                    if m_t >= time(15, 15):
                                        r_eod = (m_c - entry) / sl_dist - 0.04
                                        if not be_hit: final_r = round(r_eod, 2)
                                        elif not t1_hit: final_r = round(max(0.06, r_eod), 2)
                                        else: final_r = round(0.5 * 2.46 + 0.5 * max(0.96, r_eod), 2)
                                        break

                                if final_r is not None:
                                    vwap_trades.append({'Date': dt, 'Symbol': sym, 'Direction': 'BUY', 'R': final_r})
                                    if final_r < 0: day_loss += 1
                                    break

            # SHORT VWAP REJECTION
            if morning_low < pdc * 0.995:
                for i in range(45, min(d['len'] - 20, 225)):
                    if day_loss >= 1: break
                    c_low = d['Low'][i]
                    c_high = d['High'][i]
                    c_close = d['Close'][i]
                    c_vwap = d['VWAP'][i]

                    # Touch VWAP (Low <= VWAP <= High) and close below VWAP (Bearish rejection)
                    if c_low <= c_vwap <= c_high and c_close < c_vwap:
                        entry = c_low - (c_low * 0.0002)
                        sl = max(c_high, c_vwap) + (c_low * 0.0004)
                        sl_dist = sl - entry

                        if c_low * 0.0012 <= sl_dist <= c_low * 0.0035:
                            if i + 1 < d['len'] and d['Low'][i+1] <= entry:
                                tp1 = entry - (sl_dist * 2.5)
                                tp2 = entry - (sl_dist * 4.5)
                                be_trig = entry - (sl_dist * 1.2)
                                be_sl = entry - (sl_dist * 0.1)

                                be_hit = False
                                t1_hit = False
                                current_sl = sl
                                final_r = None

                                for m in range(i + 2, d['len']):
                                    m_h = d['High'][m]
                                    m_l = d['Low'][m]
                                    m_t = d['Time'][m]
                                    m_c = d['Close'][m]

                                    if not be_hit and m_l <= be_trig:
                                        be_hit = True
                                        current_sl = min(current_sl, be_sl)
                                    if not t1_hit and m_l <= tp1:
                                        t1_hit = True
                                        current_sl = min(current_sl, entry - sl_dist)

                                    if m_h >= current_sl:
                                        if not be_hit: final_r = -1.04
                                        elif not t1_hit: final_r = 0.06
                                        else: final_r = round(0.5 * 2.46 + 0.5 * 0.96, 2)
                                        break

                                    if t1_hit and m_l <= tp2:
                                        final_r = round(0.5 * 2.46 + 0.5 * 4.46, 2)
                                        break

                                    if m_t >= time(15, 15):
                                        r_eod = (entry - m_c) / sl_dist - 0.04
                                        if not be_hit: final_r = round(r_eod, 2)
                                        elif not t1_hit: final_r = round(max(0.06, r_eod), 2)
                                        else: final_r = round(0.5 * 2.46 + 0.5 * max(0.96, r_eod), 2)
                                        break

                                if final_r is not None:
                                    vwap_trades.append({'Date': dt, 'Symbol': sym, 'Direction': 'SELL', 'R': final_r})
                                    if final_r < 0: day_loss += 1
                                    break

    df_vwap = pd.DataFrame(vwap_trades)
    print("\n--- RESULTS: INSTITUTIONAL VWAP PULLBACK SETUP ---")
    if len(df_vwap) > 0:
        tot_r = df_vwap['R'].sum()
        df_vwap['YM'] = pd.to_datetime(df_vwap['Date']).dt.to_period('M')
        num_m = df_vwap['YM'].nunique()
        r_m = tot_r / num_m
        cum = df_vwap['R'].cumsum()
        mdd = (cum - cum.cummax()).min()
        wr = (df_vwap['R'] > 0).mean() * 100
        print(f"Trades: {len(df_vwap)} | WinRate: {wr:.1f}% | Total R: {tot_r:+.1f}R | Monthly R: {r_m:+.1f}R/m | Max DD: {mdd:.1f}R")
    else:
        print("No trades found")

if __name__ == '__main__':
    stocks = load_data_fast(UNIVERSE_TOP30)
    test_institutional_setups(stocks)
