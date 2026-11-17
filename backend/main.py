import asyncio
import os
import io
import csv
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Body, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import urllib.request
import ssl
import json

try:
    from ist_time import now_ist, now_ist_str, now_ist_datetime_str, now_ist_date_str, to_ist_time_str
except ImportError:
    from backend.ist_time import now_ist, now_ist_str, now_ist_datetime_str, now_ist_date_str, to_ist_time_str
try:
    from database import db
    from market_data import market_service, CHAMPION_14_INSTRUMENTS
    from portfolio import portfolio
    from trade_engine import trade_engine, TOP_14_SYMBOLS
    from telegram_alerts import telegram_service
except ImportError:
    from backend.database import db
    from backend.market_data import market_service, CHAMPION_14_INSTRUMENTS
    from backend.portfolio import portfolio
    from backend.trade_engine import trade_engine, TOP_14_SYMBOLS
    from backend.telegram_alerts import telegram_service

# Daily 9:00 AM Alert Tracker
last_morning_alert_date = None

async def background_market_scanner():
    global last_morning_alert_date
    print("[Engine] Top 14 VWAP Pullback Scanner & Dynamic Risk Governor initialized.")
    while True:
        try:
            # 1. Check & send 9:00 AM IST Morning Market Readiness Alert on trading days
            now_obj = now_ist()
            is_weekday = (0 <= now_obj.weekday() <= 4)
            today_date = now_obj.strftime("%Y-%m-%d")
            time_mins = now_obj.hour * 60 + now_obj.minute

            # If it's a weekday and time is on/after 09:00 AM IST (540 mins) and not yet sent today
            if is_weekday and time_mins >= 9 * 60 and last_morning_alert_date != today_date:
                try:
                    summary = portfolio.get_summary()
                    sent = telegram_service.notify_morning_readiness(summary)
                    if sent:
                        last_morning_alert_date = today_date
                        print(f"[Telegram] 09:00 AM Morning Market Readiness alert delivered for {today_date}.")
                except Exception as ex:
                    print(f"[Telegram] Error sending 9:00 AM morning readiness alert: {ex}")

            # 2. Run market scan for all 14 champions
            await asyncio.to_thread(trade_engine.run_market_scan)
        except Exception as e:
            print(f"[Engine] Background scan error: {e}")
        await asyncio.sleep(2)  # Update market scores and scan every 2 seconds

@asynccontextmanager
async def lifespan(app: FastAPI):
    scanner_task = asyncio.create_task(background_market_scanner())
    yield
    scanner_task.cancel()

app = FastAPI(
    title="Indian Stock Market Bot - Top 14 VWAP Alpha Engine",
    version="3.0.0",
    lifespan=lifespan
)

# Allow CORS for Vercel, Render, and Localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- TOP PERSISTENT STATUS -----------------
@app.get("/api/status")
@app.get("/api/portfolio")
def get_portfolio_status():
    summary = portfolio.get_summary()
    summary['server_time'] = now_ist_datetime_str() + " IST"
    summary['last_scan_time'] = trade_engine.last_scan_time or (now_ist_str() + " IST")
    return summary

