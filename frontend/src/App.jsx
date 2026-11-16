import React, { useState, useEffect, useCallback, useRef } from 'react';
import EntranceSplash from './components/EntranceSplash';
import HeaderBar from './components/HeaderBar';
import BottomNav from './components/BottomNav';
import DashboardTab from './components/DashboardTab';
import PositionsTab from './components/PositionsTab';
import AnalyticsTab from './components/AnalyticsTab';
import SettingsTab from './components/SettingsTab';
import TradingChart from './components/TradingChart';
import { 
  LayoutDashboard, 
  Layers, 
  BarChart3, 
  Sliders 
} from 'lucide-react';

// Auto-detects Render backend when on Vercel, or localhost when running locally
const API_BASE = import.meta.env.VITE_API_URL || 
  (typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
    ? 'http://127.0.0.1:8000' 
    : 'https://indian-stock-market-bot-1.onrender.com');

// Instant Hydration Baseline Data for Crown 6 Champion Stocks
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
    next_step: 'Testing EMA 9 resistance zone (₹1,336.08). Waiting for bearish confirmation candle to close below ₹1,336.08.',
    ema9: 1336.08,
    vwap: 1338.12,
    atr: 14.80
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
    next_step: 'Testing EMA 9 resistance zone (₹12,877.64). Waiting for bearish confirmation candle to close below ₹12,877.64.',
    ema9: 12877.64,
    vwap: 12904.85,
    atr: 165.00
  },
  {
    symbol: 'TCS',
    name: 'Tata Consultancy Services',
    sector: 'IT & Software • NSE Cash',
    price: 2435.50,
    change: 12.40,
    change_pct: 0.51,
    high: 2445.00,
    low: 2420.00,
    volume: 1850400,
    score: 80,
    trend: 'PULLBACK_EMA9',
    next_step: 'Bounced off EMA 9 support (₹2,430.15). Waiting for bullish expansion candle with volume.',
    ema9: 2430.15,
    vwap: 2428.50,
    atr: 28.50
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
    next_step: 'Bearish momentum below VWAP (₹1,897.03). Waiting for pullback rally towards EMA 9 near ₹1,874.59.',
    ema9: 1874.59,
    vwap: 1897.03,
    atr: 21.40
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
    next_step: 'Bearish momentum below VWAP (₹187.28). Waiting for pullback rally towards EMA 9 near ₹186.33.',
    ema9: 186.33,
    vwap: 187.28,
    atr: 2.80
  },
  {
    symbol: 'TATAMOTORS',
    name: 'Tata Motors Passenger Ltd.',
    sector: 'Automobile • NSE Cash',
    price: 985.40,
    change: 5.60,
    change_pct: 0.57,
    high: 992.00,
    low: 978.50,
    volume: 6420100,
    score: 76,
    trend: 'PULLBACK_EMA9',
    next_step: 'Testing EMA 9 support (₹982.10). Inversion FVG retest confirmed. Monitoring for buy trigger.',
    ema9: 982.10,
    vwap: 981.40,
    atr: 12.20
  }
];

