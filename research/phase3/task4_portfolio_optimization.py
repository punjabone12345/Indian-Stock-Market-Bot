"""
TASK 4: PORTFOLIO OPTIMIZATION & DYNAMIC RISK GOVERNOR (2022 - 2026)
Evaluates institutional portfolio construction, alpha weighting, and dynamic risk management:
1. Model 1: Standalone VWAP Retest (100% Benchmark, Fixed 1.0% Risk)
2. Model 2: Standalone VWAP with Ultra-Tight Dynamic Risk Governor
3. Model 3: Dual-Engine Alpha Portfolio (VWAP Retest 70% + ORB Retest 30%)
4. Model 4: Institutional Ensemble Trio (VWAP Retest 60% + ORB Retest 30% + Gap & Go 10%)
5. Model 5: Institutional Ensemble Trio with Dynamic Drawdown Circuit Breaker

Calculates exact daily equity, CMGR, CAGR, Max Drawdown %, Sharpe, Sortino, and Calmar ratios.
"""

import os, json
import numpy as np
import pandas as pd

def compute_metrics(daily_series, initial_capital=100000.0):
    df_d = daily_series.copy()
    df_d['daily_ret'] = df_d['equity'].pct_change().fillna(0.0)
    
    final_eq = df_d['equity'].iloc[-1]
    net_pnl = final_eq - initial_capital
    tot_ret_pct = (final_eq / initial_capital - 1.0) * 100.0
    
    # Drawdown
    df_d['peak'] = df_d['equity'].cummax()
    df_d['dd_pct'] = (df_d['equity'] - df_d['peak']) / df_d['peak'] * 100.0
    max_dd_pct = abs(df_d['dd_pct'].min())
    
    # Days and Months
    n_days = len(df_d)
    n_years = n_days / 248.0 # Standard NSE trading days per year
    cagr = ((final_eq / initial_capital) ** (1.0 / n_years) - 1.0) * 100.0 if n_years > 0 else 0.0
    
    # Monthly returns
    df_d['year_month'] = pd.to_datetime(df_d['date']).dt.to_period('M')
    monthly_eq = df_d.groupby('year_month')['equity'].last()
    monthly_rets = monthly_eq.pct_change().dropna() * 100.0
    
    n_months = len(monthly_rets)
    cmgr = ((final_eq / initial_capital) ** (1.0 / n_months) - 1.0) * 100.0 if n_months > 0 else 0.0
    arith_monthly = monthly_rets.mean()
    win_months = (monthly_rets > 0).sum()
    win_month_pct = (win_months / n_months * 100.0) if n_months > 0 else 0.0
    
    # Sharpe & Sortino (Annualized with 6.5% risk-free rate)
    rf_daily = 0.065 / 248.0
    excess_ret = df_d['daily_ret'] - rf_daily
    daily_vol = df_d['daily_ret'].std()
    sharpe = (excess_ret.mean() / daily_vol * np.sqrt(248.0)) if daily_vol > 0 else 0.0
    
    downside_ret = df_d['daily_ret'][df_d['daily_ret'] < 0]
    downside_vol = downside_ret.std()
    sortino = (excess_ret.mean() / downside_vol * np.sqrt(248.0)) if downside_vol > 0 else 0.0
    
    calmar = cagr / max_dd_pct if max_dd_pct > 0 else 0.0
    
    return {
        'initial_capital': initial_capital,
        'final_equity': round(final_eq, 2),
        'net_profit': round(net_pnl, 2),
        'total_return_pct': round(tot_ret_pct, 2),
        'max_drawdown_pct': round(max_dd_pct, 2),
        'cagr_pct': round(cagr, 2),
        'cmgr_pct': round(cmgr, 2),
        'arith_monthly_avg_pct': round(arith_monthly, 2),
        'total_months': n_months,
        'profitable_months': int(win_months),
        'win_month_pct': round(win_month_pct, 2),
        'sharpe_ratio': round(sharpe, 2),
        'sortino_ratio': round(sortino, 2),
        'calmar_ratio': round(calmar, 2)
    }

