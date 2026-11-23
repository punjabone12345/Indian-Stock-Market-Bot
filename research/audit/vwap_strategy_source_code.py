"""
STANDALONE REPRODUCIBLE STRATEGY CODE: VWAP PULLBACK RETEST (PURE CASH EQUITIES)
Strategy Family: Intraday VWAP Accumulation with 15-Minute Structural Invalidation
Execution: NSE Equity Cash MIS (Zero F&O, 100% SEBI Compliant)
Cost Model: Exact Zerodha Intraday Statutory Model
"""

import os
import numpy as np
import pandas as pd
from datetime import time as dtime

def compute_zerodha_charges(buy_val, sell_val):
    """Computes exact Zerodha intraday cash charges including taxes and turnover fees."""
    brokerage = min(20.0, buy_val * 0.0003) + min(20.0, sell_val * 0.0003)
    stt = sell_val * 0.00025 # 0.025% on sell side in cash equity intraday
    exchange = (buy_val + sell_val) * 0.0000297
    sebi = (buy_val + sell_val) * 0.000001
    stamp = buy_val * 0.00003
    gst = (brokerage + exchange + sebi) * 0.18
    return brokerage + stt + exchange + sebi + stamp + gst

def evaluate_vwap_pullback_session(d_df, prev_close, avg_prior_or_vol, risk_cash=1000.0):
    """
    Evaluates a single day's 5-minute bars for the VWAP Pullback Retest strategy.
    
    ENTRY LOGIC:
    1. Filter: 15-minute Opening Range Volume (RVOL) >= 1.5x of 20-day historical average.
    2. Trend Direction: 
       - Bullish Setup if 09:30 AM close > 09:15 AM open.
       - Bearish Setup if 09:30 AM close < 09:15 AM open.
    3. Trigger Window: 09:30 AM to 10:45 AM (Bars 3 to 18).
    4. Confirmation:
       - Bullish: 5-minute bar dips below or touches VWAP (Low <= VWAP) and closes back above VWAP (Close >= VWAP).
       - Bearish: 5-minute bar spikes above or touches VWAP (High >= VWAP) and closes back below VWAP (Close <= VWAP).
    5. Entry Price: Executed at VWAP price level.
    
    EXIT & RISK LOGIC:
    1. Initial Stop Loss: Midpoint of the 15-minute Opening Range ((High15 + Low15) / 2).
    2. Structural Risk Bounds: Minimum risk capped at 0.35% of price; maximum risk capped at 1.00% of price.
    3. Target 1 (Partial 50% Profit): +2.0R.
    4. Target 2 (Runner): +3.5R.
    5. Intraday Exit Time: 15:15 PM (Bar 72) mandatory square-off before market close.
    """
    if len(d_df) < 25:
        return None
        
    c15 = d_df.iloc[0:3]
    open_15m = c15.iloc[0]['Open']
    high_15m = c15['High'].max()
    low_15m = c15['Low'].min()
    close_15m = c15.iloc[-1]['Close']
    vol_15m = c15['Volume'].sum()
    mid_15m = (high_15m + low_15m) / 2.0
    
    rvol = vol_15m / avg_prior_or_vol if avg_prior_or_vol > 0 else 1.0
    if rvol < 1.5:
        return None
        
    side = 'BUY' if close_15m > open_15m else 'SELL'
    entry_p = None
    b_idx = None
    
    if side == 'BUY':
        for i in range(3, min(18, len(d_df) - 6)):
            bar = d_df.iloc[i]
            if bar['Low'] <= bar['vwap'] and bar['Close'] >= bar['vwap']:
                entry_p = bar['vwap']
                b_idx = i
                break
    else:
        for i in range(3, min(18, len(d_df) - 6)):
            bar = d_df.iloc[i]
            if bar['High'] >= bar['vwap'] and bar['Close'] <= bar['vwap']:
                entry_p = bar['vwap']
                b_idx = i
                break
                
    if entry_p is None:
        return None
        
    risk_pts = max(entry_p * 0.0035, min(entry_p * 0.010, abs(entry_p - mid_15m)))
    sl_p = entry_p - risk_pts if side == 'BUY' else entry_p + risk_pts
    t1_p = entry_p + (2.0 * risk_pts) if side == 'BUY' else entry_p - (2.0 * risk_pts)
    t2_p = entry_p + (3.5 * risk_pts) if side == 'BUY' else entry_p - (3.5 * risk_pts)
    
    shares = int(risk_cash / risk_pts)
    if shares < 1: shares = 1
    s_t1 = int(shares * 0.50)
    s_run = shares - s_t1
    if s_t1 < 1: s_t1 = 1
    
    t1_hit = False
    curr_sl = sl_p
    exit_p1, exit_pr = 0.0, 0.0
    exit_reason = ""
    exit_b = len(d_df) - 1
    
    for j in range(b_idx + 1, len(d_df)):
        bar = d_df.iloc[j]
        h, l, c = bar['High'], bar['Low'], bar['Close']
        if side == 'BUY':
            if l <= curr_sl:
                if not t1_hit: exit_p1, exit_pr = curr_sl, curr_sl; exit_reason = "STOP_LOSS"
                else: exit_pr = curr_sl; exit_reason = "T1_THEN_SL"
                exit_b = j; break
            if not t1_hit and h >= t1_p:
                t1_hit = True; exit_p1 = t1_p
            if t1_hit and h >= t2_p:
                exit_pr = t2_p; exit_reason = "FULL_TARGET_2"; exit_b = j; break
            if j == len(d_df) - 1 or j >= 72:
                if not t1_hit: exit_p1 = c; exit_reason = "EOD_CLOSE"
                else: exit_reason = "T1_THEN_EOD"
                exit_pr = c; exit_b = j; break
        else:
            if h >= curr_sl:
                if not t1_hit: exit_p1, exit_pr = curr_sl, curr_sl; exit_reason = "STOP_LOSS"
                else: exit_pr = curr_sl; exit_reason = "T1_THEN_SL"
                exit_b = j; break
            if not t1_hit and l <= t1_p:
                t1_hit = True; exit_p1 = t1_p
            if t1_hit and l <= t2_p:
                exit_pr = t2_p; exit_reason = "FULL_TARGET_2"; exit_b = j; break
            if j == len(d_df) - 1 or j >= 72:
                if not t1_hit: exit_p1 = c; exit_reason = "EOD_CLOSE"
                else: exit_reason = "T1_THEN_EOD"
                exit_pr = c; exit_b = j; break
                
    if side == 'BUY':
        gp1 = s_t1 * (exit_p1 - entry_p)
        gpr = s_run * (exit_pr - entry_p) if s_run > 0 else 0
        fee1 = compute_zerodha_charges(s_t1 * entry_p, s_t1 * exit_p1)
        feer = compute_zerodha_charges(s_run * entry_p, s_run * exit_pr) if s_run > 0 else 0
    else:
        gp1 = s_t1 * (entry_p - exit_p1)
        gpr = s_run * (entry_p - exit_pr) if s_run > 0 else 0
        fee1 = compute_zerodha_charges(s_t1 * exit_p1, s_t1 * entry_p)
        feer = compute_zerodha_charges(s_run * exit_pr, s_run * entry_p) if s_run > 0 else 0
        
    net_pnl = gp1 + gpr - fee1 - feer
    return {
        'side': side,
        'entry_time': d_df.iloc[b_idx]['time_str'],
        'entry_price': entry_p,
        'sl_price': sl_p,
        't1_price': t1_p,
        't2_price': t2_p,
        'exit_time': d_df.iloc[exit_b]['time_str'],
        'exit_reason': exit_reason,
        'holding_minutes': (exit_b - b_idx) * 5,
        'gross_pnl': gp1 + gpr,
        'total_fee': fee1 + feer,
        'net_pnl': net_pnl,
        'r_multiple': net_pnl / risk_cash
    }
