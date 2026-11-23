"""
Empirical Test of User's Gap Concept (Gap Fade vs Gap Momentum)
Universe: 30 Liquid NSE Equities (2022 - 2026, 4.8 Years, 1,182 trading sessions)
Taxes: Exact Zerodha statutory charges down to the paisa (brokerage, STT, exchange, SEBI, stamp duty, GST)

Concept:
At 09:30 AM:
15-min candle (bars 09:15, 09:20, 09:25):
Gap % = (Close_0930 - Prev_Day_Close) / Prev_Day_Close * 100
Range_15m = High_15m - Low_15m
SL_pts = Range_15m * 0.50

User's Example:
RELIANCE prev close = 1400, 09:30 close = 1372 (Gap down 2%).
15m High = 1394, Low = 1370. Range = 24. SL_pts = 12.
Took BUY trade at 1372, SL = 1360. Target = 1:2, 1:3, 1:4, 1:5.

We test:
1. Pure Gap Fade (Gap down -> BUY; Gap up -> SELL) at 1:2, 1:3, 1:4, 1:5
2. Pure Gap Momentum (Gap up -> BUY; Gap down -> SELL) at 1:2, 1:3, 1:4, 1:5
3. Pick #1 Biggest Gap vs All Gaps
"""

import os
import glob
import numpy as np
import pandas as pd
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
    if os.path.exists(prev_file):
        dfs.append(pd.read_parquet(prev_file))
    if os.path.exists(curr_file):
        dfs.append(pd.read_parquet(curr_file))
    if not dfs:
        return None
        
    df = pd.concat(dfs, ignore_index=True)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df[df['Date'].dt.year >= 2021].sort_values('Date').reset_index(drop=True)
    df.set_index('Date', inplace=True)
    
    t_start = time(9, 15)
    t_end = time(15, 30)
    
    df_5m = df.resample('5min').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }).dropna().reset_index()
    
    df_5m['time'] = df_5m['Date'].dt.time
    df_5m = df_5m[(df_5m['time'] >= t_start) & (df_5m['time'] <= t_end)].reset_index(drop=True)
    df_5m['date_str'] = df_5m['Date'].dt.strftime('%Y-%m-%d')
    return df_5m

