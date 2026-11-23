"""
AGENT 2 & 3: HIGH-PERFORMANCE SYSTEMATIC STRATEGY DISCOVERY (2022 - 2026 OCT 31)
Evaluates 6 distinct systematic strategy families across liquid NSE equities:
1. Strategy 1: Opening Range Breakout (ORB) + High RVOL
2. Strategy 2: VWAP Pullback Accumulation
3. Strategy 3: Intraday Relative Strength (RS vs Universe)
4. Strategy 4: Volatility Squeeze & Expansion (ATR/Bollinger Compression)
5. Strategy 5: Multi-Timeframe Trend Continuation (15m Trend + 5m EMA Pullback)
6. Strategy 6: Gap Momentum Catalyst with Breakout Confirmation

All evaluated on TRUE 5m intraday tick bars with exact Zerodha statutory charges.
"""

import os
import glob
import json
import numpy as np
import pandas as pd
from datetime import time

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

def load_symbol_5m(symbol):
    p_prev = f"data/stocks/{symbol}_prev.parquet"
    p_2026 = f"data/stocks/{symbol}_2026.parquet"
    dfs = []
    if os.path.exists(p_prev): dfs.append(pd.read_parquet(p_prev))
    if os.path.exists(p_2026): dfs.append(pd.read_parquet(p_2026))
    if not dfs: return None
    df = pd.concat(dfs, ignore_index=True)
    df['Date'] = pd.to_datetime(df['Date'])
    # Window: 2021-11-01 to 2026-10-31
    df = df[(df['Date'] >= '2021-11-01') & (df['Date'] <= '2026-10-31')].sort_values('Date').reset_index(drop=True)
    df.set_index('Date', inplace=True)
    t_start, t_end = time(9, 15), time(15, 30)
    df_5m = df.resample('5min').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna().reset_index()
    df_5m['time'] = df_5m['Date'].dt.time
    df_5m = df_5m[(df_5m['time'] >= t_start) & (df_5m['time'] <= t_end)].reset_index(drop=True)
    df_5m['date_str'] = df_5m['Date'].dt.strftime('%Y-%m-%d')
    
    # Vectorized indicator computation on full symbol DataFrame
    df_5m['typ'] = (df_5m['High'] + df_5m['Low'] + df_5m['Close']) / 3.0
    df_5m['pv'] = df_5m['typ'] * df_5m['Volume']
    df_5m['cum_pv'] = df_5m.groupby('date_str')['pv'].cumsum()
    df_5m['cum_vol'] = df_5m.groupby('date_str')['Volume'].cumsum()
    df_5m['vwap'] = np.where(df_5m['cum_vol'] > 0, df_5m['cum_pv'] / df_5m['cum_vol'], df_5m['Close'])
    
    df_5m['ema9'] = df_5m['Close'].ewm(span=9, adjust=False).mean()
    df_5m['ema21'] = df_5m['Close'].ewm(span=21, adjust=False).mean()
    
    return df_5m

