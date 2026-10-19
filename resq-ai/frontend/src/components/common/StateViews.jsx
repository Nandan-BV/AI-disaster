import React from 'react';
import './StateViews.css';

export function LoadingState({ label = 'Loading…' }) {
  return (
    <div className="state-view" role="status" aria-live="polite">
      <div className="state-spinner" />
      <span>{label}</span>
    </div>
  );
}

export function ErrorState({ message, onRetry }) {
  return (
    <div className="state-view state-error" role="alert">
      <span className="state-icon">⚠️</span>
      <span>{message || 'Something went wrong.'}</span>
      {onRetry && (
        <button type="button" className="btn-secondary" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}

export function EmptyState({ message = 'Nothing here yet.' }) {
  return (
    <div className="state-view state-empty">
      <span className="state-icon">📭</span>
      <span>{message}</span>
    </div>
  );
}

/**
 * Used when a dataset is legitimately unavailable rather than empty (e.g. the
 * backend returned 404 because a downstream phase has not produced data yet).
 * We surface the gap explicitly instead of fabricating a zero.
 */
export function UnavailableState({ message = 'Data unavailable.' }) {
  return (
    <div className="state-view state-unavailable">
      <span className="state-icon">🚫</span>
      <span>{message}</span>
    </div>
  );
}
