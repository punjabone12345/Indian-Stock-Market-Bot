import React, { useState } from 'react';
import { 
  Zap, 
  Power, 
  AlertTriangle, 
  TrendingUp, 
  TrendingDown, 
  Play, 
  Pause, 
  Wallet, 
  Activity, 
  ShieldCheck,
  CheckCircle2,
  X,
  Radio,
  ArrowUpRight,
  ArrowDownRight
} from 'lucide-react';

export default function HeaderBar({ portfolio, nifty, connectionStatus, onToggleBot, onPanicSquareOff }) {
  const [showPanicModal, setShowPanicModal] = useState(false);

  const capital = portfolio?.capital ?? 100000;
  const availMargin = portfolio?.available_margin ?? capital;
  const usedMargin = portfolio?.used_margin ?? 0;
  const totalPnl = portfolio?.total_pnl ?? 0;
  const totalR = portfolio?.total_r ?? 0;
  const botActive = portfolio?.bot_active ?? true;
  const tradingMode = portfolio?.trading_mode ?? 'PAPER';
  const openPositionsCount = portfolio?.open_positions_count ?? Object.keys(portfolio?.positions || {}).length;

  const isPositive = totalPnl >= 0;
  const niftyPrice = nifty?.price ?? 24350.00;
  const niftyChange = nifty?.change ?? 0.00;
  const niftyPct = nifty?.change_pct ?? 0.00;
  const isNiftyUp = niftyChange >= 0;

  // Margin buffer percentage: (Avail / Capital) * 100
  const marginBufferPct = capital > 0 ? Math.min(100, Math.max(0, (availMargin / capital) * 100)) : 100;

  return (
    <>
      <header className="sticky top-0 z-40 w-full glass-panel px-3 sm:px-6 py-2.5 sm:py-3 shadow-2xl transition-all">
        <div className="max-w-7xl mx-auto flex flex-col gap-2.5">
          
          {/* TOP ROW: BRAND LOGO, NIFTY 50 TICKER & ENGINE CONTROLS */}
          <div className="flex items-center justify-between gap-2 sm:gap-4 flex-wrap sm:flex-nowrap">
            
            {/* Left: Terminal Logo & Live Engine Status */}
            <div className="flex items-center gap-2.5 sm:gap-3">
              <div className="w-9 h-9 sm:w-10 sm:h-10 rounded-xl bg-gradient-to-tr from-sky-500/20 via-emerald-500/10 to-indigo-500/20 border border-sky-400/30 flex items-center justify-center shadow-lg shadow-sky-500/10 flex-shrink-0">
                <Zap className="w-4 h-4 sm:w-5 sm:h-5 text-sky-400 fill-sky-400/20" />
              </div>
              <div>
                <div className="flex items-center gap-1.5 leading-none">
                  <span className="text-sm sm:text-base font-black tracking-tight text-white font-mono">
                    ISMB CROWN 6
                  </span>
                  <span className="px-1.5 py-0.5 rounded text-[9px] font-mono font-extrabold bg-sky-500/15 text-sky-300 border border-sky-500/30 uppercase tracking-wider">
                    ALPHA PRO
                  </span>
                </div>
                <div className="flex items-center gap-2 text-[10px] font-mono text-slate-400 mt-1">
                  <span className="flex items-center gap-1 text-emerald-400 font-bold">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 beacon-pulse-emerald" />
                    LIVE 1s
                  </span>
                  <span>•</span>
                  <span className={`px-1.5 py-0.2 rounded font-extrabold text-[9px] ${
                    tradingMode === 'DHAN_LIVE' 
                      ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40' 
                      : 'bg-amber-500/15 text-amber-300 border border-amber-500/30'
                  }`}>
                    {tradingMode}
                  </span>
                  <span className="hidden sm:inline">•</span>
                  <span className="hidden sm:flex items-center gap-1 text-slate-400 text-[10px]">
                    <ShieldCheck className="w-3 h-3 text-sky-400" />
                    3:00 PM Squareoff Active
                  </span>
                </div>
              </div>
            </div>

            {/* Center: Nifty 50 Macro Ticker (Responsive Compact Pill) */}
            <div className="order-3 sm:order-2 w-full sm:w-auto flex items-center justify-between sm:justify-center bg-[#0C111E]/90 px-3 py-1.5 rounded-xl border border-white/[0.08] shadow-inner font-mono text-xs">
              <div className="flex items-center gap-2">
                <span className="text-slate-400 text-[10px] uppercase font-bold tracking-wider">
                  NIFTY 50
                </span>
                <span className="font-extrabold text-white text-xs sm:text-sm tabular-nums tracking-tight">
                  ₹{niftyPrice.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
                <div className={`px-2 py-0.5 rounded-full text-[10px] font-extrabold flex items-center gap-0.5 border ${
                  isNiftyUp 
                    ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' 
                    : 'bg-rose-500/15 text-rose-400 border-rose-500/30'
                }`}>
                  {isNiftyUp ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                  <span>{isNiftyUp ? '+' : ''}{niftyChange.toFixed(2)} ({isNiftyUp ? '+' : ''}{niftyPct.toFixed(2)}%)</span>
                </div>
              </div>
            </div>

            {/* Right: Engine Action Buttons */}
            <div className="order-2 sm:order-3 flex items-center gap-2">
              <button
                onClick={onToggleBot}
                className={`px-3 py-1.5 rounded-xl text-xs font-bold font-mono flex items-center gap-1.5 border transition-all cursor-pointer shadow-md ${
                  botActive 
                    ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/25 glow-emerald' 
                    : 'bg-amber-500/15 border-amber-500/40 text-amber-300 hover:bg-amber-500/25'
                }`}
                title={botActive ? "Pause automated trade scanning" : "Activate automated trading"}
              >
                {botActive ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                <span>{botActive ? 'Active' : 'Paused'}</span>
              </button>

              <button
                onClick={() => setShowPanicModal(true)}
                className="px-3 py-1.5 rounded-xl text-xs font-bold font-mono bg-rose-500/15 border border-rose-500/40 text-rose-300 flex items-center gap-1.5 hover:bg-rose-500/25 transition-all cursor-pointer shadow-md"
                title="Emergency Square Off All Open Positions"
              >
                <Power className="w-3.5 h-3.5 text-rose-400" />
                <span className="hidden xs:inline">Exit All</span>
              </button>
            </div>

          </div>

          {/* ROW 2: BENTO METRICS BAR (AVAILABLE MARGIN & REALIZED P&L) */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 border-t border-white/[0.06] text-xs font-mono">
            
            {/* 1. Available Margin */}
            <div className="bg-[#0D121F]/90 px-3 py-2 rounded-xl border border-white/[0.07] flex flex-col justify-between">
              <div className="flex items-center justify-between text-[10px] text-slate-400">
                <span className="flex items-center gap-1 font-medium">
                  <Wallet className="w-3 h-3 text-sky-400" />
                  Available Cash
                </span>
                <span className="text-emerald-400 font-bold">{marginBufferPct.toFixed(0)}% Free</span>
              </div>
              <div className="mt-1 flex items-baseline justify-between">
                <span className="text-sm sm:text-base font-extrabold text-white tabular-nums tracking-tight">
                  ₹{availMargin.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
              </div>
            </div>

            {/* 2. Total Margin Used / Cap */}
            <div className="bg-[#0D121F]/90 px-3 py-2 rounded-xl border border-white/[0.07] flex flex-col justify-between">
              <div className="flex items-center justify-between text-[10px] text-slate-400">
                <span className="font-medium">Total Capital</span>
                <span className="text-sky-400 font-bold">5x MIS Max</span>
              </div>
              <div className="mt-1 flex items-baseline justify-between">
                <span className="text-sm sm:text-base font-extrabold text-slate-200 tabular-nums tracking-tight">
                  ₹{capital.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
                <span className="text-[10px] text-slate-400 font-medium">
                  Used: ₹{usedMargin.toFixed(0)}
                </span>
              </div>
            </div>

            {/* 3. Realized Daily P&L */}
            <div className="bg-[#0D121F]/90 px-3 py-2 rounded-xl border border-white/[0.07] flex flex-col justify-between">
              <div className="flex items-center justify-between text-[10px] text-slate-400">
                <span className="font-medium">Today's Realized</span>
                {isPositive ? <TrendingUp className="w-3 h-3 text-emerald-400" /> : <TrendingDown className="w-3 h-3 text-rose-400" />}
              </div>
              <div className="mt-1 flex items-baseline justify-between">
                <span className={`text-sm sm:text-base font-extrabold tabular-nums tracking-tight ${
                  isPositive ? 'text-emerald-400' : 'text-rose-400'
                }`}>
                  {isPositive ? '+' : ''}₹{totalPnl.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
                <span className={`text-[10px] font-bold ${isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {isPositive ? '+' : ''}{totalR.toFixed(2)} R
                </span>
              </div>
            </div>

            {/* 4. Active Positions Capacity */}
            <div className="bg-[#0D121F]/90 px-3 py-2 rounded-xl border border-white/[0.07] flex flex-col justify-between">
              <div className="flex items-center justify-between text-[10px] text-slate-400">
                <span className="font-medium">Open Positions</span>
                <span className="text-slate-400 font-bold">{openPositionsCount} / 6 Max</span>
              </div>
              <div className="mt-1 flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  {[...Array(6)].map((_, i) => (
                    <div 
                      key={i} 
                      className={`w-3.5 h-1.5 rounded-sm transition-all ${
                        i < openPositionsCount 
                          ? 'bg-sky-400 shadow-sm shadow-sky-400/50' 
                          : 'bg-white/10'
                      }`}
                    />
                  ))}
                </div>
                <span className="text-[10px] font-mono text-slate-400">
                  {openPositionsCount === 0 ? 'All 6 Idle' : `${openPositionsCount} Live`}
                </span>
              </div>
            </div>

          </div>

        </div>
      </header>

      {/* PANIC SQUARE OFF VERIFICATION MODAL */}
      {showPanicModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
          <div className="bg-[#0D121F] border border-rose-500/40 rounded-2xl max-w-sm w-full p-5 space-y-4 shadow-2xl relative glow-rose">
            <button 
              onClick={() => setShowPanicModal(false)}
              className="absolute top-3 right-3 text-slate-400 hover:text-white cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>

            <div className="w-12 h-12 rounded-2xl bg-rose-500/15 border border-rose-500/30 flex items-center justify-center text-rose-400 mx-auto">
              <AlertTriangle className="w-6 h-6" />
            </div>

            <div className="text-center space-y-1">
              <h3 className="text-base font-black text-white font-mono">
                Emergency Exit All?
              </h3>
              <p className="text-xs text-slate-400 leading-relaxed font-sans">
                This will immediately close all open intraday positions at the current Market Price and cancel all pending orders.
              </p>
            </div>

            <div className="flex items-center gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowPanicModal(false)}
                className="flex-1 py-2.5 rounded-xl border border-white/10 text-xs font-bold font-mono text-slate-300 hover:bg-white/5 transition-all cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowPanicModal(false);
                  onPanicSquareOff();
                }}
                className="flex-1 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-xs font-black font-mono text-white transition-all cursor-pointer shadow-lg shadow-rose-600/40"
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
