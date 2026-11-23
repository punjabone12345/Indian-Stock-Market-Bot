"""
TEST SHORT SELLING MORNING GAP-UPS & INTRADAY FADE ON NIFTY 200 (2022 - 2026)
Since morning gaps close negative on average (-0.44%), let's test systematic Short Selling:
Sell Short at 09:15 on Gap >= 1.5% with stop-loss and profit target!
"""

import os, glob
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

def test_gap_fade():
    files = glob.glob("data/nifty200_daily_cache/*.parquet")
    print(f"Loading {len(files)} stocks for Gap Fade test...", flush=True)
    
    symbol_days = {}
    all_dates = set()
    daily_breadth = {}
    
    for f in files:
        sym = os.path.basename(f).replace(".parquet", "")
        df = pd.read_parquet(f).sort_values('Date').reset_index(drop=True)
        if len(df) < 50: continue
        df['Date'] = pd.to_datetime(df['Date'])
        df['date_str'] = df['Date'].dt.strftime('%Y-%m-%d')
        df['prev_close'] = df['Close'].shift(1)
        df['ema20'] = df['Close'].ewm(span=20, adjust=False).mean().shift(1)
        df['gap_pct'] = (df['Open'] - df['prev_close']) / df['prev_close'] * 100.0
        
        mask = (df['Date'].dt.year >= 2022) & (df['date_str'] <= '2026-10-31')
        sub_df = df[mask]
        
        sym_records = {}
        for r in sub_df.itertuples(index=False):
            d_str = r.date_str
            all_dates.add(d_str)
            if d_str not in daily_breadth: daily_breadth[d_str] = []
            daily_breadth[d_str].append(1 if r.prev_close > r.ema20 else 0)
            
            sym_records[d_str] = {
                'Open': r.Open, 'High': r.High, 'Low': r.Low, 'Close': r.Close,
                'gap_pct': r.gap_pct, 'prev_close': r.prev_close
            }
        symbol_days[sym] = sym_records
        
    dates = sorted(list(all_dates))
    market_regime = {d: np.mean(daily_breadth[d]) * 100.0 for d in dates if d in daily_breadth and len(daily_breadth[d]) > 0}
    print(f"Loaded {len(symbol_days)} stocks across {len(dates)} days.\n")
    
    # Grid of Gap Fade configurations:
    # Gap threshold: 1.5%, 2.0%, 2.5%
    # Stop Loss: 0.8%, 1.0%, 1.2%
    # Target: 1.5R, 2.0R, or EOD close
    
    configs = [
        ("Fade Gap >= 1.5% | SL 1.0% | Target 1.5R | 2 tr/d", 1.5, 0.010, 1.5, 2),
        ("Fade Gap >= 1.5% | SL 1.0% | Target 2.0R | 2 tr/d", 1.5, 0.010, 2.0, 2),
        ("Fade Gap >= 2.0% | SL 1.0% | Target 1.5R | 2 tr/d", 2.0, 0.010, 1.5, 2),
        ("Fade Gap >= 2.0% | SL 1.2% | Target 2.0R | 2 tr/d", 2.0, 0.012, 2.0, 2),
        ("Fade Gap >= 2.0% | SL 1.2% | Target 2.0R | 3 tr/d", 2.0, 0.012, 2.0, 3),
        ("Fade Gap >= 2.5% | SL 1.2% | Target 2.0R | 2 tr/d", 2.5, 0.012, 2.0, 2),
    ]
    
    for title, min_gap, sl_pct, target_r, max_tr in configs:
        trades = []
        risk_cash = 1000.0
        
        for d in dates:
            candidates = []
            for sym, d_dict in symbol_days.items():
                if d not in d_dict: continue
                r = d_dict[d]
                gap = r['gap_pct']
                if np.isnan(gap) or gap < min_gap: continue
                open_p = r['Open']
                if open_p <= 0: continue
                
                candidates.append({
                    'symbol': sym, 'open_p': open_p, 'high_p': r['High'],
                    'low_p': r['Low'], 'close_p': r['Close'], 'gap': gap
                })
                
            if not candidates: continue
            candidates.sort(key=lambda x: -x['gap']) # Highest gap first
            
            for t in candidates[:max_tr]:
                open_p = t['open_p']
                high_p = t['high_p']
                low_p = t['low_p']
                close_p = t['close_p']
                
                # Sell Short at Open
                eff_entry = open_p * (1.0 - 0.0003)
                risk_pts = open_p * sl_pct
                sl_p = open_p + risk_pts
                target_p = open_p - (target_r * risk_pts)
                
                shares = int(risk_cash / risk_pts)
                if shares < 1: continue
                
                # Check outcome:
                # Worst-case sequence: if high_p >= sl_p, stopped out
                if high_p >= sl_p:
                    exit_p = sl_p * (1.0 + 0.0003)
                else:
                    if low_p <= target_p:
                        exit_p = target_p
                    else:
                        exit_p = close_p * (1.0 + 0.0003)
                        
                sell_v = shares * eff_entry
                buy_v = shares * exit_p
                gp = sell_v - buy_v
                fee = compute_zerodha_charges(buy_v, sell_v)
                npnl = gp - fee
                
                trades.append({
                    'date': d, 'year': int(d[:4]), 'symbol': t['symbol'],
                    'net_pnl': npnl, 'fee': fee, 'R': npnl / 1000.0
                })
                
        df_t = pd.DataFrame(trades)
        if len(df_t) == 0: continue
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
        print(f"[{title}]")
        print(f"  Trades: {len(df_t)} ({len(df_t)/n_mo:.1f}/mo) | WR: {wr:5.2f}% | PF: {pf:4.2f}")
        print(f"  Net PnL: Rs {tot_pnl:+10,.0f} (+{tot_pnl/1000:.1f}R) | Avg Mo Return: {tot_pnl/100000/n_mo*100:+5.2f}% / month")
        print(f"  Max DD: {max_dd:5.2f}% | Profitable Months: {prof_mo:.1f}%")
        print(f"  Yearly: { {y: int(v) for y, v in y_pnl.items()} }\n")

if __name__ == '__main__':
    test_gap_fade()
