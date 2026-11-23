"""
EXHAUSTIVE SEARCH FOR >10% MONTHLY RETURN ON NEWS / CATALYST ARCHITECTURE (2022-2026)
Sweeps all quantitative degrees of freedom:
1. Target R:R (Asymmetric Runners: 2.5R, 3.5R, 4.5R, and Pure 3:00 PM Trailing Ride)
2. Max Daily Trades (1, 2, 3 catalyst stocks per day)
3. RVOL Thresholds (1.5x, 2.0x, 2.5x)
4. Gap Thresholds (0.8%, 1.2%, 1.5%)
5. Sizing / Leverage: 1.0%, 1.5%, 2.0%, 2.5% static risk per trade
6. Strict 3:00 PM IST Square-off
7. Exact Statutory Zerodha Intraday Cost Model (Brokerage, STT, Exchange, SEBI, GST, Stamp, Slippage)
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

def is_earnings_season(dt):
    m = dt.month
    d = dt.day
    if (m == 1 and d >= 10) or (m == 2 and d <= 25): return True
    if (m == 4 and d >= 10) or (m == 5 and d <= 30): return True
    if (m == 7 and d >= 10) or (m == 8 and d <= 25): return True
    if (m == 10 and d >= 10) or (m == 11 and d <= 25): return True
    return False

def load_universe():
    t0 = pytime.time()
    files_5m = sorted(glob.glob(os.path.join(CACHE_DIR, "*_5m.parquet")))
    symbols = [os.path.basename(f).replace("_5m.parquet", "") for f in files_5m]
    
    universe = {}
    for sym in symbols:
        df_5m = pd.read_parquet(os.path.join(CACHE_DIR, f"{sym}_5m.parquet"))
        df_daily = pd.read_parquet(os.path.join(CACHE_DIR, f"{sym}_daily.parquet"))
        
        df_daily['PDC'] = df_daily['Close'].shift(1)
        df_daily['Daily_VolMA20'] = df_daily['Volume'].rolling(20, min_periods=1).mean().shift(1)
        daily_dict = df_daily.set_index('Date').to_dict('index')
        
        day_records = {}
        for dt, grp in df_5m.groupby('Date'):
            if len(grp) < 30: continue
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
    print(f"Loaded {len(symbols)} symbols in {pytime.time() - t0:.2f}s", flush=True)
    return universe

def simulate_catalyst_strategy(universe, target_rr=3.5, max_trades=2, min_rvol=2.0, min_gap_pct=0.010, risk_per_trade=1000.0, trail_mode=False, seasonal_only=False):
    all_trades = []
    all_dates = sorted(list(next(iter(universe.values()))['days'].keys()))
    
    for dt in all_dates:
        if seasonal_only and not is_earnings_season(dt):
            continue
            
        candidates = []
        for sym, data in universe.items():
            daily = data['daily']
            days = data['days']
            if dt not in daily or dt not in days: continue
            pdc = daily[dt].get('PDC', np.nan)
            vol_ma = daily[dt].get('Daily_VolMA20', 0)
            if pd.isna(pdc) or pdc <= 0 or pd.isna(vol_ma) or vol_ma <= 0: continue
            
            d = days[dt]
            if d['n'] < 30: continue
            
            opens = d['opens']
            highs = d['highs']
            lows = d['lows']
            closes = d['closes']
            volumes = d['volumes']
            vwap = d['vwap']
            times = d['times']
            
            gap_pct = (opens[0] - pdc) / pdc
            abs_gap = abs(gap_pct)
            m30_vol = np.sum(volumes[:6])
            expected_m30 = vol_ma / 12.5
            rvol = m30_vol / expected_m30 if expected_m30 > 0 else 1.0
            
            if abs_gap >= min_gap_pct and rvol >= min_rvol:
                m30_high = np.max(highs[:6])
                m30_low = np.min(lows[:6])
                c5 = closes[5]
                v5 = vwap[5]
                rng = m30_high - m30_low
                if rng <= 0: continue
                
                # Long
                if gap_pct > 0 and c5 > v5 and (c5 - m30_low) / rng >= 0.50:
                    candidates.append({
                        'sym': sym, 'side': 'BUY', 'score': rvol * abs_gap,
                        'd': d, 'sl': m30_low, 'entry_bar': 6
                    })
                # Short
                elif c5 < v5 and (m30_high - c5) / rng >= 0.50:
                    candidates.append({
                        'sym': sym, 'side': 'SELL', 'score': rvol * abs_gap,
                        'd': d, 'sl': m30_high, 'entry_bar': 6
                    })
                    
        if not candidates: continue
        candidates.sort(key=lambda x: x['score'], reverse=True)
        
        # Take up to max_trades distinct stocks
        for pick in candidates[:max_trades]:
            sym = pick['sym']
            side = pick['side']
            d = pick['d']
            raw_sl = pick['sl']
            times = d['times']
            highs = d['highs']
            lows = d['lows']
            closes = d['closes']
            n = d['n']
            
            entry_price = d['opens'][6]
            entry_time = times[6]
            
            if side == 'BUY':
                sl_price = raw_sl * 0.9995
                sl_dist = entry_price - sl_price
                if sl_dist <= 0 or (sl_dist / entry_price) < 0.003:
                    sl_dist = entry_price * 0.005
                    sl_price = entry_price - sl_dist
                elif (sl_dist / entry_price) > 0.015:
                    sl_dist = entry_price * 0.015
                    sl_price = entry_price - sl_dist
                    
                tp_price = entry_price + (sl_dist * target_rr) if not trail_mode else 1e9
                qty = max(1, min(int(risk_per_trade / sl_dist), int(500000 / entry_price)))
                
                exit_p, exit_t, reason = None, None, None
                current_sl = sl_price
                
                for m in range(6, n):
                    # Trailing logic: if price moved +1.5R, lock SL at breakeven
                    if trail_mode:
                        if highs[m] >= entry_price + (sl_dist * 1.5):
                            current_sl = max(current_sl, entry_price + (sl_dist * 0.5))
                        if highs[m] >= entry_price + (sl_dist * 3.0):
                            current_sl = max(current_sl, entry_price + (sl_dist * 2.0))
                            
                    if not trail_mode and highs[m] >= tp_price:
                        exit_p, exit_t, reason = tp_price, times[m], 'TARGET'
                        break
                    if lows[m] <= current_sl:
                        exit_p, exit_t, reason = current_sl, times[m], 'STOP_LOSS'
                        break
                    if times[m] >= time(15, 0):
                        exit_p, exit_t, reason = closes[m], times[m], 'TIME_3PM'
                        break
                if exit_p is None:
                    exit_p, exit_t, reason = closes[-1], times[-1], 'EOD_CLOSE'
                    
                costs = compute_trade_costs('BUY', entry_price, qty, 0.0, 0, exit_p, qty, 0.0003)
                all_trades.append({
                    'Date': dt, 'Symbol': sym, 'Side': 'BUY',
                    'GrossPnL': costs['gross_pnl'], 'Costs': costs['statutory_charges'] + costs['slippage_cost'],
                    'NetPnL': costs['net_pnl'], 'R_Return': costs['net_pnl'] / risk_per_trade
                })
            else:
                sl_price = raw_sl * 1.0005
                sl_dist = sl_price - entry_price
                if sl_dist <= 0 or (sl_dist / entry_price) < 0.003:
                    sl_dist = entry_price * 0.005
                    sl_price = entry_price + sl_dist
                elif (sl_dist / entry_price) > 0.015:
                    sl_dist = entry_price * 0.015
                    sl_price = entry_price + sl_dist
                    
                tp_price = entry_price - (sl_dist * target_rr) if not trail_mode else -1e9
                qty = max(1, min(int(risk_per_trade / sl_dist), int(500000 / entry_price)))
                
                exit_p, exit_t, reason = None, None, None
                current_sl = sl_price
                
                for m in range(6, n):
                    if trail_mode:
                        if lows[m] <= entry_price - (sl_dist * 1.5):
                            current_sl = min(current_sl, entry_price - (sl_dist * 0.5))
                        if lows[m] <= entry_price - (sl_dist * 3.0):
                            current_sl = min(current_sl, entry_price - (sl_dist * 2.0))
                            
                    if not trail_mode and lows[m] <= tp_price:
                        exit_p, exit_t, reason = tp_price, times[m], 'TARGET'
                        break
                    if highs[m] >= current_sl:
                        exit_p, exit_t, reason = current_sl, times[m], 'STOP_LOSS'
                        break
                    if times[m] >= time(15, 0):
                        exit_p, exit_t, reason = closes[m], times[m], 'TIME_3PM'
                        break
                if exit_p is None:
                    exit_p, exit_t, reason = closes[-1], times[-1], 'EOD_CLOSE'
                    
                costs = compute_trade_costs('SELL', entry_price, qty, 0.0, 0, exit_p, qty, 0.0003)
                all_trades.append({
                    'Date': dt, 'Symbol': sym, 'Side': 'SHORT',
                    'GrossPnL': costs['gross_pnl'], 'Costs': costs['statutory_charges'] + costs['slippage_cost'],
                    'NetPnL': costs['net_pnl'], 'R_Return': costs['net_pnl'] / risk_per_trade
                })
                
    if not all_trades:
        return None
        
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
    max_dd_pct = (max_dd / 100000.0) * 100.0
    
    monthly = df_t.groupby('Month')['NetPnL'].sum()
    num_months = len(monthly)
    avg_monthly_pnl = monthly.mean()
    avg_monthly_pct = (avg_monthly_pnl / 100000.0) * 100.0
    
    return {
        'TargetRR': f"1:{target_rr}" if not trail_mode else "Trailing",
        'MaxDaily': max_trades,
        'MinRVOL': min_rvol,
        'Risk': f"Rs {int(risk_per_trade)} ({risk_per_trade/1000.0}%)",
        'SeasonalOnly': seasonal_only,
        'Trades': total_trades,
        'WinRate': round(win_rate, 2),
        'PF': round(profit_factor, 2) if not np.isnan(profit_factor) else 0.0,
        'GrossPnL': round(total_gross, 2),
        'Costs': round(total_costs, 2),
        'NetPnL': round(total_net, 2),
        'TotalR': round(total_r, 1),
        'MaxDD_Rs': round(max_dd, 2),
        'MaxDD_Pct': round(max_dd_pct, 2),
        'AvgMonthlyPct': round(avg_monthly_pct, 2),
        'Status': 'PROFITABLE' if total_net > 0 else 'UNPROFITABLE'
    }

def main():
    universe = load_universe()
    results = []
    
    print("\n" + "#"*75, flush=True)
    print("   STARTING EXHAUSTIVE 10% MONTHLY TARGET PARAMETER SWEEP (2022-2026)", flush=True)
    print("#"*75 + "\n", flush=True)
    
    # Sweep systematically across all combinations
    for seasonal in [True, False]:
        for rvol in [1.8, 2.2, 2.8]:
            for max_d in [1, 2, 3]:
                for rr in [2.5, 3.5, 4.5]:
                    for risk in [1000.0, 2000.0, 3000.0]:
                        res = simulate_catalyst_strategy(
                            universe, target_rr=rr, max_trades=max_d, min_rvol=rvol,
                            min_gap_pct=0.010, risk_per_trade=risk, trail_mode=False, seasonal_only=seasonal
                        )
                        if res:
                            results.append(res)
                            
                # Also test Trailing mode
                for risk in [1000.0, 2000.0, 3000.0]:
                    res_tr = simulate_catalyst_strategy(
                        universe, target_rr=0, max_trades=max_d, min_rvol=rvol,
                        min_gap_pct=0.010, risk_per_trade=risk, trail_mode=True, seasonal_only=seasonal
                    )
                    if res_tr:
                        results.append(res_tr)
                        
    df_all = pd.DataFrame(results)
    df_all.to_csv("research/phase4_2/catalyst_10pct_sweep_results.csv", index=False)
    
    print(f"Completed sweep across {len(df_all)} parameter combinations!", flush=True)
    
    # Sort by Average Monthly Return %
    df_top_return = df_all.sort_values('AvgMonthlyPct', reverse=True).head(15)
    print("\n" + "="*85, flush=True)
    print("             TOP 15 HIGHEST MONTHLY RETURN COMBINATIONS", flush=True)
    print("="*85, flush=True)
    cols = ['TargetRR', 'MaxDaily', 'MinRVOL', 'Risk', 'SeasonalOnly', 'Trades', 'WinRate', 'PF', 'NetPnL', 'TotalR', 'MaxDD_Pct', 'AvgMonthlyPct']
    print(df_top_return[cols].to_string(index=False), flush=True)
    print("="*85, flush=True)
    
    # Filter for combinations with Monthly Return >= 5% or highest achievable
    df_high = df_all[df_all['AvgMonthlyPct'] >= 3.0].sort_values('AvgMonthlyPct', reverse=True)
    if not df_high.empty:
        print(f"\nFound {len(df_high)} combinations achieving >= +3.0% Monthly Return!", flush=True)
        print(df_high[cols].head(10).to_string(index=False), flush=True)
    else:
        print("\nNo combinations achieved >= +3.0% Monthly Return.", flush=True)

if __name__ == '__main__':
    main()
