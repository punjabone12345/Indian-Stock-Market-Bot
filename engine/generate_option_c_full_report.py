import sys
sys.path.append('engine')
import os
import pandas as pd
import numpy as np
import datetime
from datetime import time
from nifty_alpha_explorer import load_nifty_fast, resample_nifty
from portfolio_synergy import load_bnf
from nifty_aligned_ema_atr_sweep import load_stock_data, get_nifty_trend_series, resample_and_calc_indicators

def backtest_option_c_detailed(df_stock, nifty_trend_idx, symbol, target_rr=3.0):
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

def run_detailed_audit():
    print("Loading Nifty 50...")
    nifty_1m = load_nifty_fast()
    nifty_trend = get_nifty_trend_series(nifty_1m, tf_min=5)
    
    basket = ['RELIANCE', 'MARUTI', 'SUNPHARMA', 'TATAMOTORS', 'TCS', 'BANKNIFTY']
    all_trades = []
    
    for sym in basket:
        print(f"Auditing {sym}...")
        df_1m = load_bnf() if sym == 'BANKNIFTY' else load_stock_data(sym)
        df_5m = resample_and_calc_indicators(df_1m, 5)
        t = backtest_option_c_detailed(df_5m, nifty_trend, sym, target_rr=3.0)
        all_trades.extend(t)
        
    df = pd.DataFrame(all_trades).sort_values(['Date', 'EntryTime']).reset_index(drop=True)
    df['Date'] = pd.to_datetime(df['Date'])
    df['YM'] = df['Date'].dt.to_period('M')
    
    # Save full trade log
    os.makedirs('reports', exist_ok=True)
    df.to_csv('reports/option_c_full_trades.csv', index=False)
    
    # 1. Overall stats
    tot_trades = len(df)
    wins = df[df['R'] > 0]
    losses = df[df['R'] < 0]
    wr = len(wins) / tot_trades * 100
    tot_r = df['R'].sum()
    num_m = df['YM'].nunique()
    r_m = tot_r / num_m
    cum = df['R'].cumsum()
    max_dd = (cum - cum.cummax()).min()
    pf = wins['R'].sum() / abs(losses['R'].sum())
    
    # 2. Streaks calculation
    win_streaks = []
    loss_streaks = []
    cur_win = 0
    cur_loss = 0
    for r in df['R'].values:
        if r > 0:
            cur_win += 1
            if cur_loss > 0:
                loss_streaks.append(cur_loss)
                cur_loss = 0
        else:
            cur_loss += 1
            if cur_win > 0:
                win_streaks.append(cur_win)
                cur_win = 0
    if cur_win > 0: win_streaks.append(cur_win)
    if cur_loss > 0: loss_streaks.append(cur_loss)
    
    max_win_streak = max(win_streaks) if win_streaks else 0
    max_loss_streak = max(loss_streaks) if loss_streaks else 0
    avg_win_streak = np.mean(win_streaks) if win_streaks else 0
    avg_loss_streak = np.mean(loss_streaks) if loss_streaks else 0
    
    # 3. Monthly Breakdown
    monthly_table = df.groupby('YM').agg(
        Trades=('R', 'count'),
        Wins=('R', lambda x: (x > 0).sum()),
        Losses=('R', lambda x: (x < 0).sum()),
        WinRate=('R', lambda x: round((x > 0).mean() * 100, 1)),
        Net_R=('R', lambda x: round(x.sum(), 2))
    ).reset_index()
    monthly_table.to_csv('reports/option_c_monthly_breakdown.csv', index=False)
    
    # 4. SL & Holding Stats
    avg_sl_pct = df['SL_Pct'].mean()
    min_sl_pct = df['SL_Pct'].min()
    max_sl_pct = df['SL_Pct'].max()
    avg_hold_mins = df['HoldingMinutes'].mean()
    exit_reasons = df['ExitReason'].value_counts(normalize=True) * 100
    
    # Print summary
    print("\n" + "="*80)
    print("OPTION C MASTER AUDIT SUMMARY")
    print("="*80)
    print(f"Total Trades: {tot_trades}")
    print(f"Win Rate: {wr:.2f}% | Profit Factor: {pf:.2f}")
    print(f"Total Return: {tot_r:+.2f} R | Average Monthly R: {r_m:+.2f} R/month")
    print(f"Max Drawdown: {max_dd:.2f} R | Calmar Ratio: {(r_m*12)/abs(max_dd):.2f}")
    print(f"Max Consecutive Wins: {max_win_streak} | Max Consecutive Losses: {max_loss_streak}")
    print(f"Avg Consecutive Wins: {avg_win_streak:.1f} | Avg Consecutive Losses: {avg_loss_streak:.1f}")
    print(f"Stop Loss Range: Min {min_sl_pct:.2f}%, Avg {avg_sl_pct:.2f}%, Max {max_sl_pct:.2f}%")
    print(f"Avg Holding Duration: {avg_hold_mins:.1f} minutes ({avg_hold_mins/60:.1f} hours)")
    print("\nExit Distribution:")
    print(exit_reasons.to_string())
    
    print("\nMonthly Performance Head & Tail:")
    print(monthly_table.head())
    print("...")
    print(monthly_table.tail())

if __name__ == '__main__':
    run_detailed_audit()
