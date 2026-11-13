import pandas as pd
import numpy as np
from datetime import time

def compute_indicators(df_5m):
    df = df_5m.copy().sort_values('Timestamp').reset_index(drop=True)
    
    # 1. EMAs
    df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()

    # 2. ATR
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['ATR14'] = tr.rolling(14).mean()

    # 3. Intraday VWAP & Day Levels (calculated per day)
    df['TypPrice'] = (df['High'] + df['Low'] + df['Close']) / 3.0
    df['PV'] = df['TypPrice'] * df['Volume']
    
    # Group by date for VWAP and Previous Day levels
    daily_groups = df.groupby('Date')
    
    df['CumPV'] = daily_groups['PV'].cumsum()
    df['CumVol'] = daily_groups['Volume'].cumsum()
    df['VWAP'] = df['CumPV'] / df['CumVol']

    # Previous Day High / Low / Close
    day_summary = daily_groups.agg({
        'High': 'max',
        'Low': 'min',
        'Close': 'last'
    }).rename(columns={'High': 'PDH', 'Low': 'PDL', 'Close': 'PDC'})
    day_summary = day_summary.shift(1)  # Prior day

    df = df.merge(day_summary, on='Date', how='left')

    # Opening Range (09:15-09:20 candle is the first candle of the day)
    first_candles = df[df['Time'] == time(9, 15)].set_index('Date')
    df['OR_High'] = df['Date'].map(first_candles['High'])
    df['OR_Low'] = df['Date'].map(first_candles['Low'])

    return df

