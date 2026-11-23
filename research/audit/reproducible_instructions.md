# INDEPENDENT QUANTITATIVE AUDIT REPRODUCIBILITY GUIDE

This guide provides exact step-by-step instructions to reproduce all quantitative findings, trade logs, performance metrics, and stress tests from scratch.

---

## 1. Environment & Dependencies

The audit engine uses standard Python data science libraries without proprietary or external black-box frameworks:
- Python 3.10+
- `pandas >= 2.0.0`
- `numpy >= 1.24.0`
- `pyarrow` (for reading historical parquet files)

Install dependencies if needed:
```bash
pip install pandas numpy pyarrow
```

---

## 2. Historical Data Files

The underlying dataset resides in `data/stocks/` containing high-resolution 1-minute historical tick bars for 30 liquid NSE mega-caps:
- Window: 01 January 2022 to 16 October 2026 (1,182 full standard sessions).
- File naming: `<SYMBOL>_prev.parquet` (2018–2025) and `<SYMBOL>_2026.parquet` (2026).

---

## 3. Reproduction Commands

### Step A: Verify Historical Trading Sessions & Discrepancies
```bash
python research/audit/check_sessions.py
```
*Identifies the exact 8 special truncated trading sessions (Diwali Muhurat, Saturday mock trading) skipped by the 25-candle filter.*

### Step B: Run Data Coverage Audit
```bash
python research/audit/audit_data_coverage.py
```
*Outputs `research/audit/data_coverage_report.json` auditing total candles, missing bars, and exact date cutoffs for all 30 stocks.*

### Step C: Execute Independent Audit & 10 Stress Tests
```bash
python -u research/audit/independent_audit_engine.py
```
*Outputs:*
1. `research/audit/trade_by_trade_vwap_audit.csv` (1,077 full trade records with timestamps and holding times).
2. `research/audit/daily_portfolio_equity.csv` (1,182-day equity curve with drawdown and circuit tiers).
3. `research/audit/monthly_portfolio_returns.csv` (58 consecutive monthly returns and drawdown).
4. `research/audit/recalculated_performance_metrics.json` (Recalculated arithmetic vs geometric metrics).
5. `research/audit/stress_test_matrix.json` (10 multi-dimensional stress tests).
6. `research/audit/portfolio_configuration.json` (Complete institutional architecture configuration).

---

## 4. Output Verification Checkpoints

1. **Win Rate Verification**:
   - Total Trades: 1,077
   - Winning Trades: 538 (538 / 1,077 = 49.95%)
   - Losing Trades: 539 (539 / 1,077 = 50.05%)
2. **Profit Factor Verification**:
   - Gross Profit: ₹7,73,812.82
   - Gross Loss: ₹4,89,644.07
   - Gross Profit Factor: 1.58
   - Total Statutory Charges: ₹1,93,166.97
   - Net Profit: ₹3,53,078.22
   - Net Profit Factor: 1.58
3. **Compound Growth Verification**:
   - Initial Capital: ₹1,00,000.00
   - Final Equity: ₹5,26,479.69
   - Compounded Monthly Growth Rate (CMGR): 2.90%
   - Compounded Annual Growth Rate (CAGR): 41.35%
   - Maximum Peak-to-Trough Drawdown: -9.10%
