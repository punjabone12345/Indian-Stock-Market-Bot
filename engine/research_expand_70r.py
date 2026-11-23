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
print("RESEARCH ENGINE: SYSTEMATIC EXPANSION TO ACHIEVE 70+ R / MONTH", flush=True)
print("Auditing Universe Expansion, Wave Extensions & Exact Zerodha/Dhan Taxes", flush=True)
print("="*95, flush=True)

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

def run_rich_backtest(df_stock, nifty_trend_idx, symbol, target_rr=3.0, max_day_trades=3, eod_cutoff_time=time(15, 0)):
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
            if day_trades >= max_day_trades or day_losses >= 1: break
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
                exit_px = None
                
                for m in range(i + 1, n):
                    if lows[m] <= sl:
                        final_r = -1.04
                        exit_px = sl
                        exit_time = times[m]
                        exit_reason = 'STOP_LOSS'
                        break
                    if highs[m] >= tp:
                        final_r = round(target_rr - 0.04, 2)
                        exit_px = tp
                        exit_time = times[m]
                        exit_reason = 'TARGET'
                        break
                    if times[m] >= eod_cutoff_time:
                        final_r = round((closes[m] - entry)/sl_dist - 0.04, 2)
                        exit_px = closes[m]
                        exit_time = times[m]
                        exit_reason = 'EOD_SQUAREOFF_3PM'
                        break
                
                if final_r is not None:
                    day_trades += 1
                    trades.append({
                        'Date': dt,
                        'Time': times[i],
                        'Symbol': symbol,
                        'Dir': 'BUY',
                        'EntryPrice': entry,
                        'ExitPrice': exit_px,
                        'SL_Dist': sl_dist,
                        'SL_Pct': sl_pct,
                        'R': final_r,
                        'ExitReason': exit_reason,
                        'WaveNum': day_trades
                    })
                    if final_r < 0: day_losses += 1

            # --- SELL PULLBACK CANDLE ---
            elif (n_trend[i] == -1 and 
                  closes[i] < vwap[i] and 
                  ema9[i] < ema21[i] and 
                  (highs[i] >= ema9[i] or highs[i-1] >= ema9[i-1]) and 
                  closes[i] < opens[i] and 
                  closes[i] < ema9[i]):
                
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
                exit_px = None
                
                for m in range(i + 1, n):
                    if highs[m] >= sl:
                        final_r = -1.04
                        exit_px = sl
                        exit_time = times[m]
                        exit_reason = 'STOP_LOSS'
                        break
                    if lows[m] <= tp:
                        final_r = round(target_rr - 0.04, 2)
                        exit_px = tp
                        exit_time = times[m]
                        exit_reason = 'TARGET'
                        break
                    if times[m] >= eod_cutoff_time:
                        final_r = round((entry - closes[m])/sl_dist - 0.04, 2)
                        exit_px = closes[m]
                        exit_time = times[m]
                        exit_reason = 'EOD_SQUAREOFF_3PM'
                        break
                
                if final_r is not None:
                    day_trades += 1
                    trades.append({
                        'Date': dt,
                        'Time': times[i],
                        'Symbol': symbol,
                        'Dir': 'SELL',
                        'EntryPrice': entry,
                        'ExitPrice': exit_px,
                        'SL_Dist': sl_dist,
                        'SL_Pct': sl_pct,
                        'R': final_r,
                        'ExitReason': exit_reason,
                        'WaveNum': day_trades
                    })
                    if final_r < 0: day_losses += 1

    return trades

print("Loading Nifty 50 macro trend...", flush=True)
nifty_1m = load_nifty_fast()
nifty_trend = get_nifty_trend_series(nifty_1m, tf_min=5)

files = sorted(glob.glob('data/stocks/*_prev.parquet'))
ALL_SYMBOLS = [os.path.basename(f).replace('_prev.parquet', '') for f in files]
print(f"Total symbols found: {len(ALL_SYMBOLS)}", flush=True)

all_trades = []
for sym in ALL_SYMBOLS:
    df_1m = load_stock_data(sym)
    if df_1m is None or len(df_1m) < 1000:
        continue
    df_5m = resample_and_calc_rich_indicators(df_1m, 5)
    t = run_rich_backtest(df_5m, nifty_trend, sym, target_rr=3.0, max_day_trades=3)
    all_trades.extend(t)
    print(f"Processed {sym:12s}: {len(t)} total raw trades.", flush=True)

df_all = pd.DataFrame(all_trades)
df_all['Date'] = pd.to_datetime(df_all['Date'])
df_all['YM'] = df_all['Date'].dt.to_period('M')
df_all = df_all.sort_values(['Date', 'Time']).reset_index(drop=True)

print(f"\nTotal raw trades generated across all 30 symbols: {len(df_all)}", flush=True)
df_all.to_parquet('reports/all_30_stocks_wave_trades.parquet', index=False)
print("Saved to reports/all_30_stocks_wave_trades.parquet", flush=True)
