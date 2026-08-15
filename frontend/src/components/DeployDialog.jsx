import React, { useState, useEffect } from 'react'
import { deployAgent, getPublicSettings } from '../api/client.js'

export default function DeployDialog({ agent, onClose, onGoRecharge }) {
  const [apiKey, setApiKey] = useState('')
  const [durationDays, setDurationDays] = useState(7)
  const [maxDays, setMaxDays] = useState(30)
  const [billingMode, setBillingMode] = useState('free')
  const [months, setMonths] = useState(1)
  const [hours, setHours] = useState(1)
  const [deploying, setDeploying] = useState(false)
  const [resultUrl, setResultUrl] = useState(null)
  const [error, setError] = useState(null)
  const [needRecharge, setNeedRecharge] = useState(false)

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

  // 价格
  const priceMonthly = agent.price_monthly || 0
  const priceHourly = agent.price_hourly || 0
  const priceDaily = agent.price_daily || 0

  function calcCost() {
    if (billingMode === 'monthly') return priceMonthly * months
    if (billingMode === 'hourly') return priceHourly * hours
    return 0
  }
  const cost = calcCost()

  async function handleConfirm() {
    setDeploying(true)
    setError(null)
    setNeedRecharge(false)
    try {
      const res = await deployAgent(agent.id, apiKey, durationDays, billingMode, months, hours)
      const url = res.url || res.endpoint || res.access_url
      setResultUrl(url)
      setTimeout(() => {
        onClose()
      }, 3000)
    } catch (err) {
      setError(err.message || '部署失败')
      if (err.message && String(err.message).includes('余额')) {
        setNeedRecharge(true)
      }
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
              placeholder="在模型 API 网关购买（如 https://api.example.com）"
            />

            <label className="field-label">计费模式</label>
            <select
              className="field-input"
              value={billingMode}
              onChange={(e) => setBillingMode(e.target.value)}
            >
              <option value="free">免费</option>
              {(priceMonthly > 0 || agent.billing_modes?.includes?.('monthly')) && <option value="monthly">按月（¥{priceMonthly}/月）</option>}
              {(priceHourly > 0 || agent.billing_modes?.includes?.('hourly')) && <option value="hourly">按小时（¥{priceHourly}/小时）</option>}
              <option value="usage">按量（预扣 ¥{(priceDaily || 1) * 3}，按天扣费）</option>
            </select>

            {billingMode === 'free' && (
              <>
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
              </>
            )}

            {billingMode === 'monthly' && (
              <>
                <label className="field-label">租用月数</label>
                <select
                  className="field-input"
                  value={months}
                  onChange={(e) => setMonths(Number(e.target.value))}
                >
                  {[1, 2, 3, 6, 12].map((m) => (
                    <option key={m} value={m}>{m} 个月</option>
                  ))}
                </select>
              </>
            )}

            {billingMode === 'hourly' && (
              <>
                <label className="field-label">租用小时数</label>
                <input
                  type="number"
                  min="1"
                  max="720"
                  className="field-input"
                  value={hours}
                  onChange={(e) => setHours(Number(e.target.value))}
                />
              </>
            )}

            {cost > 0 && (
              <p className="status-text">本次费用：<strong>¥{cost.toFixed(2)}</strong></p>
            )}

            {error && (
              <p className="status-text error">
                {error}
                {needRecharge && onGoRecharge && (
                  <button
                    className="modal-btn-secondary"
                    style={{ marginLeft: 8 }}
                    onClick={() => { onClose(); onGoRecharge() }}
                  >
                    去充值
                  </button>
                )}
              </p>
            )}

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
                {deploying ? '部署中…' : cost > 0 ? `确认部署（¥${cost.toFixed(2)}）` : '确认部署'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
