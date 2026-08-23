import React from 'react';
import { Inbox } from 'lucide-react';

export default function EmptyState({
  icon: Icon = Inbox,
  title = 'No data available',
  message = 'There is currently no information to display here.',
  action = null,
  className = '',
}) {
  return (
    <div className={`flex flex-col items-center justify-center p-8 text-center ${className}`}>
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-slate-800 bg-slate-900/80 text-slate-400 shadow-inner">
        <Icon className="h-7 w-7 stroke-[1.5]" />
      </div>
      
      <h3 className="mt-4 text-base font-semibold text-slate-200">{title}</h3>
      <p className="mt-1.5 max-w-sm text-xs text-slate-400 leading-relaxed">{message}</p>
      
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
