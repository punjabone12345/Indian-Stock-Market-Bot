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
  DollarSign
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
    <div className="space-y-6 pb-24 max-w-4xl mx-auto px-4 sm:px-6 pt-4">
      
      {/* SECTION HEADER */}
      <div>
        <h2 className="text-lg font-extrabold tracking-tight text-white flex items-center gap-2">
          <span>SYSTEM & BROKER SETTINGS</span>
          <span className="px-2 py-0.5 text-[10px] font-mono font-bold bg-slate-800 text-slate-300 rounded-full border border-slate-700">
            Control Center
          </span>
        </h2>
        <p className="text-xs text-slate-400">
          Configure capital, risk per trade, Dhan API credentials, and live Telegram push notifications.
        </p>
      </div>

      {saveStatus && (
        <div className="p-3.5 rounded-xl bg-emerald-500/15 border border-emerald-500/40 text-emerald-400 text-xs font-semibold flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
          <span>{saveStatus}</span>
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-6">
        
        {/* 1. CAPITAL & RISK SIZING */}
        <div className="glass-card p-5 space-y-4">
          <h3 className="text-sm font-bold font-mono uppercase tracking-wider text-white flex items-center gap-2">
            <DollarSign className="w-4 h-4 text-emerald-400" />
            <span>Capital & Risk Parameters</span>
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            
            {/* Total Trading Capital */}
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                Total Trading Capital (₹)
              </label>
              <input
                type="number"
                name="capital"
                value={formData.capital}
                onChange={handleChange}
                step="1000"
                min="10000"
                className="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-white font-mono text-sm focus:outline-none focus:border-emerald-500"
                required
              />
              <span className="text-[10px] text-slate-400 mt-1 block">
                Default: ₹1,00,000 (Margin buffer base)
              </span>
            </div>

            {/* Risk per Trade */}
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                Risk per Trade 1R (₹)
              </label>
              <input
                type="number"
                name="risk_per_trade"
                value={formData.risk_per_trade}
                onChange={handleChange}
                step="25"
                min="50"
                className="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-white font-mono text-sm focus:outline-none focus:border-emerald-500"
                required
              />
              <span className="text-[10px] text-slate-400 mt-1 block">
                Default: ₹200 (100% margin safe under 6 positions)
              </span>
            </div>

          </div>

          {/* Trading Mode Toggle */}
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">
              Trading Execution Mode
            </label>
            <div className="grid grid-cols-2 gap-3 font-mono text-xs">
              <button
                type="button"
                onClick={() => setFormData((p) => ({ ...p, trading_mode: 'PAPER' }))}
                className={`py-2.5 px-3 rounded-xl border flex flex-col items-center justify-center transition-all ${
                  formData.trading_mode === 'PAPER'
                    ? 'bg-emerald-500/20 border-emerald-500 text-emerald-400 font-bold'
                    : 'bg-slate-900 border-slate-800 text-slate-400'
                }`}
              >
                <span>PAPER TRADING</span>
                <span className="text-[9px] text-slate-400 mt-0.5">Realistic Live Ticks & Friction</span>
              </button>

              <button
                type="button"
                onClick={() => setFormData((p) => ({ ...p, trading_mode: 'LIVE' }))}
                className={`py-2.5 px-3 rounded-xl border flex flex-col items-center justify-center transition-all ${
                  formData.trading_mode === 'LIVE'
                    ? 'bg-amber-500/20 border-amber-500 text-amber-400 font-bold'
                    : 'bg-slate-900 border-slate-800 text-slate-400'
                }`}
              >
                <span>LIVE DHAN BROKER</span>
                <span className="text-[9px] text-slate-400 mt-0.5">Real Demat Execution</span>
              </button>
            </div>
          </div>
        </div>

        {/* 2. DHAN API CREDENTIALS */}
        <div className="glass-card p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold font-mono uppercase tracking-wider text-white flex items-center gap-2">
              <Key className="w-4 h-4 text-sky-400" />
              <span>DhanHQ API Integration</span>
            </h3>
            <button
              type="button"
              onClick={handleTestDhan}
              className="px-2.5 py-1 rounded-lg bg-sky-500/15 border border-sky-500/30 text-sky-400 text-xs font-semibold hover:bg-sky-500/25 transition-all"
            >
              Test Dhan API
            </button>
          </div>

          {dhanStatus && (
            <p className="text-xs font-mono text-sky-400 bg-sky-500/10 p-2.5 rounded-lg border border-sky-500/20">
              {dhanStatus}
            </p>
          )}

          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                Dhan Client ID
              </label>
              <input
                type="text"
                name="dhan_client_id"
                value={formData.dhan_client_id}
                onChange={handleChange}
                placeholder="e.g. 1000289123"
                className="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-white font-mono text-sm focus:outline-none focus:border-sky-500"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                Dhan Access Token
              </label>
              <input
                type="password"
                name="dhan_access_token"
                value={formData.dhan_access_token}
                onChange={handleChange}
                placeholder="eyJhbGciOi..."
                className="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-white font-mono text-sm focus:outline-none focus:border-sky-500"
              />
            </div>
          </div>
        </div>

        {/* 3. TELEGRAM BOT NOTIFICATIONS */}
        <div className="glass-card p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold font-mono uppercase tracking-wider text-white flex items-center gap-2">
              <Send className="w-4 h-4 text-emerald-400" />
              <span>Telegram Live Alerts</span>
            </h3>
            <button
              type="button"
              onClick={handleTestTelegram}
              className="px-2.5 py-1 rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 text-xs font-semibold hover:bg-emerald-500/25 transition-all"
            >
              Send Test Ping
            </button>
          </div>

          {telegramStatus && (
            <p className="text-xs font-mono text-emerald-400 bg-emerald-500/10 p-2.5 rounded-lg border border-emerald-500/20">
              {telegramStatus}
            </p>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                Telegram Bot Token
              </label>
              <input
                type="text"
                name="telegram_token"
                value={formData.telegram_token}
                onChange={handleChange}
                className="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-white font-mono text-xs focus:outline-none focus:border-emerald-500"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                Telegram Chat / Account ID
              </label>
              <input
                type="text"
                name="telegram_chat_id"
                value={formData.telegram_chat_id}
                onChange={handleChange}
                className="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-white font-mono text-xs focus:outline-none focus:border-emerald-500"
              />
            </div>
          </div>
        </div>

        {/* SUBMIT BUTTON */}
        <div className="flex justify-end">
          <button
            type="submit"
            disabled={isLoading}
            className="px-6 py-3 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-black text-xs font-extrabold flex items-center gap-2 transition-all shadow-lg shadow-emerald-500/25 disabled:opacity-50"
          >
            <Save className="w-4 h-4" />
            <span>SAVE SETTINGS</span>
          </button>
        </div>

      </form>

      {/* 4. DANGER ZONE: FACTORY RESET */}
      <div className="border border-rose-500/40 rounded-2xl p-5 bg-rose-500/5 space-y-3">
        <div className="flex items-center gap-2.5 text-rose-400">
          <AlertTriangle className="w-5 h-5 flex-shrink-0" />
          <h3 className="text-sm font-extrabold font-mono uppercase tracking-wider">
            DANGER ZONE: FACTORY RESET APP
          </h3>
        </div>

        <p className="text-xs text-slate-300 leading-relaxed">
          Resetting will <strong>clear all active open positions</strong>, delete the entire historical trade ledger, and reset your account balance to the default <strong>₹1,00,000 with 0 trades</strong>.
        </p>

        <button
          type="button"
          onClick={() => setShowResetModal(true)}
          className="px-4 py-2 rounded-xl bg-rose-500/20 hover:bg-rose-500/30 border border-rose-500/40 text-rose-400 text-xs font-bold flex items-center gap-2 transition-all"
        >
          <Trash2 className="w-4 h-4" />
          <span>FACTORY RESET APP</span>
        </button>
      </div>

      {/* FACTORY RESET CONFIRMATION MODAL */}
      {showResetModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-sm p-4">
          <div className="bg-[#0E121B] border border-rose-500 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3 text-rose-400">
              <div className="p-3 rounded-xl bg-rose-500/20 border border-rose-500/30">
                <AlertTriangle className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">CONFIRM FACTORY RESET</h3>
                <p className="text-xs text-rose-400 font-mono">Irreversible Action</p>
              </div>
            </div>

            <p className="text-sm text-slate-300 leading-relaxed">
              Are you absolutely sure? This will:
              <br /><br />
              • Permanently delete all trade history and positions.
              <br />
              • Reset capital to <strong className="text-white">₹1,00,000</strong>.
              <br />
              • Restore a fresh 0-trade ledger.
            </p>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setShowResetModal(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white bg-slate-800 border border-slate-700"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  onResetDangerZone();
                  setShowResetModal(false);
                }}
                className="px-4 py-2 rounded-xl text-xs font-bold text-white bg-rose-600 hover:bg-rose-500 transition-all shadow-lg shadow-rose-900/50"
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
