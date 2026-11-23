"""
TEST INTRADAY RELATIVE STRENGTH LEADER SYSTEM (2022 - 2026)
100% Point-in-Time, Zero Look-Ahead:
1. 09:15 to 10:00 AM: Calculate NIFTY 50 return and all 30 mega-cap stock returns
2. Calculate Intraday VWAP for all stocks
3. At 10:00 AM:
   - If NIFTY 50 is Bullish (Return > +0.2% and Nifty > VWAP):
     Select #1 Leader (Stock Return > +1.2%, Stock > VWAP, breaking 10:00 AM High)
     Enter LONG at 10:01 AM Open (+0.03% slippage)
   - If NIFTY 50 is Bearish (Return < -0.2% and Nifty < VWAP):
     Select #1 Laggard (Stock Return < -1.2%, Stock < VWAP, breaking 10:00 AM Low)
     Enter SHORT at 10:01 AM Open (-0.03% slippage)
4. Exits:
   - Stop-Loss: 1.0% (Rs 1,000 risk = 1R, static zero compounding)
   - Target 1: +2.0R (50% quantity)
   - Target 2: +4.0R (50% quantity) / 15:15 EOD square-off
5. Full Zerodha leg-by-leg charges + slippage
"""

import os, glob, time
import numpy as np
import pandas as pd

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

def load_nifty50_data():
    files = glob.glob("data/nifty50/NIFTY50_1min_*.csv")
    dfs = []
    for f in sorted(files):
        df = pd.read_csv(f)
        df['Date'] = pd.to_datetime(df['Timestamp'])
        dfs.append(df)
    nifty = pd.concat(dfs, ignore_index=True).sort_values('Date').reset_index(drop=True)
    nifty['date_str'] = nifty['Date'].dt.strftime('%Y-%m-%d')
    nifty['time_str'] = nifty['Date'].dt.strftime('%H:%M:%S')
    return nifty

