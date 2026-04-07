import React, { useState, useEffect, useCallback } from 'react';
import { Card, Button, Form, Input, Select, InputNumber, Tag, Space, message, Descriptions, Upload, Modal, Spin, Alert, Switch, Radio } from 'antd';
import { UploadOutlined, FileExcelOutlined, DownloadOutlined, RobotOutlined, LinkedinOutlined, CheckCircleOutlined, CloseCircleOutlined, WarningOutlined } from '@ant-design/icons';
import { useNavigate, useParams, useLocation } from 'react-router-dom';
import { createICP, getICP, updateICP, getICPTemplateURL, parseICPUpload, generateICPWithAI, generateICPFromFile } from '../api/icpApi';
import { startPipeline } from '../api/pipelineApi';
import { getEvabootStatus, EvabootStatus } from '../api/toolsApi';
import { ICPDefinition, DEFAULT_ICP } from '../types';
import { parseSalesNavUrl, generateNameFromExtraction, SalesNavExtraction } from '../utils/salesNavParser';

const { TextArea } = Input;

const TagInputField: React.FC<{
  label: string;
  field: string;
  values: string[];
  onChange: (vals: string[]) => void;
  placeholder?: string;
  tagInput: Record<string, string>;
  setTagInput: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  tagColor?: string;
}> = ({ label, field, values, onChange, placeholder, tagInput, setTagInput, tagColor = 'blue' }) => {
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
            <Tag key={v} closable onClose={() => onChange(values.filter((t) => t !== v))} color={tagColor}>
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
  const location = useLocation();
  const { id } = useParams<{ id: string }>();
  const [current, setCurrent] = useState(0);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [config, setConfig] = useState<ICPDefinition>({ ...DEFAULT_ICP });
  const [saving, setSaving] = useState(false);
  const [tagInput, setTagInput] = useState<Record<string, string>>({});
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [importParsing, setImportParsing] = useState(false);
  const [aiModalOpen, setAiModalOpen] = useState(false);
  const [aiDescription, setAiDescription] = useState('');
  const [aiFile, setAiFile] = useState<File | null>(null);
  const [aiGenerating, setAiGenerating] = useState(false);
  const [discoveryMode, setDiscoveryMode] = useState<'qlgen_only' | 'sales_navigator_only' | 'sales_navigator_plus_qlgen'>('qlgen_only');
  const [salesNavUrl, setSalesNavUrl] = useState('');
  const [evabootStatus, setEvabootStatus] = useState<EvabootStatus | null>(null);
  const [salesNavExtraction, setSalesNavExtraction] = useState<SalesNavExtraction | null>(null);
  const [autoFillApplied, setAutoFillApplied] = useState<string>('');

  const isSalesNav = discoveryMode !== 'qlgen_only';

  // Debounced auto-parse of Sales Nav URL
  useEffect(() => {
    if (!isSalesNav || !salesNavUrl.trim()) {
      setSalesNavExtraction(null);
      setAutoFillApplied('');
      return;
    }

    const timer = setTimeout(() => {
      const extraction = parseSalesNavUrl(salesNavUrl.trim());
      setSalesNavExtraction(extraction);

      // Auto-fill ICP fields if parseable and not already applied for this URL
      if (extraction.isParseable && !extraction.isSavedList && autoFillApplied !== salesNavUrl.trim()) {
        const partial = extraction.icpPartial;

        setConfig((prev) => {
          const next = { ...prev };

          if (partial.firmographic_details) {
            const pf = partial.firmographic_details;
            next.firmographic_details = {
              ...prev.firmographic_details,
              industry_types: pf.industry_types.length > 0 ? pf.industry_types : prev.firmographic_details.industry_types,
              geography: {
                countries: pf.geography.countries.length > 0 ? pf.geography.countries : prev.firmographic_details.geography.countries,
              },
              employee_range: (pf.employee_range.min !== 50 || pf.employee_range.max !== 1500) ? pf.employee_range : prev.firmographic_details.employee_range,
              revenue_range: (pf.revenue_range.min !== 10000000 || pf.revenue_range.max !== 500000000) ? pf.revenue_range : prev.firmographic_details.revenue_range,
              low_cost_center: prev.firmographic_details.low_cost_center,
            };
          }

          if (partial.target_capability && partial.target_capability.offerings.length > 0) {
            next.target_capability = {
              ...prev.target_capability,
              offerings: [...new Set([...prev.target_capability.offerings, ...partial.target_capability.offerings])],
            };
          }

          if (partial.authority_roles && partial.authority_roles.target_roles.length > 0) {
            next.authority_roles = {
              ...prev.authority_roles,
              target_roles: [...new Set([...prev.authority_roles.target_roles, ...partial.authority_roles.target_roles])],
            };
          }

          return next;
        });

        // Auto-generate name if empty
        if (!name.trim() || name === 'Sales Nav Search') {
          const autoName = generateNameFromExtraction(extraction.icpPartial);
          setName(autoName);
        }

        setAutoFillApplied(salesNavUrl.trim());
        message.success(`Extracted ${extraction.filters.length} filter(s) from Sales Navigator URL`);
      }
    }, 500);

    return () => clearTimeout(timer);
  }, [salesNavUrl, isSalesNav]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    getEvabootStatus()
      .then((res) => setEvabootStatus(res.data))
      .catch(() => setEvabootStatus(null));
  }, []);

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
        setCurrent(6); // Jump to Review step
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

  const handleAIGenerate = async () => {
    setAiGenerating(true);
    try {
      const res = aiFile
        ? await generateICPFromFile(aiFile, aiDescription)
        : await generateICPWithAI({ description: aiDescription });
      const { name: aiName, description: aiDesc, config: aiConfig } = res.data;

      if (isSalesNav && salesNavExtraction?.isParseable && !salesNavExtraction.isSavedList) {
        // Merge mode: only fill fields that are empty / at default values
        const generated = aiConfig as unknown as ICPDefinition;
        if (aiName && !name.trim()) setName(aiName);
        if (aiDesc && !description.trim()) setDescription(aiDesc);
        if (generated) {
          setConfig((prev) => {
            const next = { ...prev };
            // Don't overwrite URL-extracted firmographics — only fill if still at defaults
            const prevFirm = prev.firmographic_details;
            next.firmographic_details = {
              ...prevFirm,
              industry_types: prevFirm.industry_types.length > 0 ? prevFirm.industry_types : generated.firmographic_details.industry_types,
              geography: {
                countries: prevFirm.geography.countries.length > 0 ? prevFirm.geography.countries : generated.firmographic_details.geography.countries,
              },
              employee_range: (autoFillApplied && (prevFirm.employee_range.min !== 50 || prevFirm.employee_range.max !== 1500))
                ? prevFirm.employee_range
                : generated.firmographic_details.employee_range,
              revenue_range: (autoFillApplied && (prevFirm.revenue_range.min !== 10000000 || prevFirm.revenue_range.max !== 500000000))
                ? prevFirm.revenue_range
                : generated.firmographic_details.revenue_range,
              low_cost_center: prevFirm.low_cost_center,
            };
            // Fill empty scoring fields
            if (prev.target_capability.offerings.length === 0 && generated.target_capability.offerings.length > 0) {
              next.target_capability = generated.target_capability;
            }
            if (prev.urgency_signals.signals.length === 0 && generated.urgency_signals.signals.length > 0) {
              next.urgency_signals = generated.urgency_signals;
            }
            if (prev.budget_signals.signals.length === 0 && generated.budget_signals.signals.length > 0) {
              next.budget_signals = generated.budget_signals;
            }
            if (prev.authority_roles.target_roles.length === 0 && generated.authority_roles.target_roles.length > 0) {
              next.authority_roles = generated.authority_roles;
            }
            return next;
          });
        }
        message.success('AI filled remaining fields — review and edit below');
      } else {
        // Replace mode: existing behavior for qlGen
        if (aiName) setName(aiName);
        if (aiDesc) setDescription(aiDesc);
        if (aiConfig) setConfig(aiConfig as unknown as ICPDefinition);
        message.success('Search criteria generated — review and edit below');
      }

      setAiModalOpen(false);
      setAiDescription('');
      setAiFile(null);
      setCurrent(6); // Jump to Review step
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'Failed to generate search criteria with AI');
    } finally {
      setAiGenerating(false);
    }
  };

  useEffect(() => {
    if (id) {
      getICP(id).then((res) => {
        setName(res.data.name);
        setDescription(res.data.description || '');
        const rawConfig = res.data.config as unknown as Record<string, unknown>;
        // Restore discovery source settings from config JSONB
        if (rawConfig.discovery_mode) {
          setDiscoveryMode(rawConfig.discovery_mode as typeof discoveryMode);
        }
        if (rawConfig.sales_navigator_url) {
          setSalesNavUrl(rawConfig.sales_navigator_url as string);
        }
        setConfig(rawConfig as unknown as ICPDefinition);
      });
    } else {
      const cloneFrom = (location.state as any)?.cloneFrom;
      if (cloneFrom) {
        setName(`Copy of ${cloneFrom.name}`);
        setDescription(cloneFrom.description || '');
        const rawClone = cloneFrom.config as Record<string, unknown>;
        if (rawClone.discovery_mode) {
          setDiscoveryMode(rawClone.discovery_mode as typeof discoveryMode);
        }
        if (rawClone.sales_navigator_url) {
          setSalesNavUrl(rawClone.sales_navigator_url as string);
        }
        setConfig(rawClone as unknown as ICPDefinition);
        setCurrent(6); // Jump to Review step
      }
    }
  }, [id, location.state]);

  const updateIndustry = useCallback((index: number, field: 'vertical' | 'sub_vertical', value: string) => {
    setConfig((prev) => {
      const updated = [...prev.firmographic_details.industry_types];
      updated[index] = { ...updated[index], [field]: field === 'sub_vertical' ? (value || null) : value };
      return {
        ...prev,
        firmographic_details: { ...prev.firmographic_details, industry_types: updated },
      };
    });
  }, []);

  const removeIndustry = useCallback((index: number) => {
    setConfig((prev) => ({
      ...prev,
      firmographic_details: {
        ...prev.firmographic_details,
        industry_types: prev.firmographic_details.industry_types.filter((_, j) => j !== index),
      },
    }));
  }, []);

  const addIndustry = useCallback(() => {
    setConfig((prev) => ({
      ...prev,
      firmographic_details: {
        ...prev.firmographic_details,
        industry_types: [...prev.firmographic_details.industry_types, { vertical: '', sub_vertical: null }],
      },
    }));
  }, []);

  const steps = [
    {
      title: 'Discovery Source',
      content: (
        <Form layout="vertical">
          <div style={{ marginBottom: 20 }}>
            <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--g800)', marginBottom: 4 }}>How should companies be discovered?</div>
            <div style={{ fontSize: 13, color: 'var(--g500)', lineHeight: 1.6 }}>
              This controls <strong>Stage 1 (Industry Discovery)</strong> and <strong>Stage 2 (Firmographic Fit)</strong>. Stages 3–5 (Signals, Contacts, Scoring) run the same regardless.
            </div>
          </div>

          <Form.Item>
            <Radio.Group
              value={discoveryMode}
              onChange={(e) => setDiscoveryMode(e.target.value)}
              style={{ display: 'flex', flexDirection: 'column', gap: 12 }}
            >
              <Radio value="qlgen_only" style={{ padding: '14px 16px', border: '1px solid var(--g200)', borderRadius: 10, margin: 0, background: discoveryMode === 'qlgen_only' ? 'var(--purple-pale, #f9f0ff)' : '#fff' }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 14 }}>qlGen Multi-Source</div>
                  <div style={{ fontSize: 12, color: 'var(--g500)', marginTop: 2 }}>Apollo, Exa, DuckDuckGo, registries, and more. No extra credits needed.</div>
                </div>
              </Radio>
              <Radio value="sales_navigator_only" style={{ padding: '14px 16px', border: '1px solid var(--g200)', borderRadius: 10, margin: 0, background: discoveryMode === 'sales_navigator_only' ? 'var(--purple-pale, #f9f0ff)' : '#fff' }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 14 }}><LinkedinOutlined style={{ marginRight: 6, color: '#0a66c2' }} />LinkedIn Sales Navigator Only</div>
                  <div style={{ fontSize: 12, color: 'var(--g500)', marginTop: 2 }}>Extract companies & contacts from your Sales Navigator search via Evaboot (1 credit/profile).</div>
                </div>
              </Radio>
              <Radio value="sales_navigator_plus_qlgen" style={{ padding: '14px 16px', border: '1px solid var(--g200)', borderRadius: 10, margin: 0, background: discoveryMode === 'sales_navigator_plus_qlgen' ? 'var(--purple-pale, #f9f0ff)' : '#fff' }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 14 }}><LinkedinOutlined style={{ marginRight: 6, color: '#0a66c2' }} />Sales Navigator + qlGen (Hybrid)</div>
                  <div style={{ fontSize: 12, color: 'var(--g500)', marginTop: 2 }}>LinkedIn data combined with multi-source discovery for maximum coverage. Uses Evaboot credits.</div>
                </div>
              </Radio>
            </Radio.Group>
          </Form.Item>

          {isSalesNav && (
            <>
              {/* Live Credit Balance & Session Status */}
              {evabootStatus?.configured && !evabootStatus.quota?.error && (
                <div style={{
                  background: 'linear-gradient(135deg, #f0f7ff 0%, #f5f0ff 100%)',
                  borderRadius: 10,
                  padding: '16px 20px',
                  marginBottom: 16,
                  border: '1px solid var(--g200)',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                    <LinkedinOutlined style={{ color: '#0a66c2', fontSize: 16 }} />
                    <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--g700)' }}>Evaboot Account Status</span>
                  </div>
                  <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                    {/* Credits */}
                    <div style={{ background: '#fff', borderRadius: 8, padding: '10px 16px', border: '1px solid var(--g150, #eee)', flex: '1 1 120px' }}>
                      <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--g400)', textTransform: 'uppercase', letterSpacing: 0.5 }}>Credits Available</div>
                      <div style={{ fontSize: 22, fontWeight: 800, color: (evabootStatus.quota?.credits ?? 0) < 100 ? '#ff4d4f' : 'var(--purple, #722ed1)', marginTop: 2 }}>
                        {evabootStatus.quota?.credits != null ? Math.floor(evabootStatus.quota.credits).toLocaleString() : '—'}
                      </div>
                    </div>
                    {/* Daily */}
                    <div style={{ background: '#fff', borderRadius: 8, padding: '10px 16px', border: '1px solid var(--g150, #eee)', flex: '1 1 120px' }}>
                      <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--g400)', textTransform: 'uppercase', letterSpacing: 0.5 }}>Daily Usage</div>
                      <div style={{ fontSize: 22, fontWeight: 800, color: 'var(--g800)', marginTop: 2 }}>
                        {evabootStatus.quota?.used_today ?? 0}<span style={{ fontSize: 13, fontWeight: 500, color: 'var(--g400)' }}> / {evabootStatus.quota?.daily_limit ?? '—'}</span>
                      </div>
                    </div>
                    {/* Session */}
                    <div style={{ background: '#fff', borderRadius: 8, padding: '10px 16px', border: '1px solid var(--g150, #eee)', flex: '1 1 140px' }}>
                      <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--g400)', textTransform: 'uppercase', letterSpacing: 0.5 }}>Sales Nav Session</div>
                      {evabootStatus.sales_nav_sessions.length > 0 ? (
                        evabootStatus.sales_nav_sessions.map((sn, i) => (
                          <div key={sn.id || i} style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 4 }}>
                            {sn.status === 'valid' ? (
                              <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 16 }} />
                            ) : (
                              <CloseCircleOutlined style={{ color: '#ff4d4f', fontSize: 16 }} />
                            )}
                            <span style={{ fontSize: 13, fontWeight: 700, color: sn.status === 'valid' ? '#52c41a' : '#ff4d4f' }}>
                              {sn.status === 'valid' ? 'Connected' : 'Disconnected'}
                            </span>
                          </div>
                        ))
                      ) : (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 4 }}>
                          <WarningOutlined style={{ color: '#faad14', fontSize: 16 }} />
                          <span style={{ fontSize: 13, fontWeight: 700, color: '#faad14' }}>No Account</span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Error state */}
              {evabootStatus?.configured && evabootStatus.quota?.error && (
                <Alert
                  type="error"
                  showIcon
                  message="Evaboot Connection Error"
                  description={evabootStatus.quota.error}
                  style={{ marginBottom: 16 }}
                />
              )}

              {/* Not configured */}
              {evabootStatus && !evabootStatus.configured && (
                <Alert
                  type="error"
                  showIcon
                  message="Evaboot Not Configured"
                  description="No Evaboot API key is set. Ask your admin to add EVABOOT_API_KEY to the environment configuration."
                  style={{ marginBottom: 16 }}
                />
              )}

              {/* Session disconnected warning */}
              {evabootStatus?.sales_nav_sessions.some(sn => sn.status !== 'valid') && (
                <Alert
                  type="error"
                  showIcon
                  message="Sales Navigator Session Expired"
                  description="Your Sales Navigator cookie has expired. Re-link your account in the Evaboot dashboard before running a search."
                  style={{ marginBottom: 16 }}
                />
              )}

              <Form.Item
                label="Sales Navigator URL"
                required
                help="Paste a Sales Navigator search or saved list URL. Narrow your search in Sales Navigator first to control credit usage."
              >
                <Input
                  prefix={<LinkedinOutlined style={{ color: '#0a66c2' }} />}
                  placeholder="https://www.linkedin.com/sales/search/..."
                  value={salesNavUrl}
                  onChange={(e) => setSalesNavUrl(e.target.value)}
                  size="large"
                />
              </Form.Item>

              {/* Extraction feedback */}
              {salesNavExtraction && salesNavExtraction.isParseable && !salesNavExtraction.isSavedList && salesNavExtraction.filters.length > 0 && (
                <div style={{
                  background: '#f6ffed',
                  border: '1px solid #b7eb8f',
                  borderRadius: 8,
                  padding: '14px 18px',
                  marginBottom: 12,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
                    <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 15 }} />
                    <span style={{ fontWeight: 700, fontSize: 13, color: '#389e0d' }}>Filters extracted from URL</span>
                  </div>
                  <Space wrap style={{ marginBottom: 8 }}>
                    {salesNavExtraction.filters.map((f) => (
                      <Tag key={f.type} color="green">{f.type}: {f.values.join(', ')}</Tag>
                    ))}
                    {salesNavExtraction.keywords.length > 0 && (
                      <Tag color="green">KEYWORDS: {salesNavExtraction.keywords.join(', ')}</Tag>
                    )}
                  </Space>
                  {salesNavExtraction.missingFields.length > 0 && (
                    <div style={{ fontSize: 12, color: 'var(--g500)', marginTop: 6 }}>
                      <span style={{ fontWeight: 600 }}>Not in URL:</span>{' '}
                      {salesNavExtraction.missingFields.join(', ')}
                    </div>
                  )}
                  <Button
                    size="small"
                    icon={<RobotOutlined />}
                    onClick={() => {
                      setAiDescription(
                        `Sales Navigator search with: ${salesNavExtraction.summary}. Please fill in the missing fields: ${salesNavExtraction.missingFields.join(', ')}.`
                      );
                      setAiModalOpen(true);
                    }}
                    style={{ marginTop: 10 }}
                  >
                    Fill remaining with AI
                  </Button>
                </div>
              )}

              {salesNavExtraction && salesNavExtraction.isSavedList && (
                <Alert
                  type="warning"
                  showIcon
                  message="Saved list URL detected"
                  description={
                    <span>
                      Saved list URLs don't contain filter parameters to extract. Use{' '}
                      <Button size="small" type="link" style={{ padding: 0 }} icon={<RobotOutlined />} onClick={() => setAiModalOpen(true)}>
                        AI to generate criteria
                      </Button>{' '}
                      or fill in the fields manually.
                    </span>
                  }
                  style={{ marginBottom: 12 }}
                />
              )}

              {/* Credit pricing breakdown */}
              <div style={{
                background: '#fffbe6',
                border: '1px solid #ffe58f',
                borderRadius: 8,
                padding: '12px 16px',
                marginTop: 8,
              }}>
                <div style={{ fontWeight: 700, fontSize: 13, color: '#ad6800', marginBottom: 6 }}>
                  <WarningOutlined style={{ marginRight: 6 }} />Credit Usage Policy
                </div>
                <div style={{ fontSize: 12, color: '#874d00', lineHeight: 1.8 }}>
                  <div><strong>1 credit</strong> per profile extracted from your Sales Navigator search</div>
                  <div><strong>1 credit</strong> per email found for each contact</div>
                  <div><strong>0.5 credit</strong> per email validation</div>
                  <div style={{ marginTop: 6, paddingTop: 6, borderTop: '1px solid #ffe58f', fontWeight: 600 }}>
                    A search returning 100 profiles with email enrichment = ~200 credits. Narrow your Sales Navigator search first to control costs.
                  </div>
                </div>
              </div>

              <Alert
                type="info"
                showIcon
                message="ICP criteria still needed for scoring"
                description="Your Sales Navigator URL handles company discovery. The ICP criteria in the next steps will be used by the AI agent to score firmographic fit, evaluate signals, and find the right contacts."
                style={{ marginTop: 12 }}
              />
            </>
          )}
        </Form>
      ),
    },
    {
      title: 'Firmographics',
      content: (
        <Form layout="vertical">
          {isSalesNav && (
            <Alert
              type="info"
              showIcon
              icon={<LinkedinOutlined />}
              message="Sales Navigator handles discovery — these criteria are used for scoring"
              description="Since you're using a Sales Navigator URL, companies are already filtered there. The firmographic criteria below will be used by the AI agent in Stage 2 to score each company's fit. You can leave defaults or refine them."
              style={{ marginBottom: 16 }}
            />
          )}
          {!id && (
            <Alert
              type="info"
              showIcon
              icon={<RobotOutlined />}
              message={isSalesNav ? 'Fill remaining fields with AI' : 'Build your search criteria faster!'}
              description={
                <Space size="middle" style={{ marginTop: 4 }}>
                  <Button
                    size="small"
                    icon={<RobotOutlined />}
                    onClick={() => {
                      if (isSalesNav && salesNavExtraction?.summary) {
                        setAiDescription(
                          `Sales Navigator search with: ${salesNavExtraction.summary}. Please fill in the missing fields: ${salesNavExtraction.missingFields.join(', ')}.`
                        );
                      }
                      setAiModalOpen(true);
                    }}
                  >
                    {isSalesNav ? 'Fill remaining with AI' : 'Create with AI / Upload'}
                  </Button>
                  <span style={{ fontSize: 12, color: 'var(--g500)' }}>
                    {isSalesNav
                      ? 'Use AI to fill urgency signals, budget signals, offerings, and other fields not in your Sales Navigator URL'
                      : 'Describe your ideal customer and fill in all the fields using AI, or upload your own criteria from a spreadsheet'}
                  </span>
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

          {/* Industry Verticals */}
          <Form.Item label="Industry Verticals">
            <Space direction="vertical" style={{ width: '100%' }}>
              {config.firmographic_details.industry_types.map((ind, i) => (
                <Space key={i} wrap>
                  <Input
                    value={ind.vertical}
                    onChange={(e) => updateIndustry(i, 'vertical', e.target.value)}
                    placeholder="Vertical (e.g., E-Commerce)"
                    style={{ width: 250 }}
                  />
                  <Input
                    value={ind.sub_vertical || ''}
                    onChange={(e) => updateIndustry(i, 'sub_vertical', e.target.value)}
                    placeholder="Sub-vertical (optional)"
                    style={{ width: 250 }}
                  />
                  <Button danger size="small" onClick={() => removeIndustry(i)}>Remove</Button>
                </Space>
              ))}
              <Button type="dashed" onClick={addIndustry}>
                + Add Industry
              </Button>
            </Space>
          </Form.Item>

          {/* Geography */}
          <TagInputField
            label="Target Countries"
            field="countries"
            values={config.firmographic_details.geography.countries}
            onChange={(v) =>
              setConfig((prev) => ({
                ...prev,
                firmographic_details: {
                  ...prev.firmographic_details,
                  geography: { ...prev.firmographic_details.geography, countries: v },
                },
              }))
            }
            placeholder="e.g., United States"
            tagInput={tagInput}
            setTagInput={setTagInput}
          />

          {/* Employee Range */}
          <Form.Item label="Employee Count Range">
            <Space wrap>
              <InputNumber
                min={1}
                value={config.firmographic_details.employee_range.min}
                onChange={(v) =>
                  setConfig((prev) => ({
                    ...prev,
                    firmographic_details: {
                      ...prev.firmographic_details,
                      employee_range: { ...prev.firmographic_details.employee_range, min: v || 1 },
                    },
                  }))
                }
                addonBefore="Min"
              />
              <span>to</span>
              <InputNumber
                min={1}
                value={config.firmographic_details.employee_range.max}
                onChange={(v) =>
                  setConfig((prev) => ({
                    ...prev,
                    firmographic_details: {
                      ...prev.firmographic_details,
                      employee_range: { ...prev.firmographic_details.employee_range, max: v || 10000 },
                    },
                  }))
                }
                addonBefore="Max"
              />
            </Space>
          </Form.Item>

          {/* Revenue Range */}
          <Form.Item label="Revenue Range">
            <Space wrap>
              <Select
                value={config.firmographic_details.revenue_range.currency}
                onChange={(v) =>
                  setConfig((prev) => ({
                    ...prev,
                    firmographic_details: {
                      ...prev.firmographic_details,
                      revenue_range: { ...prev.firmographic_details.revenue_range, currency: v },
                    },
                  }))
                }
                style={{ width: 80 }}
              >
                <Select.Option value="USD">USD</Select.Option>
                <Select.Option value="INR">INR</Select.Option>
                <Select.Option value="EUR">EUR</Select.Option>
                <Select.Option value="GBP">GBP</Select.Option>
              </Select>
              <InputNumber
                min={0}
                value={config.firmographic_details.revenue_range.min}
                onChange={(v) =>
                  setConfig((prev) => ({
                    ...prev,
                    firmographic_details: {
                      ...prev.firmographic_details,
                      revenue_range: { ...prev.firmographic_details.revenue_range, min: v || 0 },
                    },
                  }))
                }
                formatter={(v) => `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
                addonBefore="Min"
                style={{ width: 200 }}
              />
              <span>to</span>
              <InputNumber
                min={0}
                value={config.firmographic_details.revenue_range.max}
                onChange={(v) =>
                  setConfig((prev) => ({
                    ...prev,
                    firmographic_details: {
                      ...prev.firmographic_details,
                      revenue_range: { ...prev.firmographic_details.revenue_range, max: v || 0 },
                    },
                  }))
                }
                formatter={(v) => `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
                addonBefore="Max"
                style={{ width: 200 }}
              />
            </Space>
          </Form.Item>

          {/* Low Cost Center Toggle */}
          <Form.Item label="Low Cost Center">
            <Switch
              checked={config.firmographic_details.low_cost_center}
              onChange={(checked) =>
                setConfig((prev) => ({
                  ...prev,
                  firmographic_details: { ...prev.firmographic_details, low_cost_center: checked },
                }))
              }
            />
            <span style={{ marginLeft: 8, fontSize: 12, color: 'var(--g500)' }}>
              Target companies with low-cost center operations
            </span>
          </Form.Item>

        </Form>
      ),
    },
    {
      title: 'Capability',
      content: (
        <Form layout="vertical">
          <TagInputField
            label="Target Offerings / Service Areas"
            field="offerings"
            values={config.target_capability.offerings}
            onChange={(v) =>
              setConfig((prev) => ({
                ...prev,
                target_capability: { ...prev.target_capability, offerings: v },
              }))
            }
            placeholder="e.g., Platform engineering & replatforming"
            tagInput={tagInput}
            setTagInput={setTagInput}
          />
          <Form.Item label="Match Condition">
            <div style={{ display: 'flex', gap: 12 }}>
              {(['AND', 'OR'] as const).map((opt) => (
                <div
                  key={opt}
                  onClick={() =>
                    setConfig((prev) => ({
                      ...prev,
                      target_capability: { ...prev.target_capability, condition: opt },
                    }))
                  }
                  style={{
                    flex: 1,
                    padding: '12px 16px',
                    borderRadius: 8,
                    border:
                      config.target_capability.condition === opt
                        ? '2px solid var(--purple, #722ed1)'
                        : '1px solid var(--g200, #e0e0e0)',
                    background:
                      config.target_capability.condition === opt
                        ? 'var(--purple-pale, #f9f0ff)'
                        : '#fff',
                    cursor: 'pointer',
                    transition: 'all 0.15s',
                    textAlign: 'center',
                  }}
                >
                  <div
                    style={{
                      fontWeight: 600,
                      fontSize: 14,
                      color:
                        config.target_capability.condition === opt
                          ? 'var(--purple, #722ed1)'
                          : 'var(--g800)',
                    }}
                  >
                    {opt}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--g500)', marginTop: 2 }}>
                    {opt === 'AND'
                      ? 'Company must match ALL offerings'
                      : 'Company must match ANY offering'}
                  </div>
                </div>
              ))}
            </div>
          </Form.Item>
        </Form>
      ),
    },
    {
      title: 'Urgency',
      content: (
        <Form layout="vertical">
          <TagInputField
            label="Urgency Signals"
            field="urgency"
            values={config.urgency_signals.signals}
            onChange={(v) =>
              setConfig((prev) => ({
                ...prev,
                urgency_signals: { ...prev.urgency_signals, signals: v },
              }))
            }
            placeholder="e.g., Recent funding round, Leadership change, Regulatory deadline"
            tagInput={tagInput}
            setTagInput={setTagInput}
            tagColor="orange"
          />
          <div style={{ fontSize: 12, color: 'var(--g500)', marginTop: -8, marginBottom: 16 }}>
            Add signals that indicate a company has an urgent need. These are free-form — type your own signals based on your domain expertise.
          </div>
          <Form.Item label="Match Condition">
            <div style={{ display: 'flex', gap: 12 }}>
              {(['AND', 'OR'] as const).map((opt) => (
                <div
                  key={opt}
                  onClick={() =>
                    setConfig((prev) => ({
                      ...prev,
                      urgency_signals: { ...prev.urgency_signals, condition: opt },
                    }))
                  }
                  style={{
                    flex: 1, padding: '12px 16px', borderRadius: 8, cursor: 'pointer', transition: 'all 0.15s', textAlign: 'center',
                    border: config.urgency_signals.condition === opt ? '2px solid var(--purple, #722ed1)' : '1px solid var(--g200, #e0e0e0)',
                    background: config.urgency_signals.condition === opt ? 'var(--purple-pale, #f9f0ff)' : '#fff',
                  }}
                >
                  <div style={{ fontWeight: 600, fontSize: 14, color: config.urgency_signals.condition === opt ? 'var(--purple, #722ed1)' : 'var(--g800)' }}>
                    {opt}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--g500)', marginTop: 2 }}>
                    {opt === 'AND' ? 'Company must show ALL signals' : 'Company must show ANY signal'}
                  </div>
                </div>
              ))}
            </div>
          </Form.Item>
        </Form>
      ),
    },
    {
      title: 'Budget',
      content: (
        <Form layout="vertical">
          <TagInputField
            label="Budget Signals"
            field="budget"
            values={config.budget_signals.signals}
            onChange={(v) =>
              setConfig((prev) => ({
                ...prev,
                budget_signals: { ...prev.budget_signals, signals: v },
              }))
            }
            placeholder="e.g., Recent fundraise >$10M, IT budget expansion, New CTO hire"
            tagInput={tagInput}
            setTagInput={setTagInput}
            tagColor="green"
          />
          <div style={{ fontSize: 12, color: 'var(--g500)', marginTop: -8, marginBottom: 16 }}>
            Add signals that indicate a company has budget availability. These are free-form — type your own signals based on your domain expertise.
          </div>
          <Form.Item label="Match Condition">
            <div style={{ display: 'flex', gap: 12 }}>
              {(['AND', 'OR'] as const).map((opt) => (
                <div
                  key={opt}
                  onClick={() =>
                    setConfig((prev) => ({
                      ...prev,
                      budget_signals: { ...prev.budget_signals, condition: opt },
                    }))
                  }
                  style={{
                    flex: 1, padding: '12px 16px', borderRadius: 8, cursor: 'pointer', transition: 'all 0.15s', textAlign: 'center',
                    border: config.budget_signals.condition === opt ? '2px solid var(--purple, #722ed1)' : '1px solid var(--g200, #e0e0e0)',
                    background: config.budget_signals.condition === opt ? 'var(--purple-pale, #f9f0ff)' : '#fff',
                  }}
                >
                  <div style={{ fontWeight: 600, fontSize: 14, color: config.budget_signals.condition === opt ? 'var(--purple, #722ed1)' : 'var(--g800)' }}>
                    {opt}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--g500)', marginTop: 2 }}>
                    {opt === 'AND' ? 'Company must show ALL signals' : 'Company must show ANY signal'}
                  </div>
                </div>
              ))}
            </div>
          </Form.Item>
        </Form>
      ),
    },
    {
      title: 'Authority',
      content: (
        <Form layout="vertical">
          <TagInputField
            label="Target Roles"
            field="roles"
            values={config.authority_roles.target_roles}
            onChange={(v) =>
              setConfig((prev) => ({
                ...prev,
                authority_roles: { ...prev.authority_roles, target_roles: v },
              }))
            }
            placeholder="e.g., CTO, VP of Engineering, Head of Platform"
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
            <Descriptions.Item label="Industries" span={2}>
              {config.firmographic_details.industry_types
                .map((i) => `${i.vertical}${i.sub_vertical ? ` / ${i.sub_vertical}` : ''}`)
                .join(', ') || '-'}
            </Descriptions.Item>
            <Descriptions.Item label="Countries">
              {config.firmographic_details.geography.countries.join(', ') || '-'}
            </Descriptions.Item>
            <Descriptions.Item label="Employees">
              {config.firmographic_details.employee_range.min.toLocaleString()}
              &ndash;
              {config.firmographic_details.employee_range.max.toLocaleString()}
            </Descriptions.Item>
            <Descriptions.Item label="Revenue">
              {config.firmographic_details.revenue_range.currency}{' '}
              {config.firmographic_details.revenue_range.min.toLocaleString()}
              &ndash;
              {config.firmographic_details.revenue_range.max.toLocaleString()}
            </Descriptions.Item>
            <Descriptions.Item label="Low Cost Center">
              {config.firmographic_details.low_cost_center ? 'Yes' : 'No'}
            </Descriptions.Item>
            <Descriptions.Item label="Target Offerings" span={2}>
              {config.target_capability.offerings.join(', ') || '-'}
              {config.target_capability.offerings.length > 1 && (
                <Tag color="purple" style={{ marginLeft: 8 }}>{config.target_capability.condition}</Tag>
              )}
            </Descriptions.Item>
            <Descriptions.Item label="Urgency Signals" span={2}>
              {config.urgency_signals.signals.join(', ') || '-'}
              {config.urgency_signals.signals.length > 1 && (
                <Tag color="orange" style={{ marginLeft: 8 }}>{config.urgency_signals.condition}</Tag>
              )}
            </Descriptions.Item>
            <Descriptions.Item label="Budget Signals" span={2}>
              {config.budget_signals.signals.join(', ') || '-'}
              {config.budget_signals.signals.length > 1 && (
                <Tag color="green" style={{ marginLeft: 8 }}>{config.budget_signals.condition}</Tag>
              )}
            </Descriptions.Item>
            <Descriptions.Item label="Target Roles" span={2}>
              {config.authority_roles.target_roles.join(', ') || '-'}
            </Descriptions.Item>
            <Descriptions.Item label="Discovery Source" span={2}>
              {discoveryMode === 'qlgen_only' && 'qlGen Multi-Source'}
              {discoveryMode === 'sales_navigator_only' && 'Sales Navigator Only (Evaboot)'}
              {discoveryMode === 'sales_navigator_plus_qlgen' && 'Sales Navigator + qlGen (Hybrid)'}
              {discoveryMode !== 'qlgen_only' && salesNavUrl && (
                <div style={{ fontSize: 12, color: 'var(--g500)', marginTop: 4, wordBreak: 'break-all' }}>
                  URL: {salesNavUrl}
                </div>
              )}
            </Descriptions.Item>
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
      // Persist discovery source settings inside the config JSONB
      const configToSave: Record<string, unknown> = {
        ...(config as unknown as Record<string, unknown>),
        discovery_mode: discoveryMode,
        ...(isSalesNav && salesNavUrl.trim() ? { sales_navigator_url: salesNavUrl.trim() } : {}),
      };

      let icpId = id;
      if (id) {
        await updateICP(id, { name, description, config: configToSave });
      } else {
        const res = await createICP({ name, description, config: configToSave });
        icpId = res.data.id;
      }
      message.success('Search criteria saved successfully');

      if (runPipeline && icpId) {
        const pipelinePayload: Parameters<typeof startPipeline>[0] = {
          icp_config_id: icpId,
          discovery_mode: discoveryMode,
        };
        if (discoveryMode !== 'qlgen_only' && salesNavUrl.trim()) {
          pipelinePayload.sales_navigator_url = salesNavUrl.trim();
        }
        const runRes = await startPipeline(pipelinePayload);
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
    <div style={{ padding: '28px 32px', maxWidth: 1400, margin: '0 auto', width: '100%' }}>
      <div style={{ marginBottom: 24, paddingLeft: 258 }}>
        <div className="section-label">Search Criteria Configuration</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Button size="small" onClick={() => navigate(-1)} style={{ fontSize: 12 }}>
            &larr; Back
          </Button>
          <h1 className="page-title">{id ? 'Edit Search Criteria' : 'New Search Criteria'}</h1>
        </div>
      </div>

      <div className="builder-layout">
        {/* Left Side Stepper */}
        <div className="builder-stepper">
          {steps.map((step, index) => (
            <div
              key={index}
              className={`builder-step ${index === current ? 'active' : index < current ? 'complete' : ''}`}
              onClick={() => setCurrent(index)}
            >
              <div className="builder-step-num">
                {index < current ? '\u2713' : index + 1}
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
                    <Button type="primary" onClick={() => handleSave(true)} loading={saving}>Run Pipeline</Button>
                  </>
                )}
              </Space>
            </div>
          </Card>
        </div>
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

      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <RobotOutlined style={{ color: 'var(--purple, #722ed1)', fontSize: 18 }} />
            <span>Create Search Criteria with AI</span>
          </div>
        }
        open={aiModalOpen}
        onCancel={() => { if (!aiGenerating) { setAiModalOpen(false); setAiFile(null); setAiDescription(''); } }}
        maskClosable={!aiGenerating}
        footer={
          <Space>
            <Button onClick={() => { setAiModalOpen(false); setAiFile(null); setAiDescription(''); }} disabled={aiGenerating}>Cancel</Button>
            <Button
              type="primary"
              onClick={handleAIGenerate}
              loading={aiGenerating}
              disabled={!aiDescription.trim() && !aiFile}
            >
              Generate
            </Button>
          </Space>
        }
        width={600}
      >
        <p style={{ color: 'var(--g600)', fontSize: 13, margin: '0 0 12px' }}>
          Upload a sales deck, product brief, or any document describing your offering — or type a description below.
        </p>
        <Upload.Dragger
          accept=".pdf,.docx,.xlsx,.txt,.csv"
          showUploadList={false}
          beforeUpload={(file) => {
            setAiFile(file);
            return false;
          }}
          disabled={aiGenerating}
          style={{ marginBottom: 12 }}
        >
          {aiFile ? (
            <div style={{ padding: 12 }}>
              <p style={{ fontSize: 13, fontWeight: 600, color: 'var(--g800)', margin: 0 }}>
                {aiFile.name}
              </p>
              <p style={{ fontSize: 11, color: 'var(--g400)', margin: '4px 0 0' }}>
                {(aiFile.size / 1024).toFixed(0)} KB — Click or drag to replace
              </p>
            </div>
          ) : (
            <div style={{ padding: 12 }}>
              <p className="ant-upload-drag-icon">
                <UploadOutlined style={{ fontSize: 28, color: 'var(--purple, #722ed1)' }} />
              </p>
              <p style={{ fontSize: 13, fontWeight: 600, color: 'var(--g800)', margin: 0 }}>
                Upload PDF, DOCX, XLSX, TXT, or CSV
              </p>
              <p style={{ fontSize: 11, color: 'var(--g400)', margin: '4px 0 0' }}>Max 10 MB</p>
            </div>
          )}
        </Upload.Dragger>
        <div style={{ textAlign: 'center', color: 'var(--g400)', fontSize: 12, margin: '8px 0' }}>
          — or describe in your own words —
        </div>
        <TextArea
          rows={4}
          value={aiDescription}
          onChange={(e) => setAiDescription(e.target.value)}
          placeholder="Example: We sell cloud migration services to mid-market US ecommerce companies with 200-2000 employees running legacy platforms like Magento 1 or Shopify Basic. We target CTOs and VPs of Engineering who are experiencing site performance issues during peak traffic."
          disabled={aiGenerating}
        />
      </Modal>
    </div>
  );
};

export default ICPConfigPage;
