import pandas as pd
import numpy as np

# Load the full trade log
df = pd.read_csv('reports/option_c_full_trades.csv')
df['Date'] = pd.to_datetime(df['Date'])
df = df.sort_values(['Date', 'EntryTime']).reset_index(drop=True)

df['Cum_R'] = df['R'].cumsum()
df['HWM'] = df['Cum_R'].cummax()
df['Drawdown'] = df['Cum_R'] - df['HWM']

# Find all drawdown episodes
# An episode starts when Cum_R drops below HWM, and ends when Cum_R reaches or exceeds previous HWM
episodes = []
in_dd = False
peak_val = 0
peak_idx = 0
peak_date = None
trough_val = 0
trough_idx = 0
trough_date = None

for i in range(len(df)):
    cum = df.loc[i, 'Cum_R']
    hwm = df.loc[i, 'HWM']
    dt = df.loc[i, 'Date']
    
    if not in_dd:
        if cum < hwm:
            in_dd = True
            peak_idx = i - 1
            peak_val = df.loc[peak_idx, 'Cum_R']
            peak_date = df.loc[peak_idx, 'Date']
            trough_val = cum - hwm
            trough_idx = i
            trough_date = dt
    else:
        dd = cum - peak_val
        if dd < trough_val:
            trough_val = dd
            trough_idx = i
            trough_date = dt
            
        if cum >= peak_val:
            # Recovery reached!
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

print("="*85)
print("             TOP 5 MAXIMUM DRAWDOWN PERIODS (OPTION C)")
print("="*85)
print(df_episodes.head(5).to_string(index=False))

# Focus on the #1 Max Drawdown
m1 = df_episodes.iloc[0]
print("\n" + "="*85)
print(f"DEEP DIVE: THE #1 MAXIMUM DRAWDOWN (-{abs(m1['Max_DD_R']):.2f} R)")
print("="*85)
print(f"1. Drawdown Began (Peak Date):       {m1['Peak_Date'].strftime('%d %B %Y')} (Equity: +{m1['Peak_R']:.1f} R)")
print(f"2. Lowest Point (Trough Date):        {m1['Trough_Date'].strftime('%d %B %Y')} (Equity: +{m1['Trough_R']:.1f} R)")
print(f"3. Full Recovery Date (New High):    {m1['Recovery_Date'].strftime('%d %B %Y')}")
print(f"4. Maximum Depth:                    {m1['Max_DD_R']:.2f} R")
print(f"5. Fall Duration (Peak to Trough):   {m1['Decline_Days']} calendar days ({m1['Decline_Trades']} trades)")
print(f"6. Recovery Duration (Trough to ATH):{m1['Recovery_Days']} calendar days ({m1['Recovery_Trades']} trades)")
print(f"7. Total Episode Duration:           {m1['Total_Days']} calendar days ({m1['Total_Trades']} trades)")

# What assets had trades during this period?
dd_trades = df[(df['Date'] >= m1['Peak_Date']) & (df['Date'] <= m1['Trough_Date'])]
print(f"\nTrades taken during decline ({m1['Peak_Date'].strftime('%Y-%m-%d')} to {m1['Trough_Date'].strftime('%Y-%m-%d')}):")
print(dd_trades.groupby('Symbol').agg(
    Trades=('R', 'count'),
    Losses=('R', lambda x: (x < 0).sum()),
    Wins=('R', lambda x: (x > 0).sum()),
    Net_R=('R', lambda x: round(x.sum(), 2))
).reset_index().to_string(index=False))
