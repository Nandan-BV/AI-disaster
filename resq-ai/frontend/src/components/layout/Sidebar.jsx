import React from 'react';
import { NavLink } from 'react-router-dom';
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
        <div className="sidebar-status">
          <span className="status-dot online"></span>
          <span>System Operational</span>
        </div>
      </div>
    </aside>
  );
}