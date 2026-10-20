import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { apiPost } from '../api/client';
import { useAsyncData } from '../api/useAsyncData';
import EventsPage from './EventsPage';

global.IS_REACT_ACT_ENVIRONMENT = true;

jest.mock('../api/client', () => ({
  apiGet: jest.fn(),
  apiPost: jest.fn(),
  apiDelete: jest.fn(),
}));

jest.mock('../api/useAsyncData', () => ({
  useAsyncData: jest.fn(),
}));

function setInputValue(input, value) {
  const prototype = Object.getPrototypeOf(input);
  Object.getOwnPropertyDescriptor(prototype, 'value').set.call(input, value);
  input.dispatchEvent(new Event('input', { bubbles: true }));
}

describe('EventsPage', () => {
  let container;
  let root;
  const reload = jest.fn();

  beforeEach(() => {
    container = document.createElement('div');
    root = createRoot(container);
    useAsyncData.mockReturnValue({
      data: {
        events: [
          {
            id: 'event-1',
            source: 'news',
            event_type: 'flood',
            text_content: 'Flooding reported near the river.',
            latitude: 12.9,
            longitude: 77.5,
            location_name: 'Riverside',
            timestamp: '2026-10-20T09:00:00',
          },
        ],
        total: 1,
      },
      loading: false,
      error: null,
      reload,
    });
    apiPost.mockResolvedValue({ id: 'event-2' });
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    jest.clearAllMocks();
  });

  test('renders persisted event content, source, location, and ID', async () => {
    await act(async () => root.render(<EventsPage />));

    expect(container.textContent).toContain('Flooding reported near the river.');
    expect(container.textContent).toContain('news');
    expect(container.textContent).toContain('Riverside');
    expect(container.textContent).toContain('event-1');
  });

  test('renders empty and unavailable API states instead of hiding failures', async () => {
    useAsyncData.mockReturnValueOnce({
      data: { events: [], total: 0 },
      loading: false,
      error: null,
      reload,
    });
    await act(async () => root.render(<EventsPage />));
    expect(container.textContent).toContain('No events yet.');

    await act(async () => root.unmount());
    root = createRoot(container);
    useAsyncData.mockReturnValueOnce({
      data: null,
      loading: false,
      error: 'Backend is offline',
      reload,
    });
    await act(async () => root.render(<EventsPage />));
    expect(container.textContent).toContain('Backend is offline');
  });

  test('submits a valid event and refreshes the persisted event list', async () => {
    await act(async () => root.render(<EventsPage />));

    act(() => {
      setInputValue(container.querySelector('#latitude'), '12.9');
      setInputValue(container.querySelector('#longitude'), '77.5');
      setInputValue(
        container.querySelector('#text_content'),
        'Flood report submitted by a responder.'
      );
    });

    await act(async () => {
      container.querySelector('form').dispatchEvent(
        new Event('submit', { bubbles: true, cancelable: true })
      );
      await Promise.resolve();
    });

    expect(apiPost).toHaveBeenCalledWith(
      '/events',
      expect.objectContaining({
        source: 'social_media',
        text_content: 'Flood report submitted by a responder.',
        latitude: 12.9,
        longitude: 77.5,
      })
    );
    expect(reload).toHaveBeenCalledTimes(1);
  });
});
