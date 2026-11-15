import React, { useEffect, useRef, useState } from 'react';
import { createChart, CandlestickSeries } from 'lightweight-charts';
import { BarChart3, TrendingUp, RefreshCw, X, ArrowUpRight, ArrowDownRight, Layers } from 'lucide-react';

const CROWN_SYMBOLS = [
  { id: 'RELIANCE', label: 'Reliance', sector: 'Oil & Gas' },
  { id: 'MARUTI', label: 'Maruti', sector: 'Auto' },
  { id: 'TCS', label: 'TCS', sector: 'IT' },
  { id: 'SUNPHARMA', label: 'Sun Pharma', sector: 'Pharma' },
  { id: 'TATASTEEL', label: 'Tata Steel', sector: 'Metals' },
  { id: 'TATAMOTORS', label: 'Tata Motors', sector: 'Auto' },
  { id: 'NIFTY50', label: 'Nifty 50', sector: 'Index' }
];

export default function TradingChart({ initialSymbol = 'RELIANCE', onClose, apiBase = '' }) {
  const chartContainerRef = useRef(null);
  const chartInstance = useRef(null);
  const candleSeries = useRef(null);

  const [selectedSymbol, setSelectedSymbol] = useState(initialSymbol);
  const [chartMeta, setChartMeta] = useState(null);
  const [loading, setLoading] = useState(false);
  const [activeTf, setActiveTf] = useState('5m');

  const fetchCandles = async (symbol) => {
    try {
      setLoading(true);
      const res = await fetch(`${apiBase}/api/chart/${symbol}`);
      if (res.ok) {
        const data = await res.json();
        setChartMeta(data);

        if (data.candles && candleSeries.current) {
          const formatted = data.candles.map(c => ({
            time: Number(c.time),
            open: Number(c.open),
            high: Number(c.high),
            low: Number(c.low),
            close: Number(c.close)
          })).sort((a, b) => a.time - b.time);

          candleSeries.current.setData(formatted);
          if (chartInstance.current) {
            chartInstance.current.timeScale().fitContent();
          }
        }
      }
    } catch (err) {
      console.warn("Chart fetch error:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!chartContainerRef.current) return;

    chartInstance.current = createChart(chartContainerRef.current, {
      layout: {
        background: { color: '#07090E' },
        textColor: '#94A3B8',
        fontSize: 11,
        fontFamily: "'JetBrains Mono', monospace"
      },
      grid: {
        vertLines: { color: 'rgba(255, 255, 255, 0.04)' },
        horzLines: { color: 'rgba(255, 255, 255, 0.04)' }
      },
      crosshair: {
        vertLine: { color: '#38BDF8', width: 1, style: 2 },
        horzLine: { color: '#38BDF8', width: 1, style: 2 }
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderColor: 'rgba(255, 255, 255, 0.08)'
      },
      rightPriceScale: {
        borderColor: 'rgba(255, 255, 255, 0.08)'
      }
    });

    if (typeof chartInstance.current.addSeries === 'function' && CandlestickSeries) {
      candleSeries.current = chartInstance.current.addSeries(CandlestickSeries, {
        upColor: '#10B981',
        downColor: '#F43F5E',
        borderVisible: false,
        wickUpColor: '#10B981',
        wickDownColor: '#F43F5E'
      });
    } else if (typeof chartInstance.current.addCandlestickSeries === 'function') {
      candleSeries.current = chartInstance.current.addCandlestickSeries({
        upColor: '#10B981',
        downColor: '#F43F5E',
        borderVisible: false,
        wickUpColor: '#10B981',
        wickDownColor: '#F43F5E'
      });
    }

    fetchCandles(selectedSymbol);

    const handleResize = () => {
      if (chartContainerRef.current && chartInstance.current) {
        chartInstance.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
          height: chartContainerRef.current.clientHeight
        });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (chartInstance.current) {
        chartInstance.current.remove();
      }
    };
  }, []);

  const handleSelectSymbol = (sym) => {
    setSelectedSymbol(sym);
    fetchCandles(sym);
  };

  const currentPrice = chartMeta?.price ?? 0;
  const change = chartMeta?.change ?? 0;
  const changePct = chartMeta?.change_pct ?? 0;
  const isUp = change >= 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4 bg-black/85 backdrop-blur-md animate-in fade-in duration-200">
      <div className="bg-[#0A0D17] border border-white/10 rounded-2xl w-full max-w-5xl h-[85vh] flex flex-col overflow-hidden shadow-2xl relative glow-cyan">
        
        {/* TOP BAR: INSTRUMENT SELECTOR & ACTIONS */}
        <div className="p-3 sm:px-5 border-b border-white/[0.08] flex items-center justify-between flex-wrap gap-2 bg-[#06080F]">
          
          {/* Symbol Selector Pills */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0 scrollbar-none">
            {CROWN_SYMBOLS.map((s) => (
              <button
                key={s.id}
                onClick={() => handleSelectSymbol(s.id)}
                className={`px-3 py-1.5 rounded-xl font-mono text-xs font-black transition-all cursor-pointer flex-shrink-0 ${
                  selectedSymbol === s.id
                    ? 'bg-sky-500/20 text-sky-300 border border-sky-400/40 shadow-md shadow-sky-500/15'
                    : 'bg-white/[0.04] text-slate-400 hover:text-white border border-white/[0.06]'
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>

          {/* Right Controls: Refresh & Close */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => fetchCandles(selectedSymbol)}
              className="p-2 rounded-xl bg-white/[0.05] hover:bg-white/10 text-slate-300 transition-all cursor-pointer border border-white/10"
              title="Refresh Candles"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-sky-400' : ''}`} />
            </button>

            <button
              onClick={onClose}
              className="p-2 rounded-xl bg-white/[0.05] hover:bg-rose-500/20 text-slate-300 hover:text-rose-400 transition-all cursor-pointer border border-white/10"
              title="Close Chart"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

        </div>

        {/* PRICE & STATS HEADER STRIP */}
        <div className="px-4 py-2.5 bg-[#0C101C] border-b border-white/[0.06] flex items-center justify-between flex-wrap gap-2 font-mono text-xs">
          <div className="flex items-center gap-3">
            <span className="text-sm sm:text-base font-black text-white">{selectedSymbol}</span>
            <span className="text-base sm:text-lg font-black text-white tabular-nums">
              ₹{currentPrice.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
            <div className={`px-2 py-0.5 rounded-full text-[10px] font-black flex items-center gap-0.5 border ${
              isUp ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' : 'bg-rose-500/15 text-rose-400 border-rose-500/30'
            }`}>
              {isUp ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
              <span>{isUp ? '+' : ''}{change.toFixed(2)} ({isUp ? '+' : ''}{changePct.toFixed(2)}%)</span>
            </div>
          </div>

          <div className="flex items-center gap-2 text-[10px] text-slate-400">
            <span className="px-2 py-0.5 rounded bg-white/5 border border-white/10 text-sky-300 font-bold">
              Timeframe: 5m Pullback
            </span>
            <span className="hidden sm:inline">EMA 9 / VWAP Confluence</span>
          </div>
        </div>

        {/* CHART CANVAS */}
        <div className="flex-1 w-full relative bg-[#07090E]">
          {loading && (
            <div className="absolute inset-0 z-10 flex items-center justify-center bg-black/40 backdrop-blur-xs">
              <div className="flex items-center gap-2 font-mono text-xs text-sky-400 bg-[#0C101C] px-3.5 py-2 rounded-xl border border-sky-500/30 shadow-xl">
                <RefreshCw className="w-4 h-4 animate-spin" />
                <span>Streaming 5m Candles...</span>
              </div>
            </div>
          )}
          <div ref={chartContainerRef} className="w-full h-full" />
        </div>

      </div>
    </div>
  );
}
