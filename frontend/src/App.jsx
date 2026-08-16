import React, { useState, useEffect } from 'react'
import LoginPage from './components/LoginPage.jsx'
import HomePage from './components/HomePage.jsx'
import AgentList from './components/AgentList.jsx'
import LeaseList from './components/LeaseList.jsx'
import AdminPanel from './components/AdminPanel.jsx'
import BrandLogo from './components/BrandLogo.jsx'
import RechargeDialog from './components/RechargeDialog.jsx'
import { getMe, setToken, getPublicSettings } from './api/client.js'

// ---------- 统一 SSO 登录（对接认证中心 sso.myagentlab.homes） ----------
const SSO_LOGIN_URL = 'https://sso.myagentlab.homes/login'

function redirectToSso() {
  const back = window.location.href.replace(/([?&])sso=1(&|$)/, (m, lead, tail) => (tail === '&' ? lead : ''))
  window.location.href = SSO_LOGIN_URL + '?redirect=' + encodeURIComponent(back)
}

function handleSsoCallback() {
  const params = new URLSearchParams(window.location.search)
  let sso = params.get('sso')
  if (sso === '1') {
    const withoutMark = window.location.pathname + window.location.search.replace(/([?&])sso=1(?=$|&)/, (m, lead) => (lead === '?' ? '' : lead))
    const next = withoutMark + window.location.hash
    history.replaceState(null, '', next)
  }
  if (!localStorage.getItem('myagentlab_token') && sso === '1') {
    fetch('/api/auth/sso-callback', { credentials: 'include' })
      .then((r) => r.json())
      .then((res) => {
        if (res && res.token) {
          setToken(res.token)
          window.location.href = window.location.pathname
        }
      })
      .catch(() => {})
  }
}
handleSsoCallback()

export default function App() {
  const [currentPage, setCurrentPage] = useState('home')
  const [leases, setLeases] = useState([])
  const [user, setUser] = useState(null)
  const [authChecked, setAuthChecked] = useState(false)
  const [brand, setBrand] = useState({ brand_logo: '🧪', brand_name: '' })
  const [showRecharge, setShowRecharge] = useState(false)
  const [showLogin, setShowLogin] = useState(false)
  const [loginHint, setLoginHint] = useState('')

  useEffect(() => {
    getPublicSettings().then(setBrand).catch(() => {})
    const token = localStorage.getItem('myagentlab_token')
    if (token) {
      getMe().then(setUser).catch(() => { setToken(null); setUser(null); }).finally(() => setAuthChecked(true))
    } else {
      setAuthChecked(true)
    }
  }, [])

  useEffect(() => {
    const handler = () => { setUser(null); setCurrentPage('home') }
    window.addEventListener('auth-changed', handler)
    return () => window.removeEventListener('auth-changed', handler)
  }, [])

  const navigate = (page) => {
    setCurrentPage(page)
    window.scrollTo({ top: 0 })
  }

  // 未登录时：只展示产品落地页（主页），点非主页操作一律改为唤起登录弹窗
  const handleNavigate = (page) => {
    if (!user && page !== 'home') {
      setLoginHint(
        page === 'leases' ? '请先登录，登录后可管理你的实例'
        : page === 'admin' ? '请先登录，管理员可进入管理后台'
        : '请先登录，登录后可浏览应用市场并部署 AI Agent'
      )
      setShowLogin(true)
      return
    }
    navigate(page)
  }

  const openLogin = () => { setLoginHint(''); setShowLogin(true) }

  if (!authChecked) {
    return <div className="status-text">加载中…</div>
  }

  return (
    <div>
      <nav>
        <div className="nav-brand" onClick={() => handleNavigate('home')} style={{ cursor: 'pointer' }}>
          <BrandLogo logo={brand.brand_logo} name={brand.brand_name} /> <span className="nav-brand-text">{brand.brand_name}</span>
        </div>
        <div className="nav-links">
          {user ? (
            <>
              <button style={currentPage === 'home' ? { fontWeight: 'bold' } : {}} onClick={() => handleNavigate('home')}>主页</button>
              <button style={currentPage === 'market' ? { fontWeight: 'bold' } : {}} onClick={() => handleNavigate('market')}>应用市场</button>
              <button style={currentPage === 'leases' ? { fontWeight: 'bold' } : {}} onClick={() => handleNavigate('leases')}>我的实例</button>
              {user.is_admin && (
                <button style={currentPage === 'admin' ? { fontWeight: 'bold' } : {}} onClick={() => handleNavigate('admin')}>⚙️ 管理后台</button>
              )}
              <span className="nav-user">
                💰 ¥{user.balance ?? 0}
                <button className="toggle-btn" onClick={() => setShowRecharge(true)}>充值</button>
                👤 {user.username}
                <button className="logout-btn" onClick={() => { setToken(null); setUser(null); setCurrentPage('home'); }}>退出</button>
              </span>
            </>
          ) : (
            <button className="nav-login-btn" onClick={openLogin}>登录</button>
          )}
        </div>
      </nav>

      <main>
        {currentPage === 'home' && <HomePage onNavigate={handleNavigate} />}
        {user && currentPage === 'market' && <AgentList onDeploy={() => {}} onGoRecharge={() => setShowRecharge(true)} />}
        {user && currentPage === 'leases' && <LeaseList leases={leases} setLeases={setLeases} />}
        {user && currentPage === 'admin' && user.is_admin && <AdminPanel onBrandSaved={() => getPublicSettings().then(setBrand)} />}
      </main>

      {showLogin && !user && (
        <LoginPage
          onLoggedIn={(res) => {
            setUser({ username: res.username, is_admin: res.is_admin, balance: res.balance || 0 })
            setShowLogin(false)
          }}
          onClose={() => setShowLogin(false)}
          hint={loginHint}
        />
      )}

      {showRecharge && (
        <RechargeDialog
          onClose={() => setShowRecharge(false)}
          onRecharged={(balance) => {
            setUser((u) => ({ ...u, balance }))
            setShowRecharge(false)
          }}
        />
      )}
    </div>
  )
}