# ----------------- TAB 1: HOME / DASHBOARD -----------------
@app.get("/api/dashboard")
def get_dashboard_data():
    quotes = market_service.fetch_live_quotes()
    if not trade_engine.market_scores:
        try:
            trade_engine.run_market_scan()
        except Exception as e:
            print(f"[Dashboard] Initial scan exception: {e}")
    scores = trade_engine.market_scores

    instruments_data = []
    for sym in TOP_14_SYMBOLS:
        q = quotes.get(sym, {})
        sc = scores.get(sym, {
            'score': 65,
            'trend': 'NEUTRAL',
            'next_step': 'Initializing VWAP institutional pullback scanner...'
        })
        info = CHAMPION_14_INSTRUMENTS.get(sym, {})
        instruments_data.append({
            'symbol': sym,
            'name': info.get('name', sym),
            'sector': info.get('sector', ''),
            'price': q.get('price', info.get('baseline', 1000.0)),
            'prev_close': q.get('prev_close', info.get('baseline', 1000.0)),
            'change': q.get('change', 0.0),
            'change_pct': q.get('change_pct', 0.0),
            'day_high': q.get('day_high', info.get('baseline', 1000.0)),
            'day_low': q.get('day_low', info.get('baseline', 1000.0)),
            'volume': q.get('volume', 0),
            'score': sc.get('score', 60),
            'trend': sc.get('trend', 'NEUTRAL'),
            'next_step': sc.get('next_step', 'Analyzing VWAP micro-structure...'),
            'ema9': sc.get('ema9', q.get('price', 0.0)),
            'vwap': sc.get('vwap', q.get('price', 0.0)),
            'atr': sc.get('atr', 1.0),
            'updated_at': q.get('updated_at', now_ist_str())
        })

    nifty = quotes.get('NIFTY50', {})
    now_ist_obj = now_ist()
    is_weekday = (0 <= now_ist_obj.weekday() <= 4)
    time_mins = now_ist_obj.hour * 60 + now_ist_obj.minute
    is_market_open = is_weekday and (9 * 60 + 15 <= time_mins <= 15 * 60 + 30)

    return {
        'is_market_open': is_market_open,
        'market_status': 'OPEN' if is_market_open else 'CLOSED',
        'ist_time': now_ist_obj.strftime("%H:%M:%S IST"),
        'server_time': now_ist_obj.strftime("%Y-%m-%d %H:%M:%S IST"),
        'last_scan_time': trade_engine.last_scan_time or now_ist_obj.strftime("%H:%M:%S IST"),
        'strategy': 'Nifty-Aligned VWAP Institutional Pullback + Risk Governor',
        'governor': {
            'mode': portfolio.governor_mode,
            'multiplier': portfolio.governor_multiplier,
            'current_drawdown_r': portfolio.current_drawdown_r,
            'peak_realized_r': portfolio.peak_realized_r,
            'effective_risk': portfolio.get_effective_risk()
        },
        'nifty50': {
            'price': nifty.get('price', 25291.10),
            'change': nifty.get('change', 0.0),
            'change_pct': nifty.get('change_pct', 0.0)
        },
        'instruments': instruments_data,
        'summary': portfolio.get_summary()
    }

# ----------------- TAB 2: RUNNING POSITIONS -----------------
@app.get("/api/positions")
def get_open_positions():
    portfolio.refresh_from_db()
    quotes = market_service.fetch_live_quotes()
    portfolio.update_live_prices_and_check_triggers(quotes)
    return {
        'count': len(portfolio.positions),
        'positions': list(portfolio.positions.values()),
        'used_margin': portfolio.get_used_margin(),
        'available_margin': portfolio.get_available_margin(),
        'governor_mode': portfolio.governor_mode,
        'effective_risk': portfolio.get_effective_risk()
    }

@app.delete("/api/positions/{pos_id}")
def delete_position(pos_id: str):
    """Delete position: Releases margin, removes from DB, NO P&L counted."""
    res = portfolio.delete_position(pos_id)
    if res['status'] == 'error':
        raise HTTPException(status_code=404, detail=res['message'])
    return res

@app.post("/api/positions/{pos_id}/close")
def close_position_manually(pos_id: str):
    """Close position manually at market price: Releases margin, records P&L and exact charges."""
    quotes = market_service.fetch_live_quotes()
    pos = portfolio.positions.get(pos_id)
    cur_p = quotes.get(pos['symbol'], {}).get('price') if pos else None
    res = portfolio.close_position_manually(pos_id, current_price=cur_p)
    if res['status'] == 'error':
        raise HTTPException(status_code=404, detail=res['message'])
    return res

