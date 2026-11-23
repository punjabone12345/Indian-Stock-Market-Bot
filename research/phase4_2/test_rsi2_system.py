"""
TEST INSTITUTIONAL RSI(2) MEAN REVERSION ON NIFTY 200 (2022 - 2026)
Famous institutional edge:
- Stock must be in long-term uptrend: Close > 200-day SMA
- Short-term oversold pullback: RSI(2) < 10 (or 5)
- Enter at 15:20 PM close (fully executable, zero look-ahead)
- Exit when RSI(2) > 65 or Close > 5-day SMA
- Strictly zero compounding: Sizing based on fixed rupee risk or equal allocation
- Exact Zerodha charges + slippage included
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

def compute_rsi(series, period=2):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / np.where(loss > 0, loss, 1e-9)
    return 100.0 - (100.0 / (1.0 + rs))

def test_rsi2_system():
    files = glob.glob("data/nifty200_daily_cache/*.parquet")
    print(f"Loading {len(files)} stocks for RSI(2) Mean Reversion test...", flush=True)
    
    symbol_days = {}
    all_dates = set()
    
    for f in files:
        sym = os.path.basename(f).replace(".parquet", "")
        df = pd.read_parquet(f).sort_values('Date').reset_index(drop=True)
        if len(df) < 250: continue
        df['Date'] = pd.to_datetime(df['Date'])
        df['date_str'] = df['Date'].dt.strftime('%Y-%m-%d')
        
        df['sma200'] = df['Close'].rolling(200).mean()
        df['sma5'] = df['Close'].rolling(5).mean()
        df['rsi2'] = compute_rsi(df['Close'], period=2)
        
        mask = (df['Date'].dt.year >= 2022) & (df['date_str'] <= '2026-10-31')
        sub_df = df[mask]
        
        sym_records = {}
        for r in sub_df.itertuples(index=False):
            d_str = r.date_str
            all_dates.add(d_str)
            sym_records[d_str] = {
                'Open': r.Open, 'High': r.High, 'Low': r.Low, 'Close': r.Close,
                'sma200': r.sma200, 'sma5': r.sma5, 'rsi2': r.rsi2
            }
        symbol_days[sym] = sym_records
        
    dates = sorted(list(all_dates))
    print(f"Loaded {len(symbol_days)} stocks across {len(dates)} days.\n")
    
    # Portfolio simulation:
    # Max open positions: 3, 5, 8
    # Capital: Rs 1,00,000 (equal capital per position, zero compounding)
    # Entry: Close > sma200 and rsi2 < 10 (or 5)
    # Exit: Close > sma5 or rsi2 > 70 or 5 days max hold
    
    for max_pos in [3, 5, 8]:
        for rsi_thresh in [10.0, 5.0]:
            capital = 100000.0
            pos_cap = capital / max_pos
            open_positions = {}
            trades = []
            
            for d in dates:
                # 1. Check exits for open positions
                to_close = []
                for sym, pos in open_positions.items():
                    if d not in symbol_days[sym]: continue
                    r = symbol_days[sym][d]
                    close_p = r['Close']
                    days_held = pos['days_held'] + 1
                    pos['days_held'] = days_held
                    
                    # Exit conditions: Close > sma5 or rsi2 > 70 or days_held >= 5
                    if close_p > r['sma5'] or r['rsi2'] > 70.0 or days_held >= 5:
                        exit_p = close_p * (1.0 - 0.0003) # 0.03% slippage
                        shares = pos['shares']
                        buy_v = shares * pos['entry_p']
                        sell_v = shares * exit_p
                        gp = sell_v - buy_v
                        fee = compute_zerodha_charges(buy_v, sell_v)
                        npnl = gp - fee
                        
                        trades.append({
                            'date': d, 'year': int(d[:4]), 'symbol': sym,
                            'entry_p': pos['entry_p'], 'exit_p': exit_p,
                            'shares': shares, 'net_pnl': npnl, 'fee': fee,
                            'days_held': days_held
                        })
                        to_close.append(sym)
                        
                for sym in to_close:
                    del open_positions[sym]
                    
                # 2. Check entries if capacity available
                avail_slots = max_pos - len(open_positions)
                if avail_slots <= 0: continue
                
                candidates = []
                for sym, d_dict in symbol_days.items():
                    if sym in open_positions: continue
                    if d not in d_dict: continue
                    r = d_dict[d]
                    close_p = r['Close']
                    sma200 = r['sma200']
                    rsi2 = r['rsi2']
                    if np.isnan(sma200) or np.isnan(rsi2): continue
                    
                    # Entry setup: In uptrend, oversold
                    if close_p > sma200 and rsi2 <= rsi_thresh:
                        candidates.append({
                            'symbol': sym, 'close_p': close_p, 'rsi2': rsi2
                        })
                        
                if not candidates: continue
                candidates.sort(key=lambda x: x['rsi2']) # lowest RSI first
                
                for c in candidates[:avail_slots]:
                    sym = c['symbol']
                    entry_p = c['close_p'] * (1.0 + 0.0003)
                    shares = int(pos_cap / entry_p)
                    if shares < 1: continue
                    
                    open_positions[sym] = {
                        'entry_p': entry_p,
                        'shares': shares,
                        'days_held': 0
                    }
                    
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
            avg_hold = df_t['days_held'].mean()
            
            print("="*85)
            print(f"[RSI(2) Mean Reversion | Max Pos: {max_pos} (Rs {pos_cap:,.0f}/pos) | RSI <= {rsi_thresh}]")
            print(f"  Trades: {len(df_t)} ({len(df_t)/n_mo:.1f}/mo) | WR: {wr:5.2f}% | PF: {pf:4.2f} | Avg Hold: {avg_hold:.1f} days")
            print(f"  Net PnL: Rs {tot_pnl:+10,.0f} | Avg Mo Return: {tot_pnl/100000/n_mo*100:+5.2f}% / month (+Rs {tot_pnl/n_mo:+,.0f}/mo)")
            print(f"  Max DD: {max_dd:5.2f}% (-Rs {abs((df_t['cum'] - df_t['peak']).min()):,.0f}) | Profitable Months: {prof_mo:.1f}%")
            print(f"  Yearly: { {y: int(v) for y, v in y_pnl.items()} }\n")

if __name__ == '__main__':
    test_rsi2_system()
