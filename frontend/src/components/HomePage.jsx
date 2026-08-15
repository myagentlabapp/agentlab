import React, { useState, useEffect } from 'react';
import { getPublicSettings } from '../api/client.js';
import BrandLogo from './BrandLogo.jsx';

export default function HomePage({ onNavigate }) {
  const [brand, setBrand] = useState({
    brand_logo: '🧪', brand_name: '', brand_tagline: 'Agent 租赁平台',
    brand_slogan_1: '租一个 AI Agent', brand_slogan_2: '打开就能用',
    brand_promo: '', brand_free_text: '限时免费', brand_free_sub: '限时免费，部署即用。',
    brand_footer: '', brand_announcement: '', brand_primary_color: '#4f46e5',
  });

  useEffect(() => {
    getPublicSettings().then(setBrand).catch(() => {});
  }, []);

  const entries = [
    { key: 'market', icon: '🛒', title: '应用市场', desc: '浏览可租用的 AI Agent，一键部署专属实例', cta: '去逛逛' },
    { key: 'leases', icon: '📦', title: '我的实例', desc: '管理已部署的 Agent：查看地址、停止、续期', cta: '管理实例' },
    { key: 'admin', icon: '⚙️', title: '管理后台', desc: '平台运营：用户、实例、容器、资源监控', cta: '进入后台' },
  ];

  return (
    <div className="home-page">
      {brand.brand_announcement && (
        <div className="announcement-bar">{brand.brand_announcement}</div>
      )}

      <section className="hero" style={{ background: `linear-gradient(135deg, #1e293b 0%, ${brand.brand_primary_color} 60%, ${brand.brand_primary_color} 100%)` }}>
        <div className="hero-badge"><BrandLogo logo={brand.brand_logo} name={brand.brand_name} /> {brand.brand_name} · {brand.brand_tagline}</div>
        <h1 className="hero-title">{brand.brand_slogan_1}<br />{brand.brand_slogan_2}</h1>
        {brand.brand_promo && <p className="hero-sub">{brand.brand_promo}<br /><strong>{brand.brand_free_sub}</strong></p>}
        <div className="hero-actions">
          <button className="hero-btn primary" onClick={() => onNavigate('market')}>立即部署 →</button>
          <button className="hero-btn ghost" onClick={() => onNavigate('leases')}>查看我的实例</button>
        </div>
      </section>

      <section className="home-entries">
        {entries.map((e) => (
          <div key={e.key} className="home-entry-card" onClick={() => onNavigate(e.key)}>
            <div className="home-entry-icon">{e.icon}</div>
            <div className="home-entry-title">{e.title}</div>
            <div className="home-entry-desc">{e.desc}</div>
            <div className="home-entry-cta">{e.cta} →</div>
          </div>
        ))}
      </section>

      <section className="home-features">
        <div className="feature"><div className="feature-icon">🔒</div><div className="feature-title">独立容器</div><div className="feature-desc">每个实例完全隔离，资源独立配额</div></div>
        <div className="feature"><div className="feature-icon">🌐</div><div className="feature-title">公网直达</div><div className="feature-desc">专属 HTTPS 子域名，打开即用</div></div>
        <div className="feature"><div className="feature-icon">🔑</div><div className="feature-title">自带 Key</div><div className="feature-desc">用自己的 API Key，用量自己掌控</div></div>
        <div className="feature"><div className="feature-icon">💰</div><div className="feature-title">{brand.brand_free_text}</div><div className="feature-desc">限时免费体验，先到先得</div></div>
      </section>

      <footer className="home-footer">{brand.brand_footer}</footer>
    </div>
  );
}
