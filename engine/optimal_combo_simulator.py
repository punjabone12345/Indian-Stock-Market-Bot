import sys
sys.path.append('engine')
import os
import pandas as pd
import numpy as np
import datetime
from datetime import time
from nifty_alpha_explorer import load_nifty_fast, resample_nifty, extract_all_daily_ifvgs
from portfolio_synergy import load_bnf
from asset_timeframe_matrix import load_stock_1m, resample_stock

def get_asset_trades(asset_name, df_1m, tf, target_rr, sl_mode):
    df_tf = resample_stock(df_1m, tf) if asset_name not in ['NIFTY', 'BANKNIFTY'] else resample_nifty(df_1m, tf)
    daily_signals = extract_all_daily_ifvgs(df_tf, tf)
    
    trades = []
    for dt, day_data in daily_signals.items():
        signals = day_data['signals']
        if not signals: continue
        highs, lows, closes, times, n = day_data['highs'], day_data['lows'], day_data['closes'], day_data['times'], day_data['n']
        
        day_t, day_l = 0, 0
        for sig in signals:
            if day_t >= 2 or day_l >= 1: break
            if sig['time'] >= time(14, 15): break
            
            entry = sig['entry']
            direction = sig['dir']
            
            if direction == 'BUY':
                raw_sl = sig['box_min'] - (entry * 0.0002) if sl_mode == 'FORMATION_EXTREME' else sig['trigger_low'] - (entry * 0.0002)
                sl_dist = max(entry - raw_sl, entry * 0.0020)
                sl = entry - sl_dist
                if sl_dist > entry * 0.0060: continue
                tp = entry + (sl_dist * target_rr)
                
                final_r = None
                exit_time = None
                for m in range(sig['bar'] + 1, n):
                    if lows[m] <= sl:
                        final_r = -1.04; exit_time = times[m]; break
                    if highs[m] >= tp:
                        final_r = round(target_rr - 0.04, 2); exit_time = times[m]; break
                    if times[m] >= time(15, 15):
                        final_r = round((closes[m] - entry)/sl_dist - 0.04, 2); exit_time = times[m]; break
                
                if final_r is not None:
                    trades.append({
                        'Date': dt,
                        'EntryTime': sig['time'],
                        'ExitTime': exit_time,
                        'Asset': asset_name,
                        'TF': f"{tf}m",
                        'Direction': direction,
                        'R': final_r
                    })
                    day_t += 1
                    if final_r < 0: day_l += 1

            elif direction == 'SELL':
                raw_sl = sig['box_max'] + (entry * 0.0002) if sl_mode == 'FORMATION_EXTREME' else sig['trigger_high'] + (entry * 0.0002)
                sl_dist = max(raw_sl - entry, entry * 0.0020)
                sl = entry + sl_dist
                if sl_dist > entry * 0.0060: continue
                tp = entry - (sl_dist * target_rr)
                
                final_r = None
                exit_time = None
                for m in range(sig['bar'] + 1, n):
                    if highs[m] >= sl:
                        final_r = -1.04; exit_time = times[m]; break
                    if lows[m] <= tp:
                        final_r = round(target_rr - 0.04, 2); exit_time = times[m]; break
                    if times[m] >= time(15, 15):
                        final_r = round((entry - closes[m])/sl_dist - 0.04, 2); exit_time = times[m]; break
                
                if final_r is not None:
                    trades.append({
                        'Date': dt,
                        'EntryTime': sig['time'],
                        'ExitTime': exit_time,
                        'Asset': asset_name,
                        'TF': f"{tf}m",
                        'Direction': direction,
                        'R': final_r
                    })
                    day_t += 1
                    if final_r < 0: day_l += 1
                    
    return trades

def evaluate_portfolio(trade_list, name, max_daily_losses=1, max_daily_trades=3):
    if not trade_list:
        print(f"No trades for {name}")
        return
        
    df = pd.DataFrame(trade_list)
    df['Date'] = pd.to_datetime(df['Date'])
    # Sort chronologically by Date and EntryTime
    df = df.sort_values(['Date', 'EntryTime']).reset_index(drop=True)
    
    # Portfolio level circuit breaker: max daily losses / trades across portfolio
    filtered_trades = []
    daily_groups = df.groupby('Date')
    
    for dt, group in daily_groups:
        d_losses = 0
        d_trades = 0
        for idx, row in group.iterrows():
            if d_trades >= max_daily_trades or d_losses >= max_daily_losses:
                break
            filtered_trades.append(row)
            d_trades += 1
            if row['R'] < 0:
                d_losses += 1
                
    df_p = pd.DataFrame(filtered_trades)
    df_p['YM'] = df_p['Date'].dt.to_period('M')
    
    tot_r = df_p['R'].sum()
    num_m = df_p['YM'].nunique()
    r_m = tot_r / num_m if num_m > 0 else 0
    cum = df_p['R'].cumsum()
    max_dd = (cum - cum.cummax()).min()
    wr = (df_p['R'] > 0).mean() * 100
    wins = df_p[df_p['R'] > 0]['R'].sum()
    losses = abs(df_p[df_p['R'] < 0]['R'].sum())
    pf = (wins / losses) if losses > 0 else 999.0
    
    print("-" * 80)
    print(f"PORTFOLIO CONFIGURATION: {name}")
    print(f"Max Daily Portfolio Losses Allowed: {max_daily_losses} | Max Daily Trades: {max_daily_trades}")
    print(f"Total Trades Taken: {len(df_p)} | Active Months: {num_m}")
    print(f"Win Rate: {wr:.1f}% | Profit Factor: {pf:.2f}")
    print(f"Total Cumulative Return: {tot_r:+.1f} R")
    print(f"Average Monthly Return:  {r_m:+.2f} R / Month")
    print(f"Maximum Drawdown:        {max_dd:.1f} R")
    calmar = (r_m * 12) / abs(max_dd) if max_dd < 0 else 0
    print(f"Calmar Ratio:            {calmar:.2f}")
    return df_p

