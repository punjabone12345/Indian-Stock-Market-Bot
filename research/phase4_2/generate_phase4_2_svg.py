"""
Generates an SVG chart of the Phase 4.2 Controlled Comparison Equity Curves (2022 - 2026)
Shows the honest, unvarnished equity trajectories of all 5 audited versions.
"""

import pandas as pd
import numpy as np

def generate_svg():
    df_v1 = pd.read_csv("research/phase4_2/reports/daily_equity_V1_ORIGINAL_ORB.csv")
    df_v2 = pd.read_csv("research/phase4_2/reports/daily_equity_V2_WICK_ORB.csv")
    df_v3 = pd.read_csv("research/phase4_2/reports/daily_equity_V3_CLOSE_CONFIRMED_ORB.csv")
    df_v4 = pd.read_csv("research/phase4_2/reports/daily_equity_V4_CORRECTED_VWAP_GOVERNOR.csv")
    df_v5 = pd.read_csv("research/phase4_2/reports/daily_equity_V5_COMBINED_PORTFOLIO.csv")
    
    width = 1000
    height = 550
    padding = 60
    
    dates = df_v1['date'].tolist()
    e1 = df_v1['closed_equity'].tolist()
    e2 = df_v2['closed_equity'].tolist()
    e3 = df_v3['closed_equity'].tolist()
    e4 = df_v4['closed_equity'].tolist()
    e5 = df_v5['closed_equity'].tolist()
    
    all_vals = e1 + e2 + e3 + e4 + e5
    min_val = min(all_vals) * 0.95
    max_val = max(all_vals) * 1.05
    n_pts = len(dates)
    
    def get_coords(series):
        pts = []
        for i, val in enumerate(series):
            x = padding + (i / (n_pts - 1)) * (width - 2 * padding)
            y = height - padding - ((val - min_val) / (max_val - min_val)) * (height - 2 * padding)
            pts.append(f"{x:.1f},{y:.1f}")
        return " ".join(pts)
        
    pts_e1 = get_coords(e1)
    pts_e2 = get_coords(e2)
    pts_e3 = get_coords(e3)
    pts_e4 = get_coords(e4)
    pts_e5 = get_coords(e5)
    
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%" style="background-color: #0d1117; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
  <!-- Title & Subtitle -->
  <text x="{padding}" y="35" fill="#f0f6fc" font-size="18" font-weight="600">Phase 4.2 Forensic Audit: Realistic Execution Equity Curves</text>
  <text x="{padding}" y="52" fill="#8b949e" font-size="12">1,182 Trading Sessions | Next-Candle Execution | Real Zerodha Fees &amp; Slippage Deducted | Zero Look-Ahead</text>

  <!-- Horizontal Grid Lines -->
'''
    for i in range(5):
        val = min_val + (i / 4.0) * (max_val - min_val)
        y = height - padding - (i / 4.0) * (height - 2 * padding)
        svg += f'  <line x1="{padding}" y1="{y:.1f}" x2="{width - padding}" y2="{y:.1f}" stroke="#21262d" stroke-dasharray="4,4"/>\n'
        svg += f'  <text x="{padding - 10}" y="{y + 4:.1f}" fill="#8b949e" font-size="11" text-anchor="end">Rs {val/1000:,.0f}k</text>\n'

    sample_indices = [0, int(n_pts*0.25), int(n_pts*0.5), int(n_pts*0.75), n_pts-1]
    for idx in sample_indices:
        x = padding + (idx / (n_pts - 1)) * (width - 2 * padding)
        d_label = dates[idx][:7]
        svg += f'  <text x="{x:.1f}" y="{height - padding + 22}" fill="#8b949e" font-size="11" text-anchor="middle">{d_label}</text>\n'

    # Baseline 100k line
    y_100k = height - padding - ((100000.0 - min_val) / (max_val - min_val)) * (height - 2 * padding)
    svg += f'  <line x1="{padding}" y1="{y_100k:.1f}" x2="{width - padding}" y2="{y_100k:.1f}" stroke="#f85149" stroke-width="1.5" stroke-dasharray="6,3"/>\n'
    svg += f'  <text x="{width - padding + 5}" y="{y_100k + 4:.1f}" fill="#f85149" font-size="11">Initial (Rs 100k)</text>\n'

    # Polylines
    svg += f'''
  <!-- Version 1: Original ORB (Red) -->
  <polyline fill="none" stroke="#ef4444" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" points="{pts_e1}"/>
  
  <!-- Version 2: Wick Breakout Corrected (Orange) -->
  <polyline fill="none" stroke="#f97316" stroke-width="2.0" stroke-linecap="round" stroke-linejoin="round" points="{pts_e2}"/>

  <!-- Version 3: Close Confirmed Breakout (Yellow) -->
  <polyline fill="none" stroke="#eab308" stroke-width="2.0" stroke-linecap="round" stroke-linejoin="round" points="{pts_e3}"/>

  <!-- Version 4: Corrected VWAP Governor (Cyan) -->
  <polyline fill="none" stroke="#06b6d4" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" points="{pts_e4}"/>

  <!-- Version 5: Fully Corrected Combined Portfolio (Purple) -->
  <polyline fill="none" stroke="#a855f7" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" points="{pts_e5}"/>

  <!-- Legend -->
  <g transform="translate({width - 380}, 20)">
    <rect x="0" y="0" width="360" height="110" rx="6" fill="#161b22" stroke="#30363d"/>
    <line x1="15" y1="18" x2="40" y2="18" stroke="#ef4444" stroke-width="2"/>
    <text x="50" y="22" fill="#f0f6fc" font-size="11">V1: Original ORB (CAGR -25.4%, MaxDD 78.8%)</text>
    <line x1="15" y1="36" x2="40" y2="36" stroke="#f97316" stroke-width="2"/>
    <text x="50" y="40" fill="#f0f6fc" font-size="11">V2: Wick Breakout Corrected (CAGR -3.9%, DD 29.6%)</text>
    <line x1="15" y1="54" x2="40" y2="54" stroke="#eab308" stroke-width="2"/>
    <text x="50" y="58" fill="#f0f6fc" font-size="11">V3: Close Confirmed Breakout (CAGR -6.4%, DD 30.9%)</text>
    <line x1="15" y1="72" x2="40" y2="72" stroke="#06b6d4" stroke-width="2"/>
    <text x="50" y="76" fill="#f0f6fc" font-size="11">V4: Corrected VWAP Governor (CAGR -7.2%, DD 33.9%)</text>
    <line x1="15" y1="90" x2="40" y2="90" stroke="#a855f7" stroke-width="2.5"/>
    <text x="50" y="94" fill="#a855f7" font-weight="600" font-size="11">V5: Fully Corrected Combined (CAGR -6.2%, DD 30.1%)</text>
  </g>
</svg>
'''
    with open("research/phase4_2/reports/phase4_2_equity_curves.svg", "w") as f:
        f.write(svg)
        
    art_path = "C:/Users/Admin/.gemini/antigravity/brain/5b5ac800-b5e6-421e-8b11-3463d4d99914/phase4_2_equity_curves.svg"
    with open(art_path, "w") as f:
        f.write(svg)
        
    print("Generated Phase 4.2 SVG equity curve chart.")

if __name__ == '__main__':
    generate_svg()
