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
  X,
  Radio
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

  const isPositive = totalPnl >= 0;
  const niftyPrice = nifty?.price ?? 25074.10;
  const niftyChange = nifty?.change ?? -181.00;
  const niftyPct = nifty?.change_pct ?? -0.72;
  const isNiftyUp = niftyChange >= 0;

  return (
    <>
      <header className="sticky top-0 z-40 w-full bg-[#090D16]/95 backdrop-blur-xl border-b border-white/[0.08] px-3.5 py-2.5 shadow-xl">
        <div className="flex flex-col gap-2">
          
          {/* ROW 1: ANDROID APP TITLE, LIVE STATUS & ENGINE CONTROLS */}
          <div className="flex items-center justify-between">
            
            {/* Brand Title */}
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-sky-500/20 to-emerald-500/20 border border-sky-400/40 flex items-center justify-center shadow-md shadow-sky-500/10">
                <Zap className="w-4 h-4 text-sky-400 fill-sky-400/20" />
              </div>
              <div>
                <div className="flex items-center gap-1.5 leading-none">
                  <span className="text-sm font-black tracking-tight text-white font-mono">
                    ISMB CROWN 6
                  </span>
                  <span className="px-1.5 py-0.2 rounded text-[9px] font-mono font-bold bg-sky-500/20 text-sky-300 border border-sky-500/30">
                    ALPHA
                  </span>
                </div>
                <div className="flex items-center gap-1.5 text-[10px] font-mono text-slate-400 mt-1">
                  <span className="flex items-center gap-1 text-emerald-400 font-bold">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    LIVE 1s
                  </span>
                  <span>•</span>
                  <span>{tradingMode} MODE</span>
                </div>
              </div>
            </div>

            {/* Quick Engine Actions */}
            <div className="flex items-center gap-1.5">
              <button
                onClick={onToggleBot}
                className={`px-2.5 py-1 rounded-xl text-[11px] font-bold font-mono flex items-center gap-1 border transition-all cursor-pointer ${
                  botActive 
                    ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/25' 
                    : 'bg-amber-500/15 border-amber-500/40 text-amber-300 hover:bg-amber-500/25'
                }`}
              >
                {botActive ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
                <span>{botActive ? 'Active' : 'Paused'}</span>
              </button>

              <button
                onClick={() => setShowPanicModal(true)}
                className="px-2.5 py-1 rounded-xl text-[11px] font-bold font-mono bg-rose-500/15 border border-rose-500/40 text-rose-300 flex items-center gap-1 hover:bg-rose-500/30 transition-all cursor-pointer"
                title="Emergency Square Off All"
              >
                <Power className="w-3 h-3 text-rose-400" />
                <span>Exit All</span>
              </button>
            </div>

          </div>

          {/* ROW 2: ZERODHA KITE STYLE NIFTY 50 TICKER BAR */}
          <div className="flex items-center justify-between bg-[#111726]/80 px-2.5 py-1.5 rounded-xl border border-white/[0.06] text-[11px] font-mono">
            <div className="flex items-center gap-1.5">
              <span className="text-slate-400 font-bold">NIFTY 50:</span>
              <span className="font-extrabold text-white tabular-nums">
                ₹{niftyPrice.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
              <span className={`flex items-center text-[10px] font-bold ${isNiftyUp ? 'text-emerald-400' : 'text-rose-400'}`}>
                {isNiftyUp ? '+' : ''}{niftyChange.toFixed(2)} ({isNiftyUp ? '+' : ''}{niftyPct.toFixed(2)}%)
              </span>
            </div>
            <span className="text-[10px] text-emerald-400 font-bold hidden xs:inline">
              5x MIS Aligned
            </span>
          </div>

          {/* ROW 3: PERSISTENT MARGIN STRIP (AVAILABLE, USED, DAY P&L) */}
          <div className="grid grid-cols-3 gap-1.5 pt-0.5">
            
            {/* Available Margin */}
            <div className="bg-[#121828]/90 border border-white/[0.06] rounded-xl px-2.5 py-1.5 flex flex-col justify-center">
              <span className="text-[9px] font-mono uppercase text-slate-400 tracking-wider">
                Avail Margin
              </span>
              <span className="text-xs font-black font-mono text-slate-100 tabular-nums">
                ₹{availMargin.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>

            {/* Used Margin (5x) */}
            <div className="bg-[#121828]/90 border border-white/[0.06] rounded-xl px-2.5 py-1.5 flex flex-col justify-center">
              <span className="text-[9px] font-mono uppercase text-slate-400 tracking-wider">
                Used (5x)
              </span>
              <span className="text-xs font-black font-mono text-amber-400 tabular-nums">
                ₹{usedMargin.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>

            {/* Net Day P&L */}
            <div className={`rounded-xl px-2.5 py-1.5 flex flex-col justify-center border transition-all ${
              isPositive 
                ? 'bg-emerald-500/10 border-emerald-500/30' 
                : 'bg-rose-500/10 border-rose-500/30'
            }`}>
              <span className="text-[9px] font-mono uppercase text-slate-400 tracking-wider">
                Net Day P&L
              </span>
              <div className="flex items-baseline gap-1">
                <span className={`text-xs font-black font-mono tabular-nums ${isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {isPositive ? '+' : ''}₹{totalPnl.toFixed(2)}
                </span>
                <span className={`text-[9px] font-mono font-bold ${isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
                  ({isPositive ? '+' : ''}{totalR.toFixed(2)}R)
                </span>
              </div>
            </div>

          </div>

        </div>
      </header>

      {/* PANIC SQUARE-OFF MODAL */}
      {showPanicModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md animate-fade-in">
          <div className="bg-[#101626] border border-rose-500/50 rounded-2xl max-w-sm w-full p-5 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between">
              <div className="w-10 h-10 rounded-xl bg-rose-500/20 border border-rose-500/40 flex items-center justify-center text-rose-400">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <button 
                onClick={() => setShowPanicModal(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div>
              <h3 className="text-base font-black text-white">Emergency Panic Square-Off?</h3>
              <p className="text-xs text-slate-300 mt-1 leading-relaxed">
                Immediately exits all open positions at market price, releases 100% of used margin, and halts automated entries.
              </p>
            </div>

            <div className="flex items-center gap-2.5 pt-2">
              <button
                onClick={() => setShowPanicModal(false)}
                className="flex-1 py-2 rounded-xl text-xs font-bold text-slate-300 bg-white/5 border border-white/10 hover:bg-white/10"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  onPanicSquareOff();
                  setShowPanicModal(false);
                }}
                className="flex-1 py-2 rounded-xl text-xs font-bold text-white bg-rose-600 hover:bg-rose-500 border border-rose-500"
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
