import pandas as pd
import numpy as np

df = pd.read_csv('reports/pure_equity_6champion_trades.csv')
df['Date'] = pd.to_datetime(df['Date'])
df['EntryDateTime'] = pd.to_datetime(df['Date'].astype(str) + ' ' + df['EntryTime'])
df['ExitDateTime'] = pd.to_datetime(df['Date'].astype(str) + ' ' + df['ExitTime'])
df = df.sort_values('EntryDateTime').reset_index(drop=True)

df['Margin_Factor'] = (df['EntryPrice'] / df['SL_Dist']) * 0.20

print("="*85)
print("PORTFOLIO CONCURRENCY CAP EVALUATION (100% CASH EQUITY)")
print("="*85)

for cap in [4, 5, 6, 7, 8, 12]:
    open_pos = []
    accepted = []
    peak_margin_factor = 0
    
    for idx, row in df.iterrows():
        # Filter active
        open_pos = [p for p in open_pos if p['ExitDateTime'] > row['EntryDateTime']]
        
        if len(open_pos) < cap:
            open_pos.append(row)
            accepted.append(row)
            current_mf = sum(p['Margin_Factor'] for p in open_pos)
            if current_mf > peak_margin_factor:
                peak_margin_factor = current_mf
                
    df_c = pd.DataFrame(accepted)
    tot_r = df_c['R'].sum()
    wr = (df_c['R'] > 0).mean() * 100
    cum = df_c['R'].cumsum()
    max_dd = (cum - cum.cummax()).min()
    r_m = tot_r / 49.0
    calmar = (r_m * 12) / abs(max_dd)
    
    print(f"Cap={cap:2d} Positions | Trades: {len(df_c):4d} ({len(df_c)/len(df)*100:4.1f}%) | WR: {wr:.2f}% | R/Mo: {r_m:+5.2f} R | Max DD: {max_dd:5.2f} R | Calmar: {calmar:5.2f} | Peak Margin Factor: {peak_margin_factor:6.1f}x")

print("\n" + "="*85)
print("TESTING 1R SIZING ON ₹1,00,000 CAPITAL UNDER CAP = 6 (ONE PER STOCK)")
print("="*85)

# Calculate for Cap = 6
open_pos = []
accepted = []
peak_mf_6 = 0
for idx, row in df.iterrows():
    open_pos = [p for p in open_pos if p['ExitDateTime'] > row['EntryDateTime']]
    if len(open_pos) < 6:
        open_pos.append(row)
        accepted.append(row)
        cmf = sum(p['Margin_Factor'] for p in open_pos)
        if cmf > peak_mf_6: peak_mf_6 = cmf

df_6 = pd.DataFrame(accepted)
tot_r_6 = df_6['R'].sum()
r_m_6 = tot_r_6 / 49.0
cum_6 = df_6['R'].cumsum()
max_dd_6 = (cum_6 - cum_6.cummax()).min()

for r in [100, 150, 200, 250, 300, 400]:
    peak_m = peak_mf_6 * r
    dd_inr = abs(max_dd_6) * r
    trough_cap = 100000.0 - dd_inr
    buf = trough_cap - peak_m
    m_ret = r_m_6 * r
    roi = (m_ret / 100000.0) * 100.0
    safe = buf > 0
    print(f"1R = ₹{r:3d} | Monthly = +₹{m_ret:6,.0f} (+{roi:5.2f}%) | Max DD = -₹{dd_inr:5,.0f} | Peak Margin = ₹{peak_m:6,.0f} | Buffer at Trough = ₹{buf:6,.0f} | {'100% SAFE (Never Insufficient)' if safe else 'MARGIN SHORTFALL RISK'}")
