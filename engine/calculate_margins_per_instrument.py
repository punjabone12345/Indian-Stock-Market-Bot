import pandas as pd

df = pd.read_csv('reports/option_c_full_trades.csv')

print("="*85)
print("MARGIN REQUIREMENT CALCULATIONS PER INSTRUMENT (OPTION C)")
print("="*85)

results = []
for sym, grp in df.groupby('Symbol'):
    avg_price = grp['EntryPrice'].mean()
    avg_sl_pct = grp['SL_Pct'].mean() / 100.0
    avg_sl_pts = grp['SL_Dist'].mean()
    min_sl_pct = grp['SL_Pct'].min() / 100.0
    max_sl_pct = grp['SL_Pct'].max() / 100.0
    
    # Sizing for 1R = 1,000 INR
    risk_1000 = 1000.0
    qty_1000 = int(risk_1000 / avg_sl_pts)
    pos_val_1000 = qty_1000 * avg_price
    # Equity MIS is 5x leverage (20% margin), Bank Nifty Futures is SPAN+Exposure (~50k per lot)
    if sym == 'BANKNIFTY':
        margin_1000 = 50000.0 # Standard 1 lot BNF MIS Futures
        margin_500 = 50000.0
        qty_500 = 15 # 1 lot minimum
        pos_val_500 = 15 * avg_price
    else:
        margin_1000 = pos_val_1000 * 0.20 # 5x leverage (20%)
        risk_500 = 500.0
        qty_500 = int(risk_500 / avg_sl_pts)
        pos_val_500 = qty_500 * avg_price
        margin_500 = pos_val_500 * 0.20

    results.append({
        'Symbol': sym,
        'Avg_Price': round(avg_price, 1),
        'Avg_SL_Pct': f"{avg_sl_pct*100:.2f}%",
        'Avg_SL_Points': round(avg_sl_pts, 2),
        'Qty_1R_1000': qty_1000,
        'Pos_Value_1000': round(pos_val_1000, 0),
        'Margin_1R_1000': round(margin_1000, 0),
        'Qty_1R_500': qty_500,
        'Pos_Value_500': round(pos_val_500, 0),
        'Margin_1R_500': round(margin_500, 0)
    })

df_res = pd.DataFrame(results)
print(df_res.to_string(index=False))
