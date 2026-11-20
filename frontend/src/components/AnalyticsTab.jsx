import React, { useState, useRef } from 'react';
import { 
  Download, 
  TrendingUp, 
  TrendingDown, 
  Calendar, 
  Receipt, 
  Award, 
  Percent,
  ChevronDown,
  ChevronUp,
  Clock,
  Layers,
  ShieldCheck,
  ShieldAlert,
  Activity
} from 'lucide-react';

export default function AnalyticsTab({ analyticsData, onExportCSV }) {
  const data = analyticsData || {};
  const dateGroups = data.date_groups || [];
  const totTrades = data.total_trades || 0;
  const winRate = data.win_rate || 0;
  const pf = data.profit_factor || 1.66;
  const totalPnl = data.total_pnl || 0;
  const totalR = data.total_r || 0;
  const totalCharges = data.total_charges || 0;
  const isProfit = totalPnl >= 0;

  const [expandedDates, setExpandedDates] = useState({});
  const toggleDate = (dt) => {
    setExpandedDates(prev => ({ ...prev, [dt]: !prev[dt] }));
  };

  // Derive Chronological Equity Curve & Governor Stats if not directly provided
  const points = React.useMemo(() => {
    if (data.equity_curve && Array.isArray(data.equity_curve) && data.equity_curve.length > 0) {
      return data.equity_curve;
    }

    // Client-side fallback derivation
    const pts = [{
      trade_num: 0,
      symbol: 'START',
      direction: '',
      trade_date: 'Start',
      time: '09:15',
      pnl: 0,
      r: 0,
      capital: 125000.0,
      cum_pnl: 0,
      cum_r: 0,
      drawdown_r: 0,
      peak_r: 0,
      governor_mode: 'NORMAL'
    }];

    const allTrades = [];
    const grpsCopy = [...dateGroups].reverse();
    grpsCopy.forEach(g => {
      if (g.trades) {
        g.trades.forEach(t => allTrades.push({ ...t, trade_date: g.date }));
      }
    });

    let cumP = 0;
    let cumR = 0;
    let peakR = 0;
    let maxDd = 0;
    let mode = 'NORMAL';

    allTrades.forEach((t, idx) => {
      const p = Number(t.realized_pnl || 0);
      const r = Number(t.realized_r !== undefined ? t.realized_r : (p / 200));
      cumP += p;
      cumR += r;
      if (cumR > peakR) peakR = cumR;
      const dd = cumR - peakR;
      if (dd < maxDd) maxDd = dd;

      if (mode === 'NORMAL' && dd <= -15.0) mode = 'DEFENSIVE';
      else if (mode === 'DEFENSIVE' && dd >= -5.0) mode = 'NORMAL';

      pts.push({
        trade_num: idx + 1,
        symbol: t.symbol || 'STOCK',
        direction: t.direction || 'BUY',
        trade_date: t.trade_date || '',
        time: t.exit_time || t.entry_time || '',
        pnl: Math.round(p * 100) / 100,
        r: Math.round(r * 100) / 100,
        capital: Math.round((125000.0 + cumP) * 100) / 100,
        cum_pnl: Math.round(cumP * 100) / 100,
        cum_r: Math.round(cumR * 100) / 100,
        drawdown_r: Math.round(dd * 100) / 100,
        peak_r: Math.round(peakR * 100) / 100,
        governor_mode: mode
      });
    });

    return pts;
  }, [data.equity_curve, dateGroups]);

  const govStats = React.useMemo(() => {
    if (data.governor_stats) return data.governor_stats;

    const lastPt = points[points.length - 1];
    const minDd = Math.min(...points.map(p => p.drawdown_r), 0);
    const currDd = lastPt ? lastPt.drawdown_r : 0;
    const trough = Math.abs(minDd) > 5.0 ? Math.abs(minDd) : 5.0;
    const currDdAbs = Math.abs(currDd);
    const recoveredR = Math.max(0, trough - currDdAbs);
    const totalSpan = Math.max(0.1, trough - 5.0);
    const recPct = Math.round(Math.min(100, Math.max(0, (recoveredR / totalSpan) * 100)) * 10) / 10;
    const distToNormal = Math.round(Math.max(0, currDdAbs - 5.0) * 100) / 100;
    const mode = lastPt ? lastPt.governor_mode : 'NORMAL';

    return {
      mode: mode,
      multiplier: mode === 'DEFENSIVE' ? 0.5 : 1.0,
      current_drawdown_r: currDd,
      max_drawdown_r: Math.round(minDd * 100) / 100,
      peak_realized_r: lastPt ? lastPt.peak_r : 0,
      effective_risk: mode === 'DEFENSIVE' ? 100.0 : 200.0,
      defense_threshold_r: -15.0,
      recovery_threshold_r: -5.0,
      distance_to_normal_r: distToNormal,
      recovery_pct: recPct
    };
  }, [data.governor_stats, points]);

  // SVG Hover States
  const [hoverEquity, setHoverEquity] = useState(null);
  const [hoverDd, setHoverDd] = useState(null);
  const equityContainerRef = useRef(null);
  const ddContainerRef = useRef(null);

  // SVG Dimensions & Math
  const W = 800;
  const H_EQ = 220;
  const H_DD = 240;
  const pad = { top: 25, right: 30, bottom: 35, left: 70 };
  const plotW = W - pad.left - pad.right;
  const plotH_EQ = H_EQ - pad.top - pad.bottom;
  const plotH_DD = H_DD - pad.top - pad.bottom;

  // Equity calculations
  const capitals = points.map(p => p.capital);
  const minCap = Math.floor((Math.min(...capitals, 125000) - 300) / 500) * 500;
  const maxCap = Math.ceil((Math.max(...capitals, 125000) + 300) / 500) * 500;
  const peakCapital = Math.max(...capitals);
  const latestPt = points[points.length - 1];

  const getEqX = (i) => pad.left + (points.length === 1 ? plotW / 2 : (i / (points.length - 1)) * plotW);
  const getEqY = (val) => pad.top + plotH_EQ - ((val - minCap) / (maxCap - minCap)) * plotH_EQ;
  const yEqBase = getEqY(125000.0);

  let eqPathD = `M ${getEqX(0)},${getEqY(points[0].capital)}`;
  for (let i = 1; i < points.length; i++) {
    eqPathD += ` L ${getEqX(i)},${getEqY(points[i].capital)}`;
  }
  const eqAreaD = `${eqPathD} L ${getEqX(points.length - 1)},${pad.top + plotH_EQ} L ${getEqX(0)},${pad.top + plotH_EQ} Z`;

  // Drawdown calculations
  const minDrawdown = Math.min(...points.map(p => p.drawdown_r), govStats.max_drawdown_r || -16.0);
  const yMinDd = Math.min(minDrawdown, -17.0) - 2.5;
  const yMaxDd = 1.0;

  const getDdX = (i) => pad.left + (points.length === 1 ? plotW / 2 : (i / (points.length - 1)) * plotW);
  const getDdY = (dd) => pad.top + ((yMaxDd - dd) / (yMaxDd - yMinDd)) * plotH_DD;

  const yDdZero = getDdY(0.0);
  const yDdNormal = getDdY(-5.0);
  const yDdDefensive = getDdY(-15.0);
  const yDdBottom = pad.top + plotH_DD;

  let ddPathD = `M ${getDdX(0)},${getDdY(points[0].drawdown_r)}`;
  for (let i = 1; i < points.length; i++) {
    ddPathD += ` L ${getDdX(i)},${getDdY(points[i].drawdown_r)}`;
  }
  const ddAreaD = `${ddPathD} L ${getDdX(points.length - 1)},${yDdZero} L ${getDdX(0)},${yDdZero} Z`;

  // Trough Index
  let troughIdx = 0;
  let minDdVal = points[0].drawdown_r;
  points.forEach((p, idx) => {
    if (p.drawdown_r < minDdVal) {
      minDdVal = p.drawdown_r;
      troughIdx = idx;
    }
  });

  const handleEquityHover = (clientX) => {
    if (!equityContainerRef.current) return;
    const rect = equityContainerRef.current.getBoundingClientRect();
    const offsetX = clientX - rect.left;
    const normX = (offsetX / rect.width) * W;
    const clampedX = Math.min(W - pad.right, Math.max(pad.left, normX));
    const ratio = (clampedX - pad.left) / plotW;
    const idx = Math.min(points.length - 1, Math.max(0, Math.round(ratio * (points.length - 1))));
    setHoverEquity({
      point: points[idx],
      x: getEqX(idx),
      y: getEqY(points[idx].capital),
      pctX: (getEqX(idx) / W) * 100
    });
  };

  const handleDdHover = (clientX) => {
    if (!ddContainerRef.current) return;
    const rect = ddContainerRef.current.getBoundingClientRect();
    const offsetX = clientX - rect.left;
    const normX = (offsetX / rect.width) * W;
    const clampedX = Math.min(W - pad.right, Math.max(pad.left, normX));
    const ratio = (clampedX - pad.left) / plotW;
    const idx = Math.min(points.length - 1, Math.max(0, Math.round(ratio * (points.length - 1))));
    setHoverDd({
      point: points[idx],
      x: getDdX(idx),
      y: getDdY(points[idx].drawdown_r),
      pctX: (getDdX(idx) / W) * 100
    });
  };

  return (
    <div className="space-y-4 pb-12">
      
      {/* SECTION HEADER & EXPORT CSV BUTTON */}
      <div className="flex items-center justify-between px-1 pt-1 pb-2 border-b border-white/[0.08] flex-wrap gap-2">
        <div className="flex items-center gap-2.5">
          <h2 className="text-xs sm:text-sm font-black tracking-tight text-white font-mono uppercase flex items-center gap-2">
            <span>Institutional Ledger</span>
            <span className="px-2 py-0.5 text-[10px] font-mono font-extrabold bg-sky-500/20 text-sky-300 rounded-full border border-sky-500/30">
              {totTrades} Closed Trades
            </span>
          </h2>
        </div>

        <button
          onClick={onExportCSV}
          className="px-3 py-1.5 rounded-xl bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/40 text-emerald-300 text-xs font-bold font-mono flex items-center gap-1.5 transition-all cursor-pointer shadow-md glow-emerald"
        >
          <Download className="w-3.5 h-3.5 text-emerald-400" />
          <span>Export Master CSV</span>
        </button>
      </div>

      {/* METRIC SUMMARY CARDS (Bento 4-Column Grid) */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        
        {/* 1. Net Realized P&L */}
        <div className="bento-card p-3.5 flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
            <span>Net Realized P&L</span>
            {isProfit ? <TrendingUp className="w-4 h-4 text-emerald-400" /> : <TrendingDown className="w-4 h-4 text-rose-400" />}
          </div>
          <div className="mt-2 font-mono">
            <span className={`text-lg sm:text-xl font-black tabular-nums tracking-tight ${isProfit ? 'text-emerald-400' : 'text-rose-400'}`}>
              {isProfit ? '+' : ''}₹{totalPnl.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
          </div>
          <div className="mt-1 flex items-center justify-between text-[10px] font-mono font-bold text-slate-400">
            <span>{isProfit ? '+' : ''}{totalR.toFixed(2)} R Total</span>
            <span className="text-slate-500">Net of All Fees</span>
          </div>
        </div>

        {/* 2. Win Rate */}
        <div className="bento-card p-3.5 flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
            <span>Win Rate</span>
            <Percent className="w-4 h-4 text-sky-400" />
          </div>
          <div className="mt-2 font-mono">
            <span className="text-lg sm:text-xl font-black text-white tabular-nums tracking-tight">
              {winRate.toFixed(1)}%
            </span>
          </div>
          <div className="mt-1 flex items-center justify-between text-[10px] font-mono font-bold text-slate-400">
            <span className="text-emerald-400">{data.wins || 0} Wins</span>
            <span className="text-slate-500">/</span>
            <span className="text-rose-400">{data.losses || 0} Losses</span>
          </div>
        </div>

        {/* 3. Profit Factor */}
        <div className="bento-card p-3.5 flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
            <span>Profit Factor</span>
            <Award className="w-4 h-4 text-amber-400" />
          </div>
          <div className="mt-2 font-mono">
            <span className="text-lg sm:text-xl font-black text-amber-400 tabular-nums tracking-tight">
              {pf.toFixed(2)}
            </span>
          </div>
          <div className="mt-1 flex items-center justify-between text-[10px] font-mono font-bold text-slate-400">
            <span className="text-amber-400">1:2 RRR Edge</span>
            <span className="text-slate-500">Edge</span>
          </div>
        </div>

        {/* 4. Statutory Friction */}
        <div className="bento-card p-3.5 flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
            <span>Statutory Friction</span>
            <Receipt className="w-4 h-4 text-slate-400" />
          </div>
          <div className="mt-2 font-mono">
            <span className="text-lg sm:text-xl font-black text-slate-300 tabular-nums tracking-tight">
              ₹{totalCharges.toFixed(2)}
            </span>
          </div>
          <div className="mt-1 flex items-center justify-between text-[10px] font-mono font-bold text-slate-400">
            <span>STT, GST, SEBI</span>
            <span className="text-slate-500">Brokerage</span>
          </div>
        </div>

      </div>

      {/* DUAL VISUAL CURVES: CAPITAL EQUITY & DYNAMIC RISK GOVERNOR DRAWDOWN */}
      <div className="space-y-4 pt-1">
        
        {/* CURVE 1: CAPITAL EQUITY GROWTH CURVE */}
        <div className="bento-card p-4 rounded-2xl relative overflow-hidden border border-white/10 shadow-xl bg-gradient-to-b from-[#0E1426] to-[#090E1D]">
          <div className="flex items-start justify-between flex-wrap gap-2 pb-2.5 border-b border-white/5">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shadow-[0_0_12px_rgba(16,185,129,0.25)] flex-shrink-0">
                <TrendingUp className="w-4 h-4" />
              </div>
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs font-black text-white font-mono uppercase tracking-wider">Capital Equity Growth Curve</span>
                  <span className="px-2 py-0.5 rounded-full text-[8.5px] font-mono font-extrabold bg-sky-500/15 text-sky-300 border border-sky-500/30">
                    {points.length - 1} Executions
                  </span>
                </div>
                <span className="text-[9.5px] text-slate-400 font-mono block mt-0.5">Cumulative Demat account balance &amp; cumulative R trajectory</span>
              </div>
            </div>
            
            <div className="flex items-center gap-2 text-right font-mono flex-wrap">
              <div className="bg-slate-800/60 px-2.5 py-1 rounded-xl border border-white/5">
                <span className="text-[8px] text-slate-400 block font-bold uppercase">Initial Capital</span>
                <span className="text-[11px] font-black text-slate-300">₹1,25,000</span>
              </div>
              <div className="bg-slate-800/60 px-2.5 py-1 rounded-xl border border-white/5">
                <span className="text-[8px] text-slate-400 block font-bold uppercase">Current Equity</span>
                <span className={`text-[11px] font-black ${latestPt.capital >= 125000 ? 'text-emerald-400' : 'text-amber-400'}`}>
                  ₹{latestPt.capital.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
              </div>
              <div className="bg-slate-800/60 px-2.5 py-1 rounded-xl border border-white/5">
                <span className="text-[8px] text-slate-400 block font-bold uppercase">All-Time Peak</span>
                <span className="text-[11px] font-black text-emerald-400">
                  ₹{peakCapital.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
              </div>
            </div>
          </div>

          {/* Equity SVG Canvas with Interactive Cursor & Tooltip */}
          <div 
            ref={equityContainerRef}
            onMouseMove={(e) => handleEquityHover(e.clientX)}
            onMouseLeave={() => setHoverEquity(null)}
            onTouchMove={(e) => e.touches?.[0] && handleEquityHover(e.touches[0].clientX)}
            onTouchEnd={() => setHoverEquity(null)}
            className="relative w-full h-48 sm:h-56 mt-2.5 select-none"
          >
            <svg viewBox={`0 0 ${W} ${H_EQ}`} className="w-full h-full overflow-visible" preserveAspectRatio="none">
              <defs>
                <linearGradient id="reactEqGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={latestPt.capital >= 125000 ? 'rgba(16, 185, 129, 0.35)' : 'rgba(56, 189, 248, 0.30)'} />
                  <stop offset="100%" stopColor="rgba(14, 20, 38, 0)" />
                </linearGradient>
                <filter id="reactEqGlow" x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="3" result="blur" />
                  <feComposite in="SourceGraphic" in2="blur" operator="over" />
                </filter>
              </defs>

              {/* Grid Lines */}
              {[0, 1, 2, 3, 4].map(g => {
                const val = minCap + (g / 4) * (maxCap - minCap);
                const yPos = getEqY(val);
                return (
                  <g key={g}>
                    <line x1={pad.left} y1={yPos} x2={W - pad.right} y2={yPos} stroke="rgba(255, 255, 255, 0.05)" strokeWidth="1" strokeDasharray="4,4" />
                    <text x={pad.left - 8} y={yPos + 3.5} fill="#64748B" fontSize="9" fontFamily="'JetBrains Mono', monospace" textAnchor="end">
                      ₹{Math.round(val).toLocaleString('en-IN')}
                    </text>
                  </g>
                );
              })}

              {/* Baseline */}
              <line x1={pad.left} y1={yEqBase} x2={W - pad.right} y2={yEqBase} stroke="rgba(56, 189, 248, 0.35)" strokeWidth="1.5" strokeDasharray="5,4" />
              <text x={W - pad.right} y={yEqBase - 6} fill="#38BDF8" fontSize="8.5" fontWeight="bold" fontFamily="'JetBrains Mono', monospace" textAnchor="end">
                START BASELINE (₹1,25,000)
              </text>

              {/* Area & Line */}
              <path d={eqAreaD} fill="url(#reactEqGrad)" />
              <path d={eqPathD} fill="none" stroke={latestPt.capital >= 125000 ? '#10B981' : '#38BDF8'} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" filter="url(#reactEqGlow)" />

              {/* Current Point Marker */}
              <circle cx={getEqX(points.length - 1)} cy={getEqY(latestPt.capital)} r="5" fill="#38BDF8" stroke="#FFFFFF" strokeWidth="2" />

              {/* Hover Crosshair */}
              {hoverEquity && (
                <g>
                  <line x1={hoverEquity.x} y1={pad.top} x2={hoverEquity.x} y2={pad.top + plotH_EQ} stroke="rgba(56, 189, 248, 0.7)" strokeWidth="1.5" strokeDasharray="3,3" />
                  <circle cx={hoverEquity.x} cy={hoverEquity.y} r="5" fill="#38BDF8" stroke="#FFFFFF" strokeWidth="2" />
                </g>
              )}
            </svg>

            {/* Hover Tooltip */}
            {hoverEquity && (
              <div 
                className="absolute pointer-events-none z-30 bg-[#0E1426]/95 backdrop-blur-md border border-sky-500/40 rounded-xl p-2.5 shadow-2xl text-[9.5px] font-mono space-y-0.5"
                style={{
                  top: '10px',
                  left: `clamp(10px, ${hoverEquity.pctX}% - 100px, calc(100% - 210px))`
                }}
              >
                <div className="flex items-center justify-between border-b border-white/10 pb-1 gap-3">
                  <span className="text-white font-black">Trade #{hoverEquity.point.trade_num} • {hoverEquity.point.symbol || 'START'} {hoverEquity.point.direction ? `(${hoverEquity.point.direction})` : ''}</span>
                  <span className={`px-1.5 py-0.2 rounded text-[8px] font-bold ${hoverEquity.point.governor_mode === 'DEFENSIVE' ? 'bg-amber-500/20 text-amber-400' : 'bg-emerald-500/20 text-emerald-400'}`}>
                    {hoverEquity.point.governor_mode || 'NORMAL'}
                  </span>
                </div>
                <div className="flex items-center justify-between text-slate-300 gap-3">
                  <span className="text-slate-400">Capital:</span>
                  <span className={`font-black ${hoverEquity.point.capital >= 125000 ? 'text-emerald-400' : 'text-amber-400'}`}>
                    ₹{hoverEquity.point.capital.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </span>
                </div>
                <div className="flex items-center justify-between text-slate-300 gap-3">
                  <span className="text-slate-400">Trade P&amp;L:</span>
                  <span className={`font-bold ${hoverEquity.point.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {hoverEquity.point.pnl >= 0 && hoverEquity.point.trade_num > 0 ? '+' : ''}₹{hoverEquity.point.pnl.toFixed(2)} ({hoverEquity.point.r >= 0 && hoverEquity.point.trade_num > 0 ? '+' : ''}{hoverEquity.point.r.toFixed(2)}R)
                  </span>
                </div>
                <div className="flex items-center justify-between text-slate-300 gap-3">
                  <span className="text-slate-400">Cumulative R:</span>
                  <span className="font-bold text-slate-200">{hoverEquity.point.cum_r >= 0 ? '+' : ''}{hoverEquity.point.cum_r.toFixed(2)}R</span>
                </div>
                <div className="text-[8px] text-slate-500 pt-0.5">{hoverEquity.point.trade_date} {hoverEquity.point.time || ''}</div>
              </div>
            )}
          </div>
        </div>

        {/* CURVE 2: DYNAMIC RISK GOVERNOR & DRAWDOWN RECOVERY CURVE */}
        <div className="bento-card p-4 rounded-2xl relative overflow-hidden border border-white/10 shadow-xl bg-gradient-to-b from-[#0E1426] to-[#090E1D]">
          <div className="flex items-start justify-between flex-wrap gap-2 pb-2.5 border-b border-white/5">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400 shadow-[0_0_12px_rgba(245,158,11,0.25)] flex-shrink-0">
                <ShieldAlert className="w-4 h-4" />
              </div>
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs font-black text-white font-mono uppercase tracking-wider">Dynamic Risk Governor &amp; Drawdown</span>
                  <span className={`px-2 py-0.5 rounded-full text-[8.5px] font-mono font-extrabold border ${
                    govStats.mode === 'DEFENSIVE' 
                      ? 'bg-amber-500/20 text-amber-400 border-amber-500/40 animate-pulse' 
                      : 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40'
                  }`}>
                    {govStats.mode === 'DEFENSIVE' ? 'DEFENSIVE (0.5R Risk)' : 'NORMAL (1.0R Risk)'}
                  </span>
                </div>
                <span className="text-[9.5px] text-slate-400 font-mono block mt-0.5">Peak-to-trough R-drawdown, Normal mode (&gt; -5.0R) recovery &amp; Defensive circuit breaker (&lt; -15.0R)</span>
              </div>
            </div>

            <div className="flex items-center gap-2 text-right font-mono flex-wrap">
              <div className="bg-slate-800/60 px-2.5 py-1 rounded-xl border border-white/5">
                <span className="text-[8px] text-slate-400 block font-bold uppercase">Current Drawdown</span>
                <span className={`text-[11px] font-black ${govStats.current_drawdown_r >= -5.0 ? 'text-emerald-400' : (govStats.current_drawdown_r <= -15.0 ? 'text-rose-400' : 'text-amber-400')}`}>
                  {govStats.current_drawdown_r >= 0 ? '+' : ''}{govStats.current_drawdown_r.toFixed(2)} R
                </span>
              </div>
              <div className="bg-slate-800/60 px-2.5 py-1 rounded-xl border border-white/5">
                <span className="text-[8px] text-slate-400 block font-bold uppercase">Peak Trough</span>
                <span className="text-[11px] font-black text-rose-500">{govStats.max_drawdown_r.toFixed(2)} R</span>
              </div>
              <div className="bg-slate-800/60 px-2.5 py-1 rounded-xl border border-white/5">
                <span className="text-[8px] text-slate-400 block font-bold uppercase">Normal Recovery Line</span>
                <span className="text-[11px] font-black text-sky-400">-5.00 R</span>
              </div>
            </div>
          </div>

          {/* Recovery Progress Telemetry Bar */}
          <div className="mt-2.5 p-2.5 rounded-xl bg-slate-800/40 border border-white/5 space-y-1.5 font-mono">
            <div className="flex items-center justify-between text-[9.5px]">
              <span className="text-slate-300 font-bold flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-sky-400 animate-ping"></span>
                <span>Governor Recovery Progress to Normal Mode (1.0R):</span>
                <span className="text-sky-400 font-black">{govStats.recovery_pct || 0}%</span>
              </span>
              <span className="text-slate-400">
                {govStats.distance_to_normal_r > 0 
                  ? `Gap: ${govStats.distance_to_normal_r.toFixed(2)} R (~₹${Math.round(govStats.distance_to_normal_r * 200)})`
                  : 'Normal 1.0R Mode Restored'}
              </span>
            </div>
            <div className="w-full bg-slate-800/80 rounded-full h-2 overflow-hidden p-0.5 border border-white/10">
              <div 
                className="h-full rounded-full bg-gradient-to-r from-amber-500 via-sky-400 to-emerald-400 transition-all duration-500 shadow-[0_0_8px_rgba(56,189,248,0.5)]" 
                style={{ width: `${Math.min(100, Math.max(0, govStats.recovery_pct || 0))}%` }}
              />
            </div>
            <div className="flex items-center justify-between text-[8px] text-slate-400">
              <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-rose-500"></span> Trough: <strong>{govStats.max_drawdown_r.toFixed(2)} R</strong></span>
              <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-sky-400"></span> Normal Threshold: <strong>-5.00 R</strong></span>
              <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> Peak HWM: <strong>0.00 R</strong></span>
            </div>
          </div>

          {/* Drawdown SVG Canvas with Visual Bands & Tooltip */}
          <div 
            ref={ddContainerRef}
            onMouseMove={(e) => handleDdHover(e.clientX)}
            onMouseLeave={() => setHoverDd(null)}
            onTouchMove={(e) => e.touches?.[0] && handleDdHover(e.touches[0].clientX)}
            onTouchEnd={() => setHoverDd(null)}
            className="relative w-full h-52 sm:h-60 mt-2.5 select-none"
          >
            <svg viewBox={`0 0 ${W} ${H_DD}`} className="w-full h-full overflow-visible" preserveAspectRatio="none">
              <defs>
                <linearGradient id="reactDdAreaGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="rgba(245, 158, 11, 0.02)" />
                  <stop offset="100%" stopColor="rgba(245, 158, 11, 0.25)" />
                </linearGradient>
                <filter id="reactDdGlow" x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="3" result="blur" />
                  <feComposite in="SourceGraphic" in2="blur" operator="over" />
                </filter>
              </defs>

              {/* Shaded Zones */}
              <rect x={pad.left} y={yDdZero} width={plotW} height={Math.max(0, yDdNormal - yDdZero)} fill="rgba(16, 185, 129, 0.07)" />
              <text x={pad.left + 8} y={yDdZero + 14} fill="rgba(16, 185, 129, 0.8)" fontSize="8.5" fontWeight="bold" fontFamily="'JetBrains Mono', monospace">
                NORMAL 1.0R RISK ZONE (Drawdown &gt; -5.0R)
              </text>

              <rect x={pad.left} y={yDdNormal} width={plotW} height={Math.max(0, yDdDefensive - yDdNormal)} fill="rgba(245, 158, 11, 0.07)" />
              <text x={pad.left + 8} y={yDdNormal + 14} fill="rgba(245, 158, 11, 0.8)" fontSize="8.5" fontWeight="bold" fontFamily="'JetBrains Mono', monospace">
                DEFENSIVE 0.5R RISK ZONE (Recovery in Progress)
              </text>

              <rect x={pad.left} y={yDdDefensive} width={plotW} height={Math.max(0, yDdBottom - yDdDefensive)} fill="rgba(255, 51, 102, 0.08)" />
              <text x={pad.left + 8} y={yDdDefensive + 14} fill="rgba(255, 51, 102, 0.85)" fontSize="8.5" fontWeight="bold" fontFamily="'JetBrains Mono', monospace">
                CIRCUIT BREAKER TRIGGER ZONE (&lt; -15.0R)
              </text>

              {/* Threshold Lines */}
              <line x1={pad.left} y1={yDdZero} x2={W - pad.right} y2={yDdZero} stroke="rgba(255, 255, 255, 0.25)" strokeWidth="1.2" strokeDasharray="4,4" />
              <text x={pad.left - 8} y={yDdZero + 3.5} fill="#94A3B8" fontSize="9" fontFamily="'JetBrains Mono', monospace" textAnchor="end">0.0 R</text>
              <text x={W - pad.right} y={yDdZero - 5} fill="#94A3B8" fontSize="8" fontFamily="'JetBrains Mono', monospace" textAnchor="end">PEAK HIGH-WATER MARK</text>

              <line x1={pad.left} y1={yDdNormal} x2={W - pad.right} y2={yDdNormal} stroke="#38BDF8" strokeWidth="1.8" strokeDasharray="5,4" />
              <text x={pad.left - 8} y={yDdNormal + 3.5} fill="#38BDF8" fontSize="9" fontWeight="bold" fontFamily="'JetBrains Mono', monospace" textAnchor="end">-5.0 R</text>
              <text x={W - pad.right} y={yDdNormal - 5} fill="#38BDF8" fontSize="8.5" fontWeight="bold" fontFamily="'JetBrains Mono', monospace" textAnchor="end">▲ NORMAL 1.0R RESTORATION LINE (-5.00 R)</text>

              <line x1={pad.left} y1={yDdDefensive} x2={W - pad.right} y2={yDdDefensive} stroke="#FF3366" strokeWidth="1.8" strokeDasharray="5,4" />
              <text x={pad.left - 8} y={yDdDefensive + 3.5} fill="#FF3366" fontSize="9" fontWeight="bold" fontFamily="'JetBrains Mono', monospace" textAnchor="end">-15.0 R</text>
              <text x={W - pad.right} y={yDdDefensive - 5} fill="#FF3366" fontSize="8.5" fontWeight="bold" fontFamily="'JetBrains Mono', monospace" textAnchor="end">▼ DEFENSIVE 0.5R CIRCUIT BREAKER TRIGGER (-15.00 R)</text>

              {/* Drawdown Area & Line */}
              <path d={ddAreaD} fill="url(#reactDdAreaGrad)" />
              <path d={ddPathD} fill="none" stroke="#F59E0B" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" filter="url(#reactDdGlow)" />

              {/* Peak Trough Marker */}
              <circle cx={getDdX(troughIdx)} cy={getDdY(minDdVal)} r="5" fill="#FF3366" stroke="#FFFFFF" strokeWidth="2" />
              <circle cx={getDdX(troughIdx)} cy={getDdY(minDdVal)} r="9" fill="none" stroke="#FF3366" strokeWidth="1.5" opacity="0.8" />
              <text x={getDdX(troughIdx)} y={getDdY(minDdVal) + 16} fill="#FF3366" fontSize="8.5" fontWeight="bold" fontFamily="'JetBrains Mono', monospace" textAnchor="middle">
                TROUGH: {minDdVal.toFixed(2)}R
              </text>

              {/* Current Point Marker */}
              <circle cx={getDdX(points.length - 1)} cy={getDdY(latestPt.drawdown_r)} r="5" fill="#38BDF8" stroke="#FFFFFF" strokeWidth="2" />

              {/* Hover Crosshair */}
              {hoverDd && (
                <g>
                  <line x1={hoverDd.x} y1={pad.top} x2={hoverDd.x} y2={pad.top + plotH_DD} stroke="rgba(245, 158, 11, 0.8)" strokeWidth="1.5" strokeDasharray="3,3" />
                  <circle cx={hoverDd.x} cy={hoverDd.y} r="5" fill="#F59E0B" stroke="#FFFFFF" strokeWidth="2" />
                </g>
              )}
            </svg>

            {/* Hover Tooltip */}
            {hoverDd && (
              <div 
                className="absolute pointer-events-none z-30 bg-[#0E1426]/95 backdrop-blur-md border border-amber-500/40 rounded-xl p-2.5 shadow-2xl text-[9.5px] font-mono space-y-0.5"
                style={{
                  top: '10px',
                  left: `clamp(10px, ${hoverDd.pctX}% - 105px, calc(100% - 220px))`
                }}
              >
                <div className="flex items-center justify-between border-b border-white/10 pb-1 gap-3">
                  <span className="text-white font-black">Trade #{hoverDd.point.trade_num} • {hoverDd.point.symbol || 'START'}</span>
                  <span className={`px-1.5 py-0.2 rounded text-[8px] font-bold ${hoverDd.point.governor_mode === 'NORMAL' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400'}`}>
                    {hoverDd.point.governor_mode || 'NORMAL'} ({hoverDd.point.governor_mode === 'NORMAL' ? '1.0R' : '0.5R'})
                  </span>
                </div>
                <div className="flex items-center justify-between text-slate-300 gap-3">
                  <span className="text-slate-400">R-Drawdown:</span>
                  <span className={`font-black ${hoverDd.point.drawdown_r >= -5.0 ? 'text-emerald-400' : (hoverDd.point.drawdown_r <= -15.0 ? 'text-rose-400' : 'text-amber-400')}`}>
                    {hoverDd.point.drawdown_r.toFixed(2)} R
                  </span>
                </div>
                <div className="flex items-center justify-between text-slate-300 gap-3">
                  <span className="text-slate-400">Capital Value:</span>
                  <span className="font-bold text-white">₹{hoverDd.point.capital.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                </div>
                <div className="flex items-center justify-between text-slate-300 gap-3">
                  <span className="text-slate-400">Return to Normal:</span>
                  <span className="font-bold text-sky-400">
                    {Math.abs(hoverDd.point.drawdown_r) <= 5.0 ? 'Normal Mode Active' : `Need +${(Math.abs(hoverDd.point.drawdown_r) - 5.0).toFixed(2)} R (~₹${Math.round((Math.abs(hoverDd.point.drawdown_r) - 5.0) * 200)})`}
                  </span>
                </div>
                <div className="text-[8px] text-slate-500 pt-0.5">{hoverDd.point.trade_date} {hoverDd.point.time || ''}</div>
              </div>
            )}
          </div>
        </div>

      </div>

      {/* DATE-GROUPED TRADE HISTORY */}
      <div className="space-y-3 pt-2">
        <h3 className="text-xs font-black tracking-wider text-slate-400 font-mono uppercase px-1">
          Historical Trade Sessions
        </h3>

        {dateGroups.length === 0 ? (
          <div className="bento-card p-8 text-center text-slate-400 font-mono text-xs">
            No closed trades in database. All new executions will populate here with full tick metrics.
          </div>
        ) : (
          dateGroups.map((grp) => {
            const grpPnl = grp.day_pnl !== undefined ? grp.day_pnl : (grp.total_pnl || 0);
            const isGrpProfit = grpPnl >= 0;
            const isExpanded = expandedDates[grp.date] !== false;

            return (
              <div key={grp.date} className="bento-card overflow-hidden">
                
                {/* DATE GROUP HEADER BAR */}
                <div 
                  onClick={() => toggleDate(grp.date)}
                  className="bg-[#0B0F19] p-3 sm:px-4 flex items-center justify-between cursor-pointer hover:bg-white/[0.02] transition-colors border-b border-white/[0.06]"
                >
                  <div className="flex items-center gap-2 sm:gap-3">
                    <Calendar className="w-4 h-4 text-sky-400 flex-shrink-0" />
                    <span className="text-xs sm:text-sm font-black font-mono text-white">
                      {grp.date}
                    </span>
                    <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-white/[0.08] text-slate-300">
                      {grp.trades?.length || 0} Trades
                    </span>
                  </div>

                  <div className="flex items-center gap-3">
                    <span className={`text-xs sm:text-sm font-black font-mono tabular-nums ${
                      isGrpProfit ? 'text-emerald-400' : 'text-rose-400'
                    }`}>
                      {isGrpProfit ? '+' : ''}₹{grpPnl.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                    {isExpanded ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
                  </div>
                </div>

                {/* INDIVIDUAL TRADE ROWS */}
                {isExpanded && (
                  <div className="divide-y divide-white/[0.05]">
                    {grp.trades.map((t) => {
                      const isTradeProfit = (t.realized_pnl || 0) >= 0;
                      const isLong = t.direction === 'BUY';

                      let exitBadgeStyle = "bg-slate-800 text-slate-300 border-slate-700";
                      if (t.exit_reason === 'TARGET_REACHED' || t.exit_reason === 'TARGET') {
                        exitBadgeStyle = "bg-emerald-500/20 text-emerald-300 border-emerald-500/40";
                      } else if (t.exit_reason === 'STOP_LOSS_HIT' || t.exit_reason === 'STOP_LOSS') {
                        exitBadgeStyle = "bg-rose-500/20 text-rose-300 border-rose-500/40";
                      } else if (t.exit_reason?.includes('EOD')) {
                        exitBadgeStyle = "bg-amber-500/20 text-amber-300 border-amber-500/40";
                      }

                      return (
                        <div key={t.id} className="p-3 sm:px-4 flex items-center justify-between hover:bg-white/[0.015] transition-colors text-xs font-mono">
                          
                          {/* Left: Symbol, Direction, Timestamps */}
                          <div className="space-y-0.5">
                            <div className="flex items-center gap-2">
                              <span className="font-black text-white text-sm">{t.symbol}</span>
                              <span className={`px-1.5 py-0.2 rounded text-[9px] font-black border ${
                                isLong ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' : 'bg-rose-500/15 text-rose-400 border-rose-500/30'
                              }`}>
                                {t.direction}
                              </span>
                              <span className={`px-2 py-0.2 rounded-full text-[9px] font-bold border ${exitBadgeStyle}`}>
                                {t.exit_reason}
                              </span>
                            </div>
                            <div className="flex items-center gap-2 text-[10px] text-slate-400 flex-wrap">
                              <span className="text-sky-400 font-semibold">In: {t.entry_time?.includes('IST') ? t.entry_time : `${t.entry_time} IST`}</span>
                              <span>•</span>
                              <span className="text-amber-400 font-semibold">Out: {t.exit_time?.includes('IST') ? t.exit_time : `${t.exit_time} IST`}</span>
                              <span>•</span>
                              <span>Buy: <strong className="text-slate-200">₹{(t.direction === 'BUY' ? t.entry_price : t.exit_price)?.toFixed(2)}</strong> • Sell: <strong className="text-slate-200">₹{(t.direction === 'BUY' ? t.exit_price : t.entry_price)?.toFixed(2)}</strong></span>
                            </div>
                          </div>

                          {/* Right: Net P&L & R-Multiple */}
                          <div className="text-right">
                            <div className={`font-black text-sm tabular-nums ${isTradeProfit ? 'text-emerald-400' : 'text-rose-400'}`}>
                              {isTradeProfit ? '+' : ''}₹{(t.realized_pnl || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </div>
                            <div className={`text-[10px] font-bold ${isTradeProfit ? 'text-emerald-400' : 'text-rose-400'}`}>
                              {isTradeProfit ? '+' : ''}{(t.realized_r || 0).toFixed(2)} R
                            </div>
                          </div>

                        </div>
                      );
                    })}
                  </div>
                )}

              </div>
            );
          })
        )}
      </div>

    </div>
  );
}
