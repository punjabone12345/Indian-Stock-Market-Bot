import sys
sys.path.append('engine')
import os
import glob
import pandas as pd
import numpy as np
import datetime
from datetime import time
from nifty_alpha_explorer import load_nifty_fast, resample_nifty, extract_all_daily_ifvgs
from portfolio_synergy import load_bnf

def resample_stock(df_1m, tf_min):
    if tf_min == 1:
        df = df_1m.copy()
    else:
        df = df_1m.set_index('Timestamp').resample(f'{tf_min}min', origin='start_day', offset='15min').agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum' if 'Volume' in df_1m.columns else 'count'
        }).dropna().reset_index()

    df['Date'] = df['Timestamp'].dt.date
    df['Time'] = df['Timestamp'].dt.time
    df['Typ'] = (df['High'] + df['Low'] + df['Close']) / 3.0
    vol = df['Volume'].values
    if np.sum(vol) == 0 or np.all(vol == 1):
        df['VWAP'] = df.groupby('Date')['Close'].transform(lambda x: x.expanding().mean())
    else:
        df['PV'] = df['Typ'] * df['Volume']
        df['CumPV'] = df.groupby('Date')['PV'].cumsum()
        df['CumV'] = df.groupby('Date')['Volume'].cumsum()
        df['VWAP'] = df['CumPV'] / df['CumV']

    daily = df.groupby('Date').agg({'High': 'max', 'Low': 'min', 'Close': 'last'}).shift(1)
    df['PDH'] = df['Date'].map(daily['High'])
    df['PDL'] = df['Date'].map(daily['Low'])
    df['PDC'] = df['Date'].map(daily['Close'])
    return df

def load_stock_1m(symbol):
    f_prev = f'data/stocks/{symbol}_prev.parquet'
    f_2026 = f'data/stocks/{symbol}_2026.parquet'
    dfs = []
    if os.path.exists(f_prev):
        d1 = pd.read_parquet(f_prev)
        d1['Timestamp'] = pd.to_datetime(d1['Date'])
        d1 = d1[d1['Timestamp'] >= '2022-10-01']
        dfs.append(d1[['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']])
    if os.path.exists(f_2026):
        d2 = pd.read_parquet(f_2026)
        d2['Timestamp'] = pd.to_datetime(d2['Date'])
        dfs.append(d2[['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']])
    if not dfs: return None
    df = pd.concat(dfs).sort_values('Timestamp').drop_duplicates('Timestamp').reset_index(drop=True)
    df['Time'] = df['Timestamp'].dt.time
    df = df[(df['Time'] >= time(9, 15)) & (df['Time'] <= time(15, 29))].copy()
    return df

def audit_single_asset_timeframes(asset_name, df_1m):
    timeframes = [1, 2, 3, 5, 15]
    best_results = []

    for tf in timeframes:
        df_tf = resample_stock(df_1m, tf) if asset_name not in ['NIFTY', 'BANKNIFTY'] else resample_nifty(df_1m, tf)
        daily_signals = extract_all_daily_ifvgs(df_tf, tf)

        for target_rr in [2.0, 2.5, 3.0, 3.5]:
            for sl_mode in ['FORMATION_EXTREME', 'TRIGGER_CANDLE']:
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
                            for m in range(sig['bar'] + 1, n):
                                if lows[m] <= sl: final_r = -1.04; break
                                if highs[m] >= tp: final_r = round(target_rr - 0.04, 2); break
                                if times[m] >= time(15, 15): final_r = round((closes[m] - entry)/sl_dist - 0.04, 2); break

                            if final_r is not None:
                                trades.append({'Date': dt, 'R': final_r})
                                day_t += 1
                                if final_r < 0: day_l += 1

                        elif direction == 'SELL':
                            raw_sl = sig['box_max'] + (entry * 0.0002) if sl_mode == 'FORMATION_EXTREME' else sig['trigger_high'] + (entry * 0.0002)
                            sl_dist = max(raw_sl - entry, entry * 0.0020)
                            sl = entry + sl_dist
                            if sl_dist > entry * 0.0060: continue
                            tp = entry - (sl_dist * target_rr)

                            final_r = None
                            for m in range(sig['bar'] + 1, n):
                                if highs[m] >= sl: final_r = -1.04; break
                                if lows[m] <= tp: final_r = round(target_rr - 0.04, 2); break
                                if times[m] >= time(15, 15): final_r = round((entry - closes[m])/sl_dist - 0.04, 2); break

                            if final_r is not None:
                                trades.append({'Date': dt, 'R': final_r})
                                day_t += 1
                                if final_r < 0: day_l += 1

                if len(trades) < 40: continue
                df_t = pd.DataFrame(trades).sort_values('Date').reset_index(drop=True)
                df_t['Date'] = pd.to_datetime(df_t['Date'])
                df_t['YM'] = df_t['Date'].dt.to_period('M')

                tot_r = df_t['R'].sum()
                num_m = df_t['YM'].nunique()
                r_m = tot_r / num_m if num_m > 0 else 0
                cum = df_t['R'].cumsum()
                max_dd = (cum - cum.cummax()).min()
                wr = (df_t['R'] > 0).mean() * 100
                wins = df_t[df_t['R'] > 0]['R'].sum()
                losses = abs(df_t[df_t['R'] < 0]['R'].sum())
                pf = (wins / losses) if losses > 0 else 999.0

                best_results.append({
                    'Asset': asset_name,
                    'TF': f"{tf}m",
                    'RR': f"1:{target_rr}",
                    'SL': sl_mode,
                    'Trades': len(df_t),
                    'WinRate': round(wr, 1),
                    'Total_R': round(tot_r, 1),
                    'Monthly_R': round(r_m, 2),
                    'Max_DD': round(max_dd, 1),
                    'PF': round(pf, 2),
                    'trades_list': trades
                })

    if not best_results:
        return pd.DataFrame()
    df_out = pd.DataFrame(best_results).sort_values('Total_R', ascending=False)
    return df_out

