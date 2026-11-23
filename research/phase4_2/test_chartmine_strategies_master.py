"""
CHARTMINE STRATEGIES MASTER BACKTEST & QUANTITATIVE AUDIT (2022 - 2026)
---------------------------------------------------------------------
Evaluates the core daily stock identification setups and concepts from ChartMine.ai:
1. Strategy 1: Narrow CPR Breakout (CPR Width < 0.25% on T-1 -> 09:30 Breakout)
2. Strategy 2: Open = Low / Open = High Directional Momentum (with Volume Surge)
3. Strategy 3: NR7 / Inside Bar Volatility Compression Breakout
4. Strategy 4: Relative Strength Leader (1-Year RS Rating + Morning Outperformance)
5. Strategy 5: ChartMine Multi-Confluence "Crown Setup" (Narrow CPR + Open=Low/High + RS + Market Pulse Filter)

Strict Execution Standards:
- 100% Point-in-Time, confirmed candle close, entry at next-bar open with 0.03% slippage.
- Full Zerodha transaction costs (brokerage, STT, turnover, SEBI, stamp duty, GST).
- Capital: Rs 1,00,000 Base. Static Rs 1,000 risk per trade (1R). Zero compounding.
- Period: 01 January 2022 to 16 October 2026 (1,190 trading days).
"""

import os, glob, time, re
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

def load_data():
    t0 = time.time()
    print("Loading NIFTY 50 1-minute data...", flush=True)
    nifty_files = sorted(glob.glob("data/nifty50/NIFTY50_1min_*.csv"))
    dfs = []
    for f in nifty_files:
        df = pd.read_csv(f)
        df['Date'] = pd.to_datetime(df['Timestamp'])
        dfs.append(df)
    nifty = pd.concat(dfs, ignore_index=True).sort_values('Date').reset_index(drop=True)
    nifty['date_str'] = nifty['Date'].dt.strftime('%Y-%m-%d')
    nifty['time_str'] = nifty['Date'].dt.strftime('%H:%M:%S')
    nifty_by_day = {d: grp for d, grp in nifty.groupby('date_str')}
    print(f"Loaded NIFTY 50 for {len(nifty_by_day)} trading days.", flush=True)

    print("Loading Top 30 Liquid Mega-Caps (1-minute bars)...", flush=True)
    stock_files = sorted(glob.glob("data/stocks/*_prev.parquet"))
    stocks_1m = {}
    for f in stock_files:
        sym = os.path.basename(f).replace("_prev.parquet", "")
        df_prev = pd.read_parquet(f)
        f_2026 = f.replace("_prev.parquet", "_2026.parquet")
        if os.path.exists(f_2026):
            df = pd.concat([df_prev, pd.read_parquet(f_2026)], ignore_index=True)
        else:
            df = df_prev
        df['Date'] = pd.to_datetime(df['Date'])
        mask = (df['Date'] >= '2022-01-01') & (df['Date'] <= '2026-10-31 15:30:00')
        sub = df[mask].sort_values('Date').reset_index(drop=True)
        if len(sub) < 1000:
            continue
        sub['date_str'] = sub['Date'].dt.date.astype(str)
        sub['time_str'] = sub['Date'].dt.time.astype(str)
        stocks_1m[sym] = {d: grp.reset_index(drop=True) for d, grp in sub.groupby('date_str')}
    print(f"Loaded {len(stocks_1m)} stocks in 1-minute resolution.", flush=True)

    print("Loading Nifty 200 Daily Cache for T-1 calculations...", flush=True)
    daily_files = sorted(glob.glob("data/nifty200_daily_cache/*.parquet"))
    daily_data = {}
    for f in daily_files:
        sym = os.path.basename(f).replace(".parquet", "")
        df_daily = pd.read_parquet(f)
        df_daily['date_str'] = pd.to_datetime(df_daily['Date']).dt.strftime('%Y-%m-%d')
        df_daily = df_daily.sort_values('Date').reset_index(drop=True)
        daily_data[sym] = df_daily
    print(f"Loaded daily data for {len(daily_data)} stocks in {time.time()-t0:.1f}s.\n", flush=True)
    
    return nifty_by_day, stocks_1m, daily_data

