import React, { useState } from 'react'
import { recharge, myBalance, getMe } from '../api/client.js'

export default function RechargeDialog({ onClose, onRecharged }) {
  const [amount, setAmount] = useState(50)
  const [payUrl, setPayUrl] = useState(null)
  const [orderId, setOrderId] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function handleRecharge() {
    setLoading(true)
    setError(null)
    try {
      const res = await recharge(amount)
      setPayUrl(res.pay_url)
      setOrderId(res.order_id)
    } catch (err) {
      setError(err.message || '下单失败')
    } finally {
      setLoading(false)
    }
  }

  async function handlePaid() {
    // 刷新余额
    try {
      const b = await myBalance()
      if (onRecharged) onRecharged(b.balance)
      onClose()
    } catch (e) {
      setError(e.message || '查询余额失败，请稍后重试')
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>充值余额</h2>

        {!payUrl ? (
          <>
            <label className="field-label">充值金额（元）</label>
            <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
              {[10, 50, 100, 200].map((v) => (
                <button key={v} className="toggle-btn" style={amount === v ? { background: '#4f46e5', color: '#fff' } : {}}
                  onClick={() => setAmount(v)}>¥{v}</button>
              ))}
            </div>
            <input
              type="number" min="1" max="5000"
              className="field-input"
              value={amount}
              onChange={(e) => setAmount(Number(e.target.value))}
            />
            {error && <p className="status-text error">{error}</p>}
            <div className="modal-actions">
              <button className="modal-btn-secondary" onClick={onClose} disabled={loading}>取消</button>
              <button onClick={handleRecharge} disabled={loading || !amount || amount < 1}>
                {loading ? '下单中…' : '去支付'}
              </button>
            </div>
          </>
        ) : (
          <>
            <p className="status-text">✅ 订单已创建（{orderId.slice(0, 8)}…）</p>
            <p className="status-text">请在新窗口完成支付，支付完成后点击下方按钮刷新余额。</p>
            <div className="modal-actions">
              <a className="modal-btn-secondary" href={payUrl} target="_blank" rel="noreferrer" style={{ textDecoration: 'none' }}>打开支付页面</a>
              <button onClick={handlePaid} disabled={loading}>我已支付，刷新余额</button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
