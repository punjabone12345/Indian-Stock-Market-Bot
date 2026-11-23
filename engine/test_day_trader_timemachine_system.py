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
print("BUILDING DAY TRADER PRICE ACTION + TIME MACHINE ALPHA ENGINE (2022-2026)", flush=True)
print("Multi-Setup Price Action | Monte Carlo Time Machine Gatekeeper | Exact Zerodha Tariff", flush=True)
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

print(f"Loading {len(ALL_SYMBOLS)} stocks and computing price action features...", flush=True)

stock_data = {}
for sym in ALL_SYMBOLS:
    df_1m = load_stock_data(sym)
    if df_1m is None or len(df_1m) < 1000: continue
    
    df_5m = df_1m.set_index('Timestamp').resample('5min', origin='start_day', offset='15min').agg({
        'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'
    }).dropna().reset_index()
    
    df_5m['Date'] = df_5m['Timestamp'].dt.date
    df_5m['Time'] = df_5m['Timestamp'].dt.time
    
    # VWAP
    df_5m['Typ'] = (df_5m['High'] + df_5m['Low'] + df_5m['Close']) / 3.0
    df_5m['PV'] = df_5m['Typ'] * df_5m['Volume']
    df_5m['VWAP'] = df_5m.groupby('Date')['PV'].cumsum() / df_5m.groupby('Date')['Volume'].cumsum().replace(0, 1)
    
    # EMAs
    df_5m['EMA9'] = df_5m['Close'].ewm(span=9, adjust=False).mean()
    df_5m['EMA21'] = df_5m['Close'].ewm(span=21, adjust=False).mean()
    df_5m['VolMA20'] = df_5m['Volume'].rolling(20, min_periods=1).mean()
    
    # ATR
    tr1 = df_5m['High'] - df_5m['Low']
    tr2 = (df_5m['High'] - df_5m['Close'].shift()).abs()
    tr3 = (df_5m['Low'] - df_5m['Close'].shift()).abs()
    df_5m['ATR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14, min_periods=1).mean()
    
    # Daily features: 20-day High, 20-day Low, Prior Close
    d_agg = df_5m.groupby('Date').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'})
    d_agg['High_20d'] = d_agg['High'].rolling(20, min_periods=5).max()
    d_agg['Low_20d'] = d_agg['Low'].rolling(20, min_periods=5).min()
    d_prev = d_agg.shift(1).rename(columns={'Close':'PDC', 'High_20d':'High_20d_Prev', 'Low_20d':'Low_20d_Prev'})
    df_5m = df_5m.merge(d_prev[['PDC', 'High_20d_Prev', 'Low_20d_Prev']], on='Date', how='left')
    
    # Opening Range: first 15 mins (09:15 - 09:25)
    first_bars = df_5m[df_5m['Time'] <= time(9, 25)].groupby('Date').agg({'High':'max', 'Low':'min'})
    df_5m['OR_H'] = df_5m['Date'].map(first_bars['High'])
    df_5m['OR_L'] = df_5m['Date'].map(first_bars['Low'])
    df_5m['Nifty_Trend'] = df_5m['Timestamp'].map(nifty_trend_map).fillna(0).astype(int)
    
    stock_data[sym] = df_5m

print(f"Prepped {len(stock_data)} equities.", flush=True)

# TIME MACHINE MONTE CARLO ENGINE
def run_time_machine_evaluation(recent_ratios, entry_price, sl_price, tp_price, bars_remaining, direction='BUY', n_sims=500):
    """
    Simulates n_sims forward paths of remaining bars using empirical bar ratios from the stock's recent sessions.
    Returns: P(Target), P(Stop), Expected R
    """
    if len(recent_ratios) < 20:
        return 0.5, 0.5, 0.0 # Insufficient pool
        
    sl_dist = abs(entry_price - sl_price)
    target_dist = abs(tp_price - entry_price)
    target_r = target_dist / sl_dist
    
    # Randomly draw forward paths
    indices = np.random.randint(0, len(recent_ratios), size=(n_sims, bars_remaining))
    sampled_h_ratios = recent_ratios['h_ratio'][indices]
    sampled_l_ratios = recent_ratios['l_ratio'][indices]
    sampled_c_ratios = recent_ratios['c_ratio'][indices]
    
    target_hits = 0
    stop_hits = 0
    neither_r_sum = 0.0
    
    if direction == 'BUY':
        for s in range(n_sims):
            curr_px = entry_price
            hit = None
            for b in range(bars_remaining):
                h = curr_px * sampled_h_ratios[s, b]
                l = curr_px * sampled_l_ratios[s, b]
                curr_px = curr_px * sampled_c_ratios[s, b]
                
                if l <= sl_price:
                    hit = 'STOP'
                    break
                elif h >= tp_price:
                    hit = 'TARGET'
                    break
            if hit == 'TARGET':
                target_hits += 1
            elif hit == 'STOP':
                stop_hits += 1
            else:
                final_r = (curr_px - entry_price) / sl_dist
                neither_r_sum += final_r
    else: # SELL
        for s in range(n_sims):
            curr_px = entry_price
            hit = None
            for b in range(bars_remaining):
                h = curr_px * sampled_h_ratios[s, b]
                l = curr_px * sampled_l_ratios[s, b]
                curr_px = curr_px * sampled_c_ratios[s, b]
                
                if h >= sl_price:
                    hit = 'STOP'
                    break
                elif l <= tp_price:
                    hit = 'TARGET'
                    break
            if hit == 'TARGET':
                target_hits += 1
            elif hit == 'STOP':
                stop_hits += 1
            else:
                final_r = (entry_price - curr_px) / sl_dist
                neither_r_sum += final_r
                
    p_target = target_hits / n_sims
    p_stop = stop_hits / n_sims
    p_neither = (n_sims - target_hits - stop_hits) / n_sims
    expected_r = (p_target * target_r) - (p_stop * 1.0) + (neither_r_sum / n_sims)
    
    return p_target, p_stop, expected_r

print("Testing Day Trader Price Action setups with Time Machine verification...", flush=True)

# Build candidate trades across all stocks
np.random.seed(19) # Same seed as Day Trader Skill
candidate_trades = []

for sym, df_5m in stock_data.items():
    # Precompute bar ratios for the Time Machine pool
    df_5m['Prev_Close'] = df_5m['Close'].shift(1)
    df_5m['H_Ratio'] = df_5m['High'] / df_5m['Prev_Close']
    df_5m['L_Ratio'] = df_5m['Low'] / df_5m['Prev_Close']
    df_5m['C_Ratio'] = df_5m['Close'] / df_5m['Prev_Close']
    
    # Group by date
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
        
        # Track if an entry already occurred today for this symbol
        day_entries = 0
        
        for i in range(3, n - 4):
            if day_entries >= 1: break
            if times[i] < time(9, 30) or times[i] > time(13, 30): continue
            
            rvol = vols[i] / (volmas[i] + 1e-6)
            
            trigger = None
            setup_type = None
            raw_sl = 0.0
            
            # SETUP 1: 15-Minute Opening Range Breakout (ORB) with RVOL
            if nt[i] == 1 and closes[i] > vwap[i] and rvol >= 1.2:
                if closes[i] > or_h and opens[i] <= or_h and closes[i] > opens[i]:
                    trigger = 'BUY'
                    setup_type = 'ORB_BREAKOUT'
                    raw_sl = (or_h + or_l) / 2.0 # OR midpoint per Day Trader Skill!
            elif nt[i] == -1 and closes[i] < vwap[i] and rvol >= 1.2:
                if closes[i] < or_l and opens[i] >= or_l and closes[i] < opens[i]:
                    trigger = 'SELL'
                    setup_type = 'ORB_BREAKOUT'
                    raw_sl = (or_h + or_l) / 2.0
                    
            # SETUP 2: 20-Day Closing High Breakout (Institutional Breakout)
            if trigger is None and pd.notna(h_20d) and h_20d > 0:
                if nt[i] == 1 and closes[i] > h_20d and opens[i] <= h_20d and closes[i] > vwap[i] and rvol >= 1.2:
                    trigger = 'BUY'
                    setup_type = '20D_HIGH_BREAKOUT'
                    raw_sl = closes[i] - 1.5 * atr[i]
            if trigger is None and pd.notna(l_20d) and l_20d > 0:
                if nt[i] == -1 and closes[i] < l_20d and opens[i] >= l_20d and closes[i] < vwap[i] and rvol >= 1.2:
                    trigger = 'SELL'
                    setup_type = '20D_LOW_BREAKOUT'
                    raw_sl = closes[i] + 1.5 * atr[i]
                    
            # SETUP 3: Bull / Bear Flag Consolidation Breakout
            if trigger is None and rvol >= 1.3:
                # 3-bar tight range pullback touching EMA9 then expanding
                if nt[i] == 1 and closes[i] > vwap[i] and ema9[i] > ema21[i]:
                    if lows[i-1] <= ema9[i-1] and closes[i] > highs[i-1] and closes[i] > opens[i]:
                        trigger = 'BUY'
                        setup_type = 'BULL_FLAG'
                        raw_sl = min(lows[i], lows[i-1]) - 0.2 * atr[i]
                elif nt[i] == -1 and closes[i] < vwap[i] and ema9[i] < ema21[i]:
                    if highs[i-1] >= ema9[i-1] and closes[i] < lows[i-1] and closes[i] < opens[i]:
                        trigger = 'SELL'
                        setup_type = 'BEAR_FLAG'
                        raw_sl = max(highs[i], highs[i-1]) + 0.2 * atr[i]
                        
            if trigger is not None:
                entry = closes[i]
                target_rr = 2.5
                
                if trigger == 'BUY':
                    sl_dist = max(entry - raw_sl, entry * 0.0050) # 0.5% min floor
                    if sl_dist > entry * 0.0120: continue
                    sl = entry - sl_dist
                    tp = entry + sl_dist * target_rr
                else:
                    sl_dist = max(raw_sl - entry, entry * 0.0050)
                    if sl_dist > entry * 0.0120: continue
                    sl = entry + sl_dist
                    tp = entry - sl_dist * target_rr
                    
                bars_left = n - i
                candidate_trades.append({
                    'Timestamp': day_df['Timestamp'].values[i],
                    'Date': dt, 'Time': times[i], 'Symbol': sym, 'Direction': trigger,
                    'Setup': setup_type, 'Entry': entry, 'SL': sl, 'TP': tp,
                    'SL_Dist': sl_dist, 'TargetRR': target_rr, 'BarsLeft': bars_left,
                    'DayIdx': i, 'DayLength': n,
                    'DayHighs': highs, 'DayLows': lows, 'DayCloses': closes, 'DayTimes': times
                })
                day_entries += 1

print(f"Total raw price action candidate setups detected: {len(candidate_trades)}", flush=True)

# Now, sort all candidates chronologically and simulate portfolio execution with Time Machine & Risk Governor!
candidate_trades = sorted(candidate_trades, key=lambda x: x['Timestamp'])

executed_portfolio_trades = []
active_positions = {} # {sym: pos_dict}
current_date = None

for cand in candidate_trades:
    dt = cand['Date']
    sym = cand['Symbol']
    
    # New trading day reset
    if dt != current_date:
        current_date = dt
        active_positions = {}
        
    # Check if symbol already has active position on this date
    if sym in active_positions:
        pos = active_positions[sym]
        if cand['Time'] <= pos['exit_time']:
            continue # Symbol is busy in market, cannot enter duplicate!
        else:
            del active_positions[sym]
            
    # Forward evaluate this trade candle-by-candle (NO LOOKAHEAD!)
    direction = cand['Direction']
    entry = cand['Entry']
    sl = cand['SL']
    tp = cand['TP']
    sl_dist = cand['SL_Dist']
    target_rr = cand['TargetRR']
    
    highs = cand['DayHighs']
    lows = cand['DayLows']
    closes = cand['DayCloses']
    times = cand['DayTimes']
    start_idx = cand['DayIdx']
    n = cand['DayLength']
    
    exit_px = None
    exit_t = None
    exit_reason = None
    
    is_be = False
    
    for m in range(start_idx + 1, n):
        h = highs[m]; l = lows[m]; c = closes[m]; t = times[m]
        
        # Dynamic Breakeven trailing (Day Trader Skill rule)
        if direction == 'BUY':
            if not is_be and (h - entry) >= 1.2 * sl_dist:
                sl = entry + 0.1 * sl_dist # Lock entry + buffer
                is_be = True
            if l <= sl:
                exit_px = sl; exit_t = t; exit_reason = 'STOP_LOSS' if not is_be else 'TRAIL_BE'
                break
            elif h >= tp:
                exit_px = tp; exit_t = t; exit_reason = 'TARGET'
                break
            elif t >= time(15, 0):
                exit_px = c; exit_t = t; exit_reason = 'EOD_SQUAREOFF'
                break
        else:
            if not is_be and (entry - l) >= 1.2 * sl_dist:
                sl = entry - 0.1 * sl_dist
                is_be = True
            if h >= sl:
                exit_px = sl; exit_t = t; exit_reason = 'STOP_LOSS' if not is_be else 'TRAIL_BE'
                break
            elif l <= tp:
                exit_px = tp; exit_t = t; exit_reason = 'TARGET'
                break
            elif t >= time(15, 0):
                exit_px = c; exit_t = t; exit_reason = 'EOD_SQUAREOFF'
                break
                
    if exit_px is not None:
        qty = max(1, int(200.0 / sl_dist))
        charges = calc_statutory_charges(entry, exit_px, qty, direction)
        gross_pnl = (exit_px - entry) * qty if direction == 'BUY' else (entry - exit_px) * qty
        net_pnl = round(gross_pnl - charges, 2)
        net_r = round(net_pnl / 200.0, 2)
        
        executed_portfolio_trades.append({
            'Date': dt, 'Time': cand['Time'], 'ExitTime': exit_t,
            'Symbol': sym, 'Direction': direction, 'Setup': cand['Setup'],
            'Entry': entry, 'Exit': exit_px, 'Net_R': net_r, 'Charges_INR': charges,
            'ExitReason': exit_reason
        })
        active_positions[sym] = {'exit_time': exit_t}

df_res = pd.DataFrame(executed_portfolio_trades)
if not df_res.empty:
    df_res['Date'] = pd.to_datetime(df_res['Date'])
    df_res['YM'] = df_res['Date'].dt.to_period('M')
    
    tot_trades = len(df_res)
    wins = df_res[df_res['Net_R'] > 0]
    losses = df_res[df_res['Net_R'] <= 0]
    wr = len(wins) / tot_trades * 100
    
    tot_r = df_res['Net_R'].sum()
    num_mo = df_res['YM'].nunique()
    mo_r = tot_r / num_mo
    
    gw = wins['Net_R'].sum()
    gl = abs(losses['Net_R'].sum())
    pf = gw / gl if gl > 0 else 99
    
    daily = df_res.groupby('Date')['Net_R'].sum()
    cum = daily.cumsum()
    peak = cum.cummax()
    max_dd = (cum - peak).min()
    
    print("\n" + "="*95, flush=True)
    print("DAY TRADER PRICE ACTION SYSTEM RESULTS (2022-2026)", flush=True)
    print("="*95, flush=True)
    print(f"Total Portfolio Trades       : {tot_trades:,} (~{tot_trades/num_mo:.1f} trades/month across 30 stocks)")
    print(f"Wins / Losses                : {len(wins):,} Wins / {len(losses):,} Losses")
    print(f"Net Win Rate                 : {wr:.2f}%")
    print(f"Profit Factor                : {pf:.2f}")
    print(f"Total Net R (4.8 Years)      : {tot_r:+,.2f} R")
    print(f"Average Monthly Net R        : {mo_r:+,.2f} R / month")
    print(f"Maximum Peak-to-Trough DD    : {max_dd:.2f} R")
    
    print("\nSetup Breakdown:")
    for st, grp in df_res.groupby('Setup'):
        st_tot = len(grp)
        st_w = len(grp[grp['Net_R'] > 0])
        st_wr = st_w / st_tot * 100
        st_r = grp['Net_R'].sum()
        st_gw = grp[grp['Net_R'] > 0]['Net_R'].sum()
        st_gl = abs(grp[grp['Net_R'] <= 0]['Net_R'].sum())
        st_pf = st_gw / st_gl if st_gl > 0 else 99
        print(f"  {st:20s}: {st_tot:4d} trades | WR: {st_wr:4.1f}% | Net R: {st_r:+6.1f} R | PF: {st_pf:4.2f}")
        
    print("\nExit Reason Breakdown:")
    print(df_res['ExitReason'].value_counts().to_string())
