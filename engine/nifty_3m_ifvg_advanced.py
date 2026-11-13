import os
import glob
import pandas as pd
import numpy as np
import datetime
from datetime import time
from nifty_3m_ifvg_master import load_and_resample_nifty_3m

def detect_advanced_ifvgs(day_df, min_gap_pts=5.0):
    n = len(day_df)
    if n < 5: return []

    highs = day_df['High'].values
    lows = day_df['Low'].values
    closes = day_df['Close'].values
    times = day_df['Time'].values
    vwaps = day_df['VWAP'].values
    pdh = day_df['PDH'].iloc[0]
    pdl = day_df['PDL'].iloc[0]

    # First 15m range (candles 0, 1, 2, 3, 4)
    ib_h = np.max(highs[:5]) if n >= 5 else highs[0]
    ib_l = np.min(lows[:5]) if n >= 5 else lows[0]

    active_fvgs = []
    signals = []

    for k in range(2, n):
        # Detect new FVG
        # Bullish FVG: Low[k] > High[k-2]
        gap_bull = lows[k] - highs[k-2]
        if gap_bull >= min_gap_pts:
            active_fvgs.append({
                'type': 'BULLISH',
                'fvg_idx': k,
                'top': lows[k],
                'bottom': highs[k-2],
                'gap_size': gap_bull,
                'inversion_level': highs[k-2],
                'box_max': max(highs[k-2], highs[k-1], highs[k]),
                'box_min': min(lows[k-2], lows[k-1], lows[k]),
                'active': True
            })

        # Bearish FVG: High[k] < Low[k-2]
        gap_bear = lows[k-2] - highs[k]
        if gap_bear >= min_gap_pts:
            active_fvgs.append({
                'type': 'BEARISH',
                'fvg_idx': k,
                'top': lows[k-2],
                'bottom': highs[k],
                'gap_size': gap_bear,
                'inversion_level': lows[k-2],
                'box_max': max(highs[k-2], highs[k-1], highs[k]),
                'box_min': min(lows[k-2], lows[k-1], lows[k]),
                'active': True
            })

        # Check existing active FVGs for inversion or wick-out
        for fvg in active_fvgs:
            if not fvg['active']: continue
            if fvg['fvg_idx'] >= k: continue

            if fvg['type'] == 'BULLISH':
                # Bullish inverted -> Bearish IFVG (SHORT)
                if closes[k] < fvg['inversion_level']:
                    fvg['active'] = False
                    # Check recent sweep of high (PDH or IBH)
                    recent_high = np.max(highs[max(0, k-10):k+1])
                    swept_high = (recent_high >= pdh) if pd.notna(pdh) else False
                    swept_ibh = (recent_high >= ib_h)

                    signals.append({
                        'signal_bar': k,
                        'time': times[k],
                        'direction': 'SELL',
                        'entry_price': closes[k],
                        'fvg_top': fvg['top'],
                        'fvg_bottom': fvg['bottom'],
                        'gap_size': fvg['gap_size'],
                        'fvg_box_max': fvg['box_max'],
                        'trigger_high': highs[k],
                        'trigger_low': lows[k],
                        'vwap': vwaps[k],
                        'vwap_aligned': closes[k] < vwaps[k],
                        'swept_liquidity': swept_high or swept_ibh
                    })
                elif lows[k] < fvg['inversion_level']:
                    fvg['inversion_level'] = lows[k]

            elif fvg['type'] == 'BEARISH':
                # Bearish inverted -> Bullish IFVG (LONG)
                if closes[k] > fvg['inversion_level']:
                    fvg['active'] = False
                    recent_low = np.min(lows[max(0, k-10):k+1])
                    swept_low = (recent_low <= pdl) if pd.notna(pdl) else False
                    swept_ibl = (recent_low <= ib_l)

                    signals.append({
                        'signal_bar': k,
                        'time': times[k],
                        'direction': 'BUY',
                        'entry_price': closes[k],
                        'fvg_top': fvg['top'],
                        'fvg_bottom': fvg['bottom'],
                        'gap_size': fvg['gap_size'],
                        'fvg_box_min': fvg['box_min'],
                        'trigger_high': highs[k],
                        'trigger_low': lows[k],
                        'vwap': vwaps[k],
                        'vwap_aligned': closes[k] > vwaps[k],
                        'swept_liquidity': swept_low or swept_ibl
                    })
                elif highs[k] > fvg['inversion_level']:
                    fvg['inversion_level'] = highs[k]

    return signals

