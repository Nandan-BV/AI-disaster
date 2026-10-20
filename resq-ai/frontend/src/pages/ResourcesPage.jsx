import React, { useState } from 'react';
import { apiPost, apiPatch } from '../api/client';
import { useAsyncData } from '../api/useAsyncData';
import { LoadingState, ErrorState, EmptyState } from '../components/common/StateViews';
import { formatPercent } from '../utils/format';

const RESOURCE_TYPES = [
  'ambulance',
  'rescue_team',
  'fire_vehicle',
  'police_unit',
  'shelter',
  'hospital',
  'drone',
  'emergency_vehicle',
];

const STATUSES = ['available', 'deployed', 'unavailable', 'maintenance', 'unknown'];

const STATUS_COLORS = {
  available: '#2e7d32',
  deployed: '#e65100',
  unavailable: '#c62828',
  maintenance: '#f57c00',
  unknown: '#757575',
};

const emptyForm = () => ({
  name: '',
  resource_type: '',
  status: 'available',
  latitude: '',
  longitude: '',
  address: '',
  capacity: '',
  current_load: '',
  organization: '',
});

export default function ResourcesPage() {
  const resources = useAsyncData('/resources');
  const [form, setForm] = useState(emptyForm);
  const [statusFilter, setStatusFilter] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);

  const all = Array.isArray(resources.data?.resources) ? resources.data.resources : [];
  const counts = STATUSES.reduce((acc, s) => {
    acc[s] = all.filter((r) => r.status === s).length;
    return acc;
  }, {});
  const list = statusFilter ? all.filter((r) => r.status === statusFilter) : all;

  const setField = (name, value) => setForm((prev) => ({ ...prev, [name]: value }));

  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      if (
        form.capacity &&
        form.current_load &&
        parseInt(form.current_load, 10) > parseInt(form.capacity, 10)
      ) {
        throw new Error('Current load cannot exceed capacity.');
      }
      await apiPost('/resources', {
        name: form.name,
        resource_type: form.resource_type,
        status: form.status,
        latitude: parseFloat(form.latitude),
        longitude: parseFloat(form.longitude),
        address: form.address || null,
        capacity: form.capacity ? parseInt(form.capacity, 10) : null,
        current_load: form.current_load ? parseInt(form.current_load, 10) : null,
        organization: form.organization || null,
      });
      setForm(emptyForm());
      setMessage('Resource created.');
      resources.reload();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const updateStatus = async (resource, status) => {
    setError(null);
    try {
      await apiPatch(`/resources/${resource.id}/status`, { status });
      resources.reload();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Resources</h1>
          <p className="page-subtitle">Inventory and availability for allocation.</p>
        </div>
        <button
          type="button"
          className="btn-secondary"
          onClick={resources.reload}
          disabled={resources.loading}
        >
          {resources.loading ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      <div className="grid cols-4">
        {STATUSES.map((s) => (
          <div key={s} className="stat">
            <div className="stat-value" style={{ color: STATUS_COLORS[s] }}>
              {counts[s]}
            </div>
            <div className="stat-label">{s}</div>
          </div>
        ))}
      </div>

      <div className="grid cols-2">
        <div className="card">
          <h3 className="section-title">Add resource</h3>
          <form onSubmit={submit}>
            <div className="field">
              <label htmlFor="name">Name *</label>
              <input
                id="name"
                value={form.name}
                onChange={(e) => setField('name', e.target.value)}
                required
              />
            </div>
            <div className="field">
              <label htmlFor="resource_type">Type *</label>
              <select
                id="resource_type"
                value={form.resource_type}
                onChange={(e) => setField('resource_type', e.target.value)}
                required
              >
                <option value="">Select…</option>
                {RESOURCE_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>
            <div style={{ display: 'flex', gap: 12 }}>
              <div className="field" style={{ flex: 1 }}>
                <label htmlFor="lat">Latitude *</label>
                <input
                  id="lat"
                  type="number"
                  step="0.0001"
                  value={form.latitude}
                  onChange={(e) => setField('latitude', e.target.value)}
                  required
                />
              </div>
              <div className="field" style={{ flex: 1 }}>
                <label htmlFor="lon">Longitude *</label>
                <input
                  id="lon"
                  type="number"
                  step="0.0001"
                  value={form.longitude}
                  onChange={(e) => setField('longitude', e.target.value)}
                  required
                />
              </div>
            </div>
            <div style={{ display: 'flex', gap: 12 }}>
              <div className="field" style={{ flex: 1 }}>
                <label htmlFor="capacity">Capacity</label>
                <input
                  id="capacity"
                  type="number"
                  value={form.capacity}
                  onChange={(e) => setField('capacity', e.target.value)}
                />
              </div>
              <div className="field" style={{ flex: 1 }}>
                <label htmlFor="current_load">Current load</label>
                <input
                  id="current_load"
                  type="number"
                  value={form.current_load}
                  onChange={(e) => setField('current_load', e.target.value)}
                />
              </div>
            </div>
            {error && <div className="error-banner" style={{ marginBottom: 12 }}>{error}</div>}
            {message && <div className="success-banner" style={{ marginBottom: 12 }}>{message}</div>}
            <button type="submit" className="btn-primary" disabled={submitting}>
              {submitting ? 'Saving…' : 'Add resource'}
            </button>
          </form>
        </div>

        <div className="card">
          <div className="card-header">
            <h3>Inventory ({list.length})</h3>
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="">All statuses</option>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>

          {resources.loading && !resources.data && <LoadingState />}
          {resources.error && <ErrorState message={resources.error} onRetry={resources.reload} />}
          {!resources.loading && !resources.error && list.length === 0 && (
            <EmptyState message="No resources." />
          )}

          {list.length > 0 && (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Load</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {list.map((r) => (
                  <tr key={r.id}>
                    <td>{r.name}</td>
                    <td>{r.resource_type}</td>
                    <td>
                      {r.capacity
                        ? `${r.current_load || 0}/${r.capacity} (${formatPercent(
                            (r.current_load || 0) / r.capacity
                          )})`
                        : '—'}
                    </td>
                    <td>
                      <select
                        value={r.status}
                        onChange={(e) => updateStatus(r, e.target.value)}
                        style={{
                          borderLeft: `4px solid ${STATUS_COLORS[r.status] || '#757575'}`,
                        }}
                      >
                        {STATUSES.map((s) => (
                          <option key={s} value={s}>
                            {s}
                          </option>
                        ))}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