def run_matrix_optimization():
    print("="*85)
    print("   SWEEPING EVERY ASSET ON MULTIPLE TIMEFRAMES (1m, 2m, 3m, 5m, 15m)")
    print("   Enforcing Minimum SL = 0.20% | Real Friction Deducted")
    print("="*85)

    # Assets to test
    asset_dfs = {}
    print("Loading Nifty 50...")
    asset_dfs['NIFTY'] = load_nifty_fast()

    print("Loading Bank Nifty...")
    asset_dfs['BANKNIFTY'] = load_bnf()

    stocks_to_test = ['RELIANCE', 'HDFCBANK', 'ICICIBANK', 'TCS', 'INFY', 'BHARTIARTL', 'SBIN', 'LT', 'TATASTEEL']
    for s in stocks_to_test:
        print(f"Loading {s}...")
        asset_dfs[s] = load_stock_1m(s)

    # Audit each asset and record the best configuration
    asset_best_configs = []
    asset_trade_streams = {}

    for asset_name, df_1m in asset_dfs.items():
        if df_1m is None: continue
        print(f"\nAnalyzing {asset_name} on 1m, 2m, 3m, 5m, 15m...")
        df_ranked = audit_single_asset_timeframes(asset_name, df_1m)
        if len(df_ranked) == 0: continue

        # Best overall configuration for this asset
        best = df_ranked.iloc[0]
        # Also find lowest drawdown configuration that is profitable
        profitable = df_ranked[df_ranked['Total_R'] > 20]
        best_low_dd = profitable.sort_values('Max_DD', ascending=False).iloc[0] if len(profitable) > 0 else best

        asset_best_configs.append({
            'Asset': asset_name,
            'Best_TF': best['TF'],
            'Best_RR': best['RR'],
            'Best_SL': best['SL'][:7],
            'Trades': best['Trades'],
            'WinRate': best['WinRate'],
            'Total_R': best['Total_R'],
            'Monthly_R': best['Monthly_R'],
            'Max_DD': best['Max_DD'],
            'PF': best['PF'],
            'LowDD_TF': best_low_dd['TF'],
            'LowDD_MaxDD': best_low_dd['Max_DD'],
            'LowDD_TotalR': best_low_dd['Total_R'],
            'LowDD_PF': best_low_dd['PF']
        })
        asset_trade_streams[asset_name] = best['trades_list']

    df_summary = pd.DataFrame(asset_best_configs).sort_values('Total_R', ascending=False)
    print("\n" + "="*85)
    print("         OPTIMAL TIMEFRAME & PARAMETERS DISCOVERED FOR EACH ASSET")
    print("="*85)
    print(df_summary[['Asset', 'Best_TF', 'Best_RR', 'Best_SL', 'Trades', 'WinRate', 'Total_R', 'Monthly_R', 'Max_DD', 'PF']].to_string(index=False))

    print("\n" + "="*85)
    print("         LOWEST-DRAWDOWN TIMEFRAME DISCOVERED FOR EACH ASSET")
    print("="*85)
    print(df_summary[['Asset', 'LowDD_TF', 'LowDD_TotalR', 'LowDD_MaxDD', 'LowDD_PF']].to_string(index=False))

    os.makedirs('reports', exist_ok=True)
    df_summary.to_csv('reports/asset_optimal_timeframes.csv', index=False)

if __name__ == '__main__':
    run_matrix_optimization()
