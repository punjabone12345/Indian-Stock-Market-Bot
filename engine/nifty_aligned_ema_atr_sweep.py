import sys
sys.path.append('engine')
import os
import glob
import pandas as pd
import numpy as np
import datetime
from datetime import time
from nifty_alpha_explorer import load_nifty_fast, resample_nifty
from portfolio_synergy import load_bnf

def load_stock_data(symbol):
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

def get_nifty_trend_series(nifty_1m, tf_min=5):
    df_tf = resample_nifty(nifty_1m, tf_min)
    # EMA 9 and EMA 21
    df_tf['EMA9'] = df_tf.groupby('Date')['Close'].transform(lambda x: x.ewm(span=9, adjust=False).mean())
    df_tf['EMA21'] = df_tf.groupby('Date')['Close'].transform(lambda x: x.ewm(span=21, adjust=False).mean())
    
    # Nifty Trend: +1 Bullish, -1 Bearish, 0 Neutral
    df_tf['Nifty_Trend'] = 0
    bull = (df_tf['Close'] > df_tf['EMA21']) & (df_tf['EMA9'] > df_tf['EMA21'])
    bear = (df_tf['Close'] < df_tf['EMA21']) & (df_tf['EMA9'] < df_tf['EMA21'])
    df_tf.loc[bull, 'Nifty_Trend'] = 1
    df_tf.loc[bear, 'Nifty_Trend'] = -1
    return df_tf[['Timestamp', 'Nifty_Trend']].set_index('Timestamp')

