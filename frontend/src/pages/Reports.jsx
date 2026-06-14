import { useEffect, useMemo, useState } from 'react'

import api from '../../api/axios.js'
import { useAuth } from '../auth/auth-context.js'
import AttendanceChart from '../components/AttendanceChart.jsx'
import WarningTable from '../components/WarningTable.jsx'
import { VALID_CLASSES } from '../constants/classes.js'
import { getApiErrorMessage } from '../utils/apiError.js'
import { attendanceStatusLabels, getDisplayLabel, recognitionStatusLabels } from '../utils/displayLabels.js'

// ------------------------------------------------------------------ //
// Hằng số — đồng bộ với Students.jsx và Sessions.jsx
// ------------------------------------------------------------------ //
const statusLabels = attendanceStatusLabels

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

const formatDateStr = (dateStr) => {
  if (!dateStr) return ''
  if (/^\d{2}\/\d{2}\/\d{4}$/.test(dateStr)) return dateStr
  const parts = dateStr.split('-')
  if (parts.length === 3) {
    return `${parts[2]}/${parts[1]}/${parts[0]}`
  }
  return dateStr
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
  const [modelEvalDetails,  setModelEvalDetails]  = useState([])
  const [modelEvalLoading,  setModelEvalLoading]  = useState(false)

  const selectedSession = useMemo(
    () => sessions.find((s) => String(s.id) === String(selectedSessionId)),
    [sessions, selectedSessionId],
  )

  const handleReportError = (err, fallback) => {
    if (err.response?.status === 403) {
      setError('Bạn không có quyền xem báo cáo này.')
    } else {
      setError(getApiErrorMessage(err, fallback))
    }
  }

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
      handleReportError(err, 'Không tải được báo cáo lớp.')
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
      handleReportError(err, 'Không tải được danh sách buổi học.')
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
      handleReportError(err, 'Không tải được báo cáo buổi học.')
      setSessionRows([])
    } finally {
      setLoading(false)
    }
  }

  const loadModelEvaluation = async () => {
    setModelEvalLoading(true)
    try {
      const [statsRes, detailsRes] = await Promise.all([
        api.get('/reports/model-evaluation/stats'),
        api.get('/reports/model-evaluation/details'),
      ])
      setModelEvaluation(statsRes.data)
      setModelEvalDetails(detailsRes.data?.items || [])
    } catch (err) {
      handleReportError(err, 'Không tải được kết quả đánh giá mô hình.')
      setModelEvaluation(null)
      setModelEvalDetails([])
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
        if (mounted) handleReportError(err, 'Không tải được dữ liệu báo cáo.')
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
        if (mounted) { handleReportError(err, 'Không tải được báo cáo buổi học.'); setSessionRows([]) }
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
      setMessage('Đã tải tệp báo cáo.')
      setError('')
    } catch (err) {
      handleReportError(err, 'Không xuất được báo cáo.')
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

      {error && <p className="status-message error" style={{ marginBottom: 16 }}>{error}</p>}
      {message && <p className="status-message" style={{ marginBottom: 16 }}>{message}</p>}

      {/* ── Báo cáo theo lớp ── */}
      {user?.role !== 'student' && (
        <section className="panel panel-pad" style={{ marginBottom: 24 }}>
        <div style={{ display:'flex', justifyContent:'space-between', gap:12, alignItems:'center', marginBottom:16 }}>
          <div>
            <h3 style={{ marginTop:0 }}>Đánh giá mô hình</h3>
            <p style={{ margin:0, color:'var(--muted)', fontSize:13 }}>
              Chỉ hiển thị chỉ số nhận diện khuôn mặt, không trộn với báo cáo điểm danh chính thức.
            </p>
          </div>
          {isAdmin && (
            <div className="toolbar" style={{ margin:0 }}>
              <button onClick={loadModelEvaluation} disabled={modelEvalLoading}>
                {modelEvalLoading ? 'Đang tải...' : 'Tải đánh giá'}
              </button>
              <button
                onClick={() => exportFile('model-csv', '/reports/export/model-evaluation/csv', 'model_evaluation_details.csv')}
                disabled={!modelEvaluation?.has_data || exporting === 'model-csv'}
              >
                {exporting === 'model-csv' ? 'Đang xuất...' : 'Xuất CSV'}
              </button>
              <button
                onClick={() => exportFile('model-excel', '/reports/export/model-evaluation/excel', 'model_evaluation.xlsx')}
                disabled={!modelEvaluation?.has_data || exporting === 'model-excel'}
              >
                {exporting === 'model-excel' ? 'Đang xuất...' : 'Xuất Excel'}
              </button>
            </div>
          )}
        </div>


        {!modelEvaluation?.has_data ? (
          <div className="empty-state">
            {modelEvaluation?.message || 'Chưa có dữ liệu đánh giá mô hình. Hãy chạy chương trình đánh giá với ảnh kiểm thử thật trước.'}
          </div>
        ) : (
          <>
            <div className="grid cards">
              {[
                { label:'Tổng ảnh kiểm thử', value:modelEvaluation.total_images ?? modelEvaluation.sample_count, color:'#2563eb' },
                { label:'Nhận diện đúng', value:modelEvaluation.recognized_correct, color:'#15803d' },
                { label:'Nhận diện sai', value:modelEvaluation.recognized_wrong, color:'#b91c1c' },
                { label:'Không nhận diện được', value:modelEvaluation.not_recognized, color:'#f59e0b' },
                { label:'TP', value:modelEvaluation.tp, color:'#0f766e' },
                { label:'FP', value:modelEvaluation.fp, color:'#dc2626' },
                { label:'FN', value:modelEvaluation.fn, color:'#ea580c' },
                { label:'TN', value:modelEvaluation.tn, color:'#475569' },
                { label:'Độ chính xác', value:formatRate(modelEvaluation.accuracy), color:'#7c3aed' },
                { label:'Độ chính xác dự đoán', value:formatRate(modelEvaluation.precision), color:'#0891b2' },
                { label:'Độ bao phủ', value:formatRate(modelEvaluation.recall), color:'#0369a1' },
                { label:'Điểm F1', value:formatRate(modelEvaluation.f1_score), color:'#4f46e5' },
                { label:'Tỷ lệ chấp nhận sai (FAR)', value:formatRate(modelEvaluation.far), color:'#be123c' },
                { label:'Tỷ lệ từ chối sai (FRR)', value:formatRate(modelEvaluation.frr), color:'#c2410c' },
                { label:'Độ tin cậy trung bình', value:formatConf(modelEvaluation.average_confidence), color:'#0f766e' },
                {
                  label:'Thời gian xử lý trung bình',
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

            <div className="table-wrap" style={{ marginTop: 18 }}>
              <table className="data-table">
                <thead>
                  <tr>
                    {['Tệp/Mẫu', 'Mẫu thực tế', 'Mã dự kiến', 'Mã dự đoán', 'Trạng thái', 'Độ tin cậy', 'Thời gian xử lý', 'Kết luận'].map((h) => (
                      <th key={h}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {modelEvalDetails.map((row, index) => (
                    <tr key={`${row.file_name || row.sample_name}-${index}`}>
                      <td>{row.file_name || row.sample_name || '-'}</td>
                      <td>{row.actual_student_code || row.sample_code || '-'}</td>
                      <td>{row.expected_student_code || '-'}</td>
                      <td>{row.predicted_student_code || '-'}</td>
                      <td>{getDisplayLabel(recognitionStatusLabels, row.status)}</td>
                      <td>{formatConf(Number(row.confidence))}</td>
                      <td>{row.processing_time_ms == null ? '-' : `${Number(row.processing_time_ms).toFixed(2)} ms`}</td>
                      <td><span className="badge">{row.result || '-'}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile Card Layout cho Đánh giá mô hình */}
            <div className="mobile-card-list" style={{ marginTop: 14 }}>
              {modelEvalDetails.map((row, index) => (
                <div key={`${row.file_name || row.sample_name}-${index}`} className="mobile-card">
                  <div className="mobile-card-header">
                    <span className="mobile-card-title" style={{ fontSize: '13px', fontWeight: 700 }}>
                      {row.file_name || row.sample_name || '-'}
                    </span>
                    <span className="badge">{row.result || '-'}</span>
                  </div>
                  <div className="mobile-card-row">
                    <span className="mobile-card-label">Mẫu thực tế:</span>
                    <span className="mobile-card-value">{row.actual_student_code || row.sample_code || '-'}</span>
                  </div>
                  <div className="mobile-card-row">
                    <span className="mobile-card-label">Dự kiến / Dự đoán:</span>
                    <span className="mobile-card-value">{row.expected_student_code || '-'} / {row.predicted_student_code || '-'}</span>
                  </div>
                  <div className="mobile-card-row">
                    <span className="mobile-card-label">Trạng thái:</span>
                    <span className="mobile-card-value">{getDisplayLabel(recognitionStatusLabels, row.status)}</span>
                  </div>
                  <div className="mobile-card-row">
                    <span className="mobile-card-label">Độ tin cậy:</span>
                    <span className="mobile-card-value">{formatConf(Number(row.confidence))}</span>
                  </div>
                  <div className="mobile-card-row">
                    <span className="mobile-card-label">Thời gian:</span>
                    <span className="mobile-card-value">{row.processing_time_ms == null ? '-' : `${Number(row.processing_time_ms).toFixed(1)} ms`}</span>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </section>
      )}

      {user?.role !== 'student' && (
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
      )}

      {/* ── Báo cáo theo buổi học ── */}
      <section className="panel panel-pad">
        <h3>{user?.role === 'student' ? 'Lịch sử điểm danh cá nhân' : 'Báo cáo theo buổi học'}</h3>

        <div className="toolbar" style={{ marginBottom: 16 }}>
          <select
            value={selectedSessionId}
            onChange={(e) => setSelectedSessionId(e.target.value)}
            style={{ minWidth: 320 }}
          >
            <option value="">Chọn buổi học</option>
            {sessions.map((s) => (
              <option key={s.id} value={s.id}>
                #{s.id} — {s.class_name} — {s.subject} — {formatDateStr(s.session_date)}
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
            {selectedSession.subject} — {formatDateStr(selectedSession.session_date)}
          </p>
        )}

        {!sessions.length ? (
          <div className="empty-state">
            Chưa có buổi học. Vui lòng tạo buổi học tại mục <strong>Buổi học</strong> trước.
          </div>
        ) : !sessionRows.length ? (
          <div className="empty-state">Chưa có dữ liệu điểm danh cho buổi học này.</div>
        ) : (
          <>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    {['Mã SV', 'Họ tên', 'Trạng thái', 'Vào lớp', 'Ra về', 'Độ tin cậy khi vào', 'Độ tin cậy khi ra'].map((h) => (
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
                          {getDisplayLabel(statusLabels, row.status)}
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

            {/* Mobile Card Layout cho Báo cáo theo buổi học */}
            <div className="mobile-card-list" style={{ marginTop: 14 }}>
              {sessionRows.map((row) => (
                <div key={row.student_code} className="mobile-card">
                  <div className="mobile-card-header">
                    <span className="mobile-card-title" style={{ fontFamily: 'var(--mono)', fontSize: '13px', fontWeight: 700 }}>
                      {row.student_code}
                    </span>
                    <span className={`badge ${row.status === 'absent' ? 'danger' : row.status === 'late' ? 'warning' : 'success'}`}>
                      {getDisplayLabel(statusLabels, row.status)}
                    </span>
                  </div>
                  <div className="mobile-card-row">
                    <span className="mobile-card-label">Họ tên:</span>
                    <span className="mobile-card-value">{row.full_name || '-'}</span>
                  </div>
                  <div className="mobile-card-row">
                    <span className="mobile-card-label">Vào lớp:</span>
                    <span className="mobile-card-value">
                      {formatDT(row.check_in_at)} {row.check_in_conf ? `(${formatConf(row.check_in_conf)})` : ''}
                    </span>
                  </div>
                  <div className="mobile-card-row">
                    <span className="mobile-card-label">Ra về:</span>
                    <span className="mobile-card-value">
                      {formatDT(row.check_out_at)} {row.check_out_conf ? `(${formatConf(row.check_out_conf)})` : ''}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </section>
    </div>
  )
}
