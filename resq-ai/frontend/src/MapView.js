import React, { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

const API_BASE = '/api/v1';

const INCIDENT_ICONS = {
  flood: '🌊',
  wildfire: '🔥',
  earthquake: '🌍',
  landslide: '🏔️',
  cyclone: '🌀',
  building_collapse: '🏢',
  road_blockage: '🚧',
  tornado: '🌪️',
  volcanic_activity: '🌋',
};

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

const INFRASTRUCTURE_ICONS = {
  hospital: '🏥',
  shelter: '🏠',
  fire_station: '🚒',
  police_station: '👮',
  school: '🏫',
  bridge: '🌉',
  road: '🛣️',
  emergency_center: '🚨',
  power_station: '⚡',
  water_facility: '💧',
};

function MapView({ incidentId, center, zoom = 13 }) {
  const mapContainer = useRef(null);
  const map = useRef(null);
  const [mapLoaded, setMapLoaded] = useState(false);
  const [mapData, setMapData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
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

  useEffect(() => {
    if (!mapContainer.current || map.current) return;

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
      center: center || [77.5946, 12.9716],
      zoom: zoom || 13,
    });

    map.current = mapInstance;

    mapInstance.on('load', () => {
      setMapLoaded(true);
      if (incidentId) {
        fetchMapData();
      }
    });

    return () => {
      mapInstance.remove();
      map.current = null;
      setMapLoaded(false);
    };
  }, [incidentId]);

  const fetchMapData = async () => {
    if (!incidentId) return;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/incidents/${incidentId}/map-data`);
      if (response.ok) {
        const data = await response.json();
        setMapData(data);
        addMapLayers(data);
      } else {
        setError('Failed to load map data');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const addMapLayers = (geojson) => {
    if (!map.current || !geojson) return;

    const mapInstance = map.current;

    // Clear existing dynamic layers
    ['incident-point', 'analysis-area', 'hospitals', 'shelters', 'fire-stations', 
     'police-stations', 'bridges', 'roads', 'emergency-centers', 'schools', 
     'power-stations', 'water-facilities'].forEach(layerId => {
      if (mapInstance.getLayer(layerId)) mapInstance.removeLayer(layerId);
      if (mapInstance.getSource(layerId)) mapInstance.removeSource(layerId);
    });

    // Group features by type
    const featuresByType = {
      incident: [],
      area: [],
      hospitals: [],
      shelters: [],
      fire_stations: [],
      police_stations: [],
      bridges: [],
      roads: [],
      emergency_centers: [],
      schools: [],
      power_stations: [],
      water_facilities: [],
    };

    geojson.features.forEach(feature => {
      const props = feature.properties;
      if (props.type === 'incident' || (props.id && props.id.toString().includes('incident'))) {
        featuresByType.incident.push(feature);
      } else if (props.name === 'Analysis Area') {
        featuresByType.area.push(feature);
      } else if (INFRASTRUCTURE_COLORS[props.type]) {
        const key = props.type.replace('_', '-');
        if (featuresByType[key]) {
          featuresByType[key].push(feature);
        }
      }
    });

    // Add analysis area polygon first (bottom layer)
    if (featuresByType.area.length && layersVisible.area) {
      mapInstance.addSource('area', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: featuresByType.area }
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

    // Add incident point
    if (featuresByType.incident.length) {
      mapInstance.addSource('incident-point', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: featuresByType.incident }
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

    // Add infrastructure layers
    Object.entries(featuresByType).forEach(([type, features]) => {
      if (type === 'incident' || type === 'area' || !features.length) return;
      
      const visible = layersVisible[type];
      if (!visible) return;

      const sourceId = type.replace('_', '-');
      const color = INFRASTRUCTURE_COLORS[type.replace('-', '_')] || '#666666';
      const icon = INFRASTRUCTURE_ICONS[type.replace('-', '_')] || '📍';

      mapInstance.addSource(sourceId, {
        type: 'geojson',
        data: { type: 'FeatureCollection', features }
      });

      // Circle layer
      mapInstance.addLayer({
        id: sourceId,
        type: 'circle',
        source: sourceId,
        paint: {
          'circle-radius': 8,
          'circle-color': color,
          'circle-stroke-width': 2,
          'circle-stroke-color': '#ffffff'
        }
      });

      // Symbol layer for icons
      mapInstance.addLayer({
        id: `${sourceId}-labels`,
        type: 'symbol',
        source: sourceId,
        layout: {
          'text-field': icon,
          'text-size': 16,
          'text-offset': [0, -1.5],
          'text-allow-overlap': true,
        }
      });
    });
  };

  const toggleLayer = (layer) => {
    setLayersVisible(prev => ({ ...prev, [layer]: !prev[layer] }));
    if (mapData) addMapLayers(mapData);
  };

  if (!mapLoaded) {
    return (
      <div className="map-container" style={{ height: '500px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div>Loading map...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="map-container" style={{ height: '500px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div className="error">Error: {error}</div>
      </div>
    );
  }

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
      {loading && <div className="map-loading">Loading map data...</div>}
    </div>
  );
}

export default MapView;