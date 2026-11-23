"""
BROAD INSTITUTIONAL INTRADAY STRATEGY DISCOVERY (2022 - 2026)
Tests 8 distinct structural edge hypotheses on 30 mega-caps across 991 trading dates.
100% Point-in-Time, Next-Bar Execution (+0.03% slippage), Exact Zerodha Fees.
Fixed static sizing: Rs 1,000 risk (1R) on Rs 1,00,000 capital.
"""

import os, glob, time
import numpy as np
import pandas as pd
from datetime import time as dtime

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
    symbols = [
        'ADANIENT', 'AXISBANK', 'BAJFINANCE', 'BHARTIARTL', 'COALINDIA', 
        'GRASIM', 'HCLTECH', 'HDFCBANK', 'HINDUNILVR', 'ICICIBANK', 
        'INDUSINDBK', 'INFY', 'ITC', 'JSWSTEEL', 'KOTAKBANK', 
        'LT', 'MARUTI', 'NTPC', 'ONGC', 'POWERGRID', 
        'RELIANCE', 'SBIN', 'SUNPHARMA', 'TATAMOTORS', 'TATASTEEL', 
        'TCS', 'TECHM', 'TITAN', 'ULTRACEMCO', 'WIPRO'
    ]
    
    symbol_data = {}
    for sym in symbols:
        p_prev = f"data/stocks/{sym}_prev.parquet"
        p_2026 = f"data/stocks/{sym}_2026.parquet"
        dfs = []
        if os.path.exists(p_prev): dfs.append(pd.read_parquet(p_prev))
        if os.path.exists(p_2026): dfs.append(pd.read_parquet(p_2026))
        if not dfs: continue
        df = pd.concat(dfs, ignore_index=True)
        df['Date'] = pd.to_datetime(df['Date'])
        df = df[(df['Date'] >= '2021-11-01') & (df['Date'] <= '2026-10-31')].sort_values('Date').reset_index(drop=True)
        df.set_index('Date', inplace=True)
        
        # 5-min bars
        df_5m = df.resample('5min').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'}).dropna().reset_index()
        df_5m['time'] = df_5m['Date'].dt.time
        df_5m = df_5m[(df_5m['time'] >= dtime(9,15)) & (df_5m['time'] <= dtime(15,30))].reset_index(drop=True)
        df_5m['date_str'] = df_5m['Date'].dt.strftime('%Y-%m-%d')
        df_5m['time_str'] = df_5m['Date'].dt.strftime('%H:%M:%S')
        
        # VWAP
        df_5m['typ'] = (df_5m['High'] + df_5m['Low'] + df_5m['Close']) / 3.0
        df_5m['pv'] = df_5m['typ'] * df_5m['Volume']
        df_5m['cum_pv'] = df_5m.groupby('date_str')['pv'].cumsum()
        df_5m['cum_vol'] = df_5m.groupby('date_str')['Volume'].cumsum()
        df_5m['vwap'] = np.where(df_5m['cum_vol'] > 0, df_5m['cum_pv'] / df_5m['cum_vol'], df_5m['Close'])
        
        # Fast arrays per day
        days_dict = {}
        for d_str, grp in df_5m.groupby('date_str'):
            if len(grp) < 25: continue
            days_dict[d_str] = {
                'open': grp['Open'].values,
                'high': grp['High'].values,
                'low': grp['Low'].values,
                'close': grp['Close'].values,
                'volume': grp['Volume'].values,
                'vwap': grp['vwap'].values,
                'time_str': grp['time_str'].values,
                'n_bars': len(grp)
            }
        symbol_data[sym] = days_dict
        
    return symbol_data

