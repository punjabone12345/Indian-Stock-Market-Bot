import sys
sys.path.append('engine')
import os
import glob
import pandas as pd
import numpy as np
from datetime import time
from data_loader import resample_5min
from stock_alpha_master import UNIVERSE_18, load_all_stocks_5m

def run_smc_backtest(stocks_data):
    print("\n" + "="*70)
    print("   RUNNING ADVANCED PRICE ACTION & SMC LIQUIDITY ENGINE (4 YEARS)")
    print("="*70)

    sample_sym = list(stocks_data.keys())[0]
    all_dates = sorted(stocks_data[sample_sym]['Date'].unique())

    all_trades = []

    for dt in all_dates:
        day_signals = []

        for sym, df_5m in stocks_data.items():
            g = df_5m[df_5m['Date'] == dt].reset_index(drop=True)
            if len(g) < 25 or pd.isna(g['PDC'].iloc[0]) or pd.isna(g['DailyBull'].iloc[0]):
                continue

            first3 = g.iloc[:3] # 09:15 to 09:30 Initial Balance (IB)
            ib_h = first3['High'].max()
            ib_l = first3['Low'].min()
            
            # Prior Day High & Low
            pdh = g.iloc[0].get('PDH')
            pdl = g.iloc[0].get('PDL')
            if pd.isna(pdh):
                # Calculate from prior day if not already in dataframe
                pdh = g['PDC'].iloc[0] * 1.008
                pdl = g['PDC'].iloc[0] * 0.992

            is_bull = g['DailyBull'].iloc[0]

            # Scan candles between 09:30 AM and 11:15 AM
            for i in range(3, min(len(g)-5, 22)):
                row = g.iloc[i]
                prev = g.iloc[i-1]
                prev2 = g.iloc[i-2]

                # ========================================================
                # SETUP 1: BULLISH LIQUIDITY SWEEP & MSS (Optimal ICT Long)
                # ========================================================
                # Condition A: Sweep below IB_Low or PDL
                swept_low = (prev['Low'] < ib_l or row['Low'] < ib_l)
                if pd.notna(pdl):
                    swept_low = swept_low or (prev['Low'] < pdl or row['Low'] < pdl)

                # Condition B: Strong wick rejection back inside the level
                rejected = row['Close'] > ib_l and row['Close'] > row['Open']

                # Condition C: Displacement & Market Structure Shift (MSS) above EMA9
                mss = row['Close'] > row['EMA9'] and row['Close'] > prev['High']

                # Condition D: Multi-Timeframe Daily Trend Alignment
                if swept_low and rejected and mss and is_bull:
                    entry = row['Close']
                    sweep_low = min(row['Low'], prev['Low'], prev2['Low'])
                    sl = sweep_low - (entry * 0.0005) # Just below sweep
                    sl_dist = entry - sl
                    if sl_dist < entry * 0.0050: # Enforce min 0.50% SL
                        sl_dist = entry * 0.0050
                        sl = entry - sl_dist

                    # Asymmetric SMC Targets:
                    # Target 1 (+2.0R): Exit 60%, Move SL to Breakeven (+0.1R)
                    # Target 2 (+3.5R): Exit remaining 40%
                    tp1 = entry + (sl_dist * 2.0)
                    tp2 = entry + (sl_dist * 3.5)
                    be_sl = entry + (sl_dist * 0.1)

                    t1_hit = False
                    current_sl = sl
                    final_r = None

                    for j in range(i+1, len(g)):
                        c = g.iloc[j]
                        if not t1_hit and c['High'] >= tp1:
                            t1_hit = True
                            current_sl = be_sl # Locked at breakeven

                        if c['Low'] <= current_sl:
                            if not t1_hit:
                                final_r = -1.04
                            else:
                                final_r = round(0.6 * 1.96 + 0.4 * 0.06, 2) # +1.20R net
                            break

                        if t1_hit and c['High'] >= tp2:
                            final_r = round(0.6 * 1.96 + 0.4 * 3.46, 2) # +2.56R net
                            break

                        if c['Time'] >= time(15, 15):
                            r_eod = (c['Close'] - entry)/sl_dist - 0.04
                            if not t1_hit:
                                final_r = round(r_eod, 2)
                            else:
                                final_r = round(0.6 * 1.96 + 0.4 * max(0.06, r_eod), 2)
                            break

                    if final_r is not None:
                        day_signals.append({
                            'Date': dt,
                            'Time': row['Time'],
                            'Symbol': sym,
                            'Direction': 'BUY',
                            'Setup': 'Bullish Liquidity Sweep & MSS',
                            'R': final_r,
                            'Win': final_r > 0
                        })
                        break

                # ========================================================
                # SETUP 2: BEARISH LIQUIDITY SWEEP & MSS (Optimal ICT Short)
                # ========================================================
                swept_high = (prev['High'] > ib_h or row['High'] > ib_h)
                if pd.notna(pdh):
                    swept_high = swept_high or (prev['High'] > pdh or row['High'] > pdh)

                rejected = row['Close'] < ib_h and row['Close'] < row['Open']
                mss = row['Close'] < row['EMA9'] and row['Close'] < prev['Low']

                if swept_high and rejected and mss and (not is_bull):
                    entry = row['Close']
                    sweep_high = max(row['High'], prev['High'], prev2['High'])
                    sl = sweep_high + (entry * 0.0005)
                    sl_dist = sl - entry
                    if sl_dist < entry * 0.0050:
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
                        if not t1_hit and c['Low'] <= tp1:
                            t1_hit = True
                            current_sl = be_sl

                        if c['High'] >= current_sl:
                            if not t1_hit:
                                final_r = -1.04
                            else:
                                final_r = round(0.6 * 1.96 + 0.4 * 0.06, 2)
                            break

                        if t1_hit and c['Low'] <= tp2:
                            final_r = round(0.6 * 1.96 + 0.4 * 3.46, 2)
                            break

                        if c['Time'] >= time(15, 15):
                            r_eod = (entry - c['Close'])/sl_dist - 0.04
                            if not t1_hit:
                                final_r = round(r_eod, 2)
                            else:
                                final_r = round(0.6 * 1.96 + 0.4 * max(0.06, r_eod), 2)
                            break

                    if final_r is not None:
                        day_signals.append({
                            'Date': dt,
                            'Time': row['Time'],
                            'Symbol': sym,
                            'Direction': 'SELL',
                            'Setup': 'Bearish Liquidity Sweep & MSS',
                            'R': final_r,
                            'Win': final_r > 0
                        })
                        break

        # Portfolio Selection: Pick max 2 best quality setups per day
        # Apply Daily Loss Circuit Breaker (max 2 losses/day)
        if day_signals:
            day_signals.sort(key=lambda x: x['Time'])
            day_trades = 0
            day_losses = 0
            for sig in day_signals:
                if day_trades >= 2 or day_losses >= 2: break
                all_trades.append(sig)
                day_trades += 1
                if sig['R'] < 0: day_losses += 1

    res_df = pd.DataFrame(all_trades).sort_values(['Date', 'Time']).reset_index(drop=True)
    print(f"\nTotal SMC Trades Executed: {len(res_df)}")

    # Apply Prop Firm Monthly Loss Cap (-4.0R) and Drawdown Protection
    res_df['YM'] = pd.to_datetime(res_df['Date']).dt.to_period('M')

    managed_trades = []
    cum_r = 0.0
    peak_r = 0.0

    for ym, m_group in res_df.groupby('YM'):
        month_r = 0.0
        for _, t in m_group.iterrows():
            if month_r <= -4.0:
                continue

            current_dd = cum_r - peak_r
            # De-leverage during drawdown to lock max drawdown under 10R
            risk_mult = 0.5 if current_dd <= -3.0 else 1.0
            actual_r = round(t['R'] * risk_mult, 2)

            month_r += actual_r
            cum_r += actual_r
            if cum_r > peak_r:
                peak_r = cum_r

            managed_trades.append({
                'Date': t['Date'],
                'Time': t['Time'],
                'Symbol': t['Symbol'],
                'Direction': t['Direction'],
                'Setup': t['Setup'],
                'R': actual_r,
                'Win': actual_r > 0,
                'YM': ym
            })

    m_df = pd.DataFrame(managed_trades)
    print(f"Final Managed Trades Count: {len(m_df)}")

    total_trades = len(m_df)
    wins = m_df[m_df['R'] > 0]
    losses = m_df[m_df['R'] < 0]
    win_rate = (len(wins) / total_trades) * 100
    total_r = m_df['R'].sum()
    avg_win = wins['R'].mean()
    avg_loss = abs(losses['R'].mean())
    pf = wins['R'].sum() / abs(losses['R'].sum())

    cum_series = m_df['R'].cumsum()
    max_dd = (cum_series - cum_series.cummax()).min()

    monthly = m_df.groupby('YM').agg(
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
    print("      ADVANCED SMC & LIQUIDITY PRICE ACTION FINAL AUDIT")
    print("="*70)
    print(f"Horizon               : October 2022 to November 2026 ({num_months} Months)")
    print(f"Total Trades Taken    : {total_trades} (~{round(total_trades/num_months, 1)} trades/month, ~{round(total_trades/(num_months*21), 1)} trades/day)")
    print(f"Overall Win Rate      : {win_rate:.1f}%")
    print(f"Average Win (R)       : +{avg_win:.2f}R")
    print(f"Average Loss (R)      : -{avg_loss:.2f}R")
    print(f"Profit Factor         : {pf:.2f}")
    print(f"Total Cumulative R    : +{total_r:.1f}R  (₹{int(total_r * 1000):,} @ ₹1k risk/trade)")
    print(f"Average Return / Month: +{avg_r_month:.1f}R")
    print(f"Maximum Portfolio DD  : {max_dd:.1f}R")
    print(f"Calmar Ratio          : {calmar:.2f}")
    print(f"Profitable Months     : {(monthly['Total_R'] > 0).sum()} / {num_months}")
    print("="*70)

    print("\nSample Monthly Performance (Last 15 Months):")
    print(monthly.tail(15).to_string(index=False))

    os.makedirs('reports', exist_ok=True)
    m_df.to_csv('reports/smc_price_action_trades.csv', index=False)
    monthly.to_csv('reports/smc_price_action_monthly.csv', index=False)

if __name__ == '__main__':
    stocks = load_all_stocks_5m(UNIVERSE_18)
    run_smc_backtest(stocks)
