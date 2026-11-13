import React, { useState } from 'react';
import { 
  TrendingUp, 
  TrendingDown, 
  Target, 
  Crosshair, 
  Sparkles, 
  Activity, 
  BarChart2, 
  Radio, 
  ChevronRight,
  ShieldCheck,
  Zap
} from 'lucide-react';

export default function DashboardTab({ dashboardData, onOpenChart }) {
  const instruments = dashboardData?.instruments || [];
  const nifty = dashboardData?.nifty50 || { price: 24350.0, change: 0.0, change_pct: 0.0 };

  const isNiftyUp = nifty.change >= 0;

  return (
    <div className="space-y-6 pb-24 max-w-7xl mx-auto px-4 sm:px-6 pt-4">
      
      {/* MACRO NIFTY 50 REGIME BANNER */}
      <div className="glass-panel rounded-2xl p-4 sm:p-5 border border-slate-800 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-sky-500/20 to-slate-900 border border-sky-500/30 flex items-center justify-center">
            <Radio className="w-5 h-5 text-sky-400 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono font-semibold tracking-wider text-slate-400 uppercase">
                Macro Trend Filter
              </span>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-sky-500/15 text-sky-400 border border-sky-500/30">
                NIFTY 50
              </span>
            </div>
            <div className="flex items-baseline gap-2 mt-0.5">
              <span className="text-lg font-bold font-mono text-white">
                ₹{nifty.price.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
              <span className={`text-xs font-mono font-semibold flex items-center gap-0.5 ${
                isNiftyUp ? 'text-emerald-400' : 'text-rose-400'
              }`}>
                {isNiftyUp ? '+' : ''}{nifty.change.toFixed(2)} ({isNiftyUp ? '+' : ''}{nifty.change_pct.toFixed(2)}%)
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs font-mono text-slate-300 bg-slate-900/80 px-3.5 py-2 rounded-xl border border-slate-800">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
          <span>Regime: <strong className="text-emerald-400">Bullish Aligned</strong> (Only Long Pullbacks Allowed)</span>
        </div>
      </div>

      {/* SECTION HEADER */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-extrabold tracking-tight text-white flex items-center gap-2">
            <span>CROWN 6 ALPHA WATCHLIST</span>
            <span className="px-2 py-0.5 text-[10px] font-mono font-semibold bg-emerald-500/10 text-emerald-400 rounded-full border border-emerald-500/30">
              Live Ticks (1s)
            </span>
          </h2>
          <p className="text-xs text-slate-400">
            Real-time probability scores, live market prices & next algorithmic setup triggers.
          </p>
        </div>
      </div>

      {/* 6 CROWN INSTRUMENTS GRID */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-5">
        {instruments.map((inst) => {
          const isUp = inst.change >= 0;
          const score = inst.score || 50;

          // Score styling
          let scoreBadgeColor = "bg-slate-800 text-slate-300 border-slate-700";
          let scoreText = "CONSOLIDATING";
          if (inst.trend === "ACTIVE_IN_POSITION") {
            scoreBadgeColor = "bg-sky-500/20 text-sky-400 border-sky-500/40";
            scoreText = "TRADE ACTIVE";
          } else if (score >= 80) {
            scoreBadgeColor = "bg-emerald-500/20 text-emerald-400 border-emerald-500/40";
            scoreText = "HIGH PROBABILITY";
          } else if (score >= 60) {
            scoreBadgeColor = "bg-amber-500/20 text-amber-400 border-amber-500/40";
            scoreText = "MODERATE PROBABILITY";
          }

          return (
            <div 
              key={inst.symbol}
              className="glass-card p-5 relative overflow-hidden flex flex-col justify-between group"
            >
              {/* Top Accent Gradient Line */}
              <div className={`absolute top-0 left-0 right-0 h-[2px] ${
                score >= 80 ? 'bg-gradient-to-r from-emerald-500 to-teal-400' : 'bg-gradient-to-r from-slate-700 to-slate-800'
              }`} />

              <div>
                {/* Header: Symbol & Sector */}
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-base font-extrabold tracking-tight text-white font-mono">
                        {inst.symbol}
                      </span>
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono text-slate-400 bg-slate-800/80 border border-slate-700/60">
                        {inst.sector}
                      </span>
                    </div>
                    <span className="text-xs text-slate-400 truncate block max-w-[200px]">
                      {inst.name}
                    </span>
                  </div>

                  {/* Trade Probability Score out of 100 */}
                  <div className="flex flex-col items-end">
                    <div className="flex items-center gap-1.5 font-mono">
                      <span className="text-xs text-slate-400">Score</span>
                      <span className="text-base font-extrabold text-white">
                        {score}
                      </span>
                      <span className="text-[10px] text-slate-400">/100</span>
                    </div>
                    <span className={`text-[9px] font-mono font-bold px-2 py-0.5 rounded-full border mt-0.5 tracking-tight ${scoreBadgeColor}`}>
                      {scoreText}
                    </span>
                  </div>
                </div>

                {/* Live Running Price & Change */}
                <div className="mt-4 flex items-baseline justify-between pb-3 border-b border-slate-800/60">
                  <div className="font-mono">
                    <span className="text-2xl font-black text-white tracking-tight">
                      ₹{inst.price.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                  </div>
                  <div className={`flex items-center gap-1 font-mono text-xs font-bold ${
                    isUp ? 'text-emerald-400' : 'text-rose-400'
                  }`}>
                    {isUp ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
                    <span>{isUp ? '+' : ''}{inst.change.toFixed(2)} ({isUp ? '+' : ''}{inst.change_pct.toFixed(2)}%)</span>
                  </div>
                </div>

                {/* Day Stats Grid */}
                <div className="grid grid-cols-3 gap-2 py-2.5 text-[11px] font-mono text-slate-400 border-b border-slate-800/60">
                  <div>
                    <span className="text-slate-400 block text-[9px] uppercase">High</span>
                    <span className="text-slate-200">₹{inst.day_high?.toFixed(1) || '-'}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[9px] uppercase">Low</span>
                    <span className="text-slate-200">₹{inst.day_low?.toFixed(1) || '-'}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[9px] uppercase">Volume</span>
                    <span className="text-slate-200">{(inst.volume / 1000).toFixed(0)}k</span>
                  </div>
                </div>

                {/* NEXT STEP REASONING BOX */}
                <div className="mt-3.5 bg-slate-900/80 rounded-xl p-3 border border-slate-800/80 relative">
                  <div className="flex items-center gap-1.5 text-[10px] font-mono font-bold uppercase tracking-wider text-emerald-400 mb-1">
                    <Crosshair className="w-3.5 h-3.5" />
                    <span>Next Algorithmic Step</span>
                  </div>
                  <p className="text-xs text-slate-300 leading-relaxed font-sans font-medium">
                    {inst.next_step}
                  </p>
                </div>
              </div>

              {/* Bottom Actions */}
              <div className="mt-4 pt-2 flex items-center justify-between text-xs">
                <span className="text-[10px] font-mono text-slate-400">
                  Updated {inst.updated_at}
                </span>
                <button
                  onClick={() => onOpenChart && onOpenChart(inst.symbol)}
                  className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white flex items-center gap-1 text-[11px] font-medium transition-all"
                >
                  <BarChart2 className="w-3 h-3 text-emerald-400" />
                  <span>Chart</span>
                </button>
              </div>

            </div>
          );
        })}
      </div>

    </div>
  );
}
