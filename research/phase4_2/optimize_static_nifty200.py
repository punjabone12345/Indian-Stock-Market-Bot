"""
DEEP GRID SEARCH & MECHANICS OPTIMIZATION FOR STATIC NIFTY 200 CATALYST SYSTEM
Goal: Maximize static monthly return (target 7% - 10%) while minimizing max drawdown.
Strictly zero compounding: Sizing based on fixed rupee risk on Rs 1,00,000 capital.
Zerodha leg-by-leg charges + 0.03% slippage included on all executions.
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

def load_data():
    files = glob.glob("data/nifty200_daily_cache/*.parquet")
    symbol_days = {}
    daily_breadth = {}
    all_dates = set()
    
    for f in files:
        sym = os.path.basename(f).replace(".parquet", "")
        df = pd.read_parquet(f).sort_values('Date').reset_index(drop=True)
        if len(df) < 50: continue
        df['Date'] = pd.to_datetime(df['Date'])
        df['date_str'] = df['Date'].dt.strftime('%Y-%m-%d')
        df['prev_close'] = df['Close'].shift(1)
        df['ema20'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['sma50'] = df['Close'].rolling(50).mean()
        df['gap_pct'] = (df['Open'] - df['prev_close']) / df['prev_close'] * 100.0
        df['vol_20avg'] = df['Volume'].rolling(20).mean().shift(1)
        df['rvol'] = df['Volume'] / np.where(df['vol_20avg'] > 0, df['vol_20avg'], df['Volume'])
        
        # Fast dictionary conversion
        mask = (df['Date'].dt.year >= 2022) & (df['date_str'] <= '2026-10-31')
        sub_df = df[mask]
        
        sym_records = {}
        for r in sub_df.itertuples(index=False):
            d_str = r.date_str
            all_dates.add(d_str)
            if d_str not in daily_breadth: daily_breadth[d_str] = []
            daily_breadth[d_str].append(1 if r.Close > r.ema20 else 0)
            
            sym_records[d_str] = {
                'Open': r.Open, 'High': r.High, 'Low': r.Low, 'Close': r.Close,
                'gap_pct': r.gap_pct, 'rvol': r.rvol, 'ema20': r.ema20,
                'prev_close': r.prev_close
            }
        symbol_days[sym] = sym_records
        
    dates = sorted(list(all_dates))
    market_regime = {d: np.mean(daily_breadth[d]) * 100.0 for d in dates if d in daily_breadth and len(daily_breadth[d]) > 0}
    return symbol_days, dates, market_regime

def simulate_strategy(symbol_days, dates, market_regime,
                      min_gap=1.2, min_rvol=2.5, sl_pct=0.010,
                      t1_r=2.0, t2_r=3.5, max_trades_per_day=2,
                      allow_shorts=True, min_breadth_long=45.0, max_breadth_short=55.0,
                      trailing_to_be=True, risk_per_trade=1000.0,
                      streak_throttle=False):
    
    trades = []
    consecutive_losses = 0
    
    for d in dates:
        breadth = market_regime.get(d, 50.0)
        
        # Streak-based dynamic risk throttling
        if streak_throttle:
            if consecutive_losses >= 4:
                mult = 0.5
            elif consecutive_losses >= 6:
                mult = 0.25
            else:
                mult = 1.0
        else:
            mult = 1.0
            
        risk_cash = risk_per_trade * mult
        
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
            
            # Regime filter
            if gap >= min_gap and breadth >= min_breadth_long:
                candidates.append({
                    'symbol': sym, 'side': 'BUY', 'open_p': open_p,
                    'high_p': r['High'], 'low_p': r['Low'], 'close_p': r['Close'],
                    'score': rvol * (1.0 + abs(gap))
                })
            elif allow_shorts and gap <= -min_gap and breadth <= max_breadth_short:
                candidates.append({
                    'symbol': sym, 'side': 'SELL', 'open_p': open_p,
                    'high_p': r['High'], 'low_p': r['Low'], 'close_p': r['Close'],
                    'score': rvol * (1.0 + abs(gap))
                })
                
        if not candidates: continue
        candidates.sort(key=lambda x: -x['score'])
        
        selected = candidates[:max_trades_per_day]
        for t in selected:
            open_p = t['open_p']
            high_p = t['high_p']
            low_p = t['low_p']
            close_p = t['close_p']
            side = t['side']
            
            eff_entry = open_p * (1.0 + 0.0003) if side == 'BUY' else open_p * (1.0 - 0.0003)
            risk_pts = open_p * sl_pct
            sl_p = open_p - risk_pts if side == 'BUY' else open_p + risk_pts
            t1_p = open_p + (t1_r * risk_pts) if side == 'BUY' else open_p - (t1_r * risk_pts)
            t2_p = open_p + (t2_r * risk_pts) if side == 'BUY' else open_p - (t2_r * risk_pts)
            
            shares = int(risk_cash / risk_pts)
            if shares < 1: continue
            s_t1 = int(shares * 0.50)
            s_run = shares - s_t1
            if s_t1 < 1: s_t1 = 1
            
            exit_p1 = 0.0
            exit_pr = 0.0
            
            if side == 'BUY':
                if low_p <= sl_p:
                    # Worst-case intrabar sequence: SL hit first
                    exit_p1 = sl_p * (1.0 - 0.0003)
                    exit_pr = sl_p * (1.0 - 0.0003)
                else:
                    if high_p >= t1_p:
                        exit_p1 = t1_p # Limit fill at T1
                        # If trailing_to_be, runner SL is at breakeven (entry price)
                        be_p = eff_entry
                        if high_p >= t2_p:
                            exit_pr = t2_p # Limit fill at T2
                        else:
                            # Runner closes at EOD, but not below BE if trailing_to_be
                            if trailing_to_be:
                                exit_pr = max(be_p, close_p) * (1.0 - 0.0003)
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
                        be_p = eff_entry
                        if low_p <= t2_p:
                            exit_pr = t2_p
                        else:
                            if trailing_to_be:
                                exit_pr = min(be_p, close_p) * (1.0 + 0.0003)
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
            
            if npnl <= 0:
                consecutive_losses += 1
            else:
                consecutive_losses = 0
                
            trades.append({
                'date': d,
                'year': int(d[:4]),
                'symbol': t['symbol'],
                'side': side,
                'net_pnl': round(npnl, 2),
                'fee': round(fee, 2),
                'R': round(npnl / risk_per_trade, 3)
            })
            
    if not trades: return None
    df_t = pd.DataFrame(trades)
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
    
    monthly_pnl = df_t.groupby('ym')['net_pnl'].sum()
    
    df_t['cum'] = df_t['net_pnl'].cumsum()
    df_t['peak'] = df_t['cum'].cummax()
    max_dd_inr = (df_t['cum'] - df_t['peak']).min()
    max_dd_pct = abs(max_dd_inr) / 100000.0 * 100.0
    
    avg_mo_ret = tot_pnl / 100000.0 / n_mo * 100.0
    prof_mo_pct = (monthly_pnl > 0).mean() * 100.0
    y_pnl = df_t.groupby('year')['net_pnl'].sum().to_dict()
    
    return {
        'trades': len(df_t),
        'trades_per_mo': len(df_t) / n_mo,
        'wr': wr,
        'pf': pf,
        'tot_pnl': tot_pnl,
        'tot_r': tot_r,
        'avg_mo_ret': avg_mo_ret,
        'max_dd_pct': max_dd_pct,
        'max_dd_inr': abs(max_dd_inr),
        'prof_mo_pct': prof_mo_pct,
        'y_pnl': y_pnl,
        'df_t': df_t
    }

def main():
    t0 = time.time()
    print("Loading data using itertuples...", flush=True)
    symbol_days, dates, market_regime = load_data()
    print(f"Loaded {len(symbol_days)} stocks across {len(dates)} days in {time.time()-t0:.1f}s.\n", flush=True)
    
    configs = [
        # (name, min_gap, min_rvol, sl_pct, t1_r, t2_r, max_tr, allow_shorts, trailing_be, throttle)
        ("Baseline (2 tr/d, SL 1%, T 2R/3.5R, No BE)", 1.2, 2.5, 0.010, 2.0, 3.5, 2, True, False, False),
        ("Baseline + Trailing to BE", 1.2, 2.5, 0.010, 2.0, 3.5, 2, True, True, False),
        ("3 Trades/day + Trailing BE", 1.2, 2.5, 0.010, 2.0, 3.5, 3, True, True, False),
        ("4 Trades/day + Trailing BE", 1.2, 2.5, 0.010, 2.0, 3.5, 4, True, True, False),
        ("3 Trades/day + T1=2.0R, T2=4.0R + Trailing BE", 1.2, 2.5, 0.010, 2.0, 4.0, 3, True, True, False),
        ("3 Trades/day + T1=2.0R, T2=5.0R + Trailing BE", 1.2, 2.5, 0.010, 2.0, 5.0, 3, True, True, False),
        ("3 Trades/day + SL=0.8% + T1=2.0R, T2=4.0R", 1.2, 2.5, 0.008, 2.0, 4.0, 3, True, True, False),
        ("3 Trades/day + SL=1.2% + T1=2.0R, T2=4.0R", 1.2, 2.5, 0.012, 2.0, 4.0, 3, True, True, False),
        ("Long-Only (3 tr/d, T 2R/4R, BE)", 1.2, 2.5, 0.010, 2.0, 4.0, 3, False, True, False),
        ("3 Trades/d + Streak Throttle", 1.2, 2.5, 0.010, 2.0, 4.0, 3, True, True, True),
        ("4 Trades/d + T1=2.0R, T2=4.0R + Trailing BE", 1.2, 2.5, 0.010, 2.0, 4.0, 4, True, True, False),
        ("4 Trades/d + T1=2.5R, T2=5.0R + Trailing BE", 1.2, 2.5, 0.010, 2.5, 5.0, 4, True, True, False),
    ]
    
    results = []
    for name, mgap, mrvol, sl, t1, t2, mtr, ashorts, tbe, thr in configs:
        res = simulate_strategy(
            symbol_days, dates, market_regime,
            min_gap=mgap, min_rvol=mrvol, sl_pct=sl,
            t1_r=t1, t2_r=t2, max_trades_per_day=mtr,
            allow_shorts=ashorts, min_breadth_long=45.0, max_breadth_short=55.0,
            trailing_to_be=tbe, risk_per_trade=1000.0,
            streak_throttle=thr
        )
        if res:
            res['name'] = name
            results.append(res)
            print(f"[{name}]")
            print(f"  Trades: {res['trades']} ({res['trades_per_mo']:.1f}/mo) | WR: {res['wr']:5.2f}% | PF: {res['pf']:4.2f}")
            print(f"  Net PnL: Rs {res['tot_pnl']:+10,.0f} (+{res['tot_r']:.1f}R) | Avg Mo Return: {res['avg_mo_ret']:+5.2f}% / month")
            print(f"  Max DD: -Rs {res['max_dd_inr']:,.0f} ({res['max_dd_pct']:.2f}%) | Profitable Months: {res['prof_mo_pct']:.1f}%")
            print(f"  Yearly: { {y: int(v) for y, v in res['y_pnl'].items()} }\n", flush=True)

if __name__ == '__main__':
    main()
