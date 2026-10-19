import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { apiGet } from '../api/client';
import './CommandCenter.css';

const METRIC_CARDS = [
  { key: 'active', label: 'Active Incidents', icon: '🚨', color: '#1a73e8', filter: 'active' },
  { key: 'critical_risk', label: 'Critical Risk', icon: '🔴', color: '#c62828', filter: 'critical' },
  { key: 'high_risk', label: 'High Risk', icon: '🟠', color: '#f57c00', filter: 'high' },
  { key: 'with_unmet_demand', label: 'Unmet Demand', icon: '⚠️', color: '#e65100', path: '/optimization' },
  { key: 'pending_approvals', label: 'Pending Approvals', icon: '📋', color: '#6a1b9a', path: '/optimization' },
  { key: 'available', label: 'Available Resources', icon: '🚑', color: '#2e7d32', path: '/resources' },
];

export default function CommandCenter() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastRefresh, setLastRefresh] = useState(null);
  const navigate = useNavigate();

  const fetchOverview = async () => {
    try {
      const result = await apiGet('/dashboard/overview');
      setData(result);
      setLastRefresh(new Date());
      setError(null);
    } catch (err) {
      setError(err.message || 'Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOverview();
    const interval = setInterval(fetchOverview, 30000);
    return () => clearInterval(interval);
  }, []);

  const getMetricValue = (key) => {
    if (!data) return loading ? '—' : 'N/A';
    if (key === 'pending_approvals') return data.optimization_metrics?.pending_approvals || 0;
    if (key === 'available') return data.resource_metrics?.available || 0;
    return data.incident_metrics?.[key] || 0;
  };

  if (loading && !data) {
    return (
      <div className="command-center">
        <div className="loading-state">Loading Command Center...</div>
      </div>
    );
  }

  return (
    <div className="command-center">
      <div className="page-header">
        <h1>Command Center</h1>
        <p className="page-subtitle">Emergency Operations Overview</p>
        <div className="page-actions">
          {lastRefresh && (
            <span className="last-refresh">
              Last updated: {lastRefresh.toLocaleTimeString()}
            </span>
          )}
          <button className="btn-secondary" onClick={fetchOverview} disabled={loading}>
            {loading ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {/* Metric Cards */}
      <section className="metrics-grid">
        {METRIC_CARDS.map((metric) => (
          <article
            key={metric.key}
            className="metric-card"
            onClick={() => {
              if (metric.path) {
                navigate(metric.path);
              } else if (metric.filter === 'active') {
                navigate('/incidents?status=active');
              } else if (metric.filter) {
                navigate(`/incidents?risk_level=${metric.filter}`);
              }
            }}
            style={{ '--metric-color': metric.color }}
          >
            <div className="metric-icon" style={{ background: metric.color }}>{metric.icon}</div>
            <div className="metric-content">
              <div className="metric-value">{getMetricValue(metric.key)}</div>
              <div className="metric-label">{metric.label}</div>
            </div>
          </article>
        ))}
      </section>

      {/* Critical Incidents & Recent Activity */}
      <div className="dashboard-grid">
        {/* Critical Incidents Panel */}
        <section className="panel critical-panel">
          <div className="panel-header">
            <h2>Critical Incidents</h2>
            <Link to="/incidents" className="view-all">View All</Link>
          </div>
          <div className="panel-content">
            {data?.recent_incidents?.length === 0 ? (
              <div className="empty-state">No incidents found</div>
            ) : (
              <div className="incident-list">
                {data.recent_incidents
                  .filter(i => i.risk_level === 'critical' || i.risk_level === 'high')
                  .slice(0, 5)
                  .map((incident) => (
                    <Link key={incident.id} to={`/incidents/${incident.id}`} className="incident-row">
                      <div className="incident-info">
                        <div className="incident-title-row">
                          <span className="incident-title">{incident.title || 'Untitled Incident'}</span>
                          <span className={`risk-badge ${incident.risk_level || 'unknown'}`}>
                            {incident.risk_level?.toUpperCase() || 'NO RISK DATA'}
                          </span>
                        </div>
                        <div className="incident-meta">
                          <span className={`status-badge ${incident.status || 'unknown'}`}>
                            {incident.status}
                          </span>
                          <span>{incident.event_count} events</span>
                          <span>{incident.location_name || 'Unknown location'}</span>
                        </div>
                      </div>
                      <div className="incident-time">
                        {incident.last_updated ? new Date(incident.last_updated).toLocaleString() : 'Unknown'}
                      </div>
                    </Link>
                  ))}
              </div>
            )}
            {data?.recent_incidents?.filter(i => i.risk_level === 'critical' || i.risk_level === 'high').length === 0 && (
              <div className="empty-state">No critical or high-risk incidents</div>
            )}
          </div>
        </section>

        {/* Recent Events Panel */}
        <section className="panel events-panel">
          <div className="panel-header">
            <h2>Recent Events</h2>
            <Link to="/events" className="view-all">View All</Link>
          </div>
          <div className="panel-content">
            {data?.recent_events?.length === 0 ? (
              <div className="empty-state">No events recorded</div>
            ) : (
              <div className="event-list">
                {data.recent_events.slice(0, 5).map((event) => (
                  <div key={event.id} className="event-row">
                    <div className="event-info">
                      <div className="event-type-badge">{event.event_type || 'unknown'}</div>
                      <div className="event-source">{event.source}</div>
                    </div>
                    <div className="event-details">
                      <div className="event-location">{event.location_name || `${event.latitude?.toFixed(4)}, ${event.longitude?.toFixed(4)}`}</div>
                      <div className="event-time">{event.timestamp ? new Date(event.timestamp).toLocaleString() : 'Unknown'}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>

        {/* Pending Approvals Panel */}
        <section className="panel approvals-panel">
          <div className="panel-header">
            <h2>Pending Approvals</h2>
            <Link to="/optimization" className="view-all">View All</Link>
          </div>
          <div className="panel-content">
            {data?.pending_approvals?.length === 0 ? (
              <div className="empty-state">No pending approvals</div>
            ) : (
              <div className="approval-list">
                {data.pending_approvals.slice(0, 5).map((approval) => (
                  <Link key={approval.allocation_id} to={`/incidents/${approval.incident_id}`} className="approval-row">
                    <div className="approval-info">
                      <div className="approval-incident">{approval.incident_title}</div>
                      <div className="approval-details">
                        <span>{approval.resource_type}</span>
                        <span>{approval.distance_meters ? `${Math.round(approval.distance_meters)}m` : 'Unknown distance'}</span>
                      </div>
                    </div>
                    <div className="approval-time">
                      {approval.created_at ? new Date(approval.created_at).toLocaleString() : 'Unknown'}
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </section>
      </div>

      {/* Resource Status Summary */}
      <section className="panel resources-summary-panel">
        <div className="panel-header">
          <h2>Resource Status Summary</h2>
          <Link to="/resources" className="view-all">View All</Link>
        </div>
        <div className="panel-content">
          <div className="resource-summary-grid">
            <div className="resource-summary-card available">
              <div className="resource-summary-value">{data?.resource_metrics?.available || 0}</div>
              <div className="resource-summary-label">Available</div>
            </div>
            <div className="resource-summary-card deployed">
              <div className="resource-summary-value">{data?.resource_metrics?.deployed || 0}</div>
              <div className="resource-summary-label">Deployed</div>
            </div>
            <div className="resource-summary-card total">
              <div className="resource-summary-value">{data?.resource_metrics?.total || 0}</div>
              <div className="resource-summary-label">Total Resources</div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}