import sys
sys.path.append('engine')
import os
import glob
import pandas as pd
import numpy as np
from datetime import time
from data_loader import resample_5min

UNIVERSE_18 = [
    'RELIANCE', 'TCS', 'HDFCBANK', 'ICICIBANK', 'INFY', 'SBIN',
    'BHARTIARTL', 'LT', 'AXISBANK', 'BAJFINANCE', 'TITAN', 'MARUTI',
    'KOTAKBANK', 'WIPRO', 'SUNPHARMA', 'TATASTEEL', 'ADANIENT', 'INDUSINDBK'
]

def load_all_stocks_5m(universe):
    all_stocks = {}
    for s in universe:
        f_prev = f'data/stocks/{s}_prev.parquet'
        f_2026 = f'data/stocks/{s}_2026.parquet'
        dfs = []
        if os.path.exists(f_prev):
            d1 = pd.read_parquet(f_prev)
            d1['Timestamp'] = pd.to_datetime(d1['Date'])
            d1 = d1[d1['Timestamp'] >= '2022-10-01']
            dfs.append(d1[['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']])
        if os.path.exists(f_2026):
            d2 = pd.read_parquet(f_2026)
            d2['Timestamp'] = pd.to_datetime(d2['Date'])
            dfs.append(d2[['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']])
        if not dfs:
            continue
        df = pd.concat(dfs).sort_values('Timestamp').drop_duplicates('Timestamp').reset_index(drop=True)
        df['Symbol'] = s
        df['IsIndex'] = False
        
        df_5m = resample_5min(df)

        # Precompute VWAP, EMAs, Volume MA, Daily Trend, PDC
        df_5m['Typ'] = (df_5m['High'] + df_5m['Low'] + df_5m['Close']) / 3.0
        df_5m['PV'] = df_5m['Typ'] * df_5m['Volume']
        df_5m['CumPV'] = df_5m.groupby('Date')['PV'].cumsum()
        df_5m['CumV'] = df_5m.groupby('Date')['Volume'].cumsum()
        df_5m['VWAP'] = df_5m['CumPV'] / df_5m['CumV']
        df_5m['EMA9'] = df_5m['Close'].ewm(span=9, adjust=False).mean()
        df_5m['EMA21'] = df_5m['Close'].ewm(span=21, adjust=False).mean()
        df_5m['VolMA20'] = df_5m['Volume'].rolling(20, min_periods=1).mean()

        daily_summary = df_5m.groupby('Date').agg({'Close': 'last', 'Volume': 'sum'}).shift(1)
        daily_close = daily_summary['Close']
        daily_ema20 = daily_close.ewm(span=20, adjust=False).mean()
        daily_ema50 = daily_close.ewm(span=50, adjust=False).mean()
        df_5m['DailyBull'] = df_5m['Date'].map(daily_ema20 > daily_ema50)
        df_5m['PDC'] = df_5m['Date'].map(daily_close)
        
        all_stocks[s] = df_5m
        print(f"Loaded {s}: {len(df_5m)} candles")
    return all_stocks

