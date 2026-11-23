# Phase 4.2: Institutional Execution and Risk Engine Audit — Reproducible Instructions

This document provides exact commands to independently reproduce the execution, risk engine, and transaction friction audit for the Indian National Stock Exchange (NSE).

## Execution Guide

### 1. Run Complete ORB Execution Audit
Compares the Original ORB vs Wick-Breakout Corrected vs Close-Confirmed Breakout:
```bash
python -u research/phase4_2/audit_orb_execution.py
```
- Output: `research/phase4_2/reports/orb_execution_audit_summary.json`
- Output: `research/phase4_2/reports/trade_log_V1_ORIGINAL.csv`
- Output: `research/phase4_2/reports/trade_log_V2_WICK_CORRECTED.csv`
- Output: `research/phase4_2/reports/trade_log_V3_CLOSE_CONFIRMED.csv`

### 2. Run Complete VWAP Execution Audit
Audits VWAP Pullback Retest under retroactive same-bar fills vs next-bar market orders vs next-bar limit retests:
```bash
python -u research/phase4_2/audit_vwap_execution.py
```
- Output: `research/phase4_2/reports/vwap_execution_audit_summary.json`
- Output: `research/phase4_2/reports/vwap_trade_log_V1_ORIGINAL_RETRO.csv`
- Output: `research/phase4_2/reports/vwap_trade_log_V2_NEXT_BAR_MARKET.csv`
- Output: `research/phase4_2/reports/vwap_trade_log_V3_NEXT_BAR_LIMIT_RETEST.csv`

### 3. Run Controlled Comparisons (5 Versions)
Runs all 5 controlled versions with 5-minute marked-to-market (MTM) equity tracking, MIS 5x leverage enforcement, and dynamic risk allocations:
```bash
python -u research/phase4_2/run_controlled_comparison.py
```
- Output: `research/phase4_2/reports/phase4_2_controlled_comparison_matrix.json`
- Output: `research/phase4_2/reports/daily_equity_V1_ORIGINAL_ORB.csv`
- Output: `research/phase4_2/reports/daily_equity_V2_WICK_ORB.csv`
- Output: `research/phase4_2/reports/daily_equity_V3_CLOSE_CONFIRMED_ORB.csv`
- Output: `research/phase4_2/reports/daily_equity_V4_CORRECTED_VWAP_GOVERNOR.csv`
- Output: `research/phase4_2/reports/daily_equity_V5_COMBINED_PORTFOLIO.csv`

### 4. Generate Visual Forensic Equity Curves
```bash
python research/phase4_2/generate_phase4_2_svg.py
```
- Output: `research/phase4_2/reports/phase4_2_equity_curves.svg`
