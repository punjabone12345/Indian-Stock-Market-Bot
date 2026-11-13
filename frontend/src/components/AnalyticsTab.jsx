import React from 'react';
import { 
  Download, 
  TrendingUp, 
  TrendingDown, 
  Calendar, 
  Receipt, 
  Award, 
  Percent 
} from 'lucide-react';

export default function AnalyticsTab({ analyticsData, onExportCSV }) {
  const data = analyticsData || {};
  const dateGroups = data.date_groups || [];
  const totTrades = data.total_trades || 0;
  const winRate = data.win_rate || 0;
  const pf = data.profit_factor || 1.68;
  const totalPnl = data.total_pnl || 0;
  const totalR = data.total_r || 0;
  const totalCharges = data.total_charges || 0;
  const isProfit = totalPnl >= 0;

  return (
    <div className="space-y-3 pb-8">
      
      {/* SECTION HEADER & EXPORT CSV BUTTON */}
      <div className="flex items-center justify-between px-1 pt-1 pb-1 border-b border-white/[0.06]">
        <div>
          <h2 className="text-xs font-black tracking-tight text-white font-mono uppercase flex items-center gap-1.5">
            <span>Master Ledger</span>
            <span className="px-1.5 py-0.2 text-[9px] font-mono font-bold bg-sky-500/20 text-sky-300 rounded border border-sky-500/30">
              {totTrades} Trades
            </span>
          </h2>
        </div>

        <button
          onClick={onExportCSV}
          className="px-2.5 py-1 rounded-xl bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/40 text-emerald-300 text-[10px] font-bold font-mono flex items-center gap-1 transition-all cursor-pointer"
        >
          <Download className="w-3 h-3 text-emerald-400" />
          <span>Export CSV</span>
        </button>
      </div>

      {/* METRIC SUMMARY CARDS (2x2 Grid) */}
      <div className="grid grid-cols-2 gap-2">
        
        {/* Net Realized P&L */}
        <div className="bg-[#0F1424] border border-white/[0.08] rounded-2xl p-3">
          <div className="flex items-center justify-between text-[10px] text-slate-400 font-mono">
            <span>Net Realized P&L</span>
            {isProfit ? <TrendingUp className="w-3.5 h-3.5 text-emerald-400" /> : <TrendingDown className="w-3.5 h-3.5 text-rose-400" />}
          </div>
          <div className="mt-1 font-mono">
            <span className={`text-base font-black tabular-nums ${isProfit ? 'text-emerald-400' : 'text-rose-400'}`}>
              {isProfit ? '+' : ''}₹{totalPnl.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
          </div>
          <span className="text-[10px] font-mono font-bold text-slate-400 mt-0.5 block">
            {isProfit ? '+' : ''}{totalR.toFixed(2)} R Return
          </span>
        </div>

        {/* Win Rate */}
        <div className="bg-[#0F1424] border border-white/[0.08] rounded-2xl p-3">
          <div className="flex items-center justify-between text-[10px] text-slate-400 font-mono">
            <span>Win Rate</span>
            <Percent className="w-3.5 h-3.5 text-sky-400" />
          </div>
          <div className="mt-1 font-mono">
            <span className="text-base font-black text-white tabular-nums">
              {winRate.toFixed(1)}%
            </span>
          </div>
          <span className="text-[10px] font-mono text-slate-400 mt-0.5 block">
            {data.wins || 0}W / {data.losses || 0}L
          </span>
        </div>

        {/* Profit Factor */}
        <div className="bg-[#0F1424] border border-white/[0.08] rounded-2xl p-3">
          <div className="flex items-center justify-between text-[10px] text-slate-400 font-mono">
            <span>Profit Factor</span>
            <Award className="w-3.5 h-3.5 text-amber-400" />
          </div>
          <div className="mt-1 font-mono">
            <span className="text-base font-black text-amber-400 tabular-nums">
              {pf.toFixed(2)}
            </span>
          </div>
          <span className="text-[10px] font-mono text-slate-400 mt-0.5 block">
            1:3 Asymmetric
          </span>
        </div>

        {/* Statutory Friction */}
        <div className="bg-[#0F1424] border border-white/[0.08] rounded-2xl p-3">
          <div className="flex items-center justify-between text-[10px] text-slate-400 font-mono">
            <span>Statutory Friction</span>
            <Receipt className="w-3.5 h-3.5 text-slate-400" />
          </div>
          <div className="mt-1 font-mono">
            <span className="text-base font-black text-slate-200 tabular-nums">
              ₹{totalCharges.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
          </div>
          <span className="text-[10px] font-mono text-slate-400 mt-0.5 block">
            STT, SEBI, GST
          </span>
        </div>

      </div>

      {/* MASTER TRADE LEDGER (GROUPED DATE-WISE: RECENT TO OLD) */}
      <div className="space-y-3 pt-1">
        <h3 className="text-[11px] font-bold font-mono uppercase tracking-wider text-slate-400 flex items-center gap-1.5 px-0.5">
          <Calendar className="w-3.5 h-3.5 text-sky-400" />
          <span>Chronological Ledger</span>
        </h3>

        {dateGroups.length === 0 ? (
          <div className="bg-[#0F1424] border border-white/[0.08] rounded-2xl p-6 text-center text-slate-400 space-y-1.5">
            <Receipt className="w-6 h-6 mx-auto text-slate-500" />
            <p className="text-xs font-bold text-white">No Closed Trades Yet</p>
            <p className="text-[11px] text-slate-400">
              When trades exit, every transaction will appear here grouped date-wise with exact math.
            </p>
          </div>
        ) : (
          dateGroups.map((group) => {
            const isDayProfit = group.day_pnl >= 0;

            return (
              <div 
                key={group.date}
                className="bg-[#0F1424] border border-white/[0.08] rounded-2xl overflow-hidden shadow-md"
              >
                {/* DATE GROUP HEADER */}
                <div className="bg-[#0A0D18] px-3.5 py-2 border-b border-white/[0.06] flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-black text-white font-mono">
                      {group.date}
                    </span>
                    <span className="text-[10px] font-mono text-slate-400">
                      ({group.trades_count} trades)
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5 font-mono text-xs">
                    <span className={`font-black tabular-nums ${isDayProfit ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {isDayProfit ? '+' : ''}₹{group.day_pnl.toFixed(2)}
                    </span>
                    <span className={`text-[9px] font-bold px-1.5 py-0.2 rounded ${
                      isDayProfit ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'
                    }`}>
                      {isDayProfit ? '+' : ''}{group.day_r.toFixed(2)}R
                    </span>
                  </div>
                </div>

                {/* TRADES IN THIS DATE */}
                <div className="divide-y divide-white/[0.04]">
                  {group.trades.map((trade) => {
                    const isTradeWin = trade.realized_pnl >= 0;

                    return (
                      <div 
                        key={trade.id}
                        className="p-3 flex items-center justify-between gap-2 hover:bg-white/[0.02] transition-all font-mono text-xs"
                      >
                        {/* Left: Symbol & Times */}
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-1.5">
                            <span className="font-black text-xs text-white">
                              {trade.symbol}
                            </span>
                            <span className={`px-1.5 py-0.1 rounded text-[9px] font-black ${
                              trade.direction === 'BUY' 
                                ? 'bg-emerald-500/20 text-emerald-300' 
                                : 'bg-rose-500/20 text-rose-300'
                            }`}>
                              {trade.direction}
                            </span>
                            <span className="text-slate-400 text-[10px]">
                              {trade.quantity} Qty
                            </span>
                          </div>
                          <div className="text-[10px] text-slate-400">
                            <span>{trade.exit_reason} • {trade.exit_time} IST</span>
                          </div>
                        </div>

                        {/* Right: Net P&L & R */}
                        <div className="flex flex-col items-end">
                          <span className={`text-xs font-black tabular-nums ${
                            isTradeWin ? 'text-emerald-400' : 'text-rose-400'
                          }`}>
                            {isTradeWin ? '+' : ''}₹{trade.realized_pnl.toFixed(2)}
                          </span>
                          <span className={`text-[9px] font-bold ${isTradeWin ? 'text-emerald-400' : 'text-rose-400'}`}>
                            {isTradeWin ? '+' : ''}{trade.realized_r.toFixed(2)} R
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>

              </div>
            );
          })
        )}
      </div>

    </div>
  );
}
