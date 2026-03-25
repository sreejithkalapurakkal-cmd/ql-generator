import React from 'react';
import { Tag, Typography, Tooltip } from 'antd';
import { LinkOutlined } from '@ant-design/icons';

const { Text } = Typography;

// ---------------------------------------------------------------------------
// Recency badge helper
// ---------------------------------------------------------------------------

export const getRecencyBadge = (months: number | null | undefined): { label: string; color: string } => {
  if (months == null) return { label: '', color: 'default' };
  if (months < 1) return { label: 'Fresh', color: 'green' };
  if (months <= 3) return { label: 'Recent', color: 'blue' };
  if (months <= 6) return { label: 'Aging', color: 'orange' };
  return { label: 'Stale', color: 'red' };
};

// ---------------------------------------------------------------------------
// EvidenceSignalSummary — compact inline summary for table cells
// ---------------------------------------------------------------------------

export const EvidenceSignalSummary: React.FC<{
  evidence: unknown;
  maxSignals?: number;
}> = ({ evidence, maxSignals = 2 }) => {
  if (!Array.isArray(evidence) || evidence.length === 0) return null;

  const signals = evidence as Array<Record<string, any>>;
  const shown = signals.slice(0, maxSignals);
  const remaining = signals.length - shown.length;

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
      {shown.map((item, idx) => {
        const name = item.signal_name || item.name;
        if (!name) return null;
        const scoreColor = item.score != null
          ? (item.score >= 4 ? 'green' : item.score >= 2 ? 'gold' : 'red')
          : 'default';
        return (
          <Tooltip key={idx} title={item.description || `${name}: ${item.score ?? '?'}/5`}>
            <Tag
              color={scoreColor}
              style={{ fontSize: 10, marginBottom: 0, lineHeight: '18px' }}
            >
              {name.length > 24 ? name.substring(0, 22) + '...' : name}
              {item.score != null && ` ${item.score}/5`}
            </Tag>
          </Tooltip>
        );
      })}
      {remaining > 0 && (
        <Tag style={{ fontSize: 10, marginBottom: 0, lineHeight: '18px' }} color="default">
          +{remaining} more
        </Tag>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// EvidenceDisplay — full evidence renderer
// ---------------------------------------------------------------------------

export const EvidenceDisplay: React.FC<{ evidence: unknown }> = ({ evidence }) => {
  if (!evidence) return null;

  // Handle array of signal objects
  if (Array.isArray(evidence)) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {evidence.map((item: any, idx: number) => (
          <div key={idx} style={{
            background: '#f6f8fa', padding: '10px 16px', borderRadius: 8,
            fontSize: 12, lineHeight: 1.6,
            borderLeft: `3px solid ${item.score != null ? (item.score >= 4 ? '#52c41a' : item.score >= 2 ? '#faad14' : '#ff4d4f') : '#d9d9d9'}`,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              {item.signal_name || item.name ? (
                <Text style={{ fontWeight: 600, fontSize: 12 }}>
                  {item.signal_name || item.name}
                </Text>
              ) : null}
              {item.score != null && (
                <Tag color={item.score >= 4 ? 'green' : item.score >= 2 ? 'gold' : 'red'} style={{ fontSize: 10 }}>
                  {item.score}/5
                </Tag>
              )}
            </div>
            {item.description && (
              <div style={{ color: 'var(--g600)' }}>{item.description}</div>
            )}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              {item.source_url && (
                <a href={item.source_url} target="_blank" rel="noreferrer" style={{ fontSize: 11, color: 'var(--purple)' }}>
                  <LinkOutlined style={{ marginRight: 4 }} />
                  {item.source_url.length > 60 ? item.source_url.substring(0, 60) + '...' : item.source_url}
                </a>
              )}
              {item.evidence_date && (
                <Tag style={{ fontSize: 10 }}>
                  {new Date(item.evidence_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                </Tag>
              )}
              {item.recency_months != null && (() => {
                const badge = getRecencyBadge(item.recency_months);
                return badge.label ? <Tag color={badge.color} style={{ fontSize: 10 }}>{badge.label}</Tag> : null;
              })()}
            </div>
          </div>
        ))}
      </div>
    );
  }

  // Handle object evidence (e.g. firmographic per_criterion)
  if (typeof evidence === 'object' && evidence !== null) {
    const obj = evidence as Record<string, unknown>;
    const keys = Object.keys(obj);

    // Known firmographic criterion keys
    const firmographicKeys = new Set([
      'revenue', 'employees', 'capability_fit', 'low_cost_center',
      'industry', 'geography', 'employee_count', 'revenue_range',
    ]);
    const isFirmographic = keys.some(k => firmographicKeys.has(k));

    const formatCriterionValue = (key: string, val: unknown): React.ReactNode => {
      if (val == null) return <Text type="secondary">N/A</Text>;
      if (typeof val !== 'object') return <Text>{String(val)}</Text>;

      const criterion = val as Record<string, unknown>;

      // capability_fit shape: { match: bool, reasoning: string }
      if ('match' in criterion) {
        const matched = Boolean(criterion.match);
        return (
          <div style={{
            background: '#f6f8fa', padding: '8px 12px', borderRadius: 6,
            fontSize: 12, lineHeight: 1.6, display: 'flex', flexDirection: 'column', gap: 4,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Text style={{ fontWeight: 600, fontSize: 12 }}>
                {key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
              </Text>
              <Tag color={matched ? 'green' : 'red'} style={{ fontSize: 10 }}>
                {matched ? 'Match' : 'No Match'}
              </Tag>
            </div>
            {!!criterion.reasoning && (
              <Text style={{ color: 'var(--g600)', fontSize: 12 }}>{String(criterion.reasoning)}</Text>
            )}
          </div>
        );
      }

      // Numeric criterion shape: { value: number, in_range: bool, source: string }
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
          <div style={{
            background: '#f6f8fa', padding: '8px 12px', borderRadius: 6,
            fontSize: 12, lineHeight: 1.6, display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <Text style={{ fontWeight: 600, fontSize: 12 }}>
              {key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}:
            </Text>
            <Text style={{ fontSize: 12 }}>{displayValue}</Text>
            {inRange != null && (
              <Tag color={inRange ? 'green' : 'red'} style={{ fontSize: 10 }}>
                {inRange ? 'In Range' : 'Out of Range'}
              </Tag>
            )}
            {source && <Tag style={{ fontSize: 10 }}>{source}</Tag>}
          </div>
        );
      }

      // Boolean criterion shape: { has_center: bool, source: string } or similar
      const boolKey = Object.keys(criterion).find(k => typeof criterion[k] === 'boolean');
      if (boolKey) {
        const boolVal = Boolean(criterion[boolKey]);
        const source = criterion.source ? String(criterion.source) : null;
        return (
          <div style={{
            background: '#f6f8fa', padding: '8px 12px', borderRadius: 6,
            fontSize: 12, lineHeight: 1.6, display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <Text style={{ fontWeight: 600, fontSize: 12 }}>
              {key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}:
            </Text>
            <Tag color={boolVal ? 'green' : 'default'} style={{ fontSize: 10 }}>
              {boolVal ? 'Yes' : 'No'}
            </Tag>
            {source && <Tag style={{ fontSize: 10 }}>{source}</Tag>}
          </div>
        );
      }

      // Unknown nested object — render as labeled key-value pairs
      return (
        <div style={{
          background: '#f6f8fa', padding: '8px 12px', borderRadius: 6,
          fontSize: 12, lineHeight: 1.6,
        }}>
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
          {keys.map((key) => (
            <React.Fragment key={key}>
              {formatCriterionValue(key, obj[key])}
            </React.Fragment>
          ))}
        </div>
      );
    }
  }

  // Fallback: formatted JSON
  return (
    <pre style={{
      margin: 0, fontSize: 11, whiteSpace: 'pre-wrap',
      wordBreak: 'break-word', background: '#f6f8fa',
      padding: '8px 12px', borderRadius: 6,
    }}>
      {typeof evidence === 'string' ? evidence : JSON.stringify(evidence, null, 2)}
    </pre>
  );
};
