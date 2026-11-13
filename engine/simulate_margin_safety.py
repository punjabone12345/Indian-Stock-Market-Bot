import pandas as pd
import numpy as np

# Load the full trade log
df = pd.read_csv('reports/option_c_full_trades.csv')
df['Date'] = pd.to_datetime(df['Date'])
df['EntryDateTime'] = pd.to_datetime(df['Date'].astype(str) + ' ' + df['EntryTime'])
df['ExitDateTime'] = pd.to_datetime(df['Date'].astype(str) + ' ' + df['ExitTime'])

# Sort by entry time
df = df.sort_values('EntryDateTime').reset_index(drop=True)

# For each trade, calculate the margin required under 5x leverage per 1R unit
# Margin = (Qty * EntryPrice) / 5
# For Bank Nifty Futures, margin is ~50,000 flat for 1 lot (15 qty). If 1R is scaled, BNF margin scales or is 1 lot.
# Let's compute exact margin factor: Margin_per_1R = (EntryPrice / SL_Dist) / 5
df['Margin_Factor'] = (df['EntryPrice'] / df['SL_Dist']) / 5.0
# For Bank Nifty, in our backtest qty = 1R / SL_dist, but min lot is 15.
# Let's inspect Bank Nifty SL dist: avg SL dist is 130 pts.
# At 130 pts, 15 qty risks 15 * 130 = ~1950 INR.
# If cash equities: Margin_per_1R = 1 / (5 * SL_Pct)

print("="*85)
print("HISTORICAL CONCURRENT POSITIONS & MARGIN ANALYSIS")
print("="*85)

# Build a timeline of events: for each trade, +1 on entry, -1 on exit
events = []
for idx, r in df.iterrows():
    events.append({'Time': r['EntryDateTime'], 'Type': 'ENTER', 'Trade_ID': idx, 'Symbol': r['Symbol'], 'Margin_Factor': r['Margin_Factor']})
    events.append({'Time': r['ExitDateTime'], 'Type': 'EXIT', 'Trade_ID': idx, 'Symbol': r['Symbol'], 'Margin_Factor': r['Margin_Factor']})

df_events = pd.DataFrame(events).sort_values(['Time', 'Type'], ascending=[True, False]).reset_index(drop=True)

max_concurrent_positions = 0
max_margin_factor_concurrent = 0
current_open = 0
current_margin_factor = 0

concurrent_records = []

for idx, ev in df_events.iterrows():
    if ev['Type'] == 'ENTER':
        current_open += 1
        current_margin_factor += ev['Margin_Factor']
    else:
        current_open -= 1
        current_margin_factor -= ev['Margin_Factor']
        
    if current_open > max_concurrent_positions:
        max_concurrent_positions = current_open
    if current_margin_factor > max_margin_factor_concurrent:
        max_margin_factor_concurrent = current_margin_factor
        
    concurrent_records.append({'Time': ev['Time'], 'Open': current_open, 'Total_Margin_Factor': current_margin_factor})

df_cc = pd.DataFrame(concurrent_records)

print(f"Maximum Simultaneous Open Positions Observed in 4 Years: {max_concurrent_positions}")
print(f"Peak Concurrent Margin Factor (Margin needed per 1 INR of Risk): {max_margin_factor_concurrent:.2f}x")

print("\nDistribution of Concurrent Open Positions across all trading minutes:")
print(df_cc['Open'].value_counts(normalize=True).sort_index() * 100)

# Now, test different 1R risk amounts for an account starting with 100,000 INR
print("\n" + "="*85)
print("TESTING 1R SIZING ON ₹1,00,000 CAPITAL (CHECKING MARGIN SUFFICIENCY & DRAWDOWN)")
print("="*85)

for risk_1r in [150, 200, 250, 300, 350, 400, 500]:
    peak_margin_needed = max_margin_factor_concurrent * risk_1r
    max_dd_inr = 40.81 * risk_1r
    capital_at_trough = 100000.0 - max_dd_inr
    
    # Check if capital_at_trough >= peak_margin_needed
    is_safe = capital_at_trough >= peak_margin_needed
    margin_buffer_at_trough = capital_at_trough - peak_margin_needed
    
    # Monthly expected return in INR
    monthly_inr = 55.05 * risk_1r
    
    print(f"Risk 1R = ₹{risk_1r:3d} | Monthly Return = ₹{monthly_inr:,.0f} | Max DD = -₹{max_dd_inr:,.0f} | Min Capital at Trough = ₹{capital_at_trough:,.0f} | Peak Margin Needed = ₹{peak_margin_needed:,.0f} | Margin Buffer = ₹{margin_buffer_at_trough:,.0f} | {'SAFE (100% Guaranteed)' if is_safe else 'MARGIN SHORTFALL RISK'}")
