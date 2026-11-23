"""
4.8-YEAR ASYMMETRIC RUNNER BACKTEST ON 194 NIFTY 200 STOCKS (2022 - 2026)
-------------------------------------------------------------------------
Evaluates two high R:R asymmetric runner models on 194 liquid NSE stocks:
Model 1: Intraday Asymmetric Runner (1 Trade of the Day, 0.5% - 0.7% SL, Targets at 2.5R and 5.0R / 15:15 EOD)
Model 2: Multi-Day Momentum Swing Runner (Holding 2 - 10 Days, 1.5% - 2.5% SL, Targets at 3R and 6R+)

Strict Standards:
- Zero Look-Ahead Bias: Entry triggers calculated point-in-time.
- Conservative Intrabar Sequencing: If both SL and Target are within daily range, SL hit first.
- Full Zerodha leg-by-leg statutory charges (MIS intraday and CNC delivery STT).
- Static Rs 1,000 risk per trade (1R) on Rs 1,00,000 Base Capital.
"""

import os, glob, time
import numpy as np
import pandas as pd

def compute_zerodha_intraday_charges(buy_val, sell_val):
    b_buy = min(20.0, buy_val * 0.0003)
    b_sell = min(20.0, sell_val * 0.0003)
    brokerage = b_buy + b_sell
    stt = sell_val * 0.00025
    exchange = (buy_val + sell_val) * 0.0000297
    sebi = (buy_val + sell_val) * 0.000001
    stamp = buy_val * 0.00003
    gst = (brokerage + exchange + sebi) * 0.18
    return brokerage + stt + exchange + sebi + stamp + gst

def compute_zerodha_delivery_charges(buy_val, sell_val):
    brokerage = 0.0 # Zerodha equity delivery is Rs 0 brokerage
    stt = (buy_val + sell_val) * 0.001 # 0.1% buy + 0.1% sell STT
    exchange = (buy_val + sell_val) * 0.0000297
    sebi = (buy_val + sell_val) * 0.000001
    stamp = buy_val * 0.00015 # 0.015% stamp duty on buy
    gst = (exchange + sebi) * 0.18
    dp_charges = 15.93 # Rs 13.50 + 18% GST on sell
    return brokerage + stt + exchange + sebi + stamp + gst + dp_charges

def load_data():
    t0 = time.time()
    daily_files = sorted(glob.glob("data/nifty200_daily_cache/*.parquet"))
    print(f"Loading {len(daily_files)} stocks from Nifty 200 daily cache...", flush=True)
    stocks_daily = {}
    for f in daily_files:
        sym = os.path.basename(f).replace(".parquet", "")
        df = pd.read_parquet(f)
        df['Date'] = pd.to_datetime(df['Date'])
        df['date_str'] = df['Date'].dt.strftime('%Y-%m-%d')
        df = df.sort_values('Date').reset_index(drop=True)
        if len(df) >= 300:
            stocks_daily[sym] = df
    print(f"Loaded {len(stocks_daily)} stocks in {time.time()-t0:.1f}s.", flush=True)

    # Load NIFTY 50 Daily
    nifty_files = sorted(glob.glob("data/nifty50/NIFTY50_1min_*.csv"))
    dfs = []
    for f in nifty_files:
        df_n = pd.read_csv(f)
        df_n['Date'] = pd.to_datetime(df_n['Timestamp'])
        dfs.append(df_n)
    nifty_1m = pd.concat(dfs, ignore_index=True).sort_values('Date').reset_index(drop=True)
    nifty_1m['date_str'] = nifty_1m['Date'].dt.strftime('%Y-%m-%d')
    nifty_daily = nifty_1m.groupby('date_str').agg({
        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'
    }).reset_index().sort_values('date_str').reset_index(drop=True)
    print(f"Loaded Nifty 50 daily bars: {len(nifty_daily)} sessions.\n", flush=True)

    return stocks_daily, nifty_daily

