import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'

import './App.css'
import { AuthProvider } from './auth/AuthContext.jsx'
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

const BREADCRUMBS = {
  '/': ['Tổng quan', 'Bảng điều khiển'],
  '/students': ['Quản lý', 'Sinh viên'],
  '/sessions': ['Quản lý', 'Buổi học'],
  '/course-management': ['Quản lý', 'Học phần'],
  '/faces/register': ['Nhận diện AI', 'Đăng ký khuôn mặt'],
  '/attendance': ['Nhận diện AI', 'Điểm danh'],
  '/reports': ['Phân tích', 'Báo cáo'],
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
          {user?.username || 'Người dùng'} · {getDisplayLabel(roleLabels, user?.role, 'Người dùng')}
        </div>
        <button className="secondary" onClick={logout} style={{ minHeight:34, padding:'6px 12px' }}>
          Đăng xuất
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
              <Route path="/sessions" element={user?.role === 'admin' ? <Sessions /> : <Navigate to="/" replace />} />
              <Route path="/course-management" element={isLecturerOrAdmin ? <CourseManagement /> : <Navigate to="/" replace />} />
              <Route path="/faces/register" element={user?.role === 'admin' ? <FaceRegister /> : <Navigate to="/" replace />} />
              <Route path="/attendance" element={<Attendance />} />
              <Route path="/reports" element={<Reports />} />
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
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/*" element={<ProtectedShell />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
