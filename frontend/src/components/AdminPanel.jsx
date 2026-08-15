import React, { useState, useEffect } from 'react';
import { adminOverview, adminUsers, adminLeases, adminContainers, adminResources, adminExtendLease, adminRecycleLease, adminLeaseLogs } from '../api/client.js';
import SettingsPanel from './SettingsPanel.jsx';

function AdminPanel({ onBrandSaved }) {
  const [tab, setTab] = useState('overview');
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const fetchData = async (ep) => {
    setLoading(true);
    setError('');
    try {
      const fns = {
        overview: adminOverview,
        users: adminUsers,
        leases: adminLeases,
        containers: adminContainers,
        resources: adminResources,
      };
      const json = await fns[ep]();
      setData(json);
    } catch (e) {
      setError(e.message);
      setData(null);
    }
    setLoading(false);
  };

  useEffect(() => { fetchData('overview'); }, []);

  const switchTab = (ep) => {
    setTab(ep);
    if (ep !== 'settings') fetchData(ep);
  };

  const tabs = [
    ['overview', '总览'],
    ['users', '用户'],
    ['leases', '实例'],
    ['containers', '容器'],
    ['resources', '资源'],
    ['settings', '平台设置'],
  ];

  return (
    <div className="admin-panel">
      <div className="admin-nav">
        <h2>🧪 管理后台</h2>
        <div className="admin-tabs">
          {tabs.map(([ep, label]) => (
            <button key={ep} className={tab === ep ? 'active' : ''} onClick={() => switchTab(ep)}>{label}</button>
          ))}
        </div>
      </div>

      {error && <div className="admin-error">错误：{error}</div>}
      {loading && <div>加载中...</div>}

      {!loading && data && tab === 'overview' && (
        <div className="admin-cards">
          <div className="stat-card"><div className="stat-num">{data.total_users}</div><div>总用户</div></div>
          <div className="stat-card"><div className="stat-num">{data.total_leases}</div><div>总实例</div></div>
          <div className="stat-card"><div className="stat-num green">{data.running_leases}</div><div>运行中</div></div>
          <div className="stat-card"><div className="stat-num">{data.running_containers}</div><div>容器</div></div>
          <div className="stat-card"><div className="stat-num">{data.agent_count}</div><div>Agent 种类</div></div>
          <div>
            <h4>Agent 分布</h4>
            {Object.entries(data.agent_distribution || {}).map(([k, v]) => (
              <div key={k}>{k}: {v} 个实例</div>
            ))}
          </div>
        </div>
      )}

      {!loading && data && tab === 'users' && (
        <table className="admin-table">
          <thead><tr><th>用户</th><th>部署数</th><th>运行中</th><th>最近活动</th></tr></thead>
          <tbody>
            {data.map(u => (
              <tr key={u.user_id}>
                <td>{u.user_id}</td>
                <td>{u.deploy_count}</td>
                <td className={u.running > 0 ? 'green' : ''}>{u.running}</td>
                <td>{u.last_active || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {!loading && data && tab === 'leases' && (
        <table className="admin-table">
          <thead><tr><th>Agent</th><th>用户</th><th>状态</th><th>访问地址</th><th>到期</th><th>操作</th></tr></thead>
          <tbody>
            {data.map(l => (
              <tr key={l.id}>
                <td>{l.agent_name}</td>
                <td>{l.user_id}</td>
                <td className={l.status === 'running' ? 'green' : ''}>{l.status}</td>
                <td>{l.url ? <a href={l.url} target="_blank" rel="noreferrer">{l.url}</a> : '-'}</td>
                <td>{l.expires_at ? l.expires_at.slice(0, 10) : '-'}</td>
                <td>
                  {l.status === 'running' && (
                    <>
                      <button className="toggle-btn" onClick={() => { const d = prompt('延长天数（从用户余额扣费）:'); if (d) adminExtendLease(l.id, parseInt(d)).then(() => fetchData('leases')).catch(e => alert(e.message)); }}>延长</button>{' '}
                      <button className="toggle-btn" onClick={() => { if (confirm('强制回收该实例？（停止并删除容器）')) adminRecycleLease(l.id).then(() => fetchData('leases')).catch(e => alert(e.message)); }}>回收</button>{' '}
                      <button className="toggle-btn" onClick={() => adminLeaseLogs(l.id, 200).then(r => alert(r.logs.slice(-1500))).catch(e => alert(e.message))}>日志</button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {!loading && data && tab === 'containers' && (
        <table className="admin-table">
          <thead><tr><th>容器名</th><th>状态</th><th>Agent</th><th>用户</th><th>镜像</th></tr></thead>
          <tbody>
            {data.map(ct => (
              <tr key={ct.name}>
                <td>{ct.name}</td>
                <td className={ct.status === 'running' ? 'green' : ''}>{ct.status}</td>
                <td>{ct.agent_id}</td>
                <td>{ct.user_id}</td>
                <td>{ct.image}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {!loading && data && tab === 'resources' && (
        <div className="admin-cards">
          <div className="stat-card"><div className="stat-num">{data.memory_mb?.used}/{data.memory_mb?.total}</div><div>内存 MB</div></div>
          <div className="stat-card"><div className="stat-num">{data.disk_root}</div><div>磁盘使用</div></div>
          <div className="stat-card"><div className="stat-num">{data.cpu_cores}</div><div>CPU 核数</div></div>
          <div className="stat-card"><div className="stat-num">{data.running_agent_containers}</div><div>Agent 容器</div></div>
        </div>
      )}

      {tab === 'settings' && <SettingsPanel onSaved={onBrandSaved} />}
    </div>
  );
}

export default AdminPanel;
