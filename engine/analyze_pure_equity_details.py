import pandas as pd
import numpy as np

df = pd.read_csv('reports/pure_equity_6champion_trades.csv')
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
    min_sl_pct = grp['SL_Pct'].min()
    max_sl_pct = grp['SL_Pct'].max()
    
    # Sizing for 1R = 150 INR (Safe for 1 Lakh Capital)
    r150_qty = int(150.0 / avg_sl_pts)
    r150_pos_val = r150_qty * avg_price
    r150_margin = r150_pos_val * 0.20 # 5x leverage
    
    # Sizing for 1R = 200 INR
    r200_qty = int(200.0 / avg_sl_pts)
    r200_pos_val = r200_qty * avg_price
    r200_margin = r200_pos_val * 0.20
    
    # Sizing for 1R = 1,000 INR
    r1000_qty = int(1000.0 / avg_sl_pts)
    r1000_pos_val = r1000_qty * avg_price
    r1000_margin = r1000_pos_val * 0.20
    
    inst_data.append({
        'Symbol': sym,
        'Avg_Price': round(avg_price, 1),
        'Avg_SL_Pct': f"{avg_sl_pct:.2f}%",
        'Avg_SL_Points': round(avg_sl_pts, 2),
        'Qty_1R_150': r150_qty,
        'Margin_1R_150': round(r150_margin, 0),
        'Qty_1R_200': r200_qty,
        'Margin_1R_200': round(r200_margin, 0),
        'Qty_1R_1000': r1000_qty,
        'Margin_1R_1000': round(r1000_margin, 0)
    })

df_inst = pd.DataFrame(inst_data)
print(df_inst.to_string(index=False))

print("\n" + "="*85)
print("2. CONCURRENT OPEN POSITIONS TIMELINE & PEAK MARGIN FACTOR")
print("="*85)

# Calculate Margin Factor: Margin required per 1 INR of risk
# Position Value = (Risk / SL_Dist) * EntryPrice
# Margin (5x MIS) = Position Value * 0.20 = Risk * (EntryPrice / SL_Dist) * 0.20
# Margin Factor = (EntryPrice / SL_Dist) * 0.20
df['Margin_Factor'] = (df['EntryPrice'] / df['SL_Dist']) * 0.20

events = []
for idx, r in df.iterrows():
    events.append({'Time': r['EntryDateTime'], 'Type': 'ENTER', 'Trade_ID': idx, 'Symbol': r['Symbol'], 'Margin_Factor': r['Margin_Factor']})
    events.append({'Time': r['ExitDateTime'], 'Type': 'EXIT', 'Trade_ID': idx, 'Symbol': r['Symbol'], 'Margin_Factor': r['Margin_Factor']})

df_events = pd.DataFrame(events).sort_values(['Time', 'Type'], ascending=[True, False]).reset_index(drop=True)

max_concurrent = 0
max_margin_factor = 0
cur_open = 0
cur_margin_factor = 0
concurrent_distribution = []

for idx, ev in df_events.iterrows():
    if ev['Type'] == 'ENTER':
        cur_open += 1
        cur_margin_factor += ev['Margin_Factor']
    else:
        cur_open -= 1
        cur_margin_factor -= ev['Margin_Factor']
        
    if cur_open > max_concurrent:
        max_concurrent = cur_open
    if cur_margin_factor > max_margin_factor:
        max_margin_factor = cur_margin_factor
        
    concurrent_distribution.append({'Open': cur_open, 'Margin_Factor': cur_margin_factor})

df_dist = pd.DataFrame(concurrent_distribution)

print(f"Max Concurrent Open Positions (All 4 Years): {max_concurrent}")
print(f"Peak Concurrent Margin Factor: {max_margin_factor:.2f}x (Margin needed per 1 INR of Risk)")
print("\nOpen Positions Distribution across all trade event timestamps:")
pos_counts = df_dist['Open'].value_counts(normalize=True).sort_index() * 100
for p, pct in pos_counts.items():
    print(f"  {p} concurrent positions: {pct:.2f}% of the time")

print("\n" + "="*85)
print("3. ₹1,00,000 CAPITAL SUFFICIENCY AUDIT (PEAK MARGIN VS CAPITAL AT TROUGH)")
print("="*85)

for risk_1r in [100, 150, 175, 200, 250, 300]:
    peak_margin = max_margin_factor * risk_1r
    max_dd_inr = 35.27 * risk_1r # New Max DD is -35.27 R!
    trough_capital = 100000.0 - max_dd_inr
    buffer = trough_capital - peak_margin
    monthly_return_inr = 57.00 * risk_1r
    monthly_roi_pct = (monthly_return_inr / 100000.0) * 100.0
    safe = buffer > 0
    print(f"1R = ₹{risk_1r:3d} | Monthly = +₹{monthly_return_inr:,.0f} (+{monthly_roi_pct:.2f}%) | Max DD = -₹{max_dd_inr:,.0f} | Peak Margin = ₹{peak_margin:,.0f} | Buffer at Trough = ₹{buffer:,.0f} | {'SAFE (100% Never Insufficient)' if safe else 'RISK OF MARGIN SHORTFALL'}")

print("\n" + "="*85)
print("4. STREAK DISTRIBUTION (WINNING & LOSING STREAKS)")
print("="*85)

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

s_w = pd.Series(win_streaks)
s_l = pd.Series(loss_streaks)

print(f"Total Winning Streaks: {len(win_streaks)} | Max Win Streak: {s_w.max()} | Mean Win Streak: {s_w.mean():.2f}")
print(f"Total Losing Streaks:  {len(loss_streaks)} | Max Loss Streak: {s_l.max()} | Mean Loss Streak: {s_l.mean():.2f}")
print("\nLosing Streak Frequencies:")
print(pd.cut(s_l, bins=[0, 1, 2, 4, 6, 10, 15, 25], labels=['1 loss', '2 losses', '3-4 losses', '5-6 losses', '7-10 losses', '11-15 losses', '16+ losses']).value_counts().sort_index())

print("\n" + "="*85)
print("5. INTRADAY TRADE TIMING DISTRIBUTION (ENTRY TIMES IN IST)")
print("="*85)
df['EntryHour'] = pd.to_datetime(df['EntryTime'].astype(str), format='%H:%M:%S').dt.hour
df['EntryHalfHour'] = pd.to_datetime(df['EntryTime'].astype(str), format='%H:%M:%S').dt.floor('30min').dt.time
time_dist = df['EntryHalfHour'].value_counts().sort_index()
for t_slot, cnt in time_dist.items():
    pct = (cnt / len(df)) * 100
    bar = '█' * int(pct / 2)
    print(f"  {str(t_slot)[:5]} IST : {cnt:4d} trades ({pct:5.2f}%) {bar}")

print("\n" + "="*85)
print("6. RECENT TRADE EXAMPLES (LAST 10 TRADES IN DATASET)")
print("="*85)
recent = df.tail(10)[['Date', 'EntryTime', 'ExitTime', 'Symbol', 'Dir', 'EntryPrice', 'SL_Price', 'TP_Price', 'ExitPrice', 'ExitReason', 'R']]
print(recent.to_string(index=False))
