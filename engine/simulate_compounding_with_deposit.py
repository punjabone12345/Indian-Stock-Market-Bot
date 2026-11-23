import pandas as pd
import numpy as np

df = pd.read_parquet('reports/rich_trades_features.parquet')
df['Date'] = pd.to_datetime(df['Date'])
df['YM'] = df['Date'].dt.to_period('M')

months = sorted(df['YM'].unique())

start_capital = 100000.0
monthly_deposit = 50000.0
risk_fraction = 0.0020 # 0.20% fixed fractional risk

history = []
current_capital = start_capital
peak_capital = start_capital
total_deposits = start_capital # Initial deposit

for i, ym in enumerate(months):
    m_df = df[df['YM'] == ym]
    n_trades = len(m_df)
    wins = len(m_df[m_df['R'] > 0])
    losses = len(m_df[m_df['R'] <= 0])
    wr = (wins / n_trades) * 100 if n_trades > 0 else 0
    net_r = m_df['R'].sum()
    
    # Starting capital for trading this month
    # Note: On month 0 (first month), capital is 100k. On subsequent months, user deposits 50k at the beginning of the month.
    if i > 0:
        current_capital += monthly_deposit
        total_deposits += monthly_deposit
        
    start_of_month_cap = current_capital
    
    # 1R for this month based on starting capital (rounded to nearest 10)
    r_val = round(start_of_month_cap * risk_fraction, 0)
    r_val = max(50.0, round(r_val / 10.0) * 10.0)
    
    # Monthly INR P&L
    monthly_inr_pnl = net_r * r_val
    ending_capital = start_of_month_cap + monthly_inr_pnl
    
    # Margin check
    max_margin_6_stocks = 282 * r_val
    cash_buffer_pct = ((ending_capital - max_margin_6_stocks) / ending_capital) * 100.0
    
    if ending_capital > peak_capital:
        peak_capital = ending_capital
    dd_pct = ((ending_capital - peak_capital) / peak_capital) * 100.0
    
    ret_pct = (monthly_inr_pnl / start_of_month_cap) * 100.0
    
    history.append({
        'Month': str(ym),
        'Start_Capital': round(start_of_month_cap, 2),
        'Added_Deposit': 0.0 if i == 0 else monthly_deposit,
        'Cumulative_Deposited': round(total_deposits, 2),
        '1R_Risk': int(r_val),
        'Trades': n_trades,
        'WR_%': round(wr, 1),
        'Net_R': round(net_r, 2),
        'Trading_Profit_INR': round(monthly_inr_pnl, 2),
        'End_Capital': round(ending_capital, 2),
        'Monthly_Return_%': round(ret_pct, 2),
        'Free_Buffer_%': round(cash_buffer_pct, 1)
    })
    
    current_capital = ending_capital

res_df = pd.DataFrame(history)

print("="*115)
print("4-YEAR MONTHLY COMPOUNDING WITH ₹50,000 MONTHLY DEPOSIT (0.20% RISK)")
print("="*115)
print(res_df.to_string(index=False))

total_profit_earned = current_capital - total_deposits
multiple_on_deposits = current_capital / total_deposits

print("\n" + "="*80)
print("FINAL COMPARISON: WITHOUT DEPOSIT vs WITH ₹50,000 MONTHLY DEPOSIT")
print("="*80)
print(f"Total Personal Cash Invested (100k + 48*50k): ₹{total_deposits:,.2f}")
print(f"Final Capital Balance (Nov 2026)             : ₹{current_capital:,.2f}  (₹{current_capital/10000000:.2f} Crore!)")
print(f"Total Net Trading Profit Generated           : ₹{total_profit_earned:,.2f}")
print(f"Final 1R Risk per trade                      : ₹{int(r_val):,d}")
print(f"Multiple on Total Deposited Capital          : {multiple_on_deposits:.2f}x")
