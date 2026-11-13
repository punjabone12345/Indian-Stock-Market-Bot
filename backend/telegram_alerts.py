import urllib.request
import ssl
import json
from datetime import datetime

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

    def notify_order_entry(self, pos: dict):
        dir_icon = "🟢 BUY" if pos['direction'] == 'BUY' else "🔴 SELL"
        text = (
            f"⚡ *NEW TRADE EXECUTED ({pos.get('mode', 'PAPER')})*\n\n"
            f"• *Symbol:* `{pos['symbol']}`\n"
            f"• *Action:* *{dir_icon}*\n"
            f"• *Entry Price:* `₹{pos['entry_price']:,.2f}`\n"
            f"• *Stop Loss:* `₹{pos['stop_loss']:,.2f}` ({pos.get('sl_pct', 0.34):.2f}%)\n"
            f"• *Take Profit (1:3):* `₹{pos['take_profit']:,.2f}`\n"
            f"• *Quantity:* `{pos['quantity']} shares`\n"
            f"• *Margin Locked (5x MIS):* `₹{pos['margin_used']:,.2f}`\n"
            f"• *Time:* `{datetime.now().strftime('%H:%M:%S IST')}`\n"
            f"• *Setup:* `{pos.get('setup', 'Crown 6 EMA Pullback')}`"
        )
        return self.send_message(text)

    def notify_trade_exit(self, trade: dict):
        pnl = trade['realized_pnl']
        r = trade['realized_r']
        icon = "🎯 TARGET REACHED" if "TARGET" in trade['exit_reason'] else ("🛑 STOP LOSS HIT" if "STOP" in trade['exit_reason'] else "⚡ POSITION CLOSED")
        pnl_str = f"+₹{pnl:,.2f} (+{r:+.2f} R)" if pnl >= 0 else f"-₹{abs(pnl):,.2f} ({r:+.2f} R)"
        
        text = (
            f"*{icon}*\n\n"
            f"• *Symbol:* `{trade['symbol']}` ({trade['direction']})\n"
            f"• *Exit Price:* `₹{trade['exit_price']:,.2f}`\n"
            f"• *Net Result:* *{pnl_str}*\n"
            f"• *Reason:* `{trade['exit_reason']}`\n"
            f"• *Statutory Charges:* `₹{trade.get('charges', 0):,.2f}`\n"
            f"• *Margin Released:* `₹{trade['margin_used']:,.2f}`\n"
            f"• *Exit Time:* `{datetime.now().strftime('%H:%M:%S IST')}`"
        )
        return self.send_message(text)

    def notify_manual_close(self, trade: dict):
        pnl = trade['realized_pnl']
        pnl_str = f"+₹{pnl:,.2f}" if pnl >= 0 else f"-₹{abs(pnl):,.2f}"
        text = (
            f"✋ *MANUAL EXIT CONFIRMED*\n\n"
            f"• *Symbol:* `{trade['symbol']}`\n"
            f"• *Exit Price:* `₹{trade['exit_price']:,.2f}`\n"
            f"• *P&L:* *{pnl_str}*\n"
            f"• *Margin Released:* `₹{trade['margin_used']:,.2f}`\n"
            f"• *Time:* `{datetime.now().strftime('%H:%M:%S IST')}`"
        )
        return self.send_message(text)

    def notify_position_deleted(self, symbol: str, margin_released: float):
        text = (
            f"🗑️ *POSITION DELETED FROM LEDGER*\n\n"
            f"• *Symbol:* `{symbol}`\n"
            f"• *Margin Released:* `₹{margin_released:,.2f}`\n"
            f"• *P&L Counted:* `₹0.00` (Cancelled without impact)\n"
            f"• *Time:* `{datetime.now().strftime('%H:%M:%S IST')}`"
        )
        return self.send_message(text)

    def notify_test(self):
        text = (
            f"🔔 *TEST NOTIFICATION SUCCESSFUL*\n\n"
            f"Your Telegram bot is successfully linked to **Indian Stock Market Bot**!\n"
            f"• *Time:* `{datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}`\n"
            f"• *Status:* Online & Listening for live trade signals."
        )
        return self.send_message(text)

telegram_service = TelegramService()