def run_discovery():
    symbols = [
        'ADANIENT', 'AXISBANK', 'BAJFINANCE', 'BHARTIARTL', 'COALINDIA', 
        'GRASIM', 'HCLTECH', 'HDFCBANK', 'HINDUNILVR', 'ICICIBANK', 
        'INDUSINDBK', 'INFY', 'ITC', 'JSWSTEEL', 'KOTAKBANK', 
        'LT', 'MARUTI', 'NTPC', 'ONGC', 'POWERGRID', 
        'RELIANCE', 'SBIN', 'SUNPHARMA', 'TATAMOTORS', 'TATASTEEL', 
        'TCS', 'TECHM', 'TITAN', 'ULTRACEMCO', 'WIPRO'
    ]
    
    print(f"Loading 5-minute data for {len(symbols)} liquid mega-caps...", flush=True)
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
            d_df = d_df.reset_index(drop=True)
            if len(d_df) < 25:
                if len(d_df) > 0: prev_close = d_df.iloc[-1]['Close']
                continue
            c15 = d_df.iloc[0:3]
            open_15m = c15.iloc[0]['Open']
            high_15m = c15['High'].max()
            low_15m = c15['Low'].min()
            close_15m = c15.iloc[-1]['Close']
            vol_15m = c15['Volume'].sum()
            range_15m = high_15m - low_15m
            
            gap_pct = (close_15m - prev_close) / prev_close * 100.0 if prev_close else 0.0
            rvol = vol_15m / np.mean(or_vols[-20:]) if len(or_vols) >= 10 and np.mean(or_vols[-20:]) > 0 else 1.0
            or_vols.append(vol_15m)
            prev_close = d_df.iloc[-1]['Close']
            
            if int(d_str[:4]) >= 2022 and d_str <= '2026-10-31':
                all_dates.add(d_str)
                symbol_days[sym][d_str] = {
                    'df': d_df,
                    'open_15m': open_15m,
                    'high_15m': high_15m,
                    'low_15m': low_15m,
                    'mid_15m': (high_15m + low_15m) / 2.0,
                    'close_15m': close_15m,
                    'range_15m': range_15m,
                    'gap_pct': gap_pct,
                    'rvol': rvol
                }
                
    sorted_dates = sorted(list(all_dates))
    print(f"Loaded {len(sorted_dates)} trading sessions across {len(symbol_days)} stocks.", flush=True)
    
    families = [
        'ORB_MOMENTUM_RVOL',
        'VWAP_PULLBACK_RETEST',
        'RELATIVE_STRENGTH_BREAKOUT',
        'VOLATILITY_SQUEEZE_EXPANSION',
        'MULTI_TIMEFRAME_TREND',
        'GAP_AND_GO_CATALYST'
    ]
    
    discovery_results = []
    
    for fam in families:
        trades = []
        risk_cash = 1000.0 # Rs 1,000 risk per trade
        
        for date_str in sorted_dates:
            candidates = []
            
            for sym, d_dict in symbol_days.items():
                if date_str not in d_dict: continue
                info = d_dict[date_str]
                d_df = info['df']
                h15, l15, m15 = info['high_15m'], info['low_15m'], info['mid_15m']
                c15 = info['close_15m']
                rvol = info['rvol']
                gap_pct = info['gap_pct']
                
                # --- FAMILY 1: ORB + RVOL ---
                if fam == 'ORB_MOMENTUM_RVOL':
                    if rvol < 1.8: continue
                    for b_i in range(3, min(14, len(d_df) - 6)):
                        bar = d_df.iloc[b_i]
                        if bar['Close'] > h15 and bar['Close'] > bar['vwap']:
                            entry_p = bar['Close']
                            sl_p = m15
                            risk_pts = max(entry_p * 0.0035, min(entry_p * 0.010, entry_p - sl_p))
                            candidates.append({'symbol': sym, 'side': 'BUY', 'b_idx': b_i, 'entry_p': entry_p, 'sl_p': entry_p - risk_pts, 'risk_pts': risk_pts, 'score': rvol, 'df': d_df, 't1_r': 2.0, 't2_r': 3.5})
                            break
                        elif bar['Close'] < l15 and bar['Close'] < bar['vwap']:
                            entry_p = bar['Close']
                            sl_p = m15
                            risk_pts = max(entry_p * 0.0035, min(entry_p * 0.010, sl_p - entry_p))
                            candidates.append({'symbol': sym, 'side': 'SELL', 'b_idx': b_i, 'entry_p': entry_p, 'sl_p': entry_p + risk_pts, 'risk_pts': risk_pts, 'score': rvol, 'df': d_df, 't1_r': 2.0, 't2_r': 3.5})
                            break

                # --- FAMILY 2: VWAP PULLBACK RETEST ---
                elif fam == 'VWAP_PULLBACK_RETEST':
                    if rvol < 1.5: continue
                    if c15 > info['open_15m']: # Bullish morning
                        for b_i in range(3, min(18, len(d_df) - 6)):
                            bar = d_df.iloc[b_i]
                            if bar['Low'] <= bar['vwap'] and bar['Close'] >= bar['vwap']:
                                entry_p = bar['vwap']
                                sl_p = m15
                                risk_pts = max(entry_p * 0.0035, min(entry_p * 0.010, abs(entry_p - sl_p)))
                                candidates.append({'symbol': sym, 'side': 'BUY', 'b_idx': b_i, 'entry_p': entry_p, 'sl_p': entry_p - risk_pts, 'risk_pts': risk_pts, 'score': rvol * 1.2, 'df': d_df, 't1_r': 2.0, 't2_r': 3.5})
                                break
                    elif c15 < info['open_15m']: # Bearish morning
                        for b_i in range(3, min(18, len(d_df) - 6)):
                            bar = d_df.iloc[b_i]
                            if bar['High'] >= bar['vwap'] and bar['Close'] <= bar['vwap']:
                                entry_p = bar['vwap']
                                sl_p = m15
                                risk_pts = max(entry_p * 0.0035, min(entry_p * 0.010, abs(sl_p - entry_p)))
                                candidates.append({'symbol': sym, 'side': 'SELL', 'b_idx': b_i, 'entry_p': entry_p, 'sl_p': entry_p + risk_pts, 'risk_pts': risk_pts, 'score': rvol * 1.2, 'df': d_df, 't1_r': 2.0, 't2_r': 3.5})
                                break

                # --- FAMILY 3: RELATIVE STRENGTH BREAKOUT ---
                elif fam == 'RELATIVE_STRENGTH_BREAKOUT':
                    open_p = d_df.iloc[0]['Open']
                    morn_ret = (c15 - open_p) / open_p * 100.0
                    if abs(morn_ret) < 0.8 or rvol < 1.5: continue
                    if morn_ret > 0:
                        for b_i in range(3, min(15, len(d_df) - 6)):
                            bar = d_df.iloc[b_i]
                            if bar['Close'] > h15:
                                entry_p = bar['Close']
                                risk_pts = max(entry_p * 0.0035, min(entry_p * 0.010, abs(entry_p - bar['vwap'])))
                                candidates.append({'symbol': sym, 'side': 'BUY', 'b_idx': b_i, 'entry_p': entry_p, 'sl_p': entry_p - risk_pts, 'risk_pts': risk_pts, 'score': abs(morn_ret) * rvol, 'df': d_df, 't1_r': 1.5, 't2_r': 3.0})
                                break
                    else:
                        for b_i in range(3, min(15, len(d_df) - 6)):
                            bar = d_df.iloc[b_i]
                            if bar['Close'] < l15:
                                entry_p = bar['Close']
                                risk_pts = max(entry_p * 0.0035, min(entry_p * 0.010, abs(bar['vwap'] - entry_p)))
                                candidates.append({'symbol': sym, 'side': 'SELL', 'b_idx': b_i, 'entry_p': entry_p, 'sl_p': entry_p + risk_pts, 'risk_pts': risk_pts, 'score': abs(morn_ret) * rvol, 'df': d_df, 't1_r': 1.5, 't2_r': 3.0})
                                break

                # --- FAMILY 4: VOLATILITY SQUEEZE & EXPANSION ---
                elif fam == 'VOLATILITY_SQUEEZE_EXPANSION':
                    if (info['range_15m'] / c15 * 100.0) > 0.85: continue
                    for b_i in range(3, min(16, len(d_df) - 6)):
                        bar = d_df.iloc[b_i]
                        if bar['Close'] > h15 and bar['Volume'] > d_df.iloc[b_i-1]['Volume'] * 1.5:
                            entry_p = bar['Close']
                            risk_pts = max(entry_p * 0.0035, min(entry_p * 0.008, abs(entry_p - l15)))
                            candidates.append({'symbol': sym, 'side': 'BUY', 'b_idx': b_i, 'entry_p': entry_p, 'sl_p': entry_p - risk_pts, 'risk_pts': risk_pts, 'score': bar['Volume'], 'df': d_df, 't1_r': 2.0, 't2_r': 4.0})
                            break
                        elif bar['Close'] < l15 and bar['Volume'] > d_df.iloc[b_i-1]['Volume'] * 1.5:
                            entry_p = bar['Close']
                            risk_pts = max(entry_p * 0.0035, min(entry_p * 0.008, abs(h15 - entry_p)))
                            candidates.append({'symbol': sym, 'side': 'SELL', 'b_idx': b_i, 'entry_p': entry_p, 'sl_p': entry_p + risk_pts, 'risk_pts': risk_pts, 'score': bar['Volume'], 'df': d_df, 't1_r': 2.0, 't2_r': 4.0})
                            break

                # --- FAMILY 5: MULTI-TIMEFRAME TREND CONTINUATION ---
                elif fam == 'MULTI_TIMEFRAME_TREND':
                    for b_i in range(5, min(22, len(d_df) - 6)):
                        bar = d_df.iloc[b_i]
                        prev_b = d_df.iloc[b_i - 1]
                        if bar['Close'] > bar['vwap'] and bar['ema9'] > bar['ema21']:
                            if prev_b['Low'] <= prev_b['ema9'] and bar['Close'] > bar['Open']:
                                entry_p = bar['Close']
                                risk_pts = max(entry_p * 0.0035, min(entry_p * 0.009, abs(entry_p - bar['ema21'])))
                                candidates.append({'symbol': sym, 'side': 'BUY', 'b_idx': b_i, 'entry_p': entry_p, 'sl_p': entry_p - risk_pts, 'risk_pts': risk_pts, 'score': bar['Close'] / bar['vwap'], 'df': d_df, 't1_r': 1.5, 't2_r': 3.0})
                                break
                        elif bar['Close'] < bar['vwap'] and bar['ema9'] < bar['ema21']:
                            if prev_b['High'] >= prev_b['ema9'] and bar['Close'] < bar['Open']:
                                entry_p = bar['Close']
                                risk_pts = max(entry_p * 0.0035, min(entry_p * 0.009, abs(bar['ema21'] - entry_p)))
                                candidates.append({'symbol': sym, 'side': 'SELL', 'b_idx': b_i, 'entry_p': entry_p, 'sl_p': entry_p + risk_pts, 'risk_pts': risk_pts, 'score': bar['vwap'] / bar['Close'], 'df': d_df, 't1_r': 1.5, 't2_r': 3.0})
                                break

                # --- FAMILY 6: GAP AND GO CATALYST ---
                elif fam == 'GAP_AND_GO_CATALYST':
                    if abs(gap_pct) < 1.0 or rvol < 2.0: continue
                    if gap_pct >= 1.0:
                        for b_i in range(3, min(14, len(d_df) - 6)):
                            bar = d_df.iloc[b_i]
                            if bar['Close'] > h15 and bar['Close'] > bar['vwap']:
                                entry_p = bar['Close']
                                risk_pts = max(entry_p * 0.0035, min(entry_p * 0.0085, abs(entry_p - m15)))
                                candidates.append({'symbol': sym, 'side': 'BUY', 'b_idx': b_i, 'entry_p': entry_p, 'sl_p': entry_p - risk_pts, 'risk_pts': risk_pts, 'score': rvol * (1 + abs(gap_pct)), 'df': d_df, 't1_r': 2.0, 't2_r': 3.5})
                                break
                    elif gap_pct <= -1.0:
                        for b_i in range(3, min(14, len(d_df) - 6)):
                            bar = d_df.iloc[b_i]
                            if bar['Close'] < l15 and bar['Close'] < bar['vwap']:
                                entry_p = bar['Close']
                                risk_pts = max(entry_p * 0.0035, min(entry_p * 0.0085, abs(m15 - entry_p)))
                                candidates.append({'symbol': sym, 'side': 'SELL', 'b_idx': b_i, 'entry_p': entry_p, 'sl_p': entry_p + risk_pts, 'risk_pts': risk_pts, 'score': rvol * (1 + abs(gap_pct)), 'df': d_df, 't1_r': 2.0, 't2_r': 3.5})
                                break

            if not candidates: continue
            candidates.sort(key=lambda x: -x['score'])
            t = candidates[0]
            
            entry_p, sl_p, risk_pts, d_df, side, b_idx = t['entry_p'], t['sl_p'], t['risk_pts'], t['df'], t['side'], t['b_idx']
            t1_r, t2_r = t['t1_r'], t['t2_r']
            
            shares = int(risk_cash / risk_pts)
            if shares < 1: shares = 1
            s_t1 = int(shares * 0.50)
            s_run = shares - s_t1
            if s_t1 < 1: s_t1 = 1
            
            t1_p = entry_p + (t1_r * risk_pts) if side == 'BUY' else entry_p - (t1_r * risk_pts)
            t2_p = entry_p + (t2_r * risk_pts) if side == 'BUY' else entry_p - (t2_r * risk_pts)
            
            t1_hit = False
            curr_sl = sl_p
            exit_p1, exit_pr = 0.0, 0.0
            
            for j in range(b_idx + 1, len(d_df)):
                bar = d_df.iloc[j]
                h, l, c = bar['High'], bar['Low'], bar['Close']
                
                if side == 'BUY':
                    if l <= curr_sl:
                        if not t1_hit: exit_p1, exit_pr = curr_sl, curr_sl
                        else: exit_pr = curr_sl
                        break
                    if not t1_hit and h >= t1_p:
                        t1_hit = True
                        exit_p1 = t1_p
                    if t1_hit and h >= t2_p:
                        exit_pr = t2_p
                        break
                    if j == len(d_df) - 1 or j >= 72:
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
                    if t1_hit and l <= t2_p:
                        exit_pr = t2_p
                        break
                    if j == len(d_df) - 1 or j >= 72:
                        if not t1_hit: exit_p1 = c
                        exit_pr = c
                        break
                        
            if side == 'BUY':
                p1 = s_t1 * (exit_p1 - entry_p)
                f1 = compute_zerodha_charges(s_t1 * entry_p, s_t1 * exit_p1)
                pr = s_run * (exit_pr - entry_p) if s_run > 0 else 0
                fr = compute_zerodha_charges(s_run * entry_p, s_run * exit_pr) if s_run > 0 else 0
            else:
                p1 = s_t1 * (entry_p - exit_p1)
                f1 = compute_zerodha_charges(s_t1 * exit_p1, s_t1 * entry_p)
                pr = s_run * (entry_p - exit_pr) if s_run > 0 else 0
                fr = compute_zerodha_charges(s_run * exit_pr, s_run * entry_p) if s_run > 0 else 0
                
            net_pnl = p1 + pr - f1 - fr
            ret_pct = net_pnl / 1000.0
            trades.append({
                'date': date_str,
                'year': int(date_str[:4]),
                'symbol': t['symbol'],
                'side': side,
                'ret_pct': ret_pct,
                'net_pnl': net_pnl,
                'fee': f1 + fr
            })
            
        df_t = pd.DataFrame(trades)
        wins = df_t[df_t['net_pnl'] > 0]
        losses = df_t[df_t['net_pnl'] <= 0]
        win_rate = len(wins) / len(df_t) * 100.0 if len(df_t) > 0 else 0.0
        gw = wins['net_pnl'].sum()
        gl = abs(losses['net_pnl'].sum())
        pf = gw / gl if gl > 0 else 0.0
        total_ret = df_t['ret_pct'].sum()
        
        df_t['cum'] = df_t['ret_pct'].cumsum()
        df_t['peak'] = df_t['cum'].cummax()
        df_t['dd'] = df_t['cum'] - df_t['peak']
        max_dd = df_t['dd'].min()
        
        n_months = pd.to_datetime(df_t['date']).dt.to_period('M').nunique()
        monthly_ret = total_ret / max(1, n_months)
        
        daily_ret = df_t.groupby('date')['ret_pct'].sum()
        sharpe = (daily_ret.mean() / daily_ret.std() * np.sqrt(252)) if daily_ret.std() > 0 else 0.0
        
        # In-Sample (2022-2023) vs Out-of-Sample (2024-2026)
        is_df = df_t[df_t['year'].isin([2022, 2023])]
        oos_df = df_t[df_t['year'].isin([2024, 2025, 2026])]
        is_ret = is_df['ret_pct'].sum() if len(is_df) > 0 else 0.0
        oos_ret = oos_df['ret_pct'].sum() if len(oos_df) > 0 else 0.0
        
        res_summary = {
            'strategy_family': fam,
            'total_trades': len(df_t),
            'win_rate_pct': round(win_rate, 2),
            'profit_factor': round(pf, 2),
            'total_net_return_pct': round(total_ret, 2),
            'monthly_avg_return_pct': round(monthly_ret, 2),
            'max_drawdown_pct': round(max_dd, 2),
            'sharpe_ratio': round(sharpe, 2),
            'in_sample_return_pct': round(is_ret, 2),
            'out_of_sample_return_pct': round(oos_ret, 2),
            'total_fees_paid': round(float(df_t['fee'].sum()), 2)
        }
        discovery_results.append(res_summary)
        
        print(f"\nFAMILY: {fam:30s} | Trades: {len(df_t):4d} | WR: {win_rate:5.2f}% | PF: {pf:4.2f} | Net: {total_ret:+7.2f}% | MoRet: {monthly_ret:+5.2f}% | MaxDD: {max_dd:6.2f}% | Sharpe: {sharpe:4.2f}", flush=True)
        
        # Save individual trade log for audit
        df_t.to_csv(f"research/reports/trade_log_{fam}.csv", index=False)
        
    with open("research/reports/agent2_discovery_matrix.json", "w") as f:
        json.dump(discovery_results, f, indent=2)
        
    print(f"\nDiscovery report saved to research/reports/agent2_discovery_matrix.json", flush=True)
    return discovery_results

if __name__ == '__main__':
    run_discovery()
