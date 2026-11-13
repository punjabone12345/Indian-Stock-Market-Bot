import pandas as pd
import numpy as np

df = pd.read_csv('reports/elite_top6_trades.csv')
df['Date'] = pd.to_datetime(df['Date'])
df['EntryDateTime'] = pd.to_datetime(df['Date'].astype(str) + ' ' + df['EntryTime'])
df['ExitDateTime'] = pd.to_datetime(df['Date'].astype(str) + ' ' + df['ExitTime'])
df = df.sort_values('EntryDateTime').reset_index(drop=True)

print("="*85)
print("1. INSTRUMENT SPECIFICATIONS & MARGIN REQUIREMENTS (DHAN 5x MIS CASH EQUITY)")
print("="*85)

inst_data = []
for sym, grp in df.groupby('Symbol'):
    avg_price = grp['EntryPrice'].mean()
    avg_sl_pct = grp['SL_Pct'].mean()
    avg_sl_pts = grp['SL_Dist'].mean()
    
    # Sizing for 1R = 150 INR
    r150_qty = int(150.0 / avg_sl_pts)
    r150_pos_val = r150_qty * avg_price
    r150_margin = r150_pos_val * 0.20 # 5x leverage
    
    # Sizing for 1R = 200 INR
    r200_qty = int(200.0 / avg_sl_pts)
    r200_pos_val = r200_qty * avg_price
    r200_margin = r200_pos_val * 0.20
    
    inst_data.append({
        'Symbol': sym,
        'Avg_Price': round(avg_price, 1),
        'Avg_SL_Pct': f"{avg_sl_pct:.2f}%",
        'Avg_SL_Points': round(avg_sl_pts, 2),
        'Qty_1R_150': r150_qty,
        'Margin_1R_150': round(r150_margin, 0),
        'Qty_1R_200': r200_qty,
        'Margin_1R_200': round(r200_margin, 0)
    })

df_inst = pd.DataFrame(inst_data)
print(df_inst.to_string(index=False))

print("\n" + "="*85)
print("2. CONCURRENCY & MARGIN SAFETY AUDIT ON ₹1,00,000 CAPITAL")
print("="*85)

# Calculate Margin Factor: (EntryPrice / SL_Dist) * 0.20
df['Margin_Factor'] = (df['EntryPrice'] / df['SL_Dist']) * 0.20

# Simulate chronological concurrency with portfolio cap = 6
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

df_cap = pd.DataFrame(accepted)
tot_r_cap = df_cap['R'].sum()
r_m_cap = tot_r_cap / 49.0
cum_cap = df_cap['R'].cumsum()
max_dd_cap = (cum_cap - cum_cap.cummax()).min()

print(f"Portfolio Cap = 6 Positions:")
print(f"Accepted Trades: {len(df_cap)} ({len(df_cap)/len(df)*100:.1f}%) | Monthly Return: +{r_m_cap:.2f} R/mo | Max DD: {max_dd_cap:.2f} R | Peak Margin Factor: {peak_mf_6:.1f}x")

print("\nRisk Calibration on ₹1,00,000 Capital:")
for r in [100, 150, 175, 200]:
    peak_m = peak_mf_6 * r
    dd_inr = abs(max_dd_cap) * r
    trough_cap = 100000.0 - dd_inr
    buf = trough_cap - peak_m
    m_ret = r_m_cap * r
    roi = (m_ret / 100000.0) * 100.0
    safe = buf > 0
    print(f"1R = ₹{r:3d} | Monthly = +₹{m_ret:6,.0f} (+{roi:5.2f}%) | Max DD = -₹{dd_inr:5,.0f} | Peak Margin = ₹{peak_m:6,.0f} | Buffer at Trough = ₹{buf:6,.0f} | {'100% SAFE' if safe else 'MARGIN SHORTFALL'}")
