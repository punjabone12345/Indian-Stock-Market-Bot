"""
Nifty 50 Macro Trend Gatekeeper Test on 194 Stocks (4.8 Years)
Testing if Macro Alignment fixes 2022 and 2023 performance and eliminates the "only worked in 2026" problem!
"""

import os
import ssl
import json
import glob
import urllib.request
import numpy as np
import pandas as pd

CACHE_DIR = "data/nifty200_daily_cache"

def compute_zerodha_charges(buy_val, sell_val):
    b_buy = min(20.0, buy_val * 0.0003)
    b_sell = min(20.0, sell_val * 0.0003)
    brokerage = b_buy + b_sell
    stt = sell_val * 0.00025
    exchange = (buy_val + sell_val) * 0.0000297
    sebi = (buy_val + sell_val) * 0.000001
    stamp = buy_val * 0.00003
    gst = (brokerage + exchange + sebi) * 0.18
    return brokerage + stt + exchange + sebi + stamp + gst

def load_nifty():
    url = 'https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEI?interval=1d&range=5y'
    ctx = ssl._create_unverified_context()
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    d = json.loads(urllib.request.urlopen(req, context=ctx).read().decode('utf-8'))
    res = d['chart']['result'][0]
    timestamps = res['timestamp']
    closes = res['indicators']['quote'][0]['close']
    
    df_n = pd.DataFrame({
        'Date': pd.to_datetime(timestamps, unit='s', utc=True).tz_convert('Asia/Kolkata').tz_localize(None),
        'Close': closes
    }).dropna().sort_values('Date').reset_index(drop=True)
    
    df_n['date_str'] = df_n['Date'].dt.strftime('%Y-%m-%d')
    df_n['SMA20'] = df_n['Close'].rolling(20).mean()
    df_n['SMA50'] = df_n['Close'].rolling(50).mean()
    
    nifty_regime = {}
    for idx, r in df_n.iterrows():
        c = r['Close']
        s20 = r['SMA20']
        s50 = r['SMA50']
        if np.isnan(s20) or np.isnan(s50):
            bull, bear = True, True
        else:
            bull = (c > s20) or (c > s50)
            bear = (c < s20) or (c < s50)
        nifty_regime[r['date_str']] = {'bull': bull, 'bear': bear}
    return nifty_regime

