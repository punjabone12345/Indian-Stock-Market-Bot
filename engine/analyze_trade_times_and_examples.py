import pandas as pd
import numpy as np

# Load trade log
df = pd.read_csv('reports/option_c_full_trades.csv')
df['Date'] = pd.to_datetime(df['Date'])
df['EntryTime'] = pd.to_datetime(df['EntryTime'], format='%H:%M:%S').dt.time
df['Hour'] = pd.to_datetime(df['EntryTime'].astype(str), format='%H:%M:%S').dt.hour
df['Minute'] = pd.to_datetime(df['EntryTime'].astype(str), format='%H:%M:%S').dt.minute

# Create 30-min time buckets
def get_time_bucket(t):
    h = t.hour
    m = t.minute
    if h == 9 and m < 30: return "09:15 - 09:30"
    elif h == 9 and m >= 30: return "09:30 - 10:00"
    elif h == 10 and m < 30: return "10:00 - 10:30"
    elif h == 10 and m >= 30: return "10:30 - 11:00"
    elif h == 11 and m < 30: return "11:00 - 11:30"
    elif h == 11 and m >= 30: return "11:30 - 12:00"
    elif h == 12 and m < 30: return "12:00 - 12:30"
    elif h == 12 and m >= 30: return "12:30 - 13:00"
    elif h == 13 and m < 30: return "13:00 - 13:30"
    elif h == 13 and m >= 30: return "13:30 - 14:00"
    elif h == 14 and m <= 15: return "14:00 - 14:15"
    else: return "After 14:15"

df['TimeBucket'] = df['EntryTime'].apply(get_time_bucket)

print("="*85)
print("             ENTRY TIME DISTRIBUTION ACROSS TRADING DAY (IST)")
print("="*85)
time_summary = df.groupby('TimeBucket').agg(
    Trades=('R', 'count'),
    WinRate=('R', lambda x: round((x > 0).mean() * 100, 1)),
    Total_R=('R', lambda x: round(x.sum(), 1)),
    Avg_R=('R', lambda x: round(x.mean(), 3)),
    PF=('R', lambda x: round(x[x > 0].sum() / abs(x[x < 0].sum()), 2))
).reset_index()

# Sort by bucket order
bucket_order = [
    "09:30 - 10:00", "10:00 - 10:30", "10:30 - 11:00", "11:00 - 11:30",
    "11:30 - 12:00", "12:00 - 12:30", "12:30 - 13:00", "13:00 - 13:30",
    "13:30 - 14:00", "14:00 - 14:15"
]
time_summary['Order'] = time_summary['TimeBucket'].map(lambda x: bucket_order.index(x) if x in bucket_order else 99)
time_summary = time_summary.sort_values('Order').drop(columns=['Order'])
time_summary['Pct_Of_Total'] = round((time_summary['Trades'] / len(df)) * 100, 1)

print(time_summary[['TimeBucket', 'Trades', 'Pct_Of_Total', 'WinRate', 'Total_R', 'Avg_R', 'PF']].to_string(index=False))

print("\n" + "="*85)
print("             RECENT EXECUTED TRADE EXAMPLES (OCTOBER 2026)")
print("="*85)
recent_trades = df[df['Date'] >= '2026-10-01'].sort_values(['Date', 'EntryTime'], ascending=False).head(10)
for idx, r in recent_trades.iterrows():
    print(f"Date: {r['Date'].strftime('%d %b %Y')} | Time: {r['EntryTime']} -> Exit: {r['ExitTime']} ({r['HoldingMinutes']} mins)")
    print(f"Symbol: {r['Symbol']:10s} | Dir: {r['Dir']:4s} | Entry: ₹{r['EntryPrice']:,.2f} | SL: ₹{r['SL_Price']:,.2f} (-{r['SL_Pct']:.2f}%) | TP: ₹{r['TP_Price']:,.2f}")
    print(f"Outcome: {r['ExitReason']} | Return: {r['R']:+.2f} R")
    print("-" * 80)
