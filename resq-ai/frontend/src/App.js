<<<<<<< HEAD
import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import DashboardLayout from './components/layout/DashboardLayout';
import { LoadingState } from './components/common/StateViews';
import CommandCenter from './pages/CommandCenter';
import IncidentsPage from './pages/IncidentsPage';
import IncidentDetail from './pages/IncidentDetail';
import EventsPage from './pages/EventsPage';
import LiveMapPage from './pages/LiveMapPage';
import InvestigationsPage from './pages/InvestigationsPage';
import RiskPage from './pages/RiskPage';
import ResourcesPage from './pages/ResourcesPage';
import OptimizationPage from './pages/OptimizationPage';
import CopilotPage from './pages/CopilotPage';
import SystemStatusPage from './pages/SystemStatusPage';
// Shared legacy styles provide the base styling for the reused copilot UI
// (copilot-*, section, buttons). pages.css is imported after it so command
// center styles take precedence on any shared class names.
import './App.css';
import './pages/pages.css';

// The pre-dashboard single-page UI is preserved as-is at /console and only
// loaded on demand so its global styles do not leak into the command center.
const LegacyConsole = lazy(() => import('./LegacyConsole'));

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<DashboardLayout />}>
          <Route path="/" element={<CommandCenter />} />
          <Route path="/incidents" element={<IncidentsPage />} />
          <Route path="/incidents/:incidentId" element={<IncidentDetail />} />
          <Route path="/events" element={<EventsPage />} />
          <Route path="/map" element={<LiveMapPage />} />
          <Route path="/investigations" element={<InvestigationsPage />} />
          <Route path="/risk" element={<RiskPage />} />
          <Route path="/resources" element={<ResourcesPage />} />
          <Route path="/optimization" element={<OptimizationPage />} />
          <Route path="/copilot" element={<CopilotPage />} />
          <Route path="/system-status" element={<SystemStatusPage />} />
        </Route>
        <Route
          path="/console"
          element={
            <Suspense fallback={<LoadingState label="Loading console…" />}>
              <LegacyConsole />
            </Suspense>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
=======
import React, { useState, useEffect } from 'react';
import './App.css';
import MapView from './MapView';
import Copilot from './components/copilot/Copilot';
import OptimizationDashboard from './components/optimization/OptimizationDashboard';
import AuthPanel from './components/auth/AuthPanel';
import { apiFetch } from './api';

const API_BASE = '/api/v1';

const riskLevelColors = {
  low: '#2e7d32',
  moderate: '#1a73e8',
  elevated: '#f57c00',
  high: '#e65100',
  critical: '#c62828',
};

const resourceTypeIcons = {
  ambulance: '🚑',
  rescue_team: '🚒',
  fire_vehicle: '🚒',
  police_unit: '👮',
  shelter: '🏠',
  hospital: '🏥',
  drone: '🚁',
  emergency_vehicle: '🚚',
};

const resourceStatusColors = {
  available: '#2e7d32',
  deployed: '#e65100',
  unavailable: '#c62828',
  maintenance: '#f57c00',
  unknown: '#757575',
};

function App() {
  const [currentUser, setCurrentUser] = useState(null);
  const [authChecking, setAuthChecking] = useState(true);
  const [backendStatus, setBackendStatus] = useState('checking');
  const [events, setEvents] = useState([]);
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [incidentsLoading, setIncidentsLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('events');
  const [formData, setFormData] = useState({
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
  const [submitStatus, setSubmitStatus] = useState(null);
  const [createdEvent, setCreatedEvent] = useState(null);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState(null);
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [investigationResult, setInvestigationResult] = useState(null);
  const [investigationLoading, setInvestigationLoading] = useState(false);
  const [investigationError, setInvestigationError] = useState(null);
  const [evidenceItems, setEvidenceItems] = useState([]);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [riskResult, setRiskResult] = useState(null);
  const [riskLoading, setRiskLoading] = useState(false);
  const [riskError, setRiskError] = useState(null);
  const [impactResult, setImpactResult] = useState(null);
  const [impactLoading, setImpactLoading] = useState(false);
  const [impactError, setImpactError] = useState(null);
  const [riskHistory, setRiskHistory] = useState([]);
  const [riskHistoryLoading, setRiskHistoryLoading] = useState(false);
  const [resources, setResources] = useState([]);
  const [resourcesLoading, setResourcesLoading] = useState(false);
  const [selectedResource, setSelectedResource] = useState(null);
  const [resourceFormData, setResourceFormData] = useState({
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
  const [resourceSubmitStatus, setResourceSubmitStatus] = useState(null);

  useEffect(() => {
    checkBackend();
  }, []);

  useEffect(() => {
    let active = true;
    const token = window.localStorage.getItem('resq-ai-access-token');
    if (!token) {
      setAuthChecking(false);
      return undefined;
    }

    apiFetch(`${API_BASE}/auth/me`)
      .then(async response => {
        if (!response.ok) throw new Error('Stored session is no longer valid.');
        const user = await response.json();
        if (active) setCurrentUser(user);
      })
      .catch(() => {
        window.localStorage.removeItem('resq-ai-access-token');
      })
      .finally(() => {
        if (active) setAuthChecking(false);
      });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    const expireSession = () => {
      window.localStorage.removeItem('resq-ai-access-token');
      setCurrentUser(null);
    };
    window.addEventListener('resq-ai-auth-expired', expireSession);
    return () => window.removeEventListener('resq-ai-auth-expired', expireSession);
  }, []);

  useEffect(() => {
    if (!currentUser) return;
    fetchEvents();
    fetchIncidents();
  }, [currentUser]);

  useEffect(() => {
    if (!currentUser) return undefined;
    let socket;
    let reconnectTimer;
    let stopped = false;

    const connect = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      socket = new WebSocket(`${protocol}//${window.location.host}/ws/events`);
      socket.onmessage = (message) => {
        try {
          const payload = JSON.parse(message.data);
          if (payload.type !== 'event.created' || !payload.event?.id) return;
          const event = payload.event;
          setEvents(previous => {
            const merged = new Map([
              ...previous.map(item => [item.id, item]),
              [event.id, event],
            ]);
            return [...merged.values()]
              .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
              .slice(0, 100);
          });
          fetchIncidents();
        } catch (error) {
          console.error('Received an invalid live-event update:', error);
        }
      };
      socket.onerror = (error) => {
        console.error('Live event WebSocket encountered an error:', error);
        socket.close();
      };
      socket.onclose = () => {
        if (!stopped) reconnectTimer = window.setTimeout(connect, 2000);
      };
    };

    connect();
    return () => {
      stopped = true;
      window.clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, [currentUser]);

  const checkBackend = async () => {
    try {
      const response = await apiFetch(`${API_BASE}/health`);
      if (response.ok) {
        setBackendStatus('connected');
      } else {
        setBackendStatus('error');
      }
    } catch {
      setBackendStatus('disconnected');
    }
  };

  const fetchEvents = async () => {
    setLoading(true);
    try {
      const response = await apiFetch(`${API_BASE}/events`);
      if (response.ok) {
        const data = await response.json();
        setEvents(previous => {
          const merged = new Map(
            [...(data.events || []), ...previous].map(event => [event.id, event])
          );
          return [...merged.values()]
            .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
            .slice(0, 100);
        });
      }
    } catch (error) {
      console.error('Failed to fetch events:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchIncidents = async () => {
    setIncidentsLoading(true);
    try {
      const response = await apiFetch(`${API_BASE}/incidents`);
      if (response.ok) {
        const data = await response.json();
        setIncidents(data.incidents || []);
      }
    } catch (error) {
      console.error('Failed to fetch incidents:', error);
    } finally {
      setIncidentsLoading(false);
    }
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitStatus('submitting');
    setCreatedEvent(null);

    const payload = {
      source: formData.source,
      text_content: formData.text_content || null,
      event_type: formData.event_type || null,
      latitude: parseFloat(formData.latitude),
      longitude: parseFloat(formData.longitude),
      location_name: formData.location_name || null,
      timestamp: formData.timestamp,
      image_url: formData.image_url || null,
      video_url: formData.video_url || null,
      metadata: {},
    };

    try {
      const response = await apiFetch(`${API_BASE}/events`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (response.ok) {
        const data = await response.json();
        setCreatedEvent(data);
        setSubmitStatus('success');
        setFormData(prev => ({ ...prev, text_content: '', event_type: '', location_name: '', image_url: '', video_url: '' }));
        fetchEvents();
      } else {
        const error = await response.json();
        setSubmitStatus(`error: ${JSON.stringify(error.detail)}`);
      }
    } catch (error) {
      setSubmitStatus(`error: ${error.message}`);
    }
  };

  const deleteEvent = async (id) => {
    if (!window.confirm('Delete this event?')) return;
    try {
      const response = await apiFetch(`${API_BASE}/events/${id}`, { method: 'DELETE' });
      if (response.ok) {
        fetchEvents();
        if (selectedEvent?.id === id) {
          setSelectedEvent(null);
          setAnalysisResult(null);
        }
      }
    } catch (error) {
      console.error('Failed to delete event:', error);
    }
  };

  const selectEvent = (event) => {
    setSelectedEvent(event);
    setAnalysisResult(null);
    setAnalysisError(null);
  };

  const runAnalysis = async (event) => {
    setAnalysisLoading(true);
    setAnalysisError(null);
    try {
      const response = await apiFetch(`${API_BASE}/events/${event.id}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });

      if (response.ok) {
        const data = await response.json();
        setAnalysisResult(data);
      } else {
        const error = await response.json();
        setAnalysisError(error.detail || 'Analysis failed');
      }
    } catch (error) {
      setAnalysisError(error.message);
    } finally {
      setAnalysisLoading(false);
    }
  };

  const fetchAnalysis = async (event) => {
    setAnalysisLoading(true);
    setAnalysisError(null);
    try {
      const response = await apiFetch(`${API_BASE}/events/${event.id}/analysis`);
      if (response.ok) {
        const data = await response.json();
        setAnalysisResult(data);
      } else if (response.status === 404) {
        setAnalysisError('No analysis found. Click "Analyze Event" to run analysis.');
      } else {
        const error = await response.json();
        setAnalysisError(error.detail || 'Failed to fetch analysis');
      }
    } catch (error) {
      setAnalysisError(error.message);
    } finally {
      setAnalysisLoading(false);
    }
  };

  const selectIncident = async (incident) => {
    setSelectedIncident(incident);
    setInvestigationResult(null);
    setInvestigationError(null);
    setEvidenceItems([]);
    await fetchInvestigation(incident.id);
    await fetchEvidence(incident.id);
  };

  const fetchInvestigation = async (incidentId) => {
    setInvestigationLoading(true);
    setInvestigationError(null);
    try {
      const response = await apiFetch(`${API_BASE}/incidents/${incidentId}/investigation-summary`);
      if (response.ok) {
        const data = await response.json();
        setInvestigationResult(data);
      } else if (response.status === 404) {
        setInvestigationError('No investigation found. Click "Investigate Incident" to run investigation.');
      } else {
        const error = await response.json();
        setInvestigationError(error.detail || 'Failed to fetch investigation');
      }
    } catch (error) {
      setInvestigationError(error.message);
    } finally {
      setInvestigationLoading(false);
    }
  };

  const runInvestigation = async (incidentId) => {
    setInvestigationLoading(true);
    setInvestigationError(null);
    try {
      const response = await apiFetch(`${API_BASE}/incidents/${incidentId}/investigate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ force_rerun: true }),
      });

      if (response.ok) {
        const data = await response.json();
        // Fetch the full investigation summary
        const summaryResponse = await apiFetch(`${API_BASE}/incidents/${incidentId}/investigation-summary`);
        if (summaryResponse.ok) {
          const summaryData = await summaryResponse.json();
          setInvestigationResult(summaryData);
        }
        fetchIncidents(); // Refresh incidents list
      } else {
        const error = await response.json();
        setInvestigationError(error.detail || 'Investigation failed');
      }
    } catch (error) {
      setInvestigationError(error.message);
    } finally {
      setInvestigationLoading(false);
    }
  };

  const fetchEvidence = async (incidentId) => {
    setEvidenceLoading(true);
    try {
      const response = await apiFetch(`${API_BASE}/incidents/${incidentId}/evidence?limit=100`);
      if (response.ok) {
        const data = await response.json();
        setEvidenceItems(data.evidence || []);
      }
    } catch (error) {
      console.error('Failed to fetch evidence:', error);
    } finally {
      setEvidenceLoading(false);
    }
  };

  const runRiskAssessment = async (incidentId) => {
    setRiskLoading(true);
    setRiskError(null);
    setImpactResult(null);
    try {
      const response = await apiFetch(`${API_BASE}/incidents/${incidentId}/risk-assessment`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });

      if (response.ok) {
        const data = await response.json();
        setRiskResult(data);
        // Also fetch impact
        const impactResponse = await apiFetch(`${API_BASE}/incidents/${incidentId}/impact`);
        if (impactResponse.ok) {
          const impactData = await impactResponse.json();
          setImpactResult(impactData);
        }
        // Fetch risk history
        const historyResponse = await apiFetch(`${API_BASE}/incidents/${incidentId}/risk-history`);
        if (historyResponse.ok) {
          const historyData = await historyResponse.json();
          setRiskHistory(historyData);
        }
        fetchIncidents(); // Refresh incidents list
      } else {
        const error = await response.json();
        setRiskError(error.detail || 'Risk assessment failed');
      }
    } catch (error) {
      setRiskError(error.message);
    } finally {
      setRiskLoading(false);
    }
  };

  const recalculateRisk = async (incidentId) => {
    setRiskLoading(true);
    setRiskError(null);
    try {
      const response = await apiFetch(`${API_BASE}/incidents/${incidentId}/risk-assessment/recalculate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });

      if (response.ok) {
        const data = await response.json();
        setRiskResult(data);
        // Also fetch impact
        const impactResponse = await apiFetch(`${API_BASE}/incidents/${incidentId}/impact`);
        if (impactResponse.ok) {
          const impactData = await impactResponse.json();
          setImpactResult(impactData);
        }
        // Fetch risk history
        const historyResponse = await apiFetch(`${API_BASE}/incidents/${incidentId}/risk-history`);
        if (historyResponse.ok) {
          const historyData = await historyResponse.json();
          setRiskHistory(historyData);
        }
        fetchIncidents();
      } else {
        const error = await response.json();
        setRiskError(error.detail || 'Risk recalculation failed');
      }
    } catch (error) {
      setRiskError(error.message);
    } finally {
      setRiskLoading(false);
    }
  };

  const fetchImpact = async (incidentId) => {
    setImpactLoading(true);
    setImpactError(null);
    try {
      const response = await apiFetch(`${API_BASE}/incidents/${incidentId}/impact`);
      if (response.ok) {
        const data = await response.json();
        setImpactResult(data);
      } else if (response.status === 404) {
        setImpactError('No impact assessment found. Run risk assessment first.');
      } else {
        const error = await response.json();
        setImpactError(error.detail || 'Failed to fetch impact');
      }
    } catch (error) {
      setImpactError(error.message);
    } finally {
      setImpactLoading(false);
    }
  };

  const fetchRiskHistory = async (incidentId) => {
    setRiskHistoryLoading(true);
    try {
      const response = await apiFetch(`${API_BASE}/incidents/${incidentId}/risk-history`);
      if (response.ok) {
        const data = await response.json();
        setRiskHistory(data);
      }
    } catch (error) {
      console.error('Failed to fetch risk history:', error);
    } finally {
      setRiskHistoryLoading(false);
    }
  };

  const fetchResources = async () => {
    setResourcesLoading(true);
    try {
      const response = await apiFetch(`${API_BASE}/resources`);
      if (response.ok) {
        const data = await response.json();
        setResources(data);
      }
    } catch (error) {
      console.error('Failed to fetch resources:', error);
    } finally {
      setResourcesLoading(false);
    }
  };

  const handleResourceChange = (e) => {
    const { name, value } = e.target;
    setResourceFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleResourceSubmit = async (e) => {
    e.preventDefault();
    setResourceSubmitStatus('submitting');
    try {
      const payload = {
        name: resourceFormData.name,
        resource_type: resourceFormData.resource_type,
        status: resourceFormData.status,
        latitude: parseFloat(resourceFormData.latitude),
        longitude: parseFloat(resourceFormData.longitude),
        address: resourceFormData.address || null,
        capacity: resourceFormData.capacity ? parseInt(resourceFormData.capacity) : null,
        current_load: resourceFormData.current_load ? parseInt(resourceFormData.current_load) : null,
        organization: resourceFormData.organization || null,
      };
      
      // Validate capacity/current_load
      if (payload.capacity !== null && payload.current_load !== null && payload.current_load > payload.capacity) {
        setResourceSubmitStatus('error: current load cannot exceed capacity');
        return;
      }

      const response = await apiFetch(`${API_BASE}/resources`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (response.ok) {
        const data = await response.json();
        setResourceSubmitStatus('success');
        setResourceFormData(prev => ({ ...prev, name: '', resource_type: '', latitude: '', longitude: '', address: '', capacity: '', current_load: '', organization: '' }));
        fetchResources();
      } else {
        const error = await response.json();
        setResourceSubmitStatus(`error: ${JSON.stringify(error.detail)}`);
      }
    } catch (error) {
      setResourceSubmitStatus(`error: ${error.message}`);
    }
  };

  const updateResourceStatus = async (resourceId, status) => {
    try {
      const response = await apiFetch(`${API_BASE}/resources/${resourceId}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      });

      if (response.ok) {
        const data = await response.json();
        // Update local state
        setResources(prev => prev.map(r => r.id === resourceId ? data : r));
        if (selectedResource?.id === resourceId) {
          setSelectedResource(data);
        }
      } else {
        const error = await response.json();
        alert(error.detail || 'Failed to update status');
      }
    } catch (error) {
      alert(error.message);
    }
  };

  const selectResource = (resource) => {
    setSelectedResource(resource);
  };


  const statusColors = {
    connected: '#2e7d32',
    disconnected: '#c62828',
    error: '#c62828',
    checking: '#f57c00',
  };

  const incidentStatusColors = {
    emerging: '#f57c00',
    active: '#1a73e8',
    resolved: '#2e7d32',
  };

  const assessmentColors = {
    strongly_supported: '#2e7d32',
    moderately_supported: '#1a73e8',
    weakly_supported: '#f57c00',
    conflicting: '#c62828',
    insufficient_evidence: '#f57c00',
    inconclusive: '#757575',
  };

  if (authChecking) {
    return <main className="auth-page"><section className="section auth-card">Checking your session...</section></main>;
  }

  if (!currentUser) {
    return <AuthPanel onAuthenticated={setCurrentUser} />;
  }

  return (
    <div className="app">
      <header className="header">
        <h1>RESQ-AI</h1>
        <p>Multimodal Disaster Intelligence & Emergency Response Copilot</p>
        <div className="status-indicator">
          Backend: <span style={{ color: statusColors[backendStatus] }}>{backendStatus.toUpperCase()}</span>
        </div>
        <div className="auth-user">
          Signed in as {currentUser.username} ({currentUser.role})
          <button
            type="button"
            className="btn-secondary"
            onClick={() => {
              window.localStorage.removeItem('resq-ai-access-token');
              setCurrentUser(null);
            }}
          >
            Sign out
          </button>
        </div>
      </header>

<nav className="tab-nav">
        <button
          className={`tab-btn ${activeTab === 'events' ? 'active' : ''}`}
          onClick={() => setActiveTab('events')}
        >
          Events ({events.length})
        </button>
        <button
          className={`tab-btn ${activeTab === 'incidents' ? 'active' : ''}`}
          onClick={() => setActiveTab('incidents')}
        >
          Incidents ({incidents.length})
        </button>
        <button
          className={`tab-btn ${activeTab === 'resources' ? 'active' : ''}`}
          onClick={() => setActiveTab('resources')}
        >
          Resources ({resources.length})
        </button>
        <button
          className={`tab-btn ${activeTab === 'risk' ? 'active' : ''}`}
          onClick={() => setActiveTab('risk')}
        >
          Risk & Impact
        </button>
        <button
          className={`tab-btn ${activeTab === 'optimization' ? 'active' : ''}`}
          onClick={() => setActiveTab('optimization')}
        >
          Optimization
        </button>
        <button
          className={`tab-btn ${activeTab === 'map' ? 'active' : ''}`}
          onClick={() => setActiveTab('map')}
        >
          Map
        </button>
        <button
          className={`tab-btn ${activeTab === 'copilot' ? 'active' : ''}`}
          onClick={() => setActiveTab('copilot')}
        >
          Copilot
        </button>
      </nav>

      <main className="main">
        {activeTab === 'events' && (
          <>
            <section className="section">
              <h2>Submit Event Report</h2>
              <form onSubmit={handleSubmit} className="event-form">
                <div className="form-row">
                  <div className="form-group">
                    <label htmlFor="source">Source *</label>
                    <select id="source" name="source" value={formData.source} onChange={handleChange} required>
                      <option value="social_media">Social Media</option>
                      <option value="news">News</option>
                      <option value="satellite">Satellite</option>
                      <option value="weather_service">Weather Service</option>
                      <option value="emergency_services">Emergency Services</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label htmlFor="event_type">Event Type</label>
                    <select id="event_type" name="event_type" value={formData.event_type} onChange={handleChange}>
                      <option value="">Select...</option>
                      <option value="flood">Flood</option>
                      <option value="wildfire">Wildfire</option>
                      <option value="earthquake">Earthquake</option>
                      <option value="landslide">Landslide</option>
                      <option value="cyclone">Cyclone</option>
                      <option value="building_collapse">Building Collapse</option>
                      <option value="road_blockage">Road Blockage</option>
                      <option value="tornado">Tornado</option>
                      <option value="volcanic_activity">Volcanic Activity</option>
                    </select>
                  </div>
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label htmlFor="latitude">Latitude *</label>
                    <input
                      type="number"
                      id="latitude"
                      name="latitude"
                      step="0.0001"
                      min="-90"
                      max="90"
                      value={formData.latitude}
                      onChange={handleChange}
                      required
                      placeholder="e.g., 12.9716"
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="longitude">Longitude *</label>
                    <input
                      type="number"
                      id="longitude"
                      name="longitude"
                      step="0.0001"
                      min="-180"
                      max="180"
                      value={formData.longitude}
                      onChange={handleChange}
                      required
                      placeholder="e.g., 77.5946"
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label htmlFor="location_name">Location Name</label>
                  <input
                    type="text"
                    id="location_name"
                    name="location_name"
                    value={formData.location_name}
                    onChange={handleChange}
                    placeholder="e.g., Bengaluru, Karnataka"
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="text_content">Text Content</label>
                  <textarea
                    id="text_content"
                    name="text_content"
                    value={formData.text_content}
                    onChange={handleChange}
                    rows="3"
                    placeholder="Description of the event..."
                  />
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label htmlFor="timestamp">Timestamp *</label>
                    <input
                      type="datetime-local"
                      id="timestamp"
                      name="timestamp"
                      value={formData.timestamp}
                      onChange={handleChange}
                      required
                    />
                  </div>
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label htmlFor="image_url">Image URL</label>
                    <input
                      type="url"
                      id="image_url"
                      name="image_url"
                      value={formData.image_url}
                      onChange={handleChange}
                      placeholder="https://example.com/image.jpg"
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="video_url">Video URL</label>
                    <input
                      type="url"
                      id="video_url"
                      name="video_url"
                      value={formData.video_url}
                      onChange={handleChange}
                      placeholder="https://example.com/video.mp4"
                    />
                  </div>
                </div>

                <button type="submit" disabled={submitStatus === 'submitting'}>
                  {submitStatus === 'submitting' ? 'Submitting...' : 'Submit Event'}
                </button>

                {submitStatus && (
                  <div className={`submit-status ${submitStatus.startsWith('error') ? 'error' : 'success'}`}>
                    {submitStatus}
                  </div>
                )}
              </form>

              {createdEvent && (
                <div className="created-event">
                  <h3>Event Created Successfully</h3>
                  <pre>{JSON.stringify(createdEvent, null, 2)}</pre>
                </div>
              )}
            </section>

            <section className="section">
              <h2>Existing Events ({events.length})</h2>
              {loading ? (
                <p>Loading...</p>
              ) : events.length === 0 ? (
                <p>No events yet. Submit one above!</p>
              ) : (
                <div className="events-list">
                  {events.map(event => (
                    <div key={event.id} className={`event-card ${selectedEvent?.id === event.id ? 'selected' : ''}`} onClick={() => selectEvent(event)}>
                      <div className="event-header">
                        <span className="event-source">{event.source}</span>
                        <span className="event-type">{event.event_type || 'unknown'}</span>
                      </div>
                      <div className="event-location">
                        {event.location_name || `${event.latitude}, ${event.longitude}`}
                      </div>
                      {event.text_content && <p className="event-text">{event.text_content}</p>}
                      <div className="event-meta">
                        <span>{new Date(event.timestamp).toLocaleString()}</span>
                        <button onClick={(e) => { e.stopPropagation(); deleteEvent(event.id); }} className="delete-btn">Delete</button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>

            {selectedEvent && (
              <section className="section analysis-section">
                <h2>AI Analysis for Event</h2>
                <div className="event-preview">
                  <div className="event-header">
                    <span className="event-source">{selectedEvent.source}</span>
                    <span className="event-type">{selectedEvent.event_type || 'unknown'}</span>
                  </div>
                  <div className="event-location">
                    {selectedEvent.location_name || `${selectedEvent.latitude}, ${selectedEvent.longitude}`}
                  </div>
                  {selectedEvent.text_content && <p className="event-text">{selectedEvent.text_content}</p>}
                  {selectedEvent.image_url && (
                    <div className="media-preview">
                      <img src={selectedEvent.image_url} alt="Event image" onError={(e) => e.target.style.display='none'} />
                    </div>
                  )}
                  {selectedEvent.video_url && (
                    <div className="media-preview">
                      <video src={selectedEvent.video_url} controls onError={(e) => e.target.style.display='none'} />
                    </div>
                  )}
                </div>

                <div className="analysis-actions">
                  <button
                    onClick={() => runAnalysis(selectedEvent)}
                    disabled={analysisLoading}
                    className="btn-primary"
                  >
                    {analysisLoading ? 'Analyzing...' : 'Analyze Event'}
                  </button>
                  <button
                    onClick={() => fetchAnalysis(selectedEvent)}
                    disabled={analysisLoading}
                    className="btn-secondary"
                  >
                    View Stored Analysis
                  </button>
                </div>

                {analysisError && (
                  <div className="analysis-error">
                    {analysisError}
                  </div>
                )}

                {analysisResult && (
                  <div className="analysis-result">
                    <h3>Analysis Result</h3>
                    <div className="analysis-meta">
                      <span><strong>Model:</strong> {analysisResult.model_name}</span>
                      <span><strong>Modality:</strong> {analysisResult.modality}</span>
                      <span><strong>Created:</strong> {new Date(analysisResult.created_at).toLocaleString()}</span>
                    </div>
                    <div className="analysis-fields">
                      <div className="analysis-field">
                        <label>Disaster Type</label>
                        <span className={`disaster-type ${analysisResult.analysis.disaster_type || ''}`}>
                          {analysisResult.analysis.disaster_type || 'Not classified'}
                          {analysisResult.analysis.disaster_type_confidence && (
                            <span className="confidence">
                              ({Math.round(analysisResult.analysis.disaster_type_confidence * 100)}%)
                            </span>
                          )}
                        </span>
                      </div>
                      <div className="analysis-field">
                        <label>Summary</label>
                        <p>{analysisResult.analysis.summary || 'No summary available'}</p>
                      </div>
                      <div className="analysis-field">
                        <label>Severity Indicators</label>
                        <ul>
                          {analysisResult.analysis.severity_indicators.map((item, i) => (
                            <li key={i}>{item}</li>
                          ))}
                        </ul>
                      </div>
                      <div className="analysis-field">
                        <label>Location Mentions</label>
                        <ul>
                          {analysisResult.analysis.location_mentions.map((item, i) => (
                            <li key={i}>{item}</li>
                          ))}
                        </ul>
                      </div>
                      <div className="analysis-field">
                        <label>Damage Observed</label>
                        <ul>
                          {analysisResult.analysis.damage_observed.map((item, i) => (
                            <li key={i}>{item}</li>
                          ))}
                        </ul>
                      </div>
                      <div className="analysis-field">
                        <label>People Affected</label>
                        <p>{analysisResult.analysis.people_affected || 'Not specified'}</p>
                      </div>
                      <div className="analysis-field">
                        <label>Vehicles Observed</label>
                        <ul>
                          {analysisResult.analysis.vehicles_observed.map((item, i) => (
                            <li key={i}>{item}</li>
                          ))}
                        </ul>
                      </div>
                      <div className="analysis-field">
                        <label>Infrastructure Damage</label>
                        <ul>
                          {analysisResult.analysis.infrastructure_damage.map((item, i) => (
                            <li key={i}>{item}</li>
                          ))}
                        </ul>
                      </div>
                      <div className="analysis-field">
                        <label>Environmental Conditions</label>
                        <ul>
                          {analysisResult.analysis.environmental_conditions.map((item, i) => (
                            <li key={i}>{item}</li>
                          ))}
                        </ul>
                      </div>
                      <div className="analysis-field">
                        <label>Evidence Description</label>
                        <p>{analysisResult.analysis.evidence_description}</p>
                      </div>
                    </div>
                    <details className="raw-json">
                      <summary>View Raw JSON</summary>
                      <pre>{JSON.stringify(analysisResult.analysis, null, 2)}</pre>
                    </details>
                  </div>
                )}
              </section>
            )}
          </>
        )}

        {activeTab === 'incidents' && (
          <>
            <section className="section">
              <h2>Incidents ({incidents.length})</h2>
              {incidentsLoading ? (
                <p>Loading...</p>
              ) : incidents.length === 0 ? (
                <p>No incidents yet. Process events to create incidents.</p>
              ) : (
                <div className="incidents-list">
                  {incidents.map(incident => (
                    <div key={incident.id} className={`incident-card ${selectedIncident?.id === incident.id ? 'selected' : ''}`} onClick={() => selectIncident(incident)}>
                      <div className="incident-header">
                        <span className="incident-type">{incident.incident_type || 'unknown'}</span>
                        <span className={`incident-status ${incident.status}`}>{incident.status}</span>
                      </div>
                      <div className="incident-title">{incident.title}</div>
                      <div className="incident-meta">
                        <span>Events: {incident.event_count}</span>
                        <span>Location: {incident.location_name || `${incident.centroid_latitude?.toFixed(4)}, ${incident.centroid_longitude?.toFixed(4)}`}</span>
                        <span>Updated: {new Date(incident.last_updated).toLocaleString()}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>

            {selectedIncident && (
              <section className="section investigation-section">
                <h2>Evidence Investigation: {selectedIncident.title}</h2>

                <div className="incident-summary">
                  <div className="summary-row">
                    <span><strong>Type:</strong> {selectedIncident.incident_type || 'unknown'}</span>
                    <span><strong>Events:</strong> {selectedIncident.event_count}</span>
                    <span><strong>Status:</strong> <span className={`status-badge ${selectedIncident.status}`}>{selectedIncident.status}</span></span>
                    <span><strong>Confidence:</strong> {selectedIncident.confidence ? Math.round(selectedIncident.confidence * 100) + '%' : 'N/A'}</span>
                  </div>
                  <div className="summary-row">
                    <span><strong>Location:</strong> {selectedIncident.location_name || `(${selectedIncident.centroid_latitude?.toFixed(4)}, ${selectedIncident.centroid_longitude?.toFixed(4)})`}</span>
                    <span><strong>Started:</strong> {new Date(selectedIncident.start_time).toLocaleString()}</span>
                    <span><strong>Updated:</strong> {new Date(selectedIncident.last_updated).toLocaleString()}</span>
                  </div>
                </div>

                <div className="investigation-actions">
                  <button
                    onClick={() => runInvestigation(selectedIncident.id)}
                    disabled={investigationLoading}
                    className="btn-primary"
                  >
                    {investigationLoading ? 'Investigating...' : 'Investigate Incident'}
                  </button>
                  <button
                    onClick={() => fetchInvestigation(selectedIncident.id)}
                    disabled={investigationLoading}
                    className="btn-secondary"
                  >
                    View Stored Investigation
                  </button>
                </div>

                {investigationError && (
                  <div className="analysis-error">
                    {investigationError}
                  </div>
                )}

                {investigationResult && (
                  <div className="investigation-result">
                    <div className="investigation-header">
                      <h3>Investigation Result</h3>
                      <span className={`assessment-badge ${investigationResult.assessment}`}>
                        {investigationResult.assessment.replace('_', ' ').toUpperCase()}
                      </span>
                    </div>

                    <div className="investigation-metrics">
                      <div className="metric">
                        <label>Evidence Confidence</label>
                        <div className="metric-bar">
                          <div className="metric-fill" style={{ width: `${Math.round((investigationResult.evidence_confidence_score || 0) * 100)}%` }}></div>
                        </div>
                        <span>{Math.round((investigationResult.evidence_confidence_score || 0) * 100)}%</span>
                      </div>
                      <div className="metric">
                        <label>Source Diversity</label>
                        <div className="metric-bar">
                          <div className="metric-fill" style={{ width: `${Math.round((investigationResult.source_diversity || 0) * 100)}%` }}></div>
                        </div>
                        <span>{Math.round((investigationResult.source_diversity || 0) * 100)}%</span>
                      </div>
                      <div className="metric">
                        <label>Geographic Consistency</label>
                        <div className="metric-bar">
                          <div className="metric-fill" style={{ width: `${Math.round((investigationResult.geographic_consistency || 0) * 100)}%` }}></div>
                        </div>
                        <span>{Math.round((investigationResult.geographic_consistency || 0) * 100)}%</span>
                      </div>
                      <div className="metric">
                        <label>Temporal Consistency</label>
                        <div className="metric-bar">
                          <div className="metric-fill" style={{ width: `${Math.round((investigationResult.temporal_consistency || 0) * 100)}%` }}></div>
                        </div>
                        <span>{Math.round((investigationResult.temporal_consistency || 0) * 100)}%</span>
                      </div>
                      <div className="metric">
                        <label>Multimodal Consistency</label>
                        <div className="metric-bar">
                          <div className="metric-fill" style={{ width: `${Math.round((investigationResult.multimodal_consistency || 0) * 100)}%` }}></div>
                        </div>
                        <span>{Math.round((investigationResult.multimodal_consistency || 0) * 100)}%</span>
                      </div>
                    </div>

                    <div className="investigation-explanation">
                      <h4>Explanation</h4>
                      <p>{investigationResult.explanation}</p>
                    </div>

                    {investigationResult.limitations && (
                      <div className="investigation-limitations">
                        <h4>Limitations</h4>
                        <p>{investigationResult.limitations}</p>
                      </div>
                    )}

                    <div className="evidence-categories">
                      <div className="evidence-category supporting">
                        <h4>Supporting Evidence ({investigationResult.supporting_evidence.length})</h4>
                        {investigationResult.supporting_evidence.map((item, i) => (
                          <div key={i} className="evidence-item">
                            <div className="evidence-meta">
                              <span className="evidence-type">{item.evidence_type}</span>
                              <span className="evidence-quality">Quality: {Math.round((item.evidence_quality || 0) * 100)}%</span>
                            </div>
                            <p>{item.description}</p>
                            {item.source && <span className="evidence-source">Source: {item.source}</span>}
                          </div>
                        ))}
                      </div>

                      <div className="evidence-category contradicting">
                        <h4>Contradicting Evidence ({investigationResult.contradicting_evidence.length})</h4>
                        {investigationResult.contradicting_evidence.map((item, i) => (
                          <div key={i} className="evidence-item">
                            <div className="evidence-meta">
                              <span className="evidence-type">{item.evidence_type}</span>
                              <span className="evidence-quality">Quality: {Math.round((item.evidence_quality || 0) * 100)}%</span>
                            </div>
                            <p>{item.description}</p>
                            {item.source && <span className="evidence-source">Source: {item.source}</span>}
                          </div>
                        ))}
                      </div>

                      <div className="evidence-category uncertain">
                        <h4>Uncertain Evidence ({investigationResult.uncertain_evidence.length})</h4>
                        {investigationResult.uncertain_evidence.map((item, i) => (
                          <div key={i} className="evidence-item">
                            <div className="evidence-meta">
                              <span className="evidence-type">{item.evidence_type}</span>
                              <span className="evidence-quality">Quality: {Math.round((item.evidence_quality || 0) * 100)}%</span>
                            </div>
                            <p>{item.description}</p>
                            {item.source && <span className="evidence-source">Source: {item.source}</span>}
                          </div>
                        ))}
                      </div>

                      <div className="evidence-category neutral">
                        <h4>Neutral Evidence ({investigationResult.neutral_evidence.length})</h4>
                        {investigationResult.neutral_evidence.map((item, i) => (
                          <div key={i} className="evidence-item">
                            <div className="evidence-meta">
                              <span className="evidence-type">{item.evidence_type}</span>
                              <span className="evidence-quality">Quality: {Math.round((item.evidence_quality || 0) * 100)}%</span>
                            </div>
                            <p>{item.description}</p>
                            {item.source && <span className="evidence-source">Source: {item.source}</span>}
                          </div>
                        ))}
                      </div>
                    </div>

                    <details className="raw-json">
                      <summary>View Raw JSON</summary>
                      <pre>{JSON.stringify(investigationResult, null, 2)}</pre>
                    </details>
                  </div>
                )}

                {evidenceItems.length > 0 && !investigationResult && (
                  <div className="evidence-list-section">
                    <h3>Collected Evidence ({evidenceItems.length})</h3>
                    <div className="evidence-list">
                      {evidenceItems.map((item, i) => (
                        <div key={i} className={`evidence-item ${item.evidence_role}`}>
                          <div className="evidence-meta">
                            <span className="evidence-type">{item.evidence_type}</span>
                            <span className="evidence-role">{item.evidence_role}</span>
                            <span className="evidence-quality">Quality: {Math.round((item.evidence_quality || 0) * 100)}%</span>
                          </div>
                          <p>{item.description}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </section>
            )}
          </>
        )}

        {activeTab === 'copilot' && <Copilot incidents={incidents} />}

        {activeTab === 'optimization' && <OptimizationDashboard incidents={incidents} userRole={currentUser.role} />}

        {activeTab === 'map' && (
          <section className="section map-section">
            <h2>Geospatial Map View</h2>
            <p className="map-description">
              Select an incident for its geographic context and nearby infrastructure.
              Newly reported events also appear live on the map.
            </p>
            <MapView
              incidentId={selectedIncident?.id}
              center={selectedIncident
                ? [selectedIncident.centroid_longitude, selectedIncident.centroid_latitude]
                : events[0]
                  ? [events[0].longitude, events[0].latitude]
                  : [77.5946, 12.9716]}
              zoom={13}
              liveEvents={events}
            />
            {!selectedIncident && (
              <div className="no-incident-selected">
                <p>No incident selected. Live report locations are still displayed.</p>
              </div>
            )}
          </section>
        )}

        {activeTab === 'risk' && (
          <section className="section risk-section">
            <h2>Risk & Impact Assessment</h2>
            <p className="risk-description">
              Select an incident from the Incidents tab, then run a risk assessment to evaluate 
              severity, evidence confidence, population exposure, infrastructure risk, environmental factors, and accessibility.
            </p>
            {selectedIncident && (
              <>
                <div className="incident-risk-summary">
                  <div className="summary-row">
                    <span><strong>Type:</strong> {selectedIncident.incident_type || 'unknown'}</span>
                    <span><strong>Events:</strong> {selectedIncident.event_count}</span>
                    <span><strong>Status:</strong> <span className={`status-badge ${selectedIncident.status}`}>{selectedIncident.status}</span></span>
                    <span><strong>Confidence:</strong> {selectedIncident.confidence ? Math.round(selectedIncident.confidence * 100) + '%' : 'N/A'}</span>
                  </div>
                  <div className="summary-row">
                    <span><strong>Location:</strong> {selectedIncident.location_name || `(${selectedIncident.centroid_latitude?.toFixed(4)}, ${selectedIncident.centroid_longitude?.toFixed(4)})`}</span>
                    <span><strong>Started:</strong> {new Date(selectedIncident.start_time).toLocaleString()}</span>
                    <span><strong>Updated:</strong> {new Date(selectedIncident.last_updated).toLocaleString()}</span>
                  </div>
                </div>

                <div className="risk-actions">
                  <button
                    onClick={() => runRiskAssessment(selectedIncident.id)}
                    disabled={riskLoading}
                    className="btn-primary"
                  >
                    {riskLoading ? 'Assessing...' : 'Run Risk Assessment'}
                  </button>
                  <button
                    onClick={() => recalculateRisk(selectedIncident.id)}
                    disabled={riskLoading}
                    className="btn-secondary"
                  >
                    Recalculate Risk
                  </button>
                  <button
                    onClick={() => fetchImpact(selectedIncident.id)}
                    disabled={impactLoading}
                    className="btn-secondary"
                  >
                    View Impact
                  </button>
                  <button
                    onClick={() => fetchRiskHistory(selectedIncident.id)}
                    disabled={riskHistoryLoading}
                    className="btn-secondary"
                  >
                    View Risk History
                  </button>
                </div>

                {riskError && (
                  <div className="analysis-error">
                    {riskError}
                  </div>
                )}

                {riskResult && (
                  <div className="risk-result">
                    <div className="risk-header">
                      <h3>Risk Assessment Result</h3>
                      <span className={`risk-level-badge ${riskResult.risk_level}`}>
                        {riskResult.risk_level.toUpperCase()}
                      </span>
                    </div>

                    <div className="risk-score-display">
                      <div className="risk-score-circle" style={{ borderColor: riskLevelColors[riskResult.risk_level] }}>
                        <span className="risk-score-value" style={{ color: riskLevelColors[riskResult.risk_level] }}>
                          {riskResult.risk_score}
                        </span>
                        <span className="risk-score-label">/ 100</span>
                      </div>
                    </div>

                    <div className="risk-metrics">
                      <div className="metric">
                        <label>Severity</label>
                        <div className="metric-bar">
                          <div className="metric-fill" style={{ width: `${riskResult.severity_component || 0}%` }}></div>
                        </div>
                        <span>{Math.round(riskResult.severity_component || 0)}%</span>
                      </div>
                      <div className="metric">
                        <label>Evidence</label>
                        <div className="metric-bar">
                          <div className="metric-fill" style={{ width: `${riskResult.evidence_component || 0}%` }}></div>
                        </div>
                        <span>{Math.round(riskResult.evidence_component || 0)}%</span>
                      </div>
                      <div className="metric">
                        <label>Population</label>
                        <div className="metric-bar">
                          <div className="metric-fill" style={{ width: `${riskResult.population_component || 0}%` }}></div>
                        </div>
                        <span>{Math.round(riskResult.population_component || 0)}%</span>
                      </div>
                      <div className="metric">
                        <label>Infrastructure</label>
                        <div className="metric-bar">
                          <div className="metric-fill" style={{ width: `${riskResult.infrastructure_component || 0}%` }}></div>
                        </div>
                        <span>{Math.round(riskResult.infrastructure_component || 0)}%</span>
                      </div>
                      <div className="metric">
                        <label>Environment</label>
                        <div className="metric-bar">
                          <div className="metric-fill" style={{ width: `${riskResult.environment_component || 0}%` }}></div>
                        </div>
                        <span>{Math.round(riskResult.environment_component || 0)}%</span>
                      </div>
                      <div className="metric">
                        <label>Accessibility</label>
                        <div className="metric-bar">
                          <div className="metric-fill" style={{ width: `${riskResult.accessibility_component || 0}%` }}></div>
                        </div>
                        <span>{Math.round(riskResult.accessibility_component || 0)}%</span>
                      </div>
                    </div>

                    <div className="risk-explanation">
                      <h4>Assessment Explanation</h4>
                      <p>{riskResult.explanation}</p>
                    </div>

                    <div className="risk-components-detail">
                      <h4>Component Details</h4>
                      <div className="components-grid">
                        {riskResult.severity_details && (
                          <details className="component-detail">
                            <summary>Severity Component</summary>
                            <pre>{JSON.stringify(riskResult.severity_details, null, 2)}</pre>
                          </details>
                        )}
                        {riskResult.evidence_details && (
                          <details className="component-detail">
                            <summary>Evidence Component</summary>
                            <pre>{JSON.stringify(riskResult.evidence_details, null, 2)}</pre>
                          </details>
                        )}
                        {riskResult.population_details && (
                          <details className="component-detail">
                            <summary>Population Component</summary>
                            <pre>{JSON.stringify(riskResult.population_details, null, 2)}</pre>
                          </details>
                        )}
                        {riskResult.infrastructure_details && (
                          <details className="component-detail">
                            <summary>Infrastructure Component</summary>
                            <pre>{JSON.stringify(riskResult.infrastructure_details, null, 2)}</pre>
                          </details>
                        )}
                        {riskResult.environment_details && (
                          <details className="component-detail">
                            <summary>Environment Component</summary>
                            <pre>{JSON.stringify(riskResult.environment_details, null, 2)}</pre>
                          </details>
                        )}
                        {riskResult.accessibility_details && (
                          <details className="component-detail">
                            <summary>Accessibility Component</summary>
                            <pre>{JSON.stringify(riskResult.accessibility_details, null, 2)}</pre>
                          </details>
                        )}
                      </div>
                    </div>
                    <details className="raw-json">
                      <summary>View Raw JSON</summary>
                      <pre>{JSON.stringify(riskResult, null, 2)}</pre>
                    </details>
                  </div>
                )}

                {impactResult && (
                  <div className="impact-result">
                    <h3>Impact Assessment</h3>
                    <div className="impact-metrics">
                      <div className="impact-metric">
                        <label>Population Potentially Exposed</label>
                        <span className="impact-value">{impactResult.population_potentially_exposed ? impactResult.population_potentially_exposed.toLocaleString() : 'N/A'}</span>
                      </div>
                      <div className="impact-metric">
                        <label>Population Zones Affected</label>
                        <span className="impact-value">{impactResult.population_zones_count || 0}</span>
                      </div>
                      <div className="impact-metric">
                        <label>Infrastructure in Area</label>
                        <span className="impact-value">{impactResult.infrastructure_potentially_exposed || 0}</span>
                      </div>
                      <div className="impact-metric">
                        <label>Hospitals</label>
                        <span className="impact-value">{impactResult.hospitals_count || 0}</span>
                      </div>
                      <div className="impact-metric">
                        <label>Shelters</label>
                        <span className="impact-value">{impactResult.shelters_count || 0}</span>
                      </div>
                      <div className="impact-metric">
                        <label>Fire Stations</label>
                        <span className="impact-value">{impactResult.fire_stations_count || 0}</span>
                      </div>
                      <div className="impact-metric">
                        <label>Police Stations</label>
                        <span className="impact-value">{impactResult.police_stations_count || 0}</span>
                      </div>
                      <div className="impact-metric">
                        <label>Schools</label>
                        <span className="impact-value">{impactResult.schools_count || 0}</span>
                      </div>
                      <div className="impact-metric">
                        <label>Bridges</label>
                        <span className="impact-value">{impactResult.bridges_count || 0}</span>
                      </div>
                      <div className="impact-metric">
                        <label>Roads</label>
                        <span className="impact-value">{impactResult.roads_count || 0}</span>
                      </div>
                      <div className="impact-metric">
                        <label>Emergency Centers</label>
                        <span className="impact-value">{impactResult.emergency_centers_count || 0}</span>
                      </div>
                      <div className="impact-metric">
                        <label>Power Stations</label>
                        <span className="impact-value">{impactResult.power_stations_count || 0}</span>
                      </div>
                      <div className="impact-metric">
                        <label>Water Facilities</label>
                        <span className="impact-value">{impactResult.water_facilities_count || 0}</span>
                      </div>
                      <div className="impact-metric">
                        <label>Roads Affected</label>
                        <span className="impact-value">{impactResult.roads_potentially_affected || 0}</span>
                      </div>
                      <div className="impact-metric">
                        <label>Bridges Affected</label>
                        <span className="impact-value">{impactResult.bridges_potentially_affected || 0}</span>
                      </div>
                      <div className="impact-metric">
                        <label>Accessibility</label>
                        <span className={`impact-value ${impactResult.accessibility_status}`}>{impactResult.accessibility_status || 'unknown'}</span>
                      </div>
                    </div>

                    {impactResult.explanation && (
                      <div className="impact-explanation">
                        <h4>Impact Explanation</h4>
                        <p>{impactResult.explanation}</p>
                      </div>
                    )}
                    <details className="raw-json">
                      <summary>View Raw JSON</summary>
                      <pre>{JSON.stringify(impactResult, null, 2)}</pre>
                    </details>
                  </div>
                )}

                {riskHistory.length > 0 && (
                  <div className="risk-history-section">
                    <h3>Risk History ({riskHistory.length})</h3>
                    {riskHistoryLoading && <p>Loading history...</p>}
                    <div className="risk-history-list">
                      {riskHistory.map((item, i) => (
                        <div key={i} className={`risk-history-item ${item.risk_level}`}>
                          <div className="history-meta">
                            <span className="history-time">{new Date(item.assessed_at).toLocaleString()}</span>
                            <span className={`history-trigger ${item.trigger}`}>{item.trigger || 'manual'}</span>
                          </div>
                          <div className="history-score" style={{ color: riskLevelColors[item.risk_level] }}>
                            <span className="history-level">{item.risk_level.toUpperCase()}</span>
                            <span className="history-value">{item.risk_score}/100</span>
                          </div>
                          <div className="history-components">
                            <span>S:{Math.round(item.severity_component || 0)}</span>
                            <span>E:{Math.round(item.evidence_component || 0)}</span>
                            <span>P:{Math.round(item.population_component || 0)}</span>
                            <span>I:{Math.round(item.infrastructure_component || 0)}</span>
                            <span>En:{Math.round(item.environment_component || 0)}</span>
                            <span>A:{Math.round(item.accessibility_component || 0)}</span>
                          </div>
                          {item.explanation && <p className="history-explanation">{item.explanation}</p>}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
            {!selectedIncident && (
              <div className="no-incident-selected">
                <p>No incident selected. Go to the <strong>Incidents</strong> tab and click on an incident to assess its risk.</p>
              </div>
            )}
          </section>
        )}
      </main>
    </div>
  );
}

export default App;
>>>>>>> origin/main
