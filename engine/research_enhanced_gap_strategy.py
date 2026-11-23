"""
Enhanced User Gap Strategy
Taking the user's Gap Concept and adding institutional edge:
1. Core Idea: Gap > 1.0% (at 09:30 AM close vs prev close)
2. Direction: Momentum (Gap Up -> BUY; Gap Down -> SHORT)
3. Volume Validation: RVOL >= 1.8x (Institutional conviction)
4. Trigger Confirmation: Wait for bar to break 15m High (for BUY) or 15m Low (for SHORT)
5. Stop Loss: 15m range midpoint or 15m low/high (enforcing 0.35% - 0.85% floor/ceiling)
6. Profit Scaling: 40% at +2.0R, 30% at +3.5R, 30% trailing 9 EMA
7. Dynamic Consecutive Loss Governor (1.0% -> 0.75% -> 0.50%)
8. Exact Zerodha statutory tariffs
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

def run_enhanced_gap_test():
    symbols = [
        'ADANIENT', 'AXISBANK', 'BAJFINANCE', 'BHARTIARTL', 'COALINDIA', 
        'GRASIM', 'HCLTECH', 'HDFCBANK', 'HINDUNILVR', 'ICICIBANK', 
        'INDUSINDBK', 'INFY', 'ITC', 'JSWSTEEL', 'KOTAKBANK', 
        'LT', 'MARUTI', 'NTPC', 'ONGC', 'POWERGRID', 
        'RELIANCE', 'SBIN', 'SUNPHARMA', 'TATAMOTORS', 'TATASTEEL', 
        'TCS', 'TECHM', 'TITAN', 'ULTRACEMCO', 'WIPRO'
    ]
    
    print("Loading 30 symbols for Enhanced Gap Test...", flush=True)
    symbol_days = {}
    all_dates = set()
    
    for sym in symbols:
        df = load_symbol_5m(sym)
        if df is None or len(df) == 0: continue
        symbol_days[sym] = {}
        grouped = df.groupby('date_str')
        prev_close = None
        or_vols = []
        
        for d_str, d_df in grouped:
            d_df = d_df.reset_index(drop=True)
            if len(d_df) < 25:
                if len(d_df) > 0: prev_close = d_df.iloc[-1]['Close']
                continue
                
            close_p = d_df.iloc[-1]['Close']
            
            c15 = d_df.iloc[0:3]
            open_15m = c15.iloc[0]['Open']
            high_15m = c15['High'].max()
            low_15m = c15['Low'].min()
            close_15m = c15.iloc[-1]['Close']
            vol_15m = c15['Volume'].sum()
            range_15m = high_15m - low_15m
            
            gap_pct = 0.0
            if prev_close is not None and prev_close > 0:
                gap_pct = (close_15m - prev_close) / prev_close * 100.0
                
            rvol = 1.0
            if len(or_vols) >= 10:
                avg_v = np.mean(or_vols[-20:])
                if avg_v > 0: rvol = vol_15m / avg_v
            or_vols.append(vol_15m)
            
            prev_close = close_p
            
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
                symbol_days[sym][d_str] = {
                    'df': d_df,
                    'high_15m': high_15m,
                    'low_15m': low_15m,
                    'mid_15m': (high_15m + low_15m) / 2.0,
                    'close_15m': close_15m,
                    'range_15m': range_15m,
                    'gap_pct': gap_pct,
                    'rvol': rvol
                }
                
    sorted_dates = sorted(list(all_dates))
    print(f"Total dates: {len(sorted_dates)} (4.8 Years)", flush=True)
    
    # We test:
    # Gap thresholds: 0.8% vs 1.0% vs 1.2%
    # RVOL thresholds: 1.0x (raw) vs 1.5x vs 2.0x
    for min_gap in [1.0]:
        for min_rvol in [1.0, 1.5, 2.0]:
            trades = []
            consecutive_losses = 0
            
            for date_str in sorted_dates:
                if consecutive_losses == 0:
                    risk_pct = 1.00
                elif consecutive_losses == 1:
                    risk_pct = 0.75
                else:
                    risk_pct = 0.50
                risk_cash = risk_pct * 1000.0
                
                candidates = []
                for sym, d_dict in symbol_days.items():
                    if date_str not in d_dict: continue
                    info = d_dict[date_str]
                    gap_pct = info['gap_pct']
                    rvol = info['rvol']
                    h15 = info['high_15m']
                    l15 = info['low_15m']
                    m15 = info['mid_15m']
                    c15 = info['close_15m']
                    d_df = info['df']
                    
                    if abs(gap_pct) < min_gap: continue
                    if rvol < min_rvol: continue
                    
                    # Direction: Momentum
                    if gap_pct >= min_gap: # BUY
                        # Check bars 3 to 12 for break of 15m high
                        for b_i in range(3, min(14, len(d_df) - 6)):
                            bar = d_df.iloc[b_i]
                            if bar['Close'] > h15 and bar['Close'] > bar['vwap']:
                                entry_p = bar['Close']
                                raw_sl = m15 # SL at 50% of 15m range (midpoint)
                                if (entry_p - raw_sl) / entry_p < 0.0030: raw_sl = entry_p * (1.0 - 0.0030)
                                if (entry_p - raw_sl) / entry_p > 0.0085: raw_sl = entry_p * (1.0 - 0.0085)
                                risk_pts = entry_p - raw_sl
                                if risk_pts <= 0: continue
                                score = rvol * (1.0 + abs(gap_pct))
                                candidates.append({
                                    'symbol': sym,
                                    'side': 'BUY',
                                    'bar_idx': b_i,
                                    'entry_p': entry_p,
                                    'sl_p': raw_sl,
                                    'risk_pts': risk_pts,
                                    'score': score,
                                    'df': d_df
                                })
                                break
                    elif gap_pct <= -min_gap: # SHORT
                        for b_i in range(3, min(14, len(d_df) - 6)):
                            bar = d_df.iloc[b_i]
                            if bar['Close'] < l15 and bar['Close'] < bar['vwap']:
                                entry_p = bar['Close']
                                raw_sl = m15 # SL at 50% of 15m range (midpoint)
                                if (raw_sl - entry_p) / entry_p < 0.0030: raw_sl = entry_p * (1.0 + 0.0030)
                                if (raw_sl - entry_p) / entry_p > 0.0085: raw_sl = entry_p * (1.0 + 0.0085)
                                risk_pts = raw_sl - entry_p
                                if risk_pts <= 0: continue
                                score = rvol * (1.0 + abs(gap_pct))
                                candidates.append({
                                    'symbol': sym,
                                    'side': 'SELL',
                                    'bar_idx': b_i,
                                    'entry_p': entry_p,
                                    'sl_p': raw_sl,
                                    'risk_pts': risk_pts,
                                    'score': score,
                                    'df': d_df
                                })
                                break
                                
                if not candidates: continue
                candidates.sort(key=lambda x: -x['score'])
                trade = candidates[0]
                
                sym = trade['symbol']
                side = trade['side']
                entry_p = trade['entry_p']
                sl_p = trade['sl_p']
                risk_pts = trade['risk_pts']
                d_df = trade['df']
                b_idx = trade['bar_idx']
                
                shares = int(risk_cash / risk_pts)
                if shares < 1: shares = 1
                
                s_t1 = int(shares * 0.40)
                s_t2 = int(shares * 0.30)
                s_run = shares - s_t1 - s_t2
                if s_t1 < 1: s_t1 = 1
                
                t1_p = entry_p + (2.0 * risk_pts) if side == 'BUY' else entry_p - (2.0 * risk_pts)
                t2_p = entry_p + (3.5 * risk_pts) if side == 'BUY' else entry_p - (3.5 * risk_pts)
                
                t1_hit, t2_hit = False, False
                curr_sl = sl_p
                exit_p1, exit_p2, exit_pr = 0.0, 0.0, 0.0
                exit_reason = ""
                
                if side == 'BUY':
                    for j in range(b_idx + 1, len(d_df)):
                        bar = d_df.iloc[j]
                        h, l, c = bar['High'], bar['Low'], bar['Close']
                        ema_v = bar['ema9']
                        
                        if l <= curr_sl:
                            if not t1_hit:
                                exit_p1, exit_p2, exit_pr = curr_sl, curr_sl, curr_sl
                                exit_reason = "STOP_INITIAL"
                            elif not t2_hit:
                                exit_p2, exit_pr = curr_sl, curr_sl
                                exit_reason = "RUNNER_BE_STOP"
                            else:
                                exit_pr = curr_sl
                                exit_reason = "RUNNER_LOCK_STOP"
                            break
                        if not t1_hit and h >= t1_p:
                            t1_hit = True
                            exit_p1 = t1_p
                            curr_sl = entry_p
                        if t1_hit and not t2_hit and h >= t2_p:
                            t2_hit = True
                            exit_p2 = t2_p
                            curr_sl = entry_p + (1.5 * risk_pts)
                        if t2_hit and j >= 45:
                            if c < ema_v:
                                exit_pr = c
                                exit_reason = "RUNNER_EMA_TRAIL"
                                break
                        if j == len(d_df) - 1 or j >= 72:
                            if not t1_hit: exit_p1 = c
                            if not t2_hit: exit_p2 = c
                            exit_pr = c
                            exit_reason = "EOD_SQUAREOFF"
                            break
                    p1 = s_t1 * (exit_p1 - entry_p)
                    f1 = compute_zerodha_charges(s_t1 * entry_p, s_t1 * exit_p1)
                    p2 = s_t2 * (exit_p2 - entry_p) if s_t2 > 0 else 0
                    f2 = compute_zerodha_charges(s_t2 * entry_p, s_t2 * exit_p2) if s_t2 > 0 else 0
                    pr = s_run * (exit_pr - entry_p) if s_run > 0 else 0
                    fr = compute_zerodha_charges(s_run * entry_p, s_run * exit_pr) if s_run > 0 else 0
                else: # SELL
                    for j in range(b_idx + 1, len(d_df)):
                        bar = d_df.iloc[j]
                        h, l, c = bar['High'], bar['Low'], bar['Close']
                        ema_v = bar['ema9']
                        
                        if h >= curr_sl:
                            if not t1_hit:
                                exit_p1, exit_p2, exit_pr = curr_sl, curr_sl, curr_sl
                                exit_reason = "STOP_INITIAL"
                            elif not t2_hit:
                                exit_p2, exit_pr = curr_sl, curr_sl
                                exit_reason = "RUNNER_BE_STOP"
                            else:
                                exit_pr = curr_sl
                                exit_reason = "RUNNER_LOCK_STOP"
                            break
                        if not t1_hit and l <= t1_p:
                            t1_hit = True
                            exit_p1 = t1_p
                            curr_sl = entry_p
                        if t1_hit and not t2_hit and l <= t2_p:
                            t2_hit = True
                            exit_p2 = t2_p
                            curr_sl = entry_p - (1.5 * risk_pts)
                        if t2_hit and j >= 45:
                            if c > ema_v:
                                exit_pr = c
                                exit_reason = "RUNNER_EMA_TRAIL"
                                break
                        if j == len(d_df) - 1 or j >= 72:
                            if not t1_hit: exit_p1 = c
                            if not t2_hit: exit_p2 = c
                            exit_pr = c
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
                ret_pct = net_pnl / 1000.0
                
                if ret_pct > 0: consecutive_losses = 0
                else: consecutive_losses += 1
                
                trades.append({
                    'date': date_str,
                    'symbol': sym,
                    'side': side,
                    'net_pnl': net_pnl,
                    'ret_pct': ret_pct,
                    'fee': total_fee,
                    'exit_reason': exit_reason
                })
                
            df_t = pd.DataFrame(trades)
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
            
            print(f"ENHANCED GAP (Gap>={min_gap}%, RVOL>={min_rvol}x):", flush=True)
            print(f"  Trades: {len(df_t)} ({len(df_t)/n_months:.1f}/mo) | WinRate: {win_rate:5.2f}% | PF: {pf:4.2f} | Net: {total_ret:+7.2f}% | MoRet: {monthly_ret:+5.2f}% | MaxDD: {max_dd:6.2f}% | Fees: Rs {total_fee:,.0f}", flush=True)

if __name__ == '__main__':
    run_enhanced_gap_test()
