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

// Instant Hydration Baseline Data for 29 Liquid NSE Mega-Caps (Velocity Compounder)
const INITIAL_INSTRUMENTS = [
  { symbol: 'RELIANCE', name: 'Reliance Industries', sector: 'Energy • NSE Cash', price: 1344.80, change: 5.10, change_pct: 0.38, high: 1348.00, low: 1332.10, volume: 5824900, score: 85, trend: 'MONITORING', next_step: 'Scanning for Gap >=1.2%, RVOL >=2.5x, and RS Leadership.', ema9: 1341.20, vwap: 1339.80, atr: 14.80 },
  { symbol: 'TCS', name: 'Tata Consultancy Services', sector: 'IT Services • NSE Cash', price: 2465.00, change: 12.50, change_pct: 0.51, high: 2478.00, low: 2452.00, volume: 1850400, score: 82, trend: 'MONITORING', next_step: 'Scanning for Gap >=1.2%, RVOL >=2.5x, and RS Leadership.', ema9: 2460.00, vwap: 2458.00, atr: 28.50 },
  { symbol: 'HDFCBANK', name: 'HDFC Bank Ltd', sector: 'Banking • NSE Cash', price: 1740.00, change: 8.20, change_pct: 0.47, high: 1752.00, low: 1731.00, volume: 9240000, score: 84, trend: 'MONITORING', next_step: 'Scanning for Gap >=1.2%, RVOL >=2.5x, and RS Leadership.', ema9: 1735.00, vwap: 1732.00, atr: 18.20 },
  { symbol: 'ICICIBANK', name: 'ICICI Bank Ltd', sector: 'Banking • NSE Cash', price: 1397.00, change: 6.50, change_pct: 0.47, high: 1405.00, low: 1390.00, volume: 4120000, score: 83, trend: 'MONITORING', next_step: 'Scanning for Gap >=1.2%, RVOL >=2.5x, and RS Leadership.', ema9: 1392.00, vwap: 1390.00, atr: 15.10 },
  { symbol: 'SBIN', name: 'State Bank of India', sector: 'Banking • NSE Cash', price: 962.60, change: 7.40, change_pct: 0.77, high: 968.00, low: 955.00, volume: 7850000, score: 86, trend: 'MONITORING', next_step: 'Scanning for Gap >=1.2%, RVOL >=2.5x, and RS Leadership.', ema9: 958.00, vwap: 956.00, atr: 12.80 },
  { symbol: 'INFY', name: 'Infosys Limited', sector: 'IT Services • NSE Cash', price: 1850.00, change: 11.00, change_pct: 0.60, high: 1862.00, low: 1838.00, volume: 4920000, score: 83, trend: 'MONITORING', next_step: 'Scanning for Gap >=1.2%, RVOL >=2.5x, and RS Leadership.', ema9: 1842.00, vwap: 1840.00, atr: 22.00 },
  { symbol: 'LT', name: 'Larsen & Toubro', sector: 'Infrastructure • NSE Cash', price: 3627.10, change: 25.00, change_pct: 0.69, high: 3645.00, low: 3605.00, volume: 680000, score: 85, trend: 'MONITORING', next_step: 'Scanning for Gap >=1.2%, RVOL >=2.5x, and RS Leadership.', ema9: 3615.00, vwap: 3610.00, atr: 42.00 },
  { symbol: 'TATASTEEL', name: 'Tata Steel Ltd', sector: 'Metals & Mining • NSE Cash', price: 175.50, change: 1.20, change_pct: 0.69, high: 177.00, low: 174.10, volume: 15200000, score: 81, trend: 'MONITORING', next_step: 'Scanning for Gap >=1.2%, RVOL >=2.5x, and RS Leadership.', ema9: 174.80, vwap: 174.50, atr: 2.80 },
  { symbol: 'BAJFINANCE', name: 'Bajaj Finance Ltd', sector: 'NBFC & Lending • NSE Cash', price: 6850.00, change: 48.00, change_pct: 0.71, high: 6890.00, low: 6810.00, volume: 1250000, score: 84, trend: 'MONITORING', next_step: 'Scanning for Gap >=1.2%, RVOL >=2.5x, and RS Leadership.', ema9: 6825.00, vwap: 6815.00, atr: 85.00 },
  { symbol: 'MARUTI', name: 'Maruti Suzuki India', sector: 'Automobiles • NSE Cash', price: 11489.00, change: 65.00, change_pct: 0.57, high: 11550.00, low: 11420.00, volume: 320000, score: 82, trend: 'MONITORING', next_step: 'Scanning for Gap >=1.2%, RVOL >=2.5x, and RS Leadership.', ema9: 11450.00, vwap: 11430.00, atr: 155.00 },
  { symbol: 'BHARTIARTL', name: 'Bharti Airtel Ltd', sector: 'Telecommunications • NSE Cash', price: 1905.00, change: 14.00, change_pct: 0.74, high: 1918.00, low: 1892.00, volume: 3100000, score: 84, trend: 'MONITORING', next_step: 'Scanning for Gap >=1.2%, RVOL >=2.5x, and RS Leadership.', ema9: 1898.00, vwap: 1895.00, atr: 24.50 },
  { symbol: 'WIPRO', name: 'Wipro Limited', sector: 'IT Services • NSE Cash', price: 550.00, change: 3.20, change_pct: 0.59, high: 554.00, low: 546.50, volume: 6400000, score: 80, trend: 'MONITORING', next_step: 'Scanning for Gap >=1.2%, RVOL >=2.5x, and RS Leadership.', ema9: 548.00, vwap: 547.00, atr: 7.80 },
  { symbol: 'GRASIM', name: 'Grasim Industries', sector: 'Materials & Cement • NSE Cash', price: 2920.00, change: 18.00, change_pct: 0.62, high: 2938.00, low: 2902.00, volume: 450000, score: 82, trend: 'MONITORING', next_step: 'Scanning for Gap >=1.2%, RVOL >=2.5x, and RS Leadership.', ema9: 2910.00, vwap: 2905.00, atr: 38.00 },
  { symbol: 'SUNPHARMA', name: 'Sun Pharmaceutical Ind', sector: 'Healthcare & Pharma • NSE Cash', price: 1758.80, change: 9.50, change_pct: 0.54, high: 1768.00, low: 1748.00, volume: 1120000, score: 83, trend: 'MONITORING', next_step: 'Scanning for Gap >=1.2%, RVOL >=2.5x, and RS Leadership.', ema9: 1752.00, vwap: 1750.00, atr: 21.00 },
  { symbol: 'INDUSINDBK', name: 'IndusInd Bank', sector: 'Banking • NSE Cash', price: 877.00, change: 5.20, change_pct: 0.60, high: 885.00, low: 871.00, volume: 2450000, score: 81, trend: 'MONITORING', next_step: 'Scanning for Gap >=1.2%, RVOL >=2.5x, and RS Leadership.', ema9: 874.00, vwap: 872.00, atr: 12.00 },
  { symbol: 'TECHM', name: 'Tech Mahindra Ltd', sector: 'IT Services • NSE Cash', price: 1790.00, change: 12.00, change_pct: 0.67, high: 1805.00, low: 1778.00, volume: 1350000, score: 82, trend: 'MONITORING', next_step: 'Scanning for Gap >=1.2%, RVOL >=2.5x, and RS Leadership.', ema9: 1782.00, vwap: 1780.00, atr: 25.00 },
  { symbol: 'HCLTECH', name: 'HCL Technologies', sector: 'IT Services • NSE Cash', price: 1820.00, change: 10.50, change_pct: 0.58, high: 1832.00, low: 1809.00, volume: 1680000, score: 83, trend: 'MONITORING', next_step: 'Scanning for Gap >=1.2%, RVOL >=2.5x, and RS Leadership.', ema9: 1812.00, vwap: 1810.00, atr: 23.50 },
  { symbol: 'KOTAKBANK', name: 'Kotak Mahindra Bank', sector: 'Banking • NSE Cash', price: 1750.00, change: 8.00, change_pct: 0.46, high: 1762.00, low: 1742.00, volume: 3850000, score: 82, trend: 'MONITORING', next_step: 'Scanning for Gap >=1.2%, RVOL >=2.5x, and RS Leadership.', ema9: 1745.00, vwap: 1742.00, atr: 20.00 },
  { symbol: 'AXISBANK', name: 'Axis Bank Ltd', sector: 'Banking • NSE Cash', price: 1290.00, change: 7.50, change_pct: 0.58, high: 1301.00, low: 1282.00, volume: 3950000, score: 83, trend: 'MONITORING', next_step: 'Scanning for Gap >=1.2%, RVOL >=2.5x, and RS Leadership.', ema9: 1285.00, vwap: 1283.00, atr: 16.50 },
  { symbol: 'ONGC', name: 'Oil & Natural Gas Corp', sector: 'Energy • NSE Cash', price: 222.00, change: 1.80, change_pct: 0.82, high: 224.50, low: 220.00, volume: 8900000, score: 82, trend: 'MONITORING', next_step: 'Scanning for Gap >=1.2%, RVOL >=2.5x, and RS Leadership.', ema9: 221.00, vwap: 220.50, atr: 3.20 },
  { symbol: 'NTPC', name: 'NTPC Limited', sector: 'Utilities & Power • NSE Cash', price: 315.15, change: 2.10, change_pct: 0.67, high: 318.00, low: 313.00, volume: 5400000, score: 81, trend: 'MONITORING', next_step: 'Scanning for Gap >=1.2%, RVOL >=2.5x, and RS Leadership.', ema9: 314.00, vwap: 313.50, atr: 4.80 },
  { symbol: 'POWERGRID', name: 'Power Grid Corp', sector: 'Utilities & Power • NSE Cash', price: 250.45, change: 1.60, change_pct: 0.64, high: 252.50, low: 248.50, volume: 6200000, score: 81, trend: 'MONITORING', next_step: 'Scanning for Gap >=1.2%, RVOL >=2.5x, and RS Leadership.', ema9: 249.50, vwap: 249.00, atr: 3.90 },
  { symbol: 'COALINDIA', name: 'Coal India Ltd', sector: 'Mining & Energy • NSE Cash', price: 417.20, change: 3.10, change_pct: 0.75, high: 421.00, low: 414.00, volume: 4800000, score: 82, trend: 'MONITORING', next_step: 'Scanning for Gap >=1.2%, RVOL >=2.5x, and RS Leadership.', ema9: 415.50, vwap: 415.00, atr: 6.20 },
  { symbol: 'JSWSTEEL', name: 'JSW Steel Ltd', sector: 'Metals & Mining • NSE Cash', price: 1216.30, change: 8.50, change_pct: 0.70, high: 1228.00, low: 1208.00, volume: 1450000, score: 83, trend: 'MONITORING', next_step: 'Scanning for Gap >=1.2%, RVOL >=2.5x, and RS Leadership.', ema9: 1210.00, vwap: 1208.00, atr: 17.50 },
  { symbol: 'ITC', name: 'ITC Limited', sector: 'FMCG • NSE Cash', price: 470.00, change: 2.20, change_pct: 0.47, high: 473.00, low: 468.00, volume: 8100000, score: 80, trend: 'MONITORING', next_step: 'Scanning for Gap >=1.2%, RVOL >=2.5x, and RS Leadership.', ema9: 469.00, vwap: 468.50, atr: 5.50 },
  { symbol: 'HINDUNILVR', name: 'Hindustan Unilever', sector: 'FMCG • NSE Cash', price: 2420.00, change: 12.00, change_pct: 0.50, high: 2435.00, low: 2410.00, volume: 920000, score: 81, trend: 'MONITORING', next_step: 'Scanning for Gap >=1.2%, RVOL >=2.5x, and RS Leadership.', ema9: 2415.00, vwap: 2412.00, atr: 26.00 },
  { symbol: 'TITAN', name: 'Titan Company Ltd', sector: 'Consumer Discretionary • NSE Cash', price: 3444.80, change: 22.00, change_pct: 0.64, high: 3465.00, low: 3425.00, volume: 840000, score: 83, trend: 'MONITORING', next_step: 'Scanning for Gap >=1.2%, RVOL >=2.5x, and RS Leadership.', ema9: 3435.00, vwap: 3430.00, atr: 44.00 },
  { symbol: 'ADANIENT', name: 'Adani Enterprises', sector: 'Diversified Conglomerate • NSE Cash', price: 2692.00, change: 24.00, change_pct: 0.90, high: 2715.00, low: 2670.00, volume: 1550000, score: 84, trend: 'MONITORING', next_step: 'Scanning for Gap >=1.2%, RVOL >=2.5x, and RS Leadership.', ema9: 2680.00, vwap: 2675.00, atr: 55.00 },
  { symbol: 'ULTRACEMCO', name: 'UltraTech Cement', sector: 'Materials & Cement • NSE Cash', price: 10907.00, change: 75.00, change_pct: 0.69, high: 10980.00, low: 10840.00, volume: 220000, score: 83, trend: 'MONITORING', next_step: 'Scanning for Gap >=1.2%, RVOL >=2.5x, and RS Leadership.', ema9: 10870.00, vwap: 10850.00, atr: 145.00 }
];

export default function App() {
  const [showSplash, setShowSplash] = useState(true);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [chartSymbol, setChartSymbol] = useState(null);

  // Core App State
  const [portfolio, setPortfolio] = useState({
    capital: 100000,
    available_margin: 100000,
    used_margin: 0,
    total_pnl: 0,
    total_r: 0,
    bot_active: true,
    trading_mode: 'PAPER',
    open_positions_count: 0,
    governor_mode: 'NORMAL',
    governor_multiplier: 1.0,
    current_drawdown_r: 0.0,
    effective_risk: 2500
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
