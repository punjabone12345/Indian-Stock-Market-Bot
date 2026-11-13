import os
import glob
import pandas as pd
import numpy as np
import datetime
from datetime import time

def load_and_resample_nifty_3m():
    print("Loading 4-year Nifty 1m dataset (2022-2026)...")
    dfs = []
    d22 = pd.read_csv('data/nifty50/NIFTY50_1min_2022.csv')
    d22['Timestamp'] = pd.to_datetime(d22['Timestamp'])
    dfs.append(d22[d22['Timestamp'] >= '2022-10-01'])
    for y in ['2023', '2024', '2025']:
        p = f'data/nifty50/NIFTY50_1min_{y}.csv'
        if os.path.exists(p):
            d = pd.read_csv(p)
            d['Timestamp'] = pd.to_datetime(d['Timestamp'])
            dfs.append(d)
    for f in sorted(glob.glob('data/nifty50/2026/*.csv')):
        d = pd.read_csv(f)
        d['Timestamp'] = pd.to_datetime(d['Timestamp'])
        dfs.append(d)

    df_1m = pd.concat(dfs).sort_values('Timestamp').drop_duplicates('Timestamp').reset_index(drop=True)
    df_1m['Time'] = df_1m['Timestamp'].dt.time
    df_1m = df_1m[(df_1m['Time'] >= time(9, 15)) & (df_1m['Time'] <= time(15, 29))].copy()

    # Resample to 3-minute candles anchored at 09:15
    df_3m = df_1m.set_index('Timestamp').resample('3min', origin='start_day', offset='15min').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum' if 'Volume' in df_1m.columns else 'count'
    }).dropna().reset_index()

    df_3m['Date'] = df_3m['Timestamp'].dt.date
    df_3m['Time'] = df_3m['Timestamp'].dt.time

    # Calculate VWAP
    df_3m['Typ'] = (df_3m['High'] + df_3m['Low'] + df_3m['Close']) / 3.0
    # If Volume is 0 or 1, synthetic VWAP or price MA
    vol = df_3m['Volume'].values
    if np.sum(vol) == 0 or np.all(vol == 1):
        # Time-weighted average price (TWAP)
        df_3m['VWAP'] = df_3m.groupby('Date')['Close'].transform(lambda x: x.expanding().mean())
    else:
        df_3m['PV'] = df_3m['Typ'] * df_3m['Volume']
        df_3m['CumPV'] = df_3m.groupby('Date')['PV'].cumsum()
        df_3m['CumV'] = df_3m.groupby('Date')['Volume'].cumsum()
        df_3m['VWAP'] = df_3m['CumPV'] / df_3m['CumV']

    # Pre-calculate PDH, PDL, PDC
    daily = df_3m.groupby('Date').agg({'High': 'max', 'Low': 'min', 'Close': 'last'}).shift(1)
    df_3m['PDH'] = df_3m['Date'].map(daily['High'])
    df_3m['PDL'] = df_3m['Date'].map(daily['Low'])
    df_3m['PDC'] = df_3m['Date'].map(daily['Close'])

    print(f"Resampled {len(df_3m)} 3-minute candles across {df_3m['Date'].nunique()} trading days.")
    return df_3m

