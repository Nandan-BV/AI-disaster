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
