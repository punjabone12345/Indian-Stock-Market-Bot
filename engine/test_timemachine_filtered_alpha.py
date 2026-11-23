import sys
sys.path.append('engine')
import os
import glob
import pandas as pd
import numpy as np
from datetime import time
from nifty_alpha_explorer import load_nifty_fast
from nifty_aligned_ema_atr_sweep import load_stock_data

print("="*95, flush=True)
print("TESTING TIME MACHINE FILTERED PRICE ACTION ALPHA (2022-2026)", flush=True)
print("Replaying Historical Distribution | Zero Lookahead | Exact Zerodha Tariff", flush=True)
print("="*95, flush=True)

def calc_statutory_charges(entry_price: float, exit_price: float, qty: int, direction: str = 'BUY') -> float:
    entry_p = float(entry_price)
    exit_p = float(exit_price)
    q = int(qty)
    if direction == 'BUY':
        buy_val = round(entry_p * q, 2)
        sell_val = round(exit_p * q, 2)
    else:
        buy_val = round(exit_p * q, 2)
        sell_val = round(entry_p * q, 2)
    turnover = round(buy_val + sell_val, 2)
    
    buy_brok = min(20.0, round(buy_val * 0.0003, 2))
    sell_brok = min(20.0, round(sell_val * 0.0003, 2))
    brokerage = round(buy_brok + sell_brok, 2)
    stt = round(sell_val * 0.00025, 2)
    exch_fees = round(turnover * 0.0000297, 2)
    sebi_fees = round(turnover * 0.000001, 2)
    stamp_duty = round(buy_val * 0.00003, 2)
    gst = round((brokerage + exch_fees + sebi_fees) * 0.18, 2)
    slippage = round(q * 0.05, 2)
    return round(brokerage + stt + exch_fees + sebi_fees + stamp_duty + gst + slippage, 2)

print("Loading Nifty 50 macro trend...", flush=True)
nifty_1m = load_nifty_fast()
df_nifty_5m = nifty_1m.set_index('Timestamp').resample('5min', origin='start_day', offset='15min').agg({
    'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'
}).dropna().reset_index()

df_nifty_5m['EMA9'] = df_nifty_5m['Close'].ewm(span=9, adjust=False).mean()
df_nifty_5m['EMA21'] = df_nifty_5m['Close'].ewm(span=21, adjust=False).mean()
df_nifty_5m['Nifty_Trend'] = np.where(
    (df_nifty_5m['EMA9'] > df_nifty_5m['EMA21']) & (df_nifty_5m['Close'] > df_nifty_5m['EMA21']), 1,
    np.where((df_nifty_5m['EMA9'] < df_nifty_5m['EMA21']) & (df_nifty_5m['Close'] < df_nifty_5m['EMA21']), -1, 0)
)
nifty_trend_map = dict(zip(df_nifty_5m['Timestamp'], df_nifty_5m['Nifty_Trend']))

files = sorted(glob.glob('data/stocks/*_prev.parquet'))
ALL_SYMBOLS = [os.path.basename(f).replace('_prev.parquet', '') for f in files]

