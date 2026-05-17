import React, { useEffect, useState } from 'react';
import { Button, Spin, Tooltip, message } from 'antd';
import {
  UserOutlined, ReloadOutlined, LinkOutlined,
} from '@ant-design/icons';
import { Badge, EmptyState } from './ui';
import { enrichMember, getMemberContacts } from '../api/trackingApi';
import type { EnrichedContact } from '../types';

interface ContactsPanelProps {
  listId: string;
  membershipId: string;
  companyName?: string;
  enrichmentStatus: string;
}

// ---------------------------------------------------------------------------
// Confidence display (matches CompanyDetailPage pattern)
// ---------------------------------------------------------------------------

const ConfidenceDots: React.FC<{ confidence: number; contact: EnrichedContact }> = ({ confidence, contact }) => {
  const score = Math.round(confidence * 100);
  const filled = confidence >= 0.75 ? 4 : confidence >= 0.5 ? 3 : confidence >= 0.25 ? 2 : 1;
  const accentColor = score >= 75 ? 'var(--green, #52c41a)' : score >= 50 ? 'var(--amber, #faad14)' : 'var(--red, #f5222d)';
  const level = score >= 75 ? 'High' : score >= 50 ? 'Medium' : 'Low';

  const verificationLabel =
    confidence >= 0.90 ? 'Verified by 3+ independent data sources' :
    confidence >= 0.75 ? 'Verified by 2 independent data sources' :
    confidence >= 0.55 ? 'Found in 1 external data source' :
    confidence >= 0.35 ? 'Based on AI knowledge — not externally verified' :
    'Email inferred from domain pattern';

  const sourceLabel = contact.source
    ? contact.source.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())
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
    </div>
  );

  return (
    <Tooltip title={tooltipContent} placement="bottom">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'help' }}>
        <div style={{ display: 'flex', gap: 4 }}>
          {[0, 1, 2, 3].map(i => (
            <div key={i} style={{
              width: 8, height: 8, borderRadius: '50%',
              background: i < filled ? accentColor : 'var(--g200, #e8e8e8)',
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

// ---------------------------------------------------------------------------
// Info row (matches CompanyDetailPage pattern)
// ---------------------------------------------------------------------------

const ContactInfoRow: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
  <div style={{
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '9px 0', borderBottom: '1px solid var(--g200, #e8e8e8)',
  }}>
    <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--g400, #bfbfbf)', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
      {label}
    </span>
    <span style={{ fontSize: 12, color: 'var(--g800, #262626)', textAlign: 'right', maxWidth: '65%', wordBreak: 'break-all' }}>
      {children}
    </span>
  </div>
);

// ---------------------------------------------------------------------------
// Main Panel
// ---------------------------------------------------------------------------

const ContactsPanel: React.FC<ContactsPanelProps> = ({
  listId, membershipId, companyName, enrichmentStatus: initialStatus,
}) => {
  const [contacts, setContacts] = useState<EnrichedContact[]>([]);
  const [loading, setLoading] = useState(false);
  const [enriching, setEnriching] = useState(false);
  const [status, setStatus] = useState(initialStatus);

  useEffect(() => { fetchContacts(); }, [listId, membershipId]);

  const fetchContacts = async () => {
    setLoading(true);
    try {
      const res = await getMemberContacts(listId, membershipId);
      setContacts(res.data.contacts || []);
      setStatus(res.data.enrichment_status);
    } catch {
      setContacts([]);
    } finally {
      setLoading(false);
    }
  };

  const handleEnrich = async () => {
    setEnriching(true);
    try {
      const res = await enrichMember(listId, membershipId);
      setContacts(res.data.contacts || []);
      setStatus('enriched');
      message.success(`Found ${res.data.contacts_found} contacts for ${companyName || 'company'}`);
    } catch {
      message.error('Contact enrichment failed');
      setStatus('failed');
    } finally {
      setEnriching(false);
    }
  };

  if (loading) {
    return <div className="flex justify-center py-5"><Spin size="small" /></div>;
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-gray-900">
          <UserOutlined className="text-gray-400" />
          Contacts
          {contacts.length > 0 && (
            <Badge variant="count">{contacts.length}</Badge>
          )}
        </div>
        <Button
          size="small"
          icon={status === 'enriched' ? <ReloadOutlined /> : <UserOutlined />}
          onClick={handleEnrich}
          loading={enriching}
          className="!rounded-md !text-xs"
        >
          {status === 'enriched' ? 'Re-enrich' : 'Find Contacts'}
        </Button>
      </div>

      {/* Contact cards */}
      {contacts.length === 0 ? (
        <EmptyState
          icon={<UserOutlined />}
          title={status === 'enriched' ? 'No contacts found' : 'No contacts yet'}
          description={
            status === 'enriched'
              ? 'No decision-maker contacts were found for this company.'
              : 'Click "Find Contacts" to discover decision-makers.'
          }
          className="py-6"
        />
      ) : (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
          gap: 16,
        }}>
          {contacts.map((contact, i) => {
            const displayName = contact.full_name || '—';

            return (
              <div key={`${contact.full_name}-${i}`} style={{
                background: '#fff',
                borderRadius: 'var(--radius, 8px)',
                padding: '14px 16px',
                boxShadow: 'var(--shadow, 0 1px 3px rgba(0,0,0,.08))',
                border: '1px solid var(--g200, #e8e8e8)',
                display: 'flex',
                flexDirection: 'column',
              }}>
                {/* Header: name + designation */}
                <div style={{ marginBottom: 6 }}>
                  <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--g900, #1a1a1a)', lineHeight: 1.3 }}>
                    {displayName}
                  </div>
                  {contact.designation && (
                    <div style={{ marginTop: 4, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                      <span style={{
                        display: 'inline-block', fontSize: 11,
                        background: 'var(--g100, #f5f5f5)', color: 'var(--g600, #595959)',
                        borderRadius: 20, padding: '1px 8px',
                      }}>
                        {contact.designation}
                      </span>
                    </div>
                  )}
                </div>

                {/* Info rows */}
                <ContactInfoRow label="LinkedIn">
                  {contact.linkedin_url
                    ? <a href={contact.linkedin_url} target="_blank" rel="noreferrer" style={{ color: 'var(--purple, #5C2D8F)', textDecoration: 'none' }}>
                        Profile&nbsp;<LinkOutlined style={{ fontSize: 10 }} />
                      </a>
                    : <span style={{ color: 'var(--g300, #d9d9d9)' }}>—</span>}
                </ContactInfoRow>

                <ContactInfoRow label="Email">
                  {contact.email
                    ? <a
                        href={`mailto:${contact.email}`}
                        style={{ color: 'var(--purple, #5C2D8F)', textDecoration: 'none' }}
                        onClick={(e) => {
                          e.preventDefault();
                          navigator.clipboard.writeText(contact.email!);
                          message.success('Email copied');
                        }}
                      >
                        {contact.email}
                      </a>
                    : <span style={{ color: 'var(--g300, #d9d9d9)' }}>—</span>}
                </ContactInfoRow>

                <ContactInfoRow label="Phone">
                  {contact.phone
                    ? <a href={`tel:${contact.phone}`} style={{ color: 'var(--purple, #5C2D8F)', textDecoration: 'none' }}>
                        {contact.phone}
                      </a>
                    : <span style={{ color: 'var(--g300, #d9d9d9)' }}>—</span>}
                </ContactInfoRow>

                {contact.city && (
                  <ContactInfoRow label="Location">
                    <span style={{ color: 'var(--g600, #595959)' }}>{contact.city}</span>
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
      )}
    </div>
  );
};

export default ContactsPanel;
