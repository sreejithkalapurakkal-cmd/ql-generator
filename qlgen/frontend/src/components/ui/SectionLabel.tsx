import React from 'react';

const SectionLabel: React.FC<{ children: React.ReactNode; className?: string }> = ({ children, className = '' }) => (
  <p className={`text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1.5 ${className}`}>{children}</p>
);

export default SectionLabel;
