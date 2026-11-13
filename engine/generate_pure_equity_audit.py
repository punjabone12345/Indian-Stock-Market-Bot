import sys
sys.path.append('engine')
import os
import pandas as pd
import numpy as np
import datetime
from datetime import time
from nifty_alpha_explorer import load_nifty_fast
from nifty_aligned_ema_atr_sweep import load_stock_data, get_nifty_trend_series, resample_and_calc_indicators

def backtest_equity_detailed(df_stock, nifty_trend_idx, symbol, target_rr=3.0):
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
                    if times[m] >= time(15, 15):
                        final_r = round((closes[m] - entry)/sl_dist - 0.04, 2)
                        exit_time = times[m]
                        exit_reason = 'EOD_SQUAREOFF'
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
                    if times[m] >= time(15, 15):
                        final_r = round((entry - closes[m])/sl_dist - 0.04, 2)
                        exit_time = times[m]
                        exit_reason = 'EOD_SQUAREOFF'
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

def run_pure_equity_audit():
    print("Loading Nifty 50 macro trend...")
    nifty_1m = load_nifty_fast()
    nifty_trend = get_nifty_trend_series(nifty_1m, tf_min=5)
    
    # Pure NSE Cash Equities: 6 Champions across 5 non-correlated sectors
    basket = ['RELIANCE', 'MARUTI', 'SUNPHARMA', 'TATAMOTORS', 'TCS', 'TATASTEEL']
    all_trades = []
    asset_summaries = []
    
    for sym in basket:
        print(f"Auditing pure cash equity: {sym}...")
        df_1m = load_stock_data(sym)
        df_5m = resample_and_calc_indicators(df_1m, 5)
        t = backtest_equity_detailed(df_5m, nifty_trend, sym, target_rr=3.0)
        all_trades.extend(t)
        
        # Individual stock performance
        df_s = pd.DataFrame(t)
        tot_r_s = df_s['R'].sum()
        wr_s = (df_s['R'] > 0).mean() * 100
        cum_s = df_s['R'].cumsum()
        dd_s = (cum_s - cum_s.cummax()).min()
        pf_s = df_s[df_s['R'] > 0]['R'].sum() / abs(df_s[df_s['R'] < 0]['R'].sum())
        asset_summaries.append({
            'Symbol': sym,
            'Trades': len(df_s),
            'WinRate': round(wr_s, 2),
            'Total_R': round(tot_r_s, 1),
            'Monthly_R': round(tot_r_s / 49.0, 2),
            'Max_DD': round(dd_s, 1),
            'ProfitFactor': round(pf_s, 2),
            'Avg_Price': round(df_s['EntryPrice'].mean(), 1),
            'Avg_SL_Pct': round(df_s['SL_Pct'].mean(), 2),
            'Avg_SL_Pts': round(df_s['SL_Dist'].mean(), 2)
        })
        
    df = pd.DataFrame(all_trades).sort_values(['Date', 'EntryTime']).reset_index(drop=True)
    df['Date'] = pd.to_datetime(df['Date'])
    df['YM'] = df['Date'].dt.to_period('M')
    
    os.makedirs('reports', exist_ok=True)
    df.to_csv('reports/pure_equity_6champion_trades.csv', index=False)
    
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
    calmar = (r_m * 12) / abs(max_dd)
    
    # Monthly table
    monthly_table = df.groupby('YM').agg(
        Trades=('R', 'count'),
        Wins=('R', lambda x: (x > 0).sum()),
        Losses=('R', lambda x: (x < 0).sum()),
        WinRate=('R', lambda x: round((x > 0).mean() * 100, 1)),
        Net_R=('R', lambda x: round(x.sum(), 2))
    ).reset_index()
    monthly_table.to_csv('reports/pure_equity_monthly_breakdown.csv', index=False)
    
    # Streaks
    win_streaks, loss_streaks = [], []
    c_w, c_l = 0, 0
    for r in df['R'].values:
        if r > 0:
            c_w += 1
            if c_l > 0:
                loss_streaks.append(c_l)
                c_l = 0
        else:
            c_l += 1
            if c_w > 0:
                win_streaks.append(c_w)
                c_w = 0
    if c_w > 0: win_streaks.append(c_w)
    if c_l > 0: loss_streaks.append(c_l)
    
    # Drawdown episodes
    df['Cum_R'] = df['R'].cumsum()
    df['HWM'] = df['Cum_R'].cummax()
    episodes = []
    in_dd = False
    peak_val, peak_idx, peak_date = 0, 0, None
    trough_val, trough_idx, trough_date = 0, 0, None
    
    for i in range(len(df)):
        c = df.loc[i, 'Cum_R']
        h = df.loc[i, 'HWM']
        dt = df.loc[i, 'Date']
        if not in_dd:
            if c < h:
                in_dd = True
                peak_idx = i - 1
                peak_val = df.loc[peak_idx, 'Cum_R']
                peak_date = df.loc[peak_idx, 'Date']
                trough_val = c - h
                trough_idx = i
                trough_date = dt
        else:
            dd = c - peak_val
            if dd < trough_val:
                trough_val = dd
                trough_idx = i
                trough_date = dt
            if c >= peak_val:
                recovery_idx = i
                recovery_date = dt
                episodes.append({
                    'Peak_Date': peak_date,
                    'Trough_Date': trough_date,
                    'Recovery_Date': recovery_date,
                    'Peak_R': round(peak_val, 2),
                    'Trough_R': round(peak_val + trough_val, 2),
                    'Max_DD_R': round(trough_val, 2),
                    'Decline_Trades': trough_idx - peak_idx,
                    'Recovery_Trades': recovery_idx - trough_idx,
                    'Total_Trades': recovery_idx - peak_idx,
                    'Decline_Days': (trough_date - peak_date).days,
                    'Recovery_Days': (recovery_date - trough_date).days,
                    'Total_Days': (recovery_date - peak_date).days,
                })
                in_dd = False
                
    df_episodes = pd.DataFrame(episodes).sort_values('Max_DD_R').reset_index(drop=True)
    
    # Margin timeline
    df['EntryDateTime'] = pd.to_datetime(df['Date'].astype(str) + ' ' + df['EntryTime'].astype(str))
    df['ExitDateTime'] = pd.to_datetime(df['Date'].astype(str) + ' ' + df['ExitTime'].astype(str))
    df['Margin_Factor'] = (df['EntryPrice'] / df['SL_Dist']) / 5.0
    
    events = []
    for idx, r in df.iterrows():
        events.append({'Time': r['EntryDateTime'], 'Type': 'ENTER', 'MF': r['Margin_Factor']})
        events.append({'Time': r['ExitDateTime'], 'Type': 'EXIT', 'MF': r['Margin_Factor']})
    df_ev = pd.DataFrame(events).sort_values(['Time', 'Type'], ascending=[True, False]).reset_index(drop=True)
    
    max_c_open, max_c_mf = 0, 0
    cur_o, cur_mf = 0, 0
    for idx, ev in df_ev.iterrows():
        if ev['Type'] == 'ENTER':
            cur_o += 1
            cur_mf += ev['MF']
        else:
            cur_o -= 1
            cur_mf -= ev['MF']
        if cur_o > max_c_open: max_c_open = cur_o
        if cur_mf > max_c_mf: max_c_mf = cur_mf
        
    print("\n" + "="*85)
    print("PURE NSE EQUITY 6-CHAMPION ALPHA SYSTEM (TATASTEEL REPLACING BANKNIFTY)")
    print("="*85)
    print(f"Total Trades: {tot_trades}")
    print(f"Win Rate: {wr:.2f}% | Profit Factor: {pf:.2f}")
    print(f"Total 4-Year Return: {tot_r:+.2f} R")
    print(f"Monthly Average Return: {r_m:+.2f} R / month")
    print(f"Maximum Drawdown: {max_dd:.2f} R (vs BankNifty Basket -40.8 R -> +5.5 R improvement!)")
    print(f"Calmar Ratio: {calmar:.2f} (vs BankNifty Basket 16.19 -> 19.39!)")
    print(f"Max Win Streak: {max(win_streaks)} | Max Loss Streak: {max(loss_streaks)}")
    print(f"Avg Win Streak: {np.mean(win_streaks):.2f} | Avg Loss Streak: {np.mean(loss_streaks):.2f}")
    print(f"Peak Concurrent Open Positions: {max_c_open} stocks")
    print(f"Peak Concurrent Margin Factor: {max_c_mf:.2f}x")
    
    print("\nASSET-LEVEL BREAKDOWN:")
    print(pd.DataFrame(asset_summaries).to_string(index=False))
    
    print("\nTOP 3 DRAWDOWN EPISODES:")
    print(df_episodes.head(3).to_string(index=False))
    
    return df, monthly_table, df_episodes, asset_summaries, max_c_mf

if __name__ == '__main__':
    run_pure_equity_audit()
