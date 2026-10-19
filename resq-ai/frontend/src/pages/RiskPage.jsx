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
import { formatNumber, riskColor } from '../utils/format';

function Bar({ label, value }) {
  const pct = value == null ? 0 : Math.round(value <= 1 ? value * 100 : value);
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
        <span className="muted">{label}</span>
        <span>{value == null ? '—' : `${pct}%`}</span>
      </div>
      <div className={`progress ${pct >= 75 ? 'critical' : ''}`}>
        <span style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
    </div>
  );
}

export default function RiskPage() {
  const incidents = useAsyncData('/incidents');
  const [selectedId, setSelectedId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const list = useMemo(() => incidents.data?.incidents || [], [incidents.data]);

  useEffect(() => {
    if (!selectedId && list.length > 0) setSelectedId(list[0].id);
  }, [list, selectedId]);

  const risk = useAsyncData(
    selectedId ? `/incidents/${selectedId}/risk-assessment` : null,
    Boolean(selectedId)
  );
  const impact = useAsyncData(
    selectedId ? `/incidents/${selectedId}/impact` : null,
    Boolean(selectedId)
  );

  const selectedIncident = list.find((i) => i.id === selectedId) || null;
  const riskData = risk.data;
  const impactData = impact.data;

  const run = async () => {
    if (!selectedId) return;
    setBusy(true);
    setError(null);
    try {
      await apiPost(`/incidents/${selectedId}/risk-assessment`, {});
      risk.reload();
      impact.reload();
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
          <h1>Risk &amp; Impact</h1>
          <p className="page-subtitle">
            Composite risk scoring and population/infrastructure impact assessment.
          </p>
        </div>
      </div>

      {incidents.loading && !incidents.data && <LoadingState label="Loading incidents…" />}
      {incidents.error && <ErrorState message={incidents.error} onRetry={incidents.reload} />}
      {!incidents.loading && !incidents.error && list.length === 0 && (
        <EmptyState message="No incidents to assess." />
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
                </div>
              ))}
            </div>
          </div>

          <div className="grid" style={{ gap: 16 }}>
            <div className="card">
              <div className="card-header">
                <h3>{selectedIncident?.title || 'Risk assessment'}</h3>
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
                    {busy ? 'Assessing…' : 'Run risk assessment'}
                  </button>
                </div>
              </div>

              {error && <div className="error-banner">{error}</div>}
              {risk.loading && <LoadingState />}
              {risk.status === 404 && (
                <UnavailableState message="No risk assessment yet. Run one above." />
              )}
              {riskData && (
                <div>
                  <div style={{ display: 'flex', gap: 10, alignItems: 'baseline', marginBottom: 12 }}>
                    <span
                      style={{
                        fontSize: '2.4rem',
                        fontWeight: 700,
                        color: riskColor(riskData.risk_level),
                      }}
                    >
                      {riskData.risk_score}
                    </span>
                    <span
                      className="badge"
                      style={{ background: riskColor(riskData.risk_level) }}
                    >
                      {riskData.risk_level}
                    </span>
                  </div>
                  <div className="grid cols-3">
                    <Bar label="Severity" value={riskData.severity_component} />
                    <Bar label="Evidence" value={riskData.evidence_component} />
                    <Bar label="Population" value={riskData.population_component} />
                    <Bar label="Infrastructure" value={riskData.infrastructure_component} />
                    <Bar label="Environment" value={riskData.environmental_component} />
                    <Bar label="Accessibility" value={riskData.accessibility_component} />
                  </div>
                </div>
              )}
            </div>

            <div className="card">
              <h3 className="section-title">Impact</h3>
              {impact.status === 404 && (
                <UnavailableState message="No impact assessment yet." />
              )}
              {impactData && (
                <div className="incident-summary-grid">
                  {[
                    ['Population exposed', impactData.population_potentially_exposed],
                    ['Infrastructure exposed', impactData.infrastructure_potentially_exposed],
                    ['Hospitals', impactData.hospitals_count],
                    ['Shelters', impactData.shelters_count],
                    ['Fire stations', impactData.fire_stations_count],
                    ['Police', impactData.police_stations_count],
                    ['Schools', impactData.schools_count],
                    ['Bridges', impactData.bridges_count],
                  ].map(([label, value]) => (
                    <div key={label} className="stat">
                      <div className="stat-value">{formatNumber(value)}</div>
                      <div className="stat-label">{label}</div>
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
