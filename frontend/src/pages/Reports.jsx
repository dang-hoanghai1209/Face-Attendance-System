import { useEffect, useMemo, useState } from 'react'

import api from '../../api/axios.js'
import { useAuth } from '../auth/auth-context.js'
import AttendanceChart from '../components/AttendanceChart.jsx'
import WarningTable from '../components/WarningTable.jsx'
import { VALID_CLASSES } from '../constants/classes.js'

// ------------------------------------------------------------------ //
// Hằng số — đồng bộ với Students.jsx và Sessions.jsx
// ------------------------------------------------------------------ //
const statusLabels = {
  present: 'Có mặt',
  late:    'Đi trễ',
  manual:  'Thủ công',
  absent:  'Vắng',
}

// ------------------------------------------------------------------ //
// Helpers
// ------------------------------------------------------------------ //
const getFilename = (headers, fallback) => {
  const disposition = headers?.['content-disposition']
  const match = disposition?.match(/filename="?([^"]+)"?/i)
  return match?.[1] || fallback
}

const downloadBlob = (blob, filename) => {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

/** "2025-05-15T08:32:11" → "15/05 08:32" */
const formatDT = (iso) => {
  if (!iso) return '-'
  const d = new Date(iso)
  if (isNaN(d)) return iso
  const dd   = String(d.getDate()).padStart(2, '0')
  const mm   = String(d.getMonth() + 1).padStart(2, '0')
  const hh   = String(d.getHours()).padStart(2, '0')
  const min  = String(d.getMinutes()).padStart(2, '0')
  return `${dd}/${mm} ${hh}:${min}`
}

/** 0.8734 → "87.3%" */
const formatConf = (v) =>
  typeof v === 'number' ? `${(v * 100).toFixed(1)}%` : '-'

const formatRate = (v) =>
  typeof v === 'number' ? `${(v * 100).toFixed(1)}%` : '-'

// ------------------------------------------------------------------ //
// Component
// ------------------------------------------------------------------ //
export default function Reports() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'
  const [data,              setData]              = useState([])
  const [className,         setClassName]         = useState('')        // mặc định trống, user chọn
  const [warnings,          setWarnings]          = useState([])
  const [sessions,          setSessions]          = useState([])
  const [selectedSessionId, setSelectedSessionId] = useState('')
  const [sessionRows,       setSessionRows]       = useState([])
  const [error,             setError]             = useState('')
  const [message,           setMessage]           = useState('')
  const [loading,           setLoading]           = useState(false)
  const [exporting,         setExporting]         = useState('')
  const [modelEvaluation,   setModelEvaluation]   = useState(null)
  const [modelEvalLoading,  setModelEvalLoading]  = useState(false)

  const selectedSession = useMemo(
    () => sessions.find((s) => String(s.id) === String(selectedSessionId)),
    [sessions, selectedSessionId],
  )

  // ── Load báo cáo theo lớp ──────────────────────────────────────── //
  const loadClassReports = async (cls = className) => {
    if (!cls) {
      setError('Vui lòng chọn lớp.')
      setData([])
      setWarnings([])
      return
    }
    setLoading(true)
    try {
      const [summary, warningRes] = await Promise.all([
        api.get(`/reports/summary/${cls}`),
        api.get(`/reports/warnings/${cls}`),
      ])
      setData(summary.data)
      setWarnings(warningRes.data)
      setError('')
      setMessage(`Đã tải báo cáo lớp ${cls}.`)
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
      setData([])
      setWarnings([])
    } finally {
      setLoading(false)
    }
  }

  // ── Load buổi học ──────────────────────────────────────────────── //
  const loadSessions = async () => {
    try {
      const res = await api.get('/sessions/')
      setSessions(res.data)
      if (!selectedSessionId && res.data.length > 0)
        setSelectedSessionId(String(res.data[0].id))
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    }
  }

  // ── Load báo cáo theo buổi học ─────────────────────────────────── //
  const loadSessionReport = async (sid = selectedSessionId) => {
    if (!sid) { setSessionRows([]); return }
    setLoading(true)
    try {
      const res = await api.get(`/reports/session/${sid}`)
      setSessionRows(res.data)
      setError('')
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
      setSessionRows([])
    } finally {
      setLoading(false)
    }
  }

  const loadModelEvaluation = async () => {
    setModelEvalLoading(true)
    try {
      const res = await api.get('/reports/model-evaluation/stats')
      setModelEvaluation(res.data)
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
      setModelEvaluation(null)
    } finally {
      setModelEvalLoading(false)
    }
  }

  // ── Initial load ───────────────────────────────────────────────── //
  useEffect(() => {
    let mounted = true
    const init = async () => {
      try {
        const sessionRes = await api.get('/sessions/')
        if (!mounted) return
        setSessions(sessionRes.data)
        if (sessionRes.data.length > 0)
          setSelectedSessionId(String(sessionRes.data[0].id))
        if (isAdmin) await loadModelEvaluation()
      } catch (err) {
        if (mounted) setError(err.response?.data?.detail || err.message)
      }
    }
    init()
    return () => { mounted = false }
  }, [isAdmin])

  useEffect(() => {
    let mounted = true
    const load = async () => {
      if (!selectedSessionId) { setSessionRows([]); return }
      try {
        const res = await api.get(`/reports/session/${selectedSessionId}`)
        if (mounted) setSessionRows(res.data)
      } catch (err) {
        if (mounted) { setError(err.response?.data?.detail || err.message); setSessionRows([]) }
      }
    }
    load()
    return () => { mounted = false }
  }, [selectedSessionId])

  // ── Export helper ──────────────────────────────────────────────── //
  const exportFile = async (key, url, fallbackFilename) => {
    setExporting(key)
    try {
      const res = await api.get(url, { responseType: 'blob' })
      downloadBlob(res.data, getFilename(res.headers, fallbackFilename))
      setMessage(`Đã tải file.`)
      setError('')
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    } finally {
      setExporting('')
    }
  }

  // ── Render ─────────────────────────────────────────────────────── //
  return (
    <div>
      <div className="page-header">
        <div>
          <p className="eyebrow">Báo cáo</p>
          <h1 className="page-title">Báo cáo chuyên cần</h1>
          <p className="page-subtitle">
            Xem tổng hợp theo lớp, cảnh báo sinh viên vắng nhiều, báo cáo từng buổi học và tải file Excel/PDF.
          </p>
        </div>
      </div>

      {/* ── Báo cáo theo lớp ── */}
      <section className="panel panel-pad" style={{ marginBottom: 24 }}>
        <div style={{ display:'flex', justifyContent:'space-between', gap:12, alignItems:'center', marginBottom:16 }}>
          <div>
            <h3 style={{ marginTop:0 }}>Đánh giá mô hình</h3>
            <p style={{ margin:0, color:'var(--muted)', fontSize:13 }}>
              Chỉ hiển thị chỉ số nhận diện khuôn mặt, không trộn với báo cáo điểm danh chính thức.
            </p>
          </div>
          {isAdmin && (
            <button onClick={loadModelEvaluation} disabled={modelEvalLoading}>
              {modelEvalLoading ? 'Đang tải...' : 'Tải đánh giá'}
            </button>
          )}
        </div>

        {!modelEvaluation?.has_data ? (
          <div className="empty-state">
            {modelEvaluation?.message || 'Chưa có dữ liệu đánh giá mô hình. Hãy sử dụng chức năng Kiểm thử mô hình để tạo kết quả.'}
          </div>
        ) : (
          <div className="grid cards">
            {[
              { label:'Số mẫu test', value:modelEvaluation.sample_count, color:'#2563eb' },
              {
                label:modelEvaluation.source === 'model_test_log' ? 'Có kết quả match' : 'Nhận diện đúng',
                value:modelEvaluation.recognized_correct,
                color:'#15803d',
              },
              {
                label:modelEvaluation.source === 'model_test_log' ? 'Sai (cần ground truth)' : 'Nhận diện sai',
                value:modelEvaluation.recognized_wrong,
                color:'#b91c1c',
              },
              { label:'Không nhận diện', value:modelEvaluation.not_recognized, color:'#f59e0b' },
              { label:'Accuracy', value:formatRate(modelEvaluation.accuracy), color:'#7c3aed' },
              { label:'Avg confidence', value:formatConf(modelEvaluation.average_confidence), color:'#0f766e' },
              {
                label:'Avg processing',
                value:modelEvaluation.average_processing_time_ms == null ? '-' : `${modelEvaluation.average_processing_time_ms} ms`,
                color:'#475569',
              },
            ].map((item) => (
              <div key={item.label} className="stat-card" style={{ minHeight:92, borderLeftColor:item.color }}>
                <p>{item.label}</p>
                <strong>{item.value}</strong>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="panel panel-pad" style={{ marginBottom: 24 }}>
        <h3>Báo cáo theo lớp</h3>

        <div className="toolbar" style={{ marginBottom: 16 }}>
          {/* Dropdown lớp cố định — không tự gõ */}
          <select
            value={className}
            onChange={(e) => setClassName(e.target.value)}
            style={{ minWidth: 160 }}
          >
            <option value="">-- Chọn lớp --</option>
            {VALID_CLASSES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>

          <button onClick={() => loadClassReports()} disabled={loading || !className}>
            {loading ? 'Đang tải...' : 'Tải báo cáo'}
          </button>
          {isAdmin && (
            <>
              <button
                onClick={() => exportFile('class-excel', `/reports/export/excel/${className}`, `attendance_${className}.xlsx`)}
                disabled={!className || exporting === 'class-excel'}
              >
                {exporting === 'class-excel' ? 'Đang xuất...' : 'Excel tổng hợp'}
              </button>
              <button
                onClick={() => exportFile('class-pdf', `/reports/export/pdf/${className}`, `attendance_${className}.pdf`)}
                disabled={!className || exporting === 'class-pdf'}
              >
                {exporting === 'class-pdf' ? 'Đang xuất...' : 'PDF tổng hợp'}
              </button>
              <button
                onClick={() => exportFile('warning-excel', `/reports/export/excel/warnings/${className}`, `attendance_warnings_${className}.xlsx`)}
                disabled={!className || exporting === 'warning-excel'}
              >
                {exporting === 'warning-excel' ? 'Đang xuất...' : 'Excel cảnh báo'}
              </button>
            </>
          )}
        </div>

        {error   && <p className="status-message error">{error}</p>}
        {message && <p className="status-message">{message}</p>}

        {!className ? (
          <div className="empty-state">Chọn lớp ở trên để xem báo cáo.</div>
        ) : (
          <>
            <div className="grid cards" style={{ marginBottom: 20 }}>
              <div className="stat-card" style={{ minHeight: 92, borderLeftColor: '#2563eb' }}>
                <p>Sinh viên</p>
                <strong>{data.length}</strong>
              </div>
              <div className="stat-card" style={{ minHeight: 92, borderLeftColor: warnings.length ? '#b91c1c' : '#15803d' }}>
                <p>Cảnh báo</p>
                <strong>{warnings.length} SV</strong>
              </div>
              <div className="stat-card" style={{ minHeight: 92, borderLeftColor: '#7c3aed' }}>
                <p>Tổng buổi học</p>
                <strong>{data[0]?.total_sessions || 0}</strong>
              </div>
            </div>

            <h3>Tỷ lệ chuyên cần — Lớp {className}</h3>
            <AttendanceChart data={data} />

            <h3 style={{ color: 'var(--danger)', marginTop: 16 }}>
              Cảnh báo thiếu chuyên cần ({warnings.length} sinh viên)
            </h3>
            <WarningTable warnings={warnings} />
          </>
        )}
      </section>

      {/* ── Báo cáo theo buổi học ── */}
      <section className="panel panel-pad">
        <h3>Báo cáo theo buổi học</h3>

        <div className="toolbar" style={{ marginBottom: 16 }}>
          <select
            value={selectedSessionId}
            onChange={(e) => setSelectedSessionId(e.target.value)}
            style={{ minWidth: 320 }}
          >
            <option value="">Chọn buổi học</option>
            {sessions.map((s) => (
              <option key={s.id} value={s.id}>
                #{s.id} — {s.class_name} — {s.subject} — {s.session_date}
              </option>
            ))}
          </select>

          <button onClick={loadSessions}>Tải lại buổi học</button>
          <button onClick={() => loadSessionReport()} disabled={!selectedSessionId || loading}>
            Tải báo cáo buổi học
          </button>
          {isAdmin && (
            <>
              <button
                onClick={() => exportFile('session-excel', `/reports/export/excel/session/${selectedSessionId}`, `attendance_session_${selectedSessionId}.xlsx`)}
                disabled={!selectedSessionId || exporting === 'session-excel'}
              >
                {exporting === 'session-excel' ? 'Đang xuất...' : 'Excel buổi học'}
              </button>
              <button
                onClick={() => exportFile('session-pdf', `/reports/export/pdf/session/${selectedSessionId}`, `attendance_session_${selectedSessionId}.pdf`)}
                disabled={!selectedSessionId || exporting === 'session-pdf'}
              >
                {exporting === 'session-pdf' ? 'Đang xuất...' : 'PDF buổi học'}
              </button>
            </>
          )}
        </div>

        {selectedSession && (
          <p style={{ marginBottom: 12 }}>
            Buổi học #{selectedSession.id}: <strong>{selectedSession.class_name}</strong> —{' '}
            {selectedSession.subject} — {selectedSession.session_date}
          </p>
        )}

        {!sessions.length ? (
          <div className="empty-state">
            Chưa có buổi học. Vui lòng tạo buổi học tại mục <strong>Buổi học</strong> trước.
          </div>
        ) : !sessionRows.length ? (
          <div className="empty-state">Chưa có dữ liệu điểm danh cho buổi học này.</div>
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  {['Mã SV', 'Họ tên', 'Trạng thái', 'Vào lớp', 'Ra về', 'Tin cậy vào', 'Tin cậy ra'].map((h) => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sessionRows.map((row) => (
                  <tr key={row.student_code}>
                    <td>{row.student_code}</td>
                    <td>{row.full_name || '-'}</td>
                    <td>
                      <span className={`badge ${row.status === 'absent' ? 'danger' : row.status === 'late' ? 'warning' : 'success'}`}>
                        {statusLabels[row.status] || row.status}
                      </span>
                    </td>
                    <td>{formatDT(row.check_in_at)}</td>
                    <td>{formatDT(row.check_out_at)}</td>
                    <td>{formatConf(row.check_in_conf)}</td>
                    <td>{formatConf(row.check_out_conf)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
