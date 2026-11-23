"""
PURE PRICE ACTION & DYNAMIC POI (POINTS OF INTEREST) ENGINE (2022 - 2026)
Simulates Institutional Price Action Trading on NIFTY 50 and BANK NIFTY:
1. Pre-Market Daily Analysis (Point-in-Time, 100% known before 09:15):
   - Previous Day High (PDH), Previous Day Low (PDL), Previous Day Close (PDC)
   - 3-Day Swing High (P3H) & 3-Day Swing Low (P3L)
   - Prior Day Range (PDR) & Gap Direction
2. Intraday POI Setups:
   - POI SETUP A: Liquidity Sweep & Reversal (SMC Turtle Soup / Fakeout of PDH/PDL)
     Price sweeps PDH/PDL to hunt liquidity, then produces a strong rejection candle closing back inside.
   - POI SETUP B: S/R Flip Retest (Breakout & Hold at PDH/PDL)
     Price breaks above PDH, retests PDH from above, forms a bullish rejection bar, and continues.
   - POI SETUP C: Gap Fill & Continuation at PDC (Prior Day Close POI)
     Price pulls back to fill the morning gap at PDC, finds support/resistance, and resumes trend.
3. Strict Execution:
   - Confirmed at Bar Close -> Executed on Next Bar Open (+0.02% slippage)
   - Exact Zerodha Index Intraday / Futures Charges
   - Static Rs 1,000 Risk (1R) on Rs 1,00,000 Capital (Zero Compounding)
"""

import os, glob, time
import numpy as np
import pandas as pd
from datetime import time as dtime

def compute_index_charges(buy_val, sell_val):
    brokerage = 40.0
    stt = sell_val * 0.00020
    exchange = (buy_val + sell_val) * 0.000019
    sebi = (buy_val + sell_val) * 0.000001
    stamp = buy_val * 0.00002
    gst = (brokerage + exchange + sebi) * 0.18
    return brokerage + stt + exchange + sebi + stamp + gst

def load_data():
    t0 = time.time()
    # 1. NIFTY 50
    n_files = sorted(glob.glob("data/nifty50/NIFTY50_1min_*.csv") + glob.glob("data/nifty50/2026/*.csv"))
    dfs = [pd.read_csv(f)[['Timestamp', 'Open', 'High', 'Low', 'Close']] for f in n_files]
    nifty = pd.concat(dfs, ignore_index=True)
    nifty['Date'] = pd.to_datetime(nifty['Timestamp'])
    nifty = nifty[(nifty['Date'] >= '2021-12-01') & (nifty['Date'] <= '2026-10-31 15:30:00')].sort_values('Date').reset_index(drop=True)
    nifty.set_index('Date', inplace=True)
    n5m = nifty.resample('5min').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna().reset_index()
    n5m['date_str'] = n5m['Date'].dt.strftime('%Y-%m-%d')
    n5m['time_str'] = n5m['Date'].dt.strftime('%H:%M:%S')
    n_days = {d: grp.reset_index(drop=True) for d, grp in n5m.groupby('date_str') if len(grp) >= 25}
    
    # 2. BANK NIFTY
    bn = pd.read_csv("data/banknifty/banknifty_1m.csv")
    bn['Date_parsed'] = pd.to_datetime(bn['Date'] + ' ' + bn['Time'], format='%d-%m-%Y %H:%M:%S')
    bn = bn[(bn['Date_parsed'] >= '2021-12-01') & (bn['Date_parsed'] <= '2026-10-31 15:30:00')].sort_values('Date_parsed').reset_index(drop=True)
    bn.set_index('Date_parsed', inplace=True)
    bn5m = bn.resample('5min').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna().reset_index()
    bn5m['date_str'] = bn5m['Date_parsed'].dt.strftime('%Y-%m-%d')
    bn5m['time_str'] = bn5m['Date_parsed'].dt.strftime('%H:%M:%S')
    bn_days = {d: grp.reset_index(drop=True) for d, grp in bn5m.groupby('date_str') if len(grp) >= 25}
    
    print(f"Data loaded in {time.time()-t0:.1f}s. Nifty: {len(n_days)} days, BankNifty: {len(bn_days)} days.", flush=True)
    return n_days, bn_days

