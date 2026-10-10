import React, { useEffect, useMemo, useState } from 'react';
import { apiFetch } from '../../api';

const API_BASE = '/api/v1';

const formatNumber = (value, digits = 2) => {
  if (value === null || value === undefined || value === '') return '—';
  const number = Number(value);
  return Number.isFinite(number) ? number.toLocaleString(undefined, { maximumFractionDigits: digits }) : '—';
};

const getErrorMessage = async (response) => {
  try {
    const error = await response.json();
    return typeof error.detail === 'string' ? error.detail : JSON.stringify(error.detail || error);
  } catch {
    return `Request failed (${response.status})`;
  }
};

function OptimizationDashboard({ incidents = [], userRole }) {
  const canManageAllocations = ['dispatcher', 'commander', 'admin'].includes(userRole);
  const availableIncidents = useMemo(
    () => incidents.filter((incident) => incident.status !== 'resolved'),
    [incidents]
  );
  const [incidentId, setIncidentId] = useState('');
  const [optimization, setOptimization] = useState(null);
  const [resources, setResources] = useState([]);
  const [forceRerun, setForceRerun] = useState(false);
  const [loadingResult, setLoadingResult] = useState(false);
  const [running, setRunning] = useState(false);
  const [updatingAllocation, setUpdatingAllocation] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!availableIncidents.some((incident) => incident.id === incidentId)) {
      setIncidentId(availableIncidents[0]?.id || '');
    }
  }, [availableIncidents, incidentId]);

  useEffect(() => {
    let cancelled = false;

    const loadSelectionData = async () => {
      setOptimization(null);
      setError('');
      if (!incidentId) return;

      setLoadingResult(true);
      try {
        const [optimizationResponse, resourceResponse] = await Promise.all([
          apiFetch(`${API_BASE}/incidents/${incidentId}/optimization`),
          apiFetch(`${API_BASE}/resources`),
        ]);

        if (resourceResponse.ok) {
          const resourceData = await resourceResponse.json();
          if (!cancelled) setResources(resourceData.resources || []);
        } else if (!cancelled) {
          setError(await getErrorMessage(resourceResponse));
        }

        if (optimizationResponse.ok) {
          const result = await optimizationResponse.json();
          if (!cancelled) setOptimization(result);
        } else if (optimizationResponse.status !== 404 && !cancelled) {
          setError(await getErrorMessage(optimizationResponse));
        }
      } catch (requestError) {
        if (!cancelled) setError(requestError.message || 'Could not load optimization data.');
      } finally {
        if (!cancelled) setLoadingResult(false);
      }
    };

    loadSelectionData();
    return () => {
      cancelled = true;
    };
  }, [incidentId]);

  const runOptimization = async () => {
    if (!incidentId) return;
    setRunning(true);
    setError('');
    try {
      const response = await apiFetch(`${API_BASE}/incidents/${incidentId}/optimize-resources`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ force_rerun: forceRerun }),
      });
      if (!response.ok) throw new Error(await getErrorMessage(response));

      const latestResponse = await apiFetch(`${API_BASE}/incidents/${incidentId}/optimization`);
      if (!latestResponse.ok) throw new Error(await getErrorMessage(latestResponse));
      setOptimization(await latestResponse.json());
    } catch (requestError) {
      setError(requestError.message || 'Optimization failed.');
    } finally {
      setRunning(false);
    }
  };

  const updateAllocationStatus = async (allocationId, status) => {
    setUpdatingAllocation(allocationId);
    setError('');
    try {
      const response = await apiFetch(
        `${API_BASE}/incidents/resource-allocations/${allocationId}/status`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status }),
        }
      );
      if (!response.ok) throw new Error(await getErrorMessage(response));

      const updatedAllocation = await response.json();
      setOptimization((current) => current && ({
        ...current,
        allocations: current.allocations.map((allocation) =>
          allocation.id === updatedAllocation.id ? updatedAllocation : allocation
        ),
      }));
    } catch (requestError) {
      setError(requestError.message || 'Could not update allocation status.');
    } finally {
      setUpdatingAllocation(null);
    }
  };

  const resourceById = useMemo(
    () => new Map(resources.map((resource) => [resource.id, resource])),
    [resources]
  );
  const allocations = optimization?.allocations || [];
  const unmetDemands = Array.isArray(optimization?.unmet_demand)
    ? optimization.unmet_demand
    : [];

  return (
    <section className="section optimization-dashboard">
      <div className="optimization-heading">
        <div>
          <h2>Resource Optimization</h2>
          <p className="optimization-description">
            Review suggested emergency resource assignments. Operators approve or reject each recommendation.
          </p>
        </div>
        <span className="optimization-note">Recommendations only — no resources are dispatched automatically.</span>
      </div>

      <div className="optimization-controls">
        <div className="form-group optimization-incident-picker">
          <label htmlFor="optimization-incident">Incident</label>
          <select
            id="optimization-incident"
            value={incidentId}
            onChange={(event) => setIncidentId(event.target.value)}
            disabled={!availableIncidents.length}
          >
            {!availableIncidents.length && <option value="">No active incidents available</option>}
            {availableIncidents.map((incident) => (
              <option key={incident.id} value={incident.id}>
                {incident.title} ({incident.status})
              </option>
            ))}
          </select>
        </div>
        <label className="optimization-rerun">
          <input
            type="checkbox"
            checked={forceRerun}
            onChange={(event) => setForceRerun(event.target.checked)}
          />
          Recalculate using latest data
        </label>
        <button
          type="button"
          className="btn-primary"
          onClick={runOptimization}
          disabled={!incidentId || running || loadingResult}
        >
          {running ? 'Optimizing…' : forceRerun ? 'Recalculate Optimization' : 'Run Optimization'}
        </button>
      </div>

      {error && <div className="analysis-error" role="alert">{error}</div>}
      {loadingResult && <p className="optimization-loading">Loading optimization results…</p>}

      {!loadingResult && incidentId && !optimization && !error && (
        <div className="optimization-empty">
          <p>No optimization result yet. Run optimization to see recommended resource assignments.</p>
        </div>
      )}

      {optimization && (
        <>
          <div className="optimization-summary">
            <div className="optimization-metric">
              <span>Solver status</span>
              <strong className={`solver-status ${String(optimization.solver_status || optimization.status).toLowerCase()}`}>
                {optimization.solver_status || optimization.status || 'Unknown'}
              </strong>
            </div>
            <div className="optimization-metric">
              <span>Objective value</span>
              <strong>{formatNumber(optimization.objective_value)}</strong>
            </div>
            <div className="optimization-metric">
              <span>Total travel distance</span>
              <strong>
                {formatNumber(
                  optimization.total_distance == null ? null : optimization.total_distance / 1000
                )}{' '}
                km
              </strong>
            </div>
            <div className="optimization-metric">
              <span>Resources assigned</span>
              <strong>{formatNumber(optimization.total_resources, 0)}</strong>
            </div>
          </div>

          {unmetDemands.length > 0 && (
            <div className="optimization-unmet">
              <h3>Unmet demands</h3>
              <ul>
                {unmetDemands.map((demand, index) => (
                  <li key={`${demand.resource_type || demand.type || 'demand'}-${index}`}>
                    {typeof demand === 'string'
                      ? demand
                      : `${demand.resource_type || demand.type || 'Resource'}: ${demand.unmet ?? 'some'} unmet (${demand.assigned ?? 0}/${demand.required ?? '?'} assigned)`}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {optimization.explanation && (
            <div className="optimization-explanation">
              <h3>Solver explanation</h3>
              <p>{optimization.explanation}</p>
            </div>
          )}

          <div className="optimization-allocations">
            <h3>Recommended allocations</h3>
            {!allocations.length ? (
              <p className="optimization-empty">No allocation details are available for this result.</p>
            ) : (
              <div className="optimization-table-wrap">
                <table className="optimization-table">
                  <thead>
                    <tr>
                      <th>Resource</th>
                      <th>Type</th>
                      <th>Distance</th>
                      <th>Assignment score</th>
                      <th>Status</th>
                      <th>Operator actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {allocations.map((allocation) => {
                      const status = String(allocation.status || 'recommended').toLowerCase();
                      const isUpdating = updatingAllocation === allocation.id;
                      const resource = resourceById.get(allocation.resource_id);
                      const resourceId = allocation.resource_id || '';
                      return (
                        <tr key={allocation.id}>
                          <td>{resource?.name || `Resource ${resourceId.slice(0, 8) || 'unknown'}`}</td>
                          <td>{String(allocation.resource_type || 'unknown').replaceAll('_', ' ')}</td>
                          <td>{formatNumber(allocation.distance_meters == null ? null : allocation.distance_meters / 1000)} km</td>
                          <td>{formatNumber(allocation.assignment_score)}</td>
                          <td><span className={`allocation-status ${status}`}>{status}</span></td>
                          <td>
                            {canManageAllocations && <div className="allocation-actions">
                              <button
                                type="button"
                                className="allocation-action approve"
                                onClick={() => updateAllocationStatus(allocation.id, 'approved')}
                                disabled={isUpdating || status !== 'recommended'}
                              >
                                Approve
                              </button>
                              <button
                                type="button"
                                className="allocation-action reject"
                                onClick={() => updateAllocationStatus(allocation.id, 'rejected')}
                                disabled={isUpdating || status !== 'recommended'}
                              >
                                Reject
                              </button>
                              <button
                                type="button"
                                className="allocation-action cancel"
                                onClick={() => updateAllocationStatus(allocation.id, 'cancelled')}
                                disabled={isUpdating || status !== 'approved'}
                              >
                                Cancel
                              </button>
                            </div>}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </section>
  );
}

export default OptimizationDashboard;
