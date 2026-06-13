import { useCallback, useEffect, useMemo, useState } from 'react'
import api from '../../api/axios.js'
import { VALID_CLASSES, classMatchesStudentCode } from '../constants/classes.js'
import { getApiErrorMessage } from '../utils/apiError.js'
import { dataSourceLabels, registrationMethodLabels } from '../utils/displayLabels.js'

const CODE_RE = /^(63|64)\d{6}$/
const SOURCE_LABELS = dataSourceLabels
const SOURCE_BADGES = { real: 'success', kaggle: 'warning', lfw: 'warning', evaluation: 'warning', demo: 'danger' }
const DATA_TABS = [
  { key: 'real', label: 'Sinh viên thật' },
  { key: 'evaluation', label: 'Dữ liệu đánh giá' },
  { key: 'demo', label: 'Dữ liệu demo' },
]

const emptyForm = { student_code: '', full_name: '', class_name: '' }
const emptyErrors = { student_code: '', full_name: '', class_name: '' }

function validateForm(form) {
  const errors = { ...emptyErrors }
  const code = form.student_code.trim()

  if (!code) {
    errors.student_code = 'Mã SV không được để trống.'
  } else if (!CODE_RE.test(code)) {
    errors.student_code = 'Mã SV phải bắt đầu bằng 63 hoặc 64, tiếp theo là đúng 6 chữ số (vd: 63133870).'
  }

  if (!form.full_name.trim()) errors.full_name = 'Họ tên không được để trống.'
  if (!form.class_name) {
    errors.class_name = 'Vui lòng chọn lớp.'
  } else if (CODE_RE.test(code) && !classMatchesStudentCode(code, form.class_name)) {
    errors.class_name = `Lớp ${form.class_name} không phù hợp với mã SV ${code}.`
  }
  return errors
}

const hasErrors = (errors) => Object.values(errors).some(Boolean)

const normalizeText = (value) => String(value || '').trim().toLowerCase()
const isLfwLikeStudent = (student) => {
  const source = normalizeText(student.data_source)
  const method = normalizeText(student.registration_method)
  const className = normalizeText(student.class_name)
  const fullName = normalizeText(student.full_name)
  const code = normalizeText(student.student_code)
  return (
    ['lfw', 'evaluation', 'kaggle'].includes(source) ||
    ['lfw_import', 'evaluation_import', 'lfw_folder_mean'].includes(method) ||
    className.includes('lfw') ||
    code.includes('lfw') ||
    fullName.includes('lfw')
  )
}

const isDemoLikeStudent = (student) => {
  if (isLfwLikeStudent(student)) return false
  const source = normalizeText(student.data_source)
  const method = normalizeText(student.registration_method)
  const fullName = normalizeText(student.full_name)
  return (
    student.is_demo === true ||
    source === 'demo' ||
    method.includes('demo') ||
    fullName.includes('demo') ||
    fullName.includes('mvp')
  )
}

const studentDataGroup = (student) => {
  if (isLfwLikeStudent(student)) return 'evaluation'
  if (isDemoLikeStudent(student)) return 'demo'
  return 'real'
}

const sortRealStudentsFirst = (left, right) => {
  const leftReady = left.face_status === 'registered' || left.registration_method === 'face_register'
  const rightReady = right.face_status === 'registered' || right.registration_method === 'face_register'
  if (leftReady !== rightReady) return leftReady ? -1 : 1
  return String(left.full_name || '').localeCompare(String(right.full_name || ''), 'vi')
}

function Field({ label, error, children }) {
  return (
    <div style={{ display:'flex', flexDirection:'column', gap:4 }}>
      <label style={{ fontSize:11, fontWeight:700, color:'var(--muted)', textTransform:'uppercase', letterSpacing:'.06em' }}>{label}</label>
      {children}
      {error && <span style={{ fontSize:11, color:'var(--red)', marginTop:2 }}>{error}</span>}
    </div>
  )
}

