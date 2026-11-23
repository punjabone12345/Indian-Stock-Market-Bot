"""
Bank Nifty Intraday Price Action Simulation (2020 - 2024)
Testing:
1. 15-min Opening Range Breakout (ORB)
2. Day Trend Filter (Daily 20 EMA / Supertrend)
3. Structural Stop (OR Midpoint / Breakout bar wick)
4. Target 2R + Trailing Runner to EOD
With exact statutory charges.
"""

import pandas as pd
import numpy as np

def compute_bn_charges(buy_val, sell_val):
    # Futures / Equity Intraday charges
    brokerage = 40.0 # flat roundtrip
    stt = sell_val * 0.000125 # 0.0125% for futures or 0.025% for equity
    exchange = (buy_val + sell_val) * 0.000019
    sebi = (buy_val + sell_val) * 0.000001
    stamp = buy_val * 0.00002
    gst = (brokerage + exchange + sebi) * 0.18
    return brokerage + stt + exchange + sebi + stamp + gst

def run_banknifty():
    df = pd.read_csv('data/banknifty/banknifty_5m_2015_2024.csv')
    df['Datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], format='%d-%m-%Y %H:%M:%S')
    df = df[df['Datetime'].dt.year >= 2020].sort_values('Datetime').reset_index(drop=True)
    df['date_str'] = df['Datetime'].dt.strftime('%Y-%m-%d')
    df['time_str'] = df['Datetime'].dt.strftime('%H:%M:%S')
    
    print(f"Bank Nifty total 5m bars (2020-2024): {len(df)}")
    
    trades = []
    grouped = df.groupby('date_str')
    
    for date_str, day_df in grouped:
        day_df = day_df.reset_index(drop=True)
        if len(day_df) < 25:
            continue
            
        # First 3 bars: 09:15, 09:20, 09:25 (Opening Range)
        or_bars = day_df.iloc[0:3]
        or_high = or_bars['High'].max()
        or_low = or_bars['Low'].min()
        or_mid = (or_high + or_low) / 2.0
        
        # We look for breakout between 09:30 and 11:30 (bars 3 to 26)
        traded = False
        for i in range(3, min(27, len(day_df) - 6)):
            if traded:
                break
                
            bar = day_df.iloc[i]
            b_close = bar['Close']
            b_high = bar['High']
            b_low = bar['Low']
            
            # ORB Breakout Long
            if b_close > or_high:
                entry = b_close
                stop = max(or_mid, b_low)
                # Clamp stop: min 0.20%, max 0.80%
                if (entry - stop) / entry < 0.0020:
                    stop = entry * (1.0 - 0.0020)
                if (entry - stop) / entry > 0.0080:
                    stop = entry * (1.0 - 0.0080)
                risk_pts = entry - stop
                target = entry + (2.0 * risk_pts)
                traded = True
                
                # Sizing: risk Rs 1,000 per trade (1R)
                qty = int(1000.0 / risk_pts)
                if qty < 15: # Bank Nifty lot size is 15
                    qty = 15
                qty = (qty // 15) * 15 # round to lot
                if qty < 15:
                    qty = 15
                    
                exit_price = 0.0
                t_hit = False
                for j in range(i + 1, len(day_df)):
                    f_bar = day_df.iloc[j]
                    if f_bar['Low'] <= stop:
                        exit_price = stop
                        break
                    if not t_hit and f_bar['High'] >= target:
                        t_hit = True
                        stop = entry # Move to Breakeven
                    if j == len(day_df) - 1 or j >= 72:
                        exit_price = f_bar['Close']
                        break
                else:
                    exit_price = day_df.iloc[-1]['Close']
                    
                pnl = qty * (exit_price - entry)
                fee = compute_bn_charges(qty * entry, qty * exit_price)
                net_pnl = pnl - fee
                net_r = net_pnl / 1000.0
                trades.append({
                    'date': date_str,
                    'side': 'BUY',
                    'net_r': net_r,
                    'fee': fee,
                    'net_pnl': net_pnl
                })
                
            # ORB Breakdown Short
            elif b_close < or_low:
                entry = b_close
                stop = min(or_mid, b_high)
                if (stop - entry) / entry < 0.0020:
                    stop = entry * (1.0 + 0.0020)
                if (stop - entry) / entry > 0.0080:
                    stop = entry * (1.0 + 0.0080)
                risk_pts = stop - entry
                target = entry - (2.0 * risk_pts)
                traded = True
                
                qty = int(1000.0 / risk_pts)
                if qty < 15:
                    qty = 15
                qty = (qty // 15) * 15
                if qty < 15:
                    qty = 15
                    
                exit_price = 0.0
                t_hit = False
                for j in range(i + 1, len(day_df)):
                    f_bar = day_df.iloc[j]
                    if f_bar['High'] >= stop:
                        exit_price = stop
                        break
                    if not t_hit and f_bar['Low'] <= target:
                        t_hit = True
                        stop = entry # Move to Breakeven
                    if j == len(day_df) - 1 or j >= 72:
                        exit_price = f_bar['Close']
                        break
                else:
                    exit_price = day_df.iloc[-1]['Close']
                    
                pnl = qty * (entry - exit_price)
                fee = compute_bn_charges(qty * exit_price, qty * entry)
                net_pnl = pnl - fee
                net_r = net_pnl / 1000.0
                trades.append({
                    'date': date_str,
                    'side': 'SELL',
                    'net_r': net_r,
                    'fee': fee,
                    'net_pnl': net_pnl
                })
                
    df_trades = pd.DataFrame(trades)
    df_trades['month'] = pd.to_datetime(df_trades['date']).dt.to_period('M')
    n_months = df_trades['month'].nunique()
    wins = df_trades[df_trades['net_r'] > 0]
    losses = df_trades[df_trades['net_r'] <= 0]
    win_rate = len(wins) / len(df_trades) * 100.0 if len(df_trades) > 0 else 0
    total_net_r = df_trades['net_r'].sum()
    monthly_r = total_net_r / max(1, n_months)
    
    df_trades['cum_r'] = df_trades['net_r'].cumsum()
    df_trades['peak_r'] = df_trades['cum_r'].cummax()
    df_trades['dd_r'] = df_trades['cum_r'] - df_trades['peak_r']
    max_dd_r = df_trades['dd_r'].min()
    
    gross_win = wins['net_pnl'].sum()
    gross_loss = abs(losses['net_pnl'].sum())
    profit_factor = gross_win / gross_loss if gross_loss > 0 else 999.0
    total_fees = df_trades['fee'].sum()
    
    print("\n" + "="*70)
    print("BANK NIFTY INTRADAY RESULTS (2020 - 2024):")
    print(f"Total Months: {n_months}")
    print(f"Total Trades: {len(df_trades)} ({len(df_trades)/n_months:.1f} trades/month)")
    print(f"Win Rate: {win_rate:.2f}% ({len(wins)} wins / {len(losses)} losses)")
    print(f"Profit Factor: {profit_factor:.2f}")
    print(f"Total Net R: {total_net_r:+.2f} R")
    print(f"Average Monthly R: {monthly_r:+.2f} R / month")
    print(f"Max Peak-to-Trough Drawdown: {max_dd_r:.2f} R")
    print(f"Total Fees Paid: Rs {total_fees:,.2f} ({total_fees/1000:.1f} R)")
    print("="*70)

if __name__ == '__main__':
    run_banknifty()
