"""
ULTRA-FAST MULTI-STRATEGY QUANTITATIVE EXPLORATION ENGINE (2022-2026)
Pre-indexes 29 Mega-Caps across 1,186 sessions using C-level Hash Partitioning.
Executes 10+ Distinct Quantitative Architectures across SMC, ICT, Price Action, Fib OTE, and Breakouts.
Enforces:
- Strict 3:00 PM IST Square-off
- Point-in-time signal execution with zero look-ahead bias
- Full Statutory Zerodha Intraday Cost Model (Brokerage, STT, Exchange, SEBI, Stamp Duty, GST, Slippage)
- Capital: Rs 1,00,000, Static Rs 1,000 Risk (1R)
"""
import os
import sys
import glob
import time as pytime
from datetime import time
import pandas as pd
import numpy as np

# Import costs
from costs import compute_trade_costs

CACHE_DIR = "data/master_cache_2022_2026"

def load_preindexed_universe():
    t0 = pytime.time()
    files_5m = sorted(glob.glob(os.path.join(CACHE_DIR, "*_5m.parquet")))
    symbols = [os.path.basename(f).replace("_5m.parquet", "") for f in files_5m]
    
    print(f"Loading and pre-indexing {len(symbols)} symbols...")
    universe = {}
    for sym in symbols:
        df_5m = pd.read_parquet(os.path.join(CACHE_DIR, f"{sym}_5m.parquet"))
        df_daily = pd.read_parquet(os.path.join(CACHE_DIR, f"{sym}_daily.parquet"))
        
        # Precompute daily metrics (shifted by 1 day)
        df_daily['PDH'] = df_daily['High'].shift(1)
        df_daily['PDL'] = df_daily['Low'].shift(1)
        df_daily['PDC'] = df_daily['Close'].shift(1)
        df_daily['Daily_EMA20'] = df_daily['Close'].ewm(span=20, adjust=False).mean().shift(1)
        df_daily['Daily_EMA50'] = df_daily['Close'].ewm(span=50, adjust=False).mean().shift(1)
        df_daily['Daily_VolMA20'] = df_daily['Volume'].rolling(20, min_periods=1).mean().shift(1)
        
        daily_dict = df_daily.set_index('Date').to_dict('index')
        
        # Hash partition 5m data by Date
        day_groups = dict(tuple(df_5m.groupby('Date')))
        
        universe[sym] = {
            'daily': daily_dict,
            'days': day_groups
        }
        
    print(f"Pre-indexing complete in {pytime.time() - t0:.2f} seconds.")
    return universe

