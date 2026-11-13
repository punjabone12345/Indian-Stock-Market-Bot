import sys
sys.path.append('engine')
import os
import glob
import pandas as pd
import numpy as np
import datetime
from datetime import time

def load_nifty_fast():
    print("Loading 4-year Nifty 1m data...")
    dfs_nifty = []
    d22 = pd.read_csv('data/nifty50/NIFTY50_1min_2022.csv')
    d22['Timestamp'] = pd.to_datetime(d22['Timestamp'])
    dfs_nifty.append(d22[d22['Timestamp'] >= '2022-10-01'])
    for y in ['2023', '2024', '2025']:
        p = f'data/nifty50/NIFTY50_1min_{y}.csv'
        if os.path.exists(p):
            d = pd.read_csv(p)
            d['Timestamp'] = pd.to_datetime(d['Timestamp'])
            dfs_nifty.append(d)
    for f in sorted(glob.glob('data/nifty50/2026/*.csv')):
        d = pd.read_csv(f)
        d['Timestamp'] = pd.to_datetime(d['Timestamp'])
        dfs_nifty.append(d)
    nifty_1m = pd.concat(dfs_nifty).sort_values('Timestamp').drop_duplicates('Timestamp').reset_index(drop=True)
    nifty_1m['Time'] = nifty_1m['Timestamp'].dt.time
    nifty_1m = nifty_1m[(nifty_1m['Time'] >= time(9, 15)) & (nifty_1m['Time'] <= time(15, 29))].copy()
    return nifty_1m

def resample_nifty(df_1m, tf_min):
    if tf_min == 1:
        df = df_1m.copy()
    else:
        df = df_1m.set_index('Timestamp').resample(f'{tf_min}min', origin='start_day', offset='15min').agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum' if 'Volume' in df_1m.columns else 'count'
        }).dropna().reset_index()

    df['Date'] = df['Timestamp'].dt.date
    df['Time'] = df['Timestamp'].dt.time
    df['Typ'] = (df['High'] + df['Low'] + df['Close']) / 3.0
    vol = df['Volume'].values
    if np.sum(vol) == 0 or np.all(vol == 1):
        df['VWAP'] = df.groupby('Date')['Close'].transform(lambda x: x.expanding().mean())
    else:
        df['PV'] = df['Typ'] * df['Volume']
        df['CumPV'] = df.groupby('Date')['PV'].cumsum()
        df['CumV'] = df.groupby('Date')['Volume'].cumsum()
        df['VWAP'] = df['CumPV'] / df['CumV']

    daily = df.groupby('Date').agg({'High': 'max', 'Low': 'min', 'Close': 'last'}).shift(1)
    df['PDH'] = df['Date'].map(daily['High'])
    df['PDL'] = df['Date'].map(daily['Low'])
    df['PDC'] = df['Date'].map(daily['Close'])
    return df

