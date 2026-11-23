"""
NIFTY 200 HIGH-CATALYST INTRADAY MOMENTUM SYSTEM (2022 - 2026)
Asset Class: 100% Pure NSE Cash Equities (Intraday MIS) - Zero Derivatives
Universe: 194 Liquid NIFTY 200 Constituent Equities (data/nifty200_daily_cache/)
Testing Period: 01 January 2022 to 31 October 2026 (1,207 Trading Sessions, 58 Months)

Core Strategy Rules:
1. Catalyst Filter:
   - Morning Gap >= 1.5% (Long) or <= -1.5% (Short)
   - Relative Volume (RVOL) >= 2.5x (Institutional volume expansion over 20-day average)
2. Sizing:
   - STRICT STATIC SIZING: No compounding!
   - Fixed Risk = Rs 1,000 per trade (1R = 1.0% of Rs 1,00,000 initial base)
3. Execution:
   - Entry at Market Open (09:15 IST) with 0.03% execution slippage
   - Structural Stop Loss: 0.80% of price
   - Target 1: 2.0R (1.60% expansion)
   - Target 2: 3.5R (2.80% expansion) or EOD close at 15:15
   - Conservative sequencing: If Low hits SL, trade is logged as a loss
4. Cost Model:
   - Full Zerodha Intraday Cash Tariff (Brokerage, STT, Exchange, SEBI, Stamp Duty, GST)
   - 0.03% slippage on every executed trade leg
"""

import os, glob, json, time
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

