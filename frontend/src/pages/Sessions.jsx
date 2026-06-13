import { useEffect, useMemo, useState } from 'react'

import api from '../../api/axios.js'
import { VALID_CLASSES } from '../constants/classes.js'
import { getApiErrorMessage } from '../utils/apiError.js'

// ------------------------------------------------------------------ //
// Hằng số
// ------------------------------------------------------------------ //
const initialForm = {
  subject:      '',
  class_name:   '',
  session_date: '',
  start_time:   '',
  end_time:     '',
}
const emptyErrors = {
  subject:    '',
  class_name: '',
  session_date: '',
  start_time: '',
  end_time: '',
}

function validateForm(form) {
  const errors = { ...emptyErrors }
  if (!form.subject.trim())    errors.subject      = 'Vui lòng nhập tên môn học.'
  if (!form.class_name)        errors.class_name   = 'Vui lòng chọn lớp.'
  if (!form.session_date)      errors.session_date = 'Vui lòng chọn ngày học.'
  if (!form.start_time)        errors.start_time   = 'Vui lòng chọn giờ bắt đầu.'
  if (!form.end_time)          errors.end_time     = 'Vui lòng chọn giờ kết thúc.'
  if (form.start_time && form.end_time && form.end_time <= form.start_time) {
    errors.end_time = 'Giờ kết thúc phải sau giờ bắt đầu.'
  }
  return errors
}

function hasErrors(e) { return Object.values(e).some(Boolean) }

const toTimeInput = (value) => value ? String(value).slice(0, 5) : ''
const formatTime = (value) => toTimeInput(value) || 'Chưa đặt giờ'

