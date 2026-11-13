import sys
sys.path.append('engine')
import pandas as pd
import numpy as np
from super_alpha_portfolio import load_stock_data, get_nifty_trend_series, resample_and_calc_indicators, backtest_ema_atr_pullback, load_nifty_fast
from portfolio_synergy import load_bnf

nifty_1m = load_nifty_fast()
nifty_trend = get_nifty_trend_series(nifty_1m, tf_min=5)

def test_pair(s1, s2):
    d1 = load_bnf() if s1 == 'BANKNIFTY' else load_stock_data(s1)
    d2 = load_bnf() if s2 == 'BANKNIFTY' else load_stock_data(s2)
    
    t1 = backtest_ema_atr_pullback(resample_and_calc_indicators(d1, 5), nifty_trend, s1, target_rr=3.0)
    t2 = backtest_ema_atr_pullback(resample_and_calc_indicators(d2, 5), nifty_trend, s2, target_rr=3.0)
    
    df = pd.DataFrame(t1 + t2).sort_values(['Date', 'Time']).reset_index(drop=True)
    df['Date'] = pd.to_datetime(df['Date'])
    df['YM'] = df['Date'].dt.to_period('M')
    
    # 1. Independent
    tot_r = df['R'].sum()
    num_m = df['YM'].nunique()
    r_m = tot_r / num_m
    cum = df['R'].cumsum()
    max_dd = (cum - cum.cummax()).min()
    wr = (df['R'] > 0).mean() * 100
    pf = df[df['R'] > 0]['R'].sum() / abs(df[df['R'] < 0]['R'].sum())
    print(f"\n--- PAIR: {s1} + {s2} (Independent) ---")
    print(f"Trades: {len(df)} | WR: {wr:.1f}% | Monthly: {r_m:+.2f} R/mo | Max DD: {max_dd:.1f} R | PF: {pf:.2f}")
    
    # 2. Portfolio stop 1 loss/day
    filtered = []
    for dt, grp in df.groupby('Date'):
        dl = 0
        for idx, r in grp.iterrows():
            if dl >= 1: break
            filtered.append(r)
            if r['R'] < 0: dl += 1
    df_p = pd.DataFrame(filtered)
    tot_r_p = df_p['R'].sum()
    r_m_p = tot_r_p / num_m
    cum_p = df_p['R'].cumsum()
    max_dd_p = (cum_p - cum_p.cummax()).min()
    wr_p = (df_p['R'] > 0).mean() * 100
    pf_p = df_p[df_p['R'] > 0]['R'].sum() / abs(df_p[df_p['R'] < 0]['R'].sum())
    print(f"Max 1 Loss/Day => Trades: {len(df_p)} | WR: {wr_p:.1f}% | Monthly: {r_m_p:+.2f} R/mo | Max DD: {max_dd_p:.1f} R | PF: {pf_p:.2f}")

if __name__ == '__main__':
    test_pair('SUNPHARMA', 'RELIANCE')
    test_pair('SUNPHARMA', 'BANKNIFTY')
    test_pair('SUNPHARMA', 'TATAMOTORS')
