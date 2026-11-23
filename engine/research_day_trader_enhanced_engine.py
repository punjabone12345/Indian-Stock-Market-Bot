import os
import sys
import glob
import math
import pandas as pd
import numpy as np
from datetime import time, datetime

print("="*95, flush=True)
print("DAY TRADER SKILL: HIGH-PRECISION STRATEGY OPTIMIZATION (4.8 YEARS AUDITED)", flush=True)
print("Testing 5 Day-Trader Enhancements against Production Baseline on Top 14 Champions", flush=True)
print("Statutory Charges: 100% Exact Zerodha & Dhan Official Tariff (Paisa-Level)", flush=True)
print("="*95, flush=True)

def calc_statutory_charges(entry_price, exit_price, sl_dist, direction='BUY', risk_inr=200.0):
    if sl_dist <= 0 or entry_price <= 0:
        return 0.0, 0.0, 0.0
    qty = max(1, int(risk_inr / sl_dist))
    buy_px = entry_price if direction == 'BUY' else exit_price
    sell_px = exit_price if direction == 'BUY' else entry_price
    buy_turnover = qty * buy_px
    sell_turnover = qty * sell_px
    roundtrip = buy_turnover + sell_turnover
    
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
    return trend_map

TOP14_CHAMPIONS = [
    'RELIANCE', 'INDUSINDBK', 'LT', 'ADANIENT', 'TATAMOTORS',
    'SUNPHARMA', 'WIPRO', 'JSWSTEEL', 'TATASTEEL', 'BAJFINANCE',
    'SBIN', 'ONGC', 'TCS', 'MARUTI'
]

print("Pre-loading Top 14 Champions into high-speed indexed memory...", flush=True)
stocks_dict = {}
for sym in TOP14_CHAMPIONS:
    df_s = load_stock_5m(sym)
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
                'ema9s': grp['EMA9'].to_numpy(dtype=np.float64),
                'ema21s': grp['EMA21'].to_numpy(dtype=np.float64),
                'ema50s': grp['EMA50'].to_numpy(dtype=np.float64),
                'atrs': grp['ATR'].to_numpy(dtype=np.float64),
                'volmas': grp['VolMA20'].to_numpy(dtype=np.float64),
                'times': grp['Time'].tolist(),
                'timestamps': grp['Timestamp'].tolist()
            }
        stocks_dict[sym] = sym_dict

nifty_trend = load_nifty_macro()
all_dates = sorted(stocks_dict['RELIANCE'].keys())
print(f"Loaded {len(TOP14_CHAMPIONS)} stocks across {len(all_dates)} trading sessions!\n", flush=True)

