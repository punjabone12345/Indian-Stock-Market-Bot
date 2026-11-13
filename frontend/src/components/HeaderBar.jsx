import React, { useState } from 'react';
import { 
  Zap, 
  Power, 
  AlertTriangle, 
  TrendingUp, 
  TrendingDown, 
  ShieldCheck, 
  Radio, 
  X,
  Play,
  Pause,
  RefreshCw,
  Wallet,
  Activity
} from 'lucide-react';

export default function HeaderBar({ portfolio, connectionStatus, onToggleBot, onPanicSquareOff }) {
  const [showPanicModal, setShowPanicModal] = useState(false);

  const capital = portfolio?.capital ?? 100000;
  const availMargin = portfolio?.available_margin ?? capital;
  const usedMargin = portfolio?.used_margin ?? 0;
  const totalPnl = portfolio?.total_pnl ?? 0;
  const totalR = portfolio?.total_r ?? 0;
  const botActive = portfolio?.bot_active ?? true;
  const tradingMode = portfolio?.trading_mode ?? 'PAPER';

  const isPositive = totalPnl >= 0;

  return (
    <>
      <header className="sticky top-0 z-40 w-full m3-dock border-b border-white/[0.08] px-3 sm:px-6 py-2.5 shadow-2xl">
        <div className="max-w-7xl mx-auto flex flex-col gap-2.5">
          
          {/* TOP ROW: BRANDING, STATUS & GLOBAL CONTROLS */}
          <div className="flex items-center justify-between">
            
            {/* Brand Logo & Info */}
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-2xl bg-gradient-to-tr from-sky-500/20 via-slate-900 to-emerald-500/20 border border-sky-400/30 flex items-center justify-center shadow-lg shadow-sky-500/10">
                <Zap className="w-5 h-5 text-sky-400 fill-sky-400/20 animate-pulse" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-sm sm:text-base font-extrabold tracking-tight text-white flex items-center gap-1.5">
                    <span>ISMB</span>
                    <span className="bg-gradient-to-r from-sky-400 via-teal-300 to-emerald-400 bg-clip-text text-transparent">
                      CROWN 6
                    </span>
                  </h1>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-sky-500/15 text-sky-300 border border-sky-500/30">
                    ALPHA
                  </span>
                  <span className="hidden sm:inline-flex px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-white/[0.06] text-slate-300 border border-white/10">
                    5x MIS CASH
                  </span>
                </div>
                <div className="flex items-center gap-2 text-[10px] font-mono text-slate-400">
                  <span className="flex items-center gap-1 text-emerald-400">
                    <span className={`w-1.5 h-1.5 rounded-full ${connectionStatus === 'CONNECTED' ? 'bg-emerald-400 animate-ping' : 'bg-amber-400'}`} />
                    {connectionStatus === 'CONNECTED' ? 'NSE LIVE 1s' : 'SYNCING...'}
                  </span>
                  <span>•</span>
                  <span className="text-slate-300">{tradingMode} MODE</span>
                </div>
              </div>
            </div>

            {/* Top Right: Engine Toggle & Panic Button */}
            <div className="flex items-center gap-2">
              <button
                onClick={onToggleBot}
                className={`px-3 py-1.5 rounded-xl text-xs font-bold font-mono flex items-center gap-1.5 border transition-all ${
                  botActive 
                    ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/25 shadow-sm shadow-emerald-500/20' 
                    : 'bg-amber-500/15 border-amber-500/40 text-amber-300 hover:bg-amber-500/25'
                }`}
              >
                {botActive ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                <span className="hidden sm:inline">{botActive ? 'ENGINE RUNNING' : 'ENGINE PAUSED'}</span>
                <span className="sm:hidden">{botActive ? 'Active' : 'Paused'}</span>
              </button>

              <button
                onClick={() => setShowPanicModal(true)}
                className="px-3 py-1.5 rounded-xl text-xs font-bold font-mono bg-rose-500/15 border border-rose-500/40 text-rose-300 flex items-center gap-1.5 hover:bg-rose-500/30 transition-all shadow-sm shadow-rose-500/20"
                title="Emergency Square Off All Positions"
              >
                <Power className="w-3.5 h-3.5 text-rose-400" />
                <span>Exit All</span>
              </button>
            </div>

          </div>

          {/* PERSISTENT FINANCIAL STRIP: AVAILABLE MARGIN, USED MARGIN, NET P&L */}
          <div className="grid grid-cols-3 gap-2 pt-2 border-t border-white/[0.06]">
            
            {/* Card 1: Available Margin */}
            <div className="bg-[#121724]/90 border border-white/[0.07] rounded-xl px-3 py-1.5 flex flex-col justify-center">
              <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 flex items-center gap-1">
                <Wallet className="w-3 h-3 text-sky-400 hidden xs:inline" />
                Available Margin
              </span>
              <span className="text-xs sm:text-sm font-extrabold font-mono text-slate-100 tabular-nums">
                ₹{availMargin.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>

            {/* Card 2: Used Margin (5x) */}
            <div className="bg-[#121724]/90 border border-white/[0.07] rounded-xl px-3 py-1.5 flex flex-col justify-center">
              <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 flex items-center gap-1">
                <Activity className="w-3 h-3 text-amber-400 hidden xs:inline" />
                Used (5x MIS)
              </span>
              <span className="text-xs sm:text-sm font-extrabold font-mono text-amber-400/95 tabular-nums">
                ₹{usedMargin.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>

            {/* Card 3: Net Day P&L */}
            <div className={`rounded-xl px-3 py-1.5 flex flex-col justify-center border transition-all ${
              isPositive 
                ? 'bg-emerald-500/10 border-emerald-500/30' 
                : 'bg-rose-500/10 border-rose-500/30'
            }`}>
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 flex items-center gap-1">
                  Net Day P&L
                </span>
                {isPositive ? (
                  <TrendingUp className="w-3 h-3 text-emerald-400" />
                ) : (
                  <TrendingDown className="w-3 h-3 text-rose-400" />
                )}
              </div>
              <div className="flex items-baseline gap-1.5 flex-wrap">
                <span className={`text-xs sm:text-sm font-extrabold font-mono tabular-nums ${
                  isPositive ? 'text-emerald-400' : 'text-rose-400'
                }`}>
                  {isPositive ? '+' : ''}₹{totalPnl.toFixed(2)}
                </span>
                <span className={`text-[10px] font-mono font-bold ${
                  isPositive ? 'text-emerald-300/80' : 'text-rose-300/80'
                }`}>
                  ({isPositive ? '+' : ''}{totalR.toFixed(2)}R)
                </span>
              </div>
            </div>

          </div>

        </div>
      </header>

      {/* EMERGENCY KILL SWITCH CONFIRMATION MODAL */}
      {showPanicModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in">
          <div className="m3-card-elevated max-w-md w-full p-6 border border-rose-500/40 space-y-4">
            <div className="flex items-center justify-between">
              <div className="w-12 h-12 rounded-2xl bg-rose-500/20 border border-rose-500/40 flex items-center justify-center">
                <AlertTriangle className="w-6 h-6 text-rose-400" />
              </div>
              <button
                onClick={() => setShowPanicModal(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-white/10"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div>
              <h3 className="text-lg font-black text-white">Emergency Panic Square-Off?</h3>
              <p className="text-xs text-slate-300 mt-1.5 leading-relaxed">
                This will immediately exit <strong>ALL</strong> open positions across the Crown 6 portfolio at current market price, release 100% of used margin, record final P&L into the analytics ledger, and halt the automated strategy engine.
              </p>
            </div>

            <div className="bg-rose-500/10 border border-rose-500/20 rounded-xl p-3 text-[11px] font-mono text-rose-300 flex items-center gap-2">
              <Power className="w-4 h-4 shrink-0 text-rose-400" />
              <span>Safety Protocol: Dhan & Paper Broker Execution will be executed instantly.</span>
            </div>

            <div className="flex items-center gap-3 pt-2">
              <button
                onClick={() => setShowPanicModal(false)}
                className="flex-1 py-2.5 rounded-xl text-xs font-bold text-slate-300 bg-white/5 border border-white/10 hover:bg-white/10 transition-all"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  onPanicSquareOff();
                  setShowPanicModal(false);
                }}
                className="flex-1 py-2.5 rounded-xl text-xs font-bold text-white bg-rose-600 hover:bg-rose-500 border border-rose-400 shadow-lg shadow-rose-600/30 transition-all"
              >
                Confirm Exit All
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
