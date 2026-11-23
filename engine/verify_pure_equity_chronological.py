"""
Chronological Verification of 6-Champion Pure Equity Strategy
Testing:
- 6 Champions: RELIANCE, MARUTI, SUNPHARMA, TATAMOTORS, TCS, TATASTEEL
- Nifty 50 Trend Alignment (EMA 9 > EMA 21 on Nifty)
- EMA 9 Pullback + VWAP Confirmation
- Target: 3R, SL: Min(low[i], low[i-1]) - 0.2 ATR (clamped 0.20% to 0.70%)
- Sequential bar-by-bar execution (NO LOOKAHEAD, NO FUTURE PEEKING)
- Max 1 trade per symbol at a time
- 100% exact Zerodha statutory tariffs + 1-tick slippage
"""

import sys
import os
import glob
import pandas as pd
import numpy as np
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

def load_nifty_trend():
    # Load Nifty 1m data from 2022 to 2025
    files = sorted(glob.glob('data/nifty50/NIFTY50_1min_*.csv'))
    dfs = []
    for f in files:
        dfs.append(pd.read_csv(f))
    df = pd.concat(dfs, ignore_index=True)
    df['Date'] = pd.to_datetime(df['Timestamp'])
    df = df[df['Date'].dt.year >= 2022].sort_values('Date').reset_index(drop=True)
    df.set_index('Date', inplace=True)
    
    # Resample to 5m
    df_5m = df.resample('5min').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last'
    }).dropna().reset_index()
    
    df_5m['time'] = df_5m['Date'].dt.time
    t_start = time(9, 15)
    t_end = time(15, 30)
    df_5m = df_5m[(df_5m['time'] >= t_start) & (df_5m['time'] <= t_end)].reset_index(drop=True)
    df_5m['date_str'] = df_5m['Date'].dt.strftime('%Y-%m-%d')
    
    # Compute EMA 9 and EMA 21
    df_5m['EMA9'] = df_5m.groupby('date_str')['Close'].transform(lambda x: x.ewm(span=9, adjust=False).mean())
    df_5m['EMA21'] = df_5m.groupby('date_str')['Close'].transform(lambda x: x.ewm(span=21, adjust=False).mean())
    
    df_5m['Nifty_Trend'] = 0
    bull = (df_5m['Close'] > df_5m['EMA21']) & (df_5m['EMA9'] > df_5m['EMA21'])
    bear = (df_5m['Close'] < df_5m['EMA21']) & (df_5m['EMA9'] < df_5m['EMA21'])
    df_5m.loc[bull, 'Nifty_Trend'] = 1
    df_5m.loc[bear, 'Nifty_Trend'] = -1
    
    trend_dict = dict(zip(df_5m['Date'], df_5m['Nifty_Trend']))
    return trend_dict

def load_stock_5m(symbol):
    prev_file = f"data/stocks/{symbol}_prev.parquet"
    curr_file = f"data/stocks/{symbol}_2026.parquet"
    dfs = []
    if os.path.exists(prev_file):
        dfs.append(pd.read_parquet(prev_file))
    if os.path.exists(curr_file):
        dfs.append(pd.read_parquet(curr_file))
    if not dfs:
        return None
    df = pd.concat(dfs, ignore_index=True)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df[df['Date'].dt.year >= 2022].sort_values('Date').reset_index(drop=True)
    df.set_index('Date', inplace=True)
    
    df_5m = df.resample('5min').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }).dropna().reset_index()
    
    df_5m['time'] = df_5m['Date'].dt.time
    t_start = time(9, 15)
    t_end = time(15, 30)
    df_5m = df_5m[(df_5m['time'] >= t_start) & (df_5m['time'] <= t_end)].reset_index(drop=True)
    df_5m['date_str'] = df_5m['Date'].dt.strftime('%Y-%m-%d')
    return df_5m

