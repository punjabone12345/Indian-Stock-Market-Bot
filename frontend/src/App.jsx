import React, { useState, useEffect, useCallback, useRef } from 'react';
import EntranceSplash from './components/EntranceSplash';
import HeaderBar from './components/HeaderBar';
import BottomNav from './components/BottomNav';
import DashboardTab from './components/DashboardTab';
import PositionsTab from './components/PositionsTab';
import AnalyticsTab from './components/AnalyticsTab';
import SettingsTab from './components/SettingsTab';
import TradingChart from './components/TradingChart';

// Auto-detects Render backend when on Vercel, or localhost when running locally
const API_BASE = import.meta.env.VITE_API_URL || 
  (typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
    ? 'http://127.0.0.1:8000' 
    : 'https://indian-stock-market-bot-1.onrender.com');

// Instant Hydration Baseline Data
const INITIAL_INSTRUMENTS = [
  {
    symbol: 'RELIANCE',
    name: 'Reliance Industries Ltd.',
    sector: 'Oil & Gas • NSE Cash',
    price: 1334.80,
    change: -4.90,
    change_pct: -0.37,
    high: 1344.80,
    low: 1332.10,
    volume: 5824900,
    score: 82,
    trend: 'PULLBACK_EMA9',
    next_step: 'Testing EMA9 resistance zone (₹1,336.08). Waiting for bearish red confirmation candle to close below ₹1,336.08.',
    ema9: 1336.08,
    vwap: 1338.12,
    atr: 14.80
  },
  {
    symbol: 'ITC',
    name: 'ITC Limited',
    sector: 'FMCG • NSE Cash',
    price: 284.05,
    change: 0.00,
    change_pct: 0.00,
    high: 286.30,
    low: 283.50,
    volume: 8120400,
    score: 55,
    trend: 'CONSOLIDATING',
    next_step: 'Market structure consolidating between EMA9 (₹284.10) and VWAP (₹283.67). Waiting for clear trend direction.',
    ema9: 284.10,
    vwap: 283.67,
    atr: 3.10
  },
  {
    symbol: 'MARUTI',
    name: 'Maruti Suzuki India',
    sector: 'Automobile • NSE Cash',
    price: 12871.00,
    change: -152.00,
    change_pct: -1.17,
    high: 13010.00,
    low: 12850.00,
    volume: 492100,
    score: 82,
    trend: 'PULLBACK_EMA9',
    next_step: 'Testing EMA9 resistance zone (₹12,877.64). Waiting for bearish red confirmation candle to close below ₹12,877.64.',
    ema9: 12877.64,
    vwap: 12904.85,
    atr: 165.00
  },
  {
    symbol: 'TATASTEEL',
    name: 'Tata Steel Ltd.',
    sector: 'Metals • NSE Cash',
    price: 185.93,
    change: -2.08,
    change_pct: -1.10,
    high: 188.40,
    low: 185.70,
    volume: 14209000,
    score: 74,
    trend: 'BEARISH_MOMENTUM',
    next_step: 'Bearish momentum below VWAP (₹187.28). Waiting for pullback rally towards EMA9 near ₹186.33.',
    ema9: 186.33,
    vwap: 187.28,
    atr: 2.80
  },
  {
    symbol: 'SUNPHARMA',
    name: 'Sun Pharmaceutical Ind.',
    sector: 'Healthcare • NSE Cash',
    price: 1870.30,
    change: -14.70,
    change_pct: -0.78,
    high: 1892.00,
    low: 1868.50,
    volume: 1120000,
    score: 74,
    trend: 'BEARISH_MOMENTUM',
    next_step: 'Bearish momentum below VWAP (₹1,897.03). Waiting for pullback rally towards EMA9 near ₹1,874.59.',
    ema9: 1874.59,
    vwap: 1897.03,
    atr: 22.40
  },
  {
    symbol: 'INFY',
    name: 'Infosys Limited',
    sector: 'IT Services • NSE Cash',
    price: 1137.30,
    change: -13.90,
    change_pct: -1.21,
    high: 1152.00,
    low: 1134.00,
    volume: 6420100,
    score: 74,
    trend: 'BEARISH_MOMENTUM',
    next_step: 'Bearish momentum below VWAP (₹1,144.54). Waiting for pullback rally towards EMA9 near ₹1,138.82.',
    ema9: 1138.82,
    vwap: 1144.54,
    atr: 13.50
  }
];

