import React, { useState, useEffect, useCallback } from 'react';
<<<<<<< HEAD
import { Card, Steps, Button, Form, Input, Select, InputNumber, Tag, Space, message, Descriptions, Divider, Upload, Modal, Spin, Alert } from 'antd';
import { UploadOutlined, FileExcelOutlined, DownloadOutlined } from '@ant-design/icons';
=======
import { Card, Button, Form, Input, Select, InputNumber, Tag, Space, message, Descriptions } from 'antd';
>>>>>>> c5396d41 (feat: update ui styling)
import { useNavigate, useParams } from 'react-router-dom';
import { createICP, getICP, updateICP, getICPTemplateURL, parseICPUpload } from '../api/icpApi';
import { startPipeline } from '../api/pipelineApi';
import { ICPDefinition, DEFAULT_ICP } from '../types';

const { TextArea } = Input;

const TagInputField: React.FC<{
  label: string;
  field: string;
  values: string[];
  onChange: (vals: string[]) => void;
  placeholder?: string;
  tagInput: Record<string, string>;
  setTagInput: React.Dispatch<React.SetStateAction<Record<string, string>>>;
}> = ({ label, field, values, onChange, placeholder, tagInput, setTagInput }) => {
  const addTag = () => {
    const value = tagInput[field] || '';
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
          onPressEnter={addTag}
          suffix={
            <Button size="small" type="link" onClick={addTag}>
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
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [importParsing, setImportParsing] = useState(false);

  const handleImportUpload = async (file: File) => {
    setImportParsing(true);
    try {
      const res = await parseICPUpload(file);
      const parsed = Array.isArray(res.data) ? res.data : [];
      if (parsed.length > 0) {
        const icp = parsed[0];
        if (icp.name) setName(icp.name);
        if (icp.description) setDescription(icp.description);
        if (icp.config) setConfig(icp.config as unknown as ICPDefinition);
        message.success('Search criteria imported — review and edit below');
        setImportModalOpen(false);
      } else {
        message.error('No ICP data found in uploaded file');
      }
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'Failed to parse Excel file');
    } finally {
      setImportParsing(false);
    }
    return false;
  };

  useEffect(() => {
    if (id) {
      getICP(id).then((res) => {
        setName(res.data.name);
        setDescription(res.data.description || '');
        setConfig(res.data.config as unknown as ICPDefinition);
      });
    }
  }, [id]);

  const updateIndustry = useCallback((index: number, field: 'vertical' | 'sub_vertical', value: string) => {
    setConfig((prev) => {
      const updated = [...prev.industry_types];
      updated[index] = { ...updated[index], [field]: field === 'sub_vertical' ? (value || null) : value };
      return { ...prev, industry_types: updated };
    });
  }, []);

  const removeIndustry = useCallback((index: number) => {
    setConfig((prev) => ({
      ...prev,
      industry_types: prev.industry_types.filter((_, j) => j !== index),
    }));
  }, []);

  const addIndustry = useCallback(() => {
    setConfig((prev) => ({
      ...prev,
      industry_types: [...prev.industry_types, { vertical: '', sub_vertical: null }],
    }));
  }, []);

  const steps = [
    {
      title: 'Offering',
      content: (
        <Form layout="vertical">
          {!id && (
            <Alert
              type="info"
              showIcon
              icon={<FileExcelOutlined />}
              message="Have your search criteria in a spreadsheet?"
              description={
                <Space size="middle" style={{ marginTop: 4 }}>
                  <Button size="small" icon={<UploadOutlined />} onClick={() => setImportModalOpen(true)}>
                    Import from Excel
                  </Button>
                  <a href={getICPTemplateURL()} target="_blank" rel="noreferrer" style={{ fontSize: 12 }}>
                    <DownloadOutlined /> Download Template
                  </a>
                </Space>
              }
              style={{ marginBottom: 16 }}
            />
          )}
          <Form.Item label="Name" required>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g., MidMarket US ECommerce 2026" />
          </Form.Item>
          <Form.Item label="Description">
            <TextArea rows={2} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Brief description of this search criteria..." />
          </Form.Item>
          <TagInputField
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
          <TagInputField
            label="Target Countries"
            field="countries"
            values={config.regions.countries}
            onChange={(v) => setConfig({ ...config, regions: { ...config.regions, countries: v } })}
            placeholder="e.g., United States"
            tagInput={tagInput}
            setTagInput={setTagInput}
          />
          <TagInputField
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
                <Space key={i} wrap>
                  <Input value={ind.vertical} onChange={(e) => updateIndustry(i, 'vertical', e.target.value)} placeholder="Vertical" style={{ width: 250 }} />
                  <Input value={ind.sub_vertical || ''} onChange={(e) => updateIndustry(i, 'sub_vertical', e.target.value)} placeholder="Sub-vertical (optional)" style={{ width: 250 }} />
                  <Button danger size="small" onClick={() => removeIndustry(i)}>Remove</Button>
                </Space>
              ))}
              <Button type="dashed" onClick={addIndustry}>
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
            <Space wrap>
              <InputNumber min={1} value={config.company_size.employees_min} onChange={(v) => setConfig({ ...config, company_size: { ...config.company_size, employees_min: v || 1 } })} addonBefore="Min" />
              <span>to</span>
              <InputNumber min={1} value={config.company_size.employees_max} onChange={(v) => setConfig({ ...config, company_size: { ...config.company_size, employees_max: v || 10000 } })} addonBefore="Max" />
            </Space>
          </Form.Item>
          <Form.Item label="Revenue Range">
            <Space wrap>
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
          <TagInputField
            label="Technology Maturity Signals (Positive)"
            field="tech_signals"
            values={config.technology_maturity.signals}
            onChange={(v) => setConfig({ ...config, technology_maturity: { ...config.technology_maturity, signals: v } })}
            placeholder="e.g., Running on Shopify Plus"
            tagInput={tagInput}
            setTagInput={setTagInput}
          />
          <TagInputField
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
          <TagInputField
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
          <TagInputField
            label="Growth Triggers"
            field="growth"
            values={config.digital_transformation_drivers.growth_triggers}
            onChange={(v) => setConfig({ ...config, digital_transformation_drivers: { ...config.digital_transformation_drivers, growth_triggers: v } })}
            placeholder="e.g., YoY revenue growth >20%"
            tagInput={tagInput}
            setTagInput={setTagInput}
          />
          <TagInputField
            label="Operational Pains"
            field="pains"
            values={config.digital_transformation_drivers.operational_pains}
            onChange={(v) => setConfig({ ...config, digital_transformation_drivers: { ...config.digital_transformation_drivers, operational_pains: v } })}
            placeholder="e.g., Site performance degrading during peak traffic"
            tagInput={tagInput}
            setTagInput={setTagInput}
          />
          <TagInputField
            label="Competitive Pressures"
            field="pressures"
            values={config.digital_transformation_drivers.competitive_pressures}
            onChange={(v) => setConfig({ ...config, digital_transformation_drivers: { ...config.digital_transformation_drivers, competitive_pressures: v } })}
            placeholder="e.g., Rising CAC"
            tagInput={tagInput}
            setTagInput={setTagInput}
          />
          <TagInputField
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
          <TagInputField
            label="Target Roles"
            field="roles"
            values={config.leadership_traits.target_roles}
            onChange={(v) => setConfig({ ...config, leadership_traits: { ...config.leadership_traits, target_roles: v } })}
            placeholder="e.g., CTO, VP of Engineering"
            tagInput={tagInput}
            setTagInput={setTagInput}
          />
          <TagInputField
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
          <Descriptions title="Summary" bordered column={2} size="small">
            <Descriptions.Item label="Name" span={2}>{name || '(unnamed)'}</Descriptions.Item>
            <Descriptions.Item label="Description" span={2}>{description || '-'}</Descriptions.Item>
            <Descriptions.Item label="Target Offerings" span={2}>{config.target_offering.join(', ') || '-'}</Descriptions.Item>
            <Descriptions.Item label="Countries">{config.regions.countries.join(', ') || '-'}</Descriptions.Item>
            <Descriptions.Item label="Priority Areas">{config.regions.priority_areas.join(', ') || '-'}</Descriptions.Item>
            <Descriptions.Item label="Industries" span={2}>
              {config.industry_types.map((i) => `${i.vertical}${i.sub_vertical ? ` / ${i.sub_vertical}` : ''}`).join(', ') || '-'}
            </Descriptions.Item>
            <Descriptions.Item label="Employees">{config.company_size.employees_min.toLocaleString()}–{config.company_size.employees_max.toLocaleString()}</Descriptions.Item>
            <Descriptions.Item label="Revenue">{config.company_size.revenue_currency} {config.company_size.revenue_min.toLocaleString()}–{config.company_size.revenue_max.toLocaleString()}</Descriptions.Item>
            <Descriptions.Item label="Tech Signals (Positive)">{config.technology_maturity.signals.join(', ') || '-'}</Descriptions.Item>
            <Descriptions.Item label="Tech Signals (Negative)">{config.technology_maturity.negative_signals.join(', ') || '-'}</Descriptions.Item>
            <Descriptions.Item label="Infrastructure" span={2}>{config.infrastructure_readiness.indicators.join(', ') || '-'}</Descriptions.Item>
            <Descriptions.Item label="Growth Triggers">{config.digital_transformation_drivers.growth_triggers.join(', ') || '-'}</Descriptions.Item>
            <Descriptions.Item label="Operational Pains">{config.digital_transformation_drivers.operational_pains.join(', ') || '-'}</Descriptions.Item>
            <Descriptions.Item label="Competitive Pressures">{config.digital_transformation_drivers.competitive_pressures.join(', ') || '-'}</Descriptions.Item>
            <Descriptions.Item label="Strategic Initiatives">{config.digital_transformation_drivers.strategic_initiatives.join(', ') || '-'}</Descriptions.Item>
            <Descriptions.Item label="Target Roles">{config.leadership_traits.target_roles.join(', ') || '-'}</Descriptions.Item>
            <Descriptions.Item label="Behavioral Traits">{config.leadership_traits.behavioral_traits.join(', ') || '-'}</Descriptions.Item>
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
      message.success('Search criteria saved successfully');

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
<<<<<<< HEAD
    <Card title={id ? 'Edit Search Criteria' : 'New Search Criteria'}>
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
              <Button type="primary" onClick={() => handleSave(true)} loading={saving}>Save & Run Search</Button>
            </>
          )}
        </Space>
      </div>

      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <FileExcelOutlined style={{ color: 'var(--green)', fontSize: 18 }} />
            <span>Import Search Criteria from Excel</span>
          </div>
        }
        open={importModalOpen}
        onCancel={() => setImportModalOpen(false)}
        footer={null}
        width={480}
      >
        <p style={{ color: 'var(--g600)', fontSize: 13, margin: '0 0 16px' }}>
          Upload a filled template to pre-fill the wizard. You can review and edit all fields before saving.
        </p>
        <Upload.Dragger
          accept=".xlsx"
          showUploadList={false}
          customRequest={({ file }) => handleImportUpload(file as File)}
          disabled={importParsing}
        >
          {importParsing ? (
            <div style={{ padding: 20 }}>
              <Spin size="large" />
              <p style={{ marginTop: 12, color: 'var(--g500)' }}>Parsing...</p>
            </div>
          ) : (
            <div style={{ padding: 20 }}>
              <p className="ant-upload-drag-icon">
                <FileExcelOutlined style={{ fontSize: 36, color: 'var(--green)' }} />
              </p>
              <p style={{ fontSize: 13, fontWeight: 600, color: 'var(--g800)' }}>
                Click or drag your .xlsx file here
              </p>
            </div>
          )}
        </Upload.Dragger>
      </Modal>
    </Card>
=======
    <div style={{ padding: '28px 32px', maxWidth: 1400, margin: '0 auto', width: '100%' }}>
      <div style={{ marginBottom: 24 }}>
        <div className="section-label">ICP Configuration</div>
        <h1 className="page-title">{id ? 'Edit ICP Configuration' : 'New ICP Configuration'}</h1>
      </div>

      <div className="builder-layout">
        {/* Left Side Stepper */}
        <div className="builder-stepper">
          {steps.map((step, index) => (
            <div
              key={index}
              className={`builder-step ${index === current ? 'active' : index < current ? 'complete' : ''
                }`}
              onClick={() => setCurrent(index)}
            >
              <div className="builder-step-num">
                {index < current ? '✓' : index + 1}
              </div>
              <div className="builder-step-label">{step.title}</div>
            </div>
          ))}
        </div>

        {/* Right Side Form */}
        <div className="builder-form">
          <Card>
            <div style={{ minHeight: 300 }}>{steps[current].content}</div>
            <div className="builder-nav">
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
        </div>
      </div>
    </div>
>>>>>>> c5396d41 (feat: update ui styling)
  );
};

export default ICPConfigPage;
