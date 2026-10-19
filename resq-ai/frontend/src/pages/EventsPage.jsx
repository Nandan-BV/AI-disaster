import React, { useState } from 'react';
import { apiGet, apiPost, apiDelete } from '../api/client';
import { useAsyncData } from '../api/useAsyncData';
import {
  LoadingState,
  ErrorState,
  EmptyState,
  UnavailableState,
} from '../components/common/StateViews';
import { formatDateTime } from '../utils/format';

const EVENT_TYPES = [
  'flood',
  'wildfire',
  'earthquake',
  'landslide',
  'cyclone',
  'building_collapse',
  'road_blockage',
  'tornado',
  'volcanic_activity',
];

const SOURCES = ['social_media', 'news', 'satellite', 'weather_service', 'emergency_services'];

const emptyForm = () => ({
  source: 'social_media',
  text_content: '',
  event_type: '',
  latitude: '',
  longitude: '',
  location_name: '',
  timestamp: new Date().toISOString().slice(0, 16),
  image_url: '',
  video_url: '',
});

export default function EventsPage() {
  const events = useAsyncData('/events');
  const [form, setForm] = useState(emptyForm);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [selected, setSelected] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [analysisError, setAnalysisError] = useState(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);

  const list = events.data?.events || [];

  const setField = (name, value) => setForm((prev) => ({ ...prev, [name]: value }));

  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setSubmitError(null);
    try {
      const payload = {
        source: form.source,
        text_content: form.text_content || null,
        event_type: form.event_type || null,
        latitude: parseFloat(form.latitude),
        longitude: parseFloat(form.longitude),
        location_name: form.location_name || null,
        timestamp: form.timestamp,
        image_url: form.image_url || null,
        video_url: form.video_url || null,
        metadata: {},
      };
      await apiPost('/events', payload);
      setForm(emptyForm());
      events.reload();
    } catch (err) {
      setSubmitError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const selectEvent = (event) => {
    setSelected(event);
    setAnalysis(null);
    setAnalysisError(null);
  };

  const runAnalysis = async () => {
    if (!selected) return;
    setAnalysisLoading(true);
    setAnalysisError(null);
    try {
      const data = await apiPost(`/events/${selected.id}/analyze`, {});
      setAnalysis({ record: data, fields: data.analysis || data });
    } catch (err) {
      setAnalysisError(err.message);
    } finally {
      setAnalysisLoading(false);
    }
  };

  const viewStored = async () => {
    if (!selected) return;
    setAnalysisLoading(true);
    setAnalysisError(null);
    try {
      const data = await apiGet(`/events/${selected.id}/analysis`);
      setAnalysis({ record: data, fields: data.analysis || data });
    } catch (err) {
      if (err.status === 404) setAnalysisError('No stored analysis. Run analysis first.');
      else setAnalysisError(err.message);
    } finally {
      setAnalysisLoading(false);
    }
  };

  const removeEvent = async (event) => {
    if (!window.confirm('Delete this event?')) return;
    try {
      await apiDelete(`/events/${event.id}`);
      if (selected?.id === event.id) {
        setSelected(null);
        setAnalysis(null);
      }
      events.reload();
    } catch (err) {
      setSubmitError(err.message);
    }
  };

  const analysisFields = analysis?.fields;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Events</h1>
          <p className="page-subtitle">
            Raw multimodal reports feeding the incident pipeline.
          </p>
        </div>
        <button
          type="button"
          className="btn-secondary"
          onClick={events.reload}
          disabled={events.loading}
        >
          {events.loading ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      <div className="grid cols-2">
        <div className="card">
          <h3 className="section-title">Submit event report</h3>
          <form onSubmit={submit}>
            <div className="field">
              <label htmlFor="source">Source *</label>
              <select
                id="source"
                value={form.source}
                onChange={(e) => setField('source', e.target.value)}
              >
                {SOURCES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="event_type">Event type</label>
              <select
                id="event_type"
                value={form.event_type}
                onChange={(e) => setField('event_type', e.target.value)}
              >
                <option value="">Select…</option>
                {EVENT_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>
            <div style={{ display: 'flex', gap: 12 }}>
              <div className="field" style={{ flex: 1 }}>
                <label htmlFor="latitude">Latitude *</label>
                <input
                  id="latitude"
                  type="number"
                  step="0.0001"
                  value={form.latitude}
                  onChange={(e) => setField('latitude', e.target.value)}
                  required
                />
              </div>
              <div className="field" style={{ flex: 1 }}>
                <label htmlFor="longitude">Longitude *</label>
                <input
                  id="longitude"
                  type="number"
                  step="0.0001"
                  value={form.longitude}
                  onChange={(e) => setField('longitude', e.target.value)}
                  required
                />
              </div>
            </div>
            <div className="field">
              <label htmlFor="location_name">Location name</label>
              <input
                id="location_name"
                value={form.location_name}
                onChange={(e) => setField('location_name', e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="text_content">Text content</label>
              <textarea
                id="text_content"
                rows="3"
                value={form.text_content}
                onChange={(e) => setField('text_content', e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="timestamp">Timestamp *</label>
              <input
                id="timestamp"
                type="datetime-local"
                value={form.timestamp}
                onChange={(e) => setField('timestamp', e.target.value)}
                required
              />
            </div>
            {submitError && <div className="error-banner" style={{ marginBottom: 12 }}>{submitError}</div>}
            <button type="submit" className="btn-primary" disabled={submitting}>
              {submitting ? 'Submitting…' : 'Submit event'}
            </button>
          </form>
        </div>

        <div className="card">
          <h3 className="section-title">Events ({list.length})</h3>
          {events.loading && !events.data && <LoadingState />}
          {events.error && <ErrorState message={events.error} onRetry={events.reload} />}
          {!events.loading && !events.error && list.length === 0 && (
            <EmptyState message="No events yet. Submit one on the left." />
          )}
          {list.length > 0 && (
            <div className="list" style={{ maxHeight: 560, overflowY: 'auto' }}>
              {list.map((event) => (
                <div
                  key={event.id}
                  className={`list-item clickable ${selected?.id === event.id ? 'active' : ''}`}
                  onClick={() => selectEvent(event)}
                >
                  <div>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <span className="badge outline">{event.event_type || 'unknown'}</span>
                      <span className="muted">{event.source}</span>
                    </div>
                    <div className="muted" style={{ fontSize: '0.82rem', marginTop: 4 }}>
                      {event.location_name || `${event.latitude}, ${event.longitude}`} ·{' '}
                      {formatDateTime(event.timestamp)}
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn-danger"
                    onClick={(e) => {
                      e.stopPropagation();
                      removeEvent(event);
                    }}
                  >
                    Delete
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {selected && (
        <div className="card">
          <div className="card-header">
            <h3>Analysis · {selected.event_type || 'unknown'}</h3>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                type="button"
                className="btn-primary"
                onClick={runAnalysis}
                disabled={analysisLoading}
              >
                {analysisLoading ? 'Analyzing…' : 'Analyze event'}
              </button>
              <button
                type="button"
                className="btn-secondary"
                onClick={viewStored}
                disabled={analysisLoading}
              >
                View stored analysis
              </button>
            </div>
          </div>

          {analysisError && <div className="error-banner">{analysisError}</div>}

          {analysisFields && (
            <div className="grid cols-2">
              <dl className="kv">
                <dt>Disaster type</dt>
                <dd>{analysisFields.disaster_type || 'Not classified'}</dd>
                <dt>Summary</dt>
                <dd className="pre-wrap">{analysisFields.summary || '—'}</dd>
                <dt>People affected</dt>
                <dd>{analysisFields.people_affected || 'Not specified'}</dd>
                <dt>Evidence</dt>
                <dd className="pre-wrap">{analysisFields.evidence_description || '—'}</dd>
              </dl>
              <div>
                {['severity_indicators', 'location_mentions', 'damage_observed', 'vehicles_observed', 'infrastructure_damage', 'environmental_conditions'].map(
                  (key) =>
                    Array.isArray(analysisFields[key]) &&
                    analysisFields[key].length > 0 && (
                      <div key={key} style={{ marginBottom: 10 }}>
                        <div className="muted" style={{ fontSize: '0.8rem', textTransform: 'capitalize' }}>
                          {key.replace(/_/g, ' ')}
                        </div>
                        <ul style={{ margin: '4px 0 0 18px' }}>
                          {analysisFields[key].map((item, i) => (
                            <li key={i}>{item}</li>
                          ))}
                        </ul>
                      </div>
                    )
                )}
                {!analysisFields.disaster_type && !analysisFields.summary && (
                  <UnavailableState message="Analysis returned no structured fields." />
                )}
              </div>
            </div>
          )}

          {analysis && (
            <details className="raw-json">
              <summary>View raw JSON</summary>
              <pre>{JSON.stringify(analysis.record, null, 2)}</pre>
            </details>
          )}
        </div>
      )}
    </div>
  );
}
