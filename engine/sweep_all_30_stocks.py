import sys
sys.path.append('engine')
import os
import pandas as pd
import numpy as np
import datetime
from datetime import time
from nifty_alpha_explorer import load_nifty_fast
from nifty_aligned_ema_atr_sweep import load_stock_data, get_nifty_trend_series, resample_and_calc_indicators

# Load Nifty Macro Trend (5m)
print("Loading Nifty 50 macro trend...")
nifty_1m = load_nifty_fast()
nifty_trend = get_nifty_trend_series(nifty_1m, tf_min=5)

# Discover all symbols available in data/stocks
stock_files = os.listdir('data/stocks')
symbols = sorted(list(set([f.split('_')[0] for f in stock_files])))
print(f"Found {len(symbols)} stocks to audit: {symbols}")

def backtest_single_stock(df_stock, nifty_trend_idx, symbol, target_rr=3.0):
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
        times = day_df['Time'].values
        ema9 = day_df['EMA9'].values
        ema21 = day_df['EMA21'].values
        vwap = day_df['VWAP'].values
        atr = day_df['ATR'].values
        n_trend = day_df['Nifty_Trend'].values
        
        day_trades = 0
        day_losses = 0
        
        for i in range(2, n - 2):
            if day_trades >= 2 or day_losses >= 1: break
            if times[i] < time(9, 30) or times[i] > time(14, 15): continue
            
            # --- BUY PULLBACK LOGIC ---
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
                bars_held = 0
                exit_reason = None
                
                for m in range(i + 1, n):
                    bars_held += 1
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
                    if times[m] >= time(15, 15):
                        final_r = round((closes[m] - entry)/sl_dist - 0.04, 2)
                        exit_time = times[m]
                        exit_reason = 'EOD_SQUAREOFF'
                        break
                
                if final_r is not None:
                    trades.append({
                        'Date': dt,
                        'EntryTime': times[i],
                        'ExitTime': exit_time,
                        'Symbol': symbol,
                        'Dir': 'BUY',
                        'EntryPrice': entry,
                        'SL_Price': sl,
                        'TP_Price': tp,
                        'SL_Dist': sl_dist,
                        'SL_Pct': sl_pct,
                        'BarsHeld': bars_held,
                        'HoldingMinutes': bars_held * 5,
                        'ExitReason': exit_reason,
                        'R': final_r
                    })
                    day_trades += 1
                    if final_r < 0: day_losses += 1

            # --- SELL PULLBACK LOGIC ---
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
                bars_held = 0
                exit_reason = None
                
                for m in range(i + 1, n):
                    bars_held += 1
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
                    if times[m] >= time(15, 15):
                        final_r = round((entry - closes[m])/sl_dist - 0.04, 2)
                        exit_time = times[m]
                        exit_reason = 'EOD_SQUAREOFF'
                        break
                
                if final_r is not None:
                    trades.append({
                        'Date': dt,
                        'EntryTime': times[i],
                        'ExitTime': exit_time,
                        'Symbol': symbol,
                        'Dir': 'SELL',
                        'EntryPrice': entry,
                        'SL_Price': sl,
                        'TP_Price': tp,
                        'SL_Dist': sl_dist,
                        'SL_Pct': sl_pct,
                        'BarsHeld': bars_held,
                        'HoldingMinutes': bars_held * 5,
                        'ExitReason': exit_reason,
                        'R': final_r
                    })
                    day_trades += 1
                    if final_r < 0: day_losses += 1
                    
    return trades

results = []
all_stock_trades = {}

for sym in symbols:
    print(f"Auditing {sym}...")
    df_1m = load_stock_data(sym)
    if df_1m is None or len(df_1m) == 0:
        continue
    df_5m = resample_and_calc_indicators(df_1m, 5)
    t = backtest_single_stock(df_5m, nifty_trend, sym, target_rr=3.0)
    all_stock_trades[sym] = t
    
    if len(t) == 0:
        continue
        
    df_t = pd.DataFrame(t)
    df_t['Date'] = pd.to_datetime(df_t['Date'])
    num_m = df_t['Date'].dt.to_period('M').nunique()
    if num_m == 0: num_m = 49
    
    tot_r = df_t['R'].sum()
    r_m = tot_r / num_m
    wr = (df_t['R'] > 0).mean() * 100
    cum = df_t['R'].cumsum()
    max_dd = (cum - cum.cummax()).min()
    wins = df_t[df_t['R'] > 0]['R'].sum()
    losses = abs(df_t[df_t['R'] < 0]['R'].sum())
    pf = wins / losses if losses > 0 else np.nan
    calmar = (r_m * 12) / abs(max_dd) if max_dd < 0 else np.nan
    avg_price = df_t['EntryPrice'].mean()
    avg_sl_pct = df_t['SL_Pct'].mean()
    avg_sl_pts = df_t['SL_Dist'].mean()
    
    results.append({
        'Symbol': sym,
        'Trades': len(df_t),
        'WinRate': round(wr, 2),
        'Total_Net_R': round(tot_r, 1),
        'Monthly_R': round(r_m, 2),
        'Max_DD': round(max_dd, 1),
        'ProfitFactor': round(pf, 2),
        'Calmar': round(calmar, 2),
        'Avg_Price': round(avg_price, 1),
        'Avg_SL_Pct': round(avg_sl_pct, 2),
        'Avg_SL_Pts': round(avg_sl_pts, 2)
    })

df_res = pd.DataFrame(results).sort_values('Total_Net_R', ascending=False).reset_index(drop=True)
os.makedirs('reports', exist_ok=True)
df_res.to_csv('reports/all_30_stocks_ranked.csv', index=False)

print("\n" + "="*95)
print("             ALL 30 NSE STOCKS RANKED BY TOTAL NET R (OCT 2022 - OCT 2026)")
print("="*95)
print(df_res.to_string())
