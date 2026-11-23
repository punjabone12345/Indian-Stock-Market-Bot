import os, glob
import pandas as pd

def inspect_folder(path, name):
    files = glob.glob(os.path.join(path, "*"))
    print(f"\n==========================================")
    print(f"FOLDER: {name} ({len(files)} files)")
    print(f"==========================================")
    if not files:
        print("Empty folder.")
        return
    sample = files[0]
    print(f"Sample file: {os.path.basename(sample)}")
    try:
        if sample.endswith('.parquet'):
            df = pd.read_parquet(sample)
        elif sample.endswith('.csv'):
            df = pd.read_csv(sample)
        else:
            print("Unknown format.")
            return
        print(f"Columns: {list(df.columns)}")
        print(f"Total rows in sample: {len(df)}")
        date_col = None
        for col in ['Date', 'date', 'datetime', 'Datetime', 'timestamp', 'Timestamp']:
            if col in df.columns:
                date_col = col; break
        if date_col:
            df[date_col] = pd.to_datetime(df[date_col])
            print(f"Date range: {df[date_col].min()} to {df[date_col].max()}")
            print(f"Total unique days: {df[date_col].dt.date.nunique()}")
        # Check time interval if intraday
        if len(df) > 1 and date_col:
            diffs = df[date_col].diff().dropna()
            print(f"Median time diff: {diffs.median()}")
    except Exception as e:
        print(f"Error inspecting {sample}: {e}")

inspect_folder("data/stocks", "data/stocks")
inspect_folder("data/nifty100_cache", "data/nifty100_cache")
inspect_folder("data/nifty200_cache", "data/nifty200_cache")
inspect_folder("data/nifty200_daily_cache", "data/nifty200_daily_cache")
inspect_folder("data/nifty50", "data/nifty50")
