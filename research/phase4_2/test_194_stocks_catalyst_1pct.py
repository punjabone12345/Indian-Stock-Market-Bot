"""
BACKTEST ON 194 STOCKS UNIVERSE (NIFTY 200) WITH STRICT 1.0% RISK PER TRADE
Evaluates the Institutional Catalyst & Relative Strength System on 194 stocks
Dataset: 1-Hour Intraday Data + 5-Year Daily Parquets from data/nifty200_1h_cache/ and data/nifty200_daily_cache/
Mandate: Risk per trade strictly fixed at 1.0% (Rs 1,000 on Rs 1L base capital).
Exit: Strict 3:00 PM IST Square-off.
Costs: Full Zerodha Statutory Taxes (Brokerage, STT, Exchange, SEBI, GST, Stamp) + 0.03% Slippage.
"""

import os
import sys
import glob
import time as pytime
from datetime import time
import pandas as pd
import numpy as np

sys.path.append(os.path.dirname(__file__))
from costs import compute_trade_costs

CACHE_1H = "data/nifty200_1h_cache"
CACHE_DAILY = "data/nifty200_daily_cache"

def load_194_universe():
    t0 = pytime.time()
    files_1h = sorted(glob.glob(os.path.join(CACHE_1H, "*.parquet")))
    symbols = [os.path.basename(f).replace(".parquet", "") for f in files_1h]
    print(f"Loading {len(symbols)} stocks from 1-hour and daily caches...", flush=True)
    
    universe = {}
    for sym in symbols:
        p_1h = os.path.join(CACHE_1H, f"{sym}.parquet")
        p_d = os.path.join(CACHE_DAILY, f"{sym}.parquet")
        if not os.path.exists(p_1h) or not os.path.exists(p_d):
            continue
            
        df_1h = pd.read_parquet(p_1h)
        df_daily = pd.read_parquet(p_d)
        
        # Prepare daily
        df_daily['PDC'] = df_daily['Close'].shift(1)
        df_daily['Daily_VolMA20'] = df_daily['Volume'].rolling(20, min_periods=1).mean().shift(1)
        df_daily['date_str'] = pd.to_datetime(df_daily['Date']).dt.date.astype(str)
        daily_dict = df_daily.set_index('date_str').to_dict('index')
        
        # Prepare 1h grouped by date_str
        df_1h['Date_dt'] = pd.to_datetime(df_1h['Date'])
        df_1h['date_str'] = df_1h['Date_dt'].dt.date.astype(str)
        df_1h['time_str'] = df_1h['Date_dt'].dt.time.astype(str)
        
        day_records = {}
        for dt, grp in df_1h.groupby('date_str'):
            if len(grp) < 5: continue
            day_records[dt] = {
                'opens': grp['Open'].values,
                'highs': grp['High'].values,
                'lows': grp['Low'].values,
                'closes': grp['Close'].values,
                'volumes': grp['Volume'].values,
                'times': grp['time_str'].values,
                'n': len(grp)
            }
        universe[sym] = {'daily': daily_dict, 'days': day_records}
        
    print(f"Successfully pre-indexed {len(universe)} stocks in {pytime.time() - t0:.2f}s", flush=True)
    return universe

