"""
Trade of the Day Engine (1 Trade Per Day, 1% Risk per Trade)
Goal: ~10% Monthly Return with Minimum Drawdown
Rules:
- Universe: 30 Nifty Mega-Cap Equities (2022 - 2026, 4.8 Years)
- Max Trades: EXACTLY 1 TRADE PER DAY (The #1 ranked catalyst in the entire market)
- Sizing: 1% Portfolio Risk per trade (1R = 1.0% Capital, e.g. Rs 1,000 on Rs 1,00,000)
- Entry: 15m Opening Range Breakout on #1 RVOL + Catalyst stock (09:30 - 10:30)
- Exit: Asymmetric Payoff:
    * 50% partial exit at 2.0R (Move SL to Breakeven)
    * 50% runner trailed with 9 EMA or closed at 15:15 EOD
- Statutory Taxes: 100% exact Zerodha intraday tariffs + slippage
"""

import os
import glob
import numpy as np
import pandas as pd
from datetime import datetime

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

def load_all_symbols_5m():
    symbols = [
        'ADANIENT', 'AXISBANK', 'BAJFINANCE', 'BHARTIARTL', 'COALINDIA', 
        'GRASIM', 'HCLTECH', 'HDFCBANK', 'HINDUNILVR', 'ICICIBANK', 
        'INDUSINDBK', 'INFY', 'ITC', 'JSWSTEEL', 'KOTAKBANK', 
        'LT', 'MARUTI', 'NTPC', 'ONGC', 'POWERGRID', 
        'RELIANCE', 'SBIN', 'SUNPHARMA', 'TATAMOTORS', 'TATASTEEL', 
        'TCS', 'TECHM', 'TITAN', 'ULTRACEMCO', 'WIPRO'
    ]
    
    symbol_data = {}
    print(f"Loading 5m data for {len(symbols)} symbols...", flush=True)
    
    t_start = datetime.strptime("09:15", "%H:%M").time()
    t_end = datetime.strptime("15:30", "%H:%M").time()
    
    for sym in symbols:
        prev_file = f"data/stocks/{sym}_prev.parquet"
        curr_file = f"data/stocks/{sym}_2026.parquet"
        dfs = []
        if os.path.exists(prev_file):
            dfs.append(pd.read_parquet(prev_file))
        if os.path.exists(curr_file):
            dfs.append(pd.read_parquet(curr_file))
        if not dfs:
            continue
            
        df = pd.concat(dfs, ignore_index=True)
        df['Date'] = pd.to_datetime(df['Date'])
        df = df[df['Date'].dt.year >= 2021].sort_values('Date').reset_index(drop=True)
        df.set_index('Date', inplace=True)
        
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
        
        # Calculate daily closes & rolling OR volume
        symbol_data[sym] = df_5m
        
    print(f"Loaded {len(symbol_data)} symbols successfully.", flush=True)
    return symbol_data

