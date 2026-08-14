import React, { useState, useEffect } from 'react';
import {
  adminGetSettings, adminUpdateSettings, adminGetAgents, adminUpdateAgent,
  adminCreateAgent, adminDeleteAgent, adminUserManage, adminUpdateUser,
  adminResetPassword, changeMyPassword, adminBackup, adminLogs,
} from '../api/client.js';

import BrandLogo from './BrandLogo.jsx';

function SettingsPanel({ onSaved }) {
  const [tab, setTab] = useState('brand');
  const [settings, setSettings] = useState({});
  const [agents, setAgents] = useState([]);
  const [users, setUsers] = useState([]);
  const [logs, setLogs] = useState([]);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');
  const [newAgent, setNewAgent] = useState({ name: '', image: '', description: '', icon: '🤖', price_monthly: 0 });
  const [backupData, setBackupData] = useState(null);
  const [pwdForm, setPwdForm] = useState({ old: '', neu: '' });

  const loadAll = () => {
    adminGetSettings().then(setSettings).catch((e) => setError(e.message));
    adminGetAgents().then(setAgents).catch((e) => setError(e.message));
    adminUserManage().then(setUsers).catch((e) => setError(e.message));
  };
  useEffect(loadAll, []);

  const flash = () => { setSaved(true); setTimeout(() => setSaved(false), 1800); };

  const saveSettings = async () => {
    setError('');
    try { await adminUpdateSettings(settings); flash(); if (onSaved) onSaved(); }
    catch (e) { setError(e.message); }
  };

  const updateAgent = async (id, fields) => {
    try { await adminUpdateAgent(id, fields); setAgents((p) => p.map((a) => (a.id === id ? { ...a, ...fields } : a))); flash(); }
    catch (e) { setError(e.message); }
  };

  const createAgent = async () => {
    if (!newAgent.name || !newAgent.image) { setError('名称和镜像必填'); return; }
    try {
      await adminCreateAgent(newAgent);
      setNewAgent({ name: '', image: '', description: '', icon: '🤖', price_monthly: 0 });
      adminGetAgents().then(setAgents);
      flash();
    } catch (e) { setError(e.message); }
  };

  const deleteAgent = async (id, name) => {
    if (!window.confirm('确认删除 ' + name + '？有运行中实例将无法删除')) return;
    try { await adminDeleteAgent(id); adminGetAgents().then(setAgents); flash(); }
    catch (e) { setError(e.message); }
  };

  const set = (key) => (e) => setSettings((s) => ({ ...s, [key]: e.target.value }));

  const doBackup = async () => {
    try { setBackupData(await adminBackup()); }
    catch (e) { setError(e.message); }
  };

  const downloadBackup = () => {
    const blob = new Blob([JSON.stringify(backupData, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'platform-backup-' + new Date().toISOString().slice(0, 10) + '.json';
    a.click();
  };

  const doChangePwd = async () => {
    setError('');
    try { await changeMyPassword(pwdForm.old, pwdForm.neu); setPwdForm({ old: '', neu: '' }); flash(); }
    catch (e) { setError(e.message); }
  };

  const doResetUserPwd = async (uid) => {
    const np = window.prompt('输入新密码（至少 6 位）');
    if (!np) return;
    try { await adminResetPassword(uid, np); flash(); }
    catch (e) { setError(e.message); }
  };

  const loadLogs = () => adminLogs().then(setLogs).catch((e) => setError(e.message));

  const tabs = [
    ['brand', '品牌设置'], ['pricing', '定价设置'], ['agents', 'Agent 管理'],
    ['users', '用户管理'], ['platform', '平台规则'], ['security', '安全与备份'], ['logs', '操作日志'],
  ];

  return (
    <div className="settings-panel">
      <div className="admin-nav">
        <h2>🛠 平台设置</h2>
        <div className="admin-tabs">
          {tabs.map(([k, label]) => (
            <button key={k} className={tab === k ? 'active' : ''} onClick={() => { setTab(k); if (k === 'logs') loadLogs(); }}>{label}</button>
          ))}
        </div>
      </div>

      {error && <div className="admin-error">{error}</div>}
      {saved && <div className="save-ok">✅ 已保存</div>}

      {/* ===== 品牌 ===== */}
      {tab === 'brand' && (
        <div className="settings-form">
          <div className="settings-grid">
            <div className="form-item"><label>站点名称</label><input value={settings.brand_name || ''} onChange={set('brand_name')} /></div>
            <div className="form-item"><label>Logo 链接</label>
              <input value={settings.brand_logo || ''} placeholder="图床图片链接，如 https://xxx.com/logo.png" onChange={set('brand_logo')} />
              {settings.brand_logo && (
                <div className="logo-preview">
                  <span className="muted">预览：</span>
                  <BrandLogo logo={settings.brand_logo} name="预览" />
                </div>
              )}
            </div>
            <div className="form-item"><label>副标题</label><input value={settings.brand_tagline || ''} onChange={set('brand_tagline')} /></div>
            <div className="form-item"><label>主色调</label><input type="color" value={settings.brand_primary_color || '#4f46e5'} onChange={set('brand_primary_color')} /></div>
            <div className="form-item"><label>标语第一行</label><input value={settings.brand_slogan_1 || ''} onChange={set('brand_slogan_1')} /></div>
            <div className="form-item"><label>标语第二行</label><input value={settings.brand_slogan_2 || ''} onChange={set('brand_slogan_2')} /></div>
            <div className="form-item full"><label>宣传文案</label><textarea rows="2" value={settings.brand_promo || ''} onChange={set('brand_promo')} /></div>
            <div className="form-item"><label>免费文案</label><input value={settings.brand_free_text || ''} onChange={set('brand_free_text')} /></div>
            <div className="form-item"><label>免费副文案</label><input value={settings.brand_free_sub || ''} onChange={set('brand_free_sub')} /></div>
            <div className="form-item full"><label>页脚</label><input value={settings.brand_footer || ''} onChange={set('brand_footer')} /></div>
            <div className="form-item full"><label>公告横幅（空=不显示）</label><input value={settings.brand_announcement || ''} onChange={set('brand_announcement')} /></div>
            <div className="form-item"><label>ICP 备案号</label><input value={settings.brand_icp || ''} placeholder="如 京ICP备xxxxxxxx号" onChange={set('brand_icp')} /></div>
            <div className="form-item"><label>统计代码（Umami/GA）</label><input value={settings.brand_stat_script || ''} placeholder="<script>…</script>" onChange={set('brand_stat_script')} /></div>
            <div className="form-item full"><label>自定义 CSS</label><textarea rows="3" value={settings.brand_custom_css || ''} placeholder=".hero { … }" onChange={set('brand_custom_css')} /></div>
          </div>
          <button className="save-btn" onClick={saveSettings}>保存品牌设置</button>
        </div>
      )}

      {/* ===== 定价 ===== */}
      {tab === 'pricing' && (
        <div className="settings-form">
          <div className="settings-grid">
            <div className="form-item"><label>币种符号</label><input value={settings.currency_symbol || '¥'} onChange={set('currency_symbol')} /></div>
            <div className="form-item"><label>计费模式</label>
              <select value={settings.billing_mode} onChange={set('billing_mode')}>
                <option value="monthly">按月租</option>
                <option value="hourly">按时长</option>
                <option value="usage">按用量</option>
              </select>
            </div>
            <div className="form-item"><label>新用户折扣（%）</label><input type="number" value={settings.discount_new_user} onChange={set('discount_new_user')} /></div>
            <div className="form-item"><label>免费模式</label>
              <select value={settings.free_mode} onChange={set('free_mode')}>
                <option value="true">开启（全部按免费展示）</option>
                <option value="false">关闭（按实际价格）</option>
              </select>
            </div>
            {agents.map((a) => (
              <div key={a.id} className="form-item">
                <label>{a.name} 月租（元，0=免费）</label>
                <input type="number" min="0" value={a.price_monthly} onChange={(e) => updateAgent(a.id, { price_monthly: parseInt(e.target.value) || 0 })} />
              </div>
            ))}
          </div>
          <button className="save-btn" onClick={saveSettings}>保存定价设置</button>
        </div>
      )}

      {/* ===== Agent 管理 ===== */}
      {tab === 'agents' && (
        <div>
          <div className="agent-add-card">
            <h4>➕ 新增 Agent</h4>
            <div className="agent-manage-body">
              <div className="form-item"><label>名称 *</label><input value={newAgent.name} onChange={(e) => setNewAgent({ ...newAgent, name: e.target.value })} /></div>
              <div className="form-item"><label>镜像 *</label><input value={newAgent.image} placeholder="myagentlab/xxx:latest" onChange={(e) => setNewAgent({ ...newAgent, image: e.target.value })} /></div>
              <div className="form-item"><label>图标</label><input value={newAgent.icon} onChange={(e) => setNewAgent({ ...newAgent, icon: e.target.value })} /></div>
              <div className="form-item"><label>月租（元）</label><input type="number" min="0" value={newAgent.price_monthly} onChange={(e) => setNewAgent({ ...newAgent, price_monthly: parseInt(e.target.value) || 0 })} /></div>
              <div className="form-item full"><label>描述</label><input value={newAgent.description} onChange={(e) => setNewAgent({ ...newAgent, description: e.target.value })} /></div>
            </div>
            <button className="save-btn" onClick={createAgent}>创建 Agent</button>
          </div>

          {agents.map((a) => (
            <div key={a.id} className="agent-manage-card">
              <div className="agent-manage-head">
                <span className="agent-manage-icon">{a.icon || '🤖'}</span>
                <span className="agent-manage-name">{a.name}</span>
                <span className={'agent-status ' + (a.enabled ? 'on' : 'off')}>{a.enabled ? '已上架' : '已下架'}</span>
                <button className="toggle-btn" onClick={() => updateAgent(a.id, { enabled: !a.enabled })}>{a.enabled ? '下架' : '上架'}</button>
                <button className="toggle-btn danger" onClick={() => deleteAgent(a.id, a.name)}>删除</button>
              </div>
              <div className="agent-manage-body">
                <div className="form-item"><label>名称</label><input value={a.name} onChange={(e) => updateAgent(a.id, { name: e.target.value })} /></div>
                <div className="form-item"><label>图标</label><input value={a.icon} onChange={(e) => updateAgent(a.id, { icon: e.target.value })} /></div>
                <div className="form-item full"><label>描述</label><textarea rows="2" value={a.description} onChange={(e) => updateAgent(a.id, { description: e.target.value })} /></div>
                <div className="form-item"><label>镜像</label><input value={a.image} onChange={(e) => updateAgent(a.id, { image: e.target.value })} /></div>
                <div className="form-item"><label>月租（元）</label><input type="number" min="0" value={a.price_monthly} onChange={(e) => updateAgent(a.id, { price_monthly: parseInt(e.target.value) || 0 })} /></div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ===== 用户管理 ===== */}
      {tab === 'users' && (
        <table className="admin-table">
          <thead><tr><th>用户名</th><th>角色</th><th>状态</th><th>实例(运行中/总数)</th><th>注册时间</th><th>操作</th></tr></thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>{u.username}</td>
                <td>{u.is_admin ? '管理员' : '普通用户'}</td>
                <td className={u.enabled ? 'green' : ''}>{u.enabled ? '正常' : '已禁用'}</td>
                <td>{u.instances.running}/{u.instances.total}</td>
                <td>{u.created_at ? u.created_at.slice(0, 10) : '-'}</td>
                <td>
                  {!u.is_admin && (
                    <>
                      <button className="toggle-btn" onClick={() => adminUpdateUser(u.id, { enabled: !u.enabled }).then(() => adminUserManage().then(setUsers))}>
                        {u.enabled ? '禁用' : '启用'}
                      </button>{' '}
                      <button className="toggle-btn" onClick={() => doResetUserPwd(u.id)}>重置密码</button>
                    </>
                  )}
                  {u.is_admin && <span className="muted">-</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* ===== 平台规则 ===== */}
      {tab === 'platform' && (
        <div className="settings-form">
          <div className="settings-grid">
            <div className="form-item"><label>允许注册</label>
              <select value={settings.registration_open} onChange={set('registration_open')}>
                <option value="true">开放</option><option value="false">关闭</option>
              </select>
            </div>
            <div className="form-item"><label>允许部署</label>
              <select value={settings.deploy_open} onChange={set('deploy_open')}>
                <option value="true">开放</option><option value="false">暂停</option>
              </select>
            </div>
            <div className="form-item"><label>每用户最大实例数</label><input type="number" value={settings.max_instances_per_user} onChange={set('max_instances_per_user')} /></div>
            <div className="form-item"><label>默认时长（天）</label><input type="number" value={settings.default_duration_days} onChange={set('default_duration_days')} /></div>
            <div className="form-item"><label>最大时长（天）</label><input type="number" value={settings.max_duration_days} onChange={set('max_duration_days')} /></div>
            <div className="form-item"><label>实例内存上限（MB）</label><input type="number" value={settings.instance_mem_limit_mb} onChange={set('instance_mem_limit_mb')} /></div>
            <div className="form-item"><label>CPU 配额</label><input type="number" value={settings.instance_cpu_quota} onChange={set('instance_cpu_quota')} /></div>
            <div className="form-item"><label>端口范围起</label><input type="number" value={settings.port_range_start} onChange={set('port_range_start')} /></div>
            <div className="form-item"><label>端口范围止</label><input type="number" value={settings.port_range_end} onChange={set('port_range_end')} /></div>
          </div>
          <button className="save-btn" onClick={saveSettings}>保存平台规则</button>
        </div>
      )}

      {/* ===== 安全与备份 ===== */}
      {tab === 'security' && (
        <div className="settings-form">
          <h4>🔑 修改密码</h4>
          <div className="settings-grid">
            <div className="form-item"><label>原密码</label><input type="password" value={pwdForm.old} onChange={(e) => setPwdForm({ ...pwdForm, old: e.target.value })} /></div>
            <div className="form-item"><label>新密码（至少 6 位）</label><input type="password" value={pwdForm.neu} onChange={(e) => setPwdForm({ ...pwdForm, neu: e.target.value })} /></div>
          </div>
          <button className="save-btn" onClick={doChangePwd}>修改密码</button>

          <hr className="settings-hr" />
          <h4>💾 数据备份</h4>
          <p className="muted">导出平台全部数据（Agent/用户/租约/设置），JSON 格式。</p>
          <button className="save-btn" onClick={doBackup}>{backupData ? '已生成备份' : '生成备份'}</button>
          {backupData && (
            <button className="save-btn ghost" onClick={downloadBackup}>下载备份文件</button>
          )}
        </div>
      )}

      {/* ===== 操作日志 ===== */}
      {tab === 'logs' && (
        <div>
          <button className="save-btn ghost" onClick={loadLogs} style={{ marginBottom: 12 }}>刷新日志</button>
          <table className="admin-table">
            <thead><tr><th>时间</th><th>用户</th><th>操作</th><th>Agent</th><th>状态</th></tr></thead>
            <tbody>
              {logs.length === 0 && <tr><td colSpan="5" className="muted">暂无日志（部署/停止操作会记录）</td></tr>}
              {logs.map((l, i) => (
                <tr key={i}>
                  <td>{l.time ? l.time.replace('T', ' ').slice(0, 19) : '-'}</td>
                  <td>{l.user_id.slice(0, 8)}</td>
                  <td>{l.action}</td>
                  <td>{l.agent_id}</td>
                  <td className={l.status === 'success' ? 'green' : ''}>{l.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default SettingsPanel;
