"""
Generates an SVG chart of the Phase 3 Portfolio Equity Curves (2022 - 2026)
"""

import pandas as pd
import numpy as np

def generate_svg():
    df = pd.read_csv("research/phase3/reports/task4_portfolio_daily_equity.csv")
    
    width = 1000
    height = 550
    padding = 60
    
    dates = df['date'].tolist()
    m1 = df['equity_m1_vwap_base'].tolist()
    m2 = df['equity_m2_vwap_dyn'].tolist()
    m4 = df['equity_m4_ensemble_trio'].tolist()
    m5 = df['equity_m5_ensemble_dyn'].tolist()
    
    all_vals = m1 + m2 + m4 + m5
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
        
    pts_m1 = get_coords(m1)
    pts_m2 = get_coords(m2)
    pts_m4 = get_coords(m4)
    pts_m5 = get_coords(m5)
    
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%" style="background-color: #0d1117; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
  <defs>
    <linearGradient id="gridGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#30363d" stop-opacity="0.3"/>
      <stop offset="100%" stop-color="#30363d" stop-opacity="0.1"/>
    </linearGradient>
  </defs>

  <!-- Title & Subtitle -->
  <text x="{padding}" y="35" fill="#f0f6fc" font-size="18" font-weight="600">NSE Intraday Systematic Equity Curves (2022 - 2026)</text>
  <text x="{padding}" y="52" fill="#8b949e" font-size="12">1,182 Trading Sessions | 100% Cash Equities | True Brokerage, STT, Exchange Fees Deducted</text>

  <!-- Horizontal Grid Lines -->
'''
    # Add 5 grid lines
    for i in range(5):
        val = min_val + (i / 4.0) * (max_val - min_val)
        y = height - padding - (i / 4.0) * (height - 2 * padding)
        svg += f'  <line x1="{padding}" y1="{y:.1f}" x2="{width - padding}" y2="{y:.1f}" stroke="#21262d" stroke-dasharray="4,4"/>\n'
        svg += f'  <text x="{padding - 10}" y="{y + 4:.1f}" fill="#8b949e" font-size="11" text-anchor="end">Rs {val/1000:,.0f}k</text>\n'

    # Date labels on X axis
    sample_indices = [0, int(n_pts*0.25), int(n_pts*0.5), int(n_pts*0.75), n_pts-1]
    for idx in sample_indices:
        x = padding + (idx / (n_pts - 1)) * (width - 2 * padding)
        d_label = dates[idx][:7]
        svg += f'  <text x="{x:.1f}" y="{height - padding + 22}" fill="#8b949e" font-size="11" text-anchor="middle">{d_label}</text>\n'

    # Polylines
    svg += f'''
  <!-- Model 1: Standalone VWAP Base (Cyan) -->
  <polyline fill="none" stroke="#38bdf8" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" points="{pts_m1}"/>
  
  <!-- Model 2: Standalone VWAP Dyn Breaker (Blue) -->
  <polyline fill="none" stroke="#818cf8" stroke-width="2.0" stroke-linecap="round" stroke-linejoin="round" points="{pts_m2}"/>

  <!-- Model 4: Ensemble Trio (Green) -->
  <polyline fill="none" stroke="#34d399" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" points="{pts_m4}"/>

  <!-- Model 5: Ensemble Trio + Dyn Breaker (Gold - Top Institutional) -->
  <polyline fill="none" stroke="#fbbf24" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" points="{pts_m5}"/>

  <!-- Legend -->
  <g transform="translate({width - 380}, 20)">
    <rect x="0" y="0" width="360" height="90" rx="6" fill="#161b22" stroke="#30363d"/>
    <line x1="15" y1="20" x2="40" y2="20" stroke="#38bdf8" stroke-width="2.5"/>
    <text x="50" y="24" fill="#f0f6fc" font-size="11">VWAP Retest Base (CAGR 39.8%, MaxDD 11.9%)</text>
    <line x1="15" y1="40" x2="40" y2="40" stroke="#818cf8" stroke-width="2"/>
    <text x="50" y="44" fill="#f0f6fc" font-size="11">VWAP + Dyn Breaker (CAGR 35.9%, MaxDD 6.6%)</text>
    <line x1="15" y1="60" x2="40" y2="60" stroke="#34d399" stroke-width="2.5"/>
    <text x="50" y="64" fill="#f0f6fc" font-size="11">Ensemble Trio Base (CAGR 33.2%, WinMo 79.0%)</text>
    <line x1="15" y1="80" x2="40" y2="80" stroke="#fbbf24" stroke-width="2.5"/>
    <text x="50" y="84" fill="#fbbf24" font-weight="600" font-size="11">Master Ensemble + Dyn (CAGR 31.4%, MaxDD 6.1%)</text>
  </g>
</svg>
'''
    with open("research/phase3/reports/phase3_equity_curves.svg", "w") as f:
        f.write(svg)
        
    # Copy to artifact directory
    art_path = "C:/Users/Admin/.gemini/antigravity/brain/5b5ac800-b5e6-421e-8b11-3463d4d99914/phase3_equity_curves.svg"
    with open(art_path, "w") as f:
        f.write(svg)
        
    print("Generated SVG equity curve chart.")

if __name__ == '__main__':
    generate_svg()
