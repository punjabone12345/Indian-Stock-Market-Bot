# Indian Stock Market Bot — Crown 6 Algorithmic Trading Terminal

An institutional-grade, mobile-first algorithmic trading terminal engineered for the Indian stock market (NSE). Operates exclusively on **NSE Cash Equities (5x MIS Leverage)** with asymmetric 1:3 risk-reward and synthetic server-side OCO protection.

---

## 🏛️ Crown 6 Non-Correlated Asset Universe

| Symbol | Sector | Win Rate | Profit Factor | 4-Year Return | Max Drawdown |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **RELIANCE** | Energy / Oil & Gas | 43.38% | 1.75 | **+544.7 R** | -20.1 R |
| **ITC** | FMCG / Cigarettes / Hotels | 46.11% | 1.75 | **+534.3 R** | -18.2 R |
| **MARUTI** | Automobiles | 45.07% | 1.72 | **+509.2 R** | -28.2 R |
| **TATASTEEL**| Metals & Mining | 42.04% | 1.65 | **+482.3 R** | -26.1 R |
| **SUNPHARMA**| Healthcare / Pharma | 43.96% | 1.64 | **+463.9 R** | -18.2 R |
| **INFY** | IT Services | 43.50% | 1.59 | **+430.0 R** | -23.9 R |
| **PORTFOLIO**| **6 Balanced Champions** | **44.01%** | **1.68** | **+2,964.3 R** | **-33.19 R** |

- **Average Monthly Return:** **+60.50 R / month** (e.g. +₹12,100/mo at 1R = ₹200)
- **Calmar Ratio:** **21.87**
- **Margin Required per Stock:** Under **₹9,600** at 1R = ₹150 (Dhan 5x MIS)

---

## 📱 The 4-Tab Trading Terminal Architecture

1. **Home / Dashboard:**
   - Live running prices for all 6 stocks updated every second.
   - **Trade Probability Score (0 - 100)** evaluating algorithmic setup viability.
   - **Next Algorithmic Step Reasoning:** Real-time commentary explaining what price action or candle close the bot is waiting for.
   - Nifty 50 Macro Trend Benchmark.
2. **Positions:**
   - Active running trades with real-time P&L (₹ & R), Entry, Stop Loss, Target, and Margin.
   - **Delete Button:** Removes trade, releases margin, records 0 P&L.
   - **Close Manually Button:** Exits immediately at market price, releases margin, records P&L and statutory friction.
3. **Analytics:**
   - Chronological Master Trade Ledger grouped date-wise (newest to oldest).
   - Win Rate, Profit Factor, Total R, Total P&L, Statutory charges.
   - **Export CSV Button:** 1-click download of all trade history.
4. **Settings:**
   - Capital (Default: ₹1,00,000) & Risk per Trade (Default: ₹200).
   - Dhan API Integration & Connection Tester.
   - Telegram Live Push Alerts & Test Ping.
   - **Danger Zone / Factory Reset:** Clears history, restores pristine default balance.

---

## 🚀 100% Free Cloud Deployment Guide

### 1. Database: Neon PostgreSQL
1. Log in to [Neon Console](https://console.neon.tech).
2. Under Project **tiny-resonance-58849545**, copy your **Connection String** (`postgresql://...`).
3. Ensure region is set to **Singapore (`ap-southeast-1`)**.

### 2. Backend: Render Free Web Service
- **URL:** `https://indian-stock-market-bot.onrender.com`
1. Go to [Render Dashboard](https://dashboard.render.com) and click **New > Web Service**.
2. Connect your GitHub repository: `punjabone12345/Indian-Stock-Market-Bot`.
3. Set the following settings:
   - **Environment:** `Python 3`
   - **Region:** `Singapore` (matches Neon for sub-millisecond DB latency)
   - **Build Command:** `pip install -r backend/requirements.txt`
   - **Start Command:** `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Add Environment Variable:
   - `DATABASE_URL` = *(Your Neon connection string from Step 1)*

### 3. Frontend: Vercel Web & Mobile PWA
- **URL:** `https://indian-stock-market-bot.vercel.app/`
1. Go to [Vercel Dashboard](https://vercel.com) and click **Add New > Project**.
2. Import `punjabone12345/Indian-Stock-Market-Bot`.
3. Configure Project Settings:
   - **Root Directory:** Click Edit and select `frontend`.
   - **Framework Preset:** `Vite`.
   - **Build Command:** `npm run build`.
   - **Output Directory:** `dist`.
4. Deploy!

### 4. Smart Keep-Alive (Zero Sleep Mode)
To keep Render awake throughout Indian market hours without consuming paid credits:
1. Go to [Cron-Job.org](https://cron-job.org) (Free).
2. Create a cron job:
   - **URL:** `https://indian-stock-market-bot.onrender.com/health`
   - **Schedule:** Every 5 minutes.
   - **Active Window:** 09:00 AM to 03:30 PM IST (Mon-Fri).
3. The bot stays wide awake during trading hours and sleeps at night, using only 16% of Render's free quota!

### 5. Install on Android Phone (PWA)
1. Open `https://indian-stock-market-bot.vercel.app/` in Google Chrome on your Android phone.
2. Tap the three dots (⋮) in Chrome and tap **"Add to Home screen"** or **"Install app"**.
3. The **Crown 6 Terminal** icon will appear on your Android home screen, opening fullscreen like a native app.
