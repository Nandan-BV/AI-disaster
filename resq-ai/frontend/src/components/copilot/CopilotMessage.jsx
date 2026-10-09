import React from 'react';
import ToolActivity from './ToolActivity';

function MessageMeta({ message }) {
  if (message.role === 'user') return null;
  return (
    <div className="copilot-message-meta">
      {message.model_name && <span>{message.model_name}</span>}
      {message.sources.length > 0 && (
        <span>
          Sources: {message.sources.join(', ')}
        </span>
      )}
    </div>
  );
}

function CopilotMessage({ message }) {
  const isUser = message.role === 'user';

  return (
    <div className={`copilot-message ${isUser ? 'from-user' : 'from-copilot'}`}>
      <div className="copilot-message-role">{isUser ? 'You' : 'Copilot'}</div>
      <div className="copilot-message-body">
        {message.refused_action && (
          <div className="copilot-refused">
            The copilot does not perform operational actions. It can summarise options for
            a human to approve.
          </div>
        )}

        <p className="copilot-message-text">{message.content}</p>

        {!isUser && <ToolActivity tools={message.tools_used} />}

        {!isUser && message.uncertainty.length > 0 && (
          <div className="copilot-uncertainty">
            <strong>Open questions</strong>
            <ul>
              {message.uncertainty.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </div>
        )}

        <MessageMeta message={message} />
      </div>
    </div>
  );
}

export default CopilotMessage;
