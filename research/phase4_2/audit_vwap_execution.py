"""
PHASE 4.2: AUDIT OF VWAP PULLBACK RETEST EXECUTION
Audits the VWAP strategy under realistic institutional execution models:
1. Version 1: Original Same-Bar Retro Fill (Phase 3 baseline: entered at VWAP of confirmation bar, 0 slippage, simplified fee)
2. Version 2: Next-Bar Market Order Execution (Signal at Bar i Close, executed on Bar i+1 OPEN with 0.03% slippage)
3. Version 3: Next-Bar Limit Order Retest (Signal at Bar i Close, resting limit order placed at VWAP for Bar i+1, fills if Bar i+1 dips to VWAP)

Evaluated across 1,182 trading sessions on 5-minute intraday tick data with exact leg-by-leg Zerodha charges.
"""

import os, json, time
import numpy as np
import pandas as pd
from datetime import time as dtime
from costs import compute_trade_costs

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

def run_vwap_execution_audit():
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
            
            open_15m = opens[0]
            high_15m = float(np.max(highs[:3]))
            low_15m = float(np.min(lows[:3]))
            close_15m = closes[2]
            vol_15m = float(np.sum(volumes[:3]))
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
                    'open_15m': open_15m,
                    'high_15m': high_15m,
                    'low_15m': low_15m,
                    'mid_15m': (high_15m + low_15m) / 2.0,
                    'close_15m': close_15m,
                    'rvol': rvol
                }
                
    sorted_dates = sorted(list(all_dates))
    print(f"Loaded {len(sorted_dates)} trading sessions in {time.time() - start_t:.1f}s.", flush=True)
    
    modes = ['V1_ORIGINAL_RETRO', 'V2_NEXT_BAR_MARKET', 'V3_NEXT_BAR_LIMIT_RETEST']
    vwap_results = {}
    
    for mode in modes:
        trades = []
        skipped_trades = 0
        total_costs = 0.0
        total_slippage = 0.0
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
                c15, o15 = info['close_15m'], info['open_15m']
                
                side = 'BUY' if c15 > o15 else 'SELL'
                
                # Check VWAP setup between bar 3 (09:30) and bar 18 (10:45)
                for b_i in range(3, min(18, n_bars - 6)):
                    if side == 'BUY':
                        if lows[b_i] <= vwaps[b_i] and closes[b_i] >= vwaps[b_i]:
                            # Signal confirmed at close of bar b_i
                            if mode == 'V1_ORIGINAL_RETRO':
                                entry_p = vwaps[b_i]
                                fill_bar = b_i
                                candidates.append({
                                    'symbol': sym, 'side': side, 'fill_bar': fill_bar,
                                    'entry_p': entry_p, 'score': info['rvol'], 'info': info,
                                    'signal_time': times[b_i], 'fill_time': times[b_i]
                                })
                                break
                            elif mode == 'V2_NEXT_BAR_MARKET':
                                # Executed at OPEN of next bar (b_i + 1)
                                fill_bar = b_i + 1
                                if fill_bar >= n_bars: break
                                entry_p = opens[fill_bar]
                                candidates.append({
                                    'symbol': sym, 'side': side, 'fill_bar': fill_bar,
                                    'entry_p': entry_p, 'score': info['rvol'], 'info': info,
                                    'signal_time': times[b_i], 'fill_time': times[fill_bar]
                                })
                                break
                            elif mode == 'V3_NEXT_BAR_LIMIT_RETEST':
                                # Limit order placed at VWAP for bar b_i + 1
                                fill_bar = b_i + 1
                                if fill_bar >= n_bars: break
                                # Did next bar touch VWAP?
                                if lows[fill_bar] <= vwaps[b_i]:
                                    if opens[fill_bar] < vwaps[b_i]:
                                        entry_p = opens[fill_bar] # Gapped down
                                    else:
                                        entry_p = vwaps[b_i]
                                    candidates.append({
                                        'symbol': sym, 'side': side, 'fill_bar': fill_bar,
                                        'entry_p': entry_p, 'score': info['rvol'], 'info': info,
                                        'signal_time': times[b_i], 'fill_time': times[fill_bar]
                                    })
                                    break
                    else: # SELL SIDE
                        if highs[b_i] >= vwaps[b_i] and closes[b_i] <= vwaps[b_i]:
                            if mode == 'V1_ORIGINAL_RETRO':
                                entry_p = vwaps[b_i]
                                fill_bar = b_i
                                candidates.append({
                                    'symbol': sym, 'side': side, 'fill_bar': fill_bar,
                                    'entry_p': entry_p, 'score': info['rvol'], 'info': info,
                                    'signal_time': times[b_i], 'fill_time': times[b_i]
                                })
                                break
                            elif mode == 'V2_NEXT_BAR_MARKET':
                                fill_bar = b_i + 1
                                if fill_bar >= n_bars: break
                                entry_p = opens[fill_bar]
                                candidates.append({
                                    'symbol': sym, 'side': side, 'fill_bar': fill_bar,
                                    'entry_p': entry_p, 'score': info['rvol'], 'info': info,
                                    'signal_time': times[b_i], 'fill_time': times[fill_bar]
                                })
                                break
                            elif mode == 'V3_NEXT_BAR_LIMIT_RETEST':
                                fill_bar = b_i + 1
                                if fill_bar >= n_bars: break
                                if highs[fill_bar] >= vwaps[b_i]:
                                    if opens[fill_bar] > vwaps[b_i]:
                                        entry_p = opens[fill_bar]
                                    else:
                                        entry_p = vwaps[b_i]
                                    candidates.append({
                                        'symbol': sym, 'side': side, 'fill_bar': fill_bar,
                                        'entry_p': entry_p, 'score': info['rvol'], 'info': info,
                                        'signal_time': times[b_i], 'fill_time': times[fill_bar]
                                    })
                                    break

            if not candidates: continue
            candidates.sort(key=lambda x: -x['score'])
            t = candidates[0]
            
            entry_p = t['entry_p']
            side = t['side']
            fill_bar = t['fill_bar']
            info = t['info']
            highs, lows, closes = info['highs'], info['lows'], info['closes']
            n_bars = info['n_bars']
            m15 = info['mid_15m']
            
            risk_pts = max(entry_p * 0.0035, min(entry_p * 0.010, abs(entry_p - m15)))
            sl_p = entry_p - risk_pts if side == 'BUY' else entry_p + risk_pts
            t1_p = entry_p + (2.0 * risk_pts) if side == 'BUY' else entry_p - (2.0 * risk_pts)
            t2_p = entry_p + (3.5 * risk_pts) if side == 'BUY' else entry_p - (3.5 * risk_pts)
            
            shares = int(risk_cash / risk_pts)
            if mode == 'V1_ORIGINAL_RETRO':
                if shares < 1: shares = 1
            else:
                if shares < 1:
                    skipped_trades += 1
                    continue
                    
            s_t1 = int(shares * 0.50)
            s_run = shares - s_t1
            if s_t1 < 1: s_t1 = 1
            
            t1_hit = False
            curr_sl = sl_p
            exit_p1 = 0.0
            exit_pr = 0.0
            exit_reason = ""
            
            for j in range(fill_bar + 1, n_bars):
                h, l, c = highs[j], lows[j], closes[j]
                
                if mode == 'V1_ORIGINAL_RETRO':
                    if side == 'BUY':
                        if l <= curr_sl:
                            if not t1_hit: exit_p1, exit_pr = curr_sl, curr_sl
                            else: exit_pr = curr_sl
                            break
                        if not t1_hit and h >= t1_p: t1_hit = True; exit_p1 = t1_p
                        if t1_hit and h >= t2_p: exit_pr = t2_p; break
                        if j == n_bars - 1 or j >= 72:
                            if not t1_hit: exit_p1 = c
                            exit_pr = c; break
                    else:
                        if h >= curr_sl:
                            if not t1_hit: exit_p1, exit_pr = curr_sl, curr_sl
                            else: exit_pr = curr_sl
                            break
                        if not t1_hit and l <= t1_p: t1_hit = True; exit_p1 = t1_p
                        if t1_hit and l <= t2_p: exit_pr = t2_p; break
                        if j == n_bars - 1 or j >= 72:
                            if not t1_hit: exit_p1 = c
                            exit_pr = c; break
                else:
                    # CONSERVATIVE INTRABAR SEQUENCING & REALISTIC STOPS
                    if side == 'BUY':
                        if not t1_hit:
                            # If both SL and Target within bar range, SL triggers!
                            if l <= curr_sl and h >= t1_p:
                                exit_p1, exit_pr = curr_sl, curr_sl
                                exit_reason = 'SL_ON_AMBIGUOUS_BAR'
                                break
                            elif l <= curr_sl:
                                exit_p1, exit_pr = curr_sl, curr_sl
                                exit_reason = 'STOP_LOSS'
                                break
                            elif h >= t1_p:
                                t1_hit = True
                                exit_p1 = t1_p
                                curr_sl = entry_p # Breakeven
                        else:
                            if l <= curr_sl and h >= t2_p:
                                exit_pr = curr_sl
                                exit_reason = 'BREAKEVEN_ON_AMBIGUOUS_BAR'
                                break
                            elif l <= curr_sl:
                                exit_pr = curr_sl
                                exit_reason = 'BREAKEVEN_SL'
                                break
                            elif h >= t2_p:
                                exit_pr = t2_p
                                exit_reason = 'RUNNER_T2'
                                break
                        if j >= 72 or j == n_bars - 1:
                            if not t1_hit: exit_p1 = c
                            exit_pr = c
                            exit_reason = 'EOD_SQUAREOFF'
                            break
                    else: # SELL SIDE
                        if not t1_hit:
                            if h >= curr_sl and l <= t1_p:
                                exit_p1, exit_pr = curr_sl, curr_sl
                                exit_reason = 'SL_ON_AMBIGUOUS_BAR'
                                break
                            elif h >= curr_sl:
                                exit_p1, exit_pr = curr_sl, curr_sl
                                exit_reason = 'STOP_LOSS'
                                break
                            elif l <= t1_p:
                                t1_hit = True
                                exit_p1 = t1_p
                                curr_sl = entry_p
                        else:
                            if h >= curr_sl and l <= t2_p:
                                exit_pr = curr_sl
                                exit_reason = 'BREAKEVEN_ON_AMBIGUOUS_BAR'
                                break
                            elif h >= curr_sl:
                                exit_pr = curr_sl
                                exit_reason = 'BREAKEVEN_SL'
                                break
                            elif l <= t2_p:
                                exit_pr = t2_p
                                exit_reason = 'RUNNER_T2'
                                break
                        if j >= 72 or j == n_bars - 1:
                            if not t1_hit: exit_p1 = c
                            exit_pr = c
                            exit_reason = 'EOD_SQUAREOFF'
                            break

            if mode == 'V1_ORIGINAL_RETRO':
                if side == 'BUY':
                    gp = s_t1 * (exit_p1 - entry_p) + (s_run * (exit_pr - entry_p) if s_run > 0 else 0)
                else:
                    gp = s_t1 * (entry_p - exit_p1) + (s_run * (entry_p - exit_pr) if s_run > 0 else 0)
                fee = 125.0
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
                    slippage_pct=0.0003
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
        df_t.to_csv(f"research/phase4_2/reports/vwap_trade_log_{mode}.csv", index=False)
        
        wins = df_t[df_t['net_pnl'] > 0]
        losses = df_t[df_t['net_pnl'] <= 0]
        wr = len(wins) / len(df_t) * 100.0 if len(df_t) > 0 else 0.0
        gw = wins['net_pnl'].sum()
        gl = abs(losses['net_pnl'].sum())
        pf = gw / gl if gl > 0 else 0.0
        tot_r = df_t['R'].sum()
        
        df_t['cum'] = df_t['R'].cumsum()
        df_t['peak'] = df_t['cum'].cummax()
        df_t['dd'] = df_t['cum'] - df_t['peak']
        max_dd = df_t['dd'].min()
        
        df_t['date_dt'] = pd.to_datetime(df_t['date'])
        df_t['ym'] = df_t['date_dt'].dt.to_period('M')
        monthly_pnls = df_t.groupby('ym')['net_pnl'].sum()
        m_rets = monthly_pnls / 100000.0 * 100.0
        win_months = (m_rets > 0).sum()
        tot_months = len(m_rets)
        
        is_df = df_t[df_t['year'].isin([2022, 2023])]
        oos_df = df_t[df_t['year'].isin([2024, 2025, 2026])]
        is_r = is_df['R'].sum() if len(is_df) > 0 else 0.0
        oos_r = oos_df['R'].sum() if len(oos_df) > 0 else 0.0
        
        vwap_results[mode] = {
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
        
        print(f"\n[{mode}]")
        print(f"  Trades: {len(df_t):4d} | Skipped: {skipped_trades} | WR: {wr:5.2f}% | PF: {pf:4.2f} | Net R: {tot_r:+7.2f}R | MaxDD: {max_dd:6.2f}R")
        print(f"  IS (2022-23): {is_r:+6.1f}R | OOS (2024-26): {oos_r:+6.1f}R | WinMo: {win_months}/{tot_months} ({win_months/tot_months*100.0:.1f}%)")
        print(f"  Total Fees Paid: Rs {total_costs:,.2f} | Total Slippage: Rs {total_slippage:,.2f}")
        
    with open("research/phase4_2/reports/vwap_execution_audit_summary.json", "w") as f:
        json.dump(vwap_results, f, indent=2)
    print("\nSaved VWAP Execution Audit results to research/phase4_2/reports/vwap_execution_audit_summary.json")

if __name__ == '__main__':
    run_vwap_execution_audit()
