import React, { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { apiPost, apiPatch } from '../api/client';
import { useAsyncData } from '../api/useAsyncData';
import {
  LoadingState,
  ErrorState,
  EmptyState,
  UnavailableState,
} from '../components/common/StateViews';
import Copilot from '../components/copilot/Copilot';
import MapView from '../MapView';
import {
  formatDateTime,
  formatPercent,
  formatDistance,
  formatNumber,
  riskColor,
  statusColor,
} from '../utils/format';

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'evidence', label: 'Evidence' },
  { id: 'risk', label: 'Risk & Impact' },
  { id: 'resources', label: 'Resources' },
  { id: 'map', label: 'Map' },
  { id: 'copilot', label: 'Copilot' },
];

function MetricBar({ label, value }) {
  const pct = value == null ? 0 : Math.round((value <= 1 ? value * 100 : value));
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

function EvidenceGroup({ title, items }) {
  return (
    <div className="card">
      <h3 className="section-title">
        {title} ({items.length})
      </h3>
      {items.length === 0 ? (
        <p className="muted">None.</p>
      ) : (
        <div className="list">
          {items.map((item, index) => (
            <div key={index} className="list-item" style={{ alignItems: 'flex-start' }}>
              <div>
                <div style={{ display: 'flex', gap: 8, marginBottom: 4 }}>
                  <span className="badge outline">{item.evidence_type}</span>
                  {item.source && <span className="muted">{item.source}</span>}
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
  );
}

export default function IncidentDetail() {
  const { incidentId } = useParams();
  const [tab, setTab] = useState('overview');
  const [actionError, setActionError] = useState(null);
  const [actionNotice, setActionNotice] = useState(null);
  const [busy, setBusy] = useState(null);

  const incident = useAsyncData(`/incidents/${incidentId}`);
  const risk = useAsyncData(`/incidents/${incidentId}/risk-assessment`);
  const impact = useAsyncData(`/incidents/${incidentId}/impact`);
  const investigation = useAsyncData(`/incidents/${incidentId}/investigation-summary`);
  const evidence = useAsyncData(`/incidents/${incidentId}/evidence?limit=100`);
  const optimization = useAsyncData(`/incidents/${incidentId}/optimization`);
  const nearby = useAsyncData(`/resources/incidents/${incidentId}/nearby-resources`);

  const run = async (key, fn, successMessage) => {
    setBusy(key);
    setActionError(null);
    setActionNotice(null);
    try {
      await fn();
      setActionNotice(successMessage);
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusy(null);
    }
  };

  const runInvestigation = () =>
    run(
      'investigate',
      async () => {
        await apiPost(`/incidents/${incidentId}/investigate`, { force_rerun: true });
        investigation.reload();
        incident.reload();
      },
      'Investigation completed.'
    );

  const runRisk = () =>
    run(
      'risk',
      async () => {
        await apiPost(`/incidents/${incidentId}/risk-assessment`, {});
        risk.reload();
        impact.reload();
        incident.reload();
      },
      'Risk assessment completed.'
    );

  const runOptimization = () =>
    run(
      'optimize',
      async () => {
        await apiPost(`/incidents/${incidentId}/optimize-resources`, {});
        optimization.reload();
      },
      'Optimization completed. Review the recommendations below.'
    );

  const decideAllocation = (allocationId, status) =>
    run(
      `alloc-${allocationId}`,
      async () => {
        await apiPatch(`/incidents/resource-allocations/${allocationId}/status`, { status });
        optimization.reload();
      },
      `Allocation ${status}.`
    );

  const inc = incident.data;

  if (incident.loading && !inc) return <LoadingState label="Loading incident…" />;
  if (incident.error) {
    return (
      <div className="page">
        <ErrorState message={incident.error} onRetry={incident.reload} />
        <Link className="link-row" to="/incidents">
          ← Back to incidents
        </Link>
      </div>
    );
  }
  if (!inc) return null;

  const investigationData = investigation.data;
  const riskData = risk.data;
  const impactData = impact.data;
  const evidenceItems = evidence.data?.evidence || [];
  const optimizationData = optimization.data;
  const nearbyResources =
    nearby.data?.resources || (Array.isArray(nearby.data) ? nearby.data : []);

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <Link className="link-row" to="/incidents">
            ← Incidents
          </Link>
          <h1 style={{ marginTop: 6 }}>{inc.title || 'Untitled incident'}</h1>
          <p className="page-subtitle">
            {inc.incident_type || 'unknown'} · {inc.event_count} events ·{' '}
            {inc.location_name ||
              (inc.centroid_latitude != null && inc.centroid_longitude != null
                ? `${inc.centroid_latitude.toFixed(4)}, ${inc.centroid_longitude.toFixed(4)}`
                : 'location unknown')}
          </p>
        </div>
        <div className="page-actions">
          <span className="badge" style={{ background: statusColor(inc.status) }}>
            {inc.status}
          </span>
          {riskData?.risk_level && (
            <span className="badge" style={{ background: riskColor(riskData.risk_level) }}>
              {riskData.risk_level}
            </span>
          )}
        </div>
      </div>

      {actionError && <div className="error-banner">{actionError}</div>}
      {actionNotice && <div className="success-banner">{actionNotice}</div>}

      <div className="tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`tab ${tab === t.id ? 'active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'overview' && (
        <div className="grid cols-2">
          <div className="card">
            <h3 className="section-title">Incident detail</h3>
            <dl className="kv">
              <dt>Type</dt>
              <dd>{inc.incident_type || 'unknown'}</dd>
              <dt>Status</dt>
              <dd>{inc.status}</dd>
              <dt>Confidence</dt>
              <dd>{formatPercent(inc.confidence)}</dd>
              <dt>Events</dt>
              <dd>{inc.event_count}</dd>
              <dt>Started</dt>
              <dd>{formatDateTime(inc.start_time)}</dd>
              <dt>Last updated</dt>
              <dd>{formatDateTime(inc.last_updated)}</dd>
            </dl>
          </div>

          <div className="card">
            <h3 className="section-title">Risk snapshot</h3>
            {risk.status === 404 && <UnavailableState message="No risk assessment yet." />}
            {risk.loading && <LoadingState />}
            {riskData && (
              <div>
                <div style={{ display: 'flex', gap: 10, alignItems: 'baseline' }}>
                  <span
                    style={{
                      fontSize: '2rem',
                      fontWeight: 700,
                      color: riskColor(riskData.risk_level),
                    }}
                  >
                    {riskData.risk_score}
                  </span>
                  <span className="badge" style={{ background: riskColor(riskData.risk_level) }}>
                    {riskData.risk_level}
                  </span>
                </div>
                <p className="pre-wrap muted">{riskData.explanation}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {tab === 'evidence' && (
        <div className="grid" style={{ gap: 16 }}>
          <div className="card">
            <div className="card-header">
              <h3>Investigation</h3>
              <button
                type="button"
                className="btn-primary"
                onClick={runInvestigation}
                disabled={busy === 'investigate'}
              >
                {busy === 'investigate' ? 'Investigating…' : 'Run investigation'}
              </button>
            </div>

            {investigation.status === 404 && (
              <UnavailableState message="No investigation has been run for this incident." />
            )}
            {investigation.loading && <LoadingState />}
            {investigationData && (
              <div>
                <div style={{ marginBottom: 12 }}>
                  <span className="badge outline">
                    {String(investigationData.assessment || 'unknown').replace('_', ' ')}
                  </span>
                </div>
                <div className="grid cols-3">
                  <MetricBar
                    label="Evidence confidence"
                    value={investigationData.evidence_confidence_score}
                  />
                  <MetricBar label="Source diversity" value={investigationData.source_diversity} />
                  <MetricBar
                    label="Geographic consistency"
                    value={investigationData.geographic_consistency}
                  />
                  <MetricBar
                    label="Temporal consistency"
                    value={investigationData.temporal_consistency}
                  />
                  <MetricBar
                    label="Multimodal consistency"
                    value={investigationData.multimodal_consistency}
                  />
                </div>
                {investigationData.explanation && (
                  <p className="pre-wrap" style={{ marginTop: 12 }}>
                    {investigationData.explanation}
                  </p>
                )}
              </div>
            )}
          </div>

          {investigationData && (
            <>
              <EvidenceGroup
                title="Supporting evidence"
                items={investigationData.supporting_evidence || []}
              />
              <EvidenceGroup
                title="Contradicting evidence"
                items={investigationData.contradicting_evidence || []}
              />
              <EvidenceGroup
                title="Uncertain evidence"
                items={investigationData.uncertain_evidence || []}
              />
              <EvidenceGroup
                title="Neutral evidence"
                items={investigationData.neutral_evidence || []}
              />
            </>
          )}

          <div className="card">
            <h3 className="section-title">Collected evidence ({evidenceItems.length})</h3>
            {evidenceItems.length === 0 ? (
              <EmptyState message="No evidence records for this incident." />
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
      )}

      {tab === 'risk' && (
        <div className="grid" style={{ gap: 16 }}>
          <div className="card">
            <div className="card-header">
              <h3>Risk assessment</h3>
              <button
                type="button"
                className="btn-primary"
                onClick={runRisk}
                disabled={busy === 'risk'}
              >
                {busy === 'risk' ? 'Assessing…' : 'Run risk assessment'}
              </button>
            </div>
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
                  <span className="badge" style={{ background: riskColor(riskData.risk_level) }}>
                    {riskData.risk_level}
                  </span>
                </div>
                <div className="grid cols-3">
                  <MetricBar label="Severity" value={riskData.severity_component} />
                  <MetricBar label="Evidence" value={riskData.evidence_component} />
                  <MetricBar label="Population" value={riskData.population_component} />
                  <MetricBar label="Infrastructure" value={riskData.infrastructure_component} />
                  <MetricBar label="Environment" value={riskData.environmental_component} />
                  <MetricBar label="Accessibility" value={riskData.accessibility_component} />
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
                <div className="stat">
                  <div className="stat-value">
                    {formatNumber(impactData.population_potentially_exposed)}
                  </div>
                  <div className="stat-label">Population exposed</div>
                </div>
                <div className="stat">
                  <div className="stat-value">
                    {formatNumber(impactData.infrastructure_potentially_exposed)}
                  </div>
                  <div className="stat-label">Infrastructure exposed</div>
                </div>
                <div className="stat">
                  <div className="stat-value">{formatNumber(impactData.hospitals_count)}</div>
                  <div className="stat-label">Hospitals nearby</div>
                </div>
                <div className="stat">
                  <div className="stat-value">{formatNumber(impactData.shelters_count)}</div>
                  <div className="stat-label">Shelters nearby</div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {tab === 'resources' && (
        <div className="grid" style={{ gap: 16 }}>
          <div className="card">
            <div className="card-header">
              <h3>Resource optimization</h3>
              <button
                type="button"
                className="btn-primary"
                onClick={runOptimization}
                disabled={busy === 'optimize'}
              >
                {busy === 'optimize' ? 'Optimizing…' : 'Run optimization'}
              </button>
            </div>

            {optimization.status === 404 && (
              <UnavailableState message="No optimization has been run for this incident." />
            )}
            {optimizationData && (
              <div>
                <dl className="kv" style={{ marginBottom: 14 }}>
                  <dt>Status</dt>
                  <dd>{optimizationData.status}</dd>
                  <dt>Resources assigned</dt>
                  <dd>{formatNumber(optimizationData.total_resources)}</dd>
                  <dt>Total distance</dt>
                  <dd>{formatDistance(optimizationData.total_distance)}</dd>
                  <dt>Objective value</dt>
                  <dd>{formatNumber(optimizationData.objective_value)}</dd>
                </dl>

                {optimizationData.unmet_demand?.length > 0 && (
                  <div className="error-banner" style={{ marginBottom: 14 }}>
                    Unmet demand: {optimizationData.unmet_demand.length} item(s) could not be
                    fulfilled.
                  </div>
                )}

                <h4 className="section-title">Allocations</h4>
                {(optimizationData.allocations || []).length === 0 ? (
                  <EmptyState message="No allocations in this run." />
                ) : (
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Resource type</th>
                        <th>Distance</th>
                        <th>Reason</th>
                        <th>Status</th>
                        <th>Decision</th>
                      </tr>
                    </thead>
                    <tbody>
                      {optimizationData.allocations.map((alloc) => (
                        <tr key={alloc.id}>
                          <td>{alloc.resource_type}</td>
                          <td>{formatDistance(alloc.distance_meters)}</td>
                          <td className="muted">{alloc.assignment_reason || '—'}</td>
                          <td>
                            <span className="badge outline">{alloc.status}</span>
                          </td>
                          <td>
                            {alloc.status === 'recommended' ? (
                              <div style={{ display: 'flex', gap: 6 }}>
                                <button
                                  type="button"
                                  className="btn-primary"
                                  disabled={busy === `alloc-${alloc.id}`}
                                  onClick={() => decideAllocation(alloc.id, 'approved')}
                                >
                                  Approve
                                </button>
                                <button
                                  type="button"
                                  className="btn-danger"
                                  disabled={busy === `alloc-${alloc.id}`}
                                  onClick={() => decideAllocation(alloc.id, 'rejected')}
                                >
                                  Reject
                                </button>
                              </div>
                            ) : (
                              <span className="muted">Human-decided</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}
          </div>

          <div className="card">
            <h3 className="section-title">Nearby resources</h3>
            {nearbyResources.length === 0 ? (
              <EmptyState message="No nearby resources reported." />
            ) : (
              <div className="list">
                {nearbyResources.map((res) => (
                  <div key={res.id} className="list-item">
                    <span>
                      <strong>{res.name}</strong> · {res.resource_type}
                    </span>
                    <span className="muted">
                      {res.status} · {formatDistance(res.distance_meters)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {tab === 'map' && (
        <div className="card">
          <h3 className="section-title">Geospatial context</h3>
          {inc.centroid_latitude != null && inc.centroid_longitude != null ? (
            <MapView
              incidentId={inc.id}
              center={[inc.centroid_longitude, inc.centroid_latitude]}
              zoom={13}
            />
          ) : (
            <UnavailableState message="This incident has no coordinates." />
          )}
        </div>
      )}

      {tab === 'copilot' && <Copilot incidents={[inc]} />}
    </div>
  );
}
