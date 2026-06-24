import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'

import './App.css'
import { AuthProvider } from './auth/AuthContext.jsx'
import { ThemeProvider } from './context/ThemeContext.jsx'
import ThemeToggle from './components/ThemeToggle.jsx'
import { useAuth } from './auth/auth-context.js'
import Sidebar from './components/Navbar'
import BottomNavigation from './components/BottomNavigation'
import Attendance from './pages/Attendance'
import Dashboard from './pages/Dashboard'
import Login from './pages/Login'
import Students from './pages/Students'
import { getDisplayLabel, roleLabels } from './utils/displayLabels.js'

const FaceRegister = lazy(() => import('./pages/FaceRegister'))
const Reports = lazy(() => import('./pages/Reports'))
const Sessions = lazy(() => import('./pages/Sessions'))
const CourseManagement = lazy(() => import('./pages/CourseManagement'))
const Users = lazy(() => import('./pages/Users'))
const AuditLogs = lazy(() => import('./pages/AuditLogs'))

const BREADCRUMBS = {
  '/': ['Tổng quan', 'Bảng điều khiển'],
  '/students': ['Quản lý', 'Sinh viên'],
  '/sessions': ['Quản lý', 'Buổi học'],
  '/course-management': ['Quản lý', 'Học phần'],
  '/faces/register': ['Nhận diện AI', 'Đăng ký khuôn mặt'],
  '/attendance': ['Nhận diện AI', 'Điểm danh'],
  '/reports': ['Phân tích', 'Báo cáo'],
  '/users': ['Quản lý', 'Tài khoản'],
  '/audit-logs': ['Hệ thống', 'Lịch sử hoạt động'],
}

function Topbar() {
  const { pathname } = useLocation()
  const { user, logout } = useAuth()
  const [parent, current] = BREADCRUMBS[pathname] ?? ['', pathname]

  return (
    <div className="topbar">
      <div className="topbar-breadcrumb">
        <span>{parent}</span>
        <span style={{ color:'var(--bdr2)' }}>{'>'}</span>
        <b>{current}</b>
      </div>
      <div className="topbar-right">
        <div className="topbar-pill">
          <span className="topbar-user-name">{user?.username || 'Người dùng'}</span>
          <span className="topbar-user-role">{getDisplayLabel(roleLabels, user?.role, 'Người dùng')}</span>
        </div>
        <ThemeToggle style={{ marginRight: 4 }} />
        <button className="secondary logout-button" onClick={logout} title="Đăng xuất" aria-label="Đăng xuất">
          <svg className="logout-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <polyline points="16 17 21 12 16 7" />
            <line x1="21" y1="12" x2="9" y2="12" />
          </svg>
          <span className="logout-text">Đăng xuất</span>
        </button>
      </div>
    </div>
  )
}

function ProtectedShell() {
  const { checking, isAuthenticated, user } = useAuth()
  const isLecturerOrAdmin = user?.role === 'admin' || user?.role === 'teacher' || user?.role === 'lecturer'

  if (checking) {
    return (
      <div style={{ minHeight:'100vh', display:'grid', placeItems:'center' }}>
        <p className="status-message">Đang kiểm tra phiên đăng nhập...</p>
      </div>
    )
  }

  if (!isAuthenticated) return <Navigate to="/login" replace />

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="app-main">
        <Topbar />
        <div className="page-content">
          <Suspense fallback={<p className="status-message">Đang tải trang...</p>}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/students" element={user?.role === 'admin' ? <Students /> : <Navigate to="/" replace />} />
              <Route path="/sessions" element={isLecturerOrAdmin ? <Sessions /> : <Navigate to="/" replace />} />
              <Route path="/course-management" element={isLecturerOrAdmin ? <CourseManagement /> : <Navigate to="/" replace />} />
              <Route path="/faces/register" element={user?.role === 'admin' ? <FaceRegister /> : <Navigate to="/" replace />} />
              <Route path="/attendance" element={<Attendance />} />
              <Route path="/reports" element={<Reports />} />
              <Route path="/users" element={user?.role === 'admin' ? <Users /> : <Navigate to="/" replace />} />
              <Route path="/audit-logs" element={user?.role === 'admin' ? <AuditLogs /> : <Navigate to="/" replace />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </div>
      </main>
      <BottomNavigation />
    </div>
  )
}

function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/*" element={<ProtectedShell />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  )
}

export default App