stock_data = {}
for sym in ALL_SYMBOLS:
    df_1m = load_stock_data(sym)
    if df_1m is None or len(df_1m) < 1000: continue
    
    df_5m = df_1m.set_index('Timestamp').resample('5min', origin='start_day', offset='15min').agg({
        'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'
    }).dropna().reset_index()
    
    df_5m['Date'] = df_5m['Timestamp'].dt.date
    df_5m['Time'] = df_5m['Timestamp'].dt.time
    
    df_5m['Typ'] = (df_5m['High'] + df_5m['Low'] + df_5m['Close']) / 3.0
    df_5m['PV'] = df_5m['Typ'] * df_5m['Volume']
    df_5m['VWAP'] = df_5m.groupby('Date')['PV'].cumsum() / df_5m.groupby('Date')['Volume'].cumsum().replace(0, 1)
    
    df_5m['EMA9'] = df_5m['Close'].ewm(span=9, adjust=False).mean()
    df_5m['EMA21'] = df_5m['Close'].ewm(span=21, adjust=False).mean()
    df_5m['VolMA20'] = df_5m['Volume'].rolling(20, min_periods=1).mean()
    
    tr1 = df_5m['High'] - df_5m['Low']
    tr2 = (df_5m['High'] - df_5m['Close'].shift()).abs()
    tr3 = (df_5m['Low'] - df_5m['Close'].shift()).abs()
    df_5m['ATR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14, min_periods=1).mean()
    
    d_agg = df_5m.groupby('Date').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'})
    d_agg['High_20d'] = d_agg['High'].rolling(20, min_periods=5).max()
    d_agg['Low_20d'] = d_agg['Low'].rolling(20, min_periods=5).min()
    d_prev = d_agg.shift(1).rename(columns={'Close':'PDC', 'High_20d':'High_20d_Prev', 'Low_20d':'Low_20d_Prev'})
    df_5m = df_5m.merge(d_prev[['PDC', 'High_20d_Prev', 'Low_20d_Prev']], on='Date', how='left')
    
    first_bars = df_5m[df_5m['Time'] <= time(9, 25)].groupby('Date').agg({'High':'max', 'Low':'min'})
    df_5m['OR_H'] = df_5m['Date'].map(first_bars['High'])
    df_5m['OR_L'] = df_5m['Date'].map(first_bars['Low'])
    df_5m['Nifty_Trend'] = df_5m['Timestamp'].map(nifty_trend_map).fillna(0).astype(int)
    
    # Prior return distribution for Time Machine
    df_5m['Prev_Close'] = df_5m['Close'].shift(1)
    df_5m['H_Ratio'] = df_5m['High'] / df_5m['Prev_Close']
    df_5m['L_Ratio'] = df_5m['Low'] / df_5m['Prev_Close']
    df_5m['C_Ratio'] = df_5m['Close'] / df_5m['Prev_Close']
    
    stock_data[sym] = df_5m

print(f"Prepped {len(stock_data)} equities.", flush=True)

# TIME MACHINE REPLAY FUNCTION
def evaluate_time_machine_odds(h_ratios, l_ratios, c_ratios, entry_px, sl_px, tp_px, bars_left, direction='BUY', n_replays=200):
    """Replays n_replays simulated sessions from past bar ratios."""
    if len(h_ratios) < 50: return 0.5, 0.0 # fallback
    
    sl_dist = abs(entry_px - sl_px)
    tp_dist = abs(tp_px - entry_px)
    target_r = tp_dist / sl_dist
    
    # Fast vectorized draw
    idx = np.random.randint(0, len(h_ratios), size=(n_replays, bars_left))
    sampled_h = h_ratios[idx]
    sampled_l = l_ratios[idx]
    sampled_c = c_ratios[idx]
    
    tp_hits = 0
    sl_hits = 0
    neither_r = 0.0
    
    if direction == 'BUY':
        for s in range(n_replays):
            px = entry_px
            hit = 0
            for b in range(bars_left):
                hi = px * sampled_h[s, b]
                lo = px * sampled_l[s, b]
                px = px * sampled_c[s, b]
                if lo <= sl_px:
                    hit = -1; break
                elif hi >= tp_px:
                    hit = 1; break
            if hit == 1: tp_hits += 1
            elif hit == -1: sl_hits += 1
            else: neither_r += (px - entry_px) / sl_dist
    else:
        for s in range(n_replays):
            px = entry_px
            hit = 0
            for b in range(bars_left):
                hi = px * sampled_h[s, b]
                lo = px * sampled_l[s, b]
                px = px * sampled_c[s, b]
                if hi >= sl_px:
                    hit = -1; break
                elif lo <= tp_px:
                    hit = 1; break
            if hit == 1: tp_hits += 1
            elif hit == -1: sl_hits += 1
            else: neither_r += (entry_px - px) / sl_dist
            
    p_tp = tp_hits / n_replays
    p_sl = sl_hits / n_replays
    ev = (p_tp * target_r) - (p_sl * 1.0) + (neither_r / n_replays)
    return p_tp, ev

np.random.seed(19)

# Sweep different Time Machine thresholds
for min_ev in [0.0, 0.15, 0.25]:
    for rvol_thresh in [1.2, 1.4]:
        for target_rr in [2.5, 3.0]:
            candidate_trades = []
            for sym, df_5m in stock_data.items():
                h_r = df_5m['H_Ratio'].dropna().values
                l_r = df_5m['L_Ratio'].dropna().values
                c_r = df_5m['C_Ratio'].dropna().values
                
                for dt, day_df in df_5m.groupby('Date'):
                    n = len(day_df)
                    if n < 20: continue
                    pdc = day_df['PDC'].values[0]
                    if pd.isna(pdc) or pdc <= 0: continue
                    
                    h_20d = day_df['High_20d_Prev'].values[0]
                    l_20d = day_df['Low_20d_Prev'].values[0]
                    or_h = day_df['OR_H'].values[0]
                    or_l = day_df['OR_L'].values[0]
                    
                    opens = day_df['Open'].values
                    highs = day_df['High'].values
                    lows = day_df['Low'].values
                    closes = day_df['Close'].values
                    vols = day_df['Volume'].values
                    volmas = day_df['VolMA20'].values
                    times = day_df['Time'].values
                    vwap = day_df['VWAP'].values
                    ema9 = day_df['EMA9'].values
                    ema21 = day_df['EMA21'].values
                    atr = day_df['ATR'].values
                    nt = day_df['Nifty_Trend'].values
                    gap_pct = (opens[0] - pdc) / pdc * 100.0
                    
                    for i in range(3, n - 4):
                        if times[i] < time(9, 30) or times[i] > time(13, 0): continue
                        rvol = vols[i] / (volmas[i] + 1e-6)
                        if rvol < rvol_thresh: continue
                        
                        trigger = None
                        setup = None
                        raw_sl = 0.0
                        
                        # 1. ORB Breakout with Gap Catalyst
                        if abs(gap_pct) >= 0.7:
                            if gap_pct > 0 and nt[i] == 1 and closes[i] > vwap[i] and closes[i] > or_h and opens[i] <= or_h and closes[i] > opens[i]:
                                trigger = 'BUY'; setup = 'CATALYST_ORB'; raw_sl = (or_h + or_l)/2.0
                            elif gap_pct < 0 and nt[i] == -1 and closes[i] < vwap[i] and closes[i] < or_l and opens[i] >= or_l and closes[i] < opens[i]:
                                trigger = 'SELL'; setup = 'CATALYST_ORB'; raw_sl = (or_h + or_l)/2.0
                                
                        # 2. 20-Day High Institutional Breakout
                        if trigger is None and pd.notna(h_20d) and h_20d > 0:
                            if nt[i] == 1 and closes[i] > h_20d and opens[i] <= h_20d and closes[i] > vwap[i]:
                                trigger = 'BUY'; setup = '20D_BREAKOUT'; raw_sl = closes[i] - 1.5 * atr[i]
                        if trigger is None and pd.notna(l_20d) and l_20d > 0:
                            if nt[i] == -1 and closes[i] < l_20d and opens[i] >= l_20d and closes[i] < vwap[i]:
                                trigger = 'SELL'; setup = '20D_BREAKOUT'; raw_sl = closes[i] + 1.5 * atr[i]
                                
                        if trigger is not None:
                            entry = closes[i]
                            if trigger == 'BUY':
                                sl_dist = max(entry - raw_sl, entry * 0.0050)
                                if sl_dist > entry * 0.0120: continue
                                sl = entry - sl_dist
                                tp = entry + sl_dist * target_rr
                            else:
                                sl_dist = max(raw_sl - entry, entry * 0.0050)
                                if sl_dist > entry * 0.0120: continue
                                sl = entry + sl_dist
                                tp = entry - sl_dist * target_rr
                                
                            bars_left = n - i
                            p_tp, ev = evaluate_time_machine_odds(h_r, l_r, c_r, entry, sl, tp, bars_left, trigger, n_replays=100)
                            
                            if ev < min_ev:
                                continue # REJECTED BY TIME MACHINE!
                                
                            candidate_trades.append({
                                'Date': dt, 'Time': times[i], 'Symbol': sym, 'Direction': trigger,
                                'Setup': setup, 'Entry': entry, 'SL': sl, 'TP': tp,
                                'SL_Dist': sl_dist, 'TargetRR': target_rr,
                                'DayIdx': i, 'DayLength': n,
                                'DayHighs': highs, 'DayLows': lows, 'DayCloses': closes, 'DayTimes': times,
                                'EV': ev
                            })
                            break # max 1 candidate per day per stock
                            
            # Simulate sequential portfolio execution
            candidate_trades = sorted(candidate_trades, key=lambda x: (x['Date'], x['Time']))
            executed_trades = []
            active_positions = {}
            curr_date = None
            
            for cand in candidate_trades:
                dt = cand['Date']
                sym = cand['Symbol']
                if dt != curr_date:
                    curr_date = dt
                    active_positions = {}
                if sym in active_positions:
                    if cand['Time'] <= active_positions[sym]: continue
                    else: del active_positions[sym]
                    
                direction = cand['Direction']
                entry = cand['Entry']
                sl = cand['SL']
                tp = cand['TP']
                sl_dist = cand['SL_Dist']
                highs = cand['DayHighs']
                lows = cand['DayLows']
                closes = cand['DayCloses']
                times = cand['DayTimes']
                start_i = cand['DayIdx']
                n = cand['DayLength']
                
                exit_px = None; exit_t = None
                is_be = False
                
                for m in range(start_i + 1, n):
                    h = highs[m]; l = lows[m]; c = closes[m]; t = times[m]
                    if direction == 'BUY':
                        if not is_be and (h - entry) >= 1.2 * sl_dist:
                            sl = entry + 0.1 * sl_dist
                            is_be = True
                        if l <= sl:
                            exit_px = sl; exit_t = t; break
                        elif h >= tp:
                            exit_px = tp; exit_t = t; break
                        elif t >= time(15, 0):
                            exit_px = c; exit_t = t; break
                    else:
                        if not is_be and (entry - l) >= 1.2 * sl_dist:
                            sl = entry - 0.1 * sl_dist
                            is_be = True
                        if h >= sl:
                            exit_px = sl; exit_t = t; break
                        elif l <= tp:
                            exit_px = tp; exit_t = t; break
                        elif t >= time(15, 0):
                            exit_px = c; exit_t = t; break
                            
                if exit_px is not None:
                    qty = max(1, int(200.0 / sl_dist))
                    charges = calc_statutory_charges(entry, exit_px, qty, direction)
                    gross = (exit_px - entry) * qty if direction == 'BUY' else (entry - exit_px) * qty
                    net = round(gross - charges, 2)
                    net_r = round(net / 200.0, 2)
                    executed_trades.append({'Date': dt, 'Symbol': sym, 'Net_R': net_r})
                    active_positions[sym] = exit_t
                    
            if executed_trades:
                df_ex = pd.DataFrame(executed_trades)
                df_ex['Date'] = pd.to_datetime(df_ex['Date'])
                df_ex['YM'] = df_ex['Date'].dt.to_period('M')
                tot = len(df_ex)
                wins = df_ex[df_ex['Net_R'] > 0]
                wr = len(wins) / tot * 100
                tot_r = df_ex['Net_R'].sum()
                mo_r = tot_r / 49.0
                gw = wins['Net_R'].sum()
                gl = abs(df_ex[df_ex['Net_R'] <= 0]['Net_R'].sum())
                pf = gw / gl if gl > 0 else 99
                daily = df_ex.groupby('Date')['Net_R'].sum()
                max_dd = (daily.cumsum() - daily.cumsum().cummax()).min()
                print(f"EV>={min_ev:4.2f} | RVOL>={rvol_thresh} | RR={target_rr} -> Trades: {tot:4d} (~{tot/49:.1f}/mo) | WR: {wr:4.1f}% | PF: {pf:4.2f} | Net R: {tot_r:+6.1f} R | Mo: {mo_r:+5.2f} R/mo | Max DD: {max_dd:5.1f} R", flush=True)
