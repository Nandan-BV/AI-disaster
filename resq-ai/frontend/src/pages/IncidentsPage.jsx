import React, { useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useAsyncData } from '../api/useAsyncData';
import { LoadingState, ErrorState, EmptyState } from '../components/common/StateViews';
import { formatDateTime, riskColor, statusColor } from '../utils/format';

const STATUS_OPTIONS = ['emerging', 'active', 'resolved'];
const RISK_OPTIONS = ['low', 'moderate', 'elevated', 'high', 'critical'];
const SORT_OPTIONS = [
  { value: 'last_updated', label: 'Last updated' },
  { value: 'risk_score', label: 'Risk score' },
  { value: 'event_count', label: 'Event count' },
];
const PAGE_SIZE = 20;

export default function IncidentsPage() {
  const [params, setParams] = useSearchParams();
  const [searchDraft, setSearchDraft] = useState(params.get('search') || '');

  const status = params.get('status') || '';
  const riskLevel = params.get('risk_level') || '';
  const search = params.get('search') || '';
  const sortBy = params.get('sort_by') || 'last_updated';
  const order = params.get('order') || 'desc';
  const page = Math.max(parseInt(params.get('page') || '1', 10), 1);

  const update = (patch) => {
    const next = new URLSearchParams(params);
    Object.entries(patch).forEach(([key, value]) => {
      if (value) next.set(key, value);
      else next.delete(key);
    });
    if (!('page' in patch)) next.delete('page');
    setParams(next, { replace: true });
  };

  const query = useMemo(() => {
    const q = new URLSearchParams();
    if (status) q.set('status', status);
    if (riskLevel) q.set('risk_level', riskLevel);
    if (search) q.set('search', search);
    q.set('sort_by', sortBy);
    q.set('order', order);
    q.set('limit', String(PAGE_SIZE));
    q.set('offset', String((page - 1) * PAGE_SIZE));
    return q.toString();
  }, [status, riskLevel, search, sortBy, order, page]);

  const { data, loading, error, reload } = useAsyncData(
    `/dashboard/incidents/summary?${query}`
  );

  const incidents = data?.incidents || [];
  const total = data?.total || 0;
  const totalPages = Math.max(Math.ceil(total / PAGE_SIZE), 1);
  const hasFilters = Boolean(status || riskLevel || search);

  const submitSearch = (e) => {
    e.preventDefault();
    update({ search: searchDraft.trim() });
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Incidents</h1>
          <p className="page-subtitle">
            Clustered incidents produced by the event-processing pipeline.
          </p>
        </div>
        <div className="page-actions">
          <button type="button" className="btn-secondary" onClick={reload} disabled={loading}>
            {loading ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>
      </div>

      <div className="card">
        <div className="toolbar">
          <div className="field">
            <label htmlFor="status">Status</label>
            <select
              id="status"
              value={status}
              onChange={(e) => update({ status: e.target.value })}
            >
              <option value="">All</option>
              {STATUS_OPTIONS.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label htmlFor="risk">Risk level</label>
            <select
              id="risk"
              value={riskLevel}
              onChange={(e) => update({ risk_level: e.target.value })}
            >
              <option value="">All</option>
              {RISK_OPTIONS.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label htmlFor="sort">Sort by</label>
            <select
              id="sort"
              value={sortBy}
              onChange={(e) => update({ sort_by: e.target.value })}
            >
              {SORT_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label htmlFor="order">Order</label>
            <select
              id="order"
              value={order}
              onChange={(e) => update({ order: e.target.value })}
            >
              <option value="desc">Descending</option>
              <option value="asc">Ascending</option>
            </select>
          </div>

          <form className="field" onSubmit={submitSearch} style={{ marginLeft: 'auto' }}>
            <label htmlFor="search">Search</label>
            <div style={{ display: 'flex', gap: 8 }}>
              <input
                id="search"
                type="search"
                value={searchDraft}
                placeholder="Title or type…"
                onChange={(e) => setSearchDraft(e.target.value)}
              />
              <button type="submit" className="btn-primary">
                Search
              </button>
              {hasFilters && (
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => {
                    setSearchDraft('');
                    setParams(new URLSearchParams(), { replace: true });
                  }}
                >
                  Clear
                </button>
              )}
            </div>
          </form>
        </div>
      </div>

      <div className="card">
        {loading && !data && <LoadingState label="Loading incidents…" />}
        {error && <ErrorState message={error} onRetry={reload} />}
        {!loading && !error && incidents.length === 0 && (
          <EmptyState
            message={hasFilters ? 'No incidents match these filters.' : 'No incidents yet.'}
          />
        )}

        {incidents.length > 0 && (
          <table className="data-table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Type</th>
                <th>Status</th>
                <th>Risk</th>
                <th>Events</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {incidents.map((incident) => (
                <tr key={incident.id}>
                  <td>
                    <Link className="link-row" to={`/incidents/${incident.id}`}>
                      {incident.title || 'Untitled incident'}
                    </Link>
                  </td>
                  <td>{incident.incident_type || 'unknown'}</td>
                  <td>
                    <span
                      className="badge"
                      style={{ background: statusColor(incident.status) }}
                    >
                      {incident.status}
                    </span>
                  </td>
                  <td>
                    {incident.risk_level ? (
                      <span
                        className="badge"
                        style={{ background: riskColor(incident.risk_level) }}
                      >
                        {incident.risk_level}
                        {incident.risk_score != null ? ` · ${Math.round(incident.risk_score)}` : ''}
                      </span>
                    ) : (
                      <span className="badge outline">no risk data</span>
                    )}
                  </td>
                  <td>{incident.event_count}</td>
                  <td className="muted">{formatDateTime(incident.last_updated)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {total > 0 && (
          <div className="pagination" style={{ marginTop: 16 }}>
            <span>
              Page {page} of {totalPages} · {total} incident{total === 1 ? '' : 's'}
            </span>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                type="button"
                className="btn-secondary"
                disabled={page <= 1}
                onClick={() => update({ page: String(page - 1) })}
              >
                Previous
              </button>
              <button
                type="button"
                className="btn-secondary"
                disabled={page >= totalPages}
                onClick={() => update({ page: String(page + 1) })}
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
