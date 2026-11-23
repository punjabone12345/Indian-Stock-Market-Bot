"""
DEDICATED 1.0% RISK PER TRADE OPTIMIZATION ENGINE (2022-2026)
Mandate: Risk per trade strictly fixed at 1.0% (Rs 1,000 on Rs 1L base capital).
Tests:
1. All Catalyst Setups (Earnings, Sector Coordinated Catalyst, Confluence Ensemble)
2. Entry Confirmation Timings (15M, 30M, 45M)
3. Exit Rules (2.0R, 2.5R, 3.0R, 3.5R, Trailing ATR, Partial 2R + Trail)
4. Concurrency (1, 2, 3 trades per day)
5. Strict 3:00 PM IST Square-off
6. Full Statutory Zerodha Deductions + 0.03% Slippage
7. Both Static (Rs 1,000 flat) and Dynamic (1.0% of current equity)
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

CACHE_DIR = "data/master_cache_2022_2026"

SECTOR_MAP = {
    'BANKING': ['HDFCBANK', 'ICICIBANK', 'SBIN', 'KOTAKBANK', 'AXISBANK', 'INDUSINDBK', 'BAJFINANCE'],
    'IT': ['TCS', 'INFY', 'HCLTECH', 'WIPRO', 'TECHM'],
    'ENERGY': ['RELIANCE', 'ONGC', 'NTPC', 'POWERGRID', 'COALINDIA'],
    'METALS': ['TATASTEEL', 'JSWSTEEL'],
    'AUTO': ['MARUTI'],
    'FMCG': ['ITC', 'HINDUNILVR', 'TITAN'],
    'PHARMA': ['SUNPHARMA'],
    'INFRA': ['LT', 'ADANIENT', 'BHARTIARTL', 'GRASIM', 'ULTRACEMCO']
}

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

def precalculate_daily_features(universe):
    t0 = pytime.time()
    all_dates = sorted(list(next(iter(universe.values()))['days'].keys()))
    
    daily_cache = {}
    for dt in all_dates:
        stock_feats = {}
        for sym, data in universe.items():
            daily = data['daily']
            days = data['days']
            if dt not in daily or dt not in days: continue
            pdc = daily[dt].get('PDC', np.nan)
            vol_ma = daily[dt].get('Daily_VolMA20', 0)
            if pd.isna(pdc) or pdc <= 0 or pd.isna(vol_ma) or vol_ma <= 0: continue
            
            d = days[dt]
            if d['n'] < 70: continue
            
            opens = d['opens']
            highs = d['highs']
            lows = d['lows']
            closes = d['closes']
            volumes = d['volumes']
            vwap = d['vwap']
            
            gap_pct = (opens[0] - pdc) / pdc
            
            # 15m
            m15_high = np.max(highs[:3]); m15_low = np.min(lows[:3])
            m15_vol = np.sum(volumes[:3]); rvol_15 = m15_vol / (vol_ma / 25.0) if vol_ma > 0 else 1.0
            
            # 30m
            m30_high = np.max(highs[:6]); m30_low = np.min(lows[:6])
            m30_vol = np.sum(volumes[:6]); rvol_30 = m30_vol / (vol_ma / 12.5) if vol_ma > 0 else 1.0
            
            # 45m
            m45_high = np.max(highs[:9]); m45_low = np.min(lows[:9])
            m45_vol = np.sum(volumes[:9]); rvol_45 = m45_vol / (vol_ma / 8.33) if vol_ma > 0 else 1.0
            
            stock_feats[sym] = {
                'pdc': pdc, 'vol_ma': vol_ma, 'gap_pct': gap_pct, 'abs_gap': abs(gap_pct),
                'm15_high': m15_high, 'm15_low': m15_low, 'rvol_15': rvol_15,
                'm30_high': m30_high, 'm30_low': m30_low, 'rvol_30': rvol_30,
                'm45_high': m45_high, 'm45_low': m45_low, 'rvol_45': rvol_45,
                'd': d
            }
            
        sector_stats = {}
        for sec_name, syms in SECTOR_MAP.items():
            gaps = [stock_feats[s]['gap_pct'] for s in syms if s in stock_feats]
            if len(gaps) >= 2:
                med_gap = float(np.median(gaps))
                pos_breadth = sum(1 for g in gaps if g > 0.001) / len(gaps)
                neg_breadth = sum(1 for g in gaps if g < -0.001) / len(gaps)
                sector_stats[sec_name] = {
                    'med_gap': med_gap, 'abs_gap': abs(med_gap),
                    'pos_breadth': pos_breadth, 'neg_breadth': neg_breadth
                }
                
        daily_cache[dt] = {'stocks': stock_feats, 'sectors': sector_stats}
        
    print(f"Precalculated daily features for {len(daily_cache)} sessions in {pytime.time() - t0:.2f}s", flush=True)
    return daily_cache

def simulate_1pct_strategy(daily_cache,
                           entry_timing='45M',
                           catalyst_type='EARNINGS_ONLY',
                           min_gap=0.010,
                           min_rvol=2.2,
                           exit_mode='3.5R',
                           max_daily=2,
                           mode='STATIC', # 'STATIC' (Rs 1,000 flat) or 'DYNAMIC' (1.0% of equity)
                           start_cap=100000.0):
    
    if entry_timing == '15M':
        entry_idx = 3; conf_bar = 2; high_key = 'm15_high'; low_key = 'm15_low'; rvol_key = 'rvol_15'
    elif entry_timing == '30M':
        entry_idx = 6; conf_bar = 5; high_key = 'm30_high'; low_key = 'm30_low'; rvol_key = 'rvol_30'
    else: # 45M
        entry_idx = 9; conf_bar = 8; high_key = 'm45_high'; low_key = 'm45_low'; rvol_key = 'rvol_45'
        
    equity = start_cap
    peak = start_cap
    max_dd_rs = 0.0
    max_dd_pct = 0.0
    trades = []
    
    for dt, day_data in daily_cache.items():
        stock_feats = day_data['stocks']
        sector_stats = day_data['sectors']
        if not stock_feats: continue
        
        candidates = []
        
        # Sector catalyst check
        focus_sector, focus_bias = None, None
        if catalyst_type in ('SECTOR_ONLY', 'COMBINED') and sector_stats:
            sec_sorted = sorted(sector_stats.items(), key=lambda x: x[1]['abs_gap'], reverse=True)
            for sname, sdata in sec_sorted:
                if sdata['abs_gap'] >= 0.005:
                    if sdata['med_gap'] > 0 and sdata['pos_breadth'] >= 0.60:
                        focus_sector, focus_bias = sname, 'BUY'; break
                    elif sdata['med_gap'] < 0 and sdata['neg_breadth'] >= 0.60:
                        focus_sector, focus_bias = sname, 'SELL'; break
                        
        for sym, sf in stock_feats.items():
            d = sf['d']
            opens = d['opens']
            highs = d['highs']
            lows = d['lows']
            closes = d['closes']
            vwap = d['vwap']
            
            is_sec_stock = (focus_sector and sym in SECTOR_MAP.get(focus_sector, []))
            is_co_catalyst = (sf['abs_gap'] >= min_gap and sf[rvol_key] >= min_rvol)
            
            qualifies = False
            if catalyst_type == 'SECTOR_ONLY' and is_sec_stock: qualifies = True
            elif catalyst_type == 'EARNINGS_ONLY' and is_co_catalyst: qualifies = True
            elif catalyst_type == 'COMBINED' and (is_sec_stock or is_co_catalyst): qualifies = True
            if not qualifies: continue
            
            c_conf = closes[conf_bar]
            v_conf = vwap[conf_bar]
            o_0 = opens[0]
            
            # Long
            if c_conf > v_conf and c_conf > sf[low_key]:
                ret = (c_conf - o_0) / o_0
                score = (ret * 100.0) * sf[rvol_key]
                if is_sec_stock and focus_bias == 'BUY': score *= 1.3
                candidates.append({'sym': sym, 'side': 'BUY', 'score': score, 'd': d, 'sl_raw': sf[low_key]})
            # Short
            elif c_conf < v_conf and c_conf < sf[high_key]:
                ret = (o_0 - c_conf) / o_0
                score = (ret * 100.0) * sf[rvol_key]
                if is_sec_stock and focus_bias == 'SELL': score *= 1.3
                candidates.append({'sym': sym, 'side': 'SELL', 'score': score, 'd': d, 'sl_raw': sf[high_key]})
                
        if not candidates: continue
        candidates.sort(key=lambda x: x['score'], reverse=True)
        
        for pick in candidates[:max_daily]:
            sym = pick['sym']
            side = pick['side']
            d = pick['d']
            sl_raw = pick['sl_raw']
            
            opens = d['opens']
            highs = d['highs']
            lows = d['lows']
            closes = d['closes']
            times = d['times']
            n = min(len(opens), 70)
            
            entry_p = opens[entry_idx]
            
            # 1.0% Risk Calculation
            if mode == 'STATIC':
                current_risk = 1000.0 # Exactly Rs 1,000 (1% of Rs 1L)
                max_pos = 500000.0    # 5x MIS margin on Rs 1L
            else: # DYNAMIC
                current_risk = equity * 0.010 # Exactly 1.0% of current equity
                max_pos = equity * 5.0        # SEBI 5x MIS margin
                
            if side == 'BUY':
                sl_dist = entry_p - (sl_raw * 0.9995)
                if sl_dist <= 0 or (sl_dist / entry_p) < 0.003: sl_dist = entry_p * 0.005
                elif (sl_dist / entry_p) > 0.015: sl_dist = entry_p * 0.015
                sl_p = entry_p - sl_dist
                
                if exit_mode in ('2.0R', '2.5R', '3.0R', '3.5R', '4.0R'):
                    r_mult = float(exit_mode.replace('R', ''))
                    target_p = entry_p + (sl_dist * r_mult)
                elif exit_mode == 'PARTIAL_TRAIL':
                    target_p = entry_p + (sl_dist * 2.0)
                else:
                    target_p = 1e9
                    
                qty = max(1, min(int(current_risk / sl_dist), int(max_pos / entry_p)))
                curr_sl = sl_p
                exit_p = None
                
                for m in range(entry_idx, n):
                    if exit_mode == 'TRAILING':
                        if highs[m] >= entry_p + (sl_dist * 1.5): curr_sl = max(curr_sl, entry_p + (sl_dist * 0.5))
                        if highs[m] >= entry_p + (sl_dist * 3.0): curr_sl = max(curr_sl, entry_p + (sl_dist * 2.0))
                    elif exit_mode == 'PARTIAL_TRAIL':
                        if highs[m] >= target_p: curr_sl = max(curr_sl, entry_p + (sl_dist * 1.0))
                        
                    if exit_mode in ('2.0R', '2.5R', '3.0R', '3.5R', '4.0R') and highs[m] >= target_p:
                        exit_p = target_p; break
                    if lows[m] <= curr_sl:
                        exit_p = curr_sl; break
                    if m == 69 or times[m] >= time(15, 0):
                        exit_p = closes[m]; break
                if exit_p is None: exit_p = closes[n-1]
                costs = compute_trade_costs('BUY', entry_p, qty, 0.0, 0, exit_p, qty, 0.0003)
                
            else: # SELL
                sl_dist = (sl_raw * 1.0005) - entry_p
                if sl_dist <= 0 or (sl_dist / entry_p) < 0.003: sl_dist = entry_p * 0.005
                elif (sl_dist / entry_p) > 0.015: sl_dist = entry_p * 0.015
                sl_p = entry_p + sl_dist
                
                if exit_mode in ('2.0R', '2.5R', '3.0R', '3.5R', '4.0R'):
                    r_mult = float(exit_mode.replace('R', ''))
                    target_p = entry_p - (sl_dist * r_mult)
                elif exit_mode == 'PARTIAL_TRAIL':
                    target_p = entry_p - (sl_dist * 2.0)
                else:
                    target_p = -1e9
                    
                qty = max(1, min(int(current_risk / sl_dist), int(max_pos / entry_p)))
                curr_sl = sl_p
                exit_p = None
                
                for m in range(entry_idx, n):
                    if exit_mode == 'TRAILING':
                        if lows[m] <= entry_p - (sl_dist * 1.5): curr_sl = min(curr_sl, entry_p - (sl_dist * 0.5))
                        if lows[m] <= entry_p - (sl_dist * 3.0): curr_sl = min(curr_sl, entry_p - (sl_dist * 2.0))
                    elif exit_mode == 'PARTIAL_TRAIL':
                        if lows[m] <= target_p: curr_sl = min(curr_sl, entry_p - (sl_dist * 1.0))
                        
                    if exit_mode in ('2.0R', '2.5R', '3.0R', '3.5R', '4.0R') and lows[m] <= target_p:
                        exit_p = target_p; break
                    if highs[m] >= curr_sl:
                        exit_p = curr_sl; break
                    if m == 69 or times[m] >= time(15, 0):
                        exit_p = closes[m]; break
                if exit_p is None: exit_p = closes[n-1]
                costs = compute_trade_costs('SELL', entry_p, qty, 0.0, 0, exit_p, qty, 0.0003)
                
            net_pnl = costs['net_pnl']
            equity += net_pnl
            if equity > peak: peak = equity
            dd_rs = peak - equity
            dd_pct = dd_rs / peak if peak > 0 else 0
            if dd_rs > max_dd_rs: max_dd_rs = dd_rs
            if dd_pct > max_dd_pct: max_dd_pct = dd_pct
            
            trades.append({
                'Date': dt, 'Symbol': sym, 'Side': side,
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
    gross_win = wins['GrossPnL'].sum()
    gross_loss = abs(df_t[df_t['GrossPnL'] < 0]['GrossPnL'].sum())
    pf = gross_win / gross_loss if gross_loss > 0 else 99.0
    
    net_pnl = df_t['NetPnL'].sum()
    gross_pnl = df_t['GrossPnL'].sum()
    total_costs = df_t['Costs'].sum()
    total_r = df_t['R'].sum()
    
    df_t['Year'] = pd.to_datetime(df_t['Date']).dt.year
    yearly = df_t.groupby('Year')['NetPnL'].sum().to_dict()
    
    if mode == 'STATIC':
        avg_monthly_pct = (net_pnl / 58.0 / start_cap) * 100.0
        cagr = None
    else:
        avg_monthly_pct = (((equity / start_cap) ** (1 / 58.0)) - 1) * 100.0
        cagr = ((equity / start_cap) ** (1 / 4.83) - 1) * 100.0
        
    return {
        'Timing': entry_timing,
        'Catalyst': catalyst_type,
        'MinGap': min_gap,
        'MinRVOL': min_rvol,
        'ExitMode': exit_mode,
        'MaxDaily': max_daily,
        'Mode': mode,
        'Trades': n_trades,
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
        'Y2022': yearly.get(2022, 0),
        'Y2023': yearly.get(2023, 0),
        'Y2024': yearly.get(2024, 0),
        'Y2025': yearly.get(2025, 0),
        'Y2026': yearly.get(2026, 0)
    }

def run_1pct_optimization():
    universe = load_universe()
    daily_cache = precalculate_daily_features(universe)
    
    print("\n--- Running Dedicated 1.0% Risk Optimization Sweep ---", flush=True)
    
    timings = ['15M', '30M', '45M']
    catalysts = ['EARNINGS_ONLY', 'SECTOR_ONLY', 'COMBINED']
    gaps = [0.008, 0.012]
    rvols = [1.8, 2.5]
    exits = ['2.5R', '3.5R', 'TRAILING', 'PARTIAL_TRAIL']
    max_dailies = [1, 2, 3]
    modes = ['STATIC', 'DYNAMIC']
    
    results = []
    t_start = pytime.time()
    count = 0
    
    for t in timings:
        for cat in catalysts:
            for g in gaps:
                for rv in rvols:
                    for ex in exits:
                        for md in max_dailies:
                            for m in modes:
                                count += 1
                                res = simulate_1pct_strategy(
                                    daily_cache,
                                    entry_timing=t,
                                    catalyst_type=cat,
                                    min_gap=g,
                                    min_rvol=rv,
                                    exit_mode=ex,
                                    max_daily=md,
                                    mode=m
                                )
                                if res:
                                    results.append(res)
                                    
    df_res = pd.DataFrame(results)
    out_path = "research/phase4_2/results_1pct_risk_dedicated_sweep.csv"
    df_res.to_csv(out_path, index=False)
    print(f"\nDone! Tested {count} combinations at strictly 1.0% risk. Saved to {out_path}.", flush=True)
    
    print("\n=== TOP 10 STATIC 1.0% RISK CONFIGURATIONS (Rs 1,000 Flat) ===")
    static_df = df_res[df_res['Mode'] == 'STATIC'].sort_values('NetPnL', ascending=False).head(10)
    cols = ['Timing', 'Catalyst', 'ExitMode', 'MaxDaily', 'Trades', 'WinRate', 'PF', 'NetPnL', 'TotalR', 'MaxDD_Pct', 'AvgMonthlyPct']
    print(static_df[cols].to_string())
    
    print("\n=== TOP 10 DYNAMIC 1.0% RISK COMPOUNDING CONFIGURATIONS ===")
    dynamic_df = df_res[df_res['Mode'] == 'DYNAMIC'].sort_values('FinalEquity', ascending=False).head(10)
    dcols = ['Timing', 'Catalyst', 'ExitMode', 'MaxDaily', 'Trades', 'WinRate', 'PF', 'FinalEquity', 'NetPnL', 'CAGR', 'MaxDD_Pct', 'AvgMonthlyPct']
    print(dynamic_df[dcols].to_string())

if __name__ == '__main__':
    run_1pct_optimization()
