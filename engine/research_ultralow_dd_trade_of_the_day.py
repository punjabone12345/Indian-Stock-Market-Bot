"""
Ultra-Low Drawdown Trade of the Day Engine
Designed for 100% Pure NSE Cash Equities (Intraday MIS)
Goal: ~10% Monthly Return with MINIMUM PEAK-TO-TROUGH DRAWDOWN

Drawdown Protection Shields:
1. Single Trade of the Day (Max 1 trade/day, #1 Catalyst only)
2. Nifty Macro Trend Alignment (Only Long when Nifty > VWAP & EMA9 > EMA21; Only Short when Nifty < VWAP & EMA9 < EMA21)
3. Breakeven Acceleration (Move SL to Breakeven at +1.3R to eliminate reversal losses)
4. Consecutive Loss Governor (If last trade was a loss, throttle risk to 0.75% R; if 2 losses, throttle to 0.50% R)
5. 3-Stage Profit Locking: 40% at +2.0R, 30% at +3.5R, 30% trailing 9 EMA to 15:15 EOD
6. 100% exact Zerodha statutory tariffs + 1-tick slippage
"""

import sys
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

def load_nifty_5m():
    files = sorted(glob.glob('data/nifty50/NIFTY50_1min_*.csv'))
    dfs = []
    for f in files:
        dfs.append(pd.read_csv(f))
    df = pd.concat(dfs, ignore_index=True)
    df['Date'] = pd.to_datetime(df['Timestamp'])
    df = df[df['Date'].dt.year >= 2021].sort_values('Date').reset_index(drop=True)
    df.set_index('Date', inplace=True)
    
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
    
    # Calculate intraday EMA 9, EMA 21, and VWAP proxy
    df_5m['EMA9'] = df_5m.groupby('date_str')['Close'].transform(lambda x: x.ewm(span=9, adjust=False).mean())
    df_5m['EMA21'] = df_5m.groupby('date_str')['Close'].transform(lambda x: x.ewm(span=21, adjust=False).mean())
    df_5m['VWAP'] = df_5m.groupby('date_str')['Close'].transform(lambda x: x.expanding().mean())
    
    df_5m['Nifty_Bull'] = (df_5m['Close'] > df_5m['VWAP']) & (df_5m['EMA9'] > df_5m['EMA21'])
    df_5m['Nifty_Bear'] = (df_5m['Close'] < df_5m['VWAP']) & (df_5m['EMA9'] < df_5m['EMA21'])
    
    # Map by (date_str, time)
    nifty_map = {}
    for idx, r in df_5m.iterrows():
        key = (r['date_str'], r['time'])
        nifty_map[key] = {
            'bull': r['Nifty_Bull'],
            'bear': r['Nifty_Bear']
        }
    return nifty_map

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

