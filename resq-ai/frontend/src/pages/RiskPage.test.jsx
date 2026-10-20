import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import { useAsyncData } from '../api/useAsyncData';
import RiskPage from './RiskPage';

global.IS_REACT_ACT_ENVIRONMENT = true;

jest.mock('../api/client', () => ({
  apiPost: jest.fn(),
}));

jest.mock('../api/useAsyncData', () => ({
  useAsyncData: jest.fn(),
}));

describe('RiskPage', () => {
  let container;
  let root;

  beforeEach(() => {
    container = document.createElement('div');
    root = createRoot(container);
    useAsyncData.mockImplementation(path => {
      if (path === '/incidents') {
        return {
          data: {
            incidents: [{ id: 'incident-1', title: 'River flooding' }],
            total: 1,
          },
          loading: false,
          error: null,
          reload: jest.fn(),
        };
      }
      if (path?.endsWith('/risk-assessment')) {
        return {
          data: {
            risk_score: 61,
            risk_level: 'high',
            environment_component: 44,
          },
          loading: false,
          error: null,
          status: 200,
          reload: jest.fn(),
        };
      }
      if (path?.endsWith('/impact')) {
        return {
          data: { population_potentially_exposed: 20 },
          loading: false,
          error: null,
          status: 200,
          reload: jest.fn(),
        };
      }
      return { data: null, loading: false, error: null, status: 0, reload: jest.fn() };
    });
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    jest.clearAllMocks();
  });

  test('renders risk fields using the backend response names', async () => {
    await act(async () => {
      root.render(
        <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <RiskPage />
        </MemoryRouter>
      );
    });

    expect(container.textContent).toContain('61');
    expect(container.textContent).toContain('44%');
    expect(container.textContent).toContain('20');
  });
});
