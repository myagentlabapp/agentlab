import React, { useState, useEffect, useRef } from 'react';
import { login, register, setToken, getPublicSettings, sendCode, forgotPassword, resetPassword } from '../api/client.js';
import BrandLogo from './BrandLogo.jsx';

let turnstileScriptPromise = null;
function loadTurnstileScript() {
  if (window.turnstile) return Promise.resolve();
  if (turnstileScriptPromise) return turnstileScriptPromise;
  turnstileScriptPromise = new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
    s.async = true;
    s.onload = resolve;
    s.onerror = reject;
    document.head.appendChild(s);
  });
  return turnstileScriptPromise;
}

export default function LoginPage({ onLoggedIn }) {
  const [mode, setMode] = useState('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [password2, setPassword2] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [brand, setBrand] = useState({ brand_logo: '🧪', brand_name: '', brand_tagline: 'Agent 租赁平台' });
  const [regOpen, setRegOpen] = useState(true);
  const [tsEnabled, setTsEnabled] = useState(false);
  const [tsSiteKey, setTsSiteKey] = useState('');
  const [tsToken, setTsToken] = useState('');
  const [tsWidgetId, setTsWidgetId] = useState(null);
  const tsContainerRef = useRef(null);
  const [emailReg, setEmailReg] = useState(false);
  const [ldapOn, setLdapOn] = useState(false);
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [codeSending, setCodeSending] = useState(false);
  const [codeCountdown, setCodeCountdown] = useState(0);
  // 忘记密码
  const [forgotEmail, setForgotEmail] = useState('');
  const [forgotCode, setForgotCode] = useState('');
  const [forgotNewPwd, setForgotNewPwd] = useState('');
  const [forgotHint, setForgotHint] = useState('');
  const [forgotSending, setForgotSending] = useState(false);
  const [forgotCountdown, setForgotCountdown] = useState(0);

  const getRedirect = () => {
    try {
      const p = new URLSearchParams(window.location.search);
      const r = p.get('redirect');
      if (r && r.startsWith('https://')) return r;
    } catch (e) {}
    return null;
  };

  useEffect(() => {
    getPublicSettings().then((s) => {
      setBrand(s);
      setRegOpen(s.registration_open);
      setTsEnabled(!!s.turnstile_enabled);
      setTsSiteKey(s.turnstile_site_key || '');
      setEmailReg(!!s.email_register_enabled);
      setLdapOn(!!s.lldap_enabled);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!tsEnabled || !tsSiteKey || !tsContainerRef.current) return;
    let cancelled = false;
    loadTurnstileScript().then(() => {
      if (cancelled || !tsContainerRef.current) return;
      const id = window.turnstile.render(tsContainerRef.current, {
        sitekey: tsSiteKey,
        callback: (token) => setTsToken(token),
        'expired-callback': () => setTsToken(''),
        'error-callback': () => setTsToken(''),
        theme: 'auto',
      });
      setTsWidgetId(id);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [tsEnabled, tsSiteKey]);

  useEffect(() => {
    if (codeCountdown <= 0) return;
    const t = setTimeout(() => setCodeCountdown(codeCountdown - 1), 1000);
    return () => clearTimeout(t);
  }, [codeCountdown]);

  useEffect(() => {
    if (forgotCountdown <= 0) return;
    const t = setTimeout(() => setForgotCountdown(forgotCountdown - 1), 1000);
    return () => clearTimeout(t);
  }, [forgotCountdown]);

  const switchMode = (m) => {
    setMode(m);
    setError('');
    setTsToken('');
    setForgotHint('');
    if (tsWidgetId !== null && window.turnstile) {
      try { window.turnstile.reset(tsWidgetId); } catch (e) {}
    }
  };

  const doSendCode = async () => {
    setError('');
    if (!email || !email.includes('@')) { setError('请先输入正确的邮箱'); return; }
    setCodeSending(true);
    try {
      await sendCode(email);
      setCodeCountdown(60);
    } catch (err) { setError(err.message); }
    setCodeSending(false);
  };

  const doForgotSend = async () => {
    setError('');
    setForgotSending(true);
    try {
      const res = await forgotPassword(username, tsToken);
      setForgotHint(res.email_hint || '');
      setForgotCountdown(60);
    } catch (err) { setError(err.message); }
    setForgotSending(false);
  };

  const doReset = async (e) => {
    e.preventDefault();
    setError('');
    if (!forgotEmail || !forgotCode || !forgotNewPwd) { setError('请填写邮箱、验证码和新密码'); return; }
    if (forgotNewPwd.length < 6) { setError('密码至少 6 位'); return; }
    setLoading(true);
    try {
      await resetPassword(username, forgotEmail, forgotCode, forgotNewPwd);
      setError('');
      setMode('login');
      setForgotEmail(''); setForgotCode(''); setForgotNewPwd(''); setForgotHint('');
      alert('密码重置成功，请登录');
    } catch (err) { setError(err.message); }
    setLoading(false);
  };

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    if (mode === 'register' && password !== password2) { setError('两次密码不一致'); return; }
    if (tsEnabled && !tsToken) { setError('请先完成人机验证'); return; }
    if (mode === 'register' && emailReg && (!email || !code)) { setError('请填写邮箱并输入验证码'); return; }
    setLoading(true);
    try {
      const res = mode === 'login'
        ? await login(username, password, tsToken)
        : await register(username, password, tsToken, email, code);
      setToken(res.token);
      onLoggedIn(res);
      const target = getRedirect();
      if (target) { window.location.href = target; return; }
    } catch (err) {
      setError(err.message);
      setTsToken('');
      if (tsWidgetId !== null && window.turnstile) {
        try { window.turnstile.reset(tsWidgetId); } catch (e2) {}
      }
    }
    setLoading(false);
  };

  return (
    <div className="auth-page">
      <div className="auth-box">
        <div className="auth-logo"><BrandLogo logo={brand.brand_logo} name={brand.brand_name} size="large" /></div>
        <h1 className="auth-title">{brand.brand_name}</h1>
        <p className="auth-sub">{brand.brand_tagline}{brand.brand_free_text ? ' · ' + brand.brand_free_text : ''}</p>

        {mode !== 'forgot' && (
          <div className="auth-mode">
            <button className={mode === 'login' ? 'active' : ''} onClick={() => switchMode('login')}>登录</button>
            {regOpen && (
              <button className={mode === 'register' ? 'active' : ''} onClick={() => switchMode('register')}>注册</button>
            )}
          </div>
        )}

        <form onSubmit={submit}>
          {mode !== 'forgot' ? (
            <>
              <input className="auth-input" placeholder="用户名" value={username} onChange={(e) => setUsername(e.target.value)} required minLength={2} />
              <input className="auth-input" type="password" placeholder="密码（至少 6 位）" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} />
              {mode === 'register' && (
                <input className="auth-input" type="password" placeholder="确认密码" value={password2} onChange={(e) => setPassword2(e.target.value)} required />
              )}
              {mode === 'register' && emailReg && (
                <>
                  <input className="auth-input" type="email" placeholder="邮箱（用于接收验证码）" value={email} onChange={(e) => setEmail(e.target.value)} required />
                  <div style={{ display: 'flex', gap: 8 }}>
                    <input className="auth-input" placeholder="验证码" value={code} onChange={(e) => setCode(e.target.value)} required style={{ flex: 1 }} />
                    <button type="button" className="auth-submit" style={{ flex: '0 0 110px', padding: '0 12px', fontSize: 14, opacity: (codeCountdown > 0 || codeSending) ? 0.6 : 1 }} disabled={codeCountdown > 0 || codeSending} onClick={doSendCode}>
                      {codeSending ? '发送中' : codeCountdown > 0 ? `${codeCountdown}s 后重发` : '发送验证码'}
                    </button>
                  </div>
                </>
              )}
              {(tsEnabled && tsSiteKey) && (
                <div className="auth-turnstile" ref={tsContainerRef} style={{ margin: '12px 0' }} />
              )}
              {mode === 'login' && (
                <div style={{ textAlign: 'right', marginTop: -4, marginBottom: 8 }}>
                  <a href="#!" onClick={(e) => { e.preventDefault(); switchMode('forgot'); }} style={{ fontSize: 13, color: '#4f46e5', cursor: 'pointer' }}>忘记密码？</a>
                </div>
              )}
              {error && <div className="auth-error">{error}</div>}
              <button className="auth-submit" disabled={loading || (tsEnabled && !tsToken)}>
                {loading ? '请稍候…' : mode === 'login' ? '登 录' : '注 册'}
              </button>
            </>
          ) : (
            <div style={{ marginTop: 8 }}>
              <p className="auth-sub" style={{ marginBottom: 12 }}>输入用户名，验证码将发送至绑定邮箱</p>
              <input className="auth-input" placeholder="用户名" value={username} onChange={(e) => setUsername(e.target.value)} required minLength={2} />
              {forgotHint && (
                <div className="auth-sub" style={{ fontSize: 12, color: '#22c55e', marginBottom: 8 }}>验证码已发送至 {forgotHint}</div>
              )}
              <input className="auth-input" type="email" placeholder="绑定邮箱" value={forgotEmail} onChange={(e) => setForgotEmail(e.target.value)} />
              <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                <input className="auth-input" placeholder="验证码" value={forgotCode} onChange={(e) => setForgotCode(e.target.value)} style={{ flex: 1 }} />
                <button type="button" className="auth-submit" style={{ flex: '0 0 110px', padding: '0 12px', fontSize: 14, opacity: (forgotCountdown > 0 || forgotSending) ? 0.6 : 1 }} disabled={forgotCountdown > 0 || forgotSending || !username} onClick={doForgotSend}>
                  {forgotSending ? '发送中' : forgotCountdown > 0 ? `${forgotCountdown}s` : '发送验证码'}
                </button>
              </div>
              <input className="auth-input" type="password" placeholder="新密码（至少 6 位）" value={forgotNewPwd} onChange={(e) => setForgotNewPwd(e.target.value)} />
              {(tsEnabled && tsSiteKey) && (
                <div className="auth-turnstile" ref={tsContainerRef} style={{ margin: '12px 0' }} />
              )}
              {error && <div className="auth-error">{error}</div>}
              <button className="auth-submit" disabled={loading} onClick={doReset}>
                {loading ? '请稍候…' : '重置密码'}
              </button>
              <div style={{ textAlign: 'center', marginTop: 8 }}>
                <a href="#!" onClick={(e) => { e.preventDefault(); switchMode('login'); }} style={{ fontSize: 13, color: '#4f46e5', cursor: 'pointer' }}>返回登录</a>
              </div>
            </div>
          )}
        </form>
      </div>
    </div>
  );
}
