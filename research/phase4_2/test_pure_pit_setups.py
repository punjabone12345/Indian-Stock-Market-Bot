"""
SEARCH FOR TRUE POINT-IN-TIME INTRADAY EDGE ON NIFTY 200 (2022 - 2026)
Zero look-ahead: Absolutely NO today's volume, NO today's close, NO future information.
Only variables known at 09:15 AM:
- Today's Open (from 09:08 pre-market)
- Yesterday's Open, High, Low, Close, Volume
- Multi-day historical metrics (20-day EMA, 50-day SMA, ATR, 5-day return, yesterday's volume vs 20-day avg)
- Market breadth calculated from yesterday's close vs yesterday's 20 EMA
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

def test_pit_strategies():
    files = glob.glob("data/nifty200_daily_cache/*.parquet")
    symbol_days = {}
    daily_breadth = {}
    all_dates = set()
    
    print(f"Loading {len(files)} stocks...", flush=True)
    for f in files:
        sym = os.path.basename(f).replace(".parquet", "")
        df = pd.read_parquet(f).sort_values('Date').reset_index(drop=True)
        if len(df) < 60: continue
        df['Date'] = pd.to_datetime(df['Date'])
        df['date_str'] = df['Date'].dt.strftime('%Y-%m-%d')
        
        # Point-in-time indicators (all shifted by 1 so strictly known yesterday)
        df['prev_close'] = df['Close'].shift(1)
        df['prev_high'] = df['High'].shift(1)
        df['prev_low'] = df['Low'].shift(1)
        df['prev_vol'] = df['Volume'].shift(1)
        df['vol_20avg'] = df['Volume'].rolling(20).mean().shift(1)
        df['prev_rvol'] = df['prev_vol'] / np.where(df['vol_20avg'] > 0, df['vol_20avg'], df['prev_vol'])
        
        df['ema20'] = df['Close'].ewm(span=20, adjust=False).mean().shift(1)
        df['sma50'] = df['Close'].rolling(50).mean().shift(1)
        
        # ATR(14) shifted by 1
        tr1 = df['High'] - df['Low']
        tr2 = (df['High'] - df['Close'].shift(1)).abs()
        tr3 = (df['Low'] - df['Close'].shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['atr14'] = tr.rolling(14).mean().shift(1)
        df['atr_pct'] = df['atr14'] / df['prev_close'] * 100.0
        
        # 5-day momentum shifted by 1
        df['mom5d'] = (df['prev_close'] - df['Close'].shift(6)) / df['Close'].shift(6) * 100.0
        
        # 20-day high / low shifted by 1
        df['high_20d'] = df['High'].rolling(20).max().shift(1)
        df['low_20d'] = df['Low'].rolling(20).min().shift(1)
        
        # Today's Open known at 09:15
        df['gap_pct'] = (df['Open'] - df['prev_close']) / df['prev_close'] * 100.0
        
        mask = (df['Date'].dt.year >= 2022) & (df['date_str'] <= '2026-10-31')
        sub_df = df[mask]
        
        sym_records = {}
        for r in sub_df.itertuples(index=False):
            d_str = r.date_str
            all_dates.add(d_str)
            if d_str not in daily_breadth: daily_breadth[d_str] = []
            daily_breadth[d_str].append(1 if r.prev_close > r.ema20 else 0)
            
            sym_records[d_str] = {
                'Open': r.Open, 'High': r.High, 'Low': r.Low, 'Close': r.Close,
                'gap_pct': r.gap_pct, 'prev_rvol': r.prev_rvol, 'vol_20avg': r.vol_20avg,
                'mom5d': r.mom5d, 'high_20d': r.high_20d, 'low_20d': r.low_20d,
                'atr_pct': r.atr_pct, 'prev_close': r.prev_close, 'prev_high': r.prev_high,
                'prev_low': r.prev_low, 'ema20': r.ema20, 'sma50': r.sma50
            }
        symbol_days[sym] = sym_records
        
    dates = sorted(list(all_dates))
    market_breadth = {d: np.mean(daily_breadth[d]) * 100.0 for d in dates}
    print(f"Loaded {len(symbol_days)} stocks across {len(dates)} days.\n", flush=True)
    
    # Let's test different POINT-IN-TIME setups:
    
    configs = [
        # Setup 1: Yesterday High Breakout Gap (Gap opens above yesterday's High)
        ("1. Gap Above Yesterday High (Long only)", 'gap_above_prev_high'),
        
        # Setup 2: Gap & Trend Continuation (Gap > 1%, mom5d > 2%, Close > sma50)
        ("2. Gap + Strong Trend Continuation (mom5d > 2%, > SMA50)", 'gap_trend_continuation'),
        
        # Setup 3: Yesterday Volume Expansion + Today Gap (prev_rvol >= 2.0x, Gap >= 1.0%)
        ("3. Institutional Pre-run (Yesterday RVOL >= 2.0x + Gap >= 1.0%)", 'prev_rvol_gap'),
        
        # Setup 4: 20-day High Breakout Gap (Open > high_20d)
        ("4. 20-Day High Breakout Gap (Open > 20d High)", 'gap_20d_high'),
        
        # Setup 5: Gap Fade / Mean Reversion (Extreme Gap > 2.5%, stretched from EMA20, Short)
        ("5. Gap Fade Mean Reversion (Gap > 2.5%, Sell Short)", 'gap_fade'),
        
        # Setup 6: ATR-Normalized Gap (> 0.8 * ATR)
        ("6. ATR-Normalized Gap (Gap >= 0.8 * ATR)", 'atr_gap'),
    ]
    
    for title, mode in configs:
        trades = []
        risk_cash = 1000.0
        
        for d in dates:
            breadth = market_breadth.get(d, 50.0)
            candidates = []
            
            for sym, d_dict in symbol_days.items():
                if d not in d_dict: continue
                r = d_dict[d]
                open_p = r['Open']
                if open_p <= 0: continue
                
                gap = r['gap_pct']
                prev_high = r['prev_high']
                prev_low = r['prev_low']
                prev_close = r['prev_close']
                prev_rvol = r['prev_rvol']
                mom5d = r['mom5d']
                high_20d = r['high_20d']
                low_20d = r['low_20d']
                atr_pct = r['atr_pct']
                ema20 = r['ema20']
                sma50 = r['sma50']
                
                side = None
                score = 0.0
                
                if mode == 'gap_above_prev_high':
                    if open_p > prev_high and breadth >= 45.0:
                        side = 'BUY'
                        score = (open_p - prev_high) / prev_high * 100.0
                elif mode == 'gap_trend_continuation':
                    if gap >= 1.0 and mom5d >= 2.0 and prev_close > sma50 and breadth >= 45.0:
                        side = 'BUY'
                        score = gap * mom5d
                    elif gap <= -1.0 and mom5d <= -2.0 and prev_close < sma50 and breadth <= 55.0:
                        side = 'SELL'
                        score = abs(gap * mom5d)
                elif mode == 'prev_rvol_gap':
                    if prev_rvol >= 2.0:
                        if gap >= 1.0 and breadth >= 45.0:
                            side = 'BUY'
                            score = prev_rvol * gap
                        elif gap <= -1.0 and breadth <= 55.0:
                            side = 'SELL'
                            score = prev_rvol * abs(gap)
                elif mode == 'gap_20d_high':
                    if open_p >= high_20d and breadth >= 45.0:
                        side = 'BUY'
                        score = (open_p - high_20d) / high_20d * 100.0
                elif mode == 'gap_fade':
                    if gap >= 2.0:
                        side = 'SELL'
                        score = gap
                elif mode == 'atr_gap':
                    if atr_pct > 0:
                        norm_gap = gap / atr_pct
                        if norm_gap >= 0.75 and breadth >= 45.0:
                            side = 'BUY'
                            score = norm_gap
                        elif norm_gap <= -0.75 and breadth <= 55.0:
                            side = 'SELL'
                            score = abs(norm_gap)
                            
                if side is not None:
                    candidates.append({
                        'symbol': sym, 'side': side, 'open_p': open_p,
                        'high_p': r['High'], 'low_p': r['Low'], 'close_p': r['Close'],
                        'score': score
                    })
                    
            if not candidates: continue
            candidates.sort(key=lambda x: -x['score'])
            
            for t in candidates[:3]:
                open_p = t['open_p']
                high_p = t['high_p']
                low_p = t['low_p']
                close_p = t['close_p']
                side = t['side']
                
                eff_entry = open_p * (1.0 + 0.0003) if side == 'BUY' else open_p * (1.0 - 0.0003)
                risk_pts = open_p * 0.012
                sl_p = open_p - risk_pts if side == 'BUY' else open_p + risk_pts
                t1_p = open_p + (2.0 * risk_pts) if side == 'BUY' else open_p - (2.0 * risk_pts)
                t2_p = open_p + (4.0 * risk_pts) if side == 'BUY' else open_p - (4.0 * risk_pts)
                
                shares = int(risk_cash / risk_pts)
                if shares < 1: continue
                s_t1 = int(shares * 0.50)
                s_run = shares - s_t1
                if s_t1 < 1: s_t1 = 1
                
                if side == 'BUY':
                    if low_p <= sl_p:
                        exit_p1 = sl_p * (1.0 - 0.0003)
                        exit_pr = sl_p * (1.0 - 0.0003)
                    else:
                        if high_p >= t1_p:
                            exit_p1 = t1_p
                            if high_p >= t2_p:
                                exit_pr = t2_p
                            else:
                                exit_pr = close_p * (1.0 - 0.0003)
                        else:
                            exit_p1 = close_p * (1.0 - 0.0003)
                            exit_pr = close_p * (1.0 - 0.0003)
                else:
                    if high_p >= sl_p:
                        exit_p1 = sl_p * (1.0 + 0.0003)
                        exit_pr = sl_p * (1.0 + 0.0003)
                    else:
                        if low_p <= t1_p:
                            exit_p1 = t1_p
                            if low_p <= t2_p:
                                exit_pr = t2_p
                            else:
                                exit_pr = close_p * (1.0 + 0.0003)
                        else:
                            exit_p1 = close_p * (1.0 + 0.0003)
                            exit_pr = close_p * (1.0 + 0.0003)
                            
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
                    'date': d, 'year': int(d[:4]), 'symbol': t['symbol'],
                    'net_pnl': npnl, 'fee': fee, 'R': npnl / 1000.0
                })
                
        df_res = pd.DataFrame(trades)
        if len(df_res) == 0:
            print(f"[{title}] 0 trades.")
            continue
            
        df_res['ym'] = pd.to_datetime(df_res['date']).dt.to_period('M')
        n_mo = df_res['ym'].nunique()
        tot_pnl = df_res['net_pnl'].sum()
        wins = df_res[df_res['net_pnl'] > 0]
        wr = len(wins) / len(df_res) * 100.0
        gw = wins['net_pnl'].sum()
        gl = abs(df_res[df_res['net_pnl'] <= 0]['net_pnl'].sum())
        pf = gw / gl if gl > 0 else 0.0
        
        df_res['cum'] = df_res['net_pnl'].cumsum()
        df_res['peak'] = df_res['cum'].cummax()
        max_dd = abs((df_res['cum'] - df_res['peak']).min()) / 100000.0 * 100.0
        
        mo_pnl = df_res.groupby('ym')['net_pnl'].sum()
        prof_mo = (mo_pnl > 0).mean() * 100.0
        y_pnl = df_res.groupby('year')['net_pnl'].sum().to_dict()
        
        print("="*85)
        print(f"[{title}]")
        print(f"  Trades: {len(df_res)} ({len(df_res)/n_mo:.1f}/mo) | WR: {wr:5.2f}% | PF: {pf:4.2f}")
        print(f"  Net PnL: Rs {tot_pnl:+10,.0f} (+{tot_pnl/1000:.1f}R) | Avg Mo Return: {tot_pnl/100000/n_mo*100:+5.2f}% / month")
        print(f"  Max DD: {max_dd:5.2f}% | Profitable Months: {prof_mo:.1f}%")
        print(f"  Yearly: { {y: int(v) for y, v in y_pnl.items()} }\n")

if __name__ == '__main__':
    test_pit_strategies()
