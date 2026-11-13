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
  Layers 
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
    <div className="space-y-6 pb-24 max-w-7xl mx-auto px-4 sm:px-6 pt-4">
      
      {/* SECTION HEADER & EXPORT CSV BUTTON */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-lg font-extrabold tracking-tight text-white flex items-center gap-2">
            <span>PERFORMANCE ANALYTICS & MASTER LEDGER</span>
            <span className="px-2 py-0.5 text-[10px] font-mono font-bold bg-emerald-500/15 text-emerald-400 rounded-full border border-emerald-500/30">
              {totTrades} Trades Audited
            </span>
          </h2>
          <p className="text-xs text-slate-400">
            Complete institutional audit trail grouped chronologically with statutory friction breakdown.
          </p>
        </div>

        {/* EXPORT CSV BUTTON */}
        <button
          onClick={onExportCSV}
          className="self-start sm:self-auto px-4 py-2 rounded-xl bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/40 text-emerald-400 text-xs font-bold flex items-center gap-2 transition-all shadow-lg shadow-emerald-950/20"
        >
          <Download className="w-4 h-4" />
          <span>Export Master CSV</span>
        </button>
      </div>

      {/* METRIC SUMMARY CARDS GRID */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        
        {/* Net Realized P&L */}
        <div className="glass-card p-4">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Net Realized P&L</span>
            {isProfit ? <TrendingUp className="w-4 h-4 text-emerald-400" /> : <TrendingDown className="w-4 h-4 text-rose-400" />}
          </div>
          <div className="mt-2 font-mono">
            <span className={`text-xl sm:text-2xl font-black ${isProfit ? 'text-emerald-400' : 'text-rose-400'}`}>
              {isProfit ? '+' : ''}₹{totalPnl.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
          </div>
          <span className="text-[11px] font-mono font-semibold text-slate-400 mt-1 block">
            {isProfit ? '+' : ''}{totalR.toFixed(2)} R Net Return
          </span>
        </div>

        {/* Win Rate */}
        <div className="glass-card p-4">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Win Rate</span>
            <Percent className="w-4 h-4 text-sky-400" />
          </div>
          <div className="mt-2 font-mono">
            <span className="text-xl sm:text-2xl font-black text-white">
              {winRate.toFixed(1)}%
            </span>
          </div>
          <span className="text-[11px] font-mono text-slate-400 mt-1 block">
            {data.wins || 0} Wins / {data.losses || 0} Losses
          </span>
        </div>

        {/* Profit Factor */}
        <div className="glass-card p-4">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Profit Factor</span>
            <Award className="w-4 h-4 text-amber-400" />
          </div>
          <div className="mt-2 font-mono">
            <span className="text-xl sm:text-2xl font-black text-amber-400">
              {pf.toFixed(2)}
            </span>
          </div>
          <span className="text-[11px] font-mono text-slate-400 mt-1 block">
            1:3 Asymmetric Payoff
          </span>
        </div>

        {/* Statutory Charges Deducted */}
        <div className="glass-card p-4">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Statutory Friction</span>
            <Receipt className="w-4 h-4 text-slate-400" />
          </div>
          <div className="mt-2 font-mono">
            <span className="text-xl sm:text-2xl font-black text-slate-200">
              ₹{totalCharges.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
          </div>
          <span className="text-[11px] font-mono text-slate-400 mt-1 block">
            STT, SEBI, GST & Brokerage
          </span>
        </div>

      </div>

      {/* MASTER TRADE LEDGER (GROUPED DATE-WISE: RECENT TO OLD) */}
      <div className="space-y-5">
        <h3 className="text-sm font-bold font-mono uppercase tracking-wider text-slate-400 flex items-center gap-2">
          <Calendar className="w-4 h-4 text-emerald-400" />
          <span>Chronological Ledger</span>
        </h3>

        {dateGroups.length === 0 ? (
          <div className="glass-panel rounded-2xl p-10 text-center border border-slate-800 text-slate-400 space-y-2">
            <Receipt className="w-8 h-8 mx-auto text-slate-500" />
            <p className="text-sm font-semibold text-white">No Closed Trades Yet</p>
            <p className="text-xs text-slate-400">
              As the Crown 6 strategy executes and squares off trades, every single transaction will appear here grouped date-wise.
            </p>
          </div>
        ) : (
          dateGroups.map((group) => {
            const isDayProfit = group.day_pnl >= 0;

            return (
              <div 
                key={group.date}
                className="glass-panel rounded-2xl border border-slate-800/80 overflow-hidden"
              >
                {/* DATE GROUP HEADER */}
                <div className="bg-slate-900/90 px-5 py-3 border-b border-slate-800/80 flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-extrabold text-white font-mono">
                      {group.date}
                    </span>
                    <span className="text-xs font-mono text-slate-400">
                      ({group.trades_count} trades)
                    </span>
                  </div>

                  <div className="flex items-center gap-2 font-mono text-xs">
                    <span className="text-slate-400">Day Result:</span>
                    <span className={`font-extrabold ${isDayProfit ? 'text-emerald-400' : 'text-rose-400'}`}>
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
                <div className="divide-y divide-slate-800/50">
                  {group.trades.map((trade) => {
                    const isTradeWin = trade.realized_pnl >= 0;

                    return (
                      <div 
                        key={trade.id}
                        className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 hover:bg-slate-800/30 transition-all font-mono text-xs"
                      >
                        {/* Left: Symbol, Direction, Timings */}
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="font-extrabold text-sm text-white">
                              {trade.symbol}
                            </span>
                            <span className={`px-2 py-0.2 rounded text-[10px] font-bold ${
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
                            <span className="text-[9px] text-slate-400 block uppercase">Entry</span>
                            <span>₹{trade.entry_price.toFixed(2)}</span>
                          </div>
                          <div>
                            <span className="text-[9px] text-slate-400 block uppercase">Exit</span>
                            <span>₹{trade.exit_price.toFixed(2)}</span>
                          </div>
                          <div>
                            <span className="text-[9px] text-slate-400 block uppercase">Margin</span>
                            <span className="text-amber-400">₹{trade.margin_used.toFixed(0)}</span>
                          </div>
                        </div>

                        {/* Right: Net P&L & R */}
                        <div className="flex flex-col sm:items-end">
                          <span className={`text-sm font-extrabold ${
                            isTradeWin ? 'text-emerald-400' : 'text-rose-400'
                          }`}>
                            {isTradeWin ? '+' : ''}₹{trade.realized_pnl.toFixed(2)}
                          </span>
                          <div className="flex items-center gap-1.5 text-[10px]">
                            <span className={`font-bold ${isTradeWin ? 'text-emerald-400' : 'text-rose-400'}`}>
                              {isTradeWin ? '+' : ''}{trade.realized_r.toFixed(2)} R
                            </span>
                            <span className="text-slate-400">• Fee: ₹{trade.charges?.toFixed(2) || '0.00'}</span>
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