def run_portfolio_optimization():
    os.makedirs("research/phase3/reports", exist_ok=True)
    
    # Load trade logs
    df_vwap = pd.read_csv("research/audit/trade_by_trade_vwap_audit.csv")
    df_orb = pd.read_csv("research/phase3/reports/trade_log_ORB_RETEST_SUPPORT_BOUNCE.csv")
    df_gap = pd.read_csv("research/reports/trade_log_GAP_AND_GO_CATALYST.csv")
    
    # Aggregate trades by date
    # 1. VWAP daily net pnl
    vwap_daily = df_vwap.groupby('date')['net_pnl'].sum().reset_index()
    vwap_daily.rename(columns={'net_pnl': 'pnl_vwap'}, inplace=True)
    
    # 2. ORB Retest daily net pnl
    orb_daily = df_orb.groupby('date')['net_pnl'].sum().reset_index()
    orb_daily.rename(columns={'net_pnl': 'pnl_orb'}, inplace=True)
    
    # 3. Gap & Go daily net pnl
    gap_daily = df_gap.groupby('date')['net_pnl'].sum().reset_index()
    gap_daily.rename(columns={'net_pnl': 'pnl_gap'}, inplace=True)
    
    # Merge all trading days
    all_dates = sorted(list(set(vwap_daily['date']).union(set(orb_daily['date'])).union(set(gap_daily['date']))))
    df_master = pd.DataFrame({'date': all_dates})
    df_master = df_master.merge(vwap_daily, on='date', how='left').fillna(0.0)
    df_master = df_master.merge(orb_daily, on='date', how='left').fillna(0.0)
    df_master = df_master.merge(gap_daily, on='date', how='left').fillna(0.0)
    
    # Models to test:
    # Model 1: Standalone VWAP (Fixed 1.0% risk = 1000 INR per trade)
    eq1 = [100000.0]
    for pnl in df_master['pnl_vwap']:
        eq1.append(eq1[-1] + pnl)
    df_m1 = pd.DataFrame({'date': df_master['date'], 'equity': eq1[1:]})
    m1_metrics = compute_metrics(df_m1)
    
    # Model 2: Standalone VWAP with Ultra-Tight Dynamic Risk Governor
    # Tier 1 (DD > -2.0%): 1.0x risk
    # Tier 2 (-4.0% < DD <= -2.0%): 0.65x risk
    # Tier 3 (-6.0% < DD <= -4.0%): 0.35x risk
    # Tier 4 (DD <= -6.0%): 0.15x risk
    eq2 = [100000.0]
    peak2 = 100000.0
    for pnl in df_master['pnl_vwap']:
        cur_dd = (eq2[-1] - peak2) / peak2 * 100.0
        if cur_dd > -2.0:
            scale = 1.0
        elif cur_dd > -4.0:
            scale = 0.65
        elif cur_dd > -6.0:
            scale = 0.35
        else:
            scale = 0.15
        new_eq = eq2[-1] + (pnl * scale)
        if new_eq > peak2: peak2 = new_eq
        eq2.append(new_eq)
    df_m2 = pd.DataFrame({'date': df_master['date'], 'equity': eq2[1:]})
    m2_metrics = compute_metrics(df_m2)
    
    # Model 3: Dual-Engine Momentum & Breakout (VWAP 70% + ORB Retest 30%)
    eq3 = [100000.0]
    for _, row in df_master.iterrows():
        pnl = (row['pnl_vwap'] * 0.70) + (row['pnl_orb'] * 0.30)
        eq3.append(eq3[-1] + pnl)
    df_m3 = pd.DataFrame({'date': df_master['date'], 'equity': eq3[1:]})
    m3_metrics = compute_metrics(df_m3)
    
    # Model 4: Institutional Ensemble Trio (VWAP 60% + ORB 30% + Gap 10%)
    eq4 = [100000.0]
    for _, row in df_master.iterrows():
        pnl = (row['pnl_vwap'] * 0.60) + (row['pnl_orb'] * 0.30) + (row['pnl_gap'] * 0.10)
        eq4.append(eq4[-1] + pnl)
    df_m4 = pd.DataFrame({'date': df_master['date'], 'equity': eq4[1:]})
    m4_metrics = compute_metrics(df_m4)
    
    # Model 5: Institutional Ensemble Trio with Dynamic Drawdown Circuit Breaker
    eq5 = [100000.0]
    peak5 = 100000.0
    for _, row in df_master.iterrows():
        cur_dd = (eq5[-1] - peak5) / peak5 * 100.0
        if cur_dd > -2.0:
            scale = 1.0
        elif cur_dd > -4.0:
            scale = 0.65
        elif cur_dd > -6.0:
            scale = 0.35
        else:
            scale = 0.15
        pnl = ((row['pnl_vwap'] * 0.60) + (row['pnl_orb'] * 0.30) + (row['pnl_gap'] * 0.10)) * scale
        new_eq = eq5[-1] + pnl
        if new_eq > peak5: peak5 = new_eq
        eq5.append(new_eq)
    df_m5 = pd.DataFrame({'date': df_master['date'], 'equity': eq5[1:]})
    m5_metrics = compute_metrics(df_m5)
    
    # Save Daily Equity Comparison
    df_daily_all = pd.DataFrame({
        'date': df_master['date'],
        'equity_m1_vwap_base': df_m1['equity'],
        'equity_m2_vwap_dyn': df_m2['equity'],
        'equity_m3_dual_engine': df_m3['equity'],
        'equity_m4_ensemble_trio': df_m4['equity'],
        'equity_m5_ensemble_dyn': df_m5['equity']
    })
    df_daily_all.to_csv("research/phase3/reports/task4_portfolio_daily_equity.csv", index=False)
    
    summary = [
        {'model_name': 'Model 1: Standalone VWAP Retest (Base Benchmark)', **m1_metrics},
        {'model_name': 'Model 2: Standalone VWAP + Dynamic Risk Governor', **m2_metrics},
        {'model_name': 'Model 3: Dual-Engine Alpha (VWAP 70% + ORB 30%)', **m3_metrics},
        {'model_name': 'Model 4: Ensemble Trio (VWAP 60% + ORB 30% + Gap 10%)', **m4_metrics},
        {'model_name': 'Model 5: Ensemble Trio + Dynamic Risk Governor', **m5_metrics}
    ]
    
    with open("research/phase3/reports/task4_portfolio_optimization_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
        
    print("=" * 110)
    print(f"{'Model Name':50s} | {'CMGR':6s} | {'CAGR':7s} | {'MaxDD':6s} | {'Sharpe':6s} | {'Sortino':7s} | {'Calmar':6s} | {'WinMo%':6s}")
    print("=" * 110)
    for m in summary:
        print(f"{m['model_name']:50s} | {m['cmgr_pct']:5.2f}% | {m['cagr_pct']:6.2f}% | {m['max_drawdown_pct']:5.2f}% | {m['sharpe_ratio']:6.2f} | {m['sortino_ratio']:7.2f} | {m['calmar_ratio']:6.2f} | {m['win_month_pct']:5.1f}%")
    print("=" * 110)
    print("\nSaved Task 4 portfolio comparison to research/phase3/reports/task4_portfolio_daily_equity.csv and summary.json")

if __name__ == '__main__':
    run_portfolio_optimization()
