import sys
sys.path.append('engine')
import os
import pandas as pd
import numpy as np
from datetime import time
from nifty_alpha_explorer import load_nifty_fast
from nifty_aligned_ema_atr_sweep import load_stock_data

print("="*95)
print("FAST AUDIT OF DEPLOYED LIVE APP STRATEGY (2022-2026)")
print("Strict Candle-by-Candle | Zero Lookahead | Exact Zerodha Tariff")
print("="*95)

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

print("Loading Nifty 50...")
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

# Pre-aggregate each stock into a dict keyed by (date, time)
print("Loading 14 stocks into fast memory lookup...")
candles_by_time = {} # {ts: [(sym, o, h, l, c, vwap, ema9, ema21, atr, nifty_trend), ...]}
all_dates = set()

for sym in TOP_14_SYMBOLS:
    df_1m = load_stock_data(sym)
    if df_1m is None or len(df_1m) < 1000: continue
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
    
    ts_list = df_5m['Timestamp'].values
    opens = df_5m['Open'].values
    highs = df_5m['High'].values
    lows = df_5m['Low'].values
    closes = df_5m['Close'].values
    vwaps = df_5m['VWAP'].values
    ema9s = df_5m['EMA9'].values
    ema21s = df_5m['EMA21'].values
    atrs = df_5m['ATR'].values
    ntrends = df_5m['Nifty_Trend'].values
    
    for k in range(len(df_5m)):
        t_stamp = ts_list[k]
        if t_stamp not in candles_by_time:
            candles_by_time[t_stamp] = []
        candles_by_time[t_stamp].append((
            sym, opens[k], highs[k], lows[k], closes[k],
            vwaps[k], ema9s[k], ema21s[k], atrs[k], ntrends[k]
        ))

sorted_timestamps = sorted(candles_by_time.keys())
print(f"Loaded {len(sorted_timestamps)} distinct 5m timestamps.")

base_risk = 200.0
target_rr = 2.0
max_open_pos = 14

peak_r = 0.0
cum_r = 0.0
governor_mode = "NORMAL"
governor_mult = 1.0

active_positions = {}
symbol_daily_trades = {}
current_date = None
closed_trades = []

print("Running fast portfolio execution...")

