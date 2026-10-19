import { useCallback, useEffect, useState } from 'react';
import { apiGet } from './client';

/**
 * Minimal read-only data hook. Re-fetches whenever `path` or `enabled`
 * changes, or when `reload()` is called. Great for GET-only views.
 *
 * `status` is exposed so callers can tell a genuine 404 (data not produced
 * yet) apart from a transport/server error.
 */
export function useAsyncData(path, enabled = true) {
  const [state, setState] = useState({
    data: null,
    loading: Boolean(enabled && path),
    error: null,
    status: 0,
  });
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    if (!enabled || !path) {
      setState({ data: null, loading: false, error: null, status: 0 });
      return undefined;
    }
    let active = true;
    setState((prev) => ({ data: prev.data, loading: true, error: null, status: 0 }));
    apiGet(path)
      .then((data) => {
        if (active) setState({ data, loading: false, error: null, status: 200 });
      })
      .catch((err) => {
        if (active) {
          setState({ data: null, loading: false, error: err.message, status: err.status || 0 });
        }
      });
    return () => {
      active = false;
    };
  }, [path, enabled, nonce]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  return { ...state, reload };
}
