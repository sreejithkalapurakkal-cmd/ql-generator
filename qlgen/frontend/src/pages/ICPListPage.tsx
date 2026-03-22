import React, { useEffect, useState, useMemo, useRef } from 'react';
import { Card, Button, Space, Popconfirm, message, Modal, Upload, Alert, Collapse, Descriptions, Spin, Input } from 'antd';
import { PlusOutlined, DownloadOutlined, FileExcelOutlined, SearchOutlined } from '@ant-design/icons';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { listICPs, deleteICP, createICP, getICPTemplateURL, parseICPUpload, ParsedICP } from '../api/icpApi';
import { startPipeline } from '../api/pipelineApi';
import { ICPConfig } from '../types';
import { useAuth } from '../context/AuthContext';

const ICPListPage: React.FC = () => {
  const navigate = useNavigate();
  const { user: authUser } = useAuth();
  const isAdmin = authUser?.role === 'super_admin';
  const [searchParams, setSearchParams] = useSearchParams();
  const [icps, setIcps] = useState<ICPConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [selectedICP, setSelectedICP] = useState<ICPConfig | null>(null);

  // Search + infinite scroll state
  const [searchQuery, setSearchQuery] = useState('');
  const [displayCount, setDisplayCount] = useState(12);
  const sentinelRef = useRef<HTMLDivElement>(null);

  const filteredICPs = useMemo(() => {
    if (!searchQuery.trim()) return icps;
    const q = searchQuery.toLowerCase();
    return icps.filter(
      (icp) =>
        icp.name?.toLowerCase().includes(q) ||
        icp.description?.toLowerCase().includes(q)
    );
  }, [icps, searchQuery]);

  // Reset display count when search changes
  useEffect(() => { setDisplayCount(12); }, [searchQuery]);

  // IntersectionObserver for infinite scroll
  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          setDisplayCount((prev) => prev + 12);
        }
      },
      { threshold: 0.1 }
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [filteredICPs.length]);

  // Run pipeline modal state
  const [runModalIcpId, setRunModalIcpId] = useState<string | null>(null);

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

  const handleClone = (icp: ICPConfig) => {
    navigate('/icp/new', { state: { cloneFrom: icp } });
  };

  const handleRunPipeline = async (icpId: string) => {
    try {
      const res = await startPipeline({ icp_config_id: icpId, options: { max_contacts_per_company: 5 } });
      message.success('Pipeline started');
      navigate(`/pipeline/${res.data.id}`);
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'Failed to start pipeline');
    }
  };

  const openRunModal = (icpId: string) => {
    setRunModalIcpId(icpId);
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
          await startPipeline({ icp_config_id: res.data.id!, options: { max_companies: 25, max_contacts_per_company: 5 } });
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
          <h1 className="page-title">Saved ICPs</h1>
          <Space>
            <Input
              prefix={<SearchOutlined style={{ color: 'var(--g400)' }} />}
              placeholder="Search by name or description..."
              allowClear
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ maxWidth: 320, width: 320 }}
            />
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
      ) : searchQuery && filteredICPs.length === 0 ? (
        <Card style={{ textAlign: 'center', padding: '40px 0' }}>
          <div style={{ fontSize: 40, marginBottom: 16 }}>🔍</div>
          <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 8, color: 'var(--g900)' }}>
            No Matches Found
          </h3>
          <p style={{ color: 'var(--g500)', fontSize: 13 }}>
            No ICPs match "{searchQuery}". Try a different search term.
          </p>
        </Card>
      ) : (
        <>
          <div className="card-grid">
            {filteredICPs.slice(0, displayCount).map((icp) => {
              const cfg = icp.config as any;
              const fd = cfg?.firmographic_details || {};
              const regions = fd?.geography?.countries || cfg?.regions?.countries;
              const industries = fd?.industry_types || cfg?.industry_types || cfg?.industry;
              const roles = cfg?.authority_roles?.target_roles || cfg?.leadership_traits?.target_roles;
              const empRange = fd?.employee_range;

              return (
                <div
                  key={icp.id}
                  className="run-card"
                  onClick={() => setSelectedICP(icp)}
                >
                  {/* Header: name + ... menu */}
                  <div className="rc-header">
                    <div className="rc-title">
                      {icp.name}
                      {isAdmin && icp.user_name && (
                        <span style={{ fontSize: 11, color: 'var(--g400)', fontWeight: 400, marginLeft: 8 }}>
                          by {icp.user_name}
                        </span>
                      )}
                    </div>
                    <div className="menu-wrap" onClick={(e) => e.stopPropagation()}>
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
                            openRunModal(icp.id!);
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
                        <div
                          className="menu-item"
                          onClick={() => {
                            setOpenMenuId(null);
                            handleClone(icp);
                          }}
                        >
                          Clone
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

                  {/* Date + description */}
                  <div className="rc-meta">
                    <span className="rc-date">
                      {icp.created_at ? new Date(icp.created_at).toLocaleDateString() : 'N/A'}
                    </span>
                    {icp.description && (
                      <span className="rc-offering" title={icp.description}>
                        {icp.description}
                      </span>
                    )}
                  </div>

                  {/* ICP detail rows */}
                  <div className="rc-icp-block">
                    {regions && regions.length > 0 && (
                      <div className="rc-icp-row">
                        <span className="rc-icp-key">Regions</span>
                        <span className="rc-icp-val">
                          {regions.slice(0, 3).join(', ')}
                        </span>
                      </div>
                    )}
                    {industries && industries.length > 0 && (
                      <div className="rc-icp-row">
                        <span className="rc-icp-key">Industries</span>
                        <span className="rc-icp-val">
                          {industries.map((i: any) => i.vertical).slice(0, 3).join(', ')}
                        </span>
                      </div>
                    )}
                    {roles && roles.length > 0 && (
                      <div className="rc-icp-row">
                        <span className="rc-icp-key">Target Roles</span>
                        <span className="rc-icp-val">
                          {roles.slice(0, 3).join(', ')}
                        </span>
                      </div>
                    )}
                    {empRange && (
                      <div className="rc-icp-row">
                        <span className="rc-icp-key">Company Size</span>
                        <span className="rc-icp-val">
                          {empRange.min?.toLocaleString()}–{empRange.max?.toLocaleString()} employees
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Footer */}
                  <div className="rc-footer" onClick={(e) => e.stopPropagation()}>
                    <Button
                      size="small"
                      className="rc-edit-btn"
                      onClick={() => navigate(`/icp/${icp.id}/edit`)}
                    >
                      Edit
                    </Button>
                    <span
                      className="rc-view-link"
                      onClick={() => setSelectedICP(icp)}
                    >
                      View Details →
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
          <div ref={sentinelRef} style={{ height: 1 }} />
          {displayCount < filteredICPs.length ? (
            <div style={{ textAlign: 'center', padding: '16px 0', color: 'var(--g400)', fontSize: 13 }}>
              Loading more...
            </div>
          ) : filteredICPs.length > 12 ? (
            <div style={{ textAlign: 'center', padding: '16px 0', color: 'var(--g400)', fontSize: 12 }}>
              Showing all {filteredICPs.length} items
            </div>
          ) : null}
        </>
      )}

      {/* ICP Overview Modal */}
      <Modal
        title={selectedICP?.name || 'ICP Details'}
        open={!!selectedICP}
        onCancel={() => setSelectedICP(null)}
        width="90vw"
        style={{ maxWidth: 1100, top: 32 }}
        footer={
          <Space>
            <Button onClick={() => setSelectedICP(null)}>Close</Button>
            <Button onClick={() => {
              setSelectedICP(null);
              navigate(`/icp/${selectedICP?.id}/edit`);
            }}>
              Edit
            </Button>
            <Button type="primary" onClick={() => {
              const icpId = selectedICP?.id;
              setSelectedICP(null);
              if (icpId) openRunModal(icpId);
            }}>
              Run Pipeline
            </Button>
          </Space>
        }
      >
        {selectedICP && (() => {
          const cfg = selectedICP.config as any;
          const fd = cfg?.firmographic_details || {};
          const offerings = cfg?.target_capability?.offerings || cfg?.target_offering || cfg?.offering;
          const regions = fd?.geography || cfg?.regions;
          const industries = fd?.industry_types || cfg?.industry_types || cfg?.industry;
          const empRange = fd?.employee_range;
          const revRange = fd?.revenue_range;
          const leadership = cfg?.authority_roles || cfg?.leadership_traits;
          const urgencySignals = cfg?.urgency_signals?.signals || [];
          const budgetSignals = cfg?.budget_signals?.signals || [];

          return (
            <div>
              {selectedICP.description && (
                <p style={{ color: 'var(--g500)', fontSize: 13, marginBottom: 16 }}>
                  {selectedICP.description}
                </p>
              )}
              <Descriptions column={2} size="small" bordered labelStyle={{ width: 180, fontWeight: 600 }}>
                <Descriptions.Item label="Offerings" span={2}>
                  {(Array.isArray(offerings) ? offerings.join(', ') : offerings) || '—'}
                </Descriptions.Item>
                <Descriptions.Item label="Countries" span={2}>
                  {regions?.countries?.join(', ') || '—'}
                </Descriptions.Item>
                <Descriptions.Item label="Industries" span={2}>
                  {industries?.map((i: any) =>
                    `${i.vertical}${i.sub_vertical ? ` / ${i.sub_vertical}` : ''}`
                  ).join(', ') || '—'}
                </Descriptions.Item>
                <Descriptions.Item label="Employees">
                  {empRange ? `${empRange.min?.toLocaleString()}–${empRange.max?.toLocaleString()}` : '—'}
                </Descriptions.Item>
                <Descriptions.Item label="Revenue">
                  {revRange ? `${revRange.currency || 'USD'} ${revRange.min?.toLocaleString()}–${revRange.max?.toLocaleString()}` : '—'}
                </Descriptions.Item>
                <Descriptions.Item label="Urgency Signals" span={2}>
                  {urgencySignals.length > 0 ? urgencySignals.join(', ') : '—'}
                </Descriptions.Item>
                <Descriptions.Item label="Budget Signals" span={2}>
                  {budgetSignals.length > 0 ? budgetSignals.join(', ') : '—'}
                </Descriptions.Item>
                <Descriptions.Item label="Target Roles" span={2}>
                  {leadership?.target_roles?.join(', ') || '—'}
                </Descriptions.Item>
              </Descriptions>
            </div>
          );
        })()}
      </Modal>

      {/* Run Pipeline Modal */}
      <Modal
        title="Run Pipeline"
        open={!!runModalIcpId}
        onCancel={() => setRunModalIcpId(null)}
        width={420}
        footer={
          <Space>
            <Button onClick={() => setRunModalIcpId(null)}>Cancel</Button>
            <Button
              type="primary"
              onClick={() => {
                if (runModalIcpId) {
                  handleRunPipeline(runModalIcpId);
                  setRunModalIcpId(null);
                }
              }}
            >
              Run Pipeline
            </Button>
          </Space>
        }
      >
        <div style={{ padding: '8px 0', fontSize: 13, color: 'var(--g600)', lineHeight: 1.8 }}>
          <p style={{ marginBottom: 12 }}>The pipeline runs through 5 stages:</p>
          <ol style={{ paddingLeft: 20, margin: 0 }}>
            <li>Industry Discovery (automatic)</li>
            <li>Firmographic Fit Check (automatic)</li>
            <li>Budget &amp; Urgency Signal Research</li>
            <li>Contact Discovery (automatic)</li>
            <li>Final Scoring &amp; Ranking</li>
          </ol>
          <p style={{ marginTop: 12, fontSize: 12, color: 'var(--g500)' }}>
            You will review and select companies between stages.
          </p>
        </div>
      </Modal>

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
                Download the template, fill in your ICP data, and upload the completed file.
                The template has a simple Field/Value format matching the search criteria form.
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
                        {(icp.config as any)?.target_capability?.offerings?.join(', ') || '—'}
                      </Descriptions.Item>
                      <Descriptions.Item label="Countries">
                        {(icp.config as any)?.firmographic_details?.geography?.countries?.join(', ') || '—'}
                      </Descriptions.Item>
                      <Descriptions.Item label="Priority Areas">
                        {(icp.config as any)?.firmographic_details?.geography?.priority_areas?.join(', ') || '—'}
                      </Descriptions.Item>
                      <Descriptions.Item label="Industries" span={2}>
                        {(icp.config as any)?.firmographic_details?.industry_types?.map((i: any) =>
                          `${i.vertical}${i.sub_vertical ? ` / ${i.sub_vertical}` : ''}`
                        ).join(', ') || '—'}
                      </Descriptions.Item>
                      <Descriptions.Item label="Employees">
                        {(icp.config as any)?.firmographic_details?.employee_range?.min?.toLocaleString()}–{(icp.config as any)?.firmographic_details?.employee_range?.max?.toLocaleString()}
                      </Descriptions.Item>
                      <Descriptions.Item label="Revenue">
                        {(icp.config as any)?.firmographic_details?.revenue_range?.currency || 'USD'}{' '}
                        {(icp.config as any)?.firmographic_details?.revenue_range?.min?.toLocaleString()}–{(icp.config as any)?.firmographic_details?.revenue_range?.max?.toLocaleString()}
                      </Descriptions.Item>
                      <Descriptions.Item label="Urgency Signals" span={2}>
                        {(icp.config as any)?.urgency_signals?.signals?.join(', ') || '—'}
                      </Descriptions.Item>
                      <Descriptions.Item label="Budget Signals" span={2}>
                        {(icp.config as any)?.budget_signals?.signals?.join(', ') || '—'}
                      </Descriptions.Item>
                      <Descriptions.Item label="Target Roles" span={2}>
                        {(icp.config as any)?.authority_roles?.target_roles?.join(', ') || '—'}
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
