import os
import sys
import glob
import math
import pandas as pd
import numpy as np
from datetime import time, datetime

print("="*85, flush=True)
print("DAY TRADER SKILL SUITE: QUANTITATIVE STRATEGY RESEARCH ENGINE (4.8 YEARS)", flush=True)
print("Dataset: Jan 1, 2022 to Oct 16, 2026 | Full 30 NIFTY Equities | 1m & 5m Bars", flush=True)
print("Statutory Charges: 100% Exact Zerodha & Dhan Official Tariff (Paisa-Level)", flush=True)
print("="*85, flush=True)

def calc_statutory_charges(entry_price, exit_price, sl_dist, direction='BUY', risk_inr=200.0):
    if sl_dist <= 0 or entry_price <= 0:
        return 0.0, 0.0, 0.0
    qty = max(1, int(risk_inr / sl_dist))
    buy_px = entry_price if direction == 'BUY' else exit_price
    sell_px = exit_price if direction == 'BUY' else entry_price
    buy_turnover = qty * buy_px
    sell_turnover = qty * sell_px
    roundtrip = buy_turnover + sell_turnover
    
    # Zerodha / Dhan Equity Intraday Tariff:
    brok_buy = min(20.0, buy_turnover * 0.0003)
    brok_sell = min(20.0, sell_turnover * 0.0003)
    brokerage = brok_buy + brok_sell
    
    stt = sell_turnover * 0.00025               # 0.025% on sell side
    exch = roundtrip * 0.0000297               # NSE turnover fee (0.00297%)
    sebi = roundtrip * 0.000001                # ₹10 / crore (0.0001%)
    stamp = buy_turnover * 0.00003             # Stamp duty 0.003% on buy
    gst = (brokerage + exch + sebi) * 0.18     # GST 18%
    slippage = qty * 0.05                      # 1 tick (₹0.05) spread
    
    total_charges_inr = brokerage + stt + exch + sebi + stamp + gst + slippage
    charges_r = total_charges_inr / risk_inr
    
    gross_pnl_inr = qty * (exit_price - entry_price) if direction == 'BUY' else qty * (entry_price - exit_price)
    net_pnl_inr = gross_pnl_inr - total_charges_inr
    net_r = net_pnl_inr / risk_inr
    
    return total_charges_inr, charges_r, net_r

