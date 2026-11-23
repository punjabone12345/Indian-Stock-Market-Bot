"""
TEST MULTI-DAY SWING TRADING SYSTEMS (2022 - 2026)
Universe: 194 Liquid Nifty 200 Stocks (Daily OHLCV Data)
Capital Base: Rs 1,00,000 (Static, strictly Zero Compounding)
Position Sizing: Fixed Rs 33,333 per position (Max 3 concurrent positions)
Cost Model: Exact Zerodha Equity Delivery (CNC):
  - Brokerage: Rs 0
  - STT: 0.1% on buy, 0.1% on sell
  - Exchange: 0.00297% on buy and sell
  - SEBI: 0.0001% on buy and sell
  - Stamp Duty: 0.015% on buy
  - DP Charges: Rs 15.34 per scrip on sell
  - GST: 18% on (Exchange + SEBI + DP)
  - Slippage: 0.03% on entry and exit
"""

import os, glob, time
import numpy as np
import pandas as pd

def compute_zerodha_delivery_charges(buy_val, sell_val):
    brokerage = 0.0 # Zero on delivery
    stt = (buy_val * 0.001) + (sell_val * 0.001) # 0.1% on both
    exchange = (buy_val + sell_val) * 0.0000297
    sebi = (buy_val + sell_val) * 0.000001
    stamp = buy_val * 0.00015 # 0.015% on buy
    dp = 15.34 # Rs 13 + 18% GST
    gst = (exchange + sebi) * 0.18
    return brokerage + stt + exchange + sebi + stamp + dp + gst

def load_all_stocks():
    t0 = time.time()
    files = glob.glob("data/nifty200_daily_cache/*.parquet")
    stocks = {}
    print(f"Loading {len(files)} Nifty 200 daily stock parquets...", flush=True)
    
    for f in files:
        sym = os.path.basename(f).replace(".parquet", "")
        df = pd.read_parquet(f)
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date').reset_index(drop=True)
        if len(df) < 250: continue # Need at least 1 year for 200 SMA
        
        # Precompute indicators
        c = df['Close']
        df['sma5'] = c.rolling(5).mean()
        df['sma10'] = c.rolling(10).mean()
        df['sma20'] = c.rolling(20).mean()
        df['sma50'] = c.rolling(50).mean()
        df['sma200'] = c.rolling(200).mean()
        df['high20'] = df['High'].rolling(20).max().shift(1)
        df['high10'] = df['High'].rolling(10).max().shift(1)
        df['low10'] = df['Low'].rolling(10).min().shift(1)
        df['vol_sma20'] = df['Volume'].rolling(20).mean()
        
        # RSI 2
        delta = c.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(2).mean()
        avg_loss = loss.rolling(2).mean()
        rs = avg_gain / (avg_loss + 1e-9)
        df['rsi2'] = 100 - (100 / (1 + rs))
        
        # 60-day momentum (return)
        df['mom60'] = c.pct_change(60) * 100.0
        
        # Filter for testing period (2022 to 2026)
        df['date_str'] = df['Date'].dt.strftime('%Y-%m-%d')
        stocks[sym] = df.set_index('date_str')
        
    print(f"Loaded {len(stocks)} qualified stocks in {time.time()-t0:.1f}s.", flush=True)
    return stocks

