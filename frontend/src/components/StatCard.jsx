import React from 'react';

export default function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  color = 'indigo',
  loading = false,
  badge,
  onClick,
}) {
  const colorMap = {
    indigo: {
      bg: 'from-indigo-500/10 to-transparent',
      border: 'hover:border-indigo-500/40',
      iconBg: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20',
      glow: 'glow-brand',
    },
    emerald: {
      bg: 'from-emerald-500/10 to-transparent',
      border: 'hover:border-emerald-500/40',
      iconBg: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
      glow: 'glow-emerald',
    },
    amber: {
      bg: 'from-amber-500/10 to-transparent',
      border: 'hover:border-amber-500/40',
      iconBg: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
      glow: 'glow-amber',
    },
    cyan: {
      bg: 'from-cyan-500/10 to-transparent',
      border: 'hover:border-cyan-500/40',
      iconBg: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
      glow: 'glow-brand',
    },
    rose: {
      bg: 'from-rose-500/10 to-transparent',
      border: 'hover:border-rose-500/40',
      iconBg: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
      glow: 'glow-rose',
    },
    purple: {
      bg: 'from-purple-500/10 to-transparent',
      border: 'hover:border-purple-500/40',
      iconBg: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
      glow: 'glow-brand',
    },
  };

  const scheme = colorMap[color] || colorMap.indigo;

  return (
    <div
      onClick={onClick}
      className={`relative overflow-hidden rounded-xl border border-slate-800 bg-[#111827] p-5 transition-all duration-200 ${
        scheme.border
      } ${onClick ? 'cursor-pointer hover:-translate-y-0.5' : ''}`}
    >
      {/* Background Gradient Accent */}
      <div className={`absolute inset-0 bg-gradient-to-br ${scheme.bg} pointer-events-none opacity-60`} />

      <div className="relative flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              {title}
            </span>
            {badge && (
              <span className="rounded-full bg-slate-800 px-2 py-0.5 text-[10px] font-medium text-slate-300 border border-slate-700">
                {badge}
              </span>
            )}
          </div>

          <div className="mt-2.5 flex items-baseline gap-2">
            {loading ? (
              <div className="h-8 w-20 animate-pulse rounded bg-slate-800" />
            ) : (
              <span className="text-3xl font-extrabold tracking-tight text-white font-mono">
                {value ?? '0'}
              </span>
            )}

            {trend && !loading && (
              <span
                className={`text-xs font-medium ${
                  trend > 0 ? 'text-emerald-400' : trend < 0 ? 'text-rose-400' : 'text-slate-400'
                }`}
              >
                {trend > 0 ? `+${trend}%` : `${trend}%`}
              </span>
            )}
          </div>

          {subtitle && (
            <p className="mt-1.5 text-xs text-slate-400 line-clamp-1">{subtitle}</p>
          )}
        </div>

        {Icon && (
          <div className={`flex h-11 w-11 items-center justify-center rounded-lg border ${scheme.iconBg}`}>
            <Icon className="h-5 w-5" />
          </div>
        )}
      </div>
    </div>
  );
}
