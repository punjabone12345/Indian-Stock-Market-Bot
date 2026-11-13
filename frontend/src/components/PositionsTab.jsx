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
  ArrowRight,
  Crosshair,
  X
} from 'lucide-react';

export default function PositionsTab({ positions = [], onDeletePosition, onClosePosition }) {
  const [selectedForDelete, setSelectedForDelete] = useState(null);
  const [selectedForClose, setSelectedForClose] = useState(null);

  return (
    <div className="space-y-5 pb-16 max-w-7xl mx-auto px-3 sm:px-6 pt-4">
      
      {/* SECTION HEADER */}
      <div className="flex items-center justify-between border-b border-white/[0.06] pb-3">
        <div>
          <h2 className="text-lg sm:text-xl font-extrabold tracking-tight text-white flex items-center gap-2">
            <span>ACTIVE RUNNING POSITIONS</span>
            <span className="px-2.5 py-0.5 text-[10px] font-mono font-bold bg-sky-500/15 text-sky-400 rounded-full border border-sky-500/30">
              {positions.length} Active
            </span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Real-time Stop Loss & 1:3 Target tracking under automated Synthetic OCO protection.
          </p>
        </div>
      </div>

      {/* POSITIONS LIST */}
      {positions.length === 0 ? (
        <div className="m3-card p-12 text-center border border-white/[0.08] flex flex-col items-center justify-center space-y-4">
          <div className="w-16 h-16 rounded-3xl bg-[#141A28] border border-white/10 flex items-center justify-center text-slate-400 shadow-lg">
            <Layers className="w-8 h-8 text-sky-400" />
          </div>
          <div className="space-y-1">
            <h3 className="text-base font-extrabold text-white">No Running Positions</h3>
            <p className="text-xs text-slate-400 max-w-md mx-auto leading-relaxed">
              The Crown 6 algorithmic scanner is actively evaluating 5m EMA9/21 pullbacks for RELIANCE, ITC, MARUTI, TATASTEEL, SUNPHARMA, and INFY.
            </p>
          </div>
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-mono">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
            <span>Scanning High-Frequency Ticks</span>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-5">
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
                className="m3-card p-5 border border-white/[0.08] relative overflow-hidden flex flex-col justify-between"
              >
                {/* Long/Short accent top stripe */}
                <div className={`absolute top-0 left-0 right-0 h-[3px] ${
                  isLong ? 'bg-gradient-to-r from-emerald-500 to-teal-400' : 'bg-gradient-to-r from-rose-500 to-amber-500'
                }`} />

                <div>
                  {/* Top Bar: Symbol, Direction, Entry Time */}
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-base font-black text-white font-mono tracking-tight">
                          {pos.symbol}
                        </span>
                        <span className={`px-2 py-0.5 rounded-md text-[10px] font-mono font-extrabold border ${
                          isLong 
                            ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' 
                            : 'bg-rose-500/15 text-rose-400 border-rose-500/30'
                        }`}>
                          {pos.direction}
                        </span>
                        <span className="text-[10px] font-mono text-slate-400">
                          {pos.quantity} shares
                        </span>
                      </div>
                      <div className="flex items-center gap-1.5 text-[11px] font-mono text-slate-400 mt-1">
                        <Clock className="w-3 h-3 text-slate-500" />
                        <span>Entered at {pos.entry_time} IST</span>
                      </div>
                    </div>

                    {/* Live Unrealized P&L */}
                    <div className="flex flex-col items-end">
                      <span className="text-[10px] font-mono uppercase text-slate-400">
                        Live P&L
                      </span>
                      <span className={`text-base sm:text-lg font-black font-mono tabular-nums ${
                        isProfit ? 'text-emerald-400' : 'text-rose-400'
                      }`}>
                        {isProfit ? '+' : ''}₹{pnl.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </span>
                      <span className={`text-[10px] font-mono font-bold px-1.5 py-0.2 rounded mt-0.5 ${
                        isProfit ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'
                      }`}>
                        {isProfit ? '+' : ''}{r.toFixed(2)} R
                      </span>
                    </div>
                  </div>

                  {/* Price Matrix: Entry, Current LTP */}
                  <div className="grid grid-cols-2 gap-3 mt-4 p-3 rounded-2xl bg-[#0A0D15]/80 border border-white/[0.06] font-mono text-xs">
                    <div>
                      <span className="text-[10px] text-slate-400 block uppercase">Entry Price</span>
                      <span className="text-slate-100 font-bold tabular-nums">₹{pos.entry_price.toFixed(2)}</span>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-400 block uppercase">Current LTP</span>
                      <span className={`font-bold tabular-nums ${isProfit ? 'text-emerald-400' : 'text-rose-400'}`}>
                        ₹{currentPrice.toFixed(2)}
                      </span>
                    </div>
                  </div>

                  {/* Visual SL to TP Bracket Bar */}
                  <div className="mt-3.5 space-y-1.5 px-0.5">
                    <div className="flex justify-between text-[10px] font-mono">
                      <span className="text-rose-400 font-bold">SL: ₹{pos.stop_loss.toFixed(2)}</span>
                      <span className="text-slate-400">Target RRR 1:3</span>
                      <span className="text-emerald-400 font-bold">TP: ₹{pos.take_profit.toFixed(2)}</span>
                    </div>
                    <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden p-[1px] relative">
                      <div 
                        className="h-full bg-gradient-to-r from-rose-500 via-amber-400 to-emerald-400 rounded-full transition-all duration-300"
                        style={{ width: `${clampedProgress}%` }}
                      />
                    </div>
                  </div>

                  {/* Margin & Capital Info */}
                  <div className="mt-3 flex items-center justify-between text-[11px] font-mono text-slate-400 px-1">
                    <span>Margin Locked (5x MIS):</span>
                    <span className="text-amber-400 font-bold tabular-nums">
                      ₹{pos.margin_used.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </span>
                  </div>
                </div>

                {/* TWO ACTION BUTTONS: DELETE & CLOSE MANUALLY */}
                <div className="mt-4 pt-3 border-t border-white/[0.06] flex items-center gap-2.5">
                  
                  {/* BUTTON 1: DELETE (Releases margin, no P&L counted) */}
                  <button
                    onClick={() => setSelectedForDelete(pos)}
                    className="flex-1 py-2 px-3 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-slate-300 hover:text-white text-xs font-bold font-mono flex items-center justify-center gap-1.5 transition-all"
                  >
                    <Trash2 className="w-3.5 h-3.5 text-slate-400" />
                    <span>Delete Position</span>
                  </button>

                  {/* BUTTON 2: CLOSE MANUALLY (Exits at market price, records P&L) */}
                  <button
                    onClick={() => setSelectedForClose(pos)}
                    className="flex-1 py-2 px-3 rounded-xl bg-rose-500/15 hover:bg-rose-500/25 border border-rose-500/40 text-rose-300 text-xs font-bold font-mono flex items-center justify-center gap-1.5 transition-all shadow-sm shadow-rose-950/20"
                  >
                    <Power className="w-3.5 h-3.5 text-rose-400" />
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-fade-in">
          <div className="m3-card-elevated border border-amber-500/40 max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <div className="w-12 h-12 rounded-2xl bg-amber-500/20 border border-amber-500/30 flex items-center justify-center text-amber-400">
                <Trash2 className="w-6 h-6" />
              </div>
              <button 
                onClick={() => setSelectedForDelete(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div>
              <h3 className="text-base font-extrabold text-white">Delete Position Record?</h3>
              <p className="text-xs text-amber-400 font-mono mt-0.5">
                {selectedForDelete.symbol} • {selectedForDelete.direction} ({selectedForDelete.quantity} shares)
              </p>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              Are you sure you want to <strong>delete this position</strong> from the database?
              <br /><br />
              • Locked margin of <strong className="text-amber-400 font-mono">₹{selectedForDelete.margin_used.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong> will be immediately released back to your available balance.
              <br />
              • <strong>NO P&L or charges will be counted</strong> for this trade.
            </p>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setSelectedForDelete(null)}
                className="flex-1 py-2.5 rounded-xl text-xs font-bold text-slate-300 bg-white/5 border border-white/10 hover:bg-white/10 transition-all"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  onDeletePosition(selectedForDelete.id);
                  setSelectedForDelete(null);
                }}
                className="flex-1 py-2.5 rounded-xl text-xs font-bold text-white bg-amber-600 hover:bg-amber-500 border border-amber-400 shadow-lg shadow-amber-600/30 transition-all"
              >
                Confirm Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* CONFIRMATION MODAL: CLOSE MANUALLY */}
      {selectedForClose && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-fade-in">
          <div className="m3-card-elevated border border-rose-500/40 max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <div className="w-12 h-12 rounded-2xl bg-rose-500/20 border border-rose-500/30 flex items-center justify-center text-rose-400">
                <Power className="w-6 h-6" />
              </div>
              <button 
                onClick={() => setSelectedForClose(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div>
              <h3 className="text-base font-extrabold text-white">Close Position Manually?</h3>
              <p className="text-xs text-rose-400 font-mono mt-0.5">
                {selectedForClose.symbol} • {selectedForClose.direction} ({selectedForClose.quantity} shares)
              </p>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              Are you sure you want to <strong>exit this trade immediately at current market price</strong>?
              <br /><br />
              • Current Market Price: <strong className="font-mono text-white">₹{selectedForClose.current_price?.toFixed(2) || selectedForClose.entry_price.toFixed(2)}</strong>
              <br />
              • Realized P&L and exact statutory SEBI friction will be booked into your master analytics ledger.
              <br />
              • Margin of <strong className="text-amber-400 font-mono">₹{selectedForClose.margin_used.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong> will be released.
            </p>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setSelectedForClose(null)}
                className="flex-1 py-2.5 rounded-xl text-xs font-bold text-slate-300 bg-white/5 border border-white/10 hover:bg-white/10 transition-all"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  onClosePosition(selectedForClose.id);
                  setSelectedForClose(null);
                }}
                className="flex-1 py-2.5 rounded-xl text-xs font-bold text-white bg-rose-600 hover:bg-rose-500 border border-rose-400 shadow-lg shadow-rose-600/30 transition-all flex items-center justify-center gap-1.5"
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
