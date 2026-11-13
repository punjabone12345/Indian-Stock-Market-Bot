import React, { useState } from 'react';
import { 
  Zap, 
  Power, 
  AlertTriangle, 
  Activity, 
  TrendingUp, 
  TrendingDown, 
  ShieldCheck, 
  Radio, 
  X,
  Play,
  Pause
} from 'lucide-react';

export default function HeaderBar({ portfolio, onToggleBot, onPanicSquareOff }) {
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
      <header className="sticky top-0 z-40 w-full glass-panel border-b border-slate-800/80 px-4 py-2.5 sm:px-6">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center md:justify-between gap-3">
          
          {/* Left: Brand & Engine Live Status */}
          <div className="flex items-center justify-between md:justify-start gap-3">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-emerald-500/30 to-slate-900 border border-emerald-500/40 flex items-center justify-center glow-emerald">
                <Zap className="w-4 h-4 text-emerald-400 fill-emerald-400/30" />
              </div>
              <div>
                <h1 className="text-sm font-bold tracking-tight text-white flex items-center gap-2">
                  <span>ISMB CROWN 6</span>
                  <span className="hidden sm:inline-block px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                    ALPHA
                  </span>
                </h1>
                <div className="flex items-center gap-1.5 text-[10px] font-mono text-slate-400">
                  <span className={`w-1.5 h-1.5 rounded-full ${botActive ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'}`} />
                  <span>{botActive ? 'LIVE MONITORING' : 'BOT PAUSED'}</span>
                  <span className="text-slate-600">•</span>
                  <span className="text-slate-400">{tradingMode} MODE</span>
                </div>
              </div>
            </div>

            {/* Mobile Controls */}
            <div className="flex items-center gap-2 md:hidden">
              <button
                onClick={onToggleBot}
                className={`px-2 py-1 rounded-lg text-xs font-medium flex items-center gap-1 border transition-all ${
                  botActive 
                    ? 'bg-amber-500/10 border-amber-500/30 text-amber-400' 
                    : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                }`}
              >
                {botActive ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
                {botActive ? 'Pause' : 'Resume'}
              </button>

              <button
                onClick={() => setShowPanicModal(true)}
                className="px-2 py-1 rounded-lg text-xs font-semibold bg-rose-500/15 border border-rose-500/40 text-rose-400 flex items-center gap-1 hover:bg-rose-500/25 transition-all"
                title="Emergency Square Off All"
              >
                <Power className="w-3 h-3" />
                <span>Exit All</span>
              </button>
            </div>
          </div>

          {/* Center / Right: Live Financial Matrix (Available, Used Margin, P&L) */}
          <div className="flex items-center justify-between sm:justify-end gap-3 sm:gap-6 pt-2 md:pt-0 border-t border-slate-800/60 md:border-t-0">
            
            {/* Available Margin */}
            <div className="flex flex-col">
              <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400">
                Available Margin
              </span>
              <span className="text-sm sm:text-base font-bold font-mono text-slate-100">
                ₹{availMargin.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>

            {/* Used Margin */}
            <div className="flex flex-col">
              <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400">
                Used Margin (5x)
              </span>
              <span className="text-sm sm:text-base font-bold font-mono text-amber-400/90">
                ₹{usedMargin.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>

            {/* Total P&L (Realized + Unrealized) */}
            <div className="flex flex-col items-end">
              <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 flex items-center gap-1">
                Net Day P&L
                {isPositive ? (
                  <TrendingUp className="w-3 h-3 text-emerald-400" />
                ) : (
                  <TrendingDown className="w-3 h-3 text-rose-400" />
                )}
              </span>
              <div className="flex items-baseline gap-1.5 font-mono">
                <span className={`text-sm sm:text-base font-extrabold ${isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {isPositive ? '+' : ''}₹{totalPnl.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
                <span className={`text-[11px] font-semibold px-1.5 py-0.2 rounded ${
                  isPositive ? 'bg-emerald-500/15 text-emerald-400' : 'bg-rose-500/15 text-rose-400'
                }`}>
                  {isPositive ? '+' : ''}{totalR.toFixed(2)} R
                </span>
              </div>
            </div>

            {/* Desktop Action Buttons */}
            <div className="hidden md:flex items-center gap-2 pl-3 border-l border-slate-800">
              <button
                onClick={onToggleBot}
                className={`p-2 rounded-xl text-xs font-semibold flex items-center gap-1.5 border transition-all ${
                  botActive 
                    ? 'bg-slate-800/80 border-slate-700/80 text-slate-300 hover:bg-slate-700/80' 
                    : 'bg-emerald-500/20 border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/30'
                }`}
                title={botActive ? "Pause Bot Scanner" : "Resume Bot Scanner"}
              >
                {botActive ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                <span className="text-xs">{botActive ? 'Pause' : 'Resume'}</span>
              </button>

              <button
                onClick={() => setShowPanicModal(true)}
                className="px-3 py-2 rounded-xl text-xs font-bold bg-rose-500/15 hover:bg-rose-500/25 border border-rose-500/40 text-rose-400 flex items-center gap-1.5 transition-all shadow-lg shadow-rose-950/30"
              >
                <Power className="w-3.5 h-3.5" />
                <span>Square Off All</span>
              </button>
            </div>

          </div>

        </div>
      </header>

      {/* EMERGENCY KILL SWITCH CONFIRMATION MODAL */}
      {showPanicModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-[#0E121B] border border-rose-500/50 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4 animate-in fade-in zoom-in duration-150">
            <div className="flex items-center gap-3 text-rose-400">
              <div className="p-3 rounded-xl bg-rose-500/20 border border-rose-500/30">
                <AlertTriangle className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-white">EMERGENCY KILL SWITCH</h3>
                <p className="text-xs text-rose-400/90 font-mono">Immediate Market Square-Off</p>
              </div>
            </div>

            <p className="text-sm text-slate-300 leading-relaxed">
              Are you sure you want to trigger the panic exit? This will <strong>immediately close all active open positions</strong> at the current market price and release all locked margins.
            </p>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setShowPanicModal(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700/50 transition-all"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  onPanicSquareOff();
                  setShowPanicModal(false);
                }}
                className="px-4 py-2 rounded-xl text-xs font-bold text-white bg-rose-600 hover:bg-rose-500 transition-all shadow-lg shadow-rose-900/50 flex items-center gap-1.5"
              >
                <Power className="w-4 h-4" />
                <span>CONFIRM EXIT ALL</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
