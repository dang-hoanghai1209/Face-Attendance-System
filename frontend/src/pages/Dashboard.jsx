import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'

import api from '../../api/axios.js'
import { useAuth } from '../auth/auth-context.js'
import { VALID_CLASSES } from '../constants/classes.js'
import { getApiErrorMessage } from '../utils/apiError.js'

const fallbackStats = {
  total_students: 0, registered_faces: 0, unregistered_faces: 0,
  total_sessions: 0, avg_attendance_rate: 0, warning_count: 0, pie_data: [],
}
const pieLabels = { Present: 'Có mặt', Absent: 'Vắng' }
const quickActions = [
  { to: '/students',       icon: '👤', label: 'Sinh viên',            desc: 'Thêm và quản lý danh sách sinh viên theo lớp.' },
  { to: '/sessions',       icon: '📅', label: 'Buổi học',             desc: 'Tạo lịch học theo môn, lớp và khung giờ.' },
  { to: '/faces/register', icon: '📸', label: 'Đăng ký khuôn mặt',   desc: 'Chụp mẫu bằng camera và lưu đặc trưng khuôn mặt.' },
  { to: '/attendance',     icon: '✅', label: 'Điểm danh',            desc: 'Nhận diện để ghi nhận vào lớp, ra về hoặc điểm danh thủ công.' },
  { to: '/reports',        icon: '📊', label: 'Báo cáo',              desc: 'Xem cảnh báo chuyên cần và xuất báo cáo Excel hoặc PDF.' },
]
const fmt = (v) => `${Math.round((v || 0) * 100)}%`

