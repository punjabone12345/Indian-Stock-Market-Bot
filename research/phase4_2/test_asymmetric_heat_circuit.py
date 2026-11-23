"""
ASYMMETRIC HEAT CIRCUIT & MULTI-TRADE COMPOUNDER
Rule: If Trade 1 WINS -> Take Trade 2 to compound daily gains.
      If Trade 1 LOSES -> Instantly HALT trading for the day (Zero -2R days!).
Test across:
1. HYBRID_CROWN (Catalyst + Morning Breakout + Breakeven Lock + Trailing)
2. VWAP_FVG_CONFLUENCE (Catalyst + FVG Retest + VWAP Defense)
3. SHALLOW_FIB_CONFLUENCE (Catalyst + 38.2% Retest)
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import time
sys.path.append(os.path.dirname(__file__))
from costs import compute_trade_costs
from test_smc_ict_fib_catalyst_upgrades import load_data, precalculate_features

def run_heat_simulation(daily_cache,
                        entry_mode='HYBRID_CROWN',
                        target_rr=3.5,
                        be_lock_r=1.5,
                        trail_after_r=2.5,
                        risk_mode='STATIC_1PCT',
                        base_capital=100000.0):
    
    trades = []
    current_equity = base_capital
    
    for dt, day_data in daily_cache.items():
        stock_feats = day_data['stocks']
        if not stock_feats: continue
        
        candidates = []
        for sym, sf in stock_feats.items():
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
        
        # Day execution with Asymmetric Heat Rule:
        # Trade 1 taken. If Trade 1 Net PnL > 0, Trade 2 allowed. If Trade 1 Net PnL <= 0, Halt.
        day_trades_count = 0
        trade_1_won = False
        
        for cand in candidates:
            if day_trades_count >= 2: break
            if day_trades_count == 1 and not trade_1_won:
                break # ASYMMETRIC HEAT BREAKER TRIPPED!
                
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
            
            if risk_mode == 'STATIC_1PCT':
                risk_amount = base_capital * 0.01
            elif risk_mode == 'DYNAMIC_2PCT':
                risk_amount = current_equity * 0.02
            else: # DYNAMIC_2.5PCT
                risk_amount = current_equity * 0.025
                
            if entry_mode == 'HYBRID_CROWN':
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
                    
            elif entry_mode == 'VWAP_FVG_CONFLUENCE':
                if side == 'BUY':
                    for b in range(2, 9):
                        if lows[b] > highs[b-2] and closes[b-1] > opens[b-1]:
                            fvg_mid = (lows[b] + highs[b-2]) / 2.0
                            for k in range(9, min(28, n-10)):
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
                else:
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
                            
            if entry_idx is None or entry_p is None:
                continue
                
            qty = max(1, min(int(risk_amount / sl_dist), int(5.0 * current_equity / entry_p)))
            curr_sl = sl_p
            target_p = (entry_p + (sl_dist * target_rr)) if side == 'BUY' else (entry_p - (sl_dist * target_rr))
            
            exit_p = None
            exit_reason = None
            
            for m in range(entry_idx, n):
                if be_lock_r:
                    be_threshold = (entry_p + (sl_dist * be_lock_r)) if side == 'BUY' else (entry_p - (sl_dist * be_lock_r))
                    if (side == 'BUY' and highs[m] >= be_threshold) or (side == 'SELL' and lows[m] <= be_threshold):
                        new_sl = (entry_p + (sl_dist * 0.10)) if side == 'BUY' else (entry_p - (sl_dist * 0.10))
                        curr_sl = max(curr_sl, new_sl) if side == 'BUY' else min(curr_sl, new_sl)
                        
                if trail_after_r:
                    trail_threshold = (entry_p + (sl_dist * trail_after_r)) if side == 'BUY' else (entry_p - (sl_dist * trail_after_r))
                    if (side == 'BUY' and highs[m] >= trail_threshold):
                        trail_sl = np.min(lows[max(0, m-2):m+1])
                        curr_sl = max(curr_sl, trail_sl)
                    elif (side == 'SELL' and lows[m] <= trail_threshold):
                        trail_sl = np.max(highs[max(0, m-2):m+1])
                        curr_sl = min(curr_sl, trail_sl)
                        
                if (side == 'BUY' and highs[m] >= target_p) or (side == 'SELL' and lows[m] <= target_p):
                    exit_p = target_p
                    exit_reason = 'TARGET'
                    break
                    
                if (side == 'BUY' and lows[m] <= curr_sl) or (side == 'SELL' and highs[m] >= curr_sl):
                    exit_p = curr_sl
                    exit_reason = 'STOP_LOSS'
                    break
                    
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
            
            current_equity += net_pnl
            trades.append({
                'Date': dt, 'Symbol': sym, 'Side': side,
                'GrossPnL': gross_pnl, 'Costs': costs, 'NetPnL': net_pnl,
                'EquityAfter': current_equity,
                'R': net_pnl / risk_amount, 'ExitReason': exit_reason
            })
            
            day_trades_count += 1
            if day_trades_count == 1:
                trade_1_won = (net_pnl > 0)
                
    if not trades: return None
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
        'TargetRR': f"1:{target_rr}",
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
    
    tests = [
        # Static 1.0% Risk
        {'entry_mode': 'HYBRID_CROWN', 'target_rr': 3.5, 'risk_mode': 'STATIC_1PCT'},
        {'entry_mode': 'HYBRID_CROWN', 'target_rr': 4.0, 'risk_mode': 'STATIC_1PCT'},
        {'entry_mode': 'VWAP_FVG_CONFLUENCE', 'target_rr': 3.5, 'risk_mode': 'STATIC_1PCT'},
        
        # Dynamic 2.0% Risk
        {'entry_mode': 'HYBRID_CROWN', 'target_rr': 3.5, 'risk_mode': 'DYNAMIC_2PCT'},
        {'entry_mode': 'HYBRID_CROWN', 'target_rr': 4.0, 'risk_mode': 'DYNAMIC_2PCT'},
        {'entry_mode': 'VWAP_FVG_CONFLUENCE', 'target_rr': 3.5, 'risk_mode': 'DYNAMIC_2PCT'},
        
        # Dynamic 2.5% Risk
        {'entry_mode': 'HYBRID_CROWN', 'target_rr': 3.5, 'risk_mode': 'DYNAMIC_2.5PCT'},
        {'entry_mode': 'HYBRID_CROWN', 'target_rr': 4.0, 'risk_mode': 'DYNAMIC_2.5PCT'},
    ]
    
    results = []
    for t in tests:
        em = t['entry_mode']
        tr = t['target_rr']
        rm = t['risk_mode']
        print(f"Testing Heat Circuit: {em} | Target={tr}R | Risk={rm}...", flush=True)
        res = run_heat_simulation(daily_cache, entry_mode=em, target_rr=tr, risk_mode=rm)
        if res:
            results.append(res)
            print(f" -> Trades: {res['Trades']}, WR: {res['WinRate']}%, PF: {res['PF']}, NetPnL: Rs {res['NetPnL']}, Equity: Rs {res['EndingEquity']}, MaxDD: {res['MaxDD_Pct']}%, AvgMo: {res['AvgMonthlyPct']}%, CAGR: {res['CAGR']}%", flush=True)
            
    df_res = pd.DataFrame(results)
    df_res.to_csv("research/phase4_2/results_asymmetric_heat_circuit.csv", index=False)
    print("\nSaved results to research/phase4_2/results_asymmetric_heat_circuit.csv")
    print(df_res[['EntryMode', 'TargetRR', 'RiskMode', 'Trades', 'WinRate', 'PF', 'NetPnL', 'EndingEquity', 'MaxDD_Pct', 'AvgMonthlyPct', 'CAGR']])
