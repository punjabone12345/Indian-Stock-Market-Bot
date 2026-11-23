"""
TASK 2: UNIVERSE EXPANSION & SCALING AUDIT
Tests strategy performance, liquidity capacity, and stability across:
- Top 10 Liquid Mega-Caps
- Top 30 Liquid Stocks
- Top 50 Liquid Stocks
- Top 100 Liquid Stocks
- Broader Eligible NSE Universe (194 Stocks)

Evaluated across both:
1. High-resolution 5-minute intraday cache (data/nifty200_cache/ - 194 stocks)
2. Long-term multi-year daily liquidity cache (data/nifty200_daily_cache/ - 194 stocks)
"""

import os, glob, json
import numpy as np
import pandas as pd
from datetime import time as dtime

def compute_zerodha_charges(buy_val, sell_val):
    b = min(20.0, buy_val * 0.0003) + min(20.0, sell_val * 0.0003)
    stt = sell_val * 0.00025
    exchange = (buy_val + sell_val) * 0.0000297
    sebi = (buy_val + sell_val) * 0.000001
    stamp = buy_val * 0.00003
    gst = (b + exchange + sebi) * 0.18
    return b + stt + exchange + sebi + stamp + gst

def run_universe_scaling_audit():
    os.makedirs("research/phase3/reports", exist_ok=True)
    
    # 1. Rank 194 stocks by Average Daily Traded Value (Liquidity Ranking)
    daily_files = glob.glob("data/nifty200_daily_cache/*.parquet")
    print(f"Ranking liquidity for {len(daily_files)} stocks from daily cache...", flush=True)
    
    turnover_list = []
    for f in daily_files:
        sym = os.path.basename(f).replace(".parquet", "")
        df_d = pd.read_parquet(f)
        if len(df_d) == 0: continue
        avg_turnover = (df_d['Close'] * df_d['Volume']).mean() / 1e7 # in Crores INR
        avg_price = df_d['Close'].mean()
        turnover_list.append({'symbol': sym, 'turnover_cr': avg_turnover, 'avg_price': avg_price})
        
    df_rank = pd.DataFrame(turnover_list).sort_values('turnover_cr', ascending=False).reset_index(drop=True)
    
    top10 = df_rank.iloc[0:10]['symbol'].tolist()
    top30 = df_rank.iloc[0:30]['symbol'].tolist()
    top50 = df_rank.iloc[0:50]['symbol'].tolist()
    top100 = df_rank.iloc[0:100]['symbol'].tolist()
    all_194 = df_rank['symbol'].tolist()
    
    print("\nTop 10 Liquid Stocks by Turnover (Cr/day):")
    for _, r in df_rank.iloc[0:10].iterrows():
        print(f"  {r['symbol']:12s}: Rs {r['turnover_cr']:6.1f} Cr/day (Price: Rs {r['avg_price']:.1f})")
        
    # 2. Test Intraday VWAP Retest across Tiers on 5m Cache
    print("\nLoading 5m bars from data/nifty200_cache/ for 194 stocks...", flush=True)
    cache_5m_files = glob.glob("data/nifty200_cache/*.parquet")
    stocks_5m = {}
    
    for f in cache_5m_files:
        sym = os.path.basename(f).replace(".parquet", "")
        df = pd.read_parquet(f)
        if len(df) < 200: continue
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date').reset_index(drop=True)
        df['typ'] = (df['High'] + df['Low'] + df['Close']) / 3.0
        df['pv'] = df['typ'] * df['Volume']
        df['date_str'] = df['Date'].dt.strftime('%Y-%m-%d')
        df['time_str'] = df['Date'].dt.strftime('%H:%M:%S')
        df['cum_pv'] = df.groupby('date_str')['pv'].cumsum()
        df['cum_vol'] = df.groupby('date_str')['Volume'].cumsum()
        df['vwap'] = np.where(df['cum_vol'] > 0, df['cum_pv'] / df['cum_vol'], df['Close'])
        stocks_5m[sym] = df
        
    print(f"Loaded {len(stocks_5m)} stocks with 5-minute bars.", flush=True)
    
    def evaluate_universe_tier(tier_symbols, tier_name):
        trades = []
        # Find all trading dates
        dates = sorted(list(set().union(*[stocks_5m[s]['date_str'].unique() for s in tier_symbols if s in stocks_5m])))
        
        for d in dates:
            candidates = []
            for sym in tier_symbols:
                if sym not in stocks_5m: continue
                d_df = stocks_5m[sym][stocks_5m[sym]['date_str'] == d].reset_index(drop=True)
                if len(d_df) < 25: continue
                c15 = d_df.iloc[0:3]
                open_15m = c15.iloc[0]['Open']
                high_15m = c15['High'].max()
                low_15m = c15['Low'].min()
                close_15m = c15.iloc[-1]['Close']
                vol_15m = c15['Volume'].sum()
                mid_15m = (high_15m + low_15m) / 2.0
                
                # Check VWAP setup
                if close_15m > open_15m: # Bullish
                    for b_i in range(3, min(18, len(d_df) - 6)):
                        bar = d_df.iloc[b_i]
                        if bar['Low'] <= bar['vwap'] and bar['Close'] >= bar['vwap']:
                            entry_p = bar['vwap']
                            sl_p = mid_15m
                            risk_pts = max(entry_p * 0.0035, min(entry_p * 0.010, abs(entry_p - sl_p)))
                            candidates.append({'symbol': sym, 'side': 'BUY', 'b_idx': b_i, 'entry_p': entry_p, 'sl_p': entry_p - risk_pts, 'risk_pts': risk_pts, 'vol': vol_15m, 'df': d_df})
                            break
                elif close_15m < open_15m: # Bearish
                    for b_i in range(3, min(18, len(d_df) - 6)):
                        bar = d_df.iloc[b_i]
                        if bar['High'] >= bar['vwap'] and bar['Close'] <= bar['vwap']:
                            entry_p = bar['vwap']
                            sl_p = mid_15m
                            risk_pts = max(entry_p * 0.0035, min(entry_p * 0.010, abs(sl_p - entry_p)))
                            candidates.append({'symbol': sym, 'side': 'SELL', 'b_idx': b_i, 'entry_p': entry_p, 'sl_p': entry_p + risk_pts, 'risk_pts': risk_pts, 'vol': vol_15m, 'df': d_df})
                            break
                            
            if not candidates: continue
            candidates.sort(key=lambda x: -x['vol'])
            # Take top trade of the day
            t = candidates[0]
            entry_p, sl_p, risk_pts, d_df, side, b_idx = t['entry_p'], t['sl_p'], t['risk_pts'], t['df'], t['side'], t['b_idx']
            
            risk_cash = 1000.0
            shares = int(risk_cash / risk_pts)
            if shares < 1: shares = 1
            s_t1 = int(shares * 0.50); s_run = shares - s_t1
            if s_t1 < 1: s_t1 = 1
            t1_p = entry_p + (2.0 * risk_pts) if side == 'BUY' else entry_p - (2.0 * risk_pts)
            t2_p = entry_p + (3.5 * risk_pts) if side == 'BUY' else entry_p - (3.5 * risk_pts)
            
            t1_hit = False
            curr_sl = sl_p
            exit_p1, exit_pr = 0.0, 0.0
            
            for j in range(b_idx + 1, len(d_df)):
                bar = d_df.iloc[j]
                h, l, c = bar['High'], bar['Low'], bar['Close']
                if side == 'BUY':
                    if l <= curr_sl:
                        if not t1_hit: exit_p1, exit_pr = curr_sl, curr_sl
                        else: exit_pr = curr_sl
                        break
                    if not t1_hit and h >= t1_p: t1_hit = True; exit_p1 = t1_p
                    if t1_hit and h >= t2_p: exit_pr = t2_p; break
                    if j == len(d_df) - 1 or j >= 72:
                        if not t1_hit: exit_p1 = c
                        exit_pr = c; break
                else:
                    if h >= curr_sl:
                        if not t1_hit: exit_p1, exit_pr = curr_sl, curr_sl
                        else: exit_pr = curr_sl
                        break
                    if not t1_hit and l <= t1_p: t1_hit = True; exit_p1 = t1_p
                    if t1_hit and l <= t2_p: exit_pr = t2_p; break
                    if j == len(d_df) - 1 or j >= 72:
                        if not t1_hit: exit_p1 = c
                        exit_pr = c; break
                        
            if side == 'BUY':
                gp = s_t1 * (exit_p1 - entry_p) + (s_run * (exit_pr - entry_p) if s_run > 0 else 0)
                fee = compute_zerodha_charges(s_t1 * entry_p, s_t1 * exit_p1) + (compute_zerodha_charges(s_run * entry_p, s_run * exit_pr) if s_run > 0 else 0)
            else:
                gp = s_t1 * (entry_p - exit_p1) + (s_run * (entry_p - exit_pr) if s_run > 0 else 0)
                fee = compute_zerodha_charges(s_t1 * exit_p1, s_t1 * entry_p) + (compute_zerodha_charges(s_run * exit_pr, s_run * entry_p) if s_run > 0 else 0)
                
            net_pnl = gp - fee
            trades.append({'date': d, 'symbol': t['symbol'], 'net_pnl': net_pnl, 'R': net_pnl / risk_cash})
            
        df_t = pd.DataFrame(trades)
        if len(df_t) == 0:
            return {'tier': tier_name, 'trades': 0}
            
        wins = df_t[df_t['net_pnl'] > 0]
        losses = df_t[df_t['net_pnl'] <= 0]
        wr = len(wins) / len(df_t) * 100.0
        gw = wins['net_pnl'].sum()
        gl = abs(losses['net_pnl'].sum())
        pf = gw / gl if gl > 0 else 0.0
        tot_r = df_t['R'].sum()
        
        df_t['cum'] = df_t['R'].cumsum()
        df_t['peak'] = df_t['cum'].cummax()
        df_t['dd'] = df_t['cum'] - df_t['peak']
        max_dd = df_t['dd'].min()
        
        return {
            'tier': tier_name,
            'symbols_count': len(tier_symbols),
            'trades': len(df_t),
            'win_rate_pct': round(wr, 2),
            'profit_factor': round(pf, 2),
            'total_net_R': round(tot_r, 2),
            'max_drawdown_R': round(max_dd, 2),
            'avg_daily_turnover_cr': round(float(df_rank[df_rank['symbol'].isin(tier_symbols)]['turnover_cr'].mean()), 1)
        }
        
    tiers = [
        (top10, "Top_10_Liquid_MegaCaps"),
        (top30, "Top_30_Liquid_Stocks"),
        (top50, "Top_50_Liquid_Stocks"),
        (top100, "Top_100_Liquid_Stocks"),
        (all_194, "Broader_Universe_194_Stocks")
    ]
    
    tier_results = []
    print("\n=======================================================")
    print("UNIVERSE EXPANSION AUDIT RESULTS:")
    print("=======================================================")
    for t_syms, t_name in tiers:
        res = evaluate_universe_tier(t_syms, t_name)
        tier_results.append(res)
        print(f"{res['tier']:30s} | Stocks: {res['symbols_count']:3d} | Trades: {res['trades']:2d} | WR: {res['win_rate_pct']:5.2f}% | PF: {res['profit_factor']:4.2f} | Net R: {res['total_net_R']:+5.2f}R | MaxDD: {res['max_drawdown_R']:5.2f}R | Avg Turnover: Rs {res['avg_daily_turnover_cr']} Cr/day")
        
    with open("research/phase3/reports/task2_universe_scaling_report.json", "w") as f:
        json.dump(tier_results, f, indent=2)
    print("\nSaved Task 2 report to research/phase3/reports/task2_universe_scaling_report.json")

if __name__ == '__main__':
    run_universe_scaling_audit()
