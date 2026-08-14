import React, { useState, useEffect, useCallback } from 'react'
import { getLeases, stopLease } from '../api/client.js'

const STATUS_MAP = {
  running: '运行中',
  stopped: '已停止',
  expired: '已过期',
}

export default function LeaseList({ leases: controlledLeases, setLeases: setControlledLeases }) {
  const [internalLeases, setInternalLeases] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [stoppingId, setStoppingId] = useState(null)

  const isControlled = controlledLeases !== undefined && setControlledLeases !== undefined
  const leases = isControlled ? controlledLeases : internalLeases
  const setLeases = isControlled ? setControlledLeases : setInternalLeases

  const refresh = useCallback(() => {
    setLoading(true)
    getLeases()
      .then((data) => {
        setLeases(data)
        setError(null)
      })
      .catch((err) => {
        setError(err.message || '加载失败')
      })
      .finally(() => setLoading(false))
  }, [setLeases])

  useEffect(() => {
    refresh()
  }, [refresh])

  async function handleStop(leaseId) {
    setStoppingId(leaseId)
    try {
      await stopLease(leaseId)
      await refresh()
    } catch (err) {
      setError(err.message || '停止失败')
    } finally {
      setStoppingId(null)
    }
  }

  if (loading) return <p className="status-text">加载中…</p>
  if (error) return <p className="status-text error">错误：{error}</p>
  if (leases.length === 0) return <p className="status-text">还没有任何实例</p>

  return (
    <table className="lease-table">
      <thead>
        <tr>
          <th>Agent</th>
          <th>状态</th>
          <th>访问地址</th>
          <th>到期时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        {leases.map((lease) => {
          const status = (lease.status || '').toLowerCase()
          const running = status === 'running'
          return (
            <tr key={lease.id}>
              <td>{lease.agent_name || lease.agent_id || lease.id}</td>
              <td>
                <span className={running ? 'status-running' : 'status-stopped'}>
                  {STATUS_MAP[status] || lease.status}
                </span>
              </td>
              <td>
                {lease.url ? (
                  <a href={lease.url} target="_blank" rel="noreferrer">
                    {lease.url}
                  </a>
                ) : (
                  '—'
                )}
              </td>
              <td>{lease.expires_at || lease.expires || '—'}</td>
              <td>
                <button
                  className="stop-btn"
                  onClick={() => handleStop(lease.id)}
                  disabled={!running || stoppingId === lease.id}
                >
                  {stoppingId === lease.id ? '停止中…' : '停止'}
                </button>
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}