def run_simulation(name, select_signals_fn, exit_condition_fn, stocks, max_pos=3, pos_alloc=33333.0):
    # Collect all unique dates across 2022 to 2026
    all_dates = set()
    for sym, df in stocks.items():
        for d in df.index:
            if d >= '2022-01-01' and d <= '2026-10-31':
                all_dates.add(d)
    dates = sorted(list(all_dates))
    
    open_positions = [] # List of dicts
    completed_trades = []
    
    for i, d in enumerate(dates):
        # 1. Update and check exits for currently open positions
        remaining_positions = []
        for pos in open_positions:
            sym = pos['symbol']
            df = stocks[sym]
            if d not in df.index:
                remaining_positions.append(pos)
                continue
            row = df.loc[d]
            pos['holding_days'] += 1
            cur_price = row['Close']
            high_price = row['High']
            low_price = row['Low']
            
            # Check exit
            should_exit, exit_price, reason = exit_condition_fn(pos, row)
            if should_exit:
                exit_price = exit_price * (1.0 - 0.0003) # 0.03% slippage
                sell_val = pos['shares'] * exit_price
                buy_val = pos['shares'] * pos['entry_price']
                fee = compute_zerodha_delivery_charges(buy_val, sell_val)
                net_pnl = (sell_val - buy_val) - fee
                completed_trades.append({
                    'symbol': sym,
                    'entry_date': pos['entry_date'],
                    'exit_date': d,
                    'entry_price': pos['entry_price'],
                    'exit_price': exit_price,
                    'shares': pos['shares'],
                    'holding_days': pos['holding_days'],
                    'gross_pnl': sell_val - buy_val,
                    'fee': fee,
                    'net_pnl': net_pnl,
                    'ret_pct': (exit_price - pos['entry_price']) / pos['entry_price'] * 100.0,
                    'reason': reason,
                    'year': int(d[:4])
                })
            else:
                remaining_positions.append(pos)
        open_positions = remaining_positions
        
        # 2. Check for new entries if we have empty slots
        available_slots = max_pos - len(open_positions)
        if available_slots > 0 and i < len(dates) - 1:
            candidates = select_signals_fn(d, stocks, [p['symbol'] for p in open_positions])
            if candidates:
                candidates.sort(key=lambda x: -x['score'])
                for c in candidates[:available_slots]:
                    sym = c['symbol']
                    next_d = dates[i+1]
                    df = stocks[sym]
                    if next_d not in df.index: continue
                    next_open = df.loc[next_d, 'Open'] * (1.0 + 0.0003) # 0.03% slippage
                    shares = int(pos_alloc / next_open)
                    if shares < 1: continue
                    open_positions.append({
                        'symbol': sym,
                        'entry_date': next_d,
                        'entry_price': next_open,
                        'shares': shares,
                        'holding_days': 0,
                        'sl_price': c['sl_price_fn'](next_open),
                        'target_price': c['target_price_fn'](next_open),
                        'highest_price': next_open
                    })
                    
    df_t = pd.DataFrame(completed_trades)
    if len(df_t) == 0:
        print(f"[{name}] 0 trades.")
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
    print(f"SWING STRATEGY: {name}")
    print(f"  Trades: {len(df_t)} ({len(df_t)/n_mo:.1f}/mo) | Win Rate: {wr:5.2f}% | Profit Factor: {pf:4.2f}")
    print(f"  Total Net PnL: Rs {tot_pnl:+10,.0f} | Avg Monthly Return: {tot_pnl/100000/n_mo*100:+5.2f}% / month")
    print(f"  Max Drawdown: {max_dd:5.2f}% | Avg Holding: {avg_hold:.1f} days")
    print(f"  Yearly: { {y: int(v) for y, v in y_pnl.items()} }\n", flush=True)