def evaluate_strategy_results(strategy_name, all_trades):
    if not all_trades:
        print(f"\n[{strategy_name}] ZERO TRADES GENERATED.")
        return {
            'Name': strategy_name,
            'Trades': 0, 'WinRate': 0.0, 'PF': 0.0,
            'NetPnL': 0.0, 'TotalR': 0.0, 'MaxDD': 0.0,
            'AvgMonthlyPct': 0.0, 'Status': 'NO_TRADES'
        }
        
    df_t = pd.DataFrame(all_trades)
    df_t['Date'] = pd.to_datetime(df_t['Date'])
    df_t['Year'] = df_t['Date'].dt.year
    df_t['Month'] = df_t['Date'].dt.to_period('M')
    
    total_trades = len(df_t)
    wins = df_t[df_t['NetPnL'] > 0]
    losses = df_t[df_t['NetPnL'] <= 0]
    win_rate = (len(wins) / total_trades) * 100.0
    
    total_gross = df_t['GrossPnL'].sum()
    total_costs = df_t['Costs'].sum()
    total_net = df_t['NetPnL'].sum()
    total_r = df_t['R_Return'].sum()
    
    profit_factor = abs(wins['NetPnL'].sum() / losses['NetPnL'].sum()) if len(losses) > 0 and losses['NetPnL'].sum() != 0 else np.nan
    
    df_t['CumNet'] = df_t['NetPnL'].cumsum()
    df_t['Peak'] = df_t['CumNet'].cummax()
    df_t['DD'] = df_t['Peak'] - df_t['CumNet']
    max_dd = df_t['DD'].max()
    
    monthly = df_t.groupby('Month')['NetPnL'].sum()
    num_months = len(monthly)
    avg_monthly_pnl = monthly.mean()
    avg_monthly_pct = (avg_monthly_pnl / 100000.0) * 100.0
    
    print("\n" + "="*75)
    print(f"   RESULTS: {strategy_name}")
    print(f"   Period: 2022 to 2026 (4.8 Years, {num_months} Active Months)")
    print("="*75)
    print(f"Total Trades:            {total_trades}")
    print(f"Win Rate:                {win_rate:.2f}% ({len(wins)}W / {len(losses)}L)")
    print(f"Profit Factor:           {profit_factor:.2f}")
    print(f"Total Gross Profit:      Rs {total_gross:,.2f}")
    print(f"Total Friction Deducted: Rs {total_costs:,.2f} ({total_costs/total_gross*100 if total_gross > 0 else 0:.1f}% of gross)")
    print(f"Total Net PnL:           Rs {total_net:,.2f} ({total_r:.1f}R)")
    print(f"Max Drawdown:            Rs {max_dd:,.2f} ({max_dd/1000.0:.1f}R)")
    print(f"Average Monthly Return:  Rs {avg_monthly_pnl:,.2f} ({avg_monthly_pct:.2f}% per month)")
    
    yearly = df_t.groupby('Year').agg(
        Trades=('NetPnL', 'count'),
        NetPnL=('NetPnL', 'sum'),
        R_Return=('R_Return', 'sum'),
        WinRate=('NetPnL', lambda x: (x > 0).mean() * 100.0)
    )
    print("\n--- Annual Breakdown ---")
    print(yearly.to_string())
    
    return {
        'Name': strategy_name,
        'Trades': total_trades,
        'WinRate': win_rate,
        'PF': profit_factor,
        'GrossPnL': total_gross,
        'Costs': total_costs,
        'NetPnL': total_net,
        'TotalR': total_r,
        'MaxDD': max_dd,
        'AvgMonthlyPct': avg_monthly_pct,
        'Status': 'PROFITABLE' if total_net > 0 else 'UNPROFITABLE'
    }

