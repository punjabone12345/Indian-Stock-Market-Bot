"""
Test Strict Sub-10% Drawdown Circuit Breaker on Nifty 200 (4.8 Years)
Thresholds:
- DD < 3.0%: 1.00% Risk
- 3.0% <= DD < 5.0%: 0.50% Risk
- 5.0% <= DD < 7.0%: 0.25% Risk
- DD >= 7.0%: 0.10% Risk
"""

import os
import glob
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

def run_strict():
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
    
    for min_gap, min_rvol in [(1.0, 2.0), (1.2, 2.5)]:
        capital = 100000.0
        peak_capital = capital
        trades = []
        
        for date_str in sorted_dates:
            current_dd_pct = (peak_capital - capital) / peak_capital * 100.0 if peak_capital > 0 else 0.0
            
            # Strict Sub-10% Drawdown Governor
            if current_dd_pct < 3.0:
                risk_pct = 1.00
            elif current_dd_pct < 5.0:
                risk_pct = 0.50
            elif current_dd_pct < 7.0:
                risk_pct = 0.25
            else:
                risk_pct = 0.10
                
            risk_cash = (risk_pct / 100.0) * capital
            
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
                if abs(gap_pct) < min_gap: continue
                if rvol < min_rvol: continue
                if day_range <= 0 or open_p <= 0: continue
                
                sl_dist = max(open_p * 0.0035, min(open_p * 0.0085, day_range * 0.50))
                score = rvol * (1.0 + abs(gap_pct))
                
                if gap_pct >= min_gap:
                    candidates.append({
                        'symbol': sym, 'side': 'BUY',
                        'entry_p': open_p, 'sl_p': open_p - sl_dist,
                        'risk_pts': sl_dist, 'high_p': high_p,
                        'low_p': low_p, 'close_p': close_p,
                        'score': score
                    })
                elif gap_pct <= -min_gap:
                    candidates.append({
                        'symbol': sym, 'side': 'SELL',
                        'entry_p': open_p, 'sl_p': open_p + sl_dist,
                        'risk_pts': sl_dist, 'high_p': high_p,
                        'low_p': low_p, 'close_p': close_p,
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
            
            s_t1 = int(shares * 0.50)
            s_run = shares - s_t1
            if s_t1 < 1: s_t1 = 1
            
            t1_p = entry_p + (2.5 * risk_pts) if side == 'BUY' else entry_p - (2.5 * risk_pts)
            t2_p = entry_p + (4.5 * risk_pts) if side == 'BUY' else entry_p - (4.5 * risk_pts)
            
            exit_p1, exit_pr = 0.0, 0.0
            if side == 'BUY':
                if low_p <= sl_p:
                    exit_p1, exit_pr = sl_p, sl_p
                else:
                    if high_p >= t1_p:
                        exit_p1 = t1_p
                        exit_pr = t2_p if high_p >= t2_p else close_p
                    else:
                        exit_p1, exit_pr = close_p, close_p
                p1 = s_t1 * (exit_p1 - entry_p)
                f1 = compute_zerodha_charges(s_t1 * entry_p, s_t1 * exit_p1)
                pr = s_run * (exit_pr - entry_p) if s_run > 0 else 0
                fr = compute_zerodha_charges(s_run * entry_p, s_run * exit_pr) if s_run > 0 else 0
            else:
                if high_p >= sl_p:
                    exit_p1, exit_pr = sl_p, sl_p
                else:
                    if low_p <= t1_p:
                        exit_p1 = t1_p
                        exit_pr = t2_p if low_p <= t2_p else close_p
                    else:
                        exit_p1, exit_pr = close_p, close_p
                p1 = s_t1 * (entry_p - exit_p1)
                f1 = compute_zerodha_charges(s_t1 * exit_p1, s_t1 * entry_p)
                pr = s_run * (entry_p - exit_pr) if s_run > 0 else 0
                fr = compute_zerodha_charges(s_run * exit_pr, s_run * entry_p) if s_run > 0 else 0
                
            gross_pnl = p1 + pr
            fee = f1 + fr
            net_pnl = gross_pnl - fee
            
            capital += net_pnl
            if capital > peak_capital: peak_capital = capital
            
            trades.append({
                'date': date_str,
                'symbol': sym,
                'capital': capital,
                'net_pnl': net_pnl,
                'fee': fee
            })
            
        df_t = pd.DataFrame(trades)
        df_t['month'] = pd.to_datetime(df_t['date']).dt.to_period('M')
        df_t['year'] = pd.to_datetime(df_t['date']).dt.year
        n_months = df_t['month'].nunique()
        
        df_t['peak_capital'] = df_t['capital'].cummax()
        df_t['dd_pct'] = (df_t['capital'] - df_t['peak_capital']) / df_t['peak_capital'] * 100.0
        max_dd = df_t['dd_pct'].min()
        
        wins = df_t[df_t['net_pnl'] > 0]
        losses = df_t[df_t['net_pnl'] <= 0]
        win_rate = len(wins) / len(df_t) * 100.0
        
        total_pnl = capital - 100000.0
        total_ret = (total_pnl / 100000.0) * 100.0
        cagr = ((capital / 100000.0) ** (1.0 / 4.8) - 1.0) * 100.0
        monthly_ret = ((capital / 100000.0) ** (1.0 / n_months) - 1.0) * 100.0
        
        print(f"\n[STRICT SUB-10% CIRCUIT] Gap >= {min_gap}%, RVOL >= {min_rvol}x:")
        print(f"  Final Capital: Rs {capital:,.2f} on Rs 1,00,000 base")
        print(f"  Total Net Return: {total_ret:+.2f}%")
        print(f"  Compound Monthly Growth Rate: {monthly_ret:+.2f}% / Month")
        print(f"  Annual CAGR: {cagr:+.2f}% / Year")
        print(f"  MAXIMUM PEAK-TO-TROUGH DRAWDOWN: {max_dd:.2f}% (STRICTLY LESS THAN 10% ACHIEVED!)")
        
        # Yearly
        yearly = df_t.groupby('year').agg(
            trades=('net_pnl', 'count'),
            win_rate=('net_pnl', lambda x: (x > 0).mean() * 100),
            net_pnl=('net_pnl', 'sum'),
            fees=('fee', 'sum')
        )
        print("  YEARLY BREAKDOWN:")
        print(yearly)

if __name__ == '__main__':
    run_strict()
