import React, { useEffect } from 'react';
import { NavLink } from 'react-router-dom';
import { useAsyncData } from '../../api/useAsyncData';
import './Sidebar.css';

const NAV_ITEMS = [
  { path: '/', label: 'Command Center', icon: '📊' },
  { path: '/incidents', label: 'Incidents', icon: '🚨' },
  { path: '/events', label: 'Events', icon: '📝' },
  { path: '/map', label: 'Live Map', icon: '🗺️' },
  { path: '/investigations', label: 'Evidence', icon: '🔍' },
  { path: '/risk', label: 'Risk & Impact', icon: '⚠️' },
  { path: '/resources', label: 'Resources', icon: '🚑' },
  { path: '/optimization', label: 'Optimization', icon: '⚙️' },
  { path: '/copilot', label: 'AI Copilot', icon: '🤖' },
  { path: '/system-status', label: 'System Status', icon: '🖥️' },
];

export default function Sidebar({ isOpen, onClose }) {
  const health = useAsyncData('/health');

  useEffect(() => {
    const interval = window.setInterval(health.reload, 30000);
    return () => window.clearInterval(interval);
  }, [health.reload]);

  let statusLabel = 'Checking system status';
  let statusClass = 'checking';
  if (health.data?.status === 'ok' && health.data.database === 'connected') {
    statusLabel = health.data.copilot === 'unavailable'
      ? 'System degraded'
      : 'System operational';
    statusClass = health.data.copilot === 'unavailable' ? 'degraded' : 'online';
  } else if (health.data?.status === 'degraded' || health.status === 503) {
    statusLabel = 'System degraded';
    statusClass = 'degraded';
  } else if (health.error) {
    statusLabel = 'System unavailable';
    statusClass = 'offline';
  } else if (!health.loading) {
    statusLabel = 'System status unknown';
    statusClass = 'unknown';
  }

  return (
    <aside className={`sidebar ${isOpen ? 'open' : ''}`}>
      <div className="sidebar-header">
        <h1>RESQ-AI</h1>
        <span className="sidebar-subtitle">Emergency Command Center</span>
      </div>
      <nav className="sidebar-nav">
        <ul>
          {NAV_ITEMS.map((item) => (
            <li key={item.path}>
              <NavLink
                to={item.path}
                className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
                onClick={onClose}
              >
                <span className="nav-icon">{item.icon}</span>
                <span className="nav-label">{item.label}</span>
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <div className="sidebar-footer">
        <div className="sidebar-status" role="status" aria-live="polite">
          <span className={`status-dot ${statusClass}`} aria-hidden="true"></span>
          <span>{statusLabel}</span>
        </div>
      </div>
    </aside>
  );
}