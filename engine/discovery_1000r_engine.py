import sys
sys.path.append('engine')
import os
import pandas as pd
import numpy as np
from datetime import time
from fib_sr_master_engine import load_data_fast
from master_quant_system import UNIVERSE_TOP30

def test_discovery_matrix(stocks):
    sample_sym = list(stocks.keys())[0]
    all_dates = sorted(stocks[sample_sym].keys())

    # We will test parameter combinations:
    # 1. Scratch time (15 mins, 20 mins, 30 mins, No scratch)
    # 2. RVOL threshold (1.4, 1.8, 2.2)
    # 3. Target 1 BE trigger (1.2R, 1.5R, 1.8R)
    # 4. Runner target (6.0R, 8.0R, 10.0R, Uncapped EOD)

    print("\n" + "="*70)
    print("   DISCOVERY ENGINE: QUANTITATIVE OPTIMIZATION FOR 20+ R/MONTH & <10R DD")
    print("   Searching Across 4 Years (1,018 Trading Days / 29 Top Stocks)")
    print("="*70)

    # Let's run a highly optimized grid search
    best_config = None
    best_score = -999999

    configurations = [
        {'rvol': 1.6, 'scratch_bars': 20, 'be_trigger': 1.4, 'tp_runner': 7.0, 'name': 'Config 1: Tight Scratch + 7R Runner'},
        {'rvol': 1.8, 'scratch_bars': 25, 'be_trigger': 1.5, 'tp_runner': 8.0, 'name': 'Config 2: 1.8x RVOL + 8R Runner'},
        {'rvol': 2.0, 'scratch_bars': 20, 'be_trigger': 1.3, 'tp_runner': 8.0, 'name': 'Config 3: 2.0x Catalyst + 8R Runner'},
        {'rvol': 1.5, 'scratch_bars': 30, 'be_trigger': 1.5, 'tp_runner': 9.0, 'name': 'Config 4: Deep Expansion + 9R Runner'},
        {'rvol': 1.8, 'scratch_bars': 18, 'be_trigger': 1.2, 'tp_runner': 10.0, 'name': 'Config 5: Quick Scratch + 10R Runner'},
        {'rvol': 1.6, 'scratch_bars': 25, 'be_trigger': 1.5, 'tp_runner': 8.5, 'name': 'Config 6: Multi-Scale Balanced'},
        {'rvol': 1.4, 'scratch_bars': 20, 'be_trigger': 1.4, 'tp_runner': 7.5, 'name': 'Config 7: Broad Universe + 7.5R Runner'},
    ]

    for cfg in configurations:
        rvol_thresh = cfg['rvol']
        scratch_bars = cfg['scratch_bars']
        be_trig = cfg['be_trigger']
        tp_run = cfg['tp_runner']

        all_trades = []

        for dt in all_dates:
            day_trades = 0
            day_losses = 0

            # Rank stocks on day dt
            day_cands = []
            for sym in stocks.keys():
                if dt not in stocks[sym]: continue
                d = stocks[sym][dt]
                if d['len'] < 100 or pd.isna(d['PDC']) or d['PDC'] <= 0: continue

                c15 = d['Close'][14]
                pdc = d['PDC']
                gap_pct = abs(d['Open'][0] - pdc) / pdc
                v15 = np.sum(d['Volume'][:15])
                vol_ma = d['VolMA']
                rvol = (v15 / (vol_ma / 25.0)) if vol_ma and vol_ma > 0 else 1.0

                if rvol >= rvol_thresh or gap_pct >= 0.007:
                    score = rvol * 2.0 + (gap_pct * 100)
                    day_cands.append({
                        'symbol': sym,
                        'data': d,
                        'ib_h': np.max(d['High'][:15]),
                        'ib_l': np.min(d['Low'][:15]),
                        'score': score,
                        'is_bull': c15 > pdc and c15 > d['VWAP'][14],
                        'is_bear': c15 < pdc and c15 < d['VWAP'][14]
                    })

            day_cands.sort(key=lambda x: x['score'], reverse=True)

            for cand in day_cands[:5]:
                if day_trades >= 3 or day_losses >= 2: break
                sym = cand['symbol']
                d = cand['data']
                ib_h = cand['ib_h']
                ib_l = cand['ib_l']
                is_bull = cand['is_bull']
                is_bear = cand['is_bear']

                for i in range(15, min(d['len'] - 20, 130)):
                    if day_trades >= 3 or day_losses >= 2: break
                    c_close = d['Close'][i]
                    c_low = d['Low'][i]
                    c_high = d['High'][i]
                    c_vwap = d['VWAP'][i]
                    p2_high = d['High'][i-2]
                    p2_low = d['Low'][i-2]

                    signal = None

                    # LONG Setup: FVG above VWAP & IBH
                    if is_bull and c_low > p2_high and c_close > c_vwap and c_close > ib_h:
                        fvg_top = c_low
                        fvg_bot = p2_high
                        for k in range(i+1, min(d['len']-10, i+12)):
                            if d['Low'][k] <= fvg_top and d['Close'][k] >= fvg_bot:
                                entry = fvg_top
                                raw_sl = fvg_bot - (entry * 0.0004)
                                sl_dist = entry - raw_sl
                                if entry * 0.0014 <= sl_dist <= entry * 0.0030:
                                    signal = {'dir': 'BUY', 'entry': entry, 'sl': raw_sl, 'dist': sl_dist, 'k': k}
                                break

                    # SHORT Setup: FVG below VWAP & IBL
                    elif is_bear and c_high < p2_low and c_close < c_vwap and c_close < ib_l:
                        fvg_bot = c_high
                        fvg_top = p2_low
                        for k in range(i+1, min(d['len']-10, i+12)):
                            if d['High'][k] >= fvg_bot and d['Close'][k] <= fvg_top:
                                entry = fvg_bot
                                raw_sl = fvg_top + (entry * 0.0004)
                                sl_dist = raw_sl - entry
                                if entry * 0.0014 <= sl_dist <= entry * 0.0030:
                                    signal = {'dir': 'SELL', 'entry': entry, 'sl': raw_sl, 'dist': sl_dist, 'k': k}
                                break

                    if signal:
                        entry = signal['entry']
                        raw_sl = signal['sl']
                        sl_dist = signal['dist']
                        direction = signal['dir']
                        start_k = signal['k']

                        tp1 = entry + (sl_dist * 2.5) if direction == 'BUY' else entry - (sl_dist * 2.5)
                        tp_runner = entry + (sl_dist * tp_run) if direction == 'BUY' else entry - (sl_dist * tp_run)
                        be_trigger_price = entry + (sl_dist * be_trig) if direction == 'BUY' else entry - (sl_dist * be_trig)
                        be_sl = entry + (sl_dist * 0.15) if direction == 'BUY' else entry - (sl_dist * 0.15)

                        t1_hit = False
                        be_activated = False
                        current_sl = raw_sl
                        final_r = None

                        for m in range(start_k + 1, d['len']):
                            m_h = d['High'][m]
                            m_l = d['Low'][m]
                            m_c = d['Close'][m]
                            m_t = d['Time'][m]
                            elapsed_bars = m - start_k

                            # Alpha Decay Scratch rule:
                            # If after scratch_bars, trade is stagnating in negative territory (between -0.2R and -0.7R), scratch it!
                            if elapsed_bars == scratch_bars and not be_activated:
                                curr_r = ((m_c - entry)/sl_dist if direction == 'BUY' else (entry - m_c)/sl_dist)
                                if -0.7 <= curr_r <= 0.1:
                                    final_r = round(curr_r - 0.04, 2)
                                    break

                            if direction == 'BUY':
                                # Check Breakeven activation
                                if not be_activated and m_h >= be_trigger_price:
                                    be_activated = True
                                    current_sl = be_sl

                                # Check TP1 hit
                                if not t1_hit and m_h >= tp1:
                                    t1_hit = True
                                    current_sl = entry + (sl_dist * 1.5) # Lock +1.5R for runner

                                # Check Stop hit
                                if m_l <= current_sl:
                                    if not be_activated:
                                        final_r = -1.04
                                    elif not t1_hit:
                                        final_r = 0.11 # Breakeven net of friction
                                    else:
                                        final_r = round(0.5 * 2.46 + 0.5 * 1.46, 2) # +1.96R
                                    break

                                # Check Runner hit
                                if t1_hit and m_h >= tp_runner:
                                    final_r = round(0.5 * 2.46 + 0.5 * (tp_run - 0.04), 2)
                                    break

                                # EOD square-off
                                if m_t >= time(15, 15):
                                    r_eod = (m_c - entry) / sl_dist - 0.04
                                    if not be_activated:
                                        final_r = round(r_eod, 2)
                                    elif not t1_hit:
                                        final_r = round(max(0.11, r_eod), 2)
                                    else:
                                        final_r = round(0.5 * 2.46 + 0.5 * max(1.46, r_eod), 2)
                                    break
                            else: # SELL
                                if not be_activated and m_l <= be_trigger_price:
                                    be_activated = True
                                    current_sl = be_sl

                                if not t1_hit and m_l <= tp1:
                                    t1_hit = True
                                    current_sl = entry - (sl_dist * 1.5)

                                if m_h >= current_sl:
                                    if not be_activated:
                                        final_r = -1.04
                                    elif not t1_hit:
                                        final_r = 0.11
                                    else:
                                        final_r = round(0.5 * 2.46 + 0.5 * 1.46, 2)
                                    break

                                if t1_hit and m_l <= tp_runner:
                                    final_r = round(0.5 * 2.46 + 0.5 * (tp_run - 0.04), 2)
                                    break

                                if m_t >= time(15, 15):
                                    r_eod = (entry - m_c) / sl_dist - 0.04
                                    if not be_activated:
                                        final_r = round(r_eod, 2)
                                    elif not t1_hit:
                                        final_r = round(max(0.11, r_eod), 2)
                                    else:
                                        final_r = round(0.5 * 2.46 + 0.5 * max(1.46, r_eod), 2)
                                    break

                        if final_r is not None:
                            all_trades.append({
                                'Date': dt,
                                'R': final_r,
                                'Win': final_r > 0
                            })
                            day_trades += 1
                            if final_r < 0: day_losses += 1
                            break

        df_t = pd.DataFrame(all_trades)
        if len(df_t) == 0: continue
        df_t['YM'] = pd.to_datetime(df_t['Date']).dt.to_period('M')

        num_m = df_t['YM'].nunique()
        total_r = df_t['R'].sum()
        r_month = total_r / num_m
        wins = df_t[df_t['R'] > 0]
        losses = df_t[df_t['R'] < 0]
        win_rate = (len(wins) / len(df_t)) * 100
        avg_win = wins['R'].mean()
        avg_loss = abs(losses['R'].mean()) if len(losses) > 0 else 1.0

        cum = df_t['R'].cumsum()
        max_dd = (cum - cum.cummax()).min()

        print(f"\n[{cfg['name']}]")
        print(f"  Trades: {len(df_t)} (~{round(len(df_t)/num_m, 1)}/mo) | Win Rate: {win_rate:.1f}%")
        print(f"  Avg Win: +{avg_win:.2f}R | Avg Loss: -{avg_loss:.2f}R | Ratio: {avg_win/avg_loss:.2f}:1")
        print(f"  Total Realized R: +{total_r:.1f}R  -->  AVERAGE R / MONTH: +{r_month:.1f}R / month")
        print(f"  Maximum Drawdown: {max_dd:.1f}R")

        score = r_month * 2.0 - abs(max_dd)
        if r_month > 15.0 and max_dd > -12.0:
            if score > best_score:
                best_score = score
                best_config = (cfg, df_t, r_month, max_dd, total_r)

    print("\n" + "="*70)
    print("   DISCOVERY RESULTS COMPLETED")
    print("="*70)
    return best_config

if __name__ == '__main__':
    stocks = load_data_fast(UNIVERSE_TOP30)
    test_discovery_matrix(stocks)
