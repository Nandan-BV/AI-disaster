import React from 'react';
import { Link } from 'react-router-dom';
import { useAsyncData } from '../api/useAsyncData';
import { LoadingState, ErrorState } from '../components/common/StateViews';

export default function SystemStatusPage() {
  const health = useAsyncData('/health');
  const overview = useAsyncData('/dashboard/overview?limit_recent=1');
  const tools = useAsyncData('/copilot/tools');

  const metrics = overview.data;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>System Status</h1>
          <p className="page-subtitle">Backend health, data volumes, and copilot configuration.</p>
        </div>
        <Link className="link-row" to="/console">
          Open legacy console →
        </Link>
      </div>

      <div className="grid cols-3">
        <div className="card">
          <h3 className="section-title">Backend</h3>
          {health.loading && <LoadingState />}
          {health.error && <ErrorState message={health.error} onRetry={health.reload} />}
          {health.data && (
            <dl className="kv">
              <dt>Status</dt>
              <dd>{health.data.status}</dd>
              <dt>Project</dt>
              <dd>{health.data.project}</dd>
              <dt>Database</dt>
              <dd>{health.data.database}</dd>
              <dt>Copilot service</dt>
              <dd>{health.data.copilot || 'unknown'}</dd>
            </dl>
          )}
        </div>

        <div className="card">
          <h3 className="section-title">Data volumes</h3>
          {overview.loading && <LoadingState />}
          {overview.error && <ErrorState message={overview.error} onRetry={overview.reload} />}
          {metrics && (
            <dl className="kv">
              <dt>Incidents</dt>
              <dd>{metrics.incident_metrics.total}</dd>
              <dt>Events</dt>
              <dd>{metrics.event_metrics.total}</dd>
              <dt>Events awaiting analysis</dt>
              <dd>{metrics.event_metrics.awaiting_analysis}</dd>
              <dt>Resources</dt>
              <dd>{metrics.resource_metrics.total}</dd>
              <dt>Pending approvals</dt>
              <dd>{metrics.optimization_metrics.pending_approvals}</dd>
            </dl>
          )}
        </div>

        <div className="card">
          <h3 className="section-title">Copilot</h3>
          {tools.loading && <LoadingState />}
          {tools.error && <ErrorState message={tools.error} onRetry={tools.reload} />}
          {tools.data && (
            <dl className="kv">
              <dt>Provider</dt>
              <dd>{tools.data.provider}</dd>
              <dt>Model</dt>
              <dd>{tools.data.model_name}</dd>
              <dt>Controlled actions</dt>
              <dd>{tools.data.controlled_actions_enabled ? 'enabled' : 'disabled'}</dd>
              <dt>Tools registered</dt>
              <dd>{tools.data.tools?.length ?? 0}</dd>
            </dl>
          )}
        </div>
      </div>

      {tools.data?.tools?.length > 0 && (
        <div className="card">
          <h3 className="section-title">Registered copilot tools</h3>
          <table className="data-table">
            <thead>
              <tr>
                <th>Tool</th>
                <th>Permission</th>
                <th>Source</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              {tools.data.tools.map((tool) => (
                <tr key={tool.name}>
                  <td>{tool.name}</td>
                  <td>
                    <span
                      className="badge"
                      style={{
                        background: tool.permission === 'read_only' ? '#2e7d32' : '#6a1b9a',
                      }}
                    >
                      {tool.permission}
                    </span>
                  </td>
                  <td className="muted">{tool.source}</td>
                  <td>{tool.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