# ==============================================================================
# STRATEGY 1: SMC LIQUIDITY SWEEP + MSS + FVG RETEST
# ==============================================================================
def test_smc_liquidity_sweep(universe, target_rr=2.5, min_sl_pct=0.003, max_sl_pct=0.015):
    all_trades = []
    for sym, data in universe.items():
        daily_dict = data['daily']
        days = data['days']
        
        for dt, df_day in days.items():
            if dt not in daily_dict or len(df_day) < 35:
                continue
            pd_info = daily_dict[dt]
            pdh = pd_info.get('PDH')
            pdl = pd_info.get('PDL')
            if pd.isna(pdh) or pd.isna(pdl):
                continue
                
            bars = df_day.reset_index(drop=True)
            ib_bars = bars.iloc[:6]
            ibh = max(ib_bars['High'].max(), pdh)
            ibl = min(ib_bars['Low'].min(), pdl)
            
            in_trade = False
            for i in range(6, min(len(bars) - 5, 45)):
                if in_trade:
                    break
                c1 = bars.iloc[i-2]
                c2 = bars.iloc[i-1]
                c3 = bars.iloc[i]
                
                # Bearish Sweep & FVG
                swept_h = any(bars.iloc[k]['High'] > ibh and bars.iloc[k]['Close'] < ibh for k in range(max(0, i-4), i))
                fvg_bear = (c3['High'] < c1['Low']) and (c2['Close'] < c2['Open'])
                if swept_h and fvg_bear:
                    entry_limit = c1['Low']
                    sweep_peak = max(bars.iloc[k]['High'] for k in range(max(0, i-4), i+1))
                    raw_sl = sweep_peak - entry_limit
                    if min_sl_pct <= (raw_sl / entry_limit) <= max_sl_pct:
                        for r_idx in range(i+1, min(len(bars)-2, i+10)):
                            rk = bars.iloc[r_idx]
                            if rk['High'] >= entry_limit:
                                entry = entry_limit
                                sl = sweep_peak
                                tp = entry - (raw_sl * target_rr)
                                qty = max(1, min(int(1000.0 / raw_sl), int(500000 / entry)))
                                
                                exit_p, exit_t, reason = None, None, None
                                for m_idx in range(r_idx+1, len(bars)):
                                    mb = bars.iloc[m_idx]
                                    if mb['Low'] <= tp:
                                        exit_p, exit_t, reason = tp, mb['Time'], 'TARGET'
                                        break
                                    if mb['High'] >= sl:
                                        exit_p, exit_t, reason = sl, mb['Time'], 'STOP_LOSS'
                                        break
                                    if mb['Time'] >= time(15, 0):
                                        exit_p, exit_t, reason = mb['Close'], mb['Time'], 'TIME_3PM'
                                        break
                                if exit_p is None:
                                    exit_p, exit_t, reason = bars.iloc[-1]['Close'], bars.iloc[-1]['Time'], 'EOD'
                                    
                                costs = compute_trade_costs('SELL', entry, qty, 0.0, 0, exit_p, qty, 0.0003)
                                all_trades.append({
                                    'Date': dt, 'Symbol': sym, 'Side': 'SHORT', 'EntryTime': rk['Time'],
                                    'ExitTime': exit_t, 'EntryPrice': entry, 'ExitPrice': exit_p, 'Qty': qty,
                                    'GrossPnL': costs['gross_pnl'], 'Costs': costs['statutory_charges'] + costs['slippage_cost'],
                                    'NetPnL': costs['net_pnl'], 'R_Return': costs['net_pnl'] / 1000.0
                                })
                                in_trade = True
                                break
                                
                # Bullish Sweep & FVG
                if not in_trade:
                    swept_l = any(bars.iloc[k]['Low'] < ibl and bars.iloc[k]['Close'] > ibl for k in range(max(0, i-4), i))
                    fvg_bull = (c3['Low'] > c1['High']) and (c2['Close'] > c2['Open'])
                    if swept_l and fvg_bull:
                        entry_limit = c1['High']
                        sweep_trough = min(bars.iloc[k]['Low'] for k in range(max(0, i-4), i+1))
                        raw_sl = entry_limit - sweep_trough
                        if min_sl_pct <= (raw_sl / entry_limit) <= max_sl_pct:
                            for r_idx in range(i+1, min(len(bars)-2, i+10)):
                                rk = bars.iloc[r_idx]
                                if rk['Low'] <= entry_limit:
                                    entry = entry_limit
                                    sl = sweep_trough
                                    tp = entry + (raw_sl * target_rr)
                                    qty = max(1, min(int(1000.0 / raw_sl), int(500000 / entry)))
                                    
                                    exit_p, exit_t, reason = None, None, None
                                    for m_idx in range(r_idx+1, len(bars)):
                                        mb = bars.iloc[m_idx]
                                        if mb['High'] >= tp:
                                            exit_p, exit_t, reason = tp, mb['Time'], 'TARGET'
                                            break
                                        if mb['Low'] <= sl:
                                            exit_p, exit_t, reason = sl, mb['Time'], 'STOP_LOSS'
                                            break
                                        if mb['Time'] >= time(15, 0):
                                            exit_p, exit_t, reason = mb['Close'], mb['Time'], 'TIME_3PM'
                                            break
                                    if exit_p is None:
                                        exit_p, exit_t, reason = bars.iloc[-1]['Close'], bars.iloc[-1]['Time'], 'EOD'
                                        
                                    costs = compute_trade_costs('BUY', entry, qty, 0.0, 0, exit_p, qty, 0.0003)
                                    all_trades.append({
                                        'Date': dt, 'Symbol': sym, 'Side': 'BUY', 'EntryTime': rk['Time'],
                                        'ExitTime': exit_t, 'EntryPrice': entry, 'ExitPrice': exit_p, 'Qty': qty,
                                        'GrossPnL': costs['gross_pnl'], 'Costs': costs['statutory_charges'] + costs['slippage_cost'],
                                        'NetPnL': costs['net_pnl'], 'R_Return': costs['net_pnl'] / 1000.0
                                    })
                                    in_trade = True
                                    break
    return evaluate_strategy_results(f"SMC Liquidity Sweep + FVG Retest (1:{target_rr})", all_trades)