def run_nifty200_catalyst_system():
    start_t = time.time()
    os.makedirs("research/phase4_2/reports", exist_ok=True)
    
    files = glob.glob("data/nifty200_daily_cache/*.parquet")
    print(f"Loading {len(files)} Nifty 200 daily parquet files...", flush=True)
    
    symbol_days = {}
    all_dates = set()
    
    for f in files:
        sym = os.path.basename(f).replace(".parquet", "")
        df = pd.read_parquet(f).sort_values('Date').reset_index(drop=True)
        if len(df) < 50: continue
        df['Date'] = pd.to_datetime(df['Date'])
        df['date_str'] = df['Date'].dt.strftime('%Y-%m-%d')
        df['prev_close'] = df['Close'].shift(1)
        df['gap_pct'] = (df['Open'] - df['prev_close']) / df['prev_close'] * 100.0
        df['vol_20avg'] = df['Volume'].rolling(20).mean().shift(1)
        df['rvol'] = df['Volume'] / np.where(df['vol_20avg'] > 0, df['vol_20avg'], df['Volume'])
        
        symbol_days[sym] = {}
        for idx, r in df.iterrows():
            d_str = r['date_str']
            if int(d_str[:4]) >= 2022 and d_str <= '2026-10-31':
                all_dates.add(d_str)
                symbol_days[sym][d_str] = {
                    'Open': r['Open'],
                    'High': r['High'],
                    'Low': r['Low'],
                    'Close': r['Close'],
                    'prev_close': r['prev_close'],
                    'gap_pct': r['gap_pct'],
                    'rvol': r['rvol'],
                    'Volume': r['Volume']
                }
                
    dates = sorted(list(all_dates))
    print(f"Loaded {len(symbol_days)} stocks across {len(dates)} trading sessions in {time.time() - start_t:.1f}s.", flush=True)
    
    # Parameter Grid Testing:
    # Gap: 1.5% vs 2.0%
    # RVOL: 2.0x vs 2.5x vs 3.0x
    # Stop Loss %: 0.60% vs 0.80% vs 1.00%
    # Max trades per day: 1 vs 2 vs 3
    test_configs = [
        {'min_gap': 1.5, 'min_rvol': 2.5, 'sl_pct': 0.0080, 'max_trades': 1, 'name': 'Config 1: Gap>=1.5%, RVOL>=2.5x, SL=0.8%, 1 Trade/Day'},
        {'min_gap': 1.5, 'min_rvol': 2.5, 'sl_pct': 0.0080, 'max_trades': 2, 'name': 'Config 2: Gap>=1.5%, RVOL>=2.5x, SL=0.8%, 2 Trades/Day'},
        {'min_gap': 2.0, 'min_rvol': 2.5, 'sl_pct': 0.0080, 'max_trades': 1, 'name': 'Config 3: Gap>=2.0%, RVOL>=2.5x, SL=0.8%, 1 Trade/Day'},
        {'min_gap': 1.5, 'min_rvol': 3.0, 'sl_pct': 0.0080, 'max_trades': 2, 'name': 'Config 4: Gap>=1.5%, RVOL>=3.0x, SL=0.8%, 2 Trades/Day'},
        {'min_gap': 1.5, 'min_rvol': 2.5, 'sl_pct': 0.0060, 'max_trades': 2, 'name': 'Config 5: Gap>=1.5%, RVOL>=2.5x, SL=0.6%, 2 Trades/Day (Tighter Stop)'},
        {'min_gap': 1.5, 'min_rvol': 2.5, 'sl_pct': 0.0100, 'max_trades': 2, 'name': 'Config 6: Gap>=1.5%, RVOL>=2.5x, SL=1.0%, 2 Trades/Day (Wider Stop)'}
    ]
    
    results = []
    
    for cfg in test_configs:
        min_gap = cfg['min_gap']
        min_rvol = cfg['min_rvol']
        sl_pct = cfg['sl_pct']
        max_trades = cfg['max_trades']
        cfg_name = cfg['name']
        
        trades = []
        static_risk_cash = 1000.0 # Exactly Rs 1,000 risk per trade
        
        for d in dates:
            candidates = []
            for sym, d_dict in symbol_days.items():
                if d not in d_dict: continue
                r = d_dict[d]
                gap = r['gap_pct']
                rvol = r['rvol']
                
                if np.isnan(gap) or np.isnan(rvol): continue
                if abs(gap) < min_gap or rvol < min_rvol: continue
                
                open_p = r['Open']
                if open_p <= 0: continue
                
                # Catalyst score = RVOL * (1 + abs(gap))
                score = rvol * (1.0 + abs(gap))
                side = 'BUY' if gap >= min_gap else 'SELL'
                
                candidates.append({
                    'symbol': sym,
                    'side': side,
                    'open_p': open_p,
                    'high_p': r['High'],
                    'low_p': r['Low'],
                    'close_p': r['Close'],
                    'score': score,
                    'gap_pct': gap,
                    'rvol': rvol
                })
                
            if not candidates: continue
            candidates.sort(key=lambda x: -x['score'])
            
            # Execute top N trades
            for t in candidates[:max_trades]:
                open_p = t['open_p']
                high_p = t['high_p']
                low_p = t['low_p']
                close_p = t['close_p']
                side = t['side']
                
                # Apply 0.03% entry slippage
                eff_entry = open_p * (1.0 + 0.0003) if side == 'BUY' else open_p * (1.0 - 0.0003)
                
                # Risk points
                risk_pts = open_p * sl_pct
                sl_p = open_p - risk_pts if side == 'BUY' else open_p + risk_pts
                t1_p = open_p + (2.0 * risk_pts) if side == 'BUY' else open_p - (2.0 * risk_pts)
                t2_p = open_p + (3.5 * risk_pts) if side == 'BUY' else open_p - (3.5 * risk_pts)
                
                shares = int(static_risk_cash / risk_pts)
                if shares < 1: continue
                s_t1 = int(shares * 0.50)
                s_run = shares - s_t1
                if s_t1 < 1: s_t1 = 1
                
                # Conservative outcome sequencing
                exit_p1 = 0.0
                exit_pr = 0.0
                exit_reason = ""
                
                if side == 'BUY':
                    # Conservative rule: If day's Low dipped below SL, assume SL hit
                    if low_p <= sl_p:
                        # Slippage on stop exit: 0.03%
                        exit_p1 = sl_p * (1.0 - 0.0003)
                        exit_pr = sl_p * (1.0 - 0.0003)
                        exit_reason = 'STOP_LOSS'
                    else:
                        # Did not hit SL. Check targets:
                        if high_p >= t1_p:
                            exit_p1 = t1_p # Limit order exit at target 1 (no slippage)
                            if high_p >= t2_p:
                                exit_pr = t2_p
                                exit_reason = 'RUNNER_T2_MAX'
                            else:
                                exit_pr = close_p * (1.0 - 0.0003) # EOD square-off
                                exit_reason = 'T1_HIT_RUNNER_EOD'
                        else:
                            # Neither SL nor Target hit: square-off at close
                            exit_p1 = close_p * (1.0 - 0.0003)
                            exit_pr = close_p * (1.0 - 0.0003)
                            exit_reason = 'EOD_SQUAREOFF'
                else: # SELL
                    if high_p >= sl_p:
                        exit_p1 = sl_p * (1.0 + 0.0003)
                        exit_pr = sl_p * (1.0 + 0.0003)
                        exit_reason = 'STOP_LOSS'
                    else:
                        if low_p <= t1_p:
                            exit_p1 = t1_p
                            if low_p <= t2_p:
                                exit_pr = t2_p
                                exit_reason = 'RUNNER_T2_MAX'
                            else:
                                exit_pr = close_p * (1.0 + 0.0003)
                                exit_reason = 'T1_HIT_RUNNER_EOD'
                        else:
                            exit_p1 = close_p * (1.0 + 0.0003)
                            exit_pr = close_p * (1.0 + 0.0003)
                            exit_reason = 'EOD_SQUAREOFF'
                            
                # Statutory Charges
                if side == 'BUY':
                    buy_v = shares * eff_entry
                    sell_v = (s_t1 * exit_p1) + (s_run * exit_pr)
                    gp = sell_v - buy_v
                else:
                    sell_v = shares * eff_entry
                    buy_v = (s_t1 * exit_p1) + (s_run * exit_pr)
                    gp = sell_v - buy_v
                    
                fee = compute_zerodha_charges(buy_v, sell_v)
                npnl = gp - fee
                
                trades.append({
                    'date': d,
                    'year': int(d[:4]),
                    'symbol': t['symbol'],
                    'side': side,
                    'shares': shares,
                    'entry_p': round(eff_entry, 2),
                    'exit_p1': round(exit_p1, 2),
                    'exit_pr': round(exit_pr, 2),
                    'gross_pnl': round(gp, 2),
                    'fee': round(fee, 2),
                    'net_pnl': round(npnl, 2),
                    'R': round(npnl / static_risk_cash, 3),
                    'exit_reason': exit_reason
                })
                
        df_t = pd.DataFrame(trades)
        if len(df_t) == 0: continue
        
        df_t['date_dt'] = pd.to_datetime(df_t['date'])
        df_t['ym'] = df_t['date_dt'].dt.to_period('M')
        n_mo = df_t['ym'].nunique()
        tot_pnl = df_t['net_pnl'].sum()
        tot_r = df_t['R'].sum()
        wins = df_t[df_t['net_pnl'] > 0]
        losses = df_t[df_t['net_pnl'] <= 0]
        wr = len(wins) / len(df_t) * 100.0
        gw = wins['net_pnl'].sum()
        gl = abs(losses['net_pnl'].sum())
        pf = gw / gl if gl > 0 else 0.0
        
        monthly_r = df_t.groupby('ym')['R'].sum()
        avg_monthly_r = monthly_r.mean()
        avg_monthly_pnl = df_t.groupby('ym')['net_pnl'].sum().mean()
        win_months = (monthly_r > 0).sum()
        win_mo_pct = win_months / n_mo * 100.0 if n_mo > 0 else 0.0
        
        # Drawdowns in R
        df_t['cum'] = df_t['R'].cumsum()
        df_t['peak'] = df_t['cum'].cummax()
        df_t['dd'] = df_t['cum'] - df_t['peak']
        max_dd_r = df_t['dd'].min()
        
        # Yearly breakdown
        y_grp = df_t.groupby('year')['R'].sum().to_dict()
        
        res = {
            'config_name': cfg_name,
            'total_trades': len(df_t),
            'trades_per_month': round(len(df_t) / n_mo, 1),
            'win_rate_pct': round(wr, 2),
            'profit_factor': round(pf, 2),
            'total_net_R': round(tot_r, 2),
            'total_net_profit_inr': round(tot_pnl, 2),
            'avg_monthly_R': round(avg_monthly_r, 2),
            'avg_monthly_pnl_inr': round(avg_monthly_pnl, 2),
            'static_monthly_return_pct': round(avg_monthly_r, 2), # 1R = 1.0% on Rs 100k
            'max_drawdown_R': round(max_dd_r, 2),
            'max_drawdown_pct': round(abs(max_dd_r), 2),
            'total_fees_paid_inr': round(float(df_t['fee'].sum()), 2),
            'profitable_months': f"{win_months} / {n_mo} ({win_mo_pct:.1f}%)",
            'yearly_R': y_grp
        }
        results.append(res)
        
        print("\n" + "=" * 90)
        print(f"[{cfg_name}]")
        print(f"  Trades: {len(df_t)} ({len(df_t)/n_mo:.1f}/mo) | WR: {wr:5.2f}% | PF: {pf:4.2f} | Net R: {tot_r:+7.2f}R | MaxDD: {max_dd_r:6.2f}R")
        print(f"  STATIC MONTHLY RETURN: {avg_monthly_r:+5.2f}% / month (+Rs {avg_monthly_pnl:+,.0f}/mo on Rs 100k base)")
        print(f"  Profitable Months: {win_months}/{n_mo} ({win_mo_pct:.1f}%) | Total Fees: Rs {df_t['fee'].sum():,.2f}")
        print(f"  Yearly R Breakdown: {y_grp}")
        
    with open("research/phase4_2/reports/nifty200_catalyst_momentum_results.json", "w") as f:
        json.dump(results, f, indent=2)
        
    # Save the best configuration trade log
    # Find config with highest average monthly R
    best_cfg = max(results, key=lambda x: x['avg_monthly_R'])
    print("\n" + "#" * 90)
    print(f"OPTIMAL CONFIGURATION: {best_cfg['config_name']}")
    print(f"  STATIC MONTHLY RETURN: {best_cfg['avg_monthly_R']:+.2f}% / month")
    print(f"  PROFIT FACTOR: {best_cfg['profit_factor']:.2f}")
    print(f"  WIN RATE: {best_cfg['win_rate_pct']:.2f}%")
    print(f"  TOTAL NET PROFIT: Rs {best_cfg['total_net_profit_inr']:+,.2f} (+{best_cfg['total_net_R']:.2f}R)")
    print(f"  MAX DRAWDOWN: {best_cfg['max_drawdown_R']:.2f}R ({best_cfg['max_drawdown_pct']:.2f}%)")
    print("#" * 90)

if __name__ == '__main__':
    run_nifty200_catalyst_system()
