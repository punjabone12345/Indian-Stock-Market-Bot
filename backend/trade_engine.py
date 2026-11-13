import pandas as pd
import numpy as np
from datetime import datetime
try:
    from market_data import market_service, CROWN_6_INSTRUMENTS
    from portfolio import portfolio
except ImportError:
    from backend.market_data import market_service, CROWN_6_INSTRUMENTS
    from backend.portfolio import portfolio

class TradeEngine:
    def __init__(self):
        self.market_scores = {}
        self.last_scan_time = None

    def calculate_stock_score_and_next_step(self, symbol: str, quote: dict, nifty_trend: int):
        cur_p = quote['price']
        candles = market_service.get_candle_history(symbol)
        df = pd.DataFrame(candles)

        # Technical Indicators
        df['EMA9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['EMA21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['Typ'] = (df['high'] + df['low'] + df['close']) / 3.0
        df['PV'] = df['Typ'] * df['volume']
        cum_pv = df['PV'].cumsum()
        cum_vol = df['volume'].cumsum()
        df['VWAP'] = np.where(cum_vol > 0, cum_pv / cum_vol, df['close'])

        # ATR calculation
        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(abs(df['high'] - df['close'].shift()), abs(df['low'] - df['close'].shift()))
        )
        atr = float(df['tr'].rolling(14, min_periods=1).mean().iloc[-1])

        last_row = df.iloc[-1]
        prev_row = df.iloc[-2]
        ema9 = float(last_row['EMA9'])
        ema21 = float(last_row['EMA21'])
        vwap = float(last_row['VWAP'])

        # Check active position
        has_active_pos = any(p['symbol'] == symbol for p in portfolio.positions.values())
        if has_active_pos:
            return {
                'symbol': symbol,
                'score': 95,
                'trend': 'ACTIVE_IN_POSITION',
                'next_step': f'Trade is live! Monitoring live LTP ₹{cur_p:,.2f} for Target or Stop Loss execution.',
                'ema9': round(ema9, 2),
                'ema21': round(ema21, 2),
                'vwap': round(vwap, 2),
                'atr': round(atr, 2),
                'signal_ready': False
            }

        # Calculate Score out of 100
        score = 50
        trend_label = "NEUTRAL"
        next_step = ""
        signal_ready = False
        direction = None

        # Macro Trend Alignment (+20 pts)
        if nifty_trend == 1 and cur_p > vwap and ema9 > ema21:
            score += 25
            trend_label = "BULLISH"
        elif nifty_trend == -1 and cur_p < vwap and ema9 < ema21:
            score += 25
            trend_label = "BEARISH"
        else:
            score -= 10

        # Pullback Proximity to EMA9 (+15 pts)
        ema_dist_pct = abs(cur_p - ema9) / cur_p * 100.0
        if ema_dist_pct < 0.25:
            score += 15
        elif ema_dist_pct < 0.50:
            score += 8

        # Determine Specific Next Step Reason
        if trend_label == "BULLISH":
            if cur_p <= ema9 or prev_row['low'] <= prev_row['EMA9']:
                if cur_p > last_row['open'] and cur_p > ema9:
                    score += 10
                    score = min(score, 94)
                    next_step = f"Dip confirmed into EMA9 zone. Current candle closing green above ₹{ema9:,.2f} — preparing entry!"
                    signal_ready = True
                    direction = 'BUY'
                else:
                    score = min(score, 82)
                    next_step = f"Touching EMA9 support zone (₹{ema9:,.2f}). Waiting for bullish green confirmation candle to close above ₹{ema9:,.2f}."
            else:
                score = min(score, 74)
                dip_price = round(ema9, 2)
                next_step = f"Strong bullish trend above VWAP (₹{vwap:,.2f}). Waiting for price to dip towards EMA9 near ₹{dip_price:,.2f}."
        elif trend_label == "BEARISH":
            if cur_p >= ema9 or prev_row['high'] >= prev_row['EMA9']:
                if cur_p < last_row['open'] and cur_p < ema9:
                    score += 10
                    score = min(score, 94)
                    next_step = f"Pullback into EMA9 resistance zone tested. Bearish candle closing below ₹{ema9:,.2f} — preparing entry!"
                    signal_ready = True
                    direction = 'SELL'
                else:
                    score = min(score, 82)
                    next_step = f"Testing EMA9 resistance zone (₹{ema9:,.2f}). Waiting for bearish red confirmation candle to close below ₹{ema9:,.2f}."
            else:
                score = min(score, 74)
                pullback_price = round(ema9, 2)
                next_step = f"Bearish momentum below VWAP (₹{vwap:,.2f}). Waiting for pullback rally towards EMA9 near ₹{pullback_price:,.2f}."
        else:
            score = max(score, 25)
            next_step = f"Market structure consolidating between EMA9 (₹{ema9:,.2f}) and VWAP (₹{vwap:,.2f}). Waiting for clear trend direction."

        return {
            'symbol': symbol,
            'score': int(score),
            'trend': trend_label,
            'next_step': next_step,
            'ema9': round(ema9, 2),
            'ema21': round(ema21, 2),
            'vwap': round(vwap, 2),
            'atr': round(atr, 2),
            'signal_ready': signal_ready,
            'direction': direction
        }

    def run_market_scan(self):
        quotes = market_service.fetch_live_quotes()
        self.last_scan_time = datetime.now().strftime("%H:%M:%S")

        # First, update active positions and trigger any SL/TP exits
        closed_trades = portfolio.update_live_prices_and_check_triggers(quotes)

        # Check Nifty Macro Trend
        nifty_quote = quotes.get('NIFTY50', {'price': 24350.0})
        nifty_p = nifty_quote['price']
        nifty_candles = market_service.get_candle_history('NIFTY50')
        df_n = pd.DataFrame(nifty_candles)
        n_ema9 = float(df_n['close'].ewm(span=9, adjust=False).mean().iloc[-1])
        n_ema21 = float(df_n['close'].ewm(span=21, adjust=False).mean().iloc[-1])
        nifty_trend = 1 if (n_ema9 > n_ema21 and nifty_p > n_ema21) else (-1 if (n_ema9 < n_ema21 and nifty_p < n_ema21) else 0)

        # Evaluate each of the Crown 6 stocks
        scores = {}
        for sym in ['RELIANCE', 'ITC', 'MARUTI', 'TATASTEEL', 'SUNPHARMA', 'INFY']:
            if sym not in quotes: continue
            q = quotes[sym]
            sc = self.calculate_stock_score_and_next_step(sym, q, nifty_trend)
            scores[sym] = sc

            # Auto Entry if signal confirms and bot is active
            if sc['signal_ready'] and portfolio.bot_active and len(portfolio.positions) < portfolio.max_open_positions:
                cur_p = q['price']
                atr = sc['atr']
                # SL: 0.20% min, 0.70% max
                sl_dist = max(atr * 0.8, cur_p * 0.0020)
                sl_dist = min(sl_dist, cur_p * 0.0070)
                
                if sc['direction'] == 'BUY':
                    sl = cur_p - sl_dist
                    tp = cur_p + (sl_dist * portfolio.target_rr)
                else:
                    sl = cur_p + sl_dist
                    tp = cur_p - (sl_dist * portfolio.target_rr)

                sig = {
                    'symbol': sym,
                    'direction': sc['direction'],
                    'entry_price': cur_p,
                    'stop_loss': sl,
                    'take_profit': tp,
                    'setup': 'Crown 6 Institutional EMA Pullback (1:3 RRR)'
                }
                portfolio.open_position(sig)

        self.market_scores = scores
        return scores

trade_engine = TradeEngine()
