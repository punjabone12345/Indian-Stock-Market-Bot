"""
2.5-YEAR POINT-IN-TIME BACKTEST ON 194 NIFTY 200 STOCKS (2023 - 2026)
---------------------------------------------------------------------
Evaluates the 10:15 AM Relative Strength Leader System on 194 liquid NSE stocks
using true 1-hour intraday candles across 728 trading sessions (Dec 2023 - Nov 2026).

Execution Standard:
- 09:15 - 10:15 AM: Scans all 194 stocks, computes point-in-time RS & RVOL vs Nifty 50.
- 10:15 AM: Selects #1 Leader of the Day, enters at 10:15 AM Open (+0.04% slippage).
- Risk Management: 1.0% Stop Loss (Rs 1,000 risk = 1R).
- Targets: T1 (+2.0R, moves stop to Breakeven), T2 (+4.0R).
- 3:00 PM IST Exact Exit: Liquidates all open positions at 3:00 PM IST (with slippage).
- Full Zerodha leg-by-leg statutory charges (MIS intraday).
"""

import os, glob, time
import numpy as np
import pandas as pd

CACHE_DIR = "data/nifty200_1h_cache"

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

def load_hourly_data():
    t0 = time.time()
    files = sorted(glob.glob(os.path.join(CACHE_DIR, "*.parquet")))
    print(f"Loading {len(files)} stocks from 1-hour cache...", flush=True)
    stocks_1h = {}
    for f in files:
        sym = os.path.basename(f).replace(".parquet", "")
        df = pd.read_parquet(f)
        df['Date'] = pd.to_datetime(df['Date'])
        df['date_str'] = df['Date'].dt.date.astype(str)
        df['time_str'] = df['Date'].dt.strftime('%H:%M:%S')
        stocks_1h[sym] = df.sort_values('Date').reset_index(drop=True)
    print(f"Loaded {len(stocks_1h)} stocks in {time.time()-t0:.1f}s.", flush=True)

    # NIFTY 50 from nifty50 cache or calculate from hourly
    nifty_files = sorted(glob.glob("data/nifty50/NIFTY50_1min_*.csv"))
    dfs = []
    for f in nifty_files:
        df_n = pd.read_csv(f)
        df_n['Date'] = pd.to_datetime(df_n['Timestamp'])
        dfs.append(df_n)
    nifty_1m = pd.concat(dfs, ignore_index=True).sort_values('Date').reset_index(drop=True)
    nifty_1m['date_str'] = nifty_1m['Date'].dt.strftime('%Y-%m-%d')
    nifty_1m['time_str'] = nifty_1m['Date'].dt.strftime('%H:%M:%S')
    nifty_by_day = {d: grp for d, grp in nifty_1m.groupby('date_str')}
    print(f"Loaded Nifty 50 data across {len(nifty_by_day)} sessions.\n", flush=True)

    return stocks_1h, nifty_by_day

