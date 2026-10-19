import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiPost, apiPatch } from '../api/client';
import { useAsyncData } from '../api/useAsyncData';
import {
  LoadingState,
  ErrorState,
  EmptyState,
  UnavailableState,
} from '../components/common/StateViews';
import { formatDistance, formatNumber, formatDateTime } from '../utils/format';

const ALLOCATION_COLORS = {
  recommended: '#f57c00',
  approved: '#2e7d32',
  rejected: '#c62828',
  cancelled: '#757575',
};

export default function OptimizationPage() {
  const incidents = useAsyncData('/incidents');
  const [selectedId, setSelectedId] = useState(null);
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  const list = useMemo(() => incidents.data?.incidents || [], [incidents.data]);

  useEffect(() => {
    if (!selectedId && list.length > 0) setSelectedId(list[0].id);
  }, [list, selectedId]);

  const optimization = useAsyncData(
    selectedId ? `/incidents/${selectedId}/optimization` : null,
    Boolean(selectedId)
  );
  const history = useAsyncData(
    selectedId ? `/incidents/${selectedId}/optimization/history?limit=20` : null,
    Boolean(selectedId)
  );

  const selectedIncident = list.find((i) => i.id === selectedId) || null;
  const data = optimization.data;

  const runOptimization = async () => {
    if (!selectedId) return;
    setBusy('optimize');
    setError(null);
    setNotice(null);
    try {
      await apiPost(`/incidents/${selectedId}/optimize-resources`, {});
      optimization.reload();
      history.reload();
      setNotice('Optimization complete. Review recommendations below.');
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(null);
    }
  };

  const decide = async (allocationId, status) => {
    setBusy(`alloc-${allocationId}`);
    setError(null);
    setNotice(null);
    try {
      await apiPatch(`/incidents/resource-allocations/${allocationId}/status`, { status });
      optimization.reload();
      setNotice(`Allocation ${status}.`);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Optimization</h1>
          <p className="page-subtitle">
            Resource recommendations from the CP-SAT solver. Approvals are human decisions —
            nothing is dispatched automatically.
          </p>
        </div>
      </div>

      {incidents.loading && !incidents.data && <LoadingState label="Loading incidents…" />}
      {incidents.error && <ErrorState message={incidents.error} onRetry={incidents.reload} />}
      {!incidents.loading && !incidents.error && list.length === 0 && (
        <EmptyState message="No incidents available to optimize." />
      )}

      {list.length > 0 && (
        <>
          <div className="card">
            <div className="toolbar">
              <div className="field" style={{ flex: 1, marginBottom: 0 }}>
                <label htmlFor="incident">Incident</label>
                <select
                  id="incident"
                  value={selectedId || ''}
                  onChange={(e) => {
                    setSelectedId(e.target.value);
                    setNotice(null);
                    setError(null);
                  }}
                >
                  {list.map((i) => (
                    <option key={i.id} value={i.id}>
                      {i.title || 'Untitled'} ({i.status})
                    </option>
                  ))}
                </select>
              </div>
              <button
                type="button"
                className="btn-primary"
                onClick={runOptimization}
                disabled={busy === 'optimize'}
              >
                {busy === 'optimize' ? 'Optimizing…' : 'Run optimization'}
              </button>
              {selectedIncident && (
                <Link className="link-row" to={`/incidents/${selectedIncident.id}`}>
                  Open workspace →
                </Link>
              )}
            </div>
          </div>

          {error && <div className="error-banner">{error}</div>}
          {notice && <div className="success-banner">{notice}</div>}

          <div className="card">
            <h3 className="section-title">Latest recommendation</h3>
            {optimization.loading && <LoadingState />}
            {optimization.status === 404 && (
              <UnavailableState message="No optimization has been run for this incident." />
            )}
            {optimization.error && optimization.status !== 404 && (
              <ErrorState message={optimization.error} onRetry={optimization.reload} />
            )}
            {data && (
              <>
                <dl className="kv" style={{ marginBottom: 14 }}>
                  <dt>Status</dt>
                  <dd>{data.status}</dd>
                  <dt>Solver</dt>
                  <dd>{data.solver_name || 'unknown'}</dd>
                  <dt>Resources assigned</dt>
                  <dd>{formatNumber(data.total_resources)}</dd>
                  <dt>Total distance</dt>
                  <dd>{formatDistance(data.total_distance)}</dd>
                  <dt>Objective value</dt>
                  <dd>{formatNumber(data.objective_value)}</dd>
                </dl>

                {data.unmet_demand?.length > 0 && (
                  <div className="error-banner" style={{ marginBottom: 14 }}>
                    {data.unmet_demand.length} demand item(s) could not be met.
                  </div>
                )}

                {(data.allocations || []).length === 0 ? (
                  <EmptyState message="No allocations in this run." />
                ) : (
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Resource type</th>
                        <th>Distance</th>
                        <th>Score</th>
                        <th>Reason</th>
                        <th>Status</th>
                        <th>Decision</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.allocations.map((alloc) => (
                        <tr key={alloc.id}>
                          <td>{alloc.resource_type}</td>
                          <td>{formatDistance(alloc.distance_meters)}</td>
                          <td>{alloc.assignment_score != null ? alloc.assignment_score.toFixed(2) : '—'}</td>
                          <td className="muted">{alloc.assignment_reason || '—'}</td>
                          <td>
                            <span
                              className="badge"
                              style={{ background: ALLOCATION_COLORS[alloc.status] || '#757575' }}
                            >
                              {alloc.status}
                            </span>
                          </td>
                          <td>
                            {alloc.status === 'recommended' ? (
                              <div style={{ display: 'flex', gap: 6 }}>
                                <button
                                  type="button"
                                  className="btn-primary"
                                  disabled={busy === `alloc-${alloc.id}`}
                                  onClick={() => decide(alloc.id, 'approved')}
                                >
                                  Approve
                                </button>
                                <button
                                  type="button"
                                  className="btn-danger"
                                  disabled={busy === `alloc-${alloc.id}`}
                                  onClick={() => decide(alloc.id, 'rejected')}
                                >
                                  Reject
                                </button>
                              </div>
                            ) : (
                              <span className="muted">—</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </>
            )}
          </div>

          <div className="card">
            <h3 className="section-title">Run history</h3>
            {Array.isArray(history.data) && history.data.length > 0 ? (
              <div className="list">
                {history.data.map((h) => (
                  <div key={h.id} className="list-item">
                    <span>Trigger: {h.trigger}</span>
                    <span className="muted">{formatDateTime(h.created_at)}</span>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState message="No optimization history." />
            )}
          </div>
        </>
      )}
    </div>
  );
}
