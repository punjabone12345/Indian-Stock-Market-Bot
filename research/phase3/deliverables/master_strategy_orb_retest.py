"""
INSTITUTIONAL MASTER STRATEGY: OPENING RANGE SUPPORT/RESISTANCE RETEST
Pure NSE Cash Equities (Intraday MIS) - 100% Zero Derivatives

Trading Rules:
1. Universe: Top 50 Liquid NSE Cash Equities (Turnover > Rs 500 Cr/day)
2. Opening Range: First 15 minutes (09:15 - 09:30 IST)
3. Volume Filter: Opening Range Volume >= 1.5x of 20-day average opening range volume
4. Breakout Confirmation: Price must break above OR High (Bullish) or below OR Low (Bearish)
5. Retest Entry: Limit order placed at the broken OR High (now support) or OR Low (now resistance)
6. Stop Loss: Placed at the 15-minute Opening Range Midpoint
7. Targets:
   - Partial Exit 1 (50% size): 2.0R
   - Runner Exit 2 (50% size): 3.5R with breakeven trailing stop
8. Time-Stop: Mandatory hard market square-off at 15:15 IST
"""

import numpy as np
import pandas as pd

def compute_zerodha_charges(buy_val, sell_val):
    b = min(20.0, buy_val * 0.0003) + min(20.0, sell_val * 0.0003)
    stt = sell_val * 0.00025
    exchange = (buy_val + sell_val) * 0.0000297
    sebi = (buy_val + sell_val) * 0.000001
    stamp = buy_val * 0.00003
    gst = (b + exchange + sebi) * 0.18
    return b + stt + exchange + sebi + stamp + gst

def check_orb_retest_signal(bar_5m_list, or_high, or_low, or_mid, or_rvol, side='BUY'):
    """
    Checks if a 5m bar confirms a retest bounce off the 15m opening range boundary.
    """
    if or_rvol < 1.5: return None
    
    # Needs at least 2 bars after 09:30
    if len(bar_5m_list) < 2: return None
    prev_bar = bar_5m_list[-2]
    curr_bar = bar_5m_list[-1]
    
    if side == 'BUY':
        # Prior bar was above OR high, current bar tests OR high and closes above it and VWAP
        if prev_bar['High'] > or_high and curr_bar['Low'] <= or_high and curr_bar['Close'] >= or_high:
            if curr_bar['Close'] > curr_bar['vwap']:
                entry_p = or_high
                sl_p = or_mid
                risk_pts = abs(entry_p - sl_p)
                return {
                    'side': 'BUY',
                    'entry_price': entry_p,
                    'stop_loss': sl_p,
                    'target_1': entry_p + (2.0 * risk_pts),
                    'target_2': entry_p + (3.5 * risk_pts),
                    'risk_pts': risk_pts
                }
    else:
        # Prior bar was below OR low, current bar tests OR low and closes below it and VWAP
        if prev_bar['Low'] < or_low and curr_bar['High'] >= or_low and curr_bar['Close'] <= or_low:
            if curr_bar['Close'] < curr_bar['vwap']:
                entry_p = or_low
                sl_p = or_mid
                risk_pts = abs(entry_p - sl_p)
                return {
                    'side': 'SELL',
                    'entry_price': entry_p,
                    'stop_loss': sl_p,
                    'target_1': entry_p - (2.0 * risk_pts),
                    'target_2': entry_p - (3.5 * risk_pts),
                    'risk_pts': risk_pts
                }
    return None
