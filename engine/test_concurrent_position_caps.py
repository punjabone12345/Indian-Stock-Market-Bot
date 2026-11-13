import pandas as pd
import numpy as np

# Load the full trade log
df = pd.read_csv('reports/option_c_full_trades.csv')
df['Date'] = pd.to_datetime(df['Date'])
df['EntryDateTime'] = pd.to_datetime(df['Date'].astype(str) + ' ' + df['EntryTime'])
df['ExitDateTime'] = pd.to_datetime(df['Date'].astype(str) + ' ' + df['ExitTime'])
df = df.sort_values('EntryDateTime').reset_index(drop=True)

# Test different Max Concurrent Open Positions caps: 2, 3, 4, 6
for max_open in [2, 3, 4, 6]:
    # Simulate chronological execution with max_open cap
    active_positions = [] # list of exit times and margin factors
    executed_trades = []
    
    for idx, r in df.iterrows():
        entry_t = r['EntryDateTime']
        # Remove positions that have already exited
        active_positions = [pos for pos in active_positions if pos['ExitTime'] > entry_t]
        
        # Check if we can open a new position
        if len(active_positions) < max_open:
            margin_fac = (r['EntryPrice'] / r['SL_Dist']) / 5.0
            active_positions.append({'ExitTime': r['ExitDateTime'], 'Margin_Factor': margin_fac})
            executed_trades.append(r)
            
    df_exec = pd.DataFrame(executed_trades)
    df_exec['YM'] = df_exec['Date'].dt.to_period('M')
    num_m = df_exec['YM'].nunique()
    tot_r = df_exec['R'].sum()
    r_m = tot_r / num_m
    cum = df_exec['R'].cumsum()
    max_dd = (cum - cum.cummax()).min()
    wr = (df_exec['R'] > 0).mean() * 100
    pf = df_exec[df_exec['R'] > 0]['R'].sum() / abs(df_exec[df_exec['R'] < 0]['R'].sum())
    
    # Calculate peak margin factor across this capped stream
    events = []
    for idx, r in df_exec.iterrows():
        margin_fac = (r['EntryPrice'] / r['SL_Dist']) / 5.0
        events.append({'Time': r['EntryDateTime'], 'Type': 'ENTER', 'Margin_Factor': margin_fac})
        events.append({'Time': r['ExitDateTime'], 'Type': 'EXIT', 'Margin_Factor': margin_fac})
    df_ev = pd.DataFrame(events).sort_values(['Time', 'Type'], ascending=[True, False])
    
    cur_mf = 0
    peak_mf = 0
    for idx, ev in df_ev.iterrows():
        if ev['Type'] == 'ENTER': cur_mf += ev['Margin_Factor']
        else: cur_mf -= ev['Margin_Factor']
        if cur_mf > peak_mf: peak_mf = cur_mf
        
    print("-" * 85)
    print(f"CAP: MAX CONCURRENT OPEN POSITIONS = {max_open}")
    print(f"Trades Taken: {len(df_exec)} (out of {len(df)}) | Win Rate: {wr:.1f}% | Profit Factor: {pf:.2f}")
    print(f"Monthly Return: {r_m:+.2f} R / mo | Total R: {tot_r:+.1f} R | Max Drawdown: {max_dd:.1f} R")
    print(f"Peak Concurrent Margin Factor: {peak_mf:.1f}x (Margin needed per 1 INR of 1R risk)")
    
    # For Capital = 100,000 INR, calculate the maximum 1R risk that NEVER runs out of margin
    # Available capital at bottom of Max DD = 100,000 - (abs(max_dd) * 1R)
    # Peak margin required = peak_mf * 1R
    # Equation: 100,000 - (abs(max_dd) * 1R) >= peak_mf * 1R
    # => 1R * (peak_mf + abs(max_dd)) <= 100,000
    # => Max 1R = 100,000 / (peak_mf + abs(max_dd))
    max_safe_1r = 100000.0 / (peak_mf + abs(max_dd))
    print(f"--> MATHEMATICALLY BULLETPROOF 1R RISK FOR ₹1,00,000: ₹{int(max_safe_1r)} PER TRADE")
    print(f"--> At ₹{int(max_safe_1r)} 1R: Monthly Expected Profit = ₹{int(r_m * max_safe_1r):,} / month")
    print(f"--> At ₹{int(max_safe_1r)} 1R: Worst-Case Max Drawdown = -₹{int(abs(max_dd) * max_safe_1r):,}")
    print(f"--> At ₹{int(max_safe_1r)} 1R: Peak Margin Ever Used = ₹{int(peak_mf * max_safe_1r):,}")
    print(f"--> Remaining Free Cash at Absolute Worst Moment in 4 Years: ₹{int(100000 - (peak_mf + abs(max_dd))*max_safe_1r):,}")
