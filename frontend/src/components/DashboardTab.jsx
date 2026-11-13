import React from 'react';
import { 
  TrendingUp, 
  TrendingDown, 
  Crosshair, 
  Activity, 
  BarChart2, 
  Radio, 
  Zap,
  Sparkles,
  ShieldCheck,
  Compass
} from 'lucide-react';

export default function DashboardTab({ dashboardData, onOpenChart }) {
  const instruments = dashboardData?.instruments || [];
  const nifty = dashboardData?.nifty50 || { price: 25091.15, change: -163.95, change_pct: -0.65 };
  const isNiftyUp = (nifty.change || 0) >= 0;

  return (
    <div className="space-y-6 pb-28 max-w-7xl mx-auto px-4 sm:px-6 pt-5">
      
      {/* MACRO NIFTY 50 REGIME BANNER */}
      <div className="glass-panel rounded-2xl p-4 sm:p-5 flex flex-col md:flex-row md:items-center md:justify-between gap-4 border border-slate-800/90 shadow-xl">
        <div className="flex items-center gap-3.5">
          <div className="w-11 h-11 rounded-2xl bg-gradient-to-tr from-sky-500/20 via-slate-900 to-emerald-500/20 border border-sky-500/40 flex items-center justify-center glow-emerald">
            <Radio className="w-5 h-5 text-sky-400 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-mono font-bold tracking-widest text-slate-400 uppercase">
                Macro Regime Engine
              </span>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-extrabold bg-sky-500/20 text-sky-300 border border-sky-500/30">
                NIFTY 50 BENCHMARK
              </span>
            </div>
            <div className="flex items-baseline gap-2.5 mt-1 font-mono">
              <span className="text-xl sm:text-2xl font-black text-white tracking-tight">
                ₹{nifty.price.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
              <span className={`text-xs sm:text-sm font-bold flex items-center gap-0.5 ${
                isNiftyUp ? 'text-emerald-400' : 'text-rose-400'
              }`}>
                {isNiftyUp ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
                {isNiftyUp ? '+' : ''}{nifty.change.toFixed(2)} ({isNiftyUp ? '+' : ''}{nifty.change_pct.toFixed(2)}%)
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 self-start md:self-auto bg-slate-900/90 px-4 py-2.5 rounded-xl border border-slate-800 text-xs font-mono">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping" />
          <span className="text-slate-300">
            Regime Status: <strong className="text-emerald-400">Institutional Trend Aligned</strong>
          </span>
        </div>
      </div>

      {/* SECTION TITLE & BADGE */}
      <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
        <div>
          <h2 className="text-xl font-black tracking-tight text-white flex items-center gap-2.5">
            <span className="bg-gradient-to-r from-emerald-400 via-teal-200 to-amber-400 bg-clip-text text-transparent">
              CROWN 6 ALPHA WATCHLIST
            </span>
            <span className="px-2.5 py-0.5 text-[10px] font-mono font-bold bg-emerald-500/15 text-emerald-400 rounded-full border border-emerald-500/30 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              1s Real-Time Ticks
            </span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Real-time probability scoring, exact NSE cash market prices & algorithmic step execution.
          </p>
        </div>
      </div>

      {/* 6 CROWN INSTRUMENTS GRID */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {instruments.map((inst) => {
          const isUp = (inst.change || 0) >= 0;
          const score = inst.score || 50;

          // Probability badge styling
          let scoreBadgeColor = "bg-slate-800/80 text-slate-300 border-slate-700";
          let scoreText = "CONSOLIDATING";
          let glowClass = "";

          if (inst.trend === "ACTIVE_IN_POSITION") {
            scoreBadgeColor = "bg-sky-500/20 text-sky-400 border-sky-500/50";
            scoreText = "IN POSITION";
            glowClass = "border-sky-500/40";
          } else if (score >= 80) {
            scoreBadgeColor = "bg-emerald-500/20 text-emerald-400 border-emerald-500/50";
            scoreText = "HIGH PROBABILITY";
            glowClass = "border-emerald-500/40";
          } else if (score >= 60) {
            scoreBadgeColor = "bg-amber-500/20 text-amber-400 border-amber-500/50";
            scoreText = "MODERATE SETUP";
            glowClass = "border-amber-500/30";
          }

          return (
            <div 
              key={inst.symbol}
              className={`glass-card p-5 relative overflow-hidden flex flex-col justify-between border ${glowClass || 'border-slate-800/80'} shadow-xl`}
            >
              {/* Top Accent Gradient Bar */}
              <div className={`absolute top-0 left-0 right-0 h-[3px] ${
                score >= 80 ? 'bg-gradient-to-r from-emerald-500 via-teal-400 to-amber-400' : 'bg-gradient-to-r from-slate-700 to-slate-800'
              }`} />

              <div>
                {/* Header: Symbol & Sector */}
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-lg font-black tracking-tight text-white font-mono">
                        {inst.symbol}
                      </h3>
                      <span className="px-2 py-0.5 rounded-md text-[10px] font-mono font-bold text-slate-300 bg-slate-800/90 border border-slate-700/80">
                        {inst.sector}
                      </span>
                    </div>
                    <span className="text-xs text-slate-400 font-medium block mt-0.5">
                      {inst.name}
                    </span>
                  </div>

                  {/* Probability Score Pill */}
                  <div className="flex flex-col items-end">
                    <div className="flex items-center gap-1 font-mono">
                      <span className="text-[10px] text-slate-400 uppercase">Score</span>
                      <span className="text-base font-extrabold text-white">
                        {score}
                      </span>
                      <span className="text-[10px] text-slate-400">/100</span>
                    </div>
                    <span className={`text-[9px] font-mono font-extrabold px-2 py-0.5 rounded-full border mt-1 tracking-wider ${scoreBadgeColor}`}>
                      {scoreText}
                    </span>
                  </div>
                </div>

                {/* Live Running Price & Change Badge */}
                <div className="mt-4 flex items-baseline justify-between pb-3.5 border-b border-slate-800/70">
                  <div className="font-mono">
                    <span className="text-2xl sm:text-3xl font-black text-white tracking-tight">
                      ₹{inst.price.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                  </div>

                  <div className={`flex items-center gap-1 font-mono text-xs font-bold px-2 py-1 rounded-lg ${
                    isUp ? 'bg-emerald-500/15 text-emerald-400' : 'bg-rose-500/15 text-rose-400'
                  }`}>
                    {isUp ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
                    <span>{isUp ? '+' : ''}{inst.change.toFixed(2)} ({isUp ? '+' : ''}{inst.change_pct.toFixed(2)}%)</span>
                  </div>
                </div>

                {/* Day Stats Row (High, Low, Volume) */}
                <div className="grid grid-cols-3 gap-2 py-3 text-[11px] font-mono text-slate-300 border-b border-slate-800/70">
                  <div>
                    <span className="text-slate-400 block text-[9px] uppercase font-bold">Day High</span>
                    <span className="text-white font-semibold">₹{inst.day_high?.toFixed(2) || '-'}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[9px] uppercase font-bold">Day Low</span>
                    <span className="text-white font-semibold">₹{inst.day_low?.toFixed(2) || '-'}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[9px] uppercase font-bold">Volume</span>
                    <span className="text-slate-200 font-semibold">{(inst.volume / 1000).toLocaleString('en-IN', { maximumFractionDigits: 0 })}k</span>
                  </div>
                </div>

                {/* WHAT IT IS LOOKING FOR / NEXT STEP BOX */}
                <div className="mt-4 bg-slate-950/80 rounded-xl p-3.5 border border-slate-800/90 shadow-inner">
                  <div className="flex items-center gap-1.5 text-[10px] font-mono font-extrabold uppercase tracking-widest text-emerald-400 mb-1">
                    <Crosshair className="w-3.5 h-3.5" />
                    <span>Next Algorithmic Step</span>
                  </div>
                  <p className="text-xs text-slate-200 leading-relaxed font-sans font-medium">
                    {inst.next_step}
                  </p>
                </div>
              </div>

              {/* Card Footer: Timestamp & Chart Trigger */}
              <div className="mt-4 pt-2 flex items-center justify-between text-xs">
                <span className="text-[10px] font-mono text-slate-400">
                  Live Tick {inst.updated_at}
                </span>
                <button
                  onClick={() => onOpenChart && onOpenChart(inst.symbol)}
                  className="px-3 py-1.5 rounded-lg bg-slate-800/90 hover:bg-slate-700 text-slate-300 hover:text-white flex items-center gap-1.5 text-xs font-semibold transition-all border border-slate-700/60"
                >
                  <BarChart2 className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Interactive Chart</span>
                </button>
              </div>

            </div>
          );
        })}
      </div>

    </div>
  );
}
