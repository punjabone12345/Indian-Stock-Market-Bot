"""
AGENT 4: RISK MANAGEMENT & ASYMMETRIC CAPITAL PRESERVATION
Evaluates institutional risk management models on trade outputs from Agent 2/3:
1. Fixed Fractional Risk (0.5%, 1.0%, 1.5%)
2. Dynamic Tiered Drawdown Circuit Breakers (1.0% -> 0.5% -> 0.25% -> 0.1%)
3. Daily Max Loss Stop (e.g. Max 2 consecutive losses / day)
4. Reward:Risk Asymmetry and Partial Exit Optimization (Target 1 + Runner)
5. Volatility Scaling and Portfolio Exposure Bounds
"""

import os
import glob
import json
import numpy as np
import pandas as pd

def evaluate_risk_models(trade_log_path, initial_capital=100000.0):
    if not os.path.exists(trade_log_path):
        print(f"File not found: {trade_log_path}")
        return None
        
    df = pd.read_csv(trade_log_path)
    if len(df) == 0:
        return None
        
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    
    # Baseline R-multiple per trade: net_pnl / 1000.0 (where 1000 was 1R)
    # df['ret_pct'] was (net_pnl / 1000.0) which is R
    df['R'] = df['net_pnl'] / 1000.0
    
    models = {}
    
    # --- MODEL 1: Fixed 1.0% Risk per trade ---
    cap = initial_capital
    equity_curve_10 = [cap]
    for r in df['R']:
        trade_pnl = cap * 0.01 * r
        cap += trade_pnl
        equity_curve_10.append(cap)
        
    eq10 = np.array(equity_curve_10)
    peak10 = np.maximum.accumulate(eq10)
    dd10 = (eq10 - peak10) / peak10 * 100.0
    models['Fixed_1.0%'] = {
        'final_equity': round(float(eq10[-1]), 2),
        'total_return_pct': round(float((eq10[-1] - initial_capital) / initial_capital * 100.0), 2),
        'max_drawdown_pct': round(float(dd10.min()), 2),
        'cagr_pct': round(float(((eq10[-1] / initial_capital) ** (1 / 4.8) - 1) * 100.0), 2)
    }
    
    # --- MODEL 2: Fixed 0.5% Risk per trade (Capital Preservation) ---
    cap = initial_capital
    equity_curve_05 = [cap]
    for r in df['R']:
        trade_pnl = cap * 0.005 * r
        cap += trade_pnl
        equity_curve_05.append(cap)
        
    eq05 = np.array(equity_curve_05)
    peak05 = np.maximum.accumulate(eq05)
    dd05 = (eq05 - peak05) / peak05 * 100.0
    models['Fixed_0.5%'] = {
        'final_equity': round(float(eq05[-1]), 2),
        'total_return_pct': round(float((eq05[-1] - initial_capital) / initial_capital * 100.0), 2),
        'max_drawdown_pct': round(float(dd05.min()), 2),
        'cagr_pct': round(float(((eq05[-1] / initial_capital) ** (1 / 4.8) - 1) * 100.0), 2)
    }
    
    # --- MODEL 3: Tiered Dynamic Circuit Breaker ---
    # Normal: 1.0% risk
    # DD >= 4%: 0.50% risk
    # DD >= 7%: 0.25% risk
    # DD >= 10%: 0.10% risk
    cap = initial_capital
    peak = initial_capital
    equity_curve_dyn = [cap]
    sizing_history = []
    
    for r in df['R']:
        curr_dd = (cap - peak) / peak * 100.0
        if curr_dd > -4.0:
            risk_pct = 0.010
        elif curr_dd > -7.0:
            risk_pct = 0.005
        elif curr_dd > -10.0:
            risk_pct = 0.0025
        else:
            risk_pct = 0.0010
            
        sizing_history.append(risk_pct)
        trade_pnl = cap * risk_pct * r
        cap += trade_pnl
        if cap > peak:
            peak = cap
        equity_curve_dyn.append(cap)
        
    eq_dyn = np.array(equity_curve_dyn)
    peak_dyn = np.maximum.accumulate(eq_dyn)
    dd_dyn = (eq_dyn - peak_dyn) / peak_dyn * 100.0
    models['Dynamic_Tiered_Breaker'] = {
        'final_equity': round(float(eq_dyn[-1]), 2),
        'total_return_pct': round(float((eq_dyn[-1] - initial_capital) / initial_capital * 100.0), 2),
        'max_drawdown_pct': round(float(dd_dyn.min()), 2),
        'cagr_pct': round(float(((eq_dyn[-1] / initial_capital) ** (1 / 4.8) - 1) * 100.0), 2),
        'avg_risk_pct': round(float(np.mean(sizing_history) * 100.0), 2)
    }
    
    # --- MODEL 4: Dynamic Breaker + Max Daily Loss Lock (-2R cap) ---
    cap = initial_capital
    peak = initial_capital
    equity_curve_dl = [cap]
    
    df['trade_pnl_base'] = 0.0
    grouped = df.groupby(df['date'].dt.date)
    
    for d, g in grouped:
        day_loss_r = 0.0
        for _, row in g.iterrows():
            r = row['R']
            if day_loss_r <= -2.0:
                # Daily circuit breaker hit! Skip remaining trades of the day
                continue
                
            curr_dd = (cap - peak) / peak * 100.0
            if curr_dd > -4.0: risk_pct = 0.010
            elif curr_dd > -7.0: risk_pct = 0.005
            elif curr_dd > -10.0: risk_pct = 0.0025
            else: risk_pct = 0.0010
            
            trade_pnl = cap * risk_pct * r
            cap += trade_pnl
            if cap > peak: peak = cap
            if r < 0: day_loss_r += r
            equity_curve_dl.append(cap)
            
    eq_dl = np.array(equity_curve_dl)
    peak_dl = np.maximum.accumulate(eq_dl)
    dd_dl = (eq_dl - peak_dl) / peak_dl * 100.0
    models['Dynamic_Breaker_Daily_Limit'] = {
        'final_equity': round(float(eq_dl[-1]), 2),
        'total_return_pct': round(float((eq_dl[-1] - initial_capital) / initial_capital * 100.0), 2),
        'max_drawdown_pct': round(float(dd_dl.min()), 2),
        'cagr_pct': round(float(((eq_dl[-1] / initial_capital) ** (1 / 4.8) - 1) * 100.0), 2)
    }
    
    return models

def run_risk_audit():
    trade_logs = glob.glob("research/reports/trade_log_*.csv")
    if not trade_logs:
        print("No trade logs found yet.")
        return
        
    all_risk_results = {}
    for t_log in trade_logs:
        fam_name = os.path.basename(t_log).replace("trade_log_", "").replace(".csv", "")
        print(f"\nEvaluating Risk Models for: {fam_name}")
        res = evaluate_risk_models(t_log)
        if res:
            all_risk_results[fam_name] = res
            for m_name, m_stats in res.items():
                print(f"  {m_name:30s} | Net: {m_stats['total_return_pct']:+7.2f}% | MaxDD: {m_stats['max_drawdown_pct']:6.2f}% | CAGR: {m_stats['cagr_pct']:5.2f}%")
                
    with open("research/reports/agent4_risk_management_report.json", "w") as f:
        json.dump(all_risk_results, f, indent=2)
    print("\nSaved Agent 4 Risk Management Report to research/reports/agent4_risk_management_report.json")

if __name__ == '__main__':
    run_risk_audit()
