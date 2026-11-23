"""
EXPLORATION 1: HIGH-PERFORMANCE NIFTY 200 MULTI-DAY SWING / POSITIONAL MOMENTUM (2022 - 2026)
Dictionary-indexed / vector-accelerated for instant execution.
"""

import os, glob, time
import numpy as np
import pandas as pd

def run_swing_momentum():
    start_t = time.time()
    files = glob.glob("data/nifty200_daily_cache/*.parquet")
    print(f"Loading {len(files)} Nifty 200 daily parquet files...", flush=True)
    
    symbol_days = {}
    all_dates = set()
    
    for f in files:
        sym = os.path.basename(f).replace(".parquet", "")
        df = pd.read_parquet(f).sort_values('Date').reset_index(drop=True)
        if len(df) < 200: continue
        df['Date'] = pd.to_datetime(df['Date'])
        df['date_str'] = df['Date'].dt.strftime('%Y-%m-%d')
        df['ema20'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['high_20'] = df['High'].rolling(20).max().shift(1)
        df['low_10'] = df['Low'].rolling(10).min().shift(1)
        df['vol_20'] = df['Volume'].rolling(20).mean().shift(1)
        df['rvol'] = df['Volume'] / np.where(df['vol_20'] > 0, df['vol_20'], df['Volume'])
        
        symbol_days[sym] = {}
        for idx, r in df.iterrows():
            d_str = r['date_str']
            if int(d_str[:4]) >= 2022:
                all_dates.add(d_str)
                symbol_days[sym][d_str] = {
                    'Close': r['Close'],
                    'High': r['High'],
                    'Low': r['Low'],
                    'Open': r['Open'],
                    'ema20': r['ema20'],
                    'high_20': r['high_20'],
                    'low_10': r['low_10'],
                    'rvol': r['rvol']
                }
                
    dates = sorted(list(all_dates))
    print(f"Loaded {len(symbol_days)} stocks across {len(dates)} trading days in {time.time() - start_t:.1f}s.", flush=True)
    
    # Test multiple parameter variations:
    # Slots: 5 slots (Rs 20k each) vs 10 slots (Rs 10k each)
    # Stop loss: 10-day Low vs 20 EMA vs Fixed 5%
    # Holding max days: 7 days vs 10 days vs 15 days
    for n_slots, max_hold in [(5, 10), (10, 10), (5, 7), (10, 15)]:
        slot_cash = 100000.0 / n_slots
        open_positions = []
        closed_trades = []
        
        for d in dates:
            # Check exits
            remaining_pos = []
            for p in open_positions:
                sym = p['symbol']
                if d not in symbol_days[sym]:
                    remaining_pos.append(p)
                    continue
                r = symbol_days[sym][d]
                c = r['Close']
                l = r['Low']
                days_held = p['days_held'] + 1
                
                exit_px = None
                if l <= p['sl']:
                    exit_px = p['sl']
                elif c < r['low_10'] and days_held >= 3:
                    exit_px = c
                elif days_held >= max_hold:
                    exit_px = c
                    
                if exit_px is not None:
                    gross_ret = (exit_px / p['entry'] - 1.0) * 100.0
                    fee_pct = 0.25 # Delivery statutory roundtrip
                    net_ret = gross_ret - fee_pct
                    pnl = slot_cash * (net_ret / 100.0)
                    closed_trades.append({
                        'entry_date': p['entry_date'],
                        'exit_date': d,
                        'symbol': sym,
                        'days_held': days_held,
                        'net_ret': net_ret,
                        'pnl': pnl,
                        'R': pnl / 1000.0
                    })
                else:
                    p['days_held'] = days_held
                    remaining_pos.append(p)
            open_positions = remaining_pos
            
            # Check entries
            if len(open_positions) < n_slots:
                candidates = []
                for sym, d_dict in symbol_days.items():
                    if d not in d_dict: continue
                    r = d_dict[d]
                    if r['Close'] > r['high_20'] and r['rvol'] >= 1.5 and r['Close'] > r['ema20']:
                        candidates.append({'symbol': sym, 'score': r['rvol'], 'entry': r['Close'], 'sl': r['low_10']})
                        
                candidates.sort(key=lambda x: -x['score'])
                slots_avail = n_slots - len(open_positions)
                for c in candidates[:slots_avail]:
                    sl_dist = (c['entry'] - c['sl']) / c['entry']
                    if sl_dist > 0.08: c['sl'] = c['entry'] * 0.92
                    open_positions.append({
                        'symbol': c['symbol'],
                        'entry_date': d,
                        'entry': c['entry'],
                        'sl': c['sl'],
                        'days_held': 0
                    })
                    
        df_t = pd.DataFrame(closed_trades)
        if len(df_t) > 0:
            df_t['exit_dt'] = pd.to_datetime(df_t['exit_date'])
            df_t['ym'] = df_t['exit_dt'].dt.to_period('M')
            n_mo = df_t['ym'].nunique()
            tot_pnl = df_t['pnl'].sum()
            tot_r = df_t['R'].sum()
            wins = df_t[df_t['pnl'] > 0]
            wr = len(wins) / len(df_t) * 100.0
            gw = wins['pnl'].sum()
            gl = abs(df_t[df_t['pnl'] <= 0]['pnl'].sum())
            pf = gw / gl if gl > 0 else 0
            monthly_ret = df_t.groupby('ym')['pnl'].sum() / 100000.0 * 100.0
            
            print(f"Slots: {n_slots:2d} | MaxHold: {max_hold:2d}d | Trades: {len(df_t):4d} | WR: {wr:5.2f}% | PF: {pf:4.2f} | Net PnL: Rs {tot_pnl:+10,.0f} | Monthly: {monthly_ret.mean():+5.2f}%/mo | WinMo: {(monthly_ret>0).sum()}/{n_mo}", flush=True)

if __name__ == '__main__':
    run_swing_momentum()
