import pandas as pd

df = pd.read_csv('reports/option_c_full_trades.csv')

print("=== PER ASSET DETAILED METRICS ===")
asset_summary = df.groupby('Symbol').agg(
    Trades=('R', 'count'),
    WinRate=('R', lambda x: round((x > 0).mean() * 100, 1)),
    Total_R=('R', lambda x: round(x.sum(), 1)),
    Avg_SL_Pct=('SL_Pct', lambda x: round(x.mean(), 2)),
    Min_SL_Pct=('SL_Pct', lambda x: round(x.min(), 2)),
    Max_SL_Pct=('SL_Pct', lambda x: round(x.max(), 2)),
    Avg_Hold_Mins=('HoldingMinutes', lambda x: round(x.mean(), 1)),
    PF=('R', lambda x: round(x[x > 0].sum() / abs(x[x < 0].sum()), 2))
).reset_index()

print(asset_summary.to_string(index=False))

print("\n=== STREAK DISTRIBUTION ===")
win_streaks = []
loss_streaks = []
cur_win, cur_loss = 0, 0
for r in df['R'].values:
    if r > 0:
        cur_win += 1
        if cur_loss > 0: loss_streaks.append(cur_loss); cur_loss = 0
    else:
        cur_loss += 1
        if cur_win > 0: win_streaks.append(cur_win); cur_win = 0
if cur_win > 0: win_streaks.append(cur_win)
if cur_loss > 0: loss_streaks.append(cur_loss)

s_win = pd.Series(win_streaks)
s_loss = pd.Series(loss_streaks)
print("Win Streaks Percentiles:")
print(s_win.describe())
print("\nLoss Streaks Percentiles:")
print(s_loss.describe())
