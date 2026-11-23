"""
EXPLORATION 2: 1-MINUTE MICRO-PIVOT TIGHT-STOP MOMENTUM SYSTEM (2022 - 2026)
Tests whether tighter structural stops (0.25% - 0.45% risk) allow realistic 2.5R intraday targets
(0.65% - 1.10% move) to be reached within normal daily ATR, achieving high win rate and +10R/month.

Evaluated on TRUE 1-minute intraday bars across 1,182 trading sessions with Zerodha fees and slippage.
"""

import os, time
import numpy as np
import pandas as pd
from datetime import time as dtime
from costs import compute_trade_costs

def load_symbol_1m(symbol):
    p_prev = f"data/stocks/{symbol}_prev.parquet"
    p_2026 = f"data/stocks/{symbol}_2026.parquet"
    dfs = []
    if os.path.exists(p_prev): dfs.append(pd.read_parquet(p_prev))
    if os.path.exists(p_2026): dfs.append(pd.read_parquet(p_2026))
    if not dfs: return None
    df = pd.concat(dfs, ignore_index=True)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df[(df['Date'] >= '2021-11-01') & (df['Date'] <= '2026-10-31')].sort_values('Date').reset_index(drop=True)
    df.set_index('Date', inplace=True)
    t_start, t_end = dtime(9, 15), dtime(15, 30)
    df = df.between_time(t_start, t_end).reset_index()
    df['date_str'] = df['Date'].dt.strftime('%Y-%m-%d')
    df['time_str'] = df['Date'].dt.strftime('%H:%M:%S')
    
    # Intraday VWAP on 1m bars
    df['typ'] = (df['High'] + df['Low'] + df['Close']) / 3.0
    df['pv'] = df['typ'] * df['Volume']
    df['cum_pv'] = df.groupby('date_str')['pv'].cumsum()
    df['cum_vol'] = df.groupby('date_str')['Volume'].cumsum()
    df['vwap'] = np.where(df['cum_vol'] > 0, df['cum_pv'] / df['cum_vol'], df['Close'])
    
    return df

