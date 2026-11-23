import os
import sys
import glob
import math
import pandas as pd
import numpy as np
from datetime import time, datetime

print("="*95)
print("RESEARCH ENGINE: TARGETING 70+ R / MONTH WITH CONTROLLED DRAWDOWN")
print("Benchmarking Universe Expansion, Wave Combinations & Dynamic Asymmetry (2022-2026)")
print("100% Real Zerodha & Dhan Statutory Tariffs (Paisa-Level)")
print("="*95)

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

def load_stock_5m(s, start_date='2022-01-01', end_date='2026-10-16'):
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
    
    df_n = pd.concat(dfs).sort_values('Timestamp').drop_duplicates('Timestamp').reset_index(drop=True)
    df_n = df_n[(df_n['Timestamp'] >= start_date) & (df_n['Timestamp'] <= end_date + ' 23:59:59')]
    df_n = df_n.set_index('Timestamp')
    agg_d = {'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}
    df_5m = df_n.resample('5min', origin='start_day').agg(agg_d).dropna().reset_index()
    df_5m['EMA9'] = df_5m['Close'].ewm(span=9, adjust=False).mean()
    df_5m['EMA21'] = df_5m['Close'].ewm(span=21, adjust=False).mean()
    df_5m['MacroTrend'] = 0
    df_5m.loc[(df_5m['Close'] > df_5m['EMA9']) & (df_5m['EMA9'] > df_5m['EMA21']), 'MacroTrend'] = 1
    df_5m.loc[(df_5m['Close'] < df_5m['EMA9']) & (df_5m['EMA9'] < df_5m['EMA21']), 'MacroTrend'] = -1
    return df_5m.set_index('Timestamp')['MacroTrend'].to_dict()

print("Loading NIFTY Macro...")
nifty_trend_map = load_nifty_macro()
print(f"Loaded {len(nifty_trend_map)} NIFTY 5m bars.")

# Load all 30 stock data
files = sorted(glob.glob('data/stocks/*_prev.parquet'))
ALL_SYMBOLS = [os.path.basename(f).replace('_prev.parquet', '') for f in files]

stock_cache = {}
print(f"Pre-caching 5m datasets for {len(ALL_SYMBOLS)} symbols...")
for s in ALL_SYMBOLS:
    df_s = load_stock_5m(s)
    if df_s is not None and len(df_s) > 1000:
        # Precompute daily index
        daily = {}
        for dt, grp in df_s.groupby('Date'):
            daily[dt] = {
                'opens': grp['Open'].values,
                'highs': grp['High'].values,
                'lows': grp['Low'].values,
                'closes': grp['Close'].values,
                'vols': grp['Volume'].values,
                'volmas': grp['VolMA20'].values,
                'times': grp['Time'].values,
                'timestamps': grp['Timestamp'].values,
                'ema9': grp['EMA9'].values,
                'ema21': grp['EMA21'].values,
                'ema50': grp['EMA50'].values,
                'vwap': grp['VWAP'].values,
                'atr': grp['ATR'].values,
                'n': len(grp)
            }
        stock_cache[s] = daily

print(f"Cached {len(stock_cache)} stocks successfully.")

# All unique trading dates
all_dates = sorted(list(set.union(*[set(daily.keys()) for daily in stock_cache.values()])))
print(f"Total trading days across dataset: {len(all_dates)}")

def simulate_portfolio(
    symbols,
    waves_allowed=[2],
    target_rr=3.0,
    rvol_thresh=1.0,
    be_trail_r=0.0,
    max_concurrent=3,
    max_daily_portfolio_trades=10,
    risk_inr=200.0,
    eod_time=time(15, 0)
):
    trades = []
    daily_net_pnl = {}
    
    # Track overall portfolio R curve
    portfolio_r = 0.0
    peak_r = 0.0
    max_dd_r = 0.0
    
    total_charges_sum = 0.0
    
    for dt in all_dates:
        # Collect candidate signals for the day across all allowed symbols
        # For realistic portfolio simulation, evaluate candle-by-candle across all symbols!
        day_stock_data = {s: stock_cache[s][dt] for s in symbols if s in stock_cache and dt in stock_cache[s]}
        if not day_stock_data:
            continue
            
        stock_day_trade_count = {s: 0 for s in day_stock_data}
        stock_last_trade_win = {s: None for s in day_stock_data}
        active_positions = [] # list of active dicts: {sym, entry_time, entry, sl, tp, sl_dist, dir, is_be}
        
        # Max number of 5m bars in day
        max_bars = max(data['n'] for data in day_stock_data.values())
        day_net_r = 0.0
        day_trades_count = 0
        
        for bar_idx in range(2, max_bars):
            # 1. Update/check active positions first
            still_active = []
            for pos in active_positions:
                s = pos['sym']
                s_data = day_stock_data[s]
                if bar_idx >= s_data['n']:
                    # Force EOD exit
                    exit_px = s_data['closes'][-1]
                    c_inr, c_r, net_r = calc_statutory_charges(pos['entry'], exit_px, pos['sl_dist'], pos['dir'], risk_inr)
                    trades.append({
                        'Date': dt, 'Time': s_data['times'][-1], 'Symbol': s, 'Direction': pos['dir'],
                        'Wave': pos['wave'], 'Entry': pos['entry'], 'Exit': exit_px, 'SL': pos['sl'], 'TP': pos['tp'],
                        'Charges_INR': c_inr, 'Charges_R': c_r, 'Net_R': net_r, 'Net_INR': net_r * risk_inr,
                        'ExitReason': 'EOD_SQUAREOFF'
                    })
                    day_net_r += net_r
                    total_charges_sum += c_inr
                    continue
                
                h = s_data['highs'][bar_idx]
                l = s_data['lows'][bar_idx]
                c = s_data['closes'][bar_idx]
                t = s_data['times'][bar_idx]
                
                exit_px = None
                exit_reason = None
                
                if pos['dir'] == 'BUY':
                    # Breakeven trail check
                    if be_trail_r > 0 and not pos['is_be']:
                        if (h - pos['entry']) >= (be_trail_r * pos['sl_dist']):
                            pos['sl'] = pos['entry'] + (0.1 * pos['sl_dist']) # lock +0.1R
                            pos['is_be'] = True
                    
                    if l <= pos['sl']:
                        exit_px = pos['sl']
                        exit_reason = 'STOP_LOSS' if not pos['is_be'] else 'TRAIL_BE'
                    elif h >= pos['tp']:
                        exit_px = pos['tp']
                        exit_reason = 'TARGET'
                    elif t >= eod_time:
                        exit_px = c
                        exit_reason = 'EOD_SQUAREOFF'
                else: # SELL
                    if be_trail_r > 0 and not pos['is_be']:
                        if (pos['entry'] - l) >= (be_trail_r * pos['sl_dist']):
                            pos['sl'] = pos['entry'] - (0.1 * pos['sl_dist'])
                            pos['is_be'] = True
                            
                    if h >= pos['sl']:
                        exit_px = pos['sl']
                        exit_reason = 'STOP_LOSS' if not pos['is_be'] else 'TRAIL_BE'
                    elif l <= pos['tp']:
                        exit_px = pos['tp']
                        exit_reason = 'TARGET'
                    elif t >= eod_time:
                        exit_px = c
                        exit_reason = 'EOD_SQUAREOFF'
                
                if exit_px is not None:
                    c_inr, c_r, net_r = calc_statutory_charges(pos['entry'], exit_px, pos['sl_dist'], pos['dir'], risk_inr)
                    trades.append({
                        'Date': dt, 'Time': t, 'Symbol': s, 'Direction': pos['dir'],
                        'Wave': pos['wave'], 'Entry': pos['entry'], 'Exit': exit_px, 'SL': pos['sl'], 'TP': pos['tp'],
                        'Charges_INR': c_inr, 'Charges_R': c_r, 'Net_R': net_r, 'Net_INR': net_r * risk_inr,
                        'ExitReason': exit_reason
                    })
                    day_net_r += net_r
                    total_charges_sum += c_inr
                    stock_last_trade_win[s] = (net_r > 0)
                else:
                    still_active.append(pos)
                    
            active_positions = still_active
            
            # 2. Check for new entries if capacity permits
            if len(active_positions) >= max_concurrent or day_trades_count >= max_daily_portfolio_trades:
                continue
                
            for s, s_data in day_stock_data.items():
                if len(active_positions) >= max_concurrent or day_trades_count >= max_daily_portfolio_trades:
                    break
                if any(p['sym'] == s for p in active_positions):
                    continue # already in this stock
                if bar_idx >= s_data['n']:
                    continue
                    
                cur_t = s_data['times'][bar_idx]
                if cur_t < time(9, 30) or cur_t > time(14, 15):
                    continue
                    
                cur_ts = s_data['timestamps'][bar_idx]
                nifty_m = nifty_trend_map.get(cur_ts, 0)
                
                c = s_data['closes'][bar_idx]
                o = s_data['opens'][bar_idx]
                h = s_data['highs'][bar_idx]
                l = s_data['lows'][bar_idx]
                v = s_data['vols'][bar_idx]
                vma = s_data['volmas'][bar_idx]
                e9 = s_data['ema9'][bar_idx]
                e21 = s_data['ema21'][bar_idx]
                e50 = s_data['ema50'][bar_idx]
                vw = s_data['vwap'][bar_idx]
                at = s_data['atr'][bar_idx]
                
                candle_range = h - l + 1e-6
                body_ratio = abs(c - o) / candle_range
                vol_ratio = v / (vma + 1e-6)
                
                # Check setup trigger
                trigger_dir = None
                
                # BUY: Bullish NIFTY + Above VWAP + EMA9 > EMA21 + Pullback to EMA9 + Expansion Close
                if (nifty_m == 1 and c > vw and e9 > e21 and 
                    (l <= e9 or s_data['lows'][bar_idx-1] <= s_data['ema9'][bar_idx-1]) and
                    c > o and c > e9 and vol_ratio >= rvol_thresh and body_ratio >= 0.40):
                    trigger_dir = 'BUY'
                    
                # SELL: Bearish NIFTY + Below VWAP + EMA9 < EMA21 + Pullback to EMA9 + Expansion Close
                elif (nifty_m == -1 and c < vw and e9 < e21 and 
                      (h >= e9 or s_data['highs'][bar_idx-1] >= s_data['ema9'][bar_idx-1]) and
                      c < o and c < e9 and vol_ratio >= rvol_thresh and body_ratio >= 0.40):
                    trigger_dir = 'SELL'
                    
                if trigger_dir is not None:
                    # Increment stock day trade count (this is the wave number)
                    stock_day_trade_count[s] += 1
                    current_wave = stock_day_trade_count[s]
                    
                    # Check if this wave is allowed
                    if current_wave not in waves_allowed:
                        continue
                        
                    # Calculate SL and TP
                    if trigger_dir == 'BUY':
                        raw_sl = min(l, s_data['lows'][bar_idx-1]) - (0.2 * at)
                        sl_dist = max(c - raw_sl, c * 0.0020)
                        if sl_dist > c * 0.0070: continue # reject SL too wide
                        sl = c - sl_dist
                        tp = c + (sl_dist * target_rr)
                    else:
                        raw_sl = max(h, s_data['highs'][bar_idx-1]) + (0.2 * at)
                        sl_dist = max(raw_sl - c, c * 0.0020)
                        if sl_dist > c * 0.0070: continue
                        sl = c + sl_dist
                        tp = c - (sl_dist * target_rr)
                        
                    active_positions.append({
                        'sym': s, 'entry_time': cur_t, 'entry': c, 'sl': sl, 'tp': tp,
                        'sl_dist': sl_dist, 'dir': trigger_dir, 'wave': current_wave, 'is_be': False
                    })
                    day_trades_count += 1
        
        # End of day force square off any leftover positions
        for pos in active_positions:
            s = pos['sym']
            s_data = day_stock_data[s]
            exit_px = s_data['closes'][-1]
            c_inr, c_r, net_r = calc_statutory_charges(pos['entry'], exit_px, pos['sl_dist'], pos['dir'], risk_inr)
            trades.append({
                'Date': dt, 'Time': s_data['times'][-1], 'Symbol': s, 'Direction': pos['dir'],
                'Wave': pos['wave'], 'Entry': pos['entry'], 'Exit': exit_px, 'SL': pos['sl'], 'TP': pos['tp'],
                'Charges_INR': c_inr, 'Charges_R': c_r, 'Net_R': net_r, 'Net_INR': net_r * risk_inr,
                'ExitReason': 'EOD_SQUAREOFF'
            })
            day_net_r += net_r
            total_charges_sum += c_inr
            
        portfolio_r += day_net_r
        if portfolio_r > peak_r:
            peak_r = portfolio_r
        dd = portfolio_r - peak_r
        if dd < max_dd_r:
            max_dd_r = dd
            
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
    
    num_months = df_res['YM'].nunique()
    r_per_mo = tot_net_r / num_months if num_months > 0 else 0
    inr_per_mo = tot_net_inr / num_months if num_months > 0 else 0
    
    monthly_pnl = df_res.groupby('YM')['Net_R'].sum()
    prof_months = (monthly_pnl > 0).sum()
    
    return {
        'trades': tot_trades,
        'win_rate': round(wr, 2),
        'profit_factor': round(pf, 2),
        'total_net_r': round(tot_net_r, 1),
        'monthly_net_r': round(r_per_mo, 2),
        'total_net_inr': round(tot_net_inr, 2),
        'monthly_net_inr': round(inr_per_mo, 2),
        'total_charges_inr': round(total_charges_sum, 2),
        'max_dd_r': round(max_dd_r, 2),
        'months': num_months,
        'prof_months': prof_months,
        'monthly_win_pct': round((prof_months / num_months) * 100, 1) if num_months > 0 else 0,
        'trades_df': df_res
    }

print("Simulator engine compiled successfully.")

BASKET_6 = ['RELIANCE', 'MARUTI', 'SUNPHARMA', 'TATAMOTORS', 'TCS', 'TATASTEEL']
BASKET_10 = ['RELIANCE', 'MARUTI', 'SUNPHARMA', 'TATAMOTORS', 'TCS', 'TATASTEEL', 'ICICIBANK', 'LT', 'BHARTIARTL', 'HDFCBANK']
BASKET_14 = BASKET_10 + ['KOTAKBANK', 'SBIN', 'TITAN', 'BAJFINANCE']
BASKET_20 = BASKET_14 + ['AXISBANK', 'INFY', 'ITC', 'JSWSTEEL', 'GRASIM', 'ADANIENT']
BASKET_30 = ALL_SYMBOLS

test_matrix = [
    # 1. Baseline 6 Champions (Wave 2)
    {
        'id': '1. 6 Stocks | Wave 2 | 3.0R Target | No Trail',
        'symbols': BASKET_6, 'waves': [2], 'target_rr': 3.0, 'rvol': 1.0, 'trail': 0.0, 'concur': 3
    },
    # 2. 10 Stocks | Wave 2 | 3.0R Target | No Trail
    {
        'id': '2. 10 Stocks | Wave 2 | 3.0R Target | No Trail',
        'symbols': BASKET_10, 'waves': [2], 'target_rr': 3.0, 'rvol': 1.0, 'trail': 0.0, 'concur': 3
    },
    # 3. 14 Stocks | Wave 2 | 3.0R Target | No Trail
    {
        'id': '3. 14 Stocks | Wave 2 | 3.0R Target | No Trail',
        'symbols': BASKET_14, 'waves': [2], 'target_rr': 3.0, 'rvol': 1.0, 'trail': 0.0, 'concur': 4
    },
    # 4. 20 Stocks | Wave 2 | 3.0R Target | No Trail
    {
        'id': '4. 20 Stocks | Wave 2 | 3.0R Target | No Trail',
        'symbols': BASKET_20, 'waves': [2], 'target_rr': 3.0, 'rvol': 1.0, 'trail': 0.0, 'concur': 4
    },
    # 5. 14 Stocks | Wave 2 + Wave 3 | 3.0R Target | No Trail
    {
        'id': '5. 14 Stocks | Wave 2 + Wave 3 | 3.0R Target | No Trail',
        'symbols': BASKET_14, 'waves': [2, 3], 'target_rr': 3.0, 'rvol': 1.0, 'trail': 0.0, 'concur': 4
    },
    # 6. 14 Stocks | Wave 2 + Wave 3 | 3.0R Target | BE Trail @ 1.5R
    {
        'id': '6. 14 Stocks | Wave 2 + Wave 3 | 3.0R Target | BE Trail @ 1.5R',
        'symbols': BASKET_14, 'waves': [2, 3], 'target_rr': 3.0, 'rvol': 1.0, 'trail': 1.5, 'concur': 4
    },
    # 7. 20 Stocks | Wave 2 + Wave 3 | 3.0R Target | BE Trail @ 1.5R
    {
        'id': '7. 20 Stocks | Wave 2 + Wave 3 | 3.0R Target | BE Trail @ 1.5R',
        'symbols': BASKET_20, 'waves': [2, 3], 'target_rr': 3.0, 'rvol': 1.0, 'trail': 1.5, 'concur': 4
    },
    # 8. 20 Stocks | Wave 2 + Wave 3 | 3.5R Asymmetric Target | BE Trail @ 1.5R
    {
        'id': '8. 20 Stocks | Wave 2 + Wave 3 | 3.5R Target | BE Trail @ 1.5R',
        'symbols': BASKET_20, 'waves': [2, 3], 'target_rr': 3.5, 'rvol': 1.0, 'trail': 1.5, 'concur': 4
    },
    # 9. All 30 Stocks | Wave 2 + Wave 3 | 3.0R Target | BE Trail @ 1.5R
    {
        'id': '9. All 30 Stocks | Wave 2 + Wave 3 | 3.0R Target | BE Trail @ 1.5R',
        'symbols': BASKET_30, 'waves': [2, 3], 'target_rr': 3.0, 'rvol': 1.0, 'trail': 1.5, 'concur': 4
    },
    # 10. All 30 Stocks | Wave 2 + Wave 3 + Wave 4 | 3.0R Target | BE Trail @ 1.5R
    {
        'id': '10. All 30 Stocks | Wave 2-4 | 3.0R Target | BE Trail @ 1.5R',
        'symbols': BASKET_30, 'waves': [2, 3, 4], 'target_rr': 3.0, 'rvol': 1.0, 'trail': 1.5, 'concur': 4
    }
]

print("\n" + "="*95)
print("RUNNING SYSTEMATIC SEARCH FOR 70+ R / MONTH ARCHITECTURES...")
print("="*95)

results = []
champion_df = None
highest_monthly_r = -9999
champion_id = None

for cfg in test_matrix:
    print(f"\nEvaluating: {cfg['id']}...", flush=True)
    res = simulate_portfolio(
        symbols=cfg['symbols'],
        waves_allowed=cfg['waves'],
        target_rr=cfg['target_rr'],
        rvol_thresh=cfg['rvol'],
        be_trail_r=cfg['trail'],
        max_concurrent=cfg['concur']
    )
    if res:
        print(f"  -> Trades: {res['trades']} | WR: {res['win_rate']}% | PF: {res['profit_factor']} | Net R: +{res['total_net_r']}R | Mo: +{res['monthly_net_r']}R/mo | DD: {res['max_dd_r']}R | Net Profit: INR {res['total_net_inr']:,.0f} | Months: {res['prof_months']}/{res['months']} ({res['monthly_win_pct']}%)", flush=True)
        results.append({
            'Config': cfg['id'],
            'Trades': res['trades'],
            'WinRate': f"{res['win_rate']}%",
            'PF': res['profit_factor'],
            'Total_Net_R': f"+{res['total_net_r']} R",
            'Monthly_Net_R': f"+{res['monthly_net_r']} R/mo",
            'Max_DD_R': f"{res['max_dd_r']} R",
            'Net_Profit_INR': f"INR {res['total_net_inr']:,.0f}",
            'Monthly_Win_Rate': f"{res['prof_months']}/{res['months']} ({res['monthly_win_pct']}%)"
        })
        if res['monthly_net_r'] > highest_monthly_r:
            highest_monthly_r = res['monthly_net_r']
            champion_df = res['trades_df']
            champion_id = cfg['id']

print("\n" + "="*125)
print("RESULTS MATRIX: SEARCHING FOR 70+ R / MONTH WITH CONTROLLED DRAWDOWN")
print("="*125)
df_matrix = pd.DataFrame(results)
print(df_matrix.to_string(index=False))

if champion_df is not None:
    champion_df.to_csv('reports/target_70r_champion_trades.csv', index=False)
    print(f"\nSaved highest-yield champion ({champion_id}) to reports/target_70r_champion_trades.csv")
