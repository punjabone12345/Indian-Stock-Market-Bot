import sys
sys.path.append('engine')
import os
import glob
import pandas as pd
import numpy as np
import datetime
from datetime import time
from nifty_alpha_explorer import load_nifty_and_banknifty_1m, resample_ohlcv, simulate_trades

def run_deep_exploration():
    nifty_1m, bnf_1m = load_nifty_and_banknifty_1m()

    timeframes = [1, 2, 3, 5]
    resampled_data = {tf: resample_ohlcv(nifty_1m, tf) for tf in timeframes}

    print("\n" + "="*85)
    print("   DEEP MULTI-TIMEFRAME & ENTRY MODEL EXPLORATION ON NIFTY (2022-2026)")
    print("   Target: >= 10 R / Month | Max DD <= 10 R | Minimum SL = 0.20%")
    print("="*85)

    all_results = []

    # Test Matrix:
    # Timeframe in [1, 2, 3, 5]
    # Model in ['IFVG_PURE', 'IFVG_VWAP_ALIGNED', 'IFVG_HTF_BIAS', 'IFVG_LIQUIDITY_REVERSAL', 'IFVG_MULTI_TRADE_1LOSS']
    # Target RR in [1.5, 2.0, 2.5, 3.0]

    for tf in timeframes:
        df_tf = resampled_data[tf]
        dates = sorted(df_tf['Date'].unique())
        grouped = {d: g.reset_index(drop=True) for d, g in df_tf.groupby('Date')}

        for model in ['IFVG_PURE', 'IFVG_VWAP_ALIGNED', 'IFVG_HTF_BIAS', 'IFVG_LIQ_REV', 'IFVG_2TRADES_1LOSS']:
            for target_rr in [2.0, 2.5, 3.0]:
                for use_be in [False, True]:
                    trades = []

                    for dt in dates:
                        day_df = grouped[dt]
                        n = len(day_df)
                        if n < 10: continue

                        highs = day_df['High'].values
                        lows = day_df['Low'].values
                        closes = day_df['Close'].values
                        opens = day_df['Open'].values
                        times = day_df['Time'].values
                        vwaps = day_df['VWAP'].values
                        pdh = day_df['PDH'].iloc[0]
                        pdl = day_df['PDL'].iloc[0]

                        # HTF Bias: First 15m / 30m trend
                        # In tf minutes, 15m = 15 // tf bars
                        bars_15m = max(1, 15 // tf)
                        htf_trend = 'BULL' if closes[bars_15m-1] > opens[0] else 'BEAR'
                        ib_h = np.max(highs[:bars_15m])
                        ib_l = np.min(lows[:bars_15m])

                        # Detect FVGs & IFVGs
                        active_fvgs = []
                        ifvg_signals = []

                        min_gap = 2.0 * np.sqrt(tf) # scaled by timeframe

                        for k in range(2, n):
                            # Detect FVG
                            if lows[k] > highs[k-2] + min_gap:
                                active_fvgs.append({
                                    'type': 'BULLISH',
                                    'fvg_idx': k,
                                    'top': lows[k],
                                    'bottom': highs[k-2],
                                    'inversion_level': highs[k-2],
                                    'box_max': max(highs[k-2], highs[k-1], highs[k]),
                                    'box_min': min(lows[k-2], lows[k-1], lows[k]),
                                    'active': True
                                })
                            elif highs[k] < lows[k-2] - min_gap:
                                active_fvgs.append({
                                    'type': 'BEARISH',
                                    'fvg_idx': k,
                                    'top': lows[k-2],
                                    'bottom': highs[k],
                                    'inversion_level': lows[k-2],
                                    'box_max': max(highs[k-2], highs[k-1], highs[k]),
                                    'box_min': min(lows[k-2], lows[k-1], lows[k]),
                                    'active': True
                                })

                            # Check for Inversions
                            for fvg in active_fvgs:
                                if not fvg['active'] or fvg['fvg_idx'] >= k: continue

                                if fvg['type'] == 'BULLISH':
                                    if closes[k] < fvg['inversion_level']:
                                        fvg['active'] = False
                                        # Liquidity sweep check
                                        recent_h = np.max(highs[max(0, k-10):k+1])
                                        swept = (recent_h >= pdh if pd.notna(pdh) else False) or (recent_h >= ib_h)
                                        ifvg_signals.append({
                                            'bar': k,
                                            'time': times[k],
                                            'dir': 'SELL',
                                            'entry': closes[k],
                                            'box_max': fvg['box_max'],
                                            'box_min': fvg['box_min'],
                                            'vwap_ok': closes[k] < vwaps[k],
                                            'htf_ok': htf_trend == 'BEAR',
                                            'swept': swept
                                        })
                                    elif lows[k] < fvg['inversion_level']:
                                        fvg['inversion_level'] = lows[k]

                                elif fvg['type'] == 'BEARISH':
                                    if closes[k] > fvg['inversion_level']:
                                        fvg['active'] = False
                                        recent_l = np.min(lows[max(0, k-10):k+1])
                                        swept = (recent_l <= pdl if pd.notna(pdl) else False) or (recent_l <= ib_l)
                                        ifvg_signals.append({
                                            'bar': k,
                                            'time': times[k],
                                            'dir': 'BUY',
                                            'entry': closes[k],
                                            'box_max': fvg['box_max'],
                                            'box_min': fvg['box_min'],
                                            'vwap_ok': closes[k] > vwaps[k],
                                            'htf_ok': htf_trend == 'BULL',
                                            'swept': swept
                                        })
                                    elif highs[k] > fvg['inversion_level']:
                                        fvg['inversion_level'] = highs[k]

                        # Filter signals by model
                        day_trades = 0
                        day_losses = 0
                        max_day_trades = 2 if model == 'IFVG_2TRADES_1LOSS' else 1
                        max_day_losses = 1

                        for sig in ifvg_signals:
                            if day_trades >= max_day_trades or day_losses >= max_day_losses: break
                            if sig['time'] >= time(14, 15): break

                            if model == 'IFVG_VWAP_ALIGNED' and not sig['vwap_ok']: continue
                            if model == 'IFVG_HTF_BIAS' and not sig['htf_ok']: continue
                            if model == 'IFVG_LIQ_REV' and not sig['swept']: continue

                            entry = sig['entry']
                            direction = sig['dir']

                            if direction == 'BUY':
                                raw_sl = sig['box_min'] - 2.0
                                sl_dist = entry - raw_sl
                                min_sl = entry * 0.0020
                                if sl_dist < min_sl:
                                    sl_dist = min_sl
                                    sl = entry - sl_dist
                                else:
                                    sl = raw_sl
                                if sl_dist > entry * 0.0060: continue
                                tp = entry + (sl_dist * target_rr)
                                be_trig = entry + (sl_dist * 1.2)
                                be_sl = entry + (sl_dist * 0.05)

                            elif direction == 'SELL':
                                raw_sl = sig['box_max'] + 2.0
                                sl_dist = raw_sl - entry
                                min_sl = entry * 0.0020
                                if sl_dist < min_sl:
                                    sl_dist = min_sl
                                    sl = entry + sl_dist
                                else:
                                    sl = raw_sl
                                if sl_dist > entry * 0.0060: continue
                                tp = entry - (sl_dist * target_rr)
                                be_trig = entry - (sl_dist * 1.2)
                                be_sl = entry - (sl_dist * 0.05)

                            # Execution simulation
                            be_hit = False
                            current_sl = sl
                            final_r = None

                            for m in range(sig['bar'] + 1, n):
                                m_h = highs[m]
                                m_l = lows[m]
                                m_c = closes[m]
                                m_t = times[m]

                                if direction == 'BUY':
                                    if use_be and not be_hit and m_h >= be_trig:
                                        be_hit = True
                                        current_sl = max(current_sl, be_sl)
                                    if m_l <= current_sl:
                                        final_r = 0.05 if be_hit else -1.04
                                        break
                                    if m_h >= tp:
                                        final_r = round(target_rr - 0.04, 2)
                                        break
                                    if m_t >= time(15, 15):
                                        r_eod = (m_c - entry) / sl_dist - 0.04
                                        final_r = round(max(0.05, r_eod) if be_hit else r_eod, 2)
                                        break

                                elif direction == 'SELL':
                                    if use_be and not be_hit and m_l <= be_trig:
                                        be_hit = True
                                        current_sl = min(current_sl, be_sl)
                                    if m_h >= current_sl:
                                        final_r = 0.05 if be_hit else -1.04
                                        break
                                    if m_l <= tp:
                                        final_r = round(target_rr - 0.04, 2)
                                        break
                                    if m_t >= time(15, 15):
                                        r_eod = (entry - m_c) / sl_dist - 0.04
                                        final_r = round(max(0.05, r_eod) if be_hit else r_eod, 2)
                                        break

                            if final_r is not None:
                                trades.append({'Date': dt, 'R': final_r})
                                day_trades += 1
                                if final_r < 0: day_losses += 1

                    stats = simulate_trades(trades)
                    stats['TF'] = f"{tf}m"
                    stats['Model'] = model
                    stats['RR'] = f"1:{target_rr}"
                    stats['BE'] = use_be
                    all_results.append(stats)

                    if stats['Total_R'] > 30:
                        print(f"[{tf:1d}m | {model:18s} | RR 1:{target_rr} | BE={use_be}] Trades: {stats['Trades']:4d} | WR: {stats['WinRate']:4.1f}% | Total R: {stats['Total_R']:+7.1f}R | Mo R: {stats['Monthly_R']:+5.2f}R | Max DD: {stats['Max_DD']:5.1f}R | PF: {stats['PF']:.2f}")

    df_summary = pd.DataFrame(all_results).sort_values('Total_R', ascending=False)
    print("\n" + "="*85)
    print("                    TOP 15 BEST PERFORMING CONFIGURATIONS")
    print("="*85)
    print(df_summary.head(15).to_string(index=False))
    df_summary.to_csv('reports/nifty_deep_exploration.csv', index=False)

if __name__ == '__main__':
    run_deep_exploration()