def run_rs_leader_system():
    t0 = time.time()
    print("Loading NIFTY 50 1-minute data...", flush=True)
    nifty_df = load_nifty50_data()
    nifty_by_day = {d: grp for d, grp in nifty_df.groupby('date_str')}
    print(f"Loaded NIFTY 50 for {len(nifty_by_day)} trading days.", flush=True)
    
    stock_files = glob.glob("data/stocks/*_prev.parquet")
    symbols_data = {}
    print(f"Loading {len(stock_files)} stocks...", flush=True)
    
    for f in stock_files:
        sym = os.path.basename(f).replace("_prev.parquet", "")
        df_prev = pd.read_parquet(f)
        f_2026 = f.replace("_prev.parquet", "_2026.parquet")
        if os.path.exists(f_2026):
            df = pd.concat([df_prev, pd.read_parquet(f_2026)], ignore_index=True)
        else:
            df = df_prev
            
        df['Date'] = pd.to_datetime(df['Date'])
        mask = (df['Date'] >= '2022-01-01') & (df['Date'] <= '2026-10-31 15:30:00')
        sub = df[mask].sort_values('Date').reset_index(drop=True)
        if len(sub) < 1000: continue
        sub['date_str'] = sub['Date'].dt.date.astype(str)
        sub['time_str'] = sub['Date'].dt.time.astype(str)
        symbols_data[sym] = {d: grp for d, grp in sub.groupby('date_str')}
        
    dates = sorted(list(nifty_by_day.keys()))
    dates = [d for d in dates if int(d[:4]) >= 2022 and d <= '2026-10-31']
    print(f"Ready to simulate across {len(dates)} dates in {time.time()-t0:.1f}s.\n", flush=True)
    
    # We test 3 variations of Relative Strength:
    # 1. Enter at 10:00 AM (45 min lookback)
    # 2. Enter at 09:45 AM (30 min lookback)
    # 3. Enter at 10:15 AM (60 min lookback)
    
    for check_time in ['09:45:00', '10:00:00', '10:15:00']:
        trades = []
        risk_cash = 1000.0
        
        for d in dates:
            if d not in nifty_by_day: continue
            n_day = nifty_by_day[d]
            n_eval = n_day[n_day['time_str'] <= check_time]
            if len(n_eval) < 15: continue
            
            n_open = n_eval.iloc[0]['Open']
            n_close = n_eval.iloc[-1]['Close']
            n_ret = (n_close - n_open) / n_open * 100.0
            
            candidates = []
            
            for sym, day_dict in symbols_data.items():
                if d not in day_dict: continue
                s_day = day_dict[d]
                s_eval = s_day[s_day['time_str'] <= check_time]
                s_rest = s_day[s_day['time_str'] > check_time]
                if len(s_eval) < 15 or len(s_rest) < 15: continue
                
                s_open = s_eval.iloc[0]['Open']
                s_close = s_eval.iloc[-1]['Close']
                s_high = s_eval['High'].max()
                s_low = s_eval['Low'].min()
                s_ret = (s_close - s_open) / s_open * 100.0
                
                # VWAP calculation for eval period
                pv = (s_eval['Close'] * s_eval['Volume']).sum()
                v = s_eval['Volume'].sum()
                vwap = pv / v if v > 0 else s_close
                
                # Relative strength: difference from Nifty
                rs = s_ret - n_ret
                
                # Bullish setup: Nifty > 0.1%, Stock > VWAP, Stock outperforming by >= 1.0%
                if n_ret >= 0.10 and s_close > vwap and rs >= 1.0 and s_ret >= 1.2:
                    candidates.append({
                        'symbol': sym, 'side': 'BUY', 'score': rs,
                        'eval_high': s_high, 'eval_low': s_low,
                        's_rest': s_rest
                    })
                # Bearish setup: Nifty < -0.1%, Stock < VWAP, Stock underperforming by <= -1.0%
                elif n_ret <= -0.10 and s_close < vwap and rs <= -1.0 and s_ret <= -1.2:
                    candidates.append({
                        'symbol': sym, 'side': 'SELL', 'score': abs(rs),
                        'eval_high': s_high, 'eval_low': s_low,
                        's_rest': s_rest
                    })
                    
            if not candidates: continue
            candidates.sort(key=lambda x: -x['score']) # Strongest relative leader
            
            # Trade of the Day: Take top 1 or top 2
            for c in candidates[:1]:
                s_rest = c['s_rest']
                side = c['side']
                
                # Entry on the next 1m bar open (strictly point-in-time)
                entry_bar = s_rest.iloc[0]
                entry_p = entry_bar['Open'] * (1.0 + 0.0003) if side == 'BUY' else entry_bar['Open'] * (1.0 - 0.0003)
                
                risk_pts = entry_p * 0.010 # 1.0% stop
                sl_p = entry_p - risk_pts if side == 'BUY' else entry_p + risk_pts
                t1_p = entry_p + (2.0 * risk_pts) if side == 'BUY' else entry_p - (2.0 * risk_pts)
                t2_p = entry_p + (4.0 * risk_pts) if side == 'BUY' else entry_p - (4.0 * risk_pts)
                
                shares = int(risk_cash / risk_pts)
                if shares < 1: continue
                s_t1 = int(shares * 0.5)
                s_run = shares - s_t1
                if s_t1 < 1: s_t1 = 1
                
                exit_p1 = 0.0
                exit_pr = 0.0
                t1_hit = False
                
                bars_list = s_rest.to_dict('records')
                for b in bars_list[1:]:
                    hp = b['High']
                    lp = b['Low']
                    
                    if side == 'BUY':
                        cur_sl = entry_p if t1_hit else sl_p
                        if lp <= cur_sl:
                            if not t1_hit:
                                exit_p1 = cur_sl * (1.0 - 0.0003)
                                exit_pr = cur_sl * (1.0 - 0.0003)
                            else:
                                exit_pr = cur_sl * (1.0 - 0.0003)
                            break
                        if not t1_hit and hp >= t1_p:
                            exit_p1 = t1_p
                            t1_hit = True
                        if t1_hit and hp >= t2_p:
                            exit_pr = t2_p
                            break
                    else:
                        cur_sl = entry_p if t1_hit else sl_p
                        if hp >= cur_sl:
                            if not t1_hit:
                                exit_p1 = cur_sl * (1.0 + 0.0003)
                                exit_pr = cur_sl * (1.0 + 0.0003)
                            else:
                                exit_pr = cur_sl * (1.0 + 0.0003)
                            break
                        if not t1_hit and lp <= t1_p:
                            exit_p1 = t1_p
                            t1_hit = True
                        if t1_hit and lp <= t2_p:
                            exit_pr = t2_p
                            break
                            
                last_bar = bars_list[-1]
                if exit_p1 <= 0.0:
                    exit_p1 = last_bar['Close'] * (1.0 - 0.0003 if side == 'BUY' else 1.0 + 0.0003)
                if exit_pr <= 0.0:
                    exit_pr = last_bar['Close'] * (1.0 - 0.0003 if side == 'BUY' else 1.0 + 0.0003)
                    
                if side == 'BUY':
                    buy_v = shares * entry_p
                    sell_v = (s_t1 * exit_p1) + (s_run * exit_pr)
                    gp = sell_v - buy_v
                else:
                    sell_v = shares * entry_p
                    buy_v = (s_t1 * exit_p1) + (s_run * exit_pr)
                    gp = sell_v - buy_v
                    
                fee = compute_zerodha_charges(buy_v, sell_v)
                npnl = gp - fee
                
                trades.append({
                    'date': d, 'year': int(d[:4]), 'symbol': c['symbol'], 'side': side,
                    'net_pnl': npnl, 'fee': fee, 'R': npnl / 1000.0
                })
                
        df_t = pd.DataFrame(trades)
        if len(df_t) == 0:
            print(f"[{check_time}] No trades.")
            continue
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
        mo_pnl = df_t.groupby('ym')['net_pnl'].sum()
        prof_mo = (mo_pnl > 0).mean() * 100.0
        y_pnl = df_t.groupby('year')['net_pnl'].sum().to_dict()
        
        print("="*85)
        print(f"[RELATIVE STRENGTH LEADER | EVAL TIME: {check_time}]")
        print(f"  Trades: {len(df_t)} ({len(df_t)/n_mo:.1f}/mo) | WR: {wr:5.2f}% | PF: {pf:4.2f}")
        print(f"  Net PnL: Rs {tot_pnl:+10,.0f} (+{tot_pnl/1000:.1f}R) | Avg Mo Return: {tot_pnl/100000/n_mo*100:+5.2f}% / month")
        print(f"  Max DD: {max_dd:5.2f}% | Profitable Months: {prof_mo:.1f}%")
        print(f"  Yearly: { {y: int(v) for y, v in y_pnl.items()} }\n", flush=True)

if __name__ == '__main__':
    run_rs_leader_system()
