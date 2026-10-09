import React from 'react';

const SUGGESTIONS = [
  'Summarise this incident',
  'How many resources are nearby?',
  'What is the current risk level and why?',
  'Which roads are blocked?',
  'Is the evidence here strong or weak?',
];

function IncidentContextPanel({
  incidents,
  selectedIncident,
  onIncidentChange,
  sessionId,
  onSessionChange,
  onClearConversation,
  onSuggest,
  onToggleTools,
  showTools,
}) {
  return (
    <aside className="copilot-context">
      <div className="copilot-context-section">
        <label htmlFor="copilot-session">Session</label>
        <input
          id="copilot-session"
          type="text"
          value={sessionId}
          onChange={e => onSessionChange(e.target.value)}
          placeholder="demo-session"
        />
        <button type="button" className="btn-secondary" onClick={onClearConversation}>
          Clear conversation
        </button>
      </div>

      <div className="copilot-context-section">
        <label htmlFor="copilot-incident">Incident in focus</label>
        {incidents.length === 0 ? (
          <p className="copilot-panel-note">
            No incidents loaded. Ask without selecting one, or create an incident first.
          </p>
        ) : (
          <select
            id="copilot-incident"
            value={selectedIncident?.id || ''}
            onChange={e => {
              const match = incidents.find(i => i.id === e.target.value);
              onIncidentChange(match || null);
            }}
          >
            <option value="">No specific incident</option>
            {incidents.map(incident => (
              <option key={incident.id} value={incident.id}>
                {incident.title || incident.id}
              </option>
            ))}
          </select>
        )}
        {selectedIncident && (
          <p className="copilot-panel-note">
            Follow-up questions stay pinned to{' '}
            <strong>{selectedIncident.title || selectedIncident.id}</strong>.
          </p>
        )}
      </div>

      <div className="copilot-context-section">
        <div className="copilot-tool-group-title">Try asking</div>
        <div className="copilot-suggestions">
          {SUGGESTIONS.map(text => (
            <button
              key={text}
              type="button"
              className="copilot-suggestion"
              onClick={() => onSuggest(text)}
            >
              {text}
            </button>
          ))}
        </div>
      </div>

      <div className="copilot-context-section">
        <button type="button" className="btn-secondary" onClick={onToggleTools}>
          {showTools ? 'Hide' : 'Show'} tool permissions
        </button>
      </div>
    </aside>
  );
}

export default IncidentContextPanel;
