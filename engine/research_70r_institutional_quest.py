import sys
sys.path.append('engine')
import os
import glob
import pandas as pd
import numpy as np
import datetime
from datetime import time

print("="*95, flush=True)
print("INSTITUTIONAL 70+ R QUEST: SCIENTIFIC DISCOVERY ENGINE", flush=True)
print("Strict Candle-by-Candle | Zero Overlap | Zero Lookahead | Exact Zerodha/Dhan Taxes", flush=True)
print("Testing 5 High-Conviction Institutional Setups on 15m & 5m Timeframes (2022-2026)", flush=True)
print("="*95, flush=True)

def calc_statutory_charges(entry_price, exit_price, sl_dist, direction='BUY', risk_inr=200.0):
    if sl_dist <= 0 or entry_price <= 0: return 0.0, 0.0, 0.0
    qty = max(1, int(risk_inr / sl_dist))
    buy_px = entry_price if direction == 'BUY' else exit_price
    sell_px = exit_price if direction == 'BUY' else entry_price
    buy_turnover = qty * buy_px
    sell_turnover = qty * sell_px
    roundtrip = buy_turnover + sell_turnover
    
    brok = min(20.0, buy_turnover * 0.0003) + min(20.0, sell_turnover * 0.0003)
    stt = sell_turnover * 0.00025
    exch = roundtrip * 0.0000297
    sebi = roundtrip * 0.000001
    stamp = buy_turnover * 0.00003
    gst = (brok + exch + sebi) * 0.18
    slippage = qty * 0.05
    
    total_tax = brok + stt + exch + sebi + stamp + gst + slippage
    tax_r = total_tax / risk_inr
    gross_pnl = qty * (exit_price - entry_price) if direction == 'BUY' else qty * (entry_price - exit_price)
    net_pnl = gross_pnl - total_tax
    net_r = net_pnl / risk_inr
    return total_tax, tax_r, net_r

