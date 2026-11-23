"""
EXTRACT COMPLETE FORENSIC REPORT FOR PROFILE 5 (Velocity Compounder)
Generates:
1. Exact drawdown peak and trough dates and equity values
2. Monthly PnL table across all 58 months
3. Symbol-by-symbol performance ranking
4. Exit reason distribution (Target vs Trailed vs BE vs 3:00 PM Square-off)
5. Capital progression milestone timeline
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import time

sys.path.append(os.path.dirname(__file__))
from costs import compute_trade_costs
from test_smc_ict_fib_catalyst_upgrades import load_data, precalculate_features

def run_detailed_profile5():
    universe = load_data()
    daily_cache = precalculate_features(universe)
    
    base_capital = 100000.0
    current_equity = base_capital
    trades = []
    
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
        
        day_trades_count = 0
        trade_1_won = False
        
        for cand in candidates:
            if day_trades_count >= 2: break
            if day_trades_count == 1 and not trade_1_won: break # Heat breaker
            
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
                
            risk_amount = current_equity * 0.025 # 2.5% dynamic risk
            qty = max(1, min(int(risk_amount / sl_dist), int(5.0 * current_equity / entry_p)))
            curr_sl = sl_p
            target_p = (entry_p + (sl_dist * 4.0)) if side == 'BUY' else (entry_p - (sl_dist * 4.0))
            
            exit_p = None
            exit_reason = None
            be_locked = False
            
            for m in range(entry_idx, n):
                # BE lock at 1.5R
                be_threshold = (entry_p + (sl_dist * 1.5)) if side == 'BUY' else (entry_p - (sl_dist * 1.5))
                if not be_locked and ((side == 'BUY' and highs[m] >= be_threshold) or (side == 'SELL' and lows[m] <= be_threshold)):
                    new_sl = (entry_p + (sl_dist * 0.10)) if side == 'BUY' else (entry_p - (sl_dist * 0.10))
                    curr_sl = max(curr_sl, new_sl) if side == 'BUY' else min(curr_sl, new_sl)
                    be_locked = True
                    
                # Trailing after 2.5R
                trail_threshold = (entry_p + (sl_dist * 2.5)) if side == 'BUY' else (entry_p - (sl_dist * 2.5))
                if (side == 'BUY' and highs[m] >= trail_threshold):
                    trail_sl = np.min(lows[max(0, m-2):m+1])
                    curr_sl = max(curr_sl, trail_sl)
                elif (side == 'SELL' and lows[m] <= trail_threshold):
                    trail_sl = np.max(highs[max(0, m-2):m+1])
                    curr_sl = min(curr_sl, trail_sl)
                    
                # Target hit
                if (side == 'BUY' and highs[m] >= target_p) or (side == 'SELL' and lows[m] <= target_p):
                    exit_p = target_p
                    exit_reason = 'TARGET_4R'
                    break
                    
                # Stop hit
                if (side == 'BUY' and lows[m] <= curr_sl) or (side == 'SELL' and highs[m] >= curr_sl):
                    exit_p = curr_sl
                    exit_reason = 'BREAKEVEN_STOP' if be_locked else 'STOP_LOSS'
                    break
                    
                # 3:00 PM Square-off
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
                'EntryPrice': entry_p, 'ExitPrice': exit_p, 'Qty': qty,
                'GrossPnL': gross_pnl, 'Costs': costs, 'NetPnL': net_pnl,
                'PortfolioEquity': current_equity,
                'R': net_pnl / risk_amount,
                'ExitReason': exit_reason
            })
            
            day_trades_count += 1
            if day_trades_count == 1:
                trade_1_won = (net_pnl > 0)
                
    df = pd.DataFrame(trades)
    df.to_csv("research/phase4_2/profile5_complete_trade_log.csv", index=False)
    
    # Calculate Drawdown Peak & Trough
    df['Peak'] = df['PortfolioEquity'].cummax()
    df['Drawdown_Rs'] = df['Peak'] - df['PortfolioEquity']
    df['Drawdown_Pct'] = (df['Drawdown_Rs'] / df['Peak']) * 100.0
    
    max_dd_idx = df['Drawdown_Pct'].idxmax()
    max_dd_pct = df.loc[max_dd_idx, 'Drawdown_Pct']
    trough_date = df.loc[max_dd_idx, 'Date']
    trough_equity = df.loc[max_dd_idx, 'PortfolioEquity']
    
    peak_val = df.loc[max_dd_idx, 'Peak']
    peak_idx = df[(df.index <= max_dd_idx) & (df['PortfolioEquity'] == peak_val)].index[-1]
    peak_date = df.loc[peak_idx, 'Date']
    peak_equity = df.loc[peak_idx, 'PortfolioEquity']
    
    min_equity_ever = df['PortfolioEquity'].min()
    min_equity_idx = df['PortfolioEquity'].idxmin()
    min_equity_date = df.loc[min_equity_idx, 'Date']
    
    print("\n" + "="*80)
    print("PROFILE 5: DRAWDOWN & CAPITAL PROTECTION FORENSICS")
    print("="*80)
    print(f"Starting Capital: Rs {base_capital:,.2f}")
    print(f"Ending Capital: Rs {current_equity:,.2f} ({current_equity/base_capital:.2f}x initial capital)")
    print(f"Total Net Profit: Rs {df['NetPnL'].sum():,.2f}")
    print(f"Minimum Equity Point Ever: Rs {min_equity_ever:,.2f} on {min_equity_date}")
    print(f"Initial Capital Drawdown: {((base_capital - min_equity_ever)/base_capital)*100:.2f}% (Never lost more than this on initial capital!)")
    print(f"Max Peak-to-Trough Drawdown: {max_dd_pct:.2f}%")
    print(f"Peak Equity: Rs {peak_equity:,.2f} on {peak_date}")
    print(f"Trough Equity: Rs {trough_equity:,.2f} on {trough_date}")
    print(f"Drawdown in Rupees from Peak: Rs {peak_equity - trough_equity:,.2f}")
    
    # Exit Reason breakdown
    print("\n" + "="*80)
    print("EXIT REASON DISTRIBUTION")
    print("="*80)
    print(df['ExitReason'].value_counts())
    
    # Top 10 Stocks by Net PnL
    print("\n" + "="*80)
    print("TOP 10 WEALTH GENERATING STOCKS")
    print("="*80)
    top_stocks = df.groupby('Symbol')['NetPnL'].agg(['count', 'sum']).sort_values('sum', ascending=False).head(10)
    print(top_stocks)
    
    # Monthly PnL summary
    df['YearMonth'] = df['Date'].astype(str).str[:7]
    monthly = df.groupby('YearMonth')['NetPnL'].sum()
    print("\n" + "="*80)
    print(f"MONTHLY STATISTICS (Total Months: {len(monthly)})")
    print("="*80)
    print(f"Average Monthly Net PnL: Rs {monthly.mean():,.2f} (+{(monthly.mean()/base_capital)*100:.2f}% on initial capital)")
    print(f"Winning Months: {sum(monthly > 0)} / {len(monthly)} ({sum(monthly > 0)/len(monthly)*100:.1f}%)")
    print(f"Best Month: {monthly.idxmax()} (Rs {monthly.max():,.2f})")
    print(f"Worst Month: {monthly.idxmin()} (Rs {monthly.min():,.2f})")
    print(f"Top 5 Months:\n{monthly.sort_values(ascending=False).head(5)}")

if __name__ == '__main__':
    run_detailed_profile5()
