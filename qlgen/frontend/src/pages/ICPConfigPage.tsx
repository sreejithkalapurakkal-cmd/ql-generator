import React, { useState, useEffect } from 'react';
import { Card, Steps, Button, Form, Input, Select, InputNumber, Tag, Space, message, Descriptions, Divider, Slider } from 'antd';
import { useNavigate, useParams } from 'react-router-dom';
import { createICP, getICP, updateICP } from '../api/icpApi';
import { startPipeline } from '../api/pipelineApi';
import { ICPDefinition, DEFAULT_ICP } from '../types';

const { TextArea } = Input;

interface TagInputProps {
  label: string;
  field: string;
  values: string[];
  onChange: (vals: string[]) => void;
  placeholder?: string;
  tagInput: Record<string, string>;
  setTagInput: React.Dispatch<React.SetStateAction<Record<string, string>>>;
}

const TagInput: React.FC<TagInputProps> = ({ label, field, values, onChange, placeholder, tagInput, setTagInput }) => {
  const addTag = (value: string) => {
    if (value.trim() && !values.includes(value.trim())) {
      onChange([...values, value.trim()]);
      setTagInput((prev) => ({ ...prev, [field]: '' }));
    }
  };

  return (
    <Form.Item label={label}>
      <Space direction="vertical" style={{ width: '100%' }}>
        <Space wrap>
          {values.map((v) => (
            <Tag key={v} closable onClose={() => onChange(values.filter((t) => t !== v))} color="blue">
              {v}
            </Tag>
          ))}
        </Space>
        <Input
          placeholder={placeholder || `Add ${label.toLowerCase()} and press Enter`}
          value={tagInput[field] || ''}
          onChange={(e) => setTagInput((prev) => ({ ...prev, [field]: e.target.value }))}
          onPressEnter={() => addTag(tagInput[field] || '')}
          suffix={
            <Button size="small" type="link" onClick={() => addTag(tagInput[field] || '')}>
              Add
            </Button>
          }
        />
      </Space>
    </Form.Item>
  );
};

