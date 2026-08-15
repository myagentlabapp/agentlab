import React, { useState, useEffect } from 'react'
import AgentCard from './AgentCard.jsx'
import DeployDialog from './DeployDialog.jsx'
import { getAgents } from '../api/client.js'

export default function AgentList({ onDeploy, onGoRecharge }) {
  const [agents, setAgents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [deployTarget, setDeployTarget] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getAgents()
      .then((data) => {
        if (!cancelled) {
          setAgents(data)
          setError(null)
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || '加载失败')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (loading) return <p className="status-text">加载中…</p>
  if (error) return <p className="status-text error">错误：{error}</p>
  if (agents.length === 0) return <p className="status-text">暂无可用的 Agent</p>

  return (
    <>
      <div className="grid">
        {agents.map((agent) => (
          <AgentCard
            key={agent.id}
            agent={agent}
            onDeploy={(a) => setDeployTarget(a)}
          />
        ))}
      </div>

      {deployTarget && (
        <DeployDialog
          agent={deployTarget}
          onGoRecharge={onGoRecharge}
          onClose={() => {
            setDeployTarget(null)
            if (onDeploy) onDeploy(deployTarget)
          }}
        />
      )}
    </>
  )
}