def run_advanced_nifty_ifvg_optimization():
    df_3m = load_and_resample_nifty_3m()
    dates = sorted(df_3m['Date'].unique())
    grouped = {d: g.reset_index(drop=True) for d, g in df_3m.groupby('Date')}

    # Strategy Variants to Test:
    variants = [
        # (name, min_gap, require_vwap, require_liquidity, sl_rule, tp1_r, tp2_r, max_trades_day)
        ("V1: Pure Baseline 1st IFVG (Gap >= 5pt, Min SL 0.20%, TP 2.5R)", 5.0, False, False, 'FORMATION_EXTREME', 2.5, 2.5, 1),
        ("V2: VWAP Aligned 1st IFVG (Buy > VWAP, Sell < VWAP, TP 2.5R)", 5.0, True, False, 'FORMATION_EXTREME', 2.5, 2.5, 1),
        ("V3: High Imbalance (Gap >= 10pt, VWAP Aligned, TP 2.5R)", 10.0, True, False, 'FORMATION_EXTREME', 2.5, 2.5, 1),
        ("V4: High Imbalance (Gap >= 10pt, VWAP Aligned, TP 3.0R)", 10.0, True, False, 'FORMATION_EXTREME', 3.0, 3.0, 1),
        ("V5: Liquidity Sweep + IFVG Reversal (TP 2.5R)", 5.0, False, True, 'FORMATION_EXTREME', 2.5, 2.5, 1),
        ("V6: Liquidity Sweep + VWAP Confluence (TP 3.0R)", 5.0, True, True, 'FORMATION_EXTREME', 3.0, 3.0, 1),
        ("V7: Dual Target Runner (50% @ +2.0R, 50% @ +4.0R with BE @ +1.2R)", 5.0, True, False, 'FORMATION_EXTREME', 2.0, 4.0, 1),
        ("V8: Dual Target Runner High Imbalance (Gap >= 10pt, 50% @ 2R, 50% @ 4R)", 10.0, True, False, 'FORMATION_EXTREME', 2.0, 4.0, 1),
        ("V9: Trigger Candle SL (Tight SL + Min 0.20%, VWAP Aligned, TP 2.5R)", 5.0, True, False, 'TRIGGER_CANDLE', 2.5, 2.5, 1),
        ("V10: Multi-Trade (Max 2 trades/day, Gap >= 8pt, VWAP Aligned, TP 2.5R)", 8.0, True, False, 'FORMATION_EXTREME', 2.5, 2.5, 2),
    ]

    print("\n" + "="*85)
    print("   OPTIMIZATION: ENHANCED 3-MINUTE NIFTY IFVG STRATEGY AUDIT (2022-2026)")
    print("   Enforcing Minimum Stop Loss = 0.20% | All Slippage & Friction Included")
    print("="*85)

    all_res = []

    for v_name, min_gap, req_vwap, req_liq, sl_rule, tp1_r, tp2_r, max_trades in variants:
        trades = []
        for dt in dates:
            day_df = grouped[dt]
            signals = detect_advanced_ifvgs(day_df, min_gap_pts=min_gap)
            if not signals: continue

            day_trades = 0
            for sig in signals:
                if day_trades >= max_trades: break

                # Apply Filters
                if req_vwap and not sig['vwap_aligned']: continue
                if req_liq and not sig['swept_liquidity']: continue

                bar_idx = sig['signal_bar']
                # Avoid entries after 14:15 PM
                if sig['time'] >= time(14, 15): continue

                direction = sig['direction']
                entry = sig['entry_price']

                if direction == 'BUY':
                    if sl_rule == 'FORMATION_EXTREME':
                        raw_sl = sig['fvg_box_min'] - 2.0
                    else:
                        raw_sl = sig['trigger_low'] - 2.0

                    sl_dist = entry - raw_sl
                    min_sl_dist = entry * 0.0020
                    if sl_dist < min_sl_dist:
                        sl_dist = min_sl_dist
                        sl = entry - sl_dist
                    else:
                        sl = raw_sl

                    if sl_dist > entry * 0.0060: continue

                    tp1 = entry + (sl_dist * tp1_r)
                    tp2 = entry + (sl_dist * tp2_r)
                    be_trig = entry + (sl_dist * 1.2)
                    be_sl = entry + (sl_dist * 0.05)

                elif direction == 'SELL':
                    if sl_rule == 'FORMATION_EXTREME':
                        raw_sl = sig['fvg_box_max'] + 2.0
                    else:
                        raw_sl = sig['trigger_high'] + 2.0

                    sl_dist = raw_sl - entry
                    min_sl_dist = entry * 0.0020
                    if sl_dist < min_sl_dist:
                        sl_dist = min_sl_dist
                        sl = entry + sl_dist
                    else:
                        sl = raw_sl

                    if sl_dist > entry * 0.0060: continue

                    tp1 = entry - (sl_dist * tp1_r)
                    tp2 = entry - (sl_dist * tp2_r)
                    be_trig = entry - (sl_dist * 1.2)
                    be_sl = entry - (sl_dist * 0.05)

                # Simulate Execution
                be_hit = False
                t1_hit = False
                current_sl = sl
                final_r = None

                highs = day_df['High'].values
                lows = day_df['Low'].values
                closes = day_df['Close'].values
                times = day_df['Time'].values

                for m in range(bar_idx + 1, len(day_df)):
                    m_h = highs[m]
                    m_l = lows[m]
                    m_c = closes[m]
                    m_t = times[m]

                    if direction == 'BUY':
                        if not be_hit and m_h >= be_trig:
                            be_hit = True
                            current_sl = max(current_sl, be_sl)

                        if not t1_hit and m_h >= tp1:
                            t1_hit = True
                            current_sl = max(current_sl, entry + (sl_dist * 0.5))

                        if m_l <= current_sl:
                            if not be_hit: final_r = -1.04
                            elif not t1_hit: final_r = 0.05
                            else: final_r = round(0.5 * (tp1_r - 0.04) + 0.5 * 0.46, 2)
                            break

                        if t1_hit and m_h >= tp2:
                            final_r = round(0.5 * (tp1_r - 0.04) + 0.5 * (tp2_r - 0.04), 2)
                            break

                        if m_t >= time(15, 15):
                            r_eod = (m_c - entry) / sl_dist - 0.04
                            if not be_hit: final_r = round(r_eod, 2)
                            elif not t1_hit: final_r = round(max(0.05, r_eod), 2)
                            else: final_r = round(0.5 * (tp1_r - 0.04) + 0.5 * max(0.46, r_eod), 2)
                            break

                    elif direction == 'SELL':
                        if not be_hit and m_l <= be_trig:
                            be_hit = True
                            current_sl = min(current_sl, be_sl)

                        if not t1_hit and m_l <= tp1:
                            t1_hit = True
                            current_sl = min(current_sl, entry - (sl_dist * 0.5))

                        if m_h >= current_sl:
                            if not be_hit: final_r = -1.04
                            elif not t1_hit: final_r = 0.05
                            else: final_r = round(0.5 * (tp1_r - 0.04) + 0.5 * 0.46, 2)
                            break

                        if t1_hit and m_l <= tp2:
                            final_r = round(0.5 * (tp1_r - 0.04) + 0.5 * (tp2_r - 0.04), 2)
                            break

                        if m_t >= time(15, 15):
                            r_eod = (entry - m_c) / sl_dist - 0.04
                            if not be_hit: final_r = round(r_eod, 2)
                            elif not t1_hit: final_r = round(max(0.05, r_eod), 2)
                            else: final_r = round(0.5 * (tp1_r - 0.04) + 0.5 * max(0.46, r_eod), 2)
                            break

                if final_r is not None:
                    trades.append({
                        'Date': dt,
                        'Time': sig['time'],
                        'Direction': direction,
                        'Entry': entry,
                        'SL_Pct': round(sl_dist / entry * 100, 2),
                        'R': final_r
                    })
                    day_trades += 1

        if not trades: continue
        df_res = pd.DataFrame(trades)
        df_res['YM'] = pd.to_datetime(df_res['Date']).dt.to_period('M')
        tot_r = df_res['R'].sum()
        num_m = df_res['YM'].nunique()
        r_m = tot_r / num_m if num_m > 0 else 0
        cum = df_res['R'].cumsum()
        max_dd = (cum - cum.cummax()).min()
        win_rate = (df_res['R'] > 0).mean() * 100
        wins = df_res[df_res['R'] > 0]['R'].sum()
        losses = abs(df_res[df_res['R'] < 0]['R'].sum())
        pf = (wins / losses) if losses > 0 else 999.0

        all_res.append({
            'Variant': v_name,
            'Trades': len(df_res),
            'WinRate': round(win_rate, 1),
            'Total_R': round(tot_r, 1),
            'Monthly_R': round(r_m, 2),
            'Max_DD': round(max_dd, 1),
            'PF': round(pf, 2)
        })

        print(f"\n---> {v_name}")
        print(f"     Trades: {len(df_res)} | WinRate: {win_rate:.1f}% | Total R: {tot_r:+.1f}R | Monthly R: {r_m:+.2f}R/m | Max DD: {max_dd:.1f}R | PF: {pf:.2f}")

    df_out = pd.DataFrame(all_res).sort_values('Total_R', ascending=False)
    print("\n" + "="*85)
    print("                    FINAL RANKING OF ADVANCED IFVG VARIANTS")
    print("="*85)
    print(df_out.to_string(index=False))
    df_out.to_csv('reports/nifty_3m_ifvg_advanced.csv', index=False)

if __name__ == '__main__':
    run_advanced_nifty_ifvg_optimization()
