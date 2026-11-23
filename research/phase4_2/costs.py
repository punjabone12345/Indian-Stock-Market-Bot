"""
PHASE 4.2: INSTITUTIONAL TRANSACTION COSTS & SLIPPAGE ENGINE
Computes statutory transaction charges and execution frictions for NSE Cash Equities (Intraday MIS)
according to official Zerodha / Exchange rate schedules.

Leg-by-Leg Execution Breakdown:
- Leg 1: Entry Order (Limit / Market)
- Leg 2: Target 1 Partial Exit (50% Quantity)
- Leg 3: Target 2 Runner Exit / Stop-Loss / Square-off (Remaining 50% Quantity)

Charge Rates (NSE Equities Intraday):
- Brokerage: Flat 0.03% or Rs 20 per executed order, whichever is lower
- STT (Securities Transaction Tax): 0.025% on Sell Turnover only
- Exchange Turnover Fee (NSE): 0.00297% on Buy + Sell Turnover
- SEBI Charges: Rs 10 per Crore (0.0001%) on Buy + Sell Turnover
- Stamp Duty (Government): 0.003% on Buy Turnover only
- GST (Goods & Services Tax): 18% on (Brokerage + Exchange Fee + SEBI Charges)
- Slippage: Modeled per executed trade leg (default 0.03% on market orders / square-off)
"""

def compute_order_charges(buy_value=0.0, sell_value=0.0):
    """
    Computes exact statutory charges for a single executed order leg.
    """
    turnover = buy_value + sell_value
    if turnover <= 0:
        return {
            'brokerage': 0.0,
            'stt': 0.0,
            'exchange_fee': 0.0,
            'sebi_fee': 0.0,
            'stamp_duty': 0.0,
            'gst': 0.0,
            'total_charges': 0.0
        }
        
    brokerage = min(20.0, turnover * 0.0003)
    stt = sell_value * 0.00025
    exchange_fee = turnover * 0.0000297
    sebi_fee = turnover * 0.0000010
    stamp_duty = buy_value * 0.000030
    gst = (brokerage + exchange_fee + sebi_fee) * 0.18
    total = brokerage + stt + exchange_fee + sebi_fee + stamp_duty + gst
    
    return {
        'brokerage': brokerage,
        'stt': stt,
        'exchange_fee': exchange_fee,
        'sebi_fee': sebi_fee,
        'stamp_duty': stamp_duty,
        'gst': gst,
        'total_charges': total
    }

def compute_trade_costs(side, entry_price, entry_qty, exit1_price, exit1_qty, exit2_price, exit2_qty, slippage_pct=0.0003):
    """
    Computes comprehensive costs across all legs of an intraday bracket trade.
    side: 'BUY' or 'SELL'
    slippage_pct: applied to market orders (entry slippage if market, exit slippage on stop/square-off)
    """
    # 1. Entry Leg
    if side == 'BUY':
        effective_entry_price = entry_price * (1.0 + slippage_pct)
        entry_buy_val = effective_entry_price * entry_qty
        entry_sell_val = 0.0
        entry_slip_cost = (effective_entry_price - entry_price) * entry_qty
    else:
        effective_entry_price = entry_price * (1.0 - slippage_pct)
        entry_buy_val = 0.0
        entry_sell_val = effective_entry_price * entry_qty
        entry_slip_cost = (entry_price - effective_entry_price) * entry_qty
        
    entry_charges = compute_order_charges(entry_buy_val, entry_sell_val)
    
    # 2. Exit Leg 1 (Target 1)
    if exit1_qty > 0:
        if side == 'BUY':
            exit1_buy_val = 0.0
            exit1_sell_val = exit1_price * exit1_qty
            exit1_slip_cost = 0.0 # Limit order fill
        else:
            exit1_buy_val = exit1_price * exit1_qty
            exit1_sell_val = 0.0
            exit1_slip_cost = 0.0
        exit1_charges = compute_order_charges(exit1_buy_val, exit1_sell_val)
    else:
        exit1_charges = compute_order_charges(0.0, 0.0)
        exit1_slip_cost = 0.0
        
    # 3. Exit Leg 2 (Runner / SL / Square-off)
    if exit2_qty > 0:
        # Slippage applies if market order or stop-loss trigger
        if side == 'BUY':
            effective_exit2_price = exit2_price * (1.0 - slippage_pct)
            exit2_buy_val = 0.0
            exit2_sell_val = effective_exit2_price * exit2_qty
            exit2_slip_cost = (exit2_price - effective_exit2_price) * exit2_qty
        else:
            effective_exit2_price = exit2_price * (1.0 + slippage_pct)
            exit2_buy_val = effective_exit2_price * exit2_qty
            exit2_sell_val = 0.0
            exit2_slip_cost = (effective_exit2_price - exit2_price) * exit2_qty
        exit2_charges = compute_order_charges(exit2_buy_val, exit2_sell_val)
    else:
        exit2_charges = compute_order_charges(0.0, 0.0)
        exit2_slip_cost = 0.0
        effective_exit2_price = exit2_price
        
    total_statutory = entry_charges['total_charges'] + exit1_charges['total_charges'] + exit2_charges['total_charges']
    total_slippage = entry_slip_cost + exit1_slip_cost + exit2_slip_cost
    
    # Gross PnL using pure un-slipped prices
    if side == 'BUY':
        gross_pnl = (exit1_price - entry_price) * exit1_qty + (exit2_price - entry_price) * exit2_qty
        # Net PnL after all frictions
        net_pnl = (exit1_price - effective_entry_price) * exit1_qty + (effective_exit2_price - effective_entry_price) * exit2_qty - total_statutory
    else:
        gross_pnl = (entry_price - exit1_price) * exit1_qty + (entry_price - exit2_price) * exit2_qty
        net_pnl = (effective_entry_price - exit1_price) * exit1_qty + (effective_entry_price - effective_exit2_price) * exit2_qty - total_statutory
        
    return {
        'gross_pnl': gross_pnl,
        'net_pnl': net_pnl,
        'statutory_charges': total_statutory,
        'brokerage_paid': entry_charges['brokerage'] + exit1_charges['brokerage'] + exit2_charges['brokerage'],
        'stt_paid': entry_charges['stt'] + exit1_charges['stt'] + exit2_charges['stt'],
        'exchange_fee_paid': entry_charges['exchange_fee'] + exit1_charges['exchange_fee'] + exit2_charges['exchange_fee'],
        'sebi_fee_paid': entry_charges['sebi_fee'] + exit1_charges['sebi_fee'] + exit2_charges['sebi_fee'],
        'stamp_duty_paid': entry_charges['stamp_duty'] + exit1_charges['stamp_duty'] + exit2_charges['stamp_duty'],
        'gst_paid': entry_charges['gst'] + exit1_charges['gst'] + exit2_charges['gst'],
        'slippage_cost': total_slippage,
        'effective_entry_price': effective_entry_price,
        'effective_exit2_price': effective_exit2_price
    }
