import React, { useState, useEffect } from 'react'
import LoginPage from './components/LoginPage.jsx'
import HomePage from './components/HomePage.jsx'
import AgentList from './components/AgentList.jsx'
import LeaseList from './components/LeaseList.jsx'
import AdminPanel from './components/AdminPanel.jsx'
import BrandLogo from './components/BrandLogo.jsx'
import { getMe, setToken, getPublicSettings } from './api/client.js'

export default function App() {
  const [currentPage, setCurrentPage] = useState('home')
  const [leases, setLeases] = useState([])
  const [user, setUser] = useState(null)
  const [authChecked, setAuthChecked] = useState(false)
  const [brand, setBrand] = useState({ brand_logo: '🧪', brand_name: '智体工坊' })

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
    const handler = () => setUser(null)
    window.addEventListener('auth-changed', handler)
    return () => window.removeEventListener('auth-changed', handler)
  }, [])

  const navigate = (page) => {
    setCurrentPage(page)
    window.scrollTo({ top: 0 })
  }

  if (!authChecked) {
    return <div className="status-text">加载中…</div>
  }

  if (!user) {
    return <LoginPage onLoggedIn={(res) => setUser({ username: res.username, is_admin: res.is_admin })} />
  }

  return (
    <div>
      <nav>
        <div className="nav-brand" onClick={() => navigate('home')} style={{ cursor: 'pointer' }}>
          <BrandLogo logo={brand.brand_logo} name={brand.brand_name} /> <span className="nav-brand-text">{brand.brand_name}</span>
        </div>
        <div className="nav-links">
          <button style={currentPage === 'home' ? { fontWeight: 'bold' } : {}} onClick={() => navigate('home')}>主页</button>
          <button style={currentPage === 'market' ? { fontWeight: 'bold' } : {}} onClick={() => navigate('market')}>应用市场</button>
          <button style={currentPage === 'leases' ? { fontWeight: 'bold' } : {}} onClick={() => navigate('leases')}>我的实例</button>
          {user.is_admin && (
            <>
              <button style={currentPage === 'admin' ? { fontWeight: 'bold' } : {}} onClick={() => navigate('admin')}>⚙️ 管理后台</button>
            </>
          )}
          <span className="nav-user">
            👤 {user.username}
            <button className="logout-btn" onClick={() => { setToken(null); setUser(null); }}>退出</button>
          </span>
        </div>
      </nav>

      <main>
        {currentPage === 'home' && <HomePage onNavigate={navigate} />}
        {currentPage === 'market' && <AgentList onDeploy={() => {}} />}
        {currentPage === 'leases' && <LeaseList leases={leases} setLeases={setLeases} />}
        {currentPage === 'admin' && user.is_admin && <AdminPanel onBrandSaved={() => getPublicSettings().then(setBrand)} />}
      </main>
    </div>
  )
}
