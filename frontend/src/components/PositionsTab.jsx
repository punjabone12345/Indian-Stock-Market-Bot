import React, { useState } from 'react';
import { 
  TrendingUp, 
  TrendingDown, 
  Clock, 
  Trash2, 
  Power, 
  Layers,
  X
} from 'lucide-react';

export default function PositionsTab({ positions = [], onDeletePosition, onClosePosition }) {
  const [selectedForDelete, setSelectedForDelete] = useState(null);
  const [selectedForClose, setSelectedForClose] = useState(null);

  return (
    <div className="space-y-3 pb-8">
      
      {/* SECTION HEADER */}
      <div className="flex items-center justify-between px-1 pt-1 pb-1 border-b border-white/[0.06]">
        <div>
          <h2 className="text-xs font-black tracking-tight text-white font-mono uppercase flex items-center gap-1.5">
            <span>Active Positions</span>
            <span className="px-1.5 py-0.2 text-[9px] font-mono font-bold bg-sky-500/20 text-sky-300 rounded border border-sky-500/30">
              {positions.length} Open
            </span>
          </h2>
        </div>
        <span className="text-[10px] font-mono text-slate-400">1:3 RRR Protection</span>
      </div>

      {/* POSITIONS LIST */}
      {positions.length === 0 ? (
        <div className="bg-[#0F1424] border border-white/[0.08] rounded-2xl p-8 text-center flex flex-col items-center justify-center space-y-3 mt-4">
          <div className="w-12 h-12 rounded-2xl bg-[#141A28] border border-white/10 flex items-center justify-center text-sky-400 shadow-md">
            <Layers className="w-6 h-6" />
          </div>
          <div className="space-y-1">
            <h3 className="text-sm font-black text-white">No Running Positions</h3>
            <p className="text-[11px] text-slate-400 max-w-xs mx-auto leading-relaxed">
              Evaluating 5m EMA9 pullbacks for Crown 6 champions. Positions will appear here automatically with real-time P&L.
            </p>
          </div>
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-[10px] font-mono">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
            <span>Scanning High-Frequency Ticks</span>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          {positions.map((pos) => {
            const isLong = pos.direction === 'BUY';
            const pnl = pos.unrealized_pnl || 0;
            const r = pos.unrealized_r || 0;
            const isProfit = pnl >= 0;
            const currentPrice = pos.current_price || pos.entry_price;

            // Visual bracket progress: SL (0%) -> Entry -> TP (100%)
            const totalRange = Math.abs(pos.take_profit - pos.stop_loss) || 1;
            const progress = isLong
              ? ((currentPrice - pos.stop_loss) / totalRange) * 100
              : ((pos.stop_loss - currentPrice) / totalRange) * 100;
            const clampedProgress = Math.min(100, Math.max(0, progress));

            return (
              <div 
                key={pos.id}
                className="bg-[#0F1424] border border-white/[0.08] rounded-2xl p-3.5 relative overflow-hidden flex flex-col justify-between shadow-md"
              >
                {/* Accent top stripe */}
                <div className={`absolute top-0 left-0 right-0 h-[3px] ${
                  isLong ? 'bg-gradient-to-r from-emerald-500 to-teal-400' : 'bg-gradient-to-r from-rose-500 to-amber-500'
                }`} />

                <div>
                  {/* Top: Symbol, Direction, Entry Time & P&L */}
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-sm font-black text-white font-mono">
                          {pos.symbol}
                        </span>
                        <span className={`px-1.5 py-0.2 rounded text-[9px] font-mono font-black border ${
                          isLong 
                            ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40' 
                            : 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                        }`}>
                          {pos.direction}
                        </span>
                        <span className="text-[10px] font-mono text-slate-400">
                          {pos.quantity} Qty
                        </span>
                      </div>
                      <div className="flex items-center gap-1 text-[10px] font-mono text-slate-400 mt-0.5">
                        <Clock className="w-3 h-3 text-slate-500" />
                        <span>{pos.entry_time} IST</span>
                      </div>
                    </div>

                    {/* Live Unrealized P&L */}
                    <div className="flex flex-col items-end">
                      <span className={`text-sm font-black font-mono tabular-nums ${
                        isProfit ? 'text-emerald-400' : 'text-rose-400'
                      }`}>
                        {isProfit ? '+' : ''}₹{pnl.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </span>
                      <span className={`text-[9px] font-mono font-bold px-1.5 py-0.2 rounded mt-0.5 ${
                        isProfit ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'
                      }`}>
                        {isProfit ? '+' : ''}{r.toFixed(2)} R
                      </span>
                    </div>
                  </div>

                  {/* Price Matrix: Entry, Current LTP */}
                  <div className="grid grid-cols-2 gap-2 mt-3 p-2 rounded-xl bg-[#090D18] border border-white/[0.05] font-mono text-[11px]">
                    <div>
                      <span className="text-[9px] text-slate-500 block uppercase">Entry</span>
                      <span className="text-slate-100 font-bold tabular-nums">₹{pos.entry_price.toFixed(2)}</span>
                    </div>
                    <div>
                      <span className="text-[9px] text-slate-500 block uppercase">LTP</span>
                      <span className={`font-bold tabular-nums ${isProfit ? 'text-emerald-400' : 'text-rose-400'}`}>
                        ₹{currentPrice.toFixed(2)}
                      </span>
                    </div>
                  </div>

                  {/* Visual SL to TP Bracket Bar */}
                  <div className="mt-2.5 space-y-1">
                    <div className="flex justify-between text-[9px] font-mono">
                      <span className="text-rose-400 font-bold">SL: ₹{pos.stop_loss.toFixed(2)}</span>
                      <span className="text-slate-400">1:3 Target</span>
                      <span className="text-emerald-400 font-bold">TP: ₹{pos.take_profit.toFixed(2)}</span>
                    </div>
                    <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden p-[1px]">
                      <div 
                        className="h-full bg-gradient-to-r from-rose-500 via-amber-400 to-emerald-400 rounded-full transition-all duration-300"
                        style={{ width: `${clampedProgress}%` }}
                      />
                    </div>
                  </div>

                  {/* Margin Used */}
                  <div className="mt-2 flex items-center justify-between text-[10px] font-mono text-slate-400 px-0.5">
                    <span>Margin (5x MIS):</span>
                    <span className="text-amber-400 font-bold tabular-nums">
                      ₹{pos.margin_used.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </span>
                  </div>
                </div>

                {/* ACTION BUTTONS: DELETE & CLOSE MANUALLY */}
                <div className="mt-3 pt-2.5 border-t border-white/[0.06] flex items-center gap-2">
                  <button
                    onClick={() => setSelectedForDelete(pos)}
                    className="flex-1 py-1.5 px-2 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-slate-300 text-[11px] font-bold font-mono flex items-center justify-center gap-1 transition-all cursor-pointer"
                  >
                    <Trash2 className="w-3 h-3 text-slate-400" />
                    <span>Delete</span>
                  </button>

                  <button
                    onClick={() => setSelectedForClose(pos)}
                    className="flex-1 py-1.5 px-2 rounded-xl bg-rose-500/15 hover:bg-rose-500/25 border border-rose-500/40 text-rose-300 text-[11px] font-bold font-mono flex items-center justify-center gap-1 transition-all cursor-pointer"
                  >
                    <Power className="w-3 h-3 text-rose-400" />
                    <span>Close Manually</span>
                  </button>
                </div>

              </div>
            );
          })}
        </div>
      )}

      {/* CONFIRMATION MODAL: DELETE */}
      {selectedForDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-md p-4 animate-fade-in">
          <div className="bg-[#101626] border border-amber-500/40 rounded-2xl max-w-sm w-full p-5 space-y-3.5 shadow-2xl">
            <div className="flex items-center justify-between">
              <div className="w-10 h-10 rounded-xl bg-amber-500/20 border border-amber-500/30 flex items-center justify-center text-amber-400">
                <Trash2 className="w-5 h-5" />
              </div>
              <button onClick={() => setSelectedForDelete(null)} className="p-1 rounded-lg text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div>
              <h3 className="text-sm font-black text-white">Delete Position Record?</h3>
              <p className="text-[11px] text-amber-400 font-mono mt-0.5">
                {selectedForDelete.symbol} • {selectedForDelete.direction} ({selectedForDelete.quantity} shares)
              </p>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              • Locked margin of <strong className="text-amber-400 font-mono">₹{selectedForDelete.margin_used.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong> will be released.
              <br />
              • <strong>NO P&L or charges</strong> will be counted.
            </p>

            <div className="flex items-center justify-end gap-2 pt-1">
              <button
                onClick={() => setSelectedForDelete(null)}
                className="flex-1 py-2 rounded-xl text-xs font-bold text-slate-300 bg-white/5 border border-white/10"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  onDeletePosition(selectedForDelete.id);
                  setSelectedForDelete(null);
                }}
                className="flex-1 py-2 rounded-xl text-xs font-bold text-white bg-amber-600 hover:bg-amber-500 border border-amber-400"
              >
                Confirm Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* CONFIRMATION MODAL: CLOSE MANUALLY */}
      {selectedForClose && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-md p-4 animate-fade-in">
          <div className="bg-[#101626] border border-rose-500/40 rounded-2xl max-w-sm w-full p-5 space-y-3.5 shadow-2xl">
            <div className="flex items-center justify-between">
              <div className="w-10 h-10 rounded-xl bg-rose-500/20 border border-rose-500/30 flex items-center justify-center text-rose-400">
                <Power className="w-5 h-5" />
              </div>
              <button onClick={() => setSelectedForClose(null)} className="p-1 rounded-lg text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div>
              <h3 className="text-sm font-black text-white">Close Position Manually?</h3>
              <p className="text-[11px] text-rose-400 font-mono mt-0.5">
                {selectedForClose.symbol} • {selectedForClose.direction} ({selectedForClose.quantity} shares)
              </p>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              • Exits immediately at Market Price: <strong className="font-mono text-white">₹{selectedForClose.current_price?.toFixed(2) || selectedForClose.entry_price.toFixed(2)}</strong>
              <br />
              • Realized P&L and statutory SEBI friction will be booked into the analytics ledger.
              <br />
              • Margin of <strong className="text-amber-400 font-mono">₹{selectedForClose.margin_used.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong> will be released.
            </p>

            <div className="flex items-center justify-end gap-2 pt-1">
              <button
                onClick={() => setSelectedForClose(null)}
                className="flex-1 py-2 rounded-xl text-xs font-bold text-slate-300 bg-white/5 border border-white/10"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  onClosePosition(selectedForClose.id);
                  setSelectedForClose(null);
                }}
                className="flex-1 py-2 rounded-xl text-xs font-bold text-white bg-rose-600 hover:bg-rose-500 border border-rose-400"
              >
                Confirm Close
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
