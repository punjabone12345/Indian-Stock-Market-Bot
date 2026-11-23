import sys
sys.path.append('engine')
import os
import glob
import pandas as pd
import numpy as np
import datetime
from datetime import time
from nifty_alpha_explorer import load_nifty_fast
from nifty_aligned_ema_atr_sweep import load_stock_data

print("="*95, flush=True)
print("AUDITING THE EXACT STRATEGY DEPLOYED IN THE APP (2022-2026)", flush=True)
print("14 Champion Stocks | Strict Candle-by-Candle | Exact Rules from backend/trade_engine.py", flush=True)
print("="*95, flush=True)

TOP_14_SYMBOLS = [
    'RELIANCE', 'INDUSINDBK', 'LT', 'ADANIENT', 'TATAMOTORS', 
    'SUNPHARMA', 'WIPRO', 'JSWSTEEL', 'TATASTEEL', 'BAJFINANCE', 
    'SBIN', 'ONGC', 'TCS', 'MARUTI'
]

def calc_statutory_charges(entry_price: float, exit_price: float, qty: int, direction: str = 'BUY') -> float:
    entry_p = float(entry_price)
    exit_p = float(exit_price)
    q = int(qty)
    if direction == 'BUY':
        buy_val = round(entry_p * q, 2)
        sell_val = round(exit_p * q, 2)
    else:
        buy_val = round(exit_p * q, 2)
        sell_val = round(entry_p * q, 2)
    turnover = round(buy_val + sell_val, 2)
    
    buy_brok = min(20.0, round(buy_val * 0.0003, 2))
    sell_brok = min(20.0, round(sell_val * 0.0003, 2))
    brokerage = round(buy_brok + sell_brok, 2)
    stt = round(sell_val * 0.00025, 2)
    exch_fees = round(turnover * 0.0000297, 2)
    sebi_fees = round(turnover * 0.000001, 2)
    stamp_duty = round(buy_val * 0.00003, 2)
    gst = round((brokerage + exch_fees + sebi_fees) * 0.18, 2)
    slippage = round(q * 0.05, 2)
    return round(brokerage + stt + exch_fees + sebi_fees + stamp_duty + gst + slippage, 2)

print("Loading Nifty 50 1m data...", flush=True)
nifty_1m = load_nifty_fast()
df_nifty_5m = nifty_1m.set_index('Timestamp').resample('5min', origin='start_day', offset='15min').agg({
    'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'
}).dropna().reset_index()

df_nifty_5m['EMA9'] = df_nifty_5m['Close'].ewm(span=9, adjust=False).mean()
df_nifty_5m['EMA21'] = df_nifty_5m['Close'].ewm(span=21, adjust=False).mean()
df_nifty_5m['Nifty_Trend'] = np.where(
    (df_nifty_5m['EMA9'] > df_nifty_5m['EMA21']) & (df_nifty_5m['Close'] > df_nifty_5m['EMA21']), 1,
    np.where((df_nifty_5m['EMA9'] < df_nifty_5m['EMA21']) & (df_nifty_5m['Close'] < df_nifty_5m['EMA21']), -1, 0)
)
nifty_trend_map = dict(zip(df_nifty_5m['Timestamp'], df_nifty_5m['Nifty_Trend']))

