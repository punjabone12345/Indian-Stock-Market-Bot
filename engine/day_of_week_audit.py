import sys
sys.path.append('engine')
import os
import pandas as pd
import numpy as np
import datetime
from datetime import time
from nifty_alpha_explorer import load_nifty_fast
from nifty_aligned_ema_atr_sweep import load_stock_data, get_nifty_trend_series, resample_and_calc_indicators

def backtest_equity_with_eod(df_stock, nifty_trend_idx, symbol, target_rr=3.0, eod_cutoff_time=time(15, 0)):
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
                exit_price = None
                
                for m in range(i + 1, n):
                    bars_held += 1
                    if lows[m] <= sl:
                        final_r = -1.04
                        exit_time = times[m]
                        exit_reason = 'STOP_LOSS'
                        exit_price = sl
                        break
                    if highs[m] >= tp:
                        final_r = round(target_rr - 0.04, 2)
                        exit_time = times[m]
                        exit_reason = 'TARGET'
                        exit_price = tp
                        break
                    if times[m] >= eod_cutoff_time:
                        final_r = round((closes[m] - entry)/sl_dist - 0.04, 2)
                        exit_time = times[m]
                        exit_reason = 'EOD_SQUAREOFF_3PM'
                        exit_price = closes[m]
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
                        'ExitPrice': exit_price,
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
                exit_price = None
                
                for m in range(i + 1, n):
                    bars_held += 1
                    if highs[m] >= sl:
                        final_r = -1.04
                        exit_time = times[m]
                        exit_reason = 'STOP_LOSS'
                        exit_price = sl
                        break
                    if lows[m] <= tp:
                        final_r = round(target_rr - 0.04, 2)
                        exit_time = times[m]
                        exit_reason = 'TARGET'
                        exit_price = tp
                        break
                    if times[m] >= eod_cutoff_time:
                        final_r = round((entry - closes[m])/sl_dist - 0.04, 2)
                        exit_time = times[m]
                        exit_reason = 'EOD_SQUAREOFF_3PM'
                        exit_price = closes[m]
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
                        'ExitPrice': exit_price,
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

nifty_1m = load_nifty_fast()
nifty_trend = get_nifty_trend_series(nifty_1m, tf_min=5)

basket = ['RELIANCE', 'MARUTI', 'SUNPHARMA', 'TATAMOTORS', 'TCS', 'TATASTEEL']
all_trades = []

for sym in basket:
    df_1m = load_stock_data(sym)
    df_5m = resample_and_calc_indicators(df_1m, 5)
    t = backtest_equity_with_eod(df_5m, nifty_trend, sym, target_rr=3.0, eod_cutoff_time=time(15, 0))
    all_trades.extend(t)

df = pd.DataFrame(all_trades).sort_values(['Date', 'EntryTime']).reset_index(drop=True)
df['Date'] = pd.to_datetime(df['Date'])
df['DayName'] = df['Date'].dt.day_name()
days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']

print("="*95)
print("COMPREHENSIVE DAY-OF-WEEK QUANTITATIVE PERFORMANCE (3:00 PM CUTOFF)")
print("="*95)

day_rows = []
for day in days_order:
    sub = df[df['DayName'] == day]
    tot = len(sub)
    if tot == 0: continue
    
    wins = sub[sub['R'] > 0]
    losses = sub[sub['R'] <= 0]
    
    wr = len(wins) / tot * 100
    tot_r = sub['R'].sum()
    avg_r = sub['R'].mean()
    
    gw = wins['R'].sum()
    gl = abs(losses['R'].sum())
    pf = gw / gl if gl > 0 else 0
    
    # Portfolio equity curve for that specific day of week across the 4 years
    daily_day_r = sub.groupby('Date')['R'].sum()
    cum_day = daily_day_r.cumsum()
    dd_day = (cum_day - cum_day.cummax()).min()
    
    # Exit reasons
    tgt = len(sub[sub['ExitReason'] == 'TARGET'])
    sl = len(sub[sub['ExitReason'] == 'STOP_LOSS'])
    eod = len(sub[sub['ExitReason'] == 'EOD_SQUAREOFF_3PM'])
    
    avg_win_r = wins['R'].mean() if len(wins) > 0 else 0
    avg_loss_r = losses['R'].mean() if len(losses) > 0 else 0
    
    day_rows.append({
        'Day': day,
        'Trades': tot,
        'Wins': len(wins),
        'Losses': len(losses),
        'WinRate': round(wr, 2),
        'Net_R': round(tot_r, 1),
        'Avg_R': round(avg_r, 3),
        'PF': round(pf, 2),
        'Max_DD_R': round(dd_day, 1),
        'Target_Hit': tgt,
        'SL_Hit': sl,
        'EOD_3PM': eod,
        'Avg_Win_R': round(avg_win_r, 2),
        'Avg_Loss_R': round(avg_loss_r, 2)
    })

res_table = pd.DataFrame(day_rows)
print(res_table.to_string(index=False))

print("\n" + "="*95)
print("DAY-OF-WEEK BREAKDOWN BY STOCK (TOTAL NET R)")
print("="*95)
p_r = df.pivot_table(index='DayName', columns='Symbol', values='R', aggfunc='sum').reindex(days_order)
print(p_r.round(1).to_string())

print("\n" + "="*95)
print("DAY-OF-WEEK BREAKDOWN BY STOCK (WIN RATE %)")
print("="*95)
p_wr = df.pivot_table(index='DayName', columns='Symbol', values='R', aggfunc=lambda x: (x > 0).mean() * 100).reindex(days_order)
print(p_wr.round(1).to_string())

print("\n" + "="*95)
print("DAY-OF-WEEK AVERAGE TRADES PER DAY")
print("="*95)
for day in days_order:
    sub = df[df['DayName'] == day]
    unique_dates = sub['Date'].nunique()
    tot_trades = len(sub)
    print(f"{day:10s}: {tot_trades} trades across {unique_dates} sessions ({tot_trades/unique_dates:.1f} trades/day)")