def run_tests():
    symbols = [
        'ADANIENT', 'AXISBANK', 'BAJFINANCE', 'BHARTIARTL', 'COALINDIA', 
        'GRASIM', 'HCLTECH', 'HDFCBANK', 'HINDUNILVR', 'ICICIBANK', 
        'INDUSINDBK', 'INFY', 'ITC', 'JSWSTEEL', 'KOTAKBANK', 
        'LT', 'MARUTI', 'NTPC', 'ONGC', 'POWERGRID', 
        'RELIANCE', 'SBIN', 'SUNPHARMA', 'TATAMOTORS', 'TATASTEEL', 
        'TCS', 'TECHM', 'TITAN', 'ULTRACEMCO', 'WIPRO'
    ]
    
    print("Loading 30 symbols...", flush=True)
    symbol_days = {}
    all_dates = set()
    
    for sym in symbols:
        df = load_symbol_5m(sym)
        if df is None or len(df) == 0: continue
        symbol_days[sym] = {}
        grouped = df.groupby('date_str')
        prev_close = None
        
        for d_str, d_df in grouped:
            d_df = d_df.reset_index(drop=True)
            if len(d_df) < 25:
                if len(d_df) > 0: prev_close = d_df.iloc[-1]['Close']
                continue
                
            close_p = d_df.iloc[-1]['Close']
            
            # 15m candle is the first 3 bars (0, 1, 2)
            c15 = d_df.iloc[0:3]
            open_15m = c15.iloc[0]['Open']
            high_15m = c15['High'].max()
            low_15m = c15['Low'].min()
            close_15m = c15.iloc[-1]['Close']
            range_15m = high_15m - low_15m
            
            gap_pct = 0.0
            if prev_close is not None and prev_close > 0:
                gap_pct = (close_15m - prev_close) / prev_close * 100.0
                
            prev_close = close_p
            year = int(d_str[:4])
            if year >= 2022:
                all_dates.add(d_str)
                symbol_days[sym][d_str] = {
                    'df': d_df,
                    'open_15m': open_15m,
                    'high_15m': high_15m,
                    'low_15m': low_15m,
                    'close_15m': close_15m,
                    'range_15m': range_15m,
                    'gap_pct': gap_pct
                }
                
    sorted_dates = sorted(list(all_dates))
    print(f"Total dates: {len(sorted_dates)} (4.8 Years)", flush=True)
    
    # We test RR ratios: 2, 3, 4, 5
    # And modes: 'FADE' vs 'MOMENTUM'
    for mode in ['FADE', 'MOMENTUM']:
        print(f"\n=======================================================")
        print(f"MODE: {mode} (Gap > 1.0%, SL = 50% of 15m Range)")
        print(f"=======================================================")
        
        for rr in [2.0, 3.0, 4.0, 5.0]:
            trades = []
            
            for date_str in sorted_dates:
                candidates = []
                for sym, d_dict in symbol_days.items():
                    if date_str not in d_dict: continue
                    info = d_dict[date_str]
                    gap_pct = info['gap_pct']
                    range_15m = info['range_15m']
                    close_15m = info['close_15m']
                    
                    if abs(gap_pct) < 1.0: continue
                    if range_15m <= 0: continue
                    
                    sl_pts = range_15m * 0.50
                    if sl_pts <= 0: continue
                    
                    # Minimum SL sanity: at least 0.25% of price to prevent zero-risk division
                    if sl_pts / close_15m < 0.0025:
                        sl_pts = close_15m * 0.0025
                        
                    if mode == 'FADE':
                        # Gap Down -> BUY (Mean-Reversion)
                        if gap_pct <= -1.0:
                            side = 'BUY'
                            entry_p = close_15m
                            sl_p = entry_p - sl_pts
                            tp_p = entry_p + (rr * sl_pts)
                        # Gap Up -> SELL (Mean-Reversion)
                        else:
                            side = 'SELL'
                            entry_p = close_15m
                            sl_p = entry_p + sl_pts
                            tp_p = entry_p - (rr * sl_pts)
                    else: # MOMENTUM
                        # Gap Up -> BUY (Trend following)
                        if gap_pct >= 1.0:
                            side = 'BUY'
                            entry_p = close_15m
                            sl_p = entry_p - sl_pts
                            tp_p = entry_p + (rr * sl_pts)
                        # Gap Down -> SELL (Trend following)
                        else:
                            side = 'SELL'
                            entry_p = close_15m
                            sl_p = entry_p + sl_pts
                            tp_p = entry_p - (rr * sl_pts)
                            
                    candidates.append({
                        'symbol': sym,
                        'side': side,
                        'entry_p': entry_p,
                        'sl_p': sl_p,
                        'tp_p': tp_p,
                        'sl_pts': sl_pts,
                        'gap_pct': gap_pct,
                        'df': info['df']
                    })
                    
                if not candidates: continue
                
                # Pick the #1 stock with biggest gap (>1%)
                candidates.sort(key=lambda x: -abs(x['gap_pct']))
                trade = candidates[0]
                
                sym = trade['symbol']
                side = trade['side']
                entry_p = trade['entry_p']
                sl_p = trade['sl_p']
                tp_p = trade['tp_p']
                sl_pts = trade['sl_pts']
                d_df = trade['df']
                
                # 1.0% risk = Rs 1,000 on Rs 100,000 capital
                shares = int(1000.0 / sl_pts)
                if shares < 1: shares = 1
                
                exit_p = entry_p
                hit = False
                
                # Bars from index 3 (09:30 AM) onward
                for j in range(3, len(d_df)):
                    bar = d_df.iloc[j]
                    h, l, c = bar['High'], bar['Low'], bar['Close']
                    
                    if side == 'BUY':
                        if l <= sl_p:
                            exit_p = sl_p
                            hit = True
                            break
                        elif h >= tp_p:
                            exit_p = tp_p
                            hit = True
                            break
                    else: # SELL
                        if h >= sl_p:
                            exit_p = sl_p
                            hit = True
                            break
                        elif l <= tp_p:
                            exit_p = tp_p
                            hit = True
                            break
                            
                    if j == len(d_df) - 1 or j >= 72:
                        exit_p = c
                        hit = True
                        break
                        
                if not hit: exit_p = d_df.iloc[-1]['Close']
                
                if side == 'BUY':
                    gross_pnl = shares * (exit_p - entry_p)
                    fee = compute_zerodha_charges(shares * entry_p, shares * exit_p)
                else:
                    gross_pnl = shares * (entry_p - exit_p)
                    fee = compute_zerodha_charges(shares * exit_p, shares * entry_p)
                    
                net_pnl = gross_pnl - fee
                ret_pct = net_pnl / 1000.0
                
                trades.append({
                    'date': date_str,
                    'symbol': sym,
                    'side': side,
                    'net_pnl': net_pnl,
                    'ret_pct': ret_pct,
                    'fee': fee
                })
                
            df_t = pd.DataFrame(trades)
            if len(df_t) == 0:
                print(f"RR 1:{rr:.1f} -> No trades found!")
                continue
                
            df_t['month'] = pd.to_datetime(df_t['date']).dt.to_period('M')
            n_months = df_t['month'].nunique()
            wins = df_t[df_t['ret_pct'] > 0]
            losses = df_t[df_t['ret_pct'] <= 0]
            win_rate = len(wins) / len(df_t) * 100.0
            total_ret = df_t['ret_pct'].sum()
            monthly_ret = total_ret / max(1, n_months)
            
            df_t['cum'] = df_t['ret_pct'].cumsum()
            df_t['peak'] = df_t['cum'].cummax()
            df_t['dd'] = df_t['cum'] - df_t['peak']
            max_dd = df_t['dd'].min()
            
            gw = wins['net_pnl'].sum()
            gl = abs(losses['net_pnl'].sum())
            pf = gw / gl if gl > 0 else 999.0
            total_fee = df_t['fee'].sum()
            
            print(f"RR 1:{rr:.1f} | Trades: {len(df_t)} ({len(df_t)/n_months:.1f}/mo) | WinRate: {win_rate:5.2f}% | PF: {pf:4.2f} | Net: {total_ret:+7.2f}% | MoRet: {monthly_ret:+5.2f}% | MaxDD: {max_dd:6.2f}% | Fees: Rs {total_fee:,.0f}", flush=True)

if __name__ == '__main__':
    run_tests()
