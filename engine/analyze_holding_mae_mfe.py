import pandas as pd
import numpy as np
import os
import glob
from datetime import time, datetime

print("Analyzing Holding Times and MAE/MFE on 7,482 Trades...")

df_trades = pd.read_csv('reports/pure_equity_6champion_trades.csv')
print(f"Loaded {len(df_trades):,} trades.")

# 1. Holding Time Stats
print("\n=== HOLDING TIME BREAKDOWN ===")
avg_all = df_trades['HoldingMinutes'].mean()
med_all = df_trades['HoldingMinutes'].median()
print(f"Overall Average Holding Time : {avg_all:.1f} minutes ({avg_all/60:.2f} hours)")
print(f"Overall Median Holding Time  : {med_all:.1f} minutes ({med_all/60:.2f} hours)")

by_reason = df_trades.groupby('ExitReason').agg(
    Count=('HoldingMinutes', 'count'),
    Avg_Minutes=('HoldingMinutes', 'mean'),
    Median_Minutes=('HoldingMinutes', 'median'),
    Min_Minutes=('HoldingMinutes', 'min'),
    Max_Minutes=('HoldingMinutes', 'max')
).reset_index()
print("\nHolding Time by Exit Reason:")
print(by_reason.to_string(index=False))

# Now let's compute MAE (Maximum Adverse Excursion) and MFE (Maximum Favorable Excursion)
# for every trade by checking the candles during the trade lifecycle
from nifty_aligned_ema_atr_sweep import load_stock_data, resample_and_calc_indicators

basket = ['RELIANCE', 'MARUTI', 'SUNPHARMA', 'TATAMOTORS', 'TCS', 'TATASTEEL']
stock_dfs = {}
for sym in basket:
    df_1m = load_stock_data(sym)
    df_5m = resample_and_calc_indicators(df_1m, 5)
    stock_dfs[sym] = df_5m

print("\nCalculating candle-by-candle MAE and MFE for all trades...")

mae_list = []
mfe_list = []

for idx, tr in df_trades.iterrows():
    sym = tr['Symbol']
    dt = pd.to_datetime(tr['Date']).date()
    entry_time = pd.to_datetime(tr['EntryTime']).time()
    exit_time = pd.to_datetime(tr['ExitTime']).time()
    direction = tr['Dir']
    entry_p = tr['EntryPrice']
    sl_p = tr['SL_Price']
    tp_p = tr['TP_Price']
    sl_dist = tr['SL_Dist']
    
    df_s = stock_dfs[sym]
    # Filter to this day
    day_df = df_s[(df_s['Date'] == dt) & (df_s['Time'] >= entry_time) & (df_s['Time'] <= exit_time)]
    
    if len(day_df) <= 1:
        mae_list.append(0.0)
        mfe_list.append(tr['R'])
        continue
        
    highs = day_df['High'].values
    lows = day_df['Low'].values
    
    if direction == 'BUY':
        # Adverse: Lowest low during trade
        lowest_low = np.min(lows)
        # Max adverse distance in R: (entry - lowest_low) / sl_dist
        max_adverse_r = max(0.0, (entry_p - lowest_low) / sl_dist)
        
        # Favorable: Highest high during trade
        highest_high = np.max(highs)
        max_favorable_r = max(0.0, (highest_high - entry_p) / sl_dist)
    else: # SELL
        highest_high = np.max(highs)
        max_adverse_r = max(0.0, (highest_high - entry_p) / sl_dist)
        
        lowest_low = np.min(lows)
        max_favorable_r = max(0.0, (entry_p - lowest_low) / sl_dist)
        
    mae_list.append(round(max_adverse_r, 2))
    mfe_list.append(round(max_favorable_r, 2))

df_trades['MAE_R'] = mae_list
df_trades['MFE_R'] = mfe_list

print("Done calculating MAE & MFE.")

# 2. Near-SL Misses (Heart-Attack Trades that went on to WIN)
# Winning trades where price reached >= 0.70 R, >= 0.80 R, >= 0.90 R towards SL
wins = df_trades[df_trades['ExitReason'] == 'TARGET']
near_sl_70 = wins[wins['MAE_R'] >= 0.70]
near_sl_80 = wins[wins['MAE_R'] >= 0.80]
near_sl_90 = wins[wins['MAE_R'] >= 0.90]

print("\n=== NEAR-SL MISSES (TRADES THAT ALMOST HIT SL BUT HIT FULL TARGET) ===")
print(f"Total Target Wins : {len(wins):,}")
print(f"Wins that dipped >= 70% towards SL (0.70R): {len(near_sl_70):,} ({len(near_sl_70)/len(wins)*100:.1f}%)")
print(f"Wins that dipped >= 80% towards SL (0.80R): {len(near_sl_80):,} ({len(near_sl_80)/len(wins)*100:.1f}%)")
print(f"Wins that dipped >= 90% towards SL (0.90R): {len(near_sl_90):,} ({len(near_sl_90)/len(wins)*100:.1f}%)")
print(f"  -> {len(near_sl_90)} times, price came within 10% of hitting SL and then rallied all the way to 3R TP!")

# 3. Near-TP Misses (Heartbreak Trades that ALMOST hit TP but reversed to SL)
# Losing trades where price reached >= 1.5 R, >= 2.0 R, >= 2.5 R towards TP
losses = df_trades[df_trades['ExitReason'] == 'STOP_LOSS']
near_tp_15 = losses[losses['MFE_R'] >= 1.50]
near_tp_20 = losses[losses['MFE_R'] >= 2.00]
near_tp_25 = losses[losses['MFE_R'] >= 2.50]
near_tp_28 = losses[losses['MFE_R'] >= 2.80]

print("\n=== NEAR-TP MISSES (TRADES THAT ALMOST HIT TP BUT REVERSED ALL THE WAY TO SL) ===")
print(f"Total Stop Loss Hits : {len(losses):,}")
print(f"Losses that were up >= +1.5 R before hitting SL : {len(near_tp_15):,} ({len(near_tp_15)/len(losses)*100:.1f}%)")
print(f"Losses that were up >= +2.0 R before hitting SL : {len(near_tp_20):,} ({len(near_tp_20)/len(losses)*100:.1f}%)")
print(f"Losses that were up >= +2.5 R before hitting SL : {len(near_tp_25):,} ({len(near_tp_25)/len(losses)*100:.1f}%)")
print(f"Losses that were up >= +2.8 R before hitting SL : {len(near_tp_28):,} ({len(near_tp_28)/len(losses)*100:.1f}%)")
print(f"  -> {len(near_tp_25)} times, price went up +2.5R+ (within 15% of 3R TP) and reversed to hit full SL!")

# Save enriched file
df_trades.to_csv('reports/trades_with_mae_mfe.csv', index=False)
print("\nSaved enriched trade analysis to reports/trades_with_mae_mfe.csv")