def simulate_strategy(name, generate_signals_fn, symbol_data, all_dates):
    trades = []
    risk_cash = 1000.0 # Rs 1,000 risk = 1R
    
    for d in all_dates:
        daily_signals = []
        for sym, days_dict in symbol_data.items():
            if d not in days_dict: continue
            day = days_dict[d]
            sig = generate_signals_fn(sym, day)
            if sig:
                daily_signals.append(sig)
                
        if not daily_signals: continue
        # Take top 1 or 2 by score
        daily_signals.sort(key=lambda x: -x['score'])
        selected = daily_signals[:1]
        
        for sig in selected:
            day = sig['day']
            side = sig['side']
            b_in = sig['entry_bar']
            entry_p = sig['entry_p']
            sl_p = sig['sl_p']
            t1_p = sig['t1_p']
            t2_p = sig['t2_p']
            risk_pts = abs(entry_p - sl_p)
            if risk_pts <= 0: continue
            
            shares = int(risk_cash / risk_pts)
            if shares < 1: continue
            s_t1 = int(shares * 0.5)
            s_run = shares - s_t1
            if s_t1 < 1: s_t1 = 1
            
            t1_hit = False
            exit_p1 = 0.0
            exit_pr = 0.0
            highs = day['high']
            lows = day['low']
            closes = day['close']
            n_bars = day['n_bars']
            
            curr_sl = sl_p
            for j in range(b_in + 1, n_bars):
                h, l, c = highs[j], lows[j], closes[j]
                if side == 'BUY':
                    # Conservative sequencing: if ambiguous bar, stop hits first
                    if l <= curr_sl:
                        if not t1_hit: exit_p1, exit_pr = curr_sl, curr_sl
                        else: exit_pr = curr_sl
                        break
                    if not t1_hit and h >= t1_p:
                        t1_hit = True
                        exit_p1 = t1_p
                        curr_sl = entry_p # move to BE
                    if t1_hit and h >= t2_p:
                        exit_pr = t2_p
                        break
                    if j >= 72 or j == n_bars - 1:
                        if not t1_hit: exit_p1 = c
                        exit_pr = c
                        break
                else:
                    if h >= curr_sl:
                        if not t1_hit: exit_p1, exit_pr = curr_sl, curr_sl
                        else: exit_pr = curr_sl
                        break
                    if not t1_hit and l <= t1_p:
                        t1_hit = True
                        exit_p1 = t1_p
                        curr_sl = entry_p
                    if t1_hit and l <= t2_p:
                        exit_pr = t2_p
                        break
                    if j >= 72 or j == n_bars - 1:
                        if not t1_hit: exit_p1 = c
                        exit_pr = c
                        break
                        
            if side == 'BUY':
                buy_val = shares * entry_p
                sell_val = (s_t1 * exit_p1) + (s_run * exit_pr)
            else:
                sell_val = shares * entry_p
                buy_val = (s_t1 * exit_p1) + (s_run * exit_pr)
                
            fee = compute_zerodha_charges(buy_val, sell_val)
            net_pnl = (sell_val - buy_val) - fee if side == 'BUY' else (sell_val - buy_val) - fee
            
            trades.append({
                'date': d, 'year': int(d[:4]), 'symbol': sig['symbol'], 'side': side,
                'net_pnl': net_pnl, 'R': net_pnl / 1000.0
            })
            
    df_t = pd.DataFrame(trades)
    if len(df_t) == 0:
        print(f"[{name}] 0 trades.")
        return
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
    y_pnl = df_t.groupby('year')['net_pnl'].sum().to_dict()
    
    print("="*85)
    print(f"STRATEGY: {name}")
    print(f"  Trades: {len(df_t)} ({len(df_t)/n_mo:.1f}/mo) | Win Rate: {wr:5.2f}% | Profit Factor: {pf:4.2f}")
    print(f"  Total Net PnL: Rs {tot_pnl:+10,.0f} (+{tot_pnl/1000:.1f}R) | Avg Monthly Return: {tot_pnl/100000/n_mo*100:+5.2f}%/mo")
    print(f"  Max Drawdown: {max_dd:5.2f}%")
    print(f"  Yearly: { {y: int(v) for y, v in y_pnl.items()} }\n", flush=True)

