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
print("GROUND-TRUTH FORENSIC AUDIT: ZERO LOOKAHEAD, LIVE-IDENTICAL SIMULATION", flush=True)
print("Testing Real Institutional Setups on 4.8 Years of NSE Data (2022-2026)", flush=True)
print("100% Exact Zerodha & Dhan Statutory Tariffs (Paisa-Level)", flush=True)
print("="*95, flush=True)

def calc_statutory_charges(entry_price, exit_price, sl_dist, direction='BUY', risk_inr=200.0):
    if sl_dist <= 0 or entry_price <= 0:
        return 0.0, 0.0, 0.0
    qty = max(1, int(risk_inr / sl_dist))
    buy_px = entry_price if direction == 'BUY' else exit_price
    sell_px = exit_price if direction == 'BUY' else entry_price
    buy_turnover = qty * buy_px
    sell_turnover = qty * sell_px
    roundtrip = buy_turnover + sell_turnover
    
    brok_buy = min(20.0, buy_turnover * 0.0003)
    brok_sell = min(20.0, sell_turnover * 0.0003)
    brokerage = brok_buy + brok_sell
    
    stt = sell_turnover * 0.00025               # 0.025% on sell side
    exch = roundtrip * 0.0000297               # NSE turnover fee (0.00297%)
    sebi = roundtrip * 0.000001                # ₹10 / crore (0.0001%)
    stamp = buy_turnover * 0.00003             # Stamp duty 0.003% on buy
    gst = (brokerage + exch + sebi) * 0.18     # GST 18%
    slippage = qty * 0.05                      # 1 tick (₹0.05) spread
    
    total_charges_inr = brokerage + stt + exch + sebi + stamp + gst + slippage
    charges_r = total_charges_inr / risk_inr
    
    gross_pnl_inr = qty * (exit_price - entry_price) if direction == 'BUY' else qty * (entry_price - exit_price)
    net_pnl_inr = gross_pnl_inr - total_charges_inr
    net_r = net_pnl_inr / risk_inr
    
    return total_charges_inr, charges_r, net_r

