export const API_BASE = '/api/v1';

export class ApiError extends Error {
  constructor(message, status = 0, detail = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

async function parseBody(response) {
  const contentType = response.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) return null;
  try {
    return await response.json();
  } catch {
    return null;
  }
}

export async function request(path, { method = 'GET', body, signal } = {}) {
  const options = { method, headers: {}, signal };
  if (body !== undefined) {
    options.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, options);
  } catch (err) {
    if (err.name === 'AbortError') throw err;
    throw new ApiError('Unable to reach the backend. It may be offline.', 0, null);
  }

  const data = await parseBody(response);
  if (!response.ok) {
    const raw = data && data.detail ? data.detail : `Request failed (${response.status})`;
    const message = typeof raw === 'string' ? raw : JSON.stringify(raw);
    throw new ApiError(message, response.status, data);
  }
  return data;
}

export const apiGet = (path, opts) => request(path, { ...opts, method: 'GET' });
export const apiPost = (path, body, opts) =>
  request(path, { ...opts, method: 'POST', body: body ?? {} });
export const apiPatch = (path, body, opts) =>
  request(path, { ...opts, method: 'PATCH', body: body ?? {} });
export const apiDelete = (path, opts) => request(path, { ...opts, method: 'DELETE' });
