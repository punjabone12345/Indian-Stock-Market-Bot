import pandas as pd

df = pd.read_csv('reports/trades_with_mae_mfe.csv')
near_sl_90 = df[(df['ExitReason'] == 'TARGET') & (df['MAE_R'] >= 0.90)].copy()
near_sl_90 = near_sl_90.sort_values('MAE_R', ascending=False)

print(f"Total trades reaching >= 90% SL and then hitting TP: {len(near_sl_90)}")
print("\n" + "="*115)
print(f"{'Date':10s} {'Entry':8s} {'Exit':8s} {'Symbol':10s} {'Dir':4s} {'EntryPrice':11s} {'SL_Price':11s} {'TP_Price':11s} {'SL_Dist':9s} {'MAE(%)':7s} {'MissedBy':10s} {'Held'}")
print("="*115)

for i, r in near_sl_90.head(15).iterrows():
    pct_to_sl = r['MAE_R'] * 100
    points_away = (1.0 - r['MAE_R']) * r['SL_Dist']
    print(f"{r['Date']:10s} {str(r['EntryTime'])[:5]:8s} {str(r['ExitTime'])[:5]:8s} {r['Symbol']:10s} {r['Dir']:4s} {r['EntryPrice']:11.2f} {r['SL_Price']:11.2f} {r['TP_Price']:11.2f} {r['SL_Dist']:9.2f} {pct_to_sl:6.1f}% {points_away:8.2f} pts  {int(r['HoldingMinutes'])}m")
