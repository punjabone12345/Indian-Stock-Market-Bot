import urllib.request
import ssl
import json
from datetime import datetime
try:
    from ist_time import now_ist_str, now_ist_datetime_str
except ImportError:
    from backend.ist_time import now_ist_str, now_ist_datetime_str

class TelegramService:
    def __init__(self, token="9230981995:AAHm8Pa65hwSHvH1N89qLwWzdEZDXKEVdWc", chat_id="5582938659"):
        self.token = token
        self.chat_id = chat_id
        self.ctx = ssl._create_unverified_context()

    def set_credentials(self, token, chat_id):
        if token: self.token = token
        if chat_id: self.chat_id = chat_id

    def send_message(self, text: str):
        if not self.token or not self.chat_id:
            return False
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, context=self.ctx, timeout=8) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                return res.get("ok", False)
        except Exception as e:
            print(f"[Telegram] Error sending message: {e}")
            return False

    def notify_morning_readiness(self, summary: dict):
        """Daily 09:00 AM IST Market Readiness Telegram notification"""
        capital = summary.get('capital', 100000.0)
        avail = summary.get('available_margin', capital)
        gov_mode = summary.get('governor_mode', 'NORMAL')
        gov_scale = summary.get('governor_multiplier', 1.0)
        curr_dd = summary.get('current_drawdown_r', 0.0)
        eff_risk = summary.get('effective_risk', 2500.0)
        target_rr = summary.get('target_rr', 4.0)
        mode = summary.get('trading_mode', 'PAPER')

        gov_badge = f"🟢 NORMAL ({gov_scale:.1f}x / ₹{eff_risk:,.0f})" if gov_mode == 'NORMAL' else f"🟡 DEFENSIVE ({gov_scale:.1f}x / ₹{eff_risk:,.0f})"

        text = (
            f"🔔 *MARKET READINESS CONFIRMED (09:00 AM IST)*\n\n"
            f"🤖 *Indian Stock Market Bot is Armed & Ready!*\n\n"
            f"• *Strategy:* `Velocity Compounder (Pure 90% Margin)`\n"
            f"• *Execution:* `{mode} MODE`\n"
            f"• *Universe:* `29 Liquid NSE Mega-Caps`\n"
            f"• *Capital Balance:* `₹{capital:,.2f}` (Avail Margin: `₹{avail:,.2f}`)\n"
            f"• *Position Sizing:* `Pure 90% Fixed Margin Allocation` (*{gov_badge}*)\n"
            f"• *Target RRR:* `1:{target_rr}` (Floor SL: `0.50%` | Cap SL: `1.50%`)\n"
            f"• *Protection:* `BE Lock @ +1.5R` | `Trailing Stop @ +2.5R`\n"
            f"• *Selection:* `10:00 AM Pure #1 RS Leader` (Max 1 Trade/Day)\n"
            f"• *EOD Square-Off:* `03:00 PM IST` (Strict Intraday, zero overnight hold)\n"
            f"• *Compounded Edge:* `+8.5% Compounded/Mo | 113.9x Multiplier`"
        )
        return self.send_message(text)

    def notify_order_entry(self, pos: dict):
        dir_icon = "🟢 BUY" if pos['direction'] == 'BUY' else "🔴 SELL"
        price_label = "Buy Price" if pos['direction'] == 'BUY' else "Sell Price"
        gov_mode = pos.get('governor_mode', 'NORMAL')
        gov_str = f" [{gov_mode} MODE]" if gov_mode else ""
        text = (
            f"⚡ *NEW TRADE EXECUTED ({pos.get('mode', 'PAPER')}{gov_str})*\n\n"
            f"• *Symbol:* `{pos['symbol']}`\n"
            f"• *Action:* *{dir_icon}*\n"
            f"• *{price_label}:* `₹{pos['entry_price']:,.2f}`\n"
            f"• *Stop Loss:* `₹{pos['stop_loss']:,.2f}` ({pos.get('sl_pct', 0.50):.2f}% distance)\n"
            f"• *Take Profit:* `₹{pos['take_profit']:,.2f}` (1:{pos.get('target_rr', 4.0)} RRR)\n"
            f"• *Quantity:* `{pos['quantity']} shares`\n"
            f"• *Margin Locked (5x MIS):* `₹{pos['margin_used']:,.2f}`\n"
            f"• *Risk Allocated:* `₹{pos.get('risk_amount', 6000):,.2f}` ({pos.get('risk_pct', 6.0):.2f}% of Equity)\n"
            f"• *Execution Time:* `{now_ist_str('%H:%M:%S IST')}`\n"
            f"• *Strategy:* `Velocity Compounder (Pure 90% Margin)`"
        )
        return self.send_message(text)

    def notify_breakeven_locked(self, pos: dict):
        text = (
            f"🛡️ *BREAKEVEN STOP LOCKED (+1.5R MILESTONE)*\n\n"
            f"• *Symbol:* `{pos['symbol']}` ({pos['direction']})\n"
            f"• *LTP:* `₹{pos['current_price']:,.2f}`\n"
            f"• *New Stop Loss:* `₹{pos['stop_loss']:,.2f}` (Locked at Entry + 0.10R)\n"
            f"• *Risk Status:* **RISK-FREE TRADE (Scratch Protected)**\n"
            f"• *Target Price:* `₹{pos['take_profit']:,.2f}` (4.0R)\n"
            f"• *Time:* `{now_ist_str('%H:%M:%S IST')}`"
        )
        return self.send_message(text)

    def notify_trailing_stop_updated(self, pos: dict):
        text = (
            f"📈 *TRAILING STOP ADVANCED (+2.5R RUNNER)*\n\n"
            f"• *Symbol:* `{pos['symbol']}` ({pos['direction']})\n"
            f"• *LTP:* `₹{pos['current_price']:,.2f}`\n"
            f"• *Trailing Stop Updated:* `₹{pos['stop_loss']:,.2f}`\n"
            f"• *Status:* Profit locked in! Trailing 3-bar swing.\n"
            f"• *Time:* `{now_ist_str('%H:%M:%S IST')}`"
        )
        return self.send_message(text)

    def notify_trade_exit(self, trade: dict):
        pnl = trade['realized_pnl']
        r = trade['realized_r']
        icon = "🎯 TARGET 4.0R REACHED" if "TARGET" in trade['exit_reason'] else (
            "🛡️ BREAKEVEN SCRATCH EXIT" if "BREAKEVEN" in trade['exit_reason'] else (
                "🛑 STOP LOSS HIT" if "STOP" in trade['exit_reason'] else (
                    "⏰ 03:00 PM EOD SQUARE-OFF" if "EOD" in trade['exit_reason'] else "⚡ POSITION CLOSED"
                )
            )
        )
        pnl_str = f"+₹{pnl:,.2f} (+{r:+.2f} R)" if pnl >= 0 else f"-₹{abs(pnl):,.2f} ({r:+.2f} R)"
        price_label = "Sell Price" if trade.get('direction') == 'BUY' else "Buy Price"
        
        text = (
            f"*{icon}*\n\n"
            f"• *Symbol:* `{trade['symbol']}` ({trade['direction']})\n"
            f"• *{price_label}:* `₹{trade['exit_price']:,.2f}`\n"
            f"• *Net Result:* *{pnl_str}*\n"
            f"• *Reason:* `{trade['exit_reason']}`\n"
            f"• *Statutory Charges:* `₹{trade.get('charges', 0):,.2f}` (Zerodha/Dhan schedule)\n"
            f"• *Margin Released:* `₹{trade['margin_used']:,.2f}`\n"
            f"• *Exit Time:* `{now_ist_str('%H:%M:%S IST')}`"
        )
        return self.send_message(text)

    def notify_governor_switch(self, new_mode: str, drawdown_r: float, risk_scale: float, eff_risk: float):
        badge = "🟡 DEFENSIVE MODE ACTIVATED" if new_mode == "DEFENSIVE" else "🟢 NORMAL MODE RESTORED"
        desc = (
            f"Drawdown crossed -15R threshold. Cutting position sizing by 50% (Risk: ₹{eff_risk:,.0f}) to cap maximum drawdown."
            if new_mode == "DEFENSIVE"
            else f"Drawdown recovered above -5R threshold. Restoring standard 2.5% dynamic position sizing (Risk: ₹{eff_risk:,.0f})."
        )
        text = (
            f"🛡️ *{badge}*\n\n"
            f"• *Dynamic Risk Governor Event*\n"
            f"• *Current Drawdown:* `{drawdown_r:+.2f} R`\n"
            f"• *New Risk Multiplier:* `{risk_scale}x` (₹{eff_risk:,.2f} per trade)\n"
            f"• *Action:* {desc}\n"
            f"• *Time:* `{now_ist_datetime_str('%Y-%m-%d %H:%M:%S IST')}`"
        )
        return self.send_message(text)

    def notify_manual_close(self, trade: dict):
        pnl = trade['realized_pnl']
        pnl_str = f"+₹{pnl:,.2f}" if pnl >= 0 else f"-₹{abs(pnl):,.2f}"
        price_label = "Sell Price" if trade.get('direction') == 'BUY' else "Buy Price"
        text = (
            f"✋ *MANUAL EXIT CONFIRMED*\n\n"
            f"• *Symbol:* `{trade['symbol']}`\n"
            f"• *{price_label}:* `₹{trade['exit_price']:,.2f}`\n"
            f"• *P&L:* *{pnl_str}*\n"
            f"• *Margin Released:* `₹{trade['margin_used']:,.2f}`\n"
            f"• *Time:* `{now_ist_str('%H:%M:%S IST')}`"
        )
        return self.send_message(text)

    def notify_position_deleted(self, symbol: str, margin_released: float):
        text = (
            f"🗑️ *POSITION DELETED FROM LEDGER*\n\n"
            f"• *Symbol:* `{symbol}`\n"
            f"• *Margin Released:* `₹{margin_released:,.2f}`\n"
            f"• *P&L Counted:* `₹0.00` (Cancelled without impact)\n"
            f"• *Time:* `{now_ist_str('%H:%M:%S IST')}`"
        )
        return self.send_message(text)

    def notify_test(self):
        text = (
            f"🔔 *TEST NOTIFICATION SUCCESSFUL*\n\n"
            f"Your Telegram bot is successfully linked to **Indian Stock Market Bot**!\n"
            f"• *Strategy:* Velocity Compounder (Pure Leader 4.0R)\n"
            f"• *Watchlist:* 29 Liquid NSE Mega-Caps\n"
            f"• *Time:* `{now_ist_datetime_str('%Y-%m-%d %H:%M:%S IST')}`\n"
            f"• *Status:* Online & Listening for 10:00 AM catalyst execution."
        )
        return self.send_message(text)

telegram_service = TelegramService()
