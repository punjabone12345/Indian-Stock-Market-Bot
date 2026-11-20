import React, { useState, useEffect, useCallback, useRef } from 'react';
import EntranceSplash from './components/EntranceSplash';
import HeaderBar from './components/HeaderBar';
import BottomNav from './components/BottomNav';
import DashboardTab from './components/DashboardTab';
import PositionsTab from './components/PositionsTab';
import AnalyticsTab from './components/AnalyticsTab';
import StatsTab from './components/StatsTab';
import SettingsTab from './components/SettingsTab';
import TradingChart from './components/TradingChart';
import { 
  LayoutDashboard, 
  Layers, 
  BarChart3, 
  Sliders,
  Activity 
} from 'lucide-react';

// Auto-detects Render backend when on Vercel, or localhost when running locally
const API_BASE = import.meta.env.VITE_API_URL || 
  (typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
    ? 'http://127.0.0.1:8000' 
    : 'https://indian-stock-market-bot-1.onrender.com');

// Instant Hydration Baseline Data for Top 14 Champion Stocks
const INITIAL_INSTRUMENTS = [
  {
    symbol: 'RELIANCE',
    name: 'Reliance Industries Ltd.',
    sector: 'Energy • NSE Cash',
    price: 1344.80,
    change: 5.10,
    change_pct: 0.38,
    high: 1348.00,
    low: 1332.10,
    volume: 5824900,
    score: 84,
    trend: 'PULLBACK_EMA9',
    next_step: 'Bounced off VWAP support. Monitoring for bullish pullback continuation above EMA9.',
    ema9: 1341.20,
    vwap: 1339.80,
    atr: 14.80
  },
  {
    symbol: 'INDUSINDBK',
    name: 'IndusInd Bank Ltd.',
    sector: 'Banking & Finance • NSE Cash',
    price: 914.55,
    change: 0.15,
    change_pct: 0.02,
    high: 922.00,
    low: 910.20,
    volume: 3120400,
    score: 78,
    trend: 'PULLBACK_EMA9',
    next_step: 'Consolidating above EMA9 (₹912.40). Awaiting expansion volume bar.',
    ema9: 912.40,
    vwap: 911.80,
    atr: 11.20
  },
  {
    symbol: 'LT',
    name: 'Larsen & Toubro Ltd.',
    sector: 'Infrastructure • NSE Cash',
    price: 4140.00,
    change: -3.80,
    change_pct: -0.09,
    high: 4165.00,
    low: 4125.00,
    volume: 890500,
    score: 82,
    trend: 'PULLBACK_EMA9',
    next_step: 'Testing EMA9 support zone (₹4,136.50). Watching for green candle confirmation.',
    ema9: 4136.50,
    vwap: 4132.00,
    atr: 38.50
  },
  {
    symbol: 'ADANIENT',
    name: 'Adani Enterprises Ltd.',
    sector: 'Diversified • NSE Cash',
    price: 2659.00,
    change: -29.00,
    change_pct: -1.08,
    high: 2695.00,
    low: 2650.00,
    volume: 1650300,
    score: 75,
    trend: 'BEARISH_MOMENTUM',
    next_step: 'Below VWAP (₹2,674.00). Waiting for pullback rally toward EMA9.',
    ema9: 2668.00,
    vwap: 2674.00,
    atr: 34.00
  },
  {
    symbol: 'TATAMOTORS',
    name: 'Tata Motors Limited',
    sector: 'Automobiles • NSE Cash',
    price: 428.25,
    change: -5.30,
    change_pct: -1.22,
    high: 436.00,
    low: 426.50,
    volume: 6420100,
    score: 76,
    trend: 'PULLBACK_EMA9',
    next_step: 'Testing EMA9 support (₹427.10). Inversion FVG retest confirmed.',
    ema9: 427.10,
    vwap: 429.40,
    atr: 6.80
  },
  {
    symbol: 'SUNPHARMA',
    name: 'Sun Pharmaceutical Ind.',
    sector: 'Healthcare • NSE Cash',
    price: 1867.50,
    change: -12.50,
    change_pct: -0.66,
    high: 1892.00,
    low: 1865.00,
    volume: 1120000,
    score: 79,
    trend: 'PULLBACK_EMA9',
    next_step: 'Pullback into EMA9 support zone. Monitoring for bounce trigger.',
    ema9: 1871.20,
    vwap: 1874.50,
    atr: 21.40
  },
  {
    symbol: 'WIPRO',
    name: 'Wipro Limited',
    sector: 'IT Services • NSE Cash',
    price: 193.54,
    change: -1.06,
    change_pct: -0.54,
    high: 196.20,
    low: 192.80,
    volume: 8450000,
    score: 72,
    trend: 'CONSOLIDATING',
    next_step: 'Consolidating between EMA9 and VWAP. Awaiting directional breakout.',
    ema9: 194.10,
    vwap: 194.50,
    atr: 2.40
  },
  {
    symbol: 'JSWSTEEL',
    name: 'JSW Steel Ltd.',
    sector: 'Metals & Mining • NSE Cash',
    price: 1334.60,
    change: -13.40,
    change_pct: -0.99,
    high: 1355.00,
    low: 1330.00,
    volume: 2450000,
    score: 77,
    trend: 'PULLBACK_EMA9',
    next_step: 'Retesting VWAP anchor line (₹1,338.00). Watching for rejection wick.',
    ema9: 1339.50,
    vwap: 1338.00,
    atr: 16.20
  },
  {
    symbol: 'TATASTEEL',
    name: 'Tata Steel Ltd.',
    sector: 'Metals & Mining • NSE Cash',
    price: 182.26,
    change: -4.42,
    change_pct: -2.37,
    high: 187.50,
    low: 181.80,
    volume: 14209000,
    score: 74,
    trend: 'BEARISH_MOMENTUM',
    next_step: 'Bearish momentum below VWAP (₹184.50). Waiting for pullback rally toward EMA9.',
    ema9: 183.40,
    vwap: 184.50,
    atr: 2.80
  },
  {
    symbol: 'BAJFINANCE',
    name: 'Bajaj Finance Ltd.',
    sector: 'NBFC & Finance • NSE Cash',
    price: 1110.00,
    change: -7.00,
    change_pct: -0.63,
    high: 1125.00,
    low: 1105.00,
    volume: 1420000,
    score: 81,
    trend: 'PULLBACK_EMA9',
    next_step: 'Dip into EMA9 support zone. Waiting for bullish green candle confirmation.',
    ema9: 1112.50,
    vwap: 1114.00,
    atr: 15.00
  },
  {
    symbol: 'SBIN',
    name: 'State Bank of India',
    sector: 'PSU Banking • NSE Cash',
    price: 1090.50,
    change: 10.50,
    change_pct: 0.97,
    high: 1098.00,
    low: 1078.00,
    volume: 7850000,
    score: 86,
    trend: 'PULLBACK_EMA9',
    next_step: 'Strong bullish trend above VWAP (₹1,085.00). Retesting EMA9 support.',
    ema9: 1088.00,
    vwap: 1085.00,
    atr: 12.80
  },
  {
    symbol: 'ONGC',
    name: 'Oil & Natural Gas Corp',
    sector: 'Energy • NSE Cash',
    price: 226.99,
    change: 1.99,
    change_pct: 0.88,
    high: 229.00,
    low: 224.50,
    volume: 11200000,
    score: 83,
    trend: 'PULLBACK_EMA9',
    next_step: 'Bounced off VWAP support. Monitoring for expansion break.',
    ema9: 225.80,
    vwap: 225.20,
    atr: 3.10
  },
  {
    symbol: 'TCS',
    name: 'Tata Consultancy Services',
    sector: 'IT Services • NSE Cash',
    price: 2405.00,
    change: -2.50,
    change_pct: -0.10,
    high: 2420.00,
    low: 2398.00,
    volume: 1850400,
    score: 80,
    trend: 'PULLBACK_EMA9',
    next_step: 'Bounced off EMA9 support (₹2,402.15). Waiting for expansion candle.',
    ema9: 2402.15,
    vwap: 2404.50,
    atr: 28.50
  },
  {
    symbol: 'MARUTI',
    name: 'Maruti Suzuki India',
    sector: 'Automobiles • NSE Cash',
    price: 12571.00,
    change: -283.00,
    change_pct: -2.20,
    high: 12890.00,
    low: 12540.00,
    volume: 492100,
    score: 82,
    trend: 'PULLBACK_EMA9',
    next_step: 'Testing EMA9 resistance zone (₹12,620.00). Monitoring for bearish rejection.',
    ema9: 12620.00,
    vwap: 12680.00,
    atr: 165.00
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
    open_positions_count: 0,
    governor_mode: 'NORMAL',
    governor_multiplier: 1.0,
    current_drawdown_r: 0.0,
    effective_risk: 200
  });

  const [dashboardData, setDashboardData] = useState({
    instruments: INITIAL_INSTRUMENTS,
    nifty50: { price: 25291.10, change: 146.80, change_pct: 0.58 }
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
    if (activeTab === 'analytics' || activeTab === 'stats') fetchAnalytics();
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
      const res = await fetch(`${API_BASE}/api/bot/panic-square-off`, { method: 'POST' });
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

  const handleSendMorningAlert = async () => {
    const res = await fetch(`${API_BASE}/api/bot/send-morning-alert`, { method: 'POST' });
    if (res.ok) return await res.json();
    throw new Error("Morning alert delivery failed");
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
    { id: 'stats', label: 'Stats', icon: Activity },
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
            <span className="text-sky-400 font-bold">1:2 RRR • Dynamic Risk Governor</span>
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

        {activeTab === 'stats' && (
          <StatsTab
            analyticsData={analyticsData}
            onRefresh={fetchAnalytics}
          />
        )}

        {activeTab === 'settings' && (
          <SettingsTab
            settings={settings}
            onSaveSettings={handleSaveSettings}
            onResetDangerZone={handleResetDangerZone}
            onTestTelegram={handleTestTelegram}
            onSendMorningAlert={handleSendMorningAlert}
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
