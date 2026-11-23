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
  Info,
  Layers,
  LayoutGrid,
  ListFilter
} from 'lucide-react';

export default function DashboardTab({ dashboardData, onOpenChart }) {
  const instruments = dashboardData?.instruments || [];
  const [expandedSymbol, setExpandedSymbol] = useState(null);
  const [viewMode, setViewMode] = useState('grid'); // 'grid' or 'table'

  const toggleExpand = (sym) => {
    setExpandedSymbol(prev => prev === sym ? null : sym);
  };

  return (
    <div className="space-y-4 pb-12">
      
      {/* SECTION HEADER: MARKETWATCH CONTROLS & DENSITY TOGGLE */}
      <div className="flex items-center justify-between px-1 pt-1 pb-2 border-b border-white/[0.08] flex-wrap gap-2">
        <div className="flex items-center gap-2.5">
          <span className="text-xs sm:text-sm font-black tracking-tight text-white font-mono uppercase">
            29 Mega-Cap Velocity Marketwatch
          </span>
          <span className="text-[10px] font-mono font-extrabold px-2 py-0.5 rounded-full bg-sky-500/15 text-sky-300 border border-sky-500/30">
            {instruments.length} Instruments
          </span>
        </div>

        {/* View mode toggle & Real-time status */}
        <div className="flex items-center gap-2">
          <div className="bg-[#0D121F] p-0.5 rounded-lg border border-white/10 flex items-center">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-1 sm:px-2 sm:py-1 rounded-md text-[10px] font-mono font-bold flex items-center gap-1 transition-all cursor-pointer ${
                viewMode === 'grid' 
                  ? 'bg-sky-500/20 text-sky-300 border border-sky-500/30 shadow-sm' 
                  : 'text-slate-400 hover:text-white'
              }`}
              title="Bento Grid View"
            >
              <LayoutGrid className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Cards</span>
            </button>
            <button
              onClick={() => setViewMode('table')}
              className={`p-1 sm:px-2 sm:py-1 rounded-md text-[10px] font-mono font-bold flex items-center gap-1 transition-all cursor-pointer ${
                viewMode === 'table' 
                  ? 'bg-sky-500/20 text-sky-300 border border-sky-500/30 shadow-sm' 
                  : 'text-slate-400 hover:text-white'
              }`}
              title="Compact Table View"
            >
              <ListFilter className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Table</span>
            </button>
          </div>

          <div className="hidden xs:flex items-center gap-1.5 text-[10px] font-mono text-slate-400 bg-[#0D121F] px-2.5 py-1 rounded-lg border border-white/10">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 beacon-pulse-emerald" />
            <span>NSE Cash Real-Time</span>
          </div>
        </div>
      </div>

      {/* VIEW MODE A: BENTO GRID CARDS */}
      {viewMode === 'grid' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {instruments.map((inst) => {
            const isUp = (inst.change || 0) >= 0;
            const score = inst.score || 50;
            const isExpanded = expandedSymbol === inst.symbol;

            // Setup Badge Styling
            let scoreBadgeStyle = "bg-slate-800/80 text-slate-300 border-slate-700";
            let scoreLabel = "Consolidating";

            if (inst.trend === "ACTIVE_IN_POSITION") {
              scoreBadgeStyle = "bg-sky-500/20 text-sky-300 border-sky-500/40 glow-cyan";
              scoreLabel = "In Active Trade";
            } else if (score >= 80) {
              scoreBadgeStyle = "bg-emerald-500/20 text-emerald-300 border-emerald-500/40 glow-emerald";
              scoreLabel = "High Prob (82%)";
            } else if (score >= 60) {
              scoreBadgeStyle = "bg-amber-500/20 text-amber-300 border-amber-500/40";
              scoreLabel = "Moderate (74%)";
            }

            const tickFlashClass = inst.tickDirection === 'up' 
              ? 'tick-flash-up' 
              : inst.tickDirection === 'down' 
                ? 'tick-flash-down' 
                : '';

            return (
              <div
                key={inst.symbol}
                className={`bento-card p-4 transition-all ${tickFlashClass} bento-card-interactive flex flex-col justify-between`}
              >
                <div>
                  {/* TOP ROW: SYMBOL, SECTOR, LTP, CHANGE */}
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-base font-black font-mono text-white tracking-tight">
                          {inst.symbol}
                        </h3>
                        <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded bg-white/[0.08] text-slate-300 border border-white/10 uppercase">
                          EQ
                        </span>
                      </div>
                      <p className="text-xs text-slate-400 font-medium truncate max-w-[180px] mt-0.5">
                        {inst.name}
                      </p>
                    </div>

                    {/* Price & Change Pill */}
                    <div className="flex flex-col items-end">
                      <div className="text-base sm:text-lg font-black font-mono text-white tracking-tight tabular-nums">
                        ₹{inst.price.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </div>
                      <div className={`px-2 py-0.5 rounded-full font-mono text-[10px] font-extrabold flex items-center gap-0.5 border mt-0.5 ${
                        isUp 
                          ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' 
                          : 'bg-rose-500/15 text-rose-400 border-rose-500/30'
                      }`}>
                        {isUp ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                        <span>{isUp ? '+' : ''}{inst.change_pct.toFixed(2)}%</span>
                      </div>
                    </div>
                  </div>

                  {/* PROBABILITY BADGE & TRIGGER STATE */}
                  <div className="mt-3 flex items-center justify-between text-xs font-mono">
                    <span className={`px-2.5 py-0.5 rounded-full font-extrabold border flex items-center gap-1.5 ${scoreBadgeStyle}`}>
                      <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
                      <span>{scoreLabel}</span>
                    </span>

                    <button
                      onClick={() => onOpenChart(inst.symbol)}
                      className="px-2.5 py-1 rounded-lg bg-sky-500/10 hover:bg-sky-500/20 text-sky-400 border border-sky-500/30 text-[10px] font-bold flex items-center gap-1 transition-all cursor-pointer"
                    >
                      <BarChart2 className="w-3 h-3" />
                      <span>5m Chart</span>
                    </button>
                  </div>

                  {/* NARRATIVE NEXT STEP BOX */}
                  <div className="mt-3 p-2.5 rounded-xl bg-[#080C16]/90 border border-white/[0.06] text-[11px] leading-relaxed text-slate-300 font-sans">
                    <div className="flex items-start gap-1.5">
                      <Sparkles className="w-3.5 h-3.5 text-sky-400 flex-shrink-0 mt-0.5" />
                      <span>{inst.next_step}</span>
                    </div>
                  </div>
                </div>

                {/* EXPANDABLE TELEMETRY STRIP (EMA 9, VWAP, ATR) */}
                <div className="mt-3 pt-2.5 border-t border-white/[0.06]">
                  <div 
                    onClick={() => toggleExpand(inst.symbol)}
                    className="flex items-center justify-between text-[10px] font-mono text-slate-400 cursor-pointer hover:text-slate-200"
                  >
                    <span>Technical Indicators</span>
                    <div className="flex items-center gap-1">
                      <span>{isExpanded ? 'Hide' : 'Show Details'}</span>
                      {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="grid grid-cols-3 gap-2 mt-2 pt-2 border-t border-white/[0.04] text-[10px] font-mono">
                      <div className="bg-[#121826] p-2 rounded-lg text-center">
                        <span className="text-slate-500 block">EMA 9</span>
                        <span className="font-bold text-sky-400 tabular-nums">₹{inst.ema9?.toFixed(2) || '—'}</span>
                      </div>
                      <div className="bg-[#121826] p-2 rounded-lg text-center">
                        <span className="text-slate-500 block">VWAP</span>
                        <span className="font-bold text-indigo-400 tabular-nums">₹{inst.vwap?.toFixed(2) || '—'}</span>
                      </div>
                      <div className="bg-[#121826] p-2 rounded-lg text-center">
                        <span className="text-slate-500 block">ATR 14</span>
                        <span className="font-bold text-amber-400 tabular-nums">₹{inst.atr?.toFixed(2) || '—'}</span>
                      </div>
                    </div>
                  )}
                </div>

              </div>
            );
          })}
        </div>
      ) : (
        /* VIEW MODE B: COMPACT DATA-DENSE TABLE (INSTITUTIONAL DESK SPEC) */
        <div className="bento-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-[#0B0F19] border-b border-white/[0.08] text-[10px] uppercase text-slate-400 tracking-wider">
                <tr>
                  <th className="px-4 py-3 font-bold">Instrument</th>
                  <th className="px-3 py-3 font-bold text-right">LTP (₹)</th>
                  <th className="px-3 py-3 font-bold text-right">Change (%)</th>
                  <th className="px-3 py-3 font-bold text-center">Status</th>
                  <th className="px-3 py-3 font-bold text-right">EMA 9</th>
                  <th className="px-3 py-3 font-bold text-right">VWAP</th>
                  <th className="px-4 py-3 font-bold text-center">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.05]">
                {instruments.map((inst) => {
                  const isUp = (inst.change || 0) >= 0;
                  const score = inst.score || 50;

                  return (
                    <tr key={inst.symbol} className="hover:bg-white/[0.02] transition-colors">
                      <td className="px-4 py-3">
                        <div className="font-black text-white">{inst.symbol}</div>
                        <div className="text-[10px] text-slate-400 font-sans truncate max-w-[140px]">{inst.name}</div>
                      </td>
                      <td className="px-3 py-3 text-right font-black text-white tabular-nums">
                        ₹{inst.price.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </td>
                      <td className={`px-3 py-3 text-right font-extrabold tabular-nums ${isUp ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {isUp ? '+' : ''}{inst.change_pct.toFixed(2)}%
                      </td>
                      <td className="px-3 py-3 text-center">
                        <span className={`inline-block px-2 py-0.5 rounded-full text-[9px] font-extrabold border ${
                          inst.trend === "ACTIVE_IN_POSITION"
                            ? 'bg-sky-500/20 text-sky-300 border-sky-500/40'
                            : score >= 80
                              ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                              : 'bg-slate-800 text-slate-300 border-slate-700'
                        }`}>
                          {inst.trend === "ACTIVE_IN_POSITION" ? 'In Position' : `${score}% Prob`}
                        </span>
                      </td>
                      <td className="px-3 py-3 text-right text-slate-300 tabular-nums">₹{inst.ema9?.toFixed(2) || '—'}</td>
                      <td className="px-3 py-3 text-right text-indigo-400 tabular-nums">₹{inst.vwap?.toFixed(2) || '—'}</td>
                      <td className="px-4 py-3 text-center">
                        <button
                          onClick={() => onOpenChart(inst.symbol)}
                          className="px-2.5 py-1 rounded bg-sky-500/15 hover:bg-sky-500/25 text-sky-300 text-[10px] font-bold border border-sky-500/30 transition-all cursor-pointer"
                        >
                          Chart
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

    </div>
  );
}
