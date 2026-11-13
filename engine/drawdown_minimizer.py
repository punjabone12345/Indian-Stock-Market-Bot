import sys
sys.path.append('engine')
import os
import pandas as pd
import numpy as np
import datetime
from datetime import time
from nifty_alpha_explorer import load_nifty_fast, resample_nifty
from portfolio_synergy import load_bnf
from nifty_aligned_ema_atr_sweep import load_stock_data, resample_and_calc_indicators

def get_nifty_multi_tf_trend(nifty_1m):
    # 15m Nifty Trend for Macro Filter (Strongest noise suppression)
    df_15m = resample_nifty(nifty_1m, 15)
    df_15m['EMA9'] = df_15m.groupby('Date')['Close'].transform(lambda x: x.ewm(span=9, adjust=False).mean())
    df_15m['EMA21'] = df_15m.groupby('Date')['Close'].transform(lambda x: x.ewm(span=21, adjust=False).mean())
    df_15m['Nifty_Macro'] = 0
    df_15m.loc[(df_15m['Close'] > df_15m['EMA21']) & (df_15m['EMA9'] > df_15m['EMA21']), 'Nifty_Macro'] = 1
    df_15m.loc[(df_15m['Close'] < df_15m['EMA21']) & (df_15m['EMA9'] < df_15m['EMA21']), 'Nifty_Macro'] = -1
    
    # 5m Nifty Trend
    df_5m = resample_nifty(nifty_1m, 5)
    df_5m['EMA9'] = df_5m.groupby('Date')['Close'].transform(lambda x: x.ewm(span=9, adjust=False).mean())
    df_5m['EMA21'] = df_5m.groupby('Date')['Close'].transform(lambda x: x.ewm(span=21, adjust=False).mean())
    df_5m['Nifty_5m'] = 0
    df_5m.loc[(df_5m['Close'] > df_5m['EMA21']) & (df_5m['EMA9'] > df_5m['EMA21']), 'Nifty_5m'] = 1
    df_5m.loc[(df_5m['Close'] < df_5m['EMA21']) & (df_5m['EMA9'] < df_5m['EMA21']), 'Nifty_5m'] = -1

    # Merge onto 5m index
    df_15m_res = df_15m[['Timestamp', 'Nifty_Macro']].set_index('Timestamp')
    df_5m = df_5m.join(df_15m_res, on='Timestamp')
    df_5m['Nifty_Macro'] = df_5m['Nifty_Macro'].ffill().fillna(0).astype(int)
    return df_5m[['Timestamp', 'Nifty_5m', 'Nifty_Macro']].set_index('Timestamp')