def generate_signals(df):
    """
    Scans for high-quality institutional setups:
    1. Liquidity Sweeps of OR_High/OR_Low or PDH/PDL with displacement & FVG
    2. High-momentum VWAP trend pullbacks
    """
    signals = []
    
    # Loop day by day
    for dt, group in df.groupby('Date'):
        trades_today = 0
        group = group.reset_index(drop=True)
        if len(group) < 10:
            continue
            
        is_index = group['IsIndex'].iloc[0]
        min_sl_pct = 0.0025 if is_index else 0.0050  # 0.25% for index, 0.50% for stocks
        symbol = group['Symbol'].iloc[0]

        for i in range(2, len(group) - 2):
            row = group.iloc[i]
            prev = group.iloc[i-1]
            prev2 = group.iloc[i-2]

            # Rule: Strictly after 09:20 AM and before 14:30 PM for entry
            if row['Time'] <= time(9, 20) or row['Time'] > time(14, 30):
                continue

            # Skip if we already took max 2 trades on this symbol today
            if trades_today >= 2:
                continue

            current_close = row['Close']
            vwap = row['VWAP']
            ema9 = row['EMA9']
            ema21 = row['EMA21']
            ema50 = row['EMA50']
            pdh = row['PDH']
            pdl = row['PDL']
            or_h = row['OR_High']
            or_l = row['OR_Low']

            # SETUP 1: BULLISH LIQUIDITY SWEEP (Sweeps OR_Low or PDL, rejects, shifts above VWAP/EMA9)
            sweep_low = False
            ref_low = None
            if pd.notna(pdl) and (prev['Low'] < pdl or row['Low'] < pdl) and row['Close'] > pdl:
                sweep_low = True
                ref_low = pdl
            elif pd.notna(or_l) and (prev['Low'] < or_l or row['Low'] < or_l) and row['Close'] > or_l:
                sweep_low = True
                ref_low = or_l

            if sweep_low and row['Close'] > ema9 and row['Close'] >= row['Open']:
                # Valid Bullish Reversal Signal
                entry_price = row['Close']
                # SL placed below the recent swing low
                swing_low = min(row['Low'], prev['Low'])
                raw_sl_dist = entry_price - swing_low
                min_sl_dist = entry_price * min_sl_pct
                sl_dist = max(raw_sl_dist, min_sl_dist)
                sl_price = entry_price - sl_dist
                
                # Target: 1:2.8 Risk:Reward
                tp_dist = sl_dist * 2.8
                tp_price = entry_price + tp_dist

                signals.append({
                    'Timestamp': row['Timestamp'],
                    'Date': dt,
                    'Time': row['Time'],
                    'Symbol': symbol,
                    'IsIndex': is_index,
                    'Direction': 'BUY',
                    'Setup': 'Liquidity Sweep Reversal',
                    'EntryIndex': i,
                    'EntryPrice': entry_price,
                    'StopLoss': sl_price,
                    'TakeProfit': tp_price,
                    'SL_Dist': sl_dist,
                    'MinSL_Applied': sl_dist == min_sl_dist
                })
                trades_today += 1
                continue

            # SETUP 2: BEARISH LIQUIDITY SWEEP (Sweeps OR_High or PDH, rejects, shifts below VWAP/EMA9)
            sweep_high = False
            ref_high = None
            if pd.notna(pdh) and (prev['High'] > pdh or row['High'] > pdh) and row['Close'] < pdh:
                sweep_high = True
                ref_high = pdh
            elif pd.notna(or_h) and (prev['High'] > or_h or row['High'] > or_h) and row['Close'] < or_h:
                sweep_high = True
                ref_high = or_h

            if sweep_high and row['Close'] < ema9 and row['Close'] <= row['Open']:
                # Valid Bearish Reversal Signal
                entry_price = row['Close']
                swing_high = max(row['High'], prev['High'])
                raw_sl_dist = swing_high - entry_price
                min_sl_dist = entry_price * min_sl_pct
                sl_dist = max(raw_sl_dist, min_sl_dist)
                sl_price = entry_price + sl_dist
                
                # Target: 1:2.8 Risk:Reward
                tp_dist = sl_dist * 2.8
                tp_price = entry_price - tp_dist

                signals.append({
                    'Timestamp': row['Timestamp'],
                    'Date': dt,
                    'Time': row['Time'],
                    'Symbol': symbol,
                    'IsIndex': is_index,
                    'Direction': 'SELL',
                    'Setup': 'Liquidity Sweep Reversal',
                    'EntryIndex': i,
                    'EntryPrice': entry_price,
                    'StopLoss': sl_price,
                    'TakeProfit': tp_price,
                    'SL_Dist': sl_dist,
                    'MinSL_Applied': sl_dist == min_sl_dist
                })
                trades_today += 1
                continue

            # SETUP 3: VWAP TREND CONTINUATION (Midday trend impulse)
            # Long Trend: EMA9 > EMA21 > EMA50, Close > VWAP
            if ema9 > ema21 > ema50 and current_close > vwap:
                # Pullback into VWAP / EMA21 with green candle close
                if prev['Low'] <= ema21 * 1.001 and row['Close'] > ema9 and row['Close'] > row['Open']:
                    entry_price = row['Close']
                    swing_low = min(row['Low'], prev['Low'])
                    raw_sl_dist = entry_price - swing_low
                    min_sl_dist = entry_price * min_sl_pct
                    sl_dist = max(raw_sl_dist, min_sl_dist)
                    sl_price = entry_price - sl_dist
                    tp_dist = sl_dist * 2.6
                    tp_price = entry_price + tp_dist

                    signals.append({
                        'Timestamp': row['Timestamp'],
                        'Date': dt,
                        'Time': row['Time'],
                        'Symbol': symbol,
                        'IsIndex': is_index,
                        'Direction': 'BUY',
                        'Setup': 'VWAP Trend Continuation',
                        'EntryIndex': i,
                        'EntryPrice': entry_price,
                        'StopLoss': sl_price,
                        'TakeProfit': tp_price,
                        'SL_Dist': sl_dist,
                        'MinSL_Applied': sl_dist == min_sl_dist
                    })
                    trades_today += 1
                    continue

            # Short Trend: EMA9 < EMA21 < EMA50, Close < VWAP
            if ema9 < ema21 < ema50 and current_close < vwap:
                if prev['High'] >= ema21 * 0.999 and row['Close'] < ema9 and row['Close'] < row['Open']:
                    entry_price = row['Close']
                    swing_high = max(row['High'], prev['High'])
                    raw_sl_dist = swing_high - entry_price
                    min_sl_dist = entry_price * min_sl_pct
                    sl_dist = max(raw_sl_dist, min_sl_dist)
                    sl_price = entry_price + sl_dist
                    tp_dist = sl_dist * 2.6
                    tp_price = entry_price - tp_dist

                    signals.append({
                        'Timestamp': row['Timestamp'],
                        'Date': dt,
                        'Time': row['Time'],
                        'Symbol': symbol,
                        'IsIndex': is_index,
                        'Direction': 'SELL',
                        'Setup': 'VWAP Trend Continuation',
                        'EntryIndex': i,
                        'EntryPrice': entry_price,
                        'StopLoss': sl_price,
                        'TakeProfit': tp_price,
                        'SL_Dist': sl_dist,
                        'MinSL_Applied': sl_dist == min_sl_dist
                    })
                    trades_today += 1
                    continue

    return pd.DataFrame(signals)
