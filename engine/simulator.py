import pandas as pd
import numpy as np
from datetime import time

def simulate_trade(signal, day_df, slippage_pct=0.0004):
    """
    Simulates a single trade against 5-minute candles of that day.
    Applies realistic bid/ask slippage and commissions: 0.04% round-trip.
    Enforces 15:15 PM mandatory intraday square-off.
    """
    direction = signal['Direction']
    entry_idx = signal['EntryIndex']
    entry_price_raw = signal['EntryPrice']
    sl_dist = signal['SL_Dist']
    
    # Slippage adjustment on entry
    if direction == 'BUY':
        entry_price = entry_price_raw * (1.0 + slippage_pct / 2.0)
    else:
        entry_price = entry_price_raw * (1.0 - slippage_pct / 2.0)
        
    sl_price = signal['StopLoss']
    tp_price = signal['TakeProfit']
    target_r = (tp_price - entry_price_raw) / sl_dist if direction == 'BUY' else (entry_price_raw - tp_price) / sl_dist

    # Forward iterate candles
    exit_price = None
    exit_time = None
    exit_reason = None
    r_achieved = None
    be_active = False

    candles = day_df.iloc[entry_idx + 1:].reset_index(drop=True)
    if len(candles) == 0:
        return None

    for idx, c in candles.iterrows():
        c_time = c['Time']
        c_open = c['Open']
        c_high = c['High']
        c_low = c['Low']
        c_close = c['Close']

        # Breakeven trailing check: if profit reached +1.5R, move SL to breakeven
        if direction == 'BUY':
            if not be_active and (c_high - entry_price) / sl_dist >= 1.5:
                be_active = True
                sl_price = entry_price + (sl_dist * 0.1) # lock small buffer for brokerage

            # Check SL
            if c_low <= sl_price:
                exit_price = sl_price * (1.0 - slippage_pct / 2.0)
                exit_time = c_time
                exit_reason = 'STOP_LOSS' if not be_active else 'BREAKEVEN'
                r_achieved = (exit_price - entry_price) / sl_dist
                break

            # Check TP
            if c_high >= tp_price:
                exit_price = tp_price * (1.0 - slippage_pct / 2.0)
                exit_time = c_time
                exit_reason = 'TAKE_PROFIT'
                r_achieved = (exit_price - entry_price) / sl_dist
                break

        else: # SELL
            if not be_active and (entry_price - c_low) / sl_dist >= 1.5:
                be_active = True
                sl_price = entry_price - (sl_dist * 0.1)

            # Check SL
            if c_high >= sl_price:
                exit_price = sl_price * (1.0 + slippage_pct / 2.0)
                exit_time = c_time
                exit_reason = 'STOP_LOSS' if not be_active else 'BREAKEVEN'
                r_achieved = (entry_price - exit_price) / sl_dist
                break

            # Check TP
            if c_low <= tp_price:
                exit_price = tp_price * (1.0 + slippage_pct / 2.0)
                exit_time = c_time
                exit_reason = 'TAKE_PROFIT'
                r_achieved = (entry_price - exit_price) / sl_dist
                break

        # Mandatory Intraday Square-off at or after 15:15 PM
        if c_time >= time(15, 15):
            exit_price = c_close * (1.0 - slippage_pct / 2.0) if direction == 'BUY' else c_close * (1.0 + slippage_pct / 2.0)
            exit_time = c_time
            exit_reason = 'EOD_SQUAREOFF'
            r_achieved = (exit_price - entry_price) / sl_dist if direction == 'BUY' else (entry_price - exit_price) / sl_dist
            break

    if exit_reason is None:
        last_c = candles.iloc[-1]
        exit_price = last_c['Close']
        exit_time = last_c['Time']
        exit_reason = 'EOD_CLOSE'
        r_achieved = (exit_price - entry_price) / sl_dist if direction == 'BUY' else (entry_price - exit_price) / sl_dist

    return {
        'Timestamp': signal['Timestamp'],
        'Date': signal['Date'],
        'EntryTime': signal['Time'],
        'ExitTime': exit_time,
        'Symbol': signal['Symbol'],
        'IsIndex': signal['IsIndex'],
        'Direction': signal['Direction'],
        'Setup': signal['Setup'],
        'EntryPrice': round(entry_price, 2),
        'StopLoss': round(sl_price, 2),
        'TakeProfit': round(tp_price, 2),
        'ExitPrice': round(exit_price, 2),
        'ExitReason': exit_reason,
        'R_Multiple': round(r_achieved, 2),
        'Win': r_achieved > 0
    }
