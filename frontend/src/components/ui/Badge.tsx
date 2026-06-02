import React from 'react';

type BadgeVariant = 'success' | 'warning' | 'error' | 'inactive' | 'primary';

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  className?: string;
}

const variantStyles: Record<BadgeVariant, string> = {
  success: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  warning: 'bg-amber-50 text-amber-700 ring-amber-600/20',
  error: 'bg-red-50 text-red-700 ring-red-600/10',
  inactive: 'bg-slate-50 text-slate-600 ring-slate-500/10',
  primary: 'bg-indigo-50 text-indigo-700 ring-indigo-600/10',
};

export function Badge({ children, variant = 'inactive', className = '' }: BadgeProps) {
  return (
    <span className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset ${variantStyles[variant]} ${className}`}>
      {children}
    </span>
  );
}