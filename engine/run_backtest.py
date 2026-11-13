import os
import pandas as pd
import numpy as np
from datetime import datetime, time
from data_loader import load_nifty, load_stock, resample_5min
from strategy import compute_indicators, generate_signals
from simulator import simulate_trade

def run_portfolio_backtest():
    print("="*60)
    print("  INSTITUTIONAL NSE INTRADAY STRATEGY 4-YEAR BACKTEST")
    print("  Period: October 2022 to November 11, 2026")
    print("="*60)
    
    universe = ['NIFTY50', 'RELIANCE', 'HDFCBANK', 'ICICIBANK', 'TCS', 'INFY', 'SBIN', 'BHARTIARTL', 'LT', 'AXISBANK']
    all_trades = []

    for sym in universe:
        print(f"Processing {sym}...")
        if sym == 'NIFTY50':
            df_1m = load_nifty()
        else:
            df_1m = load_stock(sym)
            
        if df_1m is None or len(df_1m) == 0:
            print(f"  Warning: No data for {sym}")
            continue

        df_5m = resample_5min(df_1m)
        df_ind = compute_indicators(df_5m)
        signals = generate_signals(df_ind)
        print(f"  {sym}: {len(signals)} raw candidate signals generated.")

        if len(signals) == 0:
            continue

        # Group df_ind by date for candle lookup in trade simulator
        daily_dfs = {dt: g for dt, g in df_ind.groupby('Date')}

        for _, sig in signals.iterrows():
            dt = sig['Date']
            if dt in daily_dfs:
                trade_res = simulate_trade(sig, daily_dfs[dt])
                if trade_res is not None:
                    all_trades.append(trade_res)

    trades_df = pd.DataFrame(all_trades)
    print(f"\nTotal simulated candidate trades before portfolio limits: {len(trades_df)}")

    # Sort all trades chronologically
    trades_df = trades_df.sort_values(['Date', 'EntryTime']).reset_index(drop=True)

    # Apply Portfolio Constraints:
    # 1. Max 2-3 trades per day across portfolio (we'll enforce max 3 trades/day)
    # 2. Max 2 concurrent open positions
    # 3. Max daily loss limit: if 2 losses occur on a single day, stop for that day
    filtered_trades = []
    
    for dt, day_group in trades_df.groupby('Date'):
        day_trades_count = 0
        day_losses_count = 0
        active_positions = [] # list of exit times

        for _, trade in day_group.iterrows():
            if day_trades_count >= 3:
                break
            if day_losses_count >= 2:
                # Daily risk circuit breaker hit
                break

            entry_t = trade['EntryTime']
            exit_t = trade['ExitTime']

            # Update active positions (remove ones that have exited before this entry)
            active_positions = [t for t in active_positions if t > entry_t]

            if len(active_positions) >= 2:
                # Concurrent position limit reached
                continue

            # Accept trade
            active_positions.append(exit_t)
            filtered_trades.append(trade)
            day_trades_count += 1
            if trade['R_Multiple'] < 0:
                day_losses_count += 1

    final_df = pd.DataFrame(filtered_trades)
    print(f"\nFinal portfolio trades executed: {len(final_df)}")
    
    # Save detailed trade logs
    os.makedirs('reports', exist_ok=True)
    final_df.to_csv('reports/all_trades_log.csv', index=False)
    
    # Performance Analysis
    final_df['YearMonth'] = pd.to_datetime(final_df['Date']).dt.to_period('M')
    
    # Monthly aggregation
    monthly = final_df.groupby('YearMonth').agg(
        Total_Trades=('R_Multiple', 'count'),
        Wins=('Win', 'sum'),
        Losses=('Win', lambda x: (x == False).sum()),
        Total_R=('R_Multiple', 'sum'),
        Avg_R_Per_Trade=('R_Multiple', 'mean')
    ).reset_index()

    monthly['WinRate_Pct'] = round((monthly['Wins'] / monthly['Total_Trades']) * 100, 1)
    monthly['Total_R'] = round(monthly['Total_R'], 1)
    monthly['Profit_INR_1kRisk'] = (monthly['Total_R'] * 1000).astype(int)

    monthly.to_csv('reports/monthly_performance.csv', index=False)

    total_r = final_df['R_Multiple'].sum()
    total_trades = len(final_df)
    total_wins = final_df['Win'].sum()
    win_rate = (total_wins / total_trades) * 100
    avg_win = final_df[final_df['R_Multiple'] > 0]['R_Multiple'].mean()
    avg_loss = final_df[final_df['R_Multiple'] < 0]['R_Multiple'].mean()
    profit_factor = abs(final_df[final_df['R_Multiple'] > 0]['R_Multiple'].sum() / final_df[final_df['R_Multiple'] < 0]['R_Multiple'].sum())
    
    # Cumulative R & Drawdown
    final_df['Cum_R'] = final_df['R_Multiple'].cumsum()
    final_df['Peak_R'] = final_df['Cum_R'].cummax()
    final_df['Drawdown_R'] = final_df['Cum_R'] - final_df['Peak_R']
    max_drawdown_r = final_df['Drawdown_R'].min()

    num_months = len(monthly)
    avg_r_per_month = total_r / num_months

    # Daily returns for Sharpe Ratio
    daily_r = final_df.groupby('Date')['R_Multiple'].sum()
    sharpe = (daily_r.mean() / daily_r.std()) * np.sqrt(252) if daily_r.std() > 0 else 0

    print("\n" + "="*60)
    print("           OVERALL 4-YEAR BACKTEST SUMMARY")
    print("="*60)
    print(f"Total Trading Months : {num_months} months (Oct 2022 - Nov 2026)")
    print(f"Total Trades Taken   : {total_trades} (Avg ~{round(total_trades/num_months, 1)} trades/month, ~{round(total_trades/(num_months*21), 1)} trades/day)")
    print(f"Overall Win Rate     : {win_rate:.2f}%")
    print(f"Average Win          : +{avg_win:.2f}R")
    print(f"Average Loss         : {avg_loss:.2f}R")
    print(f"Profit Factor        : {profit_factor:.2f}")
    print(f"Total Return         : +{total_r:.1f}R  (₹{int(total_r * 1000):,} @ ₹1k risk/trade)")
    print(f"Average Return/Month : +{avg_r_per_month:.1f}R  (₹{int(avg_r_per_month * 1000):,}/month)")
    print(f"Max Drawdown         : {max_drawdown_r:.1f}R")
    print(f"Annualized Sharpe    : {sharpe:.2f}")
    print("="*60)

    print("\nSample Monthly Performance (Last 12 Months):")
    print(monthly.tail(12).to_string(index=False))

    return monthly, final_df

if __name__ == '__main__':
    run_portfolio_backtest()
