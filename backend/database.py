import os
import sqlite3
import json
from datetime import datetime
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
                risk_per_trade REAL DEFAULT 200.0,
                trading_mode TEXT DEFAULT 'PAPER',
                dhan_client_id TEXT DEFAULT '',
                dhan_access_token TEXT DEFAULT '',
                telegram_token TEXT DEFAULT '9230981995:AAHm8Pa65hwSHvH1N89qLwWzdEZDXKEVdWc',
                telegram_chat_id TEXT DEFAULT '5582938659',
                max_open_positions INTEGER DEFAULT 6,
                target_rr REAL DEFAULT 3.0,
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
                setup TEXT DEFAULT 'EMA Pullback 1:3',
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
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cur.execute("""
                INSERT INTO settings (id, capital, risk_per_trade, trading_mode, telegram_token, telegram_chat_id, max_open_positions, target_rr, bot_active, updated_at)
                VALUES (1, 100000.0, 200.0, 'PAPER', '9230981995:AAHm8Pa65hwSHvH1N89qLwWzdEZDXKEVdWc', '5582938659', 6, 3.0, 1, ?)
            """ if not self.is_postgres else """
                INSERT INTO settings (id, capital, risk_per_trade, trading_mode, telegram_token, telegram_chat_id, max_open_positions, target_rr, bot_active, updated_at)
                VALUES (1, 100000.0, 200.0, 'PAPER', '9230981995:AAHm8Pa65hwSHvH1N89qLwWzdEZDXKEVdWc', '5582938659', 6, 3.0, 1, %s)
            """, (now_str,))

        conn.commit()
        conn.close()
        print(f"[DB] Initialized database successfully (Engine: {'Neon Postgres' if self.is_postgres else 'SQLite'}).")

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
            'risk_per_trade': 200.0,
            'trading_mode': 'PAPER',
            'dhan_client_id': '',
            'dhan_access_token': '',
            'telegram_token': '9230981995:AAHm8Pa65hwSHvH1N89qLwWzdEZDXKEVdWc',
            'telegram_chat_id': '5582938659',
            'max_open_positions': 6,
            'target_rr': 3.0,
            'bot_active': True
        }

    def update_settings(self, updates: dict):
        current = self.get_settings()
        current.update(updates)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
        return [dict(r) for r in rows]

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
            pos['entry_time'], pos.get('setup', 'EMA Pullback 1:3'), pos['sl_dist'],
            pos.get('created_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
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
        return [dict(r) for r in rows]

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
            trade['entry_time'], trade['exit_time'], trade['exit_reason'],
            trade['realized_pnl'], trade['realized_r'], trade.get('charges', 0.0),
            trade.get('trade_date', datetime.now().strftime("%Y-%m-%d")),
            trade.get('created_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        cur.execute(sql, params)
        conn.commit()
        conn.close()

    def reset_database(self):
        """Danger Zone: Clears all positions & trade history, resets balance to default ₹1,00,000"""
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM positions")
        cur.execute("DELETE FROM trade_history")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sql = """
            UPDATE settings SET
                capital = 100000.0,
                risk_per_trade = 200.0,
                updated_at = ?
            WHERE id = 1
        """ if not self.is_postgres else """
            UPDATE settings SET
                capital = 100000.0,
                risk_per_trade = 200.0,
                updated_at = %s
            WHERE id = 1
        """
        cur.execute(sql, (now_str,))
        conn.commit()
        conn.close()
        print("[DB] Danger Zone: Factory Reset executed successfully.")

db = Database()