def backtest_drawdown_optimized(df_stock, nifty_trends, symbol, 
                                target_rr=3.0, 
                                use_macro_15m=True, 
                                skip_lunch=True,
                                be_trigger_r=1.5,
                                max_daily_stock_losses=1):
    df_stock = df_stock.copy()
    df_stock['Nifty_5m'] = df_stock['Timestamp'].map(nifty_trends['Nifty_5m']).fillna(0).astype(int)
    df_stock['Nifty_Macro'] = df_stock['Timestamp'].map(nifty_trends['Nifty_Macro']).fillna(0).astype(int)
    
    trades = []
    daily_groups = df_stock.groupby('Date')
    
    for dt, day_df in daily_groups:
        n = len(day_df)
        if n < 10: continue
        
        opens = day_df['Open'].values
        highs = day_df['High'].values
        lows = day_df['Low'].values
        closes = day_df['Close'].values
        times = day_df['Time'].values
        ema9 = day_df['EMA9'].values
        ema21 = day_df['EMA21'].values
        vwap = day_df['VWAP'].values
        atr = day_df['ATR'].values
        n_5m = day_df['Nifty_5m'].values
        n_macro = day_df['Nifty_Macro'].values
        
        day_t, day_l = 0, 0
        
        for i in range(2, n - 2):
            if day_t >= 2 or day_l >= max_daily_stock_losses: break
            
            t_now = times[i]
            # Time filter: Best intraday momentum windows (9:30 to 11:30 and 13:30 to 14:30)
            if t_now < time(9, 30) or t_now > time(14, 15): continue
            if skip_lunch and (time(11, 30) <= t_now < time(13, 15)): continue
            
            # Trend filter
            n_bull = (n_macro[i] == 1) if use_macro_15m else (n_5m[i] == 1)
            n_bear = (n_macro[i] == -1) if use_macro_15m else (n_5m[i] == -1)
            
            # --- BUY SETUP ---
            if (n_bull and closes[i] > vwap[i] and ema9[i] > ema21[i] and 
                (lows[i] <= ema9[i] or lows[i-1] <= ema9[i-1]) and 
                closes[i] > opens[i] and closes[i] > ema9[i]):
                
                entry = closes[i]
                raw_sl = min(lows[i], lows[i-1]) - (0.2 * atr[i])
                sl_dist = max(entry - raw_sl, entry * 0.0020)
                sl = entry - sl_dist
                if sl_dist > entry * 0.0070: continue
                tp = entry + (sl_dist * target_rr)
                be_price = entry + (sl_dist * be_trigger_r) if be_trigger_r else None
                
                final_r = None
                current_sl = sl
                for m in range(i + 1, n):
                    # Check breakeven trail
                    if be_price and highs[m] >= be_price:
                        current_sl = max(current_sl, entry + (sl_dist * 0.1)) # Trail to small profit/cover fees
                        
                    if lows[m] <= current_sl:
                        if current_sl > sl:
                            final_r = 0.06 # Breakeven exit (+friction covered)
                        else:
                            final_r = -1.04 # Loss
                        break
                    if highs[m] >= tp:
                        final_r = round(target_rr - 0.04, 2); break
                    if times[m] >= time(15, 15):
                        final_r = round((closes[m] - entry)/sl_dist - 0.04, 2); break
                        
                if final_r is not None:
                    trades.append({'Date': dt, 'Time': times[i], 'Symbol': symbol, 'Dir': 'BUY', 'R': final_r})
                    day_t += 1
                    if final_r < 0: day_l += 1

            # --- SELL SETUP ---
            elif (n_bear and closes[i] < vwap[i] and ema9[i] < ema21[i] and 
                  (highs[i] >= ema9[i] or highs[i-1] >= ema9[i-1]) and 
                  closes[i] < opens[i] and closes[i] < ema9[i]):
                
                entry = closes[i]
                raw_sl = max(highs[i], highs[i-1]) + (0.2 * atr[i])
                sl_dist = max(raw_sl - entry, entry * 0.0020)
                sl = entry + sl_dist
                if sl_dist > entry * 0.0070: continue
                tp = entry - (sl_dist * target_rr)
                be_price = entry - (sl_dist * be_trigger_r) if be_trigger_r else None
                
                final_r = None
                current_sl = sl
                for m in range(i + 1, n):
                    if be_price and lows[m] <= be_price:
                        current_sl = min(current_sl, entry - (sl_dist * 0.1))
                        
                    if highs[m] >= current_sl:
                        if current_sl < sl:
                            final_r = 0.06
                        else:
                            final_r = -1.04
                        break
                    if lows[m] <= tp:
                        final_r = round(target_rr - 0.04, 2); break
                    if times[m] >= time(15, 15):
                        final_r = round((entry - closes[m])/sl_dist - 0.04, 2); break
                        
                if final_r is not None:
                    trades.append({'Date': dt, 'Time': times[i], 'Symbol': symbol, 'Dir': 'SELL', 'R': final_r})
                    day_t += 1
                    if final_r < 0: day_l += 1
                    
    return trades

