"""
OPTION 1: QUANTITATIVE SECTOR CATALYST & RELATIVE STRENGTH ENGINE (2022-2026)
4.8 Years, 1,186 Sessions across 29 Mega-Caps.
Workflow:
1. 09:00 AM: Sector Pre-Market Auction Gap Analysis (Banking, IT, Energy, Metal, Auto, FMCG, Infra)
2. Filter for #1 Focus Sector of the Day (Max Coordinated Sector Gap + Breadth >= 70%)
3. Hypothesis Formulation: Moderate gap -> Continuation, Extreme gap -> Fade
4. 09:15-09:45 AM: Market Open Confirmation (Sector RVOL check, VWAP adherence)
5. Stock Selection: Pick #1 Relative Strength Leader within the #1 Sector
6. Execution: Enter at 09:45 AM, Structural SL at morning extreme, Asymmetric Target (1:2, 1:2.5, 1:3)
7. Exit: Strict 3:00 PM IST Square-off
8. Cost Model: Full Statutory Zerodha Intraday Taxes (Brokerage, STT, Exchange, SEBI, GST, Stamp, Slippage)
"""
import os
import sys
import glob
import time as pytime
from datetime import time
import pandas as pd
import numpy as np
from costs import compute_trade_costs

CACHE_DIR = "data/master_cache_2022_2026"

SECTOR_MAP = {
    'BANKING': ['HDFCBANK', 'ICICIBANK', 'SBIN', 'KOTAKBANK', 'AXISBANK', 'INDUSINDBK', 'BAJFINANCE'],
    'IT': ['TCS', 'INFY', 'HCLTECH', 'WIPRO', 'TECHM'],
    'ENERGY': ['RELIANCE', 'ONGC', 'NTPC', 'POWERGRID', 'COALINDIA'],
    'METALS': ['TATASTEEL', 'JSWSTEEL'],
    'AUTO': ['MARUTI'],
    'FMCG': ['ITC', 'HINDUNILVR', 'TITAN'],
    'PHARMA': ['SUNPHARMA'],
    'INFRA': ['LT', 'ADANIENT', 'BHARTIARTL', 'GRASIM', 'ULTRACEMCO']
}

def load_universe():
    t0 = pytime.time()
    files_5m = sorted(glob.glob(os.path.join(CACHE_DIR, "*_5m.parquet")))
    symbols = [os.path.basename(f).replace("_5m.parquet", "") for f in files_5m]
    
    universe = {}
    for sym in symbols:
        df_5m = pd.read_parquet(os.path.join(CACHE_DIR, f"{sym}_5m.parquet"))
        df_daily = pd.read_parquet(os.path.join(CACHE_DIR, f"{sym}_daily.parquet"))
        
        df_daily['PDC'] = df_daily['Close'].shift(1)
        df_daily['Daily_VolMA20'] = df_daily['Volume'].rolling(20, min_periods=1).mean().shift(1)
        daily_dict = df_daily.set_index('Date').to_dict('index')
        
        day_records = {}
        for dt, grp in df_5m.groupby('Date'):
            if len(grp) < 30:
                continue
            day_records[dt] = {
                'opens': grp['Open'].values,
                'highs': grp['High'].values,
                'lows': grp['Low'].values,
                'closes': grp['Close'].values,
                'volumes': grp['Volume'].values,
                'vwap': grp['VWAP'].values,
                'times': grp['Time'].values,
                'n': len(grp)
            }
        universe[sym] = {'daily': daily_dict, 'days': day_records}
        
    print(f"Loaded {len(symbols)} symbols in {pytime.time() - t0:.2f}s", flush=True)
    return universe