for ts in sorted_timestamps:
    dt = pd.to_datetime(ts).date()
    t = pd.to_datetime(ts).time()
    
    if dt != current_date:
        current_date = dt
        symbol_daily_trades = {s: 0 for s in TOP_14_SYMBOLS}
        
    bar_tuples = candles_by_time[ts]
    # Map by symbol for O(1) lookup
    bar_map = {b[0]: b for b in bar_tuples}
    
    # 1. Update active positions
    to_remove = []
    for sym, pos in active_positions.items():
        if sym not in bar_map: continue
        b = bar_map[sym]
        h = b[2]; l = b[3]; c = b[4]
        direction = pos['direction']
        entry_p = pos['entry_price']
        sl = pos['stop_loss']
        tp = pos['take_profit']
        qty = pos['quantity']
        
        exit_p = None
        exit_reason = None
        
        if t >= time(15, 0):
            exit_p = c; exit_reason = 'EOD_AUTO_SQUAREOFF_3PM'
        elif direction == 'BUY':
            if l <= sl:
                exit_p = sl; exit_reason = 'STOP_LOSS_HIT'
            elif h >= tp:
                exit_p = tp; exit_reason = 'TARGET_REACHED'
        else:
            if h >= sl:
                exit_p = sl; exit_reason = 'STOP_LOSS_HIT'
            elif l <= tp:
                exit_p = tp; exit_reason = 'TARGET_REACHED'
                
        if exit_p is not None:
            charges = calc_statutory_charges(entry_p, exit_p, qty, direction)
            gross_pnl = (exit_p - entry_p) * qty if direction == 'BUY' else (entry_p - exit_p) * qty
            net_pnl = round(gross_pnl - charges, 2)
            realized_r = round(net_pnl / base_risk, 2)
            
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
        
    if t < time(9, 20) or t > time(14, 45):
        continue
        
    for b in bar_tuples:
        sym = b[0]
        if sym in active_positions: continue
        if len(active_positions) >= max_open_pos: continue
        if symbol_daily_trades.get(sym, 0) >= 2: continue
        
        op = b[1]; hi = b[2]; lo = b[3]; cl = b[4]
        vwap = b[5]; ema9 = b[6]; ema21 = b[7]; atr = b[8]; nifty_trend = b[9]
        
        is_bullish_trend = (nifty_trend == 1) and (cl > vwap) and (ema9 > ema21)
        is_bearish_trend = (nifty_trend == -1) and (cl < vwap) and (ema9 < ema21)
        
        signal_ready = False
        direction = None
        sl = None; tp = None; sl_dist = 0.0
        
        if is_bullish_trend:
            ema_pullback_zone = ema9 * 1.0020
            if lo <= ema_pullback_zone:
                confirmed = (cl > op) and (cl >= ema9 * 0.9990)
                price_in_range = cl <= (ema9 + max(0.6 * atr, ema9 * 0.0060))
                if confirmed and price_in_range:
                    raw_sl = lo - (0.2 * atr)
                    sl_dist = cl - raw_sl
                    sl_dist = max(sl_dist, cl * 0.0050)
                    sl_dist = min(sl_dist, cl * 0.0100)
                    sl = round(cl - sl_dist, 2)
                    tp = round(cl + (sl_dist * target_rr), 2)
                    signal_ready = True
                    direction = 'BUY'
        elif is_bearish_trend:
            ema_pullback_zone = ema9 * 0.9980
            if hi >= ema_pullback_zone:
                confirmed = (cl < op) and (cl <= ema9 * 1.0010)
                price_in_range = cl >= (ema9 - max(0.6 * atr, ema9 * 0.0060))
                if confirmed and price_in_range:
                    raw_sl = hi + (0.2 * atr)
                    sl_dist = raw_sl - cl
                    sl_dist = max(sl_dist, cl * 0.0050)
                    sl_dist = min(sl_dist, cl * 0.0100)
                    sl = round(cl + sl_dist, 2)
                    tp = round(cl - (sl_dist * target_rr), 2)
                    signal_ready = True
                    direction = 'SELL'
                    
        if signal_ready:
            eff_risk = base_risk * governor_mult
            qty = max(1, int(eff_risk / sl_dist))
            active_positions[sym] = {
                'symbol': sym, 'direction': direction, 'entry_price': cl,
                'stop_loss': sl, 'take_profit': tp, 'quantity': qty,
                'sl_dist': sl_dist, 'governor_mode': governor_mode
            }
            symbol_daily_trades[sym] = symbol_daily_trades.get(sym, 0) + 1

df_res = pd.DataFrame(closed_trades)
df_res.to_parquet('reports/deployed_strategy_full_audit.parquet')

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

print("\n" + "="*95)
print("DEPLOYED LIVE APP STRATEGY AUDIT RESULTS (FULL 2022-2026)")
print("="*95)
print(f"Total Portfolio Trades       : {tot_trades:,} (~{tot_trades/num_mo:.1f} trades/month across 14 stocks)")
print(f"Wins / Losses                : {len(wins):,} Wins / {len(losses):,} Losses")
print(f"Net Win Rate                 : {wr:.2f}%")
print(f"Profit Factor                : {pf:.2f}")
print(f"Total Statutory Taxes Paid   : Rs {tot_tax:,.2f} ({tot_tax/base_risk:,.1f} R)")
print(f"Total Net PnL (Rs 200 Base)  : Rs {tot_pnl:,.2f}")
print(f"Total Net R (4.8 Years)      : {tot_r:+,.2f} R")
print(f"Average Monthly Net R        : {mo_r:+,.2f} R / month")
print(f"Average Monthly Net PnL      : Rs {mo_pnl:+,.2f} / month")
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
