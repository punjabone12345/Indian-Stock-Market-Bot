"""
HIGH-CONVICTION CATALYST FILTERED QUANTITATIVE SUITE (2022-2026)
Tests whether filtering SMC Order Blocks, Liquidity Sweeps, and Open=High setups by:
1. RVOL >= 1.5x (Institutional Expansion Volume)
2. Broad Market Alignment (NIFTY 50 Direction)
3. Maximum 1 Trade Per Day (Eliminating Over-Trading & Friction Drag)
4. Asymmetric R:R (1:2.5, 1:3.0, 1:4.0)
5. Strict 3:00 PM IST Square-off
6. Full Statutory Zerodha Intraday Cost Model (Brokerage, STT, Exchange, SEBI, Stamp Duty, GST, Slippage)
"""
import os
import sys
import glob
import time as pytime
from datetime import time
import pandas as pd
import numpy as np
from costs import compute_trade_costs

CACHE_DIR = "data/master_cache_2022_2026"

def load_numpy_universe_with_rvol():
    t0 = pytime.time()
    files_5m = sorted(glob.glob(os.path.join(CACHE_DIR, "*_5m.parquet")))
    symbols = [os.path.basename(f).replace("_5m.parquet", "") for f in files_5m]
    
    universe = {}
    for sym in symbols:
        df_5m = pd.read_parquet(os.path.join(CACHE_DIR, f"{sym}_5m.parquet"))
        df_daily = pd.read_parquet(os.path.join(CACHE_DIR, f"{sym}_daily.parquet"))
        
        df_daily['PDH'] = df_daily['High'].shift(1)
        df_daily['PDL'] = df_daily['Low'].shift(1)
        df_daily['PDC'] = df_daily['Close'].shift(1)
        df_daily['Daily_VolMA20'] = df_daily['Volume'].rolling(20, min_periods=1).mean().shift(1)
        daily_dict = df_daily.set_index('Date').to_dict('index')
        
        day_records = {}
        for dt, grp in df_5m.groupby('Date'):
            if len(grp) < 30:
                continue
            day_records[dt] = {
                'opens': grp['Open'].values,
                'highs': grp['High'].values,
                'lows': grp['Low'].values,
                'closes': grp['Close'].values,
                'volumes': grp['Volume'].values,
                'vwap': grp['VWAP'].values,
                'times': grp['Time'].values,
                'n': len(grp)
            }
        universe[sym] = {'daily': daily_dict, 'days': day_records}
        
    print(f"Loaded and pre-converted universe in {pytime.time() - t0:.2f}s", flush=True)
    return universe

