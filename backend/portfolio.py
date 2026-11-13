import uuid
import time
from datetime import datetime
try:
    from database import db
    from telegram_alerts import telegram_service
except ImportError:
    from backend.database import db
    from backend.telegram_alerts import telegram_service

class PortfolioManager:
    def __init__(self):
        self.refresh_from_db()

    def refresh_from_db(self):
        settings = db.get_settings()
        self.capital = float(settings.get('capital', 100000.0))
        self.risk_per_trade = float(settings.get('risk_per_trade', 200.0))
        self.trading_mode = settings.get('trading_mode', 'PAPER')
        self.max_open_positions = int(settings.get('max_open_positions', 6))
        self.target_rr = float(settings.get('target_rr', 3.0))
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
                'entry_time': p['entry_time'],
                'setup': p.get('setup', 'Crown 6 EMA Pullback'),
                'sl_dist': float(p['sl_dist']),
                'current_price': float(p['entry_price']),
                'unrealized_pnl': 0.0,
                'unrealized_r': 0.0,
                'created_at': p.get('created_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            }

    def calculate_statutory_charges(self, entry_price: float, exit_price: float, qty: int, direction: str) -> float:
        """
        Exact Indian Statutory Charges (NSE Equity Intraday MIS):
        - Brokerage: ₹20 flat or 0.03% (whichever lower)
        - STT / CTT: 0.025% on sell side
        - Exchange Turnover Fee: 0.00297% (NSE)
        - GST: 18% on (Brokerage + Exchange Fees)
        - SEBI Charges: ₹10 per crore (0.0001%)
        - Stamp Duty: 0.003% on buy turnover
        """
        turnover_entry = entry_price * qty
        turnover_exit = exit_price * qty
        total_turnover = turnover_entry + turnover_exit

        # 1. Brokerage
        brok_entry = min(20.0, turnover_entry * 0.0003)
        brok_exit = min(20.0, turnover_exit * 0.0003)
        total_brok = brok_entry + brok_exit

        # 2. STT (Sell side only for equity intraday)
        stt = (turnover_exit * 0.00025) if direction == 'BUY' else (turnover_entry * 0.00025)

        # 3. Exchange Turnover charges (0.00297%)
        exch_fees = total_turnover * 0.0000297

        # 4. GST (18% on Brokerage + Exchange charges)
        gst = (total_brok + exch_fees) * 0.18

        # 5. SEBI turnover fee (₹10 / crore)
        sebi_fees = total_turnover * 0.000001

        # 6. Stamp duty (0.003% on Buy turnover)
        stamp_duty = (turnover_entry if direction == 'BUY' else turnover_exit) * 0.00003

        total_charges = total_brok + stt + exch_fees + gst + sebi_fees + stamp_duty
        return round(total_charges, 2)

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

        if sl_dist <= 0:
            return {'status': 'error', 'message': 'Invalid Stop Loss price.'}

        # Position Sizing: 1R Risk amount
        quantity = int(self.risk_per_trade / sl_dist)
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
        entry_time_str = datetime.now().strftime("%H:%M:%S")

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
            'setup': signal.get('setup', 'Crown 6 EMA Pullback 1:3'),
            'sl_dist': round(sl_dist, 2),
            'current_price': round(entry_price, 2),
            'unrealized_pnl': 0.0,
            'unrealized_r': 0.0,
            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
            'entry_time': pos['entry_time'],
            'exit_time': datetime.now().strftime("%H:%M:%S"),
            'exit_reason': 'MANUAL_USER_CLOSE',
            'realized_pnl': net_pnl,
            'realized_r': realized_r,
            'charges': charges,
            'trade_date': datetime.now().strftime("%Y-%m-%d"),
            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        db.save_closed_trade(trade_record)
        telegram_service.notify_manual_close(trade_record)
        return {'status': 'success', 'trade': trade_record}

    def update_live_prices_and_check_triggers(self, quotes: dict):
        """Updates open positions with live quotes, checks Target / Stop Loss triggers."""
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
            tp = pos['take_profit']

            # Gross & Net Unrealized P&L
            gross_pnl = (ltp - entry_p) * qty if direction == 'BUY' else (entry_p - ltp) * qty
            pos['unrealized_pnl'] = round(gross_pnl, 2)
            pos['unrealized_r'] = round(gross_pnl / self.risk_per_trade, 2)

            # Check Stop Loss / Target Triggers
            exit_reason = None
            exit_price = None

            if direction == 'BUY':
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
                    'entry_time': pos['entry_time'],
                    'exit_time': datetime.now().strftime("%H:%M:%S"),
                    'exit_reason': exit_reason,
                    'realized_pnl': net_pnl,
                    'realized_r': realized_r,
                    'charges': charges,
                    'trade_date': datetime.now().strftime("%Y-%m-%d"),
                    'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                db.save_closed_trade(trade_record)
                telegram_service.notify_trade_exit(trade_record)
                closed_trades.append(trade_record)

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
            'open_positions_count': len(self.positions),
            'positions': list(self.positions.values()),
            'unrealized_pnl': round(unrealized_pnl, 2),
            'unrealized_r': round(unrealized_r, 2),
            'realized_pnl': round(realized_pnl, 2),
            'realized_r': round(realized_r, 2),
            'total_pnl': total_pnl,
            'total_r': total_r,
            'total_trades': total_trades,
            'win_rate': win_rate
        }

portfolio = PortfolioManager()
