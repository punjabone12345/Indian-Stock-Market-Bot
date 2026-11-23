"""
EXHAUSTIVE ITERATIVE SEARCH LOOP FOR >10% MONTHLY RETURN
ON NEWS & SECTOR CATALYST ARCHITECTURE (2022-2026)
Dataset: 4.8 Years (1,186 trading sessions), 29 Liquid Mega-Caps, 5-minute bars.
Cost Model: Full Statutory Zerodha Deductions (Brokerage, STT, Exchange, SEBI, Stamp, GST, 0.03% Slippage).
"""

import os
import sys
import glob
import time as pytime
from datetime import time
import pandas as pd
import numpy as np

# Ensure research/phase4_2 is in path for costs import
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
    """
    Precomputes per-day metrics for all stocks and sectors across all 1,186 trading sessions.
    """
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
            if d['n'] < 70: continue # need full day through 3:00 PM
            
            opens = d['opens']
            highs = d['highs']
            lows = d['lows']
            closes = d['closes']
            volumes = d['volumes']
            vwap = d['vwap']
            
            gap_pct = (opens[0] - pdc) / pdc
            
            # Opening metrics
            # 15m (bars 0..2)
            m15_high = np.max(highs[:3])
            m15_low = np.min(lows[:3])
            m15_vol = np.sum(volumes[:3])
            rvol_15 = m15_vol / (vol_ma / 25.0) if vol_ma > 0 else 1.0
            
            # 30m (bars 0..5)
            m30_high = np.max(highs[:6])
            m30_low = np.min(lows[:6])
            m30_vol = np.sum(volumes[:6])
            rvol_30 = m30_vol / (vol_ma / 12.5) if vol_ma > 0 else 1.0
            
            # 45m (bars 0..8)
            m45_high = np.max(highs[:9])
            m45_low = np.min(lows[:9])
            m45_vol = np.sum(volumes[:9])
            rvol_45 = m45_vol / (vol_ma / 8.33) if vol_ma > 0 else 1.0
            
            stock_feats[sym] = {
                'pdc': pdc,
                'vol_ma': vol_ma,
                'gap_pct': gap_pct,
                'abs_gap': abs(gap_pct),
                'm15_high': m15_high, 'm15_low': m15_low, 'rvol_15': rvol_15,
                'm30_high': m30_high, 'm30_low': m30_low, 'rvol_30': rvol_30,
                'm45_high': m45_high, 'm45_low': m45_low, 'rvol_45': rvol_45,
                'd': d
            }
            
        # Compute Sector Gaps & Breadths
        sector_stats = {}
        for sec_name, syms in SECTOR_MAP.items():
            gaps = [stock_feats[s]['gap_pct'] for s in syms if s in stock_feats]
            if len(gaps) >= 2:
                med_gap = float(np.median(gaps))
                pos_breadth = sum(1 for g in gaps if g > 0.001) / len(gaps)
                neg_breadth = sum(1 for g in gaps if g < -0.001) / len(gaps)
                sector_stats[sec_name] = {
                    'med_gap': med_gap,
                    'abs_gap': abs(med_gap),
                    'pos_breadth': pos_breadth,
                    'neg_breadth': neg_breadth
                }
                
        daily_cache[dt] = {
            'stocks': stock_feats,
            'sectors': sector_stats
        }
        
    print(f"Precalculated daily features for {len(daily_cache)} sessions in {pytime.time() - t0:.2f}s", flush=True)
    return daily_cache

