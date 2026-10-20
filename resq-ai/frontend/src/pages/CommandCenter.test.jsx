import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import { apiGet } from '../api/client';
import CommandCenter from './CommandCenter';

global.IS_REACT_ACT_ENVIRONMENT = true;

jest.mock('../api/client', () => ({
  apiGet: jest.fn(),
}));

describe('CommandCenter', () => {
  let container;
  let root;

  beforeEach(() => {
    container = document.createElement('div');
    root = createRoot(container);
    apiGet.mockRejectedValue(new Error('Backend is unavailable'));
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    jest.clearAllMocks();
  });

  test('shows the request error without crashing when overview data is unavailable', async () => {
    await act(async () => {
      root.render(
        <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <CommandCenter />
        </MemoryRouter>
      );
    });

    expect(container.textContent).toContain('Command Center');
    expect(container.textContent).toContain('Backend is unavailable');
    expect(container.textContent).toContain('Incident data is unavailable.');
  });
});
