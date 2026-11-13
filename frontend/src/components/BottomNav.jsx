import React from 'react';
import { 
  LayoutDashboard, 
  Layers, 
  BarChart3, 
  Sliders 
} from 'lucide-react';

export default function BottomNav({ activeTab, onSelectTab, positionsCount = 0 }) {
  const tabs = [
    { id: 'dashboard', label: 'Home', icon: LayoutDashboard },
    { id: 'positions', label: 'Positions', icon: Layers, badge: positionsCount },
    { id: 'analytics', label: 'Analytics', icon: BarChart3 },
    { id: 'settings', label: 'Settings', icon: Sliders }
  ];

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 glass-panel border-t border-slate-800/90 py-1.5 px-4 sm:px-8">
      <div className="max-w-md sm:max-w-lg mx-auto flex items-center justify-around">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;

          return (
            <button
              key={tab.id}
              onClick={() => onSelectTab(tab.id)}
              className={`relative flex flex-col items-center justify-center py-1.5 px-3 sm:px-5 rounded-2xl transition-all duration-200 ${
                isActive 
                  ? 'text-emerald-400 font-bold' 
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <div className="relative">
                <Icon className={`w-5 h-5 transition-transform duration-200 ${isActive ? 'scale-110' : 'scale-100'}`} />
                {tab.badge > 0 && (
                  <span className="absolute -top-1.5 -right-2.5 px-1.5 py-0.2 min-w-4 text-[10px] font-mono font-extrabold rounded-full bg-emerald-500 text-black flex items-center justify-center shadow-lg shadow-emerald-500/50">
                    {tab.badge}
                  </span>
                )}
              </div>
              <span className={`text-[11px] mt-1 tracking-tight ${isActive ? 'text-emerald-400 font-bold' : 'text-slate-400'}`}>
                {tab.label}
              </span>
              {isActive && (
                <span className="absolute -bottom-1 w-6 h-0.5 rounded-full bg-emerald-400 shadow-sm shadow-emerald-400" />
              )}
            </button>
          );
        })}
      </div>
    </nav>
  );
}
