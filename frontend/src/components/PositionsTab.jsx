import React, { useState } from 'react';
import { 
  TrendingUp, 
  TrendingDown, 
  Clock, 
  Trash2, 
  Power, 
  Layers,
  X,
  AlertCircle,
  ArrowRight
} from 'lucide-react';

export default function PositionsTab({ positions = [], onDeletePosition, onClosePosition }) {
  const [selectedForDelete, setSelectedForDelete] = useState(null);
  const [selectedForClose, setSelectedForClose] = useState(null);

  return (
    <div className="space-y-4 pb-12">
      
      {/* SECTION HEADER */}
      <div className="flex items-center justify-between px-1 pt-1 pb-2 border-b border-white/[0.08]">
        <div>
          <h2 className="text-xs sm:text-sm font-black tracking-tight text-white font-mono uppercase flex items-center gap-2">
            <span>Active Live Positions</span>
            <span className="px-2 py-0.5 text-[10px] font-mono font-extrabold bg-sky-500/20 text-sky-300 rounded-full border border-sky-500/30">
              {positions.length} / 6 Max Open
            </span>
          </h2>
        </div>
        <span className="text-[10px] font-mono text-slate-400 bg-[#0D121F] px-2.5 py-1 rounded-lg border border-white/10">
          Strict 1:3 RRR Protection
        </span>
      </div>

      {/* POSITIONS LIST */}
      {positions.length === 0 ? (
        <div className="bento-card p-8 sm:p-12 text-center flex flex-col items-center justify-center space-y-4 mt-2">
          <div className="w-14 h-14 rounded-2xl bg-[#121826] border border-white/10 flex items-center justify-center text-sky-400 shadow-xl shadow-sky-500/10">
            <Layers className="w-7 h-7" />
          </div>
          <div className="space-y-1.5 max-w-sm">
            <h3 className="text-base font-black text-white font-mono">No Running Positions</h3>
            <p className="text-xs text-slate-400 leading-relaxed font-sans">
              Crown 6 Scanner is continuously monitoring 5m EMA 9 pullbacks with Nifty Macro Trend alignment. Positions trigger automatically with predefined Stop Loss and Target orders.
            </p>
          </div>
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-mono">
            <span className="w-2 h-2 rounded-full bg-emerald-400 beacon-pulse-emerald" />
            <span>High-Frequency Tick Monitoring Active</span>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3.5">
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
                className="bento-card p-4 relative overflow-hidden flex flex-col justify-between shadow-xl"
              >
                {/* Top Glowing Color Accent Stripe */}
                <div className={`absolute top-0 left-0 right-0 h-[3px] ${
                  isLong ? 'bg-gradient-to-r from-emerald-500 via-teal-400 to-sky-500' : 'bg-gradient-to-r from-rose-500 via-amber-500 to-rose-600'
                }`} />

                <div>
                  {/* TOP ROW: SYMBOL, DIRECTION, ENTRY TIME, P&L */}
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-base font-black text-white font-mono tracking-tight">
                          {pos.symbol}
                        </span>
                        <span className={`px-2 py-0.5 rounded text-[9px] font-mono font-black border ${
                          isLong 
                            ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 glow-emerald' 
                            : 'bg-rose-500/20 text-rose-300 border-rose-500/40 glow-rose'
                        }`}>
                          {pos.direction}
                        </span>
                        <span className="text-[10px] font-mono font-bold text-slate-300 bg-white/[0.08] px-1.5 py-0.5 rounded">
                          {pos.quantity} Qty
                        </span>
                      </div>
                      <div className="flex items-center gap-1.5 text-[11px] font-mono text-slate-400 mt-1">
                        <Clock className="w-3 h-3 text-slate-500" />
                        <span>Entered at {pos.entry_time} IST</span>
                      </div>
                    </div>

                    {/* Live Unrealized P&L */}
                    <div className="flex flex-col items-end">
                      <div className={`text-base sm:text-lg font-black font-mono tabular-nums ${
                        isProfit ? 'text-emerald-400' : 'text-rose-400'
                      }`}>
                        {isProfit ? '+' : ''}₹{pnl.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </div>
                      <div className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-extrabold flex items-center gap-1 border mt-0.5 ${
                        isProfit 
                          ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' 
                          : 'bg-rose-500/15 text-rose-400 border-rose-500/30'
                      }`}>
                        <span>{isProfit ? '+' : ''}{r.toFixed(2)} R Return</span>
                      </div>
                    </div>
                  </div>

                  {/* BRACKET PROGRESS BAR (SL <--> LTP <--> TP) */}
                  <div className="mt-4 p-3 rounded-xl bg-[#090D18]/90 border border-white/[0.06] space-y-2">
                    <div className="flex items-center justify-between text-[10px] font-mono">
                      <span className="text-rose-400 font-bold">SL: ₹{pos.stop_loss?.toFixed(2)}</span>
                      <span className="text-white font-extrabold bg-white/10 px-2 py-0.5 rounded">
                        LTP: ₹{currentPrice?.toFixed(2)}
                      </span>
                      <span className="text-emerald-400 font-bold">TP: ₹{pos.take_profit?.toFixed(2)}</span>
                    </div>

                    {/* Visual Progress Track */}
                    <div className="w-full h-2 rounded-full bg-slate-800/80 overflow-hidden relative border border-white/5">
                      <div 
                        className={`h-full transition-all duration-300 ${
                          isProfit ? 'bg-gradient-to-r from-teal-500 to-emerald-400' : 'bg-gradient-to-r from-rose-500 to-amber-500'
                        }`}
                        style={{ width: `${clampedProgress}%` }}
                      />
                    </div>

                    <div className="flex items-center justify-between text-[9px] font-mono text-slate-400 pt-0.5">
                      <span>{pos.direction === 'BUY' ? 'Buy Price' : 'Sell Price'}: ₹{pos.entry_price?.toFixed(2)}</span>
                      <span>Margin: ₹{pos.margin_used?.toFixed(0)}</span>
                      <span>Target: 1:3 RRR</span>
                    </div>
                  </div>
                </div>

                {/* BOTTOM ACTION BUTTONS */}
                <div className="mt-4 pt-3 border-t border-white/[0.06] flex items-center justify-end gap-2">
                  <button
                    onClick={() => setSelectedForDelete(pos.id)}
                    className="px-3 py-1.5 rounded-lg bg-white/[0.05] hover:bg-white/10 text-slate-300 text-xs font-mono font-bold flex items-center gap-1.5 transition-all cursor-pointer border border-white/10"
                    title="Delete position without recording P&L (Paper simulation)"
                  >
                    <Trash2 className="w-3.5 h-3.5 text-slate-400" />
                    <span>Delete</span>
                  </button>

                  <button
                    onClick={() => setSelectedForClose(pos.id)}
                    className="px-3 py-1.5 rounded-lg bg-rose-500/15 hover:bg-rose-500/25 border border-rose-500/40 text-rose-300 text-xs font-mono font-black flex items-center gap-1.5 transition-all cursor-pointer shadow-sm"
                    title="Close position at live Market Price"
                  >
                    <Power className="w-3.5 h-3.5 text-rose-400" />
                    <span>Close at Market</span>
                  </button>
                </div>

              </div>
            );
          })}
        </div>
      )}

      {/* CONFIRM MANUAL CLOSE MODAL */}
      {selectedForClose && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
          <div className="bg-[#0D121F] border border-rose-500/40 rounded-2xl max-w-sm w-full p-5 space-y-4 shadow-2xl relative glow-rose">
            <div className="w-12 h-12 rounded-2xl bg-rose-500/15 border border-rose-500/30 flex items-center justify-center text-rose-400 mx-auto">
              <Power className="w-6 h-6" />
            </div>
            <div className="text-center space-y-1">
              <h3 className="text-base font-black text-white font-mono">Close Position Now?</h3>
              <p className="text-xs text-slate-400 font-sans leading-relaxed">
                This will immediately exit the selected position at the current market price and record the realized P&L and statutory fees.
              </p>
            </div>
            <div className="flex items-center gap-2 pt-2 font-mono text-xs">
              <button
                onClick={() => setSelectedForClose(null)}
                className="flex-1 py-2.5 rounded-xl border border-white/10 text-slate-300 hover:bg-white/5 transition-all cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  onClosePosition(selectedForClose);
                  setSelectedForClose(null);
                }}
                className="flex-1 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-black transition-all cursor-pointer shadow-lg shadow-rose-600/40"
              >
                Confirm Exit
              </button>
            </div>
          </div>
        </div>
      )}

      {/* CONFIRM DELETE MODAL */}
      {selectedForDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
          <div className="bg-[#0D121F] border border-slate-700 rounded-2xl max-w-sm w-full p-5 space-y-4 shadow-2xl relative">
            <div className="w-12 h-12 rounded-2xl bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300 mx-auto">
              <Trash2 className="w-6 h-6" />
            </div>
            <div className="text-center space-y-1">
              <h3 className="text-base font-black text-white font-mono">Delete Position?</h3>
              <p className="text-xs text-slate-400 font-sans leading-relaxed">
                This will remove the trade from memory and release margin with zero P&L impact.
              </p>
            </div>
            <div className="flex items-center gap-2 pt-2 font-mono text-xs">
              <button
                onClick={() => setSelectedForDelete(null)}
                className="flex-1 py-2.5 rounded-xl border border-white/10 text-slate-300 hover:bg-white/5 transition-all cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  onDeletePosition(selectedForDelete);
                  setSelectedForDelete(null);
                }}
                className="flex-1 py-2.5 rounded-xl bg-slate-700 hover:bg-slate-600 text-white font-black transition-all cursor-pointer"
              >
                Confirm Delete
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