const ICPConfigPage: React.FC = () => {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const [current, setCurrent] = useState(0);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [config, setConfig] = useState<ICPDefinition>({ ...DEFAULT_ICP });
  const [saving, setSaving] = useState(false);
  const [tagInput, setTagInput] = useState<Record<string, string>>({});

  useEffect(() => {
    if (id) {
      getICP(id).then((res) => {
        setName(res.data.name);
        setDescription(res.data.description || '');
        setConfig(res.data.config as unknown as ICPDefinition);
      });
    }
  }, [id]);

  const steps = [
    {
      title: 'Offering',
      content: (
        <Form layout="vertical">
          <Form.Item label="ICP Name" required>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g., MidMarket US ECommerce 2026" />
          </Form.Item>
          <Form.Item label="Description">
            <TextArea rows={2} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Brief description of this ICP..." />
          </Form.Item>
          <TagInput
            label="Target Offerings / Service Areas"
            field="offerings"
            values={config.target_offering}
            onChange={(v) => setConfig({ ...config, target_offering: v })}
            placeholder="e.g., Platform engineering & replatforming"
            tagInput={tagInput}
            setTagInput={setTagInput}
          />
        </Form>
      ),
    },
    {
      title: 'Regions',
      content: (
        <Form layout="vertical">
          <TagInput
            label="Target Countries"
            field="countries"
            values={config.regions.countries}
            onChange={(v) => setConfig({ ...config, regions: { ...config.regions, countries: v } })}
            placeholder="e.g., United States"
            tagInput={tagInput}
            setTagInput={setTagInput}
          />
          <TagInput
            label="Priority Areas (States, Cities)"
            field="priority_areas"
            values={config.regions.priority_areas}
            onChange={(v) => setConfig({ ...config, regions: { ...config.regions, priority_areas: v } })}
            placeholder="e.g., California, New York"
            tagInput={tagInput}
            setTagInput={setTagInput}
          />
        </Form>
      ),
    },
    {
      title: 'Industry',
      content: (
        <Form layout="vertical">
          <Form.Item label="Industry Verticals">
            <Space direction="vertical" style={{ width: '100%' }}>
              {config.industry_types.map((ind, i) => (
                <Space key={i}>
                  <Input value={ind.vertical} onChange={(e) => {
                    const updated = [...config.industry_types];
                    updated[i] = { ...updated[i], vertical: e.target.value };
                    setConfig({ ...config, industry_types: updated });
                  }} placeholder="Vertical" style={{ width: 250 }} />
                  <Input value={ind.sub_vertical || ''} onChange={(e) => {
                    const updated = [...config.industry_types];
                    updated[i] = { ...updated[i], sub_vertical: e.target.value || null };
                    setConfig({ ...config, industry_types: updated });
                  }} placeholder="Sub-vertical (optional)" style={{ width: 250 }} />
                  <Button danger size="small" onClick={() => {
                    setConfig({ ...config, industry_types: config.industry_types.filter((_, j) => j !== i) });
                  }}>Remove</Button>
                </Space>
              ))}
              <Button type="dashed" onClick={() => setConfig({ ...config, industry_types: [...config.industry_types, { vertical: '', sub_vertical: null }] })}>
                + Add Industry
              </Button>
            </Space>
          </Form.Item>
        </Form>
      ),
    },
    {
      title: 'Size',
      content: (
        <Form layout="vertical">
          <Form.Item label="Employee Count Range">
            <Space>
              <InputNumber min={1} value={config.company_size.employees_min} onChange={(v) => setConfig({ ...config, company_size: { ...config.company_size, employees_min: v || 1 } })} addonBefore="Min" />
              <span>to</span>
              <InputNumber min={1} value={config.company_size.employees_max} onChange={(v) => setConfig({ ...config, company_size: { ...config.company_size, employees_max: v || 10000 } })} addonBefore="Max" />
            </Space>
          </Form.Item>
          <Form.Item label="Revenue Range">
            <Space>
              <Select value={config.company_size.revenue_currency} onChange={(v) => setConfig({ ...config, company_size: { ...config.company_size, revenue_currency: v } })} style={{ width: 80 }}>
                <Select.Option value="USD">USD</Select.Option>
                <Select.Option value="INR">INR</Select.Option>
                <Select.Option value="EUR">EUR</Select.Option>
                <Select.Option value="GBP">GBP</Select.Option>
              </Select>
              <InputNumber min={0} value={config.company_size.revenue_min} onChange={(v) => setConfig({ ...config, company_size: { ...config.company_size, revenue_min: v || 0 } })} formatter={(v) => `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')} addonBefore="Min" style={{ width: 200 }} />
              <span>to</span>
              <InputNumber min={0} value={config.company_size.revenue_max} onChange={(v) => setConfig({ ...config, company_size: { ...config.company_size, revenue_max: v || 0 } })} formatter={(v) => `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')} addonBefore="Max" style={{ width: 200 }} />
            </Space>
          </Form.Item>
        </Form>
      ),
    },
    {
      title: 'Tech',
      content: (
        <Form layout="vertical">
          <TagInput
            label="Technology Maturity Signals (Positive)"
            field="tech_signals"
            values={config.technology_maturity.signals}
            onChange={(v) => setConfig({ ...config, technology_maturity: { ...config.technology_maturity, signals: v } })}
            placeholder="e.g., Running on Shopify Plus"
            tagInput={tagInput}
            setTagInput={setTagInput}
          />
          <TagInput
            label="Negative Signals (Migration Needs)"
            field="tech_negative"
            values={config.technology_maturity.negative_signals}
            onChange={(v) => setConfig({ ...config, technology_maturity: { ...config.technology_maturity, negative_signals: v } })}
            placeholder="e.g., Legacy Magento 1 migration overdue"
            tagInput={tagInput}
            setTagInput={setTagInput}
          />
        </Form>
      ),
    },
    {
      title: 'Infra',
      content: (
        <Form layout="vertical">
          <TagInput
            label="Infrastructure Readiness Indicators"
            field="infra"
            values={config.infrastructure_readiness.indicators}
            onChange={(v) => setConfig({ ...config, infrastructure_readiness: { indicators: v } })}
            placeholder="e.g., Cloud-hosted storefront"
            tagInput={tagInput}
            setTagInput={setTagInput}
          />
        </Form>
      ),
    },
    {
      title: 'Drivers',
      content: (
        <Form layout="vertical">
          <TagInput
            label="Growth Triggers"
            field="growth"
            values={config.digital_transformation_drivers.growth_triggers}
            onChange={(v) => setConfig({ ...config, digital_transformation_drivers: { ...config.digital_transformation_drivers, growth_triggers: v } })}
            placeholder="e.g., YoY revenue growth >20%"
            tagInput={tagInput}
            setTagInput={setTagInput}
          />
          <TagInput
            label="Operational Pains"
            field="pains"
            values={config.digital_transformation_drivers.operational_pains}
            onChange={(v) => setConfig({ ...config, digital_transformation_drivers: { ...config.digital_transformation_drivers, operational_pains: v } })}
            placeholder="e.g., Site performance degrading during peak traffic"
            tagInput={tagInput}
            setTagInput={setTagInput}
          />
          <TagInput
            label="Competitive Pressures"
            field="pressures"
            values={config.digital_transformation_drivers.competitive_pressures}
            onChange={(v) => setConfig({ ...config, digital_transformation_drivers: { ...config.digital_transformation_drivers, competitive_pressures: v } })}
            placeholder="e.g., Rising CAC"
            tagInput={tagInput}
            setTagInput={setTagInput}
          />
          <TagInput
            label="Strategic Initiatives"
            field="initiatives"
            values={config.digital_transformation_drivers.strategic_initiatives}
            onChange={(v) => setConfig({ ...config, digital_transformation_drivers: { ...config.digital_transformation_drivers, strategic_initiatives: v } })}
            placeholder="e.g., Launching mobile app or PWA"
            tagInput={tagInput}
            setTagInput={setTagInput}
          />
        </Form>
      ),
    },
    {
      title: 'Leadership',
      content: (
        <Form layout="vertical">
          <TagInput
            label="Target Roles"
            field="roles"
            values={config.leadership_traits.target_roles}
            onChange={(v) => setConfig({ ...config, leadership_traits: { ...config.leadership_traits, target_roles: v } })}
            placeholder="e.g., CTO, VP of Engineering"
            tagInput={tagInput}
            setTagInput={setTagInput}
          />
          <TagInput
            label="Behavioral Traits"
            field="traits"
            values={config.leadership_traits.behavioral_traits}
            onChange={(v) => setConfig({ ...config, leadership_traits: { ...config.leadership_traits, behavioral_traits: v } })}
            placeholder="e.g., Data-driven decision maker"
            tagInput={tagInput}
            setTagInput={setTagInput}
          />
        </Form>
      ),
    },
    {
      title: 'Review',
      content: (
        <div>
          <Descriptions title="ICP Summary" bordered column={1} size="small">
            <Descriptions.Item label="Name">{name || '(unnamed)'}</Descriptions.Item>
            <Descriptions.Item label="Description">{description || '-'}</Descriptions.Item>
            <Descriptions.Item label="Target Offerings">{config.target_offering.join(', ') || '-'}</Descriptions.Item>
            <Descriptions.Item label="Regions">{config.regions.countries.join(', ')} | {config.regions.priority_areas.join(', ')}</Descriptions.Item>
            <Descriptions.Item label="Industries">{config.industry_types.map((i) => i.vertical).join(', ') || '-'}</Descriptions.Item>
            <Descriptions.Item label="Company Size">{config.company_size.employees_min}-{config.company_size.employees_max} employees, {config.company_size.revenue_currency} {config.company_size.revenue_min.toLocaleString()}-{config.company_size.revenue_max.toLocaleString()}</Descriptions.Item>
            <Descriptions.Item label="Tech Signals">{config.technology_maturity.signals.join(', ') || '-'}</Descriptions.Item>
            <Descriptions.Item label="Infrastructure">{config.infrastructure_readiness.indicators.join(', ') || '-'}</Descriptions.Item>
            <Descriptions.Item label="Target Roles">{config.leadership_traits.target_roles.join(', ') || '-'}</Descriptions.Item>
          </Descriptions>
        </div>
      ),
    },
  ];

  const handleSave = async (runPipeline: boolean) => {
    if (!name.trim()) {
      message.error('Please provide an ICP name');
      return;
    }
    setSaving(true);
    try {
      let icpId = id;
      if (id) {
        await updateICP(id, { name, description, config: config as unknown as Record<string, unknown> });
      } else {
        const res = await createICP({ name, description, config: config as unknown as Record<string, unknown> });
        icpId = res.data.id;
      }
      message.success('ICP saved successfully');

      if (runPipeline && icpId) {
        const runRes = await startPipeline({ icp_config_id: icpId, options: { max_companies: 15, max_contacts_per_company: 5 } });
        navigate(`/pipeline/${runRes.data.id}`);
      } else {
        navigate('/icp');
      }
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'Failed to save ICP');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card title={id ? 'Edit ICP Configuration' : 'New ICP Configuration'}>
      <Steps current={current} items={steps.map((s) => ({ title: s.title }))} style={{ marginBottom: 32 }} size="small" />
      <div style={{ minHeight: 300, padding: '16px 0' }}>{steps[current].content}</div>
      <Divider />
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <div>
          {current > 0 && <Button onClick={() => setCurrent((c) => c - 1)}>Previous</Button>}
        </div>
        <Space>
          {current < steps.length - 1 && (
            <Button type="primary" onClick={() => setCurrent((c) => c + 1)}>Next</Button>
          )}
          {current === steps.length - 1 && (
            <>
              <Button onClick={() => handleSave(false)} loading={saving}>Save Only</Button>
              <Button type="primary" onClick={() => handleSave(true)} loading={saving}>Save & Run Pipeline</Button>
            </>
          )}
        </Space>
      </div>
    </Card>
  );
};

export default ICPConfigPage;
