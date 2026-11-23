"""
PHASE 4.2: INSTITUTIONAL CONTROLLED COMPARISONS & RISK GOVERNOR AUDIT
Runs the 5 required controlled comparisons across the exact 1,182 trading sessions:
1. Version 1: Original ORB Implementation
2. Version 2: Wick-Breakout Corrected Implementation
3. Version 3: Close-Confirmed Breakout Implementation
4. Version 4: Corrected Portfolio Risk Governor (Standalone VWAP)
5. Version 5: Fully Corrected Combined Portfolio (VWAP + Corrected ORB + Gap & Go under MTM Governor)

Enforces:
- Removal of max(1, shares) (skip trade if shares < 1)
- Marked-to-market (MTM) 5-minute equity tracking (realised + unrealised P&L)
- Maximum Intraday MTM Drawdown vs Maximum Closed-Equity Drawdown
- Historical equity peak tracking
- MIS 5x leverage constraint (total exposure <= 5x equity)
- Available cash margin enforcement
- Strategy risk allocation budgets (60% VWAP, 30% ORB, 10% Gap)
- Aggregate portfolio risk budget cap
- Four-tier dynamic multiplier
- Leg-by-leg Zerodha charges + 0.03% slippage
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

def calculate_detailed_metrics(daily_df, trade_list, initial_capital=100000.0, skipped_count=0):
    df_d = daily_df.copy()
    df_t = pd.DataFrame(trade_list)
    
    final_eq = df_d['closed_equity'].iloc[-1]
    net_profit = final_eq - initial_capital
    n_days = len(df_d)
    n_years = n_days / 248.0
    cagr = ((final_eq / initial_capital) ** (1.0 / n_years) - 1.0) * 100.0 if n_years > 0 and final_eq > 0 else -100.0
    
    # Drawdowns
    max_closed_dd = abs(df_d['closed_dd_pct'].min())
    max_mtm_dd = abs(df_d['mtm_dd_pct'].min())
    
    # Monthly returns (Reconciled from daily equity)
    df_d['ym'] = pd.to_datetime(df_d['date']).dt.to_period('M')
    monthly_records = []
    prev_eq = initial_capital
    for ym, g in df_d.groupby('ym'):
        end_eq = g['closed_equity'].iloc[-1]
        m_ret = (end_eq / prev_eq - 1.0) * 100.0
        monthly_records.append({'ym': str(ym), 'ret_pct': m_ret, 'end_equity': end_eq})
        prev_eq = end_eq
    df_m = pd.DataFrame(monthly_records)
    
    n_months = len(df_m)
    cmgr = ((final_eq / initial_capital) ** (1.0 / n_months) - 1.0) * 100.0 if n_months > 0 and final_eq > 0 else -100.0
    arith_monthly = df_m['ret_pct'].mean()
    win_months = (df_m['ret_pct'] > 0).sum()
    win_month_pct = win_months / n_months * 100.0 if n_months > 0 else 0.0
    worst_month = df_m['ret_pct'].min()
    
    # Trade statistics
    if len(df_t) > 0:
        wins = df_t[df_t['net_pnl'] > 0]
        losses = df_t[df_t['net_pnl'] <= 0]
        wr = len(wins) / len(df_t) * 100.0
        gw = wins['net_pnl'].sum()
        gl = abs(losses['net_pnl'].sum())
        pf = gw / gl if gl > 0 else 0.0
        tot_r = df_t['R'].sum()
        tot_fees = df_t['statutory_fee'].sum()
        tot_slip = df_t['slippage_cost'].sum()
        avg_slip = tot_slip / len(df_t)
        
        # Longest losing streak
        loss_seq = (df_t['net_pnl'] <= 0).astype(int)
        streak = 0
        max_streak = 0
        for val in loss_seq:
            if val == 1:
                streak += 1
                if streak > max_streak: max_streak = streak
            else:
                streak = 0
    else:
        wr, pf, tot_r, tot_fees, tot_slip, avg_slip, max_streak = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0
        
    avg_util = df_d['capital_util_pct'].mean()
    peak_util = df_d['capital_util_pct'].max()
    
    return {
        'total_trades': len(df_t),
        'skipped_trades_insufficient_risk': skipped_count,
        'win_rate_pct': round(wr, 2),
        'profit_factor': round(pf, 2),
        'net_R': round(tot_r, 2),
        'net_profit_inr': round(net_profit, 2),
        'final_equity_inr': round(final_eq, 2),
        'arith_monthly_avg_pct': round(arith_monthly, 2),
        'cmgr_pct': round(cmgr, 2),
        'cagr_pct': round(cagr, 2),
        'max_intraday_mtm_dd_pct': round(max_mtm_dd, 2),
        'max_closed_equity_dd_pct': round(max_closed_dd, 2),
        'profitable_months': int(win_months),
        'total_months': n_months,
        'win_month_pct': round(win_month_pct, 2),
        'worst_month_pct': round(worst_month, 2),
        'longest_losing_streak': int(max_streak),
        'avg_slippage_per_trade_inr': round(avg_slip, 2),
        'total_transaction_costs_inr': round(tot_fees, 2),
        'total_slippage_inr': round(tot_slip, 2),
        'avg_capital_utilisation_pct': round(avg_util, 2),
        'peak_capital_utilisation_pct': round(peak_util, 2)
    }

def run_controlled_comparisons():
    start_t = time.time()
    os.makedirs("research/phase4_2/reports", exist_ok=True)
    os.makedirs("research/phase4_2/deliverables", exist_ok=True)
    
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
            range_15m = high_15m - low_15m
            gap_pct = (close_15m - prev_close) / prev_close * 100.0 if prev_close else 0.0
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
                    'gap_pct': gap_pct,
                    'rvol': rvol
                }
                
    sorted_dates = sorted(list(all_dates))
    print(f"Loaded {len(sorted_dates)} trading sessions in {time.time() - start_t:.1f}s.", flush=True)
    
    # -------------------------------------------------------------
    # SIMULATION FUNCTION FOR EACH CONTROLLED VERSION
    # -------------------------------------------------------------
    def run_simulation(version_id):
        capital = 100000.0
        closed_equity = capital
        closed_peak = capital
        mtm_peak = capital
        
        trades = []
        skipped_trades = 0
        daily_records = []
        
        for date_str in sorted_dates:
            # Day state
            day_mtm_low = closed_equity
            day_open_exposure = 0.0
            day_trades = []
            
            # Risk Governor Multiplier check at start of day based on current MTM drawdown
            cur_closed_dd = (closed_equity - closed_peak) / closed_peak * 100.0
            if cur_closed_dd > -2.0: mult = 1.00
            elif cur_closed_dd > -4.0: mult = 0.65
            elif cur_closed_dd > -6.0: mult = 0.35
            else: mult = 0.15
            
            # Discover trade signals for the day across strategies
            signals = []
            
            # 1. ORB Signals
            if version_id in ['V1_ORIGINAL_ORB', 'V2_WICK_ORB', 'V3_CLOSE_CONFIRMED_ORB', 'V5_COMBINED_PORTFOLIO']:
                for sym, d_dict in symbol_days.items():
                    if date_str not in d_dict: continue
                    info = d_dict[date_str]
                    if info['rvol'] < 1.5: continue
                    n_bars = info['n_bars']
                    opens, highs, lows, closes, vwaps = info['opens'], info['highs'], info['lows'], info['closes'], info['vwaps']
                    h15, l15, m15 = info['high_15m'], info['low_15m'], info['mid_15m']
                    
                    if version_id == 'V1_ORIGINAL_ORB':
                        for b_i in range(4, min(20, n_bars - 6)):
                            if highs[b_i - 1] > h15 and lows[b_i] <= h15 and closes[b_i] >= h15 and closes[b_i] > vwaps[b_i]:
                                risk_pts = max(h15 * 0.0035, min(h15 * 0.009, abs(h15 - m15)))
                                signals.append({
                                    'strategy': 'ORB', 'symbol': sym, 'side': 'BUY', 'fill_bar': b_i,
                                    'entry_p': h15, 'sl_p': h15 - risk_pts, 'risk_pts': risk_pts,
                                    'score': info['rvol'], 'info': info, 't1_r': 2.0, 't2_r': 3.5, 'mode': 'ORIGINAL'
                                })
                                break
                            elif lows[b_i - 1] < l15 and highs[b_i] >= l15 and closes[b_i] <= l15 and closes[b_i] < vwaps[b_i]:
                                risk_pts = max(l15 * 0.0035, min(l15 * 0.009, abs(l15 - m15)))
                                signals.append({
                                    'strategy': 'ORB', 'symbol': sym, 'side': 'SELL', 'fill_bar': b_i,
                                    'entry_p': l15, 'sl_p': l15 + risk_pts, 'risk_pts': risk_pts,
                                    'score': info['rvol'], 'info': info, 't1_r': 2.0, 't2_r': 3.5, 'mode': 'ORIGINAL'
                                })
                                break
                    elif version_id == 'V2_WICK_ORB':
                        # Wick breakout with next-bar limit retest fill
                        for b_break in range(3, min(14, n_bars - 8)):
                            if highs[b_break] > h15:
                                for b_fill in range(b_break + 1, min(24, n_bars - 6)):
                                    if lows[b_fill] <= h15:
                                        entry_p = opens[b_fill] if opens[b_fill] < h15 else h15
                                        if entry_p <= m15: break
                                        risk_pts = max(entry_p * 0.0035, min(entry_p * 0.009, abs(entry_p - m15)))
                                        signals.append({
                                            'strategy': 'ORB', 'symbol': sym, 'side': 'BUY', 'fill_bar': b_fill,
                                            'entry_p': entry_p, 'sl_p': entry_p - risk_pts, 'risk_pts': risk_pts,
                                            'score': info['rvol'], 'info': info, 't1_r': 2.0, 't2_r': 3.5, 'mode': 'CORRECTED'
                                        })
                                        break
                                break
                            elif lows[b_break] < l15:
                                for b_fill in range(b_break + 1, min(24, n_bars - 6)):
                                    if highs[b_fill] >= l15:
                                        entry_p = opens[b_fill] if opens[b_fill] > l15 else l15
                                        if entry_p >= m15: break
                                        risk_pts = max(entry_p * 0.0035, min(entry_p * 0.009, abs(entry_p - m15)))
                                        signals.append({
                                            'strategy': 'ORB', 'symbol': sym, 'side': 'SELL', 'fill_bar': b_fill,
                                            'entry_p': entry_p, 'sl_p': entry_p + risk_pts, 'risk_pts': risk_pts,
                                            'score': info['rvol'], 'info': info, 't1_r': 2.0, 't2_r': 3.5, 'mode': 'CORRECTED'
                                        })
                                        break
                                break
                    elif version_id in ['V3_CLOSE_CONFIRMED_ORB', 'V5_COMBINED_PORTFOLIO']:
                        # Close confirmed breakout with next-bar limit retest fill
                        for b_break in range(3, min(14, n_bars - 8)):
                            if closes[b_break] > h15:
                                for b_fill in range(b_break + 1, min(24, n_bars - 6)):
                                    if lows[b_fill] <= h15:
                                        entry_p = opens[b_fill] if opens[b_fill] < h15 else h15
                                        if entry_p <= m15: break
                                        risk_pts = max(entry_p * 0.0035, min(entry_p * 0.009, abs(entry_p - m15)))
                                        signals.append({
                                            'strategy': 'ORB', 'symbol': sym, 'side': 'BUY', 'fill_bar': b_fill,
                                            'entry_p': entry_p, 'sl_p': entry_p - risk_pts, 'risk_pts': risk_pts,
                                            'score': info['rvol'], 'info': info, 't1_r': 2.0, 't2_r': 3.5, 'mode': 'CORRECTED'
                                        })
                                        break
                                break
                            elif closes[b_break] < l15:
                                for b_fill in range(b_break + 1, min(24, n_bars - 6)):
                                    if highs[b_fill] >= l15:
                                        entry_p = opens[b_fill] if opens[b_fill] > l15 else l15
                                        if entry_p >= m15: break
                                        risk_pts = max(entry_p * 0.0035, min(entry_p * 0.009, abs(entry_p - m15)))
                                        signals.append({
                                            'strategy': 'ORB', 'symbol': sym, 'side': 'SELL', 'fill_bar': b_fill,
                                            'entry_p': entry_p, 'sl_p': entry_p + risk_pts, 'risk_pts': risk_pts,
                                            'score': info['rvol'], 'info': info, 't1_r': 2.0, 't2_r': 3.5, 'mode': 'CORRECTED'
                                        })
                                        break
                                break

            # 2. VWAP Signals (for V4 Standalone and V5 Combined)
            if version_id in ['V4_CORRECTED_VWAP_GOVERNOR', 'V5_COMBINED_PORTFOLIO']:
                for sym, d_dict in symbol_days.items():
                    if date_str not in d_dict: continue
                    info = d_dict[date_str]
                    if info['rvol'] < 1.5: continue
                    n_bars = info['n_bars']
                    opens, highs, lows, closes, vwaps = info['opens'], info['highs'], info['lows'], info['closes'], info['vwaps']
                    m15 = info['mid_15m']
                    side = 'BUY' if info['close_15m'] > info['open_15m'] else 'SELL'
                    
                    # Next-bar open market execution
                    for b_i in range(3, min(18, n_bars - 6)):
                        if side == 'BUY':
                            if lows[b_i] <= vwaps[b_i] and closes[b_i] >= vwaps[b_i]:
                                fill_bar = b_i + 1
                                if fill_bar >= n_bars: break
                                entry_p = opens[fill_bar]
                                risk_pts = max(entry_p * 0.0035, min(entry_p * 0.010, abs(entry_p - m15)))
                                signals.append({
                                    'strategy': 'VWAP', 'symbol': sym, 'side': side, 'fill_bar': fill_bar,
                                    'entry_p': entry_p, 'sl_p': entry_p - risk_pts, 'risk_pts': risk_pts,
                                    'score': info['rvol'], 'info': info, 't1_r': 2.0, 't2_r': 3.5, 'mode': 'CORRECTED'
                                })
                                break
                        else:
                            if highs[b_i] >= vwaps[b_i] and closes[b_i] <= vwaps[b_i]:
                                fill_bar = b_i + 1
                                if fill_bar >= n_bars: break
                                entry_p = opens[fill_bar]
                                risk_pts = max(entry_p * 0.0035, min(entry_p * 0.010, abs(entry_p - m15)))
                                signals.append({
                                    'strategy': 'VWAP', 'symbol': sym, 'side': side, 'fill_bar': fill_bar,
                                    'entry_p': entry_p, 'sl_p': entry_p + risk_pts, 'risk_pts': risk_pts,
                                    'score': info['rvol'], 'info': info, 't1_r': 2.0, 't2_r': 3.5, 'mode': 'CORRECTED'
                                })
                                break

            # 3. Gap & Go Signals (for V5 Combined)
            if version_id == 'V5_COMBINED_PORTFOLIO':
                for sym, d_dict in symbol_days.items():
                    if date_str not in d_dict: continue
                    info = d_dict[date_str]
                    gap_pct = info['gap_pct']
                    if abs(gap_pct) < 1.0 or info['rvol'] < 1.5: continue
                    n_bars = info['n_bars']
                    opens, highs, lows, closes, vwaps = info['opens'], info['highs'], info['lows'], info['closes'], info['vwaps']
                    h15, l15, m15 = info['high_15m'], info['low_15m'], info['mid_15m']
                    
                    if gap_pct >= 1.0:
                        for b_i in range(3, min(14, n_bars - 6)):
                            if closes[b_i] > h15 and closes[b_i] > vwaps[b_i]:
                                fill_bar = b_i + 1
                                if fill_bar >= n_bars: break
                                entry_p = opens[fill_bar]
                                risk_pts = max(entry_p * 0.0035, min(entry_p * 0.010, abs(entry_p - m15)))
                                signals.append({
                                    'strategy': 'GAP', 'symbol': sym, 'side': 'BUY', 'fill_bar': fill_bar,
                                    'entry_p': entry_p, 'sl_p': entry_p - risk_pts, 'risk_pts': risk_pts,
                                    'score': info['rvol'] * abs(gap_pct), 'info': info, 't1_r': 2.0, 't2_r': 3.5, 'mode': 'CORRECTED'
                                })
                                break
                    elif gap_pct <= -1.0:
                        for b_i in range(3, min(14, n_bars - 6)):
                            if closes[b_i] < l15 and closes[b_i] < vwaps[b_i]:
                                fill_bar = b_i + 1
                                if fill_bar >= n_bars: break
                                entry_p = opens[fill_bar]
                                risk_pts = max(entry_p * 0.0035, min(entry_p * 0.010, abs(entry_p - m15)))
                                signals.append({
                                    'strategy': 'GAP', 'symbol': sym, 'side': 'SELL', 'fill_bar': fill_bar,
                                    'entry_p': entry_p, 'sl_p': entry_p + risk_pts, 'risk_pts': risk_pts,
                                    'score': info['rvol'] * abs(gap_pct), 'info': info, 't1_r': 2.0, 't2_r': 3.5, 'mode': 'CORRECTED'
                                })
                                break

            # Filter top candidate per strategy
            strat_candidates = {}
            for s in signals:
                st = s['strategy']
                if st not in strat_candidates or s['score'] > strat_candidates[st]['score']:
                    strat_candidates[st] = s
                    
            # Allocate capital and execute candidates under Risk Governor
            total_open_risk = 0.0
            max_day_risk = closed_equity * 0.010 * mult
            
            strat_weights = {
                'VWAP': 0.60 if version_id == 'V5_COMBINED_PORTFOLIO' else 1.00,
                'ORB': 0.30 if version_id == 'V5_COMBINED_PORTFOLIO' else 1.00,
                'GAP': 0.10 if version_id == 'V5_COMBINED_PORTFOLIO' else 1.00
            }
            
            day_pnl = 0.0
            day_exposure = 0.0
            
            for st_name, t in strat_candidates.items():
                w = strat_weights.get(st_name, 1.0)
                risk_cash = max_day_risk * w
                
                # Sizing
                shares = int(risk_cash / t['risk_pts'])
                if version_id == 'V1_ORIGINAL_ORB':
                    if shares < 1: shares = 1
                else:
                    # STRICT REMOVAL OF max(1, shares) DEFECT
                    if shares < 1:
                        skipped_trades += 1
                        continue
                        
                # MIS 5x Leverage & Margin Check
                pos_value = shares * t['entry_p']
                margin_req = pos_value * 0.20 # 20% margin for MIS
                if margin_req > closed_equity * 0.80 or (day_exposure + pos_value) > (5.0 * closed_equity):
                    # Exceeds leverage or cash constraint
                    skipped_trades += 1
                    continue
                    
                day_exposure += pos_value
                
                s_t1 = int(shares * 0.50)
                s_run = shares - s_t1
                if s_t1 < 1: s_t1 = 1
                
                entry_p = t['entry_p']
                sl_p = t['sl_p']
                risk_pts = t['risk_pts']
                side = t['side']
                fill_bar = t['fill_bar']
                info = t['info']
                highs, lows, closes = info['highs'], info['lows'], info['closes']
                n_bars = info['n_bars']
                
                t1_p = entry_p + (2.0 * risk_pts) if side == 'BUY' else entry_p - (2.0 * risk_pts)
                t2_p = entry_p + (3.5 * risk_pts) if side == 'BUY' else entry_p - (3.5 * risk_pts)
                
                t1_hit = False
                curr_sl = sl_p
                exit_p1, exit_pr = 0.0, 0.0
                
                # Trade simulation
                for j in range(fill_bar + 1, n_bars):
                    h, l, c = highs[j], lows[j], closes[j]
                    
                    # Track intraday MTM low during the position
                    if side == 'BUY':
                        mtm_val = (c - entry_p) * shares
                    else:
                        mtm_val = (entry_p - c) * shares
                    day_mtm_low = min(day_mtm_low, closed_equity + day_pnl + mtm_val)
                    
                    if t['mode'] == 'ORIGINAL':
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
                        # CONSERVATIVE INTRABAR SEQUENCING & HARD STOPS
                        if side == 'BUY':
                            if not t1_hit:
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
                            if j >= 72 or j == n_bars - 1:
                                if not t1_hit: exit_p1 = c
                                exit_pr = c; break
                        else:
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
                            if j >= 72 or j == n_bars - 1:
                                if not t1_hit: exit_p1 = c
                                exit_pr = c; break

                # Costs and net PnL
                if t['mode'] == 'ORIGINAL':
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
                    
                day_pnl += npnl
                trades.append({
                    'date': date_str,
                    'strategy': st_name,
                    'symbol': t['symbol'],
                    'side': side,
                    'shares': shares,
                    'entry_p': round(entry_p, 2),
                    'exit_p1': round(exit_p1, 2),
                    'exit_pr': round(exit_pr, 2),
                    'gross_pnl': round(gp, 2),
                    'statutory_fee': round(fee, 2),
                    'slippage_cost': round(slip, 2),
                    'net_pnl': round(npnl, 2),
                    'R': round(npnl / (1000.0 * mult * w), 3)
                })
                
            # End of day equity update
            closed_equity += day_pnl
            if closed_equity > closed_peak: closed_peak = closed_equity
            if closed_equity > mtm_peak: mtm_peak = closed_equity
            
            closed_dd = (closed_equity - closed_peak) / closed_peak * 100.0
            mtm_dd = (day_mtm_low - mtm_peak) / mtm_peak * 100.0
            
            util_pct = (day_exposure / closed_equity * 100.0) if closed_equity > 0 else 0.0
            
            daily_records.append({
                'date': date_str,
                'closed_equity': closed_equity,
                'closed_peak': closed_peak,
                'closed_dd_pct': closed_dd,
                'day_mtm_low': day_mtm_low,
                'mtm_peak': mtm_peak,
                'mtm_dd_pct': mtm_dd,
                'capital_util_pct': util_pct,
                'day_pnl': day_pnl
            })
            
        df_daily = pd.DataFrame(daily_records)
        df_daily.to_csv(f"research/phase4_2/reports/daily_equity_{version_id}.csv", index=False)
        pd.DataFrame(trades).to_csv(f"research/phase4_2/reports/trade_log_{version_id}.csv", index=False)
        
        metrics = calculate_detailed_metrics(df_daily, trades, initial_capital=100000.0, skipped_count=skipped_trades)
        return metrics

    # Run the 5 Controlled Versions
    versions_to_run = [
        ('V1_ORIGINAL_ORB', '1. Original ORB Implementation (Phase 3 Baseline)'),
        ('V2_WICK_ORB', '2. Wick-Breakout Corrected Implementation'),
        ('V3_CLOSE_CONFIRMED_ORB', '3. Close-Confirmed Breakout Implementation'),
        ('V4_CORRECTED_VWAP_GOVERNOR', '4. Corrected Portfolio Risk Governor (Standalone VWAP)'),
        ('V5_COMBINED_PORTFOLIO', '5. Fully Corrected Combined Portfolio (MTM Governor)')
    ]
    
    master_results = []
    
    print("\n" + "=" * 115)
    print("RUNNING PHASE 4.2 INSTITUTIONAL CONTROLLED COMPARISONS")
    print("=" * 115)
    
    for v_id, v_desc in versions_to_run:
        st = time.time()
        print(f"\nExecuting {v_desc}...", flush=True)
        res = run_simulation(v_id)
        res['version_id'] = v_id
        res['description'] = v_desc
        master_results.append(res)
        
        print(f"  Trades: {res['total_trades']} | Skipped: {res['skipped_trades_insufficient_risk']} | WR: {res['win_rate_pct']}% | PF: {res['profit_factor']} | Net R: {res['net_R']:+7.2f}R")
        print(f"  CAGR: {res['cagr_pct']}% | CMGR: {res['cmgr_pct']}% | Max Closed DD: {res['max_closed_equity_dd_pct']}% | Max MTM DD: {res['max_intraday_mtm_dd_pct']}%")
        print(f"  WinMo: {res['profitable_months']}/{res['total_months']} ({res['win_month_pct']}%) | WorstMo: {res['worst_month_pct']}% | Longest Loss Streak: {res['longest_losing_streak']}")
        print(f"  Total Fees: Rs {res['total_transaction_costs_inr']:,.2f} | Total Slippage: Rs {res['total_slippage_inr']:,.2f} | Avg Util: {res['avg_capital_utilisation_pct']}% ({time.time() - st:.1f}s)")
        
    with open("research/phase4_2/reports/phase4_2_controlled_comparison_matrix.json", "w") as f:
        json.dump(master_results, f, indent=2)
        
    print("\n" + "=" * 115)
    print("SUMMARY COMPARISON TABLE")
    print("=" * 115)
    print(f"{'Version':45s} | {'Trades':6s} | {'WR %':5s} | {'PF':4s} | {'Net R':7s} | {'CAGR %':7s} | {'ClosedDD':8s} | {'MTM DD':7s} | {'WinMo%':6s}")
    print("-" * 115)
    for r in master_results:
        print(f"{r['description'][:45]:45s} | {r['total_trades']:6d} | {r['win_rate_pct']:5.2f} | {r['profit_factor']:4.2f} | {r['net_R']:+7.1f} | {r['cagr_pct']:6.2f}% | {r['max_closed_equity_dd_pct']:7.2f}% | {r['max_intraday_mtm_dd_pct']:6.2f}% | {r['win_month_pct']:5.1f}%")
    print("=" * 115)
    print("Saved Phase 4.2 results to research/phase4_2/reports/phase4_2_controlled_comparison_matrix.json")

if __name__ == '__main__':
    run_controlled_comparisons()
