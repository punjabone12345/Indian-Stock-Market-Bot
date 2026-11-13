import React, { useEffect, useState } from 'react';
import { ShieldCheck, TrendingUp, Sparkles, Zap } from 'lucide-react';

export default function EntranceSplash({ onFinish }) {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 100) {
          clearInterval(interval);
          setTimeout(onFinish, 300);
          return 100;
        }
        return prev + 5;
      });
    }, 45);

    return () => clearInterval(interval);
  }, [onFinish]);

  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-[#080A0F] text-white px-6 select-none overflow-hidden">
      {/* Background radial glow */}
      <div className="absolute w-[500px] h-[500px] bg-emerald-500/10 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute w-[300px] h-[300px] bg-amber-500/10 rounded-full blur-[90px] pointer-events-none -bottom-10" />

      {/* High-tech Logo Icon */}
      <div className="relative mb-8 flex items-center justify-center">
        <div className="w-24 h-24 rounded-3xl bg-gradient-to-tr from-emerald-500/20 via-slate-900 to-amber-500/20 border border-emerald-500/30 flex items-center justify-center shadow-2xl shadow-emerald-500/20 animate-pulse-glow">
          <Zap className="w-12 h-12 text-emerald-400 fill-emerald-400/20" />
        </div>
        <div className="absolute -inset-2 rounded-[30px] border border-emerald-500/20 animate-ping opacity-25" />
      </div>

      {/* App Title */}
      <div className="text-center space-y-2 z-10">
        <h1 className="text-3xl sm:text-4xl font-extrabold tracking-wider bg-gradient-to-r from-emerald-400 via-teal-200 to-amber-400 bg-clip-text text-transparent">
          INDIAN STOCK MARKET BOT
        </h1>
        <p className="text-xs sm:text-sm font-medium tracking-widest text-slate-400 uppercase">
          Institutional Crown 6 Algorithmic Engine
        </p>
      </div>

      {/* Micro Status Badges */}
      <div className="mt-6 flex items-center gap-3 text-[11px] font-mono text-slate-400">
        <span className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          5x MIS Cash
        </span>
        <span className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-800/80 border border-slate-700/50 text-slate-300">
          1:3 Asymmetric RRR
        </span>
        <span className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400">
          DhanHQ Connected
        </span>
      </div>

      {/* Progress Bar */}
      <div className="w-64 max-w-xs mt-10 space-y-2">
        <div className="h-1.5 w-full bg-slate-800/80 rounded-full overflow-hidden p-[1px] border border-slate-700/40">
          <div
            className="h-full bg-gradient-to-r from-emerald-500 via-teal-400 to-amber-400 rounded-full transition-all duration-100 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>
        <div className="flex justify-between items-center text-[10px] font-mono text-slate-400">
          <span>INITIALIZING QUANT CORE</span>
          <span>{progress}%</span>
        </div>
      </div>
    </div>
  );
}
