import React, { useState } from 'react';
import { 
  TrendingUp, 
  TrendingDown, 
  Crosshair, 
  BarChart2, 
  Sparkles, 
  ArrowUpRight, 
  ArrowDownRight,
  ChevronDown,
  ChevronUp,
  Activity,
  Zap,
  Info
} from 'lucide-react';

export default function DashboardTab({ dashboardData, onOpenChart }) {
  const instruments = dashboardData?.instruments || [];
  const [expandedSymbol, setExpandedSymbol] = useState(null);

  const toggleExpand = (sym) => {
    setExpandedSymbol(prev => prev === sym ? null : sym);
  };

  return (
    <div className="space-y-3 pb-8">
      
      {/* SECTION HEADER: ZERODHA KITE MARKETWATCH BAR */}
      <div className="flex items-center justify-between px-1 pt-1 pb-1 border-b border-white/[0.06]">
        <div className="flex items-center gap-2">
          <span className="text-xs font-black tracking-tight text-white font-mono uppercase">
            Marketwatch
          </span>
          <span className="text-[10px] font-mono font-bold px-1.5 py-0.2 rounded bg-sky-500/15 text-sky-300 border border-sky-500/30">
            6 / 6 Crown Stocks
          </span>
        </div>
        <div className="flex items-center gap-1.5 text-[10px] font-mono text-slate-400">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span>Real-Time NSE Cash</span>
        </div>
      </div>

      {/* CROWN 6 STOCKS HIGH-DENSITY LIST (Zerodha Kite & ComposeCookBook Style) */}
      <div className="space-y-2.5">
        {instruments.map((inst) => {
          const isUp = (inst.change || 0) >= 0;
          const score = inst.score || 50;
          const isExpanded = expandedSymbol === inst.symbol;

          // Probability score styling
          let scoreBadgeBg = "bg-slate-800 text-slate-300 border-slate-700";
          let scoreLabel = "Consolidating";

          if (inst.trend === "ACTIVE_IN_POSITION") {
            scoreBadgeBg = "bg-sky-500/20 text-sky-300 border-sky-500/40";
            scoreLabel = "In Position";
          } else if (score >= 80) {
            scoreBadgeBg = "bg-emerald-500/20 text-emerald-300 border-emerald-500/40";
            scoreLabel = "High Prob (82%)";
          } else if (score >= 60) {
            scoreBadgeBg = "bg-amber-500/20 text-amber-300 border-amber-500/40";
            scoreLabel = "Moderate (74%)";
          } else {
            scoreBadgeBg = "bg-rose-500/20 text-rose-300 border-rose-500/40";
            scoreLabel = "Consolidating";
          }

          // Tick flash animation
          const tickFlashClass = inst.tickDirection === 'up' 
            ? 'tick-flash-up' 
            : inst.tickDirection === 'down' 
              ? 'tick-flash-down' 
              : '';

          return (
            <div
              key={inst.symbol}
              className={`bg-[#0F1424] border border-white/[0.08] rounded-2xl p-3.5 transition-all shadow-md ${tickFlashClass} hover:border-sky-500/30`}
            >
              
              {/* PRIMARY ROW: SYMBOL, NAME, LTP, AND CHANGE */}
              <div 
                onClick={() => toggleExpand(inst.symbol)}
                className="flex items-center justify-between cursor-pointer"
              >
                {/* Left: Symbol & Sector */}
                <div>
                  <div className="flex items-center gap-1.5">
                    <h3 className="text-sm font-black font-mono text-white tracking-tight">
                      {inst.symbol}
                    </h3>
                    <span className="text-[9px] font-mono px-1 py-0.2 rounded bg-white/[0.06] text-slate-400 border border-white/[0.08]">
                      EQ
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400 font-medium truncate max-w-[150px] xs:max-w-[190px]">
                    {inst.name}
                  </p>
                </div>

                {/* Right: LTP & Percentage Change */}
                <div className="flex flex-col items-end">
                  <div className="text-base font-black font-mono text-white tracking-tight tabular-nums">
                    ₹{inst.price.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </div>
                  <div className={`px-2 py-0.2 rounded-full font-mono text-[10px] font-extrabold flex items-center gap-0.5 border ${
                    isUp 
                      ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' 
                      : 'bg-rose-500/15 text-rose-400 border-rose-500/30'
                  }`}>
                    {isUp ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                    <span>{isUp ? '+' : ''}{inst.change_pct.toFixed(2)}%</span>
                  </div>
                </div>
              </div>

              {/* SECONDARY ROW: PROBABILITY SCORE PILL & ACTION */}
              <div className="mt-2.5 pt-2 border-t border-white/[0.06] flex items-center justify-between text-xs font-mono">
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] text-slate-400 font-bold uppercase">Score:</span>
                  <span className={`px-2 py-0.5 rounded-md text-[10px] font-extrabold border ${scoreBadgeBg}`}>
                    {score} / 100 • {scoreLabel}
                  </span>
                </div>

                <div className="flex items-center gap-1.5">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onOpenChart(inst.symbol);
                    }}
                    className="p-1 px-2 rounded-lg bg-sky-500/15 hover:bg-sky-500/25 border border-sky-500/30 text-sky-300 text-[10px] font-bold font-mono flex items-center gap-1 transition-all cursor-pointer"
                  >
                    <BarChart2 className="w-3 h-3" />
                    <span>5m Chart</span>
                  </button>

                  <button
                    onClick={() => toggleExpand(inst.symbol)}
                    className="p-1 rounded-lg text-slate-400 hover:text-white"
                  >
                    {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                  </button>
                </div>
              </div>

              {/* TACTICAL RADAR BOX: NEXT ALGORITHMIC STEP */}
              <div className="mt-2 p-2.5 rounded-xl bg-[#090D18] border border-sky-500/20 flex items-start gap-2">
                <Crosshair className="w-3.5 h-3.5 text-sky-400 shrink-0 mt-0.5 animate-pulse" />
                <div className="text-[11px] leading-relaxed text-slate-200">
                  <strong className="text-sky-300 font-mono text-[10px] block uppercase">Next Trigger:</strong>
                  {inst.next_step || 'Scanning 5m price action for institutional confluence...'}
                </div>
              </div>

              {/* EXPANDABLE QUANT METRICS (EMA9, VWAP, ATR, 5x MIS MARGIN) */}
              {isExpanded && (
                <div className="mt-2.5 pt-2 border-t border-white/[0.06] grid grid-cols-4 gap-1.5 text-center text-[10px] font-mono text-slate-400 animate-fade-in">
                  <div className="bg-[#090D18] p-1.5 rounded-lg border border-white/[0.04]">
                    <div className="text-slate-500 text-[9px]">EMA 9</div>
                    <div className="text-slate-200 font-bold tabular-nums">
                      ₹{inst.ema9 ? inst.ema9.toFixed(2) : '--'}
                    </div>
                  </div>
                  <div className="bg-[#090D18] p-1.5 rounded-lg border border-white/[0.04]">
                    <div className="text-slate-500 text-[9px]">VWAP</div>
                    <div className="text-slate-200 font-bold tabular-nums">
                      ₹{inst.vwap ? inst.vwap.toFixed(2) : '--'}
                    </div>
                  </div>
                  <div className="bg-[#090D18] p-1.5 rounded-lg border border-white/[0.04]">
                    <div className="text-slate-500 text-[9px]">ATR (14)</div>
                    <div className="text-slate-200 font-bold tabular-nums">
                      ₹{inst.atr ? inst.atr.toFixed(2) : '--'}
                    </div>
                  </div>
                  <div className="bg-[#090D18] p-1.5 rounded-lg border border-white/[0.04]">
                    <div className="text-slate-500 text-[9px]">5x MIS Margin</div>
                    <div className="text-amber-400 font-bold tabular-nums">
                      ₹{(inst.price / 5).toFixed(1)}
                    </div>
                  </div>
                </div>
              )}

            </div>
          );
        })}
      </div>

    </div>
  );
}
