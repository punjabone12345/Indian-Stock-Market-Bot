"""
SHALLOW FIBONACCI (23.6% - 38.2%) + SMC FVG/OB + VWAP CONFLUENCE SUITE
Testing Precision Institutional Execution Upgrades to Cut Drawdowns and Maximize Compounded Returns
Dataset: 4.8 Years (1,186 Sessions), 29 Liquid NSE Mega-Caps (2022-2026).
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
from test_smc_ict_fib_catalyst_upgrades import load_data, precalculate_features

CACHE_DIR = "data/master_cache_2022_2026"

def run_confluence_simulation(daily_cache,
                              entry_mode='SHALLOW_FIB', # 'SHALLOW_FIB', 'VWAP_FVG_CONFLUENCE', 'HYBRID_CROWN'
                              fib_level=0.382,          # 0.236, 0.382, 0.500
                              target_rr=3.5,            # 2.5, 3.0, 3.5, 4.0
                              be_lock_r=1.5,            # 1.5R to move SL to BE
                              trail_after_r=2.5,        # start trailing 5m swing lows after 2.5R
                              daily_loss_circuit=True,  # halt trade 2 if trade 1 loses
                              max_daily_trades=1,
                              risk_mode='STATIC_1PCT',  # 'STATIC_1PCT', 'DYNAMIC_2PCT', 'DYNAMIC_3PCT'
                              base_capital=100000.0):
    
    trades = []
    current_equity = base_capital
    
    for dt, day_data in daily_cache.items():
        stock_feats = day_data['stocks']
        if not stock_feats: continue
        
        candidates = []
        for sym, sf in stock_feats.items():
            # Institutional Catalyst Filter
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
            
            if c_conf > v_conf and c_conf > sf['m45_low']:
                ret = (c_conf - o_0) / o_0
                score = (ret * 100.0) * sf['rvol_45']
                candidates.append({'sym': sym, 'side': 'BUY', 'score': score, 'sf': sf})
            elif c_conf < v_conf and c_conf < sf['m45_high']:
                ret = (o_0 - c_conf) / o_0
                score = (ret * 100.0) * sf['rvol_45']
                candidates.append({'sym': sym, 'side': 'SELL', 'score': score, 'sf': sf})
                
        if not candidates: continue
        candidates.sort(key=lambda x: x['score'], reverse=True)
        
        day_loss_count = 0
        picks_executed = 0
        
        for cand in candidates:
            if picks_executed >= max_daily_trades: break
            if daily_loss_circuit and day_loss_count >= 1: break
            
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
            
            # Risk allocation
            if risk_mode == 'STATIC_1PCT':
                risk_amount = base_capital * 0.01 # Rs 1,000
            elif risk_mode == 'DYNAMIC_2PCT':
                risk_amount = current_equity * 0.02
            else: # DYNAMIC_3PCT
                risk_amount = current_equity * 0.03
                
            if entry_mode == 'SHALLOW_FIB':
                # Morning impulse from 09:15 to 10:00 (bars 0..8)
                h_m = np.max(highs[:9])
                l_m = np.min(lows[:9])
                impulse = h_m - l_m
                if impulse / l_m < 0.008: continue
                
                if side == 'BUY':
                    fib_target_p = h_m - (impulse * fib_level)
                    # Look for pullback into fib_level between 10:00 and 11:30 AM (bars 9..26)
                    for k in range(9, min(27, n-10)):
                        # Low dips into or below fib level, but candle holds above VWAP
                        if lows[k] <= fib_target_p and closes[k] >= vwap[k] and lows[k] > l_m:
                            entry_idx = k
                            entry_p = closes[k]
                            sl_p = l_m * 0.9995
                            sl_dist = entry_p - sl_p
                            sl_dist = max(entry_p * 0.005, min(sl_dist, entry_p * 0.015))
                            sl_p = entry_p - sl_dist
                            break
                        elif lows[k] <= l_m:
                            break
                else: # SELL
                    fib_target_p = l_m + (impulse * fib_level)
                    for k in range(9, min(27, n-10)):
                        if highs[k] >= fib_target_p and closes[k] <= vwap[k] and highs[k] < h_m:
                            entry_idx = k
                            entry_p = closes[k]
                            sl_p = h_m * 1.0005
                            sl_dist = sl_p - entry_p
                            sl_dist = max(entry_p * 0.005, min(sl_dist, entry_p * 0.015))
                            sl_p = entry_p + sl_dist
                            break
                        elif highs[k] >= h_m:
                            break
                            
            elif entry_mode == 'VWAP_FVG_CONFLUENCE':
                # Look for FVG formed in bars 0..8 that sits right at or above VWAP
                if side == 'BUY':
                    for b in range(2, 9):
                        if lows[b] > highs[b-2] and closes[b-1] > opens[b-1]:
                            fvg_mid = (lows[b] + highs[b-2]) / 2.0
                            for k in range(9, min(28, n-10)):
                                # Retest FVG + VWAP bounce + rejection wick
                                if lows[k] <= fvg_mid and closes[k] >= vwap[k] and lows[k] > sf['m45_low']:
                                    bar_range = highs[k] - lows[k]
                                    lower_wick = min(opens[k], closes[k]) - lows[k]
                                    if bar_range > 0 and (lower_wick / bar_range) >= 0.20:
                                        entry_idx = k
                                        entry_p = closes[k]
                                        sl_p = sf['m45_low'] * 0.9995
                                        sl_dist = entry_p - sl_p
                                        sl_dist = max(entry_p * 0.005, min(sl_dist, entry_p * 0.015))
                                        sl_p = entry_p - sl_dist
                                        break
                            if entry_idx: break
                else: # SELL
                    for b in range(2, 9):
                        if highs[b] < lows[b-2] and closes[b-1] < opens[b-1]:
                            fvg_mid = (highs[b] + lows[b-2]) / 2.0
                            for k in range(9, min(28, n-10)):
                                if highs[k] >= fvg_mid and closes[k] <= vwap[k] and highs[k] < sf['m45_high']:
                                    bar_range = highs[k] - lows[k]
                                    upper_wick = highs[k] - max(opens[k], closes[k])
                                    if bar_range > 0 and (upper_wick / bar_range) >= 0.20:
                                        entry_idx = k
                                        entry_p = closes[k]
                                        sl_p = sf['m45_high'] * 1.0005
                                        sl_dist = sl_p - entry_p
                                        sl_dist = max(entry_p * 0.005, min(sl_dist, entry_p * 0.015))
                                        sl_p = entry_p + sl_dist
                                        break
                            if entry_idx: break
                            
            elif entry_mode == 'HYBRID_CROWN':
                # Enters at 10:00 AM (bar 9 open) if 10:00 AM bar has confirmed above VWAP + morning range
                # but adds tight trailing and breakeven lock
                entry_idx = 9
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
                    
            if entry_idx is None or entry_p is None:
                continue
                
            qty = max(1, min(int(risk_amount / sl_dist), int(5.0 * current_equity / entry_p)))
            curr_sl = sl_p
            target_p = (entry_p + (sl_dist * target_rr)) if side == 'BUY' else (entry_p - (sl_dist * target_rr))
            
            exit_p = None
            exit_reason = None
            
            for m in range(entry_idx, n):
                # 1. Breakeven Lock (+1.5R)
                if be_lock_r:
                    be_threshold = (entry_p + (sl_dist * be_lock_r)) if side == 'BUY' else (entry_p - (sl_dist * be_lock_r))
                    if (side == 'BUY' and highs[m] >= be_threshold) or (side == 'SELL' and lows[m] <= be_threshold):
                        new_sl = (entry_p + (sl_dist * 0.10)) if side == 'BUY' else (entry_p - (sl_dist * 0.10))
                        curr_sl = max(curr_sl, new_sl) if side == 'BUY' else min(curr_sl, new_sl)
                        
                # 2. Dynamic Trailing after 2.5R
                if trail_after_r:
                    trail_threshold = (entry_p + (sl_dist * trail_after_r)) if side == 'BUY' else (entry_p - (sl_dist * trail_after_r))
                    if (side == 'BUY' and highs[m] >= trail_threshold):
                        # trail to lowest low of last 3 bars
                        trail_sl = np.min(lows[max(0, m-2):m+1])
                        curr_sl = max(curr_sl, trail_sl)
                    elif (side == 'SELL' and lows[m] <= trail_threshold):
                        trail_sl = np.max(highs[max(0, m-2):m+1])
                        curr_sl = min(curr_sl, trail_sl)
                        
                # 3. Target Hit
                if (side == 'BUY' and highs[m] >= target_p) or (side == 'SELL' and lows[m] <= target_p):
                    exit_p = target_p
                    exit_reason = 'TARGET'
                    break
                    
                # 4. Stop Loss Hit
                if (side == 'BUY' and lows[m] <= curr_sl) or (side == 'SELL' and highs[m] >= curr_sl):
                    exit_p = curr_sl
                    exit_reason = 'STOP_LOSS'
                    break
                    
                # 5. 3:00 PM Square-off
                if m == 69 or times[m] >= time(15, 0):
                    exit_p = closes[m]
                    exit_reason = 'TIME_3PM'
                    break
                    
            if exit_p is None:
                exit_p = closes[n-1]
                exit_reason = 'EOD'
                
            c = compute_trade_costs(side, entry_p, qty, 0.0, 0, exit_p, qty, 0.0003)
            net_pnl = c['net_pnl']
            gross_pnl = c['gross_pnl']
            costs = c['statutory_charges'] + c['slippage_cost']
            
            # Update equity if dynamic
            current_equity += net_pnl
            
            trades.append({
                'Date': dt, 'Symbol': sym, 'Side': side,
                'GrossPnL': gross_pnl, 'Costs': costs, 'NetPnL': net_pnl,
                'EquityAfter': current_equity,
                'R': net_pnl / risk_amount, 'ExitReason': exit_reason
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
    
    # Drawdown calculations
    if risk_mode == 'STATIC_1PCT':
        df['CumNet'] = df['NetPnL'].cumsum()
        df['Peak'] = df['CumNet'].cummax()
        df['Drawdown_Rs'] = df['Peak'] - df['CumNet']
        max_dd_rs = df['Drawdown_Rs'].max()
        max_dd_pct = (max_dd_rs / (100000.0 + df['Peak'].max())) * 100.0
    else:
        df['PeakEquity'] = df['EquityAfter'].cummax()
        df['DDPct'] = (df['PeakEquity'] - df['EquityAfter']) / df['PeakEquity'] * 100.0
        max_dd_pct = df['DDPct'].max()
        max_dd_rs = (df['PeakEquity'] - df['EquityAfter']).max()
        
    df['YearMonth'] = df['Date'].astype(str).str[:7]
    monthly_pnl = df.groupby('YearMonth')['NetPnL'].sum()
    avg_monthly_rs = monthly_pnl.mean()
    avg_monthly_pct = (avg_monthly_rs / base_capital) * 100.0
    
    df['Year'] = df['Date'].astype(str).str[:4]
    yearly = df.groupby('Year')['NetPnL'].sum().to_dict()
    
    cagr = None
    if risk_mode != 'STATIC_1PCT' and current_equity > 0:
        cagr = ((current_equity / base_capital) ** (1.0 / 4.8) - 1.0) * 100.0
        
    return {
        'EntryMode': entry_mode,
        'FibLevel': fib_level if entry_mode == 'SHALLOW_FIB' else 'N/A',
        'TargetRR': f"1:{target_rr}",
        'BELock': f"{be_lock_r}R" if be_lock_r else 'None',
        'TrailAfter': f"{trail_after_r}R" if trail_after_r else 'None',
        'DailyCircuit': daily_loss_circuit,
        'RiskMode': risk_mode,
        'Trades': n_trades,
        'WinRate': round(win_rate, 2),
        'PF': round(pf, 2),
        'GrossPnL': round(gross_pnl, 2),
        'Costs': round(total_costs, 2),
        'NetPnL': round(net_pnl, 2),
        'EndingEquity': round(current_equity, 2),
        'MaxDD_Rs': round(max_dd_rs, 2),
        'MaxDD_Pct': round(max_dd_pct, 2),
        'AvgMonthlyPct': round(avg_monthly_pct, 2),
        'CAGR': round(cagr, 2) if cagr else 'N/A',
        'YearlyPnL': yearly
    }

if __name__ == '__main__':
    print("Loading universe...")
    universe = load_data()
    daily_cache = precalculate_features(universe)
    
    confluence_tests = [
        # --- SHALLOW FIBONACCI (23.6%, 38.2%) ---
        {'entry_mode': 'SHALLOW_FIB', 'fib_level': 0.236, 'target_rr': 3.5, 'be_lock_r': 1.5, 'trail_after_r': 2.5, 'daily_loss_circuit': True, 'risk_mode': 'STATIC_1PCT'},
        {'entry_mode': 'SHALLOW_FIB', 'fib_level': 0.382, 'target_rr': 3.5, 'be_lock_r': 1.5, 'trail_after_r': 2.5, 'daily_loss_circuit': True, 'risk_mode': 'STATIC_1PCT'},
        
        # --- VWAP + FVG CONFLUENCE ---
        {'entry_mode': 'VWAP_FVG_CONFLUENCE', 'fib_level': 0.382, 'target_rr': 3.5, 'be_lock_r': 1.5, 'trail_after_r': 2.5, 'daily_loss_circuit': True, 'risk_mode': 'STATIC_1PCT'},
        {'entry_mode': 'VWAP_FVG_CONFLUENCE', 'fib_level': 0.382, 'target_rr': 3.5, 'be_lock_r': 1.5, 'trail_after_r': 2.5, 'daily_loss_circuit': True, 'risk_mode': 'DYNAMIC_2PCT'},
        
        # --- HYBRID CROWN (10:00 AM CONFIRMATION + CIRCUIT + BE LOCK + TRAILING) ---
        {'entry_mode': 'HYBRID_CROWN', 'fib_level': 0.382, 'target_rr': 3.5, 'be_lock_r': 1.5, 'trail_after_r': 2.5, 'daily_loss_circuit': True, 'risk_mode': 'STATIC_1PCT'},
        {'entry_mode': 'HYBRID_CROWN', 'fib_level': 0.382, 'target_rr': 3.5, 'be_lock_r': 1.5, 'trail_after_r': 2.5, 'daily_loss_circuit': True, 'risk_mode': 'DYNAMIC_2PCT'},
        {'entry_mode': 'HYBRID_CROWN', 'fib_level': 0.382, 'target_rr': 4.0, 'be_lock_r': 1.5, 'trail_after_r': 2.5, 'daily_loss_circuit': True, 'risk_mode': 'DYNAMIC_2PCT'},
        {'entry_mode': 'HYBRID_CROWN', 'fib_level': 0.382, 'target_rr': 3.5, 'be_lock_r': 1.5, 'trail_after_r': 2.5, 'daily_loss_circuit': True, 'risk_mode': 'DYNAMIC_3PCT'}
    ]
    
    results = []
    for test in confluence_tests:
        em = test['entry_mode']
        fl = test['fib_level']
        tr = test['target_rr']
        be = test['be_lock_r']
        ta = test['trail_after_r']
        dlc = test['daily_loss_circuit']
        rm = test['risk_mode']
        
        print(f"Running {em} | Fib={fl} | Target={tr}R | BE={be}R | Trail={ta}R | Risk={rm}...", flush=True)
        res = run_confluence_simulation(
            daily_cache, entry_mode=em, fib_level=fl, target_rr=tr,
            be_lock_r=be, trail_after_r=ta, daily_loss_circuit=dlc,
            max_daily_trades=1, risk_mode=rm
        )
        if res:
            results.append(res)
            print(f" -> Trades: {res['Trades']}, WR: {res['WinRate']}%, PF: {res['PF']}, NetPnL: Rs {res['NetPnL']}, Equity: Rs {res['EndingEquity']}, MaxDD: {res['MaxDD_Pct']}%, AvgMo: {res['AvgMonthlyPct']}%", flush=True)
            
    df_out = pd.DataFrame(results)
    df_out.to_csv("research/phase4_2/results_confluence_upgrades.csv", index=False)
    print("\nSaved results to research/phase4_2/results_confluence_upgrades.csv")
    print(df_out[['EntryMode', 'FibLevel', 'TargetRR', 'RiskMode', 'Trades', 'WinRate', 'PF', 'NetPnL', 'EndingEquity', 'MaxDD_Pct', 'AvgMonthlyPct', 'CAGR']])
