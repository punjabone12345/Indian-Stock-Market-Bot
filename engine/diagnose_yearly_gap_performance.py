"""
Forensic Diagnostic of Yearly Gap Performance (2022 to 2026)
Diagnosing why 2026 was stronger and how 2022-2025 behaved under Flat Risk vs Compounding.
"""

import os
import glob
import numpy as np
import pandas as pd

CACHE_DIR = "data/nifty200_daily_cache"

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

def diagnose():
    files = glob.glob(os.path.join(CACHE_DIR, "*.parquet"))
    symbol_data = {}
    for f in files:
        sym = os.path.basename(f).replace(".parquet", "")
        symbol_data[sym] = pd.read_parquet(f)
        
    symbol_days = {}
    all_dates = set()
    
    for sym, df in symbol_data.items():
        df = df.sort_values('Date').reset_index(drop=True)
        df['prev_close'] = df['Close'].shift(1)
        df['gap_pct'] = (df['Open'] - df['prev_close']) / df['prev_close'] * 100.0
        df['vol_20avg'] = df['Volume'].rolling(20).mean().shift(1)
        df['rvol'] = df['Volume'] / np.where(df['vol_20avg'] > 0, df['vol_20avg'], df['Volume'])
        df['day_range'] = df['High'] - df['Low']
        
        symbol_days[sym] = {}
        for idx, row in df.iterrows():
            d_str = row['date_str']
            year = int(d_str[:4])
            if year >= 2022:
                all_dates.add(d_str)
                symbol_days[sym][d_str] = row
                
    sorted_dates = sorted(list(all_dates))
    
    trades = []
    risk_cash = 1000.0 # Flat 1.0% Risk (Rs 1,000 on Rs 100,000 base)
    
    for date_str in sorted_dates:
        candidates = []
        for sym, d_dict in symbol_days.items():
            if date_str not in d_dict: continue
            row = d_dict[date_str]
            gap_pct = row['gap_pct']
            rvol = row['rvol']
            open_p = row['Open']
            high_p = row['High']
            low_p = row['Low']
            close_p = row['Close']
            day_range = row['day_range']
            
            if np.isnan(gap_pct) or np.isnan(rvol): continue
            if abs(gap_pct) < 1.0: continue
            if rvol < 2.0: continue
            if day_range <= 0 or open_p <= 0: continue
            
            sl_dist = max(open_p * 0.0035, min(open_p * 0.0085, day_range * 0.50))
            score = rvol * (1.0 + abs(gap_pct))
            
            if gap_pct >= 1.0:
                candidates.append({
                    'symbol': sym, 'side': 'BUY', 'entry_p': open_p, 'sl_p': open_p - sl_dist,
                    'risk_pts': sl_dist, 'high_p': high_p, 'low_p': low_p, 'close_p': close_p,
                    'score': score, 'gap_pct': gap_pct, 'rvol': rvol
                })
            elif gap_pct <= -1.0:
                candidates.append({
                    'symbol': sym, 'side': 'SELL', 'entry_p': open_p, 'sl_p': open_p + sl_dist,
                    'risk_pts': sl_dist, 'high_p': high_p, 'low_p': low_p, 'close_p': close_p,
                    'score': score, 'gap_pct': gap_pct, 'rvol': rvol
                })
                
        if not candidates: continue
        candidates.sort(key=lambda x: -x['score'])
        trade = candidates[0]
        
        sym = trade['symbol']
        side = trade['side']
        entry_p = trade['entry_p']
        sl_p = trade['sl_p']
        risk_pts = trade['risk_pts']
        high_p = trade['high_p']
        low_p = trade['low_p']
        close_p = trade['close_p']
        
        shares = int(risk_cash / risk_pts)
        if shares < 1: shares = 1
        
        s_t1 = int(shares * 0.40)
        s_t2 = int(shares * 0.30)
        s_run = shares - s_t1 - s_t2
        if s_t1 < 1: s_t1 = 1
        
        t1_p = entry_p + (2.0 * risk_pts) if side == 'BUY' else entry_p - (2.0 * risk_pts)
        t2_p = entry_p + (3.5 * risk_pts) if side == 'BUY' else entry_p - (3.5 * risk_pts)
        
        exit_p1, exit_p2, exit_pr = 0.0, 0.0, 0.0
        exit_reason = ""
        
        if side == 'BUY':
            if low_p <= sl_p:
                exit_p1, exit_p2, exit_pr = sl_p, sl_p, sl_p
                exit_reason = "STOP_INITIAL"
            else:
                if high_p >= t1_p:
                    exit_p1 = t1_p
                    if high_p >= t2_p:
                        exit_p2 = t2_p
                        exit_pr = close_p
                        exit_reason = "RUNNER_PROFIT"
                    else:
                        exit_p2 = close_p
                        exit_pr = close_p
                        exit_reason = "T1_HIT_EOD"
                else:
                    exit_p1, exit_p2, exit_pr = close_p, close_p, close_p
                    exit_reason = "EOD_CLOSE"
            p1 = s_t1 * (exit_p1 - entry_p)
            f1 = compute_zerodha_charges(s_t1 * entry_p, s_t1 * exit_p1)
            p2 = s_t2 * (exit_p2 - entry_p) if s_t2 > 0 else 0
            f2 = compute_zerodha_charges(s_t2 * entry_p, s_t2 * exit_p2) if s_t2 > 0 else 0
            pr = s_run * (exit_pr - entry_p) if s_run > 0 else 0
            fr = compute_zerodha_charges(s_run * entry_p, s_run * exit_pr) if s_run > 0 else 0
        else: # SELL
            if high_p >= sl_p:
                exit_p1, exit_p2, exit_pr = sl_p, sl_p, sl_p
                exit_reason = "STOP_INITIAL"
            else:
                if low_p <= t1_p:
                    exit_p1 = t1_p
                    if low_p <= t2_p:
                        exit_p2 = t2_p
                        exit_pr = close_p
                        exit_reason = "RUNNER_PROFIT"
                    else:
                        exit_p2 = close_p
                        exit_pr = close_p
                        exit_reason = "T1_HIT_EOD"
                else:
                    exit_p1, exit_pr = close_p, close_p
                    exit_reason = "EOD_CLOSE"
            p1 = s_t1 * (entry_p - exit_p1)
            f1 = compute_zerodha_charges(s_t1 * exit_p1, s_t1 * entry_p)
            p2 = s_t2 * (exit_p2 - entry_p) if s_t2 > 0 else 0
            f2 = compute_zerodha_charges(s_t2 * entry_p, s_t2 * exit_p2) if s_t2 > 0 else 0
            pr = s_run * (entry_p - exit_pr) if s_run > 0 else 0
            fr = compute_zerodha_charges(s_run * exit_pr, s_run * entry_p) if s_run > 0 else 0
            
        gross_pnl = p1 + p2 + pr
        fee = f1 + f2 + fr
        net_pnl = gross_pnl - fee
        ret_pct = net_pnl / 1000.0
        
        trades.append({
            'date': date_str,
            'year': int(date_str[:4]),
            'symbol': sym,
            'side': side,
            'ret_pct': ret_pct,
            'net_pnl': net_pnl,
            'fee': fee,
            'gap_pct': trade['gap_pct'],
            'rvol': trade['rvol'],
            'exit_reason': exit_reason
        })
        
    df_t = pd.DataFrame(trades)
    
    print("\n" + "="*85)
    print("UNCOMPOUNDED (FLAT 1.0% RISK = Rs 1,000 PER TRADE) YEARLY ANALYSIS:")
    print("="*85)
    
    yearly = df_t.groupby('year').agg(
        trades=('ret_pct', 'count'),
        win_rate=('ret_pct', lambda x: (x > 0).mean() * 100),
        avg_ret_pct=('ret_pct', 'mean'),
        total_ret_pct=('ret_pct', 'sum'),
        avg_gap=('gap_pct', lambda x: x.abs().mean()),
        avg_rvol=('rvol', 'mean'),
        fees=('fee', 'sum')
    )
    yearly['monthly_avg_ret'] = yearly['total_ret_pct'] / 12.0
    print(yearly[['trades', 'win_rate', 'total_ret_pct', 'monthly_avg_ret', 'avg_gap', 'avg_rvol', 'fees']])
    
    print("\n" + "="*85)
    print("RUNNER BREAKDOWN BY YEAR (How many hit big targets?):")
    print("="*85)
    for y, y_df in df_t.groupby('year'):
        runners = y_df[y_df['exit_reason'] == 'RUNNER_PROFIT']
        stops = y_df[y_df['exit_reason'] == 'STOP_INITIAL']
        print(f"Year {y}: Total {len(y_df)} trades | Big Runners: {len(runners)} ({len(runners)/len(y_df)*100:.1f}%) | Stops: {len(stops)} ({len(stops)/len(y_df)*100:.1f}%) | Net: {y_df['ret_pct'].sum():+.2f}%")

if __name__ == '__main__':
    diagnose()