def run_poi_simulation(name, days_dict, setup_type, is_banknifty=False):
    dates = sorted(list(days_dict.keys()))
    dates_eval = [d for d in dates if d >= '2022-01-01' and d <= '2026-10-31']
    
    trades = []
    risk_cash = 1000.0
    
    # Parameters based on asset
    min_pts = 60.0 if is_banknifty else 20.0
    max_pts = 180.0 if is_banknifty else 60.0
    buf = 25.0 if is_banknifty else 8.0
    
    for i, d in enumerate(dates_eval):
        idx = dates.index(d)
        if idx < 5: continue
        
        # Point-in-Time Prior Days POI Calculation
        prev_d = dates[idx - 1]
        prev_df = days_dict[prev_d]
        pdh = prev_df['High'].max()
        pdl = prev_df['Low'].min()
        pdc = prev_df['Close'].iloc[-1]
        
        # 3-Day Swing Extremes
        p3h = max([days_dict[dates[idx-k]]['High'].max() for k in range(1, 4)])
        p3l = min([days_dict[dates[idx-k]]['Low'].min() for k in range(1, 4)])
        
        cur_df = days_dict[d]
        opens = cur_df['Open'].values
        highs = cur_df['High'].values
        lows = cur_df['Low'].values
        closes = cur_df['Close'].values
        n_bars = len(cur_df)
        
        sig = None
        
        # -----------------------------------------------------------------
        # SETUP A: LIQUIDITY SWEEP & REVERSAL (TURTLE SOUP AT PDH / PDL)
        # -----------------------------------------------------------------
        if setup_type == 'LIQUIDITY_SWEEP':
            for b_i in range(1, min(30, n_bars - 6)):
                # Bearish Reversal: High sweeps PDH, but Close rejects back below PDH
                if highs[b_i] > pdh and closes[b_i] < pdh and closes[b_i] < opens[b_i]:
                    entry_p = opens[b_i + 1] * (1.0 - 0.0002)
                    sl_p = highs[b_i] + buf
                    risk_pts = max(min_pts, min(max_pts, abs(sl_p - entry_p)))
                    sig = {
                        'side': 'SELL', 'b_idx': b_i + 1, 'entry_p': entry_p,
                        'sl_p': entry_p + risk_pts,
                        't1_p': entry_p - (1.8 * risk_pts), 't2_p': entry_p - (3.5 * risk_pts)
                    }
                    break
                # Bullish Reversal: Low sweeps PDL, but Close rejects back above PDL
                elif lows[b_i] < pdl and closes[b_i] > pdl and closes[b_i] > opens[b_i]:
                    entry_p = opens[b_i + 1] * (1.0 + 0.0002)
                    sl_p = lows[b_i] - buf
                    risk_pts = max(min_pts, min(max_pts, abs(entry_p - sl_p)))
                    sig = {
                        'side': 'BUY', 'b_idx': b_i + 1, 'entry_p': entry_p,
                        'sl_p': entry_p - risk_pts,
                        't1_p': entry_p + (1.8 * risk_pts), 't2_p': entry_p + (3.5 * risk_pts)
                    }
                    break

        # -----------------------------------------------------------------
        # SETUP B: S/R FLIP RETEST (BREAKOUT AND CONFIRMED BOUNCE AT PDH / PDL)
        # -----------------------------------------------------------------
        elif setup_type == 'SR_FLIP_RETEST':
            # Check if opened above PDH or broke above early, then retested
            broke_above = False
            broke_below = False
            for b_i in range(1, min(35, n_bars - 6)):
                if not broke_above and closes[b_i] > pdh:
                    broke_above = True
                    continue
                if not broke_below and closes[b_i] < pdl:
                    broke_below = True
                    continue
                    
                # Bullish Retest: low dips to PDH, closes above PDH
                if broke_above and lows[b_i] <= pdh * 1.001 and closes[b_i] > pdh and closes[b_i] > opens[b_i]:
                    entry_p = opens[b_i + 1] * (1.0 + 0.0002)
                    sl_p = lows[b_i] - buf
                    risk_pts = max(min_pts, min(max_pts, abs(entry_p - sl_p)))
                    sig = {
                        'side': 'BUY', 'b_idx': b_i + 1, 'entry_p': entry_p,
                        'sl_p': entry_p - risk_pts,
                        't1_p': entry_p + (2.0 * risk_pts), 't2_p': entry_p + (3.5 * risk_pts)
                    }
                    break
                # Bearish Retest: high tests PDL, closes below PDL
                elif broke_below and highs[b_i] >= pdl * 0.999 and closes[b_i] < pdl and closes[b_i] < opens[b_i]:
                    entry_p = opens[b_i + 1] * (1.0 - 0.0002)
                    sl_p = highs[b_i] + buf
                    risk_pts = max(min_pts, min(max_pts, abs(sl_p - entry_p)))
                    sig = {
                        'side': 'SELL', 'b_idx': b_i + 1, 'entry_p': entry_p,
                        'sl_p': entry_p + risk_pts,
                        't1_p': entry_p - (2.0 * risk_pts), 't2_p': entry_p - (3.5 * risk_pts)
                    }
                    break

        # -----------------------------------------------------------------
        # SETUP C: PDC GAP-FILL REJECTION
        # -----------------------------------------------------------------
        elif setup_type == 'GAP_FILL_REJECTION':
            gap_pct = (opens[0] - pdc) / pdc * 100.0
            if abs(gap_pct) >= 0.3: # Meaningful gap
                for b_i in range(1, min(25, n_bars - 6)):
                    # Gap Up: pulls down to PDC, rejects and bounces back up
                    if gap_pct > 0 and lows[b_i] <= pdc * 1.0005 and closes[b_i] > pdc and closes[b_i] > opens[b_i]:
                        entry_p = opens[b_i + 1] * (1.0 + 0.0002)
                        sl_p = lows[b_i] - buf
                        risk_pts = max(min_pts, min(max_pts, abs(entry_p - sl_p)))
                        sig = {
                            'side': 'BUY', 'b_idx': b_i + 1, 'entry_p': entry_p,
                            'sl_p': entry_p - risk_pts,
                            't1_p': entry_p + (1.8 * risk_pts), 't2_p': opens[0] # Target is morning open
                        }
                        break
                    # Gap Down: rallies up to PDC, rejects and falls back down
                    elif gap_pct < 0 and highs[b_i] >= pdc * 0.9995 and closes[b_i] < pdc and closes[b_i] < opens[b_i]:
                        entry_p = opens[b_i + 1] * (1.0 - 0.0002)
                        sl_p = highs[b_i] + buf
                        risk_pts = max(min_pts, min(max_pts, abs(sl_p - entry_p)))
                        sig = {
                            'side': 'SELL', 'b_idx': b_i + 1, 'entry_p': entry_p,
                            'sl_p': entry_p + risk_pts,
                            't1_p': entry_p - (1.8 * risk_pts), 't2_p': opens[0]
                        }
                        break

        if not sig: continue
        
        side = sig['side']
        b_in = sig['b_idx']
        entry_p = sig['entry_p']
        sl_p = sig['sl_p']
        t1_p = sig['t1_p']
        t2_p = sig['t2_p']
        risk_pts = abs(entry_p - sl_p)
        shares = risk_cash / risk_pts
        s_t1 = shares * 0.5
        s_run = shares * 0.5
        
        t1_hit = False
        exit_p1 = 0.0
        exit_pr = 0.0
        curr_sl = sl_p
        
        for j in range(b_in + 1, n_bars):
            h, l, c = highs[j], lows[j], closes[j]
            if side == 'BUY':
                if l <= curr_sl:
                    if not t1_hit: exit_p1, exit_pr = curr_sl, curr_sl
                    else: exit_pr = curr_sl
                    break
                if not t1_hit and h >= t1_p:
                    t1_hit = True
                    exit_p1 = t1_p
                    curr_sl = entry_p # Move to Break-Even!
                if t1_hit and h >= t2_p:
                    exit_pr = t2_p
                    break
                if j >= 72 or j == n_bars - 1:
                    if not t1_hit: exit_p1 = c
                    exit_pr = c
                    break
            else:
                if h >= curr_sl:
                    if not t1_hit: exit_p1, exit_pr = curr_sl, curr_sl
                    else: exit_pr = curr_sl
                    break
                if not t1_hit and l <= t1_p:
                    t1_hit = True
                    exit_p1 = t1_p
                    curr_sl = entry_p
                if t1_hit and l <= t2_p:
                    exit_pr = t2_p
                    break
                if j >= 72 or j == n_bars - 1:
                    if not t1_hit: exit_p1 = c
                    exit_pr = c
                    break
                    
        if side == 'BUY':
            exit_p1 = exit_p1 * (1.0 - 0.0002)
            exit_pr = exit_pr * (1.0 - 0.0002)
            buy_val = shares * entry_p
            sell_val = (s_t1 * exit_p1) + (s_run * exit_pr)
        else:
            exit_p1 = exit_p1 * (1.0 + 0.0002)
            exit_pr = exit_pr * (1.0 + 0.0002)
            sell_val = shares * entry_p
            buy_val = (s_t1 * exit_p1) + (s_run * exit_pr)
            
        fee = compute_index_charges(buy_val, sell_val)
        net_pnl = (sell_val - buy_val) - fee
        trades.append({'date': d, 'year': int(d[:4]), 'net_pnl': net_pnl, 'R': net_pnl / risk_cash})
        
    df_t = pd.DataFrame(trades)
    if len(df_t) == 0:
        print(f"[{name}] 0 trades.")
        return
        
    df_t['ym'] = pd.to_datetime(df_t['date']).dt.to_period('M')
    n_mo = df_t['ym'].nunique()
    tot_pnl = df_t['net_pnl'].sum()
    wins = df_t[df_t['net_pnl'] > 0]
    wr = len(wins) / len(df_t) * 100.0
    gw = wins['net_pnl'].sum()
    gl = abs(df_t[df_t['net_pnl'] <= 0]['net_pnl'].sum())
    pf = gw / gl if gl > 0 else 0.0
    
    df_t['cum'] = df_t['net_pnl'].cumsum()
    df_t['peak'] = df_t['cum'].cummax()
    max_dd = abs((df_t['cum'] - df_t['peak']).min()) / 100000.0 * 100.0
    y_pnl = df_t.groupby('year')['net_pnl'].sum().to_dict()
    
    print("="*85)
    print(f"PRICE ACTION / POI SYSTEM: {name}")
    print(f"  Trades: {len(df_t)} ({len(df_t)/n_mo:.1f}/mo) | Win Rate: {wr:5.2f}% | Profit Factor: {pf:4.2f}")
    print(f"  Total Net PnL: Rs {tot_pnl:+10,.0f} (+{tot_pnl/1000:.1f}R) | Avg Monthly Return: {tot_pnl/100000/n_mo*100:+5.2f}% / month")
    print(f"  Max Drawdown: {max_dd:5.2f}%")
    print(f"  Yearly Breakdown: { {y: int(v) for y, v in y_pnl.items()} }\n", flush=True)

def main():
    n_days, bn_days = load_data()
    
    # NIFTY 50 POI TESTS
    run_poi_simulation("NIFTY 50: POI LIQUIDITY SWEEP & REVERSAL", n_days, 'LIQUIDITY_SWEEP', is_banknifty=False)
    run_poi_simulation("NIFTY 50: POI S/R FLIP RETEST", n_days, 'SR_FLIP_RETEST', is_banknifty=False)
    run_poi_simulation("NIFTY 50: POI GAP-FILL & PDC REJECTION", n_days, 'GAP_FILL_REJECTION', is_banknifty=False)
    
    # BANK NIFTY POI TESTS
    run_poi_simulation("BANK NIFTY: POI LIQUIDITY SWEEP & REVERSAL", bn_days, 'LIQUIDITY_SWEEP', is_banknifty=True)
    run_poi_simulation("BANK NIFTY: POI S/R FLIP RETEST", bn_days, 'SR_FLIP_RETEST', is_banknifty=True)
    run_poi_simulation("BANK NIFTY: POI GAP-FILL & PDC REJECTION", bn_days, 'GAP_FILL_REJECTION', is_banknifty=True)

if __name__ == '__main__':
    main()
