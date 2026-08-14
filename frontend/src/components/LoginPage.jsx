import React, { useState, useEffect } from 'react';
import { login, register, setToken, getPublicSettings } from '../api/client.js';
import BrandLogo from './BrandLogo.jsx';

export default function LoginPage({ onLoggedIn }) {
  const [mode, setMode] = useState('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [password2, setPassword2] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [brand, setBrand] = useState({ brand_logo: '🧪', brand_name: '智体工坊', brand_tagline: 'Agent 租赁平台' });
  const [regOpen, setRegOpen] = useState(true);

  useEffect(() => {
    getPublicSettings().then((s) => {
      setBrand(s);
      setRegOpen(s.registration_open);
    }).catch(() => {});
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    if (mode === 'register' && password !== password2) {
      setError('两次密码不一致');
      return;
    }
    setLoading(true);
    try {
      const res = mode === 'login'
        ? await login(username, password)
        : await register(username, password);
      setToken(res.token);
      onLoggedIn(res);
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  };

  return (
    <div className="auth-page">
      <div className="auth-box">
        <div className="auth-logo"><BrandLogo logo={brand.brand_logo} name={brand.brand_name} size="large" /></div>
        <h1 className="auth-title">{brand.brand_name}</h1>
        <p className="auth-sub">{brand.brand_tagline}{brand.brand_free_text ? ' · ' + brand.brand_free_text : ''}</p>

        <div className="auth-mode">
          <button className={mode === 'login' ? 'active' : ''} onClick={() => { setMode('login'); setError(''); }}>登录</button>
          {regOpen && (
            <button className={mode === 'register' ? 'active' : ''} onClick={() => { setMode('register'); setError(''); }}>注册</button>
          )}
        </div>

        <form onSubmit={submit}>
          <input className="auth-input" placeholder="用户名" value={username} onChange={(e) => setUsername(e.target.value)} required minLength={2} />
          <input className="auth-input" type="password" placeholder="密码（至少 6 位）" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} />
          {mode === 'register' && (
            <input className="auth-input" type="password" placeholder="确认密码" value={password2} onChange={(e) => setPassword2(e.target.value)} required />
          )}
          {error && <div className="auth-error">{error}</div>}
          <button className="auth-submit" disabled={loading}>
            {loading ? '请稍候…' : mode === 'login' ? '登 录' : '注 册'}
          </button>
        </form>
      </div>
    </div>
  );
}