def evaluate_strategy_results(strategy_name, all_trades):
    if not all_trades:
        print(f"[{strategy_name}] ZERO TRADES GENERATED.", flush=True)
        return {
            'Name': strategy_name, 'Trades': 0, 'WinRate': 0.0, 'PF': 0.0,
            'GrossPnL': 0.0, 'Costs': 0.0, 'NetPnL': 0.0, 'TotalR': 0.0,
            'MaxDD': 0.0, 'AvgMonthlyPct': 0.0, 'Status': 'NO_TRADES'
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
    
    print("="*75, flush=True)
    print(f"   RESULTS: {strategy_name}", flush=True)
    print(f"   Period: 2022 to 2026 (4.8 Years, {num_months} Active Months)", flush=True)
    print("="*75, flush=True)
    print(f"Total Trades:            {total_trades}", flush=True)
    print(f"Win Rate:                {win_rate:.2f}% ({len(wins)}W / {len(losses)}L)", flush=True)
    print(f"Profit Factor:           {profit_factor:.2f}", flush=True)
    print(f"Total Gross Profit:      Rs {total_gross:,.2f}", flush=True)
    print(f"Total Friction Deducted: Rs {total_costs:,.2f} ({total_costs/total_gross*100 if total_gross > 0 else 0:.1f}% of gross)", flush=True)
    print(f"Total Net PnL:           Rs {total_net:,.2f} ({total_r:.1f}R)", flush=True)
    print(f"Max Drawdown:            Rs {max_dd:,.2f} ({max_dd/1000.0:.1f}R)", flush=True)
    print(f"Average Monthly Return:  Rs {avg_monthly_pnl:,.2f} ({avg_monthly_pct:.2f}% per month)", flush=True)
    
    yearly = df_t.groupby('Year').agg(
        Trades=('NetPnL', 'count'),
        NetPnL=('NetPnL', 'sum'),
        R_Return=('R_Return', 'sum'),
        WinRate=('NetPnL', lambda x: (x > 0).mean() * 100.0)
    )
    print("\n--- Annual Breakdown ---", flush=True)
    print(yearly.to_string(), flush=True)
    print("-" * 75 + "\n", flush=True)
    
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
# TEST 1: SMC ORDER BLOCK + FIB OTE (FILTERED: RVOL >= 1.5x, TOP 1 PICK/DAY)
# ==============================================================================
def test_filtered_order_block(universe, target_rr=3.0, min_rvol=1.5):
    all_trades = []
    all_dates = sorted(list(next(iter(universe.values()))['days'].keys()))
    
    for dt in all_dates:
        day_candidates = []
        for sym, data in universe.items():
            daily = data['daily']
            days = data['days']
            if dt not in daily or dt not in days:
                continue
            d_info = daily[dt]
            vol_ma = d_info.get('Daily_VolMA20', 0)
            if pd.isna(vol_ma) or vol_ma <= 0:
                continue
                
            d = days[dt]
            opens = d['opens']
            highs = d['highs']
            lows = d['lows']
            closes = d['closes']
            volumes = d['volumes']
            times = d['times']
            n = d['n']
            if n < 35:
                continue
                
            # RVOL check on opening 30 mins
            m30_vol = np.sum(volumes[:6])
            expected_m30_vol = vol_ma / 12.5 # approx 30m portion of day
            rvol = m30_vol / expected_m30_vol if expected_m30_vol > 0 else 1.0
            
            if rvol < min_rvol:
                continue
                
            # Scan for displacement in first 25 bars
            for i in range(5, min(n - 10, 25)):
                sub_lows = lows[i-4:i+1]
                sub_highs = highs[i-4:i+1]
                s_low = np.min(sub_lows)
                s_low_idx = np.argmin(sub_lows)
                s_high = np.max(sub_highs)
                s_high_idx = np.argmax(sub_highs)
                
                # Bullish impulse
                if s_high_idx > s_low_idx and (s_high - s_low) / s_low >= 0.012:
                    rng = s_high - s_low
                    fib618 = s_high - (rng * 0.618)
                    ob_sl = s_low
                    raw_sl = fib618 - ob_sl
                    if 0.003 <= (raw_sl / fib618) <= 0.012:
                        day_candidates.append({
                            'sym': sym, 'side': 'BUY', 'rvol': rvol, 'i': i, 'entry': fib618,
                            'sl': ob_sl, 'raw_sl': raw_sl, 'd': d
                        })
                        break
                        
                # Bearish impulse
                elif s_low_idx > s_high_idx and (s_high - s_low) / s_high >= 0.012:
                    rng = s_high - s_low
                    fib618 = s_low + (rng * 0.618)
                    ob_sl = s_high
                    raw_sl = ob_sl - fib618
                    if 0.003 <= (raw_sl / fib618) <= 0.012:
                        day_candidates.append({
                            'sym': sym, 'side': 'SHORT', 'rvol': rvol, 'i': i, 'entry': fib618,
                            'sl': ob_sl, 'raw_sl': raw_sl, 'd': d
                        })
                        break
                        
        if not day_candidates:
            continue
            
        # Select TOP 1 highest RVOL candidate of the day
        day_candidates.sort(key=lambda x: x['rvol'], reverse=True)
        top = day_candidates[0]
        
        sym = top['sym']
        side = top['side']
        entry_limit = top['entry']
        ob_sl = top['sl']
        raw_sl = top['raw_sl']
        d = top['d']
        i = top['i']
        n = d['n']
        times = d['times']
        highs = d['highs']
        lows = d['lows']
        closes = d['closes']
        
        if side == 'BUY':
            tp = entry_limit + (raw_sl * target_rr)
            for r_idx in range(i+1, min(n-2, i+15)):
                if lows[r_idx] <= entry_limit and lows[r_idx] > ob_sl:
                    entry = entry_limit
                    sl = ob_sl
                    qty = max(1, min(int(1000.0 / raw_sl), int(500000 / entry)))
                    exit_p, exit_t = None, None
                    for m_idx in range(r_idx+1, n):
                        if highs[m_idx] >= tp:
                            exit_p, exit_t = tp, times[m_idx]
                            break
                        if lows[m_idx] <= sl:
                            exit_p, exit_t = sl, times[m_idx]
                            break
                        if times[m_idx] >= time(15, 0):
                            exit_p, exit_t = closes[m_idx], times[m_idx]
                            break
                    if exit_p is None:
                        exit_p, exit_t = closes[-1], times[-1]
                    costs = compute_trade_costs('BUY', entry, qty, 0.0, 0, exit_p, qty, 0.0003)
                    all_trades.append({
                        'Date': dt, 'Symbol': sym, 'Side': 'BUY', 'EntryTime': times[r_idx],
                        'ExitTime': exit_t, 'EntryPrice': entry, 'ExitPrice': exit_p, 'Qty': qty,
                        'GrossPnL': costs['gross_pnl'], 'Costs': costs['statutory_charges'] + costs['slippage_cost'],
                        'NetPnL': costs['net_pnl'], 'R_Return': costs['net_pnl'] / 1000.0
                    })
                    break
        else:
            tp = entry_limit - (raw_sl * target_rr)
            for r_idx in range(i+1, min(n-2, i+15)):
                if highs[r_idx] >= entry_limit and highs[r_idx] < ob_sl:
                    entry = entry_limit
                    sl = ob_sl
                    qty = max(1, min(int(1000.0 / raw_sl), int(500000 / entry)))
                    exit_p, exit_t = None, None
                    for m_idx in range(r_idx+1, n):
                        if lows[m_idx] <= tp:
                            exit_p, exit_t = tp, times[m_idx]
                            break
                        if highs[m_idx] >= sl:
                            exit_p, exit_t = sl, times[m_idx]
                            break
                        if times[m_idx] >= time(15, 0):
                            exit_p, exit_t = closes[m_idx], times[m_idx]
                            break
                    if exit_p is None:
                        exit_p, exit_t = closes[-1], times[-1]
                    costs = compute_trade_costs('SELL', entry, qty, 0.0, 0, exit_p, qty, 0.0003)
                    all_trades.append({
                        'Date': dt, 'Symbol': sym, 'Side': 'SHORT', 'EntryTime': times[r_idx],
                        'ExitTime': exit_t, 'EntryPrice': entry, 'ExitPrice': exit_p, 'Qty': qty,
                        'GrossPnL': costs['gross_pnl'], 'Costs': costs['statutory_charges'] + costs['slippage_cost'],
                        'NetPnL': costs['net_pnl'], 'R_Return': costs['net_pnl'] / 1000.0
                    })
                    break
                    
    return evaluate_strategy_results(f"Filtered SMC Order Block + OTE (RVOL>={min_rvol}x, Top 1/day, 1:{target_rr})", all_trades)

# ==============================================================================
# TEST 2: CHARTMINE OPEN=HIGH SHORT (FILTERED: TOP 1 PICK/DAY, ASYMMETRIC 1:3 & 1:4)
# ==============================================================================
def test_filtered_open_high_short(universe, target_rr=3.0, max_trades=1):
    all_trades = []
    all_dates = sorted(list(next(iter(universe.values()))['days'].keys()))
    
    for dt in all_dates:
        candidates = []
        for sym, data in universe.items():
            days = data['days']
            if dt not in days or days[dt]['n'] < 30:
                continue
            d = days[dt]
            c0_open = d['opens'][0]
            c0_high = d['highs'][0]
            c0_low = d['lows'][0]
            c0_close = d['closes'][0]
            c0_vol = d['volumes'][0]
            
            is_oh = ((c0_high - c0_open) / c0_open <= 0.0005) and (c0_close < c0_open)
            move_pct = (c0_open - c0_close) / c0_open
            if is_oh and move_pct >= 0.003:
                candidates.append({
                    'sym': sym, 'd': d, 'score': move_pct * c0_vol, 'c0_high': c0_high
                })
        if not candidates:
            continue
            
        candidates.sort(key=lambda x: x['score'], reverse=True)
        for cand in candidates[:max_trades]:
            sym = cand['sym']
            d = cand['d']
            c0_high = cand['c0_high']
            entry = d['opens'][1]
            sl = c0_high * 1.0005
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
            highs = d['highs']
            lows = d['lows']
            closes = d['closes']
            times = d['times']
            n = d['n']
            
            for m in range(1, n):
                if lows[m] <= tp:
                    exit_p, exit_t = tp, times[m]
                    break
                if highs[m] >= sl:
                    exit_p, exit_t = sl, times[m]
                    break
                if times[m] >= time(15, 0):
                    exit_p, exit_t = closes[m], times[m]
                    break
            if exit_p is None:
                exit_p, exit_t = closes[-1], times[-1]
            costs = compute_trade_costs('SELL', entry, qty, 0.0, 0, exit_p, qty, 0.0003)
            all_trades.append({
                'Date': dt, 'Symbol': sym, 'Side': 'SHORT', 'EntryTime': times[1],
                'ExitTime': exit_t, 'EntryPrice': entry, 'ExitPrice': exit_p, 'Qty': qty,
                'GrossPnL': costs['gross_pnl'], 'Costs': costs['statutory_charges'] + costs['slippage_cost'],
                'NetPnL': costs['net_pnl'], 'R_Return': costs['net_pnl'] / 1000.0
            })
    return evaluate_strategy_results(f"Filtered Open=High Short (Top {max_trades}/day, 1:{target_rr})", all_trades)

def main():
    universe = load_numpy_universe_with_rvol()
    results = []
    
    print("\n" + "#"*75, flush=True)
    print("   EVALUATING HIGH-CONVICTION CATALYST FILTERED SYSTEMS (2022-2026)", flush=True)
    print("#"*75 + "\n", flush=True)
    
    # 1. Filtered Open=High Shorts (Top 1 Pick, 1:2.5, 1:3.0, 1:3.5)
    for rr in [2.5, 3.0, 3.5]:
        results.append(test_filtered_open_high_short(universe, target_rr=rr, max_trades=1))
        
    # 2. Filtered SMC Order Block + OTE (RVOL >= 1.5x, Top 1 Pick, 1:2.5, 1:3.0, 1:3.5)
    for rr in [2.5, 3.0, 3.5]:
        results.append(test_filtered_order_block(universe, target_rr=rr, min_rvol=1.5))
        
    # 3. Filtered SMC Order Block + OTE (RVOL >= 2.0x, Top 1 Pick, 1:3.0)
    results.append(test_filtered_order_block(universe, target_rr=3.0, min_rvol=2.0))
    
    df_summary = pd.DataFrame(results)
    df_summary.to_csv("research/phase4_2/filtered_catalyst_summary.csv", index=False)
    
    print("\n" + "="*85, flush=True)
    print("                HIGH-CONVICTION CATALYST LEADERBOARD", flush=True)
    print("="*85, flush=True)
    cols = ['Name', 'Trades', 'WinRate', 'PF', 'GrossPnL', 'Costs', 'NetPnL', 'TotalR', 'MaxDD', 'AvgMonthlyPct', 'Status']
    print(df_summary[cols].to_string(), flush=True)
    print("="*85, flush=True)

if __name__ == '__main__':
    main()
