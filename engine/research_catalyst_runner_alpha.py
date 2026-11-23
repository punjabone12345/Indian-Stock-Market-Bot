"""
Research Engine: Asymmetric Catalyst Breakout with Dynamic Runners
Multi-Asset (30 Nifty Stocks), 2022-2026 (4+ Years)
Testing Bi-directional (Long + Short) Catalyst ORB + Tight Structural Stops + Runners
With 100% exact Zerodha statutory tariffs.
"""

import os
import glob
import numpy as np
import pandas as pd
from datetime import datetime

def compute_zerodha_charges(buy_val, sell_val):
    # Brokerage: min(20, 0.03% of val) on buy and sell
    b_buy = min(20.0, buy_val * 0.0003)
    b_sell = min(20.0, sell_val * 0.0003)
    brokerage = b_buy + b_sell
    
    # STT: 0.025% on sell side for intraday equity
    stt = sell_val * 0.00025
    
    # Exchange turnover charges: 0.00297%
    exchange = (buy_val + sell_val) * 0.0000297
    
    # SEBI: 10 per crore (0.000001)
    sebi = (buy_val + sell_val) * 0.000001
    
    # Stamp duty: 0.003% on buy side
    stamp = buy_val * 0.00003
    
    # GST: 18% on (Brokerage + Exchange + SEBI)
    gst = (brokerage + exchange + sebi) * 0.18
    
    total = brokerage + stt + exchange + sebi + stamp + gst
    return total

def load_symbol_5m(symbol, start_year=2022):
    # Load 1m data and resample to 5m
    prev_file = f"data/stocks/{symbol}_prev.parquet"
    curr_file = f"data/stocks/{symbol}_2026.parquet"
    
    dfs = []
    if os.path.exists(prev_file):
        df_p = pd.read_parquet(prev_file)
        dfs.append(df_p)
    if os.path.exists(curr_file):
        df_c = pd.read_parquet(curr_file)
        dfs.append(df_c)
        
    if not dfs:
        return None
        
    df = pd.concat(dfs, ignore_index=True)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df[df['Date'].dt.year >= start_year].sort_values('Date').reset_index(drop=True)
    
    # Resample to 5m
    df.set_index('Date', inplace=True)
    df_5m = df.resample('5min').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }).dropna().reset_index()
    
    # Filter market hours 09:15 to 15:30
    df_5m['time'] = df_5m['Date'].dt.time
    t_start = datetime.strptime("09:15", "%H:%M").time()
    t_end = datetime.strptime("15:30", "%H:%M").time()
    df_5m = df_5m[(df_5m['time'] >= t_start) & (df_5m['time'] <= t_end)].reset_index(drop=True)
    df_5m['date_str'] = df_5m['Date'].dt.strftime('%Y-%m-%d')
    return df_5m

