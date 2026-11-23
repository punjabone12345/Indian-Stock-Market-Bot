"""
PHASE 4.2: AUDIT OF ORB BREAKOUT AND RETEST EXECUTION
Compares three distinct implementations of the Opening Range Breakout (ORB) Retest:
1. Version 1: Original ORB Implementation (Phase 3 baseline: same-bar retro fill, zero slippage, single fee)
2. Version 2: Corrected Wick-Breakout ORB (Candle high/low crosses OR boundary, next-bar resting limit fill, conservative sequencing, full costs)
3. Version 3: Corrected Close-Confirmed Breakout ORB (Candle close crosses OR boundary, next-bar resting limit fill, conservative sequencing, full costs)

Strictly evaluates across 1,182 trading sessions on 5-minute intraday tick data.
"""

import os, json, time
import numpy as np
import pandas as pd
from datetime import time as dtime
from costs import compute_trade_costs, compute_order_charges

def load_symbol_5m(symbol):
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
    df_5m = df.resample('5min').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna().reset_index()
    df_5m['time'] = df_5m['Date'].dt.time
    df_5m = df_5m[(df_5m['time'] >= t_start) & (df_5m['time'] <= t_end)].reset_index(drop=True)
    df_5m['date_str'] = df_5m['Date'].dt.strftime('%Y-%m-%d')
    df_5m['time_str'] = df_5m['Date'].dt.strftime('%H:%M:%S')
    
    # VWAP
    df_5m['typ'] = (df_5m['High'] + df_5m['Low'] + df_5m['Close']) / 3.0
    df_5m['pv'] = df_5m['typ'] * df_5m['Volume']
    df_5m['cum_pv'] = df_5m.groupby('date_str')['pv'].cumsum()
    df_5m['cum_vol'] = df_5m.groupby('date_str')['Volume'].cumsum()
    df_5m['vwap'] = np.where(df_5m['cum_vol'] > 0, df_5m['cum_pv'] / df_5m['cum_vol'], df_5m['Close'])
    
    return df_5m

