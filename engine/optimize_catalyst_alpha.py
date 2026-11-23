import sys
sys.path.append('engine')
import os
import glob
import pandas as pd
import numpy as np
import datetime
from datetime import time
from nifty_alpha_explorer import load_nifty_fast
from nifty_aligned_ema_atr_sweep import load_stock_data, get_nifty_trend_series

print("="*95, flush=True)
print("CATALYST OPTIMIZER: TESTING TRAIL, RVOL & DAILY TREND ALIGNMENT (2022-2026)", flush=True)
print("Strict Candle-by-Candle | Zero Lookahead | Exact Zerodha/Dhan Taxes", flush=True)
print("="*95, flush=True)

def calc_statutory_charges(entry_price, exit_price, sl_dist, direction='BUY', risk_inr=200.0):
    if sl_dist <= 0 or entry_price <= 0: return 0.0, 0.0, 0.0
    qty = max(1, int(risk_inr / sl_dist))
    buy_px = entry_price if direction == 'BUY' else exit_price
    sell_px = exit_price if direction == 'BUY' else entry_price
    buy_turnover = qty * buy_px
    sell_turnover = qty * sell_px
    roundtrip = buy_turnover + sell_turnover
    
    brok = min(20.0, buy_turnover * 0.0003) + min(20.0, sell_turnover * 0.0003)
    stt = sell_turnover * 0.00025
    exch = roundtrip * 0.0000297
    sebi = roundtrip * 0.000001
    stamp = buy_turnover * 0.00003
    gst = (brok + exch + sebi) * 0.18
    slippage = qty * 0.05
    
    total_tax = brok + stt + exch + sebi + stamp + gst + slippage
    tax_r = total_tax / risk_inr
    gross_pnl = qty * (exit_price - entry_price) if direction == 'BUY' else qty * (entry_price - exit_price)
    net_pnl = gross_pnl - total_tax
    net_r = net_pnl / risk_inr
    return total_tax, tax_r, net_r

nifty_1m = load_nifty_fast()
nifty_trend = get_nifty_trend_series(nifty_1m, tf_min=5)

files = sorted(glob.glob('data/stocks/*_prev.parquet'))
ALL_SYMBOLS = [os.path.basename(f).replace('_prev.parquet', '') for f in files]

