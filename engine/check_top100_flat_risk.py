"""
Check Top 100 Gap Strategy with Flat 1.0% Risk (No Governor Throttling)
To compare Return vs Drawdown trade-off.
"""

import os
import glob
import numpy as np
import pandas as pd
from datetime import time as dtime

CACHE_DIR = "data/nifty100_cache"

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

def test_flat_and_variations():
    files = glob.glob(os.path.join(CACHE_DIR, "*.parquet"))
    symbol_data = {}
    for f in files:
        sym = os.path.basename(f).replace(".parquet", "")
        symbol_data[sym] = pd.read_parquet(f)
        
    all_dates = set()
    symbol_days = {}
    
    for sym, df in symbol_data.items():
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
            if len(or_vols) >= 5:
                avg_v = np.mean(or_vols[-15:])
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
    if len(sorted_dates) > 5: sorted_dates = sorted_dates[5:]
    
    # Compare Flat 1.0% Risk vs Dynamic Risk Governor
    for use_gov in [False, True]:
        label = "DYNAMIC GOVERNOR" if use_gov else "FLAT 1.0% RISK"
        trades = []
        consecutive_losses = 0
        
        for date_str in sorted_dates:
            if use_gov:
                if consecutive_losses == 0: risk_pct = 1.00
                elif consecutive_losses == 1: risk_pct = 0.75
                else: risk_pct = 0.50
            else:
                risk_pct = 1.00
                
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
                d_df = info['df']
                
                if abs(gap_pct) < 1.0: continue
                if rvol < 2.0: continue
                
                if gap_pct >= 1.0:
                    for b_i in range(3, min(16, len(d_df) - 6)):
                        bar = d_df.iloc[b_i]
                        if bar['Close'] > h15 and bar['Close'] > bar['vwap']:
                            entry_p = bar['Close']
                            raw_sl = m15
                            if (entry_p - raw_sl) / entry_p < 0.0030: raw_sl = entry_p * (1.0 - 0.0030)
                            if (entry_p - raw_sl) / entry_p > 0.0085: raw_sl = entry_p * (1.0 - 0.0085)
                            risk_pts = entry_p - raw_sl
                            if risk_pts <= 0: continue
                            score = rvol * (1.0 + abs(gap_pct))
                            candidates.append({
                                'symbol': sym, 'side': 'BUY', 'bar_idx': b_i,
                                'entry_p': entry_p, 'sl_p': raw_sl, 'risk_pts': risk_pts,
                                'score': score, 'df': d_df
                            })
                            break
                elif gap_pct <= -1.0:
                    for b_i in range(3, min(16, len(d_df) - 6)):
                        bar = d_df.iloc[b_i]
                        if bar['Close'] < l15 and bar['Close'] < bar['vwap']:
                            entry_p = bar['Close']
                            raw_sl = m15
                            if (raw_sl - entry_p) / entry_p < 0.0030: raw_sl = entry_p * (1.0 + 0.0030)
                            if (raw_sl - entry_p) / entry_p > 0.0085: raw_sl = entry_p * (1.0 + 0.0085)
                            risk_pts = raw_sl - entry_p
                            if risk_pts <= 0: continue
                            score = rvol * (1.0 + abs(gap_pct))
                            candidates.append({
                                'symbol': sym, 'side': 'SELL', 'bar_idx': b_i,
                                'entry_p': entry_p, 'sl_p': raw_sl, 'risk_pts': risk_pts,
                                'score': score, 'df': d_df
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
            
            if side == 'BUY':
                for j in range(b_idx + 1, len(d_df)):
                    bar = d_df.iloc[j]
                    h, l, c = bar['High'], bar['Low'], bar['Close']
                    ema_v = bar['ema9']
                    if l <= curr_sl:
                        if not t1_hit: exit_p1, exit_p2, exit_pr = curr_sl, curr_sl, curr_sl
                        elif not t2_hit: exit_p2, exit_pr = curr_sl, curr_sl
                        else: exit_pr = curr_sl
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
                            break
                    if j == len(d_df) - 1 or j >= 72:
                        if not t1_hit: exit_p1 = c
                        if not t2_hit: exit_p2 = c
                        exit_pr = c
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
                        if not t1_hit: exit_p1, exit_p2, exit_pr = curr_sl, curr_sl, curr_sl
                        elif not t2_hit: exit_p2, exit_pr = curr_sl, curr_sl
                        else: exit_pr = curr_sl
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
                            break
                    if j == len(d_df) - 1 or j >= 72:
                        if not t1_hit: exit_p1 = c
                        if not t2_hit: exit_p2 = c
                        exit_pr = c
                        break
                p1 = s_t1 * (entry_p - exit_p1)
                f1 = compute_zerodha_charges(s_t1 * exit_p1, s_t1 * entry_p)
                p2 = s_t2 * (entry_p - exit_p2) if s_t2 > 0 else 0
                f2 = compute_zerodha_charges(s_t2 * entry_p, s_t2 * exit_p2) if s_t2 > 0 else 0
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
                'ret_pct': ret_pct,
                'fee': total_fee
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
        
        print(f"\n[{label}] 55 Trading Days (Top 100 NSE Stocks):")
        print(f"  Trades: {len(df_t)} ({len(df_t)/n_months:.1f}/mo) | WinRate: {win_rate:.2f}% | Total Net: {total_ret:+.2f}% | Monthly: {monthly_ret:+.2f}%/mo | MaxDD: {max_dd:.2f}%")

if __name__ == '__main__':
    test_flat_and_variations()