def simulate_194_system(universe,
                         min_gap=0.010,       # 1.0% morning gap
                         min_rvol=1.8,        # 1.8x first-hour volume
                         target_rr=3.5,       # 2.5R, 3.5R, or Trailing
                         trail_mode=False,
                         max_daily_trades=2,  # 1, 2, or 3 trades/day
                         mode='STATIC',       # 'STATIC' (Rs 1,000 flat) or 'DYNAMIC' (1.0% of equity)
                         start_cap=100000.0):
    
    # Collect all common trading dates across universe
    sample_sym = 'RELIANCE' if 'RELIANCE' in universe else next(iter(universe.keys()))
    all_dates = sorted(list(universe[sample_sym]['days'].keys()))
    
    equity = start_cap
    peak = start_cap
    max_dd_rs = 0.0
    max_dd_pct = 0.0
    trades = []
    
    for dt in all_dates:
        candidates = []
        for sym, sdata in universe.items():
            daily = sdata['daily']
            days = sdata['days']
            if dt not in daily or dt not in days: continue
            
            d_info = daily[dt]
            pdc = d_info.get('PDC', np.nan)
            vol_ma = d_info.get('Daily_VolMA20', 0)
            if pd.isna(pdc) or pdc <= 0 or pd.isna(vol_ma) or vol_ma <= 0: continue
            
            d = days[dt]
            if d['n'] < 5: continue
            
            opens = d['opens']
            highs = d['highs']
            lows = d['lows']
            closes = d['closes']
            volumes = d['volumes']
            times = d['times']
            
            # First bar is 09:15 - 10:15
            if times[0] != '09:15:00': continue
            
            o_0 = opens[0]
            c_0 = closes[0]
            h_0 = highs[0]
            l_0 = lows[0]
            v_0 = volumes[0]
            
            # Gap %
            gap_pct = (o_0 - pdc) / pdc
            
            # Return of 1st hour
            ret_1h = (c_0 - o_0) / o_0
            
            # Expected 1st hour volume (morning hour typically trades ~20% of daily volume)
            exp_1h_vol = vol_ma * 0.20
            rvol = v_0 / exp_1h_vol if exp_1h_vol > 0 else 1.0
            
            # Long Setup Criteria:
            # 1. Gap up >= min_gap or First hour surge >= 1.2%
            # 2. RVOL >= min_rvol
            # 3. Bar 0 closes in upper 50% of its range and above Open
            rng_0 = h_0 - l_0
            if rng_0 <= 0: continue
            pos_in_rng = (c_0 - l_0) / rng_0
            
            if (gap_pct >= min_gap or ret_1h >= 0.012) and rvol >= min_rvol and ret_1h > 0 and pos_in_rng >= 0.55:
                score = (ret_1h * 100.0) * rvol
                candidates.append({
                    'sym': sym, 'side': 'BUY', 'score': score,
                    'd': d, 'sl_raw': l_0, 'rvol': rvol
                })
                
        if not candidates: continue
        candidates.sort(key=lambda x: x['score'], reverse=True)
        
        # Take up to max_daily_trades
        for pick in candidates[:max_daily_trades]:
            sym = pick['sym']
            d = pick['d']
            sl_raw = pick['sl_raw']
            
            opens = d['opens']
            highs = d['highs']
            lows = d['lows']
            closes = d['closes']
            n = d['n']
            
            # Entry at Open of candle 1 (10:15 AM)
            entry_p = opens[1]
            
            # 1.0% Risk
            if mode == 'STATIC':
                current_risk = 1000.0 # Exactly Rs 1,000 flat
                max_pos = 500000.0    # 5x MIS margin on Rs 1L base
            else:
                current_risk = equity * 0.010 # 1.0% of current equity
                max_pos = equity * 5.0
                
            sl_dist = entry_p - (sl_raw * 0.9995)
            # Clamp SL distance between 0.4% and 1.8% to handle midcap volatility
            if sl_dist <= 0 or (sl_dist / entry_p) < 0.004:
                sl_dist = entry_p * 0.008 # Default 0.8% stop
            elif (sl_dist / entry_p) > 0.018:
                sl_dist = entry_p * 0.018
            sl_p = entry_p - sl_dist
            
            target_p = entry_p + (sl_dist * target_rr) if not trail_mode else 1e9
            
            qty = max(1, min(int(current_risk / sl_dist), int(max_pos / entry_p)))
            curr_sl = sl_p
            exit_p = None
            
            # Hourly candles:
            # Index 1: 10:15 - 11:15
            # Index 2: 11:15 - 12:15
            # Index 3: 12:15 - 13:15
            # Index 4: 13:15 - 14:15
            # Index 5: 14:15 - 15:15 (3:00 PM IST is 75% through this candle)
            for m in range(1, n):
                if trail_mode:
                    if highs[m] >= entry_p + (sl_dist * 1.5): curr_sl = max(curr_sl, entry_p + (sl_dist * 0.5))
                    if highs[m] >= entry_p + (sl_dist * 3.0): curr_sl = max(curr_sl, entry_p + (sl_dist * 2.0))
                    
                if not trail_mode and highs[m] >= target_p:
                    exit_p = target_p; break
                if lows[m] <= curr_sl:
                    exit_p = curr_sl; break
                if m == 5 or m == n - 1:
                    # 3:00 PM Square-off at bar 5 close
                    exit_p = closes[m]
                    break
                    
            if exit_p is None:
                exit_p = closes[-1]
                
            costs = compute_trade_costs('BUY', entry_p, qty, 0.0, 0, exit_p, qty, 0.0003)
            net_pnl = costs['net_pnl']
            equity += net_pnl
            if equity > peak: peak = equity
            dd_rs = peak - equity
            dd_pct = dd_rs / peak if peak > 0 else 0
            if dd_rs > max_dd_rs: max_dd_rs = dd_rs
            if dd_pct > max_dd_pct: max_dd_pct = dd_pct
            
            trades.append({
                'Date': dt, 'Symbol': sym, 'Side': 'BUY',
                'GrossPnL': costs['gross_pnl'],
                'Costs': costs['statutory_charges'] + costs['slippage_cost'],
                'NetPnL': net_pnl,
                'R': net_pnl / current_risk,
                'Equity': equity
            })
            
    if not trades: return None
    
    df_t = pd.DataFrame(trades)
    n_trades = len(df_t)
    wins = df_t[df_t['NetPnL'] > 0]
    win_rate = (len(wins) / n_trades) * 100.0
    gw = wins['GrossPnL'].sum()
    gl = abs(df_t[df_t['GrossPnL'] < 0]['GrossPnL'].sum())
    pf = gw / gl if gl > 0 else 99.0
    
    net_pnl = df_t['NetPnL'].sum()
    gross_pnl = df_t['GrossPnL'].sum()
    total_costs = df_t['Costs'].sum()
    total_r = df_t['R'].sum()
    
    # 728 trading days = approx 35 calendar months (Dec 2023 to Nov 2026)
    n_months = 35.0
    if mode == 'STATIC':
        avg_monthly_pct = (net_pnl / n_months / start_cap) * 100.0
        cagr = None
    else:
        avg_monthly_pct = (((equity / start_cap) ** (1.0 / n_months)) - 1.0) * 100.0
        cagr = ((equity / start_cap) ** (1.0 / (n_months / 12.0)) - 1.0) * 100.0
        
    df_t['Year'] = pd.to_datetime(df_t['Date']).dt.year
    yearly = df_t.groupby('Year')['NetPnL'].sum().to_dict()
    
    return {
        'MinGap': min_gap,
        'MinRVOL': min_rvol,
        'TargetRR': target_rr,
        'TrailMode': trail_mode,
        'MaxDaily': max_daily_trades,
        'Mode': mode,
        'Trades': n_trades,
        'MonthlyTrades': n_trades / n_months,
        'WinRate': win_rate,
        'PF': pf,
        'GrossPnL': gross_pnl,
        'Costs': total_costs,
        'NetPnL': net_pnl,
        'FinalEquity': equity,
        'TotalR': total_r,
        'MaxDD_Rs': max_dd_rs,
        'MaxDD_Pct': max_dd_pct * 100.0,
        'AvgMonthlyPct': avg_monthly_pct,
        'CAGR': cagr,
        'Y2023': yearly.get(2023, 0),
        'Y2024': yearly.get(2024, 0),
        'Y2025': yearly.get(2025, 0),
        'Y2026': yearly.get(2026, 0)
    }