export default function Students() {
  const [students, setStudents] = useState([])
  const [form, setForm] = useState(emptyForm)
  const [errors, setErrors] = useState(emptyErrors)
  const [editingId, setEditingId] = useState(null)
  const [search, setSearch] = useState('')
  const [activeTab, setActiveTab] = useState('real')
  const [classFilter, setClassFilter] = useState('all')
  const [sourceFilter, setSourceFilter] = useState('all')
  const [faceFilter, setFaceFilter] = useState('all')
  const [message, setMessage] = useState('')
  const [msgType, setMsgType] = useState('')
  const [loading, setLoading] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState(null)

  const notify = useCallback((msg, type='ok') => {
    setMessage(msg)
    setMsgType(type)
  }, [])

  const fetchStudents = useCallback(async (isMounted = () => true) => {
    try {
      const r = await api.get('/students/')
      if (!isMounted()) return
      setStudents(r.data)
    } catch (e) {
      if (!isMounted()) return
      notify(getApiErrorMessage(e, 'Không tải được danh sách sinh viên.'), 'error')
    }
  }, [notify])

  useEffect(() => {
    let mounted = true
    queueMicrotask(() => {
      if (mounted) fetchStudents(() => mounted)
    })
    return () => {
      mounted = false
    }
  }, [fetchStudents])

  const filtered = useMemo(() => {
    const kw = search.trim().toLowerCase()
    return students.filter((s) => {
      const source = s.data_source || 'real'
      const faceStatus = s.face_status === 'registered' ? 'registered' : 'unregistered'
      const group = studentDataGroup(s)
      const matchesSearch = !kw ||
        s.student_code?.toLowerCase().includes(kw) ||
        s.full_name?.toLowerCase().includes(kw) ||
        s.class_name?.toLowerCase().includes(kw)
      const matchesTab = group === activeTab
      const matchesClass = classFilter === 'all' || s.class_name === classFilter
      const matchesSource = sourceFilter === 'all' || source === sourceFilter
      const matchesFace = faceFilter === 'all' || faceStatus === faceFilter
      return matchesTab && matchesSearch && matchesClass && matchesSource && matchesFace
    }).sort(activeTab === 'real'
      ? sortRealStudentsFirst
      : (left, right) => String(left.full_name || '').localeCompare(String(right.full_name || ''), 'vi'))
  }, [students, search, activeTab, classFilter, sourceFilter, faceFilter])

  const groupCounts = useMemo(() => {
    return students.reduce((counts, student) => {
      const group = studentDataGroup(student)
      counts[group] = (counts[group] || 0) + 1
      return counts
    }, { real: 0, evaluation: 0, demo: 0 })
  }, [students])

  const resetForm = () => {
    setForm(emptyForm)
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
      student_code: form.student_code.trim(),
      full_name: form.full_name.trim(),
      class_name: form.class_name
    }

    setLoading(true)
    try {
      if (editingId) {
        await api.put(`/students/${editingId}`, payload)
        notify('Đã cập nhật sinh viên thành công.')
      } else {
        await api.post('/students/', payload)
        notify('Đã thêm sinh viên thành công.')
      }
      resetForm()
      await fetchStudents()
    } catch (e) {
      notify(getApiErrorMessage(e, 'Không lưu được thông tin sinh viên.'), 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleEdit = (student) => {
    setEditingId(student.id)
    setForm({
      student_code: student.student_code || '',
      full_name: student.full_name || '',
      class_name: student.class_name || ''
    })
    setErrors(emptyErrors)
    setMessage('')
  }

  const handleDelete = (id, name) => {
    setDeleteTarget({ id, name })
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return

    setLoading(true)
    try {
      await api.delete(`/students/${deleteTarget.id}`)
      notify('Đã xóa sinh viên.')
      if (editingId === deleteTarget.id) resetForm()
      setDeleteTarget(null)
      await fetchStudents()
    } catch (e) {
      notify(getApiErrorMessage(e, 'Không xóa được sinh viên.'), 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <p className="eyebrow">Quản lý</p>
          <h1 className="page-title">Sinh viên</h1>
          <p className="page-subtitle">{students.length} sinh viên - {VALID_CLASSES.length} lớp - Mã sinh viên gồm tiền tố 63/64 và 6 chữ số</p>
        </div>
        <button onClick={fetchStudents} className="secondary" disabled={loading}>Tải lại dữ liệu</button>
      </div>

      <div className="panel panel-pad" style={{ marginBottom:14 }}>
        <div style={{ fontSize:13, fontWeight:700, marginBottom:12, color:'var(--white2)' }}>
          {editingId ? 'Cập nhật sinh viên' : 'Thêm sinh viên mới'}
        </div>
        <div className="form-grid" style={{ marginBottom:12 }}>
          <Field label="Mã sinh viên" error={errors.student_code}>
            <input
              placeholder="63xxxxxx hoặc 64xxxxxx"
              value={form.student_code}
              onChange={(e) => handleChange('student_code', e.target.value)}
              maxLength={8}
              style={errors.student_code ? { borderColor:'var(--red)' } : {}}
            />
          </Field>
          <Field label="Họ tên" error={errors.full_name}>
            <input
              placeholder="Họ và tên"
              value={form.full_name}
              onChange={(e) => handleChange('full_name', e.target.value)}
              style={errors.full_name ? { borderColor:'var(--red)' } : {}}
            />
          </Field>
          <Field label="Lớp" error={errors.class_name}>
            <select
              value={form.class_name}
              onChange={(e) => handleChange('class_name', e.target.value)}
              style={errors.class_name ? { borderColor:'var(--red)' } : {}}
            >
              <option value="">-- Chọn lớp --</option>
              {VALID_CLASSES.map((className) => <option key={className} value={className}>{className}</option>)}
            </select>
          </Field>
        </div>
        <div style={{ display:'flex', gap:8, flexWrap:'wrap', marginBottom:12 }}>
          {DATA_TABS.map((tab) => (
            <button
              key={tab.key}
              className={activeTab === tab.key ? '' : 'secondary'}
              onClick={() => setActiveTab(tab.key)}
              type="button"
              style={{ minHeight:34, padding:'6px 12px' }}
            >
              {tab.label} ({groupCounts[tab.key] || 0})
            </button>
          ))}
        </div>
        <div className="toolbar">
          <button onClick={handleSubmit} disabled={loading}>
            {loading ? 'Đang lưu...' : editingId ? 'Cập nhật' : 'Thêm'}
          </button>
          <button className="secondary" onClick={resetForm} disabled={loading}>Hủy</button>
          <input
            placeholder="Tìm theo mã, tên, lớp"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ marginLeft:'auto', minWidth:220 }}
          />
          <select value={classFilter} onChange={(e) => setClassFilter(e.target.value)} style={{ minWidth:140 }}>
            <option value="all">Tất cả lớp</option>
            {VALID_CLASSES.map((className) => <option key={className} value={className}>{className}</option>)}
          </select>
          <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)} style={{ minWidth:130 }}>
            <option value="all">Tất cả nguồn</option>
            <option value="real">Dữ liệu thật</option>
            <option value="lfw">Dữ liệu đánh giá LFW</option>
            <option value="evaluation">Dữ liệu đánh giá</option>
            <option value="kaggle">Dữ liệu đánh giá Kaggle</option>
            <option value="demo">Dữ liệu demo</option>
          </select>
          <select value={faceFilter} onChange={(e) => setFaceFilter(e.target.value)} style={{ minWidth:160 }}>
            <option value="all">Tất cả khuôn mặt</option>
            <option value="registered">Đã đăng ký</option>
            <option value="unregistered">Chưa đăng ký</option>
          </select>
        </div>
      </div>

      {message && (
        <p className={`status-message${msgType === 'error' ? ' error' : ''}`} style={{ marginBottom:12 }}>
          {message}
        </p>
      )}

      <div style={{ display:'flex', gap:10, marginBottom:14 }}>
        {[
          { label:'Tổng', val:students.length, color:'var(--teal)' },
          { label:'Đã đăng ký mặt', val:students.filter((s) => s.face_status === 'registered').length, color:'var(--blue)' },
          { label:'Chưa đăng ký', val:students.filter((s) => s.face_status !== 'registered').length, color:'var(--amber)' }
        ].map((card) => (
          <div key={card.label} style={{ background:'var(--card)', border:'1px solid var(--bdr)', borderRadius:'var(--r-sm)', padding:'8px 16px', display:'flex', alignItems:'center', gap:10 }}>
            <span style={{ fontFamily:'var(--mono)', fontSize:18, fontWeight:900, color:card.color }}>{card.val}</span>
            <span style={{ fontSize:12, color:'var(--muted)' }}>{card.label}</span>
          </div>
        ))}
      </div>

      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>{['Mã SV','Họ tên','Lớp','Nguồn dữ liệu','Khuôn mặt','Thao tác'].map((header) => <th key={header}>{header}</th>)}</tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={6} style={{ textAlign:'center', color:'var(--muted)', padding:28 }}>
                  {search ? 'Không tìm thấy sinh viên phù hợp.' : 'Chưa có sinh viên nào.'}
                </td>
              </tr>
            ) : filtered.map((student) => {
              const group = studentDataGroup(student)
              const source = student.data_source || 'real'
              const effectiveSource = group === 'evaluation' && source === 'real'
                ? 'evaluation'
                : group === 'demo' && source === 'real'
                  ? 'demo'
                  : source
              return (
                <tr key={student.id}>
                  <td><span style={{ fontFamily:'var(--mono)', fontSize:12, color:'var(--teal)' }}>{student.student_code}</span></td>
                  <td style={{ fontWeight:500 }}>{student.full_name}</td>
                  <td>
                    <span style={{ fontFamily:'var(--mono)', fontSize:12, padding:'2px 8px', borderRadius:6, background:'var(--card2)', color:'var(--white2)' }}>{student.class_name || '-'}</span>
                  </td>
                  <td>
                    <span className={`badge ${SOURCE_BADGES[effectiveSource] || 'danger'}`}>
                      {SOURCE_LABELS[effectiveSource] || effectiveSource}
                    </span>
                    {group === 'evaluation' && (
                      <span className="badge danger" style={{ marginLeft:6 }}>
                        Không dùng cho điểm danh thật
                      </span>
                    )}
                    {group === 'demo' && (
                      <span className="badge warning" style={{ marginLeft:6 }}>
                        Demo/test
                      </span>
                    )}
                    {student.registration_method && (
                      <div style={{ marginTop:4, fontSize:11, color:'var(--muted)' }}>
                        {registrationMethodLabels[student.registration_method] || student.registration_method}
                      </div>
                    )}
                  </td>
                  <td>
                    <span className={`badge ${student.face_status === 'registered' ? 'success' : 'warning'}`}>
                      {student.face_status === 'registered' ? 'Đã đăng ký' : 'Chưa đăng ký'}
                    </span>
                  </td>
                  <td>
                    <div className="toolbar">
                      <button className="secondary" style={{ minHeight:30, padding:'4px 12px', fontSize:12 }} onClick={() => handleEdit(student)} disabled={loading}>Sửa</button>
                      <button style={{ minHeight:30, padding:'4px 12px', fontSize:12, background:'rgba(244,63,94,.1)', border:'1px solid rgba(244,63,94,.25)', color:'var(--red)' }} onClick={() => handleDelete(student.id, student.full_name)} disabled={loading}>Xóa</button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Mobile Card Layout */}
      <div className="mobile-card-list">
        {filtered.length === 0 ? (
          <div className="empty-state">
            {search ? 'Không tìm thấy sinh viên phù hợp.' : 'Chưa có sinh viên nào.'}
          </div>
        ) : (
          filtered.map((student) => {
            const group = studentDataGroup(student)
            const source = student.data_source || 'real'
            const effectiveSource = group === 'evaluation' && source === 'real'
              ? 'evaluation'
              : group === 'demo' && source === 'real'
                ? 'demo'
                : source
            return (
              <div key={student.id} className="mobile-card">
                <div className="mobile-card-header">
                  <span className="mobile-card-title" style={{ color: 'var(--teal)', fontFamily: 'var(--mono)', fontSize: '14px', fontWeight: 700 }}>
                    {student.student_code}
                  </span>
                  <span className={`badge ${student.face_status === 'registered' ? 'success' : 'warning'}`}>
                    {student.face_status === 'registered' ? 'Đã đăng ký' : 'Chưa đăng ký'}
                  </span>
                </div>
                <div className="mobile-card-row">
                  <span className="mobile-card-label">Họ tên:</span>
                  <span className="mobile-card-value">{student.full_name}</span>
                </div>
                <div className="mobile-card-row">
                  <span className="mobile-card-label">Lớp:</span>
                  <span className="mobile-card-value" style={{ fontFamily: 'var(--mono)' }}>{student.class_name || '-'}</span>
                </div>
                <div className="mobile-card-row">
                  <span className="mobile-card-label">Nguồn:</span>
                  <span className={`badge ${SOURCE_BADGES[effectiveSource] || 'danger'}`}>
                    {SOURCE_LABELS[effectiveSource] || effectiveSource}
                  </span>
                </div>
                {group === 'evaluation' && (
                  <div className="mobile-card-row">
                    <span className="mobile-card-label">Ghi chú:</span>
                    <span className="badge danger">Không dùng cho điểm danh thật</span>
                  </div>
                )}
                {group === 'demo' && (
                  <div className="mobile-card-row">
                    <span className="mobile-card-label">Ghi chú:</span>
                    <span className="badge warning">Demo/test</span>
                  </div>
                )}
                <div className="mobile-card-actions">
                  <button className="secondary" onClick={() => handleEdit(student)} disabled={loading}>
                    Sửa
                  </button>
                  <button
                    style={{ background: 'rgba(244,63,94,.1)', color: 'var(--red)', border: '1px solid rgba(244,63,94,.2)' }}
                    onClick={() => handleDelete(student.id, student.full_name)}
                    disabled={loading}
                  >
                    Xóa
                  </button>
                </div>
              </div>
            )
          })
        )}
      </div>

      {deleteTarget && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="delete-student-title"
          style={{
            position:'fixed',
            inset:0,
            background:'rgba(0,0,0,.58)',
            display:'flex',
            alignItems:'center',
            justifyContent:'center',
            zIndex:1000,
            padding:16
          }}
        >
          <div style={{ width:'min(460px, 100%)', background:'var(--navy2)', border:'1px solid var(--bdr2)', borderRadius:12, padding:20, boxShadow:'var(--shadow)' }}>
            <h2 id="delete-student-title" style={{ margin:'0 0 8px', fontSize:18, color:'var(--white)' }}>Xóa sinh viên</h2>
            <p style={{ margin:'0 0 16px', color:'var(--white2)', lineHeight:1.55 }}>
              Bạn có chắc muốn xóa sinh viên <strong style={{ color:'var(--white)' }}>{deleteTarget.name}</strong>? Dữ liệu điểm danh và khuôn mặt liên quan cũng sẽ bị xóa.
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
