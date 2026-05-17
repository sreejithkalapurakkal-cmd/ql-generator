import React, { useState } from 'react';
import { Modal, Button, Spin, message } from 'antd';
import { FileTextOutlined, CopyOutlined, PrinterOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { generateBrief } from '../api/briefApi';

interface CompanyBriefModalProps {
  companyKbId: string;
  companyName?: string;
  trigger?: React.ReactNode;
}

const CompanyBriefModal: React.FC<CompanyBriefModalProps> = ({
  companyKbId, companyName, trigger,
}) => {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [brief, setBrief] = useState<string | null>(null);

  const handleGenerate = async () => {
    setOpen(true);
    setLoading(true);
    setBrief(null);
    try {
      const res = await generateBrief(companyKbId);
      setBrief(res.data.brief);
    } catch {
      message.error('Failed to generate brief');
      setBrief('**Error:** Brief generation failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    if (brief) {
      navigator.clipboard.writeText(brief);
      message.success('Brief copied to clipboard');
    }
  };

  const handlePrint = () => {
    const printWindow = window.open('', '_blank');
    if (printWindow && brief) {
      printWindow.document.write(`
        <html>
          <head>
            <title>Account Brief - ${companyName || 'Company'}</title>
            <style>
              body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; color: #333; line-height: 1.6; }
              h1 { font-size: 22px; border-bottom: 2px solid #5C2D8F; padding-bottom: 8px; }
              h2 { font-size: 16px; margin-top: 24px; color: #5C2D8F; }
              table { border-collapse: collapse; width: 100%; margin: 12px 0; }
              th, td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; }
              th { background: #f5f5f5; font-weight: 600; }
              ul { padding-left: 20px; }
            </style>
          </head>
          <body>${brief}</body>
        </html>
      `);
      printWindow.document.close();
      printWindow.print();
    }
  };

  return (
    <>
      <span onClick={handleGenerate} className="cursor-pointer">
        {trigger || (
          <Button icon={<FileTextOutlined />} size="small" className="!rounded-md">
            Brief
          </Button>
        )}
      </span>

      <Modal
        title={`Account Brief${companyName ? `: ${companyName}` : ''}`}
        open={open}
        onCancel={() => setOpen(false)}
        width={720}
        footer={brief ? [
          <Button key="copy" icon={<CopyOutlined />} onClick={handleCopy}>Copy</Button>,
          <Button key="print" icon={<PrinterOutlined />} onClick={handlePrint}>Print</Button>,
          <Button key="close" type="primary" onClick={() => setOpen(false)}>Close</Button>,
        ] : null}
        styles={{ body: { maxHeight: '70vh', overflow: 'auto' } }}
      >
        {loading ? (
          <div className="flex flex-col items-center justify-center py-16">
            <Spin size="large" />
            <p className="text-sm text-gray-400 mt-4">Generating brief...</p>
          </div>
        ) : brief ? (
          <div className="text-sm leading-relaxed">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{brief}</ReactMarkdown>
          </div>
        ) : null}
      </Modal>
    </>
  );
};

export default CompanyBriefModal;
