"""
INDEPENDENT CLEAN-ROOM VERIFICATION SCRIPT FOR PROFILE 5
Strict Zero-Tolerance Verification:
1. ZERO Look-Ahead: Complete causal separation.
2. Pessimistic Intrabar Execution: If both target and stop are touched, stop hits FIRST.
3. Causal Breakeven & Trailing: Level updates only apply from candle m+1 onward.
4. Exact Zerodha Intraday Cost Model (Brokerage, STT, Exchange, SEBI, Stamp, GST) + 0.03% Slippage.
5. Strict 3:00 PM Square-off.
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import time

sys.path.append(os.path.dirname(__file__))
from costs import compute_trade_costs
from test_smc_ict_fib_catalyst_upgrades import load_data, precalculate_features

def run_clean_room_simulation(daily_cache,
                              max_daily_trades=1,      # 1 (Pure Leader) or 2 (Dual Concurrent)
                              target_rr=4.0,           # 4.0R target
                              be_lock_r=1.5,           # BE lock at 1.5R
                              trail_after_r=2.5,       # Trailing after 2.5R
                              dynamic_risk_pct=0.025,  # 2.5% dynamic equity risk
                              base_capital=100000.0):
    
    current_equity = base_capital
    trades = []
    
    for dt, day_data in daily_cache.items():
        stock_feats = day_data['stocks']
        if not stock_feats: continue
        
        candidates = []
        for sym, sf in stock_feats.items():
            # Strict Pre-Market & 45m Catalyst Filter
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
            
            c_conf = closes[8]  # 10:00 AM confirmation bar
            v_conf = vwap[8]
            o_0 = opens[0]
            
            # Microstructure directional confirmation
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
        
        # Take up to max_daily_trades CONCURRENTLY at 10:00 AM (Zero causality leak!)
        picks = candidates[:max_daily_trades]
        
        # Sizing per pick: if 2 picks, risk is split equally or applied per pick
        # Let's risk dynamic_risk_pct / max_daily_trades so total daily risk is strictly dynamic_risk_pct!
        per_trade_risk_pct = dynamic_risk_pct / len(picks) if max_daily_trades > 1 else dynamic_risk_pct
        risk_amount = current_equity * per_trade_risk_pct
        
        day_pnl = 0.0
        
        for cand in picks:
            sym = cand['sym']
            side = cand['side']
            sf = cand['sf']
            d = sf['d']
            opens = d['opens']
            highs = d['highs']
            lows = d['lows']
            closes = d['closes']
            times = d['times']
            n = min(len(opens), 70)
            
            # Entry at EXACT 10:00:00 AM open of bar 9
            entry_idx = 9
            entry_p = opens[entry_idx]
            
            if side == 'BUY':
                sl_raw = sf['m45_low']
                sl_dist = entry_p - (sl_raw * 0.9995)
                # Clamp SL between 0.5% and 1.5%
                sl_dist = max(entry_p * 0.005, min(sl_dist, entry_p * 0.015))
                sl_p = entry_p - sl_dist
                target_p = entry_p + (sl_dist * target_rr)
            else:
                sl_raw = sf['m45_high']
                sl_dist = (sl_raw * 1.0005) - entry_p
                sl_dist = max(entry_p * 0.005, min(sl_dist, entry_p * 0.015))
                sl_p = entry_p + sl_dist
                target_p = entry_p - (sl_dist * target_rr)
                
            qty = max(1, min(int(risk_amount / sl_dist), int(5.0 * current_equity / entry_p)))
            curr_sl = sl_p
            
            exit_p = None
            exit_reason = None
            be_locked = False
            pending_be_update = False
            pending_trail_sl = None
            
            for m in range(entry_idx, n):
                # 1. APPLY PENDING SL UPDATES FROM PREVIOUS CANDLE (Strict Causal Sequencing)
                if pending_be_update:
                    new_sl = (entry_p + (sl_dist * 0.10)) if side == 'BUY' else (entry_p - (sl_dist * 0.10))
                    curr_sl = max(curr_sl, new_sl) if side == 'BUY' else min(curr_sl, new_sl)
                    be_locked = True
                    pending_be_update = False
                    
                if pending_trail_sl is not None:
                    curr_sl = max(curr_sl, pending_trail_sl) if side == 'BUY' else min(curr_sl, pending_trail_sl)
                    pending_trail_sl = None
                    
                # 2. PESSIMISTIC INTRABAR RESOLUTION: STOP LOSS CHECK FIRST!
                # If low touches curr_sl, STOPPED OUT IMMEDIATELY
                if side == 'BUY' and lows[m] <= curr_sl:
                    exit_p = curr_sl
                    exit_reason = 'BREAKEVEN_STOP' if be_locked else 'STOP_LOSS'
                    break
                elif side == 'SELL' and highs[m] >= curr_sl:
                    exit_p = curr_sl
                    exit_reason = 'BREAKEVEN_STOP' if be_locked else 'STOP_LOSS'
                    break
                    
                # 3. TARGET CHECK
                if side == 'BUY' and highs[m] >= target_p:
                    exit_p = target_p
                    exit_reason = 'TARGET_4R'
                    break
                elif side == 'SELL' and lows[m] <= target_p:
                    exit_p = target_p
                    exit_reason = 'TARGET_4R'
                    break
                    
                # 4. 3:00 PM TIME EXIT
                if m == 69 or times[m] >= time(15, 0):
                    exit_p = closes[m]
                    exit_reason = 'TIME_3PM'
                    break
                    
                # 5. REGISTER SIGNALS FOR NEXT CANDLE (m+1)
                # Check BE threshold
                if be_lock_r and not be_locked:
                    be_threshold = (entry_p + (sl_dist * be_lock_r)) if side == 'BUY' else (entry_p - (sl_dist * be_lock_r))
                    if (side == 'BUY' and highs[m] >= be_threshold) or (side == 'SELL' and lows[m] <= be_threshold):
                        pending_be_update = True
                        
                # Check Trailing threshold
                if trail_after_r:
                    trail_threshold = (entry_p + (sl_dist * trail_after_r)) if side == 'BUY' else (entry_p - (sl_dist * trail_after_r))
                    if (side == 'BUY' and highs[m] >= trail_threshold):
                        pending_trail_sl = np.min(lows[max(0, m-2):m+1])
                    elif (side == 'SELL' and lows[m] <= trail_threshold):
                        pending_trail_sl = np.max(highs[max(0, m-2):m+1])
                        
            if exit_p is None:
                exit_p = closes[n-1]
                exit_reason = 'EOD'
                
            c = compute_trade_costs(side, entry_p, qty, 0.0, 0, exit_p, qty, 0.0003)
            net_pnl = c['net_pnl']
            gross_pnl = c['gross_pnl']
            costs = c['statutory_charges'] + c['slippage_cost']
            
            day_pnl += net_pnl
            trades.append({
                'Date': dt, 'Symbol': sym, 'Side': side,
                'EntryPrice': entry_p, 'ExitPrice': exit_p, 'Qty': qty,
                'GrossPnL': gross_pnl, 'Costs': costs, 'NetPnL': net_pnl,
                'R': net_pnl / risk_amount,
                'ExitReason': exit_reason
            })
            
        current_equity += day_pnl
        # Update equity on the trade record
        trades[-1]['PortfolioEquity'] = current_equity
        
    df = pd.DataFrame(trades)
    df['PortfolioEquity'] = df['NetPnL'].cumsum() + base_capital # re-sync exact trajectory
    
    n_trades = len(df)
    wins = df[df['NetPnL'] > 0]
    win_rate = (len(wins) / n_trades) * 100.0
    gross_win = wins['GrossPnL'].sum()
    gross_loss = abs(df[df['GrossPnL'] < 0]['GrossPnL'].sum())
    pf = gross_win / gross_loss if gross_loss > 0 else 999.0
    
    gross_pnl = df['GrossPnL'].sum()
    total_costs = df['Costs'].sum()
    net_pnl = df['NetPnL'].sum()
    
    # Drawdown metrics
    df['PeakEquity'] = df['PortfolioEquity'].cummax()
    df['DDPct'] = (df['PeakEquity'] - df['PortfolioEquity']) / df['PeakEquity'] * 100.0
    max_dd_pct = df['DDPct'].max()
    max_dd_rs = (df['PeakEquity'] - df['PortfolioEquity']).max()
    
    # Month by month metrics
    df['YearMonth'] = df['Date'].astype(str).str[:7]
    monthly = df.groupby('YearMonth')['NetPnL'].sum()
    avg_monthly_rs = monthly.mean()
    avg_monthly_pct = (avg_monthly_rs / base_capital) * 100.0
    
    # Year by year metrics
    df['Year'] = df['Date'].astype(str).str[:4]
    yearly = df.groupby('Year')['NetPnL'].sum().to_dict()
    
    min_equity_ever = df['PortfolioEquity'].min()
    cagr = ((current_equity / base_capital) ** (1.0 / 4.8) - 1.0) * 100.0
    
    return {
        'MaxDaily': max_daily_trades,
        'RiskPct': f"{dynamic_risk_pct*100}%",
        'TargetRR': f"1:{target_rr}",
        'Trades': n_trades,
        'WinRate': round(win_rate, 2),
        'PF': round(pf, 2),
        'GrossPnL': round(gross_pnl, 2),
        'Costs': round(total_costs, 2),
        'NetPnL': round(net_pnl, 2),
        'EndingEquity': round(current_equity, 2),
        'MinEquityEver': round(min_equity_ever, 2),
        'InitialCapitalDip': round(((base_capital - min_equity_ever)/base_capital)*100, 2),
        'MaxDD_Rs': round(max_dd_rs, 2),
        'MaxDD_Pct': round(max_dd_pct, 2),
        'AvgMonthlyPct': round(avg_monthly_pct, 2),
        'CAGR': round(cagr, 2),
        'YearlyPnL': yearly,
        'ExitReasons': df['ExitReason'].value_counts().to_dict()
    }

if __name__ == '__main__':
    print("Loading data for clean-room verification...")
    universe = load_data()
    daily_cache = precalculate_features(universe)
    
    print("\n" + "="*80)
    print("RUNNING 100% CLEAN-ROOM RE-BACKTEST (ZERO LOOK-AHEAD, PESSIMISTIC INTRABAR)")
    print("="*80)
    
    # Test 1: Clean-Room 1 Trade Per Day (Top 1 Relative Strength Leader) at 2.5% Dynamic Risk
    res1 = run_clean_room_simulation(daily_cache, max_daily_trades=1, dynamic_risk_pct=0.025, target_rr=4.0)
    print("\n--- TEST 1: PURE LEADER (1 TRADE/DAY, 2.5% RISK) ---")
    for k, v in res1.items():
        if k not in ('YearlyPnL', 'ExitReasons'):
            print(f"{k}: {v}")
    print("Yearly PnL:", res1['YearlyPnL'])
    print("Exit Reasons:", res1['ExitReasons'])
    
    # Test 2: Clean-Room 1 Trade Per Day at 3.0% Dynamic Risk
    res2 = run_clean_room_simulation(daily_cache, max_daily_trades=1, dynamic_risk_pct=0.030, target_rr=4.0)
    print("\n--- TEST 2: PURE LEADER (1 TRADE/DAY, 3.0% RISK) ---")
    for k, v in res2.items():
        if k not in ('YearlyPnL', 'ExitReasons'):
            print(f"{k}: {v}")
    print("Yearly PnL:", res2['YearlyPnL'])
    
    # Test 3: Clean-Room 1 Trade Per Day at Strict 1.0% Fixed Risk (Rs 1,000)
    # Let's run a static 1% risk test for clean-room benchmark
    res3 = run_clean_room_simulation(daily_cache, max_daily_trades=1, dynamic_risk_pct=0.010, target_rr=4.0)
    print("\n--- TEST 3: PURE LEADER (1 TRADE/DAY, 1.0% RISK) ---")
    for k, v in res3.items():
        if k not in ('YearlyPnL', 'ExitReasons'):
            print(f"{k}: {v}")
    print("Yearly PnL:", res3['YearlyPnL'])
    
    # Test 4: Dual Concurrent Trades (Top 2 Leaders, split 1.25% risk each = 2.5% total daily risk)
    res4 = run_clean_room_simulation(daily_cache, max_daily_trades=2, dynamic_risk_pct=0.025, target_rr=4.0)
    print("\n--- TEST 4: DUAL CONCURRENT LEADERS (2 TRADES/DAY, 2.5% TOTAL RISK) ---")
    for k, v in res4.items():
        if k not in ('YearlyPnL', 'ExitReasons'):
            print(f"{k}: {v}")
    print("Yearly PnL:", res4['YearlyPnL'])
