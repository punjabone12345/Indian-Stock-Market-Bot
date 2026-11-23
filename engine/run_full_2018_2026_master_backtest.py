import os
import sys
import glob
import pandas as pd
import numpy as np
from datetime import time, datetime

print("Initializing 8.8-Year Master Backtest (Jan 1, 2018 - Oct 16, 2026)...")

def load_stock_data_full(symbol):
    f_prev = f'data/stocks/{symbol}_prev.parquet'
    f_2026 = f'data/stocks/{symbol}_2026.parquet'
    dfs = []
    if os.path.exists(f_prev):
        d1 = pd.read_parquet(f_prev)
        d1['Timestamp'] = pd.to_datetime(d1['Date'])
        dfs.append(d1[['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']])
    if os.path.exists(f_2026):
        d2 = pd.read_parquet(f_2026)
        d2['Timestamp'] = pd.to_datetime(d2['Date'])
        dfs.append(d2[['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']])
    if not dfs: return None
    df = pd.concat(dfs).sort_values('Timestamp').drop_duplicates('Timestamp').reset_index(drop=True)
    df['Time'] = df['Timestamp'].dt.time
    df = df[(df['Time'] >= time(9, 15)) & (df['Time'] <= time(15, 29))].copy()
    return df

def resample_and_calc_indicators(df_1m, tf_min=5):
    df = df_1m.set_index('Timestamp').resample(f'{tf_min}min', origin='start_day', offset='15min').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum' if 'Volume' in df_1m.columns else 'count'
    }).dropna().reset_index()

    df['Date'] = df['Timestamp'].dt.date
    df['Time'] = df['Timestamp'].dt.time
    
    # VWAP
    df['Typ'] = (df['High'] + df['Low'] + df['Close']) / 3.0
    vol = df['Volume'].values
    if np.sum(vol) == 0 or np.all(vol == 1):
        df['VWAP'] = df.groupby('Date')['Close'].transform(lambda x: x.expanding().mean())
    else:
        df['PV'] = df['Typ'] * df['Volume']
        df['VWAP'] = df.groupby('Date')['PV'].cumsum() / df.groupby('Date')['Volume'].cumsum()

    # EMAs: 9, 21
    df['EMA9'] = df.groupby('Date')['Close'].transform(lambda x: x.ewm(span=9, adjust=False).mean())
    df['EMA21'] = df.groupby('Date')['Close'].transform(lambda x: x.ewm(span=21, adjust=False).mean())
    
    # ATR 14
    prev_close = df.groupby('Date')['Close'].shift(1)
    tr1 = df['High'] - df['Low']
    tr2 = (df['High'] - prev_close).abs()
    tr3 = (df['Low'] - prev_close).abs()
    df['TR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['ATR'] = df.groupby('Date')['TR'].transform(lambda x: x.rolling(14, min_periods=1).mean())
    
    return df

# Build Continuous Macro Market Trend (2018 - 2026)
print("Building Full 2018-2026 Macro Market Trend Series...")
# 1. Real Nifty 50 1m for 2022-2026
dfs_nifty = []
for y in ['2022', '2023', '2024', '2025']:
    p = f'data/nifty50/NIFTY50_1min_{y}.csv'
    if os.path.exists(p):
        d = pd.read_csv(p)
        d['Timestamp'] = pd.to_datetime(d['Timestamp'])
        dfs_nifty.append(d[['Timestamp', 'Open', 'High', 'Low', 'Close']])
for f in sorted(glob.glob('data/nifty50/2026/*.csv')):
    d = pd.read_csv(f)
    d['Timestamp'] = pd.to_datetime(d['Timestamp'])
    dfs_nifty.append(d[['Timestamp', 'Open', 'High', 'Low', 'Close']])
nifty_22_26 = pd.concat(dfs_nifty).sort_values('Timestamp').drop_duplicates('Timestamp').reset_index(drop=True)

# 2. Composite Nifty Heavyweights for 2018-2021
print("Building Composite Index for 2018-2021 from Core Heavyweights...")
hw_stocks = ['RELIANCE', 'HDFCBANK', 'ICICIBANK', 'INFY', 'TCS', 'SBIN']
hw_dfs = []
for s in hw_stocks:
    d = pd.read_parquet(f'data/stocks/{s}_prev.parquet', columns=['Date', 'Close']).drop_duplicates('Date')
    d['Timestamp'] = pd.to_datetime(d['Date'])
    d = d[d['Timestamp'] < '2022-01-01'].set_index('Timestamp')[['Close']].rename(columns={'Close': s})
    hw_dfs.append(d)
comb_hw = pd.concat(hw_dfs, axis=1).sort_index().ffill().bfill()
norm_close = (comb_hw / comb_hw.iloc[0]).mean(axis=1) * 10500.0  # Normalized to Nifty 2018 base
df_comp_1m = pd.DataFrame({'Timestamp': norm_close.index, 'Close': norm_close.values})
df_comp_1m['Open'] = df_comp_1m['Close']
df_comp_1m['High'] = df_comp_1m['Close']
df_comp_1m['Low'] = df_comp_1m['Close']

full_macro_1m = pd.concat([df_comp_1m, nifty_22_26]).sort_values('Timestamp').drop_duplicates('Timestamp').reset_index(drop=True)
full_macro_1m['Time'] = full_macro_1m['Timestamp'].dt.time
full_macro_1m = full_macro_1m[(full_macro_1m['Time'] >= time(9, 15)) & (full_macro_1m['Time'] <= time(15, 29))].copy()

# 5m Macro Trend Series
df_macro_5m = full_macro_1m.set_index('Timestamp').resample('5min', origin='start_day', offset='15min').agg({
    'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'
}).dropna().reset_index()
df_macro_5m['Date'] = df_macro_5m['Timestamp'].dt.date
df_macro_5m['EMA9'] = df_macro_5m.groupby('Date')['Close'].transform(lambda x: x.ewm(span=9, adjust=False).mean())
df_macro_5m['EMA21'] = df_macro_5m.groupby('Date')['Close'].transform(lambda x: x.ewm(span=21, adjust=False).mean())
df_macro_5m['Nifty_Trend'] = 0
df_macro_5m.loc[(df_macro_5m['Close'] > df_macro_5m['EMA21']) & (df_macro_5m['EMA9'] > df_macro_5m['EMA21']), 'Nifty_Trend'] = 1
df_macro_5m.loc[(df_macro_5m['Close'] < df_macro_5m['EMA21']) & (df_macro_5m['EMA9'] < df_macro_5m['EMA21']), 'Nifty_Trend'] = -1
macro_trend_map = df_macro_5m[['Timestamp', 'Nifty_Trend']].set_index('Timestamp')
print(f"Macro Trend Series Ready: {len(df_macro_5m):,} 5m bars from {df_macro_5m['Date'].iloc[0]} to {df_macro_5m['Date'].iloc[-1]}")

def backtest_equity_detailed(df_stock, macro_trend_map, symbol, target_rr=3.0):
    df_stock = df_stock.copy()
    df_stock['Nifty_Trend'] = df_stock['Timestamp'].map(macro_trend_map['Nifty_Trend']).fillna(0).astype(int)
    
    trades = []
    daily_groups = df_stock.groupby('Date')
    
    for dt, day_df in daily_groups:
        n = len(day_df)
        if n < 10: continue
        
        opens = day_df['Open'].values
        highs = day_df['High'].values
        lows = day_df['Low'].values
        closes = day_df['Close'].values
        times = day_df['Time'].values
        ema9 = day_df['EMA9'].values
        ema21 = day_df['EMA21'].values
        vwap = day_df['VWAP'].values
        atr = day_df['ATR'].values
        n_trend = day_df['Nifty_Trend'].values
        
        day_trades = 0
        day_losses = 0
        
        for i in range(2, n - 2):
            if day_trades >= 2 or day_losses >= 1: break
            if times[i] < time(9, 30) or times[i] > time(14, 15): continue
            
            # --- BUY PULLBACK LOGIC ---
            if (n_trend[i] == 1 and 
                closes[i] > vwap[i] and 
                ema9[i] > ema21[i] and 
                (lows[i] <= ema9[i] or lows[i-1] <= ema9[i-1]) and 
                closes[i] > opens[i] and 
                closes[i] > ema9[i]):
                
                entry = closes[i]
                raw_sl = min(lows[i], lows[i-1]) - (0.2 * atr[i])
                sl_dist = max(entry - raw_sl, entry * 0.0020)
                sl = entry - sl_dist
                if sl_dist > entry * 0.0070: continue
                tp = entry + (sl_dist * target_rr)
                sl_pct = (sl_dist / entry) * 100.0
                
                final_r = None
                exit_time = None
                exit_reason = None
                
                for m in range(i + 1, n):
                    if lows[m] <= sl:
                        final_r = -1.04
                        exit_time = times[m]
                        exit_reason = 'STOP_LOSS'
                        break
                    if highs[m] >= tp:
                        final_r = round(target_rr - 0.04, 2)
                        exit_time = times[m]
                        exit_reason = 'TARGET'
                        break
                    if times[m] >= time(15, 0):
                        final_r = round((closes[m] - entry)/sl_dist - 0.04, 2)
                        exit_time = times[m]
                        exit_reason = 'EOD_SQUAREOFF'
                        break
                
                if final_r is not None:
                    trades.append({
                        'Date': dt, 'Time': times[i], 'Symbol': symbol, 'Dir': 'BUY',
                        'Entry': entry, 'SL': sl, 'TP': tp, 'SL_Pct': sl_pct,
                        'ExitReason': exit_reason, 'R': final_r
                    })
                    day_trades += 1
                    if final_r < 0: day_losses += 1

            # --- SELL PULLBACK LOGIC ---
            elif (n_trend[i] == -1 and 
                  closes[i] < vwap[i] and 
                  ema9[i] < ema21[i] and 
                  (highs[i] >= ema9[i] or highs[i-1] >= ema9[i-1]) and 
                  closes[i] < opens[i] and 
                  closes[i] < ema9[i]):
                
                entry = closes[i]
                raw_sl = max(highs[i], highs[i-1]) + (0.2 * atr[i])
                sl_dist = max(raw_sl - entry, entry * 0.0020)
                sl = entry + sl_dist
                if sl_dist > entry * 0.0070: continue
                tp = entry - (sl_dist * target_rr)
                sl_pct = (sl_dist / entry) * 100.0
                
                final_r = None
                exit_time = None
                exit_reason = None
                
                for m in range(i + 1, n):
                    if highs[m] >= sl:
                        final_r = -1.04
                        exit_time = times[m]
                        exit_reason = 'STOP_LOSS'
                        break
                    if lows[m] <= tp:
                        final_r = round(target_rr - 0.04, 2)
                        exit_time = times[m]
                        exit_reason = 'TARGET'
                        break
                    if times[m] >= time(15, 0):
                        final_r = round((entry - closes[m])/sl_dist - 0.04, 2)
                        exit_time = times[m]
                        exit_reason = 'EOD_SQUAREOFF'
                        break
                
                if final_r is not None:
                    trades.append({
                        'Date': dt, 'Time': times[i], 'Symbol': symbol, 'Dir': 'SELL',
                        'Entry': entry, 'SL': sl, 'TP': tp, 'SL_Pct': sl_pct,
                        'ExitReason': exit_reason, 'R': final_r
                    })
                    day_trades += 1
                    if final_r < 0: day_losses += 1

    return trades

basket = ['RELIANCE', 'MARUTI', 'SUNPHARMA', 'TATAMOTORS', 'TCS', 'TATASTEEL']
all_trades = []

for sym in basket:
    print(f"Executing backtest on {sym} across all available data...")
    df_1m = load_stock_data_full(sym)
    df_5m = resample_and_calc_indicators(df_1m, 5)
    t = backtest_equity_detailed(df_5m, macro_trend_map, sym)
    all_trades.extend(t)
    print(f"  -> {sym}: {len(t)} trades executed.")

df_all = pd.DataFrame(all_trades).sort_values(['Date', 'Time']).reset_index(drop=True)
df_all['Date'] = pd.to_datetime(df_all['Date'])
df_all['Year'] = df_all['Date'].dt.year
df_all['YM'] = df_all['Date'].dt.to_period('M')

# Fixed Risk Analysis: 1 Lac capital, 200 risk per trade
init_cap = 100000.0
risk_per_trade = 200.0
df_all['PnL_INR'] = df_all['R'] * risk_per_trade
df_all['Cum_PnL_INR'] = df_all['PnL_INR'].cumsum()
df_all['Equity'] = init_cap + df_all['Cum_PnL_INR']
df_all['HWM'] = df_all['Equity'].cummax()
df_all['DD_INR'] = df_all['Equity'] - df_all['HWM']
df_all['DD_Pct'] = (df_all['DD_INR'] / df_all['HWM']) * 100.0

tot_trades = len(df_all)
wins = df_all[df_all['R'] > 0]
losses = df_all[df_all['R'] < 0]
wr = len(wins) / tot_trades * 100.0
tot_r = df_all['R'].sum()
tot_pnl = df_all['PnL_INR'].sum()
end_cap = init_cap + tot_pnl
gross_win = wins['PnL_INR'].sum()
gross_loss = abs(losses['PnL_INR'].sum())
pf = gross_win / gross_loss
max_dd_inr = abs(df_all['DD_INR'].min())
max_dd_r = max_dd_inr / risk_per_trade
max_dd_pct = abs(df_all['DD_Pct'].min())

# Streaks
c_w, c_l, max_w, max_l = 0, 0, 0, 0
for r in df_all['R'].values:
    if r > 0:
        c_w += 1
        c_l = 0
        if c_w > max_w: max_w = c_w
    else:
        c_l += 1
        c_w = 0
        if c_l > max_l: max_l = c_l

print("\n" + "="*85)
print("FULL 8.8-YEAR MASTER BACKTEST RESULTS (JAN 1, 2018 - OCT 16, 2026)")
print("="*85)
print(f"Starting Capital     : Rs {init_cap:,.2f}")
print(f"Risk Per Trade (1R)  : Rs {risk_per_trade:,.2f}")
print(f"Total Trades         : {tot_trades:,}")
print(f"Winning Trades       : {len(wins):,} ({wr:.2f}%)")
print(f"Losing Trades        : {len(losses):,} ({100-wr:.2f}%)")
print(f"Total Net R          : {tot_r:,.2f} R")
print(f"Gross Profit         : Rs {gross_win:,.2f}")
print(f"Gross Loss           : Rs {gross_loss:,.2f}")
print(f"Net Trading Profit   : Rs {tot_pnl:,.2f}")
print(f"Ending Capital       : Rs {end_cap:,.2f} ({end_cap/init_cap:.2f}x)")
print(f"Total Return on Cap  : +{(tot_pnl/init_cap)*100:.2f}%")
print(f"Profit Factor        : {pf:.2f}")
print(f"Max Drawdown (R)     : -{max_dd_r:.1f} R")
print(f"Max Drawdown (INR)   : -Rs {max_dd_inr:,.2f}")
print(f"Max Drawdown (%)     : -{max_dd_pct:.2f}% of peak equity")
print(f"Max Win Streak       : {max_w} consecutive wins")
print(f"Max Loss Streak      : {max_l} consecutive losses")

yearly = df_all.groupby('Year').agg(
    Trades=('R', 'count'),
    Wins=('R', lambda x: (x > 0).sum()),
    WinRate=('R', lambda x: round((x > 0).mean() * 100, 1)),
    Net_R=('R', lambda x: round(x.sum(), 2)),
    Profit_INR=('PnL_INR', lambda x: round(x.sum(), 2))
).reset_index()
print("\n=== YEAR-BY-YEAR SUMMARY (2018 - 2026) ===")
print(yearly.to_string(index=False))

# Monthly table
monthly = df_all.groupby('YM').agg(
    Trades=('R', 'count'),
    Wins=('R', lambda x: (x > 0).sum()),
    WinRate=('R', lambda x: round((x > 0).mean() * 100, 1)),
    Net_R=('R', lambda x: round(x.sum(), 2)),
    Profit_INR=('PnL_INR', lambda x: round(x.sum(), 2))
).reset_index()

# Save datasets
os.makedirs('reports', exist_ok=True)
df_all.to_csv('reports/master_2018_2026_trades.csv', index=False)
yearly.to_csv('reports/master_2018_2026_yearly.csv', index=False)
monthly.to_csv('reports/master_2018_2026_monthly.csv', index=False)
print("\nSaved full trade log to reports/master_2018_2026_trades.csv")