def run_simulation():
    print("Loading data for simulation...")
    nifty_1m = load_nifty_fast()
    bnf_1m = load_bnf()
    lt_1m = load_stock_1m('LT')
    sbin_1m = load_stock_1m('SBIN')
    hdfc_1m = load_stock_1m('HDFCBANK')
    tcs_1m = load_stock_1m('TCS')
    bharti_1m = load_stock_1m('BHARTIARTL')

    print("\nExtracting trades per optimal timeframe...")
    # 1. Nifty 15m (Low DD champion)
    t_nifty_15m = get_asset_trades('NIFTY', nifty_1m, tf=15, target_rr=3.5, sl_mode='FORMATION_EXTREME')
    # 2. Nifty 2m (High Alpha)
    t_nifty_2m = get_asset_trades('NIFTY', nifty_1m, tf=2, target_rr=3.5, sl_mode='FORMATION_EXTREME')
    # 3. Bank Nifty 3m (Best overall)
    t_bnf_3m = get_asset_trades('BANKNIFTY', bnf_1m, tf=3, target_rr=3.5, sl_mode='TRIGGER_CANDLE')
    # 4. Bank Nifty 5m (Smoother)
    t_bnf_5m = get_asset_trades('BANKNIFTY', bnf_1m, tf=5, target_rr=3.0, sl_mode='TRIGGER_CANDLE')
    # 5. LT 3m (Low DD)
    t_lt_3m = get_asset_trades('LT', lt_1m, tf=3, target_rr=3.0, sl_mode='FORMATION_EXTREME')
    # 6. SBIN 1m (High PF, tiny DD)
    t_sbin_1m = get_asset_trades('SBIN', sbin_1m, tf=1, target_rr=3.5, sl_mode='FORMATION_EXTREME')
    # 7. HDFC Bank 2m (Low DD)
    t_hdfc_2m = get_asset_trades('HDFCBANK', hdfc_1m, tf=2, target_rr=2.0, sl_mode='TRIGGER_CANDLE')
    # 8. TCS 5m (Clean IT play)
    t_tcs_5m = get_asset_trades('TCS', tcs_1m, tf=5, target_rr=3.0, sl_mode='FORMATION_EXTREME')
    
    print("\n" + "="*80)
    print("                 PORTFOLIO COMBINATION BACKTEST RESULTS")
    print("="*80)
    
    # COMBO 1: Ultra Low-DD Core Index + Heavyweights (Nifty 15m + Bank Nifty 5m + SBIN 1m + HDFC 2m)
    combo1 = t_nifty_15m + t_bnf_5m + t_sbin_1m + t_hdfc_2m
    evaluate_portfolio(combo1, "Ultra Low-DD Core (Nifty 15m + BNF 5m + SBIN 1m + HDFC 2m)", max_daily_losses=1, max_daily_trades=2)
    
    # COMBO 2: Balanced Multi-Asset (Nifty 15m + BNF 3m + LT 3m + SBIN 1m + TCS 5m)
    combo2 = t_nifty_15m + t_bnf_3m + t_lt_3m + t_sbin_1m + t_tcs_5m
    evaluate_portfolio(combo2, "Balanced Multi-Timeframe Ensemble (Nifty 15m + BNF 3m + LT 3m + SBIN 1m + TCS 5m)", max_daily_losses=1, max_daily_trades=2)

    # COMBO 3: Balanced Multi-Asset with 2 Daily Trades Allowed
    evaluate_portfolio(combo2, "Balanced Ensemble (Allow 2 Losses Max)", max_daily_losses=2, max_daily_trades=3)

    # COMBO 4: High-Velocity Combo (Nifty 2m + BNF 3m + LT 3m + SBIN 1m)
    combo4 = t_nifty_2m + t_bnf_3m + t_lt_3m + t_sbin_1m
    evaluate_portfolio(combo4, "High Alpha Ensemble (Nifty 2m + BNF 3m + LT 3m + SBIN 1m)", max_daily_losses=1, max_daily_trades=2)

if __name__ == '__main__':
    run_simulation()
