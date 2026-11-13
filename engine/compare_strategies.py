import sys
sys.path.append('engine')
import os
import glob
import pandas as pd
import numpy as np
from datetime import time
from data_loader import load_nifty, load_stock, resample_5min

def prepare_data(universe):
    data_dict = {}
    for sym in universe:
        print(f"Loading {sym}...")
        if sym == 'NIFTY50':
            d_1m = load_nifty()
            is_index = True
            min_sl = 0.0025
        else:
            d_1m = load_stock(sym)
            is_index = False
            min_sl = 0.0050

        if d_1m is None or len(d_1m) == 0:
            continue

        df = resample_5min(d_1m)

        # Precompute VWAP, EMAs, Volume MA, Daily Trend
        df['Typ'] = (df['High'] + df['Low'] + df['Close']) / 3.0
        df['PV'] = df['Typ'] * df['Volume']
        df['CumPV'] = df.groupby('Date')['PV'].cumsum()
        df['CumV'] = df.groupby('Date')['Volume'].cumsum()
        df['VWAP'] = df['CumPV'] / df['CumV']

        df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
        df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
        df['VolMA20'] = df['Volume'].rolling(20, min_periods=1).mean()

        daily_close = df.groupby('Date')['Close'].last()
        daily_ema20 = daily_close.ewm(span=20, adjust=False).mean().shift(1)
        daily_ema50 = daily_close.ewm(span=50, adjust=False).mean().shift(1)
        df['DailyBull'] = df['Date'].map(daily_ema20 > daily_ema50)

        data_dict[sym] = {
            'df': df,
            'is_index': is_index,
            'min_sl': min_sl
        }
    return data_dict

# ==========================================
# STRATEGY A: Institutional Trend Momentum
# (Target: 1:2.8 R:R, RVOL surge, Daily Trend)
# ==========================================
def run_strategy_a(data_dict):
    print("\n--- Running Strategy A: Institutional Trend Momentum ---")
    trades = []
    
    for sym, item in data_dict.items():
        df = item['df']
        is_index = item['is_index']
        min_sl = item['min_sl']

        for dt, g in df.groupby('Date'):
            g = g.reset_index(drop=True)
            if len(g) < 25: continue
            is_bull = g['DailyBull'].iloc[0]
            if pd.isna(is_bull): continue

            first3 = g.iloc[:3]
            orb_h = first3['High'].max()
            orb_l = first3['Low'].min()
            orb_rng = orb_h - orb_l
            if orb_rng / g.iloc[0]['Open'] < 0.0025: continue

            for i in range(3, min(len(g)-5, 22)): # 09:30 to 11:00 AM
                row = g.iloc[i]
                
                # LONG: Daily Bull + Price > ORB High + Price > VWAP + Volume Surge
                if is_bull and row['Close'] > orb_h and row['Close'] > row['VWAP'] and row['EMA9'] > row['EMA21']:
                    vol_ok = is_index or (row['Volume'] > row['VolMA20'] * 1.2)
                    if vol_ok:
                        entry = row['Close']
                        sl = max(row['VWAP'], orb_l, entry - entry * 0.007)
                        sl_dist = entry - sl
                        if sl_dist < entry * min_sl: sl_dist = entry * min_sl; sl = entry - sl_dist
                        tp = entry + (sl_dist * 2.8)
                        
                        # Trailing buffer
                        trail_active = False
                        current_sl = sl

                        for j in range(i+1, len(g)):
                            c = g.iloc[j]
                            # Trail to +0.5R when price reaches +1.8R
                            if not trail_active and c['High'] >= entry + (sl_dist * 1.8):
                                trail_active = True
                                current_sl = entry + (sl_dist * 0.5)

                            if c['Low'] <= current_sl:
                                r_res = round((current_sl - entry)/sl_dist - 0.04, 2)
                                trades.append({'Date': dt, 'Time': row['Time'], 'Symbol': sym, 'R': r_res, 'Win': r_res > 0, 'Strat': 'Strat_A'})
                                break
                            if c['High'] >= tp:
                                trades.append({'Date': dt, 'Time': row['Time'], 'Symbol': sym, 'R': 2.76, 'Win': True, 'Strat': 'Strat_A'})
                                break
                            if c['Time'] >= time(15, 15):
                                r_eod = round((c['Close'] - entry)/sl_dist - 0.04, 2)
                                trades.append({'Date': dt, 'Time': row['Time'], 'Symbol': sym, 'R': r_eod, 'Win': r_eod > 0, 'Strat': 'Strat_A'})
                                break
                        break

                # SHORT: Daily Bear + Price < ORB Low + Price < VWAP + Volume Surge
                elif (not is_bull) and row['Close'] < orb_l and row['Close'] < row['VWAP'] and row['EMA9'] < row['EMA21']:
                    vol_ok = is_index or (row['Volume'] > row['VolMA20'] * 1.2)
                    if vol_ok:
                        entry = row['Close']
                        sl = min(row['VWAP'], orb_h, entry + entry * 0.007)
                        sl_dist = sl - entry
                        if sl_dist < entry * min_sl: sl_dist = entry * min_sl; sl = entry + sl_dist
                        tp = entry - (sl_dist * 2.8)

                        trail_active = False
                        current_sl = sl

                        for j in range(i+1, len(g)):
                            c = g.iloc[j]
                            if not trail_active and c['Low'] <= entry - (sl_dist * 1.8):
                                trail_active = True
                                current_sl = entry - (sl_dist * 0.5)

                            if c['High'] >= current_sl:
                                r_res = round((entry - current_sl)/sl_dist - 0.04, 2)
                                trades.append({'Date': dt, 'Time': row['Time'], 'Symbol': sym, 'R': r_res, 'Win': r_res > 0, 'Strat': 'Strat_A'})
                                break
                            if c['Low'] <= tp:
                                trades.append({'Date': dt, 'Time': row['Time'], 'Symbol': sym, 'R': 2.76, 'Win': True, 'Strat': 'Strat_A'})
                                break
                            if c['Time'] >= time(15, 15):
                                r_eod = round((entry - c['Close'])/sl_dist - 0.04, 2)
                                trades.append({'Date': dt, 'Time': row['Time'], 'Symbol': sym, 'R': r_eod, 'Win': r_eod > 0, 'Strat': 'Strat_A'})
                                break
                        break

    return apply_portfolio_limits(pd.DataFrame(trades))

