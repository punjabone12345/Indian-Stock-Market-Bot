import os, glob, numpy as np, pandas as pd
from datetime import datetime, time

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

def load_symbol_5m(symbol):
    prev_file = f"data/stocks/{symbol}_prev.parquet"
    curr_file = f"data/stocks/{symbol}_2026.parquet"
    dfs = []
    if os.path.exists(prev_file): dfs.append(pd.read_parquet(prev_file))
    if os.path.exists(curr_file): dfs.append(pd.read_parquet(curr_file))
    if not dfs: return None
    df = pd.concat(dfs, ignore_index=True)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df[df['Date'].dt.year >= 2021].sort_values('Date').reset_index(drop=True)
    df.set_index('Date', inplace=True)
    t_start, t_end = time(9, 15), time(15, 30)
    df_5m = df.resample('5min').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna().reset_index()
    df_5m['time'] = df_5m['Date'].dt.time
    df_5m = df_5m[(df_5m['time'] >= t_start) & (df_5m['time'] <= t_end)].reset_index(drop=True)
    df_5m['date_str'] = df_5m['Date'].dt.strftime('%Y-%m-%d')
    return df_5m

symbols = [
    'ADANIENT', 'AXISBANK', 'BAJFINANCE', 'BHARTIARTL', 'COALINDIA', 
    'GRASIM', 'HCLTECH', 'HDFCBANK', 'HINDUNILVR', 'ICICIBANK', 
    'INDUSINDBK', 'INFY', 'ITC', 'JSWSTEEL', 'KOTAKBANK', 
    'LT', 'MARUTI', 'NTPC', 'ONGC', 'POWERGRID', 
    'RELIANCE', 'SBIN', 'SUNPHARMA', 'TATAMOTORS', 'TATASTEEL', 
    'TCS', 'TECHM', 'TITAN', 'ULTRACEMCO', 'WIPRO'
]

symbol_days = {}
all_dates = set()

for sym in symbols:
    df = load_symbol_5m(sym)
    if df is None: continue
    symbol_days[sym] = {}
    grouped = df.groupby('date_str')
    prev_close = None
    or_vols = []
    for d_str, d_df in grouped:
        d_df = d_df.reset_index(drop=True)
        if len(d_df) < 25:
            if len(d_df) > 0: prev_close = d_df.iloc[-1]['Close']
            continue
        c15 = d_df.iloc[0:3]
        open_15m = c15.iloc[0]['Open']
        high_15m = c15['High'].max()
        low_15m = c15['Low'].min()
        close_15m = c15.iloc[-1]['Close']
        vol_15m = c15['Volume'].sum()
        range_15m = high_15m - low_15m
        gap_pct = (close_15m - prev_close) / prev_close * 100.0 if prev_close else 0.0
        rvol = vol_15m / np.mean(or_vols[-20:]) if len(or_vols) >= 10 and np.mean(or_vols[-20:]) > 0 else 1.0
        or_vols.append(vol_15m)
        prev_close = d_df.iloc[-1]['Close']
        if int(d_str[:4]) >= 2022:
            all_dates.add(d_str)
            symbol_days[sym][d_str] = {
                'df': d_df, 'high_15m': high_15m, 'low_15m': low_15m, 'mid_15m': (high_15m + low_15m) / 2.0,
                'close_15m': close_15m, 'range_15m': range_15m, 'gap_pct': gap_pct, 'rvol': rvol
            }

sorted_dates = sorted(list(all_dates))
trades = []