def run_simulation():
    symbols = [
        'ADANIENT', 'AXISBANK', 'BAJFINANCE', 'BHARTIARTL', 'COALINDIA', 
        'GRASIM', 'HCLTECH', 'HDFCBANK', 'HINDUNILVR', 'ICICIBANK', 
        'INDUSINDBK', 'INFY', 'ITC', 'JSWSTEEL', 'KOTAKBANK', 
        'LT', 'MARUTI', 'NTPC', 'ONGC', 'POWERGRID', 
        'RELIANCE', 'SBIN', 'SUNPHARMA', 'TATAMOTORS', 'TATASTEEL', 
        'TCS', 'TECHM', 'TITAN', 'ULTRACEMCO', 'WIPRO'
    ]
    
    all_trades = []
    print(f"Loading and processing {len(symbols)} symbols from 2022 to 2026...")
    
    for sym_idx, sym in enumerate(symbols):
        df = load_symbol_5m(sym, start_year=2022)
        if df is None or len(df) == 0:
            continue
            
        print(f"[{sym_idx+1}/{len(symbols)}] Processing {sym} ({len(df)} 5m bars)...")
        
        # Group by day
        grouped = df.groupby('date_str')
        prev_day_close = None
        opening_volumes = [] # for RVOL calculation
        
        for date_str, day_df in grouped:
            day_df = day_df.reset_index(drop=True)
            if len(day_df) < 15: # Not a full day
                if len(day_df) > 0:
                    prev_day_close = day_df.iloc[-1]['Close']
                continue
                
            # First 3 bars are 09:15, 09:20, 09:25 (Opening Range 09:15-09:30)
            or_bars = day_df.iloc[0:3]
            or_high = or_bars['High'].max()
            or_low = or_bars['Low'].min()
            or_mid = (or_high + or_low) / 2.0
            or_vol = or_bars['Volume'].sum()
            
            # Gap calculation
            open_p = day_df.iloc[0]['Open']
            gap_pct = 0.0
            if prev_day_close is not None and prev_day_close > 0:
                gap_pct = (open_p - prev_day_close) / prev_day_close * 100.0
                
            # RVOL calculation (against rolling average of last 20 sessions OR volume)
            rvol = 1.0
            if len(opening_volumes) >= 10:
                avg_vol = np.mean(opening_volumes[-20:])
                if avg_vol > 0:
                    rvol = or_vol / avg_vol
            opening_volumes.append(or_vol)
            prev_day_close = day_df.iloc[-1]['Close']
            
            # Cumulative VWAP for the day
            typical_price = (day_df['High'] + day_df['Low'] + day_df['Close']) / 3.0
            cum_pv = (typical_price * day_df['Volume']).cumsum()
            cum_vol = day_df['Volume'].cumsum()
            vwap = np.where(cum_vol > 0, cum_pv / cum_vol, day_df['Close'])
            
            # Scan for entry from bar 3 (09:30) to bar 24 (11:15)
            # Only 1 trade per symbol per day
            traded_today = False
            
            for i in range(3, min(25, len(day_df) - 6)):
                if traded_today:
                    break
                    
                bar = day_df.iloc[i]
                bar_close = bar['Close']
                bar_high = bar['High']
                bar_low = bar['Low']
                curr_vwap = vwap[i]
                
                # Check Long setup
                # 1. ORB Breakout: Close > or_high
                # 2. Catalyst: gap_pct >= +0.2% OR rvol >= 1.2
                # 3. Institutional alignment: Close > curr_vwap
                long_trigger = (bar_close > or_high) and (gap_pct >= 0.2 or rvol >= 1.2) and (bar_close > curr_vwap)
                
                # Check Short setup
                # 1. ORB Breakdown: Close < or_low
                # 2. Catalyst: gap_pct <= -0.2% OR rvol >= 1.2
                # 3. Institutional alignment: Close < curr_vwap
                short_trigger = (bar_close < or_low) and (gap_pct <= -0.2 or rvol >= 1.2) and (bar_close < curr_vwap)
                
                if long_trigger:
                    entry_price = bar_close
                    # Tight structural stop: minimum of bar_low or or_mid
                    # but stop must be at least 0.25% and at most 1.2%
                    raw_stop = max(or_mid, bar_low)
                    if (entry_price - raw_stop) / entry_price < 0.0025:
                        raw_stop = entry_price * (1.0 - 0.0025)
                    if (entry_price - raw_stop) / entry_price > 0.012:
                        raw_stop = entry_price * (1.0 - 0.012)
                        
                    stop_loss = raw_stop
                    risk_pts = entry_price - stop_loss
                    if risk_pts <= 0:
                        continue
                        
                    target_1 = entry_price + (2.0 * risk_pts) # T1 = 2R
                    traded_today = True
                    
                    # Track trade forward bar by bar
                    t1_hit = False
                    exit_price_t1 = 0.0
                    exit_bar_t1 = -1
                    exit_price_runner = 0.0
                    exit_bar_runner = -1
                    exit_reason = ""
                    
                    # Assume risk capital R = Rs 500 per trade
                    # Position sizing: shares = R / risk_pts
                    shares = int(500.0 / risk_pts)
                    if shares < 1:
                        shares = 1
                    half_shares = shares // 2
                    runner_shares = shares - half_shares
                    if half_shares < 1:
                        half_shares = 1
                        runner_shares = 0
                        
                    current_sl = stop_loss
                    
                    for j in range(i + 1, len(day_df)):
                        f_bar = day_df.iloc[j]
                        f_high = f_bar['High']
                        f_low = f_bar['Low']
                        f_close = f_bar['Close']
                        
                        # Check stop loss first
                        if f_low <= current_sl:
                            # Stopped out
                            if not t1_hit:
                                # Both parts stopped at initial SL
                                exit_price_t1 = current_sl
                                exit_price_runner = current_sl
                                exit_reason = "STOP_INITIAL"
                            else:
                                # Runner stopped at breakeven
                                exit_price_runner = current_sl
                                exit_reason = "RUNNER_BE_STOP"
                            exit_bar_runner = j
                            break
                            
                        # Check Target 1 if not yet hit
                        if not t1_hit and f_high >= target_1:
                            t1_hit = True
                            exit_price_t1 = target_1
                            exit_bar_t1 = j
                            # Move SL to Entry (Breakeven) for the runner
                            current_sl = entry_price
                            
                        # If runner is still active, check EMA 9 trailing exit after 13:00
                        if t1_hit and j >= 45: # After 13:00 (bar 45)
                            # If close drops below vwap or bar_low of previous bar
                            if f_close < vwap[j]:
                                exit_price_runner = f_close
                                exit_reason = "RUNNER_VWAP_TRAIL"
                                exit_bar_runner = j
                                break
                                
                        # End of day square off at 15:15 (bar 72)
                        if j == len(day_df) - 1 or j >= 72:
                            if not t1_hit:
                                exit_price_t1 = f_close
                            exit_price_runner = f_close
                            exit_reason = "EOD_SQUAREOFF"
                            exit_bar_runner = j
                            break
                            
                    # Calculate PnL
                    # Part 1:
                    p1_pnl = half_shares * (exit_price_t1 - entry_price)
                    p1_buy = half_shares * entry_price
                    p1_sell = half_shares * exit_price_t1
                    p1_fee = compute_zerodha_charges(p1_buy, p1_sell)
                    
                    # Part 2 (Runner):
                    if runner_shares > 0:
                        p2_pnl = runner_shares * (exit_price_runner - entry_price)
                        p2_buy = runner_shares * entry_price
                        p2_sell = runner_shares * exit_price_runner
                        p2_fee = compute_zerodha_charges(p2_buy, p2_sell)
                    else:
                        p2_pnl = 0.0
                        p2_fee = 0.0
                        
                    gross_pnl = p1_pnl + p2_pnl
                    total_fee = p1_fee + p2_fee
                    net_pnl = gross_pnl - total_fee
                    net_r = net_pnl / 500.0
                    
                    all_trades.append({
                        'date': date_str,
                        'symbol': sym,
                        'side': 'BUY',
                        'entry_time': bar['Date'],
                        'entry_price': entry_price,
                        'stop_loss': stop_loss,
                        'target_1': target_1,
                        't1_hit': t1_hit,
                        'exit_reason': exit_reason,
                        'shares': shares,
                        'gross_pnl': gross_pnl,
                        'fee': total_fee,
                        'net_pnl': net_pnl,
                        'net_r': net_r,
                        'risk_pct': risk_pts / entry_price * 100.0
                    })
                    
                elif short_trigger:
                    entry_price = bar_close
                    # Tight structural stop: minimum of bar_high or or_mid
                    raw_stop = min(or_mid, bar_high)
                    if (raw_stop - entry_price) / entry_price < 0.0025:
                        raw_stop = entry_price * (1.0 + 0.0025)
                    if (raw_stop - entry_price) / entry_price > 0.012:
                        raw_stop = entry_price * (1.0 + 0.012)
                        
                    stop_loss = raw_stop
                    risk_pts = stop_loss - entry_price
                    if risk_pts <= 0:
                        continue
                        
                    target_1 = entry_price - (2.0 * risk_pts) # T1 = 2R
                    traded_today = True
                    
                    # Position sizing: shares = R / risk_pts
                    shares = int(500.0 / risk_pts)
                    if shares < 1:
                        shares = 1
                    half_shares = shares // 2
                    runner_shares = shares - half_shares
                    if half_shares < 1:
                        half_shares = 1
                        runner_shares = 0
                        
                    current_sl = stop_loss
                    t1_hit = False
                    exit_price_t1 = 0.0
                    exit_price_runner = 0.0
                    exit_reason = ""
                    
                    for j in range(i + 1, len(day_df)):
                        f_bar = day_df.iloc[j]
                        f_high = f_bar['High']
                        f_low = f_bar['Low']
                        f_close = f_bar['Close']
                        
                        # Check stop loss first (for short, high >= stop)
                        if f_high >= current_sl:
                            if not t1_hit:
                                exit_price_t1 = current_sl
                                exit_price_runner = current_sl
                                exit_reason = "STOP_INITIAL"
                            else:
                                exit_price_runner = current_sl
                                exit_reason = "RUNNER_BE_STOP"
                            break
                            
                        # Check Target 1 if not yet hit (for short, low <= target_1)
                        if not t1_hit and f_low <= target_1:
                            t1_hit = True
                            exit_price_t1 = target_1
                            # Move SL to Entry (Breakeven) for the runner
                            current_sl = entry_price
                            
                        # If runner is still active, check VWAP trailing exit after 13:00
                        if t1_hit and j >= 45:
                            if f_close > vwap[j]:
                                exit_price_runner = f_close
                                exit_reason = "RUNNER_VWAP_TRAIL"
                                break
                                
                        # End of day square off at 15:15 (bar 72)
                        if j == len(day_df) - 1 or j >= 72:
                            if not t1_hit:
                                exit_price_t1 = f_close
                            exit_price_runner = f_close
                            exit_reason = "EOD_SQUAREOFF"
                            break
                            
                    # Calculate PnL for Short
                    # For short: PnL = shares * (entry_price - exit_price)
                    p1_pnl = half_shares * (entry_price - exit_price_t1)
                    p1_sell = half_shares * entry_price
                    p1_buy = half_shares * exit_price_t1
                    p1_fee = compute_zerodha_charges(p1_buy, p1_sell)
                    
                    if runner_shares > 0:
                        p2_pnl = runner_shares * (entry_price - exit_price_runner)
                        p2_sell = runner_shares * entry_price
                        p2_buy = runner_shares * exit_price_runner
                        p2_fee = compute_zerodha_charges(p2_buy, p2_sell)
                    else:
                        p2_pnl = 0.0
                        p2_fee = 0.0
                        
                    gross_pnl = p1_pnl + p2_pnl
                    total_fee = p1_fee + p2_fee
                    net_pnl = gross_pnl - total_fee
                    net_r = net_pnl / 500.0
                    
                    all_trades.append({
                        'date': date_str,
                        'symbol': sym,
                        'side': 'SELL',
                        'entry_time': bar['Date'],
                        'entry_price': entry_price,
                        'stop_loss': stop_loss,
                        'target_1': target_1,
                        't1_hit': t1_hit,
                        'exit_reason': exit_reason,
                        'shares': shares,
                        'gross_pnl': gross_pnl,
                        'fee': total_fee,
                        'net_pnl': net_pnl,
                        'net_r': net_r,
                        'risk_pct': risk_pts / entry_price * 100.0
                    })
                    
    df_trades = pd.DataFrame(all_trades)
    print("\n" + "="*70)
    print("BACKTEST RESULTS (2022 - 2026):")
    print(f"Total Trades Taken: {len(df_trades)}")
    
    if len(df_trades) == 0:
        print("No trades generated.")
        return
        
    df_trades['month'] = pd.to_datetime(df_trades['date']).dt.to_period('M')
    n_months = df_trades['month'].nunique()
    
    wins = df_trades[df_trades['net_r'] > 0]
    losses = df_trades[df_trades['net_r'] <= 0]
    win_rate = len(wins) / len(df_trades) * 100.0
    
    total_net_r = df_trades['net_r'].sum()
    monthly_r = total_net_r / max(1, n_months)
    
    # Cumulative Drawdown
    df_trades['cum_r'] = df_trades['net_r'].cumsum()
    df_trades['peak_r'] = df_trades['cum_r'].cummax()
    df_trades['dd_r'] = df_trades['cum_r'] - df_trades['peak_r']
    max_dd_r = df_trades['dd_r'].min()
    
    # Gross Win / Gross Loss Profit Factor
    gross_win = wins['net_pnl'].sum()
    gross_loss = abs(losses['net_pnl'].sum())
    profit_factor = gross_win / gross_loss if gross_loss > 0 else 999.0
    
    total_fees = df_trades['fee'].sum()
    
    print(f"Total Months: {n_months}")
    print(f"Win Rate: {win_rate:.2f}% ({len(wins)} wins / {len(losses)} losses)")
    print(f"Profit Factor: {profit_factor:.2f}")
    print(f"Total Net R: {total_net_r:+.2f} R")
    print(f"Average Monthly R: {monthly_r:+.2f} R / month")
    print(f"Max Peak-to-Trough Drawdown: {max_dd_r:.2f} R")
    print(f"Total Fees & Taxes Paid: Rs {total_fees:,.2f} ({total_fees/500:.1f} R)")
    print("="*70)
    
    # Monthly Breakdown
    monthly = df_trades.groupby('month').agg(
        trades=('net_r', 'count'),
        win_rate=('net_r', lambda x: (x > 0).mean() * 100),
        net_r=('net_r', 'sum'),
        fees=('fee', 'sum')
    )
    print("\nMONTHLY BREAKDOWN (First 12 months & Last 6 months):")
    print(pd.concat([monthly.head(12), monthly.tail(6)]))
    
    # Breakdown by Side
    side_grp = df_trades.groupby('side').agg(
        trades=('net_r', 'count'),
        win_rate=('net_r', lambda x: (x > 0).mean() * 100),
        net_r=('net_r', 'sum')
    )
    print("\nPERFORMANCE BY SIDE (BUY vs SELL):")
    print(side_grp)
    
    # Breakdown by Exit Reason
    exit_grp = df_trades.groupby('exit_reason').agg(
        trades=('net_r', 'count'),
        avg_r=('net_r', 'mean'),
        net_r=('net_r', 'sum')
    )
    print("\nPERFORMANCE BY EXIT REASON:")
    print(exit_grp)

if __name__ == '__main__':
    run_simulation()