stock_dfs = {}
for sym in ALL_SYMBOLS:
    df_1m = load_stock_data(sym)
    if df_1m is None or len(df_1m) < 1000: continue
    
    df_5m = df_1m.set_index('Timestamp').resample('5min', origin='start_day', offset='15min').agg({
        'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'
    }).dropna().reset_index()
    
    df_5m['Date'] = df_5m['Timestamp'].dt.date
    df_5m['Time'] = df_5m['Timestamp'].dt.time
    
    df_5m['Typ'] = (df_5m['High'] + df_5m['Low'] + df_5m['Close']) / 3.0
    df_5m['PV'] = df_5m['Typ'] * df_5m['Volume']
    df_5m['VWAP'] = df_5m.groupby('Date')['PV'].cumsum() / df_5m.groupby('Date')['Volume'].cumsum()
    df_5m['VolMA20'] = df_5m['Volume'].rolling(20, min_periods=1).mean()
    
    # ATR
    tr1 = df_5m['High'] - df_5m['Low']
    tr2 = (df_5m['High'] - df_5m['Close'].shift()).abs()
    tr3 = (df_5m['Low'] - df_5m['Close'].shift()).abs()
    df_5m['ATR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14, min_periods=1).mean()
    
    # Daily aggregation for gap and 20-day trend
    d_agg = df_5m.groupby('Date').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'})
    d_agg['Daily_EMA20'] = d_agg['Close'].ewm(span=20, adjust=False).mean()
    d_agg['Daily_Trend'] = np.where(d_agg['Close'] > d_agg['Daily_EMA20'], 1, -1)
    d_prev = d_agg.shift(1).rename(columns={'Close':'PDC', 'Daily_Trend':'Daily_Trend_Prev'})
    df_5m = df_5m.merge(d_prev[['PDC', 'Daily_Trend_Prev']], on='Date', how='left')
    
    first_bars = df_5m[df_5m['Time'] <= time(9, 25)].groupby('Date').agg({'High':'max', 'Low':'min', 'Volume':'sum'})
    df_5m['OR_H'] = df_5m['Date'].map(first_bars['High'])
    df_5m['OR_L'] = df_5m['Date'].map(first_bars['Low'])
    df_5m['Nifty_Trend'] = df_5m['Timestamp'].map(nifty_trend['Nifty_Trend']).fillna(0).astype(int)
    stock_dfs[sym] = df_5m

print(f"Prepped {len(stock_dfs)} stocks.", flush=True)

def simulate_catalyst(target_rr=2.5, be_trail_r=1.2, rvol_min=1.2, require_daily_trend=True):
    trades = []
    for sym, df_5m in stock_dfs.items():
        for dt, day_df in df_5m.groupby('Date'):
            n = len(day_df)
            if n < 15: continue
            
            pdc = day_df['PDC'].values[0]
            if pd.isna(pdc) or pdc <= 0: continue
            d_trend = day_df['Daily_Trend_Prev'].values[0]
            
            opens = day_df['Open'].values
            highs = day_df['High'].values
            lows = day_df['Low'].values
            closes = day_df['Close'].values
            vols = day_df['Volume'].values
            volmas = day_df['VolMA20'].values
            times = day_df['Time'].values
            vwap = day_df['VWAP'].values
            atr = day_df['ATR'].values
            nt = day_df['Nifty_Trend'].values
            or_h = day_df['OR_H'].values[0]
            or_l = day_df['OR_L'].values[0]
            
            gap_pct = (opens[0] - pdc) / pdc * 100.0
            
            active_pos = None
            day_trades = 0
            
            for i in range(3, n):
                if active_pos is not None:
                    h = highs[i]; l = lows[i]; c = closes[i]; t = times[i]
                    exit_px = None; exit_reason = None
                    
                    if active_pos['dir'] == 'BUY':
                        if be_trail_r > 0 and not active_pos['is_be']:
                            if h - active_pos['entry'] >= be_trail_r * active_pos['sl_dist']:
                                active_pos['sl'] = active_pos['entry'] + 0.1 * active_pos['sl_dist']
                                active_pos['is_be'] = True
                                
                        if l <= active_pos['sl']:
                            exit_px = active_pos['sl']; exit_reason = 'STOP_LOSS' if not active_pos['is_be'] else 'TRAIL_BE'
                        elif h >= active_pos['tp']:
                            exit_px = active_pos['tp']; exit_reason = 'TARGET'
                        elif t >= time(15, 15):
                            exit_px = c; exit_reason = 'EOD_SQUAREOFF'
                    else:
                        if be_trail_r > 0 and not active_pos['is_be']:
                            if active_pos['entry'] - l >= be_trail_r * active_pos['sl_dist']:
                                active_pos['sl'] = active_pos['entry'] - 0.1 * active_pos['sl_dist']
                                active_pos['is_be'] = True
                                
                        if h >= active_pos['sl']:
                            exit_px = active_pos['sl']; exit_reason = 'STOP_LOSS' if not active_pos['is_be'] else 'TRAIL_BE'
                        elif l <= active_pos['tp']:
                            exit_px = active_pos['tp']; exit_reason = 'TARGET'
                        elif t >= time(15, 15):
                            exit_px = c; exit_reason = 'EOD_SQUAREOFF'
                            
                    if exit_px is not None:
                        c_inr, c_r, net_r = calc_statutory_charges(active_pos['entry'], exit_px, active_pos['sl_dist'], active_pos['dir'], 200.0)
                        trades.append({
                            'Date': dt, 'Time': active_pos['time'], 'Symbol': sym, 'Direction': active_pos['dir'],
                            'Net_R': net_r, 'Charges_INR': c_inr, 'ExitReason': exit_reason
                        })
                        active_pos = None
                    continue
                    
                if day_trades >= 1: continue
                if times[i] < time(9, 30) or times[i] > time(11, 15): continue
                
                rvol = vols[i] / (volmas[i] + 1e-6)
                if rvol < rvol_min: continue
                
                trigger_dir = None
                raw_sl = 0
                
                # BUY: Gap Up >= 0.8% + breaks OR_H + Nifty == 1 + Above VWAP (+ Daily Trend == 1)
                if gap_pct >= 0.8 and nt[i] == 1 and closes[i] > vwap[i]:
                    if not require_daily_trend or d_trend == 1:
                        if closes[i] > or_h and opens[i] <= or_h and closes[i] > opens[i]:
                            trigger_dir = 'BUY'
                            raw_sl = min(lows[i], (or_h + or_l)/2.0)
                # SELL: Gap Down <= -0.8% + breaks OR_L + Nifty == -1 + Below VWAP (+ Daily Trend == -1)
                elif gap_pct <= -0.8 and nt[i] == -1 and closes[i] < vwap[i]:
                    if not require_daily_trend or d_trend == -1:
                        if closes[i] < or_l and opens[i] >= or_l and closes[i] < opens[i]:
                            trigger_dir = 'SELL'
                            raw_sl = max(highs[i], (or_h + or_l)/2.0)
                            
                if trigger_dir is not None:
                    entry = closes[i]
                    if trigger_dir == 'BUY':
                        sl_dist = max(entry - raw_sl, entry * 0.0035)
                        if sl_dist > entry * 0.0100: continue
                        sl = entry - sl_dist
                        tp = entry + sl_dist * target_rr
                    else:
                        sl_dist = max(raw_sl - entry, entry * 0.0035)
                        if sl_dist > entry * 0.0100: continue
                        sl = entry + sl_dist
                        tp = entry - sl_dist * target_rr
                        
                    active_pos = {
                        'time': times[i], 'entry': entry, 'sl': sl, 'tp': tp,
                        'sl_dist': sl_dist, 'dir': trigger_dir, 'is_be': False
                    }
                    day_trades += 1
                    
    if not trades: return None
    df_res = pd.DataFrame(trades)
    df_res['Date'] = pd.to_datetime(df_res['Date'])
    df_res['YM'] = df_res['Date'].dt.to_period('M')
    
    tot = len(df_res)
    wins = df_res[df_res['Net_R'] > 0]
    wr = len(wins) / tot * 100
    tot_r = df_res['Net_R'].sum()
    mo_r = tot_r / df_res['YM'].nunique()
    gw = wins['Net_R'].sum()
    gl = abs(df_res[df_res['Net_R'] <= 0]['Net_R'].sum())
    pf = gw / gl if gl > 0 else 99
    daily = df_res.groupby('Date')['Net_R'].sum()
    max_dd = (daily.cumsum() - daily.cumsum().cummax()).min()
    pos_m = (df_res.groupby('YM')['Net_R'].sum() > 0).sum()
    tot_m = df_res['YM'].nunique()
    
    return {
        'Target_RR': target_rr, 'Trail': be_trail_r, 'RVOL': rvol_min, 'DailyTrend': require_daily_trend,
        'Trades': tot, 'WinRate': round(wr, 1), 'ProfitFactor': round(pf, 2),
        'Total_Net_R': round(tot_r, 1), 'Monthly_Net_R': round(mo_r, 2), 'Max_DD': round(max_dd, 1),
        'Prof_Months': f"{pos_m}/{tot_m} ({pos_m/tot_m*100:.1f}%)"
    }

print("\n" + "="*95, flush=True)
print("RUNNING PARAMETRIC MATRIX...", flush=True)
print("="*95, flush=True)

matrix_res = []
for rr in [2.0, 2.5, 3.0]:
    for trail in [0.0, 1.0, 1.2]:
        for rvol in [1.0, 1.3, 1.5]:
            for d_tr in [True, False]:
                res = simulate_catalyst(target_rr=rr, be_trail_r=trail, rvol_min=rvol, require_daily_trend=d_tr)
                if res:
                    print(f"RR: {res['Target_RR']} | Trail: {res['Trail']} | RVOL: {res['RVOL']} | DTrend: {res['DailyTrend']} -> Trades: {res['Trades']:4d} | WR: {res['WinRate']}% | PF: {res['ProfitFactor']} | Net R: {res['Total_Net_R']:+6.1f} R | Mo: {res['Monthly_Net_R']:+5.2f} R/mo | DD: {res['Max_DD']} R", flush=True)
                    matrix_res.append(res)

if matrix_res:
    df_mat = pd.DataFrame(matrix_res).sort_values('Total_Net_R', ascending=False)
    print("\n" + "="*115, flush=True)
    print("TOP 10 CONFIGURATIONS RANKED BY NET R (ZERO LOOKAHEAD, NO OVERLAPS)", flush=True)
    print("="*115, flush=True)
    print(df_mat.head(10).to_string(index=False), flush=True)