def detect_ifvg_signals_for_day(day_df, min_gap_pts=3.0):
    """
    Given a single day's 3-minute candles, track all FVGs and find the IFVGs.
    Follows exact user specification with wick-out handling.
    """
    n = len(day_df)
    if n < 5: return []

    opens = day_df['Open'].values
    highs = day_df['High'].values
    lows = day_df['Low'].values
    closes = day_df['Close'].values
    times = day_df['Time'].values
    vwaps = day_df['VWAP'].values

    # Active FVGs list:
    # Each item: {
    #   'type': 'BULLISH' / 'BEARISH',
    #   'fvg_idx': candle index j where FVG formed,
    #   'top': top level of FVG box,
    #   'bottom': bottom level of FVG box,
    #   'inversion_level': level that must be broken (adjusted on wick-outs),
    #   'box_max': highest point of formation,
    #   'box_min': lowest point of formation,
    #   'active': True
    # }
    active_fvgs = []
    ifvg_signals = []

    for k in range(2, n):
        # Step A: Check if a NEW FVG is formed by candles k-2, k-1, k
        # Bullish FVG: Low[k] > High[k-2]
        if lows[k] > highs[k-2] + min_gap_pts:
            active_fvgs.append({
                'type': 'BULLISH',
                'fvg_idx': k,
                'top': lows[k],
                'bottom': highs[k-2],
                'inversion_level': highs[k-2], # bottom of bullish FVG
                'box_max': max(highs[k-2], highs[k-1], highs[k]),
                'box_min': min(lows[k-2], lows[k-1], lows[k]),
                'active': True
            })

        # Bearish FVG: High[k] < Low[k-2]
        elif highs[k] < lows[k-2] - min_gap_pts:
            active_fvgs.append({
                'type': 'BEARISH',
                'fvg_idx': k,
                'top': lows[k-2],
                'bottom': highs[k],
                'inversion_level': lows[k-2], # top of bearish FVG
                'box_max': max(highs[k-2], highs[k-1], highs[k]),
                'box_min': min(lows[k-2], lows[k-1], lows[k]),
                'active': True
            })

        # Step B: Check existing active FVGs for inversion or wick-out by candle k
        # Note: We only check FVGs formed BEFORE candle k (i.e. fvg_idx < k)
        for fvg in active_fvgs:
            if not fvg['active']: continue
            if fvg['fvg_idx'] >= k: continue # watch starts from candle after FVG

            if fvg['type'] == 'BULLISH':
                # Bullish FVG being inverted into a Bearish IFVG (SHORT)
                # Check for inversion (Close < inversion_level)
                if closes[k] < fvg['inversion_level']:
                    # Confirmed Bearish IFVG!
                    fvg['active'] = False
                    ifvg_signals.append({
                        'signal_bar': k,
                        'time': times[k],
                        'direction': 'SELL',
                        'fvg_type': 'BULLISH_INVERTED',
                        'entry_price': closes[k],
                        'fvg_top': fvg['top'],
                        'fvg_bottom': fvg['bottom'],
                        'fvg_box_max': fvg['box_max'],
                        'fvg_box_min': fvg['box_min'],
                        'trigger_high': highs[k],
                        'trigger_low': lows[k],
                        'vwap': vwaps[k],
                    })
                # Check for wick-out (Low < inversion_level BUT Close >= inversion_level)
                elif lows[k] < fvg['inversion_level']:
                    # Wicking out! Update the inversion level to the new lowest wick
                    fvg['inversion_level'] = lows[k]

            elif fvg['type'] == 'BEARISH':
                # Bearish FVG being inverted into a Bullish IFVG (LONG)
                # Check for inversion (Close > inversion_level)
                if closes[k] > fvg['inversion_level']:
                    # Confirmed Bullish IFVG!
                    fvg['active'] = False
                    ifvg_signals.append({
                        'signal_bar': k,
                        'time': times[k],
                        'direction': 'BUY',
                        'fvg_type': 'BEARISH_INVERTED',
                        'entry_price': closes[k],
                        'fvg_top': fvg['top'],
                        'fvg_bottom': fvg['bottom'],
                        'fvg_box_max': fvg['box_max'],
                        'fvg_box_min': fvg['box_min'],
                        'trigger_high': highs[k],
                        'trigger_low': lows[k],
                        'vwap': vwaps[k],
                    })
                # Check for wick-out (High > inversion_level BUT Close <= inversion_level)
                elif highs[k] > fvg['inversion_level']:
                    # Wicking out! Update the inversion level to the new highest wick
                    fvg['inversion_level'] = highs[k]

    return ifvg_signals

