"""
REGIME-ALIGNED NIFTY 200 CATALYST MOMENTUM SYSTEM (2022 - 2026)
Tests Market Regime Filter (Index Trend Alignment):
- Long Catalyst: Only take Longs when NIFTY 50 / Universe Market Breadth is Bullish (% of stocks > 20 EMA >= 50%)
- Short Catalyst: Only take Shorts when Market Breadth is Bearish (% of stocks > 20 EMA < 50%)
- Plus Dynamic Drawdown Circuit Breaker: throttle risk during drawdowns
"""

import os, glob, json, time
import numpy as np
import pandas as pd

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

def run_regime_aligned_system():
    start_t = time.time()
    files = glob.glob("data/nifty200_daily_cache/*.parquet")
    print(f"Loading {len(files)} Nifty 200 daily parquet files...", flush=True)
    
    symbol_days = {}
    daily_breadth = {} # date -> % of stocks with Close > 20 EMA
    all_dates = set()
    
    for f in files:
        sym = os.path.basename(f).replace(".parquet", "")
        df = pd.read_parquet(f).sort_values('Date').reset_index(drop=True)
        if len(df) < 50: continue
        df['Date'] = pd.to_datetime(df['Date'])
        df['date_str'] = df['Date'].dt.strftime('%Y-%m-%d')
        df['prev_close'] = df['Close'].shift(1)
        df['ema20'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['gap_pct'] = (df['Open'] - df['prev_close']) / df['prev_close'] * 100.0
        df['vol_20avg'] = df['Volume'].rolling(20).mean().shift(1)
        df['rvol'] = df['Volume'] / np.where(df['vol_20avg'] > 0, df['vol_20avg'], df['Volume'])
        
        symbol_days[sym] = {}
        for idx, r in df.iterrows():
            d_str = r['date_str']
            if int(d_str[:4]) >= 2022 and d_str <= '2026-10-31':
                all_dates.add(d_str)
                if d_str not in daily_breadth: daily_breadth[d_str] = []
                daily_breadth[d_str].append(1 if r['Close'] > r['ema20'] else 0)
                
                symbol_days[sym][d_str] = {
                    'Open': r['Open'],
                    'High': r['High'],
                    'Low': r['Low'],
                    'Close': r['Close'],
                    'gap_pct': r['gap_pct'],
                    'rvol': r['rvol'],
                    'ema20': r['ema20']
                }
                
    dates = sorted(list(all_dates))
    market_regime = {d: np.mean(daily_breadth[d]) * 100.0 for d in dates}
    print(f"Loaded {len(symbol_days)} stocks across {len(dates)} trading days in {time.time() - start_t:.1f}s.", flush=True)
    
    # We test:
    # Breadth threshold: 40% vs 50% vs 60%
    # Risk throttling with dynamic breaker:
    # Tier 1 (DD < 4%): 1.0x risk (Rs 1,000)
    # Tier 2 (4% <= DD < 7%): 0.60x risk
    # Tier 3 (7% <= DD < 10%): 0.30x risk
    # Tier 4 (DD >= 10%): 0.15x risk
    
    for use_breaker in [False, True]:
        for min_gap, min_rvol in [(1.5, 2.5), (1.5, 3.0), (1.2, 2.5)]:
            trades = []
            capital = 100000.0
            peak_capital = capital
            
            for d in dates:
                breadth = market_regime.get(d, 50.0)
                
                if use_breaker:
                    cur_dd = (peak_capital - capital) / peak_capital * 100.0 if peak_capital > 0 else 0.0
                    if cur_dd < 4.0: mult = 1.00
                    elif cur_dd < 7.0: mult = 0.60
                    elif cur_dd < 10.0: mult = 0.30
                    else: mult = 0.15
                else:
                    mult = 1.00
                    
                risk_cash = 1000.0 * mult
                
                candidates = []
                for sym, d_dict in symbol_days.items():
                    if d not in d_dict: continue
                    r = d_dict[d]
                    gap = r['gap_pct']
                    rvol = r['rvol']
                    if np.isnan(gap) or np.isnan(rvol): continue
                    if abs(gap) < min_gap or rvol < min_rvol: continue
                    
                    open_p = r['Open']
                    if open_p <= 0: continue
                    
                    # Regime filter:
                    # Longs only allowed if breadth >= 45% (market is healthy)
                    # Shorts only allowed if breadth <= 55% (market is weak)
                    if gap >= min_gap and breadth >= 45.0:
                        candidates.append({
                            'symbol': sym, 'side': 'BUY', 'open_p': open_p,
                            'high_p': r['High'], 'low_p': r['Low'], 'close_p': r['Close'],
                            'score': rvol * (1.0 + abs(gap))
                        })
                    elif gap <= -min_gap and breadth <= 55.0:
                        candidates.append({
                            'symbol': sym, 'side': 'SELL', 'open_p': open_p,
                            'high_p': r['High'], 'low_p': r['Low'], 'close_p': r['Close'],
                            'score': rvol * (1.0 + abs(gap))
                        })
                        
                if not candidates: continue
                candidates.sort(key=lambda x: -x['score'])
                
                # Take top 2 trades of the day
                for t in candidates[:2]:
                    open_p = t['open_p']
                    high_p = t['high_p']
                    low_p = t['low_p']
                    close_p = t['close_p']
                    side = t['side']
                    
                    eff_entry = open_p * (1.0 + 0.0003) if side == 'BUY' else open_p * (1.0 - 0.0003)
                    sl_pct = 0.0100 # 1.0% stop
                    risk_pts = open_p * sl_pct
                    sl_p = open_p - risk_pts if side == 'BUY' else open_p + risk_pts
                    t1_p = open_p + (2.0 * risk_pts) if side == 'BUY' else open_p - (2.0 * risk_pts)
                    t2_p = open_p + (3.5 * risk_pts) if side == 'BUY' else open_p - (3.5 * risk_pts)
                    
                    shares = int(risk_cash / risk_pts)
                    if shares < 1: continue
                    s_t1 = int(shares * 0.50)
                    s_run = shares - s_t1
                    if s_t1 < 1: s_t1 = 1
                    
                    exit_p1 = 0.0
                    exit_pr = 0.0
                    
                    if side == 'BUY':
                        if low_p <= sl_p:
                            exit_p1 = sl_p * (1.0 - 0.0003)
                            exit_pr = sl_p * (1.0 - 0.0003)
                        else:
                            if high_p >= t1_p:
                                exit_p1 = t1_p
                                if high_p >= t2_p:
                                    exit_pr = t2_p
                                else:
                                    exit_pr = close_p * (1.0 - 0.0003)
                            else:
                                exit_p1 = close_p * (1.0 - 0.0003)
                                exit_pr = close_p * (1.0 - 0.0003)
                    else:
                        if high_p >= sl_p:
                            exit_p1 = sl_p * (1.0 + 0.0003)
                            exit_pr = sl_p * (1.0 + 0.0003)
                        else:
                            if low_p <= t1_p:
                                exit_p1 = t1_p
                                if low_p <= t2_p:
                                    exit_pr = t2_p
                                else:
                                    exit_pr = close_p * (1.0 + 0.0003)
                            else:
                                exit_p1 = close_p * (1.0 + 0.0003)
                                exit_pr = close_p * (1.0 + 0.0003)
                                
                    if side == 'BUY':
                        buy_v = shares * eff_entry
                        sell_v = (s_t1 * exit_p1) + (s_run * exit_pr)
                        gp = sell_v - buy_v
                    else:
                        sell_v = shares * eff_entry
                        buy_v = (s_t1 * exit_p1) + (s_run * exit_pr)
                        gp = sell_v - buy_v
                        
                    fee = compute_zerodha_charges(buy_v, sell_v)
                    npnl = gp - fee
                    
                    capital += npnl
                    if capital > peak_capital: peak_capital = capital
                    
                    trades.append({
                        'date': d,
                        'year': int(d[:4]),
                        'symbol': t['symbol'],
                        'side': side,
                        'net_pnl': round(npnl, 2),
                        'fee': round(fee, 2),
                        'R': round(npnl / (1000.0 * mult), 3)
                    })
                    
            df_t = pd.DataFrame(trades)
            if len(df_t) == 0: continue
            df_t['date_dt'] = pd.to_datetime(df_t['date'])
            df_t['ym'] = df_t['date_dt'].dt.to_period('M')
            n_mo = df_t['ym'].nunique()
            tot_pnl = df_t['net_pnl'].sum()
            tot_r = df_t['R'].sum()
            wins = df_t[df_t['net_pnl'] > 0]
            wr = len(wins) / len(df_t) * 100.0
            gw = wins['net_pnl'].sum()
            gl = abs(df_t[df_t['net_pnl'] <= 0]['net_pnl'].sum())
            pf = gw / gl if gl > 0 else 0.0
            
            monthly_r = df_t.groupby('ym')['R'].sum()
            monthly_pnl = df_t.groupby('ym')['net_pnl'].sum()
            
            # Cumulative drawdown
            df_t['cum'] = df_t['net_pnl'].cumsum()
            df_t['peak'] = df_t['cum'].cummax()
            max_dd_inr = (df_t['cum'] - df_t['peak']).min()
            max_dd_pct = abs(max_dd_inr) / 100000.0 * 100.0
            
            y_pnl = df_t.groupby('year')['net_pnl'].sum().to_dict()
            
            breaker_str = "WITH DYNAMIC BREAKER" if use_breaker else "STATIC 1R (NO BREAKER)"
            print("\n" + "="*85)
            print(f"[{breaker_str} | Gap>={min_gap}% | RVOL>={min_rvol}x]")
            print(f"  Trades: {len(df_t)} ({len(df_t)/n_mo:.1f}/mo) | WR: {wr:5.2f}% | PF: {pf:4.2f} | Net PnL: Rs {tot_pnl:+10,.0f} (+{tot_r:.1f}R)")
            print(f"  Avg Monthly Return: {tot_pnl/100000.0/n_mo*100.0:+5.2f}% / month (+Rs {monthly_pnl.mean():+,.0f}/mo on Rs 100k)")
            print(f"  Max Drawdown: -Rs {abs(max_dd_inr):,.0f} ({max_dd_pct:.2f}%) | Profitable Months: {(monthly_pnl>0).sum()}/{n_mo} ({(monthly_pnl>0).mean()*100:.1f}%)")
            print(f"  Yearly Net PnL: {y_pnl}")

if __name__ == '__main__':
    run_regime_aligned_system()
