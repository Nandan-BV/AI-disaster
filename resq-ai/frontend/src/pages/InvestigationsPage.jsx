import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiPost } from '../api/client';
import { useAsyncData } from '../api/useAsyncData';
import {
  LoadingState,
  ErrorState,
  EmptyState,
  UnavailableState,
} from '../components/common/StateViews';
import { formatPercent, statusColor } from '../utils/format';

export default function InvestigationsPage() {
  const incidents = useAsyncData('/incidents');
  const [selectedId, setSelectedId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const list = useMemo(() => incidents.data?.incidents || [], [incidents.data]);

  useEffect(() => {
    if (!selectedId && list.length > 0) setSelectedId(list[0].id);
  }, [list, selectedId]);

  const investigation = useAsyncData(
    selectedId ? `/incidents/${selectedId}/investigation-summary` : null,
    Boolean(selectedId)
  );
  const evidence = useAsyncData(
    selectedId ? `/incidents/${selectedId}/evidence?limit=100` : null,
    Boolean(selectedId)
  );

  const selectedIncident = list.find((i) => i.id === selectedId) || null;
  const data = investigation.data;
  const evidenceItems = evidence.data?.evidence || [];

  const run = async () => {
    if (!selectedId) return;
    setBusy(true);
    setError(null);
    try {
      await apiPost(`/incidents/${selectedId}/investigate`, { force_rerun: true });
      investigation.reload();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Evidence Investigations</h1>
          <p className="page-subtitle">
            Source-supported evidence assessment produced by the investigation engine.
          </p>
        </div>
      </div>

      {incidents.loading && !incidents.data && <LoadingState label="Loading incidents…" />}
      {incidents.error && <ErrorState message={incidents.error} onRetry={incidents.reload} />}
      {!incidents.loading && !incidents.error && list.length === 0 && (
        <EmptyState message="No incidents to investigate." />
      )}

      {list.length > 0 && (
        <div className="grid" style={{ gridTemplateColumns: '280px 1fr' }}>
          <div className="card" style={{ maxHeight: 620, overflowY: 'auto' }}>
            <h3 className="section-title">Incidents ({list.length})</h3>
            <div className="list">
              {list.map((incident) => (
                <div
                  key={incident.id}
                  className={`list-item clickable ${selectedId === incident.id ? 'active' : ''}`}
                  onClick={() => {
                    setSelectedId(incident.id);
                    setError(null);
                  }}
                >
                  <span>{incident.title || 'Untitled'}</span>
                  <span
                    className="badge"
                    style={{ background: statusColor(incident.status) }}
                  >
                    {incident.status}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="grid" style={{ gap: 16 }}>
            <div className="card">
              <div className="card-header">
                <h3>{selectedIncident?.title || 'Investigation'}</h3>
                <div style={{ display: 'flex', gap: 8 }}>
                  {selectedIncident && (
                    <Link className="link-row" to={`/incidents/${selectedIncident.id}`}>
                      Workspace →
                    </Link>
                  )}
                  <button
                    type="button"
                    className="btn-primary"
                    onClick={run}
                    disabled={busy || !selectedId}
                  >
                    {busy ? 'Investigating…' : 'Run investigation'}
                  </button>
                </div>
              </div>

              {error && <div className="error-banner">{error}</div>}
              {investigation.loading && <LoadingState />}
              {investigation.status === 404 && (
                <UnavailableState message="No investigation has been run for this incident." />
              )}
              {data && (
                <div>
                  <div style={{ marginBottom: 12 }}>
                    <span className="badge outline">
                      {String(data.assessment || 'unknown').replace('_', ' ')}
                    </span>
                  </div>
                  <div className="grid cols-3">
                    {[
                      ['Evidence confidence', data.evidence_confidence_score],
                      ['Source diversity', data.source_diversity],
                      ['Geographic consistency', data.geographic_consistency],
                      ['Temporal consistency', data.temporal_consistency],
                      ['Multimodal consistency', data.multimodal_consistency],
                    ].map(([label, value]) => (
                      <div key={label}>
                        <div className="muted" style={{ fontSize: '0.85rem' }}>
                          {label}
                        </div>
                        <div style={{ fontWeight: 600 }}>{formatPercent(value)}</div>
                      </div>
                    ))}
                  </div>
                  {data.explanation && (
                    <p className="pre-wrap" style={{ marginTop: 12 }}>
                      {data.explanation}
                    </p>
                  )}
                  {data.limitations && (
                    <p className="pre-wrap muted" style={{ marginTop: 8 }}>
                      <strong>Limitations:</strong> {data.limitations}
                    </p>
                  )}
                </div>
              )}
            </div>

            <div className="card">
              <h3 className="section-title">Collected evidence ({evidenceItems.length})</h3>
              {evidenceItems.length === 0 ? (
                <EmptyState message="No evidence records." />
              ) : (
                <div className="list">
                  {evidenceItems.map((item, index) => (
                    <div key={index} className="list-item" style={{ alignItems: 'flex-start' }}>
                      <div>
                        <div style={{ display: 'flex', gap: 8, marginBottom: 4 }}>
                          <span className="badge outline">{item.evidence_type}</span>
                          <span className="muted">{item.evidence_role}</span>
                        </div>
                        <p className="pre-wrap" style={{ margin: 0 }}>
                          {item.description}
                        </p>
                      </div>
                      <span className="muted">Q {formatPercent(item.evidence_quality)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
