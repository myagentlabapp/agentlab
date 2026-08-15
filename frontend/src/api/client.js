const BASE_URL = ''
const TOKEN_KEY = 'myagentlab_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

export function isLoggedIn() {
  return !!getToken()
}

async function request(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {})
  }
  const token = getToken()
  if (token) headers['Authorization'] = 'Bearer ' + token

  const res = await fetch(BASE_URL + path, {
    headers,
    ...options
  })
  if (res.status === 401) {
    // 登录失效：清除 token，跳回登录
    setToken(null)
    window.dispatchEvent(new Event('auth-changed'))
    throw new Error('请先登录')
  }
  if (!res.ok) {
    let message = `Request failed: ${res.status}`
    try {
      const body = await res.json()
      if (body && body.detail) message = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
      else if (body && body.message) message = body.message
    } catch (_) {}
    throw new Error(message)
  }
  const text = await res.text()
  if (!text) return null
  return JSON.parse(text)
}

// Auth
export function register(username, password, turnstileToken, email, code) {
  return request('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify({ username, password, turnstile_token: turnstileToken || '', email: email || '', code: code || '' })
  })
}

export function sendCode(email) {
  return request('/api/auth/send-code', {
    method: 'POST',
    body: JSON.stringify({ email })
  })
}

export function forgotPassword(username, turnstileToken) {
  return request('/api/auth/forgot-password', {
    method: 'POST',
    body: JSON.stringify({ username, turnstile_token: turnstileToken || '' })
  })
}

export function resetPassword(username, email, code, newPassword) {
  return request('/api/auth/reset-password', {
    method: 'POST',
    body: JSON.stringify({ username, email, code, new_password: newPassword })
  })
}

export function login(username, password, turnstileToken) {
  return request('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password, turnstile_token: turnstileToken || '' })
  })
}

export function getMe() {
  return request('/api/auth/me')
}

// Agents
export function getAgents() {
  return request('/api/agents')
}

export function deployAgent(agent_id, api_key, duration_days, billing_mode, months, hours) {
  return request('/api/deploy', {
    method: 'POST',
    body: JSON.stringify({ agent_id, api_key, duration_days, billing_mode: billing_mode || 'free', months: months || 1, hours: hours || 1 })
  })
}

export function stopLease(lease_id) {
  return request(`/api/stop/${lease_id}`, { method: 'POST' })
}

export function getLeases() {
  return request('/api/leases')
}

// Admin
export function adminOverview() {
  return request('/api/admin/overview')
}
export function adminUsers() {
  return request('/api/admin/users')
}
export function adminLeases() {
  return request('/api/admin/leases')
}
export function adminContainers() {
  return request('/api/admin/containers')
}
export function adminResources() {
  return request('/api/admin/resources')
}


// Settings
export function getPublicSettings() {
  return request('/api/settings')
}
export function adminGetSettings() {
  return request('/api/admin/settings')
}
export function adminUpdateSettings(settings) {
  return request('/api/admin/settings', {
    method: 'PUT',
    body: JSON.stringify({ settings })
  })
}
export function adminGetAgents() {
  return request('/api/admin/agents')
}
export function adminUpdateAgent(agent_id, fields) {
  return request(`/api/admin/agents/${agent_id}`, {
    method: 'PUT',
    body: JSON.stringify(fields)
  })
}


// Admin extended
export function adminCreateAgent(fields) {
  return request('/api/admin/agents', { method: 'POST', body: JSON.stringify(fields) })
}
export function adminDeleteAgent(agent_id) {
  return request(`/api/admin/agents/${agent_id}`, { method: 'DELETE' })
}
export function adminUserManage() {
  return request('/api/admin/user-manage')
}
export function adminUpdateUser(user_id, fields) {
  return request(`/api/admin/user-manage/${user_id}`, { method: 'PUT', body: JSON.stringify(fields) })
}
export function adminResetPassword(user_id, new_password) {
  return request(`/api/admin/user-manage/${user_id}/reset-password`, { method: 'POST', body: JSON.stringify({ new_password }) })
}
export function changeMyPassword(old_password, new_password) {
  return request('/api/admin/change-password', { method: 'POST', body: JSON.stringify({ old_password, new_password }) })
}
export function adminBackup() {
  return request('/api/admin/backup')
}
export function adminLogs() {
  return request('/api/admin/logs')
}


export function uploadLogo(dataUrl) {
  return request('/api/admin/upload-logo', {
    method: 'POST',
    body: JSON.stringify({ data: dataUrl })
  })
}


// Payment & Balance
export function createOrder(agent_id, billing_mode, months, hours) {
  return request('/api/pay/create', {
    method: 'POST',
    body: JSON.stringify({ agent_id, billing_mode, months: months || 1, hours: hours || 1 })
  })
}
export function recharge(amount) {
  return request('/api/pay/recharge', {
    method: 'POST',
    body: JSON.stringify({ amount })
  })
}
export function myOrders() {
  return request('/api/pay/orders')
}
export function myBalance() {
  return request('/api/pay/balance')
}

// Lease admin
export function adminExtendLease(lease_id, extend_days) {
  return request(`/api/admin/leases/${lease_id}`, {
    method: 'PUT',
    body: JSON.stringify({ extend_days })
  })
}
export function adminRecycleLease(lease_id) {
  return request(`/api/admin/leases/${lease_id}`, {
    method: 'PUT',
    body: JSON.stringify({ action: 'recycle' })
  })
}
export function adminLeaseLogs(lease_id, lines) {
  return request(`/api/admin/leases/${lease_id}/logs?lines=${lines || 100}`)
}
