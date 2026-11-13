import React, { useState } from 'react';
import { 
  TrendingUp, 
  TrendingDown, 
  Clock, 
  Trash2, 
  Power, 
  AlertCircle, 
  CheckCircle2, 
  ShieldCheck, 
  DollarSign, 
  Layers,
  ArrowRight
} from 'lucide-react';

export default function PositionsTab({ positions = [], onDeletePosition, onClosePosition }) {
  const [selectedForDelete, setSelectedForDelete] = useState(null);
  const [selectedForClose, setSelectedForClose] = useState(null);

  return (
    <div className="space-y-6 pb-24 max-w-7xl mx-auto px-4 sm:px-6 pt-4">
      
      {/* SECTION HEADER */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-extrabold tracking-tight text-white flex items-center gap-2">
            <span>ACTIVE RUNNING POSITIONS</span>
            <span className="px-2 py-0.5 text-[10px] font-mono font-bold bg-emerald-500/15 text-emerald-400 rounded-full border border-emerald-500/30">
              {positions.length} Open
            </span>
          </h2>
          <p className="text-xs text-slate-400">
            Real-time Stop Loss & 1:3 Target tracking under Synthetic OCO broker protection.
          </p>
        </div>
      </div>

      {/* POSITIONS LIST */}
      {positions.length === 0 ? (
        <div className="glass-panel rounded-3xl p-12 text-center border border-slate-800 flex flex-col items-center justify-center space-y-4">
          <div className="w-16 h-16 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center text-slate-500">
            <Layers className="w-8 h-8" />
          </div>
          <div className="space-y-1">
            <h3 className="text-base font-bold text-white">No Running Positions</h3>
            <p className="text-xs text-slate-400 max-w-md mx-auto">
              The Crown 6 algorithmic scanner is actively evaluating 5m EMA9/21 pullbacks for RELIANCE, ITC, MARUTI, TATASTEEL, SUNPHARMA, and INFY.
            </p>
          </div>
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-mono">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
            <span>Scanning Market Ticks</span>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-5">
          {positions.map((pos) => {
            const isLong = pos.direction === 'BUY';
            const pnl = pos.unrealized_pnl || 0;
            const r = pos.unrealized_r || 0;
            const isProfit = pnl >= 0;

            return (
              <div 
                key={pos.id}
                className="glass-card p-5 border border-slate-800/90 relative overflow-hidden flex flex-col justify-between"
              >
                {/* Long/Short accent badge */}
                <div className={`absolute top-0 left-0 right-0 h-[2px] ${
                  isLong ? 'bg-gradient-to-r from-emerald-500 to-teal-400' : 'bg-gradient-to-r from-rose-500 to-amber-500'
                }`} />

                <div>
                  {/* Top Bar: Symbol, Direction, Entry Time */}
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-base font-extrabold text-white font-mono">
                          {pos.symbol}
                        </span>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                          isLong 
                            ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30' 
                            : 'bg-rose-500/15 text-rose-400 border border-rose-500/30'
                        }`}>
                          {pos.direction}
                        </span>
                        <span className="text-[10px] font-mono text-slate-400">
                          {pos.quantity} shares
                        </span>
                      </div>
                      <div className="flex items-center gap-1.5 text-[11px] font-mono text-slate-400 mt-0.5">
                        <Clock className="w-3 h-3" />
                        <span>Entered at {pos.entry_time} IST</span>
                      </div>
                    </div>

                    {/* Live Unrealized P&L */}
                    <div className="flex flex-col items-end">
                      <span className="text-[10px] font-mono uppercase text-slate-400">
                        Live P&L
                      </span>
                      <span className={`text-base font-extrabold font-mono ${
                        isProfit ? 'text-emerald-400' : 'text-rose-400'
                      }`}>
                        {isProfit ? '+' : ''}₹{pnl.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </span>
                      <span className={`text-[10px] font-mono font-semibold px-1.5 py-0.2 rounded mt-0.5 ${
                        isProfit ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'
                      }`}>
                        {isProfit ? '+' : ''}{r.toFixed(2)} R
                      </span>
                    </div>
                  </div>

                  {/* Price Matrix: Entry, Current LTP */}
                  <div className="grid grid-cols-2 gap-3 mt-4 p-3 rounded-xl bg-slate-900/80 border border-slate-800/80 font-mono text-xs">
                    <div>
                      <span className="text-[10px] text-slate-400 block uppercase">Entry Price</span>
                      <span className="text-slate-100 font-bold">₹{pos.entry_price.toFixed(2)}</span>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-400 block uppercase">Current LTP</span>
                      <span className={`font-bold ${isProfit ? 'text-emerald-400' : 'text-rose-400'}`}>
                        ₹{pos.current_price?.toFixed(2) || pos.entry_price.toFixed(2)}
                      </span>
                    </div>
                  </div>

                  {/* Target & Stop Loss Levels */}
                  <div className="grid grid-cols-2 gap-3 mt-2.5 p-3 rounded-xl bg-slate-900/60 border border-slate-800/60 font-mono text-xs">
                    <div>
                      <span className="text-[10px] text-rose-400/80 block uppercase">Stop Loss (Hard SL-M)</span>
                      <span className="text-rose-400 font-bold">₹{pos.stop_loss.toFixed(2)}</span>
                    </div>
                    <div>
                      <span className="text-[10px] text-emerald-400/80 block uppercase">Target (1:3 RRR)</span>
                      <span className="text-emerald-400 font-bold">₹{pos.take_profit.toFixed(2)}</span>
                    </div>
                  </div>

                  {/* Margin & Capital Info */}
                  <div className="mt-3 flex items-center justify-between text-[11px] font-mono text-slate-400 px-1">
                    <span>Margin Locked (5x MIS):</span>
                    <span className="text-amber-400 font-semibold">₹{pos.margin_used.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                  </div>
                </div>

                {/* TWO ACTION BUTTONS: DELETE & CLOSE MANUALLY */}
                <div className="mt-4 pt-3 border-t border-slate-800 flex items-center gap-2.5">
                  
                  {/* BUTTON 1: DELETE (Releases margin, no P&L counted) */}
                  <button
                    onClick={() => setSelectedForDelete(pos)}
                    className="flex-1 py-2 px-3 rounded-xl bg-slate-800/90 hover:bg-slate-700 border border-slate-700/80 text-slate-300 hover:text-white text-xs font-semibold flex items-center justify-center gap-1.5 transition-all"
                  >
                    <Trash2 className="w-3.5 h-3.5 text-slate-400" />
                    <span>Delete</span>
                  </button>

                  {/* BUTTON 2: CLOSE MANUALLY (Exits at market price, records P&L) */}
                  <button
                    onClick={() => setSelectedForClose(pos)}
                    className="flex-1 py-2 px-3 rounded-xl bg-rose-500/15 hover:bg-rose-500/25 border border-rose-500/40 text-rose-400 text-xs font-bold flex items-center justify-center gap-1.5 transition-all shadow-md shadow-rose-950/20"
                  >
                    <Power className="w-3.5 h-3.5" />
                    <span>Close Manually</span>
                  </button>

                </div>

              </div>
            );
          })}
        </div>
      )}

      {/* CONFIRMATION MODAL: DELETE POSITION */}
      {selectedForDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-[#0E121B] border border-slate-700 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-3 rounded-xl bg-slate-800 border border-slate-700 text-slate-300">
                <Trash2 className="w-5 h-5 text-amber-400" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">Delete Position?</h3>
                <p className="text-xs text-slate-400 font-mono">{selectedForDelete.symbol} ({selectedForDelete.direction})</p>
              </div>
            </div>

            <p className="text-sm text-slate-300 leading-relaxed">
              Are you sure you want to <strong>delete this position</strong> from the database?
              <br /><br />
              • Locked margin of <strong className="text-amber-400">₹{selectedForDelete.margin_used.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong> will be released back to your available balance.
              <br />
              • <strong>NO P&L will be counted</strong> for this trade.
            </p>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setSelectedForDelete(null)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white bg-slate-800 border border-slate-700 transition-all"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  onDeletePosition(selectedForDelete.id);
                  setSelectedForDelete(null);
                }}
                className="px-4 py-2 rounded-xl text-xs font-bold text-white bg-amber-600 hover:bg-amber-500 transition-all"
              >
                Confirm Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* CONFIRMATION MODAL: CLOSE MANUALLY */}
      {selectedForClose && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-[#0E121B] border border-rose-500/40 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-3 rounded-xl bg-rose-500/20 border border-rose-500/30 text-rose-400">
                <Power className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">Close Position Manually?</h3>
                <p className="text-xs text-rose-400 font-mono">{selectedForClose.symbol} ({selectedForClose.direction})</p>
              </div>
            </div>

            <p className="text-sm text-slate-300 leading-relaxed">
              Are you sure you want to <strong>exit this trade immediately at market price</strong>?
              <br /><br />
              • Current LTP: <strong className="font-mono text-white">₹{selectedForClose.current_price?.toFixed(2) || selectedForClose.entry_price.toFixed(2)}</strong>
              <br />
              • Realized P&L will be recorded in your analytics ledger.
              <br />
              • Margin of <strong className="text-amber-400">₹{selectedForClose.margin_used.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong> will be released.
            </p>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setSelectedForClose(null)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white bg-slate-800 border border-slate-700 transition-all"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  onClosePosition(selectedForClose.id);
                  setSelectedForClose(null);
                }}
                className="px-4 py-2 rounded-xl text-xs font-bold text-white bg-rose-600 hover:bg-rose-500 transition-all flex items-center gap-1.5"
              >
                <Power className="w-3.5 h-3.5" />
                <span>Confirm Close</span>
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