def extract_all_daily_ifvgs(df_tf, tf_min):
    """Pre-extract all IFVG candidates for each day once."""
    grouped = {d: g.reset_index(drop=True) for d, g in df_tf.groupby('Date')}
    daily_signals = {}

    bars_15m = max(1, 15 // tf_min)
    min_gap = 2.0 * np.sqrt(tf_min)

    for dt, day_df in grouped.items():
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

        htf_trend = 'BULL' if closes[bars_15m-1] > opens[0] else 'BEAR'
        ib_h = np.max(highs[:bars_15m])
        ib_l = np.min(lows[:bars_15m])

        active_fvgs = []
        signals = []

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

            for fvg in active_fvgs:
                if not fvg['active'] or fvg['fvg_idx'] >= k: continue

                if fvg['type'] == 'BULLISH':
                    if closes[k] < fvg['inversion_level']:
                        fvg['active'] = False
                        recent_h = np.max(highs[max(0, k-10):k+1])
                        swept = (recent_h >= pdh if pd.notna(pdh) else False) or (recent_h >= ib_h)
                        signals.append({
                            'bar': k,
                            'time': times[k],
                            'dir': 'SELL',
                            'entry': closes[k],
                            'box_max': fvg['box_max'],
                            'box_min': fvg['box_min'],
                            'trigger_high': highs[k],
                            'trigger_low': lows[k],
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
                        signals.append({
                            'bar': k,
                            'time': times[k],
                            'dir': 'BUY',
                            'entry': closes[k],
                            'box_max': fvg['box_max'],
                            'box_min': fvg['box_min'],
                            'trigger_high': highs[k],
                            'trigger_low': lows[k],
                            'vwap_ok': closes[k] > vwaps[k],
                            'htf_ok': htf_trend == 'BULL',
                            'swept': swept
                        })
                    elif highs[k] > fvg['inversion_level']:
                        fvg['inversion_level'] = highs[k]

        daily_signals[dt] = {
            'signals': signals,
            'highs': highs,
            'lows': lows,
            'closes': closes,
            'times': times,
            'n': n
        }

    return daily_signals

def evaluate_configuration(daily_signals, model, target_rr, use_be, sl_mode='FORMATION_EXTREME'):
    trades = []
    max_day_trades = 2 if '2TRADES' in model else 1
    max_day_losses = 1

    for dt, day_data in daily_signals.items():
        signals = day_data['signals']
        if not signals: continue

        highs = day_data['highs']
        lows = day_data['lows']
        closes = day_data['closes']
        times = day_data['times']
        n = day_data['n']

        day_trades = 0
        day_losses = 0

        for sig in signals:
            if day_trades >= max_day_trades or day_losses >= max_day_losses: break
            if sig['time'] >= time(14, 15): break

            if 'VWAP' in model and not sig['vwap_ok']: continue
            if 'HTF' in model and not sig['htf_ok']: continue
            if 'LIQ' in model and not sig['swept']: continue

            entry = sig['entry']
            direction = sig['dir']

            if direction == 'BUY':
                raw_sl = sig['box_min'] - 2.0 if sl_mode == 'FORMATION_EXTREME' else sig['trigger_low'] - 2.0
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
                raw_sl = sig['box_max'] + 2.0 if sl_mode == 'FORMATION_EXTREME' else sig['trigger_high'] + 2.0
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

    if not trades:
        return None

    df = pd.DataFrame(trades).sort_values('Date').reset_index(drop=True)
    df['Date'] = pd.to_datetime(df['Date'])
    df['YM'] = df['Date'].dt.to_period('M')

    tot_trades = len(df)
    tot_r = df['R'].sum()
    num_m = df['YM'].nunique()
    r_m = tot_r / num_m if num_m > 0 else 0
    cum = df['R'].cumsum()
    max_dd = (cum - cum.cummax()).min()
    wr = (df['R'] > 0).mean() * 100
    wins = df[df['R'] > 0]['R'].sum()
    losses = abs(df[df['R'] < 0]['R'].sum())
    pf = (wins / losses) if losses > 0 else 999.0

    return {
        'Trades': tot_trades,
        'WinRate': round(wr, 1),
        'Total_R': round(tot_r, 1),
        'Monthly_R': round(r_m, 2),
        'Max_DD': round(max_dd, 1),
        'PF': round(pf, 2)
    }

def run_fast_deep_exploration():
    nifty_1m = load_nifty_fast()
    timeframes = [2, 3, 5, 15]

    all_res = []

    for tf in timeframes:
        print(f"\nProcessing Timeframe: {tf}-Minute...")
        df_tf = resample_nifty(nifty_1m, tf)
        daily_signals = extract_all_daily_ifvgs(df_tf, tf)
        print(f"Extracted signals for {len(daily_signals)} days on {tf}m. Running parameter sweep...")

        for model in ['IFVG_PURE', 'IFVG_VWAP', 'IFVG_HTF', 'IFVG_LIQ', 'IFVG_2TRADES_1LOSS']:
            for target_rr in [1.5, 2.0, 2.5, 3.0, 3.5]:
                for use_be in [False, True]:
                    for sl_mode in ['FORMATION_EXTREME', 'TRIGGER_CANDLE']:
                        res = evaluate_configuration(daily_signals, model, target_rr, use_be, sl_mode)
                        if res and res['Trades'] >= 100:
                            res['TF'] = f"{tf}m"
                            res['Model'] = model
                            res['RR'] = f"1:{target_rr}"
                            res['BE'] = use_be
                            res['SL'] = sl_mode
                            all_res.append(res)
                            if res['Total_R'] >= 40:
                                print(f"[{tf:2d}m | {model:18s} | RR 1:{target_rr} | BE={use_be} | SL={sl_mode[:7]}] Trades: {res['Trades']:4d} | WR: {res['WinRate']:4.1f}% | Total R: {res['Total_R']:+7.1f}R | Mo R: {res['Monthly_R']:+5.2f}R | Max DD: {res['Max_DD']:5.1f}R | PF: {res['PF']:.2f}")

    df_out = pd.DataFrame(all_res).sort_values('Total_R', ascending=False)
    print("\n" + "="*85)
    print("                    TOP 20 BEST CONFIGURATIONS ACROSS ALL TIMEFRAMES")
    print("="*85)
    print(df_out.head(20).to_string(index=False))
    os.makedirs('reports', exist_ok=True)
    df_out.to_csv('reports/nifty_all_timeframes_sweep.csv', index=False)

if __name__ == '__main__':
    run_fast_deep_exploration()
