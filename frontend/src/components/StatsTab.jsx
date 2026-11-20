import React, { useState, useRef, useMemo } from 'react';
import { 
  TrendingUp, 
  ShieldAlert, 
  Activity,
  RefreshCw,
  Zap
} from 'lucide-react';

export default function StatsTab({ analyticsData, onRefresh }) {
  const data = analyticsData || {};
  const dateGroups = data.date_groups || [];

  // Derive Chronological Equity Curve & Governor Stats if not directly provided
  const points = useMemo(() => {
    if (data.equity_curve && Array.isArray(data.equity_curve) && data.equity_curve.length > 0) {
      return data.equity_curve;
    }

    // Fallback derivation
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

  const govStats = useMemo(() => {
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
  const W = 1000;
  const H_EQ = 240;
  const H_DD = 280;
  const pad = { top: 25, right: 30, bottom: 30, left: 65 };
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

  // Peak Trough Index
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
    <div className="space-y-4 pb-12 w-full max-w-full">
      
      {/* SECTION HEADER BAR */}
      <div className="flex items-center justify-between pb-2 border-b border-white/[0.08] flex-wrap gap-2 px-1">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-sky-500/20 to-blue-500/20 border border-sky-400/30 flex items-center justify-center text-sky-300 shadow-[0_0_12px_rgba(56,189,248,0.25)] flex-shrink-0">
            <Activity className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-xs sm:text-sm font-black text-white font-mono uppercase tracking-wider">
                Institutional Quant Stats &amp; Risk Governor
              </h2>
              <span className="px-2 py-0.5 rounded-full text-[9px] font-mono font-extrabold bg-sky-500/15 text-sky-300 border border-sky-500/30">
                Full-Width Dual Terminal
              </span>
            </div>
            <span className="text-[9.5px] text-slate-400 font-mono block mt-0.5">
              Horizontal widescreen visualization: capital equity growth trajectory &amp; peak drawdown recovery
            </span>
          </div>
        </div>

        {onRefresh && (
          <button
            onClick={onRefresh}
            className="px-3 py-1.5 rounded-xl bg-slate-800/80 hover:bg-slate-800 border border-white/10 text-slate-300 text-xs font-bold font-mono flex items-center gap-1.5 transition-all cursor-pointer shadow-sm"
          >
            <RefreshCw className="w-3.5 h-3.5 text-sky-400" />
            <span>Refresh Stats</span>
          </button>
        )}
      </div>

      {/* DUAL CURVES CONTAINER (Horizontally side-by-side across the full screen on xl screens) */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 w-full">
        
        {/* CURVE 1: CAPITAL EQUITY GROWTH CURVE */}
        <div className="bento-card p-4 rounded-2xl relative overflow-hidden border border-white/10 shadow-xl bg-gradient-to-b from-[#0E1426] to-[#090E1D] flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-2.5 border-b border-white/5 flex-wrap gap-2">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shadow-[0_0_12px_rgba(16,185,129,0.25)] flex-shrink-0">
                  <TrendingUp className="w-4 h-4" />
                </div>
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs sm:text-sm font-black text-white font-mono uppercase tracking-wider">Capital Equity Growth Curve</span>
                    <span className="px-2 py-0.5 rounded-full text-[9px] font-mono font-extrabold bg-sky-500/15 text-sky-300 border border-sky-500/30">
                      {points.length - 1} Executions
                    </span>
                  </div>
                  <span className="text-[9.5px] text-slate-400 font-mono block mt-0.5">Realized Demat capital (₹1,25,000 base) &amp; cumulative R trajectory</span>
                </div>
              </div>
            </div>

            {/* 3-Column Bento Metric Summary Bar */}
            <div className="grid grid-cols-3 gap-2 mt-2.5 font-mono text-center">
              <div className="bg-slate-800/60 px-2 py-1.5 rounded-xl border border-white/5">
                <span className="text-[8.5px] text-slate-400 block font-bold uppercase tracking-wider">Initial Base</span>
                <span className="text-xs sm:text-sm font-black text-slate-300">₹1,25,000</span>
              </div>
              <div className="bg-slate-800/60 px-2 py-1.5 rounded-xl border border-white/5">
                <span className="text-[8.5px] text-slate-400 block font-bold uppercase tracking-wider">Current Equity</span>
                <span className={`text-xs sm:text-sm font-black ${latestPt.capital >= 125000 ? 'text-emerald-400' : 'text-amber-400'}`}>
                  ₹{latestPt.capital.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
              </div>
              <div className="bg-slate-800/60 px-2 py-1.5 rounded-xl border border-white/5">
                <span className="text-[8.5px] text-slate-400 block font-bold uppercase tracking-wider">All-Time Peak</span>
                <span className="text-xs sm:text-sm font-black text-emerald-400">
                  ₹{peakCapital.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
              </div>
            </div>
          </div>

          {/* Equity Canvas Wrapper with HTML Overlay Labels & Tooltip */}
          <div 
            ref={equityContainerRef}
            onMouseMove={(e) => handleEquityHover(e.clientX)}
            onMouseLeave={() => setHoverEquity(null)}
            onTouchMove={(e) => e.touches?.[0] && handleEquityHover(e.touches[0].clientX)}
            onTouchEnd={() => setHoverEquity(null)}
            className="relative w-full h-64 sm:h-72 mt-3 select-none rounded-xl bg-[#090E1D]/50 border border-white/5 overflow-hidden"
          >
            <svg viewBox={`0 0 ${W} ${H_EQ}`} className="w-full h-full overflow-hidden absolute inset-0" preserveAspectRatio="none">
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
                  <line key={g} x1={pad.left} y1={yPos} x2={W - pad.right} y2={yPos} stroke="rgba(255, 255, 255, 0.05)" strokeWidth="1" strokeDasharray="4,4" />
                );
              })}

              {/* Baseline */}
              <line x1={pad.left} y1={yEqBase} x2={W - pad.right} y2={yEqBase} stroke="rgba(56, 189, 248, 0.45)" strokeWidth="1.5" strokeDasharray="5,4" />

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

            {/* Crisp HTML Overlays (Zero-squeeze typography) */}
            <div className="absolute inset-0 pointer-events-none select-none">
              {/* Y-Axis Labels */}
              {[0, 1, 2, 3, 4].map(g => {
                const val = minCap + (g / 4) * (maxCap - minCap);
                const pctY = (getEqY(val) / H_EQ) * 100;
                return (
                  <span 
                    key={g} 
                    className="absolute text-[9px] font-mono font-bold text-slate-400 bg-slate-900/90 px-1.5 py-0.5 rounded border border-white/10 shadow-sm"
                    style={{ left: '8px', top: `${pctY}%`, transform: 'translateY(-50%)' }}
                  >
                    ₹{Math.round(val).toLocaleString('en-IN')}
                  </span>
                );
              })}

              {/* Baseline Badge */}
              <span 
                className="absolute text-[9.5px] font-mono font-black text-sky-400 bg-slate-900/95 px-2 py-0.5 rounded-md border border-sky-400/50 shadow-[0_0_8px_rgba(56,189,248,0.25)] flex items-center gap-1"
                style={{ right: '8px', top: `${(yEqBase / H_EQ) * 100}%`, transform: 'translateY(-50%)' }}
              >
                Start Baseline ₹1,25,000 (0.0R)
              </span>

              {/* Current Capital Marker Badge */}
              <span 
                className="absolute text-[8.5px] font-mono font-bold text-sky-300 bg-slate-900/90 px-1.5 py-0.5 rounded border border-sky-400/40 shadow-sm whitespace-nowrap"
                style={{
                  left: `${(getEqX(points.length - 1) / W) * 100}%`,
                  top: `${(getEqY(latestPt.capital) / H_EQ) * 100}%`,
                  transform: 'translate(-50%, 12px)'
                }}
              >
                Now: ₹{latestPt.capital.toLocaleString('en-IN')}
              </span>
            </div>

            {/* Hover Tooltip */}
            {hoverEquity && (
              <div 
                className="absolute pointer-events-none z-40 bg-slate-900/95 backdrop-blur-md border border-sky-500/40 rounded-xl p-2.5 shadow-2xl text-[9.5px] font-mono space-y-0.5"
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
        <div className="bento-card p-4 rounded-2xl relative overflow-hidden border border-white/10 shadow-xl bg-gradient-to-b from-[#0E1426] to-[#090E1D] flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-2.5 border-b border-white/5 flex-wrap gap-2">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400 shadow-[0_0_12px_rgba(245,158,11,0.25)] flex-shrink-0">
                  <ShieldAlert className="w-4 h-4" />
                </div>
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs sm:text-sm font-black text-white font-mono uppercase tracking-wider">Dynamic Risk Governor &amp; Drawdown</span>
                  </div>
                  <span className="text-[9.5px] text-slate-400 font-mono block mt-0.5">Peak-to-trough R-drawdown, Normal mode (&gt; -5.0R) recovery &amp; Defensive circuit breaker (&lt; -15.0R)</span>
                </div>
              </div>

              <span className={`px-2.5 py-1 rounded-full text-[9px] font-mono font-extrabold border flex-shrink-0 ${
                govStats.mode === 'DEFENSIVE' 
                  ? 'bg-amber-500/20 text-amber-400 border-amber-500/40 animate-pulse' 
                  : 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40'
              }`}>
                {govStats.mode === 'DEFENSIVE' ? 'DEFENSIVE (0.5R Risk)' : 'NORMAL (1.0R Risk)'}
              </span>
            </div>

            {/* 3-Column Bento Metric Summary Bar */}
            <div className="grid grid-cols-3 gap-2 mt-2.5 font-mono text-center">
              <div className="bg-slate-800/60 px-2 py-1.5 rounded-xl border border-white/5">
                <span className="text-[8.5px] text-slate-400 block font-bold uppercase tracking-wider">Current DD</span>
                <span className={`text-xs sm:text-sm font-black ${govStats.current_drawdown_r >= -5.0 ? 'text-emerald-400' : (govStats.current_drawdown_r <= -15.0 ? 'text-rose-400' : 'text-amber-400')}`}>
                  {govStats.current_drawdown_r >= 0 ? '+' : ''}{govStats.current_drawdown_r.toFixed(2)} R
                </span>
              </div>
              <div className="bg-slate-800/60 px-2 py-1.5 rounded-xl border border-white/5">
                <span className="text-[8.5px] text-slate-400 block font-bold uppercase tracking-wider">Peak Trough</span>
                <span className="text-xs sm:text-sm font-black text-rose-500">{govStats.max_drawdown_r.toFixed(2)} R</span>
              </div>
              <div className="bg-slate-800/60 px-2 py-1.5 rounded-xl border border-white/5">
                <span className="text-[8.5px] text-slate-400 block font-bold uppercase tracking-wider">Normal Target</span>
                <span className="text-xs sm:text-sm font-black text-sky-400">-5.00 R</span>
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
              <div className="flex items-center justify-between text-[8.5px] text-slate-400">
                <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-rose-500"></span> Trough: <strong>{govStats.max_drawdown_r.toFixed(2)} R</strong></span>
                <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-sky-400"></span> Normal Threshold: <strong>-5.00 R</strong></span>
                <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> Peak HWM: <strong>0.00 R</strong></span>
              </div>
            </div>
          </div>

          {/* Drawdown Canvas Wrapper with HTML Overlay Labels & Tooltip */}
          <div 
            ref={ddContainerRef}
            onMouseMove={(e) => handleDdHover(e.clientX)}
            onMouseLeave={() => setHoverDd(null)}
            onTouchMove={(e) => e.touches?.[0] && handleDdHover(e.touches[0].clientX)}
            onTouchEnd={() => setHoverDd(null)}
            className="relative w-full h-64 sm:h-72 mt-3 select-none rounded-xl bg-[#090E1D]/50 border border-white/5 overflow-hidden"
          >
            <svg viewBox={`0 0 ${W} ${H_DD}`} className="w-full h-full overflow-hidden absolute inset-0" preserveAspectRatio="none">
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
              <rect x={pad.left} y={yDdNormal} width={plotW} height={Math.max(0, yDdDefensive - yDdNormal)} fill="rgba(245, 158, 11, 0.07)" />
              <rect x={pad.left} y={yDdDefensive} width={plotW} height={Math.max(0, yDdBottom - yDdDefensive)} fill="rgba(255, 51, 102, 0.08)" />

              {/* Threshold Lines */}
              <line x1={pad.left} y1={yDdZero} x2={W - pad.right} y2={yDdZero} stroke="rgba(255, 255, 255, 0.25)" strokeWidth="1.2" strokeDasharray="4,4" />
              <line x1={pad.left} y1={yDdNormal} x2={W - pad.right} y2={yDdNormal} stroke="#38BDF8" strokeWidth="1.8" strokeDasharray="5,4" />
              <line x1={pad.left} y1={yDdDefensive} x2={W - pad.right} y2={yDdDefensive} stroke="#FF3366" strokeWidth="1.8" strokeDasharray="5,4" />
              <line x1={pad.left} y1={getDdY(-10.0)} x2={W - pad.right} y2={getDdY(-10.0)} stroke="rgba(255, 255, 255, 0.04)" strokeWidth="1" strokeDasharray="3,3" />
              <line x1={pad.left} y1={getDdY(-20.0)} x2={W - pad.right} y2={getDdY(-20.0)} stroke="rgba(255, 255, 255, 0.04)" strokeWidth="1" strokeDasharray="3,3" />

              {/* Drawdown Area & Line */}
              <path d={ddAreaD} fill="url(#reactDdAreaGrad)" />
              <path d={ddPathD} fill="none" stroke="#F59E0B" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" filter="url(#reactDdGlow)" />

              {/* Peak Trough Circle Marker */}
              <circle cx={getDdX(troughIdx)} cy={getDdY(minDdVal)} r="5" fill="#FF3366" stroke="#FFFFFF" strokeWidth="2" />
              <circle cx={getDdX(troughIdx)} cy={getDdY(minDdVal)} r="9" fill="none" stroke="#FF3366" strokeWidth="1.5" opacity="0.8" />

              {/* Current Circle Marker */}
              <circle cx={getDdX(points.length - 1)} cy={getDdY(latestPt.drawdown_r)} r="5" fill="#38BDF8" stroke="#FFFFFF" strokeWidth="2" />

              {/* Hover Crosshair */}
              {hoverDd && (
                <g>
                  <line x1={hoverDd.x} y1={pad.top} x2={hoverDd.x} y2={pad.top + plotH_DD} stroke="rgba(245, 158, 11, 0.8)" strokeWidth="1.5" strokeDasharray="3,3" />
                  <circle cx={hoverDd.x} cy={hoverDd.y} r="5" fill="#F59E0B" stroke="#FFFFFF" strokeWidth="2" />
                </g>
              )}
            </svg>

            {/* Crisp HTML Overlays (Zero-squeeze typography) */}
            <div className="absolute inset-0 pointer-events-none select-none">
              {/* Left Y-Axis Labels */}
              <span className="absolute text-[9px] font-mono font-bold text-slate-400 bg-slate-900/90 px-1.5 py-0.5 rounded border border-white/10 shadow-sm" style={{ left: '8px', top: `${(yDdZero / H_DD) * 100}%`, transform: 'translateY(-50%)' }}>0.0 R</span>
              <span className="absolute text-[9px] font-mono font-bold text-sky-400 bg-slate-900/90 px-1.5 py-0.5 rounded border border-sky-400/30 shadow-sm" style={{ left: '8px', top: `${(yDdNormal / H_DD) * 100}%`, transform: 'translateY(-50%)' }}>-5.0 R</span>
              <span className="absolute text-[9px] font-mono font-bold text-slate-400 bg-slate-900/90 px-1.5 py-0.5 rounded border border-white/10 shadow-sm" style={{ left: '8px', top: `${(getDdY(-10.0) / H_DD) * 100}%`, transform: 'translateY(-50%)' }}>-10.0 R</span>
              <span className="absolute text-[9px] font-mono font-bold text-rose-400 bg-slate-900/90 px-1.5 py-0.5 rounded border border-rose-500/30 shadow-sm" style={{ left: '8px', top: `${(yDdDefensive / H_DD) * 100}%`, transform: 'translateY(-50%)' }}>-15.0 R</span>
              <span className="absolute text-[9px] font-mono font-bold text-slate-400 bg-slate-900/90 px-1.5 py-0.5 rounded border border-white/10 shadow-sm" style={{ left: '8px', top: `${(getDdY(-20.0) / H_DD) * 100}%`, transform: 'translateY(-50%)' }}>-20.0 R</span>

              {/* Zone Tags */}
              <span className="absolute text-[8.5px] font-mono font-bold text-emerald-400 bg-slate-900/90 border border-emerald-500/30 px-2 py-0.5 rounded shadow-sm" style={{ left: '60px', top: `${((yDdZero + 6) / H_DD) * 100}%` }}>NORMAL 1.0R ZONE</span>
              <span className="absolute text-[8.5px] font-mono font-bold text-amber-400 bg-slate-900/90 border border-amber-500/30 px-2 py-0.5 rounded shadow-sm" style={{ left: '60px', top: `${((yDdNormal + 6) / H_DD) * 100}%` }}>DEFENSIVE 0.5R ZONE</span>
              <span className="absolute text-[8.5px] font-mono font-bold text-rose-400 bg-slate-900/90 border border-rose-500/30 px-2 py-0.5 rounded shadow-sm" style={{ left: '60px', top: `${((yDdDefensive + 6) / H_DD) * 100}%` }}>CRITICAL ZONE (&lt; -15.0R)</span>

              {/* Right Threshold Badges */}
              <span className="absolute text-[9px] font-mono font-bold text-slate-300 bg-slate-900/90 border border-white/10 px-2 py-0.5 rounded-md" style={{ right: '8px', top: `${(yDdZero / H_DD) * 100}%`, transform: 'translateY(-50%)' }}>0.00 R Peak HWM</span>
              <span className="absolute text-[9.5px] font-mono font-black text-sky-400 bg-slate-900/95 border border-sky-400/50 px-2 py-0.5 rounded-md shadow-[0_0_8px_rgba(56,189,248,0.25)] flex items-center gap-1" style={{ right: '8px', top: `${(yDdNormal / H_DD) * 100}%`, transform: 'translateY(-50%)' }}><span>▲</span> Normal Target (-5.00 R)</span>
              <span className="absolute text-[9.5px] font-mono font-black text-rose-400 bg-slate-900/95 border border-rose-500/50 px-2 py-0.5 rounded-md shadow-[0_0_8px_rgba(255,51,102,0.25)] flex items-center gap-1" style={{ right: '8px', top: `${(yDdDefensive / H_DD) * 100}%`, transform: 'translateY(-50%)' }}><span>▼</span> Defensive Trigger (-15.00 R)</span>

              {/* Point Markers */}
              <span className="absolute text-[9px] font-mono font-black text-rose-400 bg-slate-900/95 border border-rose-500/50 px-1.5 py-0.5 rounded shadow-md whitespace-nowrap" style={{ left: `${(getDdX(troughIdx) / W) * 100}%`, top: `${(getDdY(minDdVal) / H_DD) * 100}%`, transform: 'translate(-50%, 8px)' }}>Trough: {minDdVal.toFixed(2)} R</span>
              <span className="absolute text-[9px] font-mono font-black text-sky-400 bg-slate-900/95 border border-sky-400/50 px-1.5 py-0.5 rounded shadow-md whitespace-nowrap" style={{ left: `${(getDdX(points.length - 1) / W) * 100}%`, top: `${(getDdY(latestPt.drawdown_r) / H_DD) * 100}%`, transform: 'translate(-50%, -24px)' }}>Current: {latestPt.drawdown_r.toFixed(2)} R</span>
            </div>

            {/* Hover Tooltip */}
            {hoverDd && (
              <div 
                className="absolute pointer-events-none z-40 bg-slate-900/95 backdrop-blur-md border border-amber-500/40 rounded-xl p-2.5 shadow-2xl text-[9.5px] font-mono space-y-0.5"
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

    </div>
  );
}