def run_194_evaluation():
    universe = load_194_universe()
    
    print("\n--- Sweeping 194-Stock Universe Across Concurrency & Exits (Strict 1.0% Risk) ---", flush=True)
    
    gaps = [0.008, 0.012]
    rvols = [1.8, 2.2]
    targets = [2.5, 3.5]
    trails = [False, True]
    max_dailies = [1, 2, 3]
    modes = ['STATIC', 'DYNAMIC']
    
    results = []
    t_start = pytime.time()
    
    for g in gaps:
        for rv in rvols:
            for tgt in targets:
                for tr in trails:
                    for md in max_dailies:
                        for m in modes:
                            res = simulate_194_system(
                                universe,
                                min_gap=g,
                                min_rvol=rv,
                                target_rr=tgt,
                                trail_mode=tr,
                                max_daily_trades=md,
                                mode=m
                            )
                            if res:
                                results.append(res)
                                
    df_res = pd.DataFrame(results)
    out_path = "research/phase4_2/results_194_stocks_1pct_risk.csv"
    df_res.to_csv(out_path, index=False)
    print(f"\nEvaluated {len(df_res)} combinations on 194-stock universe in {pytime.time() - t_start:.2f}s. Saved to {out_path}.", flush=True)
    
    print("\n=== TOP 5 STATIC 1.0% RISK CONFIGURATIONS (194 STOCKS) ===")
    s_top = df_res[df_res['Mode'] == 'STATIC'].sort_values('NetPnL', ascending=False).head(5)
    cols = ['MinGap', 'MinRVOL', 'TargetRR', 'TrailMode', 'MaxDaily', 'Trades', 'MonthlyTrades', 'WinRate', 'PF', 'NetPnL', 'TotalR', 'MaxDD_Pct', 'AvgMonthlyPct']
    print(s_top[cols].to_string())
    
    print("\n=== TOP 5 DYNAMIC 1.0% RISK COMPOUNDING CONFIGURATIONS (194 STOCKS) ===")
    d_top = df_res[df_res['Mode'] == 'DYNAMIC'].sort_values('FinalEquity', ascending=False).head(5)
    dcols = ['MinGap', 'MinRVOL', 'TargetRR', 'TrailMode', 'MaxDaily', 'Trades', 'MonthlyTrades', 'WinRate', 'PF', 'FinalEquity', 'NetPnL', 'CAGR', 'MaxDD_Pct', 'AvgMonthlyPct']
    print(d_top[dcols].to_string())

if __name__ == '__main__':
    run_194_evaluation()
