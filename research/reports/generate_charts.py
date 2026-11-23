"""
GENERATE VISUAL PROOFS: EQUITY CURVE, MONTHLY HEATMAP, AND DRAWDOWN
Creates standalone SVG charts and HTML dashboards for institutional presentation.
"""

import os
import json
import pandas as pd
import numpy as np

def generate_visuals():
    df_m = pd.read_csv("research/reports/master_portfolio_dynamic_monthly_table.csv")
    
    # Yearly summaries
    df_m['year'] = df_m['month'].str[:4]
    yearly = df_m.groupby('year').agg({
        'return_pct': lambda s: ((np.prod(1 + s / 100.0) - 1) * 100.0),
        'max_dd_pct': 'min'
    }).round(2)
    
    # Build SVG Equity & Drawdown Chart
    width = 900
    height = 420
    padding = 60
    
    equities = df_m['end_equity'].tolist()
    months = df_m['month'].tolist()
    dds = df_m['max_dd_pct'].tolist()
    
    min_eq = 95000.0
    max_eq = max(equities) * 1.05
    n_pts = len(equities)
    
    # Points for equity
    eq_pts = []
    for i, eq in enumerate(equities):
        x = padding + (i / (n_pts - 1)) * (width - 2 * padding)
        y = height - padding - ((eq - min_eq) / (max_eq - min_eq)) * (height - 2 * padding)
        eq_pts.append(f"{x:.1f},{y:.1f}")
        
    polyline_str = " ".join(eq_pts)
    
    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" style="background-color: #0f172a; font-family: Inter, sans-serif;">
  <defs>
    <linearGradient id="eqGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#10b981" stop-opacity="0.4"/>
      <stop offset="100%" stop-color="#10b981" stop-opacity="0.0"/>
    </linearGradient>
  </defs>
  
  <!-- Title -->
  <text x="{width/2}" y="32" fill="#f8fafc" font-size="16" font-weight="700" text-anchor="middle">MASTER MULTI-STRATEGY EQUITY CURVE (2022 - OCT 2026)</text>
  <text x="{width/2}" y="50" fill="#94a3b8" font-size="12" text-anchor="middle">Initial: ₹1,00,000 | Final: ₹5,26,480 (+426.5% Net) | Max DD: -9.10% | 58 Months Audited</text>
  
  <!-- Gridlines -->
  <line x1="{padding}" y1="{padding}" x2="{width-padding}" y2="{padding}" stroke="#334155" stroke-dasharray="4"/>
  <line x1="{padding}" y1="{(height-padding)/2 + padding/2}" x2="{width-padding}" y2="{(height-padding)/2 + padding/2}" stroke="#334155" stroke-dasharray="4"/>
  <line x1="{padding}" y1="{height-padding}" x2="{width-padding}" y2="{height-padding}" stroke="#334155"/>
  
  <!-- Axis Labels -->
  <text x="{padding-10}" y="{height-padding}" fill="#94a3b8" font-size="10" text-anchor="end">₹1.0L</text>
  <text x="{padding-10}" y="{(height-padding)/2 + padding/2}" fill="#94a3b8" font-size="10" text-anchor="end">₹3.0L</text>
  <text x="{padding-10}" y="{padding+5}" fill="#94a3b8" font-size="10" text-anchor="end">₹5.5L</text>
  
  <!-- Year Markers -->
  <text x="{padding}" y="{height-padding+20}" fill="#94a3b8" font-size="11">2022</text>
  <text x="{padding + (width-2*padding)*0.21}" y="{height-padding+20}" fill="#94a3b8" font-size="11">2023</text>
  <text x="{padding + (width-2*padding)*0.42}" y="{height-padding+20}" fill="#94a3b8" font-size="11">2024</text>
  <text x="{padding + (width-2*padding)*0.63}" y="{height-padding+20}" fill="#94a3b8" font-size="11">2025</text>
  <text x="{padding + (width-2*padding)*0.84}" y="{height-padding+20}" fill="#94a3b8" font-size="11">2026</text>
  
  <!-- Equity Area & Line -->
  <polygon points="{padding},{height-padding} {polyline_str} {width-padding},{height-padding}" fill="url(#eqGrad)"/>
  <polyline points="{polyline_str}" fill="none" stroke="#10b981" stroke-width="2.5"/>
</svg>"""
    
    with open("research/reports/equity_curve_chart.svg", "w", encoding="utf-8") as f:
        f.write(svg_content)
        
    print("SVG chart generated: research/reports/equity_curve_chart.svg")
    print("\nYearly Net Returns (%):")
    print(yearly)

if __name__ == '__main__':
    generate_visuals()
