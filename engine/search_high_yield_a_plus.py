import pandas as pd
import numpy as np

df = pd.read_parquet('reports/rich_trades_features.parquet')
df['Date'] = pd.to_datetime(df['Date'])
df['DayName'] = df['Date'].dt.day_name()
df['YM'] = df['Date'].dt.to_period('M')
df['Win'] = df['R'] > 0
df['Hour'] = df['Time'].apply(lambda t: t.hour + t.minute/60.0)

# Sort chronologically
df = df.sort_values(['Date', 'Time']).reset_index(drop=True)

# Add Trade Sequence within each day for each stock
df['Stock_Day_Trade_Num'] = df.groupby(['Date', 'Symbol']).cumcount() + 1
# Add Portfolio Day Trade Sequence
df['Port_Day_Trade_Num'] = df.groupby('Date').cumcount() + 1

print(f"Total base trades: {len(df)}")

# Check Trade #1 of the day
t1 = df[df['Stock_Day_Trade_Num'] == 1]
tot_r_t1 = t1['R'].sum()
wr_t1 = t1['Win'].mean() * 100
pf_t1 = t1[t1['R']>0]['R'].sum() / abs(t1[t1['R']<=0]['R'].sum())
cum_t1 = t1['R'].cumsum()
dd_t1 = (cum_t1 - cum_t1.cummax()).min()
print(f"Trade #1 of day per stock: {len(t1)} tr | WR: {wr_t1:.2f}% | PF: {pf_t1:.2f} | Tot R: {tot_r_t1:.1f}R | R/mo: {tot_r_t1/49:.2f}R | DD: {dd_t1:.1f}R")

# Let's test combinations targeting: R/month >= 20.0 and R/month <= 35.0, WR >= 48%, PF >= 1.85, DD <= -18R
print("\n" + "="*80)
print("SEARCHING COMBINATIONS TARGETING 20-30 R/MONTH, HIGH WR & LOW DD")
print("="*80)

# Grid of potential high-yield A++ rules:
grid = []

# Rule 1: Morning Prime (09:30-11:30) + First Trade of Day
m1 = (df['Hour'] <= 11.5) & (df['Stock_Day_Trade_Num'] == 1)
grid.append(("Morning First-Pullback (09:30-11:30, Trade #1)", m1))

# Rule 2: Morning Prime + Stacked EMAs
m2 = (df['Hour'] <= 11.5) & (df['StackedEMAs'] == True)
grid.append(("Morning Prime + Stacked EMAs (9>21>50)", m2))

# Rule 3: Morning First-Pullback + Stacked EMAs
m3 = (df['Hour'] <= 11.5) & (df['Stock_Day_Trade_Num'] == 1) & (df['StackedEMAs'] == True)
grid.append(("Morning First-Pullback + Stacked EMAs", m3))

# Rule 4: Stacked EMAs + Body Ratio >= 45% + Not Lunch Chop (09:30-11:30 & 13:00-14:15)
m4 = (df['StackedEMAs'] == True) & (df['BodyRatio'] >= 0.45) & ~((df['Hour'] >= 11.5) & (df['Hour'] <= 13.0))
grid.append(("Stacked EMAs + Expansion Body (>=45%) + Two Sessions", m4))

# Rule 5: Morning First-Pullback + Body Ratio >= 40%
m5 = (df['Hour'] <= 11.5) & (df['Stock_Day_Trade_Num'] == 1) & (df['BodyRatio'] >= 0.40)
grid.append(("Morning Trade #1 + Clean Body (>=40%)", m5))

# Rule 6: Volume >= 0.85x + Stacked EMAs
m6 = (df['VolRatio'] >= 0.85) & (df['StackedEMAs'] == True)
grid.append(("Volume >= 0.85x + Stacked EMAs", m6))

# Rule 7: Volume >= 0.80x + Morning Prime (09:30-11:30)
m7 = (df['VolRatio'] >= 0.80) & (df['Hour'] <= 11.5)
grid.append(("Volume >= 0.80x + Morning Prime", m7))

# Rule 8: Morning First-Pullback + Vol >= 0.80x
m8 = (df['Hour'] <= 11.5) & (df['Stock_Day_Trade_Num'] == 1) & (df['VolRatio'] >= 0.80)
grid.append(("Morning Trade #1 + Volume >= 0.80x", m8))

# Rule 9: Stacked EMAs + VWAP Pinch + Trade #1
m9 = (df['StackedEMAs'] == True) & (df['PinchVWAP'] == True) & (df['Stock_Day_Trade_Num'] == 1)
grid.append(("Stacked EMAs + VWAP Pinch + Trade #1", m9))

# Rule 10: Expansion Candle (Body >= 50%) + Vol >= 0.85x
m10 = (df['BodyRatio'] >= 0.50) & (df['VolRatio'] >= 0.85)
grid.append(("Expansion Candle (Body>=50%) + Vol>=0.85x", m10))

for name, mask in grid:
    sub = df[mask]
    n = len(sub)
    if n == 0: continue
    tot_r = sub['R'].sum()
    r_mo = tot_r / 49.0
    wr = sub['Win'].mean() * 100
    gw = sub[sub['R']>0]['R'].sum()
    gl = abs(sub[sub['R']<=0]['R'].sum())
    pf = gw / gl if gl > 0 else 0
    cum = sub['R'].cumsum()
    dd = (cum - cum.cummax()).min()
    print(f"{name:55s} | {n:4d} tr | WR: {wr:5.2f}% | PF: {pf:4.2f} | R/mo: {r_mo:5.2f}R | Tot: {tot_r:6.1f}R | DD: {dd:5.1f}R")
