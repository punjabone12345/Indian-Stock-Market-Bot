import sys
sys.path.append('engine')
import pandas as pd
from optimal_combo_simulator import get_asset_trades
from drawdown_minimizer import backtest_drawdown_optimized, get_nifty_multi_tf_trend, resample_and_calc_indicators, load_stock_data
from nifty_alpha_explorer import load_nifty_fast
from portfolio_synergy import load_bnf

print("Loading data...")
nifty_1m = load_nifty_fast()
nifty_trends = get_nifty_multi_tf_trend(nifty_1m)

# 1. Nifty 15m IFVG (The lowest DD asset in existence, -11.6 R DD)
t_nifty_ifvg = get_asset_trades('NIFTY', nifty_1m, tf=15, target_rr=3.5, sl_mode='FORMATION_EXTREME')

# 2. Sun Pharma 5m EMA/ATR (Defensive pharma, -18.2 R DD)
sun_1m = load_stock_data('SUNPHARMA')
sun_5m = resample_and_calc_indicators(sun_1m, 5)
t_sun = backtest_drawdown_optimized(sun_5m, nifty_trends, 'SUNPHARMA', target_rr=3.0, use_macro_15m=True, skip_lunch=True, be_trigger_r=2.0)

# 3. Bank Nifty 5m EMA/ATR with BE trail
bnf_1m = load_bnf()
bnf_5m = resample_and_calc_indicators(bnf_1m, 5)
t_bnf = backtest_drawdown_optimized(bnf_5m, nifty_trends, 'BANKNIFTY', target_rr=3.0, use_macro_15m=True, skip_lunch=True, be_trigger_r=2.0)

# 4. Reliance 5m EMA/ATR with BE trail
rel_1m = load_stock_data('RELIANCE')
rel_5m = resample_and_calc_indicators(rel_1m, 5)
t_rel = backtest_drawdown_optimized(rel_5m, nifty_trends, 'RELIANCE', target_rr=3.0, use_macro_15m=True, skip_lunch=True, be_trigger_r=2.0)

def test_combo(trades_list, name, max_loss=1, max_trades=2):
    df = pd.DataFrame(trades_list).sort_values(['Date', 'Time']).reset_index(drop=True)
    df['Date'] = pd.to_datetime(df['Date'])
    df['YM'] = df['Date'].dt.to_period('M')
    num_m = df['YM'].nunique()
    
    filtered = []
    for dt, grp in df.groupby('Date'):
        dl, dt_c = 0, 0
        for idx, r in grp.iterrows():
            if dt_c >= max_trades or dl >= max_loss: break
            filtered.append(r)
            dt_c += 1
            if r['R'] < 0: dl += 1
            
    df_p = pd.DataFrame(filtered)
    tot_r = df_p['R'].sum()
    r_m = tot_r / num_m
    cum = df_p['R'].cumsum()
    max_dd = (cum - cum.cummax()).min()
    wr = (df_p['R'] > 0).mean() * 100
    pf = df_p[df_p['R'] > 0]['R'].sum() / abs(df_p[df_p['R'] < 0]['R'].sum())
    
    print("-" * 80)
    print(f"SETUP: {name}")
    print(f"Max Loss/Day: {max_loss} | Max Trades/Day: {max_trades}")
    print(f"Trades: {len(df_p)} | Win Rate: {wr:.1f}% | Profit Factor: {pf:.2f}")
    print(f"Monthly R: {r_m:+.2f} R / mo | Total R: {tot_r:+.1f} R | MAX DRAWDOWN: {max_dd:.1f} R")

# Format Nifty IFVG trades to match schema
for t in t_nifty_ifvg:
    t['Time'] = t['EntryTime']
    t['Symbol'] = 'NIFTY'

print("\n" + "="*80)
print("             DISCOVERING THE MINIMAL DRAWDOWN SETUP")
print("="*80)

# Combo 1: Nifty 15m IFVG + Sun Pharma 5m EMA/ATR
test_combo(t_nifty_ifvg + t_sun, "Nifty 15m IFVG + Sun Pharma 5m EMA (Ultra Conservative)", max_loss=1, max_trades=2)

# Combo 2: Sun Pharma + Bank Nifty + Reliance (Max 1 Loss/Day)
test_combo(t_sun + t_bnf + t_rel, "Triad: Sun Pharma + Bank Nifty + Reliance (Max 1 Loss)", max_loss=1, max_trades=2)

# Combo 3: Sun Pharma + Bank Nifty + Reliance (Max 1 Loss, 3 Trades)
test_combo(t_sun + t_bnf + t_rel, "Triad: Sun Pharma + Bank Nifty + Reliance (Max 1 Loss, 3 Trades)", max_loss=1, max_trades=3)

# Combo 4: Sun Pharma + Bank Nifty + Reliance (Max 2 Losses, 3 Trades)
test_combo(t_sun + t_bnf + t_rel, "Triad: Sun Pharma + Bank Nifty + Reliance (Max 2 Losses, 3 Trades)", max_loss=2, max_trades=3)
