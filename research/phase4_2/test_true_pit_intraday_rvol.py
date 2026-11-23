"""
TRUE POINT-IN-TIME 15-MINUTE INTRADAY RVOL BREAKOUT SYSTEM (2022 - 2026)
Tested on real 1-minute tick-aggregate data for mega-caps.
Optimized fast loading: filters dates BEFORE string formatting.
"""

import os, glob, time
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

def test_true_pit_orb():
    t0 = time.time()
    stock_files = glob.glob("data/stocks/*_prev.parquet")
    print(f"Loading {len(stock_files)} stocks 1m data...", flush=True)
    
    symbols_data = {}
    for f in stock_files:
        sym = os.path.basename(f).replace("_prev.parquet", "")
        df_prev = pd.read_parquet(f)
        
        # Also check if 2026 file exists
        f_2026 = f.replace("_prev.parquet", "_2026.parquet")
        if os.path.exists(f_2026):
            df_2026 = pd.read_parquet(f_2026)
            df = pd.concat([df_prev, df_2026], ignore_index=True)
        else:
            df = df_prev
            
        df['Date'] = pd.to_datetime(df['Date'])
        # FAST: filter date range first!
        mask = (df['Date'] >= '2022-01-01') & (df['Date'] <= '2026-10-31 15:30:00')
        sub_df = df[mask].sort_values('Date').reset_index(drop=True)
        if len(sub_df) < 1000: continue
        
        sub_df['date_str'] = sub_df['Date'].dt.date.astype(str)
        sub_df['time_str'] = sub_df['Date'].dt.time.astype(str)
        symbols_data[sym] = sub_df
        
    print(f"Loaded {len(symbols_data)} stocks in {time.time()-t0:.1f}s. Pre-computing 15m stats...", flush=True)
    
    stock_days = {}
    all_dates = set()
    
    for sym, df in symbols_data.items():
        stock_days[sym] = {}
        grouped = df.groupby('date_str')
        vol_history = []
        
        for d_str, day_df in grouped:
            all_dates.add(d_str)
            bars_15m = day_df[day_df['time_str'] <= '09:30:00']
            bars_rest = day_df[day_df['time_str'] > '09:30:00']
            
            if len(bars_15m) < 10 or len(bars_rest) < 10:
                continue
                
            or_high = bars_15m['High'].max()
            or_low = bars_15m['Low'].min()
            vol_15m = bars_15m['Volume'].sum()
            open_p = bars_15m.iloc[0]['Open']
            
            avg_15m_vol = np.mean(vol_history[-20:]) if len(vol_history) >= 5 else vol_15m
            rvol_15m = vol_15m / avg_15m_vol if avg_15m_vol > 0 else 1.0
            vol_history.append(vol_15m)
            
            stock_days[sym][d_str] = {
                'open_p': open_p,
                'or_high': or_high,
                'or_low': or_low,
                'vol_15m': vol_15m,
                'rvol_15m': rvol_15m,
                'bars_rest': bars_rest[['time_str', 'Open', 'High', 'Low', 'Close']].to_dict('records')
            }
            
    dates = sorted(list(all_dates))
    print(f"Processed {len(dates)} trading dates in {time.time()-t0:.1f}s.\n", flush=True)
    
    for min_rvol in [1.5, 2.0, 2.5]:
        for sl_mode in ['or_low', 'fixed_1pct']:
            trades = []
            
            for d in dates:
                candidates = []
                for sym, d_dict in stock_days.items():
                    if d not in d_dict: continue
                    r = d_dict[d]
                    if r['rvol_15m'] >= min_rvol:
                        candidates.append({
                            'symbol': sym,
                            'rvol': r['rvol_15m'],
                            'or_high': r['or_high'],
                            'or_low': r['or_low'],
                            'open_p': r['open_p'],
                            'bars_rest': r['bars_rest']
                        })
                        
                if not candidates: continue
                candidates.sort(key=lambda x: -x['rvol'])
                
                for c in candidates[:2]:
                    or_high = c['or_high']
                    or_low = c['or_low']
                    bars = c['bars_rest']
                    
                    entry_p = 0.0
                    entry_idx = -1
                    
                    for idx, b in enumerate(bars):
                        if b['Close'] > or_high:
                            if idx + 1 < len(bars):
                                next_bar = bars[idx + 1]
                                entry_p = next_bar['Open'] * (1.0 + 0.0003)
                                entry_idx = idx + 1
                                break
                                
                    if entry_p <= 0.0: continue
                    
                    if sl_mode == 'or_low':
                        sl_p = or_low
                        risk_pts = entry_p - sl_p
                    else:
                        risk_pts = entry_p * 0.010
                        sl_p = entry_p - risk_pts
                        
                    if risk_pts <= 0 or risk_pts / entry_p < 0.002: continue
                    if risk_pts / entry_p > 0.030: continue
                    
                    shares = int(1000.0 / risk_pts)
                    if shares < 1: continue
                    
                    t1_p = entry_p + (2.0 * risk_pts)
                    t2_p = entry_p + (4.0 * risk_pts)
                    s_t1 = int(shares * 0.5)
                    s_run = shares - s_t1
                    if s_t1 < 1: s_t1 = 1
                    
                    exit_p1 = 0.0
                    exit_pr = 0.0
                    t1_hit = False
                    
                    for b in bars[entry_idx:]:
                        hp = b['High']
                        lp = b['Low']
                        
                        cur_sl = entry_p if t1_hit else sl_p
                        if lp <= cur_sl:
                            if not t1_hit:
                                exit_p1 = cur_sl * (1.0 - 0.0003)
                                exit_pr = cur_sl * (1.0 - 0.0003)
                            else:
                                exit_pr = cur_sl * (1.0 - 0.0003)
                            break
                            
                        if not t1_hit and hp >= t1_p:
                            exit_p1 = t1_p
                            t1_hit = True
                            
                        if t1_hit and hp >= t2_p:
                            exit_pr = t2_p
                            break
                            
                    last_bar = bars[-1]
                    if exit_p1 <= 0.0:
                        exit_p1 = last_bar['Close'] * (1.0 - 0.0003)
                    if exit_pr <= 0.0:
                        exit_pr = last_bar['Close'] * (1.0 - 0.0003)
                        
                    buy_v = shares * entry_p
                    sell_v = (s_t1 * exit_p1) + (s_run * exit_pr)
                    gp = sell_v - buy_v
                    fee = compute_zerodha_charges(buy_v, sell_v)
                    npnl = gp - fee
                    
                    trades.append({
                        'date': d,
                        'year': int(d[:4]),
                        'symbol': c['symbol'],
                        'net_pnl': npnl,
                        'fee': fee,
                        'R': npnl / 1000.0
                    })
                    
            if not trades: continue
            df_t = pd.DataFrame(trades)
            df_t['ym'] = pd.to_datetime(df_t['date']).dt.to_period('M')
            n_mo = df_t['ym'].nunique()
            tot_pnl = df_t['net_pnl'].sum()
            wins = df_t[df_t['net_pnl'] > 0]
            wr = len(wins) / len(df_t) * 100.0
            gw = wins['net_pnl'].sum()
            gl = abs(df_t[df_t['net_pnl'] <= 0]['net_pnl'].sum())
            pf = gw / gl if gl > 0 else 0.0
            
            df_t['cum'] = df_t['net_pnl'].cumsum()
            df_t['peak'] = df_t['cum'].cummax()
            max_dd = abs((df_t['cum'] - df_t['peak']).min()) / 100000.0 * 100.0
            mo_pnl = df_t.groupby('ym')['net_pnl'].sum()
            prof_mo = (mo_pnl > 0).mean() * 100.0
            y_pnl = df_t.groupby('year')['net_pnl'].sum().to_dict()
            
            print("="*85)
            print(f"[TRUE 15M PIT RVOL >= {min_rvol}x | SL: {sl_mode}]")
            print(f"  Trades: {len(df_t)} ({len(df_t)/n_mo:.1f}/mo) | WR: {wr:5.2f}% | PF: {pf:4.2f}")
            print(f"  Net PnL: Rs {tot_pnl:+10,.0f} (+{tot_pnl/1000:.1f}R) | Avg Mo Return: {tot_pnl/100000/n_mo*100:+5.2f}% / month")
            print(f"  Max DD: {max_dd:5.2f}% | Profitable Months: {prof_mo:.1f}%")
            print(f"  Yearly: { {y: int(v) for y, v in y_pnl.items()} }\n", flush=True)

if __name__ == '__main__':
    test_true_pit_orb()