def test_macro_gap():
    nifty_map = load_nifty()
    
    files = glob.glob(os.path.join(CACHE_DIR, "*.parquet"))
    symbol_data = {}
    for f in files:
        sym = os.path.basename(f).replace(".parquet", "")
        symbol_data[sym] = pd.read_parquet(f)
        
    symbol_days = {}
    all_dates = set()
    
    for sym, df in symbol_data.items():
        df = df.sort_values('Date').reset_index(drop=True)
        df['prev_close'] = df['Close'].shift(1)
        df['gap_pct'] = (df['Open'] - df['prev_close']) / df['prev_close'] * 100.0
        df['vol_20avg'] = df['Volume'].rolling(20).mean().shift(1)
        df['rvol'] = df['Volume'] / np.where(df['vol_20avg'] > 0, df['vol_20avg'], df['Volume'])
        df['day_range'] = df['High'] - df['Low']
        
        symbol_days[sym] = {}
        for idx, row in df.iterrows():
            d_str = row['date_str']
            year = int(d_str[:4])
            if year >= 2022:
                all_dates.add(d_str)
                symbol_days[sym][d_str] = row
                
    sorted_dates = sorted(list(all_dates))
    
    # Compare WITHOUT Macro vs WITH Macro Filter
    for use_macro in [False, True]:
        label = "WITH NIFTY 50 MACRO TREND FILTER" if use_macro else "WITHOUT MACRO FILTER (BLIND)"
        print(f"\n{'='*85}\nSIMULATING: {label} (UNCOMPOUNDED FLAT 1.0% RISK)\n{'='*85}", flush=True)
        
        trades = []
        risk_cash = 1000.0 # Flat 1.0% Risk (Rs 1,000 per trade)
        
        for date_str in sorted_dates:
            n_reg = nifty_map.get(date_str, {'bull': True, 'bear': True})
            candidates = []
            
            for sym, d_dict in symbol_days.items():
                if date_str not in d_dict: continue
                row = d_dict[date_str]
                gap_pct = row['gap_pct']
                rvol = row['rvol']
                open_p = row['Open']
                high_p = row['High']
                low_p = row['Low']
                close_p = row['Close']
                day_range = row['day_range']
                
                if np.isnan(gap_pct) or np.isnan(rvol): continue
                if abs(gap_pct) < 1.0: continue
                if rvol < 2.0: continue
                if day_range <= 0 or open_p <= 0: continue
                
                # Check Macro Alignment if enabled
                if use_macro:
                    if gap_pct >= 1.0 and not n_reg['bull']: continue # reject Long when Nifty is bear
                    if gap_pct <= -1.0 and not n_reg['bear']: continue # reject Short when Nifty is bull
                    
                sl_dist = max(open_p * 0.0035, min(open_p * 0.0085, day_range * 0.50))
                score = rvol * (1.0 + abs(gap_pct))
                
                if gap_pct >= 1.0:
                    candidates.append({
                        'symbol': sym, 'side': 'BUY', 'entry_p': open_p, 'sl_p': open_p - sl_dist,
                        'risk_pts': sl_dist, 'high_p': high_p, 'low_p': low_p, 'close_p': close_p,
                        'score': score
                    })
                elif gap_pct <= -1.0:
                    candidates.append({
                        'symbol': sym, 'side': 'SELL', 'entry_p': open_p, 'sl_p': open_p + sl_dist,
                        'risk_pts': sl_dist, 'high_p': high_p, 'low_p': low_p, 'close_p': close_p,
                        'score': score
                    })
                    
            if not candidates: continue
            candidates.sort(key=lambda x: -x['score'])
            trade = candidates[0]
            
            sym = trade['symbol']
            side = trade['side']
            entry_p = trade['entry_p']
            sl_p = trade['sl_p']
            risk_pts = trade['risk_pts']
            high_p = trade['high_p']
            low_p = trade['low_p']
            close_p = trade['close_p']
            
            shares = int(risk_cash / risk_pts)
            if shares < 1: shares = 1
            
            s_t1 = int(shares * 0.40)
            s_t2 = int(shares * 0.30)
            s_run = shares - s_t1 - s_t2
            if s_t1 < 1: s_t1 = 1
            
            t1_p = entry_p + (2.0 * risk_pts) if side == 'BUY' else entry_p - (2.0 * risk_pts)
            t2_p = entry_p + (3.5 * risk_pts) if side == 'BUY' else entry_p - (3.5 * risk_pts)
            
            exit_p1, exit_p2, exit_pr = 0.0, 0.0, 0.0
            
            if side == 'BUY':
                if low_p <= sl_p:
                    exit_p1, exit_p2, exit_pr = sl_p, sl_p, sl_p
                else:
                    if high_p >= t1_p:
                        exit_p1 = t1_p
                        if high_p >= t2_p:
                            exit_p2 = t2_p
                            exit_pr = close_p
                        else:
                            exit_p2 = close_p
                            exit_pr = close_p
                    else:
                        exit_p1, exit_p2, exit_pr = close_p, close_p, close_p
                p1 = s_t1 * (exit_p1 - entry_p)
                f1 = compute_zerodha_charges(s_t1 * entry_p, s_t1 * exit_p1)
                p2 = s_t2 * (exit_p2 - entry_p) if s_t2 > 0 else 0
                f2 = compute_zerodha_charges(s_t2 * entry_p, s_t2 * exit_p2) if s_t2 > 0 else 0
                pr = s_run * (exit_pr - entry_p) if s_run > 0 else 0
                fr = compute_zerodha_charges(s_run * entry_p, s_run * exit_pr) if s_run > 0 else 0
            else:
                if high_p >= sl_p:
                    exit_p1, exit_p2, exit_pr = sl_p, sl_p, sl_p
                else:
                    if low_p <= t1_p:
                        exit_p1 = t1_p
                        if low_p <= t2_p:
                            exit_p2 = t2_p
                            exit_pr = close_p
                        else:
                            exit_p2 = close_p
                            exit_pr = close_p
                    else:
                        exit_p1, exit_pr = close_p, close_p
                p1 = s_t1 * (entry_p - exit_p1)
                f1 = compute_zerodha_charges(s_t1 * exit_p1, s_t1 * entry_p)
                p2 = s_t2 * (entry_p - exit_p2) if s_t2 > 0 else 0
                f2 = compute_zerodha_charges(s_t2 * entry_p, s_t2 * exit_p2) if s_t2 > 0 else 0
                pr = s_run * (entry_p - exit_pr) if s_run > 0 else 0
                fr = compute_zerodha_charges(s_run * exit_pr, s_run * entry_p) if s_run > 0 else 0
                
            gross_pnl = p1 + p2 + pr
            fee = f1 + f2 + fr
            net_pnl = gross_pnl - fee
            ret_pct = net_pnl / 1000.0
            
            trades.append({
                'date': date_str,
                'year': int(date_str[:4]),
                'symbol': sym,
                'ret_pct': ret_pct,
                'fee': fee
            })
            
        df_t = pd.DataFrame(trades)
        yearly = df_t.groupby('year').agg(
            trades=('ret_pct', 'count'),
            win_rate=('ret_pct', lambda x: (x > 0).mean() * 100),
            total_ret=('ret_pct', 'sum'),
            fees=('fee', 'sum')
        )
        total_ret = df_t['ret_pct'].sum()
        df_t['cum'] = df_t['ret_pct'].cumsum()
        df_t['peak'] = df_t['cum'].cummax()
        df_t['dd'] = df_t['cum'] - df_t['peak']
        max_dd = df_t['dd'].min()
        win_rate = (df_t['ret_pct'] > 0).mean() * 100.0
        
        print(f"\nOVERALL RESULT ({label}):")
        print(f"  Total Trades: {len(df_t)} | Win Rate: {win_rate:.2f}% | Total Net: {total_ret:+.2f}% | Max Drawdown: {max_dd:.2f}%")
        print("  YEARLY PERFORMANCE:")
        print(yearly)

if __name__ == '__main__':
    test_macro_gap()
