import { useState } from 'react'
import { Navigate } from 'react-router-dom'

import { useAuth } from '../auth/auth-context.js'

export default function Login() {
  const { isAuthenticated, login } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  if (isAuthenticated) return <Navigate to="/" replace />

  const handleSubmit = async (event) => {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(username.trim(), password)
    } catch (err) {
      setError(err.response?.data?.detail || 'Không đăng nhập được.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ minHeight:'100vh', display:'grid', placeItems:'center', padding:20 }}>
      <form
        onSubmit={handleSubmit}
        style={{
          width:'min(420px, 100%)',
          background:'#ffffff',
          border:'1px solid #e5e7eb',
          borderRadius:12,
          padding:24,
          boxShadow:'0 24px 80px rgba(0,0,0,.35)',
          color:'#111827'
        }}
      >
        <div style={{ marginBottom:18 }}>
          <p style={{ margin:0, color:'#0f766e', fontSize:12, fontWeight:800, textTransform:'uppercase', letterSpacing:'.08em' }}>Face Attendance</p>
          <h1 style={{ margin:'6px 0 4px', fontSize:24, lineHeight:1.2 }}>Đăng nhập hệ thống</h1>
          <p style={{ margin:0, color:'#6b7280', fontSize:13 }}>Cần tài khoản để xem hoặc sửa dữ liệu điểm danh.</p>
        </div>

        <label style={{ display:'block', fontSize:12, fontWeight:700, marginBottom:6 }}>Tên đăng nhập</label>
        <input
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          autoComplete="username"
          style={{ width:'100%', marginBottom:12, background:'#f9fafb', color:'#111827', borderColor:'#d1d5db' }}
          required
        />

        <label style={{ display:'block', fontSize:12, fontWeight:700, marginBottom:6 }}>Mật khẩu</label>
        <input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="current-password"
          style={{ width:'100%', marginBottom:14, background:'#f9fafb', color:'#111827', borderColor:'#d1d5db' }}
          required
        />

        {error && (
          <p style={{ padding:'9px 11px', borderRadius:8, background:'#fef2f2', color:'#b91c1c', border:'1px solid #fecaca', fontSize:13, margin:'0 0 14px' }}>
            {error}
          </p>
        )}

        <button type="submit" disabled={loading} style={{ width:'100%', justifyContent:'center' }}>
          {loading ? 'Đang đăng nhập...' : 'Đăng nhập'}
        </button>
      </form>
    </div>
  )
}
