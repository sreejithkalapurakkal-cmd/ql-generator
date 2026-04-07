import React, { useState } from 'react';
import { Popover } from 'antd';
import {
  QuestionCircleOutlined,
  BookOutlined,
  MessageOutlined,
  UnorderedListOutlined,
} from '@ant-design/icons';
import FeedbackFormModal from './FeedbackFormModal';
import MySubmissionsModal from './MySubmissionsModal';

const HelpMenu: React.FC = () => {
  const [popoverOpen, setPopoverOpen] = useState(false);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [submissionsOpen, setSubmissionsOpen] = useState(false);

  const menuItemStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '8px 12px',
    cursor: 'pointer',
    borderRadius: 6,
    transition: 'background 0.2s',
    fontSize: 14,
  };

  const content = (
    <div style={{ minWidth: 200 }}>
      <div
        style={menuItemStyle}
        onMouseEnter={(e) => (e.currentTarget.style.background = '#f5f0fa')}
        onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
        onClick={() => {
          window.open('/qlGen-User-Guide.pdf', '_blank');
          setPopoverOpen(false);
        }}
      >
        <BookOutlined style={{ fontSize: 16, color: '#5C2D8F' }} />
        <span>User Guide</span>
      </div>
      <div
        style={menuItemStyle}
        onMouseEnter={(e) => (e.currentTarget.style.background = '#f5f0fa')}
        onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
        onClick={() => {
          setFeedbackOpen(true);
          setPopoverOpen(false);
        }}
      >
        <MessageOutlined style={{ fontSize: 16, color: '#5C2D8F' }} />
        <span>Submit Feedback</span>
      </div>
      <div
        style={menuItemStyle}
        onMouseEnter={(e) => (e.currentTarget.style.background = '#f5f0fa')}
        onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
        onClick={() => {
          setSubmissionsOpen(true);
          setPopoverOpen(false);
        }}
      >
        <UnorderedListOutlined style={{ fontSize: 16, color: '#5C2D8F' }} />
        <span>My Submissions</span>
      </div>
    </div>
  );

  return (
    <>
      <Popover
        content={content}
        trigger="click"
        placement="bottomRight"
        open={popoverOpen}
        onOpenChange={setPopoverOpen}
        arrow={false}
        overlayInnerStyle={{ padding: 6 }}
      >
        <QuestionCircleOutlined
          style={{
            fontSize: 18,
            color: popoverOpen ? '#5C2D8F' : 'rgba(0,0,0,0.45)',
            cursor: 'pointer',
            transition: 'color 0.2s',
          }}
          onMouseEnter={(e) => {
            if (!popoverOpen) e.currentTarget.style.color = '#5C2D8F';
          }}
          onMouseLeave={(e) => {
            if (!popoverOpen) e.currentTarget.style.color = 'rgba(0,0,0,0.45)';
          }}
        />
      </Popover>

      <FeedbackFormModal open={feedbackOpen} onClose={() => setFeedbackOpen(false)} />
      <MySubmissionsModal open={submissionsOpen} onClose={() => setSubmissionsOpen(false)} />
    </>
  );
};

export default HelpMenu;