def run_drawdown_optimization_experiments():
    print("="*85)
    print("   QUANTITATIVE DRAWDOWN MINIMIZATION EXPERIMENTS")
    print("   Testing: 15m Macro Filter, Lunch-Hour Filter, Breakeven Trailing, Portfolio Stops")
    print("="*85)
    
    print("Loading Nifty 50...")
    nifty_1m = load_nifty_fast()
    nifty_trends = get_nifty_multi_tf_trend(nifty_1m)
    
    basket = ['RELIANCE', 'SUNPHARMA', 'BANKNIFTY', 'TATAMOTORS', 'MARUTI', 'TCS']
    data_dict = {}
    for s in basket:
        print(f"Loading {s}...")
        df_1m = load_bnf() if s == 'BANKNIFTY' else load_stock_data(s)
        data_dict[s] = resample_and_calc_indicators(df_1m, 5)

    print("\n" + "="*85)
    print("EXPERIMENT 1: EFFECT OF BREAKEVEN TRAILING & LUNCH-HOUR CHOP FILTER")
    print("="*85)
    
    for be_val in [None, 1.5, 2.0]:
        for skip_l in [False, True]:
            all_t = []
            for s in ['RELIANCE', 'SUNPHARMA', 'BANKNIFTY']:
                t = backtest_drawdown_optimized(data_dict[s], nifty_trends, s, target_rr=3.0, 
                                                use_macro_15m=True, skip_lunch=skip_l, be_trigger_r=be_val)
                all_t.extend(t)
                
            df = pd.DataFrame(all_t).sort_values(['Date', 'Time']).reset_index(drop=True)
            df['Date'] = pd.to_datetime(df['Date'])
            df['YM'] = df['Date'].dt.to_period('M')
            tot_r = df['R'].sum()
            num_m = df['YM'].nunique()
            r_m = tot_r / num_m
            cum = df['R'].cumsum()
            max_dd = (cum - cum.cummax()).min()
            wr = (df['R'] > 0).mean() * 100
            wins = df[df['R'] > 0]['R'].sum()
            losses = abs(df[df['R'] < 0]['R'].sum())
            pf = wins / losses if losses > 0 else 999.0
            
            be_str = f"BE @ {be_val}R" if be_val else "No BE"
            lunch_str = "Skip Lunch (11:30-13:15)" if skip_l else "All Day"
            print(f"{be_str:12s} | {lunch_str:25s} => Monthly: {r_m:+.2f} R/mo | Max DD: {max_dd:.1f} R | PF: {pf:.2f} | WR: {wr:.1f}%")

    print("\n" + "="*85)
    print("EXPERIMENT 2: ULTRA LOW-DRAWDOWN ENSEMBLE WITH PORTFOLIO CIRCUIT BREAKER")
    print("="*85)
    
    # Test best config with strict portfolio stop
    for max_pf_loss in [1, 2]:
        for s_list in [['RELIANCE', 'SUNPHARMA'], 
                       ['SUNPHARMA', 'BANKNIFTY'], 
                       ['RELIANCE', 'SUNPHARMA', 'BANKNIFTY'],
                       ['RELIANCE', 'SUNPHARMA', 'TATAMOTORS', 'MARUTI']]:
            all_t = []
            for s in s_list:
                t = backtest_drawdown_optimized(data_dict[s], nifty_trends, s, target_rr=3.0, 
                                                use_macro_15m=True, skip_lunch=True, be_trigger_r=1.5)
                all_t.extend(t)
            
            df = pd.DataFrame(all_t).sort_values(['Date', 'Time']).reset_index(drop=True)
            df['Date'] = pd.to_datetime(df['Date'])
            df['YM'] = df['Date'].dt.to_period('M')
            num_m = df['YM'].nunique()
            
            # Apply Portfolio Daily Loss Stop
            filtered = []
            for dt, grp in df.groupby('Date'):
                dl = 0
                for idx, r in grp.iterrows():
                    if dl >= max_pf_loss: break
                    filtered.append(r)
                    if r['R'] < 0: dl += 1
            df_p = pd.DataFrame(filtered)
            tot_r = df_p['R'].sum()
            r_m = tot_r / num_m
            cum = df_p['R'].cumsum()
            max_dd = (cum - cum.cummax()).min()
            wr = (df_p['R'] > 0).mean() * 100
            wins = df_p[df_p['R'] > 0]['R'].sum()
            losses = abs(df_p[df_p['R'] < 0]['R'].sum())
            pf = wins / losses if losses > 0 else 999.0
            
            assets_str = "+".join(s_list)
            print(f"Max Loss/Day: {max_pf_loss} | Assets: {assets_str:35s} => Monthly: {r_m:+.2f} R/mo | Max DD: {max_dd:.1f} R | PF: {pf:.2f} | Trades: {len(df_p)}")

if __name__ == '__main__':
    run_drawdown_optimization_experiments()