def run_tight_pivot_momentum():
    start_t = time.time()
    symbols = [
        'ADANIENT', 'AXISBANK', 'BAJFINANCE', 'BHARTIARTL', 'COALINDIA', 
        'GRASIM', 'HCLTECH', 'HDFCBANK', 'HINDUNILVR', 'ICICIBANK', 
        'INDUSINDBK', 'INFY', 'ITC', 'JSWSTEEL', 'KOTAKBANK', 
        'LT', 'MARUTI', 'NTPC', 'ONGC', 'POWERGRID', 
        'RELIANCE', 'SBIN', 'SUNPHARMA', 'TATAMOTORS', 'TATASTEEL', 
        'TCS', 'TECHM', 'TITAN', 'ULTRACEMCO', 'WIPRO'
    ]
    
    print(f"Loading 1-minute bars for {len(symbols)} symbols...", flush=True)
    symbol_days = {}
    all_dates = set()
    
    for sym in symbols:
        df = load_symbol_1m(sym)
        if df is None: continue
        symbol_days[sym] = {}
        grouped = df.groupby('date_str')
        prev_close = None
        or_vols = []
        
        for d_str, d_df in grouped:
            n_bars = len(d_df)
            if n_bars < 120: # Needs at least 2 hours of data
                if n_bars > 0: prev_close = d_df['Close'].values[-1]
                continue
                
            opens = d_df['Open'].values
            highs = d_df['High'].values
            lows = d_df['Low'].values
            closes = d_df['Close'].values
            volumes = d_df['Volume'].values
            vwaps = d_df['vwap'].values
            time_strs = d_df['time_str'].values
            
            # 15m Opening Range (first 15 1m bars)
            high_15m = float(np.max(highs[:15]))
            low_15m = float(np.min(lows[:15]))
            vol_15m = float(np.sum(volumes[:15]))
            rvol = vol_15m / np.mean(or_vols[-20:]) if len(or_vols) >= 10 and np.mean(or_vols[-20:]) > 0 else 1.0
            or_vols.append(vol_15m)
            prev_close = closes[-1]
            
            if int(d_str[:4]) >= 2022 and d_str <= '2026-10-31':
                all_dates.add(d_str)
                symbol_days[sym][d_str] = {
                    'n_bars': n_bars,
                    'opens': opens,
                    'highs': highs,
                    'lows': lows,
                    'closes': closes,
                    'volumes': volumes,
                    'vwaps': vwaps,
                    'time_strs': time_strs,
                    'high_15m': high_15m,
                    'low_15m': low_15m,
                    'rvol': rvol
                }
                
    sorted_dates = sorted(list(all_dates))
    print(f"Loaded 1m data for {len(symbol_days)} stocks across {len(sorted_dates)} sessions in {time.time() - start_t:.1f}s.", flush=True)
    
    # Test varying target ratios (2.0R vs 2.5R vs 3.0R) and max trades per day (1 vs 2 vs 3)
    for max_trades_per_day, target_r in [(1, 2.5), (2, 2.5), (3, 2.0), (2, 3.0)]:
        trades = []
        risk_cash = 1000.0 # Static 1R = Rs 1,000
        
        for date_str in sorted_dates:
            candidates = []
            
            for sym, d_dict in symbol_days.items():
                if date_str not in d_dict: continue
                info = d_dict[date_str]
                if info['rvol'] < 1.4: continue
                
                n_bars = info['n_bars']
                opens, highs, lows, closes, vwaps = info['opens'], info['highs'], info['lows'], info['closes'], info['vwaps']
                times = info['time_strs']
                h15, l15 = info['high_15m'], info['low_15m']
                
                # Scan between 09:30 (bar 15) and 11:30 (bar 135) for 1m breakout + micro-pullback
                for b in range(16, min(135, n_bars - 15)):
                    # Bullish: Broke above 15m high, trading above VWAP
                    if highs[b - 1] > h15 and closes[b - 1] > vwaps[b - 1]:
                        # Check micro-pullback: prior 3-5 bars had small consolidation
                        # Look for re-breakout above highest high of last 3 bars
                        local_high = float(np.max(highs[b-3:b]))
                        local_low = float(np.min(lows[b-3:b]))
                        
                        # Trigger: bar b breaks above local high
                        if closes[b] > local_high and closes[b] > vwaps[b]:
                            # Signal at bar b close -> Entry on bar b+1 open
                            fill_bar = b + 1
                            if fill_bar >= n_bars: break
                            entry_p = opens[fill_bar]
                            sl_p = local_low # Tight stop at micro-pivot low
                            
                            risk_dist = (entry_p - sl_p) / entry_p
                            # Tight stop filter: risk must be between 0.20% and 0.45%
                            if 0.0020 <= risk_dist <= 0.0045:
                                risk_pts = entry_p - sl_p
                                candidates.append({
                                    'symbol': sym, 'side': 'BUY', 'fill_bar': fill_bar,
                                    'entry_p': entry_p, 'sl_p': sl_p, 'risk_pts': risk_pts,
                                    'score': info['rvol'] * (1.0 / risk_dist), 'info': info
                                })
                                break
                    # Bearish: Broke below 15m low, trading below VWAP
                    elif lows[b - 1] < l15 and closes[b - 1] < vwaps[b - 1]:
                        local_low = float(np.min(lows[b-3:b]))
                        local_high = float(np.max(highs[b-3:b]))
                        
                        if closes[b] < local_low and closes[b] < vwaps[b]:
                            fill_bar = b + 1
                            if fill_bar >= n_bars: break
                            entry_p = opens[fill_bar]
                            sl_p = local_high
                            risk_dist = (sl_p - entry_p) / entry_p
                            if 0.0020 <= risk_dist <= 0.0045:
                                risk_pts = sl_p - entry_p
                                candidates.append({
                                    'symbol': sym, 'side': 'SELL', 'fill_bar': fill_bar,
                                    'entry_p': entry_p, 'sl_p': sl_p, 'risk_pts': risk_pts,
                                    'score': info['rvol'] * (1.0 / risk_dist), 'info': info
                                })
                                break
                                
            if not candidates: continue
            candidates.sort(key=lambda x: -x['score'])
            
            # Take top N trades of the day
            for t in candidates[:max_trades_per_day]:
                entry_p = t['entry_p']
                sl_p = t['sl_p']
                risk_pts = t['risk_pts']
                side = t['side']
                fill_bar = t['fill_bar']
                info = t['info']
                highs, lows, closes = info['highs'], info['lows'], info['closes']
                n_bars = info['n_bars']
                
                shares = int(risk_cash / risk_pts)
                if shares < 1: continue
                s_t1 = int(shares * 0.50)
                s_run = shares - s_t1
                if s_t1 < 1: s_t1 = 1
                
                t1_p = entry_p + (2.0 * risk_pts) if side == 'BUY' else entry_p - (2.0 * risk_pts)
                t2_p = entry_p + (target_r * risk_pts) if side == 'BUY' else entry_p - (target_r * risk_pts)
                
                t1_hit = False
                curr_sl = sl_p
                exit_p1 = 0.0
                exit_pr = 0.0
                
                for j in range(fill_bar + 1, n_bars):
                    h, l, c = highs[j], lows[j], closes[j]
                    if side == 'BUY':
                        if not t1_hit:
                            # Conservative intrabar: SL triggers first if both touched
                            if l <= curr_sl and h >= t1_p:
                                exit_p1, exit_pr = curr_sl, curr_sl
                                break
                            elif l <= curr_sl:
                                exit_p1, exit_pr = curr_sl, curr_sl
                                break
                            elif h >= t1_p:
                                t1_hit = True; exit_p1 = t1_p; curr_sl = entry_p
                        else:
                            if l <= curr_sl and h >= t2_p:
                                exit_pr = curr_sl; break
                            elif l <= curr_sl:
                                exit_pr = curr_sl; break
                            elif h >= t2_p:
                                exit_pr = t2_p; break
                        if j >= 360 or j == n_bars - 1: # 15:15 IST (bar 360 on 1m)
                            if not t1_hit: exit_p1 = c
                            exit_pr = c; break
                    else: # SELL
                        if not t1_hit:
                            if h >= curr_sl and l <= t1_p:
                                exit_p1, exit_pr = curr_sl, curr_sl
                                break
                            elif h >= curr_sl:
                                exit_p1, exit_pr = curr_sl, curr_sl
                                break
                            elif l <= t1_p:
                                t1_hit = True; exit_p1 = t1_p; curr_sl = entry_p
                        else:
                            if h >= curr_sl and l <= t2_p:
                                exit_pr = curr_sl; break
                            elif h >= curr_sl:
                                exit_pr = curr_sl; break
                            elif l <= t2_p:
                                exit_pr = t2_p; break
                        if j >= 360 or j == n_bars - 1:
                            if not t1_hit: exit_p1 = c
                            exit_pr = c; break

                cost_res = compute_trade_costs(
                    side=side, entry_price=entry_p, entry_qty=shares,
                    exit1_price=exit_p1, exit1_qty=s_t1,
                    exit2_price=exit_pr, exit2_qty=s_run,
                    slippage_pct=0.0003
                )
                
                trades.append({
                    'date': date_str,
                    'year': int(date_str[:4]),
                    'net_pnl': cost_res['net_pnl'],
                    'fee': cost_res['statutory_charges'],
                    'R': cost_res['net_pnl'] / risk_cash
                })
                
        df_t = pd.DataFrame(trades)
        if len(df_t) > 0:
            df_t['date_dt'] = pd.to_datetime(df_t['date'])
            df_t['ym'] = df_t['date_dt'].dt.to_period('M')
            n_mo = df_t['ym'].nunique()
            tot_pnl = df_t['net_pnl'].sum()
            tot_r = df_t['R'].sum()
            wins = df_t[df_t['net_pnl'] > 0]
            wr = len(wins) / len(df_t) * 100.0
            gw = wins['net_pnl'].sum()
            gl = abs(df_t[df_t['net_pnl'] <= 0]['net_pnl'].sum())
            pf = gw / gl if gl > 0 else 0
            monthly_pnls = df_t.groupby('ym')['net_pnl'].sum()
            monthly_r = df_t.groupby('ym')['R'].sum()
            
            # Cumulative DD in R
            df_t['cum'] = df_t['R'].cumsum()
            df_t['peak'] = df_t['cum'].cummax()
            max_dd_r = (df_t['cum'] - df_t['peak']).min()
            
            print(f"\n[MaxTrades/Day: {max_trades_per_day} | Target: {target_r}R]")
            print(f"  Trades: {len(df_t):4d} ({len(df_t)/n_mo:.1f}/mo) | WR: {wr:5.2f}% | PF: {pf:4.2f} | Net R: {tot_r:+7.2f}R | MaxDD: {max_dd_r:6.2f}R")
            print(f"  Monthly Return: {monthly_r.mean():+5.2f}R/month ({monthly_pnls.mean():+,.0f} INR/mo on Rs 100k base)")
            print(f"  Profitable Months: {(monthly_r > 0).sum()}/{n_mo} ({(monthly_r > 0).mean()*100:.1f}%) | Fees: Rs {df_t['fee'].sum():,.2f}")

if __name__ == '__main__':
    run_tight_pivot_momentum()
