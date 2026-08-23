import React from 'react';
import {
  LayoutDashboard,
  Users,
  PhoneCall,
  BarChart3,
  PhoneForwarded,
  Radio,
  Cpu,
  UserCheck,
  Zap,
  Shield,
  Layers,
  ChevronRight,
  X,
} from 'lucide-react';

export default function Sidebar({
  activePage,
  onNavigate,
  mobileOpen = false,
  onCloseMobile,
}) {
  const navItems = [
    {
      id: 'dashboard',
      label: 'Dashboard',
      icon: LayoutDashboard,
      badge: 'Live',
      badgeColor: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    },
    {
      id: 'borrowers',
      label: 'Borrowers',
      icon: Users,
    },
    {
      id: 'calls',
      label: 'Calls',
      icon: PhoneCall,
    },
    {
      id: 'call-stats',
      label: 'Call Statistics',
      icon: BarChart3,
    },
    {
      id: 'dialer',
      label: 'Dialer Control',
      icon: PhoneForwarded,
      badge: 'Core',
      badgeColor: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30',
    },
    {
      id: 'events',
      label: 'Events & Webhooks',
      icon: Radio,
    },
    {
      id: 'predictive',
      label: 'Predictive Engine',
      icon: Cpu,
    },
    {
      id: 'agents',
      label: 'Agent Pool',
      icon: UserCheck,
    },
  ];

  return (
    <>
      {/* Mobile backdrop */}
      {mobileOpen && (
        <div
          onClick={onCloseMobile}
          className="fixed inset-0 z-40 bg-black/80 backdrop-blur-sm lg:hidden transition-opacity"
        />
      )}

      {/* Sidebar container */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-slate-800 bg-[#0B0F17] transition-transform duration-300 ease-in-out lg:static lg:translate-x-0 ${
          mobileOpen ? 'translate-x-0 shadow-2xl' : '-translate-x-full'
        }`}
      >
        {/* Logo and Brand */}
        <div className="flex h-16 items-center justify-between border-b border-slate-800 px-5 bg-[#0B0F17]">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-indigo-600 to-indigo-400 text-white shadow-md shadow-indigo-500/30">
              <Zap className="h-5 w-5" />
            </div>
            <div>
              <span className="text-sm font-bold tracking-tight text-white flex items-center gap-1.5">
                SmartDialer
                <span className="rounded bg-indigo-500/20 px-1.5 py-0.5 text-[9px] font-mono text-indigo-300 border border-indigo-500/30">
                  v1.0
                </span>
              </span>
              <p className="text-[10px] font-medium text-slate-400 tracking-wider uppercase">
                Operations Suite
              </p>
            </div>
          </div>

          <button
            onClick={onCloseMobile}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white lg:hidden"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Safety Boundary Banner */}
        <div className="mx-3 mt-4 rounded-xl border border-indigo-500/20 bg-gradient-to-r from-indigo-950/40 to-slate-900/60 p-3 text-xs">
          <div className="flex items-center gap-2 text-indigo-300 font-semibold text-[11px]">
            <Shield className="h-3.5 w-3.5 text-indigo-400" />
            Safety-First Architecture
          </div>
          <p className="mt-1 text-[10px] text-slate-400 leading-snug">
            Engine &rarr; Safety Controller &rarr; Allocator &rarr; Carrier
          </p>
        </div>

        {/* Navigation List */}
        <div className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
          <div className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-400 font-mono">
            Navigation
          </div>

          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activePage === item.id;

            return (
              <button
                key={item.id}
                onClick={() => {
                  onNavigate(item.id);
                  if (onCloseMobile) onCloseMobile();
                }}
                className={`group flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-xs font-medium transition-all ${
                  isActive
                    ? 'bg-indigo-600/15 text-indigo-300 border border-indigo-500/30 shadow-sm font-semibold'
                    : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-200 border border-transparent'
                }`}
              >
                <div className="flex items-center gap-3">
                  <Icon
                    className={`h-4 w-4 transition-colors ${
                      isActive ? 'text-indigo-400' : 'text-slate-500 group-hover:text-slate-300'
                    }`}
                  />
                  <span>{item.label}</span>
                </div>

                <div className="flex items-center gap-1.5">
                  {item.badge && (
                    <span
                      className={`rounded px-1.5 py-0.5 text-[9px] font-mono border ${item.badgeColor}`}
                    >
                      {item.badge}
                    </span>
                  )}
                  {isActive && <ChevronRight className="h-3.5 w-3.5 text-indigo-400" />}
                </div>
              </button>
            );
          })}
        </div>

        {/* Footer Meta */}
        <div className="border-t border-slate-800 p-4 bg-slate-900/30">
          <div className="flex items-center justify-between text-[11px] text-slate-400">
            <span className="flex items-center gap-1.5 font-mono">
              <Layers className="h-3.5 w-3.5 text-slate-500" />
              FastAPI + SQLite
            </span>
            <span className="text-emerald-400 font-mono font-semibold">Active</span>
          </div>
        </div>
      </aside>
    </>
  );
}
