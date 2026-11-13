import React, { useState, useEffect, useCallback } from 'react';
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

export default function App() {
  const [showSplash, setShowSplash] = useState(true);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [chartSymbol, setChartSymbol] = useState(null);

  // Core App States
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

  const [dashboardData, setDashboardData] = useState({
    instruments: [],
    nifty50: { price: 24350.0, change: 0.0, change_pct: 0.0 }
  });

  const [positions, setPositions] = useState([]);
  const [analyticsData, setAnalyticsData] = useState(null);
  const [settings, setSettings] = useState(null);

  // Fetch Dashboard & Live Prices (every 1.5s)
  const fetchDashboard = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/dashboard`);
      if (res.ok) {
        const data = await res.json();
        setDashboardData(data);
        if (data.summary) {
          setPortfolio(data.summary);
          setPositions(data.summary.positions || []);
        }
      }
    } catch (err) {
      console.warn("Live feed fetch error:", err);
    }
  }, []);

  // Fetch Analytics & Ledger
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

  // Fetch Settings
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

  // Polling loop for live ticks & positions
  useEffect(() => {
    fetchDashboard();
    fetchAnalytics();
    fetchSettings();

    const interval = setInterval(() => {
      fetchDashboard();
    }, 1500);

    return () => clearInterval(interval);
  }, [fetchDashboard, fetchAnalytics, fetchSettings]);

  // Periodic refresh for analytics
  useEffect(() => {
    const analyticsInterval = setInterval(() => {
      fetchAnalytics();
    }, 5000);
    return () => clearInterval(analyticsInterval);
  }, [fetchAnalytics]);

  // ---------------- ACTION HANDLERS ----------------
  const handleToggleBot = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/bot/toggle`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setPortfolio((prev) => ({ ...prev, bot_active: data.bot_active }));
      }
    } catch (err) {
      console.error("Bot toggle error:", err);
    }
  };

  const handlePanicSquareOff = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/bot/panic-square-off`, { method: 'POST' });
      if (res.ok) {
        await fetchDashboard();
        await fetchAnalytics();
      }
    } catch (err) {
      console.error("Panic exit error:", err);
    }
  };

  const handleDeletePosition = async (posId) => {
    try {
      const res = await fetch(`${API_BASE}/api/positions/${posId}`, { method: 'DELETE' });
      if (res.ok) {
        await fetchDashboard();
      }
    } catch (err) {
      console.error("Delete position error:", err);
    }
  };

  const handleClosePosition = async (posId) => {
    try {
      const res = await fetch(`${API_BASE}/api/positions/${posId}/close`, { method: 'POST' });
      if (res.ok) {
        await fetchDashboard();
        await fetchAnalytics();
      }
    } catch (err) {
      console.error("Close position error:", err);
    }
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
    } catch (err) {
      console.error("Reset error:", err);
    }
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

  // Entrance Splash Screen
  if (showSplash) {
    return <EntranceSplash onFinish={() => setShowSplash(false)} />;
  }

  return (
    <div className="min-h-screen bg-[#080A0F] text-slate-100 flex flex-col font-sans select-none antialiased">
      
      {/* PERSISTENT TOP HEADER BAR (Always visible across all tabs) */}
      <HeaderBar
        portfolio={portfolio}
        onToggleBot={handleToggleBot}
        onPanicSquareOff={handlePanicSquareOff}
      />

      {/* ACTIVE TAB CONTENT */}
      <main className="flex-1 overflow-y-auto">
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

      {/* PERSISTENT BOTTOM NAVIGATION BAR */}
      <BottomNav
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        positionsCount={positions.length}
      />

      {/* CANDLESTICK CHART MODAL */}
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