# ==========================================
# STRATEGY B: Ultra-High Win Rate Scalp
# (Target: 1:1.1 R:R, Quick Breakeven @ +0.6R)
# ==========================================
def run_strategy_b(data_dict):
    print("\n--- Running Strategy B: Ultra-High Win Rate Scalp ---")
    trades = []
    
    for sym, item in data_dict.items():
        df = item['df']
        is_index = item['is_index']
        min_sl = item['min_sl']

        for dt, g in df.groupby('Date'):
            g = g.reset_index(drop=True)
            if len(g) < 25: continue
            is_bull = g['DailyBull'].iloc[0]
            if pd.isna(is_bull): continue

            first3 = g.iloc[:3]
            orb_h = first3['High'].max()
            orb_l = first3['Low'].min()
            orb_rng = orb_h - orb_l
            if orb_rng / g.iloc[0]['Open'] < 0.002: continue

            for i in range(3, min(len(g)-5, 20)): # 09:30 to 10:50 AM
                row = g.iloc[i]
                
                # LONG: Trend alignment + tight target 1:1.15
                if is_bull and row['Close'] > orb_h and row['Close'] > row['VWAP'] and row['EMA9'] > row['EMA21']:
                    entry = row['Close']
                    sl = max(row['VWAP'], entry - entry * 0.005)
                    sl_dist = entry - sl
                    if sl_dist < entry * min_sl: sl_dist = entry * min_sl; sl = entry - sl_dist
                    
                    tp = entry + (sl_dist * 1.15)
                    be_level = entry + (sl_dist * 0.6)
                    current_sl = sl
                    be_hit = False

                    for j in range(i+1, len(g)):
                        c = g.iloc[j]
                        # Breakeven lock
                        if not be_hit and c['High'] >= be_level:
                            be_hit = True
                            current_sl = entry + (sl_dist * 0.05)

                        if c['Low'] <= current_sl:
                            r_res = -1.04 if not be_hit else 0.01
                            trades.append({'Date': dt, 'Time': row['Time'], 'Symbol': sym, 'R': r_res, 'Win': r_res > 0, 'Strat': 'Strat_B'})
                            break
                        if c['High'] >= tp:
                            trades.append({'Date': dt, 'Time': row['Time'], 'Symbol': sym, 'R': 1.11, 'Win': True, 'Strat': 'Strat_B'})
                            break
                        if c['Time'] >= time(15, 15):
                            r_eod = round((c['Close'] - entry)/sl_dist - 0.04, 2)
                            trades.append({'Date': dt, 'Time': row['Time'], 'Symbol': sym, 'R': r_eod, 'Win': r_eod > 0, 'Strat': 'Strat_B'})
                            break
                    break

                # SHORT: Trend alignment + tight target 1:1.15
                elif (not is_bull) and row['Close'] < orb_l and row['Close'] < row['VWAP'] and row['EMA9'] < row['EMA21']:
                    entry = row['Close']
                    sl = min(row['VWAP'], entry + entry * 0.005)
                    sl_dist = sl - entry
                    if sl_dist < entry * min_sl: sl_dist = entry * min_sl; sl = entry + sl_dist

                    tp = entry - (sl_dist * 1.15)
                    be_level = entry - (sl_dist * 0.6)
                    current_sl = sl
                    be_hit = False

                    for j in range(i+1, len(g)):
                        c = g.iloc[j]
                        if not be_hit and c['Low'] <= be_level:
                            be_hit = True
                            current_sl = entry - (sl_dist * 0.05)

                        if c['High'] >= current_sl:
                            r_res = -1.04 if not be_hit else 0.01
                            trades.append({'Date': dt, 'Time': row['Time'], 'Symbol': sym, 'R': r_res, 'Win': r_res > 0, 'Strat': 'Strat_B'})
                            break
                        if c['Low'] <= tp:
                            trades.append({'Date': dt, 'Time': row['Time'], 'Symbol': sym, 'R': 1.11, 'Win': True, 'Strat': 'Strat_B'})
                            break
                        if c['Time'] >= time(15, 15):
                            r_eod = round((entry - c['Close'])/sl_dist - 0.04, 2)
                            trades.append({'Date': dt, 'Time': row['Time'], 'Symbol': sym, 'R': r_eod, 'Win': r_eod > 0, 'Strat': 'Strat_B'})
                            break
                    break

    return apply_portfolio_limits(pd.DataFrame(trades))

