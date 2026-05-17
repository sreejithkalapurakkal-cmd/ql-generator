import React from 'react';

interface Tab {
  key: string;
  label?: React.ReactNode;
  icon?: React.ReactNode;
}

interface PillTabsProps {
  tabs: Tab[];
  activeKey: string;
  onChange: (key: string) => void;
  variant?: 'pill' | 'underline';
  className?: string;
}

const PillTabs: React.FC<PillTabsProps> = ({
  tabs, activeKey, onChange, variant = 'pill', className = '',
}) => {
  if (variant === 'underline') {
    return (
      <div className={`flex gap-0 border-b border-gray-200 ${className}`}>
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => onChange(tab.key)}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
              activeKey === tab.key
                ? 'border-brand text-brand'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>
    );
  }

  return (
    <div className={`inline-flex items-center gap-1 bg-gray-100 rounded-lg p-1 ${className}`}>
      {tabs.map((tab) => (
        <button
          key={tab.key}
          onClick={() => onChange(tab.key)}
          className={`flex items-center gap-1.5 h-7 px-3 text-xs font-medium rounded-md transition-all ${
            activeKey === tab.key
              ? 'bg-white text-gray-900 shadow-sm'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          {tab.icon}
          {tab.label}
        </button>
      ))}
    </div>
  );
};

export default PillTabs;
