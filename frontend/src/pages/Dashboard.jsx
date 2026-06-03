import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'

import api from '../../api/axios.js'
import { VALID_CLASSES } from '../constants/classes.js'

const fallbackStats = {
  total_students: 0, registered_faces: 0, unregistered_faces: 0,
  total_sessions: 0, avg_attendance_rate: 0, warning_count: 0, pie_data: [],
}
const pieLabels = { Present: 'Có mặt', Absent: 'Vắng' }
const quickActions = [
  { to: '/students',       icon: '👤', label: 'Sinh viên',            desc: 'Thêm và quản lý danh sách sinh viên theo lớp.' },
  { to: '/sessions',       icon: '📅', label: 'Buổi học',             desc: 'Tạo lịch học theo môn, lớp và khung giờ.' },
  { to: '/faces/register', icon: '📸', label: 'Đăng ký khuôn mặt',   desc: 'Chụp mẫu camera và lưu mean embedding 512D.' },
  { to: '/attendance',     icon: '✅', label: 'Điểm danh',            desc: 'Nhận diện check-in / check-out hoặc thủ công.' },
  { to: '/reports',        icon: '📊', label: 'Báo cáo',              desc: 'Xem cảnh báo chuyên cần, xuất Excel / PDF.' },
]
const fmt = (v) => `${Math.round((v || 0) * 100)}%`

export default function Dashboard() {
  const [stats,   setStats]   = useState(fallbackStats)
  const [error,   setError]   = useState('')
  const [loading, setLoading] = useState(false)

  const load = useCallback(async (isMounted = () => true) => {
    setLoading(true)
    try {
      const res = await api.get('/reports/dashboard/stats')
      if (!isMounted()) return
      setStats(res.data); setError('')
    } catch (e) {
      if (!isMounted()) return
      setError(e.response?.data?.detail || e.message)
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

  const chartData = stats.pie_data.map(i => ({ ...i, name: pieLabels[i.name]||i.name }))
  const hasData   = chartData.some(i => i.value > 0)
  const regRate   = stats.total_students ? Math.round(stats.registered_faces/stats.total_students*100) : 0

  const CARDS = [
    { label:'Tổng sinh viên',           value: stats.total_students,              delta: `${VALID_CLASSES.length} lớp chính thức` },
    { label:'Đã đăng ký khuôn mặt',     value: stats.registered_faces,            delta: `${regRate}% hoàn thành` },
    { label:'Chưa đăng ký',             value: stats.unregistered_faces,           delta: 'Cần xử lý' },
    { label:'Tổng buổi học',            value: stats.total_sessions,              delta: '10 buổi/lớp' },
    { label:'Chuyên cần trung bình',    value: fmt(stats.avg_attendance_rate),    delta: 'Ngưỡng tối thiểu 80%' },
    { label:'Sinh viên cảnh báo',       value: `${stats.warning_count} SV`,       delta: 'Dưới 80% chuyên cần' },
  ]

  return (
    <div>
      <div className="page-header">
        <div>
          <p className="eyebrow">Hệ thống điểm danh khuôn mặt</p>
          <h1 className="page-title">Tổng quan hệ thống</h1>
          <p className="page-subtitle">Học kỳ 2 · 2024–2025 · MTCNN + FaceNet + Cosine Similarity</p>
        </div>
        <button className="secondary" onClick={() => load()} disabled={loading}>
          {loading ? 'Đang tải...' : '🔄 Tải lại'}
        </button>
      </div>

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
          <h3 style={{ marginTop:0, marginBottom:14, fontSize:14 }}>Tỷ lệ chuyên cần toàn hệ thống</h3>
          {!hasData
            ? <div className="empty-state">Chưa có dữ liệu điểm danh. Tạo buổi học và ghi nhận check-in để biểu đồ có số liệu.</div>
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
          {[
            { type:'danger', icon:'🚨', title:`${stats.warning_count} SV dưới ngưỡng chuyên cần`, sub:'Xem báo cáo cảnh báo để liên hệ sinh viên.' },
            { type:'warning', icon:'⚠️', title:`${stats.unregistered_faces} SV chưa đăng ký khuôn mặt`, sub:'Không thể điểm danh tự động — cần đăng ký trước.' },
            { type:'info', icon:'💡', title:'Luồng demo gợi ý', sub:'Sinh viên → Buổi học → Khuôn mặt → Điểm danh → Báo cáo.' },
          ].map(a=>(
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
        {quickActions.map((a,i)=>(
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