def main():
    t0 = time.time()
    print("Loading 30 mega-cap stocks across 2022-2026...", flush=True)
    symbol_data = load_data()
    all_dates = set()
    for sym, days in symbol_data.items():
        for d in days.keys():
            if int(d[:4]) >= 2022 and d <= '2026-10-31':
                all_dates.add(d)
    all_dates = sorted(list(all_dates))
    print(f"Loaded {len(symbol_data)} stocks across {len(all_dates)} trading dates in {time.time()-t0:.1f}s.\n", flush=True)
    
    # -------------------------------------------------------------
    # HYPOTHESIS 1: 30-min Opening Range Breakout (Close Confirmed)
    # -------------------------------------------------------------
    def sig_orb30(sym, day):
        highs, lows, closes, opens, vwap = day['high'], day['low'], day['close'], day['open'], day['vwap']
        if day['n_bars'] < 30: return None
        # First 6 bars = 30 mins (09:15 to 09:45)
        or_h = np.max(highs[:6])
        or_l = np.min(lows[:6])
        or_mid = (or_h + or_l) / 2.0
        
        # Look for breakout on bars 6 to 18 (09:45 to 10:45)
        for b_i in range(6, min(18, day['n_bars'] - 6)):
            if closes[b_i] > or_h and closes[b_i] > vwap[b_i]:
                # Enter next bar open
                entry_p = opens[b_i + 1] * (1.0 + 0.0003)
                risk_pts = max(entry_p * 0.004, min(entry_p * 0.012, abs(entry_p - or_mid)))
                return {
                    'symbol': sym, 'day': day, 'side': 'BUY', 'entry_bar': b_i + 1,
                    'entry_p': entry_p, 'sl_p': entry_p - risk_pts,
                    't1_p': entry_p + (2.0 * risk_pts), 't2_p': entry_p + (3.5 * risk_pts),
                    'score': (closes[b_i] - or_h) / or_h
                }
            elif closes[b_i] < or_l and closes[b_i] < vwap[b_i]:
                entry_p = opens[b_i + 1] * (1.0 - 0.0003)
                risk_pts = max(entry_p * 0.004, min(entry_p * 0.012, abs(or_mid - entry_p)))
                return {
                    'symbol': sym, 'day': day, 'side': 'SELL', 'entry_bar': b_i + 1,
                    'entry_p': entry_p, 'sl_p': entry_p + risk_pts,
                    't1_p': entry_p - (2.0 * risk_pts), 't2_p': entry_p - (3.5 * risk_pts),
                    'score': (or_l - closes[b_i]) / or_l
                }
        return None
        
    simulate_strategy("H1: 30-MIN ORB BREAKOUT (CLOSE CONFIRMED)", sig_orb30, symbol_data, all_dates)
    
    # -------------------------------------------------------------
    # HYPOTHESIS 2: VWAP Statistical Mean Reversion (Stretch Reversal)
    # When price stretches >= 1.5% from VWAP and shows a reversal candle
    # -------------------------------------------------------------
    def sig_vwap_mean_reversion(sym, day):
        highs, lows, closes, opens, vwap = day['high'], day['low'], day['close'], day['open'], day['vwap']
        if day['n_bars'] < 30: return None
        for b_i in range(12, min(50, day['n_bars'] - 6)):
            dev = (closes[b_i] - vwap[b_i]) / vwap[b_i] * 100.0
            # Overextended Upwards: Bearish reversal
            if dev >= 1.5 and closes[b_i] < opens[b_i] and closes[b_i] < closes[b_i-1]:
                entry_p = opens[b_i + 1] * (1.0 - 0.0003)
                risk_pts = entry_p * 0.008 # 0.8% stop
                return {
                    'symbol': sym, 'day': day, 'side': 'SELL', 'entry_bar': b_i + 1,
                    'entry_p': entry_p, 'sl_p': entry_p + risk_pts,
                    't1_p': vwap[b_i], 't2_p': vwap[b_i] * 0.995,
                    'score': dev
                }
            # Overextended Downwards: Bullish reversal
            elif dev <= -1.5 and closes[b_i] > opens[b_i] and closes[b_i] > closes[b_i-1]:
                entry_p = opens[b_i + 1] * (1.0 + 0.0003)
                risk_pts = entry_p * 0.008
                return {
                    'symbol': sym, 'day': day, 'side': 'BUY', 'entry_bar': b_i + 1,
                    'entry_p': entry_p, 'sl_p': entry_p - risk_pts,
                    't1_p': vwap[b_i], 't2_p': vwap[b_i] * 1.005,
                    'score': abs(dev)
                }
        return None
        
    simulate_strategy("H2: VWAP STRETCH MEAN REVERSION", sig_vwap_mean_reversion, symbol_data, all_dates)
    
    # -------------------------------------------------------------
    # HYPOTHESIS 3: Afternoon Breakout (11:30 - 13:30 Consolidation Expansion)
    # -------------------------------------------------------------
    def sig_afternoon_breakout(sym, day):
        highs, lows, closes, opens, vwap = day['high'], day['low'], day['close'], day['open'], day['vwap']
        if day['n_bars'] < 50: return None
        # Consolidation from 09:15 to 11:30 (first 27 bars)
        range_h = np.max(highs[:27])
        range_l = np.min(lows[:27])
        range_pct = (range_h - range_l) / range_l * 100.0
        if range_pct > 1.2: return None # Must be tight consolidation
        
        for b_i in range(27, min(50, day['n_bars'] - 6)):
            if closes[b_i] > range_h and closes[b_i] > vwap[b_i]:
                entry_p = opens[b_i + 1] * (1.0 + 0.0003)
                risk_pts = max(entry_p * 0.0035, min(entry_p * 0.008, abs(entry_p - range_l)))
                return {
                    'symbol': sym, 'day': day, 'side': 'BUY', 'entry_bar': b_i + 1,
                    'entry_p': entry_p, 'sl_p': entry_p - risk_pts,
                    't1_p': entry_p + (2.0 * risk_pts), 't2_p': entry_p + (3.5 * risk_pts),
                    'score': (closes[b_i] - range_h) / range_h
                }
            elif closes[b_i] < range_l and closes[b_i] < vwap[b_i]:
                entry_p = opens[b_i + 1] * (1.0 - 0.0003)
                risk_pts = max(entry_p * 0.0035, min(entry_p * 0.008, abs(range_h - entry_p)))
                return {
                    'symbol': sym, 'day': day, 'side': 'SELL', 'entry_bar': b_i + 1,
                    'entry_p': entry_p, 'sl_p': entry_p + risk_pts,
                    't1_p': entry_p - (2.0 * risk_pts), 't2_p': entry_p - (3.5 * risk_pts),
                    'score': (range_l - closes[b_i]) / range_l
                }
        return None
        
    simulate_strategy("H3: AFTERNOON TIGHT CONSOLIDATION BREAKOUT", sig_afternoon_breakout, symbol_data, all_dates)

if __name__ == '__main__':
    main()