@app.post("/api/bot/panic-square-off")
def panic_square_off_all():
    """Emergency Kill Switch: Square off all open positions immediately."""
    quotes = market_service.fetch_live_quotes()
    closed = []
    for pos_id in list(portfolio.positions.keys()):
        pos = portfolio.positions[pos_id]
        cur_p = quotes.get(pos['symbol'], {}).get('price', pos['entry_price'])
        res = portfolio.close_position_manually(pos_id, current_price=cur_p)
        if res['status'] == 'success':
            closed.append(res['trade'])
    return {'status': 'success', 'closed_count': len(closed), 'trades': closed}

# ----------------- MORNING 9:00 AM READINESS NOTIFICATION -----------------
@app.post("/api/bot/send-morning-alert")
def send_morning_alert_now():
    """Trigger the 9:00 AM Market Readiness Alert immediately for verification."""
    global last_morning_alert_date
    summary = portfolio.get_summary()
    sent = telegram_service.notify_morning_readiness(summary)
    if sent:
        last_morning_alert_date = now_ist_date_str()
        return {'status': 'success', 'message': '09:00 AM Morning Market Readiness alert sent to Telegram successfully!'}
    raise HTTPException(status_code=500, detail='Failed to deliver Telegram alert. Verify credentials.')

# ----------------- TAB 3: ANALYTICS & LEDGER -----------------
@app.get("/api/analytics")
def get_analytics():
    trades = db.get_trade_history()
    
    grouped = {}
    for t in trades:
        d = t.get('trade_date', 'Unknown')
        if d not in grouped:
            grouped[d] = []
        grouped[d].append(t)

    date_groups = []
    for dt in sorted(grouped.keys(), reverse=True):
        group_trades = grouped[dt]
        day_pnl = sum(tr['realized_pnl'] for tr in group_trades)
        day_r = sum(tr['realized_r'] for tr in group_trades)
        date_groups.append({
            'date': dt,
            'day_pnl': round(day_pnl, 2),
            'total_pnl': round(day_pnl, 2),
            'day_r': round(day_r, 2),
            'trades_count': len(group_trades),
            'trades': group_trades
        })

    tot = len(trades)
    wins = sum(1 for t in trades if t['realized_pnl'] > 0)
    losses = sum(1 for t in trades if t['realized_pnl'] < 0)
    win_rate = round((wins / tot) * 100.0, 1) if tot > 0 else 0.0
    tot_pnl = round(sum(t['realized_pnl'] for t in trades), 2)
    tot_r = round(sum(t['realized_r'] for t in trades), 2)
    tot_charges = round(sum(t.get('charges', 0) for t in trades), 2)

    win_pnls = [t['realized_pnl'] for t in trades if t['realized_pnl'] > 0]
    loss_pnls = [abs(t['realized_pnl']) for t in trades if t['realized_pnl'] < 0]
    pf = round(sum(win_pnls) / sum(loss_pnls), 2) if sum(loss_pnls) > 0 else (1.68 if tot == 0 else 99.0)

    best_trade = max((t['realized_pnl'] for t in trades), default=0.0)
    worst_trade = min((t['realized_pnl'] for t in trades), default=0.0)

    return {
        'total_trades': tot,
        'wins': wins,
        'losses': losses,
        'win_rate': win_rate,
        'profit_factor': pf,
        'total_pnl': tot_pnl,
        'total_r': tot_r,
        'total_charges': tot_charges,
        'best_trade': best_trade,
        'worst_trade': worst_trade,
        'governor': {
            'mode': portfolio.governor_mode,
            'multiplier': portfolio.governor_multiplier,
            'current_drawdown_r': portfolio.current_drawdown_r,
            'peak_realized_r': portfolio.peak_realized_r,
            'effective_risk': portfolio.get_effective_risk()
        },
        'date_groups': date_groups
    }

@app.post("/api/admin/recalculate-charges")
def admin_recalculate_charges():
    db.recalculate_all_trade_charges()
    portfolio.refresh_from_db()
    return {'status': 'success', 'message': 'All trade charges recalculated to 100% Zerodha / Dhan standard.'}

