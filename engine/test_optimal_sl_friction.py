import pandas as pd
import numpy as np

# Let's test the trade data with realistic turnover costs
# Load the trade logs
df_a = pd.read_csv('reports/precision_price_action_trades.csv')

print("="*70)
print("   EXACT REAL-WORLD EXECUTION AUDIT: HDFC BANK EXAMPLE & EQUITY FRICTION")
print("="*70)

# 1. HDFC Bank Single Trade Breakdown:
price = 1500.0
sl_pct = 0.0020 # 0.20%
sl_dist = price * sl_pct # ₹3.00
risk_inr = 1000.0
qty = int(risk_inr / sl_dist) # 333 shares
buy_turnover = qty * price # ₹4,99,500
sell_turnover_sl = qty * (price - sl_dist) # ₹4,98,501
roundtrip_turnover = buy_turnover + sell_turnover_sl

brokerage = 40.0 # Zerodha flat ₹20 buy + ₹20 sell
stt = sell_turnover_sl * 0.00025 # 0.025% on sell
exch_turnover = roundtrip_turnover * 0.0000297 # NSE txn charge
gst = (brokerage + exch_turnover) * 0.18 # 18% GST
stamp_duty = buy_turnover * 0.00003 # 0.003% on buy
sebi = roundtrip_turnover * 0.000001 # ₹10 / crore
spread_slippage = qty * 0.05 # 1 tick spread (₹0.05)

total_cost = brokerage + stt + exch_turnover + gst + stamp_duty + sebi + spread_slippage
cost_r = total_cost / risk_inr

print(f"HDFC Bank Stock Price     : ₹{price:.2f}")
print(f"Stop Loss (0.20%)         : ₹{sl_dist:.2f} (SL @ ₹{price - sl_dist:.2f})")
print(f"Position Quantity         : {qty} shares (to risk exact ₹{risk_inr:,.0f})")
print(f"Roundtrip Turnover        : ₹{roundtrip_turnover:,.2f} (~₹10 Lakhs)")
print(f"Brokerage (Buy + Sell)    : ₹{brokerage:.2f}")
print(f"STT (0.025% Sell)         : ₹{stt:.2f}")
print(f"NSE Exchange Charges      : ₹{exch_turnover:.2f}")
print(f"GST (18%)                 : ₹{gst:.2f}")
print(f"Stamp Duty (Buy)          : ₹{stamp_duty:.2f}")
print(f"SEBI Turnover Fee         : ₹{sebi:.2f}")
print(f"Spread Slippage (1 tick)  : ₹{spread_slippage:.2f}")
print(f"TOTAL REAL-WORLD COST     : ₹{total_cost:.2f} per trade")
print(f"COST AS FRACTION OF 1R    : {cost_r:.3f}R ({cost_r*100:.1f}% of risk!)")
print("="*70)

# Now evaluate the portfolio net returns across realistic cost levels
raw_r = df_a['R'] + 0.04 # recover un-penalized R

print("\n--- 4-YEAR PORTFOLIO NET RETURNS (876 TRADES / 49 MONTHS) ---")
for c_inr in [80, 120, 180, 240]:
    c_r = c_inr / 1000.0
    net_series = raw_r - c_r
    total_net_r = net_series.sum()
    monthly_r = total_net_r / 49.0
    total_profit_inr = total_net_r * 1000.0
    monthly_profit_inr = total_profit_inr / 49.0
    
    print(f"\nIf Average Cost per Trade is ₹{c_inr} ({c_r:.2f}R):")
    print(f"  Total Realized Net Return : +{total_net_r:.1f}R")
    print(f"  Average Monthly Net Return: +{monthly_r:.2f}R / month")
    print(f"  Net Cash Profit (₹1k risk): ₹{int(total_profit_inr):,} in 4 years (₹{int(monthly_profit_inr):,}/month)")
