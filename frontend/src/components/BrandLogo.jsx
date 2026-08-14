import React from 'react';

// Logo 渲染：URL → <img>，否则按 Emoji 文本显示
export default function BrandLogo({ logo, name, size = 'default' }) {
  const isUrl = logo && (logo.startsWith('http') || logo.startsWith('/uploads'));
  const cls = 'brand-logo ' + (size === 'large' ? 'large' : '');
  if (isUrl) {
    return <img className={cls} src={logo} alt={name || 'logo'} />;
  }
  return <span className={cls + ' emoji'}>{logo || '🧪'}</span>;
}
