"""
UNIFIED SECTOR BASKET + CORPORATE CATALYST MASTER ENGINE (2022-2026)
Combines:
1. Sector Macro Catalysts: When an entire sector gaps with high breadth, trades confirming sector constituents.
2. Corporate Earnings / News Catalysts: When individual stocks have massive earnings/news volume expansion.
Sizing: Strictly 1.0% Risk per trade (Rs 1,000 flat on Rs 1L base capital).
Exit: 3.5R Asymmetric Target or strict 3:00 PM IST Square-off.
Costs: Full Zerodha Statutory Taxes + 0.03% Slippage.
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
    'FMCG': ['ITC', 'HINDUNILVR', 'TITAN'],
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
            
            m45_high = np.max(highs[:9])
            m45_low = np.min(lows[:9])
            m45_vol = np.sum(volumes[:9])
            rvol_45 = m45_vol / (vol_ma / 8.33) if vol_ma > 0 else 1.0
            
            stock_feats[sym] = {
                'pdc': pdc, 'vol_ma': vol_ma, 'gap_pct': gap_pct, 'abs_gap': abs(gap_pct),
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
                    'pos_breadth': pos_breadth, 'neg_breadth': neg_breadth,
                    'syms': [s for s in syms if s in stock_feats]
                }
                
        daily_cache[dt] = {'stocks': stock_feats, 'sectors': sector_stats}
        
    print(f"Precalculated daily features for {len(daily_cache)} sessions in {pytime.time() - t0:.2f}s", flush=True)
    return daily_cache

def simulate_unified_system(daily_cache,
                            max_daily_trades=2,   # 1, 2, 3
                            target_rr=3.5,
                            trail_mode=False,
                            mode='STATIC',        # 'STATIC' (Rs 1,000) or 'DYNAMIC' (1.0% equity)
                            start_cap=100000.0):
    
    equity = start_cap
    peak = start_cap
    max_dd_rs = 0.0
    max_dd_pct = 0.0
    trades = []
    
    entry_idx = 9 # 10:00 AM bar open
    conf_bar = 8  # 09:55-10:00 bar close
    
    for dt, day_data in daily_cache.items():
        stock_feats = day_data['stocks']
        sector_stats = day_data['sectors']
        if not stock_feats: continue
        
        candidates = []
        
        # 1. Check Sector Basket Catalyst (Breadth >= 60%, Sector Gap >= 0.8%)
        focus_sector, focus_bias, focus_syms = None, None, []
        if sector_stats:
            sec_sorted = sorted(sector_stats.items(), key=lambda x: x[1]['abs_gap'], reverse=True)
            for sname, sdata in sec_sorted:
                if sdata['abs_gap'] >= 0.008:
                    if sdata['med_gap'] > 0 and sdata['pos_breadth'] >= 0.60:
                        focus_sector, focus_bias, focus_syms = sname, 'BUY', sdata['syms']
                        break
                    elif sdata['med_gap'] < 0 and sdata['neg_breadth'] >= 0.60:
                        focus_sector, focus_bias, focus_syms = sname, 'SELL', sdata['syms']
                        break
                        
        # 2. Check all stocks for either:
        # A) Sector basket constituent following the sector news
        # B) Corporate earnings / individual catalyst (Gap >= 1.2%, RVOL >= 2.5x)
        for sym, sf in stock_feats.items():
            d = sf['d']
            opens = d['opens']
            highs = d['highs']
            lows = d['lows']
            closes = d['closes']
            vwap = d['vwap']
            
            c_conf = closes[conf_bar]
            v_conf = vwap[conf_bar]
            o_0 = opens[0]
            rvol = sf['rvol_45']
            
            is_sector_stock = (focus_sector and sym in focus_syms)
            is_company_catalyst = (sf['abs_gap'] >= 0.012 and rvol >= 2.5)
            
            if not is_sector_stock and not is_company_catalyst:
                continue
                
            # Long confirmation
            if c_conf > v_conf and c_conf > sf['m45_low']:
                ret = (c_conf - o_0) / o_0
                score = (ret * 100.0) * rvol
                if is_sector_stock and focus_bias == 'BUY': score *= 1.4 # Sector alignment boost
                candidates.append({
                    'sym': sym, 'side': 'BUY', 'score': score,
                    'd': d, 'sl_raw': sf['m45_low'], 'rvol': rvol,
                    'type': 'SECTOR_BASKET' if is_sector_stock else 'COMPANY_CATALYST'
                })
            # Short confirmation
            elif c_conf < v_conf and c_conf < sf['m45_high']:
                ret = (o_0 - c_conf) / o_0
                score = (ret * 100.0) * rvol
                if is_sector_stock and focus_bias == 'SELL': score *= 1.4
                candidates.append({
                    'sym': sym, 'side': 'SELL', 'score': score,
                    'd': d, 'sl_raw': sf['m45_high'], 'rvol': rvol,
                    'type': 'SECTOR_BASKET' if is_sector_stock else 'COMPANY_CATALYST'
                })
                
        if not candidates: continue
        candidates.sort(key=lambda x: x['score'], reverse=True)
        
        # Take up to max_daily_trades
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
            n = min(len(opens), 70)
            
            entry_p = opens[entry_idx]
            
            if mode == 'STATIC':
                current_risk = 1000.0 # Exactly Rs 1,000 per trade
                max_pos = 500000.0
            else:
                current_risk = equity * 0.010
                max_pos = equity * 5.0
                
            if side == 'BUY':
                sl_dist = entry_p - (sl_raw * 0.9995)
                if sl_dist <= 0 or (sl_dist / entry_p) < 0.003: sl_dist = entry_p * 0.005
                elif (sl_dist / entry_p) > 0.015: sl_dist = entry_p * 0.015
                sl_p = entry_p - sl_dist
                target_p = entry_p + (sl_dist * target_rr) if not trail_mode else 1e9
                
                qty = max(1, min(int(current_risk / sl_dist), int(max_pos / entry_p)))
                curr_sl = sl_p
                exit_p = None
                
                for m in range(entry_idx, n):
                    if trail_mode:
                        if highs[m] >= entry_p + (sl_dist * 1.5): curr_sl = max(curr_sl, entry_p + (sl_dist * 0.5))
                        if highs[m] >= entry_p + (sl_dist * 3.0): curr_sl = max(curr_sl, entry_p + (sl_dist * 2.0))
                    if not trail_mode and highs[m] >= target_p:
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
                target_p = entry_p - (sl_dist * target_rr) if not trail_mode else -1e9
                
                qty = max(1, min(int(current_risk / sl_dist), int(max_pos / entry_p)))
                curr_sl = sl_p
                exit_p = None
                
                for m in range(entry_idx, n):
                    if trail_mode:
                        if lows[m] <= entry_p - (sl_dist * 1.5): curr_sl = min(curr_sl, entry_p - (sl_dist * 0.5))
                        if lows[m] <= entry_p - (sl_dist * 3.0): curr_sl = min(curr_sl, entry_p - (sl_dist * 2.0))
                    if not trail_mode and lows[m] <= target_p:
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
                'Date': dt, 'Symbol': sym, 'Side': side, 'Type': pick['type'],
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
    
    if mode == 'STATIC':
        avg_monthly_pct = (net_pnl / 58.0 / start_cap) * 100.0
        cagr = None
    else:
        avg_monthly_pct = (((equity / start_cap) ** (1.0 / 58.0)) - 1.0) * 100.0
        cagr = ((equity / start_cap) ** (1.0 / 4.83) - 1.0) * 100.0
        
    df_t['Year'] = pd.to_datetime(df_t['Date']).dt.year
    yearly = df_t.groupby('Year')['NetPnL'].sum().to_dict()
    
    return {
        'MaxDaily': max_daily_trades,
        'TargetRR': target_rr,
        'TrailMode': trail_mode,
        'Mode': mode,
        'Trades': n_trades,
        'MonthlyTrades': n_trades / 58.0,
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

def run_tests():
    universe = load_universe()
    daily_cache = precalculate_daily_features(universe)
    
    print("\n--- Evaluating Unified Sector Basket + Corporate Catalyst Engine ---", flush=True)
    results = []
    
    for md in [1, 2, 3]:
        for tgt in [2.5, 3.5]:
            for tr in [False, True]:
                for m in ['STATIC', 'DYNAMIC']:
                    res = simulate_unified_system(
                        daily_cache, max_daily_trades=md, target_rr=tgt, trail_mode=tr, mode=m
                    )
                    if res: results.append(res)
                    
    df_res = pd.DataFrame(results)
    out_path = "research/phase4_2/results_unified_catalyst_master.csv"
    df_res.to_csv(out_path, index=False)
    print(f"Tested {len(df_res)} configurations. Saved to {out_path}.", flush=True)
    
    print("\n=== TOP 5 STATIC 1.0% RISK UNIFIED SYSTEMS ===")
    s_top = df_res[df_res['Mode'] == 'STATIC'].sort_values('NetPnL', ascending=False).head(5)
    cols = ['MaxDaily', 'TargetRR', 'TrailMode', 'Trades', 'MonthlyTrades', 'WinRate', 'PF', 'NetPnL', 'TotalR', 'MaxDD_Pct', 'AvgMonthlyPct']
    print(s_top[cols].to_string())
    
    print("\n=== TOP 5 DYNAMIC 1.0% RISK UNIFIED SYSTEMS ===")
    d_top = df_res[df_res['Mode'] == 'DYNAMIC'].sort_values('FinalEquity', ascending=False).head(5)
    dcols = ['MaxDaily', 'TargetRR', 'TrailMode', 'Trades', 'MonthlyTrades', 'WinRate', 'PF', 'FinalEquity', 'NetPnL', 'CAGR', 'MaxDD_Pct', 'AvgMonthlyPct']
    print(d_top[dcols].to_string())

if __name__ == '__main__':
    run_tests()
