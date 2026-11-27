import os
import sqlite3
import json
from datetime import datetime
try:
    from ist_time import now_ist_datetime_str, now_ist_date_str, to_ist_time_str
except ImportError:
    from backend.ist_time import now_ist_datetime_str, now_ist_date_str, to_ist_time_str
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False
    RealDictCursor = None

DATABASE_URL = os.environ.get("DATABASE_URL", "")

class Database:
    def __init__(self):
        self.is_postgres = bool(HAS_PSYCOPG2 and DATABASE_URL and ("postgres" in DATABASE_URL or "neon" in DATABASE_URL))
        self.init_db()

    def get_connection(self):
        if self.is_postgres:
            try:
                # SSL required for Neon
                conn = psycopg2.connect(DATABASE_URL, sslmode="require")
                return conn
            except Exception as e:
                print(f"[DB] Postgres connection error ({e}), falling back to SQLite.")
                self.is_postgres = False
        
        # SQLite Fallback
        conn = sqlite3.connect("trades.db", check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        conn = self.get_connection()
        cur = conn.cursor()

        # Settings Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY,
                capital REAL DEFAULT 100000.0,
                risk_per_trade REAL DEFAULT 2500.0,
                trading_mode TEXT DEFAULT 'PAPER',
                dhan_client_id TEXT DEFAULT '',
                dhan_access_token TEXT DEFAULT '',
                telegram_token TEXT DEFAULT '9230981995:AAHm8Pa65hwSHvH1N89qLwWzdEZDXKEVdWc',
                telegram_chat_id TEXT DEFAULT '5582938659',
                max_open_positions INTEGER DEFAULT 1,
                target_rr REAL DEFAULT 4.0,
                bot_active INTEGER DEFAULT 1,
                updated_at TEXT
            )
        """)

        # Open Positions Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_price REAL NOT NULL,
                stop_loss REAL NOT NULL,
                take_profit REAL NOT NULL,
                quantity INTEGER NOT NULL,
                margin_used REAL NOT NULL,
                entry_time TEXT NOT NULL,
                setup TEXT DEFAULT 'Velocity Compounder (Pure Leader 4.0R)',
                sl_dist REAL NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        # Trade History / Master Ledger Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS trade_history (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                margin_used REAL NOT NULL,
                entry_time TEXT NOT NULL,
                exit_time TEXT NOT NULL,
                exit_reason TEXT NOT NULL,
                realized_pnl REAL NOT NULL,
                realized_r REAL NOT NULL,
                charges REAL NOT NULL,
                trade_date TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        # Seed initial default settings if empty
        cur.execute("SELECT COUNT(*) FROM settings")
        row = cur.fetchone()
        count = row[0] if not isinstance(row, dict) else list(row.values())[0]
        if count == 0:
            now_str = now_ist_datetime_str()
            cur.execute("""
                INSERT INTO settings (id, capital, risk_per_trade, trading_mode, telegram_token, telegram_chat_id, max_open_positions, target_rr, bot_active, updated_at)
                VALUES (1, 100000.0, 2500.0, 'PAPER', '9230981995:AAHm8Pa65hwSHvH1N89qLwWzdEZDXKEVdWc', '5582938659', 1, 4.0, 1, ?)
            """ if not self.is_postgres else """
                INSERT INTO settings (id, capital, risk_per_trade, trading_mode, telegram_token, telegram_chat_id, max_open_positions, target_rr, bot_active, updated_at)
                VALUES (1, 100000.0, 2500.0, 'PAPER', '9230981995:AAHm8Pa65hwSHvH1N89qLwWzdEZDXKEVdWc', '5582938659', 1, 4.0, 1, %s)
            """, (now_str,))

        # One-time migration: Convert any UTC timestamps in positions table to IST
        try:
            cur.execute("SELECT id, entry_time FROM positions")
            for r in cur.fetchall():
                row_dict = dict(r)
                ist_t = to_ist_time_str(row_dict.get('entry_time', ''))
                if ist_t and ist_t != row_dict.get('entry_time'):
                    cur.execute("UPDATE positions SET entry_time = ? WHERE id = ?" if not self.is_postgres else "UPDATE positions SET entry_time = %s WHERE id = %s", (ist_t, row_dict['id']))
        except Exception as e:
            pass

        # Ensure active strategy parameters: target_rr = 4.0, max_open_positions = 1
        try:
            cur.execute("UPDATE settings SET target_rr = 4.0, max_open_positions = 1 WHERE id = 1 AND (target_rr != 4.0 OR max_open_positions != 1)" if not self.is_postgres else "UPDATE settings SET target_rr = 4.0, max_open_positions = 1 WHERE id = 1 AND (target_rr != 4.0 OR max_open_positions != 1)")
        except Exception:
            pass

        # Restore persistent trade history from backup JSON if database is empty
        try:
            cur.execute("SELECT COUNT(*) FROM trade_history")
            r_th = cur.fetchone()
            th_count = r_th[0] if not isinstance(r_th, dict) else list(r_th.values())[0]
            backup_file = os.path.join(os.path.dirname(__file__), "trades_history.json")
            if th_count == 0 and os.path.exists(backup_file):
                with open(backup_file, "r", encoding="utf-8") as f:
                    backed_trades = json.load(f)
                cum_pnl = 0.0
                for tr in backed_trades:
                    sql_ins = """
                        INSERT OR IGNORE INTO trade_history (id, symbol, direction, entry_price, exit_price, quantity, margin_used, entry_time, exit_time, exit_reason, realized_pnl, realized_r, charges, trade_date, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """ if not self.is_postgres else """
                        INSERT INTO trade_history (id, symbol, direction, entry_price, exit_price, quantity, margin_used, entry_time, exit_time, exit_reason, realized_pnl, realized_r, charges, trade_date, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO NOTHING
                    """
                    cur.execute(sql_ins, (
                        tr['id'], tr['symbol'], tr['direction'], tr['entry_price'], tr['exit_price'],
                        tr['quantity'], tr['margin_used'], tr['entry_time'], tr['exit_time'],
                        tr['exit_reason'], tr['realized_pnl'], tr['realized_r'], tr.get('charges', 0.0),
                        tr.get('trade_date', now_ist_date_str()), tr.get('created_at', now_ist_datetime_str())
                    ))
                    cum_pnl += tr['realized_pnl']
                
                # Update settings capital reflecting restored trades
                if cum_pnl != 0.0:
                    new_cap = round(100000.0 + cum_pnl, 2)
                    cur.execute("UPDATE settings SET capital = ? WHERE id = 1" if not self.is_postgres else "UPDATE settings SET capital = %s WHERE id = 1", (new_cap,))
                print(f"[DB] Restored {len(backed_trades)} past trades from persistent backup JSON.")
        except Exception as ex:
            print(f"[DB] Error restoring trades backup: {ex}")

        conn.commit()
        conn.close()
        print(f"[DB] Initialized database successfully (Engine: {'Neon Postgres' if self.is_postgres else 'SQLite'}).")

        # Automatically recalculate all closed trade charges to 100% match Zerodha / Dhan
        try:
            self.recalculate_all_trade_charges()
        except Exception as e:
            pass

    def recalculate_all_trade_charges(self):
        """Recalculates all closed trades in trade_history to match exact Zerodha / Dhan charges."""
        conn = self.get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor) if self.is_postgres else conn.cursor()
        cur.execute("SELECT id, symbol, direction, entry_price, exit_price, quantity FROM trade_history")
        rows = cur.fetchall()
        for r in rows:
            d = dict(r)
            en = float(d['entry_price'])
            ex = float(d['exit_price'])
            q = int(d['quantity'])
            direction = d.get('direction', 'BUY')

            if direction == 'BUY':
                buy_val = round(en * q, 2)
                sell_val = round(ex * q, 2)
            else:
                buy_val = round(ex * q, 2)
                sell_val = round(en * q, 2)

            turnover = round(buy_val + sell_val, 2)
            buy_brok = min(20.0, round(buy_val * 0.0003, 2))
            sell_brok = min(20.0, round(sell_val * 0.0003, 2))
            brokerage = round(buy_brok + sell_brok, 2)
            stt = round(sell_val * 0.00025, 2)
            exch_fee = round(turnover * 0.0000297, 2)
            sebi_fee = round(turnover * 0.000001, 2)
            stamp_duty = round(buy_val * 0.00003, 2)
            gst = round((brokerage + exch_fee + sebi_fee) * 0.18, 2)
            total_charges = round(brokerage + stt + exch_fee + sebi_fee + stamp_duty + gst, 2)

            gross_pnl = round((ex - en) * q if direction == 'BUY' else (en - ex) * q, 2)
            net_pnl = round(gross_pnl - total_charges, 2)

            # Calculate 1R risk baseline (Profile 5 Velocity Compounder: dynamic 6.21% risk / max loss)
            risk_unit = 6210.0
            try:
                cur.execute("SELECT risk_per_trade FROM settings WHERE id = 1")
                s_r = cur.fetchone()
                if s_r:
                    r_val = s_r[0] if not isinstance(s_r, dict) else list(s_r.values())[0]
                    if r_val and float(r_val) > 1000.0:
                        risk_unit = float(r_val)
            except Exception:
                pass
            realized_r = round(net_pnl / risk_unit, 2)

            sql = "UPDATE trade_history SET charges = ?, realized_pnl = ?, realized_r = ? WHERE id = ?" if not self.is_postgres else "UPDATE trade_history SET charges = %s, realized_pnl = %s, realized_r = %s WHERE id = %s"
            cur.execute(sql, (total_charges, net_pnl, realized_r, d['id']))

        conn.commit()
        conn.close()
        print("[DB] Recalculated all trade history charges to 100% Zerodha / Dhan standard.")

    def get_settings(self):
        conn = self.get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor) if self.is_postgres else conn.cursor()
        cur.execute("SELECT * FROM settings WHERE id = 1")
        row = cur.fetchone()
        conn.close()
        if row:
            d = dict(row)
            d['bot_active'] = bool(d.get('bot_active', 1))
            return d
        return {
            'capital': 100000.0,
            'risk_per_trade': 6210.0,
            'margin_allocation_pct': 0.90,
            'trading_mode': 'PAPER',
            'dhan_client_id': '',
            'dhan_access_token': '',
            'telegram_token': '9230981995:AAHm8Pa65hwSHvH1N89qLwWzdEZDXKEVdWc',
            'telegram_chat_id': '5582938659',
            'max_open_positions': 1,
            'target_rr': 4.0,
            'bot_active': True
        }

    def update_settings(self, updates: dict):
        current = self.get_settings()
        current.update(updates)
        now_str = now_ist_datetime_str()

        conn = self.get_connection()
        cur = conn.cursor()
        sql = """
            UPDATE settings SET
                capital = ?,
                risk_per_trade = ?,
                trading_mode = ?,
                dhan_client_id = ?,
                dhan_access_token = ?,
                telegram_token = ?,
                telegram_chat_id = ?,
                max_open_positions = ?,
                target_rr = ?,
                bot_active = ?,
                updated_at = ?
            WHERE id = 1
        """ if not self.is_postgres else """
            UPDATE settings SET
                capital = %s,
                risk_per_trade = %s,
                trading_mode = %s,
                dhan_client_id = %s,
                dhan_access_token = %s,
                telegram_token = %s,
                telegram_chat_id = %s,
                max_open_positions = %s,
                target_rr = %s,
                bot_active = %s,
                updated_at = %s
            WHERE id = 1
        """
        params = (
            float(current['capital']),
            float(current['risk_per_trade']),
            str(current['trading_mode']),
            str(current['dhan_client_id']),
            str(current['dhan_access_token']),
            str(current['telegram_token']),
            str(current['telegram_chat_id']),
            int(current['max_open_positions']),
            float(current['target_rr']),
            1 if current['bot_active'] else 0,
            now_str
        )
        cur.execute(sql, params)
        conn.commit()
        conn.close()
        return current

    def get_positions(self):
        conn = self.get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor) if self.is_postgres else conn.cursor()
        cur.execute("SELECT * FROM positions ORDER BY created_at DESC")
        rows = cur.fetchall()
        conn.close()
        positions = []
        for r in rows:
            d = dict(r)
            d['entry_time'] = to_ist_time_str(d.get('entry_time', ''))
            positions.append(d)
        return positions

    def save_position(self, pos: dict):
        conn = self.get_connection()
        cur = conn.cursor()
        sql = """
            INSERT INTO positions (id, symbol, direction, entry_price, stop_loss, take_profit, quantity, margin_used, entry_time, setup, sl_dist, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """ if not self.is_postgres else """
            INSERT INTO positions (id, symbol, direction, entry_price, stop_loss, take_profit, quantity, margin_used, entry_time, setup, sl_dist, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            pos['id'], pos['symbol'], pos['direction'], pos['entry_price'],
            pos['stop_loss'], pos['take_profit'], pos['quantity'], pos['margin_used'],
            to_ist_time_str(pos['entry_time']), pos.get('setup', 'EMA Pullback 1:3'), pos['sl_dist'],
            pos.get('created_at', now_ist_datetime_str())
        )
        cur.execute(sql, params)
        conn.commit()
        conn.close()

    def delete_position(self, pos_id: str):
        conn = self.get_connection()
        cur = conn.cursor()
        sql = "DELETE FROM positions WHERE id = ?" if not self.is_postgres else "DELETE FROM positions WHERE id = %s"
        cur.execute(sql, (pos_id,))
        conn.commit()
        conn.close()

    def get_trade_history(self):
        conn = self.get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor) if self.is_postgres else conn.cursor()
        cur.execute("SELECT * FROM trade_history ORDER BY created_at DESC")
        rows = cur.fetchall()
        conn.close()
        trades = []
        for r in rows:
            d = dict(r)
            d['entry_time'] = to_ist_time_str(d.get('entry_time', ''))
            d['exit_time'] = to_ist_time_str(d.get('exit_time', ''))
            trades.append(d)
        return trades

    def save_closed_trade(self, trade: dict):
        conn = self.get_connection()
        cur = conn.cursor()
        sql = """
            INSERT INTO trade_history (id, symbol, direction, entry_price, exit_price, quantity, margin_used, entry_time, exit_time, exit_reason, realized_pnl, realized_r, charges, trade_date, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """ if not self.is_postgres else """
            INSERT INTO trade_history (id, symbol, direction, entry_price, exit_price, quantity, margin_used, entry_time, exit_time, exit_reason, realized_pnl, realized_r, charges, trade_date, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            trade['id'], trade['symbol'], trade['direction'], trade['entry_price'],
            trade['exit_price'], trade['quantity'], trade['margin_used'],
            to_ist_time_str(trade['entry_time']), to_ist_time_str(trade['exit_time']), trade['exit_reason'],
            trade['realized_pnl'], trade['realized_r'], trade.get('charges', 0.0),
            trade.get('trade_date', now_ist_date_str()),
            trade.get('created_at', now_ist_datetime_str())
        )
        cur.execute(sql, params)
        conn.commit()
        conn.close()

        # Also sync to persistent backup file so it survives container restarts/rebuilds
        try:
            backup_file = os.path.join(os.path.dirname(__file__), "trades_history.json")
            trades_list = []
            if os.path.exists(backup_file):
                with open(backup_file, "r", encoding="utf-8") as f:
                    trades_list = json.load(f)
            if not any(t.get('id') == trade['id'] for t in trades_list):
                trades_list.append(trade)
                with open(backup_file, "w", encoding="utf-8") as f:
                    json.dump(trades_list, f, indent=2)
        except Exception as ex:
            print(f"[DB] Error syncing trade to backup JSON: {ex}")

    def update_position_sl(self, pos_id: str, new_sl: float):
        """Updates stop loss price of an active position (e.g. Breakeven lock or Trailing stop)."""
        conn = self.get_connection()
        cur = conn.cursor()
        sql = "UPDATE positions SET stop_loss = ? WHERE id = ?" if not self.is_postgres else "UPDATE positions SET stop_loss = %s WHERE id = %s"
        cur.execute(sql, (round(float(new_sl), 2), pos_id))
        conn.commit()
        conn.close()

    def reset_database(self):
        """Danger Zone: Clears all positions & trade history, resets balance to default ₹1,00,000"""
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM positions")
        cur.execute("DELETE FROM trade_history")
        now_str = now_ist_datetime_str()
        sql = """
            UPDATE settings SET
                capital = 100000.0,
                risk_per_trade = 2500.0,
                target_rr = 4.0,
                max_open_positions = 1,
                updated_at = ?
            WHERE id = 1
        """ if not self.is_postgres else """
            UPDATE settings SET
                capital = 100000.0,
                risk_per_trade = 2500.0,
                target_rr = 4.0,
                max_open_positions = 1,
                updated_at = %s
            WHERE id = 1
        """
        cur.execute(sql, (now_str,))
        conn.commit()
        conn.close()

        try:
            backup_file = os.path.join(os.path.dirname(__file__), "trades_history.json")
            if os.path.exists(backup_file):
                with open(backup_file, "w", encoding="utf-8") as f:
                    json.dump([], f, indent=2)
        except Exception:
            pass

        print("[DB] Danger Zone: Factory Reset executed successfully. Account restored to ₹1,00,000.")

db = Database()
