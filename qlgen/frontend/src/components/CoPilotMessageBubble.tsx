import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface Props {
  role: 'user' | 'assistant';
  content: string;
  isStreaming?: boolean;
}

const CoPilotMessageBubble: React.FC<Props> = ({ role, content, isStreaming }) => {
  if (role === 'user') {
    return (
      <div className="copilot-msg user">
        <div className="copilot-msg-bubble user">{content}</div>
      </div>
    );
  }

  return (
    <div className="copilot-msg assistant">
      <div className="copilot-msg-bubble assistant">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
        {isStreaming && <span className="copilot-streaming-cursor" />}
      </div>
    </div>
  );
};

export default CoPilotMessageBubble;