# ==============================================================================
# STRATEGY 2: SMC ORDER BLOCK (OB) + OPTIMAL TRADE ENTRY (FIB 61.8%)
# ==============================================================================
def test_order_block_fib(universe, target_rr=2.5, min_sl_pct=0.003, max_sl_pct=0.015):
    all_trades = []
    for sym, data in universe.items():
        days = data['days']
        for dt, df_day in days.items():
            if len(df_day) < 35:
                continue
            bars = df_day.reset_index(drop=True)
            in_trade = False
            for i in range(5, min(len(bars) - 10, 25)):
                if in_trade:
                    break
                sub = bars.iloc[i-4:i+1]
                s_low = sub['Low'].min()
                s_low_idx = sub['Low'].idxmin()
                s_high = sub['High'].max()
                s_high_idx = sub['High'].idxmax()
                
                # Bullish Impulse
                if s_high_idx > s_low_idx and (s_high - s_low) / s_low >= 0.010:
                    rng = s_high - s_low
                    fib618 = s_high - (rng * 0.618)
                    ob_sl = s_low
                    raw_sl = fib618 - ob_sl
                    if min_sl_pct <= (raw_sl / fib618) <= max_sl_pct:
                        for r_idx in range(i+1, min(len(bars)-2, i+15)):
                            rk = bars.iloc[r_idx]
                            if rk['Low'] <= fib618 and rk['Low'] > ob_sl:
                                entry = fib618
                                sl = ob_sl
                                tp = entry + (raw_sl * target_rr)
                                qty = max(1, min(int(1000.0 / raw_sl), int(500000 / entry)))
                                
                                exit_p, exit_t = None, None
                                for m_idx in range(r_idx+1, len(bars)):
                                    mb = bars.iloc[m_idx]
                                    if mb['High'] >= tp:
                                        exit_p, exit_t = tp, mb['Time']
                                        break
                                    if mb['Low'] <= sl:
                                        exit_p, exit_t = sl, mb['Time']
                                        break
                                    if mb['Time'] >= time(15, 0):
                                        exit_p, exit_t = mb['Close'], mb['Time']
                                        break
                                if exit_p is None:
                                    exit_p, exit_t = bars.iloc[-1]['Close'], bars.iloc[-1]['Time']
                                costs = compute_trade_costs('BUY', entry, qty, 0.0, 0, exit_p, qty, 0.0003)
                                all_trades.append({
                                    'Date': dt, 'Symbol': sym, 'Side': 'BUY', 'EntryTime': rk['Time'],
                                    'ExitTime': exit_t, 'EntryPrice': entry, 'ExitPrice': exit_p, 'Qty': qty,
                                    'GrossPnL': costs['gross_pnl'], 'Costs': costs['statutory_charges'] + costs['slippage_cost'],
                                    'NetPnL': costs['net_pnl'], 'R_Return': costs['net_pnl'] / 1000.0
                                })
                                in_trade = True
                                break
                                
                # Bearish Impulse
                if not in_trade and s_low_idx > s_high_idx and (s_high - s_low) / s_high >= 0.010:
                    rng = s_high - s_low
                    fib618 = s_low + (rng * 0.618)
                    ob_sl = s_high
                    raw_sl = ob_sl - fib618
                    if min_sl_pct <= (raw_sl / fib618) <= max_sl_pct:
                        for r_idx in range(i+1, min(len(bars)-2, i+15)):
                            rk = bars.iloc[r_idx]
                            if rk['High'] >= fib618 and rk['High'] < ob_sl:
                                entry = fib618
                                sl = ob_sl
                                tp = entry - (raw_sl * target_rr)
                                qty = max(1, min(int(1000.0 / raw_sl), int(500000 / entry)))
                                
                                exit_p, exit_t = None, None
                                for m_idx in range(r_idx+1, len(bars)):
                                    mb = bars.iloc[m_idx]
                                    if mb['Low'] <= tp:
                                        exit_p, exit_t = tp, mb['Time']
                                        break
                                    if mb['High'] >= sl:
                                        exit_p, exit_t = sl, mb['Time']
                                        break
                                    if mb['Time'] >= time(15, 0):
                                        exit_p, exit_t = mb['Close'], mb['Time']
                                        break
                                if exit_p is None:
                                    exit_p, exit_t = bars.iloc[-1]['Close'], bars.iloc[-1]['Time']
                                costs = compute_trade_costs('SELL', entry, qty, 0.0, 0, exit_p, qty, 0.0003)
                                all_trades.append({
                                    'Date': dt, 'Symbol': sym, 'Side': 'SHORT', 'EntryTime': rk['Time'],
                                    'ExitTime': exit_t, 'EntryPrice': entry, 'ExitPrice': exit_p, 'Qty': qty,
                                    'GrossPnL': costs['gross_pnl'], 'Costs': costs['statutory_charges'] + costs['slippage_cost'],
                                    'NetPnL': costs['net_pnl'], 'R_Return': costs['net_pnl'] / 1000.0
                                })
                                in_trade = True
                                break
    return evaluate_strategy_results(f"SMC Order Block + OTE Fib (1:{target_rr})", all_trades)

