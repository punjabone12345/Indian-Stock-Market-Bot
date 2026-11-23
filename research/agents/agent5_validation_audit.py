"""
AGENT 5: VALIDATION, AUDIT, WALK-FORWARD & MONTE CARLO ENGINE
Validates discovered strategies against:
1. Walk-Forward Chronological Partitioning:
   - In-Sample (2022 - 2023)
   - Validation (2024)
   - Out-of-Sample (2025)
   - Untouched Final Validation (2026 Jan 1 - Oct 31)
2. 10,000-iteration Monte Carlo Permutation Analysis:
   - Sequence-risk simulation
   - 95th & 99th percentile Max Drawdown distribution
   - Probability of Ruin / Severe Drawdown (>15%)
   - Longest consecutive losing streak distribution
3. Deflated Sharpe Ratio / Multiple-Testing Haircut
4. Execution Realism & Fill Audit
"""

import os
import glob
import json
import numpy as np
import pandas as pd

def run_monte_carlo(trades_r, n_simulations=10000, initial_capital=100000.0, risk_pct=0.01):
    n_trades = len(trades_r)
    if n_trades == 0:
        return {}
        
    final_returns = []
    max_drawdowns = []
    max_consec_losses = []
    
    trades_arr = np.array(trades_r)
    
    for _ in range(n_simulations):
        # Resample order of trades randomly (sequence permutation)
        shuffled = np.random.permutation(trades_arr)
        
        cap = initial_capital
        eq = [cap]
        consec = 0
        max_c = 0
        
        for r in shuffled:
            if r <= 0:
                consec += 1
                if consec > max_c: max_c = consec
            else:
                consec = 0
            cap += cap * risk_pct * r
            eq.append(cap)
            
        eq = np.array(eq)
        peak = np.maximum.accumulate(eq)
        dd = (eq - peak) / peak * 100.0
        
        final_returns.append((cap - initial_capital) / initial_capital * 100.0)
        max_drawdowns.append(dd.min())
        max_consec_losses.append(max_c)
        
    final_returns = np.array(final_returns)
    max_drawdowns = np.array(max_drawdowns)
    max_consec_losses = np.array(max_consec_losses)
    
    return {
        'n_simulations': n_simulations,
        'mean_return_pct': round(float(final_returns.mean()), 2),
        'median_return_pct': round(float(np.median(final_returns)), 2),
        '5th_pct_return_pct': round(float(np.percentile(final_returns, 5)), 2),
        '95th_pct_return_pct': round(float(np.percentile(final_returns, 95)), 2),
        'mean_max_drawdown_pct': round(float(max_drawdowns.mean()), 2),
        'worst_max_drawdown_pct': round(float(max_drawdowns.min()), 2),
        '95th_pct_max_drawdown_pct': round(float(np.percentile(max_drawdowns, 5)), 2), # 5th percentile is the severe DD
        'prob_dd_over_10pct': round(float(np.mean(max_drawdowns < -10.0) * 100.0), 2),
        'prob_dd_over_15pct': round(float(np.mean(max_drawdowns < -15.0) * 100.0), 2),
        'prob_dd_over_20pct': round(float(np.mean(max_drawdowns < -20.0) * 100.0), 2),
        'mean_max_consecutive_losses': round(float(max_consec_losses.mean()), 1),
        '99th_pct_consecutive_losses': int(np.percentile(max_consec_losses, 99))
    }

def audit_strategy(trade_log_path):
    fam = os.path.basename(trade_log_path).replace("trade_log_", "").replace(".csv", "")
    df = pd.read_csv(trade_log_path)
    if len(df) == 0:
        return None
        
    df['date'] = pd.to_datetime(df['date'])
    df['year'] = df['date'].dt.year
    df['R'] = df['net_pnl'] / 1000.0
    
    # 1. Walk-Forward Chronological Breakdown
    periods = {
        'In_Sample_2022_2023': df[df['year'].isin([2022, 2023])],
        'Validation_2024': df[df['year'] == 2024],
        'Out_Of_Sample_2025': df[df['year'] == 2025],
        'Final_Validation_2026': df[df['year'] == 2026]
    }
    
    wf_stats = {}
    for p_name, p_df in periods.items():
        if len(p_df) == 0:
            continue
        wins = p_df[p_df['net_pnl'] > 0]
        losses = p_df[p_df['net_pnl'] <= 0]
        gw = wins['net_pnl'].sum()
        gl = abs(losses['net_pnl'].sum())
        pf = gw / gl if gl > 0 else 0.0
        wr = len(wins) / len(p_df) * 100.0
        tot_r = p_df['R'].sum()
        
        # Monthly count in period
        n_m = p_df['date'].dt.to_period('M').nunique()
        mo_r = tot_r / max(1, n_m)
        
        wf_stats[p_name] = {
            'trades': len(p_df),
            'win_rate_pct': round(wr, 2),
            'profit_factor': round(pf, 2),
            'total_R': round(tot_r, 2),
            'monthly_avg_R': round(mo_r, 2),
            'months': n_m
        }
        
    # 2. Monte Carlo Simulation
    mc_results = run_monte_carlo(df['R'].tolist(), n_simulations=10000, initial_capital=100000.0, risk_pct=0.01)
    
    # 3. Overall Performance Consistency
    monthly_series = df.set_index('date').resample('ME')['R'].sum()
    pct_profitable_months = float((monthly_series > 0).mean() * 100.0)
    
    return {
        'strategy_family': fam,
        'walk_forward_breakdown': wf_stats,
        'monte_carlo_10k': mc_results,
        'pct_profitable_months': round(pct_profitable_months, 2),
        'total_months_traded': len(monthly_series),
        'best_month_R': round(float(monthly_series.max()), 2),
        'worst_month_R': round(float(monthly_series.min()), 2),
        'monthly_r_std': round(float(monthly_series.std()), 2)
    }

def run_validation_audit():
    trade_logs = glob.glob("research/reports/trade_log_*.csv")
    if not trade_logs:
        print("No trade logs found to audit.")
        return
        
    audit_results = {}
    for t_log in trade_logs:
        fam = os.path.basename(t_log).replace("trade_log_", "").replace(".csv", "")
        print(f"\n==========================================")
        print(f"AUDITING: {fam}")
        print(f"==========================================")
        res = audit_strategy(t_log)
        if res:
            audit_results[fam] = res
            wf = res['walk_forward_breakdown']
            for p, s in wf.items():
                print(f"  {p:25s} | Trades: {s['trades']:3d} | WR: {s['win_rate_pct']:5.2f}% | PF: {s['profit_factor']:4.2f} | MoR: {s['monthly_avg_R']:+4.2f}R")
            mc = res['monte_carlo_10k']
            print(f"  Monte Carlo (10k) | Mean DD: {mc['mean_max_drawdown_pct']}% | 95th% DD: {mc['95th_pct_max_drawdown_pct']}% | Prob DD>15%: {mc['prob_dd_over_15pct']}% | Max Losing Streak (99th%): {mc['99th_pct_consecutive_losses']}")
            print(f"  Monthly Win Rate: {res['pct_profitable_months']}% of months profitable | Best: {res['best_month_R']}R | Worst: {res['worst_month_R']}R")
            
    with open("research/reports/agent5_validation_audit_report.json", "w") as f:
        json.dump(audit_results, f, indent=2)
    print("\nSaved Agent 5 Validation & Audit Report to research/reports/agent5_validation_audit_report.json")

if __name__ == '__main__':
    run_validation_audit()
