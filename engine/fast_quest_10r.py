import sys
sys.path.append('engine')
import os
import pandas as pd
import numpy as np
from datetime import time
from nifty_alpha_explorer import load_nifty_fast, resample_nifty, extract_all_daily_ifvgs

def run_fast_quest():
    print("="*85)
    print("   FAST MASTER QUEST: DISCOVERING HIGH-R, LOW-DRAWDOWN STRATEGIES")
    print("   Target: >= 10 R / Month | Max DD <= 10 R | Static 1R Risk Only")
    print("="*85)

    nifty_1m = load_nifty_fast()
    
    timeframes = [1, 2, 3, 5, 15]
    all_configs = []

    for tf in timeframes:
        print(f"\nEvaluating Timeframe {tf}m...")
        df_tf = resample_nifty(nifty_1m, tf)
        daily_signals = extract_all_daily_ifvgs(df_tf, tf)

        # Test varying targets, trailing modes, structural stops, and multi-trade rules
        for target_rr in [1.5, 2.0, 2.5, 3.0, 4.0]:
            for use_be in [False, True]:
                for cut_on_reversal in [False, True]:
                    for max_trades_day in [1, 2, 3]:
                        trades = []
                        for dt, day_data in daily_signals.items():
                            signals = day_data['signals']
                            if not signals: continue

                            highs, lows, closes, times, n = day_data['highs'], day_data['lows'], day_data['closes'], day_data['times'], day_data['n']
                            day_t = 0
                            day_l = 0

                            for sig in signals:
                                if day_t >= max_trades_day or day_l >= 1: break
                                if sig['time'] >= time(14, 15): break

                                entry = sig['entry']
                                direction = sig['dir']

                                if direction == 'BUY':
                                    raw_sl = sig['box_min'] - 2.0
                                    sl_dist = max(entry - raw_sl, entry * 0.0020)
                                    sl = entry - sl_dist
                                    if sl_dist > entry * 0.0060: continue
                                    tp = entry + (sl_dist * target_rr)
                                    be_trig = entry + (sl_dist * 1.0)
                                    be_sl = entry + (sl_dist * 0.05)

                                    be_hit = False
                                    current_sl = sl
                                    final_r = None

                                    for m in range(sig['bar'] + 1, n):
                                        # Structural cut: if candle closes below entry - 0.3*sl_dist
                                        if cut_on_reversal and closes[m] < entry - (sl_dist * 0.35):
                                            final_r = round((closes[m] - entry)/sl_dist - 0.04, 2)
                                            break
                                        if use_be and not be_hit and highs[m] >= be_trig:
                                            be_hit = True
                                            current_sl = max(current_sl, be_sl)
                                        if lows[m] <= current_sl:
                                            final_r = 0.05 if be_hit else -1.04
                                            break
                                        if highs[m] >= tp:
                                            final_r = round(target_rr - 0.04, 2)
                                            break
                                        if times[m] >= time(15, 15):
                                            final_r = round((closes[m] - entry)/sl_dist - 0.04, 2)
                                            break

                                    if final_r is not None:
                                        trades.append({'Date': dt, 'R': final_r})
                                        day_t += 1
                                        if final_r < 0: day_l += 1

                                elif direction == 'SELL':
                                    raw_sl = sig['box_max'] + 2.0
                                    sl_dist = max(raw_sl - entry, entry * 0.0020)
                                    sl = entry + sl_dist
                                    if sl_dist > entry * 0.0060: continue
                                    tp = entry - (sl_dist * target_rr)
                                    be_trig = entry - (sl_dist * 1.0)
                                    be_sl = entry - (sl_dist * 0.05)

                                    be_hit = False
                                    current_sl = sl
                                    final_r = None

                                    for m in range(sig['bar'] + 1, n):
                                        if cut_on_reversal and closes[m] > entry + (sl_dist * 0.35):
                                            final_r = round((entry - closes[m])/sl_dist - 0.04, 2)
                                            break
                                        if use_be and not be_hit and lows[m] <= be_trig:
                                            be_hit = True
                                            current_sl = min(current_sl, be_sl)
                                        if highs[m] >= current_sl:
                                            final_r = 0.05 if be_hit else -1.04
                                            break
                                        if lows[m] <= tp:
                                            final_r = round(target_rr - 0.04, 2)
                                            break
                                        if times[m] >= time(15, 15):
                                            final_r = round((entry - closes[m])/sl_dist - 0.04, 2)
                                            break

                                    if final_r is not None:
                                        trades.append({'Date': dt, 'R': final_r})
                                        day_t += 1
                                        if final_r < 0: day_l += 1

                        if len(trades) < 50: continue
                        df_res = pd.DataFrame(trades)
                        df_res['Date'] = pd.to_datetime(df_res['Date'])
                        df_res['YM'] = df_res['Date'].dt.to_period('M')

                        tot_r = df_res['R'].sum()
                        num_m = df_res['YM'].nunique()
                        r_m = tot_r / num_m if num_m > 0 else 0
                        cum = df_res['R'].cumsum()
                        max_dd = (cum - cum.cummax()).min()
                        wr = (df_res['R'] > 0).mean() * 100
                        wins = df_res[df_res['R'] > 0]['R'].sum()
                        losses = abs(df_res[df_res['R'] < 0]['R'].sum())
                        pf = (wins / losses) if losses > 0 else 999.0

                        cfg_info = {
                            'TF': f"{tf}m",
                            'RR': f"1:{target_rr}",
                            'BE': use_be,
                            'CutLoss': cut_on_reversal,
                            'MaxTrades': max_trades_day,
                            'Trades': len(df_res),
                            'WinRate': round(wr, 1),
                            'Total_R': round(tot_r, 1),
                            'Monthly_R': round(r_m, 2),
                            'Max_DD': round(max_dd, 1),
                            'PF': round(pf, 2)
                        }
                        all_configs.append(cfg_info)

    df_out = pd.DataFrame(all_configs).sort_values('Total_R', ascending=False)
    print("\n" + "="*85)
    print("                    TOP 25 CONFIGURATIONS SORTED BY TOTAL R")
    print("="*85)
    print(df_out.head(25).to_string(index=False))

    print("\n" + "="*85)
    print("           TOP CONFIGURATIONS WITH LOWEST DRAWDOWN (DD <= 15 R)")
    print("="*85)
    low_dd = df_out[df_out['Max_DD'] >= -15.0].sort_values('Total_R', ascending=False)
    print(low_dd.head(15).to_string(index=False))

    os.makedirs('reports', exist_ok=True)
    df_out.to_csv('reports/fast_quest_sweep.csv', index=False)

if __name__ == '__main__':
    run_fast_quest()
