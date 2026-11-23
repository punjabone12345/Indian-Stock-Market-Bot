# Phase 3: Institutional Quantitative Research & Discovery Reproducible Instructions

This document provides exact, end-to-end instructions to independently verify and reproduce all quantitative research findings, strategy backtests, Monte Carlo simulations, and stress tests for the Indian National Stock Exchange (NSE).

## Environment Requirements
- Python 3.10+
- Dependencies: `pandas`, `numpy`, `pyarrow`, `fastparquet`

## Step-by-Step Execution Guide

### Step 1: Strategy Attribution Audit (Task 1)
Evaluates Standalone VWAP Pullback Retest vs Standalone Gap & Go Catalyst vs Combined Portfolio.
```bash
python research/phase3/task1_strategy_attribution.py
```
- Output: `research/phase3/reports/task1_strategy_attribution.json`
- Output: `research/phase3/reports/task1_equity_comparison.csv`

### Step 2: Universe Expansion Audit (Task 2)
Tests liquidity ranking, turnover, and strategy performance across Top 10, Top 30, Top 50, Top 100, and 194 stocks.
```bash
python research/phase3/task2_universe_expansion.py
```
- Output: `research/phase3/reports/task2_universe_scaling_report.json`

### Step 3: New Strategy Discovery (Task 3)
Evaluates 5 independent, non-VWAP systematic price action strategies across 1,182 trading sessions:
```bash
python research/phase3/task3_new_strategy_discovery.py
```
- Discovers the Opening Range Support Retest (`ORB_RETEST_SUPPORT_BOUNCE`): +163.17R, 1.34 PF, 49.44% WR.
- Output: `research/phase3/reports/task3_new_strategies_matrix.json`
- Output: `research/phase3/reports/trade_log_ORB_RETEST_SUPPORT_BOUNCE.csv`

### Step 4: Portfolio Optimization & Dynamic Risk Governor (Task 4)
Tests 5 institutional portfolio configurations and dynamic drawdown circuit breakers:
```bash
python research/phase3/task4_portfolio_optimization.py
```
- Crushes Max Drawdown from 11.97% to 6.15% (sub-8% institutional target achieved).
- Output: `research/phase3/reports/task4_portfolio_daily_equity.csv`
- Output: `research/phase3/reports/task4_portfolio_optimization_summary.json`

### Step 5: Walk-Forward Validation & 10,000-Run Monte Carlo (Task 5)
Runs chronological walk-forward splits (2022-2023 In-Sample, 2024, 2025, 2026 Out-of-Sample) and 10,000 bootstrap simulations:
```bash
python research/phase3/task5_validation.py
```
- Output: `research/phase3/reports/task5_walk_forward_matrix.json`
- Output: `research/phase3/reports/task5_monte_carlo_summary.json`
- Output: `research/phase3/reports/task5_stress_test_matrix.json`

### Step 6 & 7: Final Deliverables & Monthly Breakdown Generator
Generates the 58-month return matrix, SVG visualization, and standalone strategy execution code:
```bash
python research/phase3/task6_final_deliverables.py
python research/phase3/generate_svg.py
```
- Output: `research/phase3/reports/task6_monthly_portfolio_returns.csv`
- Output: `research/phase3/deliverables/master_strategy_orb_retest.py`
- Output: `research/phase3/deliverables/master_ensemble_portfolio.py`
- Output: `research/phase3/reports/phase3_equity_curves.svg`
