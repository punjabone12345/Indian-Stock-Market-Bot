import os, glob
import pandas as pd

# Check NIFTY daily cache
nifty_daily = glob.glob("data/nifty200_daily_cache/*.parquet")
print(f"Found {len(nifty_daily)} daily cache files.")

# Load NIFTY 50 1m dates
nifty50_files = glob.glob("data/nifty50/*.parquet")
print(f"Found {len(nifty50_files)} nifty50 parquet files.")

# Load 30 mega-cap dates
symbols = [
    'ADANIENT', 'AXISBANK', 'BAJFINANCE', 'BHARTIARTL', 'COALINDIA', 
    'GRASIM', 'HCLTECH', 'HDFCBANK', 'HINDUNILVR', 'ICICIBANK', 
    'INDUSINDBK', 'INFY', 'ITC', 'JSWSTEEL', 'KOTAKBANK', 
    'LT', 'MARUTI', 'NTPC', 'ONGC', 'POWERGRID', 
    'RELIANCE', 'SBIN', 'SUNPHARMA', 'TATAMOTORS', 'TATASTEEL', 
    'TCS', 'TECHM', 'TITAN', 'ULTRACEMCO', 'WIPRO'
]

# Check unique dates in RELIANCE (benchmark mega-cap)
p_prev = "data/stocks/RELIANCE_prev.parquet"
p_2026 = "data/stocks/RELIANCE_2026.parquet"
dfs = []
if os.path.exists(p_prev): dfs.append(pd.read_parquet(p_prev))
if os.path.exists(p_2026): dfs.append(pd.read_parquet(p_2026))
df_rel = pd.concat(dfs, ignore_index=True)
df_rel['Date'] = pd.to_datetime(df_rel['Date'])
df_rel = df_rel[(df_rel['Date'] >= '2022-01-01') & (df_rel['Date'] <= '2026-10-31')]
df_rel['date_str'] = df_rel['Date'].dt.strftime('%Y-%m-%d')
rel_dates = sorted(df_rel['date_str'].unique())

print(f"RELIANCE unique trading dates (2022 to 2026-10-31): {len(rel_dates)}")
print(f"First timestamp: {df_rel['Date'].min()}")
print(f"Last timestamp:  {df_rel['Date'].max()}")

# Count candles per day in RELIANCE
candles_per_day = df_rel.groupby('date_str').size()
short_days = candles_per_day[candles_per_day < 125]
print(f"\nDays with fewer than 125 1-min candles (< 25 5-min bars): {len(short_days)}")
for d, cnt in short_days.items():
    print(f"  Date {d}: {cnt} 1-min candles")
