import pandas as pd
import numpy as np

df = pd.read_parquet('reports/rich_trades_features.parquet')
df['Date'] = pd.to_datetime(df['Date'])
df['DayName'] = df['Date'].dt.day_name()
df['YM'] = df['Date'].dt.to_period('M')
df = df.sort_values(['Date', 'Time']).reset_index(drop=True)
df['Stock_Day_Trade_Num'] = df.groupby(['Date', 'Symbol']).cumcount() + 1
df['Win'] = df['R'] > 0

# Filter for the Confirmed Wave 2 A++ Setup
t2 = df[df['Stock_Day_Trade_Num'] == 2].copy()

print("="*95)
print("A++ SETUP: CONFIRMED WAVE 2 EXPANSION (FULL 4-YEAR AUDIT)")
print("="*95)

tot_trades = len(t2)
wins = t2[t2['R'] > 0]
losses = t2[t2['R'] <= 0]
wr = len(wins) / tot_trades * 100
tot_r = t2['R'].sum()
avg_r = t2['R'].mean()
gw = wins['R'].sum()
gl = abs(losses['R'].sum())
pf = gw / gl if gl > 0 else 99.0

cum = t2['R'].cumsum()
peak = cum.cummax()
dd = cum - peak
max_dd = dd.min()

num_months = t2['YM'].nunique()
r_per_mo = tot_r / num_months
calmar = (r_per_mo * 12) / abs(max_dd)

w_flags = (t2['R'] > 0).astype(int).values
m_win, m_loss, c_w, c_l = 0, 0, 0, 0
for flag in w_flags:
    if flag == 1:
        c_w += 1; c_l = 0
        if c_w > m_win: m_win = c_w
    else:
        c_l += 1; c_w = 0
        if c_l > m_loss: m_loss = c_l

print(f"Total A++ Trades        : {tot_trades}")
print(f"Total Wins / Losses     : {len(wins)} Wins / {len(losses)} Losses")
print(f"Win Rate                : {wr:.2f}%")
print(f"Total 4-Year Net Return : +{tot_r:.1f} R")
print(f"Monthly Net Return      : +{r_per_mo:.2f} R / month")
print(f"Expectancy (Avg R/Trade): +{avg_r:.3f} R")
print(f"Profit Factor           : {pf:.2f}")
print(f"Maximum Drawdown        : {max_dd:.1f} R")
print(f"Calmar Ratio            : {calmar:.2f}")
print(f"Max Consecutive Wins    : {m_win} wins in a row")
print(f"Max Consecutive Losses  : {m_loss} losses in a row")
print(f"Avg Win R               : +{wins['R'].mean():.2f} R")
print(f"Avg Loss R              : {losses['R'].mean():.2f} R")

# Exit reason
print("\nExit Reason Breakdown:")
print(t2['ExitReason'].value_counts())

# Per Instrument breakdown
print("\n" + "="*95)
print("A++ CONFIRMED WAVE 2 PERFORMANCE BY INSTRUMENT")
print("="*95)
sym_rows = []
for sym, grp in t2.groupby('Symbol'):
    n = len(grp)
    w = grp[grp['R'] > 0]
    l = grp[grp['R'] <= 0]
    sym_wr = len(w) / n * 100
    sym_tot_r = grp['R'].sum()
    sym_avg_r = grp['R'].mean()
    sym_gw = w['R'].sum()
    sym_gl = abs(l['R'].sum())
    sym_pf = sym_gw / sym_gl if sym_gl > 0 else 99.0
    
    sym_cum = grp['R'].cumsum()
    sym_dd = (sym_cum - sym_cum.cummax()).min()
    
    # streaks
    w_flags = (grp['R'] > 0).astype(int).values
    mw, ml, cw, cl = 0, 0, 0, 0
    for flag in w_flags:
        if flag == 1:
            cw += 1; cl = 0
            if cw > mw: mw = cw
        else:
            cl += 1; cw = 0
            if cl > ml: ml = cl
            
    sym_rows.append({
        'Symbol': sym,
        'Trades': n,
        'Wins': len(w),
        'Losses': len(l),
        'WinRate': round(sym_wr, 2),
        'Net_R': round(sym_tot_r, 1),
        'Monthly_R': round(sym_tot_r / num_months, 2),
        'PF': round(sym_pf, 2),
        'Max_DD': round(sym_dd, 1),
        'Max_Win_Streak': mw,
        'Max_Loss_Streak': ml,
        'Avg_Win_R': round(w['R'].mean(), 2),
        'Avg_Loss_R': round(l['R'].mean(), 2)
    })
print(pd.DataFrame(sym_rows).to_string(index=False))

# Day of week breakdown
print("\n" + "="*95)
print("A++ CONFIRMED WAVE 2 PERFORMANCE BY DAY OF WEEK")
print("="*95)
days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
day_rows = []
for day in days_order:
    sub = t2[t2['DayName'] == day]
    n = len(sub)
    if n == 0: continue
    w = sub[sub['R'] > 0]
    l = sub[sub['R'] <= 0]
    d_wr = len(w) / n * 100
    d_tot_r = sub['R'].sum()
    d_avg_r = sub['R'].mean()
    d_gw = w['R'].sum()
    d_gl = abs(l['R'].sum())
    d_pf = d_gw / d_gl if d_gl > 0 else 99.0
    
    d_cum = sub['R'].cumsum()
    d_dd = (d_cum - d_cum.cummax()).min()
    
    w_flags = (sub['R'] > 0).astype(int).values
    mw, ml, cw, cl = 0, 0, 0, 0
    for flag in w_flags:
        if flag == 1:
            cw += 1; cl = 0
            if cw > mw: mw = cw
        else:
            cl += 1; cw = 0
            if cl > ml: ml = cl
            
    day_rows.append({
        'Day': day,
        'Trades': n,
        'Wins': len(w),
        'Losses': len(l),
        'WinRate': round(d_wr, 2),
        'Net_R': round(d_tot_r, 1),
        'Avg_R': round(d_avg_r, 3),
        'PF': round(d_pf, 2),
        'Max_DD': round(d_dd, 1),
        'Max_Win_Streak': mw,
        'Max_Loss_Streak': ml,
        'Target_Hit': len(sub[sub['ExitReason'] == 'TARGET']),
        'SL_Hit': len(sub[sub['ExitReason'] == 'STOP_LOSS']),
        'EOD_3PM': len(sub[sub['ExitReason'] == 'EOD_SQUAREOFF_3PM'])
    })
print(pd.DataFrame(day_rows).to_string(index=False))

# Monthly consistency
monthly_r = t2.groupby('YM')['R'].sum()
pos_m = (monthly_r > 0).sum()
tot_m = len(monthly_r)
print("\n" + "="*95)
print("MONTHLY CONSISTENCY")
print("="*95)
print(f"Total Months            : {tot_m}")
print(f"Profitable Months       : {pos_m} / {tot_m} ({pos_m/tot_m*100:.1f}%)")
print(f"Best Month              : {monthly_r.idxmax()} (+{monthly_r.max():.1f} R)")
print(f"Worst Month             : {monthly_r.idxmin()} ({monthly_r.min():.1f} R)")

# Save to reports
t2.to_csv('reports/a_plus_wave2_trades.csv', index=False)
print("\nSaved to reports/a_plus_wave2_trades.csv")
