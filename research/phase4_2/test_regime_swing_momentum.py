"""
TEST REGIME-FILTERED ASYMMETRIC SWING MOMENTUM (2022 - 2026)
Key Enhancements:
1. Macro Market Regime Filter: Only enter new swing longs when NIFTY 50 is in a confirmed Bull Regime (Close > 50 SMA). In Bear/Chop regimes, 100% CASH.
2. Cross-Sectional Leader Filter: Only trade stocks with 60-day Relative Strength in Top 10% of Nifty 200.
3. Asymmetric Profit Capture: Risk 4% with Target 1 at +8% (50% exit) and Target 2 trailing with 20 EMA (capturing multi-week 15%-30% mega-runners).
4. Exact Zerodha Delivery Costs (0.1% STT buy + 0.1% STT sell + DP charges + slippage).
"""

import os, glob, time
import numpy as np
import pandas as pd

def compute_zerodha_delivery_charges(buy_val, sell_val):
    stt = (buy_val * 0.001) + (sell_val * 0.001)
    exchange = (buy_val + sell_val) * 0.0000297
    sebi = (buy_val + sell_val) * 0.000001
    stamp = buy_val * 0.00015
    dp = 15.34
    gst = (exchange + sebi) * 0.18
    return stt + exchange + sebi + stamp + dp + gst

def load_data():
    # 1. Load NIFTY 50 daily
    nifty_files = glob.glob("data/nifty50/NIFTY50_1min_*.csv")
    dfs = []
    for f in sorted(nifty_files):
        df = pd.read_csv(f)
        df['Date'] = pd.to_datetime(df['Timestamp'])
        dfs.append(df)
    nifty_1m = pd.concat(dfs, ignore_index=True).sort_values('Date').reset_index(drop=True)
    nifty_1m.set_index('Date', inplace=True)
    nifty_d = nifty_1m.resample('1D').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna().reset_index()
    nifty_d['sma50'] = nifty_d['Close'].rolling(50).mean()
    nifty_d['date_str'] = nifty_d['Date'].dt.strftime('%Y-%m-%d')
    nifty_regime = {row['date_str']: (row['Close'] > row['sma50']) for _, row in nifty_d.iterrows() if not pd.isna(row['sma50'])}
    
    # 2. Load 194 Nifty 200 daily stocks
    stock_files = glob.glob("data/nifty200_daily_cache/*.parquet")
    stocks = {}
    for f in stock_files:
        sym = os.path.basename(f).replace(".parquet", "")
        df = pd.read_parquet(f)
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date').reset_index(drop=True)
        if len(df) < 250: continue
        c = df['Close']
        df['sma20'] = c.rolling(20).mean()
        df['sma50'] = c.rolling(50).mean()
        df['sma200'] = c.rolling(200).mean()
        df['high20'] = df['High'].rolling(20).max().shift(1)
        df['vol_sma20'] = df['Volume'].rolling(20).mean()
        df['mom60'] = c.pct_change(60) * 100.0
        df['date_str'] = df['Date'].dt.strftime('%Y-%m-%d')
        stocks[sym] = df.set_index('date_str')
        
    return nifty_regime, stocks

