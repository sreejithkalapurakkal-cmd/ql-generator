import React, { useState, useEffect } from 'react';
import { Drawer, Button, Input, Collapse, message } from 'antd';
import {
  PlusOutlined, ThunderboltOutlined, DollarOutlined, SearchOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { Badge } from './ui';
import { updateTrackingList } from '../api/trackingApi';
import type { SignalHints } from '../types';

interface SignalHintsDrawerProps {
  open: boolean;
  onClose: () => void;
  listId: string;
  hints: SignalHints;
  onSaved: (hints: SignalHints) => void;
}

const PRESETS: Record<string, string[]> = {
  budget: ['Series A/B/C funding', 'Revenue growth', 'CapEx increase', 'Cloud migration budget', 'Hiring budget expansion'],
  urgency: ['New CTO/CIO appointment', 'Regulatory compliance deadline', 'Technology migration', 'Contract renewal window', 'Competitor loss'],
  custom: ['AI/ML adoption', 'Kubernetes migration', 'Sustainability initiative', 'Digital transformation', 'International expansion'],
  roles: ['VP Engineering', 'CTO', 'Head of Product', 'Director of IT', 'Chief Revenue Officer'],
};

const SECTIONS = [
  {
    key: 'budget',
    icon: <DollarOutlined />,
    iconColor: '#52c41a',
    title: 'Budget Signals',
    description: 'Evidence that the company has budget or is investing in relevant areas.',
    tagCls: 'bg-green-50 text-green-700',
    bgCls: 'bg-green-50/40',
    borderCls: 'border-green-200/50',
  },
  {
    key: 'urgency',
    icon: <ThunderboltOutlined />,
    iconColor: '#fa541c',
    title: 'Urgency Signals',
    description: 'Evidence the company needs to act now \u2014 deadlines, compliance, competitive pressure.',
    tagCls: 'bg-orange-50 text-orange-700',
    bgCls: 'bg-orange-50/40',
    borderCls: 'border-orange-200/50',
  },
  {
    key: 'custom',
    icon: <SearchOutlined />,
    iconColor: '#1890ff',
    title: 'Custom Research Hints',
    description: 'Any other topics to research for these companies.',
    tagCls: 'bg-blue-50 text-blue-700',
    bgCls: 'bg-blue-50/40',
    borderCls: 'border-blue-200/50',
  },
  {
    key: 'roles',
    icon: <UserOutlined />,
    iconColor: '#722ed1',
    title: 'Target Roles',
    description: 'Decision-maker titles to prioritize when finding contacts.',
    tagCls: 'bg-purple-50 text-purple-700',
    bgCls: 'bg-purple-50/40',
    borderCls: 'border-purple-200/50',
  },
];

const HINTS_KEY_MAP: Record<string, keyof SignalHints> = {
  budget: 'budget_signals',
  urgency: 'urgency_signals',
  custom: 'custom_hints',
  roles: 'target_roles',
};

const SignalHintsDrawer: React.FC<SignalHintsDrawerProps> = ({
  open, onClose, listId, hints, onSaved,
}) => {
  const [data, setData] = useState<Record<string, string[]>>({
    budget: [], urgency: [], custom: [], roles: [],
  });
  const [inputs, setInputs] = useState<Record<string, string>>({
    budget: '', urgency: '', custom: '', roles: '',
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setData({
      budget: hints.budget_signals || [],
      urgency: hints.urgency_signals || [],
      custom: hints.custom_hints || [],
      roles: hints.target_roles || [],
    });
  }, [hints, open]);

  const addTag = (sectionKey: string) => {
    const value = inputs[sectionKey]?.trim();
    if (!value || data[sectionKey].includes(value)) return;
    setData((prev) => ({ ...prev, [sectionKey]: [...prev[sectionKey], value] }));
    setInputs((prev) => ({ ...prev, [sectionKey]: '' }));
  };

  const removeTag = (sectionKey: string, tag: string) => {
    setData((prev) => ({ ...prev, [sectionKey]: prev[sectionKey].filter((t) => t !== tag) }));
  };

  const addPreset = (sectionKey: string, preset: string) => {
    if (data[sectionKey].includes(preset)) return;
    setData((prev) => ({ ...prev, [sectionKey]: [...prev[sectionKey], preset] }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const newHints: SignalHints = {
        budget_signals: data.budget,
        urgency_signals: data.urgency,
        custom_hints: data.custom,
        target_roles: data.roles,
      };
      await updateTrackingList(listId, { signal_hints: newHints });
      onSaved(newHints);
      message.success('Signal hints saved');
      onClose();
    } catch {
      message.error('Failed to save signal hints');
    } finally {
      setSaving(false);
    }
  };

  const totalHints = data.budget.length + data.urgency.length + data.custom.length + data.roles.length;

  return (
    <Drawer
      title={
        <div>
          <div className="text-base font-bold text-gray-900">Signal Research Hints</div>
          <div className="text-xs text-gray-400 font-normal mt-0.5">
            Guide signal detection to find evidence specific to your sales context
          </div>
        </div>
      }
      open={open}
      onClose={onClose}
      width={640}
      styles={{ body: { padding: '16px 24px' } }}
      extra={
        <Button type="primary" onClick={handleSave} loading={saving} size="small">
          Save {totalHints > 0 ? `(${totalHints})` : ''}
        </Button>
      }
    >
      <Collapse
        defaultActiveKey={SECTIONS.map((s) => s.key)}
        ghost
        expandIconPosition="end"
        className="!bg-transparent"
        items={SECTIONS.map((section) => {
          const tags = data[section.key];
          const inputVal = inputs[section.key];
          const presets = PRESETS[section.key].filter((p) => !tags.includes(p));

          return {
            key: section.key,
            label: (
              <div className="flex items-center gap-2">
                <span style={{ color: section.iconColor }} className="text-sm">{section.icon}</span>
                <span className="font-semibold text-sm text-gray-900">{section.title}</span>
                {tags.length > 0 && (
                  <span
                    className="text-[10px] font-semibold text-white px-1.5 py-0.5 rounded-full leading-none"
                    style={{ backgroundColor: section.iconColor }}
                  >
                    {tags.length}
                  </span>
                )}
              </div>
            ),
            children: (
              <div className={`${section.bgCls} border ${section.borderCls} rounded-lg p-4`}>
                <p className="text-xs text-gray-500 mb-3">{section.description}</p>

                {/* Current tags */}
                {tags.length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-3">
                    {tags.map((tag) => (
                      <span
                        key={tag}
                        className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium ${section.tagCls}`}
                      >
                        {tag}
                        <button
                          onClick={() => removeTag(section.key, tag)}
                          className="text-current opacity-60 hover:opacity-100 ml-0.5"
                        >
                          &times;
                        </button>
                      </span>
                    ))}
                  </div>
                )}

                {/* Input */}
                <div className="flex gap-2 mb-3">
                  <Input
                    value={inputVal}
                    onChange={(e) => setInputs((prev) => ({ ...prev, [section.key]: e.target.value }))}
                    placeholder={`Add ${section.title.toLowerCase()}...`}
                    size="small"
                    onPressEnter={() => addTag(section.key)}
                    className="flex-1 !rounded-md"
                  />
                  <Button
                    size="small"
                    icon={<PlusOutlined />}
                    onClick={() => addTag(section.key)}
                    className="!rounded-md"
                  />
                </div>

                {/* Preset suggestions */}
                {presets.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {presets.map((preset) => (
                      <button
                        key={preset}
                        onClick={() => addPreset(section.key, preset)}
                        className="px-2.5 py-1 rounded-full text-[11px] bg-white/80 border border-dashed border-gray-300 text-gray-500 hover:border-brand hover:text-brand transition-colors cursor-pointer"
                      >
                        + {preset}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ),
          };
        })}
      />
    </Drawer>
  );
};

export default SignalHintsDrawer;