export default function App() {
  const [showSplash, setShowSplash] = useState(true);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [chartSymbol, setChartSymbol] = useState(null);

  // Core App State
  const [portfolio, setPortfolio] = useState({
    capital: 125000,
    available_margin: 125000,
    used_margin: 0,
    total_pnl: 0,
    total_r: 0,
    bot_active: true,
    trading_mode: 'PAPER',
    open_positions_count: 0
  });

  const [dashboardData, setDashboardData] = useState({
    instruments: INITIAL_INSTRUMENTS,
    nifty50: { price: 24350.00, change: 0.00, change_pct: 0.00 }
  });

  const [positions, setPositions] = useState([]);
  const [analyticsData, setAnalyticsData] = useState(null);
  const [settings, setSettings] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState('connecting');

  const previousPricesRef = useRef({});

  // 1. Fetch Dashboard & Portfolio Status
  const fetchStatusAndDashboard = useCallback(async () => {
    try {
      const [dashRes, portRes, posRes] = await Promise.all([
        fetch(`${API_BASE}/api/dashboard`).catch(() => null),
        fetch(`${API_BASE}/api/status`).catch(() => null),
        fetch(`${API_BASE}/api/positions`).catch(() => null)
      ]);

      if (dashRes && dashRes.ok) {
        const data = await dashRes.json();
        
        // Track tick direction for price flashes
        if (data.instruments) {
          const updated = data.instruments.map(inst => {
            const prev = previousPricesRef.current[inst.symbol];
            let tickDirection = null;
            if (prev !== undefined) {
              if (inst.price > prev) tickDirection = 'up';
              else if (inst.price < prev) tickDirection = 'down';
            }
            previousPricesRef.current[inst.symbol] = inst.price;
            return { ...inst, tickDirection };
          });
          setDashboardData({ ...data, instruments: updated });
        } else {
          setDashboardData(data);
        }
        setConnectionStatus('connected');
      }

      if (portRes && portRes.ok) {
        const pData = await portRes.json();
        setPortfolio(pData);
      }

      if (posRes && posRes.ok) {
        const posData = await posRes.json();
        setPositions(posData.positions || []);
      }
    } catch (err) {
      console.warn("Status fetch error:", err);
      setConnectionStatus('disconnected');
    }
  }, []);

  // 2. Fetch Analytics Ledger
  const fetchAnalytics = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/analytics`);
      if (res.ok) {
        const data = await res.json();
        setAnalyticsData(data);
      }
    } catch (err) {
      console.warn("Analytics fetch error:", err);
    }
  }, []);

  // 3. Fetch Settings Config
  const fetchSettings = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/settings`);
      if (res.ok) {
        const data = await res.json();
        setSettings(data);
      }
    } catch (err) {
      console.warn("Settings fetch error:", err);
    }
  }, []);

  // Polling Interval: 2 seconds for high-frequency live ticks
  useEffect(() => {
    fetchStatusAndDashboard();
    fetchAnalytics();
    fetchSettings();

    const interval = setInterval(() => {
      fetchStatusAndDashboard();
    }, 2000);

    return () => clearInterval(interval);
  }, [fetchStatusAndDashboard, fetchAnalytics, fetchSettings]);

  // Tab switch effect: refresh data
  useEffect(() => {
    if (activeTab === 'analytics') fetchAnalytics();
    if (activeTab === 'settings') fetchSettings();
  }, [activeTab, fetchAnalytics, fetchSettings]);

  // Actions
  const handleToggleBot = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/bot/toggle`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setPortfolio(prev => ({ ...prev, bot_active: data.bot_active }));
      }
    } catch (err) {
      console.error("Toggle bot error:", err);
    }
  };

  const handlePanicSquareOff = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/portfolio/panic_close`, { method: 'POST' });
      if (res.ok) {
        fetchStatusAndDashboard();
        fetchAnalytics();
      }
    } catch (err) {
      console.error("Panic squareoff error:", err);
    }
  };

  const handleDeletePosition = async (posId) => {
    try {
      const res = await fetch(`${API_BASE}/api/positions/${posId}`, { method: 'DELETE' });
      if (res.ok) {
        fetchStatusAndDashboard();
      }
    } catch (err) {
      console.error("Delete position error:", err);
    }
  };

  const handleClosePosition = async (posId) => {
    try {
      const res = await fetch(`${API_BASE}/api/positions/${posId}/close`, { method: 'POST' });
      if (res.ok) {
        fetchStatusAndDashboard();
        fetchAnalytics();
      }
    } catch (err) {
      console.error("Close position error:", err);
    }
  };

  const handleSaveSettings = async (newSettings) => {
    const res = await fetch(`${API_BASE}/api/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newSettings)
    });
    if (res.ok) {
      const data = await res.json();
      setSettings(data.settings);
      fetchStatusAndDashboard();
      return data;
    }
    throw new Error("Failed to save settings");
  };

  const handleResetDangerZone = async () => {
    const res = await fetch(`${API_BASE}/api/settings/reset`, { method: 'POST' });
    if (res.ok) {
      fetchStatusAndDashboard();
      fetchAnalytics();
      fetchSettings();
      return await res.json();
    }
    throw new Error("Failed to reset database");
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

  const desktopTabs = [
    { id: 'dashboard', label: 'Watchlist', icon: LayoutDashboard },
    { id: 'positions', label: 'Positions', icon: Layers, badge: positions.length },
    { id: 'analytics', label: 'Analytics', icon: BarChart3 },
    { id: 'settings', label: 'Settings', icon: Sliders }
  ];

  return (
    <div className="min-h-screen bg-[#06080F] text-slate-100 flex flex-col font-sans select-none antialiased">
      
      {/* PERSISTENT HIGH-TECH COMMAND HEADER */}
      <HeaderBar
        portfolio={portfolio}
        nifty={dashboardData?.nifty50}
        connectionStatus={connectionStatus}
        onToggleBot={handleToggleBot}
        onPanicSquareOff={handlePanicSquareOff}
      />

      {/* DESKTOP SUB-HEADER DOCK (VISIBLE ON >= 768px MD SCREENS) */}
      <div className="hidden md:block w-full border-b border-white/[0.06] bg-[#090D17]/80 backdrop-blur-md sticky top-[108px] z-30">
        <div className="max-w-7xl mx-auto px-6 py-2 flex items-center justify-between">
          
          <div className="flex items-center gap-2">
            {desktopTabs.map((t) => {
              const Icon = t.icon;
              const isActive = activeTab === t.id;

              return (
                <button
                  key={t.id}
                  onClick={() => setActiveTab(t.id)}
                  className={`px-3.5 py-1.5 rounded-xl font-mono text-xs font-bold flex items-center gap-2 transition-all cursor-pointer ${
                    isActive 
                      ? 'bg-sky-500/20 text-sky-300 border border-sky-400/30 shadow-md shadow-sky-500/15' 
                      : 'text-slate-400 hover:text-white hover:bg-white/[0.03]'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span>{t.label}</span>
                  {t.badge > 0 && (
                    <span className="px-1.5 py-0.2 rounded-full text-[9px] font-mono font-black bg-sky-400 text-slate-950">
                      {t.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          <div className="flex items-center gap-3 text-xs font-mono text-slate-400">
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 beacon-pulse-emerald" />
              <span>Dhan Fast-Order Ready</span>
            </span>
            <span>•</span>
            <span className="text-sky-400 font-bold">1:3 Asymmetric RRR</span>
          </div>

        </div>
      </div>

      {/* MAIN RESPONSIVE CONTENT AREA */}
      <main className="flex-1 w-full max-w-7xl mx-auto px-3 sm:px-6 pt-3 sm:pt-4 pb-24 md:pb-12">
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

      {/* MOBILE FLOATING BOTTOM NAVIGATION DOCK (VISIBLE ON < 768px MOBILE SCREENS) */}
      <div className="md:hidden">
        <BottomNav
          activeTab={activeTab}
          onSelectTab={setActiveTab}
          positionsCount={positions.length}
        />
      </div>

      {/* TRADINGVIEW LIGHTWEIGHT CHARTS MODAL */}
      {chartSymbol && (
        <TradingChart
          initialSymbol={chartSymbol}
          onClose={() => setChartSymbol(null)}
          apiBase={API_BASE}
        />
      )}

    </div>
  );
}