// ------------------------------------------------------------------ //
// Helpers for Alerts
// ------------------------------------------------------------------ //
const getImageUrl = (path) => {
  if (!path) return null
  if (/^https?:\/\//i.test(path)) return path
  const base = api.defaults.baseURL || ''
  const host = base.replace(/\/api$/, '')
  const cleanPath = path.startsWith('/') ? path : `/${path}`
  return `${host}${cleanPath}`
}

const getAlertCardStyle = (type) => {
  if (type === 'SPOOF' || type === 'UNKNOWN_FACE') {
    return {
      border: '1px solid rgba(244,63,94,0.3)',
      background: 'rgba(244,63,94,0.06)',
      color: '#fda4af',
      badgeBg: 'rgba(244,63,94,0.15)',
      badgeColor: '#fb7185',
      label: type === 'SPOOF' ? 'Giả mạo (Spoof)' : 'Khuôn mặt lạ (Unknown)'
    }
  }
  if (type === 'NOT_ENROLLED') {
    return {
      border: '1px solid rgba(249,115,22,0.3)',
      background: 'rgba(249,115,22,0.06)',
      color: '#ffedd5',
      badgeBg: 'rgba(249,115,22,0.15)',
      badgeColor: '#f97316',
      label: 'Chưa đăng ký môn học'
    }
  }
  if (type === 'LATE_ENTRY') {
    return {
      border: '1px solid rgba(251,191,36,0.3)',
      background: 'rgba(251,191,36,0.06)',
      color: '#fef3c7',
      badgeBg: 'rgba(251,191,36,0.15)',
      badgeColor: '#fbbf24',
      label: 'Đi học muộn'
    }
  }
  return {
    border: '1px solid var(--bdr)',
    background: 'rgba(255,255,255,0.02)',
    color: 'var(--white)',
    badgeBg: 'rgba(255,255,255,0.05)',
    badgeColor: 'var(--white2)',
    label: type
  }
}

// ------------------------------------------------------------------ //
// Component
// ------------------------------------------------------------------ //
export default function Sessions() {
  const [sessions,  setSessions]  = useState([])
  const [form,      setForm]      = useState(initialForm)
  const [errors,    setErrors]    = useState(emptyErrors)
  const [editingId, setEditingId] = useState(null)
  const [search,    setSearch]    = useState('')
  const [message,   setMessage]   = useState('')
  const [loading,   setLoading]   = useState(false)
  const [deleteTarget, setDeleteTarget] = useState(null)

  // Enrollment states
  const [enrollModalTarget, setEnrollModalTarget] = useState(null)
  const [enrollments,       setEnrollments]       = useState([])
  const [enrollLoading,     setEnrollLoading]     = useState(false)
  const [enrollMessage,     setEnrollMessage]     = useState('')
  const [importClassName,   setImportClassName]   = useState('')
  const [manualCodes,       setManualCodes]       = useState('')

  // Alert states
  const [alertCounts,       setAlertCounts]       = useState({})
  const [alertModalTarget,  setAlertModalTarget]  = useState(null)
  const [activeAlerts,      setActiveAlerts]      = useState([])
  const [alertLoading,      setAlertLoading]      = useState(false)
  const [alertMessage,      setAlertMessage]      = useState('')

  const loadAlertCounts = async (sessionsList) => {
    const counts = {}
    await Promise.all(
      sessionsList.map(async (s) => {
        try {
          const res = await api.get(`/alerts/session/${s.id}/count`)
          counts[s.id] = res.data.total_active
        } catch (err) {
          console.error(`Failed to load alert count for session ${s.id}`, err)
          counts[s.id] = 0
        }
      })
    )
    setAlertCounts(counts)
  }

  // Active alerts polling effect
  useEffect(() => {
    if (!alertModalTarget) return
    const id = setInterval(() => {
      loadActiveAlertsSilent(alertModalTarget.id)
    }, 5000)
    return () => clearInterval(id)
  }, [alertModalTarget])

  const loadSessions = async () => {
    try {
      const response = await api.get('/sessions/')
      setSessions(response.data)
      loadAlertCounts(response.data)
    } catch (error) {
      setMessage(getApiErrorMessage(error, 'Không tải được danh sách buổi học.'))
    }
  }

  useEffect(() => {
    let mounted = true
    const load = async () => {
      try {
        const response = await api.get('/sessions/')
        if (mounted) {
          setSessions(response.data)
          loadAlertCounts(response.data)
        }
      } catch (error) {
        if (mounted) setMessage(getApiErrorMessage(error, 'Không tải được danh sách buổi học.'))
      }
    }
    load()
    return () => { mounted = false }
  }, [])

  const filteredSessions = useMemo(() => {
    const keyword = search.trim().toLowerCase()
    if (!keyword) return sessions
    return sessions.filter((s) =>
      String(s.id).includes(keyword) ||
      s.subject?.toLowerCase().includes(keyword) ||
      s.class_name?.toLowerCase().includes(keyword) ||
      s.session_date?.includes(keyword)
    )
  }, [sessions, search])

  const resetForm = () => {
    setForm(initialForm)
    setErrors(emptyErrors)
    setEditingId(null)
  }

  const handleChange = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }))
    setErrors((prev) => ({ ...prev, [field]: '' }))
  }

  const handleSubmit = async () => {
    const validationErrors = validateForm(form)
    if (hasErrors(validationErrors)) {
      setErrors(validationErrors)
      return
    }

    const payload = {
      subject:      form.subject.trim(),
      class_name:   form.class_name,
      session_date: form.session_date,
      start_time:   form.start_time,
      end_time:     form.end_time,
      created_by:   null,
    }

    setLoading(true)
    try {
      if (editingId) {
        await api.put(`/sessions/${editingId}`, payload)
        setMessage('Cập nhật buổi học thành công.')
      } else {
        await api.post('/sessions/', payload)
        setMessage('Tạo buổi học thành công.')
      }
      resetForm()
      await loadSessions()
    } catch (error) {
      setMessage(getApiErrorMessage(error, 'Không lưu được thông tin buổi học.'))
    } finally {
      setLoading(false)
    }
  }

  const handleEdit = (session) => {
    setEditingId(session.id)
    setForm({
      subject:      session.subject      || '',
      class_name:   session.class_name   || '',
      session_date: session.session_date || '',
      start_time:   toTimeInput(session.start_time),
      end_time:     toTimeInput(session.end_time),
    })
    setErrors(emptyErrors)
    setMessage('')
  }

  const handleDelete = (session) => {
    const label = `#${session.id} - ${session.class_name} - ${session.subject}`
    setDeleteTarget({ ...session, label })
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return

    setLoading(true)
    try {
      await api.delete(`/sessions/${deleteTarget.id}`)
      setMessage('Đã xóa buổi học.')
      if (editingId === deleteTarget.id) resetForm()
      setDeleteTarget(null)
      await loadSessions()
    } catch (error) {
      setMessage(getApiErrorMessage(error, 'Không xóa được buổi học.'))
    } finally {
      setLoading(false)
    }
  }

  const handleOpenEnrollment = (session) => {
    setEnrollModalTarget(session)
    setEnrollMessage('')
    setImportClassName('')
    setManualCodes('')
    loadEnrollments(session.id)
  }

  const loadEnrollments = async (sid) => {
    setEnrollLoading(true)
    try {
      const response = await api.get(`/sessions/${sid}/enrollments`)
      setEnrollments(response.data)
    } catch (error) {
      setEnrollMessage(getApiErrorMessage(error, 'Không tải được danh sách đăng ký.'))
    } finally {
      setEnrollLoading(false)
    }
  }

  const handleImportByClass = async () => {
    if (!importClassName.trim()) {
      setEnrollMessage('⚠️ Vui lòng nhập tên lớp để thực hiện import.')
      return
    }
    setEnrollLoading(true)
    setEnrollMessage('')
    try {
      const response = await api.post(`/sessions/${enrollModalTarget.id}/enroll/import`, {
        class_name: importClassName.trim()
      })
      const { added, skipped, total_found } = response.data
      setEnrollMessage(`✅ Nhập dữ liệu thành công. Tìm thấy: ${total_found} · Thêm mới: ${added} · Bỏ qua: ${skipped}.`)
      setEnrollments(response.data.enrolled || [])
      setImportClassName('')
    } catch (error) {
      setEnrollMessage(getApiErrorMessage(error, 'Không import được theo lớp.'))
    } finally {
      setEnrollLoading(false)
    }
  }

  const handleAddManual = async () => {
    if (!manualCodes.trim()) {
      setEnrollMessage('⚠️ Vui lòng nhập mã sinh viên.')
      return
    }
    const codes = Array.from(new Set(
      manualCodes
        .split(/[\n,]+/)
        .map(c => c.trim())
        .filter(Boolean)
    ))

    if (codes.length === 0) {
      setEnrollMessage('⚠️ Vui lòng nhập ít nhất một mã sinh viên hợp lệ.')
      return
    }

    setEnrollLoading(true)
    setEnrollMessage('')
    try {
      const response = await api.post(`/sessions/${enrollModalTarget.id}/enroll`, {
        student_codes: codes
      })
      const { added, skipped, failed, failed_items } = response.data
      let statusMsg = `✅ Đã xử lý xong. Thêm mới: ${added} · Bỏ qua: ${skipped} · Thất bại: ${failed}.`
      if (failed_items && failed_items.length > 0) {
        const failDetails = failed_items.map(item => `${item.student_code} (${item.reason})`).join(', ')
        statusMsg += ` (Lỗi: ${failDetails})`
      }
      setEnrollMessage(statusMsg)
      setEnrollments(response.data.enrolled || [])
      setManualCodes('')
    } catch (error) {
      setEnrollMessage(getApiErrorMessage(error, 'Không thêm được sinh viên.'))
    } finally {
      setEnrollLoading(false)
    }
  }

  const handleDeleteEnrollment = async (studentCode) => {
    const confirmed = window.confirm(`Bạn có chắc muốn xóa sinh viên ${studentCode} khỏi buổi học này?`)
    if (!confirmed) return

    setEnrollLoading(true)
    setEnrollMessage('')
    try {
      await api.delete(`/sessions/${enrollModalTarget.id}/enroll/${studentCode}`)
      setEnrollMessage(`🗑️ Đã xóa sinh viên ${studentCode} khỏi danh sách đăng ký của buổi học.`)
      await loadEnrollments(enrollModalTarget.id)
    } catch (error) {
      setEnrollMessage(getApiErrorMessage(error, 'Không xóa được đăng ký.'))
    } finally {
      setEnrollLoading(false)
    }
  }

  const handleOpenAlerts = (session) => {
    setAlertModalTarget(session)
    setAlertMessage('')
    loadActiveAlerts(session.id)
  }

  const loadActiveAlerts = async (sid) => {
    setAlertLoading(true)
    try {
      const response = await api.get(`/alerts/session/${sid}/active`)
      setActiveAlerts(response.data)
    } catch (error) {
      setAlertMessage(getApiErrorMessage(error, 'Không tải được danh sách cảnh báo.'))
    } finally {
      setAlertLoading(false)
    }
  }

  const loadActiveAlertsSilent = async (sid) => {
    try {
      const response = await api.get(`/alerts/session/${sid}/active`)
      setActiveAlerts(response.data)
      const countRes = await api.get(`/alerts/session/${sid}/count`)
      setAlertCounts(prev => ({ ...prev, [sid]: countRes.data.total_active }))
    } catch (error) {
      console.warn('Silent alert reload failed', error)
    }
  }

  const handleDismissAlert = async (alertId) => {
    const note = window.prompt('Nhập ghi chú xử lý (không bắt buộc):', 'Đã kiểm tra thực tế')
    if (note === null) return

    setAlertLoading(true)
    setAlertMessage('')
    try {
      await api.post(`/alerts/${alertId}/dismiss`, {
        note: note.trim() || 'Đã kiểm tra',
        dismissed_by: 'lecturer'
      })
      setAlertMessage('✅ Đã tắt cảnh báo bảo mật.')
      await loadActiveAlerts(alertModalTarget.id)
      const countRes = await api.get(`/alerts/session/${alertModalTarget.id}/count`)
      setAlertCounts(prev => ({ ...prev, [alertModalTarget.id]: countRes.data.total_active }))
    } catch (error) {
      setAlertMessage(getApiErrorMessage(error, 'Không xử lý được cảnh báo.'))
    } finally {
      setAlertLoading(false)
    }
  }

  // ---------------------------------------------------------------- //
  // Render
  // ---------------------------------------------------------------- //
  return (
    <div>
      <div className="page-header">
        <div>
          <p className="eyebrow">Buổi học</p>
          <h1 className="page-title">Quản lý buổi học</h1>
          <p className="page-subtitle">
            Tạo lịch học theo lớp để hệ thống tính đi trễ, vắng mặt và tổng hợp chuyên cần.
          </p>
        </div>
      </div>

      <div className="panel panel-pad" style={{ marginBottom: 18 }}>
        <div className="form-grid" style={{ marginBottom: 12 }}>

          {/* Môn học */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <input
              placeholder="Môn học"
              value={form.subject}
              onChange={(e) => handleChange('subject', e.target.value)}
              style={errors.subject ? { borderColor: '#e53e3e' } : {}}
            />
            {errors.subject && (
              <span style={{ fontSize: 12, color: '#e53e3e' }}>{errors.subject}</span>
            )}
          </div>

          {/* Lớp — dropdown cố định */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <select
              value={form.class_name}
              onChange={(e) => handleChange('class_name', e.target.value)}
              style={errors.class_name ? { borderColor: '#e53e3e' } : {}}
            >
              <option value="">-- Chọn lớp --</option>
              {VALID_CLASSES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
            {errors.class_name && (
              <span style={{ fontSize: 12, color: '#e53e3e' }}>{errors.class_name}</span>
            )}
          </div>

          {/* Ngày học */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <input
              type="date"
              value={form.session_date}
              onChange={(e) => handleChange('session_date', e.target.value)}
              style={errors.session_date ? { borderColor: '#e53e3e' } : {}}
            />
            {errors.session_date && (
              <span style={{ fontSize: 12, color: '#e53e3e' }}>{errors.session_date}</span>
            )}
          </div>

          {/* Giờ bắt đầu */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <input
              type="time"
              value={form.start_time}
              onChange={(e) => handleChange('start_time', e.target.value)}
              style={errors.start_time ? { borderColor: '#e53e3e' } : {}}
            />
            {errors.start_time && (
              <span style={{ fontSize: 12, color: '#e53e3e' }}>{errors.start_time}</span>
            )}
          </div>

          {/* Giờ kết thúc */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <input
              type="time"
              value={form.end_time}
              onChange={(e) => handleChange('end_time', e.target.value)}
              style={errors.end_time ? { borderColor: '#e53e3e' } : {}}
            />
            {errors.end_time && (
              <span style={{ fontSize: 12, color: '#e53e3e' }}>{errors.end_time}</span>
            )}
          </div>

        </div>

        <div className="toolbar">
          <button onClick={handleSubmit} disabled={loading}>
            {loading ? 'Đang lưu...' : editingId ? 'Cập nhật buổi học' : 'Tạo buổi học'}
          </button>
          <button className="secondary" onClick={resetForm} disabled={loading}>
            Hủy
          </button>
          <button className="secondary" onClick={loadSessions} disabled={loading}>
            Tải lại dữ liệu
          </button>
          <input
            placeholder="Tìm theo mã buổi, môn học, lớp hoặc ngày"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ minWidth: 240 }}
          />
        </div>
      </div>

      {message && <p className="status-message">{message}</p>}

      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              {['Mã buổi', 'Môn học', 'Lớp', 'Ngày', 'Bắt đầu', 'Kết thúc', 'Thao tác'].map((h) => (
                <th key={h}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filteredSessions.map((session) => (
              <tr key={session.id}>
                <td>#{session.id}</td>
                <td>{session.subject}</td>
                <td>{session.class_name}</td>
                <td>{session.session_date}</td>
                <td>{formatTime(session.start_time)}</td>
                <td>{formatTime(session.end_time)}</td>
                <td>
                  <div className="toolbar">
                    <button
                      className="secondary"
                      onClick={() => handleOpenAlerts(session)}
                      disabled={loading}
                      style={{
                        position: 'relative',
                        borderColor: alertCounts[session.id] > 0 ? 'var(--red)' : 'var(--bdr)'
                      }}
                    >
                      ⚠️ Cảnh báo
                      {alertCounts[session.id] > 0 && (
                        <span style={{
                          position: 'absolute',
                          top: -6,
                          right: -6,
                          background: 'var(--red)',
                          color: '#fff',
                          borderRadius: '50%',
                          padding: '2px 6px',
                          fontSize: 10,
                          fontWeight: 'bold'
                        }}>
                          {alertCounts[session.id]}
                        </span>
                      )}
                    </button>
                    <button className="secondary" onClick={() => handleOpenEnrollment(session)} disabled={loading}>
                      Đăng ký
                    </button>
                    <button className="secondary" onClick={() => handleEdit(session)} disabled={loading}>
                      Sửa
                    </button>
                    <button className="secondary" style={{ background:'rgba(244,63,94,.1)', border:'1px solid rgba(244,63,94,.25)', color:'var(--red)' }} onClick={() => handleDelete(session)} disabled={loading}>
                      Xóa
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile Card Layout */}
      <div className="mobile-card-list">
        {filteredSessions.length === 0 ? (
          <div className="empty-state">Không có buổi học phù hợp.</div>
        ) : (
          filteredSessions.map((session) => (
            <div key={session.id} className="mobile-card">
              <div className="mobile-card-header">
                <span className="mobile-card-title" style={{ color: 'var(--teal)', fontWeight: 700 }}>
                  {session.subject}
                </span>
                <span className="badge success" style={{ fontFamily: 'var(--mono)', fontSize: '11px' }}>
                  #{session.id}
                </span>
              </div>
              <div className="mobile-card-row">
                <span className="mobile-card-label">Lớp:</span>
                <span className="mobile-card-value" style={{ fontFamily: 'var(--mono)' }}>{session.class_name}</span>
              </div>
              <div className="mobile-card-row">
                <span className="mobile-card-label">Ngày học:</span>
                <span className="mobile-card-value">{session.session_date}</span>
              </div>
              <div className="mobile-card-row">
                <span className="mobile-card-label">Thời gian:</span>
                <span className="mobile-card-value">
                  {formatTime(session.start_time)} - {formatTime(session.end_time)}
                </span>
              </div>
              <div className="mobile-card-actions">
                <button
                  className="secondary"
                  onClick={() => handleOpenAlerts(session)}
                  disabled={loading}
                  style={{
                    position: 'relative',
                    borderColor: alertCounts[session.id] > 0 ? 'var(--red)' : 'var(--bdr)'
                  }}
                >
                  ⚠️ Cảnh báo
                  {alertCounts[session.id] > 0 && (
                    <span style={{
                      position: 'absolute',
                      top: -6,
                      right: -6,
                      background: 'var(--red)',
                      color: '#fff',
                      borderRadius: '50%',
                      padding: '2px 6px',
                      fontSize: 10,
                      fontWeight: 'bold'
                    }}>
                      {alertCounts[session.id]}
                    </span>
                  )}
                </button>
                <button className="secondary" onClick={() => handleOpenEnrollment(session)} disabled={loading}>
                  Đăng ký
                </button>
                <button className="secondary" onClick={() => handleEdit(session)} disabled={loading}>
                  Sửa
                </button>
                <button
                  style={{ background: 'rgba(244,63,94,.1)', color: 'var(--red)', border: '1px solid rgba(244,63,94,.2)' }}
                  onClick={() => handleDelete(session)}
                  disabled={loading}
                >
                  Xóa
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {!filteredSessions.length && (
        <div className="empty-state" style={{ marginTop: 12 }}>Không có buổi học phù hợp.</div>
      )}

      {deleteTarget && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="delete-session-title"
          style={{
            position:'fixed',
            inset:0,
            background:'rgba(0,0,0,.45)',
            display:'flex',
            alignItems:'center',
            justifyContent:'center',
            zIndex:1000,
            padding:16
          }}
        >
          <div style={{ width:'min(460px, 100%)', background:'var(--navy2)', border:'1px solid var(--bdr2)', borderRadius:12, padding:20, boxShadow:'var(--shadow)' }}>
            <h2 id="delete-session-title" style={{ margin:'0 0 8px', fontSize:18, color:'var(--white)' }}>Xóa buổi học</h2>
            <p style={{ margin:'0 0 16px', color:'var(--white2)', lineHeight:1.55 }}>
              Bạn có chắc muốn xóa buổi học <strong style={{ color:'var(--white)' }}>{deleteTarget.label}</strong>? Dữ liệu điểm danh của buổi này cũng sẽ bị xóa.
            </p>
            <div className="toolbar" style={{ justifyContent:'flex-end' }}>
              <button
                onClick={() => setDeleteTarget(null)}
                disabled={loading}
                className="secondary"
                style={{ minHeight:38 }}
              >
                Hủy
              </button>
              <button
                onClick={confirmDelete}
                disabled={loading}
                style={{ background:'var(--red)', color:'#ffffff', minHeight:38 }}
              >
                {loading ? 'Đang xóa...' : 'Xóa'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Enrollment Management Modal */}
      {enrollModalTarget && (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,.65)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: 12
          }}
        >
          <div
            style={{
              width: 'min(560px, 100%)',
              maxHeight: '90vh',
              background: 'var(--navy2)',
              border: '1px solid var(--bdr2)',
              borderRadius: 12,
              padding: '20px 16px',
              boxShadow: 'var(--shadow)',
              display: 'flex',
              flexDirection: 'column',
              gap: 16
            }}
          >
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--bdr)', paddingBottom: 10 }}>
              <div>
                <h3 style={{ margin: 0, fontSize: 16, color: 'var(--white)' }}>Danh sách đăng ký</h3>
                <p style={{ margin: '4px 0 0', fontSize: 12, color: 'var(--muted)' }}>
                  Buổi #{enrollModalTarget.id} · {enrollModalTarget.subject} ({enrollModalTarget.class_name})
                </p>
              </div>
              <button
                className="secondary"
                onClick={() => setEnrollModalTarget(null)}
                style={{ minHeight: 32, padding: '0 8px', fontSize: 18 }}
              >
                ✕
              </button>
            </div>

            {/* Notification message inside modal */}
            {enrollMessage && (
              <p
                style={{
                  margin: 0,
                  padding: '8px 12px',
                  borderRadius: 6,
                  fontSize: 12,
                  background: enrollMessage.startsWith('✅') ? 'rgba(0, 201, 167, 0.08)' : 'rgba(244, 63, 94, 0.08)',
                  border: `1px solid ${enrollMessage.startsWith('✅') ? 'rgba(0, 201, 167, 0.2)' : 'rgba(244, 63, 94, 0.2)'}`,
                  color: enrollMessage.startsWith('✅') ? 'var(--teal)' : 'var(--red)',
                  lineHeight: 1.4,
                  wordBreak: 'break-word'
                }}
              >
                {enrollMessage}
              </p>
            )}

            {/* Quick action section: Import / Add */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, background: 'rgba(255,255,255,0.02)', padding: 12, borderRadius: 8, border: '1px solid var(--bdr)' }}>
              {/* Import by Class */}
              <div style={{ display: 'flex', gap: 8 }}>
                <input
                  placeholder="Tên lớp (ví dụ: 64-TTQL-1)"
                  value={importClassName}
                  onChange={(e) => setImportClassName(e.target.value)}
                  style={{ flex: 1, minHeight: 36, padding: '6px 10px', fontSize: 13 }}
                  disabled={enrollLoading}
                />
                <button
                  onClick={handleImportByClass}
                  disabled={enrollLoading}
                  style={{ minHeight: 36, padding: '0 12px', fontSize: 13 }}
                >
                  Import lớp
                </button>
              </div>

              {/* Add Manual */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <textarea
                  placeholder="Thêm mã SV thủ công (SV001, SV002...)"
                  rows={2}
                  value={manualCodes}
                  onChange={(e) => setManualCodes(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    fontSize: 13,
                    borderRadius: 6,
                    border: '1px solid var(--bdr)',
                    background: 'var(--navy)',
                    color: 'var(--white)',
                    resize: 'none'
                  }}
                  disabled={enrollLoading}
                />
                <button
                  onClick={handleAddManual}
                  disabled={enrollLoading}
                  style={{ minHeight: 34, fontSize: 13, width: 'fit-content', alignSelf: 'flex-end' }}
                >
                  Thêm sinh viên
                </button>
              </div>
            </div>

            {/* Enrolled list wrapper */}
            <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 8, minHeight: 180 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, fontWeight: 700, color: 'var(--white2)' }}>
                <span>Sinh viên đã đăng ký</span>
                <span style={{ color: 'var(--teal)' }}>Tổng số: {enrollments.length}</span>
              </div>

              {enrollLoading && enrollments.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--muted)', fontSize: 13 }}>
                  Đang tải danh sách đăng ký...
                </div>
              ) : enrollments.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--muted)', fontSize: 13, border: '1px dashed var(--bdr)', borderRadius: 8 }}>
                  Chưa có sinh viên nào đăng ký cho buổi học này.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {enrollments.map((en) => (
                    <div
                      key={en.id}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '8px 12px',
                        background: 'rgba(255,255,255,0.01)',
                        border: '1px solid var(--bdr)',
                        borderRadius: 6
                      }}
                    >
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <span style={{ fontSize: 13, color: 'var(--white)', fontWeight: 600 }}>
                          {en.full_name || 'Họ tên chưa rõ'}
                        </span>
                        <span style={{ fontSize: 11, color: 'var(--muted)', fontFamily: 'var(--mono)' }}>
                          {en.student_code} · {en.class_name || 'Lớp: ?'}
                        </span>
                      </div>
                      <button
                        className="secondary"
                        onClick={() => handleDeleteEnrollment(en.student_code)}
                        style={{
                          minHeight: 28,
                          padding: '0 8px',
                          fontSize: 11,
                          borderColor: 'rgba(244,63,94,.25)',
                          color: '#fb7185',
                          background: 'rgba(244,63,94,0.04)'
                        }}
                        disabled={enrollLoading}
                      >
                        Xóa
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
            {/* Footer close button */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', borderTop: '1px solid var(--bdr)', paddingTop: 10 }}>
              <button
                className="secondary"
                onClick={() => setEnrollModalTarget(null)}
                style={{ minHeight: 38 }}
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Security Alerts Modal */}
      {alertModalTarget && (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,.65)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: 12
          }}
        >
          <div
            style={{
              width: 'min(620px, 100%)',
              maxHeight: '90vh',
              background: 'var(--navy2)',
              border: '1px solid var(--bdr2)',
              borderRadius: 12,
              padding: '20px 16px',
              boxShadow: 'var(--shadow)',
              display: 'flex',
              flexDirection: 'column',
              gap: 16
            }}
          >
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--bdr)', paddingBottom: 10 }}>
              <div>
                <h3 style={{ margin: 0, fontSize: 16, color: 'var(--white)' }}>Cảnh báo bảo mật</h3>
                <p style={{ margin: '4px 0 0', fontSize: 12, color: 'var(--muted)' }}>
                  Buổi #{alertModalTarget.id} · {alertModalTarget.subject} ({alertModalTarget.class_name})
                </p>
              </div>
              <button
                className="secondary"
                onClick={() => setAlertModalTarget(null)}
                style={{ minHeight: 32, padding: '0 8px', fontSize: 18 }}
              >
                ✕
              </button>
            </div>

            {/* Notification message inside modal */}
            {alertMessage && (
              <p
                style={{
                  margin: 0,
                  padding: '8px 12px',
                  borderRadius: 6,
                  fontSize: 12,
                  background: alertMessage.startsWith('✅') ? 'rgba(0, 201, 167, 0.08)' : 'rgba(244, 63, 94, 0.08)',
                  border: `1px solid ${alertMessage.startsWith('✅') ? 'rgba(0, 201, 167, 0.2)' : 'rgba(244, 63, 94, 0.2)'}`,
                  color: alertMessage.startsWith('✅') ? 'var(--teal)' : 'var(--red)',
                  lineHeight: 1.4,
                  wordBreak: 'break-word'
                }}
              >
                {alertMessage}
              </p>
            )}

            {/* Alerts list wrapper */}
            <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 12, minHeight: 240 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, fontWeight: 700, color: 'var(--white2)' }}>
                <span>Cảnh báo chưa xử lý (Active)</span>
                <span style={{ color: 'var(--red)' }}>Số lượng: {activeAlerts.length}</span>
              </div>

              {alertLoading && activeAlerts.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--muted)', fontSize: 13 }}>
                  Đang tải danh sách cảnh báo...
                </div>
              ) : activeAlerts.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--muted)', fontSize: 13, border: '1px dashed var(--bdr)', borderRadius: 8 }}>
                  Không có cảnh báo đang hoạt động.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {activeAlerts.map((al) => {
                    const style = getAlertCardStyle(al.alert_type)
                    return (
                      <div
                        key={al.id}
                        style={{
                          display: 'flex',
                          gap: 12,
                          padding: 12,
                          background: style.background,
                          border: style.border,
                          borderRadius: 8,
                          position: 'relative'
                        }}
                      >
                        {/* Image or fallback */}
                        {al.captured_img ? (
                          <img
                            src={getImageUrl(al.captured_img)}
                            alt="Captured"
                            style={{
                              width: 72,
                              height: 72,
                              borderRadius: 6,
                              objectFit: 'cover',
                              border: '1px solid rgba(255,255,255,0.1)'
                            }}
                            onError={(e) => {
                              e.target.style.display = 'none'
                              e.target.nextSibling.style.display = 'flex'
                            }}
                          />
                        ) : null}
                        <div
                          style={{
                            width: 72,
                            height: 72,
                            borderRadius: 6,
                            background: 'rgba(255,255,255,0.05)',
                            display: al.captured_img ? 'none' : 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: 24,
                            border: '1px solid rgba(255,255,255,0.05)'
                          }}
                        >
                          ⚠️
                        </div>

                        {/* Details */}
                        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
                          <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
                            <span
                              style={{
                                fontSize: 10,
                                fontWeight: 'bold',
                                textTransform: 'uppercase',
                                padding: '2px 6px',
                                borderRadius: 4,
                                background: style.badgeBg,
                                color: style.badgeColor
                              }}
                            >
                              {style.label}
                            </span>
                            <span style={{ fontSize: 11, color: 'var(--muted)' }}>
                              {al.created_at ? new Date(al.created_at).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : ''}
                            </span>
                          </div>

                          {al.student_code && (
                            <div style={{ fontSize: 13, color: 'var(--white)', fontWeight: 600 }}>
                              {al.full_name || 'Học viên'} ({al.student_code})
                            </div>
                          )}

                          {al.class_name && (
                            <div style={{ fontSize: 11, color: 'var(--white2)' }}>
                              Lớp: {al.class_name}
                            </div>
                          )}

                          <div style={{ fontSize: 11, color: 'var(--muted)', display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                            {al.confidence !== null && al.confidence !== undefined && (
                              <span>Độ tin cậy: {(al.confidence * 100).toFixed(0)}%</span>
                            )}
                            {al.liveness_score !== null && al.liveness_score !== undefined && (
                              <span>Liveness: {(al.liveness_score * 100).toFixed(0)}%</span>
                            )}
                            {al.gps_lat !== null && al.gps_lat !== undefined && (
                              <span>GPS: {al.gps_lat.toFixed(4)}, {al.gps_lng.toFixed(4)}</span>
                            )}
                          </div>
                        </div>

                        {/* Dismiss action */}
                        <button
                          className="secondary"
                          onClick={() => handleDismissAlert(al.id)}
                          style={{
                            alignSelf: 'center',
                            minHeight: 32,
                            padding: '0 10px',
                            fontSize: 12,
                            borderColor: 'rgba(255,255,255,0.15)',
                            background: 'rgba(255,255,255,0.02)',
                            color: 'var(--white2)'
                          }}
                          disabled={alertLoading}
                        >
                          Bỏ qua
                        </button>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>

            {/* Footer close button */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', borderTop: '1px solid var(--bdr)', paddingTop: 10 }}>
              <button
                className="secondary"
                onClick={() => setAlertModalTarget(null)}
                style={{ minHeight: 38 }}
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
