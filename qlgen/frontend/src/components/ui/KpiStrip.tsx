import React from 'react';

interface KpiItem {
  label: string;
  value: string | number;
  color?: string;
}

interface KpiStripProps {
  items: KpiItem[];
  className?: string;
}

const KpiStrip: React.FC<KpiStripProps> = ({ items, className = '' }) => (
  <div className={`grid gap-3 ${className}`} style={{ gridTemplateColumns: `repeat(${items.length}, 1fr)` }}>
    {items.map((item) => (
      <div key={item.label} className="bg-white border border-gray-200 rounded-lg px-4 py-3">
        <p className="text-xs text-gray-400 mb-1">{item.label}</p>
        <p className="text-2xl font-bold leading-none" style={item.color ? { color: item.color } : { color: '#1a1a2e' }}>
          {item.value}
        </p>
      </div>
    ))}
  </div>
);

export default KpiStrip;