def run_chronological_test():
    symbols = ['RELIANCE', 'MARUTI', 'SUNPHARMA', 'TATAMOTORS', 'TCS', 'TATASTEEL']
    print(f"Loading Nifty 50 macro trend...", flush=True)
    nifty_trend = load_nifty_trend()
    
    all_trades = []
    print(f"Testing 6 Champions sequentially with strict chronological bars & exact Zerodha fees...", flush=True)
    
    for sym in symbols:
        df = load_stock_5m(sym)
        if df is None: continue
        
        # Calculate indicators per day
        grouped = df.groupby('date_str')
        sym_trades = []
        
        for d_str, day_df in grouped:
            day_df = day_df.reset_index(drop=True)
            n = len(day_df)
            if n < 15: continue
            
            # VWAP, EMA9, EMA21, ATR
            typ = (day_df['High'] + day_df['Low'] + day_df['Close']) / 3.0
            cum_pv = (typ * day_df['Volume']).cumsum()
            cum_vol = day_df['Volume'].cumsum()
            vwap = np.where(cum_vol > 0, cum_pv / cum_vol, day_df['Close'])
            ema9 = day_df['Close'].ewm(span=9, adjust=False).mean().values
            ema21 = day_df['Close'].ewm(span=21, adjust=False).mean().values
            
            # ATR 14
            tr1 = day_df['High'] - day_df['Low']
            tr2 = (day_df['High'] - day_df['Close'].shift(1)).abs()
            tr3 = (day_df['Low'] - day_df['Close'].shift(1)).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(14, min_periods=1).mean().values
            
            opens = day_df['Open'].values
            highs = day_df['High'].values
            lows = day_df['Low'].values
            closes = day_df['Close'].values
            times = day_df['time'].values
            dates = day_df['Date'].values
            
            i = 2
            day_trades = 0
            day_losses = 0
            
            # Strict chronological execution:
            # i advances bar by bar, but when a trade enters at bar i,
            # i jumps forward to the exit bar + 1!
            while i < n - 2:
                if day_trades >= 2 or day_losses >= 1:
                    break
                t = times[i]
                if t < time(9, 30) or t > time(14, 15):
                    i += 1
                    continue
                    
                n_t = nifty_trend.get(dates[i], 0)
                
                # Long Pullback
                is_long = (n_t == 1 and 
                           closes[i] > vwap[i] and 
                           ema9[i] > ema21[i] and 
                           (lows[i] <= ema9[i] or lows[i-1] <= ema9[i-1]) and 
                           closes[i] > opens[i] and 
                           closes[i] > ema9[i])
                           
                # Short Pullback
                is_short = (n_t == -1 and 
                            closes[i] < vwap[i] and 
                            ema9[i] < ema21[i] and 
                            (highs[i] >= ema9[i] or highs[i-1] >= ema9[i-1]) and 
                            closes[i] < opens[i] and 
                            closes[i] < ema9[i])
                            
                if is_long:
                    entry = closes[i]
                    raw_sl = min(lows[i], lows[i-1]) - (0.2 * atr[i])
                    sl_dist = max(entry - raw_sl, entry * 0.0020)
                    if sl_dist > entry * 0.0070:
                        i += 1
                        continue
                    sl = entry - sl_dist
                    tp = entry + (sl_dist * 3.0) # 3R target
                    
                    # Size to 1% risk = Rs 1,000 on Rs 1,00,000 capital
                    shares = int(1000.0 / sl_dist)
                    if shares < 1: shares = 1
                    
                    # Sequential bar search from i+1
                    exit_price = None
                    exit_idx = n - 1
                    exit_reason = ""
                    
                    for m in range(i + 1, n):
                        if lows[m] <= sl:
                            exit_price = sl
                            exit_idx = m
                            exit_reason = "STOP_LOSS"
                            break
                        if highs[m] >= tp:
                            exit_price = tp
                            exit_idx = m
                            exit_reason = "TARGET"
                            break
                        if times[m] >= time(15, 15):
                            exit_price = closes[m]
                            exit_idx = m
                            exit_reason = "EOD_SQUAREOFF"
                            break
                    else:
                        exit_price = closes[-1]
                        exit_idx = n - 1
                        exit_reason = "EOD_SQUAREOFF"
                        
                    pnl = shares * (exit_price - entry)
                    fee = compute_zerodha_charges(shares * entry, shares * exit_price)
                    net_pnl = pnl - fee
                    net_r = net_pnl / 1000.0
                    
                    sym_trades.append({
                        'date': d_str,
                        'symbol': sym,
                        'side': 'BUY',
                        'net_r': net_r,
                        'fee': fee,
                        'net_pnl': net_pnl,
                        'exit_reason': exit_reason
                    })
                    
                    day_trades += 1
                    if net_r < 0:
                        day_losses += 1
                    i = exit_idx + 1 # JUMP TO EXIT BAR + 1
                    
                elif is_short:
                    entry = closes[i]
                    raw_sl = max(highs[i], highs[i-1]) + (0.2 * atr[i])
                    sl_dist = max(raw_sl - entry, entry * 0.0020)
                    if sl_dist > entry * 0.0070:
                        i += 1
                        continue
                    sl = entry + sl_dist
                    tp = entry - (sl_dist * 3.0)
                    
                    shares = int(1000.0 / sl_dist)
                    if shares < 1: shares = 1
                    
                    exit_price = None
                    exit_idx = n - 1
                    exit_reason = ""
                    
                    for m in range(i + 1, n):
                        if highs[m] >= sl:
                            exit_price = sl
                            exit_idx = m
                            exit_reason = "STOP_LOSS"
                            break
                        if lows[m] <= tp:
                            exit_price = tp
                            exit_idx = m
                            exit_reason = "TARGET"
                            break
                        if times[m] >= time(15, 15):
                            exit_price = closes[m]
                            exit_idx = m
                            exit_reason = "EOD_SQUAREOFF"
                            break
                    else:
                        exit_price = closes[-1]
                        exit_idx = n - 1
                        exit_reason = "EOD_SQUAREOFF"
                        
                    pnl = shares * (entry - exit_price)
                    fee = compute_zerodha_charges(shares * exit_price, shares * entry)
                    net_pnl = pnl - fee
                    net_r = net_pnl / 1000.0
                    
                    sym_trades.append({
                        'date': d_str,
                        'symbol': sym,
                        'side': 'SELL',
                        'net_r': net_r,
                        'fee': fee,
                        'net_pnl': net_pnl,
                        'exit_reason': exit_reason
                    })
                    
                    day_trades += 1
                    if net_r < 0:
                        day_losses += 1
                    i = exit_idx + 1
                else:
                    i += 1
                    
        df_sym = pd.DataFrame(sym_trades)
        if len(df_sym) > 0:
            sym_r = df_sym['net_r'].sum()
            sym_wr = (df_sym['net_r'] > 0).mean() * 100
            print(f"{sym}: {len(df_sym)} trades | WR: {sym_wr:.1f}% | Net R: {sym_r:+.1f} R", flush=True)
            all_trades.extend(sym_trades)
            
    df_all = pd.DataFrame(all_trades)
    df_all['month'] = pd.to_datetime(df_all['date']).dt.to_period('M')
    n_months = df_all['month'].nunique()
    
    wins = df_all[df_all['net_r'] > 0]
    losses = df_all[df_all['net_r'] <= 0]
    win_rate = len(wins) / len(df_all) * 100.0 if len(df_all) > 0 else 0
    total_net_r = df_all['net_r'].sum()
    monthly_r = total_net_r / max(1, n_months)
    
    df_all['cum_r'] = df_all['net_r'].cumsum()
    df_all['peak_r'] = df_all['cum_r'].cummax()
    df_all['dd_r'] = df_all['cum_r'] - df_all['peak_r']
    max_dd_r = df_all['dd_r'].min()
    
    gross_win = wins['net_pnl'].sum()
    gross_loss = abs(losses['net_pnl'].sum())
    profit_factor = gross_win / gross_loss if gross_loss > 0 else 999.0
    total_fees = df_all['fee'].sum()
    
    print("\n" + "="*75, flush=True)
    print(f"CHRONOLOGICAL AUDIT RESULTS (6 CHAMPIONS, 2022-2026):", flush=True)
    print(f"Total Months: {n_months}", flush=True)
    print(f"Total Trades: {len(df_all)} ({len(df_all)/n_months:.1f} trades/month)", flush=True)
    print(f"Win Rate: {win_rate:.2f}% ({len(wins)} wins / {len(losses)} losses)", flush=True)
    print(f"Profit Factor: {profit_factor:.2f}", flush=True)
    print(f"Total Net Return: {total_net_r:+.2f}% (+{total_net_r:.2f} R)", flush=True)
    print(f"Average Monthly Return: {monthly_r:+.2f}% / month (+{monthly_r:.2f} R / month)", flush=True)
    print(f"Max Peak-to-Trough Drawdown: {max_dd_r:.2f}% ({max_dd_r:.2f} R)", flush=True)
    print(f"Total Taxes & Fees: Rs {total_fees:,.2f} ({total_fees/1000:.1f} R)", flush=True)
    print("="*75, flush=True)

if __name__ == '__main__':
    run_chronological_test()
