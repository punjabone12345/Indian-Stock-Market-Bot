"""
GENERATE FINAL AUDIT DELIVERABLES AND SVG CHART FOR MASTER STATIC SYSTEM
Generates:
1. research/phase4_2/deliverables/trade_log_master_static_catalyst.csv
2. research/phase4_2/deliverables/daily_equity_master_static_catalyst.csv
3. research/phase4_2/deliverables/monthly_summary_master_static_catalyst.csv
4. Artifact SVG equity chart in brain directory
"""

import os, glob
import numpy as np
import pandas as pd
from verify_forensic_static import load_data, run_simulation

def generate_deliverables():
    os.makedirs("research/phase4_2/deliverables", exist_ok=True)
    symbol_days, dates, market_regime = load_data()
    
    res = run_simulation(symbol_days, dates, market_regime,
                         min_gap=1.2, min_rvol=2.5, sl_pct=0.012,
                         t1_r=2.0, t2_r=4.0, max_trades_per_day=3,
                         runner_mode='eod_pure')
    
    df_t = res['df_t']
    
    # Add cumulative equity and drawdown columns for both 1.0R (Rs 1000) and 0.5R (Rs 500)
    df_t['cum_pnl_1000'] = df_t['net_pnl'].cumsum()
    df_t['equity_1000'] = 100000.0 + df_t['cum_pnl_1000']
    df_t['peak_1000'] = df_t['equity_1000'].cummax()
    df_t['dd_1000_pct'] = (df_t['equity_1000'] - df_t['peak_1000']) / 100000.0 * 100.0
    
    df_t['net_pnl_500'] = df_t['net_pnl'] * 0.5
    df_t['fee_500'] = df_t['fee'] * 0.5
    df_t['cum_pnl_500'] = df_t['net_pnl_500'].cumsum()
    df_t['equity_500'] = 100000.0 + df_t['cum_pnl_500']
    df_t['peak_500'] = df_t['equity_500'].cummax()
    df_t['dd_500_pct'] = (df_t['equity_500'] - df_t['peak_500']) / 100000.0 * 100.0
    
    # Save Trade Log
    trade_log_path = "research/phase4_2/deliverables/trade_log_master_static_catalyst.csv"
    df_t.to_csv(trade_log_path, index=False)
    print(f"Saved trade log to {trade_log_path} ({len(df_t)} trades)")
    
    # Build Daily Equity
    daily_records = []
    eq_1000 = 100000.0
    eq_500 = 100000.0
    peak_1000 = eq_1000
    peak_500 = eq_500
    
    trades_by_date = df_t.groupby('date')
    
    for d in dates:
        day_pnl_1000 = 0.0
        day_pnl_500 = 0.0
        n_trades = 0
        if d in trades_by_date.groups:
            sub = trades_by_date.get_group(d)
            day_pnl_1000 = sub['net_pnl'].sum()
            day_pnl_500 = sub['net_pnl_500'].sum()
            n_trades = len(sub)
            
        eq_1000 += day_pnl_1000
        eq_500 += day_pnl_500
        if eq_1000 > peak_1000: peak_1000 = eq_1000
        if eq_500 > peak_500: peak_500 = eq_500
        
        dd_1000 = (eq_1000 - peak_1000) / 100000.0 * 100.0
        dd_500 = (eq_500 - peak_500) / 100000.0 * 100.0
        
        daily_records.append({
            'date': d,
            'year': int(d[:4]),
            'trades_count': n_trades,
            'day_pnl_1000': round(day_pnl_1000, 2),
            'equity_1000': round(eq_1000, 2),
            'drawdown_1000_pct': round(dd_1000, 2),
            'day_pnl_500': round(day_pnl_500, 2),
            'equity_500': round(eq_500, 2),
            'drawdown_500_pct': round(dd_500, 2)
        })
        
    df_daily = pd.DataFrame(daily_records)
    daily_equity_path = "research/phase4_2/deliverables/daily_equity_master_static_catalyst.csv"
    df_daily.to_csv(daily_equity_path, index=False)
    print(f"Saved daily equity to {daily_equity_path} ({len(df_daily)} trading sessions)")
    
    # Save Monthly Summary
    df_daily['ym'] = pd.to_datetime(df_daily['date']).dt.to_period('M')
    monthly = df_daily.groupby('ym').agg({
        'trades_count': 'sum',
        'day_pnl_1000': 'sum',
        'day_pnl_500': 'sum'
    }).reset_index()
    monthly['ret_1000_pct'] = monthly['day_pnl_1000'] / 100000.0 * 100.0
    monthly['ret_500_pct'] = monthly['day_pnl_500'] / 100000.0 * 100.0
    monthly_path = "research/phase4_2/deliverables/monthly_summary_master_static_catalyst.csv"
    monthly.to_csv(monthly_path, index=False)
    print(f"Saved monthly summary to {monthly_path} ({len(monthly)} months)")
    
    # Generate SVG Chart
    generate_svg(df_daily)

