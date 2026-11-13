import React, { useEffect, useRef, useState } from 'react';
import { createChart, CandlestickSeries } from 'lightweight-charts';
import { BarChart3, TrendingUp, RefreshCw, X } from 'lucide-react';

const CROWN_SYMBOLS = [
  { id: 'RELIANCE', label: 'Reliance' },
  { id: 'ITC', label: 'ITC' },
  { id: 'MARUTI', label: 'Maruti' },
  { id: 'TATASTEEL', label: 'Tata Steel' },
  { id: 'SUNPHARMA', label: 'Sun Pharma' },
  { id: 'INFY', label: 'Infosys' },
  { id: 'NIFTY50', label: 'Nifty 50' }
];

export default function TradingChart({ initialSymbol = 'RELIANCE', onClose, apiBase = '' }) {
  const chartContainerRef = useRef(null);
  const chartInstance = useRef(null);
  const candleSeries = useRef(null);

  const [selectedSymbol, setSelectedSymbol] = useState(initialSymbol);
  const [chartMeta, setChartMeta] = useState(null);
  const [loading, setLoading] = useState(false);

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
        background: { color: '#0A0D15' },
        textColor: '#94A3B8',
        fontSize: 11
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

    // Lightweight charts v5 compatibility
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
        chartInstance.current = null;
      }
    };
  }, []);

  const handleSelectSymbol = (sym) => {
    setSelectedSymbol(sym);
    fetchCandles(sym);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/85 backdrop-blur-md animate-fade-in">
      <div className="m3-card-elevated border border-white/10 w-full max-w-5xl h-[85vh] flex flex-col overflow-hidden shadow-2xl">
        
        {/* Header Bar */}
        <div className="p-4 border-b border-white/[0.08] flex items-center justify-between flex-wrap gap-3 bg-[#0D111A]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-sky-500/15 border border-sky-500/30 flex items-center justify-center text-sky-400">
              <BarChart3 className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-black font-mono text-white">
                  {selectedSymbol}
                </h3>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-sky-500/20 text-sky-300 border border-sky-500/30">
                  5m INTRADAY
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Institutional EMA9 Pullback & 1:3 RRR Execution Engine
              </p>
            </div>
          </div>

          {/* Symbol Selectors */}
          <div className="flex items-center gap-1.5 overflow-x-auto max-w-full py-1">
            {CROWN_SYMBOLS.map((s) => (
              <button
                key={s.id}
                onClick={() => handleSelectSymbol(s.id)}
                className={`px-2.5 py-1 rounded-xl text-xs font-mono font-bold transition-all ${
                  selectedSymbol === s.id
                    ? 'bg-sky-500 text-slate-950 shadow-md shadow-sky-500/30'
                    : 'bg-white/[0.04] text-slate-400 hover:text-white hover:bg-white/[0.08]'
                }`}
              >
                {s.id}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => fetchCandles(selectedSymbol)}
              className="p-2 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] text-slate-300 transition-all"
              title="Refresh Candles"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-sky-400' : ''}`} />
            </button>
            <button
              onClick={onClose}
              className="p-2 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] text-slate-300 hover:text-white transition-all"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Chart Viewport */}
        <div className="flex-1 relative w-full h-full min-h-[350px] bg-[#0A0D15]">
          <div ref={chartContainerRef} className="w-full h-full" />
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/40 backdrop-blur-[2px] text-xs font-mono text-sky-400 gap-2">
              <RefreshCw className="w-4 h-4 animate-spin" />
              <span>Streaming 5m candles...</span>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
