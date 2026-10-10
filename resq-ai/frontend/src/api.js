export async function apiFetch(input, init = {}) {
  const headers = new Headers(init.headers || {});
  const token = window.localStorage.getItem('resq-ai-access-token');
  if (token) headers.set('Authorization', `Bearer ${token}`);

  const response = await fetch(input, { ...init, headers });
  if (response.status === 401 && !String(input).includes('/auth/token')) {
    window.dispatchEvent(new Event('resq-ai-auth-expired'));
  }
  return response;
}
