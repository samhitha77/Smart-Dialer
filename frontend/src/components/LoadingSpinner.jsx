import React from 'react';
import { Loader2 } from 'lucide-react';

export default function LoadingSpinner({ message = 'Loading...', size = 'md', className = '' }) {
  const sizeMap = {
    sm: 'h-4 w-4',
    md: 'h-6 w-6',
    lg: 'h-10 w-10',
  };

  return (
    <div className={`flex flex-col items-center justify-center p-6 text-center ${className}`}>
      <Loader2 className={`${sizeMap[size] || sizeMap.md} animate-spin text-indigo-500`} />
      {message && <p className="mt-2.5 text-xs text-slate-400 font-medium">{message}</p>}
    </div>
  );
}