export default function Dashboard() {
  const [stats,   setStats]   = useState(fallbackStats)
  const [error,   setError]   = useState('')
  const [loading, setLoading] = useState(false)
  const [deferredPrompt, setDeferredPrompt] = useState(null)
  const [showInstallBanner, setShowInstallBanner] = useState(false)

  const load = useCallback(async (isMounted = () => true) => {
    setLoading(true)
    try {
      const res = await api.get('/reports/dashboard/stats')
      if (!isMounted()) return
      setStats(res.data); setError('')
    } catch (e) {
      if (!isMounted()) return
      setError(getApiErrorMessage(e, 'Không tải được dữ liệu tổng quan.'))
    } finally {
      if (isMounted()) setLoading(false)
    }
  }, [])

  useEffect(() => {
    let mounted = true
    queueMicrotask(() => {
      if (mounted) load(() => mounted)
    })
    return () => {
      mounted = false
    }
  }, [load])

  useEffect(() => {
    const isStandalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone
    if (isStandalone) return

    const handleBeforeInstallPrompt = (e) => {
      e.preventDefault()
      setDeferredPrompt(e)
      setShowInstallBanner(true)
    }

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
    }
  }, [])

  const handleInstallClick = async () => {
    if (!deferredPrompt) return
    deferredPrompt.prompt()
    const { outcome } = await deferredPrompt.userChoice
    if (outcome === 'accepted') {
      console.log('User accepted NTU Face Attendance PWA installation')
    }
    setDeferredPrompt(null)
    setShowInstallBanner(false)
  }

  const { user } = useAuth()
  const isStudent = user?.role === 'student'

  const chartData = stats.pie_data.map(i => ({ ...i, name: pieLabels[i.name]||i.name }))
  const hasData   = chartData.some(i => i.value > 0)
  const regRate   = stats.total_students ? Math.round(stats.registered_faces/stats.total_students*100) : 0

  const adminCards = [
    { label:'Tổng sinh viên',           value: stats.total_students,              delta: `${VALID_CLASSES.length} lớp chính thức` },
    { label:'Đã đăng ký khuôn mặt',     value: stats.registered_faces,            delta: `${regRate}% hoàn thành` },
    { label:'Chưa đăng ký',             value: stats.unregistered_faces,           delta: 'Cần xử lý' },
    { label:'Tổng buổi học',            value: stats.total_sessions,              delta: '10 buổi/lớp' },
    { label:'Chuyên cần trung bình',    value: fmt(stats.avg_attendance_rate),    delta: 'Ngưỡng tối thiểu 80%' },
    { label:'Sinh viên cảnh báo',       value: `${stats.warning_count} SV`,       delta: 'Dưới 80% chuyên cần' },
  ]

  const studentCards = [
    { label:'Trạng thái khuôn mặt',     value: stats.registered_faces ? 'Đã đăng ký' : 'Chưa đăng ký', delta: stats.registered_faces ? 'Sẵn sàng điểm danh' : 'Cần liên hệ Admin/Giảng viên' },
    { label:'Tổng buổi học của bạn',    value: stats.total_sessions,              delta: 'Theo thời khóa biểu lớp học phần' },
    { label:'Tỷ lệ chuyên cần cá nhân', value: fmt(stats.avg_attendance_rate),    delta: 'Yêu cầu tối thiểu 80%' },
  ]
  const CARDS = isStudent ? studentCards : adminCards

  const getFilteredQuickActions = () => {
    const isTeacherOrAdmin = user?.role === 'admin' || user?.role === 'teacher'
    const isAdmin = user?.role === 'admin'

    const actions = []
    if (isAdmin) {
      actions.push({ to: '/students', icon: '👤', label: 'Sinh viên', desc: 'Thêm và quản lý danh sách sinh viên theo lớp.' })
      actions.push({ to: '/sessions', icon: '📅', label: 'Buổi học', desc: 'Tạo lịch học theo môn, lớp và khung giờ.' })
      actions.push({ to: '/faces/register', icon: '📸', label: 'Đăng ký khuôn mặt', desc: 'Chụp mẫu bằng camera và lưu đặc trưng khuôn mặt.' })
    }
    if (isTeacherOrAdmin) {
      actions.push({ to: '/course-management', icon: '👥', label: 'Quản lý học phần', desc: 'Quản lý môn học, phòng học, lớp học phần và xếp lịch.' })
    }
    actions.push({ to: '/attendance', icon: '✅', label: 'Điểm danh', desc: 'Nhận diện để ghi nhận vào lớp hoặc ra về.' })
    actions.push({ to: '/reports', icon: '📊', label: 'Báo cáo', desc: isStudent ? 'Xem lịch sử chuyên cần cá nhân.' : 'Xem cảnh báo chuyên cần và xuất báo cáo Excel hoặc PDF.' })
    return actions
  }

  const adminAlerts = [
    { type:'danger', icon:'🚨', title:`${stats.warning_count} SV dưới ngưỡng chuyên cần`, sub:'Xem báo cáo cảnh báo để liên hệ sinh viên.' },
    { type:'warning', icon:'⚠️', title:`${stats.unregistered_faces} SV chưa đăng ký khuôn mặt`, sub:'Không thể điểm danh tự động — cần đăng ký trước.' },
    { type:'info', icon:'💡', title:'Quy trình minh họa', sub:'Sinh viên → Buổi học → Khuôn mặt → Điểm danh → Báo cáo.' },
  ]

  const studentAlerts = []
  if (stats.warning_count > 0) {
    studentAlerts.push({ type: 'danger', icon: '🚨', title: 'Bạn đang dưới ngưỡng chuyên cần (80%)', sub: 'Vui lòng tham gia các buổi học đầy đủ để tránh ảnh hưởng kết quả.' })
  }
  if (!stats.registered_faces) {
    studentAlerts.push({ type: 'warning', icon: '⚠️', title: 'Chưa đăng ký khuôn mặt', sub: 'Tài khoản chưa có dữ liệu khuôn mặt. Hãy liên hệ Giảng viên/Admin để đăng ký mẫu.' })
  }
  studentAlerts.push({ type: 'info', icon: '💡', title: 'Hướng dẫn điểm danh', sub: 'Bật GPS -> Chọn buổi học -> Nhìn thẳng camera -> Ghi nhận điểm danh.' })

  const ALERTS = isStudent ? studentAlerts : adminAlerts
  const filteredQuickActions = getFilteredQuickActions()

  return (
    <div>
      <div className="page-header">
        <div>
          <p className="eyebrow">Hệ thống điểm danh khuôn mặt</p>
          <h1 className="page-title">Tổng quan hệ thống</h1>
          <p className="page-subtitle">Học kỳ 2 · 2024–2025 · MTCNN + FaceNet + độ tương đồng cosine</p>
        </div>
        <button className="secondary" onClick={() => load()} disabled={loading}>
          {loading ? 'Đang tải...' : '🔄 Tải lại'}
        </button>
      </div>

      {showInstallBanner && (
        <div className="panel panel-pad" style={{
          background: 'rgba(0, 201, 167, 0.08)',
          borderColor: 'rgba(0, 201, 167, 0.3)',
          marginBottom: 16,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 16,
          flexWrap: 'wrap',
          animation: 'fadeUp 0.35s ease both'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 24 }}>📱</span>
            <div>
              <strong style={{ fontSize: 13, color: 'var(--white)', display: 'block', marginBottom: 2 }}>Cài đặt ứng dụng di động</strong>
              <p style={{ margin: 0, fontSize: 11, color: 'var(--white2)' }}>Cài đặt NTU Face Attendance vào màn hình chính để sử dụng mượt mà, tiện lợi hơn trên điện thoại.</p>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="secondary" onClick={() => setShowInstallBanner(false)} style={{ minHeight: 36, padding: '6px 12px', fontSize: 12 }}>Bỏ qua</button>
            <button onClick={handleInstallClick} style={{ minHeight: 36, padding: '6px 12px', fontSize: 12 }}>Cài đặt ngay</button>
          </div>
        </div>
      )}

      {error && <p className="status-message error">⚠️ {error}</p>}

      {/* Stat cards */}
      <div className="grid cards" style={{ marginBottom: 18 }}>
        {CARDS.map(c => (
          <div key={c.label} className="stat-card">
            <p>{c.label}</p>
            <strong>{c.value}</strong>
            <span style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4, display: 'block', fontFamily: 'var(--mono)' }}>{c.delta}</span>
          </div>
        ))}
      </div>

      {/* Charts + alerts */}
      <div className="grid two" style={{ marginBottom: 18 }}>
        <div className="panel panel-pad">
          <h3 style={{ marginTop:0, marginBottom:14, fontSize:14 }}>
            {isStudent ? 'Tỷ lệ chuyên cần của bạn' : 'Tỷ lệ chuyên cần toàn hệ thống'}
          </h3>
          {!hasData
            ? <div className="empty-state">{isStudent ? 'Chưa có dữ liệu điểm danh cá nhân.' : 'Chưa có dữ liệu điểm danh. Hãy tạo buổi học và ghi nhận vào lớp để biểu đồ có số liệu.'}</div>
            : <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie data={chartData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={95} label={({name,percent})=>`${name} ${(percent*100).toFixed(0)}%`}>
                    {chartData.map(i=>(
                      <Cell key={i.name} fill={i.name==='Có mặt'?'#00c9a7':'#f43f5e'}/>
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ background:'var(--navy2)', border:'1px solid var(--bdr2)', borderRadius:8, color:'var(--white)', fontSize:12 }}/>
                  <Legend wrapperStyle={{ fontSize:12, color:'var(--white2)' }}/>
                </PieChart>
              </ResponsiveContainer>
          }
        </div>

        <div style={{ display:'flex', flexDirection:'column', gap:10 }}>
          {/* Alert cards */}
          {ALERTS.map(a=>(
            <div key={a.title} className="panel panel-pad" style={{
              background: a.type==='danger' ? 'rgba(244,63,94,.06)' : a.type==='warning' ? 'rgba(245,158,11,.06)' : 'rgba(59,130,246,.06)',
              borderColor: a.type==='danger' ? 'rgba(244,63,94,.2)' : a.type==='warning' ? 'rgba(245,158,11,.2)' : 'rgba(59,130,246,.2)',
            }}>
              <div style={{ display:'flex', gap:10 }}>
                <span style={{ fontSize:16 }}>{a.icon}</span>
                <div>
                  <strong style={{ fontSize:13, display:'block', marginBottom:3 }}>{a.title}</strong>
                  <p style={{ margin:0, fontSize:12, color:'var(--muted)' }}>{a.sub}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Quick actions */}
      <h3 style={{ marginBottom:12, fontSize:14, color:'var(--muted)', textTransform:'uppercase', letterSpacing:'.07em' }}>Thao tác nhanh</h3>
      <div className="grid cards">
        {filteredQuickActions.map((a,i)=>(
          <Link key={a.to} to={a.to} style={{ textDecoration:'none' }}>
            <div className="panel panel-pad" style={{ cursor:'pointer', transition:'all .2s', position:'relative', overflow:'hidden' }}
              onMouseEnter={e=>{e.currentTarget.style.background='var(--card2)';e.currentTarget.style.transform='translateY(-2px)'}}
              onMouseLeave={e=>{e.currentTarget.style.background='var(--card)';e.currentTarget.style.transform='none'}}
            >
              <div style={{ position:'absolute', right:12, top:8, fontSize:32, fontWeight:900, color:'rgba(255,255,255,.04)', fontFamily:'var(--mono)', lineHeight:1 }}>0{i+1}</div>
              <div style={{ fontSize:22, marginBottom:10 }}>{a.icon}</div>
              <strong style={{ fontSize:13, display:'block', marginBottom:4 }}>{a.label}</strong>
              <p style={{ margin:0, fontSize:11, color:'var(--muted)', lineHeight:1.5 }}>{a.desc}</p>
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}
