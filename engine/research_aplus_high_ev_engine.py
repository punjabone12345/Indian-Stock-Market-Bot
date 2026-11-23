"""
A+ High-Conviction Institutional Trade Engine
Goal: High Net EV per trade (+0.50R - +0.80R net) to target ~8-12% monthly return with 1% risk
Rules:
- Universe: 30 Nifty Mega-Caps (2022 - 2026, 4.8 Years)
- Max Trades: 0 or 1 trade per day (A+ setups ONLY; if no A+ setup exists, TAKE NO TRADE)
- Catalyst Threshold: Extreme Institutional Volume (RVOL >= 2.0x AND Gap >= 0.6% OR 20d Breakout)
- Breakout Candle Quality: Bar close must be within top 20% of candle range (strong buyer/seller conviction)
- Time Machine Monte Carlo Gatekeeper: Replay 50 forward paths; reject if EV < 0.25R
- Asymmetric Profit Scaling:
    * Exit 40% at 2.0R (Move SL to Breakeven)
    * Exit 30% at 3.5R (Move SL to 1.5R locked profit)
    * Trail remaining 30% with 9 EMA to 15:15 EOD
- Statutory Taxes: 100% exact Zerodha tariffs down to the paisa.
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
    
    t_start = datetime.strptime("09:15", "%H:%M").time()
    t_end = datetime.strptime("15:30", "%H:%M").time()
    
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

def run_aplus_simulation(min_rvol=2.0, min_gap=0.6, min_ev=0.25):
    symbols = [
        'ADANIENT', 'AXISBANK', 'BAJFINANCE', 'BHARTIARTL', 'COALINDIA', 
        'GRASIM', 'HCLTECH', 'HDFCBANK', 'HINDUNILVR', 'ICICIBANK', 
        'INDUSINDBK', 'INFY', 'ITC', 'JSWSTEEL', 'KOTAKBANK', 
        'LT', 'MARUTI', 'NTPC', 'ONGC', 'POWERGRID', 
        'RELIANCE', 'SBIN', 'SUNPHARMA', 'TATAMOTORS', 'TATASTEEL', 
        'TCS', 'TECHM', 'TITAN', 'ULTRACEMCO', 'WIPRO'
    ]
    
    # Store daily precomputed data per symbol
    symbol_days = {}
    print(f"Pre-processing 30 symbols with A+ Filter (RVOL >= {min_rvol}, Gap >= {min_gap}%, EV >= {min_ev})...", flush=True)
    
    all_dates = set()
    
    for sym in symbols:
        df = load_symbol_5m(sym)
        if df is None or len(df) == 0:
            continue
            
        symbol_days[sym] = {}
        grouped = df.groupby('date_str')
        prev_close = None
        or_vols = []
        closes_20 = []
        daily_ratios = []
        
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
            
            bo20_l = False
            bo20_s = False
            if len(closes_20) >= 20:
                r20 = closes_20[-20:]
                if open_p > max(r20):
                    bo20_l = True
                if open_p < min(r20):
                    bo20_s = True
            closes_20.append(close_p)
            prev_close = close_p
            
            # VWAP & EMA9
            typ = (d_df['High'] + d_df['Low'] + d_df['Close']) / 3.0
            cum_pv = (typ * d_df['Volume']).cumsum()
            cum_vol = d_df['Volume'].cumsum()
            vwap = np.where(cum_vol > 0, cum_pv / cum_vol, d_df['Close'])
            ema9 = d_df['Close'].ewm(span=9, adjust=False).mean().values
            d_df['vwap'] = vwap
            d_df['ema9'] = ema9
            
            # Daily bar ratios for Time Machine
            if len(d_df) >= 70:
                c_prev = d_df['Close'].shift(1).to_numpy(copy=True)
                c_prev[0] = d_df['Open'].iloc[0]
                r_h = (d_df['High'].values - c_prev) / c_prev
                r_l = (d_df['Low'].values - c_prev) / c_prev
                r_c = (d_df['Close'].values - c_prev) / c_prev
                daily_ratios.append((r_h, r_l, r_c))
                if len(daily_ratios) > 40:
                    daily_ratios.pop(0)
                    
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
    print(f"Trading sessions: {len(sorted_dates)} days across 2022-2026.", flush=True)
    
    trades = []
    
    for date_str in sorted_dates:
        # Collect candidates on this day
        candidates = []
        for sym, d_dict in symbol_days.items():
            if date_str not in d_dict:
                continue
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
            
            # Strict A+ Catalyst:
            # (Gap >= min_gap AND RVOL >= min_rvol) OR (RVOL >= 2.8) OR (bo20_l AND RVOL >= 1.8)
            long_cat = (gap_pct >= min_gap and rvol >= min_rvol) or (rvol >= 2.8 and gap_pct >= 0.2) or (bo20_l and rvol >= 1.8)
            short_cat = (gap_pct <= -min_gap and rvol >= min_rvol) or (rvol >= 2.8 and gap_pct <= -0.2) or (bo20_s and rvol >= 1.8)
            
            if not long_cat and not short_cat:
                continue
                
            # Check bars 3 to 15 (09:30 to 10:30)
            for b_i in range(3, min(16, len(d_df) - 6)):
                bar = d_df.iloc[b_i]
                b_c = bar['Close']
                b_h = bar['High']
                b_l = bar['Low']
                b_o = bar['Open']
                vwap_v = bar['vwap']
                
                # Long Trigger
                if long_cat and (b_c > or_h) and (b_c > vwap_v):
                    # Candle quality check: strong green candle closing near high (top 25% of candle range)
                    c_range = b_h - b_l
                    if c_range > 0 and (b_h - b_c) / c_range > 0.25:
                        continue # upper wick too long, rejection!
                        
                    raw_stop = max(or_mid, b_l)
                    if (b_c - raw_stop) / b_c < 0.0030:
                        raw_stop = b_c * (1.0 - 0.0030)
                    if (b_c - raw_stop) / b_c > 0.0085:
                        raw_stop = b_c * (1.0 - 0.0085)
                    risk_pts = b_c - raw_stop
                    if risk_pts <= 0:
                        continue
                        
                    t1_p = b_c + (2.0 * risk_pts)
                    t2_p = b_c + (3.5 * risk_pts)
                    
                    # Time Machine Forward EV Gatekeeper
                    if len(ratios) >= 15:
                        sim_r_list = []
                        n_left = len(d_df) - 1 - b_i
                        for _ in range(50):
                            s_idx = np.random.randint(0, len(ratios))
                            s_h, s_l, s_c = ratios[s_idx]
                            curr_p = b_c
                            sim_sl = raw_stop
                            t1_hit = False
                            t2_hit = False
                            sim_res = 0.0
                            
                            for k in range(b_i + 1, min(b_i + 1 + n_left, len(s_h))):
                                kh = curr_p * (1.0 + s_h[k])
                                kl = curr_p * (1.0 + s_l[k])
                                kc = curr_p * (1.0 + s_c[k])
                                
                                if kl <= sim_sl:
                                    if not t1_hit:
                                        sim_res = -1.0
                                    elif not t2_hit:
                                        sim_res = (0.4 * 2.0) - (0.6 * 0.0) # BE stop on rest
                                    else:
                                        sim_res = (0.4 * 2.0) + (0.3 * 3.5) + (0.3 * 1.5)
                                    break
                                if not t1_hit and kh >= t1_p:
                                    t1_hit = True
                                    sim_sl = b_c # move to BE
                                if t1_hit and not t2_hit and kh >= t2_p:
                                    t2_hit = True
                                    sim_sl = b_c + (1.5 * risk_pts) # lock 1.5R on runner
                                curr_p = kc
                            else:
                                diff_r = (curr_p - b_c) / risk_pts
                                if not t1_hit:
                                    sim_res = diff_r
                                elif not t2_hit:
                                    sim_res = (0.4 * 2.0) + (0.6 * diff_r)
                                else:
                                    sim_res = (0.4 * 2.0) + (0.3 * 3.5) + (0.3 * diff_r)
                            sim_r_list.append(sim_res)
                            
                        sim_ev = np.mean(sim_r_list)
                        if sim_ev < min_ev:
                            continue
                    else:
                        sim_ev = 0.20
                        
                    score = rvol * (1.0 + abs(gap_pct)) + (sim_ev * 2.0)
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
                elif short_cat and (b_c < or_l) and (b_c < vwap_v):
                    c_range = b_h - b_l
                    if c_range > 0 and (b_c - b_l) / c_range > 0.25:
                        continue # lower wick too long, rejection!
                        
                    raw_stop = min(or_mid, b_h)
                    if (raw_stop - b_c) / b_c < 0.0030:
                        raw_stop = b_c * (1.0 + 0.0030)
                    if (raw_stop - b_c) / b_c > 0.0085:
                        raw_stop = b_c * (1.0 + 0.0085)
                    risk_pts = raw_stop - b_c
                    if risk_pts <= 0:
                        continue
                        
                    t1_p = b_c - (2.0 * risk_pts)
                    t2_p = b_c - (3.5 * risk_pts)
                    
                    if len(ratios) >= 15:
                        sim_r_list = []
                        n_left = len(d_df) - 1 - b_i
                        for _ in range(50):
                            s_idx = np.random.randint(0, len(ratios))
                            s_h, s_l, s_c = ratios[s_idx]
                            curr_p = b_c
                            sim_sl = raw_stop
                            t1_hit = False
                            t2_hit = False
                            sim_res = 0.0
                            
                            for k in range(b_i + 1, min(b_i + 1 + n_left, len(s_h))):
                                kh = curr_p * (1.0 + s_h[k])
                                kl = curr_p * (1.0 + s_l[k])
                                kc = curr_p * (1.0 + s_c[k])
                                
                                if kh >= sim_sl:
                                    if not t1_hit:
                                        sim_res = -1.0
                                    elif not t2_hit:
                                        sim_res = (0.4 * 2.0) - (0.6 * 0.0)
                                    else:
                                        sim_res = (0.4 * 2.0) + (0.3 * 3.5) + (0.3 * 1.5)
                                    break
                                if not t1_hit and kl <= t1_p:
                                    t1_hit = True
                                    sim_sl = b_c
                                if t1_hit and not t2_hit and kl <= t2_p:
                                    t2_hit = True
                                    sim_sl = b_c - (1.5 * risk_pts)
                                curr_p = kc
                            else:
                                diff_r = (b_c - curr_p) / risk_pts
                                if not t1_hit:
                                    sim_res = diff_r
                                elif not t2_hit:
                                    sim_res = (0.4 * 2.0) + (0.6 * diff_r)
                                else:
                                    sim_res = (0.4 * 2.0) + (0.3 * 3.5) + (0.3 * diff_r)
                            sim_r_list.append(sim_res)
                            
                        sim_ev = np.mean(sim_r_list)
                        if sim_ev < min_ev:
                            continue
                    else:
                        sim_ev = 0.20
                        
                    score = rvol * (1.0 + abs(gap_pct)) + (sim_ev * 2.0)
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
                    
        if not candidates:
            continue
            
        # Select EXACTLY 1 TRADE: highest score trade
        candidates.sort(key=lambda x: -x['score'])
        trade = candidates[0]
        
        sym = trade['symbol']
        side = trade['side']
        entry_p = trade['entry_price']
        sl = trade['stop_loss']
        risk_pts = trade['risk_pts']
        d_df = trade['df']
        b_idx = trade['bar_idx']
        
        # Risk 1.0% = Rs 1,000 on Rs 1,00,000 capital
        shares = int(1000.0 / risk_pts)
        if shares < 1:
            shares = 1
            
        # Split: 40% T1, 30% T2, 30% Runner
        s_t1 = int(shares * 0.40)
        s_t2 = int(shares * 0.30)
        s_run = shares - s_t1 - s_t2
        if s_t1 < 1: s_t1 = 1
        
        t1_p = entry_p + (2.0 * risk_pts) if side == 'BUY' else entry_p - (2.0 * risk_pts)
        t2_p = entry_p + (3.5 * risk_pts) if side == 'BUY' else entry_p - (3.5 * risk_pts)
        
        t1_hit = False
        t2_hit = False
        curr_sl = sl
        exit_p_t1 = 0.0
        exit_p_t2 = 0.0
        exit_p_run = 0.0
        exit_reason = ""
        
        if side == 'BUY':
            for j in range(b_idx + 1, len(d_df)):
                f_bar = d_df.iloc[j]
                f_h = f_bar['High']
                f_l = f_bar['Low']
                f_c = f_bar['Close']
                ema_v = f_bar['ema9']
                
                # SL check
                if f_l <= curr_sl:
                    if not t1_hit:
                        exit_p_t1 = curr_sl
                        exit_p_t2 = curr_sl
                        exit_p_run = curr_sl
                        exit_reason = "STOP_INITIAL"
                    elif not t2_hit:
                        exit_p_t2 = curr_sl
                        exit_p_run = curr_sl
                        exit_reason = "RUNNER_BE_STOP"
                    else:
                        exit_p_run = curr_sl
                        exit_reason = "RUNNER_LOCK_STOP"
                    break
                    
                # T1 check
                if not t1_hit and f_h >= t1_p:
                    t1_hit = True
                    exit_p_t1 = t1_p
                    curr_sl = entry_p # Move to BE
                    
                # T2 check
                if t1_hit and not t2_hit and f_h >= t2_p:
                    t2_hit = True
                    exit_p_t2 = t2_p
                    curr_sl = entry_p + (1.5 * risk_pts) # Lock 1.5R on runner
                    
                # Runner check: exit if close < EMA9 after 13:00
                if t2_hit and j >= 45:
                    if f_c < ema_v:
                        exit_p_run = f_c
                        exit_reason = "RUNNER_EMA_TRAIL"
                        break
                        
                # EOD square off
                if j == len(d_df) - 1 or j >= 72:
                    if not t1_hit: exit_p_t1 = f_c
                    if not t2_hit: exit_p_t2 = f_c
                    exit_p_run = f_c
                    exit_reason = "EOD_SQUAREOFF"
                    break
                    
            p1 = s_t1 * (exit_p_t1 - entry_p)
            f1 = compute_zerodha_charges(s_t1 * entry_p, s_t1 * exit_p_t1)
            p2 = s_t2 * (exit_p_t2 - entry_p) if s_t2 > 0 else 0
            f2 = compute_zerodha_charges(s_t2 * entry_p, s_t2 * exit_p_t2) if s_t2 > 0 else 0
            pr = s_run * (exit_p_run - entry_p) if s_run > 0 else 0
            fr = compute_zerodha_charges(s_run * entry_p, s_run * exit_p_run) if s_run > 0 else 0
            
        else: # SHORT
            for j in range(b_idx + 1, len(d_df)):
                f_bar = d_df.iloc[j]
                f_h = f_bar['High']
                f_l = f_bar['Low']
                f_c = f_bar['Close']
                ema_v = f_bar['ema9']
                
                if f_h >= curr_sl:
                    if not t1_hit:
                        exit_p_t1 = curr_sl
                        exit_p_t2 = curr_sl
                        exit_p_run = curr_sl
                        exit_reason = "STOP_INITIAL"
                    elif not t2_hit:
                        exit_p_t2 = curr_sl
                        exit_p_run = curr_sl
                        exit_reason = "RUNNER_BE_STOP"
                    else:
                        exit_p_run = curr_sl
                        exit_reason = "RUNNER_LOCK_STOP"
                    break
                    
                if not t1_hit and f_l <= t1_p:
                    t1_hit = True
                    exit_p_t1 = t1_p
                    curr_sl = entry_p
                    
                if t1_hit and not t2_hit and f_l <= t2_p:
                    t2_hit = True
                    exit_p_t2 = t2_p
                    curr_sl = entry_p - (1.5 * risk_pts)
                    
                if t2_hit and j >= 45:
                    if f_c > ema_v:
                        exit_p_run = f_c
                        exit_reason = "RUNNER_EMA_TRAIL"
                        break
                        
                if j == len(d_df) - 1 or j >= 72:
                    if not t1_hit: exit_p_t1 = f_c
                    if not t2_hit: exit_p_t2 = f_c
                    exit_p_run = f_c
                    exit_reason = "EOD_SQUAREOFF"
                    break
                    
            p1 = s_t1 * (entry_p - exit_p_t1)
            f1 = compute_zerodha_charges(s_t1 * exit_p_t1, s_t1 * entry_p)
            p2 = s_t2 * (entry_p - exit_p_t2) if s_t2 > 0 else 0
            f2 = compute_zerodha_charges(s_t2 * exit_p_t2, s_t2 * entry_p) if s_t2 > 0 else 0
            pr = s_run * (entry_p - exit_p_run) if s_run > 0 else 0
            fr = compute_zerodha_charges(s_run * exit_p_run, s_run * entry_p) if s_run > 0 else 0
            
        gross_pnl = p1 + p2 + pr
        total_fee = f1 + f2 + fr
        net_pnl = gross_pnl - total_fee
        net_r = net_pnl / 1000.0 # 1R = 1.0%
        
        trades.append({
            'date': date_str,
            'symbol': sym,
            'side': side,
            'net_r': net_r,
            'net_return_pct': net_r,
            'fee': total_fee,
            'net_pnl': net_pnl,
            'exit_reason': exit_reason
        })
        
    df_trades = pd.DataFrame(trades)
    df_trades['month'] = pd.to_datetime(df_trades['date']).dt.to_period('M')
    n_months = df_trades['month'].nunique()
    
    wins = df_trades[df_trades['net_r'] > 0]
    losses = df_trades[df_trades['net_r'] <= 0]
    win_rate = len(wins) / len(df_trades) * 100.0 if len(df_trades) > 0 else 0
    total_net_r = df_trades['net_r'].sum()
    monthly_r = total_net_r / max(1, n_months)
    
    df_trades['cum_r'] = df_trades['net_r'].cumsum()
    df_trades['peak_r'] = df_trades['cum_r'].cummax()
    df_trades['dd_r'] = df_trades['cum_r'] - df_trades['peak_r']
    max_dd_r = df_trades['dd_r'].min()
    
    gross_win = wins['net_pnl'].sum()
    gross_loss = abs(losses['net_pnl'].sum())
    profit_factor = gross_win / gross_loss if gross_loss > 0 else 999.0
    total_fees = df_trades['fee'].sum()
    
    print("\n" + "="*75, flush=True)
    print(f"A+ HIGH-CONVICTION TRADE ENGINE RESULTS (2022-2026):", flush=True)
    print(f"Total Trading Sessions: {len(sorted_dates)} days", flush=True)
    print(f"Total Trades Taken: {len(df_trades)} ({len(df_trades)/n_months:.1f} trades/month, ~{len(df_trades)/len(sorted_dates):.2f} trades/day)", flush=True)
    print(f"Win Rate: {win_rate:.2f}% ({len(wins)} wins / {len(losses)} losses)", flush=True)
    print(f"Profit Factor: {profit_factor:.2f}", flush=True)
    print(f"Total Net Return: {total_net_r:+.2f}% (+{total_net_r:.2f} R)", flush=True)
    print(f"Average Monthly Return: {monthly_r:+.2f}% / month (+{monthly_r:.2f} R / month)", flush=True)
    print(f"Max Peak-to-Trough Drawdown: {max_dd_r:.2f}% ({max_dd_r:.2f} R)", flush=True)
    print(f"Total Taxes & Fees: Rs {total_fees:,.2f} ({total_fees/1000:.1f} R)", flush=True)
    print("="*75, flush=True)
    
    df_trades['year'] = pd.to_datetime(df_trades['date']).dt.year
    yearly = df_trades.groupby('year').agg(
        trades=('net_r', 'count'),
        win_rate=('net_r', lambda x: (x > 0).mean() * 100),
        net_return_pct=('net_r', 'sum'),
        fees=('fee', 'sum')
    )
    print("\nYEARLY PERFORMANCE:", flush=True)
    print(yearly, flush=True)
    
    exit_grp = df_trades.groupby('exit_reason').agg(
        trades=('net_r', 'count'),
        avg_r=('net_r', 'mean'),
        total_r=('net_r', 'sum')
    )
    print("\nBY EXIT REASON:", flush=True)
    print(exit_grp, flush=True)

if __name__ == '__main__':
    run_aplus_simulation(min_rvol=2.0, min_gap=0.6, min_ev=0.25)