def simulate_engine(daily_cache, 
                     entry_timing='30M',       # '15M', '30M', '45M'
                     catalyst_type='COMBINED', # 'SECTOR_ONLY', 'EARNINGS_ONLY', 'COMBINED'
                     min_gap=0.008,            # 0.8%, 1.0%, 1.2%
                     min_rvol=1.8,             # 1.8x, 2.2x, 2.8x
                     direction_mode='BOTH',    # 'LONG_ONLY', 'BOTH'
                     exit_mode='TRAILING',     # '2.0R', '2.5R', '3.0R', '3.5R', 'TRAILING', 'PARTIAL_TRAIL', 'TIME_3PM'
                     max_daily_trades=2,       # 1, 2, 3, 4
                     risk_per_trade=2000.0):   # 1000, 1500, 2000, 2500, 3000, 4000
    
    trades = []
    
    # Timing mappings:
    # 15M: entry at candle 3 (09:30), confirmation bar 2
    # 30M: entry at candle 6 (09:45), confirmation bar 5
    # 45M: entry at candle 9 (10:00), confirmation bar 8
    if entry_timing == '15M':
        entry_idx = 3
        conf_bar = 2
        high_key = 'm15_high'
        low_key = 'm15_low'
        rvol_key = 'rvol_15'
    elif entry_timing == '30M':
        entry_idx = 6
        conf_bar = 5
        high_key = 'm30_high'
        low_key = 'm30_low'
        rvol_key = 'rvol_30'
    else: # 45M
        entry_idx = 9
        conf_bar = 8
        high_key = 'm45_high'
        low_key = 'm45_low'
        rvol_key = 'rvol_45'
        
    for dt, day_data in daily_cache.items():
        stock_feats = day_data['stocks']
        sector_stats = day_data['sectors']
        if not stock_feats: continue
        
        candidates = []
        
        # 1. Sector Catalyst Identification
        focus_sector = None
        focus_bias = None
        if catalyst_type in ('SECTOR_ONLY', 'COMBINED') and sector_stats:
            sec_sorted = sorted(sector_stats.items(), key=lambda x: x[1]['abs_gap'], reverse=True)
            for sname, sdata in sec_sorted:
                if sdata['abs_gap'] >= 0.005:
                    if sdata['med_gap'] > 0 and sdata['pos_breadth'] >= 0.60:
                        focus_sector = sname
                        focus_bias = 'BUY'
                        break
                    elif sdata['med_gap'] < 0 and sdata['neg_breadth'] >= 0.60:
                        focus_sector = sname
                        focus_bias = 'SELL'
                        break
                        
        # 2. Constituent Evaluation
        for sym, sf in stock_feats.items():
            d = sf['d']
            opens = d['opens']
            highs = d['highs']
            lows = d['lows']
            closes = d['closes']
            vwap = d['vwap']
            
            # Check catalyst qualification
            is_sector_stock = False
            if focus_sector and sym in SECTOR_MAP.get(focus_sector, []):
                is_sector_stock = True
                
            is_company_catalyst = (sf['abs_gap'] >= min_gap and sf[rvol_key] >= min_rvol)
            
            qualifies = False
            if catalyst_type == 'SECTOR_ONLY' and is_sector_stock:
                qualifies = True
            elif catalyst_type == 'EARNINGS_ONLY' and is_company_catalyst:
                qualifies = True
            elif catalyst_type == 'COMBINED' and (is_sector_stock or is_company_catalyst):
                qualifies = True
                
            if not qualifies: continue
            
            # Microstructure confirmation at entry time
            c_conf = closes[conf_bar]
            v_conf = vwap[conf_bar]
            o_0 = opens[0]
            
            # Long candidate
            if c_conf > v_conf and c_conf > sf[low_key]:
                if direction_mode in ('LONG_ONLY', 'BOTH'):
                    # Relative strength & volume expansion score
                    ret = (c_conf - o_0) / o_0
                    score = (ret * 100.0) * sf[rvol_key]
                    if is_sector_stock and focus_bias == 'BUY': score *= 1.3
                    candidates.append({
                        'sym': sym, 'side': 'BUY', 'score': score,
                        'd': d, 'sl_raw': sf[low_key]
                    })
                    
            # Short candidate
            elif c_conf < v_conf and c_conf < sf[high_key]:
                if direction_mode == 'BOTH':
                    ret = (o_0 - c_conf) / o_0
                    score = (ret * 100.0) * sf[rvol_key]
                    if is_sector_stock and focus_bias == 'SELL': score *= 1.3
                    candidates.append({
                        'sym': sym, 'side': 'SELL', 'score': score,
                        'd': d, 'sl_raw': sf[high_key]
                    })
                    
        if not candidates: continue
        
        candidates.sort(key=lambda x: x['score'], reverse=True)
        
        # Execute up to max_daily_trades
        for pick in candidates[:max_daily_trades]:
            sym = pick['sym']
            side = pick['side']
            d = pick['d']
            sl_raw = pick['sl_raw']
            
            opens = d['opens']
            highs = d['highs']
            lows = d['lows']
            closes = d['closes']
            times = d['times']
            n = min(len(opens), 70) # strictly evaluate up to 3:00 PM (candle 69)
            
            entry_p = opens[entry_idx]
            
            if side == 'BUY':
                sl_dist = entry_p - (sl_raw * 0.9995)
                # Risk bounds
                if sl_dist <= 0 or (sl_dist / entry_p) < 0.003:
                    sl_dist = entry_p * 0.005
                elif (sl_dist / entry_p) > 0.015:
                    sl_dist = entry_p * 0.015
                sl_p = entry_p - sl_dist
                
                qty = max(1, min(int(risk_per_trade / sl_dist), int(500000 / entry_p)))
                
                curr_sl = sl_p
                exit_p = None
                
                # Setup target R if fixed
                target_r = None
                if exit_mode in ('2.0R', '2.5R', '3.0R', '3.5R'):
                    r_mult = float(exit_mode.replace('R', ''))
                    target_p = entry_p + (sl_dist * r_mult)
                elif exit_mode == 'PARTIAL_TRAIL':
                    target_p = entry_p + (sl_dist * 2.0)
                else:
                    target_p = 1e9
                    
                for m in range(entry_idx, n):
                    # Trailing management
                    if exit_mode == 'TRAILING':
                        if highs[m] >= entry_p + (sl_dist * 1.5):
                            curr_sl = max(curr_sl, entry_p + (sl_dist * 0.5))
                        if highs[m] >= entry_p + (sl_dist * 3.0):
                            curr_sl = max(curr_sl, entry_p + (sl_dist * 2.0))
                    elif exit_mode == 'PARTIAL_TRAIL':
                        if highs[m] >= target_p:
                            curr_sl = max(curr_sl, entry_p + (sl_dist * 1.0))
                            
                    # Target check (for fixed target modes)
                    if exit_mode in ('2.0R', '2.5R', '3.0R', '3.5R') and highs[m] >= target_p:
                        exit_p = target_p
                        break
                    # Stop loss check
                    if lows[m] <= curr_sl:
                        exit_p = curr_sl
                        break
                    # 3:00 PM Square-off
                    if m == 69 or times[m] >= time(15, 0):
                        exit_p = closes[m]
                        break
                        
                if exit_p is None:
                    exit_p = closes[n-1]
                    
                costs = compute_trade_costs('BUY', entry_p, qty, 0.0, 0, exit_p, qty, 0.0003)
                trades.append({
                    'Date': dt, 'Symbol': sym, 'Side': 'BUY',
                    'GrossPnL': costs['gross_pnl'],
                    'Costs': costs['statutory_charges'] + costs['slippage_cost'],
                    'NetPnL': costs['net_pnl'],
                    'R': costs['net_pnl'] / risk_per_trade
                })
                
            else: # SELL
                sl_dist = (sl_raw * 1.0005) - entry_p
                if sl_dist <= 0 or (sl_dist / entry_p) < 0.003:
                    sl_dist = entry_p * 0.005
                elif (sl_dist / entry_p) > 0.015:
                    sl_dist = entry_p * 0.015
                sl_p = entry_p + sl_dist
                
                qty = max(1, min(int(risk_per_trade / sl_dist), int(500000 / entry_p)))
                
                curr_sl = sl_p
                exit_p = None
                
                if exit_mode in ('2.0R', '2.5R', '3.0R', '3.5R'):
                    r_mult = float(exit_mode.replace('R', ''))
                    target_p = entry_p - (sl_dist * r_mult)
                elif exit_mode == 'PARTIAL_TRAIL':
                    target_p = entry_p - (sl_dist * 2.0)
                else:
                    target_p = -1e9
                    
                for m in range(entry_idx, n):
                    if exit_mode == 'TRAILING':
                        if lows[m] <= entry_p - (sl_dist * 1.5):
                            curr_sl = min(curr_sl, entry_p - (sl_dist * 0.5))
                        if lows[m] <= entry_p - (sl_dist * 3.0):
                            curr_sl = min(curr_sl, entry_p - (sl_dist * 2.0))
                    elif exit_mode == 'PARTIAL_TRAIL':
                        if lows[m] <= target_p:
                            curr_sl = min(curr_sl, entry_p - (sl_dist * 1.0))
                            
                    if exit_mode in ('2.0R', '2.5R', '3.0R', '3.5R') and lows[m] <= target_p:
                        exit_p = target_p
                        break
                    if highs[m] >= curr_sl:
                        exit_p = curr_sl
                        break
                    if m == 69 or times[m] >= time(15, 0):
                        exit_p = closes[m]
                        break
                        
                if exit_p is None:
                    exit_p = closes[n-1]
                    
                costs = compute_trade_costs('SELL', entry_p, qty, 0.0, 0, exit_p, qty, 0.0003)
                trades.append({
                    'Date': dt, 'Symbol': sym, 'Side': 'SELL',
                    'GrossPnL': costs['gross_pnl'],
                    'Costs': costs['statutory_charges'] + costs['slippage_cost'],
                    'NetPnL': costs['net_pnl'],
                    'R': costs['net_pnl'] / risk_per_trade
                })
                
    if not trades:
        return None
        
    df = pd.DataFrame(trades)
    n_trades = len(df)
    wins = df[df['NetPnL'] > 0]
    win_rate = (len(wins) / n_trades) * 100.0
    gross_win = wins['GrossPnL'].sum()
    gross_loss = abs(df[df['GrossPnL'] < 0]['GrossPnL'].sum())
    pf = gross_win / gross_loss if gross_loss > 0 else 99.0
    
    net_pnl = df['NetPnL'].sum()
    gross_pnl = df['GrossPnL'].sum()
    total_costs = df['Costs'].sum()
    total_r = df['R'].sum()
    
    # Calculate Max Drawdown in Rupees and Pct
    df['CumNet'] = df['NetPnL'].cumsum()
    df['Peak'] = df['CumNet'].cummax()
    df['DD'] = df['Peak'] - df['CumNet']
    max_dd_rs = df['DD'].max()
    max_dd_pct = (max_dd_rs / 100000.0) * 100.0
    
    # 58 total calendar months (Jan 2022 to Oct 2026 = 4.83 years = 58 months)
    avg_monthly_pct = (net_pnl / 58.0 / 100000.0) * 100.0
    
    # Check yearly PnL
    df['Year'] = pd.to_datetime(df['Date']).dt.year
    yearly = df.groupby('Year')['NetPnL'].sum().to_dict()
    
    return {
        'Timing': entry_timing,
        'Catalyst': catalyst_type,
        'MinGap': min_gap,
        'MinRVOL': min_rvol,
        'Direction': direction_mode,
        'ExitMode': exit_mode,
        'MaxDaily': max_daily_trades,
        'Risk': risk_per_trade,
        'Trades': n_trades,
        'WinRate': win_rate,
        'PF': pf,
        'GrossPnL': gross_pnl,
        'Costs': total_costs,
        'NetPnL': net_pnl,
        'TotalR': total_r,
        'MaxDD_Rs': max_dd_rs,
        'MaxDD_Pct': max_dd_pct,
        'AvgMonthlyPct': avg_monthly_pct,
        'Y2022': yearly.get(2022, 0),
        'Y2023': yearly.get(2023, 0),
        'Y2024': yearly.get(2024, 0),
        'Y2025': yearly.get(2025, 0),
        'Y2026': yearly.get(2026, 0)
    }