def evaluate_strategy_results(strategy_name, all_trades):
    if not all_trades:
        print(f"[{strategy_name}] ZERO TRADES GENERATED.", flush=True)
        return {
            'Name': strategy_name, 'Trades': 0, 'WinRate': 0.0, 'PF': 0.0,
            'GrossPnL': 0.0, 'Costs': 0.0, 'NetPnL': 0.0, 'TotalR': 0.0,
            'MaxDD': 0.0, 'AvgMonthlyPct': 0.0, 'Status': 'NO_TRADES'
        }
        
    df_t = pd.DataFrame(all_trades)
    df_t['Date'] = pd.to_datetime(df_t['Date'])
    df_t['Year'] = df_t['Date'].dt.year
    df_t['Month'] = df_t['Date'].dt.to_period('M')
    
    total_trades = len(df_t)
    wins = df_t[df_t['NetPnL'] > 0]
    losses = df_t[df_t['NetPnL'] <= 0]
    win_rate = (len(wins) / total_trades) * 100.0
    
    total_gross = df_t['GrossPnL'].sum()
    total_costs = df_t['Costs'].sum()
    total_net = df_t['NetPnL'].sum()
    total_r = df_t['R_Return'].sum()
    
    profit_factor = abs(wins['NetPnL'].sum() / losses['NetPnL'].sum()) if len(losses) > 0 and losses['NetPnL'].sum() != 0 else np.nan
    
    df_t['CumNet'] = df_t['NetPnL'].cumsum()
    df_t['Peak'] = df_t['CumNet'].cummax()
    df_t['DD'] = df_t['Peak'] - df_t['CumNet']
    max_dd = df_t['DD'].max()
    
    monthly = df_t.groupby('Month')['NetPnL'].sum()
    num_months = len(monthly)
    avg_monthly_pnl = monthly.mean()
    avg_monthly_pct = (avg_monthly_pnl / 100000.0) * 100.0
    
    print("="*75, flush=True)
    print(f"   RESULTS: {strategy_name}", flush=True)
    print(f"   Period: 2022 to 2026 (4.8 Years, {num_months} Active Months)", flush=True)
    print("="*75, flush=True)
    print(f"Total Trades:            {total_trades}", flush=True)
    print(f"Win Rate:                {win_rate:.2f}% ({len(wins)}W / {len(losses)}L)", flush=True)
    print(f"Profit Factor:           {profit_factor:.2f}", flush=True)
    print(f"Total Gross Profit:      Rs {total_gross:,.2f}", flush=True)
    print(f"Total Friction Deducted: Rs {total_costs:,.2f} ({total_costs/total_gross*100 if total_gross > 0 else 0:.1f}% of gross)", flush=True)
    print(f"Total Net PnL:           Rs {total_net:,.2f} ({total_r:.1f}R)", flush=True)
    print(f"Max Drawdown:            Rs {max_dd:,.2f} ({max_dd/1000.0:.1f}R)", flush=True)
    print(f"Average Monthly Return:  Rs {avg_monthly_pnl:,.2f} ({avg_monthly_pct:.2f}% per month)", flush=True)
    
    yearly = df_t.groupby('Year').agg(
        Trades=('NetPnL', 'count'),
        NetPnL=('NetPnL', 'sum'),
        R_Return=('R_Return', 'sum'),
        WinRate=('NetPnL', lambda x: (x > 0).mean() * 100.0)
    )
    print("\n--- Annual Breakdown ---", flush=True)
    print(yearly.to_string(), flush=True)
    print("-" * 75 + "\n", flush=True)
    
    return {
        'Name': strategy_name,
        'Trades': total_trades,
        'WinRate': win_rate,
        'PF': profit_factor,
        'GrossPnL': total_gross,
        'Costs': total_costs,
        'NetPnL': total_net,
        'TotalR': total_r,
        'MaxDD': max_dd,
        'AvgMonthlyPct': avg_monthly_pct,
        'Status': 'PROFITABLE' if total_net > 0 else 'UNPROFITABLE'
    }

