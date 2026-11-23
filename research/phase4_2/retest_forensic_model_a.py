"""
FORENSIC AUDIT OF MODEL A: TESTING FOR AND ELIMINATING LOOK-AHEAD BIAS
1. Test with strict point-in-time Breadth: Close[t-1] > ema20[t-1]
2. Test WITHOUT today's EOD Volume (since at 09:15 AM today's volume is unknown)
3. Test using Prior Day Volume / 20-day Average Liquidity
4. Compare performance honestly!
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

def run_forensic_retest():
    files = glob.glob("data/nifty200_daily_cache/*.parquet")
    symbol_days = {}
    daily_breadth_eod = {}
    daily_breadth_pit = {} # Point-in-time (using t-1)
    all_dates = set()
    
    for f in files:
        sym = os.path.basename(f).replace(".parquet", "")
        df = pd.read_parquet(f).sort_values('Date').reset_index(drop=True)
        if len(df) < 50: continue
        df['Date'] = pd.to_datetime(df['Date'])
        df['date_str'] = df['Date'].dt.strftime('%Y-%m-%d')
        df['prev_close'] = df['Close'].shift(1)
        df['ema20'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['prev_ema20'] = df['ema20'].shift(1)
        df['gap_pct'] = (df['Open'] - df['prev_close']) / df['prev_close'] * 100.0
        df['vol_20avg'] = df['Volume'].rolling(20).mean().shift(1)
        df['turnover_cr'] = (df['vol_20avg'] * df['prev_close']) / 1e7
        df['rvol_eod'] = df['Volume'] / np.where(df['vol_20avg'] > 0, df['vol_20avg'], df['Volume'])
        
        mask = (df['Date'].dt.year >= 2022) & (df['date_str'] <= '2026-10-31')
        sub_df = df[mask]
        
        sym_records = {}
        for r in sub_df.itertuples(index=False):
            d_str = r.date_str
            all_dates.add(d_str)
            
            # EOD Breadth (Look-ahead leak)
            if d_str not in daily_breadth_eod: daily_breadth_eod[d_str] = []
            daily_breadth_eod[d_str].append(1 if r.Close > r.ema20 else 0)
            
            # Strict Point-in-Time Breadth (known at 09:15 AM from yesterday's close and yesterday's ema)
            if d_str not in daily_breadth_pit: daily_breadth_pit[d_str] = []
            daily_breadth_pit[d_str].append(1 if r.prev_close > r.prev_ema20 else 0)
            
            sym_records[d_str] = {
                'Open': r.Open, 'High': r.High, 'Low': r.Low, 'Close': r.Close,
                'gap_pct': r.gap_pct, 'rvol_eod': r.rvol_eod, 'vol_20avg': r.vol_20avg,
                'turnover_cr': r.turnover_cr, 'prev_close': r.prev_close
            }
        symbol_days[sym] = sym_records
        
    dates = sorted(list(all_dates))
    market_regime_eod = {d: np.mean(daily_breadth_eod[d]) * 100.0 for d in dates}
    market_regime_pit = {d: np.mean(daily_breadth_pit[d]) * 100.0 for d in dates}
    
    print(f"Loaded {len(symbol_days)} stocks across {len(dates)} days.\n")
    
    # We test 4 variants:
    # 1. As reported: EOD Breadth + EOD RVOL (Check if our previous numbers match exactly)
    # 2. Strict PIT Breadth + EOD RVOL (Isolate Breadth look-ahead)
    # 3. Strict PIT Breadth + NO TODAY RVOL (Only pure Gap >= 1.2% + Turnover > 10 Cr)
    # 4. Strict PIT Breadth + Pure Gap (ranked by Gap magnitude alone)
    
    variants = [
        ("1. Original Model A (EOD Breadth + EOD RVOL)", market_regime_eod, True, 'rvol_gap'),
        ("2. Model A with PIT Breadth + EOD RVOL", market_regime_pit, True, 'rvol_gap'),
        ("3. Model A with PIT Breadth + NO RVOL (Ranked by Gap %)", market_regime_pit, False, 'gap_only'),
        ("4. Model A with PIT Breadth + Min Turnover 10Cr (Ranked by Gap %)", market_regime_pit, False, 'gap_liquidity'),
    ]
    
    for title, regime, use_rvol, ranking_mode in variants:
        trades = []
        risk_cash = 1000.0
        
        for d in dates:
            breadth = regime.get(d, 50.0)
            candidates = []
            for sym, d_dict in symbol_days.items():
                if d not in d_dict: continue
                r = d_dict[d]
                gap = r['gap_pct']
                rvol = r['rvol_eod']
                turnover = r['turnover_cr']
                if np.isnan(gap): continue
                if abs(gap) < 1.2: continue
                
                if use_rvol and (np.isnan(rvol) or rvol < 2.5): continue
                if ranking_mode == 'gap_liquidity' and turnover < 10.0: continue
                
                open_p = r['Open']
                if open_p <= 0: continue
                
                if ranking_mode == 'rvol_gap':
                    score = rvol * (1.0 + abs(gap))
                else:
                    score = abs(gap)
                    
                if gap >= 1.2 and breadth >= 45.0:
                    candidates.append({
                        'symbol': sym, 'side': 'BUY', 'open_p': open_p,
                        'high_p': r['High'], 'low_p': r['Low'], 'close_p': r['Close'],
                        'score': score
                    })
                elif gap <= -1.2 and breadth <= 55.0:
                    candidates.append({
                        'symbol': sym, 'side': 'SELL', 'open_p': open_p,
                        'high_p': r['High'], 'low_p': r['Low'], 'close_p': r['Close'],
                        'score': score
                    })
                    
            if not candidates: continue
            candidates.sort(key=lambda x: -x['score'])
            
            for t in candidates[:3]:
                open_p = t['open_p']
                high_p = t['high_p']
                low_p = t['low_p']
                close_p = t['close_p']
                side = t['side']
                
                eff_entry = open_p * (1.0 + 0.0003) if side == 'BUY' else open_p * (1.0 - 0.0003)
                risk_pts = open_p * 0.012 # 1.2% SL
                sl_p = open_p - risk_pts if side == 'BUY' else open_p + risk_pts
                t1_p = open_p + (2.0 * risk_pts) if side == 'BUY' else open_p - (2.0 * risk_pts)
                t2_p = open_p + (4.0 * risk_pts) if side == 'BUY' else open_p - (4.0 * risk_pts)
                
                shares = int(risk_cash / risk_pts)
                if shares < 1: continue
                s_t1 = int(shares * 0.50)
                s_run = shares - s_t1
                if s_t1 < 1: s_t1 = 1
                
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
                
                trades.append({
                    'date': d, 'year': int(d[:4]), 'symbol': t['symbol'],
                    'net_pnl': npnl, 'fee': fee, 'R': npnl / 1000.0
                })
                
        df_res = pd.DataFrame(trades)
        if len(df_res) == 0: continue
        df_res['ym'] = pd.to_datetime(df_res['date']).dt.to_period('M')
        n_mo = df_res['ym'].nunique()
        tot_pnl = df_res['net_pnl'].sum()
        wins = df_res[df_res['net_pnl'] > 0]
        wr = len(wins) / len(df_res) * 100.0
        gw = wins['net_pnl'].sum()
        gl = abs(df_res[df_res['net_pnl'] <= 0]['net_pnl'].sum())
        pf = gw / gl if gl > 0 else 0.0
        
        df_res['cum'] = df_res['net_pnl'].cumsum()
        df_res['peak'] = df_res['cum'].cummax()
        max_dd = abs((df_res['cum'] - df_res['peak']).min()) / 100000.0 * 100.0
        
        mo_pnl = df_res.groupby('ym')['net_pnl'].sum()
        prof_mo = (mo_pnl > 0).mean() * 100.0
        y_pnl = df_res.groupby('year')['net_pnl'].sum().to_dict()
        
        print("="*85)
        print(f"[{title}]")
        print(f"  Trades: {len(df_res)} ({len(df_res)/n_mo:.1f}/mo) | WR: {wr:5.2f}% | PF: {pf:4.2f}")
        print(f"  Net PnL: Rs {tot_pnl:+10,.0f} (+{tot_pnl/1000:.1f}R) | Avg Mo Return: {tot_pnl/100000/n_mo*100:+5.2f}% / month")
        print(f"  Max DD: {max_dd:5.2f}% | Profitable Months: {prof_mo:.1f}%")
        print(f"  Yearly: { {y: int(v) for y, v in y_pnl.items()} }\n")

if __name__ == '__main__':
    run_forensic_retest()
