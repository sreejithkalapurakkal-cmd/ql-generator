import React, { useState, useEffect, useCallback } from 'react';
import { Drawer, Tooltip, Spin, Select, message } from 'antd';
import {
  CloseOutlined, MailOutlined, LinkedinOutlined,
  ThunderboltOutlined, CopyOutlined, SendOutlined,
  DeleteOutlined, ReloadOutlined, CheckCircleFilled,
  LinkOutlined,
} from '@ant-design/icons';
import { useDraftDrawer } from '../context/DraftDrawerContext';
import { generateDraft, updateDraft } from '../api/briefApi';
import client from '../api/client';
import type { DraftFormat, DraftTone } from '../types';

type VoiceProfile = 'concise' | 'consultative' | 'formal';

const FORMAT_OPTIONS: { key: DraftFormat; label: string; icon: React.ReactNode }[] = [
  { key: 'email', label: 'Email', icon: <MailOutlined /> },
  { key: 'linkedin', label: 'LinkedIn', icon: <LinkedinOutlined /> },
];

const TONE_OPTIONS: { key: DraftTone; label: string }[] = [
  { key: 'direct', label: 'Direct' },
  { key: 'consultative', label: 'Consultative' },
  { key: 'formal', label: 'Formal' },
  { key: 'casual', label: 'Casual' },
];

const VOICE_OPTIONS: { key: VoiceProfile; label: string; desc: string }[] = [
  { key: 'concise', label: 'Concise', desc: 'Short, punchy, no fluff' },
  { key: 'consultative', label: 'Consultative', desc: 'Value-led, advisory tone' },
  { key: 'formal', label: 'Formal', desc: 'Professional, enterprise-grade' },
];

const CHAR_LIMITS: Record<DraftFormat, number> = {
  email: 2000,
  linkedin: 600,
};

