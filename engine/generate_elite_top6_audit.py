import sys
sys.path.append('engine')
import os
import pandas as pd
import numpy as np
from datetime import time
from nifty_alpha_explorer import load_nifty_fast
from nifty_aligned_ema_atr_sweep import load_stock_data, get_nifty_trend_series, resample_and_calc_indicators
from generate_pure_equity_audit import backtest_equity_detailed

print("Loading Nifty 50 macro trend...")
nifty_1m = load_nifty_fast()
nifty_trend = get_nifty_trend_series(nifty_1m, tf_min=5)

# The Top 6 Crowned Champions
basket = ['RELIANCE', 'ITC', 'MARUTI', 'TATASTEEL', 'SUNPHARMA', 'INFY']
all_trades = []
asset_summaries = []

for sym in basket:
    print(f"Auditing Crown Champion: {sym}...")
    df_1m = load_stock_data(sym)
    df_5m = resample_and_calc_indicators(df_1m, 5)
    t = backtest_equity_detailed(df_5m, nifty_trend, sym, target_rr=3.0)
    all_trades.extend(t)
    
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
df.to_csv('reports/elite_top6_trades.csv', index=False)

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
monthly_table.to_csv('reports/elite_top6_monthly_breakdown.csv', index=False)

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

print("\n" + "="*85)
print("ELITE TOP 6 CROWN CHAMPIONS SYSTEM AUDIT")
print("="*85)
print(f"Total Trades: {tot_trades}")
print(f"Win Rate: {wr:.2f}% | Profit Factor: {pf:.2f}")
print(f"Total 4-Year Return: {tot_r:+.2f} R")
print(f"Monthly Average Return: {r_m:+.2f} R / month")
print(f"Maximum Drawdown: {max_dd:.2f} R")
print(f"Calmar Ratio: {calmar:.2f}")
print(f"Max Win Streak: {max(win_streaks)} | Max Loss Streak: {max(loss_streaks)}")
print(f"Avg Win Streak: {np.mean(win_streaks):.2f} | Avg Loss Streak: {np.mean(loss_streaks):.2f}")

print("\nASSET-LEVEL BREAKDOWN:")
print(pd.DataFrame(asset_summaries).to_string(index=False))

print("\nTOP 3 DRAWDOWN EPISODES:")
print(df_episodes.head(3).to_string(index=False))
