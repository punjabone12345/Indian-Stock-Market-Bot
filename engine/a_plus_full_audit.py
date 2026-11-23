import pandas as pd
import numpy as np

df = pd.read_parquet('reports/rich_trades_features.parquet')
df['Date'] = pd.to_datetime(df['Date'])
df['DayName'] = df['Date'].dt.day_name()
df['YM'] = df['Date'].dt.to_period('M')
df['Win'] = df['R'] > 0

# Define A++ boolean masks per instrument
def get_a_plus_mask(row):
    sym = row['Symbol']
    vol = row['VolRatio']
    body = row['BodyRatio']
    time_cat = row['TimeCat']
    stacked = row['StackedEMAs']
    
    if sym == 'RELIANCE':
        # Institutional Expansion: Vol >= 1.20x & Body >= 55%
        return (vol >= 1.20) and (body >= 0.55)
    elif sym == 'MARUTI':
        # Morning Prime Momentum: Morning Prime & Vol >= 1.25x
        return (time_cat == 'MORNING_PRIME') and (vol >= 1.25)
    elif sym == 'SUNPHARMA':
        # Mid-Day Defense Trend: Mid-Day & Vol >= 1.0x
        return (time_cat == 'MID_DAY') and (vol >= 1.0)
    elif sym == 'TATAMOTORS':
        # Mid-Day European Cross: Mid-Day & Vol >= 1.0x
        return (time_cat == 'MID_DAY') and (vol >= 1.0)
    elif sym == 'TCS':
        # Triple EMA Power Stack: Morning Prime & Stacked EMAs & Vol >= 1.20x
        return (time_cat == 'MORNING_PRIME') and stacked and (vol >= 1.20)
    elif sym == 'TATASTEEL':
        # Mid-Day Metals Trend: Mid-Day & Stacked EMAs & Body >= 50%
        return (time_cat == 'MID_DAY') and stacked and (body >= 0.50)
    return False

df['Is_APlus'] = df.apply(get_a_plus_mask, axis=1)
a_df = df[df['Is_APlus']].sort_values(['Date', 'Time']).reset_index(drop=True)

print("="*95)
print("A++ SETUPS MASTER AUDIT (4-YEAR EMPIRICAL DATA)")
print("="*95)

tot_trades = len(a_df)
wins = a_df[a_df['R'] > 0]
losses = a_df[a_df['R'] <= 0]
wr = len(wins) / tot_trades * 100
tot_r = a_df['R'].sum()
avg_r = a_df['R'].mean()

gw = wins['R'].sum()
gl = abs(losses['R'].sum())
pf = gw / gl if gl > 0 else 99.0

# Streaks
win_flags = (a_df['R'] > 0).astype(int).values
max_win_streak = 0
max_loss_streak = 0
cur_win = 0
cur_loss = 0

for w in win_flags:
    if w == 1:
        cur_win += 1
        cur_loss = 0
        if cur_win > max_win_streak: max_win_streak = cur_win
    else:
        cur_loss += 1
        cur_win = 0
        if cur_loss > max_loss_streak: max_loss_streak = cur_loss

# Drawdown
cum_r = a_df['R'].cumsum()
peak = cum_r.cummax()
dd = cum_r - peak
max_dd = dd.min()

num_months = a_df['YM'].nunique()
r_per_month = tot_r / num_months
calmar = (r_per_month * 12) / abs(max_dd)

avg_win = wins['R'].mean()
avg_loss = losses['R'].mean()

