import React, { useEffect } from 'react';
import { CheckCircle2, AlertCircle, AlertTriangle, Info, X } from 'lucide-react';

export default function Toast({ toast, onClose }) {
  if (!toast) return null;

  const { id, type = 'info', message, duration = 4000 } = toast;

  useEffect(() => {
    if (duration) {
      const timer = setTimeout(() => {
        onClose(id);
      }, duration);
      return () => clearTimeout(timer);
    }
  }, [id, duration, onClose]);

  const typeConfig = {
    success: {
      icon: CheckCircle2,
      bg: 'bg-emerald-950/90 border-emerald-500/40 text-emerald-200',
      iconColor: 'text-emerald-400',
    },
    error: {
      icon: AlertCircle,
      bg: 'bg-rose-950/90 border-rose-500/40 text-rose-200',
      iconColor: 'text-rose-400',
    },
    warning: {
      icon: AlertTriangle,
      bg: 'bg-amber-950/90 border-amber-500/40 text-amber-200',
      iconColor: 'text-amber-400',
    },
    info: {
      icon: Info,
      bg: 'bg-indigo-950/90 border-indigo-500/40 text-indigo-200',
      iconColor: 'text-indigo-400',
    },
  };

  const config = typeConfig[type] || typeConfig.info;
  const Icon = config.icon;

  return (
    <div className="fixed bottom-5 right-5 z-50 flex max-w-md items-center gap-3 rounded-xl border p-4 shadow-2xl backdrop-blur-md transition-all duration-300 animate-in fade-in slide-in-from-bottom-5">
      <div className={`flex items-center gap-3 rounded-lg border px-4 py-3 shadow-lg ${config.bg}`}>
        <Icon className={`h-5 w-5 shrink-0 ${config.iconColor}`} />
        <p className="text-xs font-medium leading-relaxed">{message}</p>
        <button
          onClick={() => onClose(id)}
          className="ml-2 rounded-md p-1 hover:bg-white/10 transition-colors text-slate-300"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
