import React from 'react';

const STATUS_LABELS = {
  success: 'read',
  unavailable: 'no data',
  error: 'failed',
  denied: 'blocked',
  invalid: 'rejected',
};

function ToolActivity({ tools }) {
  if (!tools || tools.length === 0) return null;

  return (
    <div className="tool-activity">
      <div className="tool-activity-header">
        Checked against the system ({tools.length})
      </div>
      <ul>
        {tools.map((entry, index) => (
          <li key={`${entry.tool}-${index}`} className={`tool-entry ${entry.status}`}>
            <span className="tool-entry-name">{entry.tool}</span>
            <span className={`tool-entry-status ${entry.status}`}>
              {STATUS_LABELS[entry.status] || entry.status}
            </span>
            {entry.source && <span className="tool-entry-source">{entry.source}</span>}
            {entry.note && <span className="tool-entry-note">{entry.note}</span>}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default ToolActivity;