print(f"Total A++ Trades        : {tot_trades}")
print(f"Total Wins / Losses     : {len(wins)} Wins / {len(losses)} Losses")
print(f"Win Rate                : {wr:.2f}%")
print(f"Total 4-Year Net Return : +{tot_r:.1f} R")
print(f"Average Monthly Return  : +{r_per_month:.2f} R / month")
print(f"Expectancy (Avg R/Trade): +{avg_r:.3f} R")
print(f"Profit Factor           : {pf:.2f}")
print(f"Max Drawdown            : {max_dd:.1f} R")
print(f"Calmar Ratio            : {calmar:.2f}")
print(f"Max Win Streak          : {max_win_streak} consecutive wins")
print(f"Max Loss Streak         : {max_loss_streak} consecutive losses")
print(f"Avg Win R               : +{avg_win:.2f} R")
print(f"Avg Loss R              : {avg_loss:.2f} R")

# Exit reasons
print("\nExit Reason Breakdown:")
print(a_df['ExitReason'].value_counts())

# Instrument-by-instrument breakdown
print("\n" + "="*95)
print("A++ PERFORMANCE BY INSTRUMENT")
print("="*95)
sym_rows = []
for sym, grp in a_df.groupby('Symbol'):
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
    
    # instrument streaks
    w_flags = (grp['R'] > 0).astype(int).values
    m_win, m_loss, c_w, c_l = 0, 0, 0, 0
    for flag in w_flags:
        if flag == 1:
            c_w += 1; c_l = 0
            if c_w > m_win: m_win = c_w
        else:
            c_l += 1; c_w = 0
            if c_l > m_loss: m_loss = c_l
            
    sym_rows.append({
        'Symbol': sym,
        'Trades': n,
        'Wins': len(w),
        'Losses': len(l),
        'WinRate': round(sym_wr, 2),
        'Net_R': round(sym_tot_r, 1),
        'Avg_R': round(sym_avg_r, 3),
        'PF': round(sym_pf, 2),
        'Max_DD': round(sym_dd, 1),
        'Max_Win_Streak': m_win,
        'Max_Loss_Streak': m_loss,
        'Avg_Win_R': round(w['R'].mean(), 2),
        'Avg_Loss_R': round(l['R'].mean(), 2)
    })
print(pd.DataFrame(sym_rows).to_string(index=False))

# Day of week breakdown
print("\n" + "="*95)
print("A++ PERFORMANCE BY DAY OF WEEK")
print("="*95)
days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
day_rows = []
for day in days_order:
    sub = a_df[a_df['DayName'] == day]
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
    
    # Day streaks
    w_flags = (sub['R'] > 0).astype(int).values
    m_win, m_loss, c_w, c_l = 0, 0, 0, 0
    for flag in w_flags:
        if flag == 1:
            c_w += 1; c_l = 0
            if c_w > m_win: m_win = c_w
        else:
            c_l += 1; c_w = 0
            if c_l > m_loss: m_loss = c_l
            
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
        'Max_Win_Streak': m_win,
        'Max_Loss_Streak': m_loss,
        'Target_Hit': len(sub[sub['ExitReason'] == 'TARGET']),
        'SL_Hit': len(sub[sub['ExitReason'] == 'STOP_LOSS']),
        'EOD_3PM': len(sub[sub['ExitReason'] == 'EOD_SQUAREOFF_3PM'])
    })
print(pd.DataFrame(day_rows).to_string(index=False))

# Monthly consistency
monthly_r = a_df.groupby('YM')['R'].sum()
pos_m = (monthly_r > 0).sum()
tot_m = len(monthly_r)
print("\n" + "="*95)
print("MONTHLY CONSISTENCY & DISTRIBUTION")
print("="*95)
print(f"Total Active Months     : {tot_m}")
print(f"Profitable Months       : {pos_m} / {tot_m} ({pos_m/tot_m*100:.1f}%)")
print(f"Best Month              : {monthly_r.idxmax()} (+{monthly_r.max():.1f} R)")
print(f"Worst Month             : {monthly_r.idxmin()} ({monthly_r.min():.1f} R)")

# Save A++ trades log
a_df.to_csv('reports/a_plus_master_trades.csv', index=False)
print("\nSaved A++ trades to reports/a_plus_master_trades.csv")