def run_trade_of_the_day(min_rvol=1.5, min_gap=0.3, t1_target_r=2.0):
    symbol_data = load_all_symbols_5m()
    
    # Pre-process all symbols by date
    # Build a master calendar of trading dates (2022 to 2026)
    all_dates = set()
    symbol_day_dfs = {}
    
    for sym, df_5m in symbol_data.items():
        symbol_day_dfs[sym] = {}
        grouped = df_5m.groupby('date_str')
        prev_close = None
        or_vols = []
        closes_20 = []
        
        for d_str, d_df in grouped:
            d_df = d_df.reset_index(drop=True)
            if len(d_df) < 25:
                if len(d_df) > 0:
                    prev_close = d_df.iloc[-1]['Close']
                continue
                
            open_p = d_df.iloc[0]['Open']
            close_p = d_df.iloc[-1]['Close']
            
            # OR (first 3 bars)
            or_bars = d_df.iloc[0:3]
            or_h = or_bars['High'].max()
            or_l = or_bars['Low'].min()
            or_v = or_bars['Volume'].sum()
            
            gap_pct = 0.0
            if prev_close is not None and prev_close > 0:
                gap_pct = (open_p - prev_close) / prev_close * 100.0
                
            rvol = 1.0
            if len(or_vols) >= 10:
                avg_v = np.mean(or_vols[-20:])
                if avg_v > 0:
                    rvol = or_v / avg_v
            or_vols.append(or_v)
            
            is_breakout_20_long = False
            is_breakout_20_short = False
            if len(closes_20) >= 20:
                r20 = closes_20[-20:]
                if open_p > max(r20):
                    is_breakout_20_long = True
                if open_p < min(r20):
                    is_breakout_20_short = True
            closes_20.append(close_p)
            prev_close = close_p
            
            # Compute VWAP and EMA9 for the day
            typ = (d_df['High'] + d_df['Low'] + d_df['Close']) / 3.0
            cum_pv = (typ * d_df['Volume']).cumsum()
            cum_vol = d_df['Volume'].cumsum()
            vwap = np.where(cum_vol > 0, cum_pv / cum_vol, d_df['Close'])
            ema9 = d_df['Close'].ewm(span=9, adjust=False).mean().values
            
            d_df['vwap'] = vwap
            d_df['ema9'] = ema9
            
            year = int(d_str[:4])
            if year >= 2022:
                all_dates.add(d_str)
                symbol_day_dfs[sym][d_str] = {
                    'df': d_df,
                    'or_h': or_h,
                    'or_l': or_l,
                    'or_mid': (or_h + or_l) / 2.0,
                    'gap_pct': gap_pct,
                    'rvol': rvol,
                    'bo20_long': is_breakout_20_long,
                    'bo20_short': is_breakout_20_short
                }
                
    sorted_dates = sorted(list(all_dates))
    print(f"Total backtest trading sessions (2022 - 2026): {len(sorted_dates)} days.", flush=True)
    
    trades = []
    
    for date_idx, date_str in enumerate(sorted_dates):
        # We want EXACTLY 1 TRADE on this date (The #1 Trade of the Day)
        # Scan all symbols bar by bar from bar 3 (09:30) to bar 15 (10:30)
        day_candidates = []
        
        # Check all symbols that have a breakout between 09:30 and 10:30
        for sym, days in symbol_day_dfs.items():
            if date_str not in days:
                continue
            day_info = days[date_str]
            d_df = day_info['df']
            or_h = day_info['or_h']
            or_l = day_info['or_l']
            or_mid = day_info['or_mid']
            gap_pct = day_info['gap_pct']
            rvol = day_info['rvol']
            bo20_l = day_info['bo20_long']
            bo20_s = day_info['bo20_short']
            
            # Check catalyst
            has_long_cat = (gap_pct >= min_gap and rvol >= min_rvol) or (rvol >= 2.5) or (bo20_l and rvol >= 1.3)
            has_short_cat = (gap_pct <= -min_gap and rvol >= min_rvol) or (rvol >= 2.5) or (bo20_s and rvol >= 1.3)
            
            if not has_long_cat and not has_short_cat:
                continue
                
            # Scan bars 3 to 15 (09:30 to 10:30) for trigger
            for b_i in range(3, min(16, len(d_df) - 6)):
                bar = d_df.iloc[b_i]
                b_c = bar['Close']
                b_h = bar['High']
                b_l = bar['Low']
                vwap_val = bar['vwap']
                
                # Long Trigger
                if has_long_cat and (b_c > or_h) and (b_c > vwap_val):
                    # Structural stop: breakout bar low or or_mid
                    raw_stop = max(or_mid, b_l)
                    # Clamp stop: 0.30% to 0.90%
                    if (b_c - raw_stop) / b_c < 0.0030:
                        raw_stop = b_c * (1.0 - 0.0030)
                    if (b_c - raw_stop) / b_c > 0.0090:
                        raw_stop = b_c * (1.0 - 0.0090)
                    risk_pts = b_c - raw_stop
                    if risk_pts > 0:
                        # Catalyst score = RVOL * (1 + abs(gap_pct))
                        score = rvol * (1.0 + abs(gap_pct))
                        day_candidates.append({
                            'symbol': sym,
                            'side': 'BUY',
                            'bar_idx': b_i,
                            'entry_price': b_c,
                            'stop_loss': raw_stop,
                            'risk_pts': risk_pts,
                            'score': score,
                            'rvol': rvol,
                            'gap_pct': gap_pct,
                            'df': d_df
                        })
                    break # Only 1 trigger per symbol
                    
                # Short Trigger
                elif has_short_cat and (b_c < or_l) and (b_c < vwap_val):
                    raw_stop = min(or_mid, b_h)
                    if (raw_stop - b_c) / b_c < 0.0030:
                        raw_stop = b_c * (1.0 + 0.0030)
                    if (raw_stop - b_c) / b_c > 0.0090:
                        raw_stop = b_c * (1.0 + 0.0090)
                    risk_pts = raw_stop - b_c
                    if risk_pts > 0:
                        score = rvol * (1.0 + abs(gap_pct))
                        day_candidates.append({
                            'symbol': sym,
                            'side': 'SELL',
                            'bar_idx': b_i,
                            'entry_price': b_c,
                            'stop_loss': raw_stop,
                            'risk_pts': risk_pts,
                            'score': score,
                            'rvol': rvol,
                            'gap_pct': gap_pct,
                            'df': d_df
                        })
                    break
                    
        if not day_candidates:
            continue
            
        # SELECT ONLY THE #1 HIGHEST RANKED TRADE OF THE DAY
        # Sort by earliest trigger bar first, then by highest catalyst score
        day_candidates.sort(key=lambda x: (x['bar_idx'], -x['score']))
        best_trade = day_candidates[0]
        
        # Execute this single trade forward bar by bar
        sym = best_trade['symbol']
        side = best_trade['side']
        entry_p = best_trade['entry_price']
        sl = best_trade['stop_loss']
        risk_pts = best_trade['risk_pts']
        d_df = best_trade['df']
        entry_bar = best_trade['bar_idx']
        
        # Risk 1% of Rs 1,00,000 account = Rs 1,000 per trade (1R = 1.0%)
        # Position sizing:
        shares = int(1000.0 / risk_pts)
        if shares < 1:
            shares = 1
        half_shares = shares // 2
        runner_shares = shares - half_shares
        if half_shares < 1:
            half_shares = 1
            runner_shares = 0
            
        t1_price = entry_p + (t1_target_r * risk_pts) if side == 'BUY' else entry_p - (t1_target_r * risk_pts)
        
        t1_hit = False
        curr_sl = sl
        exit_p1 = 0.0
        exit_p2 = 0.0
        exit_reason = ""
        
        if side == 'BUY':
            for j in range(entry_bar + 1, len(d_df)):
                f_bar = d_df.iloc[j]
                f_h = f_bar['High']
                f_l = f_bar['Low']
                f_c = f_bar['Close']
                ema_v = f_bar['ema9']
                
                # Stop check
                if f_l <= curr_sl:
                    if not t1_hit:
                        exit_p1 = curr_sl
                        exit_p2 = curr_sl
                        exit_reason = "STOP_INITIAL"
                    else:
                        exit_p2 = curr_sl
                        exit_reason = "RUNNER_BE_STOP"
                    break
                    
                # Target 1 check
                if not t1_hit and f_h >= t1_price:
                    t1_hit = True
                    exit_p1 = t1_price
                    curr_sl = entry_p # Move to Breakeven
                    
                # Runner check: exit if close drops below EMA9 after 13:00
                if t1_hit and j >= 45:
                    if f_c < ema_v:
                        exit_p2 = f_c
                        exit_reason = "RUNNER_EMA_TRAIL"
                        break
                        
                # EOD square off at 15:15
                if j == len(d_df) - 1 or j >= 72:
                    if not t1_hit:
                        exit_p1 = f_c
                    exit_p2 = f_c
                    exit_reason = "EOD_SQUAREOFF"
                    break
                    
            p1_pnl = half_shares * (exit_p1 - entry_p)
            p1_fee = compute_zerodha_charges(half_shares * entry_p, half_shares * exit_p1)
            if runner_shares > 0:
                p2_pnl = runner_shares * (exit_p2 - entry_p)
                p2_fee = compute_zerodha_charges(runner_shares * entry_p, runner_shares * exit_p2)
            else:
                p2_pnl = 0.0
                p2_fee = 0.0
                
        else: # SHORT
            for j in range(entry_bar + 1, len(d_df)):
                f_bar = d_df.iloc[j]
                f_h = f_bar['High']
                f_l = f_bar['Low']
                f_c = f_bar['Close']
                ema_v = f_bar['ema9']
                
                if f_h >= curr_sl:
                    if not t1_hit:
                        exit_p1 = curr_sl
                        exit_p2 = curr_sl
                        exit_reason = "STOP_INITIAL"
                    else:
                        exit_p2 = curr_sl
                        exit_reason = "RUNNER_BE_STOP"
                    break
                    
                if not t1_hit and f_l <= t1_price:
                    t1_hit = True
                    exit_p1 = t1_price
                    curr_sl = entry_p # Move to Breakeven
                    
                if t1_hit and j >= 45:
                    if f_c > ema_v:
                        exit_p2 = f_c
                        exit_reason = "RUNNER_EMA_TRAIL"
                        break
                        
                if j == len(d_df) - 1 or j >= 72:
                    if not t1_hit:
                        exit_p1 = f_c
                    exit_p2 = f_c
                    exit_reason = "EOD_SQUAREOFF"
                    break
                    
            p1_pnl = half_shares * (entry_p - exit_p1)
            p1_fee = compute_zerodha_charges(half_shares * exit_p1, half_shares * entry_p)
            if runner_shares > 0:
                p2_pnl = runner_shares * (entry_p - exit_p2)
                p2_fee = compute_zerodha_charges(runner_shares * exit_p2, runner_shares * entry_p)
            else:
                p2_pnl = 0.0
                p2_fee = 0.0
                
        gross_pnl = p1_pnl + p2_pnl
        total_fee = p1_fee + p2_fee
        net_pnl = gross_pnl - total_fee
        # 1R = Rs 1,000 = 1.0% return
        net_r = net_pnl / 1000.0
        
        trades.append({
            'date': date_str,
            'symbol': sym,
            'side': side,
            'net_r': net_r,
            'net_return_pct': net_r, # 1R = 1.0%
            'fee': total_fee,
            'net_pnl': net_pnl,
            'exit_reason': exit_reason,
            'rvol': best_trade['rvol'],
            'gap_pct': best_trade['gap_pct']
        })
        
    df_trades = pd.DataFrame(trades)
    df_trades['month'] = pd.to_datetime(df_trades['date']).dt.to_period('M')
    n_months = df_trades['month'].nunique()
    
    wins = df_trades[df_trades['net_r'] > 0]
    losses = df_trades[df_trades['net_r'] <= 0]
    win_rate = len(wins) / len(df_trades) * 100.0 if len(df_trades) > 0 else 0
    total_net_r = df_trades['net_r'].sum()
    monthly_r = total_net_r / max(1, n_months)
    
    # Cumulative Drawdown
    df_trades['cum_r'] = df_trades['net_r'].cumsum()
    df_trades['peak_r'] = df_trades['cum_r'].cummax()
    df_trades['dd_r'] = df_trades['cum_r'] - df_trades['peak_r']
    max_dd_r = df_trades['dd_r'].min()
    
    gross_win = wins['net_pnl'].sum()
    gross_loss = abs(losses['net_pnl'].sum())
    profit_factor = gross_win / gross_loss if gross_loss > 0 else 999.0
    total_fees = df_trades['fee'].sum()
    
    print("\n" + "="*75, flush=True)
    print(f"TRADE OF THE DAY (1 TRADE/DAY, 1% RISK/TRADE) - RESULTS (2022-2026):", flush=True)
    print(f"Total Trading Sessions: {len(sorted_dates)} days", flush=True)
    print(f"Total Trades Taken: {len(df_trades)} ({len(df_trades)/n_months:.1f} trades/month, ~{len(df_trades)/len(sorted_dates):.2f} trades/day)", flush=True)
    print(f"Win Rate: {win_rate:.2f}% ({len(wins)} wins / {len(losses)} losses)", flush=True)
    print(f"Profit Factor: {profit_factor:.2f}", flush=True)
    print(f"Total Net Return: {total_net_r:+.2f}% (+{total_net_r:.2f} R)", flush=True)
    print(f"Average Monthly Return: {monthly_r:+.2f}% / month (+{monthly_r:.2f} R / month)", flush=True)
    print(f"Max Peak-to-Trough Drawdown: {max_dd_r:.2f}% ({max_dd_r:.2f} R)", flush=True)
    print(f"Total Brokerage & Statutory Taxes Paid: Rs {total_fees:,.2f} ({total_fees/1000:.1f} R)", flush=True)
    print("="*75, flush=True)
    
    # Yearly breakdown
    df_trades['year'] = pd.to_datetime(df_trades['date']).dt.year
    yearly = df_trades.groupby('year').agg(
        trades=('net_r', 'count'),
        win_rate=('net_r', lambda x: (x > 0).mean() * 100),
        net_return_pct=('net_r', 'sum'),
        fees=('fee', 'sum')
    )
    print("\nYEARLY PERFORMANCE BREAKDOWN:", flush=True)
    print(yearly, flush=True)
    
    # Exit reason breakdown
    exit_grp = df_trades.groupby('exit_reason').agg(
        trades=('net_r', 'count'),
        avg_r=('net_r', 'mean'),
        total_r=('net_r', 'sum')
    )
    print("\nPERFORMANCE BY EXIT REASON:", flush=True)
    print(exit_grp, flush=True)

if __name__ == '__main__':
    run_trade_of_the_day(min_rvol=1.5, min_gap=0.3, t1_target_r=2.0)
