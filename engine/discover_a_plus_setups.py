import sys
sys.path.append('engine')
import os
import pandas as pd
import numpy as np
import datetime
from datetime import time
from nifty_alpha_explorer import load_nifty_fast
from nifty_aligned_ema_atr_sweep import load_stock_data, get_nifty_trend_series

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

def run_rich_backtest(df_stock, nifty_trend_idx, symbol, target_rr=3.0, eod_cutoff_time=time(15, 0)):
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
        day_losses = 0
        
        for i in range(2, n - 2):
            if day_trades >= 2 or day_losses >= 1: break
            if times[i] < time(9, 30) or times[i] > time(14, 15): continue
            
            candle_range = highs[i] - lows[i] + 1e-6
            body_size = abs(closes[i] - opens[i])
            body_ratio = body_size / candle_range
            vol_ratio = vols[i] / (vol_smas[i] + 1e-6)
            
            # --- BUY PULLBACK CANDLE ---
            if (n_trend[i] == 1 and 
                closes[i] > vwap[i] and 
                ema9[i] > ema21[i] and 
                (lows[i] <= ema9[i] or lows[i-1] <= ema9[i-1]) and 
                closes[i] > opens[i] and 
                closes[i] > ema9[i]):
                
                lower_wick = min(opens[i], closes[i]) - lows[i]
                wick_ratio = lower_wick / candle_range
                
                vwap_dist_pct = (closes[i] - vwap[i]) / vwap[i] * 100.0
                touched_vwap = (lows[i] <= vwap[i] or lows[i-1] <= vwap[i-1])
                pinch_vwap_ema = touched_vwap or (vwap_dist_pct <= 0.25)
                
                is_stacked = (closes[i] > ema9[i] > ema21[i] > ema50[i])
                
                if times[i] < time(11, 15):
                    time_cat = "MORNING_PRIME"
                elif times[i] < time(13, 0):
                    time_cat = "MID_DAY"
                else:
                    time_cat = "AFTERNOON"
                
                entry = closes[i]
                raw_sl = min(lows[i], lows[i-1]) - (0.2 * atr[i])
                sl_dist = max(entry - raw_sl, entry * 0.0020)
                sl = entry - sl_dist
                if sl_dist > entry * 0.0070: continue
                tp = entry + (sl_dist * target_rr)
                sl_pct = (sl_dist / entry) * 100.0
                
                final_r = None
                exit_time = None
                exit_reason = None
                
                for m in range(i + 1, n):
                    if lows[m] <= sl:
                        final_r = -1.04
                        exit_time = times[m]
                        exit_reason = 'STOP_LOSS'
                        break
                    if highs[m] >= tp:
                        final_r = round(target_rr - 0.04, 2)
                        exit_time = times[m]
                        exit_reason = 'TARGET'
                        break
                    if times[m] >= eod_cutoff_time:
                        final_r = round((closes[m] - entry)/sl_dist - 0.04, 2)
                        exit_time = times[m]
                        exit_reason = 'EOD_SQUAREOFF_3PM'
                        break
                
                if final_r is not None:
                    trades.append({
                        'Date': dt,
                        'Time': times[i],
                        'Symbol': symbol,
                        'Dir': 'BUY',
                        'R': final_r,
                        'ExitReason': exit_reason,
                        'SL_Pct': sl_pct,
                        'WickRatio': wick_ratio,
                        'BodyRatio': body_ratio,
                        'VolRatio': vol_ratio,
                        'PinchVWAP': pinch_vwap_ema,
                        'StackedEMAs': is_stacked,
                        'TimeCat': time_cat
                    })
                    day_trades += 1
                    if final_r < 0: day_losses += 1

            # --- SELL PULLBACK CANDLE ---
            elif (n_trend[i] == -1 and 
                  closes[i] < vwap[i] and 
                  ema9[i] < ema21[i] and 
                  (highs[i] >= ema9[i] or highs[i-1] >= ema9[i-1]) and 
                  closes[i] < opens[i] and 
                  closes[i] < ema9[i]):
                
                upper_wick = highs[i] - max(opens[i], closes[i])
                wick_ratio = upper_wick / candle_range
                
                vwap_dist_pct = (vwap[i] - closes[i]) / vwap[i] * 100.0
                touched_vwap = (highs[i] >= vwap[i] or highs[i-1] >= vwap[i-1])
                pinch_vwap_ema = touched_vwap or (vwap_dist_pct <= 0.25)
                
                is_stacked = (closes[i] < ema9[i] < ema21[i] < ema50[i])
                
                if times[i] < time(11, 15):
                    time_cat = "MORNING_PRIME"
                elif times[i] < time(13, 0):
                    time_cat = "MID_DAY"
                else:
                    time_cat = "AFTERNOON"
                
                entry = closes[i]
                raw_sl = max(highs[i], highs[i-1]) + (0.2 * atr[i])
                sl_dist = max(raw_sl - entry, entry * 0.0020)
                sl = entry + sl_dist
                if sl_dist > entry * 0.0070: continue
                tp = entry - (sl_dist * target_rr)
                sl_pct = (sl_dist / entry) * 100.0
                
                final_r = None
                exit_time = None
                exit_reason = None
                
                for m in range(i + 1, n):
                    if highs[m] >= sl:
                        final_r = -1.04
                        exit_time = times[m]
                        exit_reason = 'STOP_LOSS'
                        break
                    if lows[m] <= tp:
                        final_r = round(target_rr - 0.04, 2)
                        exit_time = times[m]
                        exit_reason = 'TARGET'
                        break
                    if times[m] >= eod_cutoff_time:
                        final_r = round((entry - closes[m])/sl_dist - 0.04, 2)
                        exit_time = times[m]
                        exit_reason = 'EOD_SQUAREOFF_3PM'
                        break
                
                if final_r is not None:
                    trades.append({
                        'Date': dt,
                        'Time': times[i],
                        'Symbol': symbol,
                        'Dir': 'SELL',
                        'R': final_r,
                        'ExitReason': exit_reason,
                        'SL_Pct': sl_pct,
                        'WickRatio': wick_ratio,
                        'BodyRatio': body_ratio,
                        'VolRatio': vol_ratio,
                        'PinchVWAP': pinch_vwap_ema,
                        'StackedEMAs': is_stacked,
                        'TimeCat': time_cat
                    })
                    day_trades += 1
                    if final_r < 0: day_losses += 1

    return trades