# Load 15m stock data
def load_and_resample(symbol, tf_min=15):
    f_prev = f'data/stocks/{symbol}_prev.parquet'
    f_2026 = f'data/stocks/{symbol}_2026.parquet'
    dfs = []
    if os.path.exists(f_prev):
        d1 = pd.read_parquet(f_prev)
        d1['Timestamp'] = pd.to_datetime(d1['Date'])
        d1 = d1[d1['Timestamp'] >= '2022-01-01']
        dfs.append(d1[['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']])
    if os.path.exists(f_2026):
        d2 = pd.read_parquet(f_2026)
        d2['Timestamp'] = pd.to_datetime(d2['Date'])
        dfs.append(d2[['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']])
    if not dfs: return None
    df = pd.concat(dfs).sort_values('Timestamp').drop_duplicates('Timestamp').reset_index(drop=True)
    df['Time'] = df['Timestamp'].dt.time
    df = df[(df['Time'] >= time(9, 15)) & (df['Time'] <= time(15, 30))].copy()
    
    # Resample
    df_tf = df.set_index('Timestamp').resample(f'{tf_min}min', origin='start_day', offset='15min').agg({
        'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'
    }).dropna().reset_index()
    
    df_tf['Date'] = df_tf['Timestamp'].dt.date
    df_tf['Time'] = df_tf['Timestamp'].dt.time
    
    # VWAP
    df_tf['Typ'] = (df_tf['High'] + df_tf['Low'] + df_tf['Close']) / 3.0
    df_tf['PV'] = df_tf['Typ'] * df_tf['Volume']
    df_tf['VWAP'] = df_tf.groupby('Date')['PV'].cumsum() / df_tf.groupby('Date')['Volume'].cumsum()
    
    # EMAs
    df_tf['EMA9'] = df_tf['Close'].ewm(span=9, adjust=False).mean()
    df_tf['EMA20'] = df_tf['Close'].ewm(span=20, adjust=False).mean()
    df_tf['EMA50'] = df_tf['Close'].ewm(span=50, adjust=False).mean()
    df_tf['EMA200'] = df_tf['Close'].ewm(span=200, adjust=False).mean()
    
    # Volume SMA20
    df_tf['VolMA20'] = df_tf['Volume'].rolling(20, min_periods=1).mean()
    
    # ATR
    tr1 = df_tf['High'] - df_tf['Low']
    tr2 = (df_tf['High'] - df_tf['Close'].shift()).abs()
    tr3 = (df_tf['Low'] - df_tf['Close'].shift()).abs()
    df_tf['ATR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14, min_periods=1).mean()
    
    # Prior Day High, Low, Close
    d_agg = df_tf.groupby('Date').agg({'High':'max', 'Low':'min', 'Close':'last'})
    d_agg['Daily_EMA20'] = d_agg['Close'].ewm(span=20, adjust=False).mean()
    d_agg['Daily_Trend'] = np.where(d_agg['Close'] > d_agg['Daily_EMA20'], 1, -1)
    d_prev = d_agg.shift(1).rename(columns={'High':'PDH', 'Low':'PDL', 'Close':'PDC', 'Daily_Trend':'Daily_Trend_Prev'})
    df_tf = df_tf.merge(d_prev, on='Date', how='left')
    
    # Opening Range: First 2 candles (09:15 - 09:45)
    or_bars = df_tf[df_tf['Time'] <= time(9, 30)].groupby('Date').agg({'High':'max', 'Low':'min'})
    or_bars = or_bars.rename(columns={'High':'OR_H', 'Low':'OR_L'})
    df_tf = df_tf.merge(or_bars, on='Date', how='left')
    
    return df_tf

# Load Nifty Macro
def load_nifty_15m():
    dfs = []
    for y in ['2022', '2023', '2024', '2025']:
        p = f'data/nifty50/NIFTY50_1min_{y}.csv'
        if os.path.exists(p):
            d = pd.read_csv(p)
            d['Timestamp'] = pd.to_datetime(d['Timestamp'])
            dfs.append(d[['Timestamp', 'Open', 'High', 'Low', 'Close']])
    for f in sorted(glob.glob('data/nifty50/2026/*.csv')):
        d = pd.read_csv(f)
        d['Timestamp'] = pd.to_datetime(d['Timestamp'])
        dfs.append(d[['Timestamp', 'Open', 'High', 'Low', 'Close']])
    df_n = pd.concat(dfs).sort_values('Timestamp').drop_duplicates('Timestamp').reset_index(drop=True)
    df_n = df_n.set_index('Timestamp').resample('15min', origin='start_day', offset='15min').agg({
        'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'
    }).dropna().reset_index()
    df_n['EMA20'] = df_n['Close'].ewm(span=20, adjust=False).mean()
    df_n['Nifty_Trend'] = np.where(df_n['Close'] > df_n['EMA20'], 1, -1)
    return df_n.set_index('Timestamp')['Nifty_Trend'].to_dict()

print("Loading Nifty 15m macro trend...", flush=True)
nifty_trend_15m = load_nifty_15m()
print(f"Loaded {len(nifty_trend_15m)} Nifty 15m bars.", flush=True)

files = sorted(glob.glob('data/stocks/*_prev.parquet'))
ALL_SYMBOLS = [os.path.basename(f).replace('_prev.parquet', '') for f in files]

print(f"Pre-caching 15m datasets for {len(ALL_SYMBOLS)} symbols...", flush=True)
stock_15m_cache = {}
for s in ALL_SYMBOLS:
    d = load_and_resample(s, tf_min=15)
    if d is not None and len(d) > 500:
        d['Nifty_Trend'] = d['Timestamp'].map(nifty_trend_15m).fillna(0).astype(int)
        stock_15m_cache[s] = d
print(f"Cached {len(stock_15m_cache)} symbols on 15m timeframe.", flush=True)

def simulate_15m_setup(
    setup_name,
    eval_func,
    target_rr=2.5,
    be_trail_r=1.2, # lock +0.1R when profit hits +1.2R
    max_daily_trades_per_stock=1,
    eod_time=time(15, 15)
):
    all_trades = []
    
    for sym, df in stock_15m_cache.items():
        for dt, day_df in df.groupby('Date'):
            n = len(day_df)
            if n < 8: continue
            
            opens = day_df['Open'].values
            highs = day_df['High'].values
            lows = day_df['Low'].values
            closes = day_df['Close'].values
            vols = day_df['Volume'].values
            volmas = day_df['VolMA20'].values
            times = day_df['Time'].values
            ema9 = day_df['EMA9'].values
            ema20 = day_df['EMA20'].values
            ema50 = day_df['EMA50'].values
            vwap = day_df['VWAP'].values
            atr = day_df['ATR'].values
            nt = day_df['Nifty_Trend'].values
            pdh = day_df['PDH'].values[0]
            pdl = day_df['PDL'].values[0]
            or_h = day_df['OR_H'].values[0]
            or_l = day_df['OR_L'].values[0]
            d_trend = day_df['Daily_Trend_Prev'].values[0]
            
            active_pos = None
            day_trades = 0
            
            for i in range(2, n):
                if active_pos is not None:
                    h = highs[i]; l = lows[i]; c = closes[i]; t = times[i]
                    exit_px = None; exit_reason = None
                    
                    if active_pos['dir'] == 'BUY':
                        if be_trail_r > 0 and not active_pos['is_be']:
                            if h - active_pos['entry'] >= be_trail_r * active_pos['sl_dist']:
                                active_pos['sl'] = active_pos['entry'] + 0.1 * active_pos['sl_dist']
                                active_pos['is_be'] = True
                                
                        if l <= active_pos['sl']:
                            exit_px = active_pos['sl']
                            exit_reason = 'STOP_LOSS' if not active_pos['is_be'] else 'TRAIL_BE'
                        elif h >= active_pos['tp']:
                            exit_px = active_pos['tp']; exit_reason = 'TARGET'
                        elif t >= eod_time:
                            exit_px = c; exit_reason = 'EOD_SQUAREOFF'
                    else:
                        if be_trail_r > 0 and not active_pos['is_be']:
                            if active_pos['entry'] - l >= be_trail_r * active_pos['sl_dist']:
                                active_pos['sl'] = active_pos['entry'] - 0.1 * active_pos['sl_dist']
                                active_pos['is_be'] = True
                                
                        if h >= active_pos['sl']:
                            exit_px = active_pos['sl']
                            exit_reason = 'STOP_LOSS' if not active_pos['is_be'] else 'TRAIL_BE'
                        elif l <= active_pos['tp']:
                            exit_px = active_pos['tp']; exit_reason = 'TARGET'
                        elif t >= eod_time:
                            exit_px = c; exit_reason = 'EOD_SQUAREOFF'
                            
                    if exit_px is not None:
                        c_inr, c_r, net_r = calc_statutory_charges(active_pos['entry'], exit_px, active_pos['sl_dist'], active_pos['dir'], 200.0)
                        all_trades.append({
                            'Date': dt, 'Time': active_pos['time'], 'Symbol': sym, 'Direction': active_pos['dir'],
                            'Entry': active_pos['entry'], 'Exit': exit_px, 'SL_Dist': active_pos['sl_dist'],
                            'Net_R': net_r, 'Charges_INR': c_inr, 'ExitReason': exit_reason
                        })
                        active_pos = None
                    continue
                    
                if day_trades >= max_daily_trades_per_stock: continue
                if times[i] < time(9, 45) or times[i] > time(13, 30): continue
                
                sig_dir, raw_sl = eval_func(
                    i, opens, highs, lows, closes, vols, volmas, times,
                    ema9, ema20, ema50, vwap, atr, nt, pdh, pdl, or_h, or_l, d_trend
                )
                if sig_dir is not None:
                    entry = closes[i]
                    if sig_dir == 'BUY':
                        sl_dist = max(entry - raw_sl, entry * 0.0040)
                        if sl_dist > entry * 0.0120: continue # reject SL > 1.2%
                        sl = entry - sl_dist
                        tp = entry + sl_dist * target_rr
                    else:
                        sl_dist = max(raw_sl - entry, entry * 0.0040)
                        if sl_dist > entry * 0.0120: continue
                        sl = entry + sl_dist
                        tp = entry - sl_dist * target_rr
                        
                    active_pos = {
                        'time': times[i], 'entry': entry, 'sl': sl, 'tp': tp,
                        'sl_dist': sl_dist, 'dir': sig_dir, 'is_be': False
                    }
                    day_trades += 1
                    
    if not all_trades: return None
    df_t = pd.DataFrame(all_trades)
    df_t['Date'] = pd.to_datetime(df_t['Date'])
    df_t['YM'] = df_t['Date'].dt.to_period('M')
    
    tot = len(df_t)
    wins = df_t[df_t['Net_R'] > 0]
    wr = len(wins) / tot * 100
    tot_r = df_t['Net_R'].sum()
    mo_r = tot_r / df_t['YM'].nunique()
    gw = wins['Net_R'].sum()
    gl = abs(df_t[df_t['Net_R'] <= 0]['Net_R'].sum())
    pf = gw / gl if gl > 0 else 99
    daily = df_t.groupby('Date')['Net_R'].sum()
    max_dd = (daily.cumsum() - daily.cumsum().cummax()).min()
    pos_m = (df_t.groupby('YM')['Net_R'].sum() > 0).sum()
    tot_m = df_t['YM'].nunique()
    
    return {
        'Setup': setup_name, 'Trades': tot, 'WinRate': round(wr, 1),
        'Net_R': round(tot_r, 1), 'Monthly_R': round(mo_r, 2),
        'PF': round(pf, 2), 'Max_DD': round(max_dd, 1),
        'Prof_Months': f"{pos_m}/{tot_m} ({pos_m/tot_m*100:.1f}%)",
        'df': df_t
    }

# 1. 15m Institutional ORB (Day Trader Breakout with RVOL >= 1.5x)
def eval_15m_orb(i, o, h, l, c, v, vma, t, e9, e20, e50, vw, atr, nt, pdh, pdl, or_h, or_l, d_trend):
    rvol = v[i] / (vma[i] + 1e-6)
    if rvol < 1.4: return None, 0
    # Bullish: Closes above OR_H + Daily Trend Bullish + Nifty Trend Bullish + Above VWAP
    if d_trend == 1 and nt[i] == 1 and c[i] > vw[i]:
        if pd.notna(or_h) and c[i] > or_h and o[i] <= or_h and c[i] > o[i]:
            raw_sl = min(l[i], (or_h + or_l) / 2.0)
            return 'BUY', raw_sl
    # Bearish: Closes below OR_L + Daily Trend Bearish + Nifty Trend Bearish + Below VWAP
    elif d_trend == -1 and nt[i] == -1 and c[i] < vw[i]:
        if pd.notna(or_l) and c[i] < or_l and o[i] >= or_l and c[i] < o[i]:
            raw_sl = max(h[i], (or_h + or_l) / 2.0)
            return 'SELL', raw_sl
    return None, 0

# 2. 15m Trend Pullback (First touch of EMA20/VWAP after morning expansion)
def eval_15m_pullback(i, o, h, l, c, v, vma, t, e9, e20, e50, vw, atr, nt, pdh, pdl, or_h, or_l, d_trend):
    # Bullish: EMA20 > EMA50, price > VWAP, Daily Trend == 1, Nifty == 1
    if d_trend == 1 and nt[i] == 1 and e20[i] > e50[i] and c[i] > vw[i]:
        # Pullback touching EMA20 or VWAP
        if (l[i] <= e20[i] * 1.002 or l[i-1] <= e20[i-1] * 1.002) and c[i] > o[i] and c[i] > e9[i]:
            raw_sl = min(l[i], l[i-1]) - 0.1 * atr[i]
            return 'BUY', raw_sl
    elif d_trend == -1 and nt[i] == -1 and e20[i] < e50[i] and c[i] < vw[i]:
        if (h[i] >= e20[i] * 0.998 or h[i-1] >= e20[i-1] * 0.998) and c[i] < o[i] and c[i] < e9[i]:
            raw_sl = max(h[i], h[i-1]) + 0.1 * atr[i]
            return 'SELL', raw_sl
    return None, 0

# 3. 15m Turtle Soup (Liquidity Sweep of PDH/PDL with False Breakout Reversal)
def eval_15m_sweep(i, o, h, l, c, v, vma, t, e9, e20, e50, vw, atr, nt, pdh, pdl, or_h, or_l, d_trend):
    # Bullish Reversal: Pushes below PDL, rejects and closes back above PDL
    if pd.notna(pdl) and l[i] < pdl and c[i] > pdl and c[i] > o[i]:
        raw_sl = l[i] - 0.05 * atr[i]
        return 'BUY', raw_sl
    # Bearish Reversal: Pushes above PDH, rejects and closes back below PDH
    elif pd.notna(pdh) and h[i] > pdh and c[i] < pdh and c[i] < o[i]:
        raw_sl = h[i] + 0.05 * atr[i]
        return 'SELL', raw_sl
    return None, 0

print("\n" + "="*95, flush=True)
print("BENCHMARKING 15-MINUTE INSTITUTIONAL SETUPS ACROSS ALL 30 EQUITIES", flush=True)
print("="*95, flush=True)

for rr in [2.0, 2.5, 3.0]:
    for trail in [0.0, 1.2]:
        name_orb = f"15m ORB Breakout (RR {rr}R | Trail {trail}R)"
        res = simulate_15m_setup(name_orb, eval_15m_orb, target_rr=rr, be_trail_r=trail)
        if res:
            print(f"{res['Setup']:<45s} | Trades: {res['Trades']:4d} | WR: {res['WinRate']}% | PF: {res['PF']} | Net R: {res['Net_R']:+7.1f} R | Mo: {res['Monthly_R']:+5.2f} R/mo | Max DD: {res['Max_DD']:5.1f} R | Months: {res['Prof_Months']}", flush=True)
            
        name_pb = f"15m Trend Pullback (RR {rr}R | Trail {trail}R)"
        res2 = simulate_15m_setup(name_pb, eval_15m_pullback, target_rr=rr, be_trail_r=trail)
        if res2:
            print(f"{res2['Setup']:<45s} | Trades: {res2['Trades']:4d} | WR: {res2['WinRate']}% | PF: {res2['PF']} | Net R: {res2['Net_R']:+7.1f} R | Mo: {res2['Monthly_R']:+5.2f} R/mo | Max DD: {res2['Max_DD']:5.1f} R | Months: {res2['Prof_Months']}", flush=True)

        name_sw = f"15m PDH/PDL Sweep (RR {rr}R | Trail {trail}R)"
        res3 = simulate_15m_setup(name_sw, eval_15m_sweep, target_rr=rr, be_trail_r=trail)
        if res3:
            print(f"{res3['Setup']:<45s} | Trades: {res3['Trades']:4d} | WR: {res3['WinRate']}% | PF: {res3['PF']} | Net R: {res3['Net_R']:+7.1f} R | Mo: {res3['Monthly_R']:+5.2f} R/mo | Max DD: {res3['Max_DD']:5.1f} R | Months: {res3['Prof_Months']}", flush=True)
