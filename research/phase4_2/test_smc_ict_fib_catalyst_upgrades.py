"""
ADVANCED SMC, ICT, FIBONACCI & PRICE ACTION UPGRADE SUITE
Backtesting Confluence Models on Top of the Proven News Catalyst Architecture (2022-2026)
Dataset: 4.8 Years (1,186 Sessions), 29 Liquid NSE Mega-Caps, 5-minute Intraday Bars.
Cost Model: Exact Zerodha Statutory Deductions + 0.03% Slippage per order.
Risk Model: Strictly 1.0% Risk Per Trade (Rs 1,000 per trade on Rs 1,00,000 base).
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

def load_data():
    t0 = pytime.time()
    files_5m = sorted(glob.glob(os.path.join(CACHE_DIR, "*_5m.parquet")))
    symbols = [os.path.basename(f).replace("_5m.parquet", "") for f in files_5m]
    
    universe = {}
    for sym in symbols:
        df_5m = pd.read_parquet(os.path.join(CACHE_DIR, f"{sym}_5m.parquet"))
        df_daily = pd.read_parquet(os.path.join(CACHE_DIR, f"{sym}_daily.parquet"))
        
        df_daily['PDC'] = df_daily['Close'].shift(1)
        df_daily['PDH'] = df_daily['High'].shift(1)
        df_daily['PDL'] = df_daily['Low'].shift(1)
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

def precalculate_features(universe):
    t0 = pytime.time()
    all_dates = sorted(list(next(iter(universe.values()))['days'].keys()))
    
    daily_cache = {}
    for dt in all_dates:
        stock_feats = {}
        for sym, data in universe.items():
            daily = data['daily']
            days = data['days']
            if dt not in daily or dt not in days: continue
            pd_info = daily[dt]
            pdc = pd_info.get('PDC', np.nan)
            pdh = pd_info.get('PDH', np.nan)
            pdl = pd_info.get('PDL', np.nan)
            vol_ma = pd_info.get('Daily_VolMA20', 0)
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
            
            # 45m volume & range (bars 0..8)
            m45_high = np.max(highs[:9])
            m45_low = np.min(lows[:9])
            m45_vol = np.sum(volumes[:9])
            rvol_45 = m45_vol / (vol_ma / 8.33) if vol_ma > 0 else 1.0
            
            # 15m volume & range (bars 0..2)
            m15_high = np.max(highs[:3])
            m15_low = np.min(lows[:3])
            m15_vol = np.sum(volumes[:3])
            rvol_15 = m15_vol / (vol_ma / 25.0) if vol_ma > 0 else 1.0
            
            stock_feats[sym] = {
                'pdc': pdc, 'pdh': pdh, 'pdl': pdl,
                'vol_ma': vol_ma, 'gap_pct': gap_pct,
                'abs_gap': abs(gap_pct),
                'm45_high': m45_high, 'm45_low': m45_low, 'rvol_45': rvol_45,
                'm15_high': m15_high, 'm15_low': m15_low, 'rvol_15': rvol_15,
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
        
    print(f"Precalculated features for {len(daily_cache)} sessions in {pytime.time() - t0:.2f}s", flush=True)
    return daily_cache

def run_simulation(daily_cache,
                   model_type='BASELINE',      # 'BASELINE', 'FIB_OTE', 'SMC_FVG_OB', 'ICT_SWEEP_MSS'
                   fib_level=0.618,            # 0.50, 0.618, 0.705
                   target_rr=3.5,              # 2.5, 3.0, 3.5, 4.0
                   be_lock_r=None,             # e.g. 1.5R (move SL to BE once reached)
                   partial_target_r=None,      # e.g. 2.0R (take 50% profit at 2R)
                   daily_loss_circuit=False,   # halt/reduce if trade 1 loses
                   risk_per_trade=1000.0,
                   max_daily_trades=2):
    
    trades = []
    
    for dt, day_data in daily_cache.items():
        stock_feats = day_data['stocks']
        sector_stats = day_data['sectors']
        if not stock_feats: continue
        
        # 1. Sector Catalyst Focus
        focus_sector = None
        focus_bias = None
        if sector_stats:
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
                        
        candidates = []
        for sym, sf in stock_feats.items():
            # Strict High-Conviction Institutional Catalyst Filter (Row 654 baseline)
            is_catalyst = (sf['abs_gap'] >= 0.012 and sf['rvol_45'] >= 2.5)
            if not is_catalyst: continue
            
            d = sf['d']
            opens = d['opens']
            highs = d['highs']
            lows = d['lows']
            closes = d['closes']
            vwap = d['vwap']
            volumes = d['volumes']
            times = d['times']
            n = min(len(opens), 70)
            
            c_conf = closes[8]  # 10:00 AM bar close
            v_conf = vwap[8]
            o_0 = opens[0]
            
            # LONG CANDIDATE
            if c_conf > v_conf and c_conf > sf['m45_low']:
                ret = (c_conf - o_0) / o_0
                score = (ret * 100.0) * sf['rvol_45']
                candidates.append({
                    'sym': sym, 'side': 'BUY', 'score': score, 'sf': sf
                })
            # SHORT CANDIDATE
            elif c_conf < v_conf and c_conf < sf['m45_high']:
                ret = (o_0 - c_conf) / o_0
                score = (ret * 100.0) * sf['rvol_45']
                candidates.append({
                    'sym': sym, 'side': 'SELL', 'score': score, 'sf': sf
                })
                
        if not candidates: continue
        candidates.sort(key=lambda x: x['score'], reverse=True)
        
        # Day execution
        day_loss_count = 0
        picks_executed = 0
        
        for cand in candidates:
            if picks_executed >= max_daily_trades: break
            if daily_loss_circuit and day_loss_count >= 1:
                break # circuit breaker tripped for the day
                
            sym = cand['sym']
            side = cand['side']
            sf = cand['sf']
            d = sf['d']
            opens = d['opens']
            highs = d['highs']
            lows = d['lows']
            closes = d['closes']
            volumes = d['volumes']
            vwap = d['vwap']
            times = d['times']
            n = min(len(opens), 70)
            
            entry_idx = None
            entry_p = None
            sl_p = None
            sl_dist = None
            
            if model_type == 'BASELINE':
                entry_idx = 9 # 10:00 AM open
                entry_p = opens[entry_idx]
                if side == 'BUY':
                    sl_raw = sf['m45_low']
                    sl_dist = entry_p - (sl_raw * 0.9995)
                    sl_dist = max(entry_p * 0.005, min(sl_dist, entry_p * 0.015))
                    sl_p = entry_p - sl_dist
                else:
                    sl_raw = sf['m45_high']
                    sl_dist = (sl_raw * 1.0005) - entry_p
                    sl_dist = max(entry_p * 0.005, min(sl_dist, entry_p * 0.015))
                    sl_p = entry_p + sl_dist
                    
            elif model_type == 'FIB_OTE':
                # Morning impulse from 09:15 to 10:00 (bars 0..8)
                h_m = np.max(highs[:9])
                l_m = np.min(lows[:9])
                impulse = h_m - l_m
                
                if impulse / l_m < 0.008: continue # insufficient range for clean fib
                
                if side == 'BUY':
                    ote_level = h_m - (impulse * fib_level)
                    sl_level = l_m * 0.9995
                    raw_sl = ote_level - sl_level
                    if raw_sl / ote_level < 0.003 or raw_sl / ote_level > 0.015:
                        raw_sl = max(ote_level * 0.005, min(raw_sl, ote_level * 0.015))
                        sl_level = ote_level - raw_sl
                    
                    # Look for limit entry fill in bars 9 to 24 (10:00 to 11:15 AM)
                    for k in range(9, min(25, n-10)):
                        if lows[k] <= ote_level and lows[k] > sl_level:
                            entry_idx = k
                            entry_p = ote_level
                            sl_p = sl_level
                            sl_dist = entry_p - sl_p
                            break
                        elif lows[k] <= sl_level: # invalidated
                            break
                else: # SELL
                    ote_level = l_m + (impulse * fib_level)
                    sl_level = h_m * 1.0005
                    raw_sl = sl_level - ote_level
                    if raw_sl / ote_level < 0.003 or raw_sl / ote_level > 0.015:
                        raw_sl = max(ote_level * 0.005, min(raw_sl, ote_level * 0.015))
                        sl_level = ote_level + raw_sl
                        
                    for k in range(9, min(25, n-10)):
                        if highs[k] >= ote_level and highs[k] < sl_level:
                            entry_idx = k
                            entry_p = ote_level
                            sl_p = sl_level
                            sl_dist = sl_p - entry_p
                            break
                        elif highs[k] >= sl_level:
                            break
                            
            elif model_type == 'SMC_FVG_OB':
                # Search for 3-candle FVG in morning 09:15-10:00 (bars 0..8)
                fvg_found = False
                fvg_entry = None
                fvg_sl = None
                
                if side == 'BUY':
                    for b in range(2, 9):
                        # Bullish FVG: Bar b-2 High < Bar b Low
                        if lows[b] > highs[b-2] and closes[b-1] > opens[b-1]:
                            # FVG zone between highs[b-2] and lows[b]
                            fvg_entry = (lows[b] + highs[b-2]) / 2.0
                            fvg_sl = opens[b-1] * 0.9990 # below order block open/low
                            fvg_found = True
                            break
                    if fvg_found:
                        raw_sl = fvg_entry - fvg_sl
                        if raw_sl / fvg_entry < 0.003 or raw_sl / fvg_entry > 0.015:
                            raw_sl = max(fvg_entry * 0.005, min(raw_sl, fvg_entry * 0.015))
                            fvg_sl = fvg_entry - raw_sl
                        for k in range(9, min(28, n-10)):
                            # Retest with price action rejection (lower wick)
                            bar_range = highs[k] - lows[k]
                            lower_wick = min(opens[k], closes[k]) - lows[k]
                            has_rejection = (bar_range > 0 and (lower_wick / bar_range) >= 0.25)
                            if lows[k] <= fvg_entry and lows[k] > fvg_sl and has_rejection:
                                entry_idx = k
                                entry_p = fvg_entry
                                sl_p = fvg_sl
                                sl_dist = entry_p - sl_p
                                break
                            elif lows[k] <= fvg_sl:
                                break
                else: # SELL
                    for b in range(2, 9):
                        # Bearish FVG: Bar b-2 Low > Bar b High
                        if highs[b] < lows[b-2] and closes[b-1] < opens[b-1]:
                            fvg_entry = (highs[b] + lows[b-2]) / 2.0
                            fvg_sl = opens[b-1] * 1.0010
                            fvg_found = True
                            break
                    if fvg_found:
                        raw_sl = fvg_sl - fvg_entry
                        if raw_sl / fvg_entry < 0.003 or raw_sl / fvg_entry > 0.015:
                            raw_sl = max(fvg_entry * 0.005, min(raw_sl, fvg_entry * 0.015))
                            fvg_sl = fvg_entry + raw_sl
                        for k in range(9, min(28, n-10)):
                            bar_range = highs[k] - lows[k]
                            upper_wick = highs[k] - max(opens[k], closes[k])
                            has_rejection = (bar_range > 0 and (upper_wick / bar_range) >= 0.25)
                            if highs[k] >= fvg_entry and highs[k] < fvg_sl and has_rejection:
                                entry_idx = k
                                entry_p = fvg_entry
                                sl_p = fvg_sl
                                sl_dist = sl_p - entry_p
                                break
                            elif highs[k] >= fvg_sl:
                                break
                                
            elif model_type == 'ICT_SWEEP_MSS':
                # Sweep of PDH/PDL or IB (09:15-09:30) with rapid reversal (MSS)
                ib_high = np.max(highs[:3])
                ib_low = np.min(lows[:3])
                
                if side == 'BUY':
                    # Swept lower then reclaimed with volume
                    for k in range(3, min(18, n-10)):
                        if lows[k] < min(ib_low, sf['pdl']) and closes[k] > vwap[k]:
                            entry_idx = k + 1
                            entry_p = opens[entry_idx]
                            sl_p = lows[k] * 0.9995
                            sl_dist = entry_p - sl_p
                            sl_dist = max(entry_p * 0.005, min(sl_dist, entry_p * 0.015))
                            sl_p = entry_p - sl_dist
                            break
                else: # SELL
                    for k in range(3, min(18, n-10)):
                        if highs[k] > max(ib_high, sf['pdh']) and closes[k] < vwap[k]:
                            entry_idx = k + 1
                            entry_p = opens[entry_idx]
                            sl_p = highs[k] * 1.0005
                            sl_dist = sl_p - entry_p
                            sl_dist = max(entry_p * 0.005, min(sl_dist, entry_p * 0.015))
                            sl_p = entry_p + sl_dist
                            break
                            
            if entry_idx is None or entry_p is None:
                continue
                
            # Quantity sizing: strictly 1.0% risk (Rs 1,000)
            qty = max(1, min(int(risk_per_trade / sl_dist), int(500000 / entry_p)))
            
            # TRADE SIMULATION
            curr_sl = sl_p
            target_p = (entry_p + (sl_dist * target_rr)) if side == 'BUY' else (entry_p - (sl_dist * target_rr))
            partial_p = None
            if partial_target_r:
                partial_p = (entry_p + (sl_dist * partial_target_r)) if side == 'BUY' else (entry_p - (sl_dist * partial_target_r))
                
            partial_taken = False
            exit_p = None
            exit_reason = None
            exit_time_idx = None
            
            for m in range(entry_idx, n):
                # 1. Check Breakeven Locking Circuit
                if be_lock_r and not partial_taken:
                    be_threshold = (entry_p + (sl_dist * be_lock_r)) if side == 'BUY' else (entry_p - (sl_dist * be_lock_r))
                    if (side == 'BUY' and highs[m] >= be_threshold) or (side == 'SELL' and lows[m] <= be_threshold):
                        # Move stop to Entry + 0.1R to cover fees
                        new_sl = (entry_p + (sl_dist * 0.10)) if side == 'BUY' else (entry_p - (sl_dist * 0.10))
                        curr_sl = max(curr_sl, new_sl) if side == 'BUY' else min(curr_sl, new_sl)
                        
                # 2. Check Partial Take Profit
                if partial_p and not partial_taken:
                    if (side == 'BUY' and highs[m] >= partial_p) or (side == 'SELL' and lows[m] <= partial_p):
                        partial_taken = True
                        # Move SL to entry
                        curr_sl = entry_p
                        
                # 3. Target Hit
                if (side == 'BUY' and highs[m] >= target_p) or (side == 'SELL' and lows[m] <= target_p):
                    exit_p = target_p
                    exit_reason = 'TARGET'
                    exit_time_idx = m
                    break
                    
                # 4. Stop Loss Hit
                if (side == 'BUY' and lows[m] <= curr_sl) or (side == 'SELL' and highs[m] >= curr_sl):
                    exit_p = curr_sl
                    exit_reason = 'STOP_LOSS'
                    exit_time_idx = m
                    break
                    
                # 5. 3:00 PM Square-off (candle 69 or >= 15:00)
                if m == 69 or times[m] >= time(15, 0):
                    exit_p = closes[m]
                    exit_reason = 'TIME_3PM'
                    exit_time_idx = m
                    break
                    
            if exit_p is None:
                exit_p = closes[n-1]
                exit_reason = 'EOD'
                
            # Compute exact statutory costs & net PnL
            if partial_taken:
                # 50% closed at partial_p, 50% closed at exit_p
                q1 = qty // 2
                q2 = qty - q1
                c1 = compute_trade_costs(side, entry_p, q1, 0.0, 0, partial_p, q1, 0.0003)
                c2 = compute_trade_costs(side, entry_p, q2, 0.0, 0, exit_p, q2, 0.0003)
                net_pnl = c1['net_pnl'] + c2['net_pnl']
                gross_pnl = c1['gross_pnl'] + c2['gross_pnl']
                costs = (c1['statutory_charges'] + c1['slippage_cost']) + (c2['statutory_charges'] + c2['slippage_cost'])
            else:
                c = compute_trade_costs(side, entry_p, qty, 0.0, 0, exit_p, qty, 0.0003)
                net_pnl = c['net_pnl']
                gross_pnl = c['gross_pnl']
                costs = c['statutory_charges'] + c['slippage_cost']
                
            r_multiple = net_pnl / risk_per_trade
            trades.append({
                'Date': dt, 'Symbol': sym, 'Side': side,
                'GrossPnL': gross_pnl, 'Costs': costs, 'NetPnL': net_pnl,
                'R': r_multiple, 'ExitReason': exit_reason
            })
            
            picks_executed += 1
            if net_pnl < 0:
                day_loss_count += 1
                
    if not trades:
        return None
        
    df = pd.DataFrame(trades)
    n_trades = len(df)
    wins = df[df['NetPnL'] > 0]
    win_rate = (len(wins) / n_trades) * 100.0
    gross_win = wins['GrossPnL'].sum()
    gross_loss = abs(df[df['GrossPnL'] < 0]['GrossPnL'].sum())
    pf = gross_win / gross_loss if gross_loss > 0 else 999.0
    
    gross_pnl = df['GrossPnL'].sum()
    total_costs = df['Costs'].sum()
    net_pnl = df['NetPnL'].sum()
    total_r = df['R'].sum()
    
    # Drawdown metrics
    df['CumNet'] = df['NetPnL'].cumsum()
    df['Peak'] = df['CumNet'].cummax()
    df['Drawdown_Rs'] = df['Peak'] - df['CumNet']
    max_dd_rs = df['Drawdown_Rs'].max()
    max_dd_pct = (max_dd_rs / (100000.0 + df['Peak'].max())) * 100.0 if (100000.0 + df['Peak'].max()) > 0 else 0.0
    
    # Monthly metrics
    df['YearMonth'] = df['Date'].astype(str).str[:7]
    monthly_pnl = df.groupby('YearMonth')['NetPnL'].sum()
    avg_monthly_rs = monthly_pnl.mean()
    avg_monthly_pct = (avg_monthly_rs / 100000.0) * 100.0
    
    # Year by year breakdown
    df['Year'] = df['Date'].astype(str).str[:4]
    yearly = df.groupby('Year')['NetPnL'].sum().to_dict()
    
    return {
        'Model': model_type,
        'FibLevel': fib_level if model_type == 'FIB_OTE' else 'N/A',
        'TargetRR': f"1:{target_rr}",
        'BELock': f"{be_lock_r}R" if be_lock_r else 'None',
        'PartialTarget': f"{partial_target_r}R" if partial_target_r else 'None',
        'DailyLossCircuit': daily_loss_circuit,
        'Trades': n_trades,
        'WinRate': round(win_rate, 2),
        'PF': round(pf, 2),
        'GrossPnL': round(gross_pnl, 2),
        'Costs': round(total_costs, 2),
        'NetPnL': round(net_pnl, 2),
        'TotalR': round(total_r, 2),
        'MaxDD_Rs': round(max_dd_rs, 2),
        'MaxDD_Pct': round(max_dd_pct, 2),
        'AvgMonthlyPct': round(avg_monthly_pct, 2),
        'YearlyPnL': yearly
    }

if __name__ == '__main__':
    print("Loading universe and precalculating features...")
    universe = load_data()
    daily_cache = precalculate_features(universe)
    
    print("\nRunning Backtest Suite on SMC, ICT, Fibonacci & Drawdown Circuits...")
    
    experiments = [
        # 1. Baseline Benchmark (Matches Row 654)
        {'model_type': 'BASELINE', 'max_daily_trades': 1, 'target_rr': 3.5, 'be_lock_r': None, 'partial_target_r': None, 'daily_loss_circuit': False},
        {'model_type': 'BASELINE', 'max_daily_trades': 2, 'target_rr': 3.5, 'be_lock_r': None, 'partial_target_r': None, 'daily_loss_circuit': False},
        
        # 2. Baseline + Drawdown Circuits (BE Lock, Circuit Breaker)
        {'model_type': 'BASELINE', 'max_daily_trades': 1, 'target_rr': 3.5, 'be_lock_r': 1.5, 'partial_target_r': None, 'daily_loss_circuit': False},
        {'model_type': 'BASELINE', 'max_daily_trades': 1, 'target_rr': 3.5, 'be_lock_r': 1.5, 'partial_target_r': 2.0, 'daily_loss_circuit': False},
        {'model_type': 'BASELINE', 'max_daily_trades': 2, 'target_rr': 3.5, 'be_lock_r': 1.5, 'partial_target_r': None, 'daily_loss_circuit': True},
        {'model_type': 'BASELINE', 'max_daily_trades': 2, 'target_rr': 3.5, 'be_lock_r': 1.5, 'partial_target_r': 2.0, 'daily_loss_circuit': True},
        
        # 3. Fibonacci OTE (Optimal Trade Entry 50%, 61.8%, 70.5%)
        {'model_type': 'FIB_OTE', 'max_daily_trades': 1, 'fib_level': 0.50, 'target_rr': 3.5, 'be_lock_r': None, 'partial_target_r': None, 'daily_loss_circuit': False},
        {'model_type': 'FIB_OTE', 'max_daily_trades': 1, 'fib_level': 0.618, 'target_rr': 3.5, 'be_lock_r': None, 'partial_target_r': None, 'daily_loss_circuit': False},
        {'model_type': 'FIB_OTE', 'max_daily_trades': 1, 'fib_level': 0.705, 'target_rr': 3.5, 'be_lock_r': None, 'partial_target_r': None, 'daily_loss_circuit': False},
        
        # 4. Fibonacci OTE + Drawdown Mitigation Circuits
        {'model_type': 'FIB_OTE', 'max_daily_trades': 1, 'fib_level': 0.618, 'target_rr': 3.5, 'be_lock_r': 1.5, 'partial_target_r': None, 'daily_loss_circuit': False},
        {'model_type': 'FIB_OTE', 'max_daily_trades': 1, 'fib_level': 0.618, 'target_rr': 3.5, 'be_lock_r': 1.5, 'partial_target_r': 2.0, 'daily_loss_circuit': False},
        {'model_type': 'FIB_OTE', 'max_daily_trades': 2, 'fib_level': 0.618, 'target_rr': 3.5, 'be_lock_r': 1.5, 'partial_target_r': None, 'daily_loss_circuit': True},
        {'model_type': 'FIB_OTE', 'max_daily_trades': 2, 'fib_level': 0.705, 'target_rr': 3.5, 'be_lock_r': 1.5, 'partial_target_r': None, 'daily_loss_circuit': True},
        
        # 5. SMC FVG & Order Block Retest with Price Action Rejection
        {'model_type': 'SMC_FVG_OB', 'max_daily_trades': 1, 'target_rr': 3.0, 'be_lock_r': None, 'partial_target_r': None, 'daily_loss_circuit': False},
        {'model_type': 'SMC_FVG_OB', 'max_daily_trades': 1, 'target_rr': 3.5, 'be_lock_r': 1.5, 'partial_target_r': None, 'daily_loss_circuit': False},
        {'model_type': 'SMC_FVG_OB', 'max_daily_trades': 1, 'target_rr': 3.5, 'be_lock_r': 1.5, 'partial_target_r': 2.0, 'daily_loss_circuit': False},
        {'model_type': 'SMC_FVG_OB', 'max_daily_trades': 2, 'target_rr': 3.5, 'be_lock_r': 1.5, 'partial_target_r': None, 'daily_loss_circuit': True},
        
        # 6. ICT Liquidity Sweep (Turtle Soup) + MSS Reversal
        {'model_type': 'ICT_SWEEP_MSS', 'max_daily_trades': 1, 'target_rr': 3.0, 'be_lock_r': None, 'partial_target_r': None, 'daily_loss_circuit': False},
        {'model_type': 'ICT_SWEEP_MSS', 'max_daily_trades': 1, 'target_rr': 3.5, 'be_lock_r': 1.5, 'partial_target_r': None, 'daily_loss_circuit': False},
        {'model_type': 'ICT_SWEEP_MSS', 'max_daily_trades': 2, 'target_rr': 3.5, 'be_lock_r': 1.5, 'partial_target_r': None, 'daily_loss_circuit': True},
    ]
    
    results = []
    for exp in experiments:
        m = exp['model_type']
        f = exp.get('fib_level', 0.618)
        tr = exp['target_rr']
        be = exp['be_lock_r']
        pt = exp['partial_target_r']
        dlc = exp['daily_loss_circuit']
        mdt = exp.get('max_daily_trades', 1)
        
        print(f"Testing {m} (MaxDaily={mdt}, Fib={f}, Target={tr}R, BE={be}, Partial={pt}, Circuit={dlc})...", flush=True)
        res = run_simulation(daily_cache, model_type=m, fib_level=f, target_rr=tr,
                             be_lock_r=be, partial_target_r=pt, daily_loss_circuit=dlc,
                             max_daily_trades=mdt)
        if res:
            results.append(res)
            print(f" -> Trades: {res['Trades']}, WR: {res['WinRate']}%, PF: {res['PF']}, Net PnL: Rs {res['NetPnL']}, MaxDD: Rs {res['MaxDD_Rs']} ({res['MaxDD_Pct']}%)", flush=True)
            
    df_res = pd.DataFrame(results)
    df_res.to_csv("research/phase4_2/results_smc_ict_fib_upgrades.csv", index=False)
    print("\nSaved full results to research/phase4_2/results_smc_ict_fib_upgrades.csv")
    print(df_res[['Model', 'FibLevel', 'TargetRR', 'BELock', 'PartialTarget', 'Trades', 'WinRate', 'PF', 'NetPnL', 'MaxDD_Pct', 'AvgMonthlyPct']])
