import React from 'react';
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import { useAsyncData } from '../../api/useAsyncData';
import Sidebar from './Sidebar';

jest.mock('../../api/useAsyncData');
global.IS_REACT_ACT_ENVIRONMENT = true;

function renderSidebar(health) {
  useAsyncData.mockReturnValue({ reload: jest.fn(), ...health });
  const container = document.createElement('div');
  document.body.appendChild(container);
  const root = createRoot(container);
  act(() => {
    root.render(
      <MemoryRouter>
        <Sidebar isOpen={false} onClose={jest.fn()} />
      </MemoryRouter>
    );
  });
  return {
    status: container.querySelector('[role="status"]'),
    cleanup: () => {
      act(() => root.unmount());
      container.remove();
    },
  };
}

describe('Sidebar health status', () => {
  let cleanup;

  afterEach(() => {
    cleanup?.();
    jest.clearAllMocks();
  });

  test('reports healthy only when backend and database are healthy', () => {
    const rendered = renderSidebar({
      data: { status: 'ok', database: 'connected', copilot: 'available' },
      loading: false,
      error: null,
      status: 200,
    });
    cleanup = rendered.cleanup;

    expect(rendered.status.textContent).toBe('System operational');
  });

  test('reports a degraded backend health response', () => {
    const rendered = renderSidebar({
      data: null,
      loading: false,
      error: 'Request failed (503)',
      status: 503,
    });
    cleanup = rendered.cleanup;

    expect(rendered.status.textContent).toBe('System degraded');
  });

  test('reports a disconnected optional copilot as degraded', () => {
    const rendered = renderSidebar({
      data: { status: 'degraded', database: 'connected', copilot: 'unavailable' },
      loading: false,
      error: null,
      status: 200,
    });
    cleanup = rendered.cleanup;

    expect(rendered.status.textContent).toBe('System degraded');
  });

  test('reports an unreachable backend as unavailable', () => {
    const rendered = renderSidebar({
      data: null,
      loading: false,
      error: 'Network request failed',
      status: 0,
    });
    cleanup = rendered.cleanup;

    expect(rendered.status.textContent).toBe('System unavailable');
  });

  test('does not imply a healthy state when status is unknown', () => {
    const rendered = renderSidebar({ data: null, loading: false, error: null, status: 0 });
    cleanup = rendered.cleanup;

    expect(rendered.status.textContent).toBe('System status unknown');
  });
});
