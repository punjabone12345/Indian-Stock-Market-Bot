import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
try:
    from ist_time import now_ist, now_ist_str, now_ist_datetime_str, to_ist_time_str
except ImportError:
    from backend.ist_time import now_ist, now_ist_str, now_ist_datetime_str, to_ist_time_str
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
        self.last_entered_candle_time = {}  # {symbol: candle_timestamp} to prevent multiple entries on the same bar

    def calculate_stock_score_and_next_step(self, symbol: str, quote: dict, nifty_trend: int):
        cur_p = quote['price']
        candles = market_service.get_candle_history(symbol)
        if not candles or len(candles) < 5:
            return {
                'symbol': symbol,
                'score': 50,
                'trend': 'NEUTRAL',
                'next_step': 'Awaiting 5-minute candle history from NSE feed...',
                'ema9': cur_p,
                'ema21': cur_p,
                'vwap': cur_p,
                'atr': 1.0,
                'signal_ready': False,
                'direction': None,
                'cur_p': cur_p,
                'stop_loss': None,
                'take_profit': None,
                'bar_time': 0
            }

        df = pd.DataFrame(candles)

        # In Yahoo Finance v8 chart, the last item is often an unclosed live candle stub with volume == 0
        # For indicators and confirmation, we use completed 5m bars to avoid flat zero-volume distortion
        if len(df) >= 2 and df.iloc[-1]['volume'] == 0:
            completed_df = df.iloc[:-1].copy()
        else:
            completed_df = df.copy()

        # Technical Indicators on Completed Bars
        completed_df['EMA9'] = completed_df['close'].ewm(span=9, adjust=False).mean()
        completed_df['EMA21'] = completed_df['close'].ewm(span=21, adjust=False).mean()
        completed_df['Typ'] = (completed_df['high'] + completed_df['low'] + completed_df['close']) / 3.0
        completed_df['PV'] = completed_df['Typ'] * completed_df['volume']
        cum_pv = completed_df['PV'].cumsum()
        cum_vol = completed_df['volume'].cumsum()
        completed_df['VWAP'] = np.where(cum_vol > 0, cum_pv / cum_vol, completed_df['close'])

        completed_df['tr'] = np.maximum(
            completed_df['high'] - completed_df['low'],
            np.maximum(abs(completed_df['high'] - completed_df['close'].shift()), abs(completed_df['low'] - completed_df['close'].shift()))
        )
        completed_df['ATR'] = completed_df['tr'].rolling(14, min_periods=1).mean()

        last_bar = completed_df.iloc[-1]
        prev_bar = completed_df.iloc[-2] if len(completed_df) >= 2 else last_bar
        prev2_bar = completed_df.iloc[-3] if len(completed_df) >= 3 else prev_bar

        ema9 = float(last_bar['EMA9'])
        ema21 = float(last_bar['EMA21'])
        vwap = float(last_bar['VWAP'])
        atr = float(last_bar['ATR'])
        bar_time = int(last_bar['time'])

        # Check if already active in position
        for pos in portfolio.positions.values():
            if pos['symbol'] == symbol:
                return {
                    'symbol': symbol,
                    'score': 95,
                    'trend': 'ACTIVE_IN_POSITION',
                    'next_step': f"Active {pos['direction']} trade live @ ₹{pos['entry_price']:,.2f}! Monitoring LTP ₹{cur_p:,.2f} (SL: ₹{pos['stop_loss']:,.2f}, TP: ₹{pos['take_profit']:,.2f}).",
                    'ema9': round(ema9, 2),
                    'ema21': round(ema21, 2),
                    'vwap': round(vwap, 2),
                    'atr': round(atr, 2),
                    'signal_ready': False,
                    'direction': None,
                    'cur_p': cur_p,
                    'stop_loss': pos['stop_loss'],
                    'take_profit': pos['take_profit'],
                    'bar_time': bar_time
                }

        # Calculate Score out of 100
        score = 50
        trend_label = "NEUTRAL"
        next_step = ""
        signal_ready = False
        direction = None
        sl = None
        tp = None

        # Macro Trend Alignment (+25 pts)
        is_bullish_trend = (nifty_trend == 1) and (cur_p > vwap or last_bar['close'] > vwap) and (ema9 > ema21)
        is_bearish_trend = (nifty_trend == -1) and (cur_p < vwap or last_bar['close'] < vwap) and (ema9 < ema21)

        if is_bullish_trend:
            score += 25
            trend_label = "BULLISH"
        elif is_bearish_trend:
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

        # Setup Confirmation Evaluation
        if trend_label == "BULLISH":
            # Dip into EMA9 support zone within 0.20% tolerance on recent candles
            ema_pullback_zone = ema9 * 1.0020
            touched_ema9 = (last_bar['low'] <= ema_pullback_zone) or (prev_bar['low'] <= prev_bar['EMA9'] * 1.0020) or (prev2_bar['low'] <= prev2_bar['EMA9'] * 1.0020)
            
            if touched_ema9:
                # Completed bar closed green and above EMA9, OR live price is green and bouncing above EMA9
                completed_confirmed = (last_bar['close'] > last_bar['open']) and (last_bar['close'] >= ema9 * 0.9990)
                live_confirmed = (cur_p >= ema9 * 0.9990) and (cur_p >= last_bar['close'])
                price_in_range = cur_p <= (ema9 + max(0.6 * atr, ema9 * 0.0060))

                if (completed_confirmed or live_confirmed) and price_in_range:
                    # Structural Stop Loss anchored below recent swing low wick
                    raw_sl = min(last_bar['low'], prev_bar['low']) - (0.2 * atr)
                    sl_dist = max(cur_p - raw_sl, cur_p * 0.0020)
                    sl_dist = min(sl_dist, cur_p * 0.0070)
                    sl = round(cur_p - sl_dist, 2)
                    tp = round(cur_p + (sl_dist * portfolio.target_rr), 2)
                    score = 94
                    next_step = f"A+ Bullish Pullback confirmed above EMA9 (₹{ema9:,.2f})! Entry triggered @ ₹{cur_p:,.2f} (SL: ₹{sl:,.2f}, TP: ₹{tp:,.2f})."
                    signal_ready = True
                    direction = 'BUY'
                else:
                    score = min(score, 82)
                    next_step = f"Touching EMA9 support zone (₹{ema9:,.2f}). Waiting for bullish green confirmation above ₹{ema9:,.2f}."
            else:
                score = min(score, 74)
                dip_price = round(ema9, 2)
                next_step = f"Strong bullish trend above VWAP (₹{vwap:,.2f}). Waiting for price to dip towards EMA9 near ₹{dip_price:,.2f}."

        elif trend_label == "BEARISH":
            # Pullback into EMA9 resistance zone within 0.20% tolerance on recent candles
            ema_pullback_zone = ema9 * 0.9980
            touched_ema9 = (last_bar['high'] >= ema_pullback_zone) or (prev_bar['high'] >= prev_bar['EMA9'] * 0.9980) or (prev2_bar['high'] >= prev2_bar['EMA9'] * 0.9980)

            if touched_ema9:
                completed_confirmed = (last_bar['close'] < last_bar['open']) and (last_bar['close'] <= ema9 * 1.0010)
                live_confirmed = (cur_p <= ema9 * 1.0010) and (cur_p <= last_bar['close'])
                price_in_range = cur_p >= (ema9 - max(0.6 * atr, ema9 * 0.0060))

                if (completed_confirmed or live_confirmed) and price_in_range:
                    # Structural Stop Loss anchored above recent swing high wick
                    raw_sl = max(last_bar['high'], prev_bar['high']) + (0.2 * atr)
                    sl_dist = max(raw_sl - cur_p, cur_p * 0.0020)
                    sl_dist = min(sl_dist, cur_p * 0.0070)
                    sl = round(cur_p + sl_dist, 2)
                    tp = round(cur_p - (sl_dist * portfolio.target_rr), 2)
                    score = 94
                    next_step = f"A+ Bearish Pullback confirmed below EMA9 (₹{ema9:,.2f})! Entry triggered @ ₹{cur_p:,.2f} (SL: ₹{sl:,.2f}, TP: ₹{tp:,.2f})."
                    signal_ready = True
                    direction = 'SELL'
                else:
                    score = min(score, 82)
                    next_step = f"Testing EMA9 resistance zone (₹{ema9:,.2f}). Waiting for bearish red confirmation below ₹{ema9:,.2f}."
            else:
                score = min(score, 74)
                pullback_price = round(ema9, 2)
                next_step = f"Bearish momentum below VWAP (₹{vwap:,.2f}). Waiting for pullback rally towards EMA9 near ₹{pullback_price:,.2f}."
        else:
            score = max(score, 30)
            next_step = f"Market structure consolidating between EMA9 (₹{ema9:,.2f}) and VWAP (₹{vwap:,.2f}). Waiting for clear trend breakout."

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
            'direction': direction,
            'cur_p': cur_p,
            'stop_loss': sl,
            'take_profit': tp,
            'bar_time': bar_time
        }

    def run_market_scan(self):
        quotes = market_service.fetch_live_quotes()
        self.last_scan_time = now_ist_str("%H:%M:%S IST")

        # First, update active positions and trigger any SL/TP exits
        closed_trades = portfolio.update_live_prices_and_check_triggers(quotes)

        # Check Nifty Macro Trend on completed candles
        nifty_quote = quotes.get('NIFTY50', {'price': 25260.0})
        nifty_p = nifty_quote['price']
        nifty_candles = market_service.get_candle_history('NIFTY50')
        df_n = pd.DataFrame(nifty_candles)
        if len(df_n) >= 2 and df_n.iloc[-1]['volume'] == 0:
            df_n = df_n.iloc[:-1].copy()
            
        n_ema9 = float(df_n['close'].ewm(span=9, adjust=False).mean().iloc[-1])
        n_ema21 = float(df_n['close'].ewm(span=21, adjust=False).mean().iloc[-1])
        n_close = float(df_n['close'].iloc[-1])
        nifty_trend = 1 if (n_ema9 > n_ema21 and n_close > n_ema21) else (-1 if (n_ema9 < n_ema21 and n_close < n_ema21) else 0)

        now_ist_obj = now_ist()
        is_weekday = (0 <= now_ist_obj.weekday() <= 4)
        time_mins = now_ist_obj.hour * 60 + now_ist_obj.minute
        is_market_open = is_weekday and (9 * 60 + 15 <= time_mins <= 15 * 60 + 30)
        is_entry_window = is_weekday and (9 * 60 + 30 <= time_mins <= 14 * 60 + 15)  # No new entries after 2:15 PM IST
        is_past_3pm = is_weekday and (time_mins >= 15 * 60)  # All open positions squared off by 3:00 PM IST

        # Evaluate each of the Crown 6 stocks
        scores = {}
        for sym in ['RELIANCE', 'ITC', 'MARUTI', 'TATASTEEL', 'SUNPHARMA', 'INFY']:
            if sym not in quotes: continue
            q = quotes[sym]
            sc = self.calculate_stock_score_and_next_step(sym, q, nifty_trend)
            if not is_market_open:
                sc['signal_ready'] = False
                sc['next_step'] = f"NSE Closed (Recorded LTP: ₹{q['price']:,.2f}). Session starts 09:15 AM."
            elif is_past_3pm:
                sc['signal_ready'] = False
                sc['next_step'] = "Past 03:00 PM IST: All intraday positions squared off. Session closing."
            elif not is_entry_window:
                sc['signal_ready'] = False
                sc['next_step'] = "Outside Entry Window (09:30 AM - 02:15 PM IST): Active position tracking only."
            scores[sym] = sc

            # Auto Entry if signal confirms, within entry window, and bot is active
            if is_entry_window and sc['signal_ready'] and portfolio.bot_active and len(portfolio.positions) < portfolio.max_open_positions:
                # Prevent duplicate entries on the same 5-minute candle
                last_entered = self.last_entered_candle_time.get(sym)
                if last_entered != sc['bar_time']:
                    sig = {
                        'symbol': sym,
                        'direction': sc['direction'],
                        'entry_price': sc['cur_p'],
                        'stop_loss': sc['stop_loss'],
                        'take_profit': sc['take_profit'],
                        'setup': 'Crown 6 Institutional EMA Pullback (1:3 RRR)'
                    }
                    res = portfolio.open_position(sig)
                    if res.get('status') == 'success':
                        self.last_entered_candle_time[sym] = sc['bar_time']
                        sc['signal_ready'] = False
                        sc['trend'] = 'ACTIVE_IN_POSITION'
                        sc['next_step'] = f"Active {sc['direction']} trade live @ ₹{sc['cur_p']:,.2f}! (SL: ₹{sc['stop_loss']:,.2f}, TP: ₹{sc['take_profit']:,.2f})"

        self.market_scores = scores
        return scores

trade_engine = TradeEngine()
