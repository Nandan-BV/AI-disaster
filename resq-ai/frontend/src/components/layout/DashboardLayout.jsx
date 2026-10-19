import React, { useEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import Sidebar from './Sidebar';
import TopNav from './TopNav';
import './DashboardLayout.css';

const PAGE_TITLES = [
  { match: /^\/incidents\/.+/, title: 'Incident Workspace' },
  { match: /^\/incidents$/, title: 'Incidents' },
  { match: /^\/events$/, title: 'Events' },
  { match: /^\/map$/, title: 'Live Map' },
  { match: /^\/investigations$/, title: 'Evidence Investigations' },
  { match: /^\/risk$/, title: 'Risk & Impact' },
  { match: /^\/resources$/, title: 'Resources' },
  { match: /^\/optimization$/, title: 'Optimization' },
  { match: /^\/copilot$/, title: 'AI Copilot' },
  { match: /^\/system-status$/, title: 'System Status' },
  { match: /^\/$/, title: 'Command Center' },
];

function titleForPath(pathname) {
  const found = PAGE_TITLES.find((entry) => entry.match.test(pathname));
  return found ? found.title : 'RESQ-AI';
}

export default function DashboardLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { pathname } = useLocation();

  useEffect(() => {
    setSidebarOpen(false);
  }, [pathname]);

  return (
    <div className="dashboard-layout">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="dashboard-main">
        <TopNav onMenuClick={() => setSidebarOpen(true)} pageTitle={titleForPath(pathname)} />
        <main className="dashboard-content">
          <Outlet />
        </main>
      </div>
      {sidebarOpen && (
        <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)} />
      )}
    </div>
  );
}
