import React, { useEffect, useRef, useState } from 'react';
import { createChart } from 'lightweight-charts';
import { BarChart3, TrendingUp, RefreshCw, X } from 'lucide-react';

const CROWN_SYMBOLS = [
  { id: 'RELIANCE', label: 'Reliance' },
  { id: 'ITC', label: 'ITC' },
  { id: 'MARUTI', label: 'Maruti Suzuki' },
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
            time: c.time,
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close
          })).sort((a, b) => a.time - b.time);

          candleSeries.current.setData(formatted);
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
        background: { color: '#0E121B' },
        textColor: '#94A3B8',
        fontSize: 11
      },
      grid: {
        vertLines: { color: 'rgba(255, 255, 255, 0.05)' },
        horzLines: { color: 'rgba(255, 255, 255, 0.05)' }
      },
      crosshair: {
        vertLine: { color: '#10B981', width: 1, style: 2 },
        horzLine: { color: '#10B981', width: 1, style: 2 }
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

    candleSeries.current = chartInstance.current.addCandlestickSeries({
      upColor: '#10B981',
      downColor: '#F43F5E',
      borderVisible: false,
      wickUpColor: '#10B981',
      wickDownColor: '#F43F5E'
    });

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

  useEffect(() => {
    fetchCandles(selectedSymbol);
  }, [selectedSymbol]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-md p-4">
      <div className="bg-[#0E121B] border border-slate-800 rounded-3xl max-w-4xl w-full p-5 shadow-2xl flex flex-col h-[85vh] space-y-4">
        
        {/* Modal Top Bar */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-emerald-400" />
            <h3 className="text-base font-bold text-white">Crown 6 Candlestick Terminal</h3>
          </div>

          <div className="flex items-center gap-2">
            {/* Symbol Switcher */}
            <div className="flex gap-1 overflow-x-auto py-1">
              {CROWN_SYMBOLS.map((s) => (
                <button
                  key={s.id}
                  onClick={() => setSelectedSymbol(s.id)}
                  className={`px-2.5 py-1 rounded-lg text-xs font-mono font-bold transition-all ${
                    selectedSymbol === s.id
                      ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                      : 'bg-slate-900 text-slate-400 border border-slate-800 hover:text-white'
                  }`}
                >
                  {s.id}
                </button>
              ))}
            </div>

            {onClose && (
              <button
                onClick={onClose}
                className="p-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white ml-2 transition-all"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>

        {/* Chart Viewport */}
        <div className="relative flex-1 w-full rounded-2xl overflow-hidden border border-slate-800/80">
          {loading && (
            <div className="absolute inset-0 bg-[#0E121B]/70 flex items-center justify-center z-10 text-emerald-400 font-mono text-xs gap-2">
              <RefreshCw className="w-4 h-4 animate-spin" />
              <span>Streaming Candles...</span>
            </div>
          )}
          <div ref={chartContainerRef} className="w-full h-full" />
        </div>

        {/* Footer info */}
        <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 pt-1">
          <span>5-Minute Micro-Structure Timeframe</span>
          <span className="text-emerald-400">Institutional Strategy Active</span>
        </div>

      </div>
    </div>
  );
}
