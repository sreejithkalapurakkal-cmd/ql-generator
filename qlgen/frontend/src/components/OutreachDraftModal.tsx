import React, { useState } from 'react';
import { Modal, Button, Spin, message } from 'antd';
import { SendOutlined, CopyOutlined, EditOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { generateOutreachDraft } from '../api/briefApi';

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

  const handleGenerate = async () => {
    setOpen(true);
    setLoading(true);
    setDraft(null);
    try {
      const res = await generateOutreachDraft(companyKbId, {
        contact_name: contactName,
      });
      setDraft(res.data.draft);
    } catch {
      message.error('Failed to generate outreach draft');
      setDraft('**Error:** Draft generation failed. Please try again.');
    } finally {
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
        onCancel={() => setOpen(false)}
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
