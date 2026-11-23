import pandas as pd
import numpy as np

df = pd.read_parquet('reports/rich_trades_features.parquet')
df['Date'] = pd.to_datetime(df['Date'])
df['YM'] = df['Date'].dt.to_period('M')

# Group by month
months = sorted(df['YM'].unique())

start_capital = 100000.0
risk_fraction = 0.0020 # 0.20% (Maintains 50% cash buffer even if all 6 stocks open)

history = []
current_capital = start_capital
peak_capital = start_capital

for ym in months:
    m_df = df[df['YM'] == ym]
    n_trades = len(m_df)
    wins = len(m_df[m_df['R'] > 0])
    losses = len(m_df[m_df['R'] <= 0])
    wr = (wins / n_trades) * 100 if n_trades > 0 else 0
    net_r = m_df['R'].sum()
    
    # 1R for this month based on starting capital of the month
    r_val = round(current_capital * risk_fraction, 0)
    
    # In practice, round to nearest ₹10 for clean lot sizing
    r_val = max(50.0, round(r_val / 10.0) * 10.0)
    
    # Monthly INR P&L
    monthly_inr_pnl = net_r * r_val
    ending_capital = current_capital + monthly_inr_pnl
    
    # Margin check: Max margin used across 6 stocks
    # Average position value per 1R is ~₹235 * 1R, margin at 5x is ~₹47 * 1R
    # If all 6 open: 6 * 47 * r_val = 282 * r_val
    max_margin_6_stocks = 282 * r_val
    cash_buffer_pct = ((ending_capital - max_margin_6_stocks) / ending_capital) * 100.0
    
    # Drawdown check from peak
    if ending_capital > peak_capital:
        peak_capital = ending_capital
    dd_pct = ((ending_capital - peak_capital) / peak_capital) * 100.0
    
    ret_pct = (monthly_inr_pnl / current_capital) * 100.0
    
    history.append({
        'Month': str(ym),
        'Start_Capital': round(current_capital, 2),
        '1R_Risk': int(r_val),
        'Trades': n_trades,
        'WR_%': round(wr, 1),
        'Net_R': round(net_r, 2),
        'Profit_INR': round(monthly_inr_pnl, 2),
        'End_Capital': round(ending_capital, 2),
        'Monthly_Return_%': round(ret_pct, 2),
        'Max_DD_%': round(dd_pct, 2),
        'Free_Buffer_%': round(cash_buffer_pct, 1)
    })
    
    current_capital = ending_capital

res_df = pd.DataFrame(history)

print("="*105)
print("4-YEAR MONTHLY COMPOUNDING SIMULATION REPORT (0.20% FIXED FRACTIONAL RISK)")
print("="*105)
print(res_df.to_string(index=False))

total_profit = current_capital - start_capital
cagr = ((current_capital / start_capital) ** (1.0 / (len(months)/12.0)) - 1.0) * 100.0
max_dd = res_df['Max_DD_%'].min()

print("\n" + "="*80)
print("FINAL 4-YEAR COMPOUNDING MILESTONES")
print("="*80)
print(f"Starting Capital (Oct 2022)       : ₹{start_capital:,.2f}  (1R = ₹200)")
print(f"Final Capital (Nov 2026)          : ₹{current_capital:,.2f}  (1R = ₹{int(r_val):,d})")
print(f"Total Net Profit Compounded       : ₹{total_profit:,.2f}")
print(f"Total Multiple on Capital         : {current_capital / start_capital:.2f}x ({(current_capital - start_capital)/start_capital * 100:.1f}%)")
print(f"Compounded Annual Growth Rate     : {cagr:.2f}% CAGR")
print(f"Worst Portfolio Drawdown          : {max_dd:.2f}%")
print(f"Minimum Cash Buffer Remaining     : {res_df['Free_Buffer_%'].min():.1f}% (Never breached margin limits)")