# ==============================================================================
# STRATEGY 3: MULTI-TIMEFRAME TREND + VWAP PULLBACK REVERSAL
# ==============================================================================
def test_mtf_vwap_pullback(universe, target_rr=2.5, min_sl_pct=0.003, max_sl_pct=0.012):
    all_trades = []
    for sym, data in universe.items():
        daily_dict = data['daily']
        days = data['days']
        for dt, df_day in days.items():
            if dt not in daily_dict or len(df_day) < 35:
                continue
            d_info = daily_dict[dt]
            ema20 = d_info.get('Daily_EMA20')
            ema50 = d_info.get('Daily_EMA50')
            if pd.isna(ema20) or pd.isna(ema50):
                continue
            is_bull = ema20 > ema50
            is_bear = ema20 < ema50
            
            bars = df_day.reset_index(drop=True)
            ibh = bars.iloc[:6]['High'].max()
            ibl = bars.iloc[:6]['Low'].min()
            
            in_trade = False
            for i in range(6, min(len(bars)-5, 40)):
                if in_trade:
                    break
                row = bars.iloc[i]
                prev = bars.iloc[i-1]
                t = row['Time']
                vwap = row['VWAP']
                
                # Long
                if is_bull and any(bars.iloc[k]['Close'] > ibh for k in range(6, i)):
                    if abs(row['Low'] - vwap) / vwap <= 0.002 and row['Close'] > vwap and row['Close'] > row['Open']:
                        entry = row['Close']
                        sl = min(min(row['Low'], prev['Low']) * 0.999, vwap * 0.996)
                        sl_dist = entry - sl
                        if min_sl_pct <= (sl_dist / entry) <= max_sl_pct:
                            tp = entry + (sl_dist * target_rr)
                            qty = max(1, min(int(1000.0 / sl_dist), int(500000 / entry)))
                            
                            exit_p, exit_t = None, None
                            for m in range(i+1, len(bars)):
                                mb = bars.iloc[m]
                                if mb['High'] >= tp:
                                    exit_p, exit_t = tp, mb['Time']
                                    break
                                if mb['Low'] <= sl:
                                    exit_p, exit_t = sl, mb['Time']
                                    break
                                if mb['Time'] >= time(15, 0):
                                    exit_p, exit_t = mb['Close'], mb['Time']
                                    break
                            if exit_p is None:
                                exit_p, exit_t = bars.iloc[-1]['Close'], bars.iloc[-1]['Time']
                            costs = compute_trade_costs('BUY', entry, qty, 0.0, 0, exit_p, qty, 0.0003)
                            all_trades.append({
                                'Date': dt, 'Symbol': sym, 'Side': 'BUY', 'EntryTime': t,
                                'ExitTime': exit_t, 'EntryPrice': entry, 'ExitPrice': exit_p, 'Qty': qty,
                                'GrossPnL': costs['gross_pnl'], 'Costs': costs['statutory_charges'] + costs['slippage_cost'],
                                'NetPnL': costs['net_pnl'], 'R_Return': costs['net_pnl'] / 1000.0
                            })
                            in_trade = True
                            
                # Short
                if not in_trade and is_bear and any(bars.iloc[k]['Close'] < ibl for k in range(6, i)):
                    if abs(row['High'] - vwap) / vwap <= 0.002 and row['Close'] < vwap and row['Close'] < row['Open']:
                        entry = row['Close']
                        sl = max(max(row['High'], prev['High']) * 1.001, vwap * 1.004)
                        sl_dist = sl - entry
                        if min_sl_pct <= (sl_dist / entry) <= max_sl_pct:
                            tp = entry - (sl_dist * target_rr)
                            qty = max(1, min(int(1000.0 / sl_dist), int(500000 / entry)))
                            
                            exit_p, exit_t = None, None
                            for m in range(i+1, len(bars)):
                                mb = bars.iloc[m]
                                if mb['Low'] <= tp:
                                    exit_p, exit_t = tp, mb['Time']
                                    break
                                if mb['High'] >= sl:
                                    exit_p, exit_t = sl, mb['Time']
                                    break
                                if mb['Time'] >= time(15, 0):
                                    exit_p, exit_t = mb['Close'], mb['Time']
                                    break
                            if exit_p is None:
                                exit_p, exit_t = bars.iloc[-1]['Close'], bars.iloc[-1]['Time']
                            costs = compute_trade_costs('SELL', entry, qty, 0.0, 0, exit_p, qty, 0.0003)
                            all_trades.append({
                                'Date': dt, 'Symbol': sym, 'Side': 'SHORT', 'EntryTime': t,
                                'ExitTime': exit_t, 'EntryPrice': entry, 'ExitPrice': exit_p, 'Qty': qty,
                                'GrossPnL': costs['gross_pnl'], 'Costs': costs['statutory_charges'] + costs['slippage_cost'],
                                'NetPnL': costs['net_pnl'], 'R_Return': costs['net_pnl'] / 1000.0
                            })
                            in_trade = True
    return evaluate_strategy_results(f"MTF Trend + VWAP Pullback (1:{target_rr})", all_trades)