@app.get("/api/analytics/export")
def export_trades_csv():
    trades = db.get_trade_history()
    output = io.StringIO()
    writer = csv.writer(output)
    
    headers = [
        "Trade ID", "Date", "Symbol", "Direction", "Quantity", 
        "Buy Price", "Sell Price", "Stop Loss", "Take Profit",
        "Margin Used", "Realized PnL (INR)", "Realized R", 
        "Statutory Charges", "Exit Reason", "Entry Time", "Exit Time"
    ]
    writer.writerow(headers)
    
    for t in trades:
        buy_p = t['entry_price'] if t.get('direction') == 'BUY' else t['exit_price']
        sell_p = t['exit_price'] if t.get('direction') == 'BUY' else t['entry_price']
        writer.writerow([
            t['id'], t['trade_date'], t['symbol'], t['direction'], t['quantity'],
            buy_p, sell_p, t.get('stop_loss', ''), t.get('take_profit', ''),
            t['margin_used'], t['realized_pnl'], t['realized_r'],
            t.get('charges', 0.0), t['exit_reason'], t['entry_time'], t['exit_time']
        ])
        
    output.seek(0)
    filename = f"indian_stock_market_bot_trades_{now_ist().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# ----------------- TECHNICAL CANDLESTICK CHART -----------------
@app.get("/api/chart/{symbol}")
def get_chart_data(symbol: str):
    sym = symbol.upper()
    candles = market_service.get_candle_history(sym)
    quotes = market_service.fetch_live_quotes()
    q = quotes.get(sym, {})
    return {
        "symbol": sym,
        "candles": candles,
        "current_price": q.get("price", 0.0),
        "change_pct": q.get("change_pct", 0.0),
        "day_high": q.get("day_high", 0.0),
        "day_low": q.get("day_low", 0.0),
        "volume": q.get("volume", 0)
    }

# ----------------- TAB 4: SETTINGS & DANGER ZONE -----------------
@app.get("/api/settings")
def get_settings():
    s = db.get_settings()
    masked_token = s.get('dhan_access_token', '')
    if masked_token and len(masked_token) > 8:
        s['dhan_access_token_masked'] = masked_token[:4] + "..." + masked_token[-4:]
    else:
        s['dhan_access_token_masked'] = ""
    s['governor_mode'] = portfolio.governor_mode
    s['governor_multiplier'] = portfolio.governor_multiplier
    s['current_drawdown_r'] = portfolio.current_drawdown_r
    s['effective_risk'] = portfolio.get_effective_risk()
    return s

@app.post("/api/settings")
def update_settings(payload: dict = Body(...)):
    allowed_keys = [
        'capital', 'risk_per_trade', 'trading_mode', 'dhan_client_id',
        'dhan_access_token', 'telegram_token', 'telegram_chat_id',
        'max_open_positions', 'target_rr', 'bot_active'
    ]
    updates = {k: payload[k] for k in allowed_keys if k in payload}
    res = db.update_settings(updates)
    portfolio.refresh_from_db()
    telegram_service.set_credentials(
        updates.get('telegram_token', telegram_service.token),
        updates.get('telegram_chat_id', telegram_service.chat_id)
    )
    return {'status': 'success', 'settings': res}

@app.post("/api/settings/test-telegram")
def test_telegram():
    ok = telegram_service.notify_test()
    if ok:
        return {'status': 'success', 'message': 'Test alert sent successfully to your Telegram!'}
    raise HTTPException(status_code=400, detail='Failed to send alert. Check Telegram Bot Token & Chat ID.')

@app.post("/api/settings/test-dhan")
def test_dhan_connection(payload: dict = Body(...)):
    client_id = payload.get('client_id', '')
    access_token = payload.get('access_token', '')
    
    if not client_id or not access_token:
        return {'status': 'error', 'message': 'Client ID and Access Token are required.'}
        
    url = "https://api.dhan.co/fundlimit"
    headers = {
        'access-token': access_token,
        'client-id': client_id,
        'Content-Type': 'application/json'
    }
    ctx = ssl._create_unverified_context()
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=6) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            avail = data.get('availMargin', 0.0)
            return {
                'status': 'success',
                'message': f'Dhan API Connected! Available Dhan Margin: ₹{avail:,.2f}',
                'dhan_data': data
            }
    except Exception as e:
        return {
            'status': 'simulated',
            'message': f'Dhan API verification note: {e}. (Paper trading mode active with full simulator!)'
        }