def apply_portfolio_limits(trades_df):
    if len(trades_df) == 0:
        return trades_df
    trades_df = trades_df.sort_values(['Date', 'Time']).reset_index(drop=True)
    filtered = []
    
    for dt, g in trades_df.groupby('Date'):
        cnt = 0
        losses = 0
        for _, t in g.iterrows():
            if cnt >= 3: break
            if losses >= 2: break
            filtered.append(t)
            cnt += 1
            if t['R'] < 0: losses += 1

    return pd.DataFrame(filtered)

def evaluate_metrics(df, name):
    if len(df) == 0:
        return {}
    df['YM'] = pd.to_datetime(df['Date']).dt.to_period('M')
    total_trades = len(df)
    wins = df[df['R'] > 0]
    losses = df[df['R'] < 0]
    win_rate = (len(wins) / total_trades) * 100
    
    total_r = df['R'].sum()
    avg_win = wins['R'].mean() if len(wins) > 0 else 0
    avg_loss = abs(losses['R'].mean()) if len(losses) > 0 else 1
    profit_factor = (wins['R'].sum() / abs(losses['R'].sum())) if len(losses) > 0 and losses['R'].sum() != 0 else 0
    
    # Cumulative Drawdown
    cum_r = df['R'].cumsum()
    peak_r = cum_r.cummax()
    dd_series = cum_r - peak_r
    max_dd = dd_series.min()

    # Max losing streak
    streak = 0
    max_streak = 0
    for r in df['R']:
        if r < 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0

    monthly = df.groupby('YM')['R'].sum()
    avg_r_month = monthly.mean()
    positive_months = (monthly > 0).sum()
    total_months = len(monthly)
    month_win_rate = (positive_months / total_months) * 100

    # Calmar ratio
    annual_r = total_r / (total_months / 12.0)
    calmar = abs(annual_r / max_dd) if max_dd != 0 else 0

    return {
        'Name': name,
        'Total Trades': total_trades,
        'Trades / Month': round(total_trades / total_months, 1),
        'Win Rate (%)': round(win_rate, 1),
        'Avg Win (R)': round(avg_win, 2),
        'Avg Loss (R)': round(avg_loss, 2),
        'Profit Factor': round(profit_factor, 2),
        'Total Return (R)': round(total_r, 1),
        'Avg Return / Month (R)': round(avg_r_month, 1),
        'Max Drawdown (R)': round(max_dd, 1),
        'Max Consecutive Losses': max_streak,
        'Monthly Win Rate (%)': round(month_win_rate, 1),
        'Profitable Months': f"{positive_months}/{total_months}",
        'Annualized Return (R)': round(annual_r, 1),
        'Calmar Ratio': round(calmar, 2)
    }

if __name__ == '__main__':
    universe = ['NIFTY50', 'RELIANCE', 'TCS', 'BHARTIARTL', 'SBIN', 'LT', 'HDFCBANK', 'AXISBANK', 'ICICIBANK']
    data_dict = prepare_data(universe)

    trades_a = run_strategy_a(data_dict)
    trades_b = run_strategy_b(data_dict)

    metrics_a = evaluate_metrics(trades_a, 'Strategy A: Institutional Trend Momentum')
    metrics_b = evaluate_metrics(trades_b, 'Strategy B: Ultra-High Win Rate Scalp')

    print("\n" + "="*75)
    print("                HEAD-TO-HEAD STRATEGY COMPARISON")
    print("="*75)
    comp_df = pd.DataFrame([metrics_a, metrics_b]).set_index('Name').T
    print(comp_df.to_string())
    print("="*75)

    # Save to reports
    os.makedirs('reports', exist_ok=True)
    trades_a.to_csv('reports/trades_strategy_a.csv', index=False)
    trades_b.to_csv('reports/trades_strategy_b.csv', index=False)
    comp_df.to_csv('reports/strategy_comparison.csv')
    print("Detailed trade files saved in reports/")
