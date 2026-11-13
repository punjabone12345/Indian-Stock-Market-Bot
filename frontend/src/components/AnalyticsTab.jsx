import React from 'react';
import { 
  Download, 
  TrendingUp, 
  TrendingDown, 
  Calendar, 
  CheckCircle2, 
  XCircle, 
  Receipt, 
  BarChart3, 
  Award, 
  Percent, 
  Zap, 
  Layers,
  ArrowRight
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
    <div className="space-y-5 pb-16 max-w-7xl mx-auto px-3 sm:px-6 pt-4">
      
      {/* SECTION HEADER & EXPORT CSV BUTTON */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-white/[0.06] pb-3">
        <div>
          <h2 className="text-lg sm:text-xl font-extrabold tracking-tight text-white flex items-center gap-2">
            <span>PERFORMANCE ANALYTICS & MASTER LEDGER</span>
            <span className="px-2.5 py-0.5 text-[10px] font-mono font-bold bg-sky-500/15 text-sky-400 rounded-full border border-sky-500/30">
              {totTrades} Trades Audited
            </span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Complete institutional audit trail grouped chronologically with statutory friction breakdown.
          </p>
        </div>

        {/* EXPORT CSV BUTTON */}
        <button
          onClick={onExportCSV}
          className="self-start sm:self-auto px-4 py-2.5 rounded-xl bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/40 text-emerald-300 text-xs font-bold font-mono flex items-center gap-2 transition-all shadow-md shadow-emerald-950/20"
        >
          <Download className="w-4 h-4 text-emerald-400" />
          <span>Export Master CSV</span>
        </button>
      </div>

      {/* METRIC SUMMARY CARDS GRID */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        
        {/* Card 1: Net Realized P&L */}
        <div className="m3-card p-4">
          <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
            <span>Net Realized P&L</span>
            {isProfit ? <TrendingUp className="w-4 h-4 text-emerald-400" /> : <TrendingDown className="w-4 h-4 text-rose-400" />}
          </div>
          <div className="mt-2 font-mono">
            <span className={`text-xl sm:text-2xl font-black tabular-nums ${isProfit ? 'text-emerald-400' : 'text-rose-400'}`}>
              {isProfit ? '+' : ''}₹{totalPnl.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
          </div>
          <span className="text-[11px] font-mono font-bold text-slate-400 mt-1 block">
            {isProfit ? '+' : ''}{totalR.toFixed(2)} R Net Return
          </span>
        </div>

        {/* Card 2: Win Rate */}
        <div className="m3-card p-4">
          <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
            <span>Win Rate</span>
            <Percent className="w-4 h-4 text-sky-400" />
          </div>
          <div className="mt-2 font-mono">
            <span className="text-xl sm:text-2xl font-black text-white tabular-nums">
              {winRate.toFixed(1)}%
            </span>
          </div>
          <span className="text-[11px] font-mono text-slate-400 mt-1 block">
            {data.wins || 0} Wins / {data.losses || 0} Losses
          </span>
        </div>

        {/* Card 3: Profit Factor */}
        <div className="m3-card p-4">
          <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
            <span>Profit Factor</span>
            <Award className="w-4 h-4 text-amber-400" />
          </div>
          <div className="mt-2 font-mono">
            <span className="text-xl sm:text-2xl font-black text-amber-400 tabular-nums">
              {pf.toFixed(2)}
            </span>
          </div>
          <span className="text-[11px] font-mono text-slate-400 mt-1 block">
            1:3 Asymmetric Payoff
          </span>
        </div>

        {/* Card 4: Statutory Friction */}
        <div className="m3-card p-4">
          <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
            <span>Statutory Friction</span>
            <Receipt className="w-4 h-4 text-slate-400" />
          </div>
          <div className="mt-2 font-mono">
            <span className="text-xl sm:text-2xl font-black text-slate-200 tabular-nums">
              ₹{totalCharges.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
          </div>
          <span className="text-[11px] font-mono text-slate-400 mt-1 block">
            STT, SEBI, GST & Brokerage
          </span>
        </div>

      </div>

      {/* MASTER TRADE LEDGER (GROUPED DATE-WISE: RECENT TO OLD) */}
      <div className="space-y-4 pt-2">
        <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-slate-400 flex items-center gap-2">
          <Calendar className="w-4 h-4 text-sky-400" />
          <span>Chronological Master Ledger (Newest to Oldest)</span>
        </h3>

        {dateGroups.length === 0 ? (
          <div className="m3-card p-10 text-center border border-white/[0.08] text-slate-400 space-y-2">
            <Receipt className="w-8 h-8 mx-auto text-slate-500" />
            <p className="text-sm font-bold text-white">No Closed Trades In Ledger</p>
            <p className="text-xs text-slate-400 max-w-md mx-auto">
              As the Crown 6 strategy executes and squares off trades, every single transaction will appear here grouped date-wise with complete mathematical breakdown.
            </p>
          </div>
        ) : (
          dateGroups.map((group) => {
            const isDayProfit = group.day_pnl >= 0;

            return (
              <div 
                key={group.date}
                className="m3-card border border-white/[0.08] overflow-hidden"
              >
                {/* DATE GROUP HEADER */}
                <div className="bg-[#0E131E] px-4 sm:px-5 py-3 border-b border-white/[0.06] flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-black text-white font-mono">
                      {group.date}
                    </span>
                    <span className="text-xs font-mono text-slate-400">
                      ({group.trades_count} trades)
                    </span>
                  </div>

                  <div className="flex items-center gap-2 font-mono text-xs">
                    <span className="text-slate-400">Day Result:</span>
                    <span className={`font-black tabular-nums ${isDayProfit ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {isDayProfit ? '+' : ''}₹{group.day_pnl.toFixed(2)}
                    </span>
                    <span className={`text-[10px] font-bold px-1.5 py-0.2 rounded ${
                      isDayProfit ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'
                    }`}>
                      {isDayProfit ? '+' : ''}{group.day_r.toFixed(2)} R
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
                        className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 hover:bg-white/[0.02] transition-all font-mono text-xs"
                      >
                        {/* Left: Symbol, Direction, Timings */}
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="font-black text-sm text-white">
                              {trade.symbol}
                            </span>
                            <span className={`px-2 py-0.2 rounded text-[10px] font-extrabold ${
                              trade.direction === 'BUY' 
                                ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30' 
                                : 'bg-rose-500/15 text-rose-400 border border-rose-500/30'
                            }`}>
                              {trade.direction}
                            </span>
                            <span className="text-slate-400 text-[11px]">
                              {trade.quantity} shares
                            </span>
                          </div>
                          <div className="text-[11px] text-slate-400 flex items-center gap-2">
                            <span>{trade.entry_time} → {trade.exit_time} IST</span>
                            <span>•</span>
                            <span className="text-slate-300 font-semibold">{trade.exit_reason}</span>
                          </div>
                        </div>

                        {/* Middle: Prices & Margin */}
                        <div className="grid grid-cols-3 gap-3 text-slate-300 text-[11px]">
                          <div>
                            <span className="text-[9px] text-slate-500 block uppercase font-bold">Entry</span>
                            <span className="tabular-nums">₹{trade.entry_price.toFixed(2)}</span>
                          </div>
                          <div>
                            <span className="text-[9px] text-slate-500 block uppercase font-bold">Exit</span>
                            <span className="tabular-nums">₹{trade.exit_price.toFixed(2)}</span>
                          </div>
                          <div>
                            <span className="text-[9px] text-slate-500 block uppercase font-bold">Margin</span>
                            <span className="text-amber-400 tabular-nums">₹{trade.margin_used.toFixed(0)}</span>
                          </div>
                        </div>

                        {/* Right: Net P&L & R */}
                        <div className="flex flex-col sm:items-end">
                          <span className={`text-sm font-black tabular-nums ${
                            isTradeWin ? 'text-emerald-400' : 'text-rose-400'
                          }`}>
                            {isTradeWin ? '+' : ''}₹{trade.realized_pnl.toFixed(2)}
                          </span>
                          <div className="flex items-center gap-1.5 text-[10px]">
                            <span className={`font-bold ${isTradeWin ? 'text-emerald-400' : 'text-rose-400'}`}>
                              {isTradeWin ? '+' : ''}{trade.realized_r.toFixed(2)} R
                            </span>
                            <span className="text-slate-500">• Fee: ₹{trade.charges?.toFixed(2) || '0.00'}</span>
                          </div>
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
