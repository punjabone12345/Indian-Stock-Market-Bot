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
    <nav className="fixed bottom-0 w-full max-w-[480px] z-40 bg-[#090D16]/95 backdrop-blur-2xl border-t border-white/[0.08] py-1.5 px-3 shadow-2xl">
      <div className="flex items-center justify-around">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;

          return (
            <button
              key={tab.id}
              onClick={() => onSelectTab(tab.id)}
              className={`relative flex flex-col items-center justify-center py-1 px-3 rounded-2xl transition-all duration-200 cursor-pointer ${
                isActive 
                  ? 'text-sky-300 font-black' 
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {/* NOW IN ANDROID ACTIVE PILL INDICATOR */}
              <div className={`relative px-4 py-1 rounded-full flex items-center justify-center transition-all ${
                isActive 
                  ? 'bg-sky-500/20 text-sky-300 border border-sky-400/30 shadow-md shadow-sky-500/15' 
                  : 'bg-transparent text-slate-400'
              }`}>
                <Icon className={`w-5 h-5 transition-transform duration-200 ${isActive ? 'scale-110 text-sky-300' : 'scale-100'}`} />
                
                {/* Positions Badge */}
                {tab.badge > 0 && (
                  <span className="absolute -top-1 -right-1 px-1.5 py-0.2 min-w-4 text-[9px] font-mono font-extrabold rounded-full bg-sky-400 text-slate-950 flex items-center justify-center shadow-lg shadow-sky-400/50">
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
    </nav>
  );
}
