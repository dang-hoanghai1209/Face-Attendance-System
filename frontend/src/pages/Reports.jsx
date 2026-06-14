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

const formatDateForDisplay = (dateStr) => {
  if (!dateStr) return ''
  if (/^\d{2}\/\d{2}\/\d{4}$/.test(dateStr)) return dateStr
  const parts = String(dateStr).split('-')
  if (parts.length === 3) {
    return `${parts[2]}/${parts[1]}/${parts[0]}`
  }
  return dateStr
}
const formatDateStr = formatDateForDisplay

const getSessionDateValue = (session) => session.session_date || session.date || ''
const getSessionSubjectValue = (session) => session.subject_name || session.subject || ''
const getSessionIdValue = (session) => session.id || session.session_id

const getSessionDateTime = (session, timeField = 'start_time') => {
  const sessionDate = getSessionDateValue(session)
  const timeValue = session?.[timeField]
  if (!sessionDate || !timeValue) return null
  const [year, month, day] = String(sessionDate).split('-').map(Number)
  const [hour, minute] = String(timeValue).split(':').map(Number)
  return new Date(year, month - 1, day, hour || 0, minute || 0, 0)
}

const getSessionStatus = (session) => {
  const start = getSessionDateTime(session, 'start_time')
  const end = getSessionDateTime(session, 'end_time')
  if (!start || !end) return { label: 'Không rõ', badgeClass: 'badge' }

  const now = new Date()
  if (now < start) return { label: 'Sắp diễn ra', badgeClass: 'badge info' }
  if (now > end) return { label: 'Đã kết thúc', badgeClass: 'badge muted' }
  return { label: 'Đang diễn ra', badgeClass: 'badge success' }
}

const getSessionGroupKey = (session) => {
  if (session.section_id !== null && session.section_id !== undefined) return `section:${session.section_id}`
  return [
    session.section_code || '',
    session.section_group || '',
    session.class_name || '',
    getSessionSubjectValue(session),
  ].join('|')
}

const formatSectionLabel = (group) => [
  group.section_code,
  group.subject_name,
  group.section_group ? `Nhóm ${group.section_group}` : '',
  group.class_name ? `Lớp ${group.class_name}` : '',
].filter(Boolean).join(' - ')

const formatSessionOptionLabel = (session) => {
  const status = getSessionStatus(session)
  return `Buổi ${session.session_number || `#${getSessionIdValue(session)}`} - ${formatDateForDisplay(getSessionDateValue(session))} - ${status.label}`
}

const sortSessionsForPicker = (sessionsList) => [...sessionsList].sort((a, b) => {
  const statusPriority = { 'Đang diễn ra': 0, 'Sắp diễn ra': 1, 'Đã kết thúc': 2, 'Không rõ': 3 }
  const statusA = getSessionStatus(a).label
  const statusB = getSessionStatus(b).label
  const priorityDiff = (statusPriority[statusA] ?? 3) - (statusPriority[statusB] ?? 3)
  if (priorityDiff !== 0) return priorityDiff

  const timeA = getSessionDateTime(a, 'start_time')?.getTime() ?? 0
  const timeB = getSessionDateTime(b, 'start_time')?.getTime() ?? 0
  if (statusA === 'Đã kết thúc') return timeB - timeA
  return timeA - timeB
})

const groupSessionsBySection = (sessionsList) => {
  const groups = new Map()

  sessionsList.forEach((session) => {
    const key = getSessionGroupKey(session)
    if (!groups.has(key)) {
      groups.set(key, {
        key,
        section_id: session.section_id ?? null,
        section_code: session.section_code || session.subject_code || '',
        subject_name: getSessionSubjectValue(session),
        section_group: session.section_group || '',
        class_name: session.class_name || '',
        sessions: [],
      })
    }
    groups.get(key).sessions.push(session)
  })

  return Array.from(groups.values())
    .map((group) => ({ ...group, sessions: sortSessionsForPicker(group.sessions) }))
    .sort((a, b) => formatSectionLabel(a).localeCompare(formatSectionLabel(b), 'vi'))
}

const pickBestSessionInGroup = (groupSessions) => sortSessionsForPicker(groupSessions)[0] || null

