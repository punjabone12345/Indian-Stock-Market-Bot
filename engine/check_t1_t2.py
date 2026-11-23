import pandas as pd

df = pd.read_parquet('reports/rich_trades_features.parquet')
df['Date'] = pd.to_datetime(df['Date'])
df = df.sort_values(['Date', 'Time']).reset_index(drop=True)
df['Stock_Day_Trade_Num'] = df.groupby(['Date', 'Symbol']).cumcount() + 1

t1 = df[df['Stock_Day_Trade_Num'] == 1]
t2 = df[df['Stock_Day_Trade_Num'] == 2]

wr1 = (t1['R'] > 0).mean() * 100
wr2 = (t2['R'] > 0).mean() * 100

print(f"Total T1 trades: {len(t1)} | T1 Win Rate: {wr1:.1f}% | T1 Net R: {t1['R'].sum():.1f} R")
print(f"Total T2 trades: {len(t2)} | T2 Win Rate: {wr2:.1f}% | T2 Net R: {t2['R'].sum():.1f} R")
