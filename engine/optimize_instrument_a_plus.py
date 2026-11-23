import pandas as pd
import numpy as np

df = pd.read_parquet('reports/rich_trades_features.parquet')
df['Win'] = df['R'] > 0

symbols = ['RELIANCE', 'MARUTI', 'SUNPHARMA', 'TATAMOTORS', 'TCS', 'TATASTEEL']

print("="*95)
print("EXPLORING A++ CONFLUENCE COMBINATIONS PER INSTRUMENT")
print("="*95)

results = []

for sym in symbols:
    sub = df[df['Symbol'] == sym].copy()
    base_n = len(sub)
    base_wr = sub['Win'].mean() * 100
    base_pf = sub[sub['R']>0]['R'].sum() / abs(sub[sub['R']<=0]['R'].sum())
    base_r = sub['R'].sum()
    
    print(f"\n>>> {sym} (Baseline: {base_n} trades, WR: {base_wr:.1f}%, PF: {base_pf:.2f}, Net: {base_r:.1f}R)")
    
    # We will test multiple confluence rules
    candidates = [
        ("Volume >= 1.2x", sub['VolRatio'] >= 1.2),
        ("Volume >= 1.5x", sub['VolRatio'] >= 1.5),
        ("Stacked EMAs + Vol >= 1.1x", (sub['StackedEMAs'] == True) & (sub['VolRatio'] >= 1.1)),
        ("VWAP Pinch + Vol >= 1.2x", (sub['PinchVWAP'] == True) & (sub['VolRatio'] >= 1.2)),
        ("Mid-Day / Afternoon Session", sub['TimeCat'].isin(['MID_DAY', 'AFTERNOON'])),
        ("Morning Prime + Vol >= 1.25x", (sub['TimeCat'] == 'MORNING_PRIME') & (sub['VolRatio'] >= 1.25)),
        ("Wick Rejection >= 35% + Vol >= 1.1x", (sub['WickRatio'] >= 0.35) & (sub['VolRatio'] >= 1.1)),
        ("Stacked EMAs + VWAP Pinch + Vol >= 1.0x", (sub['StackedEMAs'] == True) & (sub['PinchVWAP'] == True) & (sub['VolRatio'] >= 1.0)),
        ("Tight ATR SL (SL_Pct <= 0.45%)", sub['SL_Pct'] <= 0.45),
        ("Mid-Day + Stacked EMAs", (sub['TimeCat'] == 'MID_DAY') & (sub['StackedEMAs'] == True)),
        ("Mid-Day + Vol >= 1.0x", (sub['TimeCat'] == 'MID_DAY') & (sub['VolRatio'] >= 1.0)),
        ("Morning Prime + Stacked + Vol >= 1.2x", (sub['TimeCat'] == 'MORNING_PRIME') & (sub['StackedEMAs'] == True) & (sub['VolRatio'] >= 1.2)),
        ("Body Ratio >= 55% (Expansion Candle)", sub['BodyRatio'] >= 0.55),
        ("Body Ratio >= 55% + Vol >= 1.2x", (sub['BodyRatio'] >= 0.55) & (sub['VolRatio'] >= 1.2)),
        ("VWAP Pinch + Stacked + Wick >= 30%", (sub['PinchVWAP'] == True) & (sub['StackedEMAs'] == True) & (sub['WickRatio'] >= 0.30)),
        ("Wick >= 30% + Body >= 45% (Power Rejection)", (sub['WickRatio'] >= 0.30) & (sub['BodyRatio'] >= 0.45)),
    ]
    
    best_candidate = None
    best_score = 0
    
    for name, mask in candidates:
        m_sub = sub[mask]
        n_trades = len(m_sub)
        if n_trades < 50: continue # statistical validity threshold
        
        wr = m_sub['Win'].mean() * 100
        gw = m_sub[m_sub['R']>0]['R'].sum()
        gl = abs(m_sub[m_sub['R']<=0]['R'].sum())
        pf = gw / gl if gl > 0 else 99.0
        tot_r = m_sub['R'].sum()
        avg_r = m_sub['R'].mean()
        
        # Max DD
        daily_r = m_sub.groupby('Date')['R'].sum()
        cum_r = daily_r.cumsum()
        dd = (cum_r - cum_r.cummax()).min()
        
        score = wr * pf # composite quality score
        
        if score > best_score and wr > base_wr + 3.0:
            best_score = score
            best_candidate = {
                'Symbol': sym,
                'Setup_Name': name,
                'Trades': n_trades,
                'WinRate': round(wr, 2),
                'ProfitFactor': round(pf, 2),
                'Total_R': round(tot_r, 1),
                'Avg_R': round(avg_r, 3),
                'Max_DD': round(dd, 1),
                'Base_WR': round(base_wr, 2),
                'WR_Boost': round(wr - base_wr, 2)
            }
        
        print(f"  {name:42s}: {n_trades:4d} tr | WR: {wr:5.2f}% (+{wr-base_wr:4.1f}%) | PF: {pf:4.2f} | Net: {tot_r:6.1f}R | DD: {dd:5.1f}R")
    
    if best_candidate:
        results.append(best_candidate)

print("\n" + "="*95)
print("FINAL DISCOVERED A++ SETUPS PER INSTRUMENT")
print("="*95)
res_df = pd.DataFrame(results)
print(res_df.to_string(index=False))
