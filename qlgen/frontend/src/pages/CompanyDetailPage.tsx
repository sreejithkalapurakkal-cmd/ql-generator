import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  Button, Card, Tag, Tooltip, Typography, Spin, Select, message, Space,
} from 'antd';
import { LinkOutlined, ThunderboltOutlined, TeamOutlined, LoadingOutlined } from '@ant-design/icons';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import {
  getSingleCompany, discoverCompanySignals, discoverCompanyContacts, getDiscoveryStreamUrl,
  getDiscoveryStatus,
} from '../api/leadsApi';
import { Company, CompanyStageResult, Contact } from '../types';
import { usePageContext } from '../context/PageContextProvider';

const { Text } = Typography;

// ---------------------------------------------------------------------------
// Score helpers
// ---------------------------------------------------------------------------

const getScoreColor = (score: number | null | undefined): string => {
  if (score == null) return 'var(--g300)';
  if (score >= 75) return 'var(--green)';
  if (score >= 50) return 'var(--amber)';
  if (score >= 25) return 'var(--amber)';
  return 'var(--red)';
};

const getScoreTagColor = (score: number | null | undefined): string => {
  if (score == null) return 'default';
  if (score >= 75) return 'green';
  if (score >= 50) return 'gold';
  if (score >= 25) return 'orange';
  return 'red';
};

const getScoreLabel = (score: number | null | undefined): string => {
  if (score == null) return 'N/A';
  if (score >= 75) return 'High';
  if (score >= 50) return 'Medium';
  if (score >= 25) return 'Low';
  return 'Very Low';
};

// ---------------------------------------------------------------------------
// Stage display helpers
// ---------------------------------------------------------------------------

const STAGE_DISPLAY: Record<string, { label: string; color: string }> = {
  company_discovery:      { label: 'Company Discovery',         color: 'blue' },
  industry_discovery:     { label: 'Industry Discovery',        color: 'blue' },
  firmographic_filter:    { label: 'Firmographic Filter',       color: 'purple' },
  firmographic_fit:       { label: 'Firmographic Fit',          color: 'purple' },
  budget_signal:          { label: 'Budget Signal',             color: 'green' },
  budget_signals:         { label: 'Budget Signals',            color: 'green' },
  urgency_signal:         { label: 'Urgency Signal',            color: 'orange' },
  urgency_signals:        { label: 'Urgency Signals',           color: 'orange' },
  budget_urgency_signals: { label: 'Budget & Urgency Signals',  color: 'cyan' },
  contact_discovery:      { label: 'Contact Discovery',         color: 'cyan' },
  contact_enrichment:     { label: 'Contact Enrichment',        color: 'magenta' },
  scoring:                { label: 'Final Scoring',             color: 'red' },
  final_scoring:          { label: 'Final Scoring',             color: 'red' },
};

const getStageDisplay = (stage: string) =>
  STAGE_DISPLAY[stage] || {
    label: stage.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
    color: 'var(--g400)',
  };

// Maps Ant Design semantic color names → CSS custom properties for use in inline styles
const STAGE_BORDER_COLOR: Record<string, string> = {
  blue:    'var(--purple)',
  purple:  'var(--purple)',
  green:   'var(--green)',
  orange:  'var(--amber)',
  cyan:    'var(--green)',
  magenta: 'var(--purple)',
  red:     'var(--red)',
};
const getStageBorderColor = (antColor: string): string =>
  STAGE_BORDER_COLOR[antColor] || 'var(--g300)';

// ---------------------------------------------------------------------------
// Evidence Display
// ---------------------------------------------------------------------------

