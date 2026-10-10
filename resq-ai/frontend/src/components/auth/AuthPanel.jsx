import React, { useState } from 'react';
import { apiFetch } from '../../api';

const API_BASE = '/api/v1';

function AuthPanel({ onAuthenticated }) {
  const [mode, setMode] = useState('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      if (mode === 'register') {
        const registration = await apiFetch(`${API_BASE}/auth/register`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, password }),
        });
        if (!registration.ok) {
          const detail = await registration.json().catch(() => ({}));
          throw new Error(detail.detail || `Registration failed (${registration.status}).`);
        }
      }

      const tokenResponse = await apiFetch(`${API_BASE}/auth/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      if (!tokenResponse.ok) {
        const detail = await tokenResponse.json().catch(() => ({}));
        throw new Error(detail.detail || `Sign in failed (${tokenResponse.status}).`);
      }

      const token = await tokenResponse.json();
      window.localStorage.setItem('resq-ai-access-token', token.access_token);
      const userResponse = await apiFetch(`${API_BASE}/auth/me`);
      if (!userResponse.ok) throw new Error('Could not load the signed-in account.');
      onAuthenticated(await userResponse.json());
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="auth-page">
      <section className="section auth-card">
        <h2>{mode === 'login' ? 'Sign in to RESQ-AI' : 'Create an analyst account'}</h2>
        <p>Accounts created here receive analyst access. Elevated roles must be assigned by an administrator.</p>
        <form onSubmit={submit} className="auth-form">
          <label htmlFor="auth-username">Username</label>
          <input
            id="auth-username"
            autoComplete="username"
            value={username}
            onChange={event => setUsername(event.target.value)}
            required
          />
          <label htmlFor="auth-password">Password</label>
          <input
            id="auth-password"
            type="password"
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            value={password}
            onChange={event => setPassword(event.target.value)}
            minLength={mode === 'register' ? 8 : 1}
            required
          />
          {error && <div className="analysis-error">{error}</div>}
          <button type="submit" className="btn-primary" disabled={busy}>
            {busy ? 'Please wait...' : mode === 'login' ? 'Sign in' : 'Register'}
          </button>
        </form>
        <button
          type="button"
          className="btn-secondary auth-mode-toggle"
          onClick={() => {
            setMode(mode === 'login' ? 'register' : 'login');
            setError('');
          }}
          disabled={busy}
        >
          {mode === 'login' ? 'Create an account' : 'Back to sign in'}
        </button>
      </section>
    </main>
  );
}

export default AuthPanel;
