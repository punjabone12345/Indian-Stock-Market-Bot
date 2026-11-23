import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
try:
    from ist_time import now_ist, now_ist_str, now_ist_datetime_str, now_ist_date_str, to_ist_time_str
    from database import db
    from market_data import market_service, MEGACAP_29_INSTRUMENTS
    from portfolio import portfolio
except ImportError:
    from backend.ist_time import now_ist, now_ist_str, now_ist_datetime_str, now_ist_date_str, to_ist_time_str
    from backend.database import db
    from backend.market_data import market_service, MEGACAP_29_INSTRUMENTS
    from backend.portfolio import portfolio

MEGACAP_29_SYMBOLS = [s for s in MEGACAP_29_INSTRUMENTS.keys() if s != 'NIFTY50']
TOP_14_SYMBOLS = MEGACAP_29_SYMBOLS  # alias for backward compatibility

class TradeEngine:
    def __init__(self):
        self.market_scores = {}
        self.last_scan_time = None
        self.last_entered_candle_time = {}  # {symbol: candle_timestamp}
        self.daily_trade_date = None
        self.daily_trade_count = 0  # Pure Leader: max 1 trade per day

    def calculate_stock_score_and_next_step(self, symbol: str, quote: dict, nifty_trend: int):
        cur_p = quote['price']
        prev_close = quote.get('prev_close', cur_p)
        candles = market_service.get_candle_history(symbol)
        vol_45m_base = quote.get('vol_45m_base', 500000)

        # Baseline response if data is insufficient
        if not candles or len(candles) < 2:
            return {
                'symbol': symbol,
                'score': 50,
                'trend': 'NEUTRAL',
                'next_step': 'Awaiting 5-minute candle history from NSE feed...',
                'rvol': 1.0,
                'gap_pct': round(((cur_p - prev_close) / prev_close) * 100.0, 2) if prev_close else 0.0,
                'vwap': cur_p,
                'morning_low': cur_p * 0.995,
                'morning_high': cur_p * 1.005,
                'signal_ready': False,
                'direction': None,
                'cur_p': cur_p,
                'stop_loss': None,
                'take_profit': None,
                'bar_time': 0,
                'setup': 'Velocity Compounder'
            }

        df = pd.DataFrame(candles)
        if len(df) >= 2 and df.iloc[-1]['volume'] == 0:
            completed_df = df.iloc[:-1].copy()
        else:
            completed_df = df.copy()

        # Compute intraday VWAP
        completed_df['Typ'] = (completed_df['high'] + completed_df['low'] + completed_df['close']) / 3.0
        completed_df['PV'] = completed_df['Typ'] * completed_df['volume']
        cum_pv = completed_df['PV'].cumsum()
        cum_vol = completed_df['volume'].cumsum()
        completed_df['VWAP'] = np.where(cum_vol > 0, cum_pv / cum_vol, completed_df['close'])

        last_bar = completed_df.iloc[-1]
        vwap = float(last_bar['VWAP'])
        bar_time = int(last_bar['time'])

        # Check if already active in position
        for pos in portfolio.positions.values():
            if pos['symbol'] == symbol:
                return {
                    'symbol': symbol,
                    'score': 98,
                    'trend': 'ACTIVE_IN_POSITION',
                    'next_step': f"Active {pos['direction']} trade live @ ₹{pos['entry_price']:,.2f}! Tracking LTP ₹{cur_p:,.2f} (SL: ₹{pos['stop_loss']:,.2f}, 4R TP: ₹{pos['take_profit']:,.2f}).",
                    'rvol': 2.8,
                    'gap_pct': round(((cur_p - prev_close) / prev_close) * 100.0, 2) if prev_close else 0.0,
                    'vwap': round(vwap, 2),
                    'morning_low': round(pos['stop_loss'], 2),
                    'morning_high': round(pos['take_profit'], 2),
                    'signal_ready': False,
                    'direction': None,
                    'cur_p': cur_p,
                    'stop_loss': pos['stop_loss'],
                    'take_profit': pos['take_profit'],
                    'bar_time': bar_time,
                    'setup': 'Velocity Compounder (Pure Leader 4.0R)'
                }

        # 1. Overnight Gap Filter (|Gap| >= 1.2%)
        open_0 = completed_df.iloc[0]['open']
        gap_pct = ((open_0 - prev_close) / prev_close) * 100.0 if prev_close > 0 else 0.0
        abs_gap = abs(gap_pct)
        has_catalyst_gap = (abs_gap >= 1.20)

        # 2. 45-Minute RVOL Calculation (Bars 0 to 8: 09:15 to 10:00)
        n_bars = min(len(completed_df), 9)
        morning_vol = completed_df.iloc[:n_bars]['volume'].sum()
        rvol = round(morning_vol / max(vol_45m_base, 1), 2)
        has_volume_expansion = (rvol >= 2.50)

        # 3. Morning Extreme Range (09:15–10:00)
        morning_high = float(completed_df.iloc[:n_bars]['high'].max())
        morning_low = float(completed_df.iloc[:n_bars]['low'].min())

        # 4. Microstructure Confirmation at 10:00 AM (Candle 8 close)
        score = 50
        trend_label = "NEUTRAL"
        next_step = ""
        signal_ready = False
        direction = None
        sl = None
        tp = None

        if len(completed_df) >= 9:
            # 10:00 AM bar is available
            c_conf = float(completed_df.iloc[8]['close'])
            v_conf = float(completed_df.iloc[8]['VWAP'])
            
            # LONG Confirmation
            if c_conf > v_conf and c_conf > morning_low:
                trend_label = "BULLISH"
                rs_pct = ((c_conf - open_0) / open_0) * 100.0
                rs_score = max(0.0, rs_pct) * rvol
                score = min(99, int(50 + (rs_score * 5.0)))
                
                if has_catalyst_gap and has_volume_expansion:
                    # Clean Catalyst Leader Long Signal
                    sl_dist = cur_p - (morning_low * 0.9995)
                    sl_dist = max(cur_p * 0.0050, min(sl_dist, cur_p * 0.0150))
                    sl = round(cur_p - sl_dist, 2)
                    tp = round(cur_p + (sl_dist * portfolio.target_rr), 2)
                    signal_ready = True
                    direction = 'BUY'
                    score = 96
                    next_step = f"Velocity Leader Bullish Signal! Gap: {gap_pct:+.2f}%, RVOL: {rvol}x, Above VWAP. Triggering Entry @ ₹{cur_p:,.2f}."
                elif has_catalyst_gap:
                    next_step = f"Catalyst Gap ({gap_pct:+.2f}%) confirmed above VWAP. Waiting for RVOL to cross 2.5x (Current: {rvol}x)."
                else:
                    next_step = f"Trading above VWAP. Overnight gap ({gap_pct:+.2f}%) below 1.2% threshold."

            # SHORT Confirmation
            elif c_conf < v_conf and c_conf < morning_high:
                trend_label = "BEARISH"
                rs_pct = ((open_0 - c_conf) / open_0) * 100.0
                rs_score = max(0.0, rs_pct) * rvol
                score = min(99, int(50 + (rs_score * 5.0)))
                
                if has_catalyst_gap and has_volume_expansion:
                    sl_dist = (morning_high * 1.0005) - cur_p
                    sl_dist = max(cur_p * 0.0050, min(sl_dist, cur_p * 0.0150))
                    sl = round(cur_p + sl_dist, 2)
                    tp = round(cur_p - (sl_dist * portfolio.target_rr), 2)
                    signal_ready = True
                    direction = 'SELL'
                    score = 96
                    next_step = f"Velocity Leader Bearish Signal! Gap: {gap_pct:+.2f}%, RVOL: {rvol}x, Below VWAP. Triggering Entry @ ₹{cur_p:,.2f}."
                elif has_catalyst_gap:
                    next_step = f"Catalyst Gap ({gap_pct:+.2f}%) confirmed below VWAP. Waiting for RVOL to cross 2.5x (Current: {rvol}x)."
                else:
                    next_step = f"Trading below VWAP. Overnight gap ({gap_pct:+.2f}%) below 1.2% threshold."
            else:
                score = 45
                trend_label = "CONSOLIDATING"
                next_step = "Consolidating inside morning range. Awaiting directional expansion."
        else:
            # During 09:15-10:00 observation period
            if cur_p > vwap:
                trend_label = "OBSERVING_BULLISH"
                next_step = f"09:15–10:00 Window: Above VWAP (₹{vwap:,.2f}). RVOL: {rvol}x. Awaiting 10:00 AM candle confirmation."
            else:
                trend_label = "OBSERVING_BEARISH"
                next_step = f"09:15–10:00 Window: Below VWAP (₹{vwap:,.2f}). RVOL: {rvol}x. Awaiting 10:00 AM candle confirmation."

        return {
            'symbol': symbol,
            'score': int(score),
            'trend': trend_label,
            'next_step': next_step,
            'rvol': rvol,
            'gap_pct': round(gap_pct, 2),
            'vwap': round(vwap, 2),
            'morning_low': round(morning_low, 2),
            'morning_high': round(morning_high, 2),
            'signal_ready': signal_ready,
            'direction': direction,
            'cur_p': cur_p,
            'stop_loss': sl,
            'take_profit': tp,
            'bar_time': bar_time,
            'setup': 'Velocity Compounder (Pure Leader 4.0R)'
        }

    def run_market_scan(self):
        quotes = market_service.fetch_live_quotes()
        self.last_scan_time = now_ist_str("%H:%M:%S IST")

        # 1. Update open positions and check SL, Target, Breakeven Lock, Trailing, or 3:00 PM Square-off
        closed_trades = portfolio.update_live_prices_and_check_triggers(quotes)

        # 2. Check Nifty Macro Trend on completed candles
        nifty_quote = quotes.get('NIFTY50', {'price': 24350.00})
        nifty_candles = market_service.get_candle_history('NIFTY50')
        df_n = pd.DataFrame(nifty_candles)
        if len(df_n) >= 2 and df_n.iloc[-1]['volume'] == 0:
            df_n = df_n.iloc[:-1].copy()
            
        if len(df_n) >= 5:
            n_ema9 = float(df_n['close'].ewm(span=9, adjust=False).mean().iloc[-1])
            n_ema21 = float(df_n['close'].ewm(span=21, adjust=False).mean().iloc[-1])
            n_close = float(df_n['close'].iloc[-1])
            nifty_trend = 1 if (n_ema9 > n_ema21 and n_close > n_ema21) else (-1 if (n_ema9 < n_ema21 and n_close < n_ema21) else 0)
        else:
            nifty_trend = 0

        now_ist_obj = now_ist()
        is_weekday = (0 <= now_ist_obj.weekday() <= 4)
        time_mins = now_ist_obj.hour * 60 + now_ist_obj.minute
        is_market_open = is_weekday and (9 * 60 + 15 <= time_mins <= 15 * 60 + 30)
        is_entry_window = is_weekday and (10 * 60 <= time_mins <= 14 * 60 + 45)  # 10:00 AM to 02:45 PM IST
        is_past_cutoff = is_weekday and (time_mins >= 15 * 60)  # 3:00 PM IST strict square-off

        today_date = now_ist_date_str()
        if self.daily_trade_date != today_date:
            self.daily_trade_date = today_date
            self.daily_trade_count = 0
            try:
                for t in db.get_trade_history():
                    if t.get('trade_date') == today_date:
                        self.daily_trade_count += 1
            except Exception:
                pass
            self.daily_trade_count += len(portfolio.positions)

        # 3. Evaluate all 29 Mega-Cap stocks
        scores = {}
        qualified_candidates = []

        for sym in MEGACAP_29_SYMBOLS:
            if sym not in quotes: continue
            q = quotes[sym]
            sc = self.calculate_stock_score_and_next_step(sym, q, nifty_trend)

            if not is_market_open:
                sc['signal_ready'] = False
                sc['next_step'] = f"NSE Closed (Recorded LTP: ₹{q['price']:,.2f}). Session starts 09:15 AM."
            elif is_past_cutoff:
                sc['signal_ready'] = False
                sc['next_step'] = "Past 03:00 PM IST: All intraday positions squared off. Session closing."
            elif not is_entry_window:
                sc['signal_ready'] = False
                sc['next_step'] = "09:15–10:00 AM Observation Phase: Establishing morning high/low and 45m RVOL baseline."
            elif self.daily_trade_count >= 1:
                sc['signal_ready'] = False
                sc['next_step'] = "Daily trade allocation complete (1/1 completed). Pure Leader sitting out."

            scores[sym] = sc
            if sc['signal_ready'] and is_entry_window and self.daily_trade_count == 0 and len(portfolio.positions) == 0:
                qualified_candidates.append(sc)

        # 4. Pure Leader Execution: Sort by score descending and take the #1 highest-ranking stock
        if qualified_candidates and portfolio.bot_active and len(portfolio.positions) < portfolio.max_open_positions and self.daily_trade_count == 0:
            qualified_candidates.sort(key=lambda x: x['score'], reverse=True)
            top_leader = qualified_candidates[0]
            leader_sym = top_leader['symbol']

            last_entered = self.last_entered_candle_time.get(leader_sym)
            if last_entered != top_leader['bar_time']:
                sig = {
                    'symbol': leader_sym,
                    'direction': top_leader['direction'],
                    'entry_price': top_leader['cur_p'],
                    'stop_loss': top_leader['stop_loss'],
                    'take_profit': top_leader['take_profit'],
                    'setup': 'Velocity Compounder (Pure Leader 4.0R)'
                }
                res = portfolio.open_position(sig)
                if res.get('status') == 'success':
                    self.last_entered_candle_time[leader_sym] = top_leader['bar_time']
                    self.daily_trade_count += 1
                    top_leader['signal_ready'] = False
                    top_leader['trend'] = 'ACTIVE_IN_POSITION'
                    top_leader['next_step'] = f"Active {top_leader['direction']} trade live @ ₹{top_leader['cur_p']:,.2f}! (SL: ₹{top_leader['stop_loss']:,.2f}, 4R TP: ₹{top_leader['take_profit']:,.2f})"

        self.market_scores = scores
        return scores

trade_engine = TradeEngine()
