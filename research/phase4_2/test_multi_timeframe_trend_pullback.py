"""
MULTI-TIMEFRAME TREND CONTINUATION & VWAP PULLBACK SYSTEM (2022-2026)
Empirical Backtest across 29 Mega-Caps (4.8 Years, 1,186 Sessions).
Concepts:
1. Higher Timeframe Trend Alignment: Daily 20 EMA > Daily 50 EMA (Longs) or < (Shorts).
2. Institutional Breakout: Morning 15m Initial Balance Breakout (09:15-09:45).
3. Intraday Pullback Confluence: Retest of VWAP or 20 EMA on 5m chart between 10:00 AM and 13:00 PM.
4. Trigger: Reversal rejection candle at VWAP.
5. Invalidation (SL): Swing low of the pullback (below VWAP).
6. Target: Asymmetric 2.0R to 3.5R.
7. Strict 3:00 PM IST Square-off.
8. Full Statutory Zerodha Intraday Cost Model (Brokerage, STT, Exchange, SEBI, Stamp Duty, GST, Slippage).
"""
import os
import glob
import pandas as pd
import numpy as np
from datetime import time
from costs import compute_trade_costs

CACHE_DIR = "data/master_cache_2022_2026"

def run_mtf_pullback_backtest(target_rr=2.5, min_sl_pct=0.003, max_sl_pct=0.012):
    files_5m = sorted(glob.glob(os.path.join(CACHE_DIR, "*_5m.parquet")))
    if not files_5m:
        print("Master cache not ready!")
        return None
        
    symbols = [os.path.basename(f).replace("_5m.parquet", "") for f in files_5m]
    print(f"Loaded {len(symbols)} symbols from cache.")
    
    all_trades = []
    
    for sym in symbols:
        df_5m = pd.read_parquet(os.path.join(CACHE_DIR, f"{sym}_5m.parquet"))
        df_daily = pd.read_parquet(os.path.join(CACHE_DIR, f"{sym}_daily.parquet"))
        
        # Calculate Daily 20 EMA and 50 EMA (lagged by 1 day to prevent look-ahead bias)
        df_daily['Daily_EMA20'] = df_daily['Close'].ewm(span=20, adjust=False).mean().shift(1)
        df_daily['Daily_EMA50'] = df_daily['Close'].ewm(span=50, adjust=False).mean().shift(1)
        daily_trend = df_daily.set_index('Date')[['Daily_EMA20', 'Daily_EMA50']].to_dict('index')
        
        dates = df_5m['Date'].unique()
        
        for dt in dates:
            if dt not in daily_trend:
                continue
            d_info = daily_trend[dt]
            ema20 = d_info['Daily_EMA20']
            ema50 = d_info['Daily_EMA50']
            if pd.isna(ema20) or pd.isna(ema50):
                continue
                
            is_macro_bull = ema20 > ema50
            is_macro_bear = ema20 < ema50
            
            day_bars = df_5m[df_5m['Date'] == dt].reset_index(drop=True)
            if len(day_bars) < 35:
                continue
                
            # Initial Balance: first 6 bars (09:15 to 09:45)
            ib_bars = day_bars.iloc[:6]
            ibh = ib_bars['High'].max()
            ibl = ib_bars['Low'].min()
            
            # Setup Long: Macro Bull + IBH Breakout + Pullback to VWAP
            in_trade = False
            for i in range(6, min(len(day_bars) - 5, 45)):
                if in_trade:
                    break
                    
                row = day_bars.iloc[i]
                prev_row = day_bars.iloc[i-1]
                t = row['Time']
                
                # Check Long Setup:
                if is_macro_bull:
                    # Stock broke above IBH earlier
                    had_breakout = any(day_bars.iloc[k]['Close'] > ibh for k in range(6, i))
                    if had_breakout:
                        # Pullback to VWAP: Low touches or dips near VWAP (within 0.15%), but Close > VWAP
                        vwap = row['VWAP']
                        if abs(row['Low'] - vwap) / vwap <= 0.002 and row['Close'] > vwap and row['Close'] > row['Open']:
                            # Reversal candle at VWAP confirmed!
                            entry_price = row['Close']
                            entry_time = t
                            # Stop loss: below the pullback low or 0.4% below VWAP
                            pullback_low = min(row['Low'], prev_row['Low'])
                            sl_price = min(pullback_low * 0.999, vwap * 0.996)
                            sl_dist = entry_price - sl_price
                            sl_pct = sl_dist / entry_price
                            
                            if min_sl_pct <= sl_pct <= max_sl_pct:
                                tp_price = entry_price + (sl_dist * target_rr)
                                qty = max(1, int(1000.0 / sl_dist))
                                if qty * entry_price > 500000:
                                    qty = int(500000 / entry_price)
                                    
                                exit_price = None
                                exit_time = None
                                exit_reason = None
                                
                                for m_idx in range(i+1, len(day_bars)):
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
                                
                # Check Short Setup:
                if not in_trade and is_macro_bear:
                    had_breakdown = any(day_bars.iloc[k]['Close'] < ibl for k in range(6, i))
                    if had_breakdown:
                        vwap = row['VWAP']
                        if abs(row['High'] - vwap) / vwap <= 0.002 and row['Close'] < vwap and row['Close'] < row['Open']:
                            entry_price = row['Close']
                            entry_time = t
                            pullback_high = max(row['High'], prev_row['High'])
                            sl_price = max(pullback_high * 1.001, vwap * 1.004)
                            sl_dist = sl_price - entry_price
                            sl_pct = sl_dist / entry_price
                            
                            if min_sl_pct <= sl_pct <= max_sl_pct:
                                tp_price = entry_price - (sl_dist * target_rr)
                                qty = max(1, int(1000.0 / sl_dist))
                                if qty * entry_price > 500000:
                                    qty = int(500000 / entry_price)
                                    
                                exit_price = None
                                exit_time = None
                                exit_reason = None
                                
                                for m_idx in range(i+1, len(day_bars)):
                                    m_bar = day_bars.iloc[m_idx]
                                    m_time = m_bar['Time']
                                    
                                    if m_bar['Low'] <= tp_price:
                                        exit_price = tp_price
                                        exit_time = m_time
                                        exit_reason = 'TARGET'
                                        break
                                    if m_bar['High'] >= sl_price:
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
    
    monthly = df_t.groupby('Month')['NetPnL'].sum()
    num_months = len(monthly)
    avg_monthly_pnl = monthly.mean()
    avg_monthly_pct = (avg_monthly_pnl / 100000.0) * 100.0
    
    print("\n" + "="*75)
    print(f"   MULTI-TIMEFRAME TREND CONTINUATION & VWAP PULLBACK (Target R:R = 1:{target_rr})")
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
    run_mtf_pullback_backtest(target_rr=2.5)
