import { useState } from 'react';
import { api } from '../apiClient';
import { Arrow } from './Home';

function EyeIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function EyeOffIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M9.88 9.88a3 3 0 1 0 4.24 4.24" />
      <path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68" />
      <path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3.5 7 10 7a9.74 9.74 0 0 0 5.39-1.61" />
      <line x1="2" y1="2" x2="22" y2="22" />
    </svg>
  );
}

function GlobalStyles() {
  return (
    <style>{`
      :root {
        --yellow: #fff313;
        --white: #eeeeee;
        --carbon: #333333;
        --line: #4b4b4b;
        --muted: #afafaf;
        --gutter: clamp(24px, 4.2vw, 80px);
      }
      .auth-page .button.outline {
        color: #ffffff;
      }
      .password-wrapper {
        position: relative;
        margin-bottom: 24px;
      }
      .password-wrapper input {
        margin-bottom: 0 !important;
        padding-right: 44px !important;
      }
      .password-toggle-btn {
        position: absolute;
        right: 12px;
        top: 50%;
        transform: translateY(-50%);
        background: none;
        border: none;
        padding: 4px;
        cursor: pointer;
        color: var(--muted);
        display: flex;
        align-items: center;
        justify-content: center;
        transition: color 0.15s ease;
      }
      .password-toggle-btn:hover {
        color: var(--white);
      }
    `}</style>
  );
}