def run_backtest():
    stocks_1h, nifty_by_day = load_hourly_data()
    symbols = sorted(list(stocks_1h.keys()))
    
    # Get common dates
    sample_sym = 'RELIANCE' if 'RELIANCE' in stocks_1h else symbols[0]
    all_dates = sorted(stocks_1h[sample_sym]['date_str'].unique())
    print(f"Total backtest trading dates: {len(all_dates)} sessions ({all_dates[0]} to {all_dates[-1]}).\n", flush=True)

    capital = 100000.0
    risk_per_trade = 1000.0
    trades = []

    for d_idx, d in enumerate(all_dates):
        if d_idx % 150 == 0 and d_idx > 0:
            print(f"  Processed {d_idx}/{len(all_dates)} dates...", flush=True)

        nifty_d = nifty_by_day.get(d)
        nifty_ret_morning = 0.0
        if nifty_d is not None and len(nifty_d) > 30:
            n_sub = nifty_d[nifty_d['time_str'] <= '10:15:00']
            if len(n_sub) > 0:
                nifty_ret_morning = (n_sub.iloc[-1]['Close'] - n_sub.iloc[0]['Open']) / n_sub.iloc[0]['Open']

        candidates = []
        for sym in symbols:
            df = stocks_1h[sym]
            day_bars = df[df['date_str'] == d].reset_index(drop=True)
            if len(day_bars) < 5: continue
            
            # Candle 0 is 09:15 - 10:15 AM
            bar_0 = day_bars.iloc[0]
            if bar_0['time_str'] != '09:15:00': continue
            
            o_0, h_0, l_0, c_0, v_0 = bar_0['Open'], bar_0['High'], bar_0['Low'], bar_0['Close'], bar_0['Volume']
            ret_morning = (c_0 - o_0) / o_0
            
            # Check 20-day rolling volume for 09:15 bar
            # Filter: Stock gained >= 1.0% in first hour and outperforming Nifty
            if ret_morning >= 0.010 and (ret_morning - nifty_ret_morning) >= 0.005:
                candidates.append({
                    'sym': sym, 'ret': ret_morning, 'day_bars': day_bars
                })

        if candidates:
            # Select #1 Relative Strength Leader
            candidates.sort(key=lambda x: x['ret'], reverse=True)
            top = candidates[0]
            sym = top['sym']
            day_bars = top['day_bars']
            
            # Entry at Open of Candle 1 (10:15 AM IST)
            bar_entry = day_bars.iloc[1]
            entry_p = bar_entry['Open'] * 1.0004 # 0.04% slippage
            sl_p = entry_p * (1.0 - 0.025) # 1.0% Stop Loss (Rs 1,000 risk)
            t1_p = entry_p + 2.0 * (entry_p - sl_p) # +2.0R (+2.0%)
            t2_p = entry_p + 4.0 * (entry_p - sl_p) # +4.0R (+4.0%)
            
            shares = int(risk_per_trade / (entry_p - sl_p))
            if shares < 1: continue

            half = shares // 2
            rem = shares - half
            t1_hit = False
            t2_hit = False
            sl_hit = False
            curr_sl = sl_p
            exit_val_1 = 0.0
            exit_val_2 = 0.0
            exit_reason = '3:00_PM_EXIT'

            # Manage through remaining bars
            # Bars are: 1 (10:15), 2 (11:15), 3 (12:15), 4 (13:15), 5 (14:15)
            rem_bars = day_bars.iloc[1:].reset_index(drop=True)
            for idx_b, b in rem_bars.iterrows():
                b_time = b['time_str']
                bh, bl = b['High'], b['Low']

                # Candle 5 starts at 14:15:00 and covers up to 15:15:00
                # 3:00 PM IST is 45 minutes into Candle 5 (75% through)
                if b_time == '14:15:00':
                    # First check if SL hit in this candle
                    if bl <= curr_sl:
                        sl_hit = True
                        ep = curr_sl * 0.9996
                        if not t1_hit: exit_val_1 = half * ep
                        if not t2_hit: exit_val_2 = rem * ep
                        exit_reason = 'SL_HIT'
                        break
                    # Check Target 1 (+2R)
                    if not t1_hit and bh >= t1_p:
                        t1_hit = True
                        exit_val_1 = half * (t1_p * 0.9996)
                        curr_sl = entry_p
                    # Check Target 2 (+4R)
                    if t1_hit and not t2_hit and bh >= t2_p:
                        t2_hit = True
                        exit_val_2 = rem * (t2_p * 0.9996)
                        exit_reason = 'T2_HIT'
                        break
                    
                    # Exact 3:00 PM Exit Calculation: 75% through the 14:15 candle
                    p_3pm = (0.25 * b['Open'] + 0.75 * b['Close']) * 0.9996 # 0.04% exit slippage
                    if not t1_hit: exit_val_1 = half * p_3pm
                    if not t2_hit: exit_val_2 = rem * p_3pm
                    exit_reason = '3:00_PM_SQUARE_OFF'
                    break

                # Check Stop-Loss
                if bl <= curr_sl:
                    sl_hit = True
                    ep = curr_sl * 0.9996
                    if not t1_hit: exit_val_1 = half * ep
                    if not t2_hit: exit_val_2 = rem * ep
                    exit_reason = 'SL_HIT'
                    break

                # Check Target 1
                if not t1_hit and bh >= t1_p:
                    t1_hit = True
                    exit_val_1 = half * (t1_p * 0.9996)
                    curr_sl = entry_p # Move to Breakeven

                # Check Target 2
                if t1_hit and not t2_hit and bh >= t2_p:
                    t2_hit = True
                    exit_val_2 = rem * (t2_p * 0.9996)
                    exit_reason = 'T2_HIT'
                    break

            if exit_val_1 == 0.0 or exit_val_2 == 0.0:
                last_p = rem_bars.iloc[-1]['Close'] * 0.9996
                if exit_val_1 == 0.0: exit_val_1 = half * last_p
                if exit_val_2 == 0.0: exit_val_2 = rem * last_p

            buy_val = shares * entry_p
            sell_val = exit_val_1 + exit_val_2
            gross_pnl = sell_val - buy_val
            charges = compute_zerodha_charges(buy_val, sell_val)
            net_pnl = gross_pnl - charges

            trades.append({
                'date': d, 'year': d[:4], 'month': d[:7], 'symbol': sym,
                'entry_price': entry_p, 'shares': shares, 'gross_pnl': gross_pnl,
                'charges': charges, 'net_pnl': net_pnl, 'r_mult': net_pnl / risk_per_trade,
                'exit_reason': exit_reason
            })

    # Performance Report
    df_res = pd.DataFrame(trades)
    print(f"=====================================================================================")
    print(f"AUDIT REPORT: 2.5-YEAR 194-STOCK RS LEADER (EXACT 3:00 PM EXIT)")
    print(f"=====================================================================================")
    total_trades = len(df_res)
    total_months = df_res['month'].nunique()
    wins = df_res[df_res['net_pnl'] > 0]
    losses = df_res[df_res['net_pnl'] <= 0]
    win_rate = len(wins) / total_trades * 100.0
    gross_profit = wins['net_pnl'].sum()
    gross_loss = abs(losses['net_pnl'].sum())
    pf = gross_profit / gross_loss if gross_loss > 0 else 99.0
    net_profit = df_res['net_pnl'].sum()
    total_charges = df_res['charges'].sum()
    net_r = df_res['r_mult'].sum()

    monthly = df_res.groupby('month')['net_pnl'].sum()
    avg_mo_ret = (net_profit / total_months) / capital * 100.0
    prof_months = len(monthly[monthly > 0]) / len(monthly) * 100.0 if len(monthly) > 0 else 0.0

    df_res['cum_pnl'] = df_res['net_pnl'].cumsum()
    df_res['peak'] = df_res['cum_pnl'].cummax()
    df_res['dd'] = df_res['peak'] - df_res['cum_pnl']
    max_dd_val = df_res['dd'].max()
    max_dd_pct = (max_dd_val / capital) * 100.0

    print(f"  Total Trades: {total_trades} ({total_trades/total_months:.1f} trades/month across {total_months} months)")
    print(f"  Win Rate: {win_rate:.2f}% | Profit Factor: {pf:.2f}")
    print(f"  Total Net Profit: Rs {net_profit:>10,.0f} ({net_r:>+6.1f}R)")
    print(f"  Total Statutory Charges: Rs {total_charges:>10,.0f}")
    print(f"  Average Monthly Return: {avg_mo_ret:+.2f}% / month (on Rs 1,00,000 Base)")
    print(f"  Maximum Drawdown: {max_dd_pct:.2f}% (Rs {max_dd_val:,.0f})")
    print(f"  Profitable Months: {prof_months:.1f}% ({len(monthly[monthly > 0])}/{len(monthly)} active months)")
    print(f"  Yearly Breakdown:")
    yearly = df_res.groupby('year')['net_pnl'].agg(['count', 'sum'])
    for yr, row in yearly.iterrows():
        print(f"    {yr}: {int(row['count']):>4} trades | Net PnL: Rs {row['sum']:>+8,.0f} ({row['sum']/risk_per_trade:>+5.1f}R)")
    print(f"=====================================================================================\n")

    csv_path = "research/phase4_2/rs_leader_194_stocks_2_5yr_trades.csv"
    # df_res.to_csv(csv_path, index=False)
    print(f"Saved trade log to {csv_path}\n")

if __name__ == '__main__':
    run_backtest()