def run_option1_backtest(universe, target_rr=2.5, mode='TREND_ONLY'):
    """
    mode: 'TREND_ONLY' (Continuation only), 'FADE_ONLY' (Exhaustion only), 'HYBRID' (Both)
    """
    all_trades = []
    all_dates = sorted(list(next(iter(universe.values()))['days'].keys()))
    
    for dt in all_dates:
        # Step 1: Pre-Market Sector Gap & Breadth Calculation
        sector_stats = {}
        for sec_name, sec_syms in SECTOR_MAP.items():
            gaps = []
            for s in sec_syms:
                if s not in universe:
                    continue
                daily = universe[s]['daily']
                days = universe[s]['days']
                if dt not in daily or dt not in days:
                    continue
                pdc = daily[dt].get('PDC', np.nan)
                if pd.isna(pdc) or pdc <= 0:
                    continue
                open_0 = days[dt]['opens'][0]
                gap_pct = (open_0 - pdc) / pdc
                gaps.append((s, gap_pct))
                
            if len(gaps) >= 2: # Need at least 2 stocks for a sector reading
                gap_vals = [g[1] for g in gaps]
                med_gap = np.median(gap_vals)
                pos_count = sum(1 for g in gap_vals if g > 0.001)
                neg_count = sum(1 for g in gap_vals if g < -0.001)
                total = len(gap_vals)
                
                pos_breadth = pos_count / total
                neg_breadth = neg_count / total
                
                sector_stats[sec_name] = {
                    'median_gap': med_gap,
                    'abs_gap': abs(med_gap),
                    'pos_breadth': pos_breadth,
                    'neg_breadth': neg_breadth,
                    'stocks': gaps
                }
                
        if not sector_stats:
            continue
            
        # Step 2: Filter for #1 Focus Sector
        # Criterion: Highest coordinated gap with >= 60% breadth
        eligible_sectors = []
        for sec_name, stats in sector_stats.items():
            if stats['median_gap'] > 0 and stats['pos_breadth'] >= 0.60 and stats['abs_gap'] >= 0.004:
                eligible_sectors.append((sec_name, 'BULLISH', stats['abs_gap'], stats))
            elif stats['median_gap'] < 0 and stats['neg_breadth'] >= 0.60 and stats['abs_gap'] >= 0.004:
                eligible_sectors.append((sec_name, 'BEARISH', stats['abs_gap'], stats))
                
        if not eligible_sectors:
            continue
            
        # Pick sector with highest absolute catalyst gap
        eligible_sectors.sort(key=lambda x: x[2], reverse=True)
        top_sector, top_bias, top_gap, sec_meta = eligible_sectors[0]
        
        # Step 3: Determine Hypothesis: Continuation vs Fade
        action = None
        if top_gap <= 0.022: # Moderate gap: Trend Continuation
            if mode in ('TREND_ONLY', 'HYBRID'):
                action = 'LONG' if top_bias == 'BULLISH' else 'SHORT'
        else: # Extreme gap (> 2.2%): Gap Fade / Exhaustion
            if mode in ('FADE_ONLY', 'HYBRID'):
                action = 'SHORT' if top_bias == 'BULLISH' else 'LONG'
                
        if action is None:
            continue
            
        # Step 4: 09:15-09:45 AM Confirmation & Stock Selection
        # Score constituents of the top sector based on 09:15-09:45 price action
        stock_candidates = []
        for sym, g_pct in sec_meta['stocks']:
            d = universe[sym]['days'][dt]
            vol_ma = universe[sym]['daily'][dt].get('Daily_VolMA20', 0)
            if d['n'] < 30 or vol_ma <= 0:
                continue
                
            opens = d['opens']
            highs = d['highs']
            lows = d['lows']
            closes = d['closes']
            volumes = d['volumes']
            vwap = d['vwap']
            times = d['times']
            
            # Opening 30 min (first 6 bars)
            m30_vol = np.sum(volumes[:6])
            expected_m30_vol = vol_ma / 12.5
            rvol = m30_vol / expected_m30_vol if expected_m30_vol > 0 else 1.0
            
            # Return from open to 09:45 close (bar 5 close vs bar 0 open)
            ret_m30 = (closes[5] - opens[0]) / opens[0]
            vwap_5 = vwap[5]
            
            if action == 'LONG':
                # Long Candidate: Positive return, trading above VWAP, good RVOL
                if closes[5] > vwap_5 and closes[5] > opens[0] and rvol >= 1.1:
                    score = ret_m30 * rvol
                    stock_candidates.append({
                        'sym': sym, 'score': score, 'rvol': rvol, 'side': 'BUY',
                        'd': d, 'm30_low': np.min(lows[:6]), 'm30_high': np.max(highs[:6])
                    })
            else: # SHORT
                # Short Candidate: Negative return, trading below VWAP, good RVOL
                if closes[5] < vwap_5 and closes[5] < opens[0] and rvol >= 1.1:
                    score = abs(ret_m30) * rvol
                    stock_candidates.append({
                        'sym': sym, 'score': score, 'rvol': rvol, 'side': 'SELL',
                        'd': d, 'm30_low': np.min(lows[:6]), 'm30_high': np.max(highs[:6])
                    })
                    
        if not stock_candidates:
            continue
            
        # Select the #1 Relative Strength Leader of the sector
        stock_candidates.sort(key=lambda x: x['score'], reverse=True)
        lead = stock_candidates[0]
        
        sym = lead['sym']
        side = lead['side']
        d = lead['d']
        highs = d['highs']
        lows = d['lows']
        closes = d['closes']
        times = d['times']
        n = d['n']
        
        # Entry at Open of candle 6 (09:45 AM)
        entry_price = d['opens'][6]
        entry_time = times[6]
        
        if side == 'BUY':
            sl_price = lead['m30_low'] * 0.9995
            sl_dist = entry_price - sl_price
            if sl_dist <= 0 or (sl_dist / entry_price) < 0.003:
                sl_dist = entry_price * 0.005 # Min 0.5% SL
                sl_price = entry_price - sl_dist
            elif (sl_dist / entry_price) > 0.015:
                sl_dist = entry_price * 0.015 # Max 1.5% SL
                sl_price = entry_price - sl_dist
                
            tp_price = entry_price + (sl_dist * target_rr)
            qty = max(1, min(int(1000.0 / sl_dist), int(500000 / entry_price)))
            
            exit_p, exit_t, reason = None, None, None
            for m in range(6, n):
                if highs[m] >= tp_price:
                    exit_p, exit_t, reason = tp_price, times[m], 'TARGET'
                    break
                if lows[m] <= sl_price:
                    exit_p, exit_t, reason = sl_price, times[m], 'STOP_LOSS'
                    break
                if times[m] >= time(15, 0):
                    exit_p, exit_t, reason = closes[m], times[m], 'TIME_3PM'
                    break
            if exit_p is None:
                exit_p, exit_t, reason = closes[-1], times[-1], 'EOD_CLOSE'
                
            costs = compute_trade_costs('BUY', entry_price, qty, 0.0, 0, exit_p, qty, 0.0003)
            all_trades.append({
                'Date': dt, 'Symbol': sym, 'Sector': top_sector, 'Side': 'BUY',
                'EntryTime': entry_time, 'ExitTime': exit_t, 'EntryPrice': entry_price,
                'ExitPrice': exit_p, 'Qty': qty, 'Reason': reason,
                'GrossPnL': costs['gross_pnl'], 'Costs': costs['statutory_charges'] + costs['slippage_cost'],
                'NetPnL': costs['net_pnl'], 'R_Return': costs['net_pnl'] / 1000.0
            })
            
        else: # SHORT
            sl_price = lead['m30_high'] * 1.0005
            sl_dist = sl_price - entry_price
            if sl_dist <= 0 or (sl_dist / entry_price) < 0.003:
                sl_dist = entry_price * 0.005
                sl_price = entry_price + sl_dist
            elif (sl_dist / entry_price) > 0.015:
                sl_dist = entry_price * 0.015
                sl_price = entry_price + sl_dist
                
            tp_price = entry_price - (sl_dist * target_rr)
            qty = max(1, min(int(1000.0 / sl_dist), int(500000 / entry_price)))
            
            exit_p, exit_t, reason = None, None, None
            for m in range(6, n):
                if lows[m] <= tp_price:
                    exit_p, exit_t, reason = tp_price, times[m], 'TARGET'
                    break
                if highs[m] >= sl_price:
                    exit_p, exit_t, reason = sl_price, times[m], 'STOP_LOSS'
                    break
                if times[m] >= time(15, 0):
                    exit_p, exit_t, reason = closes[m], times[m], 'TIME_3PM'
                    break
            if exit_p is None:
                exit_p, exit_t, reason = closes[-1], times[-1], 'EOD_CLOSE'
                
            costs = compute_trade_costs('SELL', entry_price, qty, 0.0, 0, exit_p, qty, 0.0003)
            all_trades.append({
                'Date': dt, 'Symbol': sym, 'Sector': top_sector, 'Side': 'SHORT',
                'EntryTime': entry_time, 'ExitTime': exit_t, 'EntryPrice': entry_price,
                'ExitPrice': exit_p, 'Qty': qty, 'Reason': reason,
                'GrossPnL': costs['gross_pnl'], 'Costs': costs['statutory_charges'] + costs['slippage_cost'],
                'NetPnL': costs['net_pnl'], 'R_Return': costs['net_pnl'] / 1000.0
            })
            
    return evaluate_strategy_results(f"Option 1: Sector Catalyst ({mode}, 1:{target_rr})", all_trades)

