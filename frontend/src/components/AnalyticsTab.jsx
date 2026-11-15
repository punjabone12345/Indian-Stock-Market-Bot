import React, { useState } from 'react';
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
  ShieldCheck
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
            <span className="text-amber-400">1:3 Asymmetric RRR</span>
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
            const isGrpProfit = (grp.total_pnl || 0) >= 0;
            const isExpanded = expandedDates[grp.date] !== false; // expanded by default

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
                      {isGrpProfit ? '+' : ''}₹{(grp.total_pnl || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
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
                            <div className="flex items-center gap-2 text-[10px] text-slate-400">
                              <span>Entry: {t.entry_time}</span>
                              <span>•</span>
                              <span>Exit: {t.exit_time}</span>
                              <span>•</span>
                              <span>₹{t.entry_price?.toFixed(2)} → ₹{t.exit_price?.toFixed(2)}</span>
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
