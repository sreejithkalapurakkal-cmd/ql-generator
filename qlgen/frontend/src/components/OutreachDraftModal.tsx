import React, { useState } from 'react';
import { Modal, Button, Spin, message } from 'antd';
import { CopyOutlined, EditOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { startOutreachGeneration, getOutreachStreamUrl } from '../api/briefApi';
import { useSSEStream } from '../hooks/useSSEStream';

interface OutreachDraftModalProps {
  companyKbId: string;
  companyName?: string;
  contactName?: string;
  trigger?: React.ReactNode;
}

const OutreachDraftModal: React.FC<OutreachDraftModalProps> = ({
  companyKbId, companyName, contactName, trigger,
}) => {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [draft, setDraft] = useState<string | null>(null);
  const [agentThought, setAgentThought] = useState('');

  const outreachStream = useSSEStream({
    terminalEvents: ['outreach_ready', 'outreach_failed'],
    onEvent: (eventType, data) => {
      if (eventType === 'agent_thought') {
        setAgentThought(data.message as string || '');
      }
    },
    onComplete: (eventType, data) => {
      if (eventType === 'outreach_ready') {
        setDraft((data.raw_markdown as string) || (data.body as string) || '');
        setLoading(false);
        setAgentThought('');
      } else {
        message.error((data.message as string) || 'Failed to generate outreach draft');
        setDraft('**Error:** Draft generation failed. Please try again.');
        setLoading(false);
        setAgentThought('');
      }
    },
    onError: () => {
      setLoading(false);
      setAgentThought('');
    },
  });

  const handleGenerate = async () => {
    setOpen(true);
    setLoading(true);
    setDraft(null);
    setAgentThought('');
    try {
      const res = await startOutreachGeneration(companyKbId, {
        contact_name: contactName,
      });
      const streamUrl = getOutreachStreamUrl(companyKbId, res.data.run_id);
      outreachStream.connect(streamUrl);
    } catch {
      message.error('Failed to start outreach draft generation');
      setDraft('**Error:** Draft generation failed. Please try again.');
      setLoading(false);
    }
  };

  const handleCopy = () => {
    if (!draft) return;
    // Extract just the email body (between the --- markers) for copying
    const parts = draft.split('---');
    const emailBody = parts.length >= 3 ? parts.slice(1, -1).join('---').trim() : draft;
    navigator.clipboard.writeText(emailBody);
    message.success('Email copied to clipboard');
  };

  const handleCopyAll = () => {
    if (draft) {
      navigator.clipboard.writeText(draft);
      message.success('Full draft copied to clipboard');
    }
  };

  return (
    <>
      <span onClick={handleGenerate} className="cursor-pointer">
        {trigger || (
          <Button icon={<EditOutlined />} size="small" className="!rounded-md">
            Draft Outreach
          </Button>
        )}
      </span>

      <Modal
        title={`Outreach Draft${companyName ? `: ${companyName}` : ''}`}
        open={open}
        onCancel={() => { setOpen(false); outreachStream.disconnect(); }}
        width={720}
        footer={draft ? [
          <Button key="copy-body" icon={<CopyOutlined />} onClick={handleCopy}>Copy Email</Button>,
          <Button key="copy-all" icon={<CopyOutlined />} onClick={handleCopyAll}>Copy All</Button>,
          <Button key="close" type="primary" onClick={() => setOpen(false)}>Close</Button>,
        ] : null}
        styles={{ body: { maxHeight: '70vh', overflow: 'auto' } }}
      >
        {loading ? (
          <div className="flex flex-col items-center justify-center py-16">
            <Spin size="large" />
            <p className="text-sm text-gray-400 mt-4">Crafting outreach email...</p>
            {agentThought && (
              <p className="text-xs text-purple-500 italic mt-2 animate-pulse max-w-sm text-center">{agentThought}</p>
            )}
            {outreachStream.progress > 0 && (
              <div className="w-48 mt-3">
                <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-purple-500 rounded-full transition-all duration-500 ease-out"
                    style={{ width: `${outreachStream.progress}%` }}
                  />
                </div>
                <p className="text-[10px] text-gray-400 text-center mt-1">{outreachStream.progress}%</p>
              </div>
            )}
          </div>
        ) : draft ? (
          <div className="text-sm leading-relaxed outreach-draft">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{draft}</ReactMarkdown>
          </div>
        ) : null}
      </Modal>
    </>
  );
};

export default OutreachDraftModal;
