import { apiGet, apiPost, ApiError } from './client';

describe('API client', () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    jest.clearAllMocks();
  });

  test('uses the API prefix and serializes POST bodies', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 201,
      headers: { get: () => 'application/json' },
      json: async () => ({ id: 'event-1' }),
    });

    await expect(apiPost('/events', { text_content: 'Flood reported' })).resolves.toEqual({
      id: 'event-1',
    });
    expect(global.fetch).toHaveBeenCalledWith('/api/v1/events', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: undefined,
      body: JSON.stringify({ text_content: 'Flood reported' }),
    });
  });

  test('preserves backend error details and status', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 422,
      headers: { get: () => 'application/json' },
      json: async () => ({ detail: 'Invalid event' }),
    });

    await expect(apiGet('/events')).rejects.toMatchObject({
      name: 'ApiError',
      message: 'Invalid event',
      status: 422,
      detail: { detail: 'Invalid event' },
    });
  });

  test('reports backend connectivity errors as ApiError', async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error('network unavailable'));

    await expect(apiGet('/dashboard/overview')).rejects.toBeInstanceOf(ApiError);
  });
});
