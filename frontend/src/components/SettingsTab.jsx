import React, { useState } from 'react';
import { 
  DollarSign, 
  Key, 
  Send, 
  AlertTriangle, 
  Save, 
  CheckCircle2, 
  Trash2,
  X
} from 'lucide-react';

export default function SettingsTab({ settings, onSaveSettings, onResetDangerZone, onTestTelegram, onTestDhan }) {
  const [formData, setFormData] = useState({
    capital: settings?.capital || 100000,
    risk_per_trade: settings?.risk_per_trade || 200,
    trading_mode: settings?.trading_mode || 'PAPER',
    dhan_client_id: settings?.dhan_client_id || '',
    dhan_access_token: settings?.dhan_access_token || '',
    telegram_token: settings?.telegram_token || '9230981995:AAHm8Pa65hwSHvH1N89qLwWzdEZDXKEVdWc',
    telegram_chat_id: settings?.telegram_chat_id || '5582938659'
  });

  const [showResetModal, setShowResetModal] = useState(false);
  const [saveStatus, setSaveStatus] = useState('');
  const [telegramStatus, setTelegramStatus] = useState('');
  const [dhanStatus, setDhanStatus] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setSaveStatus('');
    try {
      await onSaveSettings(formData);
      setSaveStatus('Settings successfully saved to database!');
      setTimeout(() => setSaveStatus(''), 4000);
    } catch (err) {
      setSaveStatus('Error saving settings.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleTestTelegram = async () => {
    setTelegramStatus('Sending test notification...');
    try {
      const res = await onTestTelegram();
      setTelegramStatus(res?.message || 'Telegram alert delivered!');
      setTimeout(() => setTelegramStatus(''), 5000);
    } catch (err) {
      setTelegramStatus('Failed to send Telegram alert.');
    }
  };

  const handleTestDhan = async () => {
    setDhanStatus('Verifying Dhan API...');
    try {
      const res = await onTestDhan(formData.dhan_client_id, formData.dhan_access_token);
      setDhanStatus(res?.message || 'Dhan API Verified!');
      setTimeout(() => setDhanStatus(''), 5000);
    } catch (err) {
      setDhanStatus('Dhan API verification error.');
    }
  };

  return (
    <div className="space-y-3 pb-8">
      
      {/* SECTION HEADER */}
      <div className="flex items-center justify-between px-1 pt-1 pb-1 border-b border-white/[0.06]">
        <div>
          <h2 className="text-xs font-black tracking-tight text-white font-mono uppercase">
            Broker & Risk Config
          </h2>
        </div>
        <span className="text-[10px] font-mono text-slate-400">Control Center</span>
      </div>

      {saveStatus && (
        <div className="p-3 rounded-xl bg-emerald-500/15 border border-emerald-500/40 text-emerald-300 text-xs font-bold flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 flex-shrink-0 text-emerald-400" />
          <span>{saveStatus}</span>
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-3">
        
        {/* 1. CAPITAL & RISK SIZING */}
        <div className="bg-[#0F1424] border border-white/[0.08] rounded-2xl p-3.5 space-y-3 shadow-md">
          <h3 className="text-[11px] font-bold font-mono uppercase tracking-wider text-white flex items-center gap-1.5">
            <DollarSign className="w-3.5 h-3.5 text-emerald-400" />
            <span>Capital & Risk Parameters</span>
          </h3>

          <div className="grid grid-cols-2 gap-2.5">
            <div>
              <label className="block text-[11px] font-semibold text-slate-300 mb-1">
                Capital (₹)
              </label>
              <input
                type="number"
                name="capital"
                value={formData.capital}
                onChange={handleChange}
                step="1000"
                min="10000"
                className="w-full px-3 py-2 rounded-xl bg-[#090D18] border border-white/[0.08] text-white font-mono text-xs focus:outline-none focus:border-sky-400"
                required
              />
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-slate-300 mb-1">
                Risk / Trade 1R (₹)
              </label>
              <input
                type="number"
                name="risk_per_trade"
                value={formData.risk_per_trade}
                onChange={handleChange}
                step="25"
                min="50"
                className="w-full px-3 py-2 rounded-xl bg-[#090D18] border border-white/[0.08] text-white font-mono text-xs focus:outline-none focus:border-sky-400"
                required
              />
            </div>
          </div>

          {/* Trading Mode */}
          <div>
            <label className="block text-[11px] font-semibold text-slate-300 mb-1">
              Execution Mode
            </label>
            <div className="grid grid-cols-2 gap-2 font-mono text-xs">
              <button
                type="button"
                onClick={() => setFormData((p) => ({ ...p, trading_mode: 'PAPER' }))}
                className={`py-2 px-2 rounded-xl border flex flex-col items-center justify-center transition-all cursor-pointer ${
                  formData.trading_mode === 'PAPER'
                    ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-300 font-black'
                    : 'bg-[#090D18] border-white/[0.08] text-slate-400'
                }`}
              >
                <span>PAPER TRADING</span>
                <span className="text-[9px] text-slate-400">Live Ticks + Friction</span>
              </button>

              <button
                type="button"
                onClick={() => setFormData((p) => ({ ...p, trading_mode: 'LIVE' }))}
                className={`py-2 px-2 rounded-xl border flex flex-col items-center justify-center transition-all cursor-pointer ${
                  formData.trading_mode === 'LIVE'
                    ? 'bg-amber-500/20 border-amber-500/50 text-amber-300 font-black'
                    : 'bg-[#090D18] border-white/[0.08] text-slate-400'
                }`}
              >
                <span>LIVE DHAN BROKER</span>
                <span className="text-[9px] text-slate-400">Real Demat Execution</span>
              </button>
            </div>
          </div>
        </div>

        {/* 2. DHAN API CREDENTIALS */}
        <div className="bg-[#0F1424] border border-white/[0.08] rounded-2xl p-3.5 space-y-3 shadow-md">
          <div className="flex items-center justify-between">
            <h3 className="text-[11px] font-bold font-mono uppercase tracking-wider text-white flex items-center gap-1.5">
              <Key className="w-3.5 h-3.5 text-sky-400" />
              <span>DhanHQ API Credentials</span>
            </h3>
            <button
              type="button"
              onClick={handleTestDhan}
              className="px-2 py-1 rounded-lg bg-sky-500/15 border border-sky-500/30 text-sky-300 text-[10px] font-bold font-mono hover:bg-sky-500/25"
            >
              Test API
            </button>
          </div>

          {dhanStatus && (
            <p className="text-[11px] font-mono text-sky-300 bg-sky-500/10 p-2 rounded-xl border border-sky-500/20">
              {dhanStatus}
            </p>
          )}

          <div className="space-y-2">
            <div>
              <label className="block text-[11px] font-semibold text-slate-300 mb-1">
                Dhan Client ID
              </label>
              <input
                type="text"
                name="dhan_client_id"
                value={formData.dhan_client_id}
                onChange={handleChange}
                placeholder="e.g. 1000289123"
                className="w-full px-3 py-2 rounded-xl bg-[#090D18] border border-white/[0.08] text-white font-mono text-xs focus:outline-none focus:border-sky-400"
              />
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-slate-300 mb-1">
                Dhan Access Token
              </label>
              <input
                type="password"
                name="dhan_access_token"
                value={formData.dhan_access_token}
                onChange={handleChange}
                placeholder="eyJhbGciOi..."
                className="w-full px-3 py-2 rounded-xl bg-[#090D18] border border-white/[0.08] text-white font-mono text-xs focus:outline-none focus:border-sky-400"
              />
            </div>
          </div>
        </div>

        {/* 3. TELEGRAM BOT NOTIFICATIONS */}
        <div className="bg-[#0F1424] border border-white/[0.08] rounded-2xl p-3.5 space-y-3 shadow-md">
          <div className="flex items-center justify-between">
            <h3 className="text-[11px] font-bold font-mono uppercase tracking-wider text-white flex items-center gap-1.5">
              <Send className="w-3.5 h-3.5 text-emerald-400" />
              <span>Telegram Live Alerts</span>
            </h3>
            <button
              type="button"
              onClick={handleTestTelegram}
              className="px-2 py-1 rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 text-[10px] font-bold font-mono hover:bg-emerald-500/25"
            >
              Test Ping
            </button>
          </div>

          {telegramStatus && (
            <p className="text-[11px] font-mono text-emerald-300 bg-emerald-500/10 p-2 rounded-xl border border-emerald-500/20">
              {telegramStatus}
            </p>
          )}

          <div className="space-y-2">
            <div>
              <label className="block text-[11px] font-semibold text-slate-300 mb-1">
                Telegram Bot Token
              </label>
              <input
                type="text"
                name="telegram_token"
                value={formData.telegram_token}
                onChange={handleChange}
                className="w-full px-3 py-2 rounded-xl bg-[#090D18] border border-white/[0.08] text-white font-mono text-xs focus:outline-none focus:border-emerald-400"
              />
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-slate-300 mb-1">
                Telegram Chat ID
              </label>
              <input
                type="text"
                name="telegram_chat_id"
                value={formData.telegram_chat_id}
                onChange={handleChange}
                className="w-full px-3 py-2 rounded-xl bg-[#090D18] border border-white/[0.08] text-white font-mono text-xs focus:outline-none focus:border-emerald-400"
              />
            </div>
          </div>
        </div>

        {/* SAVE BUTTON */}
        <button
          type="submit"
          disabled={isLoading}
          className="w-full py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 text-slate-950 font-black text-xs font-mono flex items-center justify-center gap-1.5 transition-all shadow-md shadow-emerald-500/20 cursor-pointer disabled:opacity-50"
        >
          <Save className="w-3.5 h-3.5" />
          <span>SAVE CONFIGURATION</span>
        </button>

      </form>

      {/* 4. DANGER ZONE: FACTORY RESET */}
      <div className="border border-rose-500/40 rounded-2xl p-3.5 bg-rose-500/[0.04] space-y-2.5 mt-4">
        <div className="flex items-center gap-2 text-rose-400">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          <h3 className="text-[11px] font-black font-mono uppercase tracking-wider">
            DANGER ZONE: FACTORY RESET APP
          </h3>
        </div>

        <p className="text-[11px] text-slate-300 leading-relaxed">
          Clears all open positions, deletes all trade history, and resets balance to <strong>₹1,00,000.00 with 0 trades</strong>.
        </p>

        <button
          type="button"
          onClick={() => setShowResetModal(true)}
          className="w-full py-2 rounded-xl bg-rose-500/15 hover:bg-rose-500/25 border border-rose-500/40 text-rose-300 text-xs font-bold font-mono flex items-center justify-center gap-1.5 transition-all cursor-pointer"
        >
          <Trash2 className="w-3.5 h-3.5 text-rose-400" />
          <span>FACTORY RESET APP</span>
        </button>
      </div>

      {/* CONFIRMATION MODAL */}
      {showResetModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-md p-4 animate-fade-in">
          <div className="bg-[#101626] border border-rose-500/50 rounded-2xl max-w-sm w-full p-5 space-y-3 shadow-2xl">
            <div className="flex items-center justify-between">
              <div className="w-10 h-10 rounded-xl bg-rose-500/20 border border-rose-500/40 flex items-center justify-center text-rose-400">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <button onClick={() => setShowResetModal(false)} className="p-1 rounded-lg text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div>
              <h3 className="text-sm font-black text-white">CONFIRM FACTORY RESET</h3>
              <p className="text-[11px] text-rose-400 font-mono mt-0.5">Irreversible Action</p>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              • Purges all trade history and ledger records.
              <br />
              • Resets capital to <strong className="text-white font-mono">₹1,00,000.00</strong>.
            </p>

            <div className="flex items-center justify-end gap-2 pt-1">
              <button
                type="button"
                onClick={() => setShowResetModal(false)}
                className="flex-1 py-2 rounded-xl text-xs font-bold text-slate-300 bg-white/5 border border-white/10"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  onResetDangerZone();
                  setShowResetModal(false);
                }}
                className="flex-1 py-2 rounded-xl text-xs font-bold text-white bg-rose-600 hover:bg-rose-500 border border-rose-400"
              >
                YES, RESET
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