const pickBestInitialGroup = (groups) => {
  const candidates = groups
    .map((group) => ({ group, session: pickBestSessionInGroup(group.sessions) }))
    .filter((item) => item.session)

  const ongoing = candidates.find((item) => getSessionStatus(item.session).label === 'Đang diễn ra')
  if (ongoing) return ongoing

  const upcoming = candidates
    .filter((item) => getSessionStatus(item.session).label === 'Sắp diễn ra')
    .sort((a, b) => {
      const timeA = getSessionDateTime(a.session, 'start_time')?.getTime() ?? Number.MAX_SAFE_INTEGER
      const timeB = getSessionDateTime(b.session, 'start_time')?.getTime() ?? Number.MAX_SAFE_INTEGER
      return timeA - timeB
    })[0]
  if (upcoming) return upcoming

  return candidates
    .sort((a, b) => {
      const timeA = getSessionDateTime(a.session, 'start_time')?.getTime() ?? 0
      const timeB = getSessionDateTime(b.session, 'start_time')?.getTime() ?? 0
      return timeB - timeA
    })[0] || null
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
  const [selectedSectionKey, setSelectedSectionKey] = useState('')
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
    () => sessions.find((s) => String(getSessionIdValue(s)) === String(selectedSessionId)),
    [sessions, selectedSessionId],
  )

  const groupedSections = useMemo(() => groupSessionsBySection(sessions), [sessions])

  const selectedSection = useMemo(
    () => groupedSections.find((group) => group.key === selectedSectionKey) || null,
    [groupedSections, selectedSectionKey],
  )

  const selectedSectionSessions = selectedSection?.sessions || []

  const applyBestSessionSelection = (sessionsList) => {
    const best = pickBestInitialGroup(groupSessionsBySection(sessionsList))
    if (best) {
      setSelectedSectionKey(best.group.key)
      setSelectedSessionId(String(getSessionIdValue(best.session)))
    } else {
      setSelectedSectionKey('')
      setSelectedSessionId('')
    }
  }

  const handleSectionChange = (sectionKey) => {
    setSelectedSectionKey(sectionKey)
    const group = groupedSections.find((item) => item.key === sectionKey)
    const bestSession = group ? pickBestSessionInGroup(group.sessions) : null
    setSelectedSessionId(bestSession ? String(getSessionIdValue(bestSession)) : '')
  }

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
      if (!selectedSessionId) {
        applyBestSessionSelection(res.data)
      }
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
        applyBestSessionSelection(sessionRes.data)
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

        <div className="toolbar" style={{ marginBottom: 16, alignItems: 'stretch' }}>
          <select
            value={selectedSectionKey}
            onChange={(e) => handleSectionChange(e.target.value)}
            style={{ minWidth: 280, flex: '1 1 280px' }}
          >
            <option value="">Chọn lớp học phần</option>
            {groupedSections.map((group) => (
              <option key={group.key} value={group.key}>
                {formatSectionLabel(group)}
              </option>
            ))}
          </select>

          <select
            value={selectedSessionId}
            onChange={(e) => setSelectedSessionId(e.target.value)}
            disabled={!selectedSectionKey}
            style={{ minWidth: 260, flex: '1 1 260px' }}
          >
            <option value="">Chọn buổi học</option>
            {selectedSectionSessions.map((session) => (
              <option key={getSessionIdValue(session)} value={getSessionIdValue(session)}>
                {formatSessionOptionLabel(session)}
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
          <div className="grid cards" style={{ marginBottom: 16 }}>
            <div className="stat-card" style={{ minHeight: 92 }}>
              <p>Lớp học phần</p>
              <strong style={{ fontSize: 15, lineHeight: 1.3 }}>
                {selectedSection ? formatSectionLabel(selectedSection) : [
                  selectedSession.section_code,
                  getSessionSubjectValue(selectedSession),
                  selectedSession.section_group ? `Nhóm ${selectedSession.section_group}` : '',
                  selectedSession.class_name ? `Lớp ${selectedSession.class_name}` : ''
                ].filter(Boolean).join(' - ')}
              </strong>
            </div>
            <div className="stat-card" style={{ minHeight: 92 }}>
              <p>Buổi học</p>
              <strong style={{ fontSize: 18 }}>
                Buổi {selectedSession.session_number || `#${getSessionIdValue(selectedSession)}`}
              </strong>
            </div>
            <div className="stat-card" style={{ minHeight: 92 }}>
              <p>Ngày học</p>
              <strong style={{ fontSize: 18 }}>{formatDateForDisplay(getSessionDateValue(selectedSession))}</strong>
            </div>
            <div className="stat-card" style={{ minHeight: 92 }}>
              <p>Trạng thái</p>
              <strong style={{ fontSize: 18 }}>{getSessionStatus(selectedSession).label}</strong>
            </div>
            <div className="stat-card" style={{ minHeight: 92 }}>
              <p>Tổng sinh viên</p>
              <strong>{sessionRows.length}</strong>
            </div>
          </div>
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