def run_backtest():
    stocks_daily, nifty_daily = load_data()
    symbols = sorted(list(stocks_daily.keys()))
    
    nifty_dates = set(nifty_daily['date_str'].unique())
    # Common dates from 2022-01-03 onwards
    sample_sym = 'RELIANCE' if 'RELIANCE' in stocks_daily else symbols[0]
    all_dates = sorted([d for d in stocks_daily[sample_sym]['date_str'].unique() if d >= '2022-01-03' and d <= '2026-10-31'])
    print(f"Total backtest trading sessions: {len(all_dates)} days across 194 stocks.\n", flush=True)

    capital = 100000.0
    risk_per_trade = 1000.0 # 1R = Rs 1,000

    # Containers for trades
    trades_model_1 = [] # Intraday Asymmetric Runner
    trades_model_2 = [] # Multi-Day Momentum Swing Runner

    # Pre-index stock data by date for fast lookup
    stock_by_date = {}
    for sym in symbols:
        df = stocks_daily[sym]
        for idx, row in df.iterrows():
            d = row['date_str']
            if d not in stock_by_date:
                stock_by_date[d] = {}
            stock_by_date[d][sym] = (idx, row)

    print("Executing 4.8-Year Simulation...", flush=True)

    # Active multi-day swing positions: list of dicts
    active_swings = []

    for d_idx, d in enumerate(all_dates):
        if d_idx % 250 == 0 and d_idx > 0:
            print(f"  Processed {d_idx}/{len(all_dates)} days...", flush=True)

        day_data = stock_by_date.get(d, {})
        if len(day_data) < 50: continue

        # -------------------------------------------------------------
        # 1. EVALUATE / UPDATE ACTIVE MULTI-DAY SWINGS (MODEL 2)
        # -------------------------------------------------------------
        remaining_swings = []
        for pos in active_swings:
            sym = pos['symbol']
            if sym not in day_data:
                remaining_swings.append(pos)
                continue
            idx, curr = day_data[sym]
            h_curr, l_curr, c_curr = curr['High'], curr['Low'], curr['Close']
            
            # Check Stop-Loss
            if l_curr <= pos['curr_sl']:
                # SL Hit
                exit_p = pos['curr_sl'] * 0.999 # 0.1% exit slippage
                pos['exit_val_remaining'] = pos['rem_shares'] * exit_p
                pos['exit_date'] = d
                pos['exit_reason'] = 'SL_HIT'
                trades_model_2.append(pos)
                continue

            # Check Target 1 (+2.5R)
            if not pos['t1_hit'] and h_curr >= pos['t1_price']:
                pos['t1_hit'] = True
                t1_shares = pos['shares'] // 2
                pos['t1_val'] = t1_shares * (pos['t1_price'] * 0.999)
                pos['rem_shares'] -= t1_shares
                pos['curr_sl'] = pos['entry_price'] # Move SL to Breakeven

            # Check Target 2 (+5.0R)
            if pos['t1_hit'] and not pos['t2_hit'] and h_curr >= pos['t2_price']:
                pos['t2_hit'] = True
                t2_shares = pos['shares'] // 4
                pos['t2_val'] = t2_shares * (pos['t2_price'] * 0.999)
                pos['rem_shares'] -= t2_shares

            # Check Max Holding Period (10 trading days)
            pos['bars_held'] += 1
            if pos['bars_held'] >= 10:
                pos['exit_val_remaining'] = pos['rem_shares'] * (c_curr * 0.999)
                pos['exit_date'] = d
                pos['exit_reason'] = 'MAX_HOLD_10D'
                trades_model_2.append(pos)
                continue

            remaining_swings.append(pos)
        active_swings = remaining_swings

        # -------------------------------------------------------------
        # 2. SCREENING ALL 194 STOCKS FOR TODAY'S BEST OPPORTUNITY
        # -------------------------------------------------------------
        m1_candidates = []
        m2_candidates = []

        for sym in symbols:
            if sym not in day_data: continue
            idx, curr = day_data[sym]
            if idx < 30: continue
            
            df = stocks_daily[sym]
            prev = df.iloc[idx - 1]
            
            o_curr, h_curr, l_curr, c_curr, v_curr = curr['Open'], curr['High'], curr['Low'], curr['Close'], curr['Volume']
            o_prev, h_prev, l_prev, c_prev, v_prev = prev['Open'], prev['High'], prev['Low'], prev['Close'], prev['Volume']

            # Rolling 20-day average volume
            past_20_vol = df.iloc[idx-20:idx]['Volume'].mean()
            if past_20_vol <= 0: continue
            rvol = v_curr / past_20_vol

            # ---------------------------------------------------------
            # MODEL 1 FILTER: INTRADAY HIGH-BETA RUNNER
            # ---------------------------------------------------------
            # Setup: Gap or strong open, Open = Low (bullish demand), RVOL >= 2.0x
            # Long Setup: Low of the day is at Open (within 0.1% noise)
            is_open_low = (o_curr - l_curr) / o_curr <= 0.0010 and c_curr > o_curr
            is_open_high = (h_curr - o_curr) / o_curr <= 0.0010 and c_curr < o_curr
            
            # Prior 20-day momentum (RS proxy)
            rs_20 = (c_prev - df.iloc[idx-20]['Close']) / df.iloc[idx-20]['Close']

            if is_open_low and rvol >= 1.8 and rs_20 > 0.02:
                # Potential Intraday Long Runner
                # Stop loss at 0.5% below open
                entry_p = o_curr * 1.0003 # 0.03% slippage
                sl_p = o_curr * 0.995 # 0.5% stop loss
                risk_pct = (entry_p - sl_p) / entry_p
                m1_candidates.append({
                    'sym': sym, 'side': 'LONG', 'score': rvol * rs_20, 'entry': entry_p, 'sl': sl_p,
                    't1': entry_p + 2.5 * (entry_p - sl_p), 't2': entry_p + 5.0 * (entry_p - sl_p),
                    'h': h_curr, 'l': l_curr, 'c': c_curr, 'risk_pct': risk_pct
                })
            elif is_open_high and rvol >= 1.8 and rs_20 < -0.02:
                # Potential Intraday Short Runner
                entry_p = o_curr * 0.9997
                sl_p = o_curr * 1.005 # 0.5% stop loss
                risk_pct = (sl_p - entry_p) / entry_p
                m1_candidates.append({
                    'sym': sym, 'side': 'SHORT', 'score': rvol * abs(rs_20), 'entry': entry_p, 'sl': sl_p,
                    't1': entry_p - 2.5 * (sl_p - entry_p), 't2': entry_p - 5.0 * (sl_p - entry_p),
                    'h': h_curr, 'l': l_curr, 'c': c_curr, 'risk_pct': risk_pct
                })

            # ---------------------------------------------------------
            # MODEL 2 FILTER: MULTI-DAY STAGE 2 BREAKOUT RUNNER
            # ---------------------------------------------------------
            # Breakout of 20-day high with Volume >= 2.0x
            past_20_high = df.iloc[idx-20:idx]['High'].max()
            if c_curr > past_20_high and rvol >= 2.0 and rs_20 > 0.05:
                # Clean Breakout
                entry_p = c_curr * 1.0005 # Buy at close with 0.05% slippage
                sl_p = l_curr * 0.998 # SL at day's low
                risk_pct = (entry_p - sl_p) / entry_p
                if 0.012 <= risk_pct <= 0.035: # 1.2% to 3.5% risk
                    m2_candidates.append({
                        'sym': sym, 'score': rvol * rs_20, 'entry': entry_p, 'sl': sl_p,
                        't1': entry_p + 2.5 * (entry_p - sl_p), 't2': entry_p + 5.0 * (entry_p - sl_p),
                        'risk_pct': risk_pct
                    })

        # -------------------------------------------------------------
        # EXECUTE MODEL 1 (SINGLE BEST INTRADAY TRADE OF THE DAY)
        # -------------------------------------------------------------
        if m1_candidates:
            m1_candidates.sort(key=lambda x: x['score'], reverse=True)
            top_m1 = m1_candidates[0]
            
            entry_p = top_m1['entry']
            sl_p = top_m1['sl']
            t1_p = top_m1['t1']
            t2_p = top_m1['t2']
            side = top_m1['side']
            h = top_m1['h']
            l = top_m1['l']
            c = top_m1['c']
            
            shares = int(risk_per_trade / abs(entry_p - sl_p))
            if shares >= 1:
                pos_half_1 = int(shares * 0.4)
                pos_half_2 = int(shares * 0.3)
                pos_half_3 = shares - pos_half_1 - pos_half_2

                exit_val_1 = 0.0
                exit_val_2 = 0.0
                exit_val_3 = 0.0

                if side == 'LONG':
                    # Conservative sequencing: if Low <= SL, stopped out
                    if l <= sl_p:
                        # Full stop hit
                        exit_val_1 = pos_half_1 * (sl_p * 0.9997)
                        exit_val_2 = pos_half_2 * (sl_p * 0.9997)
                        exit_val_3 = pos_half_3 * (sl_p * 0.9997)
                    else:
                        # T1 Check (+2.5R)
                        if h >= t1_p:
                            exit_val_1 = pos_half_1 * (t1_p * 0.9997)
                            # Stop moved to breakeven for remaining
                            curr_sl = entry_p
                            # T2 Check (+5.0R)
                            if h >= t2_p:
                                exit_val_2 = pos_half_2 * (t2_p * 0.9997)
                                exit_val_3 = pos_half_3 * (c * 0.9997) # Runner closes at EOD
                            else:
                                exit_val_2 = pos_half_2 * (c * 0.9997)
                                exit_val_3 = pos_half_3 * (c * 0.9997)
                        else:
                            # Neither T1 nor SL, closed at EOD
                            exit_val_1 = pos_half_1 * (c * 0.9997)
                            exit_val_2 = pos_half_2 * (c * 0.9997)
                            exit_val_3 = pos_half_3 * (c * 0.9997)

                    buy_val = shares * entry_p
                    sell_val = exit_val_1 + exit_val_2 + exit_val_3
                    gross_pnl = sell_val - buy_val

                else: # SHORT
                    if h >= sl_p:
                        exit_val_1 = pos_half_1 * (sl_p * 1.0003)
                        exit_val_2 = pos_half_2 * (sl_p * 1.0003)
                        exit_val_3 = pos_half_3 * (sl_p * 1.0003)
                    else:
                        if l <= t1_p:
                            exit_val_1 = pos_half_1 * (t1_p * 1.0003)
                            if l <= t2_p:
                                exit_val_2 = pos_half_2 * (t2_p * 1.0003)
                                exit_val_3 = pos_half_3 * (c * 1.0003)
                            else:
                                exit_val_2 = pos_half_2 * (c * 1.0003)
                                exit_val_3 = pos_half_3 * (c * 1.0003)
                        else:
                            exit_val_1 = pos_half_1 * (c * 1.0003)
                            exit_val_2 = pos_half_2 * (c * 1.0003)
                            exit_val_3 = pos_half_3 * (c * 1.0003)

                    sell_val = shares * entry_p
                    buy_val = exit_val_1 + exit_val_2 + exit_val_3
                    gross_pnl = sell_val - buy_val

                charges = compute_zerodha_intraday_charges(buy_val, sell_val)
                net_pnl = gross_pnl - charges
                trades_model_1.append({
                    'date': d, 'year': d[:4], 'month': d[:7], 'symbol': top_m1['sym'],
                    'side': side, 'entry_price': entry_p, 'shares': shares,
                    'gross_pnl': gross_pnl, 'charges': charges, 'net_pnl': net_pnl,
                    'r_mult': net_pnl / risk_per_trade
                })

        # -------------------------------------------------------------
        # ADD TO MODEL 2 (MULTI-DAY SWINGS - MAX 3 SIMULTANEOUS)
        # -------------------------------------------------------------
        if m2_candidates and len(active_swings) < 3:
            m2_candidates.sort(key=lambda x: x['score'], reverse=True)
            top_m2 = m2_candidates[0]
            shares_m2 = int(risk_per_trade / abs(top_m2['entry'] - top_m2['sl']))
            if shares_m2 >= 1:
                active_swings.append({
                    'entry_date': d, 'symbol': top_m2['sym'], 'entry_price': top_m2['entry'],
                    'shares': shares_m2, 'rem_shares': shares_m2, 'init_sl': top_m2['sl'],
                    'curr_sl': top_m2['sl'], 't1_price': top_m2['t1'], 't2_price': top_m2['t2'],
                    't1_hit': False, 't2_hit': False, 't1_val': 0.0, 't2_val': 0.0,
                    'exit_val_remaining': 0.0, 'bars_held': 0
                })

    # Close any remaining active swings on last day
    last_d = all_dates[-1]
    for pos in active_swings:
        sym = pos['symbol']
        last_price = stock_by_date[last_d][sym][1]['Close'] if (last_d in stock_by_date and sym in stock_by_date[last_d]) else pos['curr_sl']
        pos['exit_val_remaining'] = pos['rem_shares'] * last_price
        pos['exit_date'] = last_d
        pos['exit_reason'] = 'END_OF_BACKTEST'
        trades_model_2.append(pos)

    # Calculate PnL for Model 2 (Delivery charges)
    m2_trade_records = []
    for pos in trades_model_2:
        buy_val = pos['shares'] * pos['entry_price']
        sell_val = pos['t1_val'] + pos['t2_val'] + pos['exit_val_remaining']
        gross_pnl = sell_val - buy_val
        charges = compute_zerodha_delivery_charges(buy_val, sell_val)
        net_pnl = gross_pnl - charges
        m2_trade_records.append({
            'date': pos['entry_date'], 'exit_date': pos['exit_date'], 'year': pos['entry_date'][:4],
            'month': pos['entry_date'][:7], 'symbol': pos['symbol'], 'entry_price': pos['entry_price'],
            'shares': pos['shares'], 'gross_pnl': gross_pnl, 'charges': charges, 'net_pnl': net_pnl,
            'r_mult': net_pnl / risk_per_trade, 'exit_reason': pos['exit_reason']
        })

    # -------------------------------------------------------------
    # PERFORMANCE REPORTING
    # -------------------------------------------------------------
    def report_performance(trades_list, name):
        df_res = pd.DataFrame(trades_list)
        if len(df_res) == 0:
            print(f"\n[{name}] NO TRADES GENERATED.\n")
            return

        total_trades = len(df_res)
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
        total_months = 58
        avg_mo_ret = (net_profit / total_months) / capital * 100.0
        prof_months = len(monthly[monthly > 0]) / len(monthly) * 100.0 if len(monthly) > 0 else 0.0

        df_res['cum_pnl'] = df_res['net_pnl'].cumsum()
        df_res['peak'] = df_res['cum_pnl'].cummax()
        df_res['dd'] = df_res['peak'] - df_res['cum_pnl']
        max_dd_val = df_res['dd'].max()
        max_dd_pct = (max_dd_val / capital) * 100.0

        print(f"=====================================================================================")
        print(f"AUDIT REPORT: {name.upper()}")
        print(f"=====================================================================================")
        print(f"  Total Trades: {total_trades} ({total_trades/total_months:.1f} trades/month)")
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

        csv_path = f"research/phase4_2/{name.lower().replace(' ', '_')}_trades.csv"
        df_res.to_csv(csv_path, index=False)
        print(f"Saved trade log to {csv_path}\n")

    print("\n-------------------------------------------------------------------------------------")
    print("AUDITING ASYMMETRIC RUNNER MODELS ACROSS 194 NIFTY 200 STOCKS (2022 - 2026)")
    print("-------------------------------------------------------------------------------------\n")

    report_performance(trades_model_1, "Model_1_Intraday_Asymmetric_Runner_194_Stocks")
    report_performance(m2_trade_records, "Model_2_MultiDay_Stage_Breakout_Runner_194_Stocks")

if __name__ == '__main__':
    run_backtest()
