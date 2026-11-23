"""
HONEST POINT-IN-TIME TEST: INTRADAY RUNNER ON 194 STOCKS (2022 - 2026)
Zero look-ahead bias: At 09:15 AM, only prior-day close and current open are known.
Conservative sequencing: If Low <= Stop Loss at any point in the day, trade is stopped out.
"""

import os, glob, pandas as pd, numpy as np

# Load daily data for all 194 stocks
daily_files = sorted(glob.glob('data/nifty200_daily_cache/*.parquet'))
stocks_daily = {}
for f in daily_files:
    sym = os.path.basename(f).replace('.parquet', '')
    df = pd.read_parquet(f)
    df['date_str'] = pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d')
    stocks_daily[sym] = df.sort_values('Date').reset_index(drop=True)

symbols = sorted(list(stocks_daily.keys()))
dates = sorted([d for d in stocks_daily['RELIANCE']['date_str'].unique() if d >= '2022-01-03' and d <= '2026-10-31'])

stock_by_date = {}
for sym in symbols:
    df = stocks_daily[sym]
    for idx, row in df.iterrows():
        d = row['date_str']
        if d not in stock_by_date: stock_by_date[d] = {}
        stock_by_date[d][sym] = (idx, row)

def compute_zerodha_charges(buy_val, sell_val):
    b_buy = min(20.0, buy_val * 0.0003)
    b_sell = min(20.0, sell_val * 0.0003)
    brokerage = b_buy + b_sell
    stt = sell_val * 0.00025
    exchange = (buy_val + sell_val) * 0.0000297
    sebi = (buy_val + sell_val) * 0.000001
    stamp = buy_val * 0.00003
    gst = (brokerage + exchange + sebi) * 0.18
    return brokerage + stt + exchange + sebi + stamp + gst

trades = []
risk_per_trade = 1000.0

for d in dates:
    day_data = stock_by_date.get(d, {})
    if len(day_data) < 50: continue
    
    candidates = []
    for sym in symbols:
        if sym not in day_data: continue
        idx, curr = day_data[sym]
        if idx < 25: continue
        df = stocks_daily[sym]
        prev = df.iloc[idx - 1]
        
        # PURE POINT IN TIME: Only use prev day metrics and Day T Open!
        o_curr = curr['Open']
        c_prev = prev['Close']
        gap_pct = (o_curr - c_prev) / c_prev
        
        # Prior 20-day momentum
        rs_20 = (c_prev - df.iloc[idx-20]['Close']) / df.iloc[idx-20]['Close']
        
        # Gap up between 0.5% and 2.5%, strong prior momentum
        if 0.005 <= gap_pct <= 0.025 and rs_20 > 0.03:
            candidates.append({
                'sym': sym, 'score': rs_20 * gap_pct, 'entry': o_curr * 1.0003,
                'curr': curr
            })
            
    if candidates:
        candidates.sort(key=lambda x: x['score'], reverse=True)
        top = candidates[0]
        curr = top['curr']
        entry_p = top['entry']
        sl_p = entry_p * 0.992 # 0.8% stop loss (1R)
        t1_p = entry_p + 2.0 * (entry_p - sl_p) # +2R (+1.6%)
        t2_p = entry_p + 4.0 * (entry_p - sl_p) # +4R (+3.2%)
        
        h = curr['High']
        l = curr['Low']
        c = curr['Close']
        
        shares = int(risk_per_trade / (entry_p - sl_p))
        if shares >= 1:
            # Conservative sequencing: if Low <= SL, stop is hit!
            if l <= sl_p:
                sell_val = shares * (sl_p * 0.9997)
            else:
                if h >= t1_p:
                    half = shares // 2
                    rem = shares - half
                    if h >= t2_p:
                        sell_val = half * (t1_p * 0.9997) + rem * (t2_p * 0.9997)
                    else:
                        sell_val = half * (t1_p * 0.9997) + rem * (c * 0.9997)
                else:
                    sell_val = shares * (c * 0.9997)
                    
            buy_val = shares * entry_p
            gross_pnl = sell_val - buy_val
            charges = compute_zerodha_charges(buy_val, sell_val)
            net_pnl = gross_pnl - charges
            trades.append({'date': d, 'year': d[:4], 'net_pnl': net_pnl, 'r': net_pnl / risk_per_trade})

df_t = pd.DataFrame(trades)
print(f'Total Trades: {len(df_t)}')
wins = df_t[df_t['net_pnl'] > 0]
print(f'Win Rate: {len(wins)/len(df_t)*100:.2f}%')
gp = wins['net_pnl'].sum()
gl = abs(df_t[df_t['net_pnl'] <= 0]['net_pnl'].sum())
print(f'Profit Factor: {gp/gl:.2f}')
net_profit = df_t['net_pnl'].sum()
net_r = df_t['r'].sum()
print(f'Total Net Profit: Rs {net_profit:,.0f} ({net_r:+.1f}R)')
print('Yearly:')
print(df_t.groupby('year')['net_pnl'].agg(['count', 'sum']))
