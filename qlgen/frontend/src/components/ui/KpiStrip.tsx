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
  <div className={`grid gap-2 ${className}`} style={{ gridTemplateColumns: `repeat(${items.length}, 1fr)` }}>
    {items.map((item) => (
      <div key={item.label} className="bg-white border border-gray-200 rounded-lg px-3 py-2">
        <p className="text-[11px] text-gray-400 mb-0.5">{item.label}</p>
        <p className="text-lg font-bold leading-none" style={item.color ? { color: item.color } : { color: '#1a1a2e' }}>
          {item.value}
        </p>
      </div>
    ))}
  </div>
);

export default KpiStrip;
