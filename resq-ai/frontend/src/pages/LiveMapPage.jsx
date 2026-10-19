import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAsyncData } from '../api/useAsyncData';
import { LoadingState, ErrorState, EmptyState } from '../components/common/StateViews';
import MapView from '../MapView';
import { statusColor } from '../utils/format';

export default function LiveMapPage() {
  const incidents = useAsyncData('/incidents');
  const [selectedId, setSelectedId] = useState(null);

  const list = useMemo(() => incidents.data?.incidents || [], [incidents.data]);

  useEffect(() => {
    if (!selectedId && list.length > 0) setSelectedId(list[0].id);
  }, [list, selectedId]);

  const selected = list.find((i) => i.id === selectedId) || null;
  const hasCoords =
    selected && selected.centroid_latitude != null && selected.centroid_longitude != null;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Live Map</h1>
          <p className="page-subtitle">
            Select an incident to view its analysis area and nearby infrastructure.
          </p>
        </div>
      </div>

      {incidents.loading && !incidents.data && <LoadingState label="Loading map data…" />}
      {incidents.error && <ErrorState message={incidents.error} onRetry={incidents.reload} />}
      {!incidents.loading && !incidents.error && list.length === 0 && (
        <EmptyState message="No incidents to display on the map." />
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
                  onClick={() => setSelectedId(incident.id)}
                >
                  <div>
                    <div>{incident.title || 'Untitled'}</div>
                    <span
                      className="badge"
                      style={{ background: statusColor(incident.status), marginTop: 4 }}
                    >
                      {incident.status}
                    </span>
                  </div>
                  {incident.centroid_latitude == null && (
                    <span className="muted" title="No coordinates">
                      no coords
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            {selected ? (
              <>
                <div className="card-header">
                  <h3>{selected.title || 'Untitled incident'}</h3>
                  <Link className="link-row" to={`/incidents/${selected.id}`}>
                    Open workspace →
                  </Link>
                </div>
                {hasCoords ? (
                  <MapView
                    incidentId={selected.id}
                    center={[selected.centroid_longitude, selected.centroid_latitude]}
                    zoom={13}
                  />
                ) : (
                  <EmptyState message="This incident has no coordinates." />
                )}
              </>
            ) : (
              <EmptyState message="Select an incident." />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
