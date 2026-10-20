import React from 'react';
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { useAsyncData } from '../api/useAsyncData';
import ResourcesPage from './ResourcesPage';

global.IS_REACT_ACT_ENVIRONMENT = true;

jest.mock('../api/useAsyncData', () => ({
  useAsyncData: jest.fn(),
}));

describe('ResourcesPage', () => {
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

  test('renders resources from the backend paginated response', async () => {
    useAsyncData.mockReturnValue({
      data: {
        resources: [
          {
            id: 'resource-1',
            name: 'Central Hospital',
            resource_type: 'hospital',
            status: 'available',
            capacity: 20,
            current_load: 8,
          },
        ],
      },
      loading: false,
      error: null,
      reload: jest.fn(),
    });

    await act(async () => root.render(<ResourcesPage />));

    expect(container.textContent).toContain('Central Hospital');
    expect(container.textContent).toContain('8/20');
  });

  test('renders an explicit empty state for an empty backend response', async () => {
    useAsyncData.mockReturnValue({
      data: { resources: [], total: 0, limit: 100, offset: 0 },
      loading: false,
      error: null,
      reload: jest.fn(),
    });

    await act(async () => root.render(<ResourcesPage />));

    expect(container.textContent).toContain('No resources.');
  });
});
