import pandas as pd
import numpy as np

df = pd.read_csv('reports/option_c_full_trades.csv')
df['Date'] = pd.to_datetime(df['Date'])
df['EntryDateTime'] = pd.to_datetime(df['Date'].astype(str) + ' ' + df['EntryTime'])
df['ExitDateTime'] = pd.to_datetime(df['Date'].astype(str) + ' ' + df['ExitTime'])
df = df.sort_values('EntryDateTime').reset_index(drop=True)

# Compute minute-by-minute margin usage for 1R = 150 INR and 1R = 200 INR
events = []
for idx, r in df.iterrows():
    # Margin for this trade = (Qty * EntryPrice) / 5
    # Since Qty = 1R / SL_Dist: Margin = (1R * EntryPrice / SL_Dist) / 5
    events.append({'Time': r['EntryDateTime'], 'Type': 'ENTER', 'Ratio': (r['EntryPrice'] / r['SL_Dist']) / 5.0})
    events.append({'Time': r['ExitDateTime'], 'Type': 'EXIT', 'Ratio': (r['EntryPrice'] / r['SL_Dist']) / 5.0})

df_ev = pd.DataFrame(events).sort_values(['Time', 'Type'], ascending=[True, False]).reset_index(drop=True)

margin_history = []
cur_m_ratio = 0

for idx, ev in df_ev.iterrows():
    if ev['Type'] == 'ENTER':
        cur_m_ratio += ev['Ratio']
    else:
        cur_m_ratio -= ev['Ratio']
    margin_history.append({'Time': ev['Time'], 'Margin_Ratio': cur_m_ratio})

df_m = pd.DataFrame(margin_history)

print("="*85)
print("MARGIN UTILIZATION STATS FOR THE +55 R / MONTH COMBO")
print("="*85)
print("Margin Ratio (Margin Needed per 1 INR of 1R Risk) Percentiles:")
print(df_m['Margin_Ratio'].describe(percentiles=[0.50, 0.75, 0.90, 0.95, 0.99]))

print("\n" + "="*85)
print("EVALUATING 1R = ₹150 VS 1R = ₹200 ON ₹1,00,000 CAPITAL")
print("="*85)

for risk in [150, 200]:
    margin_p50 = df_m['Margin_Ratio'].quantile(0.50) * risk
    margin_p95 = df_m['Margin_Ratio'].quantile(0.95) * risk
    margin_p99 = df_m['Margin_Ratio'].quantile(0.99) * risk
    max_margin = df_m['Margin_Ratio'].max() * risk
    
    max_dd_inr = 40.81 * risk
    monthly_profit = 55.05 * risk
    annual_profit = monthly_profit * 12
    roi_annual = (annual_profit / 100000.0) * 100
    
    print(f"\n--- OPTION C CONFIGURATION WITH 1R = ₹{risk} ---")
    print(f"Fixed Risk per Trade (1R):       ₹{risk}")
    print(f"Expected Monthly Return:         ₹{monthly_profit:,.0f} / month (+55.05 R)")
    print(f"Expected Annual Profit:          ₹{annual_profit:,.0f} / year ({roi_annual:.1f}% Annual ROI)")
    print(f"Worst-Case Historical Drawdown:  -₹{max_dd_inr:,.0f} (-40.81 R, only {max_dd_inr/1000:.1f}% of capital)")
    print(f"Median Margin in Use (50% time): ₹{margin_p50:,.0f}")
    print(f"High-Volume Margin (95% time):   ₹{margin_p95:,.0f}")
    print(f"Peak Freak Margin (99.9% time):  ₹{margin_p99:,.0f}")
    print(f"Absolute 4-Year Peak Margin:     ₹{max_margin:,.0f}")
