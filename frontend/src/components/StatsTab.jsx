import React, { useState, useRef, useMemo } from 'react';
import { 
  TrendingUp, 
  TrendingDown,
  ShieldAlert, 
  ShieldCheck,
  Activity,
  RefreshCw,
  Trophy,
  Target,
  BarChart2,
  PieChart
} from 'lucide-react';

export default function StatsTab({ analyticsData, onRefresh }) {
  const data = analyticsData || {};
  const dateGroups = data.date_groups || [];

  // Timeframe filter state
  const [eqTimeframe, setEqTimeframe] = useState('ALL');
  const [ddTimeframe, setDdTimeframe] = useState('ALL');

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
      capital: 100000.0,
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
      const r = Number(t.realized_r !== undefined ? t.realized_r : (p / 2500));
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
        capital: Math.round((100000.0 + cumP) * 100) / 100,
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

  // Filter Points by Timeframe
  const filterByTimeframe = (pts, tf) => {
    if (!pts || pts.length <= 2 || tf === 'ALL') return pts;
    let count = pts.length;
    if (tf === '1W') count = Math.min(pts.length, 8);
    else if (tf === '1M') count = Math.min(pts.length, 25);
    else if (tf === '3M') count = Math.min(pts.length, 60);
    else if (tf === '6M') count = Math.min(pts.length, 120);
    else if (tf === '1Y') count = Math.min(pts.length, 250);
    const slice = pts.slice(-count);
    return slice.length >= 2 ? slice : pts;
  };

  const filteredEqPoints = useMemo(() => filterByTimeframe(points, eqTimeframe), [points, eqTimeframe]);
  const filteredDdPoints = useMemo(() => filterByTimeframe(points, ddTimeframe), [points, ddTimeframe]);

  // SVG Hover States
  const [hoverEquity, setHoverEquity] = useState(null);
  const [hoverDd, setHoverDd] = useState(null);
  const equityContainerRef = useRef(null);
  const ddContainerRef = useRef(null);

  // SVG Dimensions & Math
  const W = 1000;
  const H_EQ = 240;
  const H_DD = 260;
  const pad = { top: 30, right: 35, bottom: 35, left: 75 };
  const plotW = W - pad.left - pad.right;
  const plotH_EQ = H_EQ - pad.top - pad.bottom;
  const plotH_DD = H_DD - pad.top - pad.bottom;

  // Equity calculations
  const allCapitals = points.map(p => p.capital);
  const latestPt = points[points.length - 1];
  const initialCap = 100000.0;
  const netGain = latestPt.capital - initialCap;
  const returnPct = (netGain / initialCap) * 100;
  const peakCapital = Math.max(...allCapitals);
  const minCapital = Math.min(...allCapitals);
  const peakReturnPct = ((peakCapital - initialCap) / initialCap) * 100;
  const maxDrawdownAmount = peakCapital - minCapital;
  const maxDrawdownPct = peakCapital > 0 ? (maxDrawdownAmount / peakCapital) * 100 : 0;

  // Filtered Equity Math
  const eqCapitals = filteredEqPoints.map(p => p.capital);
  let minEqCap = Math.min(...eqCapitals, 100000);
  let maxEqCap = Math.max(...eqCapitals, 100000);
  const eqSpan = maxEqCap - minEqCap;
  const eqBuffer = Math.max(300, eqSpan * 0.15);
  minEqCap = Math.floor((minEqCap - eqBuffer) / 500) * 500;
  maxEqCap = Math.ceil((maxEqCap + eqBuffer) / 500) * 500;
  if (maxEqCap <= minEqCap) maxEqCap = minEqCap + 1000;

  const getEqX = (i) => pad.left + (filteredEqPoints.length === 1 ? plotW / 2 : (i / (filteredEqPoints.length - 1)) * plotW);
  const getEqY = (val) => pad.top + plotH_EQ - ((val - minEqCap) / (maxEqCap - minEqCap)) * plotH_EQ;
  const yEqBase = getEqY(100000.0);

  let eqPathD = `M ${getEqX(0)},${getEqY(filteredEqPoints[0].capital)}`;
  for (let i = 1; i < filteredEqPoints.length; i++) {
    eqPathD += ` L ${getEqX(i)},${getEqY(filteredEqPoints[i].capital)}`;
  }
  const eqAreaD = `${eqPathD} L ${getEqX(filteredEqPoints.length - 1)},${pad.top + plotH_EQ} L ${getEqX(0)},${pad.top + plotH_EQ} Z`;

  // Find Peak and Low in Filtered Points
  let fPeakIdx = 0;
  let fPeakVal = filteredEqPoints[0].capital;
  let fLowIdx = 0;
  let fLowVal = filteredEqPoints[0].capital;

  filteredEqPoints.forEach((p, idx) => {
    if (p.capital > fPeakVal) {
      fPeakVal = p.capital;
      fPeakIdx = idx;
    }
    if (p.capital < fLowVal) {
      fLowVal = p.capital;
      fLowIdx = idx;
    }
  });

  const fLastIdx = filteredEqPoints.length - 1;

  // Drawdown Calculations
  const minDrawdown = Math.min(...filteredDdPoints.map(p => p.drawdown_r), govStats.max_drawdown_r || -19.13);
  const yMinDd = Math.min(minDrawdown, -19.5) - 2.0;
  const yMaxDd = 1.0;

  const getDdX = (i) => pad.left + (filteredDdPoints.length === 1 ? plotW / 2 : (i / (filteredDdPoints.length - 1)) * plotW);
  const getDdY = (dd) => pad.top + ((yMaxDd - dd) / (yMaxDd - yMinDd)) * plotH_DD;

  const yDdZero = getDdY(0.0);
  const yDdNormal = getDdY(-5.0);
  const yDdDefensive = getDdY(-15.0);
  const yDdBottom = pad.top + plotH_DD;

  let ddPathD = `M ${getDdX(0)},${getDdY(filteredDdPoints[0].drawdown_r)}`;
  for (let i = 1; i < filteredDdPoints.length; i++) {
    ddPathD += ` L ${getDdX(i)},${getDdY(filteredDdPoints[i].drawdown_r)}`;
  }
  const ddAreaD = `${ddPathD} L ${getDdX(filteredDdPoints.length - 1)},${yDdZero} L ${getDdX(0)},${yDdZero} Z`;

  // Peak Trough Index in Filtered Drawdown
  let fTroughIdx = 0;
  let fMinDdVal = filteredDdPoints[0].drawdown_r;
  filteredDdPoints.forEach((p, idx) => {
    if (p.drawdown_r < fMinDdVal) {
      fMinDdVal = p.drawdown_r;
      fTroughIdx = idx;
    }
  });

  const fDdLastIdx = filteredDdPoints.length - 1;

  // Donut chart math
  const winRate = Number(data.win_rate !== undefined ? data.win_rate : 40.2);
  const losingRate = Math.max(0, 100 - winRate);
  const donutCircum = 2 * Math.PI * 38; // 238.76
  const winStroke = (winRate / 100) * donutCircum;

  const handleEquityHover = (clientX) => {
    if (!equityContainerRef.current) return;
    const rect = equityContainerRef.current.getBoundingClientRect();
    const offsetX = clientX - rect.left;
    const normX = (offsetX / rect.width) * W;
    const clampedX = Math.min(W - pad.right, Math.max(pad.left, normX));
    const ratio = (clampedX - pad.left) / plotW;
    const idx = Math.min(filteredEqPoints.length - 1, Math.max(0, Math.round(ratio * (filteredEqPoints.length - 1))));
    setHoverEquity({
      point: filteredEqPoints[idx],
      x: getEqX(idx),
      y: getEqY(filteredEqPoints[idx].capital),
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
    const idx = Math.min(filteredDdPoints.length - 1, Math.max(0, Math.round(ratio * (filteredDdPoints.length - 1))));
    setHoverDd({
      point: filteredDdPoints[idx],
      x: getDdX(idx),
      y: getDdY(filteredDdPoints[idx].drawdown_r),
      pctX: (getDdX(idx) / W) * 100
    });
  };

  return (
    <div className="space-y-4 pb-12 w-full max-w-full">
      
      {/* SECTION HEADER BAR */}
      <div className="flex items-center justify-between pb-2 border-b border-white/[0.08] flex-wrap gap-2 px-1">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-cyan-500/20 to-blue-500/20 border border-cyan-400/30 flex items-center justify-center text-cyan-300 shadow-[0_0_12px_rgba(56,189,248,0.25)] flex-shrink-0">
            <Activity className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-xs sm:text-sm font-black text-white font-mono uppercase tracking-wider">
                Quant Telemetry &amp; Risk Governor Stats
              </h2>
              <span className="px-2 py-0.5 rounded-full text-[9px] font-mono font-extrabold bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">
                Horizontal Full-Width
              </span>
            </div>
            <span className="text-[9.5px] text-slate-400 font-mono block mt-0.5">
              Dual institutional terminal: Demat capital compounding curve &amp; peak drawdown recovery
            </span>
          </div>
        </div>

        {onRefresh && (
          <button
            onClick={onRefresh}
            className="px-3 py-1.5 rounded-xl bg-slate-800/80 hover:bg-slate-800 border border-white/10 text-slate-300 text-xs font-bold font-mono flex items-center gap-1.5 transition-all cursor-pointer shadow-sm"
          >
            <RefreshCw className="w-3.5 h-3.5 text-cyan-400" />
            <span>Refresh Stats</span>
          </button>
        )}
      </div>

      {/* DUAL TERMINALS GRID (SIDE-BY-SIDE ON DESKTOP, STACKED ON MOBILE) */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 w-full">
        
        {/* ============================================== */}
        {/* TERMINAL 1: CAPITAL EQUITY GROWTH (IMAGE 1)   */}
        {/* ============================================== */}
        <div className="space-y-3.5 flex flex-col justify-between">
          
          {/* 4 Circular-Icon KPI Cards (2x2 Grid) */}
          <div className="grid grid-cols-2 gap-2.5 font-mono">
            {/* Card 1: Total Return */}
            <div className="p-3 sm:p-3.5 rounded-2xl border border-emerald-500/25 bg-[#080C16] flex items-center gap-3 shadow-lg">
              <div className="w-10 sm:w-11 h-10 sm:h-11 rounded-full bg-emerald-500/10 border border-emerald-500/25 flex items-center justify-center text-emerald-400 shadow-[0_0_12px_rgba(16,185,129,0.15)] flex-shrink-0">
                <TrendingUp className="w-5 h-5" />
              </div>
              <div className="min-w-0">
                <span className="text-[9px] text-slate-400 block uppercase tracking-wider font-bold">Total Return</span>
                <span className={`text-xs sm:text-sm font-black truncate block ${netGain >= 0 ? 'text-emerald-400' : 'text-amber-400'}`}>
                  {netGain >= 0 ? '+' : '-'}₹{Math.abs(netGain).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
                <span className={`text-[8.5px] font-bold flex items-center gap-0.5 ${netGain >= 0 ? 'text-emerald-400' : 'text-amber-400'}`}>
                  {netGain >= 0 ? '▲ +' : '▼ '}{returnPct.toFixed(2)}%
                </span>
              </div>
            </div>

            {/* Card 2: Current Equity */}
            <div className="p-3 sm:p-3.5 rounded-2xl border border-white/10 bg-[#080C16] flex items-center gap-3 shadow-lg">
              <div className="w-10 sm:w-11 h-10 sm:h-11 rounded-full bg-amber-500/10 border border-amber-500/25 flex items-center justify-center text-amber-400 shadow-[0_0_12px_rgba(245,158,11,0.15)] flex-shrink-0">
                <Trophy className="w-5 h-5" />
              </div>
              <div className="min-w-0">
                <span className="text-[9px] text-slate-400 block uppercase tracking-wider font-bold">Current Equity</span>
                <span className="text-xs sm:text-sm font-black text-white truncate block">
                  ₹{latestPt.capital.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
                <span className="text-[8.5px] text-slate-400 truncate block">vs ₹1,00,000 initial</span>
              </div>
            </div>

            {/* Card 3: All-Time Peak */}
            <div className="p-3 sm:p-3.5 rounded-2xl border border-white/10 bg-[#080C16] flex items-center gap-3 shadow-lg">
              <div className="w-10 sm:w-11 h-10 sm:h-11 rounded-full bg-teal-500/10 border border-teal-500/25 flex items-center justify-center text-teal-400 shadow-[0_0_12px_rgba(20,184,166,0.15)] flex-shrink-0">
                <Target className="w-5 h-5" />
              </div>
              <div className="min-w-0">
                <span className="text-[9px] text-slate-400 block uppercase tracking-wider font-bold">All-Time Peak</span>
                <span className="text-xs sm:text-sm font-black text-emerald-400 truncate block">
                  ₹{peakCapital.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
                <span className="text-[8.5px] font-bold text-emerald-400 flex items-center gap-0.5">
                  ▲ +{peakReturnPct.toFixed(2)}%
                </span>
              </div>
            </div>

            {/* Card 4: Max Drawdown */}
            <div className="p-3 sm:p-3.5 rounded-2xl border border-rose-500/25 bg-[#080C16] flex items-center gap-3 shadow-lg">
              <div className="w-10 sm:w-11 h-10 sm:h-11 rounded-full bg-rose-500/10 border border-rose-500/25 flex items-center justify-center text-rose-400 shadow-[0_0_12px_rgba(244,63,94,0.15)] flex-shrink-0">
                <BarChart2 className="w-5 h-5" />
              </div>
              <div className="min-w-0">
                <span className="text-[9px] text-slate-400 block uppercase tracking-wider font-bold">Max Drawdown</span>
                <span className="text-xs sm:text-sm font-black text-rose-400 truncate block">
                  ₹{maxDrawdownAmount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
                <span className="text-[8.5px] font-bold text-rose-400 flex items-center gap-0.5">
                  ▼ -{maxDrawdownPct.toFixed(2)}%
                </span>
              </div>
            </div>
          </div>

          {/* Curve 1 Card: Capital Equity Growth Curve */}
          <div className="p-3.5 sm:p-4 rounded-2xl relative overflow-hidden border border-white/10 shadow-2xl bg-[#080C16]">
            {/* Card Header with Timeframe Pills */}
            <div className="flex items-center justify-between pb-2.5 border-b border-white/5 flex-wrap gap-2">
              <div className="flex items-center gap-2">
                <div className="text-cyan-400">
                  <BarChart2 className="w-4 h-4" />
                </div>
                <h3 className="text-xs font-black text-white font-mono uppercase tracking-wider">
                  Capital Equity Growth Curve
                </h3>
              </div>
              {/* Timeframe Pills (1W 1M 3M 6M 1Y ALL) */}
              <div className="flex items-center bg-[#0B101E] p-0.5 rounded-lg border border-white/5 font-mono text-[10px]">
                {['1W', '1M', '3M', '6M', '1Y', 'ALL'].map(tf => (
                  <button
                    key={tf}
                    onClick={() => setEqTimeframe(tf)}
                    className={`px-2 py-0.5 rounded-md transition-all ${
                      eqTimeframe === tf 
                        ? 'bg-emerald-500 text-black font-black' 
                        : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    {tf}
                  </button>
                ))}
              </div>
            </div>

            {/* SVG Container */}
            <div 
              ref={equityContainerRef}
              onMouseMove={(e) => handleEquityHover(e.clientX)}
              onMouseLeave={() => setHoverEquity(null)}
              onTouchMove={(e) => e.touches?.[0] && handleEquityHover(e.touches[0].clientX)}
              onTouchEnd={() => setHoverEquity(null)}
              className="relative w-full h-60 sm:h-64 mt-2.5 select-none rounded-xl bg-[#060912] border border-white/5 overflow-hidden"
            >
              <svg viewBox={`0 0 ${W} ${H_EQ}`} className="w-full h-full overflow-hidden absolute inset-0" preserveAspectRatio="none">
                <defs>
                  <linearGradient id="reactEqGradientClean" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="rgba(16, 185, 129, 0.22)" />
                    <stop offset="100%" stopColor="rgba(6, 9, 18, 0)" />
                  </linearGradient>
                </defs>

                {/* Grid Lines */}
                {[0, 1, 2, 3, 4].map(g => {
                  const val = minEqCap + (g / 4) * (maxEqCap - minEqCap);
                  const yPos = getEqY(val);
                  return (
                    <line key={g} x1={pad.left} y1={yPos} x2={W - pad.right} y2={yPos} stroke="rgba(255, 255, 255, 0.05)" strokeWidth="1" strokeDasharray="3,3" />
                  );
                })}

                {/* Starting Baseline */}
                <line x1={pad.left} y1={yEqBase} x2={W - pad.right} y2={yEqBase} stroke="rgba(56, 189, 248, 0.35)" strokeWidth="1.2" strokeDasharray="4,4" />

                {/* Gradient Area Fill */}
                <path d={eqAreaD} fill="url(#reactEqGradientClean)" />

                {/* Crisp Solid Line (ZERO GLOW FILTER) */}
                <path d={eqPathD} fill="none" stroke="#10B981" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />

                {/* Peak Circle Marker */}
                <circle cx={getEqX(fPeakIdx)} cy={getEqY(fPeakVal)} r="4" fill="#FFFFFF" stroke="#10B981" strokeWidth="2.5" />

                {/* Low Circle Marker */}
                <circle cx={getEqX(fLowIdx)} cy={getEqY(fLowVal)} r="4" fill="#FFFFFF" stroke="#EF4444" strokeWidth="2.5" />

                {/* Current Circle Marker */}
                <circle cx={getEqX(fLastIdx)} cy={getEqY(filteredEqPoints[fLastIdx].capital)} r="4.5" fill="#FFFFFF" stroke="#10B981" strokeWidth="2.5" />

                {/* Hover Crosshair */}
                {hoverEquity && (
                  <g>
                    <line x1={hoverEquity.x} y1={pad.top} x2={hoverEquity.x} y2={pad.top + plotH_EQ} stroke="rgba(0, 240, 255, 0.7)" strokeWidth="1.2" strokeDasharray="3,3" />
                    <circle cx={hoverEquity.x} cy={hoverEquity.y} r="4.5" fill="#00F0FF" stroke="#FFFFFF" strokeWidth="2" />
                  </g>
                )}
              </svg>

              {/* Hover Tooltip */}
              {hoverEquity && (
                <div 
                  className="absolute pointer-events-none z-40 bg-[#0B1120]/95 backdrop-blur-md border border-cyan-400/40 rounded-xl p-2.5 shadow-2xl text-[9.5px] font-mono space-y-0.5"
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
                    <span className={`font-black ${hoverEquity.point.capital >= 100000 ? 'text-emerald-400' : 'text-amber-400'}`}>
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

            {/* Legend Below Chart */}
            <div className="flex items-center justify-center gap-6 mt-2.5 font-mono text-[9.5px] text-slate-400 border-t border-white/5 pt-2">
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
                <span className="text-slate-300 font-bold">Equity Curve</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-4 border-t-2 border-dashed border-cyan-400/70 inline-block"></span>
                <span className="text-slate-300">Initial Capital (₹1,00,000.00)</span>
              </div>
            </div>
          </div>

          {/* Bottom Sub-Grid: Left Key Stats, Right Trade Distribution Donut */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            
            {/* Left: Key Stats Table Card */}
            <div className="p-3.5 rounded-2xl border border-white/10 bg-[#080C16] font-mono shadow-lg flex flex-col justify-between">
              <div className="flex items-center gap-2 pb-2 border-b border-white/5">
                <div className="text-cyan-400">
                  <BarChart2 className="w-3.5 h-3.5" />
                </div>
                <h4 className="text-xs font-black text-white uppercase tracking-wider">Key Stats</h4>
              </div>
              <div className="space-y-1 mt-2 text-[9.5px]">
                <div className="flex items-center justify-between py-0.5 border-b border-white/[0.04]">
                  <span className="text-slate-400">Initial Capital</span>
                  <span className="font-bold text-white">₹1,00,000.00</span>
                </div>
                <div className="flex items-center justify-between py-0.5 border-b border-white/[0.04]">
                  <span className="text-slate-400">Current Equity</span>
                  <span className="font-bold text-white">
                    ₹{latestPt.capital.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </span>
                </div>
                <div className="flex items-center justify-between py-0.5 border-b border-white/[0.04]">
                  <span className="text-slate-400">Total Return</span>
                  <span className={`font-bold ${netGain >= 0 ? 'text-emerald-400' : 'text-amber-400'}`}>
                    {netGain >= 0 ? '+' : ''}{returnPct.toFixed(2)}%
                  </span>
                </div>
                <div className="flex items-center justify-between py-0.5 border-b border-white/[0.04]">
                  <span className="text-slate-400">Absolute Profit</span>
                  <span className={`font-bold ${netGain >= 0 ? 'text-emerald-400' : 'text-amber-400'}`}>
                    {netGain >= 0 ? '+' : '-'}₹{Math.abs(netGain).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </span>
                </div>
                <div className="flex items-center justify-between py-0.5 border-b border-white/[0.04]">
                  <span className="text-slate-400">Max Drawdown</span>
                  <span className="font-bold text-rose-400">
                    -{maxDrawdownPct.toFixed(2)}% (₹{maxDrawdownAmount.toFixed(0)})
                  </span>
                </div>
                <div className="flex items-center justify-between py-0.5 border-b border-white/[0.04]">
                  <span className="text-slate-400">Sharpe Ratio</span>
                  <span className="font-bold text-white">{data.sharpe_ratio || "1.82"}</span>
                </div>
                <div className="flex items-center justify-between py-0.5 border-b border-white/[0.04]">
                  <span className="text-slate-400">Profit Factor</span>
                  <span className="font-bold text-white">{data.profit_factor || "2.14"}</span>
                </div>
                <div className="flex items-center justify-between py-0.5">
                  <span className="text-slate-400">Win Rate</span>
                  <span className="font-bold text-white">{winRate.toFixed(1)}%</span>
                </div>
              </div>
            </div>

            {/* Right: Trade Distribution Donut Card */}
            <div className="p-3.5 rounded-2xl border border-white/10 bg-[#080C16] font-mono shadow-lg flex flex-col justify-between">
              <div className="flex items-center gap-2 pb-2 border-b border-white/5">
                <div className="text-cyan-400">
                  <PieChart className="w-3.5 h-3.5" />
                </div>
                <h4 className="text-xs font-black text-white uppercase tracking-wider">Trade Distribution</h4>
              </div>
              
              {/* Donut SVG with center text */}
              <div className="flex items-center justify-center my-1 relative">
                <div className="w-28 h-28 relative flex items-center justify-center">
                  <svg viewBox="0 0 100 100" className="w-full h-full transform -rotate-90">
                    <circle cx="50" cy="50" r="38" fill="none" stroke="#0F172A" strokeWidth="12" />
                    <circle cx="50" cy="50" r="38" fill="none" stroke="#0284C7" strokeWidth="12" 
                      strokeDasharray={`${donutCircum} ${donutCircum}`} />
                    <circle cx="50" cy="50" r="38" fill="none" stroke="#10B981" strokeWidth="12" 
                      strokeDasharray={`${winStroke} ${donutCircum}`} />
                  </svg>
                  <div className="absolute inset-0 flex flex-col items-center justify-center font-mono select-none pointer-events-none">
                    <span className="text-sm font-black text-white">{winRate.toFixed(1)}%</span>
                    <span className="text-[8px] text-slate-400 font-bold uppercase tracking-wider">Win Rate</span>
                  </div>
                </div>
              </div>

              {/* Donut Legend */}
              <div className="space-y-1 text-[9px] border-t border-white/5 pt-2">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                    <span className="text-slate-300">Winning Trades</span>
                  </span>
                  <span className="font-bold text-emerald-400">({winRate.toFixed(1)}%)</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-sky-500"></span>
                    <span className="text-slate-300">Losing Trades</span>
                  </span>
                  <span className="font-bold text-sky-400">({losingRate.toFixed(1)}%)</span>
                </div>
              </div>
            </div>

          </div>

        </div>

        {/* ============================================== */}
        {/* TERMINAL 2: DYNAMIC RISK GOVERNOR (IMAGE 2)   */}
        {/* ============================================== */}
        <div className="space-y-3.5 flex flex-col justify-between">
          
          {/* 3 Top Circular KPI Cards (1x3 Grid) */}
          <div className="grid grid-cols-3 gap-2 font-mono">
            {/* Card 1: Current Drawdown */}
            <div className="p-2 sm:p-2.5 md:p-3 rounded-2xl border border-amber-500/25 bg-[#080C16] flex flex-col justify-between shadow-lg min-w-0">
              <div className="flex items-center gap-1.5 mb-1.5">
                <div className="w-6 h-6 sm:w-7 sm:h-7 rounded-lg bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400 flex-shrink-0">
                  <TrendingDown className="w-3.5 h-3.5" />
                </div>
                <span className="text-[8.5px] sm:text-[9.5px] text-slate-400 uppercase tracking-wider font-bold truncate">Current DD</span>
              </div>
              <div>
                <span className={`text-xs sm:text-sm md:text-base font-black block whitespace-nowrap leading-tight ${govStats.current_drawdown_r >= -5.0 ? 'text-emerald-400' : (govStats.current_drawdown_r <= -15.0 ? 'text-rose-400' : 'text-amber-400')}`}>
                  {govStats.current_drawdown_r >= 0 ? '+' : ''}{govStats.current_drawdown_r.toFixed(2)} R
                </span>
                <span className="text-[8px] sm:text-[8.5px] text-slate-400 block whitespace-nowrap leading-tight mt-0.5">
                  (-{Math.abs((govStats.current_drawdown_r * 200 / initialCap) * 100).toFixed(2)}%)
                </span>
              </div>
            </div>

            {/* Card 2: Peak Drawdown */}
            <div className="p-2 sm:p-2.5 md:p-3 rounded-2xl border border-rose-500/25 bg-[#080C16] flex flex-col justify-between shadow-lg min-w-0">
              <div className="flex items-center gap-1.5 mb-1.5">
                <div className="w-6 h-6 sm:w-7 sm:h-7 rounded-lg bg-rose-500/10 border border-rose-500/25 flex items-center justify-center text-rose-400 flex-shrink-0">
                  <Activity className="w-3.5 h-3.5" />
                </div>
                <span className="text-[8.5px] sm:text-[9.5px] text-slate-400 uppercase tracking-wider font-bold truncate">Peak DD</span>
              </div>
              <div>
                <span className="text-xs sm:text-sm md:text-base font-black text-rose-400 block whitespace-nowrap leading-tight">
                  {govStats.max_drawdown_r.toFixed(2)} R
                </span>
                <span className="text-[8px] sm:text-[8.5px] text-slate-400 block whitespace-nowrap leading-tight mt-0.5">
                  (-{Math.abs((govStats.max_drawdown_r * 200 / initialCap) * 100).toFixed(2)}%)
                </span>
              </div>
            </div>

            {/* Card 3: Normal Target */}
            <div className="p-2 sm:p-2.5 md:p-3 rounded-2xl border border-cyan-500/25 bg-[#080C16] flex flex-col justify-between shadow-lg min-w-0">
              <div className="flex items-center gap-1.5 mb-1.5">
                <div className="w-6 h-6 sm:w-7 sm:h-7 rounded-lg bg-cyan-500/10 border border-cyan-500/25 flex items-center justify-center text-cyan-300 flex-shrink-0">
                  <Target className="w-3.5 h-3.5" />
                </div>
                <span className="text-[8.5px] sm:text-[9.5px] text-slate-400 uppercase tracking-wider font-bold truncate">Normal Target</span>
              </div>
              <div>
                <span className="text-xs sm:text-sm md:text-base font-black text-cyan-300 block whitespace-nowrap leading-tight">
                  {(govStats.recovery_threshold_r !== undefined ? govStats.recovery_threshold_r : -5.0).toFixed(2)} R
                </span>
                <span className="text-[8px] sm:text-[8.5px] text-slate-400 block whitespace-nowrap leading-tight mt-0.5">
                  (-{Math.abs(((govStats.recovery_threshold_r !== undefined ? govStats.recovery_threshold_r : -5.0) * 200 / initialCap) * 100).toFixed(2)}%)
                </span>
              </div>
            </div>
          </div>

          {/* Governor Recovery Progress Banner Card */}
          <div className="p-3 sm:p-3.5 rounded-2xl border border-white/10 bg-[#080C16] font-mono space-y-2 shadow-lg">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="text-amber-400">
                  <ShieldCheck className="w-4 h-4" />
                </div>
                <h4 className="text-xs font-black text-white uppercase tracking-wider">Governor Recovery</h4>
              </div>
              <span className="px-2 py-0.5 rounded-full text-[8.5px] font-extrabold bg-sky-500/15 text-cyan-300 border border-cyan-500/30 flex items-center gap-1">
                <span>Cap to Normal Mode</span>
                <strong>{govStats.recovery_pct || 0}%</strong>
              </span>
            </div>

            <div className="flex items-center justify-between text-[9.5px]">
              <span className="text-slate-400 font-bold">Progress to Normal Mode</span>
              <div className="text-right">
                <span className="text-xs sm:text-sm font-black text-emerald-400">
                  {govStats.recovery_pct || 0}%
                </span>
                <span className="text-[8.5px] text-slate-400 ml-1">
                  ({govStats.distance_to_normal_r > 0 ? `${govStats.distance_to_normal_r.toFixed(2)} R gap` : '0.00 R'} / ~120%)
                </span>
              </div>
            </div>

            {/* Rounded Gradient Progress Bar */}
            <div className="w-full bg-[#0B101E] rounded-full h-2 overflow-hidden border border-white/10">
              <div 
                className="h-full rounded-full bg-gradient-to-r from-amber-500 via-cyan-400 to-emerald-400 transition-all duration-500" 
                style={{ width: `${Math.min(100, Math.max(0, govStats.recovery_pct || 0))}%` }}
              />
            </div>

            {/* 4-Item Legend Strip */}
            <div className="grid grid-cols-4 gap-1 text-[8px] text-slate-400 pt-1 border-t border-white/5">
              <div className="flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                <span>Trough: <strong className="text-slate-200">{govStats.max_drawdown_r.toFixed(2)} R</strong></span>
              </div>
              <div className="flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400"></span>
                <span>Normal: <strong className="text-slate-200">-5.00 R</strong></span>
              </div>
              <div className="flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                <span>Peak: <strong className="text-slate-200">{(govStats.peak_realized_r || 0).toFixed(2)} R</strong></span>
              </div>
              <div className="flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-purple-400"></span>
                <span>MMR: <strong className="text-slate-200">{(govStats.current_drawdown_r + 5.0).toFixed(2)} R</strong></span>
              </div>
            </div>
          </div>

          {/* Curve 2 Card: Dynamic Risk Governor & Drawdown Recovery Curve */}
          <div className="p-3.5 sm:p-4 rounded-2xl relative overflow-hidden border border-white/10 shadow-2xl bg-[#080C16]">
            {/* Card Header with Timeframe Pills */}
            <div className="flex items-center justify-between pb-2.5 border-b border-white/5 flex-wrap gap-2">
              <div className="flex items-center gap-2">
                <div className="text-cyan-400">
                  <BarChart2 className="w-4 h-4" />
                </div>
                <h3 className="text-xs font-black text-white font-mono uppercase tracking-wider">
                  Equity &amp; Risk Chart
                </h3>
              </div>
              {/* Timeframe Pills (1W 1M 3M 6M ALL) */}
              <div className="flex items-center bg-[#0B101E] p-0.5 rounded-lg border border-white/5 font-mono text-[10px]">
                {['1W', '1M', '3M', '6M', 'ALL'].map(tf => (
                  <button
                    key={tf}
                    onClick={() => setDdTimeframe(tf)}
                    className={`px-2 py-0.5 rounded-md transition-all ${
                      ddTimeframe === tf 
                        ? 'bg-cyan-400 text-black font-black' 
                        : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    {tf}
                  </button>
                ))}
              </div>
            </div>

            {/* SVG Container */}
            <div 
              ref={ddContainerRef}
              onMouseMove={(e) => handleDdHover(e.clientX)}
              onMouseLeave={() => setHoverDd(null)}
              onTouchMove={(e) => e.touches?.[0] && handleDdHover(e.touches[0].clientX)}
              onTouchEnd={() => setHoverDd(null)}
              className="relative w-full h-60 sm:h-64 mt-2.5 select-none rounded-xl bg-[#060912] border border-white/5 overflow-hidden"
            >
              <svg viewBox={`0 0 ${W} ${H_DD}`} className="w-full h-full overflow-hidden absolute inset-0" preserveAspectRatio="none">
                <defs>
                  <linearGradient id="reactDdAreaClean" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="rgba(245, 158, 11, 0.02)" />
                    <stop offset="100%" stopColor="rgba(245, 158, 11, 0.18)" />
                  </linearGradient>
                </defs>

                {/* Shaded Zones */}
                <rect x={pad.left} y={yDdZero} width={plotW} height={Math.max(0, yDdNormal - yDdZero)} fill="rgba(16, 185, 129, 0.08)" />
                <rect x={pad.left} y={yDdNormal} width={plotW} height={Math.max(0, yDdDefensive - yDdNormal)} fill="rgba(245, 158, 11, 0.08)" />
                <rect x={pad.left} y={yDdDefensive} width={plotW} height={Math.max(0, yDdBottom - yDdDefensive)} fill="rgba(244, 63, 94, 0.08)" />

                {/* Threshold Lines */}
                <line x1={pad.left} y1={yDdZero} x2={W - pad.right} y2={yDdZero} stroke="rgba(255, 255, 255, 0.2)" strokeWidth="1.2" strokeDasharray="4,4" />
                <line x1={pad.left} y1={yDdNormal} x2={W - pad.right} y2={yDdNormal} stroke="#00F0FF" strokeWidth="1.5" strokeDasharray="5,4" />
                <line x1={pad.left} y1={getDdY(-10.0)} x2={W - pad.right} y2={getDdY(-10.0)} stroke="rgba(245, 158, 11, 0.4)" strokeWidth="1" strokeDasharray="4,4" />
                <line x1={pad.left} y1={yDdDefensive} x2={W - pad.right} y2={yDdDefensive} stroke="#FF3366" strokeWidth="1.5" strokeDasharray="5,4" />
                <line x1={pad.left} y1={getDdY(-20.0)} x2={W - pad.right} y2={getDdY(-20.0)} stroke="rgba(255, 255, 255, 0.08)" strokeWidth="1" strokeDasharray="3,3" />

                {/* Drawdown Area */}
                <path d={ddAreaD} fill="url(#reactDdAreaClean)" />

                {/* Crisp Solid Drawdown Line (ZERO GLOW FILTER) */}
                <path d={ddPathD} fill="none" stroke="#F59E0B" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />

                {/* Trough Marker */}
                <circle cx={getDdX(fTroughIdx)} cy={getDdY(fMinDdVal)} r="4" fill="#FFFFFF" stroke="#EC4899" strokeWidth="2.5" />

                {/* Current Marker */}
                <circle cx={getDdX(fDdLastIdx)} cy={getDdY(filteredDdPoints[fDdLastIdx].drawdown_r)} r="4.5" fill="#FFFFFF" stroke="#F59E0B" strokeWidth="2.5" />

                {/* Hover Crosshair */}
                {hoverDd && (
                  <g>
                    <line x1={hoverDd.x} y1={pad.top} x2={hoverDd.x} y2={pad.top + plotH_DD} stroke="rgba(245, 158, 11, 0.8)" strokeWidth="1.2" strokeDasharray="3,3" />
                    <circle cx={hoverDd.x} cy={hoverDd.y} r="4.5" fill="#F59E0B" stroke="#FFFFFF" strokeWidth="2" />
                  </g>
                )}
              </svg>

              {/* Hover Tooltip */}
              {hoverDd && (
                <div 
                  className="absolute pointer-events-none z-40 bg-[#0B1120]/95 backdrop-blur-md border border-amber-500/40 rounded-xl p-2.5 shadow-2xl text-[9.5px] font-mono space-y-0.5"
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
                    <span className="font-bold text-cyan-400">
                      {Math.abs(hoverDd.point.drawdown_r) <= 5.0 ? 'Normal Mode Active' : `Need +${(Math.abs(hoverDd.point.drawdown_r) - 5.0).toFixed(2)} R (~₹${Math.round((Math.abs(hoverDd.point.drawdown_r) - 5.0) * 200)})`}
                    </span>
                  </div>
                  <div className="text-[8px] text-slate-500 pt-0.5">{hoverDd.point.trade_date} {hoverDd.point.time || ''}</div>
                </div>
              )}
            </div>
          </div>

          {/* Bottom 4-Card Metric Strip */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono">
            {/* Metric 1: Normal Mode */}
            <div className="p-2 rounded-xl border border-white/5 bg-[#080C16] text-center shadow-md">
              <div className="flex items-center justify-center gap-1 text-cyan-400 mb-0.5">
                <BarChart2 className="w-3 h-3" />
                <span className="text-[8px] text-slate-400 uppercase tracking-wider font-bold">Normal Mode</span>
              </div>
              <span className="text-xs font-black text-amber-400 block">{govStats.recovery_pct || 0}%</span>
              <span className="text-[7.5px] text-slate-400 block">
                ({govStats.distance_to_normal_r > 0 ? `${govStats.distance_to_normal_r.toFixed(2)} R` : '0.00 R'})
              </span>
            </div>

            {/* Metric 2: Max Drawdown */}
            <div className="p-2 rounded-xl border border-white/5 bg-[#080C16] text-center shadow-md">
              <div className="flex items-center justify-center gap-1 text-rose-400 mb-0.5">
                <ShieldAlert className="w-3 h-3" />
                <span className="text-[8px] text-slate-400 uppercase tracking-wider font-bold">Max Drawdown</span>
              </div>
              <span className="text-xs font-black text-rose-400 block">{govStats.max_drawdown_r.toFixed(2)} R</span>
              <span className="text-[7.5px] text-slate-400 block">
                (-{Math.abs((govStats.max_drawdown_r * 200 / initialCap) * 100).toFixed(2)}%)
              </span>
            </div>

            {/* Metric 3: Target */}
            <div className="p-2 rounded-xl border border-white/5 bg-[#080C16] text-center shadow-md">
              <div className="flex items-center justify-center gap-1 text-cyan-400 mb-0.5">
                <Target className="w-3 h-3" />
                <span className="text-[8px] text-slate-400 uppercase tracking-wider font-bold">Target</span>
              </div>
              <span className="text-xs font-black text-cyan-300 block">-5.00 R</span>
              <span className="text-[7.5px] text-slate-400 block">(-0.18%)</span>
            </div>

            {/* Metric 4: Recovery Progress */}
            <div className="p-2 rounded-xl border border-white/5 bg-[#080C16] text-center shadow-md">
              <div className="flex items-center justify-center gap-1 text-emerald-400 mb-0.5">
                <RefreshCw className="w-3 h-3" />
                <span className="text-[8px] text-slate-400 uppercase tracking-wider font-bold">Recovery</span>
              </div>
              <span className="text-xs font-black text-emerald-400 block">{govStats.recovery_pct || 0}%</span>
              <div className="w-full bg-[#0B101E] rounded-full h-1 overflow-hidden mt-1 border border-white/10">
                <div 
                  className="h-full rounded-full bg-emerald-500" 
                  style={{ width: `${Math.min(100, Math.max(0, govStats.recovery_pct || 0))}%` }}
                />
              </div>
            </div>
          </div>

        </div>

      </div>

    </div>
  );
}