for date_str in sorted_dates:
    candidates = []
    for sym, d_dict in symbol_days.items():
        if date_str not in d_dict: continue
        info = d_dict[date_str]
        gap_pct, rvol, h15, l15, m15 = info['gap_pct'], info['rvol'], info['high_15m'], info['low_15m'], info['mid_15m']
        d_df = info['df']
        if abs(gap_pct) < 1.0 or rvol < 2.0: continue
        
        if gap_pct >= 1.0: # BUY
            for b_i in range(3, min(14, len(d_df) - 6)):
                bar = d_df.iloc[b_i]
                if bar['Close'] > h15:
                    entry_p = bar['Close']
                    raw_sl = m15
                    if (entry_p - raw_sl) / entry_p < 0.0035: raw_sl = entry_p * (1.0 - 0.0035)
                    if (entry_p - raw_sl) / entry_p > 0.0085: raw_sl = entry_p * (1.0 - 0.0085)
                    risk_pts = entry_p - raw_sl
                    if risk_pts <= 0: continue
                    candidates.append({'symbol': sym, 'side': 'BUY', 'b_idx': b_i, 'entry_p': entry_p, 'sl_p': raw_sl, 'risk_pts': risk_pts, 'score': rvol*(1+abs(gap_pct)), 'df': d_df})
                    break
        elif gap_pct <= -1.0: # SHORT
            for b_i in range(3, min(14, len(d_df) - 6)):
                bar = d_df.iloc[b_i]
                if bar['Close'] < l15:
                    entry_p = bar['Close']
                    raw_sl = m15
                    if (raw_sl - entry_p) / entry_p < 0.0035: raw_sl = entry_p * (1.0 + 0.0035)
                    if (raw_sl - entry_p) / entry_p > 0.0085: raw_sl = entry_p * (1.0 + 0.0085)
                    risk_pts = raw_sl - entry_p
                    if risk_pts <= 0: continue
                    candidates.append({'symbol': sym, 'side': 'SELL', 'b_idx': b_i, 'entry_p': entry_p, 'sl_p': raw_sl, 'risk_pts': risk_pts, 'score': rvol*(1+abs(gap_pct)), 'df': d_df})
                    break
                    
    if not candidates: continue
    candidates.sort(key=lambda x: -x['score'])
    t = candidates[0]
    
    shares = int(1000.0 / t['risk_pts'])
    if shares < 1: shares = 1
    s_t1 = int(shares * 0.50)
    s_t2 = shares - s_t1
    if s_t1 < 1: s_t1 = 1
    
    t1_p = t['entry_p'] + 2.0 * t['risk_pts'] if t['side'] == 'BUY' else t['entry_p'] - 2.0 * t['risk_pts']
    t2_p = t['entry_p'] + 3.5 * t['risk_pts'] if t['side'] == 'BUY' else t['entry_p'] - 3.5 * t['risk_pts']
    
    t1_hit, t2_hit = False, False
    curr_sl = t['sl_p']
    exit_p1, exit_p2 = 0.0, 0.0
    d_df = t['df']
    
    for j in range(t['b_idx'] + 1, len(d_df)):
        bar = d_df.iloc[j]
        h, l, c = bar['High'], bar['Low'], bar['Close']
        if t['side'] == 'BUY':
            if l <= curr_sl:
                if not t1_hit: exit_p1, exit_p2 = curr_sl, curr_sl
                else: exit_p2 = curr_sl
                break
            if not t1_hit and h >= t1_p:
                t1_hit = True
                exit_p1 = t1_p
                curr_sl = t['entry_p'] # BE
            if t1_hit and not t2_hit and h >= t2_p:
                t2_hit = True
                exit_p2 = t2_p
                break
            if j == len(d_df) - 1 or j >= 72:
                if not t1_hit: exit_p1 = c
                if not t2_hit: exit_p2 = c
                break
        else: # SELL
            if h >= curr_sl:
                if not t1_hit: exit_p1, exit_p2 = curr_sl, curr_sl
                else: exit_p2 = curr_sl
                break
            if not t1_hit and l <= t1_p:
                t1_hit = True
                exit_p1 = t1_p
                curr_sl = t['entry_p']
            if t1_hit and not t2_hit and l <= t2_p:
                t2_hit = True
                exit_p2 = t2_p
                break
            if j == len(d_df) - 1 or j >= 72:
                if not t1_hit: exit_p1 = c
                if not t2_hit: exit_p2 = c
                break
                
    if t['side'] == 'BUY':
        p1 = s_t1 * (exit_p1 - t['entry_p'])
        f1 = compute_zerodha_charges(s_t1 * t['entry_p'], s_t1 * exit_p1)
        p2 = s_t2 * (exit_p2 - t['entry_p']) if s_t2 > 0 else 0
        f2 = compute_zerodha_charges(s_t2 * t['entry_p'], s_t2 * exit_p2) if s_t2 > 0 else 0
    else:
        p1 = s_t1 * (t['entry_p'] - exit_p1)
        f1 = compute_zerodha_charges(s_t1 * exit_p1, s_t1 * t['entry_p'])
        p2 = s_t2 * (t['entry_p'] - exit_p2) if s_t2 > 0 else 0
        f2 = compute_zerodha_charges(s_t2 * exit_p2, s_t2 * t['entry_p']) if s_t2 > 0 else 0
        
    net_pnl = p1 + p2 - f1 - f2
    ret_pct = net_pnl / 1000.0
    trades.append({'date': date_str, 'year': int(date_str[:4]), 'symbol': t['symbol'], 'side': t['side'], 'ret_pct': ret_pct, 'net_pnl': net_pnl})

df_t = pd.DataFrame(trades)
print("="*80)
print("TRUE 5-MINUTE INTRADAY YEAR-BY-YEAR AUDIT (2022-2026, 30 STOCKS):")
print("="*80)
yearly = df_t.groupby('year').agg(
    trades=('ret_pct', 'count'),
    win_rate=('ret_pct', lambda x: (x > 0).mean() * 100),
    total_ret=('ret_pct', 'sum'),
    avg_trade_ret=('ret_pct', 'mean')
)
print(yearly)
print(f"OVERALL: Total Trades: {len(df_t)} | Win Rate: {(df_t['ret_pct'] > 0).mean()*100:.2f}% | Total Net: {df_t['ret_pct'].sum():+.2f}%")