const DraftDrawer: React.FC = () => {
  const { isOpen, options, closeDraftDrawer } = useDraftDrawer();

  // Form state
  const [format, setFormat] = useState<DraftFormat>('email');
  const [tone, setTone] = useState<DraftTone>('direct');
  const [voice, setVoice] = useState<VoiceProfile>('concise');
  const [contactName, setContactName] = useState('');
  const [contactTitle, setContactTitle] = useState('');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [draftId, setDraftId] = useState<string | null>(null);

  // Contact picker state
  const [contacts, setContacts] = useState<any[]>([]);
  const [manualContactEntry, setManualContactEntry] = useState(false);

  // UI state
  const [generating, setGenerating] = useState(false);
  const [edited, setEdited] = useState(false);
  const [copied, setCopied] = useState(false);
  const [sentConfirm, setSentConfirm] = useState(false);

  // Reset form when options change
  useEffect(() => {
    if (options) {
      setFormat(options.format || 'email');
      setTone(options.tone || 'direct');
      setVoice('concise');
      setContactName(options.contactName || '');
      setContactTitle(options.contactTitle || '');
      setSubject('');
      setBody('');
      setDraftId(null);
      setEdited(false);
      setCopied(false);
      setSentConfirm(false);
      setManualContactEntry(false);
    }
  }, [options]);

  // Fetch contacts when drawer opens
  useEffect(() => {
    if (options?.companyKbId) {
      client.get(`/contacts/${options.companyKbId}`).then(res => {
        setContacts(res.data.contacts || []);
      }).catch(() => {
        setContacts([]);
      });
    }
  }, [options?.companyKbId]);

  // Auto-generate on open
  useEffect(() => {
    if (isOpen && options && !body && !generating) {
      handleGenerate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, options]);

  const handleGenerate = useCallback(async () => {
    if (!options) return;
    setGenerating(true);
    setEdited(false);
    try {
      const res = await generateDraft(options.companyKbId, {
        contact_name: contactName || options.contactName || undefined,
        contact_title: contactTitle || options.contactTitle || undefined,
        format,
        tone,
        signal_id: options.signalId || undefined,
        context: options.signalTitle
          ? `This outreach is anchored to the signal: "${options.signalTitle}". Reference this signal naturally in the opening.`
          : undefined,
      });
      setSubject(res.data.subject || '');
      setBody(res.data.body || res.data.raw_markdown || '');
      setDraftId(res.data.id);
    } catch {
      message.error('Failed to generate draft');
    } finally {
      setGenerating(false);
    }
  }, [options, contactName, contactTitle, format, tone]);

  const handleCopy = () => {
    const text = format === 'email' && subject
      ? `Subject: ${subject}\n\n${body}`
      : body;
    navigator.clipboard.writeText(text);
    setCopied(true);
    message.success('Copied to clipboard');
    setTimeout(() => setCopied(false), 2000);
  };

  const handleMarkSent = async () => {
    if (!draftId) return;
    if (!sentConfirm) {
      setSentConfirm(true);
      return;
    }
    try {
      await updateDraft(draftId, { status: 'sent' });
      message.success('Draft marked as sent');
      closeDraftDrawer();
    } catch {
      message.error('Failed to update draft');
    }
  };

  const handleDiscard = async () => {
    if (draftId) {
      try {
        await updateDraft(draftId, { status: 'discarded' });
      } catch { /* ignore */ }
    }
    closeDraftDrawer();
  };

  const handleSaveEdits = async () => {
    if (!draftId) return;
    try {
      await updateDraft(draftId, { subject: subject || undefined, body });
      setEdited(false);
      message.success('Draft saved');
    } catch {
      message.error('Failed to save');
    }
  };

  const charCount = body.length;
  const charLimit = CHAR_LIMITS[format];
  const isOverLimit = charCount > charLimit;

  return (
    <Drawer
      open={isOpen}
      onClose={closeDraftDrawer}
      width={580}
      closable={false}
      styles={{ body: { padding: 0 }, header: { display: 'none' } }}
      maskClosable
    >
      <div className="flex flex-col h-full">
        {/* Header */}
        <div className="shrink-0 px-6 pt-5 pb-4 border-b border-gray-100">
          <div className="flex items-start justify-between gap-3 mb-3">
            <div>
              <h2 className="text-base font-bold text-gray-900">Draft Outreach</h2>
              {options?.companyName && (
                <div className="flex items-center gap-1.5 mt-1">
                  <span className="text-sm font-medium text-brand">{options.companyName}</span>
                  {options.domain && (
                    <span className="text-xs text-gray-400 flex items-center gap-0.5">
                      <LinkOutlined className="text-[10px]" />{options.domain}
                    </span>
                  )}
                </div>
              )}
            </div>
            <button
              onClick={closeDraftDrawer}
              className="w-8 h-8 flex items-center justify-center rounded-md text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
            >
              <CloseOutlined />
            </button>
          </div>

          {/* Agent attribution */}
          <div className="flex items-center gap-2 mb-3">
            <span className="inline-flex items-center gap-1 text-[10px] font-semibold bg-brand-bg text-brand px-2 py-0.5 rounded-full">
              <ThunderboltOutlined className="text-[9px]" /> Outreach Agent
            </span>
            {options?.signalTitle && (
              <Tooltip title={`Signal-anchored: ${options.signalTitle}`}>
                <span className="inline-flex items-center gap-1 text-[10px] font-medium bg-amber-50 text-amber-700 px-2 py-0.5 rounded-full truncate max-w-[300px]">
                  <ThunderboltOutlined className="text-[9px]" />
                  {options.signalType || 'Signal'}: {options.signalTitle.slice(0, 60)}{options.signalTitle.length > 60 ? '...' : ''}
                </span>
              </Tooltip>
            )}
          </div>

          {/* Format toggle */}
          <div className="flex items-center gap-1.5 mb-3">
            <span className="text-xs text-gray-400 mr-1">Format:</span>
            {FORMAT_OPTIONS.map((opt) => (
              <button
                key={opt.key}
                onClick={() => setFormat(opt.key)}
                className={`flex items-center gap-1.5 h-8 px-3 text-xs font-semibold rounded-lg transition-colors ${
                  format === opt.key
                    ? 'bg-brand text-white'
                    : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                }`}
              >
                {opt.icon} {opt.label}
              </button>
            ))}
          </div>

          {/* Tone pills */}
          <div className="flex items-center gap-1.5 mb-3">
            <span className="text-xs text-gray-400 mr-1">Tone:</span>
            {TONE_OPTIONS.map((opt) => (
              <button
                key={opt.key}
                onClick={() => setTone(opt.key)}
                className={`h-7 px-3 text-[11px] font-semibold rounded-full transition-colors ${
                  tone === opt.key
                    ? 'bg-brand-pale text-brand'
                    : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {/* Voice selector */}
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-gray-400 mr-1">Voice:</span>
            {VOICE_OPTIONS.map((opt) => (
              <Tooltip key={opt.key} title={opt.desc}>
                <button
                  onClick={() => setVoice(opt.key)}
                  className={`h-7 px-3 text-[11px] font-semibold rounded-full transition-colors ${
                    voice === opt.key
                      ? 'bg-gray-800 text-white'
                      : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                  }`}
                >
                  {opt.label}
                </button>
              </Tooltip>
            ))}
          </div>
        </div>

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {generating ? (
            <div className="flex flex-col items-center justify-center py-16 gap-3">
              <Spin size="large" />
              <p className="text-sm text-gray-500">Generating {format === 'linkedin' ? 'LinkedIn message' : 'email draft'}...</p>
              <p className="text-xs text-gray-400">Analyzing signals and company data</p>
            </div>
          ) : (
            <>
              {/* Contact fields */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-1">Contact Name</label>
                  {contacts.length > 0 && !manualContactEntry ? (
                    <div>
                      <Select
                        placeholder="Select contact"
                        style={{ width: '100%' }}
                        value={contactName || undefined}
                        onChange={(val) => {
                          const c = contacts.find((c: any) => c.name === val);
                          setContactName(val);
                          setContactTitle(c?.title || '');
                        }}
                        allowClear
                        showSearch
                        optionFilterProp="label"
                        options={contacts.map((c: any) => ({
                          value: c.name,
                          label: `${c.name} — ${c.title || 'Unknown role'}`,
                        }))}
                      />
                      <button
                        onClick={() => setManualContactEntry(true)}
                        className="text-[10px] text-brand hover:underline mt-1"
                      >
                        or enter manually
                      </button>
                    </div>
                  ) : (
                    <div>
                      <input
                        value={contactName}
                        onChange={(e) => setContactName(e.target.value)}
                        placeholder="e.g. Sarah Chen"
                        className="w-full h-9 px-3 text-sm border border-gray-200 rounded-lg focus:border-brand focus:ring-1 focus:ring-brand/30 outline-none transition-colors"
                      />
                      {contacts.length > 0 && manualContactEntry && (
                        <button
                          onClick={() => setManualContactEntry(false)}
                          className="text-[10px] text-brand hover:underline mt-1"
                        >
                          pick from contacts
                        </button>
                      )}
                    </div>
                  )}
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-1">Title</label>
                  <input
                    value={contactTitle}
                    onChange={(e) => setContactTitle(e.target.value)}
                    placeholder="e.g. VP Engineering"
                    className="w-full h-9 px-3 text-sm border border-gray-200 rounded-lg focus:border-brand focus:ring-1 focus:ring-brand/30 outline-none transition-colors"
                  />
                </div>
              </div>

              {/* Subject (email only) */}
              {format === 'email' && (
                <div>
                  <label className="block text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-1">Subject</label>
                  <input
                    value={subject}
                    onChange={(e) => { setSubject(e.target.value); setEdited(true); }}
                    placeholder="Email subject line..."
                    className="w-full h-9 px-3 text-sm border border-gray-200 rounded-lg focus:border-brand focus:ring-1 focus:ring-brand/30 outline-none transition-colors"
                  />
                </div>
              )}

              {/* Body */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide">
                    {format === 'linkedin' ? 'Message' : 'Body'}
                  </label>
                  <span className={`text-[11px] font-mono ${isOverLimit ? 'text-red-500 font-bold' : 'text-gray-400'}`}>
                    {charCount}/{charLimit}
                  </span>
                </div>
                <textarea
                  value={body}
                  onChange={(e) => { setBody(e.target.value); setEdited(true); }}
                  rows={format === 'linkedin' ? 8 : 12}
                  className={`w-full px-3 py-2.5 text-sm border rounded-lg focus:ring-1 outline-none transition-colors resize-y leading-relaxed ${
                    isOverLimit
                      ? 'border-red-300 focus:border-red-400 focus:ring-red-200'
                      : 'border-gray-200 focus:border-brand focus:ring-brand/30'
                  }`}
                  placeholder={`Write your ${format === 'linkedin' ? 'LinkedIn message' : 'email'}...`}
                />
                {isOverLimit && (
                  <p className="text-xs text-red-500 mt-1">
                    {format === 'linkedin' ? 'LinkedIn messages' : 'Emails'} should stay under {charLimit} characters
                  </p>
                )}
              </div>

              {/* Edited draft notice */}
              {edited && draftId && (
                <div className="flex items-center gap-2 px-3 py-2 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-700">
                  <span>Draft has unsaved edits</span>
                  <button
                    onClick={handleSaveEdits}
                    className="font-semibold underline hover:no-underline"
                  >
                    Save changes
                  </button>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        {!generating && body && (
          <div className="shrink-0 px-6 py-3 border-t border-gray-100 bg-white">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {/* Regenerate */}
                <Tooltip title="Generate a new draft with current settings">
                  <button
                    onClick={handleGenerate}
                    className="flex items-center gap-1.5 h-8 px-3 text-xs font-medium rounded-md border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 transition-colors"
                  >
                    <ReloadOutlined /> Regenerate
                  </button>
                </Tooltip>

                {/* Copy */}
                <button
                  onClick={handleCopy}
                  className={`flex items-center gap-1.5 h-8 px-3 text-xs font-medium rounded-md border transition-colors ${
                    copied
                      ? 'border-green-200 bg-green-50 text-green-700'
                      : 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  {copied ? <CheckCircleFilled /> : <CopyOutlined />}
                  {copied ? 'Copied' : 'Copy'}
                </button>

                {/* Discard */}
                <button
                  onClick={handleDiscard}
                  className="flex items-center gap-1.5 h-8 px-3 text-xs font-medium rounded-md border border-gray-200 bg-white text-red-500 hover:bg-red-50 hover:border-red-200 transition-colors"
                >
                  <DeleteOutlined /> Discard
                </button>
              </div>

              {/* Mark as Sent */}
              <button
                onClick={handleMarkSent}
                className={`flex items-center gap-1.5 h-9 px-4 text-xs font-semibold rounded-lg transition-colors ${
                  sentConfirm
                    ? 'bg-green-600 text-white hover:bg-green-700'
                    : 'bg-brand text-white hover:bg-brand-dark'
                }`}
              >
                <SendOutlined />
                {sentConfirm ? 'Confirm Sent?' : 'Mark as Sent'}
              </button>
            </div>
          </div>
        )}
      </div>
    </Drawer>
  );
};

export default DraftDrawer;
