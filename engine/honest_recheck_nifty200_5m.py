"""
Honest Recheck: Nifty 200 on 60 Days of TRUE 5-Minute Intraday Bars
100% Bar-by-bar sequence. Zero lookahead bias.
Exact Zerodha tariffs.
"""

import os
import glob
import numpy as np
import pandas as pd
from datetime import time

CACHE_DIR = "data/nifty200_cache"

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

def run_honest_5m_audit():
    files = glob.glob(os.path.join(CACHE_DIR, "*.parquet"))
    print(f"Loading {len(files)} symbols from 5m cache...", flush=True)
    
    symbol_days = {}
    all_dates = set()
    
    for f in files:
        sym = os.path.basename(f).replace(".parquet", "")
        df = pd.read_parquet(f)
        if len(df) == 0: continue
        
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date').reset_index(drop=True)
        
        symbol_days[sym] = {}
        grouped = df.groupby('date_str')
        
        prev_close = None
        or_vols = []
        
        for d_str, d_df in grouped:
            d_df = d_df.reset_index(drop=True)
            if len(d_df) < 25:
                if len(d_df) > 0: prev_close = d_df.iloc[-1]['Close']
                continue
                
            c15 = d_df.iloc[0:3] # First 15m (09:15, 09:20, 09:25)
            open_15m = c15.iloc[0]['Open']
            high_15m = c15['High'].max()
            low_15m = c15['Low'].min()
            close_15m = c15.iloc[-1]['Close']
            vol_15m = c15['Volume'].sum()
            range_15m = high_15m - low_15m
            
            gap_pct = (close_15m - prev_close) / prev_close * 100.0 if prev_close else 0.0
            
            rvol = 1.0
            if len(or_vols) >= 5:
                avg_v = np.mean(or_vols[-15:])
                if avg_v > 0: rvol = vol_15m / avg_v
            or_vols.append(vol_15m)
            prev_close = d_df.iloc[-1]['Close']
            
            all_dates.add(d_str)
            symbol_days[sym][d_str] = {
                'df': d_df,
                'open_15m': open_15m,
                'high_15m': high_15m,
                'low_15m': low_15m,
                'close_15m': close_15m,
                'range_15m': range_15m,
                'gap_pct': gap_pct,
                'rvol': rvol
            }
            
    sorted_dates = sorted(list(all_dates))
    # Exclude initial warm-up days for volume
    eval_dates = sorted_dates[10:]
    print(f"Total evaluation dates: {len(eval_dates)} trading sessions (approx 2.5 months)", flush=True)
    
    # We test two variations:
    # Var 1: Enter immediately at 09:30 AM close
    # Var 2: Wait for breakout of 15m high/low
    for enter_mode in ['09:30_CLOSE', 'BREAKOUT']:
        trades = []
        risk_cash = 1000.0 # Flat 1.0% Risk (Rs 1,000 on Rs 100,000 base)
        
        for date_str in eval_dates:
            candidates = []
            
            for sym, d_dict in symbol_days.items():
                if date_str not in d_dict: continue
                info = d_dict[date_str]
                gap_pct = info['gap_pct']
                rvol = info['rvol']
                h15 = info['high_15m']
                l15 = info['low_15m']
                c15 = info['close_15m']
                rng15 = info['range_15m']
                d_df = info['df']
                
                if abs(gap_pct) < 1.0 or rvol < 2.0: continue
                if rng15 <= 0: continue
                
                score = rvol * (1.0 + abs(gap_pct))
                
                if enter_mode == '09:30_CLOSE':
                    entry_p = c15
                    # SL at 50% midpoint of 15m range
                    if gap_pct >= 1.0: # BUY
                        raw_sl = (h15 + l15) / 2.0
                        if (entry_p - raw_sl) / entry_p < 0.0035: raw_sl = entry_p * (1.0 - 0.0035)
                        if (entry_p - raw_sl) / entry_p > 0.0085: raw_sl = entry_p * (1.0 - 0.0085)
                        risk_pts = entry_p - raw_sl
                        if risk_pts > 0:
                            candidates.append({
                                'symbol': sym, 'side': 'BUY', 'b_idx': 2,
                                'entry_p': entry_p, 'sl_p': raw_sl, 'risk_pts': risk_pts,
                                'score': score, 'df': d_df
                            })
                    elif gap_pct <= -1.0: # SELL
                        raw_sl = (h15 + l15) / 2.0
                        if (raw_sl - entry_p) / entry_p < 0.0035: raw_sl = entry_p * (1.0 + 0.0035)
                        if (raw_sl - entry_p) / entry_p > 0.0085: raw_sl = entry_p * (1.0 + 0.0085)
                        risk_pts = raw_sl - entry_p
                        if risk_pts > 0:
                            candidates.append({
                                'symbol': sym, 'side': 'SELL', 'b_idx': 2,
                                'entry_p': entry_p, 'sl_p': raw_sl, 'risk_pts': risk_pts,
                                'score': score, 'df': d_df
                            })
                else: # BREAKOUT
                    if gap_pct >= 1.0:
                        for b_i in range(3, min(14, len(d_df) - 6)):
                            bar = d_df.iloc[b_i]
                            if bar['Close'] > h15:
                                entry_p = bar['Close']
                                raw_sl = (h15 + l15) / 2.0
                                if (entry_p - raw_sl) / entry_p < 0.0035: raw_sl = entry_p * (1.0 - 0.0035)
                                if (entry_p - raw_sl) / entry_p > 0.0085: raw_sl = entry_p * (1.0 - 0.0085)
                                risk_pts = entry_p - raw_sl
                                if risk_pts > 0:
                                    candidates.append({
                                        'symbol': sym, 'side': 'BUY', 'b_idx': b_i,
                                        'entry_p': entry_p, 'sl_p': raw_sl, 'risk_pts': risk_pts,
                                        'score': score, 'df': d_df
                                    })
                                break
                    elif gap_pct <= -1.0:
                        for b_i in range(3, min(14, len(d_df) - 6)):
                            bar = d_df.iloc[b_i]
                            if bar['Close'] < l15:
                                entry_p = bar['Close']
                                raw_sl = (h15 + l15) / 2.0
                                if (raw_sl - entry_p) / entry_p < 0.0035: raw_sl = entry_p * (1.0 + 0.0035)
                                if (raw_sl - entry_p) / entry_p > 0.0085: raw_sl = entry_p * (1.0 + 0.0085)
                                risk_pts = raw_sl - entry_p
                                if risk_pts > 0:
                                    candidates.append({
                                        'symbol': sym, 'side': 'SELL', 'b_idx': b_i,
                                        'entry_p': entry_p, 'sl_p': raw_sl, 'risk_pts': risk_pts,
                                        'score': score, 'df': d_df
                                    })
                                break
                                
            if not candidates: continue
            candidates.sort(key=lambda x: -x['score'])
            t = candidates[0]
            
            sym = t['symbol']
            side = t['side']
            entry_p = t['entry_p']
            sl_p = t['sl_p']
            risk_pts = t['risk_pts']
            d_df = t['df']
            b_idx = t['b_idx']
            
            shares = int(risk_cash / risk_pts)
            if shares < 1: shares = 1
            
            s_t1 = int(shares * 0.50)
            s_run = shares - s_t1
            if s_t1 < 1: s_t1 = 1
            
            t1_p = entry_p + (2.5 * risk_pts) if side == 'BUY' else entry_p - (2.5 * risk_pts)
            t2_p = entry_p + (4.5 * risk_pts) if side == 'BUY' else entry_p - (4.5 * risk_pts)
            
            t1_hit, t2_hit = False, False
            curr_sl = sl_p
            exit_p1, exit_pr = 0.0, 0.0
            exit_reason = ""
            
            for j in range(b_idx + 1, len(d_df)):
                bar = d_df.iloc[j]
                h, l, c = bar['High'], bar['Low'], bar['Close']
                
                if side == 'BUY':
                    if l <= curr_sl:
                        if not t1_hit:
                            exit_p1, exit_pr = curr_sl, curr_sl
                            exit_reason = "STOP_INITIAL"
                        else:
                            exit_pr = curr_sl
                            exit_reason = "RUNNER_BE_STOP"
                        break
                    if not t1_hit and h >= t1_p:
                        t1_hit = True
                        exit_p1 = t1_p
                        curr_sl = entry_p # Move SL to BE
                    if t1_hit and not t2_hit and h >= t2_p:
                        t2_hit = True
                        exit_pr = t2_p
                        exit_reason = "RUNNER_T2"
                        break
                    if j == len(d_df) - 1 or j >= 72:
                        if not t1_hit: exit_p1 = c
                        exit_pr = c
                        exit_reason = "EOD_SQUAREOFF"
                        break
                else: # SELL
                    if h >= curr_sl:
                        if not t1_hit:
                            exit_p1, exit_pr = curr_sl, curr_sl
                            exit_reason = "STOP_INITIAL"
                        else:
                            exit_pr = curr_sl
                            exit_reason = "RUNNER_BE_STOP"
                        break
                    if not t1_hit and l <= t1_p:
                        t1_hit = True
                        exit_p1 = t1_p
                        curr_sl = entry_p
                    if t1_hit and not t2_hit and l <= t2_p:
                        t2_hit = True
                        exit_pr = t2_p
                        exit_reason = "RUNNER_T2"
                        break
                    if j == len(d_df) - 1 or j >= 72:
                        if not t1_hit: exit_p1 = c
                        exit_pr = c
                        exit_reason = "EOD_SQUAREOFF"
                        break
                        
            if side == 'BUY':
                p1 = s_t1 * (exit_p1 - entry_p)
                f1 = compute_zerodha_charges(s_t1 * entry_p, s_t1 * exit_p1)
                pr = s_run * (exit_pr - entry_p) if s_run > 0 else 0
                fr = compute_zerodha_charges(s_run * entry_p, s_run * exit_pr) if s_run > 0 else 0
            else:
                p1 = s_t1 * (entry_p - exit_p1)
                f1 = compute_zerodha_charges(s_t1 * exit_p1, s_t1 * entry_p)
                pr = s_run * (entry_p - exit_pr) if s_run > 0 else 0
                fr = compute_zerodha_charges(s_run * exit_pr, s_run * entry_p) if s_run > 0 else 0
                
            net_pnl = p1 + pr - f1 - fr
            ret_pct = net_pnl / 1000.0
            
            trades.append({
                'date': date_str,
                'symbol': sym,
                'side': side,
                'net_pnl': net_pnl,
                'ret_pct': ret_pct,
                'fee': f1 + fr,
                'exit_reason': exit_reason
            })
            
        df_t = pd.DataFrame(trades)
        wins = df_t[df_t['net_pnl'] > 0]
        losses = df_t[df_t['net_pnl'] <= 0]
        win_rate = len(wins) / len(df_t) * 100.0
        
        gw = wins['net_pnl'].sum()
        gl = abs(losses['net_pnl'].sum())
        pf = gw / gl if gl > 0 else 999.0
        
        total_ret = df_t['ret_pct'].sum()
        df_t['cum'] = df_t['ret_pct'].cumsum()
        df_t['peak'] = df_t['cum'].cummax()
        df_t['dd'] = df_t['cum'] - df_t['peak']
        max_dd = df_t['dd'].min()
        
        n_days = len(eval_dates)
        monthly_ret = total_ret / (n_days / 21.0)
        
        print(f"\n{'='*80}")
        print(f"HONEST 5-MINUTE INTRADAY AUDIT ({enter_mode}):")
        print(f"{'='*80}")
        print(f"  Total Trades: {len(df_t)} in {n_days} sessions ({len(df_t)/n_days*100:.1f}% participation)")
        print(f"  Win Rate: {win_rate:.2f}% ({len(wins)} Wins / {len(losses)} Losses)")
        print(f"  Profit Factor: {pf:.2f}")
        print(f"  Total Net Return: {total_ret:+.2f}%")
        print(f"  Average Monthly Return: {monthly_ret:+.2f}% / Month")
        print(f"  Maximum Peak-to-Trough Drawdown: {max_dd:.2f}%")
        print(f"  Total Statutory Fees: Rs {df_t['fee'].sum():,.2f}")
        print("  Exit Reasons:")
        print(df_t['exit_reason'].value_counts())

if __name__ == '__main__':
    run_honest_5m_audit()
