import React, { useState, useEffect } from 'react'
import { deployAgent, getPublicSettings } from '../api/client.js'

export default function DeployDialog({ agent, onClose }) {
  const [apiKey, setApiKey] = useState('')
  const [durationDays, setDurationDays] = useState(7)
  const [maxDays, setMaxDays] = useState(30)
  const [deploying, setDeploying] = useState(false)
  const [resultUrl, setResultUrl] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    // 从平台设置读默认/最大时长
    getPublicSettings().then((s) => {
      const def = s.default_duration_days || 7
      const max = s.max_duration_days || 30
      setDurationDays(def)
      setMaxDays(max)
    }).catch(() => {})
  }, [])

  // 生成时长选项：7/15/30/60/90... 不超过 max
  const durations = []
  for (const d of [7, 15, 30, 60, 90, 180, 365]) {
    if (d <= maxDays) durations.push(d)
  }
  if (durations.length === 0) durations.push(maxDays)

  async function handleConfirm() {
    setDeploying(true)
    setError(null)
    try {
      const res = await deployAgent(agent.id, apiKey, durationDays)
      const url = res.url || res.endpoint || res.access_url
      setResultUrl(url)
      setTimeout(() => {
        onClose()
      }, 3000)
    } catch (err) {
      setError(err.message || '部署失败')
    } finally {
      setDeploying(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>部署 {agent.name}</h2>
        <p className="modal-agent-desc">{agent.description}</p>

        {resultUrl ? (
          <div className="modal-success">
            <p>✅ 部署成功！</p>
            <p>
              访问地址：{' '}
              <a href={resultUrl} target="_blank" rel="noreferrer">
                {resultUrl}
              </a>
            </p>
          </div>
        ) : (
          <>
            <label className="field-label">API Key</label>
            <input
              type="text"
              className="field-input"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="在 api.myagentlab.homes 购买"
            />

            <label className="field-label">租用时长（最长 {maxDays} 天）</label>
            <select
              className="field-input"
              value={durationDays}
              onChange={(e) => setDurationDays(Number(e.target.value))}
            >
              {durations.map((d) => (
                <option key={d} value={d}>{d} 天</option>
              ))}
            </select>

            {error && <p className="status-text error">{error}</p>}

            <div className="modal-actions">
              <button
                className="modal-btn-secondary"
                onClick={onClose}
                disabled={deploying}
              >
                取消
              </button>
              <button
                onClick={handleConfirm}
                disabled={deploying || !apiKey}
              >
                {deploying ? '部署中…' : '确认部署'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
