import sys
sys.path.append('engine')
import pandas as pd
from drawdown_minimizer import backtest_drawdown_optimized, get_nifty_multi_tf_trend, resample_and_calc_indicators, load_stock_data
from nifty_alpha_explorer import load_nifty_fast
from portfolio_synergy import load_bnf

nifty_1m = load_nifty_fast()
nifty_trends = get_nifty_multi_tf_trend(nifty_1m)

def get_trades(s):
    d = load_bnf() if s == 'BANKNIFTY' else load_stock_data(s)
    df_5m = resample_and_calc_indicators(d, 5)
    return backtest_drawdown_optimized(df_5m, nifty_trends, s, target_rr=3.0, use_macro_15m=True, skip_lunch=True, be_trigger_r=2.0)

t_sun = get_trades('SUNPHARMA')
t_bnf = get_trades('BANKNIFTY')
t_rel = get_trades('RELIANCE')
t_tm = get_trades('TATAMOTORS')
t_mar = get_trades('MARUTI')

quad = t_sun + t_bnf + t_rel + t_tm
pent = t_sun + t_bnf + t_rel + t_tm + t_mar

def evaluate_circuit(t_list, name, max_loss=1, max_trades=3):
    df = pd.DataFrame(t_list).sort_values(['Date', 'Time']).reset_index(drop=True)
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
    calmar = (r_m * 12) / abs(max_dd)
    
    print("-" * 80)
    print(f"SETUP: {name} (Max Loss: {max_loss}, Max Trades: {max_trades})")
    print(f"Trades: {len(df_p)} | Win Rate: {wr:.1f}% | Profit Factor: {pf:.2f}")
    print(f"MONTHLY RETURN: {r_m:+.2f} R / mo | TOTAL RETURN: {tot_r:+.1f} R | MAX DRAWDOWN: {max_dd:.1f} R | Calmar: {calmar:.2f}")

evaluate_circuit(quad, "Quad Core (Sun + BNF + Rel + TataMotors)", max_loss=1, max_trades=2)
evaluate_circuit(quad, "Quad Core (Sun + BNF + Rel + TataMotors)", max_loss=1, max_trades=3)
evaluate_circuit(quad, "Quad Core (Sun + BNF + Rel + TataMotors)", max_loss=1, max_trades=4)
evaluate_circuit(quad, "Quad Core (Sun + BNF + Rel + TataMotors)", max_loss=2, max_trades=4)
evaluate_circuit(pent, "5-Star Core (Sun + BNF + Rel + TM + Maruti)", max_loss=1, max_trades=3)
evaluate_circuit(pent, "5-Star Core (Sun + BNF + Rel + TM + Maruti)", max_loss=2, max_trades=4)
