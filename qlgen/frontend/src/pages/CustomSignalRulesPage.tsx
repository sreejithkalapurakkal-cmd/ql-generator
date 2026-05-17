import React, { useEffect, useState, useCallback } from 'react';
import { Button, Modal, Input, Select, Switch, Spin, Popconfirm, Tooltip, message } from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, ThunderboltOutlined,
  ClockCircleOutlined, CheckCircleFilled,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { PillTabs, Badge, EmptyState } from '../components/ui';
import {
  getSignalRules, createSignalRule, updateSignalRule, deleteSignalRule,
  toggleSignalRule, type CustomSignalRule, type CreateRuleData,
} from '../api/signalRulesApi';
import { SIGNAL_TYPE_LABELS } from '../types';

const RULE_TYPE_LABELS: Record<string, string> = {
  keyword: 'Keyword Match',
  pattern: 'Regex Pattern',
  composite: 'Multi-Signal Composite',
};

const RULE_TYPE_DESCRIPTIONS: Record<string, string> = {
  keyword: 'Fires when specified keywords appear in signal search results',
  pattern: 'Fires when a regex pattern matches signal text',
  composite: 'Fires when multiple signal types co-occur within a time window',
};

const PRIORITY_OPTIONS = [
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
];

const CustomSignalRulesPage: React.FC = () => {
  const navigate = useNavigate();
  const [rules, setRules] = useState<CustomSignalRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<CustomSignalRule | null>(null);

  // Form state
  const [formName, setFormName] = useState('');
  const [formDesc, setFormDesc] = useState('');
  const [formType, setFormType] = useState<'keyword' | 'pattern' | 'composite'>('keyword');
  const [formKeywords, setFormKeywords] = useState('');
  const [formMatchAny, setFormMatchAny] = useState(true);
  const [formPattern, setFormPattern] = useState('');
  const [formConditions, setFormConditions] = useState<{ signal_type: string; min_count: number; within_days: number }[]>([
    { signal_type: 'funding', min_count: 1, within_days: 90 },
  ]);
  const [formSignalTypeOutput, setFormSignalTypeOutput] = useState('custom_signal');
  const [formPriority, setFormPriority] = useState('medium');
  const [saving, setSaving] = useState(false);

  const fetchRules = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getSignalRules();
      setRules(res.data.rules || []);
    } catch {
      setRules([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchRules(); }, [fetchRules]);

  const resetForm = () => {
    setFormName('');
    setFormDesc('');
    setFormType('keyword');
    setFormKeywords('');
    setFormMatchAny(true);
    setFormPattern('');
    setFormConditions([{ signal_type: 'funding', min_count: 1, within_days: 90 }]);
    setFormSignalTypeOutput('custom_signal');
    setFormPriority('medium');
    setEditingRule(null);
  };

  const openCreate = () => {
    resetForm();
    setModalOpen(true);
  };

  const openEdit = (rule: CustomSignalRule) => {
    setEditingRule(rule);
    setFormName(rule.name);
    setFormDesc(rule.description || '');
    setFormType(rule.rule_type);
    setFormSignalTypeOutput(rule.signal_type_output);
    setFormPriority(rule.priority_output);

    const config = rule.rule_config || {};
    if (rule.rule_type === 'keyword') {
      setFormKeywords((config.keywords as string[] || []).join(', '));
      setFormMatchAny(config.match_any !== false);
    } else if (rule.rule_type === 'pattern') {
      setFormPattern((config.pattern as string) || '');
    } else if (rule.rule_type === 'composite') {
      setFormConditions((config.conditions as typeof formConditions) || []);
    }
    setModalOpen(true);
  };

  const handleSave = async () => {
    if (!formName.trim()) {
      message.error('Rule name is required');
      return;
    }

    let rule_config: Record<string, unknown> = {};
    if (formType === 'keyword') {
      const kws = formKeywords.split(',').map((k) => k.trim()).filter(Boolean);
      if (kws.length === 0) {
        message.error('At least one keyword is required');
        return;
      }
      rule_config = { keywords: kws, match_any: formMatchAny };
    } else if (formType === 'pattern') {
      if (!formPattern.trim()) {
        message.error('Pattern is required');
        return;
      }
      rule_config = { pattern: formPattern };
    } else if (formType === 'composite') {
      if (formConditions.length === 0) {
        message.error('At least one condition is required');
        return;
      }
      rule_config = { conditions: formConditions, operator: 'all' };
    }

    setSaving(true);
    try {
      if (editingRule) {
        await updateSignalRule(editingRule.id, {
          name: formName,
          description: formDesc || undefined,
          rule_config,
          signal_type_output: formSignalTypeOutput,
          priority_output: formPriority,
        });
        message.success('Rule updated');
      } else {
        await createSignalRule({
          name: formName,
          description: formDesc || undefined,
          rule_type: formType,
          rule_config,
          signal_type_output: formSignalTypeOutput,
          priority_output: formPriority,
        });
        message.success('Rule created');
      }
      setModalOpen(false);
      resetForm();
      fetchRules();
    } catch {
      message.error('Failed to save rule');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (ruleId: string) => {
    try {
      await deleteSignalRule(ruleId);
      setRules((prev) => prev.filter((r) => r.id !== ruleId));
      message.success('Rule deleted');
    } catch {
      message.error('Failed to delete');
    }
  };

  const handleToggle = async (ruleId: string) => {
    try {
      const res = await toggleSignalRule(ruleId);
      setRules((prev) => prev.map((r) => r.id === ruleId ? res.data : r));
    } catch {
      message.error('Failed to toggle rule');
    }
  };

  const addCondition = () => {
    setFormConditions((prev) => [...prev, { signal_type: 'hiring_surge', min_count: 1, within_days: 90 }]);
  };

  const removeCondition = (idx: number) => {
    setFormConditions((prev) => prev.filter((_, i) => i !== idx));
  };

  const updateCondition = (idx: number, field: string, value: string | number) => {
    setFormConditions((prev) => prev.map((c, i) => i === idx ? { ...c, [field]: value } : c));
  };

  const signalTypeOptions = Object.entries(SIGNAL_TYPE_LABELS).map(([k, v]) => ({ value: k, label: v }));

  return (
    <div className="px-10 py-8 max-w-[1200px] mx-auto">
      {/* Secondary nav */}
      <PillTabs
        tabs={[
          { key: 'lists', label: 'My Lists' },
          { key: 'feed', label: 'Signal Feed' },
          { key: 'rules', label: 'Signal Rules' },
        ]}
        activeKey="rules"
        onChange={(v) => {
          if (v === 'lists') navigate('/tracking');
          if (v === 'feed') navigate('/signals');
        }}
        className="mb-6"
      />

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Custom Signal Rules</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Define patterns to automatically detect custom signals during monitoring
          </p>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          New Rule
        </Button>
      </div>

      {/* Rules list */}
      {loading ? (
        <div className="flex justify-center py-20"><Spin size="large" /></div>
      ) : rules.length === 0 ? (
        <div className="bg-white border border-gray-200 rounded-lg">
          <EmptyState
            icon={<ThunderboltOutlined />}
            title="No custom rules yet"
            description="Create rules to define custom signal patterns — keyword matches, regex patterns, or multi-signal composites."
            className="py-16"
          />
        </div>
      ) : (
        <div className="space-y-3">
          {rules.map((rule) => (
            <div
              key={rule.id}
              className={`bg-white border rounded-lg px-5 py-4 transition-colors ${
                rule.is_active ? 'border-gray-200' : 'border-gray-100 opacity-60'
              }`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1.5">
                    <h3 className="text-sm font-semibold text-gray-900">{rule.name}</h3>
                    <span className="text-[10px] font-bold uppercase bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">
                      {RULE_TYPE_LABELS[rule.rule_type] || rule.rule_type}
                    </span>
                    <Badge variant="priority" priority={rule.priority_output} className="text-[10px]">
                      {rule.priority_output}
                    </Badge>
                    {!rule.is_active && (
                      <span className="text-[10px] font-bold text-gray-400 bg-gray-50 px-2 py-0.5 rounded-full">
                        INACTIVE
                      </span>
                    )}
                  </div>

                  {rule.description && (
                    <p className="text-xs text-gray-500 mb-2">{rule.description}</p>
                  )}

                  {/* Rule config summary */}
                  <div className="flex items-center gap-3 text-[11px] text-gray-400">
                    {rule.rule_type === 'keyword' && (
                      <span>
                        Keywords: {((rule.rule_config?.keywords as string[]) || []).slice(0, 5).join(', ')}
                        {((rule.rule_config?.keywords as string[]) || []).length > 5 && '...'}
                      </span>
                    )}
                    {rule.rule_type === 'pattern' && (
                      <span className="font-mono">/{(rule.rule_config?.pattern as string) || ''}/</span>
                    )}
                    {rule.rule_type === 'composite' && (
                      <span>
                        {((rule.rule_config?.conditions as { signal_type: string }[]) || [])
                          .map((c) => SIGNAL_TYPE_LABELS[c.signal_type] || c.signal_type)
                          .join(' + ')}
                      </span>
                    )}
                    <span className="text-gray-300">|</span>
                    <span>Output: {SIGNAL_TYPE_LABELS[rule.signal_type_output] || rule.signal_type_output}</span>
                    {rule.trigger_count > 0 && (
                      <>
                        <span className="text-gray-300">|</span>
                        <span className="flex items-center gap-0.5">
                          <CheckCircleFilled className="text-green-500 text-[10px]" />
                          Triggered {rule.trigger_count}x
                        </span>
                      </>
                    )}
                    {rule.last_triggered_at && (
                      <>
                        <span className="text-gray-300">|</span>
                        <span className="flex items-center gap-0.5">
                          <ClockCircleOutlined className="text-[10px]" />
                          Last: {new Date(rule.last_triggered_at).toLocaleDateString()}
                        </span>
                      </>
                    )}
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2 shrink-0">
                  <Tooltip title={rule.is_active ? 'Deactivate' : 'Activate'}>
                    <Switch
                      size="small"
                      checked={rule.is_active}
                      onChange={() => handleToggle(rule.id)}
                    />
                  </Tooltip>
                  <Tooltip title="Edit">
                    <button
                      onClick={() => openEdit(rule)}
                      className="w-7 h-7 flex items-center justify-center rounded-md text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
                    >
                      <EditOutlined className="text-xs" />
                    </button>
                  </Tooltip>
                  <Popconfirm
                    title="Delete this rule?"
                    onConfirm={() => handleDelete(rule.id)}
                    okText="Delete"
                    okButtonProps={{ danger: true }}
                  >
                    <Tooltip title="Delete">
                      <button className="w-7 h-7 flex items-center justify-center rounded-md text-gray-400 hover:bg-red-50 hover:text-red-500 transition-colors">
                        <DeleteOutlined className="text-xs" />
                      </button>
                    </Tooltip>
                  </Popconfirm>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create/Edit Modal */}
      <Modal
        title={editingRule ? 'Edit Signal Rule' : 'Create Signal Rule'}
        open={modalOpen}
        onCancel={() => { setModalOpen(false); resetForm(); }}
        onOk={handleSave}
        confirmLoading={saving}
        okText={editingRule ? 'Save Changes' : 'Create Rule'}
        width={580}
      >
        <div className="space-y-4 mt-4">
          <div>
            <label className="block text-xs font-semibold text-gray-500 mb-1">Rule Name</label>
            <Input value={formName} onChange={(e) => setFormName(e.target.value)} placeholder="e.g. Cloud Migration Keywords" />
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-500 mb-1">Description (optional)</label>
            <Input.TextArea value={formDesc} onChange={(e) => setFormDesc(e.target.value)} rows={2} placeholder="What does this rule detect?" />
          </div>

          {!editingRule && (
            <div>
              <label className="block text-xs font-semibold text-gray-500 mb-1">Rule Type</label>
              <Select value={formType} onChange={setFormType} style={{ width: '100%' }}>
                <Select.Option value="keyword">Keyword Match — {RULE_TYPE_DESCRIPTIONS.keyword}</Select.Option>
                <Select.Option value="pattern">Regex Pattern — {RULE_TYPE_DESCRIPTIONS.pattern}</Select.Option>
                <Select.Option value="composite">Multi-Signal Composite — {RULE_TYPE_DESCRIPTIONS.composite}</Select.Option>
              </Select>
            </div>
          )}

          {/* Keyword config */}
          {formType === 'keyword' && (
            <div className="space-y-3 p-3 bg-gray-50 rounded-lg">
              <div>
                <label className="block text-xs font-semibold text-gray-500 mb-1">Keywords (comma-separated)</label>
                <Input.TextArea value={formKeywords} onChange={(e) => setFormKeywords(e.target.value)} rows={2} placeholder="cloud migration, data platform, infrastructure" />
              </div>
              <div className="flex items-center gap-2">
                <Switch size="small" checked={formMatchAny} onChange={setFormMatchAny} />
                <span className="text-xs text-gray-600">{formMatchAny ? 'Match ANY keyword' : 'Match ALL keywords'}</span>
              </div>
            </div>
          )}

          {/* Pattern config */}
          {formType === 'pattern' && (
            <div className="p-3 bg-gray-50 rounded-lg">
              <label className="block text-xs font-semibold text-gray-500 mb-1">Regex Pattern</label>
              <Input value={formPattern} onChange={(e) => setFormPattern(e.target.value)} placeholder="raised?\s*\$\d+[MBmb]" className="font-mono" />
              <p className="text-[11px] text-gray-400 mt-1">Case-insensitive regex applied to signal titles and summaries</p>
            </div>
          )}

          {/* Composite config */}
          {formType === 'composite' && (
            <div className="p-3 bg-gray-50 rounded-lg space-y-2">
              <label className="block text-xs font-semibold text-gray-500 mb-1">Conditions (ALL must match)</label>
              {formConditions.map((cond, idx) => (
                <div key={idx} className="flex items-center gap-2 bg-white p-2 rounded-md border border-gray-200">
                  <Select value={cond.signal_type} onChange={(v) => updateCondition(idx, 'signal_type', v)} style={{ width: 160 }} size="small" options={signalTypeOptions} />
                  <span className="text-xs text-gray-400">min</span>
                  <Input type="number" value={cond.min_count} onChange={(e) => updateCondition(idx, 'min_count', parseInt(e.target.value) || 1)} style={{ width: 50 }} size="small" />
                  <span className="text-xs text-gray-400">within</span>
                  <Input type="number" value={cond.within_days} onChange={(e) => updateCondition(idx, 'within_days', parseInt(e.target.value) || 90)} style={{ width: 60 }} size="small" />
                  <span className="text-xs text-gray-400">days</span>
                  {formConditions.length > 1 && (
                    <button onClick={() => removeCondition(idx)} className="text-red-400 hover:text-red-500 text-xs ml-auto"><DeleteOutlined /></button>
                  )}
                </div>
              ))}
              <Button size="small" type="dashed" onClick={addCondition} icon={<PlusOutlined />} className="!text-xs">
                Add Condition
              </Button>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-gray-500 mb-1">Output Signal Type</label>
              <Select value={formSignalTypeOutput} onChange={setFormSignalTypeOutput} style={{ width: '100%' }} options={signalTypeOptions} />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-500 mb-1">Output Priority</label>
              <Select value={formPriority} onChange={setFormPriority} style={{ width: '100%' }} options={PRIORITY_OPTIONS} />
            </div>
          </div>
        </div>
      </Modal>
    </div>
  );
};

export default CustomSignalRulesPage;
