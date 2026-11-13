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
  Compass,
  ArrowUpRight,
  ArrowDownRight,
  Maximize2
} from 'lucide-react';

export default function DashboardTab({ dashboardData, onOpenChart }) {
  const instruments = dashboardData?.instruments || [];
  const nifty = dashboardData?.nifty50 || { price: 25078.25, change: -176.85, change_pct: -0.70 };
  const isNiftyUp = (nifty.change || 0) >= 0;

  // Sector color accents for avatar badges
  const sectorColors = {
    RELIANCE: 'from-blue-500/20 to-cyan-500/20 border-cyan-500/40 text-cyan-400',
    ITC: 'from-amber-500/20 to-orange-500/20 border-amber-500/40 text-amber-400',
    MARUTI: 'from-red-500/20 to-rose-500/20 border-rose-500/40 text-rose-400',
    TATASTEEL: 'from-indigo-500/20 to-sky-500/20 border-indigo-500/40 text-indigo-400',
    SUNPHARMA: 'from-emerald-500/20 to-teal-500/20 border-emerald-500/40 text-emerald-400',
    INFY: 'from-violet-500/20 to-purple-500/20 border-purple-500/40 text-purple-400'
  };

  return (
    <div className="space-y-5 max-w-7xl mx-auto px-3 sm:px-6 pt-4 pb-12">
      
      {/* ====================================================================
          MACRO NIFTY 50 REGIME BANNER (Compose CookBook Macro Card)
          ==================================================================== */}
      <div className="m3-card p-4 sm:p-5 flex flex-col md:flex-row md:items-center md:justify-between gap-4 border border-white/[0.08] relative overflow-hidden">
        {/* Subtle background glow */}
        <div className="absolute -right-10 -top-10 w-48 h-48 bg-sky-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="flex items-center gap-3.5 z-10">
          <div className="w-11 h-11 rounded-2xl bg-gradient-to-tr from-sky-500/20 via-slate-900 to-indigo-500/20 border border-sky-500/30 flex items-center justify-center shadow-lg shadow-sky-500/10">
            <Radio className="w-5 h-5 text-sky-400 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-mono font-bold tracking-widest text-slate-400 uppercase">
                Macro Regime Filter
              </span>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-extrabold bg-sky-500/20 text-sky-300 border border-sky-500/30">
                NIFTY 50 CASH
              </span>
            </div>
            <div className="flex items-baseline gap-2.5 mt-1 font-mono">
              <span className="text-xl sm:text-2xl font-black text-white tracking-tight tabular-nums">
                ₹{nifty.price.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
              <span className={`text-xs sm:text-sm font-extrabold flex items-center gap-0.5 px-2 py-0.5 rounded-full ${
                isNiftyUp 
                  ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30' 
                  : 'bg-rose-500/15 text-rose-400 border border-rose-500/30'
              }`}>
                {isNiftyUp ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
                {isNiftyUp ? '+' : ''}{nifty.change.toFixed(2)} ({isNiftyUp ? '+' : ''}{nifty.change_pct.toFixed(2)}%)
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 self-start md:self-auto bg-[#0A0D14]/80 px-4 py-2.5 rounded-2xl border border-white/[0.08] text-xs font-mono z-10">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping" />
          <span className="text-slate-300">
            Regime Status: <strong className="text-emerald-400">Institutional Trend Aligned (Shorts/Pullbacks Allowed)</strong>
          </span>
        </div>
      </div>

      {/* ====================================================================
          WATCHLIST HEADER
          ==================================================================== */}
      <div className="flex items-center justify-between border-b border-white/[0.06] pb-3 pt-2">
        <div>
          <h2 className="text-lg sm:text-xl font-extrabold tracking-tight text-white flex items-center gap-2">
            <span className="bg-gradient-to-r from-sky-400 via-teal-300 to-emerald-400 bg-clip-text text-transparent">
              CROWN 6 ALPHA WATCHLIST
            </span>
            <span className="px-2.5 py-0.5 text-[10px] font-mono font-bold bg-emerald-500/15 text-emerald-400 rounded-full border border-emerald-500/30 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              1s High-Freq Ticks
            </span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Real-time probability scores (0–100), exact NSE cash prices & institutional next-step execution triggers.
          </p>
        </div>
      </div>

      {/* ====================================================================
          6 CROWN INSTRUMENTS GRID (ComposeCookBook Card Layout)
          ==================================================================== */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-5">
        {instruments.map((inst) => {
          const isUp = (inst.change || 0) >= 0;
          const score = inst.score || 50;
          const colorClass = sectorColors[inst.symbol] || 'from-sky-500/20 to-indigo-500/20 border-sky-500/40 text-sky-400';

          // Score Badge styling
          let scoreBadgeClass = "bg-slate-800/80 text-slate-300 border-slate-700/60";
          let scoreLabel = "CONSOLIDATING";
          let scoreBarColor = "from-slate-500 to-slate-400";

          if (inst.trend === "ACTIVE_IN_POSITION") {
            scoreBadgeClass = "bg-sky-500/20 text-sky-300 border-sky-500/50 shadow-sm shadow-sky-500/20";
            scoreLabel = "IN POSITION";
            scoreBarColor = "from-sky-500 to-cyan-400";
          } else if (score >= 80) {
            scoreBadgeClass = "bg-emerald-500/20 text-emerald-300 border-emerald-500/50 shadow-sm shadow-emerald-500/20";
            scoreLabel = "HIGH PROBABILITY";
            scoreBarColor = "from-emerald-500 to-teal-400";
          } else if (score >= 60) {
            scoreBadgeClass = "bg-amber-500/20 text-amber-300 border-amber-500/50 shadow-sm shadow-amber-500/20";
            scoreLabel = "MODERATE SETUP";
            scoreBarColor = "from-amber-500 to-yellow-400";
          } else {
            scoreBadgeClass = "bg-rose-500/20 text-rose-300 border-rose-500/50";
            scoreLabel = "LOW PROBABILITY";
            scoreBarColor = "from-rose-500 to-rose-400";
          }

          // Tick direction flash styling
          const tickClass = inst.tickDirection === 'up' 
            ? 'tick-flash-up' 
            : inst.tickDirection === 'down' 
              ? 'tick-flash-down' 
              : '';

          return (
            <div 
              key={inst.symbol}
              className={`m3-card p-4 sm:p-5 flex flex-col justify-between relative group ${tickClass}`}
            >
              <div>
                
                {/* 1. CARD TOP: SYMBOL, NAME & TECHNICAL CHART BUTTON */}
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-2xl bg-gradient-to-tr ${colorClass} border flex items-center justify-center font-black text-xs font-mono shadow-inner`}>
                      {inst.symbol.substring(0, 3)}
                    </div>
                    <div>
                      <div className="flex items-center gap-1.5">
                        <h3 className="text-base font-extrabold text-white font-mono tracking-tight">
                          {inst.symbol}
                        </h3>
                        <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-white/[0.06] text-slate-400 border border-white/[0.08]">
                          EQ
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400 font-medium truncate max-w-[170px]">
                        {inst.name}
                      </p>
                    </div>
                  </div>

                  <button
                    onClick={() => onOpenChart(inst.symbol)}
                    className="p-2 rounded-xl bg-white/[0.04] border border-white/[0.08] hover:bg-sky-500/15 hover:border-sky-500/40 hover:text-sky-300 text-slate-400 transition-all flex items-center gap-1"
                    title="Open 5m Interactive Candlestick Chart"
                  >
                    <BarChart2 className="w-4 h-4" />
                    <span className="text-[10px] font-mono font-bold hidden sm:inline">5m Chart</span>
                  </button>
                </div>

                {/* 2. PRICE & LTP ROW (Tabular Numbers & Live Change Pill) */}
                <div className="mt-4 pt-3 border-t border-white/[0.06] flex items-baseline justify-between">
                  <div>
                    <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400">
                      Live Market Price (LTP)
                    </span>
                    <div className="text-2xl sm:text-3xl font-black font-mono text-white tracking-tight tabular-nums flex items-baseline gap-1">
                      <span>₹{inst.price.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                    </div>
                  </div>

                  <div className={`px-2.5 py-1 rounded-full font-mono text-xs font-extrabold flex items-center gap-1 border ${
                    isUp 
                      ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' 
                      : 'bg-rose-500/15 text-rose-400 border-rose-500/30'
                  }`}>
                    {isUp ? <ArrowUpRight className="w-3.5 h-3.5" /> : <ArrowDownRight className="w-3.5 h-3.5" />}
                    <span>{isUp ? '+' : ''}{inst.change_pct.toFixed(2)}%</span>
                  </div>
                </div>

                {/* 3. TRADE PROBABILITY SCORE (Compose CookBook Gauge Bar) */}
                <div className="mt-4 bg-[#0A0D15]/80 p-3 rounded-2xl border border-white/[0.06] space-y-2">
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="text-slate-400 flex items-center gap-1 font-bold">
                      <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                      Trade Probability Score
                    </span>
                    <div className="flex items-center gap-1.5">
                      <span className="text-sm font-black font-mono text-white tabular-nums">
                        {score}
                      </span>
                      <span className="text-[10px] text-slate-500">/ 100</span>
                    </div>
                  </div>

                  {/* Visual Progress Bar */}
                  <div className="w-full h-2 bg-slate-800/80 rounded-full overflow-hidden p-[1px] border border-white/[0.05]">
                    <div 
                      className={`h-full rounded-full bg-gradient-to-r ${scoreBarColor} transition-all duration-500 ease-out`}
                      style={{ width: `${Math.min(100, Math.max(5, score))}%` }}
                    />
                  </div>

                  <div className="flex items-center justify-between pt-0.5">
                    <span className={`px-2 py-0.5 rounded-md text-[10px] font-mono font-extrabold border ${scoreBadgeClass}`}>
                      {scoreLabel}
                    </span>
                    <span className="text-[10px] font-mono text-slate-400">
                      5x MIS: <strong className="text-slate-200">₹{(inst.price / 5).toFixed(1)}</strong> / share
                    </span>
                  </div>
                </div>

                {/* 4. NEXT ALGORITHMIC STEP RADAR BOX (Institutional Strategy State) */}
                <div className="mt-3.5 p-3 rounded-2xl bg-[#0F1422] border border-sky-500/20 shadow-inner">
                  <div className="flex items-center gap-1.5 text-[11px] font-mono font-bold text-sky-400 uppercase tracking-wider mb-1">
                    <Crosshair className="w-3.5 h-3.5 animate-spin-slow text-sky-400" />
                    <span>Next Algorithmic Step</span>
                  </div>
                  <p className="text-xs text-slate-200 leading-relaxed font-sans">
                    {inst.next_step || 'Scanning 5m candlestick price action for institutional confluence...'}
                  </p>
                </div>

              </div>

              {/* 5. CARD FOOTER: TECHNICAL METRICS (EMA9, VWAP, ATR) */}
              <div className="mt-4 pt-3 border-t border-white/[0.06] grid grid-cols-3 gap-2 text-center text-[10px] font-mono text-slate-400">
                <div className="bg-white/[0.02] p-1.5 rounded-xl border border-white/[0.04]">
                  <div className="text-slate-500">EMA 9</div>
                  <div className="text-slate-200 font-bold tabular-nums">
                    ₹{inst.ema9 ? inst.ema9.toFixed(2) : '--'}
                  </div>
                </div>
                <div className="bg-white/[0.02] p-1.5 rounded-xl border border-white/[0.04]">
                  <div className="text-slate-500">VWAP</div>
                  <div className="text-slate-200 font-bold tabular-nums">
                    ₹{inst.vwap ? inst.vwap.toFixed(2) : '--'}
                  </div>
                </div>
                <div className="bg-white/[0.02] p-1.5 rounded-xl border border-white/[0.04]">
                  <div className="text-slate-500">ATR(14)</div>
                  <div className="text-slate-200 font-bold tabular-nums">
                    ₹{inst.atr ? inst.atr.toFixed(2) : '--'}
                  </div>
                </div>
              </div>

            </div>
          );
        })}
      </div>

    </div>
  );
}