const EvidenceDisplay: React.FC<{ evidence: unknown }> = ({ evidence }) => {
  if (!evidence) return null;

  if (Array.isArray(evidence)) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {evidence.map((item: any, idx: number) => (
          <div key={idx} style={{
            background: 'var(--g50)', padding: '10px 16px', borderRadius: 'var(--radius-sm)',
            fontSize: 12, lineHeight: 1.6,
            borderLeft: `3px solid ${item.score != null
              ? (item.score >= 4 ? 'var(--green)' : item.score >= 2 ? 'var(--amber)' : 'var(--red)')
              : 'var(--g300)'}`,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              {(item.signal_name || item.name) && (
                <Text style={{ fontWeight: 600, fontSize: 12 }}>{item.signal_name || item.name}</Text>
              )}
              {item.score != null && (
                <Tag color={item.score >= 4 ? 'green' : item.score >= 2 ? 'gold' : 'red'} style={{ fontSize: 10 }}>
                  {item.score}/5
                </Tag>
              )}
            </div>
            {item.description && <div style={{ color: 'var(--g600)' }}>{item.description}</div>}
            {item.source_url && (
              <a href={item.source_url} target="_blank" rel="noreferrer" style={{ fontSize: 11, color: 'var(--purple)' }}>
                <LinkOutlined style={{ marginRight: 4 }} />
                {item.source_url.length > 60 ? item.source_url.substring(0, 60) + '...' : item.source_url}
              </a>
            )}
          </div>
        ))}
      </div>
    );
  }

  if (typeof evidence === 'object' && evidence !== null) {
    const obj = evidence as Record<string, unknown>;
    const keys = Object.keys(obj);

    const firmographicKeys = new Set([
      'revenue', 'employees', 'capability_fit', 'low_cost_center',
      'industry', 'geography', 'employee_count', 'revenue_range',
    ]);
    const isFirmographic = keys.some(k => firmographicKeys.has(k));

    const formatCriterionValue = (key: string, val: unknown): React.ReactNode => {
      if (val == null) return <Text type="secondary">N/A</Text>;
      if (typeof val !== 'object') return <Text>{String(val)}</Text>;

      const criterion = val as Record<string, unknown>;

      if ('match' in criterion) {
        const matched = Boolean(criterion.match);
        return (
          <div style={{ background: 'var(--g50)', padding: '8px 12px', borderRadius: 'var(--radius-sm)', fontSize: 12, lineHeight: 1.6, display: 'flex', flexDirection: 'column', gap: 4 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Text style={{ fontWeight: 600, fontSize: 12 }}>
                {key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
              </Text>
              <Tag color={matched ? 'green' : 'red'} style={{ fontSize: 10 }}>{matched ? 'Match' : 'No Match'}</Tag>
            </div>
            {!!criterion.reasoning && <Text style={{ color: 'var(--g600)', fontSize: 12 }}>{String(criterion.reasoning)}</Text>}
          </div>
        );
      }

      if ('value' in criterion) {
        const inRange = 'in_range' in criterion ? Boolean(criterion.in_range) : null;
        const value = criterion.value;
        const source = criterion.source ? String(criterion.source) : null;
        let displayValue = String(value);
        if (typeof value === 'number') {
          if (key.toLowerCase().includes('revenue')) {
            displayValue = value >= 1_000_000_000
              ? `$${(value / 1_000_000_000).toFixed(1)}B`
              : value >= 1_000_000
                ? `$${(value / 1_000_000).toFixed(0)}M`
                : `$${value.toLocaleString()}`;
          } else {
            displayValue = value.toLocaleString();
          }
        }
        return (
          <div style={{ background: 'var(--g50)', padding: '8px 12px', borderRadius: 'var(--radius-sm)', fontSize: 12, lineHeight: 1.6, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Text style={{ fontWeight: 600, fontSize: 12 }}>{key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}:</Text>
            <Text style={{ fontSize: 12 }}>{displayValue}</Text>
            {inRange != null && <Tag color={inRange ? 'green' : 'red'} style={{ fontSize: 10 }}>{inRange ? 'In Range' : 'Out of Range'}</Tag>}
            {source && <Tag style={{ fontSize: 10 }}>{source}</Tag>}
          </div>
        );
      }

      const boolKey = Object.keys(criterion).find(k => typeof criterion[k] === 'boolean');
      if (boolKey) {
        const boolVal = Boolean(criterion[boolKey]);
        const source = criterion.source ? String(criterion.source) : null;
        return (
          <div style={{ background: 'var(--g50)', padding: '8px 12px', borderRadius: 'var(--radius-sm)', fontSize: 12, lineHeight: 1.6, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Text style={{ fontWeight: 600, fontSize: 12 }}>{key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}:</Text>
            <Tag color={boolVal ? 'green' : 'default'} style={{ fontSize: 10 }}>{boolVal ? 'Yes' : 'No'}</Tag>
            {source && <Tag style={{ fontSize: 10 }}>{source}</Tag>}
          </div>
        );
      }

      return (
        <div style={{ background: 'var(--g50)', padding: '8px 12px', borderRadius: 'var(--radius-sm)', fontSize: 12, lineHeight: 1.6 }}>
          <Text style={{ fontWeight: 600, fontSize: 12, display: 'block', marginBottom: 4 }}>
            {key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
          </Text>
          {Object.entries(criterion).map(([subKey, subVal]) => (
            <div key={subKey} style={{ display: 'flex', gap: 6, marginBottom: 2 }}>
              <Text type="secondary" style={{ fontSize: 11 }}>{subKey.replace(/_/g, ' ')}:</Text>
              <Text style={{ fontSize: 11 }}>{typeof subVal === 'object' ? JSON.stringify(subVal) : String(subVal)}</Text>
            </div>
          ))}
        </div>
      );
    };

    if (isFirmographic || keys.length > 0) {
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {keys.map(key => (
            <React.Fragment key={key}>{formatCriterionValue(key, obj[key])}</React.Fragment>
          ))}
        </div>
      );
    }
  }

  return (
    <pre style={{ margin: 0, fontSize: 11, whiteSpace: 'pre-wrap', wordBreak: 'break-word', background: 'var(--g50)', padding: '8px 12px', borderRadius: 'var(--radius-sm)' }}>
      {typeof evidence === 'string' ? evidence : JSON.stringify(evidence, null, 2)}
    </pre>
  );
};

// ---------------------------------------------------------------------------
// Dimension Score Tags
// ---------------------------------------------------------------------------

const DIMENSION_LABELS: Record<string, string> = {
  offering_fit: 'Offering', geography_fit: 'Geography', industry_fit: 'Industry',
  size_fit: 'Size', tech_maturity: 'Tech', infra_readiness: 'Infra',
  transformation_drivers: 'Transformation', leadership_fit: 'Leadership',
  priority_areas: 'Priority Areas',
};

const DimensionScoreTags: React.FC<{ rawData: Record<string, unknown> | null | undefined }> = ({ rawData }) => {
  if (!rawData) return null;
  const evidence = (rawData.dimension_evidence || rawData) as Record<string, unknown>;
  const rendered: React.ReactNode[] = [];
  Object.entries(DIMENSION_LABELS).forEach(([key, label]) => {
    const dim = evidence[key] as Record<string, unknown> | undefined;
    if (!dim) return;
    const score = typeof dim.score === 'number' ? dim.score : null;
    const dimEvidence = (dim.evidence || dim.reasoning || '') as string;
    if (score === null) return;
    const color = score === 2 ? 'green' : score === 1 ? 'gold' : 'default';
    rendered.push(
      <Tooltip key={key} title={dimEvidence || `${label}: ${score}/2`}>
        <Tag color={color} style={{ fontSize: 11, marginBottom: 3 }}>{label} ({score}/2)</Tag>
      </Tooltip>
    );
  });
  if (rendered.length === 0) return null;
  // Rendered inside a Card with title "Dimension Scores" — no extra label or margin needed
  return <div style={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>{rendered}</div>;
};

// ---------------------------------------------------------------------------
// Stage Results renderer (shared by fit & signal tabs)
// ---------------------------------------------------------------------------

const StageResultsPanel: React.FC<{ stageResults: CompanyStageResult[]; emptyText?: string; hideScore?: boolean }> = ({
  stageResults,
  emptyText = 'No results available for this stage.',
  hideScore = false,
}) => {
  if (stageResults.length === 0) {
    return (
      <Card style={{ textAlign: 'center', padding: '32px 24px' }}>
        <Text type="secondary">{emptyText}</Text>
      </Card>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {stageResults.map(result => {
        const display = getStageDisplay(result.stage);
        const statusColor = result.status === 'passed' ? 'green'
          : result.status === 'failed' ? 'red'
          : result.status === 'skipped' ? 'default' : 'blue';

        return (
          <Card key={result.id} size="small" style={{ borderLeft: `3px solid ${getStageBorderColor(display.color)}` }}>
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: (result.reasoning || result.evidence != null) ? 10 : 0 }}>
              <Tag color={display.color} style={{ fontSize: 11 }}>{display.label}</Tag>
              <Tag color={statusColor} style={{ fontSize: 11 }}>
                {result.status.charAt(0).toUpperCase() + result.status.slice(1)}
              </Tag>
              {!hideScore && result.score != null && (
                <Text style={{ fontSize: 12, fontWeight: 600, color: getScoreColor(result.score) }}>
                  Score: {Math.round(result.score)}/100
                </Text>
              )}
            </div>

            {/* Reasoning */}
            {result.reasoning && (
              <div style={{
                background: 'var(--g50)', padding: '8px 12px',
                borderRadius: 'var(--radius-sm)', fontSize: 12, color: 'var(--g700)',
                lineHeight: 1.7, marginBottom: result.evidence != null ? 10 : 0,
              }}>
                <Text type="secondary" style={{ fontSize: 11, fontWeight: 600 }}>Reasoning: </Text>
                {result.reasoning}
              </div>
            )}

            {/* Evidence */}
            {result.evidence != null && (
              <div>
                <Text type="secondary" style={{ fontSize: 11, fontWeight: 600, marginBottom: 6, display: 'block' }}>Evidence</Text>
                <EvidenceDisplay evidence={result.evidence} />
              </div>
            )}
          </Card>
        );
      })}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Tab: Contacts
// ---------------------------------------------------------------------------

const ConfidenceDots: React.FC<{ confidence: number; contact: Contact }> = ({ confidence, contact }) => {
  const score = Math.round(confidence * 100);
  const filled = confidence >= 0.75 ? 4 : confidence >= 0.5 ? 3 : confidence >= 0.25 ? 2 : 1;
  const accentColor = score >= 75 ? 'var(--green)' : score >= 50 ? 'var(--amber)' : 'var(--red)';
  const level = score >= 75 ? 'High' : score >= 50 ? 'Medium' : 'Low';

  // Confidence is source-based: how many independent external sources verified this contact
  const verificationLabel =
    confidence >= 0.90 ? 'Verified by 3+ independent data sources' :
    confidence >= 0.75 ? 'Verified by 2 independent data sources' :
    confidence >= 0.55 ? 'Found in 1 external data source' :
    confidence >= 0.35 ? 'Based on AI knowledge — not externally verified' :
    'Email inferred from domain pattern';

  const sourceLabel = contact.source
    ? contact.source.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
    : null;

  const tooltipContent = (
    <div style={{ maxWidth: 230 }}>
      <div style={{ fontWeight: 600, marginBottom: 6, fontSize: 12 }}>
        {level} Confidence — {score}/100
      </div>
      <div style={{ fontSize: 11, lineHeight: 1.6, marginBottom: 6 }}>
        {verificationLabel}
      </div>
      {sourceLabel && (
        <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.7)' }}>
          Source: {sourceLabel}
        </div>
      )}
      <div style={{ borderTop: '1px solid rgba(255,255,255,0.15)', marginTop: 8, paddingTop: 8, fontSize: 10, color: 'rgba(255,255,255,0.5)', lineHeight: 1.5 }}>
        Score reflects how many tools independently confirmed this contact, not the amount of data fields present.
      </div>
    </div>
  );

  return (
    <Tooltip title={tooltipContent} placement="bottom">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'help' }}>
        <div style={{ display: 'flex', gap: 4 }}>
          {[0, 1, 2, 3].map(i => (
            <div key={i} style={{
              width: 8, height: 8, borderRadius: '50%',
              background: i < filled ? accentColor : 'var(--g200)',
            }} />
          ))}
        </div>
        <div style={{
          width: 28, height: 28, borderRadius: '50%',
          background: accentColor,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontWeight: 700, fontSize: 11, color: '#fff',
        }}>
          {score}
        </div>
      </div>
    </Tooltip>
  );
};

const ContactInfoRow: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
  <div style={{
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '9px 0', borderBottom: '1px solid var(--g200)',
  }}>
    <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--g400)', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
      {label}
    </span>
    <span style={{ fontSize: 12, color: 'var(--g800)', textAlign: 'right', maxWidth: '65%', wordBreak: 'break-all' }}>
      {children}
    </span>
  </div>
);

const ContactsTab: React.FC<{ contacts: Contact[] }> = ({ contacts }) => {
  if (contacts.length === 0) {
    return (
      <Card style={{ textAlign: 'center', padding: '32px 24px' }}>
        <Text type="secondary">No contacts found for this company.</Text>
      </Card>
    );
  }

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
      gap: 16,
    }}>
      {contacts.map(contact => {
        const displayName = contact.full_name
          || [contact.first_name, contact.last_name].filter(Boolean).join(' ')
          || '—';

        return (
          <div key={contact.id} style={{
            background: '#fff',
            borderRadius: 'var(--radius)',
            padding: '14px 16px',
            boxShadow: 'var(--shadow)',
            border: '1px solid var(--g200)',
            display: 'flex',
            flexDirection: 'column',
          }}>
            {/* Header: name + designation */}
            <div style={{ marginBottom: 6 }}>
              <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--g900)', lineHeight: 1.3 }}>
                {displayName}
              </div>
              {(contact.designation || contact.role_category) && (
                <div style={{ marginTop: 4, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                  {contact.designation && (
                    <span style={{
                      display: 'inline-block', fontSize: 11,
                      background: 'var(--g100)', color: 'var(--g600)',
                      borderRadius: 20, padding: '1px 8px',
                    }}>
                      {contact.designation}
                    </span>
                  )}
                  {contact.role_category && contact.role_category !== contact.designation && (
                    <span style={{
                      display: 'inline-block', fontSize: 11,
                      background: 'var(--g100)', color: 'var(--g600)',
                      borderRadius: 20, padding: '1px 8px',
                    }}>
                      {contact.role_category}
                    </span>
                  )}
                </div>
              )}
            </div>

            {/* Info rows */}
            <ContactInfoRow label="LinkedIn">
              {contact.linkedin_url
                ? <a href={contact.linkedin_url} target="_blank" rel="noreferrer" style={{ color: 'var(--purple)', textDecoration: 'none' }}>
                    Profile&nbsp;↗
                  </a>
                : <span style={{ color: 'var(--g300)' }}>—</span>}
            </ContactInfoRow>

            <ContactInfoRow label="Email">
              {contact.email
                ? <a href={`mailto:${contact.email}`} style={{ color: 'var(--purple)', textDecoration: 'none' }}>
                    {contact.email}
                  </a>
                : <span style={{ color: 'var(--g300)' }}>—</span>}
            </ContactInfoRow>

            <ContactInfoRow label="Phone">
              {contact.phone
                ? <a href={`tel:${contact.phone}`} style={{ color: 'var(--purple)', textDecoration: 'none' }}>
                    {contact.phone}
                  </a>
                : <span style={{ color: 'var(--g300)' }}>—</span>}
            </ContactInfoRow>

            {/* Secondary fields */}
            {contact.city && (
              <ContactInfoRow label="Location">
                <span style={{ color: 'var(--g600)' }}>{contact.city}</span>
              </ContactInfoRow>
            )}
            {/* Footer: confidence dots + score */}
            {contact.confidence != null && (
              <div style={{ marginTop: 20 }}>
                <ConfidenceDots confidence={contact.confidence} contact={contact} />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Tab: Overview
// ---------------------------------------------------------------------------

const OverviewTab: React.FC<{ company: Company }> = ({ company }) => {
  const matchScore = company.icp_match_score;

  const techStack = company.tech_stack_json;
  const techItems: string[] = Array.isArray(techStack) ? techStack.map(String) : [];

  const fmtRevenue = (v: number | null | undefined) => {
    if (!v) return null;
    if (v >= 1_000_000_000) return `$${(v / 1_000_000_000).toFixed(1)}B`;
    if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(0)}M`;
    return `$${v.toLocaleString()}`;
  };

  const revenueStr = fmtRevenue(company.revenue_estimate);
  const assetStr = fmtRevenue(company.asset_value);

  const scoreItems = [
    { label: 'Match Score', value: matchScore, color: getScoreColor(matchScore), formatted: matchScore != null ? `${Math.round(matchScore)}/100` : null },
    { label: 'Final Score', value: company.final_score, color: getScoreColor(company.final_score), formatted: company.final_score != null ? `${Math.round(company.final_score)}/100` : null },
    { label: 'Budget Signal', value: company.budget_signal_score, color: getScoreColor(company.budget_signal_score), formatted: company.budget_signal_score != null ? `${Math.round(company.budget_signal_score)}/100` : null },
    { label: 'Urgency Signal', value: company.urgency_signal_score, color: getScoreColor(company.urgency_signal_score), formatted: company.urgency_signal_score != null ? `${Math.round(company.urgency_signal_score)}/100` : null },
  ].filter(s => s.formatted !== null);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Company Details */}
      <Card size="small" title="Company Details">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 16 }}>
          {company.industry && (
            <div>
              <Text type="secondary" style={{ fontSize: 11 }}>Industry</Text>
              <div style={{ fontWeight: 600, fontSize: 13 }}>{company.industry}</div>
            </div>
          )}
          {company.sub_industry && (
            <div>
              <Text type="secondary" style={{ fontSize: 11 }}>Sub-Industry</Text>
              <div style={{ fontWeight: 600, fontSize: 13 }}>{company.sub_industry}</div>
            </div>
          )}
          {company.country && (
            <div>
              <Text type="secondary" style={{ fontSize: 11 }}>Country</Text>
              <div style={{ fontWeight: 600, fontSize: 13 }}>{company.country}</div>
            </div>
          )}
          {(company.city || company.state_region) && (
            <div>
              <Text type="secondary" style={{ fontSize: 11 }}>Location</Text>
              <div style={{ fontWeight: 600, fontSize: 13 }}>{[company.city, company.state_region].filter(Boolean).join(', ')}</div>
            </div>
          )}
          {company.employee_count != null && (
            <div>
              <Text type="secondary" style={{ fontSize: 11 }}>Employees</Text>
              <div style={{ fontWeight: 600, fontSize: 13 }}>{company.employee_count.toLocaleString()}</div>
            </div>
          )}
          {revenueStr && (
            <div>
              <Text type="secondary" style={{ fontSize: 11 }}>Revenue Estimate</Text>
              <div style={{ fontWeight: 600, fontSize: 13 }}>{revenueStr}</div>
            </div>
          )}
          {assetStr && (
            <div>
              <Text type="secondary" style={{ fontSize: 11 }}>Asset Value</Text>
              <div style={{ fontWeight: 600, fontSize: 13 }}>{assetStr}</div>
            </div>
          )}
          {company.website && (
            <div>
              <Text type="secondary" style={{ fontSize: 11 }}>Website</Text>
              <div>
                <a
                  href={company.website.startsWith('http') ? company.website : `https://${company.website}`}
                  target="_blank" rel="noreferrer"
                  style={{ fontSize: 13, color: 'var(--purple)' }}
                >
                  <LinkOutlined style={{ marginRight: 4 }} />{company.website}
                </a>
              </div>
            </div>
          )}
          {company.source && (
            <div>
              <Text type="secondary" style={{ fontSize: 11 }}>Source</Text>
              <div style={{ fontWeight: 600, fontSize: 13 }}>{company.source}</div>
            </div>
          )}
          {company.qualification && (
            <div>
              <Text type="secondary" style={{ fontSize: 11 }}>Qualification</Text>
              <div>
                <Tag color={
                  company.qualification === 'qualified' || company.qualification === 'verified_match' || company.qualification === 'best_fit' ? 'green' :
                  company.qualification === 'good_fit' || company.qualification === 'potential_match' ? 'blue' :
                  company.qualification === 'possible_fit' || company.qualification === 'weak_match' ? 'gold' :
                  company.qualification === 'disqualified' || company.qualification === 'not_qualified' ? 'red' : 'default'
                } style={{ fontSize: 12 }}>
                  {company.qualification.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                </Tag>
              </div>
            </div>
          )}
        </div>
        {company.description && (
          <div style={{ marginTop: 16, padding: '10px 14px', background: 'var(--g50)', borderRadius: 'var(--radius-sm)', fontSize: 12, color: 'var(--g700)', lineHeight: 1.7 }}>
            {company.description}
          </div>
        )}
      </Card>

      {/* Scores */}
      {scoreItems.length > 0 && (
        <Card size="small" title="Scores">
          <div style={{ display: 'flex', gap: 32, flexWrap: 'wrap', alignItems: 'flex-start' }}>
            {scoreItems.map(s => (
              <Tooltip key={s.label} title={`${s.label}: ${getScoreLabel(s.value as number)}`}>
                <div>
                  <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 2 }}>{s.label}</Text>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                    <span style={{ fontWeight: 700, fontSize: 22, color: s.color, lineHeight: 1 }}>{s.formatted?.replace('/100', '')}</span>
                    <Text type="secondary" style={{ fontSize: 12 }}>/100</Text>
                  </div>
                  <Tag color={getScoreTagColor(s.value as number)} style={{ fontSize: 10, marginTop: 4 }}>
                    {getScoreLabel(s.value as number)}
                  </Tag>
                </div>
              </Tooltip>
            ))}
            {company.final_rank != null && (
              <div>
                <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 2 }}>Rank</Text>
                <div style={{ fontWeight: 700, fontSize: 22, color: 'var(--purple)', lineHeight: 1 }}>#{company.final_rank}</div>
              </div>
            )}
          </div>
        </Card>
      )}

      {/* Tech Stack */}
      {techItems.length > 0 && (
        <Card size="small" title="Tech Stack">
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {techItems.map((t, i) => <Tag key={i} color="blue" style={{ fontSize: 12, marginBottom: 3 }}>{t}</Tag>)}
          </div>
        </Card>
      )}

      {/* Dimension Scores */}
      {company.raw_data_json && (
        <Card size="small" title="Dimension Scores">
          <DimensionScoreTags rawData={company.raw_data_json} />
        </Card>
      )}

      {/* Match Reasoning */}
      {company.match_reasoning && (
        <Card size="small" title="Match Reasoning">
          <div style={{ fontSize: 13, color: 'var(--g700)', lineHeight: 1.7 }}>
            {company.match_reasoning}
          </div>
        </Card>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Tab: Discovery & Fit  (Industry Discovery + Firmographic Fit)
// ---------------------------------------------------------------------------

const DiscoveryFitTab: React.FC<{ company: Company }> = ({ company }) => {
  const stageOrder = ['industry_discovery', 'company_discovery', 'firmographic_fit'];
  const results = [...(company.stage_results || [])]
    .filter(r =>
      stageOrder.includes(r.stage) &&
      !r.user_override &&
      !r.reasoning?.toLowerCase().includes('firmographic review') &&
      !r.reasoning?.toLowerCase().includes('deselected')
    )
    .sort((a, b) => stageOrder.indexOf(a.stage) - stageOrder.indexOf(b.stage));

  return (
    <StageResultsPanel
      stageResults={results}
      emptyText="No discovery or firmographic fit results available for this company."
    />
  );
};

// ---------------------------------------------------------------------------
// Tab: Budget Signals
// ---------------------------------------------------------------------------

const BudgetSignalsTab: React.FC<{ company: Company }> = ({ company }) => {
  const results = (company.stage_results || []).filter(
    r => r.stage === 'budget_signals' || r.stage === 'budget_signal'
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {company.budget_signal_score != null && (
        <Card size="small">
          <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
            <div>
              <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 4 }}>Budget Signal Score</Text>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
                <span style={{ fontWeight: 700, fontSize: 28, color: getScoreColor(company.budget_signal_score), lineHeight: 1 }}>
                  {Math.round(company.budget_signal_score)}
                </span>
                <Text type="secondary" style={{ fontSize: 13 }}>/100</Text>
              </div>
            </div>
            <Tag color={getScoreTagColor(company.budget_signal_score)} style={{ fontSize: 12, padding: '2px 10px' }}>
              {getScoreLabel(company.budget_signal_score)}
            </Tag>
          </div>
        </Card>
      )}
      <StageResultsPanel
        stageResults={results}
        emptyText="No budget signal results available for this company."
        hideScore
      />
    </div>
  );
};

// ---------------------------------------------------------------------------
// Tab: Urgency Signals
// ---------------------------------------------------------------------------

const UrgencySignalsTab: React.FC<{ company: Company }> = ({ company }) => {
  const results = (company.stage_results || []).filter(
    r => r.stage === 'urgency_signals' || r.stage === 'urgency_signal'
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {company.urgency_signal_score != null && (
        <Card size="small">
          <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
            <div>
              <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 4 }}>Urgency Signal Score</Text>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
                <span style={{ fontWeight: 700, fontSize: 28, color: getScoreColor(company.urgency_signal_score), lineHeight: 1 }}>
                  {Math.round(company.urgency_signal_score)}
                </span>
                <Text type="secondary" style={{ fontSize: 13 }}>/100</Text>
              </div>
            </div>
            <Tag color={getScoreTagColor(company.urgency_signal_score)} style={{ fontSize: 12, padding: '2px 10px' }}>
              {getScoreLabel(company.urgency_signal_score)}
            </Tag>
          </div>
        </Card>
      )}
      <StageResultsPanel
        stageResults={results}
        emptyText="No urgency signal results available for this company."
        hideScore
      />
    </div>
  );
};

// ---------------------------------------------------------------------------
// Main CompanyDetailPage
// ---------------------------------------------------------------------------

const CompanyDetailPage: React.FC = () => {
  const { runId, companyId } = useParams<{ runId: string; companyId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const { setCompanyId } = usePageContext();

  const [company, setCompany] = useState<Company | null>(
    (location.state as any)?.company ?? null
  );
  const icpName: string | null = (location.state as any)?.icp_name ?? null;
  const [loading, setLoading] = useState(!company);
  const [activeTab, setActiveTab] = useState<'contacts' | 'overview' | 'discovery_fit' | 'budget_signals' | 'urgency_signals'>('overview');

  // Discovery state
  const [discoveryRunning, setDiscoveryRunning] = useState(false);
  const [discoveryType, setDiscoveryType] = useState<'signals' | 'contacts' | null>(null);
  const [discoveryProgress, setDiscoveryProgress] = useState('');
  const [discoveryLog, setDiscoveryLog] = useState<{ type: string; text: string }[]>([]);
  const [signalTypeChoice, setSignalTypeChoice] = useState<'budget_signals' | 'urgency_signals' | 'both'>('both');
  const eventSourceRef = useRef<EventSource | null>(null);
  const [showLog, setShowLog] = useState(false);

  // Set co-pilot context
  useEffect(() => {
    if (companyId) setCompanyId(companyId);
    return () => setCompanyId(null);
  }, [companyId, setCompanyId]);

  // Fallback: fetch from API if navigated directly (no state)
  useEffect(() => {
    if (company || !runId || !companyId) return;
    setLoading(true);
    getSingleCompany(runId, companyId)
      .then(res => setCompany(res.data as Company))
      .catch(() => setCompany(null))
      .finally(() => setLoading(false));
  }, [runId, companyId, company]);

  // Cleanup EventSource on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) eventSourceRef.current.close();
    };
  }, []);

  // localStorage helpers for persisting discovery state across navigation/refresh
  const discoveryStorageKey = companyId ? `qlgen:discovery:${companyId}` : null;

  const saveDiscoveryState = useCallback((kind: 'signals' | 'contacts') => {
    if (!discoveryStorageKey) return;
    try {
      localStorage.setItem(discoveryStorageKey, JSON.stringify({ type: kind, startedAt: Date.now() }));
    } catch { /* quota errors etc */ }
  }, [discoveryStorageKey]);

  const clearDiscoveryState = useCallback(() => {
    if (!discoveryStorageKey) return;
    try { localStorage.removeItem(discoveryStorageKey); } catch { /* */ }
  }, [discoveryStorageKey]);

  const readDiscoveryState = useCallback((): { type: 'signals' | 'contacts' } | null => {
    if (!discoveryStorageKey) return null;
    try {
      const raw = localStorage.getItem(discoveryStorageKey);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      // Ignore entries older than 2 hours (matching event store TTL)
      if (Date.now() - parsed.startedAt > 2 * 60 * 60 * 1000) {
        localStorage.removeItem(discoveryStorageKey);
        return null;
      }
      return { type: parsed.type };
    } catch {
      return null;
    }
  }, [discoveryStorageKey]);

  // Connect to an active discovery SSE stream (shared by start + resume)
  const connectToStream = useCallback((kind: 'signals' | 'contacts', isResume = false) => {
    if (!runId || !companyId) return;

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    const streamUrl = getDiscoveryStreamUrl(runId, companyId, kind);
    const es = new EventSource(streamUrl);
    eventSourceRef.current = es;

    // For resumes: if no events arrive within 8s, the discovery is likely gone
    let receivedAnyEvent = false;
    let safetyTimeout: ReturnType<typeof setTimeout> | null = null;
    if (isResume) {
      safetyTimeout = setTimeout(() => {
        if (!receivedAnyEvent) {
          es.close();
          eventSourceRef.current = null;
          setDiscoveryRunning(false);
          setDiscoveryType(null);
          setDiscoveryProgress('');
          clearDiscoveryState();
        }
      }, 8000);
    }
    const markEvent = () => {
      receivedAnyEvent = true;
      if (safetyTimeout) { clearTimeout(safetyTimeout); safetyTimeout = null; }
    };

    es.addEventListener('stage_update', (event) => {
      markEvent();
      const data = JSON.parse(event.data);
      setDiscoveryProgress(data.message || 'Researching...');
      setDiscoveryLog(prev => [...prev, { type: 'stage', text: data.message || '' }]);
    });

    es.addEventListener('tool_start', (event) => {
      markEvent();
      const data = JSON.parse(event.data);
      const displayName = data.display_name || data.tool_name || '';
      setDiscoveryProgress(displayName);
      setDiscoveryLog(prev => [...prev, { type: 'tool', text: `${displayName}${data.context ? ': ' + data.context : ''}` }]);
    });

    es.addEventListener('agent_reasoning', (event) => {
      markEvent();
      const data = JSON.parse(event.data);
      if (data.text) {
        setDiscoveryLog(prev => [...prev, { type: 'reasoning', text: data.text }]);
      }
    });

    es.addEventListener('completed', async (event) => {
      markEvent();
      const data = JSON.parse(event.data);
      es.close();
      eventSourceRef.current = null;
      setDiscoveryProgress('');
      setDiscoveryRunning(false);
      setDiscoveryType(null);
      clearDiscoveryState();

      try {
        const res = await getSingleCompany(runId!, companyId!);
        setCompany(res.data as Company);
        if (kind === 'signals') {
          message.success(`Signal discovery complete! Budget: ${data.budget_signal_score ?? 'N/A'}, Urgency: ${data.urgency_signal_score ?? 'N/A'}`);
        } else {
          message.success(`Contact discovery complete! ${data.contacts_found ?? 0} contacts found.`);
        }
      } catch {
        message.success('Discovery complete! Refresh the page to see results.');
      }
    });

    // Server-sent "error" events (backend explicitly reports failure via SSE)
    es.addEventListener('error', (event: Event) => {
      // Only handle server-sent error events (MessageEvent), not native connection errors.
      // Native errors are handled by es.onerror which allows EventSource auto-reconnect.
      if (!(event instanceof MessageEvent)) return;
      let msg = 'Discovery failed';
      try { msg = JSON.parse(event.data)?.message || msg; } catch { /* */ }
      es.close();
      eventSourceRef.current = null;
      setDiscoveryRunning(false);
      setDiscoveryType(null);
      setDiscoveryProgress('');
      clearDiscoveryState();
      message.error(msg);
    });

    // Native connection errors — let EventSource auto-reconnect handle transient issues.
    // Only reset state if the connection stays dead after 5s.
    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED) return;
      setTimeout(() => {
        if (es.readyState === EventSource.CLOSED) {
          setDiscoveryRunning(false);
          setDiscoveryType(null);
          setDiscoveryProgress('');
          clearDiscoveryState();
        }
      }, 5000);
    };
  }, [runId, companyId, clearDiscoveryState]);

  // Resume active discovery on mount (survives navigation & page refresh)
  useEffect(() => {
    if (!runId || !companyId || discoveryRunning || loading) return;

    let cancelled = false;

    // First check localStorage for a discovery we started
    const stored = readDiscoveryState();

    // Then verify against the backend status endpoint
    getDiscoveryStatus(runId, companyId)
      .then(res => {
        if (cancelled) return;
        const status = res.data;
        // Determine which (if any) discovery is actively running
        let activeKind: 'signals' | 'contacts' | null = null;
        if (status.signals === 'running') activeKind = 'signals';
        else if (status.contacts === 'running') activeKind = 'contacts';
        // Also check localStorage hint (backend might not have events yet if just started)
        else if (stored && status[stored.type] !== 'completed') activeKind = stored.type;

        if (activeKind) {
          setDiscoveryRunning(true);
          setDiscoveryType(activeKind);
          setDiscoveryProgress('Resuming...');
          setDiscoveryLog([]);
          connectToStream(activeKind, true);
        } else {
          // No active discovery — clean up stale localStorage if any
          clearDiscoveryState();
          // If a discovery completed while we were away, refresh data
          if (status.signals === 'completed' || status.contacts === 'completed') {
            getSingleCompany(runId, companyId)
              .then(r => { if (!cancelled) setCompany(r.data as Company); })
              .catch(() => {});
          }
        }
      })
      .catch(() => {
        if (cancelled) return;
        // Status endpoint failed — fall back to localStorage hint
        if (stored) {
          setDiscoveryRunning(true);
          setDiscoveryType(stored.type);
          setDiscoveryProgress('Resuming...');
          setDiscoveryLog([]);
          connectToStream(stored.type, true);
        }
      });

    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId, companyId, loading]);

  const handleStartDiscovery = useCallback(async (kind: 'signals' | 'contacts') => {
    if (!runId || !companyId || discoveryRunning) return;

    setDiscoveryRunning(true);
    setDiscoveryType(kind);
    setDiscoveryProgress('Initializing...');
    setDiscoveryLog([]);
    saveDiscoveryState(kind);

    try {
      if (kind === 'signals') {
        await discoverCompanySignals(runId, companyId, signalTypeChoice);
      } else {
        await discoverCompanyContacts(runId, companyId);
      }

      connectToStream(kind);
    } catch {
      setDiscoveryRunning(false);
      setDiscoveryType(null);
      setDiscoveryProgress('');
      clearDiscoveryState();
      message.error('Failed to start discovery');
    }
  }, [runId, companyId, discoveryRunning, signalTypeChoice, connectToStream, saveDiscoveryState, clearDiscoveryState]);

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 300 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!company) {
    return (
      <div style={{ padding: '28px 32px' }}>
        <Button size="small" onClick={() => navigate(`/leads/${runId}`)} style={{ marginBottom: 16 }}>&larr; Back</Button>
        <div style={{ textAlign: 'center', color: 'var(--g400)', padding: 40 }}>Company not found.</div>
      </div>
    );
  }

  // Count stage results per tab for badges
  const fitStages = new Set(['industry_discovery', 'company_discovery', 'firmographic_fit', 'firmographic_filter']);
  const fitCount = (company.stage_results || []).filter(r => fitStages.has(r.stage) && !r.user_override).length;
  const budgetResults = (company.stage_results || []).filter(r => r.stage === 'budget_signals' || r.stage === 'budget_signal');
  const budgetCount = budgetResults.reduce((sum, r) => sum + Object.keys(r.evidence || {}).length, 0);
  const urgencyResults = (company.stage_results || []).filter(r => r.stage === 'urgency_signals' || r.stage === 'urgency_signal');
  const urgencyCount = urgencyResults.reduce((sum, r) => sum + Object.keys(r.evidence || {}).length, 0);

  const tabs: { key: typeof activeTab; label: string }[] = [
    { key: 'overview',       label: 'Overview' },
    { key: 'contacts',       label: `Contacts${company.contacts.length ? ` (${company.contacts.length})` : ''}` },
    { key: 'discovery_fit',  label: `Discovery & Fit${fitCount ? ` (${fitCount})` : ''}` },
    { key: 'budget_signals', label: `Budget Signals${budgetCount ? ` (${budgetCount})` : ''}` },
    { key: 'urgency_signals',label: `Urgency Signals${urgencyCount ? ` (${urgencyCount})` : ''}` },
  ];

  return (
    <div style={{ padding: '28px 32px', maxWidth: 1400, margin: '0 auto', width: '100%' }}>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <div className="section-label">Lead Generation</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <Button
            size="small"
            onClick={() => navigate(`/leads/${runId}`)}
            style={{ fontSize: 12 }}
          >
            &larr; Back to Results
          </Button>
          <h1 className="page-title" style={{ margin: 0 }}>{company.name}</h1>
          {icpName && (
            <Tag color="purple" style={{ fontSize: 13, padding: '2px 12px' }}>{icpName}</Tag>
          )}
          {company.website && (
            <a
              href={company.website.startsWith('http') ? company.website : `https://${company.website}`}
              target="_blank" rel="noreferrer"
              style={{ fontSize: 14, color: 'var(--purple)', lineHeight: 1 }}
            >
              <LinkOutlined />
            </a>
          )}
          {company.final_rank != null && (
            <Tag color="purple" style={{ fontSize: 12, padding: '2px 10px' }}>#{company.final_rank}</Tag>
          )}
          {company.final_score != null && (
            <Tooltip title={getScoreLabel(company.final_score)}>
              <Tag color={getScoreTagColor(company.final_score)} style={{ fontSize: 12, padding: '2px 10px', fontWeight: 700 }}>
                Score: {Math.round(company.final_score)}/100
              </Tag>
            </Tooltip>
          )}
        </div>

        {/* Industry / country meta tags */}
        {(company.industry || company.country) && (
          <div style={{ marginTop: 8, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {company.industry && <Tag style={{ fontSize: 12 }}>{company.industry}</Tag>}
            {company.country && <Tag style={{ fontSize: 12 }}>{company.country}</Tag>}
          </div>
        )}
      </div>

      {/* Discovery CTA / Progress */}
      {(() => {
        const hasBudget = company.budget_signal_score != null;
        const hasUrgency = company.urgency_signal_score != null;
        const hasContacts = (company.contacts?.length ?? 0) > 0;
        const missingSignals = !hasBudget || !hasUrgency;

        if (discoveryRunning) {
          return (
            <div style={{
              marginBottom: 12, padding: '8px 16px',
              background: 'var(--g50, #fafafa)', borderRadius: 8,
              borderLeft: '3px solid var(--amber, #e0820a)',
              fontSize: 12,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <LoadingOutlined spin style={{ color: 'var(--amber, #e0820a)' }} />
                  <Text style={{ fontWeight: 600, fontSize: 12 }}>
                    {discoveryType === 'contacts' ? 'Contact' : 'Signal'} Discovery
                  </Text>
                  <Text type="secondary" style={{ fontSize: 11 }}>
                    {discoveryProgress || 'Working...'}
                  </Text>
                </div>
                <Button type="text" size="small" onClick={() => setShowLog(prev => !prev)} style={{ fontSize: 11 }}>
                  {showLog ? 'Hide log' : 'Show log'}
                </Button>
              </div>
              {showLog && (
                <div style={{
                  maxHeight: 120, overflowY: 'auto', fontSize: 10,
                  marginTop: 6, padding: '4px 8px',
                  background: '#fff', borderRadius: 4,
                }}>
                  {discoveryLog.map((entry, i) => (
                    <div key={i} style={{ marginBottom: 2, display: 'flex', gap: 6 }}>
                      <span style={{
                        fontWeight: 600,
                        color: entry.type === 'tool' ? 'var(--purple, #5C2D8F)' : entry.type === 'stage' ? 'var(--green, #1E9B6B)' : 'var(--g400, #bfbfbf)',
                        minWidth: 36,
                      }}>
                        {entry.type === 'tool' ? 'TOOL' : entry.type === 'stage' ? 'STAGE' : 'AI'}
                      </span>
                      <span>{entry.text}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        }

        if (missingSignals || !hasContacts) {
          return (
            <Card size="small" style={{ marginBottom: 16, borderLeft: '3px solid var(--purple, #5C2D8F)' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
                <div>
                  <Text style={{ fontWeight: 600, fontSize: 13 }}>
                    <ThunderboltOutlined style={{ marginRight: 6, color: 'var(--purple, #5C2D8F)' }} />
                    On-Demand Discovery
                  </Text>
                  <div style={{ fontSize: 12, color: 'var(--g500, #8c8c8c)', marginTop: 2 }}>
                    {missingSignals && !hasContacts
                      ? 'Signals and contacts have not been discovered for this company.'
                      : missingSignals
                        ? `${!hasBudget && !hasUrgency ? 'Budget and urgency signals' : !hasBudget ? 'Budget signals' : 'Urgency signals'} not yet researched.`
                        : 'No contacts found for this company.'}
                  </div>
                </div>
                <Space wrap>
                  {missingSignals && (
                    <>
                      <Select
                        value={signalTypeChoice}
                        onChange={setSignalTypeChoice}
                        style={{ width: 180 }}
                        size="small"
                        options={[
                          { value: 'both', label: 'Budget & Urgency' },
                          { value: 'budget_signals', label: 'Budget Only' },
                          { value: 'urgency_signals', label: 'Urgency Only' },
                        ]}
                      />
                      <Button type="primary" icon={<ThunderboltOutlined />} onClick={() => handleStartDiscovery('signals')} size="small">
                        Discover Signals
                      </Button>
                    </>
                  )}
                  {!hasContacts && (
                    <Button icon={<TeamOutlined />} onClick={() => handleStartDiscovery('contacts')} size="small">
                      Discover Contacts
                    </Button>
                  )}
                </Space>
              </div>
            </Card>
          );
        }

        return null;
      })()}

      {/* Tab navigation — matches LeadsPage pattern */}
      <div className="tabs">
        {tabs.map(t => (
          <div
            key={t.key}
            className={`tab ${activeTab === t.key ? 'active' : ''}`}
            onClick={() => setActiveTab(t.key)}
          >
            {t.label}
          </div>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'contacts' && (
        <div>
          {(company.contacts?.length ?? 0) > 0 && !discoveryRunning && (
            <div style={{ marginBottom: 12, textAlign: 'right' }}>
              <Button size="small" type="text" icon={<TeamOutlined />}
                onClick={() => handleStartDiscovery('contacts')}
                style={{ fontSize: 11, color: 'var(--g400, #bfbfbf)' }}
              >
                Re-discover Contacts
              </Button>
            </div>
          )}
          <ContactsTab contacts={company.contacts} />
        </div>
      )}
      {activeTab === 'overview'        && <OverviewTab company={company} />}
      {activeTab === 'discovery_fit'   && <DiscoveryFitTab company={company} />}
      {activeTab === 'budget_signals' && (
        <div>
          {company.budget_signal_score != null && !discoveryRunning && (
            <div style={{ marginBottom: 12, textAlign: 'right' }}>
              <Button size="small" type="text" icon={<ThunderboltOutlined />}
                onClick={() => { setSignalTypeChoice('budget_signals'); handleStartDiscovery('signals'); }}
                style={{ fontSize: 11, color: 'var(--g400, #bfbfbf)' }}
              >
                Re-discover
              </Button>
            </div>
          )}
          <BudgetSignalsTab company={company} />
        </div>
      )}
      {activeTab === 'urgency_signals' && (
        <div>
          {company.urgency_signal_score != null && !discoveryRunning && (
            <div style={{ marginBottom: 12, textAlign: 'right' }}>
              <Button size="small" type="text" icon={<ThunderboltOutlined />}
                onClick={() => { setSignalTypeChoice('urgency_signals'); handleStartDiscovery('signals'); }}
                style={{ fontSize: 11, color: 'var(--g400, #bfbfbf)' }}
              >
                Re-discover
              </Button>
            </div>
          )}
          <UrgencySignalsTab company={company} />
        </div>
      )}
    </div>
  );
};

export default CompanyDetailPage;
