import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import { useAsyncData } from '../api/useAsyncData';
import IncidentsPage from './IncidentsPage';

global.IS_REACT_ACT_ENVIRONMENT = true;

jest.mock('../api/useAsyncData', () => ({
  useAsyncData: jest.fn(),
}));

describe('IncidentsPage', () => {
  let container;
  let root;

  beforeEach(() => {
    container = document.createElement('div');
    root = createRoot(container);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    jest.clearAllMocks();
  });

  test('renders incidents and links to their detail workspace', async () => {
    useAsyncData.mockReturnValue({
      data: {
        incidents: [
          {
            id: 'incident-1',
            title: 'River flooding',
            incident_type: 'flood',
            status: 'active',
            event_count: 2,
            risk_level: 'high',
            risk_score: 82,
            last_updated: '2026-10-20T09:00:00',
          },
        ],
        total: 1,
      },
      loading: false,
      error: null,
      reload: jest.fn(),
    });

    await act(async () => {
      root.render(
        <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <IncidentsPage />
        </MemoryRouter>
      );
    });

    expect(container.textContent).toContain('River flooding');
    expect(container.textContent).toContain('82');
    expect(container.querySelector('a[href="/incidents/incident-1"]')).not.toBeNull();
  });

  test('renders an informative empty state', async () => {
    useAsyncData.mockReturnValue({
      data: { incidents: [], total: 0 },
      loading: false,
      error: null,
      reload: jest.fn(),
    });

    await act(async () => {
      root.render(
        <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <IncidentsPage />
        </MemoryRouter>
      );
    });

    expect(container.textContent).toContain('No incidents yet.');
  });
});