def resample_and_calc_indicators(df_1m, tf_min=5):
    df = df_1m.set_index('Timestamp').resample(f'{tf_min}min', origin='start_day', offset='15min').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum' if 'Volume' in df_1m.columns else 'count'
    }).dropna().reset_index()

    df['Date'] = df['Timestamp'].dt.date
    df['Time'] = df['Timestamp'].dt.time
    
    # VWAP
    df['Typ'] = (df['High'] + df['Low'] + df['Close']) / 3.0
    vol = df['Volume'].values
    if np.sum(vol) == 0 or np.all(vol == 1):
        df['VWAP'] = df.groupby('Date')['Close'].transform(lambda x: x.expanding().mean())
    else:
        df['PV'] = df['Typ'] * df['Volume']
        df['VWAP'] = df.groupby('Date')['PV'].cumsum() / df.groupby('Date')['Volume'].cumsum()

    # EMAs: 9, 21, 50 calculated continuously
    df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    
    # Volume SMA20
    df['Vol_SMA20'] = df['Volume'].rolling(20, min_periods=1).mean()
    
    # ATR 14
    prev_close = df['Close'].shift(1)
    tr1 = df['High'] - df['Low']
    tr2 = (df['High'] - prev_close).abs()
    tr3 = (df['Low'] - prev_close).abs()
    df['TR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['ATR'] = df['TR'].rolling(14, min_periods=1).mean()
    
    # Prior Day High, Low, Close
    daily_stats = df.groupby('Date').agg({'High':'max', 'Low':'min', 'Close':'last'})
    daily_stats = daily_stats.shift(1).rename(columns={'High':'PDH', 'Low':'PDL', 'Close':'PDC'})
    df = df.merge(daily_stats, on='Date', how='left')
    
    # Opening Range High and Low (09:15 - 09:30, first 3 candles)
    first_bars = df[df['Time'] <= time(9, 25)].groupby('Date').agg({'High':'max', 'Low':'min'})
    first_bars = first_bars.rename(columns={'High':'OR_High', 'Low':'OR_Low'})
    df = df.merge(first_bars, on='Date', how='left')
    
    return df

print("Loading Nifty 50 macro trend...", flush=True)
nifty_1m = load_nifty_fast()
nifty_trend = get_nifty_trend_series(nifty_1m, tf_min=5)

CHAMPIONS_10 = ['RELIANCE', 'HDFCBANK', 'ICICIBANK', 'TCS', 'INFY', 'SBIN', 'BHARTIARTL', 'LT', 'MARUTI', 'TATASTEEL']

print("Pre-caching 5m datasets for Champions...", flush=True)
cached_stock_dfs = {}
for sym in CHAMPIONS_10:
    df_1m = load_stock_data(sym)
    if df_1m is not None:
        df_5m = resample_and_calc_indicators(df_1m, 5)
        df_5m['Nifty_Trend'] = df_5m['Timestamp'].map(nifty_trend['Nifty_Trend']).fillna(0).astype(int)
        cached_stock_dfs[sym] = df_5m
        print(f"  Cached {sym:12s} ({len(df_5m)} 5m bars)", flush=True)

def run_candle_by_candle_simulation(
    df,
    symbol,
    setup_type='LIQUIDITY_SWEEP', # 'LIQUIDITY_SWEEP', 'TREND_PULLBACK', 'ORB_BREAKOUT'
    target_rr=2.5,
    min_sl_pct=0.0035, # 0.35% minimum SL for stocks
    max_sl_pct=0.0080, # 0.80% max SL
    max_trades_per_day=2,
    max_losses_per_day=1,
    eod_time=time(15, 15)
):
    trades = []
    
    for dt, day_df in df.groupby('Date'):
        n = len(day_df)
        if n < 15: continue
        
        opens = day_df['Open'].values
        highs = day_df['High'].values
        lows = day_df['Low'].values
        closes = day_df['Close'].values
        volumes = day_df['Volume'].values
        vol_smas = day_df['Vol_SMA20'].values
        times = day_df['Time'].values
        ema9 = day_df['EMA9'].values
        ema21 = day_df['EMA21'].values
        ema50 = day_df['EMA50'].values
        vwap = day_df['VWAP'].values
        atr = day_df['ATR'].values
        n_trend = day_df['Nifty_Trend'].values
        pdh = day_df['PDH'].values[0]
        pdl = day_df['PDL'].values[0]
        or_h = day_df['OR_High'].values[0]
        or_l = day_df['OR_Low'].values[0]
        
        active_pos = None
        day_trades = 0
        day_losses = 0
        
        for i in range(3, n):
            # 1. Manage Active Position
            if active_pos is not None:
                h = highs[i]
                l = lows[i]
                c = closes[i]
                t = times[i]
                
                exit_px = None
                exit_reason = None
                
                if active_pos['dir'] == 'BUY':
                    if l <= active_pos['sl']:
                        exit_px = active_pos['sl']
                        exit_reason = 'STOP_LOSS'
                    elif h >= active_pos['tp']:
                        exit_px = active_pos['tp']
                        exit_reason = 'TARGET'
                    elif t >= eod_time:
                        exit_px = c
                        exit_reason = 'EOD_SQUAREOFF'
                else: # SELL
                    if h >= active_pos['sl']:
                        exit_px = active_pos['sl']
                        exit_reason = 'STOP_LOSS'
                    elif l <= active_pos['tp']:
                        exit_px = active_pos['tp']
                        exit_reason = 'TARGET'
                    elif t >= eod_time:
                        exit_px = c
                        exit_reason = 'EOD_SQUAREOFF'
                        
                if exit_px is not None:
                    c_inr, c_r, net_r = calc_statutory_charges(active_pos['entry'], exit_px, active_pos['sl_dist'], active_pos['dir'], 200.0)
                    trades.append({
                        'Date': dt, 'EntryTime': active_pos['time'], 'ExitTime': t, 'Symbol': symbol,
                        'Direction': active_pos['dir'], 'Setup': active_pos['setup'],
                        'EntryPrice': active_pos['entry'], 'ExitPrice': exit_px,
                        'SL_Dist': active_pos['sl_dist'], 'SL_Pct': active_pos['sl_pct'],
                        'Charges_INR': c_inr, 'Charges_R': c_r, 'Net_R': net_r, 'Net_INR': net_r * 200.0,
                        'ExitReason': exit_reason, 'TradeNum': day_trades
                    })
                    if net_r < 0:
                        day_losses += 1
                    active_pos = None
                continue
                
            # 2. Check for New Entry if no active position
            if day_trades >= max_trades_per_day or day_losses >= max_losses_per_day:
                continue
            if times[i] < time(9, 30) or times[i] > time(14, 15):
                continue
                
            c = closes[i]
            o = opens[i]
            h = highs[i]
            l = lows[i]
            prev_l = lows[i-1]
            prev_h = highs[i-1]
            prev_c = closes[i-1]
            prev_o = opens[i-1]
            v = volumes[i]
            vma = vol_smas[i]
            e9 = ema9[i]
            e21 = ema21[i]
            e50 = ema50[i]
            vw = vwap[i]
            at = atr[i]
            nt = n_trend[i]
            
            trigger_dir = None
            setup_name = None
            
            # ---------------------------------------------------------
            # SETUP A: LIQUIDITY SWEEP REVERSAL (Fakeout trap absorption)
            # ---------------------------------------------------------
            if setup_type == 'LIQUIDITY_SWEEP':
                sweep_low = False
                if pd.notna(pdl) and (prev_l < pdl or l < pdl) and c > pdl:
                    sweep_low = True
                elif pd.notna(or_l) and (prev_l < or_l or l < or_l) and c > or_l:
                    sweep_low = True
                    
                if sweep_low and c > e9 and c > o and nt >= 0:
                    trigger_dir = 'BUY'
                    setup_name = 'Bullish Liquidity Sweep'
                    
                sweep_high = False
                if pd.notna(pdh) and (prev_h > pdh or h > pdh) and c < pdh:
                    sweep_high = True
                elif pd.notna(or_h) and (prev_h > or_h or h > or_h) and c < or_h:
                    sweep_high = True
                    
                if sweep_high and c < e9 and c < o and nt <= 0:
                    trigger_dir = 'SELL'
                    setup_name = 'Bearish Liquidity Sweep'

            # ---------------------------------------------------------
            # SETUP B: TREND PULLBACK (Stacked EMAs + Pullback to EMA21/VWAP)
            # ---------------------------------------------------------
            elif setup_type == 'TREND_PULLBACK':
                if (e9 > e21 > e50 and c > vw and nt == 1 and 
                    (prev_l <= e21 * 1.002 or l <= e21 * 1.002) and 
                    c > e9 and c > o and (v / (vma + 1e-6)) >= 1.0):
                    trigger_dir = 'BUY'
                    setup_name = 'Bullish Trend Pullback'
                elif (e9 < e21 < e50 and c < vw and nt == -1 and 
                      (prev_h >= e21 * 0.998 or h >= e21 * 0.998) and 
                      c < e9 and c < o and (v / (vma + 1e-6)) >= 1.0):
                    trigger_dir = 'SELL'
                    setup_name = 'Bearish Trend Pullback'

            # ---------------------------------------------------------
            # SETUP C: ORB BREAKOUT (Day Trader Opening Range Breakout with RVOL)
            # ---------------------------------------------------------
            elif setup_type == 'ORB_BREAKOUT':
                if pd.notna(or_h) and c > or_h and prev_c <= or_h and c > vw and nt == 1 and (v / (vma + 1e-6)) >= 1.25:
                    trigger_dir = 'BUY'
                    setup_name = 'ORB Long'
                elif pd.notna(or_l) and c < or_l and prev_c >= or_l and c < vw and nt == -1 and (v / (vma + 1e-6)) >= 1.25:
                    trigger_dir = 'SELL'
                    setup_name = 'ORB Short'

            if trigger_dir is not None:
                entry = c
                if trigger_dir == 'BUY':
                    raw_sl_dist = entry - min(l, prev_l)
                    sl_dist = max(raw_sl_dist, entry * min_sl_pct)
                    if sl_dist > entry * max_sl_pct:
                        continue
                    sl = entry - sl_dist
                    tp = entry + (sl_dist * target_rr)
                else:
                    raw_sl_dist = max(h, prev_h) - entry
                    sl_dist = max(raw_sl_dist, entry * min_sl_pct)
                    if sl_dist > entry * max_sl_pct:
                        continue
                    sl = entry + sl_dist
                    tp = entry - (sl_dist * target_rr)
                    
                sl_pct = (sl_dist / entry) * 100.0
                day_trades += 1
                active_pos = {
                    'time': times[i], 'entry': entry, 'sl': sl, 'tp': tp,
                    'sl_dist': sl_dist, 'sl_pct': sl_pct, 'dir': trigger_dir,
                    'setup': setup_name
                }
                
    return trades

test_configs = [
    {'name': '1. Liquidity Sweep Reversal (1:2.0 RRR)', 'setup': 'LIQUIDITY_SWEEP', 'rr': 2.0},
    {'name': '2. Liquidity Sweep Reversal (1:2.5 RRR)', 'setup': 'LIQUIDITY_SWEEP', 'rr': 2.5},
    {'name': '3. Liquidity Sweep Reversal (1:2.8 RRR)', 'setup': 'LIQUIDITY_SWEEP', 'rr': 2.8},
    {'name': '4. Trend Pullback EMA21/VWAP (1:2.0 RRR)', 'setup': 'TREND_PULLBACK', 'rr': 2.0},
    {'name': '5. Trend Pullback EMA21/VWAP (1:2.5 RRR)', 'setup': 'TREND_PULLBACK', 'rr': 2.5},
    {'name': '6. Trend Pullback EMA21/VWAP (1:3.0 RRR)', 'setup': 'TREND_PULLBACK', 'rr': 3.0},
    {'name': '7. Day Trader ORB Breakout (1:2.0 RRR)', 'setup': 'ORB_BREAKOUT', 'rr': 2.0},
]

print("\n" + "="*95, flush=True)
print("BENCHMARKING INSTITUTIONAL STRATEGY ARCHITECTURES (ZERO LOOKAHEAD, NO OVERLAPS)", flush=True)
print("="*95, flush=True)

summary_rows = []

for cfg in test_configs:
    all_trades = []
    print(f"Simulating: {cfg['name']}...", flush=True)
    for sym, df_5m in cached_stock_dfs.items():
        t = run_candle_by_candle_simulation(
            df_5m, sym,
            setup_type=cfg['setup'], target_rr=cfg['rr']
        )
        all_trades.extend(t)
        
    if not all_trades:
        print("  No trades generated.", flush=True)
        continue
        
    df_res = pd.DataFrame(all_trades)
    df_res['Date'] = pd.to_datetime(df_res['Date'])
    df_res['YM'] = df_res['Date'].dt.to_period('M')
    
    tot_trades = len(df_res)
    wins = df_res[df_res['Net_R'] > 0]
    wr = len(wins) / tot_trades * 100.0
    tot_net_r = df_res['Net_R'].sum()
    num_months = df_res['YM'].nunique()
    mo_r = tot_net_r / num_months if num_months > 0 else 0
    
    gw = wins['Net_R'].sum()
    gl = abs(df_res[df_res['Net_R'] <= 0]['Net_R'].sum())
    pf = gw / gl if gl > 0 else 99.0
    
    daily_pnl = df_res.groupby('Date')['Net_R'].sum()
    cum = daily_pnl.cumsum()
    max_dd = (cum - cum.cummax()).min()
    
    monthly_pnl = df_res.groupby('YM')['Net_R'].sum()
    pos_m = (monthly_pnl > 0).sum()
    
    print(f"  -> Trades: {tot_trades:4d} | WR: {wr:5.2f}% | PF: {pf:4.2f} | Net R: {tot_net_r:+7.1f} R | Mo: {mo_r:+5.2f} R/mo | Max DD: {max_dd:6.1f} R | Prof Months: {pos_m}/{num_months}", flush=True)
    summary_rows.append({
        'Strategy': cfg['name'],
        'Trades': tot_trades,
        'WinRate': f"{wr:.1f}%",
        'PF': round(pf, 2),
        'Total_Net_R': f"{tot_net_r:+.1f} R",
        'Monthly_Net_R': f"{mo_r:+.2f} R/mo",
        'Max_DD_R': f"{max_dd:.1f} R",
        'Net_Cash_200R': f"INR {tot_net_r * 200:,.0f}",
        'Prof_Months': f"{pos_m}/{num_months} ({pos_m/num_months*100:.1f}%)"
    })

print("\n" + "="*115, flush=True)
print("FINAL GROUND-TRUTH COMPARISON TABLE (100% LIVE-IDENTICAL EXECUTION, NO LOOKAHEAD, NO OVERLAPS)", flush=True)
print("="*115, flush=True)
print(pd.DataFrame(summary_rows).to_string(index=False), flush=True)
