import pandas as pd
import numpy as np

# Load Option A trades
df = pd.read_csv('reports/precision_price_action_trades.csv')
print(f"Loaded {len(df)} trades.")

# Base parameters
initial_capital = 500000.0 # ₹5 Lakhs

# Let's test Compounded Equity Sizing:
# Sizing 1R = 1.0% of current capital (or 0.75%)
# Notice: When capital grows, R in INR grows exponentially!
# Let's measure:
# 1. Final Capital
# 2. Total Profit in INR
# 3. Equivalent Initial R (Profit / Initial 1R)
# 4. Max Drawdown % of capital

for risk_pct in [0.5, 0.75, 1.0, 1.5]:
    capital = initial_capital
    initial_1r = capital * (risk_pct / 100.0)
    peak_capital = capital
    max_dd_pct = 0.0
    equity_curve = []

    for _, row in df.iterrows():
        trade_r = row['R'] # Already net of slippage
        risk_inr = capital * (risk_pct / 100.0)
        pnl_inr = trade_r * risk_inr
        capital += pnl_inr

        if capital > peak_capital:
            peak_capital = capital
        dd_pct = (capital - peak_capital) / peak_capital * 100.0
        if dd_pct < max_dd_pct:
            max_dd_pct = dd_pct

        equity_curve.append(capital)

    total_profit = capital - initial_capital
    compounded_r = total_profit / initial_1r
    monthly_r = compounded_r / 49.0
    max_dd_r = abs(max_dd_pct) / risk_pct # Drawdown in initial R units

    print("\n" + "="*65)
    print(f"COMPOUNDED SIZING: Risk {risk_pct}% of Current Equity (Initial 1R = ₹{int(initial_1r)})")
    print("="*65)
    print(f"Initial Capital       : ₹{int(initial_capital):,}")
    print(f"Final Capital         : ₹{int(capital):,}")
    print(f"Total Net Cash Profit : ₹{int(total_profit):,} (+{total_profit/initial_capital*100:.1f}%)")
    print(f"Total Compounded R    : +{compounded_r:.1f} R (in initial R units!)")
    print(f"AVERAGE R PER MONTH   : +{monthly_r:.1f} R / MONTH!")
    print(f"Maximum Account DD    : {max_dd_pct:.1f}% ({max_dd_r:.1f} R equivalent)")
    print("="*65)