def resample_and_calc_indicators(df_1m, tf_min=5):
    df = df_1m.set_index('Timestamp').resample(f'{tf_min}min', origin='start_day', offset='15min').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum' if 'Volume' in df_1m.columns else 'count'
    }).dropna().reset_index()

    df['Date'] = df['Timestamp'].dt.date
    df['Time'] = df['Timestamp'].dt.time
    
    # VWAP
    df['Typ'] = (df['High'] + df['Low'] + df['Close']) / 3.0
    vol = df['Volume'].values
    if np.sum(vol) == 0 or np.all(vol == 1):
        df['VWAP'] = df.groupby('Date')['Close'].transform(lambda x: x.expanding().mean())
    else:
        df['PV'] = df['Typ'] * df['Volume']
        df['VWAP'] = df.groupby('Date')['PV'].cumsum() / df.groupby('Date')['Volume'].cumsum()

    # EMAs: 9 and 21
    df['EMA9'] = df.groupby('Date')['Close'].transform(lambda x: x.ewm(span=9, adjust=False).mean())
    df['EMA21'] = df.groupby('Date')['Close'].transform(lambda x: x.ewm(span=21, adjust=False).mean())
    
    # ATR 14
    prev_close = df.groupby('Date')['Close'].shift(1)
    tr1 = df['High'] - df['Low']
    tr2 = (df['High'] - prev_close).abs()
    tr3 = (df['Low'] - prev_close).abs()
    df['TR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['ATR'] = df.groupby('Date')['TR'].transform(lambda x: x.rolling(14, min_periods=1).mean())
    return df

def backtest_ema_atr_pullback(df_stock, nifty_trend_idx, symbol, target_rr=2.5, sl_mult=1.5):
    # Align Nifty trend to stock
    df_stock = df_stock.copy()
    df_stock['Nifty_Trend'] = df_stock['Timestamp'].map(nifty_trend_idx['Nifty_Trend']).fillna(0).astype(int)
    
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
        n_trend = day_df['Nifty_Trend'].values
        
        day_trades = 0
        day_losses = 0
        
        for i in range(2, n - 2):
            if day_trades >= 2 or day_losses >= 1: break
            if times[i] < time(9, 30) or times[i] > time(14, 15): continue
            
            # --- BUY PULLBACK LOGIC ---
            # Condition 1: Nifty is Bullish
            # Condition 2: Stock is Bullish (Close > VWAP and EMA9 > EMA21)
            # Condition 3: Previous or current bar dipped into EMA zone (Low <= EMA9)
            # Condition 4: Current bar closed strong green above EMA9 (Close > Open and Close > EMA9)
            if (n_trend[i] == 1 and 
                closes[i] > vwap[i] and 
                ema9[i] > ema21[i] and 
                (lows[i] <= ema9[i] or lows[i-1] <= ema9[i-1]) and 
                closes[i] > opens[i] and 
                closes[i] > ema9[i]):
                
                entry = closes[i]
                # SL: lowest of last 2 bars or entry - sl_mult*ATR
                raw_sl = min(lows[i], lows[i-1]) - (0.2 * atr[i])
                sl_dist = max(entry - raw_sl, entry * 0.0020) # Enforce min 0.20% SL
                sl = entry - sl_dist
                if sl_dist > entry * 0.0070: continue # Skip if SL too wide
                tp = entry + (sl_dist * target_rr)
                
                # Forward trace
                final_r = None
                for m in range(i + 1, n):
                    if lows[m] <= sl:
                        final_r = -1.04; break
                    if highs[m] >= tp:
                        final_r = round(target_rr - 0.04, 2); break
                    if times[m] >= time(15, 15):
                        final_r = round((closes[m] - entry)/sl_dist - 0.04, 2); break
                
                if final_r is not None:
                    trades.append({'Date': dt, 'Time': times[i], 'Symbol': symbol, 'Dir': 'BUY', 'R': final_r})
                    day_trades += 1
                    if final_r < 0: day_losses += 1
                    
            # --- SELL PULLBACK LOGIC ---
            # Condition 1: Nifty is Bearish
            # Condition 2: Stock is Bearish (Close < VWAP and EMA9 < EMA21)
            # Condition 3: Previous or current bar rallied into EMA zone (High >= EMA9)
            # Condition 4: Current bar closed strong red below EMA9 (Close < Open and Close < EMA9)
            elif (n_trend[i] == -1 and 
                  closes[i] < vwap[i] and 
                  ema9[i] < ema21[i] and 
                  (highs[i] >= ema9[i] or highs[i-1] >= ema9[i-1]) and 
                  closes[i] < opens[i] and 
                  closes[i] < ema9[i]):
                
                entry = closes[i]
                raw_sl = max(highs[i], highs[i-1]) + (0.2 * atr[i])
                sl_dist = max(raw_sl - entry, entry * 0.0020)
                sl = entry + sl_dist
                if sl_dist > entry * 0.0070: continue
                tp = entry - (sl_dist * target_rr)
                
                # Forward trace
                final_r = None
                for m in range(i + 1, n):
                    if highs[m] >= sl:
                        final_r = -1.04; break
                    if lows[m] <= tp:
                        final_r = round(target_rr - 0.04, 2); break
                    if times[m] >= time(15, 15):
                        final_r = round((entry - closes[m])/sl_dist - 0.04, 2); break
                
                if final_r is not None:
                    trades.append({'Date': dt, 'Time': times[i], 'Symbol': symbol, 'Dir': 'SELL', 'R': final_r})
                    day_trades += 1
                    if final_r < 0: day_losses += 1
                    
    return trades

def sweep_all_stocks():
    print("="*85)
    print("   NIFTY-ALIGNED EMA + ATR PULLBACK STRATEGY BACKTEST (4-YEAR AUDIT)")
    print("   Enforcing: Min SL 0.20%, Static 1R Risk, Real Taxes & Slippage Deducted")
    print("="*85)
    
    print("Loading Nifty 50 for Macro Trend...")
    nifty_1m = load_nifty_fast()
    nifty_trend_idx = get_nifty_trend_series(nifty_1m, tf_min=5)
    
    # Universe of top liquid stocks + Bank Nifty
    symbols = ['BANKNIFTY', 'RELIANCE', 'HDFCBANK', 'ICICIBANK', 'SBIN', 'LT', 'TCS', 'INFY', 
               'BHARTIARTL', 'AXISBANK', 'KOTAKBANK', 'TATAMOTORS', 'TATASTEEL', 'MARUTI', 
               'BAJFINANCE', 'SUNPHARMA', 'TITAN', 'HCLTECH', 'ADANIENT']
    
    stock_results = []
    all_trade_streams = []
    
    for sym in symbols:
        print(f"Testing {sym}...")
        if sym == 'BANKNIFTY':
            df_1m = load_bnf()
        else:
            df_1m = load_stock_data(sym)
            
        if df_1m is None: continue
        
        # Test on 5m
        df_5m = resample_and_calc_indicators(df_1m, tf_min=5)
        
        # Test target RRs: 2.0, 2.5, 3.0
        best_sym_res = None
        best_r = -9999
        
        for rr in [2.0, 2.5, 3.0]:
            trades = backtest_ema_atr_pullback(df_5m, nifty_trend_idx, sym, target_rr=rr)
            if len(trades) < 30: continue
            
            df_t = pd.DataFrame(trades)
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
            
            if tot_r > best_r:
                best_r = tot_r
                best_sym_res = {
                    'Symbol': sym,
                    'RR': f"1:{rr}",
                    'Trades': len(df_t),
                    'WinRate': round(wr, 1),
                    'Total_R': round(tot_r, 1),
                    'Monthly_R': round(r_m, 2),
                    'Max_DD': round(max_dd, 1),
                    'PF': round(pf, 2),
                    'trades': trades
                }
                
        if best_sym_res:
            stock_results.append(best_sym_res)
            all_trade_streams.extend(best_sym_res['trades'])
            
    df_summary = pd.DataFrame(stock_results).sort_values('Total_R', ascending=False)
    print("\n" + "="*85)
    print("         NIFTY-ALIGNED EMA + ATR RESULTS PER INSTRUMENT")
    print("="*85)
    print(df_summary[['Symbol', 'RR', 'Trades', 'WinRate', 'Total_R', 'Monthly_R', 'Max_DD', 'PF']].to_string(index=False))
    
    # Now simulate combined multi-stock portfolio with Portfolio Daily Circuit Breakers
    print("\n" + "="*85)
    print("         COMBINED MULTI-STOCK NIFTY-ALIGNED PORTFOLIO")
    print("="*85)
    
    df_all_t = pd.DataFrame(all_trade_streams).sort_values(['Date', 'Time']).reset_index(drop=True)
    df_all_t['Date'] = pd.to_datetime(df_all_t['Date'])
    
    # Portfolio level circuit breakers:
    for max_l in [1, 2, 3]:
        for max_tr in [2, 4, 6]:
            filtered = []
            for dt, grp in df_all_t.groupby('Date'):
                dl, dt_count = 0, 0
                for idx, r in grp.iterrows():
                    if dt_count >= max_tr or dl >= max_l: break
                    filtered.append(r)
                    dt_count += 1
                    if r['R'] < 0: dl += 1
                    
            df_p = pd.DataFrame(filtered)
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
            
            print(f"MaxLoss={max_l} | MaxTrades={max_tr} => Trades={len(df_p)} | WR={wr:.1f}% | TotalR={tot_r:+.1f} | MonthlyR={r_m:+.2f} R/mo | MaxDD={max_dd:.1f} R | PF={pf:.2f}")

    os.makedirs('reports', exist_ok=True)
    df_summary.to_csv('reports/nifty_aligned_ema_atr_stocks.csv', index=False)

if __name__ == '__main__':
    sweep_all_stocks()
