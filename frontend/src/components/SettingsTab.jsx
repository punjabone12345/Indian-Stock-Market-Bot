import React, { useState } from 'react';
import { 
  Sliders, 
  Key, 
  Send, 
  AlertTriangle, 
  Save, 
  CheckCircle2, 
  HelpCircle, 
  RefreshCw, 
  ShieldCheck, 
  Trash2,
  DollarSign,
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
    setTelegramStatus('Sending test notification to your phone...');
    try {
      const res = await onTestTelegram();
      setTelegramStatus(res?.message || 'Telegram alert delivered!');
      setTimeout(() => setTelegramStatus(''), 5000);
    } catch (err) {
      setTelegramStatus('Failed to send Telegram alert. Check Token/ID.');
    }
  };

  const handleTestDhan = async () => {
    setDhanStatus('Verifying Dhan API credentials...');
    try {
      const res = await onTestDhan(formData.dhan_client_id, formData.dhan_access_token);
      setDhanStatus(res?.message || 'Dhan API Verified!');
      setTimeout(() => setDhanStatus(''), 5000);
    } catch (err) {
      setDhanStatus('Dhan API verification error.');
    }
  };

  return (
    <div className="space-y-5 pb-16 max-w-4xl mx-auto px-3 sm:px-6 pt-4">
      
      {/* SECTION HEADER */}
      <div className="border-b border-white/[0.06] pb-3">
        <h2 className="text-lg sm:text-xl font-extrabold tracking-tight text-white flex items-center gap-2">
          <span>SYSTEM & BROKER CONFIGURATION</span>
          <span className="px-2.5 py-0.5 text-[10px] font-mono font-bold bg-white/[0.06] text-slate-300 rounded-full border border-white/10">
            Control Center
          </span>
        </h2>
        <p className="text-xs text-slate-400 mt-0.5">
          Configure capital, risk per trade, Dhan API credentials, and live Telegram push notifications.
        </p>
      </div>

      {saveStatus && (
        <div className="p-3.5 rounded-2xl bg-emerald-500/15 border border-emerald-500/40 text-emerald-300 text-xs font-bold flex items-center gap-2 animate-fade-in">
          <CheckCircle2 className="w-4 h-4 flex-shrink-0 text-emerald-400" />
          <span>{saveStatus}</span>
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-5">
        
        {/* 1. CAPITAL & RISK SIZING */}
        <div className="m3-card p-5 space-y-4">
          <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-white flex items-center gap-2">
            <DollarSign className="w-4 h-4 text-emerald-400" />
            <span>Capital & Risk Parameters</span>
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            
            {/* Total Trading Capital */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Total Trading Capital (₹)
              </label>
              <input
                type="number"
                name="capital"
                value={formData.capital}
                onChange={handleChange}
                step="1000"
                min="10000"
                className="w-full px-3.5 py-2.5 rounded-xl bg-[#0A0D15] border border-white/[0.08] text-white font-mono text-sm focus:outline-none focus:border-sky-400 focus:ring-1 focus:ring-sky-400/50"
                required
              />
              <span className="text-[10px] text-slate-500 font-mono mt-1 block">
                Default: ₹1,00,000 (Base margin buffer)
              </span>
            </div>

            {/* Risk per Trade */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Risk per Trade 1R (₹)
              </label>
              <input
                type="number"
                name="risk_per_trade"
                value={formData.risk_per_trade}
                onChange={handleChange}
                step="25"
                min="50"
                className="w-full px-3.5 py-2.5 rounded-xl bg-[#0A0D15] border border-white/[0.08] text-white font-mono text-sm focus:outline-none focus:border-sky-400 focus:ring-1 focus:ring-sky-400/50"
                required
              />
              <span className="text-[10px] text-slate-500 font-mono mt-1 block">
                Default: ₹200 (100% margin safe under 6 positions)
              </span>
            </div>

          </div>

          {/* Trading Mode Toggle */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              Trading Execution Mode
            </label>
            <div className="grid grid-cols-2 gap-3 font-mono text-xs">
              <button
                type="button"
                onClick={() => setFormData((p) => ({ ...p, trading_mode: 'PAPER' }))}
                className={`py-3 px-3 rounded-2xl border flex flex-col items-center justify-center transition-all cursor-pointer ${
                  formData.trading_mode === 'PAPER'
                    ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-300 font-black shadow-md shadow-emerald-500/10'
                    : 'bg-[#0A0D15] border-white/[0.08] text-slate-400 hover:text-white'
                }`}
              >
                <span>PAPER TRADING</span>
                <span className="text-[9px] text-slate-400 mt-0.5">Realistic Live Ticks & Friction</span>
              </button>

              <button
                type="button"
                onClick={() => setFormData((p) => ({ ...p, trading_mode: 'LIVE' }))}
                className={`py-3 px-3 rounded-2xl border flex flex-col items-center justify-center transition-all cursor-pointer ${
                  formData.trading_mode === 'LIVE'
                    ? 'bg-amber-500/20 border-amber-500/50 text-amber-300 font-black shadow-md shadow-amber-500/10'
                    : 'bg-[#0A0D15] border-white/[0.08] text-slate-400 hover:text-white'
                }`}
              >
                <span>LIVE DHAN BROKER</span>
                <span className="text-[9px] text-slate-400 mt-0.5">Real Demat Execution</span>
              </button>
            </div>
          </div>
        </div>

        {/* 2. DHAN API CREDENTIALS */}
        <div className="m3-card p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-white flex items-center gap-2">
              <Key className="w-4 h-4 text-sky-400" />
              <span>DhanHQ API Integration</span>
            </h3>
            <button
              type="button"
              onClick={handleTestDhan}
              className="px-3 py-1.5 rounded-xl bg-sky-500/15 border border-sky-500/30 text-sky-300 text-xs font-bold font-mono hover:bg-sky-500/25 transition-all"
            >
              Test Dhan API
            </button>
          </div>

          {dhanStatus && (
            <p className="text-xs font-mono text-sky-300 bg-sky-500/10 p-3 rounded-xl border border-sky-500/20">
              {dhanStatus}
            </p>
          )}

          <div className="space-y-3">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Dhan Client ID
              </label>
              <input
                type="text"
                name="dhan_client_id"
                value={formData.dhan_client_id}
                onChange={handleChange}
                placeholder="e.g. 1000289123"
                className="w-full px-3.5 py-2.5 rounded-xl bg-[#0A0D15] border border-white/[0.08] text-white font-mono text-sm focus:outline-none focus:border-sky-400"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Dhan Access Token (JWT)
              </label>
              <input
                type="password"
                name="dhan_access_token"
                value={formData.dhan_access_token}
                onChange={handleChange}
                placeholder="eyJhbGciOi..."
                className="w-full px-3.5 py-2.5 rounded-xl bg-[#0A0D15] border border-white/[0.08] text-white font-mono text-sm focus:outline-none focus:border-sky-400"
              />
            </div>
          </div>
        </div>

        {/* 3. TELEGRAM BOT NOTIFICATIONS */}
        <div className="m3-card p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-white flex items-center gap-2">
              <Send className="w-4 h-4 text-emerald-400" />
              <span>Telegram Live Alerts</span>
            </h3>
            <button
              type="button"
              onClick={handleTestTelegram}
              className="px-3 py-1.5 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 text-xs font-bold font-mono hover:bg-emerald-500/25 transition-all"
            >
              Send Test Ping
            </button>
          </div>

          {telegramStatus && (
            <p className="text-xs font-mono text-emerald-300 bg-emerald-500/10 p-3 rounded-xl border border-emerald-500/20">
              {telegramStatus}
            </p>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Telegram Bot Token
              </label>
              <input
                type="text"
                name="telegram_token"
                value={formData.telegram_token}
                onChange={handleChange}
                className="w-full px-3.5 py-2.5 rounded-xl bg-[#0A0D15] border border-white/[0.08] text-white font-mono text-xs focus:outline-none focus:border-emerald-400"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Telegram Chat / Account ID
              </label>
              <input
                type="text"
                name="telegram_chat_id"
                value={formData.telegram_chat_id}
                onChange={handleChange}
                className="w-full px-3.5 py-2.5 rounded-xl bg-[#0A0D15] border border-white/[0.08] text-white font-mono text-xs focus:outline-none focus:border-emerald-400"
              />
            </div>
          </div>
        </div>

        {/* SUBMIT BUTTON */}
        <div className="flex justify-end pt-2">
          <button
            type="submit"
            disabled={isLoading}
            className="px-6 py-3 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-slate-950 font-black text-xs font-mono flex items-center gap-2 transition-all shadow-lg shadow-emerald-500/20 cursor-pointer disabled:opacity-50"
          >
            <Save className="w-4 h-4" />
            <span>SAVE CONFIGURATION</span>
          </button>
        </div>

      </form>

      {/* 4. DANGER ZONE: FACTORY RESET */}
      <div className="border border-rose-500/40 rounded-2xl p-5 bg-rose-500/[0.04] space-y-3 mt-6">
        <div className="flex items-center gap-2.5 text-rose-400">
          <AlertTriangle className="w-5 h-5 flex-shrink-0" />
          <h3 className="text-xs font-black font-mono uppercase tracking-wider">
            DANGER ZONE: FACTORY RESET APP
          </h3>
        </div>

        <p className="text-xs text-slate-300 leading-relaxed">
          Resetting will <strong>clear all active open positions</strong>, delete the entire historical trade ledger, and restore your account balance to the default <strong>₹1,00,000 with 0 trades</strong>.
        </p>

        <button
          type="button"
          onClick={() => setShowResetModal(true)}
          className="px-4 py-2.5 rounded-xl bg-rose-500/15 hover:bg-rose-500/25 border border-rose-500/40 text-rose-300 text-xs font-bold font-mono flex items-center gap-2 transition-all cursor-pointer shadow-sm shadow-rose-950/20"
        >
          <Trash2 className="w-4 h-4 text-rose-400" />
          <span>FACTORY RESET APP</span>
        </button>
      </div>

      {/* FACTORY RESET CONFIRMATION MODAL */}
      {showResetModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-md p-4 animate-fade-in">
          <div className="m3-card-elevated border border-rose-500/50 max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <div className="w-12 h-12 rounded-2xl bg-rose-500/20 border border-rose-500/40 flex items-center justify-center text-rose-400">
                <AlertTriangle className="w-6 h-6" />
              </div>
              <button
                type="button"
                onClick={() => setShowResetModal(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div>
              <h3 className="text-base font-black text-white">CONFIRM FACTORY RESET</h3>
              <p className="text-xs text-rose-400 font-mono mt-0.5">Irreversible Destructive Action</p>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              Are you absolutely sure you want to perform a factory reset?
              <br /><br />
              • Permanently purge all trade history and ledger records.
              <br />
              • Close and delete any running positions.
              <br />
              • Reset capital balance to default <strong className="text-white font-mono">₹1,00,000.00</strong>.
            </p>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setShowResetModal(false)}
                className="flex-1 py-2.5 rounded-xl text-xs font-bold text-slate-300 bg-white/5 border border-white/10 hover:bg-white/10 transition-all cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  onResetDangerZone();
                  setShowResetModal(false);
                }}
                className="flex-1 py-2.5 rounded-xl text-xs font-bold text-white bg-rose-600 hover:bg-rose-500 border border-rose-400 shadow-lg shadow-rose-600/30 transition-all cursor-pointer"
              >
                YES, RESET EVERYTHING
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
