import React, { useEffect, useState } from 'react';
import { Card, Button, Space, Popconfirm, message, Modal, Upload, Alert, Collapse, Descriptions, Spin } from 'antd';
import { PlusOutlined, UploadOutlined, DownloadOutlined, FileExcelOutlined } from '@ant-design/icons';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { listICPs, deleteICP, createICP, getICPTemplateURL, parseICPUpload, ParsedICP } from '../api/icpApi';
import { startPipeline } from '../api/pipelineApi';
import { ICPConfig } from '../types';

const ICPListPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [icps, setIcps] = useState<ICPConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);

  // Import modal state
  const [importOpen, setImportOpen] = useState(false);
  const [importStep, setImportStep] = useState<'upload' | 'review'>('upload');
  const [parsedICPs, setParsedICPs] = useState<ParsedICP[]>([]);
  const [parsing, setParsing] = useState(false);
  const [saving, setSaving] = useState(false);

  const fetchICPs = () => {
    setLoading(true);
    listICPs()
      .then((res) => setIcps(Array.isArray(res.data) ? res.data : []))
      .catch(() => setIcps([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchICPs(); }, []);

  // Auto-open import modal when navigated with ?import=true
  useEffect(() => {
    if (searchParams.get('import') === 'true') {
      setImportOpen(true);
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  // Close dropdown menu when clicking outside
  useEffect(() => {
    const handleClickOutside = () => setOpenMenuId(null);
    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  }, []);

  const toggleMenu = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    setOpenMenuId(openMenuId === id ? null : id);
  };

  const handleDelete = async (id: string) => {
    await deleteICP(id);
    message.success('ICP deleted');
    fetchICPs();
  };

  const handleRunPipeline = async (icpId: string) => {
    try {
      const res = await startPipeline({ icp_config_id: icpId, options: { max_companies: 15, max_contacts_per_company: 5 } });
      message.success('Pipeline started');
      navigate(`/pipeline/${res.data.id}`);
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'Failed to start pipeline');
    }
  };

  const handleFileUpload = async (file: File) => {
    setParsing(true);
    try {
      const res = await parseICPUpload(file);
      setParsedICPs(res.data);
      setImportStep('review');
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'Failed to parse Excel file');
    } finally {
      setParsing(false);
    }
    return false; // prevent default upload
  };

  const handleRemoveParsedICP = (index: number) => {
    setParsedICPs((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSaveAll = async () => {
    setSaving(true);
    let successCount = 0;
    for (const icp of parsedICPs) {
      try {
        await createICP({ name: icp.name, description: icp.description, config: icp.config });
        successCount++;
      } catch {
        message.error(`Failed to save ICP: ${icp.name}`);
      }
    }
    setSaving(false);
    if (successCount > 0) {
      message.success(`${successCount} ICP(s) saved successfully`);
      setImportOpen(false);
      setImportStep('upload');
      setParsedICPs([]);
      fetchICPs();
    }
  };

  const handleSaveAndRunAll = async () => {
    setSaving(true);
    let successCount = 0;
    for (const icp of parsedICPs) {
      try {
        const res = await createICP({ name: icp.name, description: icp.description, config: icp.config });
        successCount++;
        try {
          await startPipeline({ icp_config_id: res.data.id!, options: { max_companies: 15, max_contacts_per_company: 5 } });
        } catch {
          message.warning(`ICP "${icp.name}" saved but pipeline failed to start`);
        }
      } catch {
        message.error(`Failed to save ICP: ${icp.name}`);
      }
    }
    setSaving(false);
    if (successCount > 0) {
      message.success(`${successCount} ICP(s) saved and pipelines started`);
      setImportOpen(false);
      setImportStep('upload');
      setParsedICPs([]);
      fetchICPs();
    }
  };

  const closeImportModal = () => {
    setImportOpen(false);
    setImportStep('upload');
    setParsedICPs([]);
  };

  return (
    <div style={{ padding: '28px 32px', maxWidth: 1400, margin: '0 auto', width: '100%' }}>
      <div style={{ marginBottom: 24 }}>
        <div className="section-label">Configuration</div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h1 className="page-title">Saved Searches</h1>
          <Space>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/icp/new')}>
              New Search
            </Button>
          </Space>
        </div>
      </div>

      {!loading && icps.length === 0 ? (
        <Card style={{ textAlign: 'center', padding: '40px 0' }}>
          <div style={{ fontSize: 40, marginBottom: 16 }}>📋</div>
          <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 8, color: 'var(--g900)' }}>
            No ICP Configurations Yet
          </h3>
          <p style={{ color: 'var(--g500)', marginBottom: 28, maxWidth: 500, margin: '0 auto 28px', fontSize: 13, lineHeight: 1.6 }}>
            Define your Ideal Customer Profile to start discovering qualified leads. You can create one manually or import multiple ICPs from an Excel spreadsheet.
          </p>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 16, flexWrap: 'wrap' }}>
            <Button type="primary" size="large" icon={<PlusOutlined />} onClick={() => navigate('/icp/new')}>
              Create New Search
            </Button>
            <Button size="large" icon={<FileExcelOutlined style={{ color: 'var(--green)' }} />} onClick={() => setImportOpen(true)}>
              Import from Excel
            </Button>
          </div>
        </Card>
      ) : (
        <div className="card-grid">
          {icps.map((icp) => (
            <Card key={icp.id} hoverable>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                <div>
                  <div className="icp-card-name">{icp.name}</div>
                  <div className="icp-card-date">
                    {icp.created_at ? new Date(icp.created_at).toLocaleDateString() : 'N/A'}
                  </div>
                </div>
                <div className="menu-wrap">
                  <button
                    className="menu-toggle"
                    onClick={(e) => toggleMenu(e, icp.id!)}
                  >
                    ⋯
                  </button>
                  <div className={`dropdown-menu ${openMenuId === icp.id ? 'open' : ''}`}>
                    <div
                      className="menu-item"
                      onClick={() => {
                        setOpenMenuId(null);
                        handleRunPipeline(icp.id!);
                      }}
                    >
                      Run Pipeline
                    </div>
                    <div
                      className="menu-item"
                      onClick={() => {
                        setOpenMenuId(null);
                        navigate(`/icp/${icp.id}/edit`);
                      }}
                    >
                      Edit
                    </div>
                    <div className="menu-divider"></div>
                    <Popconfirm
                      title="Delete this ICP?"
                      onConfirm={() => {
                        setOpenMenuId(null);
                        handleDelete(icp.id!);
                      }}
                      onCancel={() => setOpenMenuId(null)}
                    >
                      <div className="menu-item danger">Delete</div>
                    </Popconfirm>
                  </div>
                </div>
              </div>
              {icp.description && (
                <div className="icp-card-offering">{icp.description}</div>
              )}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: "10px" }}>
                {icp.config?.regions?.countries?.slice(0, 2).map((country, idx) => (
                  <span key={idx} className="tag">{country}</span>
                ))}
                {icp.config?.industry_types?.slice(0, 2).map((ind, idx) => (
                  <span key={idx} className="tag">{ind.vertical}</span>
                ))}
                {icp.config?.company_size && (
                  <span className="tag">
                    {icp.config.company_size.employees_min}-{icp.config.company_size.employees_max} emp
                  </span>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Import from Excel Modal */}
      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <FileExcelOutlined style={{ color: 'var(--green)', fontSize: 18 }} />
            <span>Import ICPs from Excel</span>
          </div>
        }
        open={importOpen}
        onCancel={closeImportModal}
        width={720}
        footer={importStep === 'review' ? (
          <Space>
            <Button onClick={() => { setImportStep('upload'); setParsedICPs([]); }}>
              Back
            </Button>
            <Button type="primary" loading={saving} onClick={handleSaveAll}>
              Save All ({parsedICPs.length})
            </Button>
            <Button type="primary" loading={saving} onClick={handleSaveAndRunAll}
              style={{ background: 'var(--green)', borderColor: 'var(--green)' }}>
              Save &amp; Run All
            </Button>
          </Space>
        ) : null}
      >
        {importStep === 'upload' && (
          <div>
            <div style={{ marginBottom: 20 }}>
              <p style={{ color: 'var(--g600)', fontSize: 13, margin: '0 0 12px' }}>
                Download the template, fill in your ICP data across the 8 sheets, and upload the completed file.
                Each sheet uses an "ICP Name" column to support multiple ICPs in a single file.
              </p>
              <Button
                icon={<DownloadOutlined />}
                href={getICPTemplateURL()}
                target="_blank"
                style={{ marginBottom: 16 }}
              >
                Download Template
              </Button>
            </div>
            <Upload.Dragger
              accept=".xlsx"
              showUploadList={false}
              customRequest={({ file }) => handleFileUpload(file as File)}
              disabled={parsing}
            >
              {parsing ? (
                <div style={{ padding: 24 }}>
                  <Spin size="large" />
                  <p style={{ marginTop: 12, color: 'var(--g500)' }}>Parsing Excel file...</p>
                </div>
              ) : (
                <div style={{ padding: 24 }}>
                  <p className="ant-upload-drag-icon">
                    <FileExcelOutlined style={{ fontSize: 40, color: 'var(--green)' }} />
                  </p>
                  <p style={{ fontSize: 14, fontWeight: 600, color: 'var(--g800)' }}>
                    Click or drag your .xlsx file here
                  </p>
                  <p style={{ fontSize: 12, color: 'var(--g400)' }}>
                    Supports multiple ICPs per file
                  </p>
                </div>
              )}
            </Upload.Dragger>
          </div>
        )}

        {importStep === 'review' && (
          <div>
            <Alert
              type="info"
              showIcon
              message={`Found ${parsedICPs.length} ICP(s) in uploaded file`}
              style={{ marginBottom: 16 }}
            />
            {parsedICPs.length === 0 && (
              <Alert type="warning" showIcon message="No ICPs found. Please check your file format." />
            )}
            <Collapse
              accordion
              items={parsedICPs.map((icp, idx) => ({
                key: String(idx),
                label: (
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                    <span style={{ fontWeight: 600 }}>{icp.name || `ICP ${idx + 1}`}</span>
                    <Button
                      size="small"
                      danger
                      onClick={(e) => { e.stopPropagation(); handleRemoveParsedICP(idx); }}
                      style={{ marginRight: 8 }}
                    >
                      Remove
                    </Button>
                  </div>
                ),
                children: (
                  <div>
                    {icp.warnings.length > 0 && (
                      <Alert
                        type="warning"
                        showIcon
                        message={
                          <ul style={{ margin: 0, paddingLeft: 16 }}>
                            {icp.warnings.map((w, wi) => <li key={wi}>{w}</li>)}
                          </ul>
                        }
                        style={{ marginBottom: 12 }}
                      />
                    )}
                    <Descriptions column={2} size="small" bordered>
                      <Descriptions.Item label="Description" span={2}>
                        {icp.description || '—'}
                      </Descriptions.Item>
                      <Descriptions.Item label="Offerings" span={2}>
                        {(icp.config as any)?.target_offering?.join(', ') || '—'}
                      </Descriptions.Item>
                      <Descriptions.Item label="Countries">
                        {(icp.config as any)?.regions?.countries?.join(', ') || '—'}
                      </Descriptions.Item>
                      <Descriptions.Item label="Priority Areas">
                        {(icp.config as any)?.regions?.priority_areas?.join(', ') || '—'}
                      </Descriptions.Item>
                      <Descriptions.Item label="Industries" span={2}>
                        {(icp.config as any)?.industry_types?.map((i: any) =>
                          `${i.vertical}${i.sub_vertical ? ` / ${i.sub_vertical}` : ''}`
                        ).join(', ') || '—'}
                      </Descriptions.Item>
                      <Descriptions.Item label="Employees">
                        {(icp.config as any)?.company_size?.employees_min}–{(icp.config as any)?.company_size?.employees_max}
                      </Descriptions.Item>
                      <Descriptions.Item label="Revenue">
                        {(icp.config as any)?.company_size?.revenue_currency} {((icp.config as any)?.company_size?.revenue_min / 1000000).toFixed(0)}M–{((icp.config as any)?.company_size?.revenue_max / 1000000).toFixed(0)}M
                      </Descriptions.Item>
                      <Descriptions.Item label="Tech Signals" span={2}>
                        {(icp.config as any)?.technology_maturity?.signals?.join(', ') || '—'}
                      </Descriptions.Item>
                      <Descriptions.Item label="Target Roles" span={2}>
                        {(icp.config as any)?.leadership_traits?.target_roles?.join(', ') || '—'}
                      </Descriptions.Item>
                    </Descriptions>
                  </div>
                ),
              }))}
            />
          </div>
        )}
      </Modal>
    </div>
  );
};

export default ICPListPage;
