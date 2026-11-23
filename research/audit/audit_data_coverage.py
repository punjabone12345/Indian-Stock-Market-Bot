import os, glob, json
import pandas as pd

symbols = [
    'ADANIENT', 'AXISBANK', 'BAJFINANCE', 'BHARTIARTL', 'COALINDIA', 
    'GRASIM', 'HCLTECH', 'HDFCBANK', 'HINDUNILVR', 'ICICIBANK', 
    'INDUSINDBK', 'INFY', 'ITC', 'JSWSTEEL', 'KOTAKBANK', 
    'LT', 'MARUTI', 'NTPC', 'ONGC', 'POWERGRID', 
    'RELIANCE', 'SBIN', 'SUNPHARMA', 'TATAMOTORS', 'TATASTEEL', 
    'TCS', 'TECHM', 'TITAN', 'ULTRACEMCO', 'WIPRO'
]

coverage_report = {}

for sym in symbols:
    p_prev = f"data/stocks/{sym}_prev.parquet"
    p_2026 = f"data/stocks/{sym}_2026.parquet"
    
    exists_prev = os.path.exists(p_prev)
    exists_2026 = os.path.exists(p_2026)
    
    if not exists_prev and not exists_2026:
        coverage_report[sym] = {"status": "MISSING"}
        continue
        
    dfs = []
    if exists_prev: dfs.append(pd.read_parquet(p_prev))
    if exists_2026: dfs.append(pd.read_parquet(p_2026))
    df = pd.concat(dfs, ignore_index=True)
    df['Date'] = pd.to_datetime(df['Date'])
    
    df_window = df[(df['Date'] >= '2022-01-01') & (df['Date'] <= '2026-10-31')].sort_values('Date').reset_index(drop=True)
    df_window['date_str'] = df_window['Date'].dt.strftime('%Y-%m-%d')
    
    n_days = df_window['date_str'].nunique()
    total_rows = len(df_window)
    first_ts = str(df_window['Date'].min())
    last_ts = str(df_window['Date'].max())
    
    # Calculate missing candles vs expected 375 candles per 6.25 hr day
    # Expected: n_days * 375
    expected_candles = n_days * 375
    missing_candles = max(0, expected_candles - total_rows)
    completeness_pct = round((total_rows / expected_candles) * 100.0, 2) if expected_candles > 0 else 0.0
    
    coverage_report[sym] = {
        "status": "VALID",
        "total_1m_bars": total_rows,
        "unique_days": n_days,
        "first_timestamp": first_ts,
        "last_timestamp": last_ts,
        "expected_candles": expected_candles,
        "missing_candles": missing_candles,
        "completeness_pct": completeness_pct,
        "has_2026_file": exists_2026
    }
    print(f"Audited {sym:12s} | Days: {n_days} | Bars: {total_rows:7d} | Completeness: {completeness_pct}% | End: {last_ts}", flush=True)

with open("research/audit/data_coverage_report.json", "w") as f:
    json.dump(coverage_report, f, indent=2)

print("\nSaved data coverage report to research/audit/data_coverage_report.json")
