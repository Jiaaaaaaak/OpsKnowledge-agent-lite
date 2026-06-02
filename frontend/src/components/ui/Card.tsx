import React from 'react';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  title?: string;
  description?: string;
}

export function Card({ children, className = '', title, description }: CardProps) {
  return (
    <div className={`bg-card rounded-lg border border-slate-200 shadow-sm ${className}`}>
      {(title || description) && (
        <div className="px-6 py-4 border-b border-slate-100">
          {title && <h3 className="text-lg font-semibold text-slate-800">{title}</h3>}
          {description && <p className="text-sm text-secondary mt-1">{description}</p>}
        </div>
      )}
      <div className="p-6">{children}</div>
    </div>
  );
}