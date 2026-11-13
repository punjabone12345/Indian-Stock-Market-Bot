import sys
sys.path.append('engine')
import os
import pandas as pd
import numpy as np
from datetime import time
from nifty_alpha_explorer import load_nifty_fast, resample_nifty

def run_master_quest():
    print("="*85)
    print("   MASTER QUEST: DISCOVERING THE STATIC 1R STRATEGY (>= 10 R/mo, DD <= 10 R)")
    print("   Testing Structural Invalidation Exits, High Win-Rate Filters & Regime Selection")
    print("="*85)

    nifty_1m = load_nifty_fast()
    
    # We will test on 1m, 2m, 3m, 5m
    timeframes = [1, 2, 3, 5]
    resampled = {tf: resample_nifty(nifty_1m, tf) for tf in timeframes}

    print("\nData loaded and resampled. Beginning multi-concept algorithmic search...")

    all_strategies = []

    # -----------------------------------------------------------------
    # CONCEPT 1: STRUCTURAL INVALIDATION EXIT (THESIS FAILURE STOP)
    # When entering an IFVG, if ANY subsequent candle closes back inside/against
    # the inverted FVG box, EXIT IMMEDIATELY at market close! (Scratch/cut loss)
    # Hard SL is still at Formation Extreme, but structural stop cuts loss to -0.2R to -0.4R!
    # -----------------------------------------------------------------
    for tf in [2, 3, 5]:
        df = resampled[tf]
        dates = sorted(df['Date'].unique())
        grouped = {d: g.reset_index(drop=True) for d, g in df.groupby('Date')}

        for target_rr in [1.5, 2.0, 2.5, 3.0]:
            for cut_on_close_back in [True, False]:
                trades = []
                for dt in dates:
                    day_df = grouped[dt]
                    n = len(day_df)
                    if n < 10: continue

                    highs = day_df['High'].values
                    lows = day_df['Low'].values
                    closes = day_df['Close'].values
                    times = day_df['Time'].values

                    # Detect IFVGs
                    min_gap = 2.0 * np.sqrt(tf)
                    active_fvgs = []
                    signals = []

                    for k in range(2, n):
                        if lows[k] > highs[k-2] + min_gap:
                            active_fvgs.append({'type': 'BULLISH', 'fvg_idx': k, 'top': lows[k], 'bottom': highs[k-2], 'inv_level': highs[k-2], 'box_max': max(highs[k-2], highs[k-1], highs[k]), 'box_min': min(lows[k-2], lows[k-1], lows[k]), 'active': True})
                        elif highs[k] < lows[k-2] - min_gap:
                            active_fvgs.append({'type': 'BEARISH', 'fvg_idx': k, 'top': lows[k-2], 'bottom': highs[k], 'inv_level': lows[k-2], 'box_max': max(highs[k-2], highs[k-1], highs[k]), 'box_min': min(lows[k-2], lows[k-1], lows[k]), 'active': True})

                        for fvg in active_fvgs:
                            if not fvg['active'] or fvg['fvg_idx'] >= k: continue
                            if fvg['type'] == 'BULLISH':
                                if closes[k] < fvg['inv_level']:
                                    fvg['active'] = False
                                    signals.append({'bar': k, 'time': times[k], 'dir': 'SELL', 'entry': closes[k], 'box_max': fvg['box_max'], 'box_min': fvg['box_min'], 'fvg_top': fvg['top'], 'fvg_bottom': fvg['bottom']})
                                elif lows[k] < fvg['inv_level']:
                                    fvg['inv_level'] = lows[k]
                            elif fvg['type'] == 'BEARISH':
                                if closes[k] > fvg['inv_level']:
                                    fvg['active'] = False
                                    signals.append({'bar': k, 'time': times[k], 'dir': 'BUY', 'entry': closes[k], 'box_max': fvg['box_max'], 'box_min': fvg['box_min'], 'fvg_top': fvg['top'], 'fvg_bottom': fvg['bottom']})
                                elif highs[k] > fvg['inv_level']:
                                    fvg['inv_level'] = highs[k]

                    if not signals: continue
                    sig = signals[0] # 1st IFVG
                    if sig['time'] >= time(14, 15): continue

                    entry = sig['entry']
                    direction = sig['dir']

                    if direction == 'BUY':
                        raw_sl = sig['box_min'] - 2.0
                        sl_dist = max(entry - raw_sl, entry * 0.0020)
                        sl = entry - sl_dist
                        if sl_dist > entry * 0.0060: continue
                        tp = entry + (sl_dist * target_rr)
                        inval_level = sig['fvg_top'] # if close drops back below FVG top

                        final_r = None
                        for m in range(sig['bar'] + 1, n):
                            # Check structural failure exit
                            if cut_on_close_back and closes[m] < inval_level:
                                final_r = round((closes[m] - entry) / sl_dist - 0.04, 2)
                                break
                            if lows[m] <= sl:
                                final_r = -1.04
                                break
                            if highs[m] >= tp:
                                final_r = round(target_rr - 0.04, 2)
                                break
                            if times[m] >= time(15, 15):
                                final_r = round((closes[m] - entry) / sl_dist - 0.04, 2)
                                break
                        if final_r is not None:
                            trades.append({'Date': dt, 'R': final_r})

                    elif direction == 'SELL':
                        raw_sl = sig['box_max'] + 2.0
                        sl_dist = max(raw_sl - entry, entry * 0.0020)
                        sl = entry + sl_dist
                        if sl_dist > entry * 0.0060: continue
                        tp = entry - (sl_dist * target_rr)
                        inval_level = sig['fvg_bottom'] # if close rises back above FVG bottom

                        final_r = None
                        for m in range(sig['bar'] + 1, n):
                            if cut_on_close_back and closes[m] > inval_level:
                                final_r = round((entry - closes[m]) / sl_dist - 0.04, 2)
                                break
                            if highs[m] >= sl:
                                final_r = -1.04
                                break
                            if lows[m] <= tp:
                                final_r = round(target_rr - 0.04, 2)
                                break
                            if times[m] >= time(15, 15):
                                final_r = round((entry - closes[m]) / sl_dist - 0.04, 2)
                                break
                        if final_r is not None:
                            trades.append({'Date': dt, 'R': final_r})

                if not trades: continue
                df_t = pd.DataFrame(trades)
                df_t['Date'] = pd.to_datetime(df_t['Date'])
                df_t['YM'] = df_t['Date'].dt.to_period('M')

                tot_r = df_t['R'].sum()
                num_m = df_t['YM'].nunique()
                r_m = tot_r / num_m if num_m > 0 else 0
                cum = df_t['R'].cumsum()
                max_dd = (cum - cum.cummax()).min()
                wr = (df_t['R'] > 0).mean() * 100
                wins = df_t[df_t['R'] > 0]['R'].sum()
                losses = abs(df_t[df_t['R'] < 0]['R'].sum())
                pf = (wins / losses) if losses > 0 else 999.0
                avg_win = df_t[df_t['R'] > 0]['R'].mean()
                avg_loss = abs(df_t[df_t['R'] < 0]['R'].mean()) if len(df_t[df_t['R'] < 0]) > 0 else 1.0

                strat_name = f"IFVG {tf}m | RR 1:{target_rr} | StructuralCut={cut_on_close_back}"
                all_strategies.append({
                    'Name': strat_name,
                    'TF': f"{tf}m",
                    'RR': target_rr,
                    'CutLoss': cut_on_close_back,
                    'Trades': len(df_t),
                    'WinRate': round(wr, 1),
                    'AvgWin': round(avg_win, 2),
                    'AvgLoss': round(avg_loss, 2),
                    'Payoff': round(avg_win / avg_loss, 2) if avg_loss > 0 else 0,
                    'Total_R': round(tot_r, 1),
                    'Monthly_R': round(r_m, 2),
                    'Max_DD': round(max_dd, 1),
                    'PF': round(pf, 2)
                })

    df_res = pd.DataFrame(all_strategies).sort_values('Total_R', ascending=False)
    print("\n" + "="*85)
    print("                    TOP 15 STRUCTURAL CUT-LOSS STRATEGIES")
    print("="*85)
    print(df_res.head(15).to_string(index=False))
    os.makedirs('reports', exist_ok=True)
    df_res.to_csv('reports/structural_cut_loss_sweep.csv', index=False)

if __name__ == '__main__':
    run_master_quest()