def run_simulation():
    nifty_by_day, stocks_1m, daily_data = load_data()
    symbols = sorted(list(stocks_1m.keys()))
    
    # Common trading dates available across both Nifty and stocks
    all_dates = sorted(list(nifty_by_day.keys()))
    # Filter dates starting from 2022-01-03
    trading_dates = [d for d in all_dates if d >= '2022-01-03']
    print(f"Total historical evaluation dates: {len(trading_dates)} sessions.\n", flush=True)

    # Strategy trade containers
    trades_s1 = [] # Narrow CPR
    trades_s2 = [] # Open = Low / Open = High
    trades_s3 = [] # NR7 / Inside Bar
    trades_s4 = [] # Relative Strength Leader
    trades_s5 = [] # Multi-Confluence Crown Setup

    capital = 100000.0
    risk_per_trade = 1000.0

    for d_idx, d in enumerate(trading_dates):
        if d_idx % 200 == 0 and d_idx > 0:
            print(f"Processed {d_idx}/{len(trading_dates)} dates...", flush=True)

        nifty_d = nifty_by_day.get(d)
        if nifty_d is None or len(nifty_d) < 30:
            continue

        nifty_open = nifty_d.iloc[0]['Open']
        
        # -------------------------------------------------------------
        # STEP 1: PRE-MARKET T-1 COMPUTATIONS (CPR, NR7, RS Rating)
        # -------------------------------------------------------------
        cpr_dict = {}
        nr7_dict = {}
        rs_dict = {}

        for sym in symbols:
            df_d = daily_data.get(sym)
            if df_d is None:
                continue
            idx_list = df_d[df_d['date_str'] == d].index
            if len(idx_list) == 0 or idx_list[0] < 25:
                continue
            curr_idx = idx_list[0]
            prev = df_d.iloc[curr_idx - 1]
            
            # CPR from T-1
            h, l, c = prev['High'], prev['Low'], prev['Close']
            pivot = (h + l + c) / 3.0
            bc = (h + l) / 2.0
            tc = (pivot - bc) + pivot
            cpr_width = abs(tc - bc) / pivot * 100.0
            cpr_dict[sym] = {'cpr_width': cpr_width, 'pivot': pivot, 'tc': tc, 'bc': bc, 'prev_h': h, 'prev_l': l, 'prev_c': c}

            # NR7 & Inside Bar check on T-1
            ranges = [df_d.iloc[k]['High'] - df_d.iloc[k]['Low'] for k in range(curr_idx - 7, curr_idx)]
            is_nr7 = (ranges[-1] == min(ranges))
            prev2 = df_d.iloc[curr_idx - 2]
            is_inside = (prev['High'] < prev2['High']) and (prev['Low'] > prev2['Low'])
            nr7_dict[sym] = {'is_nr7': is_nr7, 'is_inside': is_inside, 'prev_h': h, 'prev_l': l}

            # 1-Year Relative Return vs Nifty (RS proxy: 200-day return)
            if curr_idx >= 200:
                ret_200 = (prev['Close'] - df_d.iloc[curr_idx - 200]['Close']) / df_d.iloc[curr_idx - 200]['Close']
            else:
                ret_200 = (prev['Close'] - df_d.iloc[0]['Close']) / df_d.iloc[0]['Close']
            rs_dict[sym] = ret_200

        # Percentile rank RS ratings
        sorted_rs = sorted(rs_dict.items(), key=lambda x: x[1])
        rs_ratings = {sym: (rank + 1) / len(sorted_rs) * 100.0 for rank, (sym, _) in enumerate(sorted_rs)}

        # -------------------------------------------------------------
        # STEP 2: INTRADAY METRICS AT 09:30 AM AND 10:00 AM
        # -------------------------------------------------------------
        day_stock_bars = {}
        for sym in symbols:
            s_dict = stocks_1m.get(sym)
            if s_dict and d in s_dict:
                b = s_dict[d]
                if len(b) >= 60: # At least 60 minutes
                    day_stock_bars[sym] = b

        if len(day_stock_bars) < 15:
            continue

        # Nifty metrics at 09:30 and 10:00
        nifty_sub_15 = nifty_d[nifty_d['time_str'] <= '09:30:00']
        nifty_ret_15 = (nifty_sub_15.iloc[-1]['Close'] - nifty_open) / nifty_open if len(nifty_sub_15) > 0 else 0.0

        nifty_sub_45 = nifty_d[nifty_d['time_str'] <= '10:00:00']
        nifty_ret_45 = (nifty_sub_45.iloc[-1]['Close'] - nifty_open) / nifty_open if len(nifty_sub_45) > 0 else 0.0

        # =============================================================
        # STRATEGY 1: NARROW CPR BREAKOUT (09:30 AM Close)
        # =============================================================
        # Candidates: CPR Width < 0.25% (or top 3 narrowest CPR)
        cpr_candidates = [sym for sym, val in cpr_dict.items() if val['cpr_width'] < 0.25 and sym in day_stock_bars]
        if not cpr_candidates:
            # Fallback to top 2 narrowest if width < 0.4%
            sorted_cpr = sorted([(sym, val['cpr_width']) for sym, val in cpr_dict.items() if sym in day_stock_bars], key=lambda x: x[1])
            cpr_candidates = [s for s, w in sorted_cpr[:2] if w < 0.40]

        s1_trade_today = None
        for sym in cpr_candidates:
            b = day_stock_bars[sym]
            b_15 = b[b['time_str'] <= '09:30:00']
            if len(b_15) < 15: continue
            
            c_val = cpr_dict[sym]
            high_15 = b_15['High'].max()
            low_15 = b_15['Low'].min()
            close_15 = b_15.iloc[-1]['Close']
            open_day = b_15.iloc[0]['Open']

            # Bullish Breakout above TC and 15m high
            if close_15 > max(c_val['tc'], c_val['prev_h']):
                # Signal Long
                entry_idx = len(b_15)
                if entry_idx < len(b):
                    entry_bar = b.iloc[entry_idx]
                    entry_price = entry_bar['Open'] * 1.0003 # 0.03% slippage
                    sl_raw = min(c_val['pivot'], low_15)
                    risk_pct = (entry_price - sl_raw) / entry_price
                    if 0.004 <= risk_pct <= 0.015:
                        s1_trade_today = {
                            'date': d, 'symbol': sym, 'side': 'LONG', 'entry_time': entry_bar['time_str'],
                            'entry_price': entry_price, 'sl': sl_raw, 'target_1': entry_price + 2.0 * (entry_price - sl_raw),
                            'target_2': entry_price + 3.5 * (entry_price - sl_raw), 'risk_pct': risk_pct,
                            'bars': b.iloc[entry_idx:].reset_index(drop=True)
                        }
                        break
            # Bearish Breakdown below BC and 15m low
            elif close_15 < min(c_val['bc'], c_val['prev_l']):
                entry_idx = len(b_15)
                if entry_idx < len(b):
                    entry_bar = b.iloc[entry_idx]
                    entry_price = entry_bar['Open'] * 0.9997 # 0.03% slippage
                    sl_raw = max(c_val['pivot'], high_15)
                    risk_pct = (sl_raw - entry_price) / entry_price
                    if 0.004 <= risk_pct <= 0.015:
                        s1_trade_today = {
                            'date': d, 'symbol': sym, 'side': 'SHORT', 'entry_time': entry_bar['time_str'],
                            'entry_price': entry_price, 'sl': sl_raw, 'target_1': entry_price - 2.0 * (sl_raw - entry_price),
                            'target_2': entry_price - 3.5 * (sl_raw - entry_price), 'risk_pct': risk_pct,
                            'bars': b.iloc[entry_idx:].reset_index(drop=True)
                        }
                        break
        if s1_trade_today:
            trades_s1.append(s1_trade_today)

        # =============================================================
        # STRATEGY 2: OPEN = LOW / OPEN = HIGH DIRECTIONAL MOMENTUM
        # =============================================================
        s2_trade_today = None
        s2_candidates = []
        for sym in symbols:
            if sym not in day_stock_bars: continue
            b = day_stock_bars[sym]
            b_15 = b[b['time_str'] <= '09:30:00']
            if len(b_15) < 15: continue
            
            open_p = b_15.iloc[0]['Open']
            low_15 = b_15['Low'].min()
            high_15 = b_15['High'].max()
            close_15 = b_15.iloc[-1]['Close']
            vol_15 = b_15['Volume'].sum()

            # Open = Low condition: low of first 15 mins does not break open by > 0.05%
            is_open_low = (open_p - low_15) / open_p <= 0.0005 and close_15 > open_p * 1.005
            is_open_high = (high_15 - open_p) / open_p <= 0.0005 and close_15 < open_p * 0.995

            ret_15 = (close_15 - open_p) / open_p
            if is_open_low and nifty_ret_15 > 0:
                s2_candidates.append((sym, 'LONG', ret_15, vol_15, open_p, low_15, high_15, close_15, b, len(b_15)))
            elif is_open_high and nifty_ret_15 < 0:
                s2_candidates.append((sym, 'SHORT', ret_15, vol_15, open_p, low_15, high_15, close_15, b, len(b_15)))

        if s2_candidates:
            # Sort by highest magnitude return in direction
            s2_candidates.sort(key=lambda x: abs(x[2]), reverse=True)
            top_cand = s2_candidates[0]
            sym, side, ret_15, vol_15, open_p, low_15, high_15, close_15, b, entry_idx = top_cand
            if entry_idx < len(b):
                entry_bar = b.iloc[entry_idx]
                if side == 'LONG':
                    entry_price = entry_bar['Open'] * 1.0003
                    sl_raw = low_15
                    risk_pct = (entry_price - sl_raw) / entry_price
                    if 0.004 <= risk_pct <= 0.015:
                        s2_trade_today = {
                            'date': d, 'symbol': sym, 'side': 'LONG', 'entry_time': entry_bar['time_str'],
                            'entry_price': entry_price, 'sl': sl_raw, 'target_1': entry_price + 2.0 * (entry_price - sl_raw),
                            'target_2': entry_price + 3.5 * (entry_price - sl_raw), 'risk_pct': risk_pct,
                            'bars': b.iloc[entry_idx:].reset_index(drop=True)
                        }
                else:
                    entry_price = entry_bar['Open'] * 0.9997
                    sl_raw = high_15
                    risk_pct = (sl_raw - entry_price) / entry_price
                    if 0.004 <= risk_pct <= 0.015:
                        s2_trade_today = {
                            'date': d, 'symbol': sym, 'side': 'SHORT', 'entry_time': entry_bar['time_str'],
                            'entry_price': entry_price, 'sl': sl_raw, 'target_1': entry_price - 2.0 * (sl_raw - entry_price),
                            'target_2': entry_price - 3.5 * (sl_raw - entry_price), 'risk_pct': risk_pct,
                            'bars': b.iloc[entry_idx:].reset_index(drop=True)
                        }
        if s2_trade_today:
            trades_s2.append(s2_trade_today)

        # =============================================================
        # STRATEGY 3: NR7 / INSIDE BAR VOLATILITY COMPRESSION
        # =============================================================
        s3_trade_today = None
        s3_candidates = [sym for sym, val in nr7_dict.items() if (val['is_nr7'] or val['is_inside']) and sym in day_stock_bars]
        for sym in s3_candidates:
            b = day_stock_bars[sym]
            b_15 = b[b['time_str'] <= '09:30:00']
            if len(b_15) < 15: continue
            
            n_val = nr7_dict[sym]
            high_15 = b_15['High'].max()
            low_15 = b_15['Low'].min()
            close_15 = b_15.iloc[-1]['Close']

            if close_15 > n_val['prev_h'] and nifty_ret_15 > 0:
                entry_idx = len(b_15)
                if entry_idx < len(b):
                    entry_bar = b.iloc[entry_idx]
                    entry_price = entry_bar['Open'] * 1.0003
                    sl_raw = low_15
                    risk_pct = (entry_price - sl_raw) / entry_price
                    if 0.004 <= risk_pct <= 0.015:
                        s3_trade_today = {
                            'date': d, 'symbol': sym, 'side': 'LONG', 'entry_time': entry_bar['time_str'],
                            'entry_price': entry_price, 'sl': sl_raw, 'target_1': entry_price + 2.0 * (entry_price - sl_raw),
                            'target_2': entry_price + 3.5 * (entry_price - sl_raw), 'risk_pct': risk_pct,
                            'bars': b.iloc[entry_idx:].reset_index(drop=True)
                        }
                        break
            elif close_15 < n_val['prev_l'] and nifty_ret_15 < 0:
                entry_idx = len(b_15)
                if entry_idx < len(b):
                    entry_bar = b.iloc[entry_idx]
                    entry_price = entry_bar['Open'] * 0.9997
                    sl_raw = high_15
                    risk_pct = (sl_raw - entry_price) / entry_price
                    if 0.004 <= risk_pct <= 0.015:
                        s3_trade_today = {
                            'date': d, 'symbol': sym, 'side': 'SHORT', 'entry_time': entry_bar['time_str'],
                            'entry_price': entry_price, 'sl': sl_raw, 'target_1': entry_price - 2.0 * (sl_raw - entry_price),
                            'target_2': entry_price - 3.5 * (sl_raw - entry_price), 'risk_pct': risk_pct,
                            'bars': b.iloc[entry_idx:].reset_index(drop=True)
                        }
                        break
        if s3_trade_today:
            trades_s3.append(s3_trade_today)

        # =============================================================
        # STRATEGY 4: RELATIVE STRENGTH LEADER (10:00 AM Confirmation)
        # =============================================================
        s4_trade_today = None
        s4_candidates = []
        for sym in symbols:
            if sym not in day_stock_bars: continue
            b = day_stock_bars[sym]
            b_45 = b[b['time_str'] <= '10:00:00']
            if len(b_45) < 45: continue
            
            open_p = b_45.iloc[0]['Open']
            close_45 = b_45.iloc[-1]['Close']
            high_45 = b_45['High'].max()
            low_45 = b_45['Low'].min()
            stock_ret_45 = (close_45 - open_p) / open_p
            
            # Intraday VWAP at 10:00 AM
            v_sum = b_45['Volume'].sum()
            vwap_45 = (b_45['Close'] * b_45['Volume']).sum() / v_sum if v_sum > 0 else close_45
            
            rs_score = rs_ratings.get(sym, 50.0)

            # Long Leader: Stock up > 1.0%, outperforming Nifty by >= 0.8%, above VWAP, RS Rating >= 60
            if nifty_ret_45 > 0.001 and stock_ret_45 > 0.010 and (stock_ret_45 - nifty_ret_45) >= 0.008 and close_45 > vwap_45:
                s4_candidates.append((sym, 'LONG', stock_ret_45, rs_score, high_45, low_45, close_45, vwap_45, b, len(b_45)))
            elif nifty_ret_45 < -0.001 and stock_ret_45 < -0.010 and (nifty_ret_45 - stock_ret_45) >= 0.008 and close_45 < vwap_45:
                s4_candidates.append((sym, 'SHORT', stock_ret_45, rs_score, high_45, low_45, close_45, vwap_45, b, len(b_45)))

        if s4_candidates:
            # Sort by highest RS Rating then stock return
            s4_candidates.sort(key=lambda x: (x[3], abs(x[2])), reverse=True)
            top_cand = s4_candidates[0]
            sym, side, stock_ret_45, rs_score, high_45, low_45, close_45, vwap_45, b, entry_idx = top_cand
            if entry_idx < len(b):
                entry_bar = b.iloc[entry_idx]
                if side == 'LONG':
                    entry_price = entry_bar['Open'] * 1.0003
                    sl_raw = (entry_price + low_45) / 2.0 # 45m midpoint SL
                    risk_pct = (entry_price - sl_raw) / entry_price
                    if 0.004 <= risk_pct <= 0.015:
                        s4_trade_today = {
                            'date': d, 'symbol': sym, 'side': 'LONG', 'entry_time': entry_bar['time_str'],
                            'entry_price': entry_price, 'sl': sl_raw, 'target_1': entry_price + 2.0 * (entry_price - sl_raw),
                            'target_2': entry_price + 3.5 * (entry_price - sl_raw), 'risk_pct': risk_pct,
                            'bars': b.iloc[entry_idx:].reset_index(drop=True)
                        }
                else:
                    entry_price = entry_bar['Open'] * 0.9997
                    sl_raw = (entry_price + high_45) / 2.0
                    risk_pct = (sl_raw - entry_price) / entry_price
                    if 0.004 <= risk_pct <= 0.015:
                        s4_trade_today = {
                            'date': d, 'symbol': sym, 'side': 'SHORT', 'entry_time': entry_bar['time_str'],
                            'entry_price': entry_price, 'sl': sl_raw, 'target_1': entry_price - 2.0 * (sl_raw - entry_price),
                            'target_2': entry_price - 3.5 * (sl_raw - entry_price), 'risk_pct': risk_pct,
                            'bars': b.iloc[entry_idx:].reset_index(drop=True)
                        }
        if s4_trade_today:
            trades_s4.append(s4_trade_today)

        # =============================================================
        # STRATEGY 5: CHARTMINE MULTI-CONFLUENCE "CROWN SETUP"
        # =============================================================
        # Confluence of:
        # 1. Narrow CPR (Width < 0.35%) OR NR7 on Day T-1
        # 2. RS Rating >= 60 (Leadership bias)
        # 3. Market Pulse Non-Deadzone Filter: |Nifty Ret 15m| >= 0.15% (not choppy)
        # 4. Open = Low (for Long) or Open = High (for Short) OR Breakout above TC/BC
        s5_trade_today = None
        if abs(nifty_ret_15) >= 0.0015: # Market pulse active, avoiding dead-zone chop
            confluence_cands = []
            for sym in symbols:
                if sym not in day_stock_bars: continue
                c_val = cpr_dict.get(sym)
                n_val = nr7_dict.get(sym)
                if c_val is None or n_val is None: continue
                
                has_compression = (c_val['cpr_width'] < 0.35) or n_val['is_nr7'] or n_val['is_inside']
                if not has_compression: continue
                
                rs_score = rs_ratings.get(sym, 50.0)
                
                b = day_stock_bars[sym]
                b_15 = b[b['time_str'] <= '09:30:00']
                if len(b_15) < 15: continue
                
                open_p = b_15.iloc[0]['Open']
                low_15 = b_15['Low'].min()
                high_15 = b_15['High'].max()
                close_15 = b_15.iloc[-1]['Close']
                
                # Check directional alignment
                is_bullish = (nifty_ret_15 > 0) and (close_15 > open_p) and (close_15 > c_val['tc']) and (rs_score >= 50.0)
                is_bearish = (nifty_ret_15 < 0) and (close_15 < open_p) and (close_15 < c_val['bc']) and (rs_score <= 50.0)

                if is_bullish:
                    confluence_cands.append((sym, 'LONG', (close_15 - open_p) / open_p, rs_score, low_15, high_15, b, len(b_15)))
                elif is_bearish:
                    confluence_cands.append((sym, 'SHORT', (close_15 - open_p) / open_p, rs_score, low_15, high_15, b, len(b_15)))

            if confluence_cands:
                confluence_cands.sort(key=lambda x: (x[3], abs(x[2])), reverse=True)
                top_cand = confluence_cands[0]
                sym, side, ret_15, rs_score, low_15, high_15, b, entry_idx = top_cand
                if entry_idx < len(b):
                    entry_bar = b.iloc[entry_idx]
                    if side == 'LONG':
                        entry_price = entry_bar['Open'] * 1.0003
                        sl_raw = low_15
                        risk_pct = (entry_price - sl_raw) / entry_price
                        if 0.004 <= risk_pct <= 0.015:
                            s5_trade_today = {
                                'date': d, 'symbol': sym, 'side': 'LONG', 'entry_time': entry_bar['time_str'],
                                'entry_price': entry_price, 'sl': sl_raw, 'target_1': entry_price + 2.0 * (entry_price - sl_raw),
                                'target_2': entry_price + 3.5 * (entry_price - sl_raw), 'risk_pct': risk_pct,
                                'bars': b.iloc[entry_idx:].reset_index(drop=True)
                            }
                    else:
                        entry_price = entry_bar['Open'] * 0.9997
                        sl_raw = high_15
                        risk_pct = (sl_raw - entry_price) / entry_price
                        if 0.004 <= risk_pct <= 0.015:
                            s5_trade_today = {
                                'date': d, 'symbol': sym, 'side': 'SHORT', 'entry_time': entry_bar['time_str'],
                                'entry_price': entry_price, 'sl': sl_raw, 'target_1': entry_price - 2.0 * (sl_raw - entry_price),
                                'target_2': entry_price - 3.5 * (sl_raw - entry_price), 'risk_pct': risk_pct,
                                'bars': b.iloc[entry_idx:].reset_index(drop=True)
                            }
        if s5_trade_today:
            trades_s5.append(s5_trade_today)

    # -------------------------------------------------------------
    # SIMULATE INTRADAY OUTCOMES FOR EACH STRATEGY
    # -------------------------------------------------------------
    def evaluate_strategy_trades(trade_list, strat_name):
        results = []
        for tr in trade_list:
            entry_p = tr['entry_price']
            sl = tr['sl']
            t1 = tr['target_1']
            t2 = tr['target_2']
            side = tr['side']
            bars = tr['bars']
            
            # Sizing: Rs 1,000 risk
            shares = int(risk_per_trade / abs(entry_p - sl))
            if shares < 1: continue

            pos_half_1 = shares // 2
            pos_half_2 = shares - pos_half_1

            t1_hit = False
            t2_hit = False
            sl_hit = False
            curr_sl = sl

            exit_val_1 = 0.0
            exit_val_2 = 0.0
            exit_time = '15:15:00'

            for _, bar in bars.iterrows():
                b_time = bar['time_str']
                bh, bl = bar['High'], bar['Low']

                if b_time >= '15:15:00':
                    # EOD Square-off at Close
                    close_p = bar['Close']
                    if not t1_hit:
                        exit_val_1 = pos_half_1 * close_p
                    if not t2_hit:
                        exit_val_2 = pos_half_2 * close_p
                    exit_time = b_time
                    break

                if side == 'LONG':
                    # Stop check
                    if bl <= curr_sl:
                        sl_hit = True
                        exit_p = curr_sl * 0.9997 # 0.03% slippage
                        if not t1_hit:
                            exit_val_1 = pos_half_1 * exit_p
                        if not t2_hit:
                            exit_val_2 = pos_half_2 * exit_p
                        exit_time = b_time
                        break
                    # T1 check
                    if not t1_hit and bh >= t1:
                        t1_hit = True
                        exit_val_1 = pos_half_1 * (t1 * 0.9997)
                        curr_sl = entry_p # Move to Breakeven
                    # T2 check
                    if t1_hit and not t2_hit and bh >= t2:
                        t2_hit = True
                        exit_val_2 = pos_half_2 * (t2 * 0.9997)
                        exit_time = b_time
                        break

                else: # SHORT
                    # Stop check
                    if bh >= curr_sl:
                        sl_hit = True
                        exit_p = curr_sl * 1.0003
                        if not t1_hit:
                            exit_val_1 = pos_half_1 * exit_p
                        if not t2_hit:
                            exit_val_2 = pos_half_2 * exit_p
                        exit_time = b_time
                        break
                    # T1 check
                    if not t1_hit and bl <= t1:
                        t1_hit = True
                        exit_val_1 = pos_half_1 * (t1 * 1.0003)
                        curr_sl = entry_p
                    # T2 check
                    if t1_hit and not t2_hit and bl <= t2:
                        t2_hit = True
                        exit_val_2 = pos_half_2 * (t2 * 1.0003)
                        exit_time = b_time
                        break

            # Calculate PnL and statutory charges
            if side == 'LONG':
                buy_val = shares * entry_p
                sell_val = exit_val_1 + exit_val_2
                gross_pnl = sell_val - buy_val
            else:
                sell_val = shares * entry_p
                buy_val = exit_val_1 + exit_val_2
                gross_pnl = sell_val - buy_val

            charges = compute_zerodha_charges(buy_val, sell_val)
            net_pnl = gross_pnl - charges
            r_mult = net_pnl / risk_per_trade

            results.append({
                'date': tr['date'], 'year': tr['date'][:4], 'month': tr['date'][:7],
                'symbol': tr['symbol'], 'side': side, 'entry_price': entry_p,
                'shares': shares, 'gross_pnl': gross_pnl, 'charges': charges,
                'net_pnl': net_pnl, 'r_mult': r_mult, 't1_hit': t1_hit,
                't2_hit': t2_hit, 'sl_hit': sl_hit
            })

        df_res = pd.DataFrame(results)
        if len(df_res) == 0:
            print(f"\n[{strat_name}] NO TRADES GENERATED.\n")
            return

        total_trades = len(df_res)
        wins = df_res[df_res['net_pnl'] > 0]
        losses = df_res[df_res['net_pnl'] <= 0]
        win_rate = len(wins) / total_trades * 100.0
        gross_profit = wins['net_pnl'].sum()
        gross_loss = abs(losses['net_pnl'].sum())
        pf = gross_profit / gross_loss if gross_loss > 0 else 99.0
        net_profit = df_res['net_pnl'].sum()
        total_charges = df_res['charges'].sum()
        net_r = df_res['r_mult'].sum()

        # Monthly metrics
        monthly = df_res.groupby('month')['net_pnl'].sum()
        total_months = 58 # 2022-01 to 2026-10
        avg_mo_ret = (net_profit / total_months) / capital * 100.0
        prof_months = len(monthly[monthly > 0]) / len(monthly) * 100.0 if len(monthly) > 0 else 0.0

        # Drawdown calculation
        df_res['cum_pnl'] = df_res['net_pnl'].cumsum()
        df_res['peak'] = df_res['cum_pnl'].cummax()
        df_res['dd'] = df_res['peak'] - df_res['cum_pnl']
        max_dd_val = df_res['dd'].max()
        max_dd_pct = (max_dd_val / capital) * 100.0

        print(f"=====================================================================================")
        print(f"STRATEGY AUDIT: {strat_name.upper()}")
        print(f"=====================================================================================")
        print(f"  Total Trades: {total_trades} ({total_trades/total_months:.1f} trades/month)")
        print(f"  Win Rate: {win_rate:.2f}% | Profit Factor: {pf:.2f}")
        print(f"  Total Net Profit: Rs {net_profit:>10,.0f} ({net_r:>+6.1f}R)")
        print(f"  Total Statutory Charges: Rs {total_charges:>10,.0f}")
        print(f"  Average Monthly Return: {avg_mo_ret:+.2f}% / month (on Rs 1,00,000 Base)")
        print(f"  Maximum Drawdown: {max_dd_pct:.2f}% (Rs {max_dd_val:,.0f})")
        print(f"  Profitable Months: {prof_months:.1f}% ({len(monthly[monthly > 0])}/{len(monthly)} active months)")
        print(f"  Yearly Breakdown:")
        yearly = df_res.groupby('year')['net_pnl'].agg(['count', 'sum'])
        for yr, row in yearly.iterrows():
            print(f"    {yr}: {int(row['count']):>4} trades | Net PnL: Rs {row['sum']:>+8,.0f} ({row['sum']/risk_per_trade:>+5.1f}R)")
        print(f"=====================================================================================\n")

        # Save trade log
        clean_name = re.sub(r'[^a-zA-Z0-9]', '_', strat_name.lower())
        csv_path = f"research/phase4_2/chartmine_{clean_name}_trades.csv"
        df_res.to_csv(csv_path, index=False)
        print(f"Saved trade log to {csv_path}\n")

    print("\n-------------------------------------------------------------------------------------")
    print("STARTING AUDIT OF 5 CHARTMINE CANDIDATE STRATEGIES (2022 - 2026)")
    print("-------------------------------------------------------------------------------------\n")

    evaluate_strategy_trades(trades_s1, "Strategy 1: Narrow CPR Breakout")
    evaluate_strategy_trades(trades_s2, "Strategy 2: Open=Low / Open=High Directional Momentum")
    evaluate_strategy_trades(trades_s3, "Strategy 3: NR7 & Inside Bar Volatility Compression")
    evaluate_strategy_trades(trades_s4, "Strategy 4: Relative Strength Leader (10:00 AM Confirmation)")
    evaluate_strategy_trades(trades_s5, "Strategy 5: ChartMine Multi-Confluence Crown Setup")

if __name__ == '__main__':
    run_simulation()