print("Loading and preparing 14 Champion stocks...", flush=True)
stock_data = {}
for sym in TOP_14_SYMBOLS:
    df_1m = load_stock_data(sym)
    if df_1m is None or len(df_1m) < 1000:
        print(f"Warning: Missing data for {sym}")
        continue
    df_5m = df_1m.set_index('Timestamp').resample('5min', origin='start_day', offset='15min').agg({
        'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'
    }).dropna().reset_index()
    
    df_5m['Date'] = df_5m['Timestamp'].dt.date
    df_5m['Time'] = df_5m['Timestamp'].dt.time
    df_5m['EMA9'] = df_5m['Close'].ewm(span=9, adjust=False).mean()
    df_5m['EMA21'] = df_5m['Close'].ewm(span=21, adjust=False).mean()
    
    df_5m['Typ'] = (df_5m['High'] + df_5m['Low'] + df_5m['Close']) / 3.0
    df_5m['PV'] = df_5m['Typ'] * df_5m['Volume']
    df_5m['VWAP'] = df_5m.groupby('Date')['PV'].cumsum() / df_5m.groupby('Date')['Volume'].cumsum()
    
    tr1 = df_5m['High'] - df_5m['Low']
    tr2 = (df_5m['High'] - df_5m['Close'].shift()).abs()
    tr3 = (df_5m['Low'] - df_5m['Close'].shift()).abs()
    df_5m['ATR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14, min_periods=1).mean()
    
    df_5m['Nifty_Trend'] = df_5m['Timestamp'].map(nifty_trend_map).fillna(0).astype(int)
    stock_data[sym] = df_5m

print(f"Successfully loaded {len(stock_data)} stocks.", flush=True)

# Combine all 5m candles chronologically to run a real-time portfolio simulation
all_candles = []
for sym, df_5m in stock_data.items():
    df_sym = df_5m.copy()
    df_sym['Symbol'] = sym
    all_candles.append(df_sym)

master_df = pd.concat(all_candles).sort_values(['Timestamp', 'Symbol']).reset_index(drop=True)
print(f"Total chronological 5m multi-stock events: {len(master_df)}", flush=True)

# SIMULATE THE EXACT LIVE ENGINE
# Dynamic Risk Governor state:
base_risk = 200.0
target_rr = 2.0
capital = 125000.0
max_open_pos = 14

peak_r = 0.0
cum_r = 0.0
governor_mode = "NORMAL"
governor_mult = 1.0

# Track active positions: {sym: pos_dict}
active_positions = {}
symbol_daily_trades = {}
current_date = None

closed_trades = []

# Group by Timestamp to process bar-by-bar across all 14 stocks simultaneously
grouped_timestamps = master_df.groupby('Timestamp')

print("\nRunning candle-by-candle portfolio execution...", flush=True)

for ts, bar_group in grouped_timestamps:
    dt = ts.date()
    t = ts.time()
    
    # New trading day reset
    if dt != current_date:
        current_date = dt
        symbol_daily_trades = {sym: 0 for sym in TOP_14_SYMBOLS}
        
    # 1. First, check SL / TP / EOD triggers for all active positions
    to_remove = []
    for sym, pos in active_positions.items():
        # Find current bar for this symbol
        sym_bar = bar_group[bar_group['Symbol'] == sym]
        if sym_bar.empty: continue
        
        row = sym_bar.iloc[0]
        h = row['High']
        l = row['Low']
        c = row['Close']
        direction = pos['direction']
        entry_p = pos['entry_price']
        sl = pos['stop_loss']
        tp = pos['take_profit']
        qty = pos['quantity']
        
        exit_p = None
        exit_reason = None
        
        # Check EOD cutoff (>= 15:00 IST)
        if t >= time(15, 0):
            exit_p = c
            exit_reason = 'EOD_AUTO_SQUAREOFF_3PM'
        elif direction == 'BUY':
            if l <= sl:
                exit_p = sl
                exit_reason = 'STOP_LOSS_HIT'
            elif h >= tp:
                exit_p = tp
                exit_reason = 'TARGET_REACHED'
        else: # SELL
            if h >= sl:
                exit_p = sl
                exit_reason = 'STOP_LOSS_HIT'
            elif l <= tp:
                exit_p = tp
                exit_reason = 'TARGET_REACHED'
                
        if exit_p is not None:
            charges = calc_statutory_charges(entry_p, exit_p, qty, direction)
            gross_pnl = (exit_p - entry_p) * qty if direction == 'BUY' else (entry_p - exit_p) * qty
            net_pnl = round(gross_pnl - charges, 2)
            realized_r = round(net_pnl / base_risk, 2)
            
            # Update governor
            cum_r += realized_r
            if cum_r > peak_r:
                peak_r = cum_r
            dd = cum_r - peak_r
            
            if governor_mode == "NORMAL" and dd <= -15.0:
                governor_mode = "DEFENSIVE"
                governor_mult = 0.5
            elif governor_mode == "DEFENSIVE" and dd >= -5.0:
                governor_mode = "NORMAL"
                governor_mult = 1.0
                
            closed_trades.append({
                'Date': dt, 'Time': t, 'Symbol': sym, 'Direction': direction,
                'EntryPrice': entry_p, 'ExitPrice': exit_p, 'Qty': qty,
                'ExitReason': exit_reason, 'Charges_INR': charges,
                'Net_PnL': net_pnl, 'Realized_R': realized_r, 'GovernorMode': pos['governor_mode']
            })
            to_remove.append(sym)
            
    for sym in to_remove:
        del active_positions[sym]
        
    # 2. Check for new entries if within entry window (09:15 - 14:45 IST)
    if t < time(9, 20) or t > time(14, 45):
        continue
        
    for _, row in bar_group.iterrows():
        sym = row['Symbol']
        
        # Constraints from trade_engine.py
        if sym in active_positions: continue
        if len(active_positions) >= max_open_pos: continue
        if symbol_daily_trades.get(sym, 0) >= 2: continue
        
        nifty_trend = row['Nifty_Trend']
        cur_p = row['Close']
        vwap = row['VWAP']
        ema9 = row['EMA9']
        ema21 = row['EMA21']
        atr = row['ATR']
        
        # Trends
        is_bullish_trend = (nifty_trend == 1) and (cur_p > vwap) and (ema9 > ema21)
        is_bearish_trend = (nifty_trend == -1) and (cur_p < vwap) and (ema9 < ema21)
        
        signal_ready = False
        direction = None
        sl = None
        tp = None
        sl_dist = 0.0
        
        # BUY
        if is_bullish_trend:
            ema_pullback_zone = ema9 * 1.0020
            # Dip into EMA9 support
            touched_ema9 = (row['Low'] <= ema_pullback_zone)
            if touched_ema9:
                confirmed = (row['Close'] > row['Open']) and (row['Close'] >= ema9 * 0.9990)
                price_in_range = cur_p <= (ema9 + max(0.6 * atr, ema9 * 0.0060))
                if confirmed and price_in_range:
                    raw_sl = row['Low'] - (0.2 * atr)
                    sl_dist = cur_p - raw_sl
                    sl_dist = max(sl_dist, cur_p * 0.0050)
                    sl_dist = min(sl_dist, cur_p * 0.0100)
                    sl = round(cur_p - sl_dist, 2)
                    tp = round(cur_p + (sl_dist * target_rr), 2)
                    signal_ready = True
                    direction = 'BUY'
        # SELL
        elif is_bearish_trend:
            ema_pullback_zone = ema9 * 0.9980
            touched_ema9 = (row['High'] >= ema_pullback_zone)
            if touched_ema9:
                confirmed = (row['Close'] < row['Open']) and (row['Close'] <= ema9 * 1.0010)
                price_in_range = cur_p >= (ema9 - max(0.6 * atr, ema9 * 0.0060))
                if confirmed and price_in_range:
                    raw_sl = row['High'] + (0.2 * atr)
                    sl_dist = raw_sl - cur_p
                    sl_dist = max(sl_dist, cur_p * 0.0050)
                    sl_dist = min(sl_dist, cur_p * 0.0100)
                    sl = round(cur_p + sl_dist, 2)
                    tp = round(cur_p - (sl_dist * target_rr), 2)
                    signal_ready = True
                    direction = 'SELL'
                    
        if signal_ready:
            eff_risk = base_risk * governor_mult
            qty = max(1, int(eff_risk / sl_dist))
            active_positions[sym] = {
                'symbol': sym, 'direction': direction, 'entry_price': cur_p,
                'stop_loss': sl, 'take_profit': tp, 'quantity': qty,
                'sl_dist': sl_dist, 'governor_mode': governor_mode
            }
            symbol_daily_trades[sym] = symbol_daily_trades.get(sym, 0) + 1

print(f"Simulation completed. Total trades executed: {len(closed_trades)}", flush=True)

df_res = pd.DataFrame(closed_trades)
if not df_res.empty:
    df_res['Date'] = pd.to_datetime(df_res['Date'])
    df_res['YM'] = df_res['Date'].dt.to_period('M')
    
    tot_trades = len(df_res)
    wins = df_res[df_res['Realized_R'] > 0]
    losses = df_res[df_res['Realized_R'] <= 0]
    wr = len(wins) / tot_trades * 100
    
    tot_r = df_res['Realized_R'].sum()
    tot_pnl = df_res['Net_PnL'].sum()
    tot_tax = df_res['Charges_INR'].sum()
    
    num_mo = df_res['YM'].nunique()
    mo_r = tot_r / num_mo
    mo_pnl = tot_pnl / num_mo
    
    gw = wins['Realized_R'].sum()
    gl = abs(losses['Realized_R'].sum())
    pf = gw / gl if gl > 0 else 99
    
    daily = df_res.groupby('Date')['Realized_R'].sum()
    cum_daily = daily.cumsum()
    peak_daily = cum_daily.cummax()
    max_dd = (cum_daily - peak_daily).min()
    
    print("\n" + "="*95, flush=True)
    print("DEPLOYED LIVE APP STRATEGY AUDIT RESULTS (FULL 2022-2026)", flush=True)
    print("="*95, flush=True)
    print(f"Total Portfolio Trades       : {tot_trades:,} (~{tot_trades/num_mo:.1f} trades/month across 14 stocks)")
    print(f"Wins / Losses                : {len(wins):,} Wins / {len(losses):,} Losses")
    print(f"Net Win Rate                 : {wr:.2f}%")
    print(f"Profit Factor                : {pf:.2f}")
    print(f"Total Statutory Taxes Paid   : ₹{tot_tax:,.2f} ({tot_tax/base_risk:,.1f} R)")
    print(f"Total Net PnL (₹200 Base)    : ₹{tot_pnl:,.2f}")
    print(f"Total Net R (4.8 Years)      : {tot_r:+,.2f} R")
    print(f"Average Monthly Net R        : {mo_r:+,.2f} R / month")
    print(f"Average Monthly Net PnL      : ₹{mo_pnl:+,.2f} / month")
    print(f"Maximum Peak-to-Trough DD    : {max_dd:.2f} R")
    
    print("\nExit Reason Breakdown:")
    print(df_res['ExitReason'].value_counts().to_string())
    
    print("\nGovernor Mode Trade Breakdown:")
    print(df_res['GovernorMode'].value_counts().to_string())
    
    print("\nPer Symbol Breakdown:")
    sym_summary = []
    for s, grp in df_res.groupby('Symbol'):
        s_tot = len(grp)
        s_w = len(grp[grp['Realized_R'] > 0])
        s_wr = s_w / s_tot * 100
        s_r = grp['Realized_R'].sum()
        s_pnl = grp['Net_PnL'].sum()
        s_tax = grp['Charges_INR'].sum()
        sym_summary.append({
            'Symbol': s, 'Trades': s_tot, 'WinRate': round(s_wr, 1),
            'Net_R': round(s_r, 1), 'Net_PnL': round(s_pnl, 0), 'Taxes_INR': round(s_tax, 0)
        })
    df_sym = pd.DataFrame(sym_summary).sort_values('Net_R', ascending=False)
    print(df_sym.to_string(index=False))
