import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Button, Steps, Upload, Input, Select, Table, Tag, Progress, message,
  Card, Alert, Space, Segmented, Spin, Switch, InputNumber,
} from 'antd';
import {
  FileExcelOutlined,
  CheckCircleOutlined, LoadingOutlined, FilterOutlined,
  PlusOutlined, DeleteOutlined, CloseOutlined,
} from '@ant-design/icons';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  uploadFile, pasteText, confirmIngest, getIngestStreamUrl, listBatches, dismissBatch,
  type UploadResponse, type PasteResponse, type IngestBatchSummary,
} from '../api/ingestApi';
import { getTrackingLists } from '../api/trackingApi';
import { listICPs } from '../api/icpApi';
import {
  TrackingList, ICPConfig,
  FirmographicFilter, DEFAULT_FIRMOGRAPHIC_FILTER,
} from '../types';

type InputMode = 'upload' | 'paste';
type Step = 'input' | 'mapping' | 'filter' | 'processing' | 'done';

const TARGET_FIELDS = [
  { value: 'company_name', label: 'Company Name' },
  { value: 'domain', label: 'Domain / Website' },
  { value: 'industry', label: 'Industry' },
  { value: 'country', label: 'Country' },
  { value: 'city', label: 'City' },
  { value: 'employee_count', label: 'Employee Count' },
  { value: 'revenue', label: 'Revenue' },
  { value: 'contact_name', label: 'Contact Name' },
  { value: 'contact_email', label: 'Contact Email' },
  { value: 'contact_title', label: 'Contact Title' },
  { value: 'linkedin_url', label: 'LinkedIn URL' },
  { value: '', label: '(Skip this column)' },
];

const IngestPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const targetListIdParam = searchParams.get('targetListId');

  const [step, setStep] = useState<Step>('input');
  const [inputMode, setInputMode] = useState<InputMode>('upload');

  // Input state
  const [pasteValue, setPasteValue] = useState('');
  const [batchName, setBatchName] = useState('');

  // Upload response
  const [batchId, setBatchId] = useState<string | null>(null);
  const [headers, setHeaders] = useState<string[]>([]);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [previewRows, setPreviewRows] = useState<Record<string, string>[]>([]);
  const [totalRows, setTotalRows] = useState(0);

  // Tracking list selection
  const [trackingLists, setTrackingLists] = useState<TrackingList[]>([]);
  const [targetListId, setTargetListId] = useState<string>(targetListIdParam || '');

  // Processing state (non-filter flow only)
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [progressData, setProgressData] = useState<{
    processed: number; total: number; matched_kb: number;
    newly_created: number; errors: number;
  } | null>(null);
  const [completedData, setCompletedData] = useState<{
    processed: number; matched_kb: number; newly_created: number;
    errors: number; company_kb_ids: string[];
  } | null>(null);

  // Filter state
  const [filterEnabled, setFilterEnabled] = useState(false);
  const [filterConfig, setFilterConfig] = useState<FirmographicFilter>({ ...DEFAULT_FIRMOGRAPHIC_FILTER });
  const [icpList, setIcpList] = useState<ICPConfig[]>([]);
  const [countryInput, setCountryInput] = useState('');

  // Recent batches with firmographic filter
  const [recentBatches, setRecentBatches] = useState<IngestBatchSummary[]>([]);

  // Fetch tracking lists, ICPs, and recent batches
  useEffect(() => {
    getTrackingLists()
      .then((res) => setTrackingLists(res.data.lists || []))
      .catch(() => {});
    listICPs()
      .then((res) => setIcpList(res.data || []))
      .catch(() => {});
    listBatches(undefined, true, 5)
      .then((res) => setRecentBatches(res.data.filter((b) => b.has_filter)))
      .catch(() => {});
  }, []);

  // Dynamic steps — filter step is always available
  const stepsItems = useMemo(() => {
    return [
      { title: 'Input' },
      { title: 'Map Columns' },
      { title: 'Filter' },
      { title: 'Processing' },
      { title: 'Done' },
    ];
  }, []);

  const stepIndex = useMemo(() => {
    const order: Step[] = ['input', 'mapping', 'filter', 'processing', 'done'];
    return order.indexOf(step);
  }, [step]);

  // Filter helpers
  const handleLoadFromICP = useCallback((icpId: string) => {
    const icp = icpList.find((i) => i.id === icpId);
    if (!icp) return;
    const fd = (icp.config as unknown as Record<string, unknown>)?.firmographic_details as Record<string, unknown> | undefined;
    if (fd) {
      setFilterConfig({
        industry_types: (fd.industry_types as FirmographicFilter['industry_types']) || [],
        countries: ((fd.geography as Record<string, unknown>)?.countries as string[]) || [],
        employee_range: (fd.employee_range as FirmographicFilter['employee_range']) || { min: 50, max: 5000 },
        revenue_range: (fd.revenue_range as FirmographicFilter['revenue_range']) || { min: 1000000, max: 500000000, currency: 'USD' },
      });
      setFilterEnabled(true);
      message.success('Criteria loaded from ICP');
    }
  }, [icpList]);

  const addIndustry = () => {
    setFilterConfig((prev) => ({
      ...prev,
      industry_types: [...prev.industry_types, { vertical: '', sub_vertical: null }],
    }));
  };

  const removeIndustry = (index: number) => {
    setFilterConfig((prev) => ({
      ...prev,
      industry_types: prev.industry_types.filter((_, i) => i !== index),
    }));
  };

  const updateIndustry = (index: number, field: 'vertical' | 'sub_vertical', value: string) => {
    setFilterConfig((prev) => {
      const updated = [...prev.industry_types];
      updated[index] = { ...updated[index], [field]: field === 'sub_vertical' ? (value || null) : value };
      return { ...prev, industry_types: updated };
    });
  };

  const addCountry = () => {
    const val = countryInput.trim();
    if (val && !filterConfig.countries.includes(val)) {
      setFilterConfig((prev) => ({ ...prev, countries: [...prev.countries, val] }));
      setCountryInput('');
    }
  };

  // Upload / Paste handlers
  const handleUpload = async (file: File) => {
    try {
      const res = await uploadFile(file, batchName || undefined, targetListId || undefined);
      handleUploadResponse(res.data);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      message.error(e?.response?.data?.detail || 'Upload failed');
    }
    return false;
  };

  const handlePaste = async () => {
    if (!pasteValue.trim()) { message.warning('Paste some company names or domains'); return; }
    try {
      const res = await pasteText(pasteValue, batchName || undefined, targetListId || undefined);
      handleUploadResponse(res.data);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      message.error(e?.response?.data?.detail || 'Parse failed');
    }
  };

  const handleUploadResponse = (data: UploadResponse | PasteResponse) => {
    setBatchId(data.batch_id);
    setHeaders(data.headers);
    setMapping(data.column_mapping);
    setPreviewRows(data.preview_rows);
    setTotalRows(data.total_rows);
    setStep('mapping');
  };

  const handleMappingChange = (sourceCol: string, targetField: string) => {
    setMapping((prev) => {
      const next = { ...prev };
      if (targetField) {
        next[sourceCol] = targetField;
      } else {
        delete next[sourceCol];
      }
      return next;
    });
  };

  const handleMappingNext = () => {
    const mappedFields = Object.values(mapping);
    if (!mappedFields.includes('company_name') && !mappedFields.includes('domain')) {
      message.warning('Map at least "Company Name" or "Domain" column');
      return;
    }
    setStep('filter');
  };

  // Confirm and start processing
  const handleConfirm = async () => {
    if (!batchId) return;

    const mappedFields = Object.values(mapping);
    if (!mappedFields.includes('company_name') && !mappedFields.includes('domain')) {
      message.warning('Map at least "Company Name" or "Domain" column');
      return;
    }

    const activeFilter = filterEnabled ? filterConfig : undefined;

    try {
      await confirmIngest(batchId, mapping, targetListId || undefined, activeFilter);

      if (filterEnabled) {
        // Navigate to the evaluation page — async monitoring with activity feed
        navigate(`/ingest/${batchId}`);
        return;
      }

      // Non-filter flow: stay on page with SSE progress
      setStep('processing');
      setProcessing(true);

      const url = getIngestStreamUrl(batchId);
      const es = new EventSource(url);

      es.addEventListener('ingest_progress', (e) => {
        const data = JSON.parse(e.data);
        setProgress(data.percent || 0);
        setProgressData(data);
      });

      es.addEventListener('ingest_completed', (e) => {
        const data = JSON.parse(e.data);
        setCompletedData(data);
        setProgress(100);
        setProcessing(false);
        setStep('done');
        es.close();
      });

      es.addEventListener('ingest_failed', (e) => {
        const data = JSON.parse(e.data);
        message.error(data.message || 'Ingest failed');
        setProcessing(false);
        es.close();
      });

      es.addEventListener('timeout', () => {
        message.warning('Stream timed out');
        setProcessing(false);
        es.close();
      });

      es.onerror = () => {
        if (step !== 'done') setProcessing(false);
        es.close();
      };
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      message.error(e?.response?.data?.detail || 'Failed to start processing');
    }
  };

  const targetListName = targetListIdParam
    ? trackingLists.find((tl) => tl.id === targetListIdParam)?.name
    : null;

  return (
    <div style={{ padding: '32px 40px', maxWidth: 1000, margin: '0 auto' }}>
      {targetListIdParam && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6,
          fontSize: 13, marginBottom: 16, color: '#888',
        }}>
          <span style={{ color: '#5C2D8F', cursor: 'pointer' }} onClick={() => navigate('/tracking')}>Tracking</span>
          <span>/</span>
          <span style={{ color: '#5C2D8F', cursor: 'pointer' }} onClick={() => navigate(`/tracking/${targetListIdParam}`)}>
            {targetListName || 'List'}
          </span>
          <span>/</span>
          <span>Import</span>
        </div>
      )}

      <h1 style={{ fontSize: 26, fontWeight: 700, color: '#1a1a2e', marginBottom: 8 }}>
        Ingest Companies
      </h1>
      <p style={{ color: '#666', fontSize: 14, marginBottom: 28 }}>
        Upload a list of companies or paste names/domains to add them to your tracking lists
      </p>

      {/* Recent filter batches */}
      {recentBatches.length > 0 && step === 'input' && (
        <div style={{ marginBottom: 24 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#555', marginBottom: 8 }}>
            Recent Evaluations
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {recentBatches.map((b) => {
              const isActive = b.evaluation_status !== 'completed' && b.evaluation_status !== 'not_applicable';
              return (
                <div
                  key={b.batch_id}
                  onClick={() => navigate(`/ingest/${b.batch_id}`)}
                  style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '8px 14px', borderRadius: 8, cursor: 'pointer',
                    border: `1px solid ${isActive ? '#d6bcfa' : '#e5e7eb'}`,
                    background: isActive ? '#faf5ff' : '#f9fafb',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    {isActive
                      ? <LoadingOutlined spin style={{ color: '#5C2D8F', fontSize: 13 }} />
                      : <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 13 }} />
                    }
                    <span style={{ fontSize: 13, fontWeight: 500, color: '#333' }}>{b.name || 'Import'}</span>
                    <span style={{ fontSize: 12, color: '#999' }}>
                      {b.total_rows} companies
                      {b.enriched_count ? ` · ${b.enriched_count} evaluated` : ''}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Tag color={isActive ? 'purple' : 'green'} style={{ margin: 0, fontSize: 11 }}>
                      {isActive ? 'In Progress' : 'Completed'}
                    </Tag>
                    <button
                      title="Dismiss"
                      onClick={(e) => {
                        e.stopPropagation();
                        dismissBatch(b.batch_id).then(() => {
                          setRecentBatches((prev) => prev.filter((x) => x.batch_id !== b.batch_id));
                        }).catch(() => message.error('Failed to dismiss batch'));
                      }}
                      style={{
                        background: 'none', border: 'none', cursor: 'pointer', padding: 2,
                        color: '#999', display: 'flex', alignItems: 'center',
                      }}
                      onMouseOver={(e) => { (e.currentTarget as HTMLButtonElement).style.color = '#666'; }}
                      onMouseOut={(e) => { (e.currentTarget as HTMLButtonElement).style.color = '#999'; }}
                    >
                      <CloseOutlined style={{ fontSize: 12 }} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <Steps current={stepIndex} items={stepsItems} style={{ marginBottom: 32 }} />

      {/* Step 1: Input */}
      {step === 'input' && (
        <Card style={{ borderRadius: 14 }}>
          <div style={{ marginBottom: 20 }}>
            <label style={{ fontWeight: 500, fontSize: 13, display: 'block', marginBottom: 6 }}>Batch Name (optional)</label>
            <Input placeholder="e.g., Conference SaaStr 2026" value={batchName} onChange={(e) => setBatchName(e.target.value)} style={{ maxWidth: 400 }} />
          </div>
          <div style={{ marginBottom: 20 }}>
            <label style={{ fontWeight: 500, fontSize: 13, display: 'block', marginBottom: 6 }}>Add to Tracking List (optional)</label>
            <Select
              placeholder="Select a tracking list..."
              value={targetListId || undefined}
              onChange={setTargetListId}
              allowClear
              style={{ width: 400 }}
              options={trackingLists.map((tl) => ({ value: tl.id, label: `${tl.name} (${tl.company_count} companies)` }))}
            />
          </div>
          <Segmented
            value={inputMode}
            onChange={(v) => setInputMode(v as InputMode)}
            options={[{ value: 'upload', label: 'Upload File' }, { value: 'paste', label: 'Paste List' }]}
            style={{ marginBottom: 20 }}
          />
          {inputMode === 'upload' ? (
            <Upload.Dragger
              accept=".xlsx,.csv"
              showUploadList={false}
              beforeUpload={(file) => { handleUpload(file); return false; }}
              style={{ borderRadius: 12, padding: '30px 20px' }}
            >
              <p style={{ fontSize: 40, color: '#5C2D8F', marginBottom: 12 }}><FileExcelOutlined /></p>
              <p style={{ fontSize: 15, fontWeight: 500, color: '#333' }}>Drop an XLSX or CSV file here, or click to browse</p>
              <p style={{ color: '#999', fontSize: 13 }}>Supported formats: .xlsx, .csv</p>
            </Upload.Dragger>
          ) : (
            <div>
              <Input.TextArea
                placeholder={"Paste company names or domains, one per line:\n\nacme.com\nWidgetCorp\nsalesforce.com\nStripe, Figma, Notion"}
                value={pasteValue}
                onChange={(e) => setPasteValue(e.target.value)}
                rows={10}
                style={{ fontFamily: 'monospace', fontSize: 13 }}
              />
              <Button type="primary" onClick={handlePaste} style={{ marginTop: 14, borderRadius: 8 }} disabled={!pasteValue.trim()}>
                Parse List
              </Button>
            </div>
          )}
        </Card>
      )}

      {/* Step 2: Mapping */}
      {step === 'mapping' && (
        <Card style={{ borderRadius: 14 }}>
          <Alert type="info" showIcon message={`${totalRows} rows found. Map your columns to qlGen fields below.`} style={{ marginBottom: 20, borderRadius: 8 }} />
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 14 }}>Column Mapping</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: '10px 16px', alignItems: 'center', marginBottom: 24 }}>
            <div style={{ fontWeight: 600, fontSize: 12, color: '#999' }}>YOUR COLUMN</div>
            <div />
            <div style={{ fontWeight: 600, fontSize: 12, color: '#999' }}>MAPS TO</div>
            {headers.map((h) => (
              <React.Fragment key={h}>
                <div style={{ padding: '8px 12px', background: '#fafafa', borderRadius: 6, fontSize: 13, fontWeight: 500 }}>{h}</div>
                <span style={{ color: '#ccc' }}>→</span>
                <Select value={mapping[h] || ''} onChange={(val) => handleMappingChange(h, val)} style={{ width: '100%' }} options={TARGET_FIELDS} size="small" />
              </React.Fragment>
            ))}
          </div>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 14 }}>Preview (first 5 rows)</h3>
          <Table
            dataSource={previewRows.slice(0, 5)}
            columns={headers.map((h) => ({
              title: (
                <div>
                  <div style={{ fontSize: 12 }}>{h}</div>
                  {mapping[h] && <Tag color="purple" style={{ fontSize: 10, marginTop: 2 }}>→ {TARGET_FIELDS.find((f) => f.value === mapping[h])?.label || mapping[h]}</Tag>}
                </div>
              ),
              dataIndex: h, key: h, ellipsis: true, width: 150,
            }))}
            rowKey={(_, i) => String(i)}
            pagination={false}
            size="small"
            scroll={{ x: headers.length * 150 }}
            style={{ marginBottom: 24 }}
          />
          <Space>
            <Button onClick={() => setStep('input')}>Back</Button>
            <Button type="primary" onClick={handleMappingNext} style={{ borderRadius: 8 }}>
              Next: Configure Filters
            </Button>
          </Space>
        </Card>
      )}

      {/* Step 3: Filter */}
      {step === 'filter' && (
        <Card style={{ borderRadius: 14 }}>
          {/* Tracking list selection if not already set */}
          {!targetListId && (
            <Alert
              type="info"
              showIcon
              message="Select a tracking list to add filtered companies to"
              description={
                <Select
                  placeholder="Select a tracking list..."
                  value={targetListId || undefined}
                  onChange={setTargetListId}
                  allowClear
                  style={{ width: 400, marginTop: 8 }}
                  options={trackingLists.map((tl) => ({ value: tl.id, label: `${tl.name} (${tl.company_count} companies)` }))}
                />
              }
              style={{ marginBottom: 20, borderRadius: 8 }}
            />
          )}

          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 20 }}>
            <div>
              <h3 style={{ fontSize: 16, fontWeight: 600, color: '#1a1a2e', marginBottom: 4 }}>
                <FilterOutlined style={{ marginRight: 8, color: '#5C2D8F' }} />
                Firmographic Fit Filter
              </h3>
              <p style={{ color: '#666', fontSize: 13, margin: 0 }}>
                Score and filter {totalRows} imported companies against firmographic criteria.
                Each company is researched via Apollo &amp; web sources, then AI-scored on industry fit,
                geography, employee size, and revenue. You review and select which companies to track.
              </p>
            </div>
            <Switch checked={filterEnabled} onChange={setFilterEnabled} style={{ marginTop: 4 }} />
          </div>

          {filterEnabled && (
            <div style={{ background: '#fafbfc', borderRadius: 10, padding: '20px 24px', border: '1px solid #f0f0f0' }}>
              <div style={{ marginBottom: 20 }}>
                <label style={{ fontWeight: 500, fontSize: 13, display: 'block', marginBottom: 6, color: '#555' }}>Load from existing search criteria</label>
                <Select
                  placeholder="Select an ICP to load criteria..."
                  onChange={handleLoadFromICP}
                  allowClear
                  style={{ width: 400 }}
                  options={icpList.filter((i) => i.id).map((icp) => ({ value: icp.id!, label: icp.name }))}
                />
              </div>
              <div style={{ marginBottom: 20 }}>
                <label style={{ fontWeight: 500, fontSize: 13, display: 'block', marginBottom: 6, color: '#555' }}>Industry Verticals</label>
                <Space direction="vertical" style={{ width: '100%' }}>
                  {filterConfig.industry_types.map((ind, i) => (
                    <Space key={i} wrap>
                      <Input value={ind.vertical} onChange={(e) => updateIndustry(i, 'vertical', e.target.value)} placeholder="Vertical (e.g., Technology)" style={{ width: 220 }} size="small" />
                      <Input value={ind.sub_vertical || ''} onChange={(e) => updateIndustry(i, 'sub_vertical', e.target.value)} placeholder="Sub-vertical (optional)" style={{ width: 220 }} size="small" />
                      <Button danger size="small" icon={<DeleteOutlined />} onClick={() => removeIndustry(i)} />
                    </Space>
                  ))}
                  <Button type="dashed" size="small" icon={<PlusOutlined />} onClick={addIndustry}>Add Industry</Button>
                </Space>
              </div>
              <div style={{ marginBottom: 20 }}>
                <label style={{ fontWeight: 500, fontSize: 13, display: 'block', marginBottom: 6, color: '#555' }}>Target Countries</label>
                <Space wrap style={{ marginBottom: 8 }}>
                  {filterConfig.countries.map((c) => (
                    <Tag key={c} closable onClose={() => setFilterConfig((prev) => ({ ...prev, countries: prev.countries.filter((x) => x !== c) }))} color="blue">{c}</Tag>
                  ))}
                </Space>
                <Input
                  placeholder="Add country and press Enter (e.g., United States)"
                  value={countryInput}
                  onChange={(e) => setCountryInput(e.target.value)}
                  onPressEnter={addCountry}
                  style={{ maxWidth: 400 }}
                  size="small"
                  suffix={<Button size="small" type="link" onClick={addCountry}>Add</Button>}
                />
              </div>
              <div style={{ marginBottom: 20 }}>
                <label style={{ fontWeight: 500, fontSize: 13, display: 'block', marginBottom: 6, color: '#555' }}>Employee Count Range</label>
                <Space wrap>
                  <InputNumber min={1} value={filterConfig.employee_range.min} onChange={(v) => setFilterConfig((prev) => ({ ...prev, employee_range: { ...prev.employee_range, min: v || 1 } }))} addonBefore="Min" size="small" style={{ width: 160 }} />
                  <span style={{ color: '#999' }}>to</span>
                  <InputNumber min={1} value={filterConfig.employee_range.max} onChange={(v) => setFilterConfig((prev) => ({ ...prev, employee_range: { ...prev.employee_range, max: v || 10000 } }))} addonBefore="Max" size="small" style={{ width: 160 }} />
                </Space>
              </div>
              <div>
                <label style={{ fontWeight: 500, fontSize: 13, display: 'block', marginBottom: 6, color: '#555' }}>Revenue Range</label>
                <Space wrap>
                  <Select value={filterConfig.revenue_range.currency} onChange={(v) => setFilterConfig((prev) => ({ ...prev, revenue_range: { ...prev.revenue_range, currency: v } }))} style={{ width: 80 }} size="small">
                    <Select.Option value="USD">USD</Select.Option>
                    <Select.Option value="INR">INR</Select.Option>
                    <Select.Option value="EUR">EUR</Select.Option>
                    <Select.Option value="GBP">GBP</Select.Option>
                  </Select>
                  <InputNumber min={0} value={filterConfig.revenue_range.min} onChange={(v) => setFilterConfig((prev) => ({ ...prev, revenue_range: { ...prev.revenue_range, min: v || 0 } }))} formatter={(v) => `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')} addonBefore="Min" size="small" style={{ width: 200 }} />
                  <span style={{ color: '#999' }}>to</span>
                  <InputNumber min={0} value={filterConfig.revenue_range.max} onChange={(v) => setFilterConfig((prev) => ({ ...prev, revenue_range: { ...prev.revenue_range, max: v || 0 } }))} formatter={(v) => `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')} addonBefore="Max" size="small" style={{ width: 200 }} />
                </Space>
              </div>
            </div>
          )}

          {filterEnabled && !targetListId && (
            <Alert
              type="warning"
              showIcon
              message="Select a tracking list above to use firmographic filtering. Without a list, companies will be imported without scoring."
              style={{ marginTop: 16, borderRadius: 8 }}
            />
          )}

          <Space style={{ marginTop: 24 }}>
            <Button onClick={() => setStep('mapping')}>Back</Button>
            <Button
              type="primary"
              onClick={handleConfirm}
              style={{ borderRadius: 8 }}
              disabled={filterEnabled && !targetListId}
            >
              {filterEnabled
                ? `Start Firmographic Evaluation (${totalRows} companies)`
                : `Import ${totalRows} Companies`
              }
            </Button>
            {!filterEnabled && (
              <span style={{ color: '#999', fontSize: 12 }}>
                Skipping filter — all companies will be imported directly
              </span>
            )}
          </Space>
        </Card>
      )}

      {/* Step 4: Processing (non-filter flow only) */}
      {step === 'processing' && (
        <Card style={{ borderRadius: 14, textAlign: 'center', padding: '40px 20px' }}>
          <Spin indicator={<LoadingOutlined style={{ fontSize: 40, color: '#5C2D8F' }} />} />
          <h2 style={{ marginTop: 20, color: '#1a1a2e' }}>Importing companies...</h2>
          <Progress percent={progress} strokeColor="#5C2D8F" style={{ maxWidth: 400, margin: '20px auto' }} />
          {progressData && (
            <div style={{ color: '#666', fontSize: 13 }}>
              Processed {progressData.processed} of {progressData.total} |{' '}
              {progressData.matched_kb} matched in KB |{' '}
              {progressData.newly_created} new
              {progressData.errors > 0 && <span style={{ color: '#f5222d' }}> | {progressData.errors} errors</span>}
            </div>
          )}
        </Card>
      )}

      {/* Step 5: Done (non-filter flow only) */}
      {step === 'done' && completedData && (
        <Card style={{ borderRadius: 14, textAlign: 'center', padding: '40px 20px' }}>
          <CheckCircleOutlined style={{ fontSize: 48, color: '#52c41a' }} />
          <h2 style={{ marginTop: 16, color: '#1a1a2e' }}>Ingest Complete</h2>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 32, margin: '24px 0', fontSize: 14 }}>
            <div>
              <div style={{ fontSize: 28, fontWeight: 700, color: '#5C2D8F' }}>{completedData.processed}</div>
              <div style={{ color: '#999' }}>Processed</div>
            </div>
            <div>
              <div style={{ fontSize: 28, fontWeight: 700, color: '#1E9B6B' }}>{completedData.matched_kb}</div>
              <div style={{ color: '#999' }}>KB Matches</div>
            </div>
            <div>
              <div style={{ fontSize: 28, fontWeight: 700, color: '#E0820A' }}>{completedData.newly_created}</div>
              <div style={{ color: '#999' }}>New Records</div>
            </div>
            {completedData.errors > 0 && (
              <div>
                <div style={{ fontSize: 28, fontWeight: 700, color: '#f5222d' }}>{completedData.errors}</div>
                <div style={{ color: '#999' }}>Errors</div>
              </div>
            )}
          </div>
          <Space size="middle">
            {targetListId && (
              <Button type="primary" onClick={() => navigate(`/tracking/${targetListId}`)} style={{ borderRadius: 8 }}>
                View Tracking List
              </Button>
            )}
            <Button onClick={() => navigate('/tracking')} style={{ borderRadius: 8 }}>All Tracking Lists</Button>
            <Button onClick={() => { setStep('input'); setBatchId(null); setProgress(0); setProgressData(null); setCompletedData(null); }} style={{ borderRadius: 8 }}>
              Upload Another
            </Button>
          </Space>
        </Card>
      )}
    </div>
  );
};

export default IngestPage;
