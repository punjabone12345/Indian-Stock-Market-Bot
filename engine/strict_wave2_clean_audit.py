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
print("STRICT FORENSIC AUDIT: ZERO LOOKAHEAD, NO OVERLAPS, 100% REALISTIC WAVE 2", flush=True)
print("Rule: Trade 2 can ONLY enter AFTER Trade 1 has fully closed as a WINNER in live time!", flush=True)
print("Statutory Charges: 100% Exact Zerodha & Dhan Official Tariff (Paisa-Level)", flush=True)
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

def resample_and_calc_rich_indicators(df_1m, tf_min=5):
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

    # EMAs: 9, 21, 50
    df['EMA9'] = df.groupby('Date')['Close'].transform(lambda x: x.ewm(span=9, adjust=False).mean())
    df['EMA21'] = df.groupby('Date')['Close'].transform(lambda x: x.ewm(span=21, adjust=False).mean())
    df['EMA50'] = df.groupby('Date')['Close'].transform(lambda x: x.ewm(span=50, adjust=False).mean())
    
    # Volume SMA20
    df['Vol_SMA20'] = df.groupby('Date')['Volume'].transform(lambda x: x.rolling(20, min_periods=1).mean())
    
    # ATR 14
    prev_close = df.groupby('Date')['Close'].shift(1)
    tr1 = df['High'] - df['Low']
    tr2 = (df['High'] - prev_close).abs()
    tr3 = (df['Low'] - prev_close).abs()
    df['TR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['ATR'] = df.groupby('Date')['TR'].transform(lambda x: x.rolling(14, min_periods=1).mean())
    
    return df

def run_strict_non_overlapping_backtest(df_stock, nifty_trend_idx, symbol, target_rr=3.0, max_day_trades=2, eod_cutoff_time=time(15, 0)):
    df_stock = df_stock.copy()
    df_stock['Nifty_Trend'] = df_stock['Timestamp'].map(nifty_trend_idx['Nifty_Trend']).fillna(0).astype(int)
    
    trades = []
    daily_groups = df_stock.groupby('Date')
    
    for dt, day_df in daily_groups:
        n = len(day_df)
        if n < 10: continue
        
        opens = day_df['Open'].values
        highs = day_df['High'].values
        lows = day_df['Low'].values
        closes = day_df['Close'].values
        vols = day_df['Volume'].values
        vol_smas = day_df['Vol_SMA20'].values
        times = day_df['Time'].values
        ema9 = day_df['EMA9'].values
        ema21 = day_df['EMA21'].values
        ema50 = day_df['EMA50'].values
        vwap = day_df['VWAP'].values
        atr = day_df['ATR'].values
        n_trend = day_df['Nifty_Trend'].values
        
        day_trades = 0
        i = 2
        
        while i < n - 2:
            if day_trades >= max_day_trades:
                break
            if times[i] < time(9, 30) or times[i] > time(14, 15):
                i += 1
                continue
                
            candle_range = highs[i] - lows[i] + 1e-6
            body_size = abs(closes[i] - opens[i])
            body_ratio = body_size / candle_range
            vol_ratio = vols[i] / (vol_smas[i] + 1e-6)
            
            trigger_dir = None
            # BUY
            if (n_trend[i] == 1 and closes[i] > vwap[i] and ema9[i] > ema21[i] and 
                (lows[i] <= ema9[i] or lows[i-1] <= ema9[i-1]) and 
                closes[i] > opens[i] and closes[i] > ema9[i]):
                trigger_dir = 'BUY'
            # SELL
            elif (n_trend[i] == -1 and closes[i] < vwap[i] and ema9[i] < ema21[i] and 
                  (highs[i] >= ema9[i] or highs[i-1] >= ema9[i-1]) and 
                  closes[i] < opens[i] and closes[i] < ema9[i]):
                trigger_dir = 'SELL'
                
            if trigger_dir is None:
                i += 1
                continue
                
            entry = closes[i]
            if trigger_dir == 'BUY':
                raw_sl = min(lows[i], lows[i-1]) - (0.2 * atr[i])
                sl_dist = max(entry - raw_sl, entry * 0.0020)
                if sl_dist > entry * 0.0070:
                    i += 1
                    continue
                sl = entry - sl_dist
                tp = entry + (sl_dist * target_rr)
            else:
                raw_sl = max(highs[i], highs[i-1]) + (0.2 * atr[i])
                sl_dist = max(raw_sl - entry, entry * 0.0020)
                if sl_dist > entry * 0.0070:
                    i += 1
                    continue
                sl = entry + sl_dist
                tp = entry - (sl_dist * target_rr)
                
            sl_pct = (sl_dist / entry) * 100.0
            
            # Now simulate the forward holding strictly bar by bar
            final_r = None
            exit_time = None
            exit_reason = None
            exit_px = None
            exit_bar_idx = n
            
            for m in range(i + 1, n):
                if trigger_dir == 'BUY':
                    if lows[m] <= sl:
                        final_r = -1.04
                        exit_px = sl
                        exit_time = times[m]
                        exit_reason = 'STOP_LOSS'
                        exit_bar_idx = m
                        break
                    elif highs[m] >= tp:
                        final_r = round(target_rr - 0.04, 2)
                        exit_px = tp
                        exit_time = times[m]
                        exit_reason = 'TARGET'
                        exit_bar_idx = m
                        break
                    elif times[m] >= eod_cutoff_time:
                        final_r = round((closes[m] - entry)/sl_dist - 0.04, 2)
                        exit_px = closes[m]
                        exit_time = times[m]
                        exit_reason = 'EOD_SQUAREOFF_3PM'
                        exit_bar_idx = m
                        break
                else: # SELL
                    if highs[m] >= sl:
                        final_r = -1.04
                        exit_px = sl
                        exit_time = times[m]
                        exit_reason = 'STOP_LOSS'
                        exit_bar_idx = m
                        break
                    elif lows[m] <= tp:
                        final_r = round(target_rr - 0.04, 2)
                        exit_px = tp
                        exit_time = times[m]
                        exit_reason = 'TARGET'
                        exit_bar_idx = m
                        break
                    elif times[m] >= eod_cutoff_time:
                        final_r = round((entry - closes[m])/sl_dist - 0.04, 2)
                        exit_px = closes[m]
                        exit_time = times[m]
                        exit_reason = 'EOD_SQUAREOFF_3PM'
                        exit_bar_idx = m
                        break
                        
            if final_r is not None:
                day_trades += 1
                c_inr, c_r, net_r = calc_statutory_charges(entry, exit_px, sl_dist, trigger_dir, 200.0)
                trades.append({
                    'Date': dt,
                    'EntryTime': times[i],
                    'ExitTime': exit_time,
                    'Symbol': symbol,
                    'Dir': trigger_dir,
                    'EntryPrice': entry,
                    'ExitPrice': exit_px,
                    'SL_Dist': sl_dist,
                    'SL_Pct': sl_pct,
                    'Gross_R': final_r,
                    'Charges_INR': c_inr,
                    'Charges_R': c_r,
                    'Net_R': net_r,
                    'Net_INR': net_r * 200.0,
                    'ExitReason': exit_reason,
                    'TradeNum': day_trades
                })
                
                # CRITICAL REALISM:
                # 1. Advance i to AFTER the trade exits!
                i = exit_bar_idx + 1
                
                # 2. If this trade was a LOSS, STOP for the day!
                if final_r < 0:
                    break
            else:
                i += 1

    return trades

print("Loading Nifty 50 macro trend...", flush=True)
nifty_1m = load_nifty_fast()
nifty_trend = get_nifty_trend_series(nifty_1m, tf_min=5)

BASKET_6 = ['RELIANCE', 'MARUTI', 'SUNPHARMA', 'TATAMOTORS', 'TCS', 'TATASTEEL']
files = sorted(glob.glob('data/stocks/*_prev.parquet'))
ALL_SYMBOLS = [os.path.basename(f).replace('_prev.parquet', '') for f in files]

print(f"\nRunning strict non-overlapping audit on the 6 Champion basket first...", flush=True)
all_trades_strict = []
for sym in BASKET_6:
    df_1m = load_stock_data(sym)
    if df_1m is None: continue
    df_5m = resample_and_calc_rich_indicators(df_1m, 5)
    t = run_strict_non_overlapping_backtest(df_5m, nifty_trend, sym, target_rr=3.0, max_day_trades=2)
    all_trades_strict.extend(t)
    print(f"Processed {sym:12s}: {len(t)} strict sequential trades.", flush=True)

df_s = pd.DataFrame(all_trades_strict)
df_s['Date'] = pd.to_datetime(df_s['Date'])
df_s['YM'] = df_s['Date'].dt.to_period('M')

print("\n" + "="*95, flush=True)
print("STRICT NON-OVERLAPPING RESULTS: 6 CHAMPIONS (2022-2026)", flush=True)
print("="*95, flush=True)

for t_num in [1, 2]:
    sub = df_s[df_s['TradeNum'] == t_num]
    tot = len(sub)
    wins = sub[sub['Net_R'] > 0]
    wr = len(wins) / tot * 100.0 if tot > 0 else 0
    net_r = sub['Net_R'].sum()
    gw = wins['Net_R'].sum()
    gl = abs(sub[sub['Net_R'] <= 0]['Net_R'].sum())
    pf = gw / gl if gl > 0 else 99.0
    cum = sub.groupby('Date')['Net_R'].sum().cumsum()
    dd = (cum - cum.cummax()).min()
    print(f"Trade #{t_num}: Trades: {tot:4d} | Win Rate: {wr:5.2f}% | Net R: {net_r:7.1f} R | PF: {pf:.2f} | Max DD: {dd:.1f} R", flush=True)

# Combined Trade 1 + Trade 2
tot = len(df_s)
wins = df_s[df_s['Net_R'] > 0]
wr = len(wins) / tot * 100.0
net_r = df_s['Net_R'].sum()
gw = wins['Net_R'].sum()
gl = abs(df_s[df_s['Net_R'] <= 0]['Net_R'].sum())
pf = gw / gl if gl > 0 else 99.0
daily = df_s.groupby('Date')['Net_R'].sum()
cum = daily.cumsum()
dd = (cum - cum.cummax()).min()
num_months = df_s['YM'].nunique()
mo_r = net_r / num_months

print("\nTOTAL PORTFOLIO (Strict Sequential T1 + T2):", flush=True)
print(f"Total Trades: {tot} | Win Rate: {wr:.2f}% | Profit Factor: {pf:.2f} | Net R: +{net_r:.1f} R | Monthly: +{mo_r:.2f} R/mo | Max DD: {dd:.1f} R", flush=True)