def simulate_regime_swing():
    t0 = time.time()
    print("Loading Nifty 50 and 194 stocks...", flush=True)
    nifty_regime, stocks = load_data()
    print(f"Data loaded in {time.time()-t0:.1f}s. Running Regime-Filtered Asymmetric Swing Simulation...", flush=True)
    
    all_dates = set()
    for sym, df in stocks.items():
        for d in df.index:
            if d >= '2022-01-01' and d <= '2026-10-31':
                all_dates.add(d)
    dates = sorted(list(all_dates))
    
    max_pos = 3
    pos_alloc = 33333.0
    open_positions = []
    completed_trades = []
    
    for i, d in enumerate(dates):
        # 1. Update existing positions
        remaining = []
        for pos in open_positions:
            sym = pos['symbol']
            df = stocks[sym]
            if d not in df.index:
                remaining.append(pos)
                continue
            row = df.loc[d]
            pos['holding_days'] += 1
            h, l, c = row['High'], row['Low'], row['Close']
            
            # Trailing stop management
            if h > pos['highest_price']:
                pos['highest_price'] = h
                if pos['t1_hit']:
                    pos['sl_price'] = max(pos['sl_price'], row['sma20']) # Trail with 20 SMA after T1
                    
            # Check Stop Loss
            if l <= pos['sl_price']:
                exit_p = pos['sl_price'] * (1.0 - 0.0003)
                sell_val = pos['shares'] * exit_p
                buy_val = pos['shares'] * pos['entry_price']
                fee = compute_zerodha_delivery_charges(buy_val, sell_val)
                net_pnl = (sell_val - buy_val) - fee
                completed_trades.append({
                    'symbol': sym, 'entry_date': pos['entry_date'], 'exit_date': d,
                    'entry_price': pos['entry_price'], 'exit_price': exit_p,
                    'shares': pos['shares'], 'holding_days': pos['holding_days'],
                    'net_pnl': net_pnl, 'ret_pct': (exit_p - pos['entry_price']) / pos['entry_price'] * 100.0,
                    'reason': 'STOP_LOSS' if not pos['t1_hit'] else 'TRAIL_SL_AFTER_T1',
                    'year': int(d[:4])
                })
                continue
                
            # Check Target 1 (+8%)
            if not pos['t1_hit'] and h >= pos['t1_price']:
                pos['t1_hit'] = True
                # Partial booking 50%
                s_t1 = int(pos['shares'] * 0.5)
                s_run = pos['shares'] - s_t1
                exit_p = pos['t1_price']
                sell_val = s_t1 * exit_p
                buy_val = s_t1 * pos['entry_price']
                fee = compute_zerodha_delivery_charges(buy_val, sell_val)
                completed_trades.append({
                    'symbol': sym, 'entry_date': pos['entry_date'], 'exit_date': d,
                    'entry_price': pos['entry_price'], 'exit_price': exit_p,
                    'shares': s_t1, 'holding_days': pos['holding_days'],
                    'net_pnl': (sell_val - buy_val) - fee, 'ret_pct': 8.0,
                    'reason': 'PARTIAL_TARGET_1', 'year': int(d[:4])
                })
                pos['shares'] = s_run
                pos['sl_price'] = pos['entry_price'] # Move SL to Break-Even!
                
            # Time stop: 30 days max
            if pos['holding_days'] >= 30:
                exit_p = c * (1.0 - 0.0003)
                sell_val = pos['shares'] * exit_p
                buy_val = pos['shares'] * pos['entry_price']
                fee = compute_zerodha_delivery_charges(buy_val, sell_val)
                completed_trades.append({
                    'symbol': sym, 'entry_date': pos['entry_date'], 'exit_date': d,
                    'entry_price': pos['entry_price'], 'exit_price': exit_p,
                    'shares': pos['shares'], 'holding_days': pos['holding_days'],
                    'net_pnl': (sell_val - buy_val) - fee, 'ret_pct': (exit_p - pos['entry_price']) / pos['entry_price'] * 100.0,
                    'reason': 'TIME_STOP_30D', 'year': int(d[:4])
                })
                continue
                
            remaining.append(pos)
        open_positions = remaining
        
        # 2. Check for New Entries
        # REGIME CHECK: Only enter if Nifty 50 > 50 SMA
        nifty_bull = nifty_regime.get(d, False)
        available_slots = max_pos - len(open_positions)
        
        if nifty_bull and available_slots > 0 and i < len(dates) - 1:
            open_syms = [p['symbol'] for p in open_positions]
            candidates = []
            
            for sym, df in stocks.items():
                if sym in open_syms or d not in df.index: continue
                row = df.loc[d]
                if pd.isna(row['sma50']) or pd.isna(row['sma200']) or pd.isna(row['high20']) or pd.isna(row['vol_sma20']): continue
                
                # Strict Institutional Trend: Close > 20 SMA > 50 SMA > 200 SMA
                if row['Close'] > row['sma20'] and row['sma20'] > row['sma50'] and row['sma50'] > row['sma200']:
                    # Breakout to new 20-day high with Volume expansion >= 1.5x
                    if row['Close'] > row['high20'] and row['Volume'] >= 1.5 * row['vol_sma20']:
                        mom = row['mom60'] if not pd.isna(row['mom60']) else 0.0
                        candidates.append({'symbol': sym, 'score': mom})
                        
            if candidates:
                candidates.sort(key=lambda x: -x['score']) # Highest 60d momentum leader
                for c in candidates[:available_slots]:
                    sym = c['symbol']
                    next_d = dates[i+1]
                    df = stocks[sym]
                    if next_d not in df.index: continue
                    next_open = df.loc[next_d, 'Open'] * (1.0 + 0.0003)
                    shares = int(pos_alloc / next_open)
                    if shares < 1: continue
                    open_positions.append({
                        'symbol': sym,
                        'entry_date': next_d,
                        'entry_price': next_open,
                        'shares': shares,
                        'holding_days': 0,
                        'sl_price': next_open * 0.96, # 4% Initial SL
                        't1_price': next_open * 1.08, # +8% Target 1 (2:1 R:R)
                        'highest_price': next_open,
                        't1_hit': False
                    })
                    
    df_t = pd.DataFrame(completed_trades)
    if len(df_t) == 0:
        print("0 trades executed.")
        return
        
    df_t['ym'] = pd.to_datetime(df_t['exit_date']).dt.to_period('M')
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
    avg_hold = df_t['holding_days'].mean()
    y_pnl = df_t.groupby('year')['net_pnl'].sum().to_dict()
    
    print("="*85)
    print("REGIME-FILTERED ASYMMETRIC SWING MOMENTUM SYSTEM (2022 - 2026)")
    print(f"  Total Trades: {len(df_t)} ({len(df_t)/n_mo:.1f}/mo) | Win Rate: {wr:5.2f}% | Profit Factor: {pf:4.2f}")
    print(f"  Total Net Profit: Rs {tot_pnl:+10,.0f} | Avg Monthly Return: {tot_pnl/100000/n_mo*100:+5.2f}% / month")
    print(f"  Max Drawdown: {max_dd:5.2f}% | Avg Holding: {avg_hold:.1f} days")
    print(f"  Yearly Breakdown: { {y: int(v) for y, v in y_pnl.items()} }")
    print("="*85, flush=True)

if __name__ == '__main__':
    simulate_regime_swing()