def run_nifty_ifvg_backtests():
    df_3m = load_and_resample_nifty_3m()
    dates = sorted(df_3m['Date'].unique())
    print(f"\nProcessing {len(dates)} trading days...")

    # Group by date for speed
    grouped = {d: g.reset_index(drop=True) for d, g in df_3m.groupby('Date')}

    # We will test multiple SL placements and TP / RR configurations:
    # SL Types:
    # 1. 'TRIGGER_CANDLE': High of trigger candle (for SELL) / Low of trigger candle (for BUY)
    # 2. 'FVG_BOX': Top of FVG box (for SELL) / Bottom of FVG box (for BUY)
    # 3. 'FORMATION_EXTREME': Max high of formation (for SELL) / Min low of formation (for BUY)
    # With min_sl_pct = 0.20% (strictly enforced as requested by user)
    # Target R:R: 1.5, 2.0, 2.5, 3.0, with optional Breakeven trailing

    sl_types = ['TRIGGER_CANDLE', 'FVG_BOX', 'FORMATION_EXTREME']
    target_rrs = [1.5, 2.0, 2.5, 3.0]
    be_modes = [False, True] # BE trailing: move to entry + 0.05R when price reaches +1.0R

    print("\n" + "="*85)
    print("   SWEEPING 3-MINUTE NIFTY IFVG CONFIGURATIONS (FIRST IFVG OF DAY ONLY)")
    print("   Enforcing Minimum Stop Loss = 0.20% | Friction Deducted (0.04R)")
    print("="*85)

    summary_results = []

    for sl_type in sl_types:
        for target_rr in target_rrs:
            for use_be in be_modes:
                trades = []
                for dt in dates:
                    day_df = grouped[dt]
                    signals = detect_ifvg_signals_for_day(day_df)
                    if not signals: continue

                    # ONLY 1ST IFVG OF THE DAY
                    sig = signals[0]
                    bar_idx = sig['signal_bar']
                    direction = sig['direction']
                    entry = sig['entry_price']

                    # Determine Raw Stop Loss
                    if direction == 'BUY':
                        if sl_type == 'TRIGGER_CANDLE':
                            raw_sl = sig['trigger_low'] - 2.0
                        elif sl_type == 'FVG_BOX':
                            raw_sl = sig['fvg_bottom'] - 2.0
                        elif sl_type == 'FORMATION_EXTREME':
                            raw_sl = sig['fvg_box_min'] - 2.0

                        sl_dist = entry - raw_sl
                        # Enforce Minimum SL of 0.20%
                        min_sl_dist = entry * 0.0020
                        if sl_dist < min_sl_dist:
                            sl_dist = min_sl_dist
                            sl = entry - sl_dist
                        else:
                            sl = raw_sl

                        # Check max reasonable SL (e.g. 0.60% to avoid absurd risk)
                        if sl_dist > entry * 0.0060:
                            continue

                        tp = entry + (sl_dist * target_rr)
                        be_trig = entry + (sl_dist * 1.0)
                        be_sl = entry + (sl_dist * 0.05)

                    elif direction == 'SELL':
                        if sl_type == 'TRIGGER_CANDLE':
                            raw_sl = sig['trigger_high'] + 2.0
                        elif sl_type == 'FVG_BOX':
                            raw_sl = sig['fvg_top'] + 2.0
                        elif sl_type == 'FORMATION_EXTREME':
                            raw_sl = sig['fvg_box_max'] + 2.0

                        sl_dist = raw_sl - entry
                        min_sl_dist = entry * 0.0020
                        if sl_dist < min_sl_dist:
                            sl_dist = min_sl_dist
                            sl = entry + sl_dist
                        else:
                            sl = raw_sl

                        if sl_dist > entry * 0.0060:
                            continue

                        tp = entry - (sl_dist * target_rr)
                        be_trig = entry - (sl_dist * 1.0)
                        be_sl = entry - (sl_dist * 0.05)

                    # Simulate trade execution candle-by-candle from bar_idx + 1 to EOD
                    be_hit = False
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
                        trades.append({
                            'Date': dt,
                            'Time': sig['time'],
                            'Direction': direction,
                            'Entry': entry,
                            'SL': sl,
                            'SL_Dist': round(sl_dist, 1),
                            'SL_Pct': round(sl_dist / entry * 100, 2),
                            'R': final_r
                        })

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

                label = f"SL={sl_type[:7]} | RR=1:{target_rr} | BE={use_be}"
                summary_results.append({
                    'SL_Type': sl_type,
                    'RR': target_rr,
                    'BE': use_be,
                    'Trades': len(df_res),
                    'WinRate': round(win_rate, 1),
                    'Total_R': round(tot_r, 1),
                    'Monthly_R': round(r_m, 2),
                    'Max_DD': round(max_dd, 1),
                    'PF': round(pf, 2)
                })
                print(f"[{label:34s}] Trades: {len(df_res):4d} | WR: {win_rate:4.1f}% | Total R: {tot_r:+7.1f}R | Mo R: {r_m:+5.2f}R/m | Max DD: {max_dd:5.1f}R | PF: {pf:.2f}")

    df_sum = pd.DataFrame(summary_results).sort_values('Total_R', reverse=True)
    print("\n" + "="*85)
    print("                    TOP 10 BEST PERFORMING CONFIGURATIONS")
    print("="*85)
    print(df_sum.head(10).to_string(index=False))

    os.makedirs('reports', exist_ok=True)
    df_sum.to_csv('reports/nifty_3m_ifvg_sweep.csv', index=False)

if __name__ == '__main__':
    run_nifty_ifvg_backtests()