export default function App() {
  const [showSplash, setShowSplash] = useState(true);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [chartSymbol, setChartSymbol] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState('CONNECTED');

  // Core Portfolio & Margin State (Persistent across all tabs)
  const [portfolio, setPortfolio] = useState({
    capital: 100000.0,
    available_margin: 100000.0,
    used_margin: 0.0,
    risk_per_trade: 200.0,
    trading_mode: 'PAPER',
    bot_active: true,
    positions: [],
    unrealized_pnl: 0.0,
    unrealized_r: 0.0,
    realized_pnl: 0.0,
    realized_r: 0.0,
    total_pnl: 0.0,
    total_r: 0.0
  });

  // Watchlist & Market Regime State
  const [dashboardData, setDashboardData] = useState({
    instruments: INITIAL_INSTRUMENTS,
    nifty50: { price: 25074.10, change: -181.00, change_pct: -0.72 }
  });

  const [positions, setPositions] = useState([]);
  const [analyticsData, setAnalyticsData] = useState(null);
  const [settings, setSettings] = useState({
    capital: 100000.0,
    risk_per_trade: 200.0,
    dhan_client_id: '',
    dhan_access_token: '',
    dhan_risk_per_trade: 200.0,
    trading_mode: 'PAPER',
    bot_active: true,
    telegram_bot_token: '9230981995:AAHm8Pa65hwSHvH1N89qLwWzdEZDXKEVdWc',
    telegram_chat_id: '5582938659'
  });

  const prevPricesRef = useRef({});

  // Polling loop for dashboard data (1.5s)
  const fetchDashboard = useCallback(async () => {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 3500);
      const res = await fetch(`${API_BASE}/api/dashboard`, { signal: controller.signal });
      clearTimeout(timeoutId);

      if (res.ok) {
        const data = await res.json();
        setConnectionStatus('CONNECTED');

        if (data.instruments && data.instruments.length > 0) {
          const updated = data.instruments.map(inst => {
            const prev = prevPricesRef.current[inst.symbol];
            let tickDirection = null;
            if (prev !== undefined) {
              if (inst.price > prev) tickDirection = 'up';
              else if (inst.price < prev) tickDirection = 'down';
            }
            prevPricesRef.current[inst.symbol] = inst.price;
            return { ...inst, tickDirection };
          });

          setDashboardData(prev => ({
            ...prev,
            instruments: updated,
            nifty50: data.nifty50 || prev.nifty50
          }));
        }

        if (data.summary) {
          setPortfolio(data.summary);
          setPositions(data.summary.positions || []);
        }
      }
    } catch (err) {
      // Keep existing data gracefully
    }
  }, []);

  const fetchAnalytics = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/analytics`);
      if (res.ok) {
        const data = await res.json();
        setAnalyticsData(data);
      }
    } catch (err) {}
  }, []);

  const fetchSettings = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/settings`);
      if (res.ok) {
        const data = await res.json();
        if (data.settings) setSettings(data.settings);
      }
    } catch (err) {}
  }, []);

  useEffect(() => {
    fetchDashboard();
    fetchAnalytics();
    fetchSettings();

    const interval = setInterval(fetchDashboard, 1500);
    return () => clearInterval(interval);
  }, [fetchDashboard, fetchAnalytics, fetchSettings]);

  // Action handlers
  const handleToggleBot = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/bot/toggle`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setPortfolio(prev => ({ ...prev, bot_active: data.bot_active }));
      }
    } catch (err) {}
  };

  const handlePanicSquareOff = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/bot/panic-square-off`, { method: 'POST' });
      if (res.ok) {
        await fetchDashboard();
        await fetchAnalytics();
      }
    } catch (err) {}
  };

  const handleDeletePosition = async (posId) => {
    try {
      const res = await fetch(`${API_BASE}/api/positions/${posId}`, { method: 'DELETE' });
      if (res.ok) await fetchDashboard();
    } catch (err) {}
  };

  const handleClosePosition = async (posId) => {
    try {
      const res = await fetch(`${API_BASE}/api/positions/${posId}/close`, { method: 'POST' });
      if (res.ok) {
        await fetchDashboard();
        await fetchAnalytics();
      }
    } catch (err) {}
  };

  const handleSaveSettings = async (formData) => {
    const res = await fetch(`${API_BASE}/api/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formData)
    });
    if (res.ok) {
      const data = await res.json();
      setSettings(data.settings);
      await fetchDashboard();
      return data;
    }
    throw new Error("Failed to save settings");
  };

  const handleResetDangerZone = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/settings/reset-danger-zone`, { method: 'POST' });
      if (res.ok) {
        await fetchDashboard();
        await fetchAnalytics();
        await fetchSettings();
      }
    } catch (err) {}
  };

  const handleTestTelegram = async () => {
    const res = await fetch(`${API_BASE}/api/settings/test-telegram`, { method: 'POST' });
    if (res.ok) return await res.json();
    throw new Error("Telegram test failed");
  };

  const handleTestDhan = async (clientId, accessToken) => {
    const res = await fetch(`${API_BASE}/api/settings/test-dhan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ client_id: clientId, access_token: accessToken })
    });
    if (res.ok) return await res.json();
    throw new Error("Dhan verification failed");
  };

  const handleExportCSV = () => {
    window.open(`${API_BASE}/api/analytics/export`, '_blank');
  };

  if (showSplash) {
    return <EntranceSplash onFinish={() => setShowSplash(false)} />;
  }

  return (
    // OUTER VIEWPORT WRAPPER: Centers cleanly on desktop, 100% full screen on Android
    <div className="min-h-screen bg-[#030509] text-slate-100 flex justify-center font-sans select-none antialiased">
      
      {/* ANDROID DEVICE SCREEN CONTAINER (Matches Zerodha Kite & NowInAndroid phone aspect ratio) */}
      <div className="w-full max-w-[480px] min-h-screen bg-[#07090E] border-x border-white/[0.08] flex flex-col relative shadow-2xl">
        
        {/* PERSISTENT ANDROID TOP APP BAR & MARGIN CHIPS */}
        <HeaderBar
          portfolio={portfolio}
          nifty={dashboardData?.nifty50}
          connectionStatus={connectionStatus}
          onToggleBot={handleToggleBot}
          onPanicSquareOff={handlePanicSquareOff}
        />

        {/* ACTIVE SCREEN CONTENT (With pb-24 so bottom bar never obscures content) */}
        <main className="flex-1 overflow-y-auto pb-24 px-3 pt-2">
          {activeTab === 'dashboard' && (
            <DashboardTab
              dashboardData={dashboardData}
              onOpenChart={(sym) => setChartSymbol(sym)}
            />
          )}

          {activeTab === 'positions' && (
            <PositionsTab
              positions={positions}
              onDeletePosition={handleDeletePosition}
              onClosePosition={handleClosePosition}
            />
          )}

          {activeTab === 'analytics' && (
            <AnalyticsTab
              analyticsData={analyticsData}
              onExportCSV={handleExportCSV}
            />
          )}

          {activeTab === 'settings' && (
            <SettingsTab
              settings={settings}
              onSaveSettings={handleSaveSettings}
              onResetDangerZone={handleResetDangerZone}
              onTestTelegram={handleTestTelegram}
              onTestDhan={handleTestDhan}
            />
          )}
        </main>

        {/* PERSISTENT ANDROID DOCKED BOTTOM NAVIGATION BAR */}
        <BottomNav
          activeTab={activeTab}
          onSelectTab={setActiveTab}
          positionsCount={positions.length}
        />

        {/* CANDLESTICK CHART BOTTOM SHEET / MODAL */}
        {chartSymbol && (
          <TradingChart
            initialSymbol={chartSymbol}
            onClose={() => setChartSymbol(null)}
            apiBase={API_BASE}
          />
        )}

      </div>
    </div>
  );
}
