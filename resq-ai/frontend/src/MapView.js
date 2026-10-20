import React, { useCallback, useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { apiFetch } from './api';

const API_BASE = '/api/v1';

const INFRASTRUCTURE_COLORS = {
  hospital: '#e53935',
  shelter: '#43a047',
  fire_station: '#fb8c00',
  police_station: '#1e88e5',
  school: '#8e24aa',
  bridge: '#546e7a',
  road: '#78909c',
  emergency_center: '#00acc1',
  power_station: '#fdd835',
  water_facility: '#29b6f6',
};

const INFRASTRUCTURE_LAYERS = [
  { key: 'hospitals', type: 'hospital', source: 'hospitals', label: 'Hospitals' },
  { key: 'shelters', type: 'shelter', source: 'shelters', label: 'Shelters' },
  { key: 'fire_stations', type: 'fire_station', source: 'fire-stations', label: 'Fire Stations' },
  { key: 'police_stations', type: 'police_station', source: 'police-stations', label: 'Police' },
  { key: 'bridges', type: 'bridge', source: 'bridges', label: 'Bridges' },
  { key: 'roads', type: 'road', source: 'roads', label: 'Roads' },
  {
    key: 'emergency_centers',
    type: 'emergency_center',
    source: 'emergency-centers',
    label: 'Emergency Centers',
  },
  { key: 'schools', type: 'school', source: 'schools', label: 'Schools' },
  {
    key: 'power_stations',
    type: 'power_station',
    source: 'power-stations',
    label: 'Power Stations',
  },
  {
    key: 'water_facilities',
    type: 'water_facility',
    source: 'water-facilities',
    label: 'Water Facilities',
  },
];

function coordinate(value, min, max) {
  if (value == null || (typeof value === 'string' && !value.trim())) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= min && parsed <= max ? parsed : null;
}

function hasValidCoordinates(value) {
  if (!Array.isArray(value) || value.length === 0) return false;
  if (typeof value[0] === 'number') {
    return (
      value.length >= 2 &&
      coordinate(value[0], -180, 180) !== null &&
      coordinate(value[1], -90, 90) !== null
    );
  }
  return value.every(hasValidCoordinates);
}

function hasValidGeometry(geometry) {
  if (!geometry || typeof geometry !== 'object') return false;
  if (geometry.type === 'GeometryCollection') {
    return Array.isArray(geometry.geometries) &&
      geometry.geometries.every(hasValidGeometry);
  }
  return hasValidCoordinates(geometry.coordinates);
}

function MapView({ incidentId, center, zoom = 13, liveEvents = [] }) {
  const mapContainer = useRef(null);
  const map = useRef(null);
  const latestLiveEventId = useRef(null);
  const [mapLoaded, setMapLoaded] = useState(false);
  const [mapData, setMapData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [basemapError, setBasemapError] = useState(null);
  const mapLoadedRef = useRef(false);
  const centerRef = useRef(center);
  const zoomRef = useRef(zoom);
  centerRef.current = center;
  zoomRef.current = zoom;
  const [layersVisible, setLayersVisible] = useState({
    incident: true,
    area: true,
    hospitals: true,
    shelters: true,
    fire_stations: true,
    police_stations: true,
    bridges: true,
    roads: true,
    emergency_centers: true,
    schools: true,
    power_stations: true,
    water_facilities: true,
  });

  const fetchMapData = useCallback(async () => {
    if (!incidentId) return;
    setLoading(true);
    setError(null);
    try {
      const response = await apiFetch(`${API_BASE}/incidents/${incidentId}/map-data`);
      if (!response.ok) {
        let message = `Failed to load map data (${response.status})`;
        try {
          const body = await response.json();
          if (typeof body.detail === 'string') message = body.detail;
        } catch {
          // Keep the HTTP status message when the backend does not return JSON.
        }
        throw new Error(message);
      }
      const data = await response.json();
      if (data?.type !== 'FeatureCollection' || !Array.isArray(data.features)) {
        throw new Error('The backend returned an invalid map-data response.');
      }
      setMapData(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [incidentId]);

  useEffect(() => {
    if (!mapContainer.current || map.current) return;
    const longitude = coordinate(centerRef.current?.[0], -180, 180);
    const latitude = coordinate(centerRef.current?.[1], -90, 90);
    setMapLoaded(false);
    setLoading(Boolean(incidentId));
    setError(null);
    setBasemapError(null);
    setMapData(null);

    const mapInstance = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        sources: {
          'osm': {
            type: 'raster',
            tiles: ['https://a.tile.openstreetmap.org/{z}/{x}/{y}.png'],
            tileSize: 256,
            attribution: '© OpenStreetMap contributors'
          }
        },
        layers: [
          {
            id: 'osm',
            type: 'raster',
            source: 'osm',
            minzoom: 0,
            maxzoom: 19
          }
        ]
      },
      center: longitude === null || latitude === null
        ? [77.5946, 12.9716]
        : [longitude, latitude],
      zoom: zoomRef.current || 13,
    });

    map.current = mapInstance;

    mapInstance.on('error', event => {
      if (event.sourceId === 'osm') {
        setBasemapError('OpenStreetMap tiles are unavailable. Check your network connection.');
      } else if (!mapLoadedRef.current) {
        setError(event.error?.message || 'The map could not be initialized.');
      }
    });
    mapInstance.on('load', () => {
      mapLoadedRef.current = true;
      setMapLoaded(true);
      if (incidentId) {
        fetchMapData();
      } else {
        setLoading(false);
      }
    });

    return () => {
      mapInstance.remove();
      map.current = null;
      mapLoadedRef.current = false;
      setMapLoaded(false);
    };
  }, [fetchMapData, incidentId]);

  useEffect(() => {
    if (!mapLoaded || !map.current) return;

    const features = liveEvents
      .filter(event =>
        coordinate(event.longitude, -180, 180) !== null &&
        coordinate(event.latitude, -90, 90) !== null
      )
      .map(event => ({
        type: 'Feature',
        geometry: {
          type: 'Point',
          coordinates: [
            coordinate(event.longitude, -180, 180),
            coordinate(event.latitude, -90, 90),
          ],
        },
        properties: {
          id: event.id,
          event_type: event.event_type || 'disaster report',
          location_name: event.location_name || '',
        },
      }));
    const source = map.current.getSource('live-events');
    if (source) {
      source.setData({ type: 'FeatureCollection', features });
    } else {
      map.current.addSource('live-events', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features },
      });
      map.current.addLayer({
        id: 'live-events',
        type: 'circle',
        source: 'live-events',
        paint: {
          'circle-radius': 8,
          'circle-color': '#ff1744',
          'circle-stroke-width': 2,
          'circle-stroke-color': '#ffffff',
        },
      });
    }

    const latestEvent = liveEvents.find(event =>
      coordinate(event.longitude, -180, 180) !== null &&
      coordinate(event.latitude, -90, 90) !== null
    );
    if (latestEvent && latestEvent.id !== latestLiveEventId.current) {
      latestLiveEventId.current = latestEvent.id;
      if (!incidentId) {
        map.current.easeTo({
          center: [
            coordinate(latestEvent.longitude, -180, 180),
            coordinate(latestEvent.latitude, -90, 90),
          ],
          zoom: Math.max(map.current.getZoom(), 12),
          duration: 400,
        });
      }
    }
  }, [liveEvents, mapLoaded, incidentId]);

  const addMapLayers = useCallback((geojson) => {
    if (!map.current || !geojson || !Array.isArray(geojson.features)) return;

    const mapInstance = map.current;

    const layerIds = [
      'analysis-area',
      'incident-point',
      ...INFRASTRUCTURE_LAYERS.map(({ source }) => source),
    ];
    layerIds.forEach(layerId => {
      if (mapInstance.getLayer(layerId)) mapInstance.removeLayer(layerId);
    });
    ['area', 'incident-point', ...INFRASTRUCTURE_LAYERS.map(({ source }) => source)]
      .forEach(sourceId => {
        if (mapInstance.getSource(sourceId)) mapInstance.removeSource(sourceId);
      });

    const featuresByType = new Map(INFRASTRUCTURE_LAYERS.map(({ type }) => [type, []]));
    const incidentFeatures = [];
    const areaFeatures = [];

    geojson.features.forEach(feature => {
      if (
        !feature ||
        feature.type !== 'Feature' ||
        !feature.properties ||
        !hasValidGeometry(feature.geometry)
      ) return;

      if (feature.properties.id === incidentId) {
        incidentFeatures.push(feature);
      } else if (feature.properties.name === 'Analysis Area') {
        areaFeatures.push(feature);
      } else {
        const layer = INFRASTRUCTURE_LAYERS.find(({ type }) => type === feature.properties.type);
        if (layer) featuresByType.get(layer.type).push(feature);
      }
    });

    if (areaFeatures.length && layersVisible.area) {
      mapInstance.addSource('area', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: areaFeatures }
      });
      mapInstance.addLayer({
        id: 'analysis-area',
        type: 'fill',
        source: 'area',
        paint: {
          'fill-color': '#1a73e8',
          'fill-opacity': 0.15,
          'fill-outline-color': '#1a73e8'
        }
      });
    }

    if (incidentFeatures.length && layersVisible.incident) {
      mapInstance.addSource('incident-point', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: incidentFeatures }
      });
      mapInstance.addLayer({
        id: 'incident-point',
        type: 'circle',
        source: 'incident-point',
        paint: {
          'circle-radius': 12,
          'circle-color': '#c62828',
          'circle-stroke-width': 3,
          'circle-stroke-color': '#ffffff'
        }
      });
    }

    INFRASTRUCTURE_LAYERS.forEach(({ key, type, source }) => {
      const features = featuresByType.get(type);
      if (!features.length || !layersVisible[key]) return;

      mapInstance.addSource(source, {
        type: 'geojson',
        data: { type: 'FeatureCollection', features }
      });

      mapInstance.addLayer({
        id: source,
        type: 'circle',
        source,
        paint: {
          'circle-radius': 8,
          'circle-color': INFRASTRUCTURE_COLORS[type],
          'circle-stroke-width': 2,
          'circle-stroke-color': '#ffffff'
        }
      });
    });
  }, [incidentId, layersVisible]);

  useEffect(() => {
    if (mapLoaded && mapData) addMapLayers(mapData);
  }, [addMapLayers, mapLoaded, mapData]);

  const toggleLayer = layer => {
    setLayersVisible(prev => ({ ...prev, [layer]: !prev[layer] }));
  };

  return (
    <div className="map-section">
      <div className="map-header">
        <h3>Incident Map View</h3>
        <div className="map-controls">
          <label>
            <input
              type="checkbox"
              checked={layersVisible.area}
              onChange={() => toggleLayer('area')}
            />
            Analysis Area
          </label>
          <label>
            <input
              type="checkbox"
              checked={layersVisible.hospitals}
              onChange={() => toggleLayer('hospitals')}
            />
            Hospitals
          </label>
          <label>
            <input
              type="checkbox"
              checked={layersVisible.shelters}
              onChange={() => toggleLayer('shelters')}
            />
            Shelters
          </label>
          <label>
            <input
              type="checkbox"
              checked={layersVisible.fire_stations}
              onChange={() => toggleLayer('fire_stations')}
            />
            Fire Stations
          </label>
          <label>
            <input
              type="checkbox"
              checked={layersVisible.police_stations}
              onChange={() => toggleLayer('police_stations')}
            />
            Police
          </label>
        </div>
      </div>
      <div className="map-layers-controls">
        <label>
          <input
            type="checkbox"
            checked={layersVisible.bridges}
            onChange={() => toggleLayer('bridges')}
          />
          Bridges
        </label>
        <label>
          <input
            type="checkbox"
            checked={layersVisible.roads}
            onChange={() => toggleLayer('roads')}
          />
          Roads
        </label>
        <label>
          <input
            type="checkbox"
            checked={layersVisible.emergency_centers}
            onChange={() => toggleLayer('emergency_centers')}
          />
          Emergency Centers
        </label>
        <label>
          <input
            type="checkbox"
            checked={layersVisible.schools}
            onChange={() => toggleLayer('schools')}
          />
          Schools
        </label>
        <label>
          <input
            type="checkbox"
            checked={layersVisible.power_stations}
            onChange={() => toggleLayer('power_stations')}
          />
          Power Stations
        </label>
        <label>
          <input
            type="checkbox"
            checked={layersVisible.water_facilities}
            onChange={() => toggleLayer('water_facilities')}
          />
          Water Facilities
        </label>
      </div>
      <div ref={mapContainer} className="map-container" style={{ height: '500px' }} />
      {!mapLoaded && (
        <div className="map-status" role="status">
          {error || 'Loading map…'}
        </div>
      )}
      {error && mapLoaded && (
        <div className="map-status" role="alert">
          {error}
        </div>
      )}
      {basemapError && (
        <div className="map-notice" role="status">
          {basemapError} Incident overlays may still be available.
        </div>
      )}
      {loading && mapLoaded && !error && (
        <div className="map-status" role="status">Loading incident map data…</div>
      )}
      {!loading && mapLoaded && !error && mapData?.features.length === 0 && (
        <div className="map-status" role="status">
          No incident or infrastructure coordinates are available for this map.
        </div>
      )}
    </div>
  );
}

export default MapView;