# ==============================================================================
# STRATEGY 4: CHARTMINE OPEN=HIGH SHORT DIRECTIONAL MOMENTUM
# ==============================================================================
def test_open_high_short_runners(universe, target_rr=2.5):
    all_trades = []
    # Collect all unique dates
    all_dates = sorted(list(next(iter(universe.values()))['days'].keys()))
    
    for dt in all_dates:
        candidates = []
        for sym, data in universe.items():
            days = data['days']
            if dt not in days or len(days[dt]) < 30:
                continue
            bars = days[dt].reset_index(drop=True)
            c0 = bars.iloc[0]
            is_oh = ((c0['High'] - c0['Open']) / c0['Open'] <= 0.0005) and (c0['Close'] < c0['Open'])
            move_pct = (c0['Open'] - c0['Close']) / c0['Open']
            if is_oh and move_pct >= 0.003:
                candidates.append({
                    'sym': sym, 'bars': bars, 'score': move_pct * c0['Volume'], 'c0': c0
                })
        if not candidates:
            continue
            
        candidates.sort(key=lambda x: x['score'], reverse=True)
        # Take Top 2 candidates
        for cand in candidates[:2]:
            sym = cand['sym']
            bars = cand['bars']
            c0 = cand['c0']
            c1 = bars.iloc[1]
            entry = c1['Open']
            sl = c0['High'] * 1.0005
            sl_dist = sl - entry
            if sl_dist <= 0 or (sl_dist / entry) < 0.002:
                sl_dist = entry * 0.005
                sl = entry + sl_dist
            elif (sl_dist / entry) > 0.015:
                sl_dist = entry * 0.015
                sl = entry + sl_dist
                
            tp = entry - (sl_dist * target_rr)
            qty = max(1, min(int(1000.0 / sl_dist), int(500000 / entry)))
            
            exit_p, exit_t = None, None
            for m in range(1, len(bars)):
                mb = bars.iloc[m]
                if mb['Low'] <= tp:
                    exit_p, exit_t = tp, mb['Time']
                    break
                if mb['High'] >= sl:
                    exit_p, exit_t = sl, mb['Time']
                    break
                if mb['Time'] >= time(15, 0):
                    exit_p, exit_t = mb['Close'], mb['Time']
                    break
            if exit_p is None:
                exit_p, exit_t = bars.iloc[-1]['Close'], bars.iloc[-1]['Time']
            costs = compute_trade_costs('SELL', entry, qty, 0.0, 0, exit_p, qty, 0.0003)
            all_trades.append({
                'Date': dt, 'Symbol': sym, 'Side': 'SHORT', 'EntryTime': c1['Time'],
                'ExitTime': exit_t, 'EntryPrice': entry, 'ExitPrice': exit_p, 'Qty': qty,
                'GrossPnL': costs['gross_pnl'], 'Costs': costs['statutory_charges'] + costs['slippage_cost'],
                'NetPnL': costs['net_pnl'], 'R_Return': costs['net_pnl'] / 1000.0
            })
    return evaluate_strategy_results(f"ChartMine Open=High Shorts (1:{target_rr})", all_trades)

