import sys
sys.path.append('engine')
import os
import pandas as pd
import numpy as np
import datetime
from datetime import time
from nifty_alpha_explorer import load_nifty_fast, resample_nifty, extract_all_daily_ifvgs
from fib_sr_master_engine import load_data_fast

def test_nifty_stock_ensemble():
    print("="*85)
    print("   QUANT AUDIT: NIFTY + TOP SECTOR HEAVYWEIGHTS ENSEMBLE (2022-2026)")
    print("   Testing if Cross-Asset Diversification increases R and lowers Drawdown")
    print("="*85)

    # 1. Load Nifty 1m and pre-compute 2m/15m IFVG
    nifty_1m = load_nifty_fast()
    print("Pre-computing Nifty 15m...")
    nifty_15m = resample_nifty(nifty_1m, 15)
    nifty_15m_signals = extract_all_daily_ifvgs(nifty_15m, 15)

    print("Pre-computing Nifty 2m...")
    nifty_2m = resample_nifty(nifty_1m, 2)
    nifty_2m_signals = extract_all_daily_ifvgs(nifty_2m, 2)

    # 2. Load Top Major Stocks (Sector Leaders)
    top_stocks = ['RELIANCE', 'TCS', 'HDFCBANK', 'ICICIBANK', 'INFY', 'BHARTIARTL', 'LT', 'SBIN']
    stock_data = load_data_fast(top_stocks)

    all_dates = sorted(stock_data['RELIANCE'].keys())
    print(f"Total Trading Days in Ensemble: {len(all_dates)}")

    # We will test several ensemble models:
    # Ensemble 1: Nifty 15m (Conservative, -12R DD) + Top 1 Catalyst Stock (Max 2 trades/day, 1-Loss Stop)
    # Ensemble 2: Nifty 2m (High Return, +147R) + Top 1 Catalyst Stock (Max 2 trades/day, 1-Loss Stop)
    # Ensemble 3: Nifty 15m + Top 2 Catalyst Stocks (Max 3 trades/day, 1-Loss Stop)
    # Ensemble 4: Nifty 2m + Top 2 Catalyst Stocks (Max 3 trades/day, 1-Loss Stop)
    # Ensemble 5: Unconstrained (Nifty + Top Stocks, Max 2 trades/day, 2-Loss Stop)

    ensemble_configs = [
        ("Ensemble A: Nifty 15m (Low DD) + 1 Stock (Max 2 trades/day, 1-Loss Stop, RR 1:3.0)", '15m', 1, 1, 3.0),
        ("Ensemble B: Nifty 2m (High Return) + 1 Stock (Max 2 trades/day, 1-Loss Stop, RR 1:3.0)", '2m', 1, 1, 3.0),
        ("Ensemble C: Nifty 15m + Top 2 Stocks (Max 3 trades/day, 1-Loss Stop, RR 1:3.0)", '15m', 2, 1, 3.0),
        ("Ensemble D: Nifty 2m + Top 2 Stocks (Max 3 trades/day, 1-Loss Stop, RR 1:3.0)", '2m', 2, 1, 3.0),
        ("Ensemble E: Nifty 15m + 1 Stock (Max 2 trades/day, 1-Loss Stop, RR 1:2.5)", '15m', 1, 1, 2.5),
        ("Ensemble F: Nifty 2m + 1 Stock (Max 2 trades/day, 1-Loss Stop, RR 1:2.5)", '2m', 1, 1, 2.5),
        ("Ensemble G: Nifty 15m + 1 Stock (No circuit breaker, Max 2 trades/day, RR 1:3.0)", '15m', 1, 2, 3.0),
    ]

    for cfg_name, nifty_tf, max_stock_trades, max_day_losses, target_rr in ensemble_configs:
        nifty_daily = nifty_15m_signals if nifty_tf == '15m' else nifty_2m_signals
        max_day_trades = 1 + max_stock_trades

        portfolio_trades = []

        for dt in all_dates:
            day_trades = 0
            day_losses = 0

            # -------------------------------------------------------------
            # STEP A: Check NIFTY Trade
            # -------------------------------------------------------------
            if dt in nifty_daily and nifty_daily[dt]['signals'] and day_trades < max_day_trades and day_losses < max_day_losses:
                day_data = nifty_daily[dt]
                sig = day_data['signals'][0] # 1st IFVG of the day
                if sig['time'] < time(14, 0):
                    entry = sig['entry']
                    direction = sig['dir']
                    highs, lows, closes, times, n = day_data['highs'], day_data['lows'], day_data['closes'], day_data['times'], day_data['n']

                    if direction == 'BUY':
                        raw_sl = sig['box_min'] - 2.0
                        sl_dist = max(entry - raw_sl, entry * 0.0020)
                        sl = entry - sl_dist
                        if sl_dist <= entry * 0.0060:
                            tp = entry + (sl_dist * target_rr)
                            final_r = None
                            for m in range(sig['bar'] + 1, n):
                                if lows[m] <= sl: final_r = -1.04; break
                                if highs[m] >= tp: final_r = round(target_rr - 0.04, 2); break
                                if times[m] >= time(15, 15): final_r = round((closes[m] - entry)/sl_dist - 0.04, 2); break
                            if final_r is not None:
                                portfolio_trades.append({'Date': dt, 'Time': sig['time'], 'Asset': 'NIFTY', 'R': final_r})
                                day_trades += 1
                                if final_r < 0: day_losses += 1

                    elif direction == 'SELL':
                        raw_sl = sig['box_max'] + 2.0
                        sl_dist = max(raw_sl - entry, entry * 0.0020)
                        sl = entry + sl_dist
                        if sl_dist <= entry * 0.0060:
                            tp = entry - (sl_dist * target_rr)
                            final_r = None
                            for m in range(sig['bar'] + 1, n):
                                if highs[m] >= sl: final_r = -1.04; break
                                if lows[m] <= tp: final_r = round(target_rr - 0.04, 2); break
                                if times[m] >= time(15, 15): final_r = round((entry - closes[m])/sl_dist - 0.04, 2); break
                            if final_r is not None:
                                portfolio_trades.append({'Date': dt, 'Time': sig['time'], 'Asset': 'NIFTY', 'R': final_r})
                                day_trades += 1
                                if final_r < 0: day_losses += 1

            # -------------------------------------------------------------
            # STEP B: Check Top Major Stocks (High-Catalyst Catalyst FVG)
            # -------------------------------------------------------------
            if day_trades < max_day_trades and day_losses < max_day_losses:
                # Rank stocks by RVOL / Gap Catalyst
                cands = []
                for sym in top_stocks:
                    if dt not in stock_data[sym]: continue
                    d = stock_data[sym][dt]
                    if d['len'] < 100 or pd.isna(d['PDC']) or d['PDC'] <= 0: continue

                    pdc = d['PDC']
                    o15 = d['Open'][0]
                    gap_pct = abs(o15 - pdc) / pdc
                    v15 = np.sum(d['Volume'][:15])
                    vol_ma = d['VolMA']
                    rvol = (v15 / (vol_ma / 25.0)) if vol_ma and vol_ma > 0 else 1.0

                    if rvol >= 1.5 or gap_pct >= 0.006:
                        score = rvol * 2.0 + gap_pct * 100
                        cands.append({'symbol': sym, 'data': d, 'ib_h': np.max(d['High'][:15]), 'ib_l': np.min(d['Low'][:15]), 'score': score})

                cands.sort(key=lambda x: x['score'], reverse=True)

                stock_trades_taken = 0
                for cand in cands[:3]:
                    if day_trades >= max_day_trades or day_losses >= max_day_losses or stock_trades_taken >= max_stock_trades: break
                    sym = cand['symbol']
                    d = cand['data']
                    ib_h = cand['ib_h']

                    # Scan for Bullish FVG above VWAP & IBH (09:30 to 12:00)
                    for i in range(15, min(d['len'] - 15, 160)):
                        if day_trades >= max_day_trades or day_losses >= max_day_losses or stock_trades_taken >= max_stock_trades: break
                        c_c = d['Close'][i]
                        c_low = d['Low'][i]
                        p2_h = d['High'][i-2]
                        c_vwap = d['VWAP'][i]

                        if c_low > p2_h and c_c > c_vwap and c_c > ib_h:
                            entry = c_c
                            raw_sl = min(p2_h, c_vwap) - (entry * 0.0004)
                            sl_dist = entry - raw_sl
                            min_sl = entry * 0.0020 # Enforce min 0.20%
                            if sl_dist < min_sl:
                                sl_dist = min_sl
                                sl = entry - sl_dist
                            else:
                                sl = raw_sl

                            if sl_dist <= entry * 0.0045:
                                tp = entry + (sl_dist * target_rr)
                                final_r = None
                                for m in range(i + 1, d['len']):
                                    if d['Low'][m] <= sl: final_r = -1.04; break
                                    if d['High'][m] >= tp: final_r = round(target_rr - 0.04, 2); break
                                    if d['Time'][m] >= time(15, 15): final_r = round((d['Close'][m] - entry)/sl_dist - 0.04, 2); break
                                if final_r is not None:
                                    portfolio_trades.append({'Date': dt, 'Time': d['Time'][i], 'Asset': sym, 'R': final_r})
                                    day_trades += 1
                                    stock_trades_taken += 1
                                    if final_r < 0: day_losses += 1
                                    break

        # Calculate Portfolio Metrics
        df_p = pd.DataFrame(portfolio_trades).sort_values('Date').reset_index(drop=True)
        if len(df_p) == 0: continue

        df_p['Date'] = pd.to_datetime(df_p['Date'])
        df_p['YM'] = df_p['Date'].dt.to_period('M')

        tot_trades = len(df_p)
        tot_r = df_p['R'].sum()
        num_m = df_p['YM'].nunique()
        r_m = tot_r / num_m if num_m > 0 else 0
        cum = df_p['R'].cumsum()
        max_dd = (cum - cum.cummax()).min()
        wr = (df_p['R'] > 0).mean() * 100
        wins = df_p[df_p['R'] > 0]['R'].sum()
        losses = abs(df_p[df_p['R'] < 0]['R'].sum())
        pf = (wins / losses) if losses > 0 else 999.0

        nifty_cnt = (df_p['Asset'] == 'NIFTY').sum()
        stock_cnt = tot_trades - nifty_cnt

        print(f"\n---> {cfg_name}")
        print(f"     Trades: {tot_trades:4d} (Nifty: {nifty_cnt}, Stocks: {stock_cnt}) | Trades/Month: {tot_trades/num_m:.1f}")
        print(f"     WinRate: {wr:4.1f}% | Profit Factor: {pf:.2f}")
        print(f"     TOTAL REALIZED RETURN : {tot_r:+7.1f} R")
        print(f"     AVERAGE MONTHLY RETURN: {r_m:+5.2f} R / month")
        print(f"     MAXIMUM DRAWDOWN      : {max_dd:5.1f} R")

if __name__ == '__main__':
    test_nifty_stock_ensemble()
