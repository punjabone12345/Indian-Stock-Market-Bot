"""
TEST RISK SIZING VS DRAWDOWN FRONTIER
Evaluates the Master System across different base risk amounts (Rs 500, Rs 600, Rs 750, Rs 1000)
and adaptive drawdown circuit breakers.
"""

import numpy as np
import pandas as pd
from verify_forensic_static import load_data, run_simulation

def evaluate_risk_frontier():
    symbol_days, dates, market_regime = load_data()
    
    # Run with Rs 1000 base to get trades
    res = run_simulation(symbol_days, dates, market_regime,
                         min_gap=1.2, min_rvol=2.5, sl_pct=0.012,
                         t1_r=2.0, t2_r=4.0, max_trades_per_day=3,
                         runner_mode='eod_pure')
    
    df_t = res['df_t']
    
    print("\n" + "="*80)
    print("CAPITAL RISK SIZING FRONTIER (BASE CAPITAL: Rs 1,00,000, ZERO COMPOUNDING)")
    print("="*80)
    
    for risk in [500.0, 600.0, 750.0, 850.0, 1000.0]:
        mult = risk / 1000.0
        pnl = df_t['net_pnl'] * mult
        cum = pnl.cumsum()
        peak = cum.cummax()
        dd = cum - peak
        max_dd_inr = abs(dd.min())
        max_dd_pct = max_dd_inr / 100000.0 * 100.0
        
        tot_pnl = pnl.sum()
        mo_pnl = (df_t.assign(pnl=pnl)).groupby('ym')['pnl'].sum()
        avg_mo_ret = tot_pnl / 100000.0 / len(mo_pnl) * 100.0
        prof_mo = (mo_pnl > 0).mean() * 100.0
        calmar = (tot_pnl / 100000.0 / (len(mo_pnl) / 12.0)) / (max_dd_pct / 100.0)
        
        print(f"Risk: Rs {risk:4.0f} ({risk/1000:.1f}% risk/tr) | Net PnL: Rs {tot_pnl:+9,.0f} | Avg Mo Ret: {avg_mo_ret:+5.2f}%/mo | Max DD: {max_dd_pct:5.2f}% (Rs {max_dd_inr:6,.0f}) | Calmar: {calmar:4.2f} | Prof Mo: {prof_mo:.1f}%")

if __name__ == '__main__':
    evaluate_risk_frontier()