def run_alpha_backtest(all_stocks):
    print("\n" + "="*70)
    print("      RUNNING INSTITUTIONAL RVOL MOMENTUM BACKTEST (18 STOCKS)")
    print("="*70)

    # Get all unique trading dates
    sample_sym = list(all_stocks.keys())[0]
    all_dates = sorted(all_stocks[sample_sym]['Date'].unique())

    portfolio_trades = []
    
    for dt in all_dates:
        # Step 1: Scan all 18 stocks on this date for RVOL & Gap
        day_candidates = []
        
        for sym, df_5m in all_stocks.items():
            g = df_5m[df_5m['Date'] == dt].reset_index(drop=True)
            if len(g) < 25 or pd.isna(g['PDC'].iloc[0]) or pd.isna(g['DailyBull'].iloc[0]):
                continue

            first3 = g.iloc[:3]
            orb_h = first3['High'].max()
            orb_l = first3['Low'].min()
            orb_rng = orb_h - orb_l
            pdc = g['PDC'].iloc[0]
            gap_pct = abs(g.iloc[0]['Open'] - pdc) / pdc
            
            avg_vol = g['VolMA20'].iloc[0]
            rvol = (first3['Volume'].mean() / avg_vol) if avg_vol > 0 else 1.0

            # Filter: RVOL >= 1.7 OR Gap >= 0.7%
            if rvol >= 1.7 or gap_pct >= 0.007:
                score = rvol * 1.5 + (gap_pct * 100)
                day_candidates.append({
                    'symbol': sym,
                    'df': g,
                    'score': score,
                    'rvol': rvol,
                    'gap_pct': gap_pct,
                    'orb_h': orb_h,
                    'orb_l': orb_l,
                    'daily_bull': g['DailyBull'].iloc[0]
                })

        # Sort candidates by momentum score and pick Top 3 stocks of the day
        day_candidates.sort(key=lambda x: x['score'], reverse=True)
        top_picks = day_candidates[:3]

        if not top_picks:
            continue

        # Step 2: Trade Execution on Top Picks
        day_trades_count = 0
        day_losses_count = 0

        for pick in top_picks:
            if day_trades_count >= 3 or day_losses_count >= 2:
                break # Daily limits reached

            sym = pick['symbol']
            g = pick['df']
            orb_h = pick['orb_h']
            orb_l = pick['orb_l']
            is_bull = pick['daily_bull']

            for i in range(3, min(len(g)-5, 20)): # 09:30 to 10:50 AM
                if day_trades_count >= 3 or day_losses_count >= 2:
                    break

                row = g.iloc[i]
                
                # LONG: Daily Bull + Breakout above ORB High + Price > VWAP + EMA9 > EMA21
                if is_bull and row['Close'] > orb_h and row['Close'] > row['VWAP'] and row['EMA9'] > row['EMA21']:
                    entry = row['Close']
                    sl = max(row['VWAP'], orb_l, entry - entry * 0.007)
                    sl_dist = entry - sl
                    if sl_dist < entry * 0.0050: # Enforce 0.50% min SL
                        sl_dist = entry * 0.0050
                        sl = entry - sl_dist

                    # Asymmetric Scale-Out Targets:
                    # Target 1 (+2.0R): Exit 50% & Move SL to Breakeven (+0.1R)
                    # Target 2 (+3.5R): Exit remaining 50%
                    tp1 = entry + (sl_dist * 2.0)
                    tp2 = entry + (sl_dist * 3.5)
                    be_sl = entry + (sl_dist * 0.1)

                    t1_hit = False
                    current_sl = sl
                    final_r = None

                    for j in range(i+1, len(g)):
                        c = g.iloc[j]

                        # Check Target 1 (+2.0R)
                        if not t1_hit and c['High'] >= tp1:
                            t1_hit = True
                            current_sl = be_sl # Trail remaining half to breakeven

                        # Check Stop Loss
                        if c['Low'] <= current_sl:
                            if not t1_hit:
                                final_r = -1.04 # Full stop hit (with slippage)
                            else:
                                # Half was exited at +2.0R, remaining half exited at +0.1R
                                final_r = round(0.5 * 1.96 + 0.5 * 0.06, 2) # = +1.01R net!
                            break

                        # Check Target 2 (+3.5R)
                        if t1_hit and c['High'] >= tp2:
                            final_r = round(0.5 * 1.96 + 0.5 * 3.46, 2) # = +2.71R net!
                            break

                        # EOD 15:15 Square-off
                        if c['Time'] >= time(15, 15):
                            r_eod = (c['Close'] - entry)/sl_dist - 0.04
                            if not t1_hit:
                                final_r = round(r_eod, 2)
                            else:
                                final_r = round(0.5 * 1.96 + 0.5 * max(0.06, r_eod), 2)
                            break

                    if final_r is not None:
                        trade_entry = {
                            'Date': dt,
                            'Time': row['Time'],
                            'Symbol': sym,
                            'Direction': 'BUY',
                            'R': final_r,
                            'Win': final_r > 0
                        }
                        portfolio_trades.append(trade_entry)
                        day_trades_count += 1
                        if final_r < 0:
                            day_losses_count += 1
                        break

                # SHORT: Daily Bear + Breakdown below ORB Low + Price < VWAP + EMA9 < EMA21
                elif (not is_bull) and row['Close'] < orb_l and row['Close'] < row['VWAP'] and row['EMA9'] < row['EMA21']:
                    entry = row['Close']
                    sl = min(row['VWAP'], orb_h, entry + entry * 0.007)
                    sl_dist = sl - entry
                    if sl_dist < entry * 0.0050: # Enforce 0.50% min SL
                        sl_dist = entry * 0.0050
                        sl = entry + sl_dist

                    tp1 = entry - (sl_dist * 2.0)
                    tp2 = entry - (sl_dist * 3.5)
                    be_sl = entry - (sl_dist * 0.1)

                    t1_hit = False
                    current_sl = sl
                    final_r = None

                    for j in range(i+1, len(g)):
                        c = g.iloc[j]

                        # Check Target 1 (+2.0R)
                        if not t1_hit and c['Low'] <= tp1:
                            t1_hit = True
                            current_sl = be_sl

                        # Check Stop Loss
                        if c['High'] >= current_sl:
                            if not t1_hit:
                                final_r = -1.04
                            else:
                                final_r = round(0.5 * 1.96 + 0.5 * 0.06, 2)
                            break

                        # Check Target 2 (+3.5R)
                        if t1_hit and c['Low'] <= tp2:
                            final_r = round(0.5 * 1.96 + 0.5 * 3.46, 2)
                            break

                        # EOD 15:15 Square-off
                        if c['Time'] >= time(15, 15):
                            r_eod = (entry - c['Close'])/sl_dist - 0.04
                            if not t1_hit:
                                final_r = round(r_eod, 2)
                            else:
                                final_r = round(0.5 * 1.96 + 0.5 * max(0.06, r_eod), 2)
                            break

                    if final_r is not None:
                        trade_entry = {
                            'Date': dt,
                            'Time': row['Time'],
                            'Symbol': sym,
                            'Direction': 'SELL',
                            'R': final_r,
                            'Win': final_r > 0
                        }
                        portfolio_trades.append(trade_entry)
                        day_trades_count += 1
                        if final_r < 0:
                            day_losses_count += 1
                        break

    res_df = pd.DataFrame(portfolio_trades)
    print(f"\nTotal Portfolio Trades Executed: {len(res_df)}")
    
    res_df['YM'] = pd.to_datetime(res_df['Date']).dt.to_period('M')
    
    total_trades = len(res_df)
    wins = res_df[res_df['R'] > 0]
    losses = res_df[res_df['R'] < 0]
    win_rate = (len(wins) / total_trades) * 100
    
    total_r = res_df['R'].sum()
    avg_win = wins['R'].mean()
    avg_loss = abs(losses['R'].mean())
    profit_factor = wins['R'].sum() / abs(losses['R'].sum())
    
    # Cumulative Drawdown
    cum_r = res_df['R'].cumsum()
    peak_r = cum_r.cummax()
    max_dd = (cum_r - peak_r).min()

    monthly = res_df.groupby('YM').agg(
        Trades=('R', 'count'),
        Wins=('Win', 'sum'),
        Total_R=('R', 'sum')
    ).reset_index()
    monthly['WinRate'] = round(monthly['Wins'] / monthly['Trades'] * 100, 1)
    monthly['Total_R'] = round(monthly['Total_R'], 1)
    monthly['Profit_INR_1k'] = (monthly['Total_R'] * 1000).astype(int)

    num_months = len(monthly)
    avg_r_month = total_r / num_months
    annual_r = total_r / (num_months / 12.0)
    calmar = abs(annual_r / max_dd)

    print("\n" + "="*70)
    print("      FINAL 18-STOCK INSTITUTIONAL ALPHA STRATEGY RESULTS")
    print("="*70)
    print(f"Horizon               : October 2022 to November 2026 ({num_months} Months)")
    print(f"Total Trades Taken    : {total_trades} (~{round(total_trades/num_months, 1)} trades/month, ~{round(total_trades/(num_months*21), 1)} trades/day)")
    print(f"Overall Win Rate      : {win_rate:.1f}%")
    print(f"Average Win (R)       : +{avg_win:.2f}R")
    print(f"Average Loss (R)      : -{avg_loss:.2f}R")
    print(f"Profit Factor         : {profit_factor:.2f}")
    print(f"Total Cumulative R    : +{total_r:.1f}R  (₹{int(total_r * 1000):,} @ ₹1k risk/trade)")
    print(f"Average Return / Month: +{avg_r_month:.1f}R  (₹{int(avg_r_month * 1000):,}/month)")
    print(f"Maximum Drawdown      : {max_dd:.1f}R")
    print(f"Calmar Ratio          : {calmar:.2f}")
    print("="*70)

    print("\nSample Monthly Performance (Last 15 Months):")
    print(monthly.tail(15).to_string(index=False))

    os.makedirs('reports', exist_ok=True)
    res_df.to_csv('reports/stock_alpha_master_trades.csv', index=False)
    monthly.to_csv('reports/stock_alpha_master_monthly.csv', index=False)

if __name__ == '__main__':
    stocks_data = load_all_stocks_5m(UNIVERSE_18)
    run_alpha_backtest(stocks_data)