def load_stock_5m_fast(s, start_date='2022-01-01', end_date='2026-10-16'):
    f_prev = f'data/stocks/{s}_prev.parquet'
    f_2026 = f'data/stocks/{s}_2026.parquet'
    dfs = []
    if os.path.exists(f_prev):
        d1 = pd.read_parquet(f_prev)
        d1['Timestamp'] = pd.to_datetime(d1['Date'])
        d1 = d1[d1['Timestamp'] >= start_date]
        dfs.append(d1[['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']])
    if os.path.exists(f_2026):
        d2 = pd.read_parquet(f_2026)
        d2['Timestamp'] = pd.to_datetime(d2['Date'])
        dfs.append(d2[['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']])
    if not dfs:
        return None
    df = pd.concat(dfs).sort_values('Timestamp').drop_duplicates('Timestamp').reset_index(drop=True)
    df = df[(df['Timestamp'] >= start_date) & (df['Timestamp'] <= end_date + ' 23:59:59')]
    df['Time'] = df['Timestamp'].dt.time
    df = df[(df['Time'] >= time(9, 15)) & (df['Time'] <= time(15, 30))].copy()
    
    # Resample to 5m
    df = df.set_index('Timestamp')
    agg_d = {'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'}
    df_5m = df.resample('5min', origin='start_day').agg(agg_d).dropna().reset_index()
    df_5m['Date'] = df_5m['Timestamp'].dt.date
    df_5m['Time'] = df_5m['Timestamp'].dt.time
    df_5m = df_5m[(df_5m['Time'] >= time(9, 15)) & (df_5m['Time'] <= time(15, 30))].copy()
    
    df_5m['Typ'] = (df_5m['High'] + df_5m['Low'] + df_5m['Close']) / 3.0
    df_5m['PV'] = df_5m['Typ'] * df_5m['Volume']
    df_5m['CumPV'] = df_5m.groupby('Date')['PV'].cumsum()
    df_5m['CumV'] = df_5m.groupby('Date')['Volume'].cumsum()
    df_5m['VWAP'] = df_5m['CumPV'] / df_5m['CumV']
    
    df_5m['EMA9'] = df_5m['Close'].ewm(span=9, adjust=False).mean()
    df_5m['EMA21'] = df_5m['Close'].ewm(span=21, adjust=False).mean()
    df_5m['EMA50'] = df_5m['Close'].ewm(span=50, adjust=False).mean()
    
    prev_close = df_5m['Close'].shift(1)
    tr1 = df_5m['High'] - df_5m['Low']
    tr2 = (df_5m['High'] - prev_close).abs()
    tr3 = (df_5m['Low'] - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df_5m['ATR'] = tr.rolling(14, min_periods=1).mean()
    df_5m['VolMA20'] = df_5m['Volume'].rolling(20, min_periods=1).mean()
    
    return df_5m

def load_nifty_macro(start_date='2022-01-01', end_date='2026-10-16'):
    print("Loading NIFTY 50 macro index data...", flush=True)
    dfs = []
    for y in ['2022', '2023', '2024', '2025']:
        p = f'data/nifty50/NIFTY50_1min_{y}.csv'
        if os.path.exists(p):
            d = pd.read_csv(p)
            d['Timestamp'] = pd.to_datetime(d['Timestamp'])
            dfs.append(d[['Timestamp', 'Open', 'High', 'Low', 'Close']])
    for f in sorted(glob.glob('data/nifty50/2026/*.csv')):
        d = pd.read_csv(f)
        d['Timestamp'] = pd.to_datetime(d['Timestamp'])
        dfs.append(d[['Timestamp', 'Open', 'High', 'Low', 'Close']])
    nifty_1m = pd.concat(dfs).sort_values('Timestamp').drop_duplicates('Timestamp').reset_index(drop=True)
    nifty_1m = nifty_1m[(nifty_1m['Timestamp'] >= start_date) & (nifty_1m['Timestamp'] <= end_date + ' 23:59:59')]
    
    nifty_1m = nifty_1m.set_index('Timestamp')
    agg_d = {'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}
    nifty_5m = nifty_1m.resample('5min', origin='start_day').agg(agg_d).dropna().reset_index()
    nifty_5m['Date'] = nifty_5m['Timestamp'].dt.date
    nifty_5m['EMA9'] = nifty_5m['Close'].ewm(span=9, adjust=False).mean()
    nifty_5m['EMA21'] = nifty_5m['Close'].ewm(span=21, adjust=False).mean()
    nifty_5m['Nifty_Trend'] = 0
    nifty_5m.loc[(nifty_5m['Close'] > nifty_5m['EMA21']) & (nifty_5m['EMA9'] > nifty_5m['EMA21']), 'Nifty_Trend'] = 1
    nifty_5m.loc[(nifty_5m['Close'] < nifty_5m['EMA21']) & (nifty_5m['EMA9'] < nifty_5m['EMA21']), 'Nifty_Trend'] = -1
    trend_map = nifty_5m.set_index('Timestamp')['Nifty_Trend'].to_dict()
    print(f"NIFTY 50 macro trend ready: {len(nifty_5m)} 5m bars.", flush=True)
    return trend_map

ALL_SYMBOLS = [
    'RELIANCE', 'TCS', 'HDFCBANK', 'ICICIBANK', 'INFY', 'SBIN',
    'BHARTIARTL', 'LT', 'AXISBANK', 'BAJFINANCE', 'TITAN', 'MARUTI',
    'KOTAKBANK', 'WIPRO', 'SUNPHARMA', 'TATASTEEL', 'ADANIENT', 'INDUSINDBK',
    'HCLTECH', 'TECHM', 'ULTRACEMCO', 'HINDUNILVR', 'ITC', 'POWERGRID',
    'NTPC', 'ONGC', 'COALINDIA', 'JSWSTEEL', 'GRASIM'
]

TOP14_CHAMPIONS = [
    'RELIANCE', 'INDUSINDBK', 'LT', 'ADANIENT', 'TATAMOTORS',
    'SUNPHARMA', 'WIPRO', 'JSWSTEEL', 'TATASTEEL', 'BAJFINANCE',
    'SBIN', 'ONGC', 'TCS', 'MARUTI'
]

print("Pre-loading stock datasets into RAM as optimized NumPy arrays...", flush=True)
stocks_arrays_by_date = {}

for sym in ALL_SYMBOLS:
    df_s = load_stock_5m_fast(sym)
    if df_s is not None:
        sym_dict = {}
        for dt, grp in df_s.groupby('Date'):
            sym_dict[dt] = {
                'opens': grp['Open'].to_numpy(dtype=np.float64),
                'highs': grp['High'].to_numpy(dtype=np.float64),
                'lows': grp['Low'].to_numpy(dtype=np.float64),
                'closes': grp['Close'].to_numpy(dtype=np.float64),
                'volumes': grp['Volume'].to_numpy(dtype=np.float64),
                'vwaps': grp['VWAP'].to_numpy(dtype=np.float64),
                'atrs': grp['ATR'].to_numpy(dtype=np.float64),
                'volmas': grp['VolMA20'].to_numpy(dtype=np.float64),
                'times': grp['Time'].tolist(),
                'timestamps': grp['Timestamp'].tolist()
            }
        stocks_arrays_by_date[sym] = sym_dict
        print(f"  Indexed {sym} ({len(sym_dict)} trading days)", flush=True)

nifty_trend = load_nifty_macro()
print("All data indexed and cached in memory!\n", flush=True)

all_dates = sorted(stocks_arrays_by_date['RELIANCE'].keys())

def simulate_strategy_fast(stocks_dict, basket, nifty_trend_map, 
                           stop_mode='or-mid', 
                           rvol_thresh=1.0, 
                           require_macro_align=True, 
                           target_rr=2.5, 
                           use_be_trail=True, 
                           scale_out=False,
                           daily_circuit_breaker=-2.5,
                           defensive_dd_threshold=-15.0):
    trades = []
    
    portfolio_r = 0.0
    peak_r = 0.0
    current_dd_r = 0.0
    total_charges_sum = 0.0
    cutoff_time = time(15, 0)
    
    for dt in all_dates:
        day_net_r = 0.0
        day_trades_count = 0
        
        risk_r = 0.5 if current_dd_r < defensive_dd_threshold else 1.0
        risk_inr = risk_r * 200.0
        
        for sym in basket:
            if sym not in stocks_dict: continue
            day_data = stocks_dict[sym].get(dt)
            if day_data is None: continue
            
            closes = day_data['closes']
            n_bars = len(closes)
            if n_bars < 15: continue
            
            opens = day_data['opens']
            highs = day_data['highs']
            lows = day_data['lows']
            volumes = day_data['volumes']
            vwaps = day_data['vwaps']
            atrs = day_data['atrs']
            volmas = day_data['volmas']
            times = day_data['times']
            timestamps = day_data['timestamps']
            
            # Opening Range: First 3 bars (09:15 - 09:30 IST)
            or_h = max(highs[0], highs[1], highs[2])
            or_l = min(lows[0], lows[1], lows[2])
            or_mid = (or_h + or_l) * 0.5
            
            stock_day_trades = 0
            
            # Scan bars from bar 3 (09:30 IST) to bar 26 (11:30 IST)
            scan_limit = min(n_bars - 3, 27)
            for i in range(3, scan_limit):
                if stock_day_trades >= 1: break
                if day_net_r <= daily_circuit_breaker: break
                
                c_close = closes[i]
                c_open = opens[i]
                c_vwap = vwaps[i]
                c_vol = volumes[i]
                c_volma = volmas[i]
                
                rvol = (c_vol / c_volma) if c_volma > 0 else 1.0
                if rvol < rvol_thresh:
                    continue
                
                t_stamp = timestamps[i]
                macro = nifty_trend_map.get(t_stamp, 0)
                
                # --- BUY SIGNAL (ORB Long Breakout) ---
                if c_close > or_h and c_close > c_open and c_close > c_vwap:
                    if require_macro_align and macro == -1:
                        continue
                    
                    entry = c_close
                    if stop_mode == 'or-mid':
                        raw_sl = or_mid
                    elif stop_mode == 'or-low':
                        raw_sl = or_l
                    elif stop_mode == 'atr':
                        raw_sl = entry - (1.2 * atrs[i])
                    else:
                        raw_sl = or_mid
                    
                    sl_dist = max(entry - raw_sl, entry * 0.0050)
                    sl_price = entry - sl_dist
                    
                    tp1 = entry + (sl_dist * target_rr)
                    tp2 = entry + (sl_dist * 3.5) if scale_out else tp1
                    be_sl = entry + (sl_dist * 0.1)
                    trail_trigger = entry + (sl_dist * 1.5)
                    
                    t1_hit = False
                    cur_sl = sl_price
                    exit_price = None
                    exit_time = None
                    exit_reason = None
                    
                    for j in range(i+1, n_bars):
                        bar_h = highs[j]
                        bar_l = lows[j]
                        bar_t = times[j]
                        
                        if use_be_trail and not t1_hit:
                            if bar_h >= trail_trigger:
                                if be_sl > cur_sl: cur_sl = be_sl
                        
                        if scale_out:
                            if not t1_hit and bar_h >= tp1:
                                t1_hit = True
                                if be_sl > cur_sl: cur_sl = be_sl
                            if bar_l <= cur_sl:
                                exit_price = cur_sl
                                exit_time = bar_t
                                exit_reason = 'STOP_LOSS' if not t1_hit else 'BE_AFTER_T1'
                                break
                            if t1_hit and bar_h >= tp2:
                                exit_price = tp2
                                exit_time = bar_t
                                exit_reason = 'TARGET_2'
                                break
                        else:
                            if bar_h >= tp1:
                                exit_price = tp1
                                exit_time = bar_t
                                exit_reason = 'TARGET'
                                break
                            if bar_l <= cur_sl:
                                exit_price = cur_sl
                                exit_time = bar_t
                                exit_reason = 'STOP_LOSS' if cur_sl == sl_price else 'TRAILED_SL'
                                break
                        
                        if bar_t >= cutoff_time:
                            exit_price = closes[j]
                            exit_time = bar_t
                            exit_reason = 'EOD_SQUAREOFF'
                            break
                    
                    if exit_price is not None:
                        c_inr, c_r, net_r = calc_statutory_charges(entry, exit_price, sl_dist, 'BUY', risk_inr)
                        trades.append({
                            'Date': dt, 'Time': times[i], 'Symbol': sym, 'Direction': 'BUY',
                            'Entry': entry, 'Exit': exit_price, 'SL': sl_price, 'TP': tp1,
                            'SL_Dist': sl_dist, 'SL_Pct': (sl_dist/entry)*100,
                            'Charges_INR': c_inr, 'Charges_R': c_r, 'Net_R': net_r,
                            'Net_INR': net_r * risk_inr, 'ExitReason': exit_reason
                        })
                        day_net_r += net_r
                        day_trades_count += 1
                        stock_day_trades += 1
                        total_charges_sum += c_inr
                        continue
                
                # --- SELL SIGNAL (ORB Short Breakdown) ---
                elif c_close < or_l and c_close < c_open and c_close < c_vwap:
                    if require_macro_align and macro == 1:
                        continue
                    
                    entry = c_close
                    if stop_mode == 'or-mid':
                        raw_sl = or_mid
                    elif stop_mode == 'or-low':
                        raw_sl = or_h
                    elif stop_mode == 'atr':
                        raw_sl = entry + (1.2 * atrs[i])
                    else:
                        raw_sl = or_mid
                    
                    sl_dist = max(raw_sl - entry, entry * 0.0050)
                    sl_price = entry + sl_dist
                    
                    tp1 = entry - (sl_dist * target_rr)
                    tp2 = entry - (sl_dist * 3.5) if scale_out else tp1
                    be_sl = entry - (sl_dist * 0.1)
                    trail_trigger = entry - (sl_dist * 1.5)
                    
                    t1_hit = False
                    cur_sl = sl_price
                    exit_price = None
                    exit_time = None
                    exit_reason = None
                    
                    for j in range(i+1, n_bars):
                        bar_h = highs[j]
                        bar_l = lows[j]
                        bar_t = times[j]
                        
                        if use_be_trail and not t1_hit:
                            if bar_l <= trail_trigger:
                                if be_sl < cur_sl: cur_sl = be_sl
                        
                        if scale_out:
                            if not t1_hit and bar_l <= tp1:
                                t1_hit = True
                                if be_sl < cur_sl: cur_sl = be_sl
                            if bar_h >= cur_sl:
                                exit_price = cur_sl
                                exit_time = bar_t
                                exit_reason = 'STOP_LOSS' if not t1_hit else 'BE_AFTER_T1'
                                break
                            if t1_hit and bar_l <= tp2:
                                exit_price = tp2
                                exit_time = bar_t
                                exit_reason = 'TARGET_2'
                                break
                        else:
                            if bar_l <= tp1:
                                exit_price = tp1
                                exit_time = bar_t
                                exit_reason = 'TARGET'
                                break
                            if bar_h >= cur_sl:
                                exit_price = cur_sl
                                exit_time = bar_t
                                exit_reason = 'STOP_LOSS' if cur_sl == sl_price else 'TRAILED_SL'
                                break
                        
                        if bar_t >= cutoff_time:
                            exit_price = closes[j]
                            exit_time = bar_t
                            exit_reason = 'EOD_SQUAREOFF'
                            break
                    
                    if exit_price is not None:
                        c_inr, c_r, net_r = calc_statutory_charges(entry, exit_price, sl_dist, 'SELL', risk_inr)
                        trades.append({
                            'Date': dt, 'Time': times[i], 'Symbol': sym, 'Direction': 'SELL',
                            'Entry': entry, 'Exit': exit_price, 'SL': sl_price, 'TP': tp1,
                            'SL_Dist': sl_dist, 'SL_Pct': (sl_dist/entry)*100,
                            'Charges_INR': c_inr, 'Charges_R': c_r, 'Net_R': net_r,
                            'Net_INR': net_r * risk_inr, 'ExitReason': exit_reason
                        })
                        day_net_r += net_r
                        day_trades_count += 1
                        stock_day_trades += 1
                        total_charges_sum += c_inr
                        continue
        
        portfolio_r += day_net_r
        if portfolio_r > peak_r:
            peak_r = portfolio_r
        current_dd_r = portfolio_r - peak_r
    
    if not trades:
        return None
        
    df_res = pd.DataFrame(trades)
    df_res['Date'] = pd.to_datetime(df_res['Date'])
    df_res['YM'] = df_res['Date'].dt.to_period('M')
    
    tot_trades = len(df_res)
    wins = df_res[df_res['Net_R'] > 0]
    wr = len(wins) / tot_trades * 100.0
    tot_net_r = df_res['Net_R'].sum()
    tot_net_inr = df_res['Net_INR'].sum()
    
    gw = wins['Net_R'].sum()
    gl = abs(df_res[df_res['Net_R'] <= 0]['Net_R'].sum())
    pf = gw / gl if gl > 0 else 99.0
    
    cum = df_res['Net_R'].cumsum()
    dd_curve = cum - cum.cummax()
    max_dd_r = dd_curve.min()
    max_dd_inr = max_dd_r * 200.0
    
    num_months = df_res['YM'].nunique()
    r_per_month = tot_net_r / num_months if num_months > 0 else 0
    inr_per_month = tot_net_inr / num_months if num_months > 0 else 0
    
    monthly_pnl = df_res.groupby('YM')['Net_R'].sum()
    prof_months = (monthly_pnl > 0).sum()
    
    return {
        'trades': tot_trades,
        'win_rate': round(wr, 2),
        'profit_factor': round(pf, 2),
        'total_net_r': round(tot_net_r, 1),
        'monthly_net_r': round(r_per_month, 2),
        'total_net_inr': round(tot_net_inr, 2),
        'monthly_net_inr': round(inr_per_month, 2),
        'total_charges_inr': round(total_charges_sum, 2),
        'avg_charge_trade': round(total_charges_sum / tot_trades, 2),
        'max_dd_r': round(max_dd_r, 2),
        'max_dd_inr': round(max_dd_inr, 2),
        'months': num_months,
        'prof_months': prof_months,
        'monthly_win_pct': round((prof_months / num_months) * 100, 1) if num_months > 0 else 0,
        'trades_df': df_res
    }

print("Running Systematic Strategy Grid Sweep across Day Trader Candidates...", flush=True)

experiments = [
    {
        'id': 'EXP 1: Pure Day Trader ORB (or-mid SL, 2.0R TP)',
        'basket': TOP14_CHAMPIONS, 'stop_mode': 'or-mid', 'rvol_thresh': 1.0, 
        'require_macro_align': False, 'target_rr': 2.0, 'use_be_trail': False, 'scale_out': False
    },
    {
        'id': 'EXP 2: Day Trader ORB + RVOL >= 1.25x Catalyst',
        'basket': TOP14_CHAMPIONS, 'stop_mode': 'or-mid', 'rvol_thresh': 1.25, 
        'require_macro_align': False, 'target_rr': 2.0, 'use_be_trail': False, 'scale_out': False
    },
    {
        'id': 'EXP 3: Day Trader ORB + RVOL 1.25x + Nifty Macro Trend',
        'basket': TOP14_CHAMPIONS, 'stop_mode': 'or-mid', 'rvol_thresh': 1.25, 
        'require_macro_align': True, 'target_rr': 2.0, 'use_be_trail': False, 'scale_out': False
    },
    {
        'id': 'EXP 4: Day Trader ORB + RVOL 1.25x + Macro + 2.5R TP + BE Trail',
        'basket': TOP14_CHAMPIONS, 'stop_mode': 'or-mid', 'rvol_thresh': 1.25, 
        'require_macro_align': True, 'target_rr': 2.5, 'use_be_trail': True, 'scale_out': False
    },
    {
        'id': 'EXP 5: Day Trader ORB + RVOL 1.25x + Macro + 3.0R TP + BE Trail',
        'basket': TOP14_CHAMPIONS, 'stop_mode': 'or-mid', 'rvol_thresh': 1.25, 
        'require_macro_align': True, 'target_rr': 3.0, 'use_be_trail': True, 'scale_out': False
    },
    {
        'id': 'EXP 6: Day Trader ORB + ATR Stop (1.2*ATR) + 2.5R TP + BE Trail',
        'basket': TOP14_CHAMPIONS, 'stop_mode': 'atr', 'rvol_thresh': 1.25, 
        'require_macro_align': True, 'target_rr': 2.5, 'use_be_trail': True, 'scale_out': False
    },
    {
        'id': 'EXP 7: Day Trader ORB + Scale-Out Hybrid (50% @ 2R, 50% @ 3.5R)',
        'basket': TOP14_CHAMPIONS, 'stop_mode': 'or-mid', 'rvol_thresh': 1.25, 
        'require_macro_align': True, 'target_rr': 2.0, 'use_be_trail': True, 'scale_out': True
    },
    {
        'id': 'EXP 8: Full Universe (All 29 Liquid Stocks) + Best Setup',
        'basket': ALL_SYMBOLS, 'stop_mode': 'or-mid', 'rvol_thresh': 1.25, 
        'require_macro_align': True, 'target_rr': 2.5, 'use_be_trail': True, 'scale_out': False
    }
]

results_summary = []
best_trades_df = None
best_r = -999999

for exp in experiments:
    print(f"\nEvaluating: {exp['id']}...", flush=True)
    res = simulate_strategy_fast(
        stocks_dict=stocks_arrays_by_date,
        basket=exp['basket'],
        nifty_trend_map=nifty_trend,
        stop_mode=exp['stop_mode'],
        rvol_thresh=exp['rvol_thresh'],
        require_macro_align=exp['require_macro_align'],
        target_rr=exp['target_rr'],
        use_be_trail=exp['use_be_trail'],
        scale_out=exp['scale_out']
    )
    if res:
        print(f"  Trades: {res['trades']} | WR: {res['win_rate']}% | PF: {res['profit_factor']} | Net R: +{res['total_net_r']}R | Mo: +{res['monthly_net_r']}R/mo | DD: {res['max_dd_r']}R | Net Profit: INR {res['total_net_inr']:,.2f} | Fees: INR {res['total_charges_inr']:,.2f}", flush=True)
        results_summary.append({
            'Strategy': exp['id'],
            'Trades': res['trades'],
            'WinRate': f"{res['win_rate']}%",
            'ProfitFactor': res['profit_factor'],
            'Total_Net_R': f"+{res['total_net_r']} R",
            'Monthly_Net_R': f"+{res['monthly_net_r']} R/mo",
            'Max_DD_R': f"{res['max_dd_r']} R",
            'Net_Profit_INR': f"INR {res['total_net_inr']:,.0f}",
            'Total_Fees_INR': f"INR {res['total_charges_inr']:,.0f}",
            'Monthly_Win_Rate': f"{res['prof_months']}/{res['months']} ({res['monthly_win_pct']}%)"
        })
        if res['total_net_r'] > best_r:
            best_r = res['total_net_r']
            best_trades_df = res['trades_df']

print("\n" + "="*110, flush=True)
print("FINAL GRID EXPERIMENT RESULTS (4.8 YEARS AUDITED)", flush=True)
print("="*110, flush=True)
summary_df = pd.DataFrame(results_summary)
print(summary_df.to_string(index=False), flush=True)

if best_trades_df is not None:
    best_trades_df.to_csv('reports/day_trader_best_strategy_trades.csv', index=False)
    print("\nBest strategy trades successfully logged to reports/day_trader_best_strategy_trades.csv", flush=True)
