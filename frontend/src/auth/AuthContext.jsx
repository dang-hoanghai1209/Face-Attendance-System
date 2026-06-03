import { useCallback, useEffect, useMemo, useState } from 'react'

import api from '../../api/axios.js'
import { AuthContext } from './auth-context.js'

const readStoredUser = () => {
  try {
    return JSON.parse(localStorage.getItem('auth_user') || 'null')
  } catch {
    return null
  }
}

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('auth_token') || '')
  const [user, setUser] = useState(readStoredUser)
  const [checking, setChecking] = useState(Boolean(token))

  const clearAuth = useCallback(() => {
    localStorage.removeItem('auth_token')
    localStorage.removeItem('auth_user')
    setToken('')
    setUser(null)
    setChecking(false)
  }, [])

  const login = useCallback(async (username, password) => {
    const res = await api.post('/auth/login', { username, password })
    localStorage.setItem('auth_token', res.data.access_token)
    localStorage.setItem('auth_user', JSON.stringify(res.data.user))
    setToken(res.data.access_token)
    setUser(res.data.user)
    return res.data.user
  }, [])

  const logout = useCallback(() => {
    clearAuth()
  }, [clearAuth])

  useEffect(() => {
    window.addEventListener('auth:logout', clearAuth)
    return () => window.removeEventListener('auth:logout', clearAuth)
  }, [clearAuth])

  useEffect(() => {
    if (!token) {
      return
    }

    let mounted = true
    api.get('/auth/me')
      .then((res) => {
        if (!mounted) return
        localStorage.setItem('auth_user', JSON.stringify(res.data))
        setUser(res.data)
      })
      .catch(() => {
        if (mounted) clearAuth()
      })
      .finally(() => {
        if (mounted) setChecking(false)
      })

    return () => {
      mounted = false
    }
  }, [clearAuth, token])

  const value = useMemo(() => ({
    token,
    user,
    checking,
    isAuthenticated: Boolean(token && user),
    login,
    logout,
  }), [checking, login, logout, token, user])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
