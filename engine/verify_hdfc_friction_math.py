import pandas as pd
import numpy as np

# Load the 876 trades from Option A
df = pd.read_csv('reports/precision_price_action_trades.csv')
print(f"Loaded {len(df)} trades.")

# In the original file, df['R'] had standard 0.04R deduction.
# Let's reconstruct raw trade outcome and apply the realistic Indian Equity Intraday Cost:
# For a 0.20% SL trade risking ₹1,000 (Quantity = 333 shares @ ₹1,500 = ₹5 Lakh turnover):
# - Brokerage (Buy + Sell): ₹40.00
# - STT (0.025% on sell): ₹125.00
# - Exchange transaction charge (0.00297%): ₹29.70
# - GST (18% on brokerage + txn charges): ₹12.55
# - Stamp duty (0.003% on buy): ₹15.00
# - SEBI turnover fee: ₹1.00
# - Realistic bid-ask slippage (1 tick = 0.05 on ₹1500 = 0.0033% x 2 sides = ~₹33)
# Total friction = ₹223.25 + ₹33 = ₹256 per trade on ₹1,000 risk!
# That is ~0.15R to 0.20R per trade!

for cost_r in [0.05, 0.10, 0.15, 0.20]:
    # Adjust each trade:
    # If trade was a loss (-1.0R): becomes -(1.0 + cost_r)
    # If trade was win: R_net = R_gross - cost_r
    # Note: original df['R'] already had 0.04R deducted.
    # So raw R = df['R'] + 0.04
    raw_r = df['R'] + 0.04
    net_r = np.where(raw_r > 0, raw_r - cost_r, raw_r - cost_r)
    
    total_net_r = net_r.sum()
    monthly_avg_r = total_net_r / 49.0
    profit_1k_risk = total_net_r * 1000
    
    print(f"\n--- COST SCENARIO: {cost_r*100:.0f}% of Risk (₹{int(cost_r*1000)} cost per ₹1k risk trade) ---")
    print(f"Total Net Realized R : {total_net_r:.1f}R")
    print(f"Average Monthly R    : {monthly_avg_r:.2f}R / month")
    print(f"Net Profit (₹1k risk): ₹{int(profit_1k_risk):,} in 4 years (₹{int(profit_1k_risk/49):,}/month)")