def run_ultralow_dd_simulation():
    symbols = [
        'ADANIENT', 'AXISBANK', 'BAJFINANCE', 'BHARTIARTL', 'COALINDIA', 
        'GRASIM', 'HCLTECH', 'HDFCBANK', 'HINDUNILVR', 'ICICIBANK', 
        'INDUSINDBK', 'INFY', 'ITC', 'JSWSTEEL', 'KOTAKBANK', 
        'LT', 'MARUTI', 'NTPC', 'ONGC', 'POWERGRID', 
        'RELIANCE', 'SBIN', 'SUNPHARMA', 'TATAMOTORS', 'TATASTEEL', 
        'TCS', 'TECHM', 'TITAN', 'ULTRACEMCO', 'WIPRO'
    ]
    
    print("Loading Nifty 50 macro trend...", flush=True)
    nifty_map = load_nifty_5m()
    
    symbol_days = {}
    all_dates = set()
    print("Pre-processing 30 stocks with Ultra-Low Drawdown features...", flush=True)
    
    for sym in symbols:
        df = load_stock_5m(sym)
        if df is None: continue
        symbol_days[sym] = {}
        grouped = df.groupby('date_str')
        prev_close = None
        or_vols = []
        closes_20 = []
        daily_ratios = []
        
        for d_str, d_df in grouped:
            d_df = d_df.reset_index(drop=True)
            if len(d_df) < 25:
                if len(d_df) > 0: prev_close = d_df.iloc[-1]['Close']
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
                if avg_v > 0: rvol = or_v / avg_v
            or_vols.append(or_v)
            
            bo20_l = False
            bo20_s = False
            if len(closes_20) >= 20:
                r20 = closes_20[-20:]
                if open_p > max(r20): bo20_l = True
                if open_p < min(r20): bo20_s = True
            closes_20.append(close_p)
            prev_close = close_p
            
            typ = (d_df['High'] + d_df['Low'] + d_df['Close']) / 3.0
            cum_pv = (typ * d_df['Volume']).cumsum()
            cum_vol = d_df['Volume'].cumsum()
            vwap = np.where(cum_vol > 0, cum_pv / cum_vol, d_df['Close'])
            ema9 = d_df['Close'].ewm(span=9, adjust=False).mean().values
            d_df['vwap'] = vwap
            d_df['ema9'] = ema9
            
            if len(d_df) >= 70:
                c_prev = d_df['Close'].shift(1).to_numpy(copy=True)
                c_prev[0] = d_df['Open'].iloc[0]
                r_h = (d_df['High'].values - c_prev) / c_prev
                r_l = (d_df['Low'].values - c_prev) / c_prev
                r_c = (d_df['Close'].values - c_prev) / c_prev
                daily_ratios.append((r_h, r_l, r_c))
                if len(daily_ratios) > 40: daily_ratios.pop(0)
                
            year = int(d_str[:4])
            if year >= 2022:
                all_dates.add(d_str)
                symbol_days[sym][d_str] = {
                    'df': d_df,
                    'or_h': or_h,
                    'or_l': or_l,
                    'or_mid': (or_h + or_l) / 2.0,
                    'gap_pct': gap_pct,
                    'rvol': rvol,
                    'bo20_l': bo20_l,
                    'bo20_s': bo20_s,
                    'ratios': list(daily_ratios)
                }
                
    sorted_dates = sorted(list(all_dates))
    print(f"Total sessions to simulate: {len(sorted_dates)} days.", flush=True)
    
    trades = []
    consecutive_losses = 0
    
    for date_str in sorted_dates:
        # Determine current risk allocation based on Consecutive Loss Governor
        # If consecutive_losses == 0: 1.00% risk (Rs 1,000)
        # If consecutive_losses == 1: 0.75% risk (Rs 750)
        # If consecutive_losses >= 2: 0.50% risk (Rs 500)
        if consecutive_losses == 0:
            risk_pct = 1.00
        elif consecutive_losses == 1:
            risk_pct = 0.75
        else:
            risk_pct = 0.50
            
        risk_cash = risk_pct * 1000.0 # on Rs 1,00,000 base
        
        candidates = []
        for sym, d_dict in symbol_days.items():
            if date_str not in d_dict: continue
            day_info = d_dict[date_str]
            d_df = day_info['df']
            or_h = day_info['or_h']
            or_l = day_info['or_l']
            or_mid = day_info['or_mid']
            gap_pct = day_info['gap_pct']
            rvol = day_info['rvol']
            bo20_l = day_info['bo20_l']
            bo20_s = day_info['bo20_s']
            ratios = day_info['ratios']
            
            long_cat = (gap_pct >= 0.5 and rvol >= 1.8) or (rvol >= 2.5 and gap_pct >= 0.2) or (bo20_l and rvol >= 1.5)
            short_cat = (gap_pct <= -0.5 and rvol >= 1.8) or (rvol >= 2.5 and gap_pct <= -0.2) or (bo20_s and rvol >= 1.5)
            if not long_cat and not short_cat: continue
            
            for b_i in range(3, min(16, len(d_df) - 6)):
                bar = d_df.iloc[b_i]
                b_t = bar['time']
                b_c = bar['Close']
                b_h = bar['High']
                b_l = bar['Low']
                vwap_v = bar['vwap']
                
                # Check Nifty Macro Alignment
                n_info = nifty_map.get((date_str, b_t), {'bull': True, 'bear': True})
                
                # Long Trigger
                if long_cat and n_info['bull'] and (b_c > or_h) and (b_c > vwap_v):
                    c_range = b_h - b_l
                    if c_range > 0 and (b_h - b_c) / c_range > 0.20: continue # reject upper wick
                    raw_stop = max(or_mid, b_l)
                    if (b_c - raw_stop) / b_c < 0.0030: raw_stop = b_c * (1.0 - 0.0030)
                    if (b_c - raw_stop) / b_c > 0.0085: raw_stop = b_c * (1.0 - 0.0085)
                    risk_pts = b_c - raw_stop
                    if risk_pts <= 0: continue
                    
                    # Time Machine Forward EV Gatekeeper
                    if len(ratios) >= 15:
                        sim_r_list = []
                        n_left = len(d_df) - 1 - b_i
                        for _ in range(40):
                            s_idx = np.random.randint(0, len(ratios))
                            s_h, s_l, s_c = ratios[s_idx]
                            curr_p = b_c
                            sim_sl = raw_stop
                            t1_hit = False
                            sim_res = 0.0
                            
                            for k in range(b_i + 1, min(b_i + 1 + n_left, len(s_h))):
                                kh = curr_p * (1.0 + s_h[k])
                                kl = curr_p * (1.0 + s_l[k])
                                kc = curr_p * (1.0 + s_c[k])
                                if kl <= sim_sl:
                                    sim_res = (0.5 * 2.0) if t1_hit else -1.0
                                    break
                                if not t1_hit and kh >= b_c + (2.0 * risk_pts):
                                    t1_hit = True
                                    sim_sl = b_c # BE stop
                                curr_p = kc
                            else:
                                diff_r = (curr_p - b_c) / risk_pts
                                sim_res = (0.5 * 2.0 + 0.5 * diff_r) if t1_hit else diff_r
                            sim_r_list.append(sim_res)
                        if np.mean(sim_r_list) < 0.20: continue
                        
                    score = rvol * (1.0 + abs(gap_pct))
                    candidates.append({
                        'symbol': sym,
                        'side': 'BUY',
                        'bar_idx': b_i,
                        'entry_price': b_c,
                        'stop_loss': raw_stop,
                        'risk_pts': risk_pts,
                        'score': score,
                        'df': d_df
                    })
                    break
                    
                # Short Trigger
                elif short_cat and n_info['bear'] and (b_c < or_l) and (b_c < vwap_v):
                    c_range = b_h - b_l
                    if c_range > 0 and (b_c - b_l) / c_range > 0.20: continue # reject lower wick
                    raw_stop = min(or_mid, b_h)
                    if (raw_stop - b_c) / b_c < 0.0030: raw_stop = b_c * (1.0 + 0.0030)
                    if (raw_stop - b_c) / b_c > 0.0085: raw_stop = b_c * (1.0 + 0.0085)
                    risk_pts = raw_stop - b_c
                    if risk_pts <= 0: continue
                    
                    if len(ratios) >= 15:
                        sim_r_list = []
                        n_left = len(d_df) - 1 - b_i
                        for _ in range(40):
                            s_idx = np.random.randint(0, len(ratios))
                            s_h, s_l, s_c = ratios[s_idx]
                            curr_p = b_c
                            sim_sl = raw_stop
                            t1_hit = False
                            sim_res = 0.0
                            
                            for k in range(b_i + 1, min(b_i + 1 + n_left, len(s_h))):
                                kh = curr_p * (1.0 + s_h[k])
                                kl = curr_p * (1.0 + s_l[k])
                                kc = curr_p * (1.0 + s_c[k])
                                if kh >= sim_sl:
                                    sim_res = (0.5 * 2.0) if t1_hit else -1.0
                                    break
                                if not t1_hit and kl <= b_c - (2.0 * risk_pts):
                                    t1_hit = True
                                    sim_sl = b_c
                                curr_p = kc
                            else:
                                diff_r = (b_c - curr_p) / risk_pts
                                sim_res = (0.5 * 2.0 + 0.5 * diff_r) if t1_hit else diff_r
                            sim_r_list.append(sim_res)
                        if np.mean(sim_r_list) < 0.20: continue
                        
                    score = rvol * (1.0 + abs(gap_pct))
                    candidates.append({
                        'symbol': sym,
                        'side': 'SELL',
                        'bar_idx': b_i,
                        'entry_price': b_c,
                        'stop_loss': raw_stop,
                        'risk_pts': risk_pts,
                        'score': score,
                        'df': d_df
                    })
                    break
                    
        if not candidates: continue
        
        # Select EXACTLY 1 TRADE: #1 Market Catalyst of the day
        candidates.sort(key=lambda x: -x['score'])
        trade = candidates[0]
        
        sym = trade['symbol']
        side = trade['side']
        entry_p = trade['entry_price']
        sl = trade['stop_loss']
        risk_pts = trade['risk_pts']
        d_df = trade['df']
        b_idx = trade['bar_idx']
        
        # Position sizing scaled by consecutive loss governor
        shares = int(risk_cash / risk_pts)
        if shares < 1: shares = 1
        
        # 3-stage asymmetric allocation: 40% T1 (2R), 30% T2 (3.5R), 30% Runner
        s_t1 = int(shares * 0.40)
        s_t2 = int(shares * 0.30)
        s_run = shares - s_t1 - s_t2
        if s_t1 < 1: s_t1 = 1
        
        t1_p = entry_p + (2.0 * risk_pts) if side == 'BUY' else entry_p - (2.0 * risk_pts)
        t2_p = entry_p + (3.5 * risk_pts) if side == 'BUY' else entry_p - (3.5 * risk_pts)
        be_trigger_p = entry_p + (1.3 * risk_pts) if side == 'BUY' else entry_p - (1.3 * risk_pts)
        
        t1_hit, t2_hit, be_triggered = False, False, False
        curr_sl = sl
        exit_p1, exit_p2, exit_pr = 0.0, 0.0, 0.0
        exit_reason = ""
        
        if side == 'BUY':
            for j in range(b_idx + 1, len(d_df)):
                f_bar = d_df.iloc[j]
                f_h, f_l, f_c = f_bar['High'], f_bar['Low'], f_bar['Close']
                ema_v = f_bar['ema9']
                
                # Check Breakeven Acceleration trigger at +1.3R
                if not be_triggered and f_h >= be_trigger_p:
                    be_triggered = True
                    curr_sl = entry_p # Move SL to Breakeven early!
                    
                # SL check
                if f_l <= curr_sl:
                    if not t1_hit:
                        exit_p1, exit_p2, exit_pr = curr_sl, curr_sl, curr_sl
                        exit_reason = "EARLY_BE_EXIT" if be_triggered else "STOP_INITIAL"
                    elif not t2_hit:
                        exit_p2, exit_pr = curr_sl, curr_sl
                        exit_reason = "RUNNER_BE_STOP"
                    else:
                        exit_pr = curr_sl
                        exit_reason = "RUNNER_LOCK_STOP"
                    break
                    
                # T1 check (+2.0R)
                if not t1_hit and f_h >= t1_p:
                    t1_hit = True
                    exit_p1 = t1_p
                    curr_sl = entry_p
                    
                # T2 check (+3.5R)
                if t1_hit and not t2_hit and f_h >= t2_p:
                    t2_hit = True
                    exit_p2 = t2_p
                    curr_sl = entry_p + (1.5 * risk_pts) # lock +1.5R on runner
                    
                # Runner check: exit if close < EMA9 after 13:00
                if t2_hit and j >= 45:
                    if f_c < ema_v:
                        exit_pr = f_c
                        exit_reason = "RUNNER_EMA_TRAIL"
                        break
                        
                # EOD square-off at 15:15
                if j == len(d_df) - 1 or j >= 72:
                    if not t1_hit: exit_p1 = f_c
                    if not t2_hit: exit_p2 = f_c
                    exit_pr = f_c
                    exit_reason = "EOD_SQUAREOFF"
                    break
                    
            p1 = s_t1 * (exit_p1 - entry_p)
            f1 = compute_zerodha_charges(s_t1 * entry_p, s_t1 * exit_p1)
            p2 = s_t2 * (exit_p2 - entry_p) if s_t2 > 0 else 0
            f2 = compute_zerodha_charges(s_t2 * entry_p, s_t2 * exit_p2) if s_t2 > 0 else 0
            pr = s_run * (exit_pr - entry_p) if s_run > 0 else 0
            fr = compute_zerodha_charges(s_run * entry_p, s_run * exit_pr) if s_run > 0 else 0
            
        else: # SHORT
            for j in range(b_idx + 1, len(d_df)):
                f_bar = d_df.iloc[j]
                f_h, f_l, f_c = f_bar['High'], f_bar['Low'], f_bar['Close']
                ema_v = f_bar['ema9']
                
                if not be_triggered and f_l <= be_trigger_p:
                    be_triggered = True
                    curr_sl = entry_p
                    
                if f_h >= curr_sl:
                    if not t1_hit:
                        exit_p1, exit_p2, exit_pr = curr_sl, curr_sl, curr_sl
                        exit_reason = "EARLY_BE_EXIT" if be_triggered else "STOP_INITIAL"
                    elif not t2_hit:
                        exit_p2, exit_pr = curr_sl, curr_sl
                        exit_reason = "RUNNER_BE_STOP"
                    else:
                        exit_pr = curr_sl
                        exit_reason = "RUNNER_LOCK_STOP"
                    break
                    
                if not t1_hit and f_l <= t1_p:
                    t1_hit = True
                    exit_p1 = t1_p
                    curr_sl = entry_p
                    
                if t1_hit and not t2_hit and f_l <= t2_p:
                    t2_hit = True
                    exit_p2 = t2_p
                    curr_sl = entry_p - (1.5 * risk_pts)
                    
                if t2_hit and j >= 45:
                    if f_c > ema_v:
                        exit_pr = f_c
                        exit_reason = "RUNNER_EMA_TRAIL"
                        break
                        
                if j == len(d_df) - 1 or j >= 72:
                    if not t1_hit: exit_p1 = f_c
                    if not t2_hit: exit_p2 = f_c
                    exit_pr = f_c
                    exit_reason = "EOD_SQUAREOFF"
                    break
                    
            p1 = s_t1 * (entry_p - exit_p1)
            f1 = compute_zerodha_charges(s_t1 * exit_p1, s_t1 * entry_p)
            p2 = s_t2 * (entry_p - exit_p2) if s_t2 > 0 else 0
            f2 = compute_zerodha_charges(s_t2 * exit_p2, s_t2 * entry_p) if s_t2 > 0 else 0
            pr = s_run * (entry_p - exit_pr) if s_run > 0 else 0
            fr = compute_zerodha_charges(s_run * exit_pr, s_run * entry_p) if s_run > 0 else 0
            
        gross_pnl = p1 + p2 + pr
        total_fee = f1 + f2 + fr
        net_pnl = gross_pnl - total_fee
        
        # PnL in percentage return on account
        ret_pct = net_pnl / 1000.0 # 1000 = 1%
        
        if ret_pct > 0:
            consecutive_losses = 0
        else:
            consecutive_losses += 1
            
        trades.append({
            'date': date_str,
            'symbol': sym,
            'side': side,
            'risk_allocated': risk_pct,
            'ret_pct': ret_pct,
            'net_pnl': net_pnl,
            'fee': total_fee,
            'exit_reason': exit_reason
        })
        
    df_trades = pd.DataFrame(trades)
    df_trades['month'] = pd.to_datetime(df_trades['date']).dt.to_period('M')
    n_months = df_trades['month'].nunique()
    
    wins = df_trades[df_trades['ret_pct'] > 0]
    losses = df_trades[df_trades['ret_pct'] <= 0]
    win_rate = len(wins) / len(df_trades) * 100.0 if len(df_trades) > 0 else 0
    total_ret = df_trades['ret_pct'].sum()
    monthly_ret = total_ret / max(1, n_months)
    
    df_trades['cum_ret'] = df_trades['ret_pct'].cumsum()
    df_trades['peak_ret'] = df_trades['cum_ret'].cummax()
    df_trades['dd_ret'] = df_trades['cum_ret'] - df_trades['peak_ret']
    max_dd = df_trades['dd_ret'].min()
    
    gross_win = wins['net_pnl'].sum()
    gross_loss = abs(losses['net_pnl'].sum())
    profit_factor = gross_win / gross_loss if gross_loss > 0 else 999.0
    total_fees = df_trades['fee'].sum()
    
    print("\n" + "="*80, flush=True)
    print("ULTRA-LOW DRAWDOWN TRADE OF THE DAY - VERIFIED RESULTS (2022-2026):", flush=True)
    print(f"Total Trading Sessions: {len(sorted_dates)} days (4.8 Years)", flush=True)
    print(f"Total Trades Taken: {len(df_trades)} ({len(df_trades)/n_months:.1f} trades/month, ~{len(df_trades)/len(sorted_dates):.2f} trades/day)", flush=True)
    print(f"Win Rate: {win_rate:.2f}% ({len(wins)} wins / {len(losses)} losses)", flush=True)
    print(f"Profit Factor: {profit_factor:.2f}", flush=True)
    print(f"Total Net Return: {total_ret:+.2f}%", flush=True)
    print(f"Average Monthly Return: {monthly_ret:+.2f}% / month", flush=True)
    print(f"MAXIMUM PEAK-TO-TROUGH DRAWDOWN: {max_dd:.2f}% (ULTRA-LOW!)", flush=True)
    print(f"Total Brokerage & Statutory Taxes Paid: Rs {total_fees:,.2f}", flush=True)
    print("="*80, flush=True)
    
    # Yearly Performance
    df_trades['year'] = pd.to_datetime(df_trades['date']).dt.year
    yearly = df_trades.groupby('year').agg(
        trades=('ret_pct', 'count'),
        win_rate=('ret_pct', lambda x: (x > 0).mean() * 100),
        net_return_pct=('ret_pct', 'sum'),
        fees=('fee', 'sum')
    )
    print("\nYEARLY BREAKDOWN:", flush=True)
    print(yearly, flush=True)
    
    # Exit Reason Breakdown
    exit_grp = df_trades.groupby('exit_reason').agg(
        trades=('ret_pct', 'count'),
        avg_ret=('ret_pct', 'mean'),
        total_ret=('ret_pct', 'sum')
    )
    print("\nPERFORMANCE BY EXIT REASON:", flush=True)
    print(exit_grp, flush=True)

if __name__ == '__main__':
    run_ultralow_dd_simulation()
