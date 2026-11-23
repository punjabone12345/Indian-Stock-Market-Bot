import pandas as pd
import numpy as np

df = pd.read_parquet('reports/rich_trades_features.parquet')
df['Date'] = pd.to_datetime(df['Date'])
df['YM'] = df['Date'].dt.to_period('M')
df['Win'] = df['R'] > 0
df['Hour'] = df['Time'].apply(lambda t: t.hour + t.minute/60.0)

print("="*95)
print("AUDIT: BASELINE ALL INDEPENDENT TRADES")
print("="*95)
base_n = len(df)
base_tot_r = df['R'].sum()
base_wr = df['Win'].mean() * 100
base_gw = df[df['R']>0]['R'].sum()
base_gl = abs(df[df['R']<=0]['R'].sum())
base_pf = base_gw / base_gl
base_cum = df['R'].cumsum()
base_dd = (base_cum - base_cum.cummax()).min()

print(f"Total Base Trades: {base_n} | WR: {base_wr:.2f}% | PF: {base_pf:.2f} | Tot R: {base_tot_r:.1f}R | R/mo: {base_tot_r/49:.2f}R | DD: {base_dd:.1f}R")

# Now let's explore genuine independent A++ filters that can be executed in real time
# without ANY survivorship or sequence conditioning:

# What if we test:
# Candidate 1: Stacked EMAs (9 > 21 > 50) + Volume >= 1.0x SMA + Mid-Day / Two-Sessions
# Candidate 2: Pullback touching VWAP (Pinch) + Stacked EMAs + Volume >= 1.0x
# Candidate 3: Post-10:00 AM (Confirmed Opening Range) + Stacked EMAs + Vol >= 1.1x
# Candidate 4: Clean Expansion Body (>= 50%) + Volume >= 1.0x
# Candidate 5: Strong Volume Surge (>= 1.25x) across all times

candidates = {
    "1. Base Setup (All EMA9 Pullbacks)": pd.Series(True, index=df.index),
    "2. Stacked EMAs (9>21>50) Only": df['StackedEMAs'] == True,
    "3. Post-10:00 AM + Stacked EMAs": (df['Hour'] >= 10.0) & (df['StackedEMAs'] == True),
    "4. Volume Surge (>=1.0x SMA20)": df['VolRatio'] >= 1.0,
    "5. Volume Surge (>=1.20x SMA20)": df['VolRatio'] >= 1.20,
    "6. Stacked EMAs + Volume >= 1.0x": (df['StackedEMAs'] == True) & (df['VolRatio'] >= 1.0),
    "7. Post-10:00 AM + Stacked + Vol >= 1.0x": (df['Hour'] >= 10.0) & (df['StackedEMAs'] == True) & (df['VolRatio'] >= 1.0),
    "8. VWAP Pinch + Stacked EMAs": (df['PinchVWAP'] == True) & (df['StackedEMAs'] == True),
    "9. VWAP Pinch + Stacked + Vol >= 1.0x": (df['PinchVWAP'] == True) & (df['StackedEMAs'] == True) & (df['VolRatio'] >= 1.0),
    "10. High Expansion (Body>=50% + Stacked + Vol>=1.0x)": (df['BodyRatio'] >= 0.50) & (df['StackedEMAs'] == True) & (df['VolRatio'] >= 1.0)
}

print("\n" + "="*95)
print("INDEPENDENT TRADABLE SETUP AUDIT (NO SEQUENCE BIAS)")
print("="*95)

rows = []
for name, mask in candidates.items():
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
    
    rows.append({
        'Setup': name,
        'Trades': n,
        'WinRate': round(wr, 2),
        'ProfitFactor': round(pf, 2),
        'Total_R': round(tot_r, 1),
        'Monthly_R': round(r_mo, 2),
        'Max_DD': round(dd, 1),
        'Avg_R': round(sub['R'].mean(), 3)
    })

res_df = pd.DataFrame(rows)
print(res_df.to_string(index=False))
