import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { authApi } from '../api/auth';

const emptyForm = {
  full_name: '',
  email: '',
  phone: '',
  organization_name: '',
  password: ''
};

const formatRequestError = (error, fallback) => {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') return detail;

  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        const location = Array.isArray(item?.loc) ? item.loc.filter((part) => part !== 'body') : [];
        const field = location.length ? String(location[location.length - 1]).replaceAll('_', ' ') : '';
        const message = typeof item?.msg === 'string' ? item.msg : 'Invalid value';
        return field ? field + ': ' + message : message;
      })
      .filter(Boolean)
      .join('; ') || fallback;
  }

  if (detail && typeof detail === 'object' && typeof detail.message === 'string') {
    return detail.message;
  }

  return fallback;
};

export const SignIn = () => {
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState(emptyForm);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  useEffect(() => {
    if (isAuthenticated) navigate('/dashboard', { replace: true });
  }, [isAuthenticated, navigate]);

  const updateField = (field, value) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError('');
    setMessage('');
    try {
      if (mode === 'register') {
        await authApi.register(form);
        setMode('login');
        setMessage('Registration complete. Sign in with your new account.');
      } else {
        const response = await authApi.login({ email: form.email, password: form.password });
        login(response.access_token);
        navigate('/dashboard', { replace: true });
      }
    } catch (err) {
      setError(formatRequestError(
        err,
        mode === 'register' ? 'Registration failed. Check your details and try again.' : 'Authentication failed. Check your email and password.'
      ));
    } finally {
      setLoading(false);
    }
  };

  const isRegistering = mode === 'register';
  const fields = isRegistering ? ['full_name', 'email', 'phone', 'organization_name', 'password'] : ['email', 'password'];
  const labels = {
    full_name: 'Administrator name',
    email: 'Work email',
    phone: 'Phone number',
    organization_name: 'Organization name',
    password: 'Password'
  };

  return (
    <div className="signin-page">
      <div className="signin-orb signin-orb-one" />
      <div className="signin-orb signin-orb-two" />
      <main className="signin-shell">
        <section className="signin-brand-panel">
          <div className="signin-brand-mark"><i className="bi bi-shield-check" aria-hidden="true" /></div>
          <p className="signin-eyebrow">DPI TRUST FRAMEWORK</p>
          <h1>Trust every agent.<br /><span>Authorize every action.</span></h1>
          <p className="signin-brand-copy">A secure foundation for digital identities, delegated capabilities, and accountable agent activity.</p>
          <div className="signin-feature-list">
            <div><i className="bi bi-fingerprint" aria-hidden="true" /><span>Verifiable agent identities</span></div>
            <div><i className="bi bi-diagram-3" aria-hidden="true" /><span>Policy-driven authorization</span></div>
            <div><i className="bi bi-journal-check" aria-hidden="true" /><span>Auditable actions by design</span></div>
          </div>
          <div className="signin-status"><span className="signin-status-dot" /> Framework services ready</div>
        </section>

        <section className="signin-form-panel">
          <div className="signin-form-heading">
            <p className="signin-eyebrow">SECURE WORKSPACE ACCESS</p>
            <h2>{isRegistering ? 'Create your organization' : 'Welcome back'}</h2>
            <p>{isRegistering ? 'Set up your organization administrator account.' : 'Sign in to continue to your trust workspace.'}</p>
          </div>

          {message && <div className="alert alert-success py-2 small" role="status">{message}</div>}
          {error && <div className="alert alert-danger py-2 small" role="alert">{error}</div>}

          <form onSubmit={submit}>
            {fields.map((field) => (
              <div className="mb-3" key={field}>
                <label htmlFor={'account-' + field} className="form-label text-muted small fw-semibold">
                  {labels[field]}
                </label>
                <div className="position-relative">
                  <input
                    id={'account-' + field}
                    type={field === 'password' ? (showPassword ? 'text' : 'password') : field === 'email' ? 'email' : field === 'phone' ? 'tel' : 'text'}
                    className={'form-control bg-dark text-light border-secondary' + (field === 'password' ? ' pe-5' : '')}
                    value={form[field]}
                    onChange={(event) => updateField(field, event.target.value)}
                    autoComplete={
                      field === 'password'
                        ? (isRegistering ? 'new-password' : 'current-password')
                        : field === 'email'
                          ? 'email'
                          : field === 'full_name'
                            ? 'name'
                            : field === 'phone'
                              ? 'tel'
                              : 'organization'
                    }
                    minLength={isRegistering && field === 'password' ? 8 : isRegistering && field === 'phone' ? 10 : undefined}
                    maxLength={field === 'password' ? 256 : isRegistering && field === 'phone' ? 10 : undefined}
                    pattern={isRegistering && field === 'phone' ? '[0-9]{10}' : undefined}
                    inputMode={isRegistering && field === 'phone' ? 'numeric' : undefined}
                    title={isRegistering && field === 'phone' ? 'Enter exactly 10 digits.' : undefined}
                    required
                  />
                {field === 'password' && (
                  <button
                    type="button"
                    className="btn btn-link position-absolute top-50 end-0 translate-middle-y me-1 text-secondary"
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                    aria-pressed={showPassword}
                    onClick={() => setShowPassword((visible) => !visible)}
                  >
                    <i className={'bi ' + (showPassword ? 'bi-eye-slash' : 'bi-eye')} aria-hidden="true" />
                  </button>
                )}
                </div>
                {isRegistering && field === 'phone' && (
                  <div className="form-text">Enter exactly 10 digits.</div>
                )}
                {isRegistering && field === 'password' && (
                  <div className="form-text">Use at least 8 characters.</div>
                )}
              </div>
            ))}
            {isRegistering && <p className="text-muted small">Email verification is not required for local account setup.</p>}
            <button type="submit" className="btn signin-submit w-100 py-2 fw-semibold" disabled={loading}>
              {loading ? (isRegistering ? 'Registering...' : 'Signing in...') : (isRegistering ? 'Create Organization Account' : 'Sign In')}
            </button>
          </form>

          <button type="button" className="btn btn-link signin-switch w-100 mt-3" onClick={() => { setMode(isRegistering ? 'login' : 'register'); setError(''); setMessage(''); }}>
            {isRegistering ? 'Back to sign in' : 'Create a new organization account'}
          </button>
          <div className="signin-form-footer"><i className="bi bi-lock-fill" aria-hidden="true" /> Your access is protected by the Trust Framework</div>
        </section>
      </main>
      <p className="signin-page-footer">DPI Trust Framework <span>•</span> Identity, authority, accountability</p>
    </div>
  );
};