# ==============================================================================
# STRATEGY 5: 15-MINUTE OPENING RANGE BREAKOUT (ORB) RUNNER
# ==============================================================================
def test_orb_15m_runners(universe, target_rr=3.0):
    all_trades = []
    all_dates = sorted(list(next(iter(universe.values()))['days'].keys()))
    
    for dt in all_dates:
        candidates = []
        for sym, data in universe.items():
            days = data['days']
            if dt not in days or len(days[dt]) < 30:
                continue
            bars = days[dt].reset_index(drop=True)
            # 15m range is first 3 bars (09:15 to 09:30)
            m15 = bars.iloc[:3]
            m15_h = m15['High'].max()
            m15_l = m15['Low'].min()
            m15_vol = m15['Volume'].sum()
            rng_pct = (m15_h - m15_l) / m15_l
            if 0.005 <= rng_pct <= 0.015: # Healthy range, not blown out
                candidates.append({
                    'sym': sym, 'bars': bars, 'h': m15_h, 'l': m15_l, 'vol': m15_vol
                })
        if not candidates:
            continue
        candidates.sort(key=lambda x: x['vol'], reverse=True)
        # Scan Top 3 volume stocks for breakout
        for cand in candidates[:3]:
            sym = cand['sym']
            bars = cand['bars']
            h = cand['h']
            l = cand['l']
            
            in_trade = False
            for i in range(3, min(len(bars)-5, 25)): # Trigger between 09:30 and 11:20
                if in_trade:
                    break
                row = bars.iloc[i]
                # Long breakout
                if row['Close'] > h and row['Close'] > row['VWAP']:
                    entry = row['Close']
                    sl = (h + l) / 2.0 # Midpoint SL
                    sl_dist = entry - sl
                    if (sl_dist / entry) >= 0.003:
                        tp = entry + (sl_dist * target_rr)
                        qty = max(1, min(int(1000.0 / sl_dist), int(500000 / entry)))
                        exit_p, exit_t = None, None
                        for m in range(i+1, len(bars)):
                            mb = bars.iloc[m]
                            if mb['High'] >= tp:
                                exit_p, exit_t = tp, mb['Time']
                                break
                            if mb['Low'] <= sl:
                                exit_p, exit_t = sl, mb['Time']
                                break
                            if mb['Time'] >= time(15, 0):
                                exit_p, exit_t = mb['Close'], mb['Time']
                                break
                        if exit_p is None:
                            exit_p, exit_t = bars.iloc[-1]['Close'], bars.iloc[-1]['Time']
                        costs = compute_trade_costs('BUY', entry, qty, 0.0, 0, exit_p, qty, 0.0003)
                        all_trades.append({
                            'Date': dt, 'Symbol': sym, 'Side': 'BUY', 'EntryTime': row['Time'],
                            'ExitTime': exit_t, 'EntryPrice': entry, 'ExitPrice': exit_p, 'Qty': qty,
                            'GrossPnL': costs['gross_pnl'], 'Costs': costs['statutory_charges'] + costs['slippage_cost'],
                            'NetPnL': costs['net_pnl'], 'R_Return': costs['net_pnl'] / 1000.0
                        })
                        in_trade = True
                        break
                        
                # Short breakdown
                elif row['Close'] < l and row['Close'] < row['VWAP']:
                    entry = row['Close']
                    sl = (h + l) / 2.0 # Midpoint SL
                    sl_dist = sl - entry
                    if (sl_dist / entry) >= 0.003:
                        tp = entry - (sl_dist * target_rr)
                        qty = max(1, min(int(1000.0 / sl_dist), int(500000 / entry)))
                        exit_p, exit_t = None, None
                        for m in range(i+1, len(bars)):
                            mb = bars.iloc[m]
                            if mb['Low'] <= tp:
                                exit_p, exit_t = tp, mb['Time']
                                break
                            if mb['High'] >= sl:
                                exit_p, exit_t = sl, mb['Time']
                                break
                            if mb['Time'] >= time(15, 0):
                                exit_p, exit_t = mb['Close'], mb['Time']
                                break
                        if exit_p is None:
                            exit_p, exit_t = bars.iloc[-1]['Close'], bars.iloc[-1]['Time']
                        costs = compute_trade_costs('SELL', entry, qty, 0.0, 0, exit_p, qty, 0.0003)
                        all_trades.append({
                            'Date': dt, 'Symbol': sym, 'Side': 'SHORT', 'EntryTime': row['Time'],
                            'ExitTime': exit_t, 'EntryPrice': entry, 'ExitPrice': exit_p, 'Qty': qty,
                            'GrossPnL': costs['gross_pnl'], 'Costs': costs['statutory_charges'] + costs['slippage_cost'],
                            'NetPnL': costs['net_pnl'], 'R_Return': costs['net_pnl'] / 1000.0
                        })
                        in_trade = True
                        break
    return evaluate_strategy_results(f"15m ORB Midpoint SL Runner (1:{target_rr})", all_trades)

