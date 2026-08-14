import React from 'react'

const ICONS = {
  lobster: '\u{1F99E}',
  robot: '\u{1F916}',
  chat: '\u{1F4AC}',
}

export default function AgentCard({ agent, onDeploy }) {
  const { id, name, description, icon, price_monthly } = agent
  const emoji = ICONS[icon] || '\u{1F916}'

  return (
    <div className="card">
      <div className="card-icon" style={{ fontSize: '48px' }}>
        {emoji}
      </div>
      <h3 className="card-name">{name}</h3>
      <p className="card-description">{description}</p>
      <p className="card-price">{price_monthly === 0 ? "免费" : `¥${price_monthly}/月`}</p>
      <button onClick={() => onDeploy(agent)}>立即部署</button>
    </div>
  )
}