print("Loading Nifty 50 macro trend...")
nifty_1m = load_nifty_fast()
nifty_trend = get_nifty_trend_series(nifty_1m, tf_min=5)

basket = ['RELIANCE', 'MARUTI', 'SUNPHARMA', 'TATAMOTORS', 'TCS', 'TATASTEEL']
all_trades = []

for sym in basket:
    df_1m = load_stock_data(sym)
    df_5m = resample_and_calc_rich_indicators(df_1m, 5)
    t = run_rich_backtest(df_5m, nifty_trend, sym)
    all_trades.extend(t)
    print(f"Loaded {sym}: {len(t)} trades.")

df = pd.DataFrame(all_trades)
df['Win'] = df['R'] > 0

print("="*95)
print("A++ CONFLUENCE FEATURE STUDY (FULL 7,511 TRADES)")
print("="*95)

# 1. Baseline
base_wr = df['Win'].mean() * 100
base_pf = df[df['R']>0]['R'].sum() / abs(df[df['R']<=0]['R'].sum())
print(f"BASELINE ALL TRADES     : {len(df):4d} trades | Win Rate: {base_wr:5.2f}% | PF: {base_pf:.2f} | Net R: {df['R'].sum():7.1f} R")

# 2. Wick Rejection (Absorption Pinbar)
for w_thresh in [0.25, 0.35, 0.45]:
    sub = df[df['WickRatio'] >= w_thresh]
    wr = sub['Win'].mean() * 100
    pf = sub[sub['R']>0]['R'].sum() / abs(sub[sub['R']<=0]['R'].sum())
    print(f"Wick Ratio >= {w_thresh*100:.0f}%      : {len(sub):4d} trades | Win Rate: {wr:5.2f}% | PF: {pf:.2f} | Net R: {sub['R'].sum():7.1f} R")

# 3. Volume Expansion
for v_thresh in [1.0, 1.25, 1.5]:
    sub = df[df['VolRatio'] >= v_thresh]
    wr = sub['Win'].mean() * 100
    pf = sub[sub['R']>0]['R'].sum() / abs(sub[sub['R']<=0]['R'].sum())
    print(f"Volume Ratio >= {v_thresh:.2f}x    : {len(sub):4d} trades | Win Rate: {wr:5.2f}% | PF: {pf:.2f} | Net R: {sub['R'].sum():7.1f} R")

# 4. VWAP Pinch Confluence
sub_pinch = df[df['PinchVWAP'] == True]
wr_p = sub_pinch['Win'].mean() * 100
pf_p = sub_pinch[sub_pinch['R']>0]['R'].sum() / abs(sub_pinch[sub_pinch['R']<=0]['R'].sum())
print(f"VWAP Pinch Confluence   : {len(sub_pinch):4d} trades | Win Rate: {wr_p:5.2f}% | PF: {pf_p:.2f} | Net R: {sub_pinch['R'].sum():7.1f} R")

# 5. Multi-EMA Stacked (EMA 9 > 21 > 50)
sub_stack = df[df['StackedEMAs'] == True]
wr_s = sub_stack['Win'].mean() * 100
pf_s = sub_stack[sub_stack['R']>0]['R'].sum() / abs(sub_stack[sub_stack['R']<=0]['R'].sum())
print(f"Stacked 9/21/50 EMAs    : {len(sub_stack):4d} trades | Win Rate: {wr_s:5.2f}% | PF: {pf_s:.2f} | Net R: {sub_stack['R'].sum():7.1f} R")

# 6. Session Timing Window
for tc in ["MORNING_PRIME", "MID_DAY", "AFTERNOON"]:
    sub_t = df[df['TimeCat'] == tc]
    wr_t = sub_t['Win'].mean() * 100
    pf_t = sub_t[sub_t['R']>0]['R'].sum() / abs(sub_t[sub_t['R']<=0]['R'].sum())
    print(f"Session {tc:15s} : {len(sub_t):4d} trades | Win Rate: {wr_t:5.2f}% | PF: {pf_t:.2f} | Net R: {sub_t['R'].sum():7.1f} R")

df.to_parquet('reports/rich_trades_features.parquet')
print("\nSaved rich trades dataset to reports/rich_trades_features.parquet")
