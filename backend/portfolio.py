import uuid
import time
from datetime import datetime, timezone, timedelta
try:
    from ist_time import now_ist, now_ist_str, now_ist_datetime_str, now_ist_date_str, to_ist_time_str
except ImportError:
    from backend.ist_time import now_ist, now_ist_str, now_ist_datetime_str, now_ist_date_str, to_ist_time_str
try:
    from database import db
    from telegram_alerts import telegram_service
except ImportError:
    from backend.database import db
    from backend.telegram_alerts import telegram_service

class PortfolioManager:
    def __init__(self):
        self.governor_mode = "NORMAL"
        self.governor_multiplier = 1.0
        self.peak_realized_r = 0.0
        self.cumulative_realized_r = 0.0
        self.current_drawdown_r = 0.0
        self.refresh_from_db()

    def refresh_from_db(self):
        settings = db.get_settings()
        self.capital = float(settings.get('capital', 125000.0))
        self.risk_per_trade = float(settings.get('risk_per_trade', 200.0))
        self.trading_mode = settings.get('trading_mode', 'PAPER')
        self.max_open_positions = int(settings.get('max_open_positions', 14))
        self.target_rr = float(settings.get('target_rr', 2.0))
        self.bot_active = bool(settings.get('bot_active', True))
        
        # Load positions from DB
        db_positions = db.get_positions()
        self.positions = {}
        for p in db_positions:
            self.positions[p['id']] = {
                'id': p['id'],
                'symbol': p['symbol'],
                'direction': p['direction'],
                'entry_price': float(p['entry_price']),
                'stop_loss': float(p['stop_loss']),
                'take_profit': float(p['take_profit']),
                'quantity': int(p['quantity']),
                'margin_used': float(p['margin_used']),
                'entry_time': to_ist_time_str(p['entry_time']),
                'setup': p.get('setup', 'Top 14 VWAP Pullback'),
                'sl_dist': float(p['sl_dist']),
                'current_price': float(p['entry_price']),
                'unrealized_pnl': 0.0,
                'unrealized_r': 0.0,
                'created_at': p.get('created_at', now_ist_datetime_str()),
                'governor_mode': p.get('governor_mode', self.governor_mode)
            }

        # Calculate Dynamic Risk Governor state from trade history
        self._recalculate_governor_state()

    def _recalculate_governor_state(self):
        """
        Recomputes peak realized R and current drawdown in R.
        Governor Rule:
          - If current_drawdown_r <= -15.0 R: DEFENSIVE MODE (multiplier = 0.5)
          - If current_drawdown_r >= -5.0 R: NORMAL MODE (multiplier = 1.0)
        """
        history = db.get_trade_history()
        # Sort chronologically by entry_time / created_at
        cum_r = 0.0
        peak_r = 0.0
        curr_mode = "NORMAL"
        curr_mult = 1.0

        for t in history:
            r = float(t.get('realized_r', 0.0))
            cum_r += r
            if cum_r > peak_r:
                peak_r = cum_r
            dd = cum_r - peak_r
            if curr_mode == "NORMAL" and dd <= -15.0:
                curr_mode = "DEFENSIVE"
                curr_mult = 0.5
            elif curr_mode == "DEFENSIVE" and dd >= -5.0:
                curr_mode = "NORMAL"
                curr_mult = 1.0

        prev_mode = self.governor_mode
        self.cumulative_realized_r = round(cum_r, 2)
        self.peak_realized_r = round(peak_r, 2)
        self.current_drawdown_r = round(cum_r - peak_r, 2)
        self.governor_mode = curr_mode
        self.governor_multiplier = curr_mult

        # If state transitioned during execution, notify via Telegram
        if prev_mode != curr_mode and len(history) > 0:
            eff = self.get_effective_risk()
            telegram_service.notify_governor_switch(curr_mode, self.current_drawdown_r, curr_mult, eff)

    def get_effective_risk(self) -> float:
        """Returns the current trade risk in ₹ scaled by the Dynamic Risk Governor."""
        return round(self.risk_per_trade * self.governor_multiplier, 2)

    def calculate_statutory_charges(self, entry_price: float, exit_price: float, qty: int, direction: str = 'BUY') -> float:
        """
        100% Exact Zerodha & Dhan Equity Intraday (MIS) Charges Schedule on NSE:
        1. Brokerage: min(₹20, 0.03% of turnover) per leg (separate on entry and exit leg)
        2. STT (Securities Transaction Tax): 0.025% on SELL turnover only
        3. Exchange Turnover Fee: 0.00297% (NSE) of total round-trip turnover
        4. SEBI Turnover Fee: ₹10 per crore (0.0001% of total round-trip turnover)
        5. Stamp Duty: 0.003% (₹300 per crore) on BUY turnover only
        6. GST: 18% on (Brokerage + Exchange Turnover Fee + SEBI Fee)
        """
        entry_p = float(entry_price)
        exit_p = float(exit_price)
        q = int(qty)

        if direction == 'BUY':
            buy_val = round(entry_p * q, 2)
            sell_val = round(exit_p * q, 2)
        else:
            buy_val = round(exit_p * q, 2)
            sell_val = round(entry_p * q, 2)

        turnover = round(buy_val + sell_val, 2)

        # 1. Brokerage (charged on both Buy and Sell legs, max ₹20 per leg)
        buy_brok = min(20.0, round(buy_val * 0.0003, 2))
        sell_brok = min(20.0, round(sell_val * 0.0003, 2))
        brokerage = round(buy_brok + sell_brok, 2)

        # 2. STT (0.025% on sell side only)
        stt = round(sell_val * 0.00025, 2)

        # 3. NSE Exchange transaction fee (0.00297% of total turnover)
        exch_fees = round(turnover * 0.0000297, 2)

        # 4. SEBI turnover charge (₹10/cr = 0.0001% of total turnover)
        sebi_fees = round(turnover * 0.000001, 2)

        # 5. Stamp duty (0.003% on buy side only)
        stamp_duty = round(buy_val * 0.00003, 2)

        # 6. GST (18% on Brokerage + Exchange Fees + SEBI Fees)
        gst = round((brokerage + exch_fees + sebi_fees) * 0.18, 2)

        total = round(brokerage + stt + exch_fees + sebi_fees + stamp_duty + gst, 2)
        return total

    def get_used_margin(self) -> float:
        return sum(pos['margin_used'] for pos in self.positions.values())

    def get_available_margin(self) -> float:
        return max(0.0, self.capital - self.get_used_margin())

    def open_position(self, signal: dict):
        self.refresh_from_db()
        if not self.bot_active:
            return {'status': 'error', 'message': 'Bot is currently paused.'}

        if len(self.positions) >= self.max_open_positions:
            return {'status': 'error', 'message': f'Max concurrent positions ({self.max_open_positions}) reached.'}

        symbol = signal['symbol']
        # Check if symbol already open
        for pos in self.positions.values():
            if pos['symbol'] == symbol:
                return {'status': 'error', 'message': f'Active position already exists for {symbol}.'}

        entry_price = float(signal['entry_price'])
        stop_loss = float(signal['stop_loss'])
        take_profit = float(signal['take_profit'])
        direction = signal['direction']
        sl_dist = abs(entry_price - stop_loss)

        # Enforce strict 0.50% SL floor to prevent micro-SL turnover charge blowout
        min_sl_dist = round(entry_price * 0.0050, 2)
        if sl_dist < min_sl_dist:
            sl_dist = min_sl_dist
            stop_loss = round(entry_price - sl_dist, 2) if direction == 'BUY' else round(entry_price + sl_dist, 2)
            take_profit = round(entry_price + (sl_dist * self.target_rr), 2) if direction == 'BUY' else round(entry_price - (sl_dist * self.target_rr), 2)

        if sl_dist <= 0:
            return {'status': 'error', 'message': 'Invalid Stop Loss price.'}

        # Dynamic Risk Governor Position Sizing:
        # Normal Mode: 1.0R (₹200) | Defensive Mode: 0.5R (₹100)
        eff_risk = self.get_effective_risk()
        quantity = int(eff_risk / sl_dist)
        if quantity <= 0:
            quantity = 1

        # 5x MIS Margin required
        pos_val = quantity * entry_price
        margin_used = round(pos_val * 0.20, 2)

        avail_margin = self.get_available_margin()
        if margin_used > avail_margin:
            return {
                'status': 'error',
                'message': f'Insufficient margin! Needed: ₹{margin_used:,.2f}, Available: ₹{avail_margin:,.2f}'
            }

        pos_id = str(uuid.uuid4())[:8]
        entry_time_str = now_ist_str("%H:%M:%S")

        pos_dict = {
            'id': pos_id,
            'symbol': symbol,
            'direction': direction,
            'entry_price': round(entry_price, 2),
            'stop_loss': round(stop_loss, 2),
            'take_profit': round(take_profit, 2),
            'quantity': quantity,
            'margin_used': margin_used,
            'entry_time': entry_time_str,
            'setup': signal.get('setup', 'Top 14 VWAP Pullback'),
            'sl_dist': round(sl_dist, 2),
            'current_price': round(entry_price, 2),
            'unrealized_pnl': 0.0,
            'unrealized_r': 0.0,
            'created_at': now_ist_datetime_str(),
            'governor_mode': self.governor_mode,
            'risk_amount': eff_risk,
            'target_rr': self.target_rr
        }

        # Save to DB & memory
        self.positions[pos_id] = pos_dict
        db.save_position(pos_dict)

        # Telegram Alert
        telegram_service.notify_order_entry({
            **pos_dict,
            'mode': self.trading_mode,
            'sl_pct': (sl_dist / entry_price) * 100.0
        })

        return {'status': 'success', 'position': pos_dict}

    def delete_position(self, pos_id: str):
        """Deletes position from DB, releases margin, NO P&L counted."""
        if pos_id not in self.positions:
            return {'status': 'error', 'message': 'Position not found'}

        pos = self.positions.pop(pos_id)
        db.delete_position(pos_id)
        telegram_service.notify_position_deleted(pos['symbol'], pos['margin_used'])
        return {'status': 'success', 'message': f'Position {pos["symbol"]} deleted without P&L impact.'}

    def close_position_manually(self, pos_id: str, current_price: float = None):
        """Exits position at market price, releases margin, records P&L and charges."""
        if pos_id not in self.positions:
            return {'status': 'error', 'message': 'Position not found'}

        pos = self.positions.pop(pos_id)
        db.delete_position(pos_id)

        exit_p = round(current_price if current_price else pos['current_price'], 2)
        entry_p = pos['entry_price']
        qty = pos['quantity']
        direction = pos['direction']

        gross_pnl = (exit_p - entry_p) * qty if direction == 'BUY' else (entry_p - exit_p) * qty
        charges = self.calculate_statutory_charges(entry_p, exit_p, qty, direction)
        net_pnl = round(gross_pnl - charges, 2)
        # R accounting relative to base risk (₹200)
        realized_r = round(net_pnl / self.risk_per_trade, 2)

        # Update capital
        self.capital = round(self.capital + net_pnl, 2)
        db.update_settings({'capital': self.capital})

        trade_record = {
            'id': pos_id,
            'symbol': pos['symbol'],
            'direction': direction,
            'entry_price': entry_p,
            'exit_price': exit_p,
            'quantity': qty,
            'margin_used': pos['margin_used'],
            'entry_time': to_ist_time_str(pos['entry_time']),
            'exit_time': now_ist_str("%H:%M:%S"),
            'exit_reason': 'MANUAL_USER_CLOSE',
            'realized_pnl': net_pnl,
            'realized_r': realized_r,
            'charges': charges,
            'trade_date': now_ist_date_str(),
            'created_at': now_ist_datetime_str()
        }

        db.save_closed_trade(trade_record)
        telegram_service.notify_manual_close(trade_record)
        self._recalculate_governor_state()
        return {'status': 'success', 'trade': trade_record}

    def update_live_prices_and_check_triggers(self, quotes: dict):
        """Updates open positions with live quotes, checks Target / Stop Loss triggers, or 3:10 PM EOD squareoff."""
        closed_trades = []

        for pos_id, pos in list(self.positions.items()):
            sym = pos['symbol']
            if sym not in quotes: continue

            ltp = quotes[sym]['price']
            pos['current_price'] = ltp
            entry_p = pos['entry_price']
            qty = pos['quantity']
            direction = pos['direction']
            sl = pos['stop_loss']
            # Dynamically ensure take_profit aligns with active target_rr (1:2 RRR)
            sl_dist = abs(entry_p - sl)
            expected_tp = round(entry_p + (sl_dist * self.target_rr), 2) if direction == 'BUY' else round(entry_p - (sl_dist * self.target_rr), 2)
            if pos.get('take_profit') != expected_tp:
                pos['take_profit'] = expected_tp
            tp = pos['take_profit']

            # Gross & Net Unrealized P&L
            gross_pnl = (ltp - entry_p) * qty if direction == 'BUY' else (entry_p - ltp) * qty
            pos['unrealized_pnl'] = round(gross_pnl, 2)
            pos['unrealized_r'] = round(gross_pnl / self.risk_per_trade, 2)

            # Check Stop Loss / Target Triggers or 3:00 PM IST EOD Square-off
            exit_reason = None
            exit_price = None

            now_ist_obj = now_ist()
            time_mins = now_ist_obj.hour * 60 + now_ist_obj.minute
            is_eod_cutoff = (time_mins >= 15 * 60)  # 3:00 PM IST auto square-off

            if is_eod_cutoff:
                exit_reason = 'EOD_AUTO_SQUAREOFF_3PM'
                exit_price = ltp
            elif direction == 'BUY':
                if ltp <= sl:
                    exit_reason = 'STOP_LOSS_HIT'
                    exit_price = sl
                elif ltp >= tp:
                    exit_reason = 'TARGET_REACHED'
                    exit_price = tp
            else: # SELL
                if ltp >= sl:
                    exit_reason = 'STOP_LOSS_HIT'
                    exit_price = sl
                elif ltp <= tp:
                    exit_reason = 'TARGET_REACHED'
                    exit_price = tp

            if exit_reason:
                # Trigger Auto Exit
                self.positions.pop(pos_id)
                db.delete_position(pos_id)

                charges = self.calculate_statutory_charges(entry_p, exit_price, qty, direction)
                final_pnl = (exit_price - entry_p) * qty if direction == 'BUY' else (entry_p - exit_price) * qty
                net_pnl = round(final_pnl - charges, 2)
                realized_r = round(net_pnl / self.risk_per_trade, 2)

                self.capital = round(self.capital + net_pnl, 2)
                db.update_settings({'capital': self.capital})

                trade_record = {
                    'id': pos_id,
                    'symbol': sym,
                    'direction': direction,
                    'entry_price': entry_p,
                    'exit_price': exit_price,
                    'quantity': qty,
                    'margin_used': pos['margin_used'],
                    'entry_time': to_ist_time_str(pos['entry_time']),
                    'exit_time': now_ist_str("%H:%M:%S"),
                    'exit_reason': exit_reason,
                    'realized_pnl': net_pnl,
                    'realized_r': realized_r,
                    'charges': charges,
                    'trade_date': now_ist_date_str(),
                    'created_at': now_ist_datetime_str()
                }
                db.save_closed_trade(trade_record)
                telegram_service.notify_trade_exit(trade_record)
                closed_trades.append(trade_record)
                self._recalculate_governor_state()

        return closed_trades

    def get_summary(self):
        used_margin = self.get_used_margin()
        avail_margin = self.get_available_margin()
        unrealized_pnl = sum(p['unrealized_pnl'] for p in self.positions.values())
        unrealized_r = sum(p['unrealized_r'] for p in self.positions.values())
        
        # Load trade history stats
        history = db.get_trade_history()
        realized_pnl = sum(t['realized_pnl'] for t in history)
        realized_r = sum(t['realized_r'] for t in history)
        total_trades = len(history)
        wins = sum(1 for t in history if t['realized_pnl'] > 0)
        win_rate = round((wins / total_trades) * 100.0, 1) if total_trades > 0 else 0.0

        total_pnl = round(realized_pnl + unrealized_pnl, 2)
        total_r = round(realized_r + unrealized_r, 2)

        return {
            'capital': round(self.capital, 2),
            'available_margin': round(avail_margin, 2),
            'used_margin': round(used_margin, 2),
            'risk_per_trade': round(self.risk_per_trade, 2),
            'trading_mode': self.trading_mode,
            'bot_active': self.bot_active,
            'max_open_positions': self.max_open_positions,
            'target_rr': self.target_rr,
            'open_positions_count': len(self.positions),
            'positions': list(self.positions.values()),
            'unrealized_pnl': round(unrealized_pnl, 2),
            'unrealized_r': round(unrealized_r, 2),
            'realized_pnl': round(realized_pnl, 2),
            'realized_r': round(realized_r, 2),
            'total_pnl': total_pnl,
            'total_r': total_r,
            'total_trades': total_trades,
            'win_rate': win_rate,
            'strategy_name': 'Nifty-Aligned VWAP Pullback + Risk Governor',
            'governor_mode': self.governor_mode,
            'governor_multiplier': self.governor_multiplier,
            'current_drawdown_r': self.current_drawdown_r,
            'peak_realized_r': self.peak_realized_r,
            'effective_risk': self.get_effective_risk(),
            'instruments_count': 14,
            'eod_squareoff_time': '15:00 IST'
        }

portfolio = PortfolioManager()