def simulate_engine(target_rr=2.0, 
                    require_rvol=0.0, 
                    require_stacked_ema=False, 
                    min_start_time=time(9, 25), 
                    be_trail_r=0.0,
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
        risk_r = 0.5 if current_dd_r < defensive_dd_threshold else 1.0
        risk_inr = risk_r * 200.0
        
        for sym in TOP14_CHAMPIONS:
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
            ema9s = day_data['ema9s']
            ema21s = day_data['ema21s']
            ema50s = day_data['ema50s']
            atrs = day_data['atrs']
            volmas = day_data['volmas']
            times = day_data['times']
            timestamps = day_data['timestamps']
            
            stock_day_trades = 0
            
            for i in range(2, n_bars - 3):
                if stock_day_trades >= 2: break
                if day_net_r <= daily_circuit_breaker: break
                
                bar_t = times[i]
                if bar_t < min_start_time or bar_t > time(14, 30):
                    continue
                
                c_close = closes[i]
                c_open = opens[i]
                c_low = lows[i]
                c_high = highs[i]
                c_vwap = vwaps[i]
                c_ema9 = ema9s[i]
                c_ema21 = ema21s[i]
                c_ema50 = ema50s[i]
                c_atr = atrs[i]
                c_vol = volumes[i]
                c_volma = volmas[i]
                
                # RVOL check
                if require_rvol > 0:
                    rvol = (c_vol / c_volma) if c_volma > 0 else 1.0
                    if rvol < require_rvol:
                        continue
                
                # Stacked EMA check
                if require_stacked_ema:
                    # Will be checked in direction
                    pass
                
                t_stamp = timestamps[i]
                macro = nifty_trend.get(t_stamp, 0)
                
                p_low = lows[i-1]
                p_high = highs[i-1]
                p2_low = lows[i-2] if i >= 2 else p_low
                p2_high = highs[i-2] if i >= 2 else p_high
                
                # --- BUY SIGNAL (TradeEngine Bullish Pullback) ---
                is_bull_trend = (macro == 1) and (c_close > c_vwap) and (c_ema9 > c_ema21)
                if require_stacked_ema:
                    is_bull_trend = is_bull_trend and (c_ema21 > c_ema50)
                
                if is_bull_trend:
                    touched_ema9 = (c_low <= c_ema9 * 1.0020) or (p_low <= ema9s[i-1] * 1.0020) or (p2_low <= ema9s[i-2] * 1.0020)
                    if touched_ema9:
                        confirmed = (c_close > c_open) and (c_close >= c_ema9 * 0.9990)
                        in_range = c_close <= (c_ema9 + max(0.6 * c_atr, c_ema9 * 0.0060))
                        
                        if confirmed and in_range:
                            entry = c_close
                            raw_sl = min(c_low, p_low) - (0.2 * c_atr)
                            sl_dist = entry - raw_sl
                            sl_dist = max(sl_dist, entry * 0.0050)
                            sl_dist = min(sl_dist, entry * 0.0100)
                            sl_price = entry - sl_dist
                            
                            tp_price = entry + (sl_dist * target_rr)
                            be_sl = entry + (sl_dist * 0.1)
                            trail_trigger = entry + (sl_dist * be_trail_r)
                            
                            cur_sl = sl_price
                            exit_price = None
                            exit_time = None
                            exit_reason = None
                            
                            for j in range(i+1, n_bars):
                                bh = highs[j]
                                bl = lows[j]
                                bt = times[j]
                                
                                if be_trail_r > 0 and bh >= trail_trigger:
                                    if be_sl > cur_sl: cur_sl = be_sl
                                
                                if bl <= cur_sl:
                                    exit_price = cur_sl
                                    exit_time = bt
                                    exit_reason = 'STOP_LOSS' if cur_sl == sl_price else 'TRAILED_BE'
                                    break
                                
                                if bh >= tp_price:
                                    exit_price = tp_price
                                    exit_time = bt
                                    exit_reason = 'TARGET'
                                    break
                                
                                if bt >= cutoff_time:
                                    exit_price = closes[j]
                                    exit_time = bt
                                    exit_reason = 'EOD_SQUAREOFF'
                                    break
                            
                            if exit_price is not None:
                                c_inr, c_r, net_r = calc_statutory_charges(entry, exit_price, sl_dist, 'BUY', risk_inr)
                                trades.append({
                                    'Date': dt, 'Time': bar_t, 'Symbol': sym, 'Direction': 'BUY',
                                    'Entry': entry, 'Exit': exit_price, 'SL': sl_price, 'TP': tp_price,
                                    'Charges_INR': c_inr, 'Charges_R': c_r, 'Net_R': net_r,
                                    'Net_INR': net_r * risk_inr, 'ExitReason': exit_reason
                                })
                                day_net_r += net_r
                                stock_day_trades += 1
                                total_charges_sum += c_inr
                                continue
                
                # --- SELL SIGNAL (TradeEngine Bearish Pullback) ---
                is_bear_trend = (macro == -1) and (c_close < c_vwap) and (c_ema9 < c_ema21)
                if require_stacked_ema:
                    is_bear_trend = is_bear_trend and (c_ema21 < c_ema50)
                
                if is_bear_trend:
                    touched_ema9 = (c_high >= c_ema9 * 0.9980) or (p_high >= ema9s[i-1] * 0.9980) or (p2_high >= ema9s[i-2] * 0.9980)
                    if touched_ema9:
                        confirmed = (c_close < c_open) and (c_close <= c_ema9 * 1.0010)
                        in_range = c_close >= (c_ema9 - max(0.6 * c_atr, c_ema9 * 0.0060))
                        
                        if confirmed and in_range:
                            entry = c_close
                            raw_sl = max(c_high, p_high) + (0.2 * c_atr)
                            sl_dist = raw_sl - entry
                            sl_dist = max(sl_dist, entry * 0.0050)
                            sl_dist = min(sl_dist, entry * 0.0100)
                            sl_price = entry + sl_dist
                            
                            tp_price = entry - (sl_dist * target_rr)
                            be_sl = entry - (sl_dist * 0.1)
                            trail_trigger = entry - (sl_dist * be_trail_r)
                            
                            cur_sl = sl_price
                            exit_price = None
                            exit_time = None
                            exit_reason = None
                            
                            for j in range(i+1, n_bars):
                                bh = highs[j]
                                bl = lows[j]
                                bt = times[j]
                                
                                if be_trail_r > 0 and bl <= trail_trigger:
                                    if be_sl < cur_sl: cur_sl = be_sl
                                
                                if bh >= cur_sl:
                                    exit_price = cur_sl
                                    exit_time = bt
                                    exit_reason = 'STOP_LOSS' if cur_sl == sl_price else 'TRAILED_BE'
                                    break
                                
                                if bl <= tp_price:
                                    exit_price = tp_price
                                    exit_time = bt
                                    exit_reason = 'TARGET'
                                    break
                                
                                if bt >= cutoff_time:
                                    exit_price = closes[j]
                                    exit_time = bt
                                    exit_reason = 'EOD_SQUAREOFF'
                                    break
                            
                            if exit_price is not None:
                                c_inr, c_r, net_r = calc_statutory_charges(entry, exit_price, sl_dist, 'SELL', risk_inr)
                                trades.append({
                                    'Date': dt, 'Time': bar_t, 'Symbol': sym, 'Direction': 'SELL',
                                    'Entry': entry, 'Exit': exit_price, 'SL': sl_price, 'TP': tp_price,
                                    'Charges_INR': c_inr, 'Charges_R': c_r, 'Net_R': net_r,
                                    'Net_INR': net_r * risk_inr, 'ExitReason': exit_reason
                                })
                                day_net_r += net_r
                                stock_day_trades += 1
                                total_charges_sum += c_inr
                                continue

        portfolio_r += day_net_r
        if portfolio_r > peak_r: peak_r = portfolio_r
        current_dd_r = portfolio_r - peak_r

    if not trades: return None
    
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

print("Running Systematic Test Matrix of 6 Strategy Architectures...", flush=True)

test_matrix = [
    {
        'name': '1. Current Production Engine (Baseline 1:2.0 RRR, No Volume Filter)',
        'target_rr': 2.0, 'require_rvol': 0.0, 'require_stacked_ema': False, 'min_start_time': time(9, 25), 'be_trail_r': 0.0
    },
    {
        'name': '2. Day-Trader RVOL Filter (RVOL >= 1.0x Surge)',
        'target_rr': 2.0, 'require_rvol': 1.0, 'require_stacked_ema': False, 'min_start_time': time(9, 25), 'be_trail_r': 0.0
    },
    {
        'name': '3. Day-Trader Post-Opening Range (Start 09:45 AM after 30m OR settles)',
        'target_rr': 2.0, 'require_rvol': 1.0, 'require_stacked_ema': False, 'min_start_time': time(9, 45), 'be_trail_r': 0.0
    },
    {
        'name': '4. Day-Trader Breakeven Trail (Trail to +0.1R when profit reaches +1.4R)',
        'target_rr': 2.0, 'require_rvol': 1.0, 'require_stacked_ema': False, 'min_start_time': time(9, 45), 'be_trail_r': 1.4
    },
    {
        'name': '5. Day-Trader Higher Asymmetry (1:2.5 Target RRR + RVOL 1.0x + Start 09:45)',
        'target_rr': 2.5, 'require_rvol': 1.0, 'require_stacked_ema': False, 'min_start_time': time(9, 45), 'be_trail_r': 0.0
    },
    {
        'name': '6. Day-Trader Stacked Trend Power (Stacked EMAs 9>21>50 + RVOL 1.0x + 1:2.5 RRR)',
        'target_rr': 2.5, 'require_rvol': 1.0, 'require_stacked_ema': True, 'min_start_time': time(9, 45), 'be_trail_r': 0.0
    }
]

comparison = []
best_df = None
highest_net_r = -999999
best_name = None

for tm in test_matrix:
    print(f"\nTesting: {tm['name']}...", flush=True)
    res = simulate_engine(
        target_rr=tm['target_rr'],
        require_rvol=tm['require_rvol'],
        require_stacked_ema=tm['require_stacked_ema'],
        min_start_time=tm['min_start_time'],
        be_trail_r=tm['be_trail_r']
    )
    if res:
        print(f"  -> Trades: {res['trades']} | WR: {res['win_rate']}% | PF: {res['profit_factor']} | Net R: +{res['total_net_r']}R | Mo: +{res['monthly_net_r']}R/mo | DD: {res['max_dd_r']}R | Net Profit: INR {res['total_net_inr']:,.2f} | Fees: INR {res['total_charges_inr']:,.2f} | Months: {res['prof_months']}/{res['months']} ({res['monthly_win_pct']}%)", flush=True)
        comparison.append({
            'Strategy': tm['name'],
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
        if res['total_net_r'] > highest_net_r:
            highest_net_r = res['total_net_r']
            best_df = res['trades_df']
            best_name = tm['name']

print("\n" + "="*125, flush=True)
print("FINAL BENCHMARK COMPARISON MATRIX (4.8 YEARS | 2022-2026 | ALL ZERODHA/DHAN TAXES DEDUCTED)", flush=True)
print("="*125, flush=True)
comp_df = pd.DataFrame(comparison)
print(comp_df.to_string(index=False), flush=True)

if best_df is not None:
    best_df.to_csv('reports/day_trader_enhanced_champion_trades.csv', index=False)
    print(f"\nBest strategy ({best_name}) saved to reports/day_trader_enhanced_champion_trades.csv", flush=True)
