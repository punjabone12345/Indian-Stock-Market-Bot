"""
SMC & ICT LIQUIDITY SWEEP + FAIR VALUE GAP (FVG) RETEST SYSTEM (4+ YEARS: 2022-2026)
Rigorous Empirical Backtest on 29 Nifty Mega-Caps.
Concepts:
1. Liquidity Sweep (Turtle Soup) of PDH/PDL or Morning Initial Balance (09:15-09:45)
2. Market Structure Shift (Displacement) creating a 3-candle Fair Value Gap (FVG)
3. Retest of FVG zone for Point-in-Time execution (No look-ahead bias)
4. Structural Stop Loss at the Sweep Extreme
5. Asymmetric Targets (2R, 3R, 4R)
6. Exact 3:00 PM IST Square-off
7. Full Statutory Zerodha Intraday Cost Model (Brokerage, STT, Exchange, SEBI, Stamp Duty, GST, Slippage)
"""
import os
import glob
import pandas as pd
import numpy as np
from datetime import time
from costs import compute_trade_costs

CACHE_DIR = "data/master_cache_2022_2026"

def run_smc_backtest(target_rr=3.0, min_sl_pct=0.003, max_sl_pct=0.015):
    files_5m = sorted(glob.glob(os.path.join(CACHE_DIR, "*_5m.parquet")))
    if not files_5m:
        print("Master cache not ready yet!")
        return None
        
    symbols = [os.path.basename(f).replace("_5m.parquet", "") for f in files_5m]
    print(f"Loaded {len(symbols)} symbols from cache.")
    
    all_trades = []
    
    for sym in symbols:
        df_5m = pd.read_parquet(os.path.join(CACHE_DIR, f"{sym}_5m.parquet"))
        df_daily = pd.read_parquet(os.path.join(CACHE_DIR, f"{sym}_daily.parquet"))
        
        # Merge Previous Day High and Low
        df_daily['PDH'] = df_daily['High'].shift(1)
        df_daily['PDL'] = df_daily['Low'].shift(1)
        df_daily['PDC'] = df_daily['Close'].shift(1)
        pd_map = df_daily.set_index('Date')[['PDH', 'PDL', 'PDC']].to_dict('index')
        
        # Group 5m data by Date
        dates = df_5m['Date'].unique()
        
        for dt in dates:
            if dt not in pd_map:
                continue
            pd_info = pd_map[dt]
            pdh = pd_info['PDH']
            pdl = pd_info['PDL']
            if pd.isna(pdh) or pd.isna(pdl):
                continue
                
            day_bars = df_5m[df_5m['Date'] == dt].reset_index(drop=True)
            if len(day_bars) < 30: # Need sufficient bars
                continue
                
            # Initial Balance: first 6 bars (09:15 to 09:45)
            ib_bars = day_bars.iloc[:6]
            ibh = max(ib_bars['High'].max(), pdh) # Confluence with PDH
            ibl = min(ib_bars['Low'].min(), pdl)  # Confluence with PDL
            
            # Search for Liquidity Sweep & Displacement FVG between 09:45 and 13:30 (bars 6 to 50)
            in_trade = False
            for i in range(6, min(len(day_bars) - 5, 52)):
                if in_trade:
                    break
                    
                c1 = day_bars.iloc[i-2]
                c2 = day_bars.iloc[i-1] # Displacement
                c3 = day_bars.iloc[i]   # FVG formation
                
                # SETUP A: BEARISH LIQUIDITY SWEEP + BEARISH FVG (SHORT)
                # Sweep condition: High broke above IBH/PDH recently, but closed below
                swept_high = any(day_bars.iloc[k]['High'] > ibh and day_bars.iloc[k]['Close'] < ibh for k in range(max(0, i-4), i))
                fvg_bearish = (c3['High'] < c1['Low']) and (c2['Close'] < c2['Open']) # Valid FVG
                
                if swept_high and fvg_bearish:
                    fvg_zone_top = c1['Low']
                    fvg_zone_bottom = c3['High']
                    entry_limit = fvg_zone_top
                    
                    # Stop loss: Sweep peak
                    sweep_peak = max(day_bars.iloc[k]['High'] for k in range(max(0, i-4), i+1))
                    raw_sl_dist = sweep_peak - entry_limit
                    sl_pct = raw_sl_dist / entry_limit
                    
                    if min_sl_pct <= sl_pct <= max_sl_pct:
                        # Check retest in subsequent candles (up to next 10 candles / 50 mins)
                        for r_idx in range(i+1, min(len(day_bars)-2, i+12)):
                            rk = day_bars.iloc[r_idx]
                            # Retest condition: Price retraces back UP into the FVG
                            if rk['High'] >= entry_limit:
                                entry_price = entry_limit
                                sl_price = sweep_peak
                                tp_price = entry_price - (raw_sl_dist * target_rr)
                                entry_time = rk['Time']
                                
                                # Sizing: ₹1,000 risk (1R)
                                qty = max(1, int(1000.0 / raw_sl_dist))
                                position_value = qty * entry_price
                                
                                # SEBI MIS leverage limit: max 5x capital (₹5,00,000)
                                if position_value > 500000:
                                    qty = int(500000 / entry_price)
                                    
                                # Track trade outcome bar-by-bar
                                exit_price = None
                                exit_time = None
                                exit_reason = None
                                
                                for m_idx in range(r_idx+1, len(day_bars)):
                                    m_bar = day_bars.iloc[m_idx]
                                    m_time = m_bar['Time']
                                    
                                    # Target check
                                    if m_bar['Low'] <= tp_price:
                                        exit_price = tp_price
                                        exit_time = m_time
                                        exit_reason = 'TARGET'
                                        break
                                    # Stop loss check
                                    if m_bar['High'] >= sl_price:
                                        exit_price = sl_price
                                        exit_time = m_time
                                        exit_reason = 'STOP_LOSS'
                                        break
                                    # 3:00 PM IST Square-off
                                    if m_time >= time(15, 0):
                                        exit_price = m_bar['Close']
                                        exit_time = m_time
                                        exit_reason = 'TIME_3PM'
                                        break
                                        
                                if exit_price is None:
                                    last_bar = day_bars.iloc[-1]
                                    exit_price = last_bar['Close']
                                    exit_time = last_bar['Time']
                                    exit_reason = 'EOD_CLOSE'
                                    
                                # Compute costs
                                costs = compute_trade_costs(
                                    side='SELL',
                                    entry_price=entry_price,
                                    entry_qty=qty,
                                    exit1_price=0.0,
                                    exit1_qty=0,
                                    exit2_price=exit_price,
                                    exit2_qty=qty,
                                    slippage_pct=0.0003
                                )
                                gross_pnl = costs['gross_pnl']
                                net_pnl = costs['net_pnl']
                                total_costs = costs['statutory_charges'] + costs['slippage_cost']
                                r_realized = net_pnl / 1000.0
                                
                                all_trades.append({
                                    'Date': dt,
                                    'Symbol': sym,
                                    'Side': 'SHORT',
                                    'EntryTime': entry_time,
                                    'ExitTime': exit_time,
                                    'EntryPrice': entry_price,
                                    'ExitPrice': exit_price,
                                    'Qty': qty,
                                    'Reason': exit_reason,
                                    'GrossPnL': gross_pnl,
                                    'Costs': total_costs,
                                    'NetPnL': net_pnl,
                                    'R_Return': r_realized
                                })
                                in_trade = True
                                break
                                
                # SETUP B: BULLISH LIQUIDITY SWEEP + BULLISH FVG (LONG)
                if not in_trade:
                    swept_low = any(day_bars.iloc[k]['Low'] < ibl and day_bars.iloc[k]['Close'] > ibl for k in range(max(0, i-4), i))
                    fvg_bullish = (c3['Low'] > c1['High']) and (c2['Close'] > c2['Open']) # Valid FVG
                    
                    if swept_low and fvg_bullish:
                        fvg_zone_bottom = c1['High']
                        entry_limit = fvg_zone_bottom
                        sweep_trough = min(day_bars.iloc[k]['Low'] for k in range(max(0, i-4), i+1))
                        raw_sl_dist = entry_limit - sweep_trough
                        sl_pct = raw_sl_dist / entry_limit
                        
                        if min_sl_pct <= sl_pct <= max_sl_pct:
                            for r_idx in range(i+1, min(len(day_bars)-2, i+12)):
                                rk = day_bars.iloc[r_idx]
                                if rk['Low'] <= entry_limit:
                                    entry_price = entry_limit
                                    sl_price = sweep_trough
                                    tp_price = entry_price + (raw_sl_dist * target_rr)
                                    entry_time = rk['Time']
                                    
                                    qty = max(1, int(1000.0 / raw_sl_dist))
                                    position_value = qty * entry_price
                                    if position_value > 500000:
                                        qty = int(500000 / entry_price)
                                        
                                    exit_price = None
                                    exit_time = None
                                    exit_reason = None
                                    
                                    for m_idx in range(r_idx+1, len(day_bars)):
                                        m_bar = day_bars.iloc[m_idx]
                                        m_time = m_bar['Time']
                                        
                                        if m_bar['High'] >= tp_price:
                                            exit_price = tp_price
                                            exit_time = m_time
                                            exit_reason = 'TARGET'
                                            break
                                        if m_bar['Low'] <= sl_price:
                                            exit_price = sl_price
                                            exit_time = m_time
                                            exit_reason = 'STOP_LOSS'
                                            break
                                        if m_time >= time(15, 0):
                                            exit_price = m_bar['Close']
                                            exit_time = m_time
                                            exit_reason = 'TIME_3PM'
                                            break
                                            
                                    if exit_price is None:
                                        last_bar = day_bars.iloc[-1]
                                        exit_price = last_bar['Close']
                                        exit_time = last_bar['Time']
                                        exit_reason = 'EOD_CLOSE'
                                        
                                    costs = compute_trade_costs(
                                        side='BUY',
                                        entry_price=entry_price,
                                        entry_qty=qty,
                                        exit1_price=0.0,
                                        exit1_qty=0,
                                        exit2_price=exit_price,
                                        exit2_qty=qty,
                                        slippage_pct=0.0003
                                    )
                                    gross_pnl = costs['gross_pnl']
                                    net_pnl = costs['net_pnl']
                                    total_costs = costs['statutory_charges'] + costs['slippage_cost']
                                    r_realized = net_pnl / 1000.0
                                    
                                    all_trades.append({
                                        'Date': dt,
                                        'Symbol': sym,
                                        'Side': 'BUY',
                                        'EntryTime': entry_time,
                                        'ExitTime': exit_time,
                                        'EntryPrice': entry_price,
                                        'ExitPrice': exit_price,
                                        'Qty': qty,
                                        'Reason': exit_reason,
                                        'GrossPnL': gross_pnl,
                                        'Costs': total_costs,
                                        'NetPnL': net_pnl,
                                        'R_Return': r_realized
                                    })
                                    in_trade = True
                                    break

    if not all_trades:
        print("No trades generated.")
        return None
        
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
    
    # Monthly stats
    monthly = df_t.groupby('Month')['NetPnL'].sum()
    num_months = len(monthly)
    avg_monthly_pnl = monthly.mean()
    avg_monthly_pct = (avg_monthly_pnl / 100000.0) * 100.0
    
    print("\n" + "="*75)
    print(f"   SMC / ICT LIQUIDITY SWEEP + FVG RETEST (Target R:R = 1:{target_rr})")
    print(f"   Period: 2022 to 2026 (4.8 Years, {num_months} Months)")
    print("="*75)
    print(f"Total Trades Executed:   {total_trades}")
    print(f"Win Rate:                {win_rate:.2f}% ({len(wins)}W / {len(losses)}L)")
    print(f"Profit Factor:           {profit_factor:.2f}")
    print(f"Total Gross Profit:      Rs {total_gross:,.2f}")
    print(f"Total Friction Deducted: Rs {total_costs:,.2f} ({total_costs/total_gross*100:.1f}% of gross)")
    print(f"Total Net PnL:           Rs {total_net:,.2f} ({total_r:.1f}R)")
    print(f"Max Drawdown:            Rs {max_dd:,.2f} ({max_dd/1000.0:.1f}R)")
    print(f"Average Monthly Return:  Rs {avg_monthly_pnl:,.2f} ({avg_monthly_pct:.2f}% per month)")
    
    print("\n--- ANNUAL BREAKDOWN ---")
    yearly = df_t.groupby('Year').agg(
        Trades=('NetPnL', 'count'),
        NetPnL=('NetPnL', 'sum'),
        R_Return=('R_Return', 'sum'),
        WinRate=('NetPnL', lambda x: (x > 0).mean() * 100.0)
    )
    print(yearly.to_string())
    
    return df_t

if __name__ == '__main__':
    run_smc_backtest(target_rr=3.0)
