import React, { useState } from 'react';
import { 
  DollarSign, 
  Key, 
  Send, 
  AlertTriangle, 
  Save, 
  CheckCircle2, 
  Trash2,
  X,
  Shield,
  Radio,
  Eye,
  EyeOff,
  Cpu,
  Clock,
  Activity,
  Layers,
  TrendingDown
} from 'lucide-react';

export default function SettingsTab({ 
  settings, 
  onSaveSettings, 
  onResetDangerZone, 
  onTestTelegram, 
  onSendMorningAlert,
  onTestDhan 
}) {
  const [formData, setFormData] = useState({
    capital: settings?.capital || 100000,
    risk_per_trade: settings?.risk_per_trade || 6210,
    target_rr: settings?.target_rr || 4.0,
    max_open_positions: settings?.max_open_positions || 1,
    trading_mode: settings?.trading_mode || 'PAPER',
    dhan_client_id: settings?.dhan_client_id || '',
    dhan_access_token: settings?.dhan_access_token || '',
    telegram_token: settings?.telegram_token || '9230981995:AAHm8Pa65hwSHvH1N89qLwWzdEZDXKEVdWc',
    telegram_chat_id: settings?.telegram_chat_id || '5582938659'
  });

  const [showToken, setShowToken] = useState(false);
  const [showResetModal, setShowResetModal] = useState(false);
  const [saveStatus, setSaveStatus] = useState('');
  const [telegramStatus, setTelegramStatus] = useState('');
  const [morningStatus, setMorningStatus] = useState('');
  const [dhanStatus, setDhanStatus] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const govMode = settings?.governor_mode || 'NORMAL';
  const govMult = settings?.governor_multiplier || 1.0;
  const currDD = settings?.current_drawdown_r || 0.0;
  const effRisk = settings?.effective_risk || formData.risk_per_trade;

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
    setTelegramStatus('Delivering test message to Telegram...');
    try {
      const res = await onTestTelegram();
      setTelegramStatus(res?.message || 'Telegram alert delivered successfully!');
      setTimeout(() => setTelegramStatus(''), 5000);
    } catch (err) {
      setTelegramStatus('Failed to send Telegram alert.');
    }
  };

  const handleTestMorningAlert = async () => {
    setMorningStatus('Dispatching 09:00 AM Morning Market Readiness Alert...');
    try {
      const res = await onSendMorningAlert();
      setMorningStatus(res?.message || '09:00 AM Alert delivered successfully to your Telegram!');
      setTimeout(() => setMorningStatus(''), 6000);
    } catch (err) {
      setMorningStatus('Failed to send 09:00 AM morning readiness alert.');
    }
  };

  const handleTestDhan = async () => {
    setDhanStatus('Authenticating with Dhan API servers...');
    try {
      const res = await onTestDhan(formData.dhan_client_id, formData.dhan_access_token);
      setDhanStatus(res?.message || 'Dhan API Verified Successfully!');
      setTimeout(() => setDhanStatus(''), 5000);
    } catch (err) {
      setDhanStatus('Dhan API verification error.');
    }
  };

  return (
    <div className="space-y-4 pb-12 max-w-3xl mx-auto">
      
      {/* SECTION HEADER */}
      <div className="flex items-center justify-between px-1 pt-1 pb-2 border-b border-white/[0.08]">
        <div>
          <h2 className="text-xs sm:text-sm font-black tracking-tight text-white font-mono uppercase">
            Broker & Risk Command Center
          </h2>
        </div>
        <span className="text-[10px] font-mono text-slate-400 bg-[#0D121F] px-2.5 py-1 rounded-lg border border-white/10">
          Velocity Leader 4.0R Config
        </span>
      </div>

      {saveStatus && (
        <div className="p-3.5 rounded-xl bg-emerald-500/15 border border-emerald-500/40 text-emerald-300 text-xs font-mono font-bold flex items-center gap-2.5 glow-emerald">
          <CheckCircle2 className="w-4 h-4 flex-shrink-0 text-emerald-400" />
          <span>{saveStatus}</span>
        </div>
      )}

      {/* DYNAMIC RISK GOVERNOR LIVE DASHBOARD PILL */}
      <div className="bento-card p-4 space-y-3 bg-gradient-to-r from-sky-500/[0.04] to-emerald-500/[0.04] border border-sky-500/20">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-black uppercase tracking-wider text-sky-400 flex items-center gap-2">
            <Shield className="w-4 h-4 text-sky-400" />
            <span>Dynamic Risk Governor (Max DD &lt; 40 R Protection)</span>
          </h3>
          <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-mono font-black border ${
            govMode === 'DEFENSIVE' 
              ? 'bg-amber-500/20 text-amber-300 border-amber-500/50 animate-pulse' 
              : 'bg-emerald-500/20 text-emerald-300 border-emerald-500/50'
          }`}>
            {govMode} MODE ({govMult}x)
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs font-mono">
          <div className="bg-[#0A0E1A] p-2.5 rounded-xl border border-white/5">
            <div className="text-[10px] text-slate-400">Current Drawdown</div>
            <div className={`text-sm font-black mt-1 ${currDD < 0 ? 'text-amber-400' : 'text-emerald-400'}`}>
              {currDD.toFixed(2)} R
            </div>
          </div>
          <div className="bg-[#0A0E1A] p-2.5 rounded-xl border border-white/5">
            <div className="text-[10px] text-slate-400">Base Risk (1.0R)</div>
            <div className="text-sm font-black text-white mt-1">₹{formData.risk_per_trade}</div>
          </div>
          <div className="bg-[#0A0E1A] p-2.5 rounded-xl border border-white/5">
            <div className="text-[10px] text-slate-400">Effective Active Risk</div>
            <div className="text-sm font-black text-emerald-400 mt-1">₹{effRisk}</div>
          </div>
          <div className="bg-[#0A0E1A] p-2.5 rounded-xl border border-white/5">
            <div className="text-[10px] text-slate-400">Auto EOD Square-Off</div>
            <div className="text-sm font-black text-sky-400 mt-1">15:00 IST</div>
          </div>
        </div>

        <div className="text-[10px] text-slate-400 font-sans leading-relaxed pt-1 border-t border-white/5">
          <p>
            • <strong>Drawdown Defense:</strong> If drawdown crosses <strong>-15 R</strong>, sizing automatically cuts in half to <strong>0.5R (₹{effRisk})</strong> until recovery to -5 R.
            <br />
            • <strong>Commission Protection:</strong> Enforces strict <strong>0.50% SL floor</strong> to cap broker turnover fees to ~₹42 or less per trade.
          </p>
        </div>
      </div>

      <form onSubmit={handleSave} className="space-y-4 font-mono text-xs">
        
        {/* 1. CAPITAL & RISK PARAMETERS */}
        <div className="bento-card p-4 space-y-3.5">
          <h3 className="text-xs font-black uppercase tracking-wider text-white flex items-center gap-2">
            <DollarSign className="w-4 h-4 text-emerald-400" />
            <span>Capital Sizing & Fixed Fractional Risk</span>
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="block text-[11px] text-slate-400 font-medium mb-1">
                Account Starting Capital (₹)
              </label>
              <input
                type="number"
                name="capital"
                value={formData.capital}
                onChange={handleChange}
                className="w-full bg-[#0A0E1A] border border-white/10 rounded-xl px-3.5 py-2.5 text-white font-bold text-sm focus:border-sky-500 focus:outline-none tabular-nums"
                required
              />
              <span className="text-[9px] text-slate-500 mt-1 block">Baseline equity for position sizing</span>
            </div>

            <div>
              <label className="block text-[11px] text-slate-400 font-medium mb-1">
                Risk Per Trade (1R in ₹)
              </label>
              <input
                type="number"
                name="risk_per_trade"
                value={formData.risk_per_trade}
                onChange={handleChange}
                className="w-full bg-[#0A0E1A] border border-white/10 rounded-xl px-3.5 py-2.5 text-white font-bold text-sm focus:border-sky-500 focus:outline-none tabular-nums"
                required
              />
              <span className="text-[9px] text-emerald-400 mt-1 block">
                Standard 1.0R baseline = ₹{formData.risk_per_trade}
              </span>
            </div>

            <div>
              <label className="block text-[11px] text-slate-400 font-medium mb-1">
                Target Risk-Reward Ratio
              </label>
              <input
                type="number"
                step="0.1"
                name="target_rr"
                value={formData.target_rr}
                onChange={handleChange}
                className="w-full bg-[#0A0E1A] border border-white/10 rounded-xl px-3.5 py-2.5 text-white font-bold text-sm focus:border-sky-500 focus:outline-none tabular-nums"
                required
              />
              <span className="text-[9px] text-sky-400 mt-1 block">
                1:{formData.target_rr} RRR (Velocity Compounder: 1:4.0)
              </span>
            </div>
          </div>
        </div>

        {/* 2. TRADING EXECUTION MODE */}
        <div className="bento-card p-4 space-y-3">
          <h3 className="text-xs font-black uppercase tracking-wider text-white flex items-center gap-2">
            <Cpu className="w-4 h-4 text-sky-400" />
            <span>Execution Environment</span>
          </h3>

          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => setFormData(prev => ({ ...prev, trading_mode: 'PAPER' }))}
              className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${
                formData.trading_mode === 'PAPER'
                  ? 'bg-amber-500/15 border-amber-500/50 text-white shadow-md'
                  : 'bg-[#0A0E1A] border-white/10 text-slate-400 hover:border-white/20'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-black text-sm">PAPER SIMULATION</span>
                <span className={`w-2 h-2 rounded-full ${formData.trading_mode === 'PAPER' ? 'bg-amber-400 animate-pulse' : 'bg-slate-700'}`} />
              </div>
              <p className="text-[10px] text-slate-400 font-sans leading-relaxed">
                Executes orders in memory without risking real cash. Full mathematical simulator with exact Zerodha/Dhan charges.
              </p>
            </button>

            <button
              type="button"
              onClick={() => setFormData(prev => ({ ...prev, trading_mode: 'DHAN_LIVE' }))}
              className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${
                formData.trading_mode === 'DHAN_LIVE'
                  ? 'bg-emerald-500/15 border-emerald-500/50 text-white shadow-md glow-emerald'
                  : 'bg-[#0A0E1A] border-white/10 text-slate-400 hover:border-white/20'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-black text-sm text-emerald-400">DHAN LIVE API</span>
                <span className={`w-2 h-2 rounded-full ${formData.trading_mode === 'DHAN_LIVE' ? 'bg-emerald-400 beacon-pulse-emerald' : 'bg-slate-700'}`} />
              </div>
              <p className="text-[10px] text-slate-400 font-sans leading-relaxed">
                Places real MIS orders on your Dhan trading account via authenticated SuperFast API.
              </p>
            </button>
          </div>
        </div>

        {/* 3. DHAN BROKER CREDENTIALS */}
        <div className="bento-card p-4 space-y-3.5">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-black uppercase tracking-wider text-white flex items-center gap-2">
              <Key className="w-4 h-4 text-sky-400" />
              <span>Dhan HQ API Credentials</span>
            </h3>

            <button
              type="button"
              onClick={handleTestDhan}
              className="px-2.5 py-1 rounded-lg bg-sky-500/15 hover:bg-sky-500/25 border border-sky-500/40 text-sky-300 text-[10px] font-bold transition-all cursor-pointer"
            >
              Test Dhan Link
            </button>
          </div>

          {dhanStatus && (
            <div className="p-2.5 rounded-lg bg-sky-500/10 border border-sky-500/30 text-sky-300 text-[11px]">
              {dhanStatus}
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-[11px] text-slate-400 font-medium mb-1">
                Dhan Client ID
              </label>
              <input
                type="text"
                name="dhan_client_id"
                value={formData.dhan_client_id}
                onChange={handleChange}
                placeholder="e.g. 1000123456"
                className="w-full bg-[#0A0E1A] border border-white/10 rounded-xl px-3.5 py-2.5 text-white font-mono text-xs focus:border-sky-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-[11px] text-slate-400 font-medium mb-1">
                Dhan JWT Access Token
              </label>
              <div className="relative">
                <input
                  type={showToken ? "text" : "password"}
                  name="dhan_access_token"
                  value={formData.dhan_access_token}
                  onChange={handleChange}
                  placeholder="Paste your 24-hour Dhan Access Token"
                  className="w-full bg-[#0A0E1A] border border-white/10 rounded-xl px-3.5 py-2.5 pr-10 text-white font-mono text-xs focus:border-sky-500 focus:outline-none"
                />
                <button
                  type="button"
                  onClick={() => setShowToken(!showToken)}
                  className="absolute right-3 top-2.5 text-slate-400 hover:text-white cursor-pointer"
                >
                  {showToken ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* 4. TELEGRAM ALERTS & 09:00 AM MORNING READINESS */}
        <div className="bento-card p-4 space-y-3.5">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h3 className="text-xs font-black uppercase tracking-wider text-white flex items-center gap-2">
              <Send className="w-4 h-4 text-emerald-400" />
              <span>Telegram Real-Time Dispatcher & 09:00 AM Alert</span>
            </h3>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleTestMorningAlert}
                className="px-2.5 py-1 rounded-lg bg-sky-500/15 hover:bg-sky-500/25 border border-sky-500/40 text-sky-300 text-[10px] font-bold transition-all cursor-pointer flex items-center gap-1"
                title="Send the 09:00 AM morning market readiness message to Telegram now"
              >
                <Clock className="w-3 h-3 text-sky-400" />
                <span>Test 9 AM Alert</span>
              </button>
              <button
                type="button"
                onClick={handleTestTelegram}
                className="px-2.5 py-1 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/40 text-emerald-300 text-[10px] font-bold transition-all cursor-pointer"
              >
                Send Test Alert
              </button>
            </div>
          </div>

          {morningStatus && (
            <div className="p-2.5 rounded-lg bg-sky-500/10 border border-sky-500/30 text-sky-300 text-[11px] flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-sky-400 flex-shrink-0" />
              <span>{morningStatus}</span>
            </div>
          )}

          {telegramStatus && (
            <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-[11px] flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
              <span>{telegramStatus}</span>
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-[11px] text-slate-400 font-medium mb-1">
                Telegram Bot Token
              </label>
              <input
                type="text"
                name="telegram_token"
                value={formData.telegram_token}
                onChange={handleChange}
                className="w-full bg-[#0A0E1A] border border-white/10 rounded-xl px-3.5 py-2.5 text-white font-mono text-xs focus:border-sky-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-[11px] text-slate-400 font-medium mb-1">
                Telegram Chat ID
              </label>
              <input
                type="text"
                name="telegram_chat_id"
                value={formData.telegram_chat_id}
                onChange={handleChange}
                className="w-full bg-[#0A0E1A] border border-white/10 rounded-xl px-3.5 py-2.5 text-white font-mono text-xs focus:border-sky-500 focus:outline-none"
              />
            </div>
          </div>

          <div className="text-[10px] text-slate-400 bg-[#0A0E1A] p-2.5 rounded-xl border border-white/5 flex items-center gap-2">
            <Clock className="w-3.5 h-3.5 text-sky-400 flex-shrink-0" />
            <span>Automatic 09:00 AM IST Market Readiness alert is scheduled on every weekday trading morning!</span>
          </div>
        </div>

        {/* SUBMIT BUTTON */}
        <div className="pt-2">
          <button
            type="submit"
            disabled={isLoading}
            className="w-full py-3 rounded-xl bg-gradient-to-r from-sky-500 to-emerald-500 hover:from-sky-400 hover:to-emerald-400 text-slate-950 font-black text-sm uppercase tracking-wider flex items-center justify-center gap-2 transition-all cursor-pointer shadow-lg shadow-sky-500/20"
          >
            <Save className="w-4 h-4" />
            <span>{isLoading ? 'Saving Changes...' : 'Save Configuration to Database'}</span>
          </button>
        </div>

        {/* 5. DANGER ZONE */}
        <div className="bento-card p-4 border border-rose-500/30 bg-rose-500/[0.03] space-y-3 mt-6">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-black uppercase tracking-wider text-rose-400 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4" />
              <span>Danger Zone: Factory Database Reset</span>
            </h3>

            <button
              type="button"
              onClick={() => setShowResetModal(true)}
              className="px-3 py-1.5 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 border border-rose-500/50 text-rose-300 text-xs font-bold transition-all cursor-pointer"
            >
              Reset Data
            </button>
          </div>
          <p className="text-[11px] text-slate-400 font-sans leading-relaxed">
            Purges all closed trade records and active positions from database, restoring starting capital to ₹1,00,000.
          </p>
        </div>

      </form>

      {/* DANGER ZONE CONFIRMATION MODAL */}
      {showResetModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
          <div className="bg-[#0D121F] border border-rose-500/40 rounded-2xl max-w-sm w-full p-5 space-y-4 shadow-2xl relative glow-rose">
            <div className="w-12 h-12 rounded-2xl bg-rose-500/15 border border-rose-500/30 flex items-center justify-center text-rose-400 mx-auto">
              <Trash2 className="w-6 h-6" />
            </div>
            <div className="text-center space-y-1">
              <h3 className="text-base font-black text-white font-mono">Factory Reset Database?</h3>
              <p className="text-xs text-slate-400 font-sans leading-relaxed">
                This action is permanent and cannot be undone. All trade ledger entries will be erased.
              </p>
            </div>
            <div className="flex items-center gap-2 pt-2 font-mono text-xs">
              <button
                onClick={() => setShowResetModal(false)}
                className="flex-1 py-2.5 rounded-xl border border-white/10 text-slate-300 hover:bg-white/5 transition-all cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  setShowResetModal(false);
                  onResetDangerZone();
                }}
                className="flex-1 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-black transition-all cursor-pointer shadow-lg shadow-rose-600/40"
              >
                Confirm Reset
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
