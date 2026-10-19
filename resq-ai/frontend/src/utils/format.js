export function formatDateTime(value) {
  if (!value) return 'Unknown';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Unknown';
  return date.toLocaleString();
}

export function formatTime(value) {
  if (!value) return 'Unknown';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Unknown';
  return date.toLocaleTimeString();
}

export function formatNumber(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return new Intl.NumberFormat().format(value);
}

export function formatPercent(value, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  const scaled = value <= 1 ? value * 100 : value;
  return `${scaled.toFixed(digits)}%`;
}

export function formatDistance(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return 'Unknown';
  if (value >= 1000) return `${(value / 1000).toFixed(1)} km`;
  return `${Math.round(value)} m`;
}

export const RISK_LEVEL_COLORS = {
  low: '#2e7d32',
  moderate: '#1a73e8',
  elevated: '#f57c00',
  high: '#e65100',
  critical: '#c62828',
};

export const INCIDENT_STATUS_COLORS = {
  emerging: '#f57c00',
  active: '#1a73e8',
  resolved: '#2e7d32',
};

export const ALLOCATION_STATUS_COLORS = {
  recommended: '#f57c00',
  approved: '#2e7d32',
  rejected: '#c62828',
  cancelled: '#757575',
};

export function riskColor(level) {
  return RISK_LEVEL_COLORS[level] || '#757575';
}

export function statusColor(status) {
  return INCIDENT_STATUS_COLORS[status] || '#757575';
}
