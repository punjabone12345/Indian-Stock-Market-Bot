import sys
sys.path.append('engine')
import os
import pandas as pd
import numpy as np
from nifty_alpha_explorer import load_nifty_fast, resample_nifty, extract_all_daily_ifvgs
from portfolio_synergy import load_bnf
from asset_timeframe_matrix import load_stock_1m, resample_stock, audit_single_asset_timeframes

def get_full_breakdown():
    assets = {
        'NIFTY': load_nifty_fast(),
        'BANKNIFTY': load_bnf(),
        'LT': load_stock_1m('LT'),
        'SBIN': load_stock_1m('SBIN'),
        'HDFCBANK': load_stock_1m('HDFCBANK'),
        'TCS': load_stock_1m('TCS'),
        'BHARTIARTL': load_stock_1m('BHARTIARTL'),
        'ICICIBANK': load_stock_1m('ICICIBANK'),
        'RELIANCE': load_stock_1m('RELIANCE'),
    }

    all_rows = []
    for asset_name, df_1m in assets.items():
        if df_1m is None: continue
        res = audit_single_asset_timeframes(asset_name, df_1m)
        if len(res) == 0: continue
        
        # Get best per timeframe (1m, 2m, 3m, 5m, 15m)
        for tf in ['1m', '2m', '3m', '5m', '15m']:
            tf_data = res[res['TF'] == tf]
            if len(tf_data) > 0:
                best_tf = tf_data.sort_values('Total_R', ascending=False).iloc[0]
                all_rows.append({
                    'Asset': asset_name,
                    'TF': tf,
                    'RR': best_tf['RR'],
                    'SL_Mode': best_tf['SL'],
                    'Trades': best_tf['Trades'],
                    'WinRate': best_tf['WinRate'],
                    'Total_R': best_tf['Total_R'],
                    'Monthly_R': best_tf['Monthly_R'],
                    'Max_DD': best_tf['Max_DD'],
                    'PF': best_tf['PF']
                })
    
    df_all = pd.DataFrame(all_rows)
    df_all.to_csv('reports/all_assets_timeframe_comparison.csv', index=False)
    print(df_all.to_string(index=False))

if __name__ == '__main__':
    get_full_breakdown()
