import { NavLink } from 'react-router-dom'

import { useAuth } from '../auth/auth-context.js'

const NTU_LOGO_SRC = '/logo-dai-hoc-nha-trang.jpg'

const NAV = [
  {
    label: 'Chính',
    items: [
      { to: '/', label: 'Tổng quan' },
      { to: '/students', label: 'Sinh viên', adminOnly: true },
      { to: '/sessions', label: 'Buổi học', adminOnly: true },
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
    ],
  },
]

export default function Sidebar() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <img className="brand-logo" src={NTU_LOGO_SRC} alt="Logo Đại học Nha Trang" />
        <div className="logo-text">
          <strong>Hệ thống điểm danh</strong>
          <span>Project chuyên đề</span>
        </div>
      </div>

      {NAV.map((section) => {
        const items = section.items.filter((item) => !item.adminOnly || isAdmin)
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
            <div className="status-txt">Hệ thống online</div>
            <div className="status-sub">Face Attendance NTU</div>
          </div>
        </div>
      </div>
    </aside>
  )
}
