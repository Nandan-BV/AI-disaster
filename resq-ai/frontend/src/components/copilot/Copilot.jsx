import React, { useCallback, useEffect, useRef, useState } from 'react';
import CopilotMessage from './CopilotMessage';
import IncidentContextPanel from './IncidentContextPanel';
import ToolPermissionList from './ToolPermissionList';

const API_BASE = '/api/v1';

function Copilot({ incidents = [] }) {
  const [sessionId, setSessionId] = useState('demo-session');
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const [showTools, setShowTools] = useState(false);
  const [toolsInfo, setToolsInfo] = useState(null);
  const [toolsError, setToolsError] = useState(null);
  const [toolsLoading, setToolsLoading] = useState(false);

  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, sending]);

  const loadTools = useCallback(async () => {
    setToolsLoading(true);
    setToolsError(null);
    try {
      const response = await fetch(`${API_BASE}/copilot/tools`);
      if (response.ok) {
        setToolsInfo(await response.json());
      } else {
        setToolsError('Could not load tool permissions.');
      }
    } catch (err) {
      setToolsError(err.message);
    } finally {
      setToolsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (showTools && !toolsInfo) loadTools();
  }, [showTools, toolsInfo, loadTools]);

  const send = async (text) => {
    const message = text.trim();
    if (!message || sending) return;

    setError(null);
    setSending(true);
    setInput('');

    const outgoing = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: message,
      sources: [],
      tools_used: [],
      uncertainty: [],
      refused_action: false,
    };
    setMessages(prev => [...prev, outgoing]);

    try {
      const response = await fetch(`${API_BASE}/copilot/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          incident_id: selectedIncident ? selectedIncident.id : null,
          message,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setMessages(prev => [
          ...prev,
          {
            id: `c-${Date.now()}`,
            role: 'assistant',
            content: data.answer,
            sources: data.sources || [],
            tools_used: data.tools_used || [],
            uncertainty: data.uncertainty || [],
            refused_action: data.refused_action,
            model_name: data.model_name,
          },
        ]);
      } else if (response.status === 503) {
        const detail = await response.json().catch(() => ({}));
        setError(
          detail.detail ||
            'The copilot is currently unavailable. No answer was generated.'
        );
      } else {
        const detail = await response.json().catch(() => ({}));
        setError(detail.detail || `Request failed (${response.status}).`);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
    }
  };

  const clearConversation = async () => {
    setMessages([]);
    setError(null);
    if (!sessionId) return;
    try {
      await fetch(`${API_BASE}/copilot/conversations/${encodeURIComponent(sessionId)}`, {
        method: 'DELETE',
      });
    } catch (err) {
      console.error('Failed to delete conversation:', err);
    }
  };

  const onSubmit = (e) => {
    e.preventDefault();
    send(input);
  };

  return (
    <section className="section copilot-section">
      <h2>Emergency Response Copilot</h2>
      <p className="copilot-description">
        Ask about incidents, evidence, risk, infrastructure, or resources. Every answer is
        grounded in backend data and shows which tools it consulted. The copilot recommends;
        a human approves and dispatches.
      </p>

      <div className="copilot-layout">
        <IncidentContextPanel
          incidents={incidents}
          selectedIncident={selectedIncident}
          onIncidentChange={setSelectedIncident}
          sessionId={sessionId}
          onSessionChange={setSessionId}
          onClearConversation={clearConversation}
          onSuggest={send}
          onToggleTools={() => setShowTools(v => !v)}
          showTools={showTools}
        />

        <div className="copilot-main">
          {showTools && (
            <ToolPermissionList toolsInfo={toolsInfo} loading={toolsLoading} error={toolsError} />
          )}

          <div className="copilot-transcript">
            {messages.length === 0 && !sending && (
              <div className="copilot-empty">
                <p>Start with a question about the incident you are handling.</p>
                <p className="copilot-panel-note">
                  Example: "Summarise this incident and tell me what is uncertain."
                </p>
              </div>
            )}

            {messages.map(message => (
              <CopilotMessage key={message.id} message={message} />
            ))}

            {sending && (
              <div className="copilot-message from-copilot">
                <div className="copilot-message-role">Copilot</div>
                <div className="copilot-message-body">
                  <span className="copilot-typing">Reading backend data...</span>
                </div>
              </div>
            )}

            <div ref={bottomRef} />
          </div>

          {error && <div className="analysis-error">{error}</div>}

          <form className="copilot-input" onSubmit={onSubmit}>
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  send(input);
                }
              }}
              rows="2"
              placeholder="Ask the copilot about this incident..."
              disabled={sending}
            />
            <button type="submit" className="btn-primary" disabled={sending || !input.trim()}>
              {sending ? 'Thinking...' : 'Send'}
            </button>
          </form>
        </div>
      </div>
    </section>
  );
}

export default Copilot;