@app.post("/api/settings/reset-danger-zone")
def reset_danger_zone():
    """Danger Zone: Factory reset - clears all trades, open positions, resets capital to ₹1,25,000"""
    db.reset_database()
    portfolio.refresh_from_db()
    telegram_service.send_message(
        "⚠️ *FACTORY RESET EXECUTED*\n\n"
        "• All positions and trade history cleared.\n"
        "• Account capital reset to default: *₹1,25,000*.\n"
        "• Strategy: Top 14 VWAP Institutional Pullback.\n"
        "• Risk Governor initialized to NORMAL (1.0R)."
    )
    return {'status': 'success', 'message': 'Factory reset complete. Account restored to default ₹1,25,000.'}

@app.post("/api/bot/toggle")
def toggle_bot():
    new_state = not portfolio.bot_active
    db.update_settings({'bot_active': new_state})
    portfolio.refresh_from_db()
    status_str = "RESUMED" if new_state else "PAUSED"
    telegram_service.send_message(f"🤖 *BOT STATE CHANGED*\n\nTop 14 VWAP Engine is now *{status_str}*.")
    return {'status': 'success', 'bot_active': new_state}

# ----------------- SIMULATION & COMPATIBILITY ALIASES -----------------
@app.post("/api/panic-close")
@app.post("/api/portfolio/panic_close")
def panic_close_alias():
    return panic_square_off_all()

@app.post("/api/test-telegram")
def test_telegram_alias(payload: dict = Body(None)):
    if payload:
        token = payload.get('token') or payload.get('bot_token')
        chat_id = payload.get('chat_id')
        if token or chat_id:
            telegram_service.set_credentials(token, chat_id)
    return test_telegram()

@app.post("/api/reset")
@app.post("/api/settings/reset")
def reset_alias():
    return reset_danger_zone()

@app.post("/api/positions/delete/{pos_id}")
def delete_position_post_alias(pos_id: str):
    return delete_position(pos_id)

@app.post("/api/positions/close/{pos_id}")
def close_position_post_alias(pos_id: str):
    return close_position_manually(pos_id)

@app.post("/api/positions/simulate")
def simulate_paper_position(payload: dict = Body(None)):
    """Simulate a realistic Top 14 VWAP trade with 0.50% SL floor, 5x MIS margin & Dynamic Risk Governor"""
    import random
    quotes = market_service.fetch_live_quotes()
    available_symbols = [s for s in TOP_14_SYMBOLS if s not in [p['symbol'] for p in portfolio.positions.values()]]
    if not available_symbols:
        available_symbols = ['RELIANCE']
    
    sym = random.choice(available_symbols)
    q = quotes.get(sym, {})
    cur_p = q.get('price', 1344.80)
    direction = random.choice(['BUY', 'SELL'])
    # Strict 0.50% SL floor
    sl_dist = round(max(cur_p * 0.0050, 1.0), 2)

    sl_price = round(cur_p - sl_dist, 2) if direction == 'BUY' else round(cur_p + sl_dist, 2)
    tp_price = round(cur_p + (sl_dist * portfolio.target_rr), 2) if direction == 'BUY' else round(cur_p - (sl_dist * portfolio.target_rr), 2)

    signal = {
        'symbol': sym,
        'direction': direction,
        'entry_price': cur_p,
        'stop_loss': sl_price,
        'take_profit': tp_price,
        'setup': 'Top 14 VWAP Institutional Pullback'
    }

    res = portfolio.open_position(signal)
    return res

@app.get("/health")
def health_check():
    return {
        'status': 'healthy', 
        'strategy': 'Top 14 VWAP Pullback + Dynamic Risk Governor',
        'timestamp': now_ist().isoformat()
    }
