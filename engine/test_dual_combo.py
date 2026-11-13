import sys
sys.path.append('engine')
import pandas as pd
from optimal_combo_simulator import get_asset_trades, evaluate_portfolio
from nifty_alpha_explorer import load_nifty_fast
from portfolio_synergy import load_bnf

nifty_1m = load_nifty_fast()
bnf_1m = load_bnf()

t_nifty_15m = get_asset_trades('NIFTY', nifty_1m, tf=15, target_rr=3.5, sl_mode='FORMATION_EXTREME')
t_bnf_3m = get_asset_trades('BANKNIFTY', bnf_1m, tf=3, target_rr=3.5, sl_mode='TRIGGER_CANDLE')
t_bnf_15m = get_asset_trades('BANKNIFTY', bnf_1m, tf=15, target_rr=3.0, sl_mode='FORMATION_EXTREME')

print("\n--- 1. NIFTY 15m ALONE ---")
evaluate_portfolio(t_nifty_15m, "Nifty 15m Alone", max_daily_losses=1, max_daily_trades=1)

print("\n--- 2. BANK NIFTY 15m ALONE ---")
evaluate_portfolio(t_bnf_15m, "Bank Nifty 15m Alone", max_daily_losses=1, max_daily_trades=1)

print("\n--- 3. NIFTY 15m + BANK NIFTY 15m (Dual Index 15m) ---")
evaluate_portfolio(t_nifty_15m + t_bnf_15m, "Dual Index 15m (1 Trade/Day Max)", max_daily_losses=1, max_daily_trades=1)

print("\n--- 4. NIFTY 15m + BANK NIFTY 3m (Best Timeframe Combo, 1 Trade/Day Max) ---")
evaluate_portfolio(t_nifty_15m + t_bnf_3m, "Nifty 15m + BNF 3m (1 Trade/Day Max)", max_daily_losses=1, max_daily_trades=1)
