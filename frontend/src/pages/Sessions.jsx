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

  const loadSessions = async () => {
    try {
      const response = await api.get('/sessions/')
      setSessions(response.data)
    } catch (error) {
      setMessage(getApiErrorMessage(error, 'Không tải được danh sách buổi học.'))
    }
  }

  useEffect(() => {
    let mounted = true
    const load = async () => {
      try {
        const response = await api.get('/sessions/')
        if (mounted) setSessions(response.data)
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
    </div>
  )
}
