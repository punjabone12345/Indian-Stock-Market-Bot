"""
IN-DEPTH DRAWDOWN & RISK GOVERNOR ANALYSIS
Analyze drawdown episodes of the Master Strategy:
SL 1.2%, T1 2.0R, T2 4.0R, 3 trades/day, Pure EOD Runner
"""

import os, glob
import numpy as np
import pandas as pd
from verify_forensic_static import load_data, run_simulation

def analyze_master_system():
    symbol_days, dates, market_regime = load_data()
    res = run_simulation(symbol_days, dates, market_regime,
                         min_gap=1.2, min_rvol=2.5, sl_pct=0.012,
                         t1_r=2.0, t2_r=4.0, max_trades_per_day=3,
                         runner_mode='eod_pure')
    
    df_t = res['df_t']
    
    # Analyze losing streaks
    losses = (df_t['net_pnl'] <= 0).astype(int)
    streak = 0
    max_loss_streak = 0
    streaks = []
    for l in losses:
        if l == 1:
            streak += 1
            if streak > max_loss_streak:
                max_loss_streak = streak
        else:
            if streak > 0:
                streaks.append(streak)
            streak = 0
            
    print(f"Max Consecutive Loss Streak: {max_loss_streak} trades")
    print(f"Average Losing Streak: {np.mean(streaks):.2f} trades")
    
    # Analyze Drawdown Episodes
    df_t['cum'] = df_t['net_pnl'].cumsum()
    df_t['peak'] = df_t['cum'].cummax()
    df_t['dd'] = df_t['cum'] - df_t['peak']
    
    # Find worst drawdown date and recovery
    worst_idx = df_t['dd'].idxmin()
    worst_row = df_t.loc[worst_idx]
    peak_before = df_t.loc[:worst_idx]['cum'].idxmax()
    peak_row = df_t.loc[peak_before]
    
    # Recovery
    recovery_rows = df_t.loc[worst_idx:]
    recovery = recovery_rows[recovery_rows['cum'] >= peak_row['cum']]
    recovery_date = recovery.iloc[0]['date'] if len(recovery) > 0 else "Not yet"
    
    print(f"\n--- WORST DRAWDOWN EPISODE ---")
    print(f"Peak Date: {peak_row['date']} (Cumulative Profit: Rs {peak_row['cum']:,.0f})")
    print(f"Trough Date: {worst_row['date']} (Cumulative Profit: Rs {worst_row['cum']:,.0f})")
    print(f"Max Drawdown: Rs {worst_row['dd']:,.0f} ({abs(worst_row['dd'])/100000*100:.2f}%)")
    print(f"Recovery Date: {recovery_date}")
    
    # Monthly Returns Distribution
    mo = res['monthly_pnl']
    print(f"\n--- MONTHLY PERFORMANCE ---")
    print(f"Total Months: {len(mo)}")
    print(f"Profitable Months: {(mo > 0).sum()} ({(mo > 0).mean()*100:.1f}%)")
    print(f"Loss Months: {(mo <= 0).sum()}")
    print(f"Best Month: Rs {mo.max():+,.0f} ({mo.max()/1000:.1f}%)")
    print(f"Worst Month: Rs {mo.min():+,.0f} ({mo.min()/1000:.1f}%)")
    print(f"Average Month: Rs {mo.mean():+,.0f} ({mo.mean()/1000:.2f}%)")
    print(f"Median Month: Rs {mo.median():+,.0f} ({mo.median()/1000:.2f}%)")
    
    print("\n--- MONTHLY BREAKDOWN ---")
    for ym, val in mo.items():
        print(f"  {ym}: Rs {val:+8,.0f} ({val/1000:+5.1f}%) | {'PROFIT' if val > 0 else 'LOSS'}")

if __name__ == '__main__':
    analyze_master_system()