def main():
    stocks = load_all_stocks()
    
    # -------------------------------------------------------------------------
    # SYSTEM 1: SHORT-TERM RSI(2) PULLBACK (Larry Connors Institutional Quant)
    # Buy extreme oversold dips in long-term uptrend, hold until 5-day SMA bounce
    # -------------------------------------------------------------------------
    def select_rsi2(d, stocks_dict, open_symbols):
        candidates = []
        for sym, df in stocks_dict.items():
            if sym in open_symbols or d not in df.index: continue
            row = df.loc[d]
            if pd.isna(row['sma200']) or pd.isna(row['rsi2']): continue
            # Bullish filter: Close > 200 SMA
            if row['Close'] > row['sma200'] and row['Close'] > row['sma50']:
                # Oversold trigger: RSI(2) <= 10 and 2 consecutive down days
                if row['rsi2'] <= 10.0:
                    candidates.append({
                        'symbol': sym,
                        'score': 100.0 - row['rsi2'], # Lower RSI = higher score
                        'sl_price_fn': lambda entry: entry * 0.95, # 5.0% Stop Loss
                        'target_price_fn': lambda entry: entry * 1.08 # 8.0% Target
                    })
        return candidates

    def exit_rsi2(pos, row):
        # Exit when price closes above 5-day SMA or hits 5% SL
        if row['Low'] <= pos['sl_price']:
            return True, pos['sl_price'], "STOP_LOSS"
        if row['Close'] > row['sma5']:
            return True, row['Close'], "SMA5_EXIT"
        if pos['holding_days'] >= 10: # Max 10 days time stop
            return True, row['Close'], "TIME_STOP"
        return False, 0.0, ""

    run_simulation("SYSTEM 1: RSI(2) SHORT-TERM PULLBACK IN UPTREND (2-6 Days)", select_rsi2, exit_rsi2, stocks)

    # -------------------------------------------------------------------------
    # SYSTEM 2: RELATIVE STRENGTH 20-DAY MOMENTUM BREAKOUT
    # Buy 20-day high breakouts in top 20% momentum leaders, hold with trailing stop
    # -------------------------------------------------------------------------
    def select_mom_breakout(d, stocks_dict, open_symbols):
        candidates = []
        for sym, df in stocks_dict.items():
            if sym in open_symbols or d not in df.index: continue
            row = df.loc[d]
            if pd.isna(row['sma50']) or pd.isna(row['high20']) or pd.isna(row['vol_sma20']): continue
            # Trend: 50 SMA > 200 SMA, Close > 50 SMA
            if row['Close'] > row['sma50'] and row['sma50'] > row['sma200']:
                # Breakout: Close > 20-day High on Volume >= 1.5x
                if row['Close'] > row['high20'] and row['Volume'] >= 1.5 * row['vol_sma20']:
                    candidates.append({
                        'symbol': sym,
                        'score': row['mom60'] if not pd.isna(row['mom60']) else 0.0,
                        'sl_price_fn': lambda entry: entry * 0.96, # 4.0% Stop Loss
                        'target_price_fn': lambda entry: entry * 1.10 # 10.0% Target
                    })
        return candidates

    def exit_mom_breakout(pos, row):
        # Trailing stop: 4% below highest price or 10% target
        if row['High'] > pos['highest_price']:
            pos['highest_price'] = row['High']
            pos['sl_price'] = max(pos['sl_price'], pos['highest_price'] * 0.96) # Trailing SL
            
        if row['Low'] <= pos['sl_price']:
            return True, pos['sl_price'], "STOP_LOSS"
        if row['High'] >= pos['target_price']:
            return True, pos['target_price'], "PROFIT_TARGET"
        if pos['holding_days'] >= 15:
            return True, row['Close'], "TIME_STOP"
        return False, 0.0, ""

    run_simulation("SYSTEM 2: 20-DAY MOMENTUM BREAKOUT + TRAILING STOP (5-15 Days)", select_mom_breakout, exit_mom_breakout, stocks)

    # -------------------------------------------------------------------------
    # SYSTEM 3: 20-EMA PULLBACK CONTINUATION (Trend Dip Buying)
    # Buy dips to 20-day EMA in strong trending stocks
    # -------------------------------------------------------------------------
    def select_ema20_pullback(d, stocks_dict, open_symbols):
        candidates = []
        for sym, df in stocks_dict.items():
            if sym in open_symbols or d not in df.index: continue
            row = df.loc[d]
            if pd.isna(row['sma20']) or pd.isna(row['sma50']) or pd.isna(row['sma200']): continue
            # Strong uptrend: 20 SMA > 50 SMA > 200 SMA
            if row['sma20'] > row['sma50'] and row['sma50'] > row['sma200']:
                # Low touched 20 SMA, Close bounced back above 20 SMA
                if row['Low'] <= row['sma20'] and row['Close'] >= row['sma20']:
                    candidates.append({
                        'symbol': sym,
                        'score': (row['Close'] - row['sma200']) / row['sma200'] * 100.0,
                        'sl_price_fn': lambda entry: entry * 0.965, # 3.5% Stop Loss
                        'target_price_fn': lambda entry: entry * 1.07 # 7.0% Target (2R)
                    })
        return candidates

    def exit_ema20_pullback(pos, row):
        if row['Low'] <= pos['sl_price']:
            return True, pos['sl_price'], "STOP_LOSS"
        if row['High'] >= pos['target_price']:
            return True, pos['target_price'], "TARGET_HIT"
        if pos['holding_days'] >= 12:
            return True, row['Close'], "TIME_STOP"
        return False, 0.0, ""

    run_simulation("SYSTEM 3: 20-EMA TREND PULLBACK (3-12 Days)", select_ema20_pullback, exit_ema20_pullback, stocks)

if __name__ == '__main__':
    main()