def main():
    universe = load_universe()
    results = []
    
    print("\n" + "#"*75, flush=True)
    print("   RUNNING OPTION 1: SECTOR CATALYST & RELATIVE STRENGTH ENGINE (2022-2026)", flush=True)
    print("#"*75 + "\n", flush=True)
    
    # Test 1: Trend Continuation Only (1:2.0, 1:2.5, 1:3.0)
    for rr in [2.0, 2.5, 3.0]:
        results.append(run_option1_backtest(universe, target_rr=rr, mode='TREND_ONLY'))
        
    # Test 2: Hybrid (Continuation on normal gap, Fade on extreme gap >2.2%)
    for rr in [2.0, 2.5, 3.0]:
        results.append(run_option1_backtest(universe, target_rr=rr, mode='HYBRID'))
        
    df_summary = pd.DataFrame(results)
    df_summary.to_csv("research/phase4_2/option1_sector_catalyst_summary.csv", index=False)
    
    print("\n" + "="*85, flush=True)
    print("                  OPTION 1 SECTOR CATALYST LEADERBOARD", flush=True)
    print("="*85, flush=True)
    cols = ['Name', 'Trades', 'WinRate', 'PF', 'GrossPnL', 'Costs', 'NetPnL', 'TotalR', 'MaxDD', 'AvgMonthlyPct', 'Status']
    print(df_summary[cols].to_string(), flush=True)
    print("="*85, flush=True)

if __name__ == '__main__':
    main()