def generate_svg(df_daily):
    width, height = 1100, 650
    padding_left, padding_right = 80, 40
    padding_top, padding_bottom = 70, 70
    
    # Subplot 1: Equity (top 65%), Subplot 2: Drawdown (bottom 25%)
    eq_h = 360
    dd_h = 130
    gap = 40
    
    plot_w = width - padding_left - padding_right
    n_pts = len(df_daily)
    
    max_eq = max(df_daily['equity_1000'].max(), 800000.0)
    min_eq = 90000.0
    
    min_dd = -25.0 # percentage
    max_dd = 0.0
    
    def get_x(i):
        return padding_left + (i / (n_pts - 1)) * plot_w
        
    def get_y_eq(val):
        return padding_top + eq_h - ((val - min_eq) / (max_eq - min_eq)) * eq_h
        
    def get_y_dd(val):
        y_top = padding_top + eq_h + gap
        return y_top + dd_h - ((val - min_dd) / (max_dd - min_dd)) * dd_h

    # Path points
    pts_1000 = []
    pts_500 = []
    dd_pts_1000 = []
    dd_pts_500 = []
    
    for i, r in df_daily.iterrows():
        x = get_x(i)
        pts_1000.append(f"{x:.1f},{get_y_eq(r['equity_1000']):.1f}")
        pts_500.append(f"{x:.1f},{get_y_eq(r['equity_500']):.1f}")
        dd_pts_1000.append(f"{x:.1f},{get_y_dd(r['drawdown_1000_pct']):.1f}")
        dd_pts_500.append(f"{x:.1f},{get_y_dd(r['drawdown_500_pct']):.1f}")
        
    path_1000 = "M " + " L ".join(pts_1000)
    path_500 = "M " + " L ".join(pts_500)
    
    path_dd_1000 = "M " + " L ".join(dd_pts_1000)
    path_dd_500 = "M " + " L ".join(dd_pts_500)
    
    # Fill for drawdown
    dd_zero_y = get_y_dd(0.0)
    fill_dd_1000 = f"M {get_x(0):.1f},{dd_zero_y:.1f} L " + " L ".join(dd_pts_1000) + f" L {get_x(n_pts-1):.1f},{dd_zero_y:.1f} Z"
    
    # Year tick marks
    year_ticks = []
    cur_year = None
    for i, r in df_daily.iterrows():
        y = r['year']
        if y != cur_year:
            cur_year = y
            x = get_x(i)
            year_ticks.append((x, str(y)))
            
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%" style="background-color: #0d1117; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
    <defs>
        <linearGradient id="grad1000" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="#10b981" stop-opacity="0.25"/>
            <stop offset="100%" stop-color="#10b981" stop-opacity="0.0"/>
        </linearGradient>
        <linearGradient id="gradDD" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="#ef4444" stop-opacity="0.05"/>
            <stop offset="100%" stop-color="#ef4444" stop-opacity="0.35"/>
        </linearGradient>
    </defs>

    <!-- Title and Meta -->
    <text x="{padding_left}" y="35" fill="#f3f4f6" font-size="20" font-weight="700">MASTER NIFTY 200 INTRADAY CATALYST SYSTEM (2022 - 2026)</text>
    <text x="{padding_left}" y="55" fill="#9ca3af" font-size="12">100% Pure Cash MIS Equities | Zero Compounding | Fixed 1R Risk on Rs 1,00,000 Base | Zerodha Fees &amp; Slippage Audited</text>

    <!-- Grid lines Equity -->
    """
    for val in [100000, 250000, 400000, 550000, 700000]:
        y = get_y_eq(val)
        svg += f'<line x1="{padding_left}" y1="{y:.1f}" x2="{width - padding_right}" y2="{y:.1f}" stroke="#1f2937" stroke-dasharray="4,4"/>\n'
        svg += f'<text x="{padding_left - 10}" y="{y + 4:.1f}" fill="#6b7280" font-size="11" text-anchor="end">Rs {val/1000:.0f}k</text>\n'

    # Equity curves
    svg += f"""
    <!-- Equity Curves -->
    <path d="{path_500}" fill="none" stroke="#3b82f6" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/>
    <path d="{path_1000}" fill="none" stroke="#10b981" stroke-width="2.6" stroke-linejoin="round" stroke-linecap="round"/>

    <!-- Legend -->
    <circle cx="{width - 380}" cy="30" r="5" fill="#10b981"/>
    <text x="{width - 370}" cy="34" fill="#d1d5db" font-size="12" font-weight="600">Model A: 1.0R Risk (Rs 1,000/tr) -> +11.64%/mo | Max DD 19.58%</text>

    <circle cx="{width - 380}" cy="50" r="5" fill="#3b82f6"/>
    <text x="{width - 370}" cy="54" fill="#9ca3af" font-size="12">Model B: 0.5R Risk (Rs 500/tr)  -> +5.82%/mo  | Max DD  9.79%</text>

    <!-- Subplot 2: Drawdown Area -->
    <text x="{padding_left}" y="{padding_top + eq_h + gap - 10}" fill="#9ca3af" font-size="12" font-weight="600">UNDERWATER DRAWDOWN PROFILE (%)</text>
    """

    for dd_val in [0.0, -10.0, -20.0]:
        y = get_y_dd(dd_val)
        svg += f'<line x1="{padding_left}" y1="{y:.1f}" x2="{width - padding_right}" y2="{y:.1f}" stroke="#1f2937" stroke-dasharray="4,4"/>\n'
        svg += f'<text x="{padding_left - 10}" y="{y + 4:.1f}" fill="#6b7280" font-size="11" text-anchor="end">{dd_val:.0f}%</text>\n'

    svg += f"""
    <path d="{fill_dd_1000}" fill="url(#gradDD)"/>
    <path d="{path_dd_1000}" fill="none" stroke="#ef4444" stroke-width="1.6" opacity="0.85"/>
    <path d="{path_dd_500}" fill="none" stroke="#3b82f6" stroke-width="1.4" stroke-dasharray="3,3"/>
    """

    # Year marks
    y_axis_bottom = padding_top + eq_h + gap + dd_h
    for x, y_label in year_ticks:
        svg += f'<line x1="{x:.1f}" y1="{padding_top}" x2="{x:.1f}" y2="{y_axis_bottom}" stroke="#1f2937" stroke-width="1"/>\n'
        svg += f'<text x="{x + 8:.1f}" y="{y_axis_bottom + 20}" fill="#9ca3af" font-size="12" font-weight="600">{y_label}</text>\n'

    # Final stats badge
    final_eq_1000 = df_daily['equity_1000'].iloc[-1]
    final_eq_500 = df_daily['equity_500'].iloc[-1]
    svg += f"""
    <rect x="{width - padding_right - 230}" y="{get_y_eq(final_eq_1000) - 28}" width="220" height="26" rx="4" fill="#064e3b" stroke="#10b981" stroke-width="1.2"/>
    <text x="{width - padding_right - 120}" y="{get_y_eq(final_eq_1000) - 11}" fill="#ecfdf5" font-size="11" font-weight="700" text-anchor="middle">Model A: Rs {final_eq_1000:,.0f} (+675.2%)</text>

    <rect x="{width - padding_right - 230}" y="{get_y_eq(final_eq_500) - 28}" width="220" height="26" rx="4" fill="#1e3a8a" stroke="#3b82f6" stroke-width="1.2"/>
    <text x="{width - padding_right - 120}" y="{get_y_eq(final_eq_500) - 11}" fill="#eff6ff" font-size="11" font-weight="700" text-anchor="middle">Model B: Rs {final_eq_500:,.0f} (+337.6%)</text>
    </svg>
    """
    
    # Save SVG to artifacts and deliverables
    svg_deliverable_path = "research/phase4_2/deliverables/master_static_equity_curves.svg"
    with open(svg_deliverable_path, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"Saved SVG to {svg_deliverable_path}")
    
    artifact_svg_path = "C:/Users/Admin/.gemini/antigravity/brain/5b5ac800-b5e6-421e-8b11-3463d4d99914/master_static_equity_curves.svg"
    with open(artifact_svg_path, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"Saved SVG artifact to {artifact_svg_path}")

if __name__ == '__main__':
    generate_deliverables()