def main():
    universe = load_preindexed_universe()
    results = []
    
    print("\n" + "#"*75)
    print("   STARTING MASTER MULTI-STRATEGY QUANTITATIVE SUITE (2022-2026)")
    print("#"*75)
    
    # 1. ChartMine Open=High Shorts (1:2.0, 1:2.5, 1:3.0)
    for rr in [2.0, 2.5, 3.0]:
        results.append(test_open_high_short_runners(universe, target_rr=rr))
        
    # 2. SMC Liquidity Sweep + FVG Retest (1:2.0, 1:2.5, 1:3.0)
    for rr in [2.0, 2.5, 3.0]:
        results.append(test_smc_liquidity_sweep(universe, target_rr=rr))
        
    # 3. SMC Order Block + OTE Fib (1:2.0, 1:2.5, 1:3.0)
    for rr in [2.0, 2.5, 3.0]:
        results.append(test_order_block_fib(universe, target_rr=rr))
        
    # 4. Multi-Timeframe Trend + VWAP Pullback (1:2.0, 1:2.5, 1:3.0)
    for rr in [2.0, 2.5, 3.0]:
        results.append(test_mtf_vwap_pullback(universe, target_rr=rr))
        
    # 5. 15m ORB Runner (1:2.0, 1:3.0)
    for rr in [2.0, 3.0]:
        results.append(test_orb_15m_runners(universe, target_rr=rr))
        
    df_summary = pd.DataFrame(results)
    df_summary.to_csv("research/phase4_2/master_suite_summary.csv", index=False)
    
    print("\n" + "="*85)
    print("                       MASTER COMPARATIVE LEADERBOARD")
    print("="*85)
    cols = ['Name', 'Trades', 'WinRate', 'PF', 'NetPnL', 'TotalR', 'MaxDD', 'AvgMonthlyPct', 'Status']
    print(df_summary[cols].to_string())
    print("="*85)

if __name__ == '__main__':
    main()