export default function SignUp({ onJoined, onNavigate }) {
  const [mode, setMode] = useState('signup'); // 'signup' | 'login'
  const [showSignupPassword, setShowSignupPassword] = useState(false);
  const [showLoginPassword, setShowLoginPassword] = useState(false);
  const [type, setType] = useState('consumer');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');

  async function handleSignup(e) {
    e.preventDefault();
    setBusy(true);
    setError('');
    const fields = new FormData(e.currentTarget);
    const payload = {
      name: fields.get('name'),
      email: fields.get('email').trim(),
      password: fields.get('password'),
      pod: fields.get('pod'),
      type,
      load_kw: Number(fields.get('load_kw')),
      solar_kwp: type === 'prosumer' ? Number(fields.get('solar_kwp')) : 0,
    };

    try {
      const member = await api('signup', 'POST', payload);
      localStorage.setItem('gridlink-token', member.access_token);
      setNotice('Welcome to GridLink!');
      if (onJoined) onJoined(member);
      onNavigate('home');
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleLogin(e) {
    e.preventDefault();
    setBusy(true);
    setError('');
    const fields = new FormData(e.currentTarget);
    const payload = {
      email: fields.get('email'),
      password: fields.get('password'),
    };

    try {
      const res = await api('login', 'POST', payload);
      if (res?.access_token) {
        localStorage.setItem('gridlink-token', res.access_token);
      }
      if (res?.user?.id) {
        localStorage.setItem('gridlink-member', res.user.id);
      }
      if (res?.user?.email || payload.email) {
        localStorage.setItem('gridlink-email', res?.user?.email || payload.email);
      }
      if (onJoined && res?.user) {
        onJoined(res.user);
      }
      setNotice('Logged in successfully.');
      onNavigate('account');
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-page dark" style={{ minHeight: 'calc(100vh - 85px)', padding: '60px var(--gutter)' }}>
      <GlobalStyles />
      <div style={{ maxWidth: '560px', margin: '0 auto' }}>
        <button
          className="text-button"
          onClick={() => onNavigate('home')}
          style={{ marginBottom: '24px', display: 'inline-flex', alignItems: 'center', gap: '8px' }}
        >
          ← Back to Community Overview
        </button>

        <div className="auth-card" style={{ border: '1px solid var(--line)', borderRadius: '9px', padding: '36px', background: '#0a0a0a' }}>
          <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid var(--carbon)', paddingBottom: '16px', marginBottom: '28px' }}>
            <button
              type="button"
              className={mode === 'signup' ? 'button primary' : 'button outline'}
              style={{ flex: 1, color: mode === 'signup' ? '#000' : 'var(--white)' }}
              onClick={() => { setMode('signup'); setError(''); }}
            >
              Join Community
            </button>
            <button
              type="button"
              className={mode === 'login' ? 'button primary' : 'button outline'}
              style={{ flex: 1, color: mode === 'login' ? '#000' : 'var(--white)' }}
              onClick={() => { setMode('login'); setError(''); }}
            >
              Sign In
            </button>
          </div>

          {error && <p className="error" role="alert" style={{ marginBottom: '20px', color: '#ff6b6b' }}>{error}</p>}
          {notice && <p className="notice" style={{ marginBottom: '20px' }}>{notice}</p>}

          {mode === 'signup' ? (
            <form onSubmit={handleSignup}>
              <fieldset disabled={busy}>
                <p className="eyebrow" style={{ color: 'var(--yellow)', marginBottom: '8px' }}>SECTION 1 · PROFILE & CREDENTIALS</p>
                <label htmlFor="member-name">Home or business name</label>
                <input id="member-name" name="name" placeholder="e.g. Alex's home" minLength="2" maxLength="80" required autoFocus />

                <label htmlFor="member-email">Email address</label>
                <input id="member-email" name="email" type="email" placeholder="alex@energy.ie" required />

                <label htmlFor="member-password">Password (min 8 characters)</label>
                <div className="password-wrapper">
                  <input
                    id="member-password"
                    name="password"
                    type={showSignupPassword ? 'text' : 'password'}
                    minLength="8"
                    placeholder="••••••••"
                    required
                  />
                  <button
                    type="button"
                    className="password-toggle-btn"
                    onClick={() => setShowSignupPassword((prev) => !prev)}
                    aria-label={showSignupPassword ? 'Hide password' : 'Show password'}
                    title={showSignupPassword ? 'Hide password' : 'Show password'}
                  >
                    {showSignupPassword ? <EyeOffIcon /> : <EyeIcon />}
                  </button>
                </div>

                <p className="eyebrow" style={{ color: 'var(--yellow)', marginTop: '24px', marginBottom: '8px' }}>SECTION 2 · POINT OF DELIVERY (METER)</p>
                <label htmlFor="member-pod">
                  Grid Point of Delivery (POD)
                  <input id="member-pod" name="pod" placeholder="e.g. IT001E12345678" minLength="10" maxLength="36" required />
                </label>
                <p className="form-note" style={{ marginTop: '-14px', marginBottom: '20px' }}>
                  The unique alphanumeric code from your utility bill identifying your electricity meter.
                </p>

                <p className="eyebrow" style={{ color: 'var(--yellow)', marginTop: '24px', marginBottom: '8px' }}>SECTION 3 · ENERGY PARTICIPATION</p>
                <span className="field-label" id="type-label">How will you participate?</span>
                <div className="role-picker" role="group" aria-labelledby="type-label">
                  <button type="button" className={type === 'consumer' ? 'chosen' : ''} onClick={() => setType('consumer')}>
                    Consumer<span>I buy electricity</span>
                  </button>
                  <button type="button" className={type === 'prosumer' ? 'chosen' : ''} onClick={() => setType('prosumer')}>
                    Prosumer<span>I also produce solar</span>
                  </button>
                </div>

                <label htmlFor="member-load">Average demand <span>(kW)</span></label>
                <input id="member-load" name="load_kw" type="number" min="0" max="1000" step="0.01" required />

                {type === 'prosumer' && (
                  <>
                    <label htmlFor="member-solar">Installed solar capacity <span>(kWp)</span></label>
                    <input id="member-solar" name="solar_kwp" type="number" min="0.01" max="1000" step="0.01" required />
                  </>
                )}

                <button className="button primary w-full" type="submit" style={{ width: '100%', marginTop: '24px' }}>
                  {busy ? 'Registering…' : 'Join GridLink Community'}
                  <Arrow />
                </button>
              </fieldset>
            </form>
          ) : (
            <form onSubmit={handleLogin}>
              <fieldset disabled={busy}>
                <p className="eyebrow" style={{ color: 'var(--muted)', marginBottom: '8px' }}>ACCESS YOUR COMMUNITY ACCOUNT</p>
                <label htmlFor="login-email">Email address</label>
                <input id="login-email" name="email" type="email" placeholder="alex@energy.ie" required autoFocus />

                <label htmlFor="login-password">Password</label>
                <div className="password-wrapper">
                  <input
                    id="login-password"
                    name="password"
                    type={showLoginPassword ? 'text' : 'password'}
                    placeholder="••••••••"
                    required
                  />
                  <button
                    type="button"
                    className="password-toggle-btn"
                    onClick={() => setShowLoginPassword((prev) => !prev)}
                    aria-label={showLoginPassword ? 'Hide password' : 'Show password'}
                    title={showLoginPassword ? 'Hide password' : 'Show password'}
                  >
                    {showLoginPassword ? <EyeOffIcon /> : <EyeIcon />}
                  </button>
                </div>

                <button className="button primary w-full" type="submit" style={{ width: '100%', marginTop: '16px' }}>
                  {busy ? 'Signing in…' : 'Sign in to Account'}
                  <Arrow />
                </button>
              </fieldset>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
