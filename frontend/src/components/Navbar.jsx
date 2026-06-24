import { NavLink } from 'react-router-dom'

import { useAuth } from '../auth/auth-context.js'

const NTU_LOGO_SRC = '/logo-dai-hoc-nha-trang.jpg'

const NAV = [
  {
    label: 'Chính',
    items: [
      { to: '/', label: 'Tổng quan' },
      { to: '/students', label: 'Sinh viên', adminOnly: true },
      { to: '/sessions', label: 'Buổi học', lecturerOrAdminOnly: true },
      { to: '/course-management', label: 'Quản lý học phần', lecturerOrAdminOnly: true },
      { to: '/users', label: 'Quản lý tài khoản', adminOnly: true },
    ],
  },
  {
    label: 'Nhận diện',
    items: [
      { to: '/faces/register', label: 'Đăng ký khuôn mặt', adminOnly: true },
      { to: '/attendance', label: 'Điểm danh' },
    ],
  },
  {
    label: 'Phân tích',
    items: [
      { to: '/reports', label: 'Báo cáo' },
      { to: '/audit-logs', label: 'Lịch sử hoạt động', adminOnly: true },
    ],
  },
]

export default function Sidebar() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'
  const isLecturerOrAdmin = user?.role === 'admin' || user?.role === 'teacher' || user?.role === 'lecturer'

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <img className="brand-logo" src={NTU_LOGO_SRC} alt="Logo Đại học Nha Trang" />
        <div className="logo-text">
          <strong>Hệ thống điểm danh</strong>
          <span>Đề tài chuyên đề</span>
        </div>
      </div>

      {NAV.map((section) => {
        const items = section.items.filter((item) => {
          if (item.adminOnly && !isAdmin) return false
          if (item.lecturerOrAdminOnly && !isLecturerOrAdmin) return false
          return true
        })
        if (!items.length) return null

        return (
          <div className="nav-section" key={section.label}>
            <div className="nav-section-label">{section.label}</div>
            {items.map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                className={({ isActive }) => 'nav-link' + (isActive ? ' active' : '')}
              >
                {label}
              </NavLink>
            ))}
          </div>
        )
      })}

      <div className="sidebar-footer">
        <div className="sys-status">
          <div className="status-dot" />
          <div>
            <div className="status-txt">Hệ thống đang hoạt động</div>
            <div className="status-sub">Điểm danh khuôn mặt NTU</div>
          </div>
        </div>
      </div>
    </aside>
  )
}
