import React from 'react';
import { 
  LayoutDashboard, 
  Layers, 
  BarChart3, 
  Sliders 
} from 'lucide-react';

export default function BottomNav({ activeTab, onSelectTab, positionsCount = 0 }) {
  const tabs = [
    { id: 'dashboard', label: 'Watchlist', icon: LayoutDashboard },
    { id: 'positions', label: 'Positions', icon: Layers, badge: positionsCount },
    { id: 'analytics', label: 'Analytics', icon: BarChart3 },
    { id: 'settings', label: 'Settings', icon: Sliders }
  ];

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 flex justify-center p-2 sm:p-3 pointer-events-none">
      <div className="w-full max-w-lg sm:max-w-xl glass-panel rounded-2xl sm:rounded-3xl py-1.5 px-2.5 sm:px-4 shadow-2xl pointer-events-auto border border-white/[0.12] bg-[#0A0E17]/90 backdrop-blur-2xl">
        <div className="flex items-center justify-around gap-1">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;

            return (
              <button
                key={tab.id}
                onClick={() => onSelectTab(tab.id)}
                className={`relative flex-1 flex flex-col items-center justify-center py-1 sm:py-1.5 px-2 rounded-xl transition-all duration-200 cursor-pointer ${
                  isActive 
                    ? 'text-sky-300 font-black' 
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {/* ACTIVE PILL INDICATOR */}
                <div className={`relative px-3.5 py-1 rounded-xl flex items-center justify-center transition-all ${
                  isActive 
                    ? 'bg-sky-500/20 text-sky-300 border border-sky-400/30 shadow-md shadow-sky-500/20' 
                    : 'bg-transparent text-slate-400'
                }`}>
                  <Icon className={`w-4 h-4 sm:w-5 sm:h-5 transition-transform duration-200 ${isActive ? 'scale-110 text-sky-300' : 'scale-100'}`} />
                  
                  {/* Positions Badge */}
                  {tab.badge > 0 && (
                    <span className="absolute -top-1 -right-1 px-1.5 py-0.2 min-w-4 text-[9px] font-mono font-black rounded-full bg-sky-400 text-slate-950 flex items-center justify-center shadow-lg shadow-sky-400/50">
                      {tab.badge}
                    </span>
                  )}
                </div>

                <span className={`text-[10px] mt-0.5 font-mono tracking-tight ${
                  isActive ? 'text-sky-300 font-extrabold' : 'text-slate-400 font-medium'
                }`}>
                  {tab.label}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </nav>
  );
}
