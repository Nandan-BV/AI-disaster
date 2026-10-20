import React from 'react';
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import maplibregl from 'maplibre-gl';
import MapView from './MapView';

global.IS_REACT_ACT_ENVIRONMENT = true;

jest.mock('maplibre-gl', () => ({
  __esModule: true,
  default: { Map: jest.fn() },
}));

jest.mock('./api', () => ({
  apiFetch: jest.fn(),
}));

describe('MapView', () => {
  let container;
  let root;
  let mockMap;

  beforeEach(() => {
    container = document.createElement('div');
    root = createRoot(container);
    mockMap = {
      on: jest.fn(),
      remove: jest.fn(),
      getLayer: jest.fn(() => false),
      getSource: jest.fn(() => null),
      addSource: jest.fn(),
      addLayer: jest.fn(),
      getZoom: jest.fn(() => 12),
      easeTo: jest.fn(),
    };
    maplibregl.Map.mockReturnValue(mockMap);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    jest.clearAllMocks();
  });

  test('mounts the map into its rendered container while loading', async () => {
    await act(async () => {
      root.render(<MapView incidentId="incident-1" center={[77.5, 12.9]} />);
    });

    expect(maplibregl.Map).toHaveBeenCalledTimes(1);
    expect(maplibregl.Map.mock.calls[0][0].container).toBe(
      container.querySelector('.map-container')
    );
  });
});
