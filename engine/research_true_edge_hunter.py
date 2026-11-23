import sys
sys.path.append('engine')
import os
import glob
import pandas as pd
import numpy as np
import datetime
from datetime import time
from nifty_alpha_explorer import load_nifty_fast
from nifty_aligned_ema_atr_sweep import load_stock_data, get_nifty_trend_series

print("="*95, flush=True)
print("TRUE EDGE HUNTER: SCIENTIFIC SEARCH FOR ROBUST, UNBIASED NSE ALPHA", flush=True)
print("Strict Candle-by-Candle | Zero Overlap | Zero Lookahead | Exact Statutory Tariffs", flush=True)
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

# Load Nifty Macro
nifty_1m = load_nifty_fast()
nifty_trend = get_nifty_trend_series(nifty_1m, tf_min=5)

# Load stocks with daily indicators
def prepare_stock_data(symbol):
    df_1m = load_stock_data(symbol)
    if df_1m is None or len(df_1m) < 1000: return None
    
    # 5m resample
    df_5m = df_1m.set_index('Timestamp').resample('5min', origin='start_day', offset='15min').agg({
        'Open':'first', 'High':'max', 'Low':'min', 'Close':'last',
        'Volume':'sum' if 'Volume' in df_1m.columns else 'count'
    }).dropna().reset_index()
    
    df_5m['Date'] = df_5m['Timestamp'].dt.date
    df_5m['Time'] = df_5m['Timestamp'].dt.time
    
    # Intraday indicators
    df_5m['Typ'] = (df_5m['High'] + df_5m['Low'] + df_5m['Close']) / 3.0
    df_5m['PV'] = df_5m['Typ'] * df_5m['Volume']
    df_5m['VWAP'] = df_5m.groupby('Date')['PV'].cumsum() / df_5m.groupby('Date')['Volume'].cumsum()
    
    df_5m['EMA9'] = df_5m['Close'].ewm(span=9, adjust=False).mean()
    df_5m['EMA21'] = df_5m['Close'].ewm(span=21, adjust=False).mean()
    df_5m['EMA50'] = df_5m['Close'].ewm(span=50, adjust=False).mean()
    df_5m['EMA200'] = df_5m['Close'].ewm(span=200, adjust=False).mean()
    
    df_5m['VolMA20'] = df_5m['Volume'].rolling(20, min_periods=1).mean()
    
    tr1 = df_5m['High'] - df_5m['Low']
    tr2 = (df_5m['High'] - df_5m['Close'].shift()).abs()
    tr3 = (df_5m['Low'] - df_5m['Close'].shift()).abs()
    df_5m['ATR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14, min_periods=1).mean()
    
    # Prior Day Levels
    d_agg = df_5m.groupby('Date').agg({'High':'max', 'Low':'min', 'Close':'last'})
    d_agg['Daily_EMA20'] = d_agg['Close'].ewm(span=20, adjust=False).mean()
    d_agg['Daily_Trend'] = np.where(d_agg['Close'] > d_agg['Daily_EMA20'], 1, -1)
    
    d_prev = d_agg.shift(1).rename(columns={
        'High':'PDH', 'Low':'PDL', 'Close':'PDC', 'Daily_Trend':'Daily_Trend_Prev'
    })
    df_5m = df_5m.merge(d_prev, on='Date', how='left')
    
    # Opening Range (first 3 candles, 09:15 - 09:30)
    or_bars = df_5m[df_5m['Time'] <= time(9, 25)].groupby('Date').agg({'High':'max', 'Low':'min'})
    or_bars = or_bars.rename(columns={'High':'OR_H', 'Low':'OR_L'})
    df_5m = df_5m.merge(or_bars, on='Date', how='left')
    
    df_5m['Nifty_Trend'] = df_5m['Timestamp'].map(nifty_trend['Nifty_Trend']).fillna(0).astype(int)
    return df_5m

CHAMPIONS = ['RELIANCE', 'HDFCBANK', 'ICICIBANK', 'TCS', 'INFY', 'SBIN', 'BHARTIARTL', 'LT', 'MARUTI', 'TATASTEEL']
cached = {}
for s in CHAMPIONS:
    d = prepare_stock_data(s)
    if d is not None:
        cached[s] = d
        print(f"Prepped {s:12s} ({len(d)} bars)", flush=True)

print(f"Loaded {len(cached)} champions.", flush=True)

def simulate_edge(
    setup_name,
    eval_func,
    target_rr=2.5,
    min_sl_pct=0.0035,
    max_sl_pct=0.0080,
    max_daily_trades=1,
    eod_time=time(15, 15)
):
    all_trades = []
    for sym, df in cached.items():
        for dt, day_df in df.groupby('Date'):
            n = len(day_df)
            if n < 15: continue
            
            opens = day_df['Open'].values
            highs = day_df['High'].values
            lows = day_df['Low'].values
            closes = day_df['Close'].values
            vols = day_df['Volume'].values
            volmas = day_df['VolMA20'].values
            times = day_df['Time'].values
            ema9 = day_df['EMA9'].values
            ema21 = day_df['EMA21'].values
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
            
            for i in range(3, n):
                if active_pos is not None:
                    h = highs[i]; l = lows[i]; c = closes[i]; t = times[i]
                    exit_px = None; exit_reason = None
                    
                    if active_pos['dir'] == 'BUY':
                        if l <= active_pos['sl']:
                            exit_px = active_pos['sl']; exit_reason = 'STOP_LOSS'
                        elif h >= active_pos['tp']:
                            exit_px = active_pos['tp']; exit_reason = 'TARGET'
                        elif t >= eod_time:
                            exit_px = c; exit_reason = 'EOD_SQUAREOFF'
                    else:
                        if h >= active_pos['sl']:
                            exit_px = active_pos['sl']; exit_reason = 'STOP_LOSS'
                        elif l <= active_pos['tp']:
                            exit_px = active_pos['tp']; exit_reason = 'TARGET'
                        elif t >= eod_time:
                            exit_px = c; exit_reason = 'EOD_SQUAREOFF'
                            
                    if exit_px is not None:
                        c_inr, c_r, net_r = calc_statutory_charges(active_pos['entry'], exit_px, active_pos['sl_dist'], active_pos['dir'], 200.0)
                        all_trades.append({
                            'Date': dt, 'Time': active_pos['time'], 'Symbol': sym, 'Direction': active_pos['dir'],
                            'Net_R': net_r, 'Charges_INR': c_inr, 'ExitReason': exit_reason
                        })
                        active_pos = None
                    continue
                    
                if day_trades >= max_daily_trades: continue
                if times[i] < time(9, 30) or times[i] > time(14, 15): continue
                
                # Evaluate signal
                sig_dir, raw_sl = eval_func(
                    i, opens, highs, lows, closes, vols, volmas, times,
                    ema9, ema21, ema50, vwap, atr, nt, pdh, pdl, or_h, or_l, d_trend
                )
                if sig_dir is not None:
                    entry = closes[i]
                    if sig_dir == 'BUY':
                        sl_dist = max(entry - raw_sl, entry * min_sl_pct)
                        if sl_dist > entry * max_sl_pct: continue
                        sl = entry - sl_dist
                        tp = entry + (sl_dist * target_rr)
                    else:
                        sl_dist = max(raw_sl - entry, entry * min_sl_pct)
                        if sl_dist > entry * max_sl_pct: continue
                        sl = entry + sl_dist
                        tp = entry - (sl_dist * target_rr)
                        
                    active_pos = {
                        'time': times[i], 'entry': entry, 'sl': sl, 'tp': tp,
                        'sl_dist': sl_dist, 'dir': sig_dir
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
        'Prof_Months': f"{pos_m}/{tot_m} ({pos_m/tot_m*100:.1f}%)"
    }

# Setup 1: Daily Trend + Intraday Pullback to VWAP
def eval_daily_trend_pullback(i, o, h, l, c, v, vma, t, e9, e21, e50, vw, atr, nt, pdh, pdl, or_h, or_l, d_trend):
    # Daily Trend is Bullish (d_trend == 1) AND Nifty is Bullish (nt[i] == 1)
    if d_trend == 1 and nt[i] == 1 and c[i] > vw[i]:
        # Pullback touching VWAP or EMA21
        if (l[i] <= vw[i] or l[i-1] <= vw[i-1]) and c[i] > o[i] and c[i] > e9[i]:
            raw_sl = min(l[i], l[i-1]) - (0.1 * atr[i])
            return 'BUY', raw_sl
    elif d_trend == -1 and nt[i] == -1 and c[i] < vw[i]:
        if (h[i] >= vw[i] or h[i-1] >= vw[i-1]) and c[i] < o[i] and c[i] < e9[i]:
            raw_sl = max(h[i], h[i-1]) + (0.1 * atr[i])
            return 'SELL', raw_sl
    return None, 0

# Setup 2: Institutional Fakeout (Opening Range Liquidity Trap)
def eval_orb_trap(i, o, h, l, c, v, vma, t, e9, e21, e50, vw, atr, nt, pdh, pdl, or_h, or_l, d_trend):
    # Only between 09:30 and 11:30
    if t[i] > time(11, 30): return None, 0
    # Bearish Trap: Pushes above OR_H, then drops back below OR_H with red candle
    if pd.notna(or_h) and h[i-1] > or_h and c[i] < or_h and c[i] < o[i] and c[i] < vw[i]:
        raw_sl = max(h[i], h[i-1])
        return 'SELL', raw_sl
    # Bullish Trap: Pushes below OR_L, then rallies back above OR_L with green candle
    elif pd.notna(or_l) and l[i-1] < or_l and c[i] > or_l and c[i] > o[i] and c[i] > vw[i]:
        raw_sl = min(l[i], l[i-1])
        return 'BUY', raw_sl
    return None, 0

# Setup 3: High RVOL Breakout (Expansion Candle RVOL >= 2.0x aligned with Daily Trend)
def eval_rvol_expansion(i, o, h, l, c, v, vma, t, e9, e21, e50, vw, atr, nt, pdh, pdl, or_h, or_l, d_trend):
    rvol = v[i] / (vma[i] + 1e-6)
    if rvol < 2.0: return None, 0
    candle_body = abs(c[i] - o[i])
    if candle_body < 0.6 * (h[i] - l[i] + 1e-6): return None, 0
    
    if d_trend == 1 and nt[i] == 1 and c[i] > pdh and o[i] <= pdh:
        return 'BUY', l[i] - 0.1 * atr[i]
    elif d_trend == -1 and nt[i] == -1 and c[i] < pdl and o[i] >= pdl:
        return 'SELL', h[i] + 0.1 * atr[i]
    return None, 0

print("\n" + "="*95, flush=True)
print("TESTING 3 INSTITUTIONAL EDGES (ZERO LOOKAHEAD, NO OVERLAPS, STRICT live SIMULATION)")
print("="*95, flush=True)

res1 = simulate_edge("1. Daily Trend + VWAP Pullback (TP 2.5R)", eval_daily_trend_pullback, target_rr=2.5)
if res1: print(res1, flush=True)

res2 = simulate_edge("2. Opening Range Liquidity Trap (TP 2.5R)", eval_orb_trap, target_rr=2.5)
if res2: print(res2, flush=True)

res3 = simulate_edge("3. High RVOL Daily Breakout (TP 2.5R)", eval_rvol_expansion, target_rr=2.5)
if res3: print(res3, flush=True)
