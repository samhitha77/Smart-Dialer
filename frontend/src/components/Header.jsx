import React, { useState, useEffect } from 'react';
import { RefreshCw, Activity, CheckCircle2, AlertTriangle, Menu, ShieldCheck } from 'lucide-react';
import api, { API_BASE_URL } from '../services/api';

export default function Header({
  title,
  subtitle,
  onRefresh,
  refreshing = false,
  onToggleSidebar,
}) {
  const [backendStatus, setBackendStatus] = useState('checking'); // 'online' | 'offline' | 'checking'
  const [lastChecked, setLastChecked] = useState(null);

  const checkHealth = async () => {
    try {
      await api.getHealth();
      setBackendStatus('online');
      setLastChecked(new Date().toLocaleTimeString());
    } catch {
      setBackendStatus('offline');
      setLastChecked(new Date().toLocaleTimeString());
    }
  };

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 20000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="sticky top-0 z-30 flex h-16 w-full items-center justify-between border-b border-slate-800/80 bg-[#0B0F17]/85 px-4 sm:px-6 backdrop-blur-md">
      {/* Left: Mobile Toggle & Title */}
      <div className="flex items-center gap-3">
        <button
          onClick={onToggleSidebar}
          className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-800 text-slate-400 hover:bg-slate-800 hover:text-white lg:hidden"
        >
          <Menu className="h-5 w-5" />
        </button>

        <div>
          <h1 className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
            {title}
          </h1>
          {subtitle && (
            <p className="text-xs text-slate-400 hidden sm:block">{subtitle}</p>
          )}
        </div>
      </div>

      {/* Right: Backend Connection Status & Refresh */}
      <div className="flex items-center gap-3">
        {/* Backend status badge */}
        <div
          className={`flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-mono transition-all ${
            backendStatus === 'online'
              ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
              : backendStatus === 'offline'
              ? 'border-rose-500/30 bg-rose-500/10 text-rose-300'
              : 'border-slate-700 bg-slate-800/60 text-slate-400'
          }`}
          title={`Backend API: ${API_BASE_URL}`}
        >
          <span
            className={`h-2 w-2 rounded-full ${
              backendStatus === 'online'
                ? 'bg-emerald-400 animate-pulse'
                : backendStatus === 'offline'
                ? 'bg-rose-500'
                : 'bg-amber-400 animate-ping'
            }`}
          />
          <span className="hidden md:inline font-semibold">
            {backendStatus === 'online'
              ? 'FastAPI Connected'
              : backendStatus === 'offline'
              ? 'Backend Disconnected'
              : 'Checking API...'}
          </span>
          <span className="md:hidden">
            {backendStatus === 'online' ? 'Online' : 'Offline'}
          </span>
        </div>

        {/* Refresh button */}
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={refreshing}
            className="flex h-9 items-center gap-2 rounded-lg border border-slate-800 bg-[#111827] px-3 text-xs font-medium text-slate-300 hover:border-slate-700 hover:bg-slate-800 hover:text-white transition-all disabled:opacity-50"
            title="Refresh active dataset"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin text-indigo-400' : ''}`} />
            <span className="hidden sm:inline">Refresh</span>
          </button>
        )}
      </div>
    </header>
  );
}
