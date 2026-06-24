import { NavLink } from 'react-router-dom'
import { useAuth } from '../auth/auth-context.js'

export default function BottomNavigation() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'
  const isLecturerOrAdmin = user?.role === 'admin' || user?.role === 'teacher' || user?.role === 'lecturer'

  return (
    <nav className="bottom-nav">
      <NavLink
        to="/"
        end
        className={({ isActive }) => 'bottom-nav-item' + (isActive ? ' active' : '')}
      >
        <span className="bottom-nav-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="3" width="7" height="9" />
            <rect x="14" y="3" width="7" height="5" />
            <rect x="14" y="12" width="7" height="9" />
            <rect x="3" y="16" width="7" height="5" />
          </svg>
        </span>
        <span>Tổng</span>
      </NavLink>

      {isAdmin && (
        <NavLink
          to="/students"
          className={({ isActive }) => 'bottom-nav-item' + (isActive ? ' active' : '')}
        >
          <span className="bottom-nav-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
              <circle cx="9" cy="7" r="4" />
              <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
              <path d="M16 3.13a4 4 0 0 1 0 7.75" />
            </svg>
          </span>
          <span>Sinh viên</span>
        </NavLink>
      )}

      {isLecturerOrAdmin && (
        <NavLink
          to="/sessions"
          className={({ isActive }) => 'bottom-nav-item' + (isActive ? ' active' : '')}
        >
          <span className="bottom-nav-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
              <line x1="16" y1="2" x2="16" y2="6" />
              <line x1="8" y1="2" x2="8" y2="6" />
              <line x1="3" y1="10" x2="21" y2="10" />
            </svg>
          </span>
          <span>Buổi</span>
        </NavLink>
      )}

      <NavLink
        to="/attendance"
        className={({ isActive }) => 'bottom-nav-item' + (isActive ? ' active' : '')}
      >
        <span className="bottom-nav-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
            <circle cx="12" cy="13" r="4" />
          </svg>
        </span>
        <span>Điểm danh</span>
      </NavLink>

      {isLecturerOrAdmin && (
        <NavLink
          to="/course-management"
          className={({ isActive }) => 'bottom-nav-item' + (isActive ? ' active' : '')}
        >
          <span className="bottom-nav-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
              <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
            </svg>
          </span>
          <span>HP</span>
        </NavLink>
      )}

      <NavLink
        to="/reports"
        className={({ isActive }) => 'bottom-nav-item' + (isActive ? ' active' : '')}
      >
        <span className="bottom-nav-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="20" x2="18" y2="10" />
            <line x1="12" y1="20" x2="12" y2="4" />
            <line x1="6" y1="20" x2="6" y2="14" />
          </svg>
        </span>
        <span>Báo cáo</span>
      </NavLink>
    </nav>
  )
}
