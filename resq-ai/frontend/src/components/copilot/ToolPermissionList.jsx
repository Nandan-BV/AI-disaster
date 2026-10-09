import React from 'react';

function ToolPermissionList({ toolsInfo, loading, error }) {
  if (loading) return <p className="copilot-panel-note">Loading tool permissions...</p>;
  if (error) return <p className="copilot-panel-error">{error}</p>;
  if (!toolsInfo) return null;

  const readOnly = toolsInfo.tools.filter(t => t.permission === 'read_only');
  const controlled = toolsInfo.tools.filter(t => t.permission === 'controlled_action');

  return (
    <div className="copilot-tool-list">
      <div className="copilot-tool-group">
        <div className="copilot-tool-group-title">
          Read-only ({readOnly.length})
        </div>
        <ul>
          {readOnly.map(tool => (
            <li key={tool.name}>
              <span className="copilot-tool-name">{tool.name}</span>
              <span className="copilot-tool-source">{tool.source}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="copilot-tool-group">
        <div className="copilot-tool-group-title">
          Controlled actions ({controlled.length})
          <span className={`copilot-toggle ${toolsInfo.controlled_actions_enabled ? 'on' : 'off'}`}>
            {toolsInfo.controlled_actions_enabled ? 'ENABLED' : 'DISABLED'}
          </span>
        </div>
        {controlled.length === 0 ? (
          <p className="copilot-panel-note">No controlled actions registered.</p>
        ) : (
          <ul>
            {controlled.map(tool => (
              <li key={tool.name}>
                <span className="copilot-tool-name">{tool.name}</span>
                <span className="copilot-tool-source">{tool.source}</span>
              </li>
            ))}
          </ul>
        )}
        <p className="copilot-panel-note">
          The copilot has no approve, dispatch, or record-mutation tool at any setting. An
          operator always makes the final call.
        </p>
      </div>
    </div>
  );
}

export default ToolPermissionList;