def run_orb_audit():
    start_t = time.time()
    os.makedirs("research/phase4_2/reports", exist_ok=True)
    
    symbols = [
        'ADANIENT', 'AXISBANK', 'BAJFINANCE', 'BHARTIARTL', 'COALINDIA', 
        'GRASIM', 'HCLTECH', 'HDFCBANK', 'HINDUNILVR', 'ICICIBANK', 
        'INDUSINDBK', 'INFY', 'ITC', 'JSWSTEEL', 'KOTAKBANK', 
        'LT', 'MARUTI', 'NTPC', 'ONGC', 'POWERGRID', 
        'RELIANCE', 'SBIN', 'SUNPHARMA', 'TATAMOTORS', 'TATASTEEL', 
        'TCS', 'TECHM', 'TITAN', 'ULTRACEMCO', 'WIPRO'
    ]
    
    print(f"Loading 5-minute bars for {len(symbols)} liquid mega-caps...", flush=True)
    symbol_days = {}
    all_dates = set()
    
    for sym in symbols:
        df = load_symbol_5m(sym)
        if df is None: continue
        symbol_days[sym] = {}
        grouped = df.groupby('date_str')
        prev_close = None
        or_vols = []
        
        for d_str, d_df in grouped:
            n_bars = len(d_df)
            if n_bars < 25:
                if n_bars > 0: prev_close = d_df['Close'].values[-1]
                continue
            
            opens = d_df['Open'].values
            highs = d_df['High'].values
            lows = d_df['Low'].values
            closes = d_df['Close'].values
            volumes = d_df['Volume'].values
            vwaps = d_df['vwap'].values
            time_strs = d_df['time_str'].values
            
            high_15m = float(np.max(highs[:3]))
            low_15m = float(np.min(lows[:3]))
            close_15m = closes[2]
            vol_15m = float(np.sum(volumes[:3]))
            range_15m = high_15m - low_15m
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
                    'mid_15m': (high_15m + low_15m) / 2.0,
                    'close_15m': close_15m,
                    'range_15m': range_15m,
                    'rvol': rvol
                }
                
    sorted_dates = sorted(list(all_dates))
    print(f"Loaded {len(sorted_dates)} trading sessions across {len(symbol_days)} stocks in {time.time() - start_t:.1f}s.", flush=True)
    
    versions = ['V1_ORIGINAL', 'V2_WICK_CORRECTED', 'V3_CLOSE_CONFIRMED']
    audit_results = {}
    
    for ver in versions:
        trades = []
        skipped_trades = 0
        total_slippage = 0.0
        total_costs = 0.0
        risk_cash = 1000.0
        
        for date_str in sorted_dates:
            candidates = []
            
            for sym, d_dict in symbol_days.items():
                if date_str not in d_dict: continue
                info = d_dict[date_str]
                if info['rvol'] < 1.5: continue
                
                n_bars = info['n_bars']
                opens, highs, lows, closes, vwaps = info['opens'], info['highs'], info['lows'], info['closes'], info['vwaps']
                times = info['time_strs']
                h15, l15, m15 = info['high_15m'], info['low_15m'], info['mid_15m']
                
                # --- VERSION 1: ORIGINAL ORB (Phase 3 baseline) ---
                if ver == 'V1_ORIGINAL':
                    max_b = min(20, n_bars - 6)
                    for b_i in range(4, max_b):
                        # Retest condition checked at bar b_i:
                        if highs[b_i - 1] > h15 and lows[b_i] <= h15 and closes[b_i] >= h15 and closes[b_i] > vwaps[b_i]:
                            entry_p = h15
                            sl_p = m15
                            risk_pts = max(entry_p * 0.0035, min(entry_p * 0.009, abs(entry_p - sl_p)))
                            candidates.append({
                                'symbol': sym, 'side': 'BUY', 'fill_bar': b_i,
                                'entry_p': entry_p, 'sl_p': entry_p - risk_pts,
                                'risk_pts': risk_pts, 'score': info['rvol'], 'info': info,
                                't1_r': 2.0, 't2_r': 3.5, 'signal_time': times[b_i], 'fill_time': times[b_i]
                            })
                            break
                        elif lows[b_i - 1] < l15 and highs[b_i] >= l15 and closes[b_i] <= l15 and closes[b_i] < vwaps[b_i]:
                            entry_p = l15
                            sl_p = m15
                            risk_pts = max(entry_p * 0.0035, min(entry_p * 0.009, abs(sl_p - entry_p)))
                            candidates.append({
                                'symbol': sym, 'side': 'SELL', 'fill_bar': b_i,
                                'entry_p': entry_p, 'sl_p': entry_p + risk_pts,
                                'risk_pts': risk_pts, 'score': info['rvol'], 'info': info,
                                't1_r': 2.0, 't2_r': 3.5, 'signal_time': times[b_i], 'fill_time': times[b_i]
                            })
                            break
                            
                # --- VERSION 2: CORRECTED WICK-BREAKOUT ORB ---
                elif ver == 'V2_WICK_CORRECTED':
                    # Breakout: High/Low crosses range boundary between bar 3 (09:30) and bar 14 (10:25)
                    # Once a wick breakout occurs, a resting limit order is placed at the boundary for subsequent bars
                    for b_break in range(3, min(14, n_bars - 8)):
                        # Bullish Wick Breakout:
                        if highs[b_break] > h15:
                            signal_time = times[b_break]
                            # Resting limit order placed at h15 starting at bar b_break + 1
                            for b_fill in range(b_break + 1, min(24, n_bars - 6)):
                                # Did price dip to h15?
                                if lows[b_fill] <= h15:
                                    # Realistic fill modeling
                                    if opens[b_fill] < h15:
                                        # Gapped down below limit: fill at Open
                                        entry_p = opens[b_fill]
                                    else:
                                        entry_p = h15
                                    sl_p = m15
                                    # Don't enter if entry is already below stop loss
                                    if entry_p <= sl_p: break
                                    risk_pts = max(entry_p * 0.0035, min(entry_p * 0.009, abs(entry_p - sl_p)))
                                    candidates.append({
                                        'symbol': sym, 'side': 'BUY', 'fill_bar': b_fill,
                                        'entry_p': entry_p, 'sl_p': entry_p - risk_pts,
                                        'risk_pts': risk_pts, 'score': info['rvol'], 'info': info,
                                        't1_r': 2.0, 't2_r': 3.5, 'signal_time': signal_time, 'fill_time': times[b_fill]
                                    })
                                    break
                            break # Only evaluate first breakout
                        elif lows[b_break] < l15:
                            signal_time = times[b_break]
                            for b_fill in range(b_break + 1, min(24, n_bars - 6)):
                                if highs[b_fill] >= l15:
                                    if opens[b_fill] > l15:
                                        entry_p = opens[b_fill]
                                    else:
                                        entry_p = l15
                                    sl_p = m15
                                    if entry_p >= sl_p: break
                                    risk_pts = max(entry_p * 0.0035, min(entry_p * 0.009, abs(sl_p - entry_p)))
                                    candidates.append({
                                        'symbol': sym, 'side': 'SELL', 'fill_bar': b_fill,
                                        'entry_p': entry_p, 'sl_p': entry_p + risk_pts,
                                        'risk_pts': risk_pts, 'score': info['rvol'], 'info': info,
                                        't1_r': 2.0, 't2_r': 3.5, 'signal_time': signal_time, 'fill_time': times[b_fill]
                                    })
                                    break
                            break

                # --- VERSION 3: CORRECTED CLOSE-CONFIRMED BREAKOUT ORB ---
                elif ver == 'V3_CLOSE_CONFIRMED':
                    # Breakout: Candle CLOSE crosses outside range boundary between bar 3 and bar 14
                    for b_break in range(3, min(14, n_bars - 8)):
                        if closes[b_break] > h15:
                            signal_time = times[b_break]
                            # Resting limit order at h15 starting at bar b_break + 1
                            for b_fill in range(b_break + 1, min(24, n_bars - 6)):
                                if lows[b_fill] <= h15:
                                    if opens[b_fill] < h15:
                                        entry_p = opens[b_fill]
                                    else:
                                        entry_p = h15
                                    sl_p = m15
                                    if entry_p <= sl_p: break
                                    risk_pts = max(entry_p * 0.0035, min(entry_p * 0.009, abs(entry_p - sl_p)))
                                    candidates.append({
                                        'symbol': sym, 'side': 'BUY', 'fill_bar': b_fill,
                                        'entry_p': entry_p, 'sl_p': entry_p - risk_pts,
                                        'risk_pts': risk_pts, 'score': info['rvol'], 'info': info,
                                        't1_r': 2.0, 't2_r': 3.5, 'signal_time': signal_time, 'fill_time': times[b_fill]
                                    })
                                    break
                            break
                        elif closes[b_break] < l15:
                            signal_time = times[b_break]
                            for b_fill in range(b_break + 1, min(24, n_bars - 6)):
                                if highs[b_fill] >= l15:
                                    if opens[b_fill] > l15:
                                        entry_p = opens[b_fill]
                                    else:
                                        entry_p = l15
                                    sl_p = m15
                                    if entry_p >= sl_p: break
                                    risk_pts = max(entry_p * 0.0035, min(entry_p * 0.009, abs(sl_p - entry_p)))
                                    candidates.append({
                                        'symbol': sym, 'side': 'SELL', 'fill_bar': b_fill,
                                        'entry_p': entry_p, 'sl_p': entry_p + risk_pts,
                                        'risk_pts': risk_pts, 'score': info['rvol'], 'info': info,
                                        't1_r': 2.0, 't2_r': 3.5, 'signal_time': signal_time, 'fill_time': times[b_fill]
                                    })
                                    break
                            break

            if not candidates: continue
            candidates.sort(key=lambda x: -x['score'])
            t = candidates[0]
            
            entry_p = t['entry_p']
            sl_p = t['sl_p']
            risk_pts = t['risk_pts']
            side = t['side']
            fill_bar = t['fill_bar']
            info = t['info']
            highs, lows, closes = info['highs'], info['lows'], info['closes']
            n_bars = info['n_bars']
            
            # Position sizing
            shares = int(risk_cash / risk_pts)
            if ver == 'V1_ORIGINAL':
                if shares < 1: shares = 1
            else:
                # REMOVE max(1, shares) defect
                if shares < 1:
                    skipped_trades += 1
                    continue
                    
            s_t1 = int(shares * 0.50)
            s_run = shares - s_t1
            if s_t1 < 1: s_t1 = 1
            
            t1_p = entry_p + (2.0 * risk_pts) if side == 'BUY' else entry_p - (2.0 * risk_pts)
            t2_p = entry_p + (3.5 * risk_pts) if side == 'BUY' else entry_p - (3.5 * risk_pts)
            
            t1_hit = False
            curr_sl = sl_p
            exit_p1 = 0.0
            exit_pr = 0.0
            exit_reason = 'UNKNOWN'
            
            # Simulate trade execution bar by bar
            for j in range(fill_bar + 1, n_bars):
                h, l, c = highs[j], lows[j], closes[j]
                
                if ver == 'V1_ORIGINAL':
                    # Original logic
                    if side == 'BUY':
                        if l <= curr_sl:
                            if not t1_hit: exit_p1, exit_pr = curr_sl, curr_sl
                            else: exit_pr = curr_sl
                            exit_reason = 'STOP_LOSS'
                            break
                        if not t1_hit and h >= t1_p: t1_hit = True; exit_p1 = t1_p
                        if t1_hit and h >= t2_p: exit_pr = t2_p; exit_reason = 'TARGET_2'; break
                        if j == n_bars - 1 or j >= 72:
                            if not t1_hit: exit_p1 = c
                            exit_pr = c; exit_reason = 'EOD_SQUAREOFF'; break
                    else:
                        if h >= curr_sl:
                            if not t1_hit: exit_p1, exit_pr = curr_sl, curr_sl
                            else: exit_pr = curr_sl
                            exit_reason = 'STOP_LOSS'
                            break
                        if not t1_hit and l <= t1_p: t1_hit = True; exit_p1 = t1_p
                        if t1_hit and l <= t2_p: exit_pr = t2_p; exit_reason = 'TARGET_2'; break
                        if j == n_bars - 1 or j >= 72:
                            if not t1_hit: exit_p1 = c
                            exit_pr = c; exit_reason = 'EOD_SQUAREOFF'; break
                else:
                    # CORRECTED CONSERVATIVE INTRABAR SEQUENCING & SLIPPAGE
                    if side == 'BUY':
                        # Case 1: Before T1 is hit
                        if not t1_hit:
                            # Conservative intrabar rule: If BOTH SL and Target hit within same bar, SL triggered!
                            if l <= curr_sl and h >= t1_p:
                                exit_p1, exit_pr = curr_sl, curr_sl
                                exit_reason = 'CONSERVATIVE_SL_ON_AMBIGUOUS_BAR'
                                break
                            elif l <= curr_sl:
                                exit_p1, exit_pr = curr_sl, curr_sl
                                exit_reason = 'STOP_LOSS'
                                break
                            elif h >= t1_p:
                                t1_hit = True
                                exit_p1 = t1_p
                                curr_sl = entry_p # Move runner to Breakeven
                        # Case 2: After T1 hit, runner active
                        else:
                            # Runner stop is at breakeven (entry_p). If both breakeven and T2 hit:
                            if l <= curr_sl and h >= t2_p:
                                exit_pr = curr_sl
                                exit_reason = 'CONSERVATIVE_BREAKEVEN_ON_AMBIGUOUS_BAR'
                                break
                            elif l <= curr_sl:
                                exit_pr = curr_sl
                                exit_reason = 'RUNNER_BREAKEVEN_SL'
                                break
                            elif h >= t2_p:
                                exit_pr = t2_p
                                exit_reason = 'RUNNER_TARGET_2'
                                break
                                
                        # Time-stop: 15:15 IST (bar 72)
                        if j >= 72 or j == n_bars - 1:
                            if not t1_hit: exit_p1 = c
                            exit_pr = c
                            exit_reason = '1515_HARD_SQUAREOFF'
                            break
                    else: # SELL SIDE
                        if not t1_hit:
                            if h >= curr_sl and l <= t1_p:
                                exit_p1, exit_pr = curr_sl, curr_sl
                                exit_reason = 'CONSERVATIVE_SL_ON_AMBIGUOUS_BAR'
                                break
                            elif h >= curr_sl:
                                exit_p1, exit_pr = curr_sl, curr_sl
                                exit_reason = 'STOP_LOSS'
                                break
                            elif l <= t1_p:
                                t1_hit = True
                                exit_p1 = t1_p
                                curr_sl = entry_p # Move runner to Breakeven
                        else:
                            if h >= curr_sl and l <= t2_p:
                                exit_pr = curr_sl
                                exit_reason = 'CONSERVATIVE_BREAKEVEN_ON_AMBIGUOUS_BAR'
                                break
                            elif h >= curr_sl:
                                exit_pr = curr_sl
                                exit_reason = 'RUNNER_BREAKEVEN_SL'
                                break
                            elif l <= t2_p:
                                exit_pr = t2_p
                                exit_reason = 'RUNNER_TARGET_2'
                                break
                                
                        if j >= 72 or j == n_bars - 1:
                            if not t1_hit: exit_p1 = c
                            exit_pr = c
                            exit_reason = '1515_HARD_SQUAREOFF'
                            break

            # Calculate charges and frictions
            if ver == 'V1_ORIGINAL':
                # Simplified single fee formula
                if side == 'BUY':
                    gp = s_t1 * (exit_p1 - entry_p) + (s_run * (exit_pr - entry_p) if s_run > 0 else 0)
                else:
                    gp = s_t1 * (entry_p - exit_p1) + (s_run * (entry_p - exit_pr) if s_run > 0 else 0)
                fee = 125.0 # Fixed average
                npnl = gp - fee
                slip = 0.0
            else:
                cost_res = compute_trade_costs(
                    side=side,
                    entry_price=entry_p,
                    entry_qty=shares,
                    exit1_price=exit_p1,
                    exit1_qty=s_t1,
                    exit2_price=exit_pr,
                    exit2_qty=s_run,
                    slippage_pct=0.0003 # 0.03% institutional slippage
                )
                gp = cost_res['gross_pnl']
                fee = cost_res['statutory_charges']
                slip = cost_res['slippage_cost']
                npnl = cost_res['net_pnl']
                
            total_slippage += slip
            total_costs += fee
            
            trades.append({
                'date': date_str,
                'year': int(date_str[:4]),
                'symbol': t['symbol'],
                'side': side,
                'signal_time': t['signal_time'],
                'fill_time': t['fill_time'],
                'shares': shares,
                'entry_p': round(entry_p, 2),
                'exit_p1': round(exit_p1, 2),
                'exit_pr': round(exit_pr, 2),
                'exit_reason': exit_reason,
                'gross_pnl': round(gp, 2),
                'statutory_fee': round(fee, 2),
                'slippage_cost': round(slip, 2),
                'net_pnl': round(npnl, 2),
                'R': round(npnl / risk_cash, 3)
            })
            
        df_t = pd.DataFrame(trades)
        df_t.to_csv(f"research/phase4_2/reports/trade_log_{ver}.csv", index=False)
        
        # Performance metrics
        wins = df_t[df_t['net_pnl'] > 0]
        losses = df_t[df_t['net_pnl'] <= 0]
        wr = len(wins) / len(df_t) * 100.0 if len(df_t) > 0 else 0.0
        gw = wins['net_pnl'].sum()
        gl = abs(losses['net_pnl'].sum())
        pf = gw / gl if gl > 0 else 0.0
        tot_r = df_t['R'].sum()
        
        # Drawdowns
        df_t['cum'] = df_t['R'].cumsum()
        df_t['peak'] = df_t['cum'].cummax()
        df_t['dd'] = df_t['cum'] - df_t['peak']
        max_dd = df_t['dd'].min()
        
        # Monthly returns (assuming ₹100,000 base)
        df_t['date_dt'] = pd.to_datetime(df_t['date'])
        df_t['ym'] = df_t['date_dt'].dt.to_period('M')
        monthly_pnls = df_t.groupby('ym')['net_pnl'].sum()
        m_rets = monthly_pnls / 100000.0 * 100.0
        win_months = (m_rets > 0).sum()
        tot_months = len(m_rets)
        
        # In-Sample vs Out-of-Sample
        is_df = df_t[df_t['year'].isin([2022, 2023])]
        oos_df = df_t[df_t['year'].isin([2024, 2025, 2026])]
        is_r = is_df['R'].sum() if len(is_df) > 0 else 0.0
        oos_r = oos_df['R'].sum() if len(oos_df) > 0 else 0.0
        
        audit_results[ver] = {
            'trades': len(df_t),
            'skipped_trades': skipped_trades,
            'win_rate_pct': round(wr, 2),
            'profit_factor': round(pf, 2),
            'net_R': round(tot_r, 2),
            'net_profit_inr': round(float(df_t['net_pnl'].sum()), 2),
            'max_drawdown_R': round(max_dd, 2),
            'in_sample_R': round(is_r, 2),
            'out_of_sample_R': round(oos_r, 2),
            'total_statutory_fees': round(total_costs, 2),
            'total_slippage_cost': round(total_slippage, 2),
            'profitable_months': int(win_months),
            'total_months': tot_months,
            'win_month_pct': round(win_months / tot_months * 100.0, 2) if tot_months > 0 else 0.0
        }
        
        print(f"\n[{ver}]")
        print(f"  Trades: {len(df_t):4d} | Skipped: {skipped_trades} | WR: {wr:5.2f}% | PF: {pf:4.2f} | Net R: {tot_r:+7.2f}R | MaxDD: {max_dd:6.2f}R")
        print(f"  IS (2022-23): {is_r:+6.1f}R | OOS (2024-26): {oos_r:+6.1f}R | WinMo: {win_months}/{tot_months} ({win_months/tot_months*100.0:.1f}%)")
        print(f"  Total Fees Paid: Rs {total_costs:,.2f} | Total Slippage: Rs {total_slippage:,.2f}")
        
    with open("research/phase4_2/reports/orb_execution_audit_summary.json", "w") as f:
        json.dump(audit_results, f, indent=2)
    print("\nSaved ORB Execution Audit results to research/phase4_2/reports/orb_execution_audit_summary.json")

if __name__ == '__main__':
    run_orb_audit()