def run_sweep():
    universe = load_universe()
    daily_cache = precalculate_daily_features(universe)
    
    print("\nStarting Exhaustive Parameter Sweep Across Degrees of Freedom...", flush=True)
    
    # Sweep grid
    timings = ['15M', '30M', '45M']
    catalysts = ['COMBINED', 'SECTOR_ONLY', 'EARNINGS_ONLY']
    gaps = [0.008, 0.012]
    rvols = [1.8, 2.5]
    directions = ['LONG_ONLY', 'BOTH']
    exits = ['2.5R', '3.5R', 'TRAILING', 'PARTIAL_TRAIL']
    max_dailies = [1, 2, 3, 4]
    risks = [1500.0, 2500.0, 3500.0, 5000.0]
    
    results = []
    t_start = pytime.time()
    count = 0
    
    # Iterative loop
    for t in timings:
        for cat in catalysts:
            for g in gaps:
                for rv in rvols:
                    for d in directions:
                        for ex in exits:
                            for md in max_dailies:
                                for rk in risks:
                                    count += 1
                                    res = simulate_engine(
                                        daily_cache,
                                        entry_timing=t,
                                        catalyst_type=cat,
                                        min_gap=g,
                                        min_rvol=rv,
                                        direction_mode=d,
                                        exit_mode=ex,
                                        max_daily_trades=md,
                                        risk_per_trade=rk
                                    )
                                    if res:
                                        results.append(res)
                                        if res['AvgMonthlyPct'] >= 10.0:
                                            print(f"--> FOUND >=10% MONTHLY: NetPnL=+Rs {res['NetPnL']:.0f}, Monthly={res['AvgMonthlyPct']:.2f}%, DD={res['MaxDD_Pct']:.1f}%, Timing={t}, Cat={cat}, Exit={ex}, Daily={md}, Risk={rk}", flush=True)
                                            
                                    if count % 200 == 0:
                                        print(f"Swept {count} parameter sets in {pytime.time() - t_start:.1f}s...", flush=True)
                                        
    df_res = pd.DataFrame(results)
    out_path = "research/phase4_2/exhaustive_loop_sweep_results.csv"
    df_res.to_csv(out_path, index=False)
    print(f"\nExhaustive sweep complete! Tested {count} combinations. Saved to {out_path}.", flush=True)
    
    # Top 15 by Avg Monthly Return
    print("\n=== TOP 15 CONFIGURATIONS BY AVERAGE MONTHLY RETURN ===")
    top15 = df_res.sort_values('AvgMonthlyPct', ascending=False).head(15)
    cols = ['Timing', 'Catalyst', 'ExitMode', 'MaxDaily', 'Risk', 'Trades', 'WinRate', 'PF', 'NetPnL', 'TotalR', 'MaxDD_Pct', 'AvgMonthlyPct']
    print(top15[cols].to_string())
    
    # Check configurations with > 10%
    ge_10 = df_res[df_res['AvgMonthlyPct'] >= 10.0]
    print(f"\nConfigurations achieving >= 10.0% average monthly return: {len(ge_10)}")
    if len(ge_10) > 0:
        print(ge_10.sort_values('AvgMonthlyPct', ascending=False).head(10)[cols].to_string())

if __name__ == '__main__':
    run_sweep()
