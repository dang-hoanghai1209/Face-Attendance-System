import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../../api/axios.js'
import { getApiErrorMessage } from '../utils/apiError.js'
import { VALID_CLASSES } from '../constants/classes.js'

const formatDateForDisplay = (isoDate) => {
  if (!isoDate) return ''
  const parts = isoDate.split('-')
  if (parts.length === 3) {
    return `${parts[2]}/${parts[1]}/${parts[0]}`
  }
  return isoDate
}

export default function CourseManagement() {
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState('classrooms')
  const [message, setMessage] = useState('')
  const [msgType, setMsgType] = useState('ok')
  const schedDateRef = useRef(null)

  const notify = useCallback((msg, type = 'ok') => {
    setMessage(msg)
    setMsgType(type)
  }, [])

  // ════════════════════════════════════════════════════════════════
  // 1. STATE & LOGIC CHO PHÒNG HỌC (CLASSROOMS)
  // ════════════════════════════════════════════════════════════════
  const [classrooms, setClassrooms] = useState([])
  const [crForm, setCrForm] = useState({ name: '', building: '', gps_lat: '', gps_lng: '', radius_meters: 15, is_active: true })
  const [crEditingId, setCrEditingId] = useState(null)
  const [crLoading, setCrLoading] = useState(false)

  const fetchClassrooms = useCallback(async () => {
    try {
      const res = await api.get('/classrooms/')
      setClassrooms(res.data)
    } catch (e) {
      notify(getApiErrorMessage(e, 'Không tải được danh sách phòng học.'), 'error')
    }
  }, [notify])

  const handleSaveClassroom = async () => {
    if (!crForm.name.trim() || !crForm.gps_lat || !crForm.gps_lng || !crForm.radius_meters) {
      notify('Vui lòng nhập đầy đủ thông tin phòng học và tọa độ GPS.', 'error')
      return
    }
    const payload = {
      name: crForm.name.trim(),
      building: crForm.building.trim() || null,
      gps_lat: parseFloat(crForm.gps_lat),
      gps_lng: parseFloat(crForm.gps_lng),
      radius_meters: parseFloat(crForm.radius_meters),
      is_active: crForm.is_active,
    }
    setCrLoading(true)
    try {
      if (crEditingId) {
        await api.put(`/classrooms/${crEditingId}`, payload)
        notify('Cập nhật phòng học thành công.')
      } else {
        await api.post('/classrooms/', payload)
        notify('Thêm phòng học thành công.')
      }
      setCrForm({ name: '', building: '', gps_lat: '', gps_lng: '', radius_meters: 15, is_active: true })
      setCrEditingId(null)
      fetchClassrooms()
    } catch (e) {
      notify(getApiErrorMessage(e, 'Không lưu được thông tin phòng học.'), 'error')
    } finally {
      setCrLoading(false)
    }
  }

  const handleEditClassroom = (cr) => {
    setCrEditingId(cr.id)
    setCrForm({
      name: cr.name,
      building: cr.building || '',
      gps_lat: cr.gps_lat,
      gps_lng: cr.gps_lng,
      radius_meters: cr.radius_meters,
      is_active: cr.is_active,
    })
    setMessage('')
  }

  const handleDeleteClassroom = async (id, name) => {
    if (!window.confirm(`Bạn có chắc muốn xóa phòng học "${name}" không?`)) return
    setCrLoading(true)
    try {
      await api.delete(`/classrooms/${id}`)
      notify('Đã xóa phòng học.')
      if (crEditingId === id) {
        setCrEditingId(null)
        setCrForm({ name: '', building: '', gps_lat: '', gps_lng: '', radius_meters: 15, is_active: true })
      }
      fetchClassrooms()
    } catch (e) {
      notify(getApiErrorMessage(e, 'Không xóa được phòng học (Có thể phòng đang có buổi học).'), 'error')
    } finally {
      setCrLoading(false)
    }
  }

  // ════════════════════════════════════════════════════════════════
  // 2. STATE & LOGIC CHO MÔN HỌC (SUBJECTS)
  // ════════════════════════════════════════════════════════════════
  const [subjects, setSubjects] = useState([])
  const [sbForm, setSbForm] = useState({ subject_code: '', subject_name: '', credits: 3, department: '' })
  const [sbEditingId, setSbEditingId] = useState(null)
  const [sbLoading, setSbLoading] = useState(false)

  const fetchSubjects = useCallback(async () => {
    try {
      const res = await api.get('/subjects/')
      setSubjects(res.data)
    } catch (e) {
      notify(getApiErrorMessage(e, 'Không tải được danh sách học phần.'), 'error')
    }
  }, [notify])

  const handleSaveSubject = async () => {
    if (!sbForm.subject_code.trim() || !sbForm.subject_name.trim()) {
      notify('Vui lòng nhập Mã học phần và Tên học phần.', 'error')
      return
    }
    const payload = {
      subject_code: sbForm.subject_code.trim(),
      subject_name: sbForm.subject_name.trim(),
      credits: sbForm.credits ? parseInt(sbForm.credits, 10) : null,
      department: sbForm.department.trim() || null,
    }
    setSbLoading(true)
    try {
      if (sbEditingId) {
        await api.put(`/subjects/${sbEditingId}`, payload)
        notify('Cập nhật học phần thành công.')
      } else {
        await api.post('/subjects/', payload)
        notify('Thêm học phần thành công.')
      }
      setSbForm({ subject_code: '', subject_name: '', credits: 3, department: '' })
      setSbEditingId(null)
      fetchSubjects()
    } catch (e) {
      notify(getApiErrorMessage(e, 'Không lưu được học phần.'), 'error')
    } finally {
      setSbLoading(false)
    }
  }

  const handleEditSubject = (sb) => {
    setSbEditingId(sb.id)
    setSbForm({
      subject_code: sb.subject_code,
      subject_name: sb.subject_name,
      credits: sb.credits || '',
      department: sb.department || '',
    })
    setMessage('')
  }

  const handleDeleteSubject = async (id, name) => {
    if (!window.confirm(`Bạn có chắc muốn xóa học phần "${name}" không?`)) return
    setSbLoading(true)
    try {
      await api.delete(`/subjects/${id}`)
      notify('Đã xóa học phần.')
      if (sbEditingId === id) {
        setSbEditingId(null)
        setSbForm({ subject_code: '', subject_name: '', credits: 3, department: '' })
      }
      fetchSubjects()
    } catch (e) {
      notify(getApiErrorMessage(e, 'Không xóa được học phần (Học phần này đang gắn với lớp học phần).'), 'error')
    } finally {
      setSbLoading(false)
    }
  }

  // ════════════════════════════════════════════════════════════════
  // 3. STATE & LOGIC CHO LỚP HỌC PHẦN & ENROLLMENTS (COURSE SECTIONS)
  // ════════════════════════════════════════════════════════════════
  const [sections, setSections] = useState([])
  const [secForm, setSecForm] = useState({ section_code: '', subject_id: '', class_name: '', section_group: '', semester: '', academic_year: '2025-2026', lecturer_name: '', status: 'open' })
  const [secEditingId, setSecEditingId] = useState(null)
  const [secLoading, setSecLoading] = useState(false)

  // Danh sách sinh viên thuộc Lớp học phần đang chọn
  const [selectedSecId, setSelectedSecId] = useState(null)
  const [enrollments, setEnrollments] = useState([])
  const [allStudents, setAllStudents] = useState([])
  const [enrollStudentId, setEnrollStudentId] = useState('')

  const fetchSections = useCallback(async () => {
    try {
      const res = await api.get('/course-sections/')
      setSections(res.data)
    } catch (e) {
      notify(getApiErrorMessage(e, 'Không tải được danh sách lớp học phần.'), 'error')
    }
  }, [notify])

  const fetchAllStudents = useCallback(async () => {
    try {
      const res = await api.get('/students/')
      setAllStudents(res.data)
    } catch (e) {
      console.error(e)
    }
  }, [])

  const fetchEnrollments = useCallback(async (secId) => {
    if (!secId) return
    try {
      const res = await api.get(`/course-sections/${secId}/students`)
      setEnrollments(res.data)
    } catch (e) {
      notify(getApiErrorMessage(e, 'Không tải được danh sách sinh viên xếp lớp.'), 'error')
    }
  }, [notify])

  const handleSaveSection = async () => {
    if (!secForm.class_name || !secForm.subject_id) {
      notify('Vui lòng chọn Lớp sinh viên và chọn Học phần.', 'error')
      return
    }
    const selectedSubject = subjects.find(sb => sb.id === parseInt(secForm.subject_id, 10))
    const resolvedSectionCode = selectedSubject ? selectedSubject.subject_code : ''

    const payload = {
      section_code: resolvedSectionCode,
      class_name: secForm.class_name,
      section_group: secForm.section_group ? secForm.section_group.trim() : null,
      subject_id: parseInt(secForm.subject_id, 10),
      semester: secForm.semester.trim() || null,
      academic_year: secForm.academic_year.trim() || null,
      lecturer_name: secForm.lecturer_name.trim() || null,
      status: secForm.status,
    }
    setSecLoading(true)
    try {
      if (secEditingId) {
        await api.put(`/course-sections/${secEditingId}`, payload)
        notify('Cập nhật lớp học phần thành công.')
      } else {
        await api.post('/course-sections/', payload)
        notify('Thêm lớp học phần thành công.')
      }
      setSecForm({ section_code: '', subject_id: '', class_name: '', section_group: '', semester: '', academic_year: '2025-2026', lecturer_name: '', status: 'open' })
      setSecEditingId(null)
      fetchSections()
    } catch (e) {
      notify(getApiErrorMessage(e, 'Không lưu được lớp học phần.'), 'error')
    } finally {
      setSecLoading(false)
    }
  }

  const handleEditSection = (sec) => {
    setSecEditingId(sec.id)
    setSecForm({
      section_code: sec.section_code,
      subject_id: sec.subject_id,
      class_name: sec.class_name || '',
      section_group: sec.section_group || '',
      semester: sec.semester || '',
      academic_year: sec.academic_year || '',
      lecturer_name: sec.lecturer_name || '',
      status: sec.status,
    })
    setMessage('')
  }

  const handleDeleteSection = async (id, code) => {
    if (!window.confirm(`Bạn có chắc muốn xóa lớp học phần "${code}" không? Tất cả buổi học, dữ liệu điểm danh và danh sách sinh viên xếp lớp liên quan sẽ bị xóa hoàn toàn.`)) return
    setSecLoading(true)
    try {
      await api.delete(`/course-sections/${id}`)
      notify('Đã xóa lớp học phần cùng các dữ liệu liên quan.')
      if (secEditingId === id) {
        setSecEditingId(null)
        setSecForm({ section_code: '', subject_id: '', class_name: '', semester: '', academic_year: '2025-2026', lecturer_name: '', status: 'open' })
      }
      if (selectedSecId === id) setSelectedSecId(null)
      fetchSections()
    } catch (e) {
      notify(getApiErrorMessage(e, 'Không xóa được lớp học phần.'), 'error')
    } finally {
      setSecLoading(false)
    }
  }

  const handleAddEnrollment = async () => {
    if (!selectedSecId) return
    if (!enrollStudentId) {
      notify('Vui lòng chọn một sinh viên để thêm vào lớp học phần.', 'error')
      return
    }
    setSecLoading(true)
    try {
      await api.post('/enrollments', {
        course_section_id: selectedSecId,
        student_id: parseInt(enrollStudentId, 10),
        status: 'active',
      })
      notify('Đã thêm sinh viên vào lớp học phần.')
      setEnrollStudentId('')
      fetchEnrollments(selectedSecId)
      fetchSections() // Cập nhật số lượng đếm sinh viên
    } catch (e) {
      notify(getApiErrorMessage(e, 'Không thêm được sinh viên vào lớp (Có thể đã tồn tại).'), 'error')
    } finally {
      setSecLoading(false)
    }
  }

  const handleRemoveEnrollment = async (enrollmentId) => {
    if (!window.confirm('Bạn có chắc muốn xóa sinh viên khỏi lớp học phần này?')) return
    setSecLoading(true)
    try {
      await api.delete(`/enrollments/${enrollmentId}`)
      notify('Đã xóa sinh viên khỏi lớp học phần.')
      fetchEnrollments(selectedSecId)
      fetchSections()
    } catch (e) {
      notify(getApiErrorMessage(e, 'Không xóa được đăng ký học phần.'), 'error')
    } finally {
      setSecLoading(false)
    }
  }

  // ════════════════════════════════════════════════════════════════
  // 4. STATE & LOGIC CHO XẾP BUỔI HỌC (SCHEDULE SESSIONS)
  // ════════════════════════════════════════════════════════════════
  const [schedForm, setSchedForm] = useState({ section_id: '', room_name: '', classroom_id: '', session_date: '', start_time: '', end_time: '', note: '', weeks: 1 })
  const [schedLoading, setSchedLoading] = useState(false)

  const getClassroomOptionLabel = (classroom) => {
    if (!classroom) return ''
    return classroom.building ? `${classroom.building} - ${classroom.name}` : classroom.name
  }

  const handleClassroomChange = (classroomId) => {
    const matched = classrooms.find(cr => cr.id === parseInt(classroomId, 10) && cr.is_active)
    setSchedForm(prev => ({
      ...prev,
      classroom_id: matched ? String(matched.id) : '',
      room_name: matched ? matched.name : ''
    }))
  }

  const selectedRoom = useMemo(() => {
    if (!schedForm.classroom_id) return null
    return classrooms.find(cr => cr.id === parseInt(schedForm.classroom_id, 10))
  }, [schedForm.classroom_id, classrooms])

  const handleScheduleSession = async () => {
    if (!schedForm.section_id || !schedForm.classroom_id || !schedForm.session_date || !schedForm.start_time || !schedForm.end_time) {
      notify('Vui lòng chọn phòng học đã lưu và điền đầy đủ các thông tin.', 'error')
      return
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(schedForm.session_date)) {
      notify('Ngày học không hợp lệ. Vui lòng chọn ngày từ lịch.', 'error')
      return
    }
    if (schedForm.end_time <= schedForm.start_time) {
      notify('Thời gian kết thúc phải sau giờ bắt đầu học.', 'error')
      return
    }

    const weeksVal = parseInt(schedForm.weeks, 10)
    if (isNaN(weeksVal) || weeksVal < 1 || weeksVal > 20) {
      notify('Số tuần học phải là số nguyên từ 1 đến 20.', 'error')
      return
    }

    const payload = {
      section_id: parseInt(schedForm.section_id, 10),
      classroom_id: parseInt(schedForm.classroom_id, 10),
      session_date: schedForm.session_date,
      start_time: schedForm.start_time + (schedForm.start_time.length === 5 ? ':00' : ''),
      end_time: schedForm.end_time + (schedForm.end_time.length === 5 ? ':00' : ''),
      note: schedForm.note.trim() || null,
      weeks: weeksVal,
    }
    setSchedLoading(true)
    try {
      await api.post('/sessions/from-section', payload)
      notify('Tạo chuỗi buổi học theo tuần thành công. Đang chuyển hướng...')
      setSchedForm({ section_id: '', room_name: '', classroom_id: '', session_date: '', start_time: '', end_time: '', note: '', weeks: 1 })
      setTimeout(() => {
        navigate('/sessions')
      }, 1500)
    } catch (e) {
      notify(getApiErrorMessage(e, 'Không tạo được buổi học.'), 'error')
    } finally {
      setSchedLoading(false)
    }
  }

  // ════════════════════════════════════════════════════════════════
  // FETCH DỮ LIỆU KHI CHUYỂN TAB
  // ════════════════════════════════════════════════════════════════
  useEffect(() => {
    setMessage('')
    if (activeTab === 'classrooms') {
      fetchClassrooms()
    } else if (activeTab === 'subjects') {
      fetchSubjects()
    } else if (activeTab === 'sections') {
      fetchSections()
      fetchSubjects()
      fetchAllStudents()
    } else if (activeTab === 'schedule') {
      fetchSections()
      fetchClassrooms()
    }
  }, [activeTab, fetchClassrooms, fetchSubjects, fetchSections, fetchAllStudents])

  // Xử lý xem enrollments của lớp học phần
  useEffect(() => {
    if (selectedSecId) {
      fetchEnrollments(selectedSecId)
    } else {
      setEnrollments([])
    }
  }, [selectedSecId, fetchEnrollments])

  // Lọc sinh viên chưa tham gia lớp học phần để tránh chọn trùng
  const availableStudents = useMemo(() => {
    const enrolledIds = new Set(enrollments.map((e) => e.student_id))
    return allStudents.filter((s) => !enrolledIds.has(s.id))
  }, [allStudents, enrollments])

  return (
    <div>
      <div className="page-header">
        <div>
          <p className="eyebrow">Quản lý đào tạo</p>
          <h1 className="page-title">Quản lý học phần và sắp lịch</h1>
          <p className="page-subtitle">Quản trị danh mục phòng học GPS, danh sách môn học, lớp học phần và xếp buổi điểm danh.</p>
        </div>
      </div>

      {/* Tabs Menu */}
      <div className="toolbar" style={{ marginBottom: 16 }}>
        <button className={activeTab === 'classrooms' ? '' : 'secondary'} onClick={() => setActiveTab('classrooms')}>
          📍 Phòng học
        </button>
        <button className={activeTab === 'subjects' ? '' : 'secondary'} onClick={() => setActiveTab('subjects')}>
          📖 Môn học
        </button>
        <button className={activeTab === 'sections' ? '' : 'secondary'} onClick={() => setActiveTab('sections')}>
          👥 Lớp học phần
        </button>
        <button className={activeTab === 'schedule' ? '' : 'secondary'} onClick={() => setActiveTab('schedule')}>
          📅 Xếp buổi học
        </button>
      </div>

      {message && (
        <p className={`status-message${msgType === 'error' ? ' error' : ''}`} style={{ marginBottom: 16 }}>
          {message}
        </p>
      )}

      {/* ==================== TAB 1: PHÒNG HỌC ==================== */}
      {activeTab === 'classrooms' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="panel panel-pad">
            <h3 style={{ marginTop: 0, marginBottom: 12 }}>{crEditingId ? 'Sửa phòng học' : 'Thêm phòng học mới'}</h3>
            <div className="form-grid" style={{ marginBottom: 12 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <input
                  placeholder="Tên phòng (vd: Phòng 101)"
                  value={crForm.name}
                  onChange={(e) => setCrForm({ ...crForm, name: e.target.value })}
                />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <input
                  placeholder="Building/Khu nhà (vd: Khu A)"
                  value={crForm.building}
                  onChange={(e) => setCrForm({ ...crForm, building: e.target.value })}
                />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <input
                  type="number"
                  step="any"
                  placeholder="Vĩ độ (GPS Lat)"
                  value={crForm.gps_lat}
                  onChange={(e) => setCrForm({ ...crForm, gps_lat: e.target.value })}
                />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <input
                  type="number"
                  step="any"
                  placeholder="Kinh độ (GPS Lng)"
                  value={crForm.gps_lng}
                  onChange={(e) => setCrForm({ ...crForm, gps_lng: e.target.value })}
                />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <input
                  type="number"
                  placeholder="Bán kính điểm danh (mét)"
                  value={crForm.radius_meters}
                  onChange={(e) => setCrForm({ ...crForm, radius_meters: e.target.value })}
                />
              </div>
            </div>
            <div className="toolbar">
              <button onClick={handleSaveClassroom} disabled={crLoading}>
                {crLoading ? 'Đang xử lý...' : crEditingId ? 'Cập nhật' : 'Thêm phòng học'}
              </button>
              {crEditingId && (
                <button
                  className="secondary"
                  onClick={() => {
                    setCrEditingId(null)
                    setCrForm({ name: '', building: '', gps_lat: '', gps_lng: '', radius_meters: 15, is_active: true })
                  }}
                >
                  Hủy
                </button>
              )}
            </div>
          </div>

          {/* Desktop Table View */}
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Tên phòng</th>
                  <th>Khu nhà</th>
                  <th>Tọa độ GPS (Vĩ độ, Kinh độ)</th>
                  <th>Bán kính</th>
                  <th>Trạng thái</th>
                  <th>Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {classrooms.length === 0 ? (
                  <tr>
                    <td colSpan={6} style={{ textAlign: 'center', color: 'var(--muted)', padding: 28 }}>
                      Chưa có phòng học nào được tạo.
                    </td>
                  </tr>
                ) : (
                  classrooms.map((cr) => (
                    <tr key={cr.id}>
                      <td style={{ fontWeight: 700 }}>{cr.name}</td>
                      <td>{cr.building || '-'}</td>
                      <td style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>
                        {cr.gps_lat.toFixed(6)}, {cr.gps_lng.toFixed(6)}
                      </td>
                      <td>{cr.radius_meters}m</td>
                      <td>
                        <span className={`badge ${cr.is_active ? 'success' : 'danger'}`}>
                          {cr.is_active ? 'Hoạt động' : 'Vô hiệu hóa'}
                        </span>
                      </td>
                      <td>
                        <div className="toolbar">
                          <button className="secondary" style={{ minHeight: 30 }} onClick={() => handleEditClassroom(cr)}>
                            Sửa
                          </button>
                          <button
                            style={{ minHeight: 30, background: 'rgba(244,63,94,.1)', color: 'var(--red)', border: '1px solid rgba(244,63,94,.2)' }}
                            onClick={() => handleDeleteClassroom(cr.id, cr.name)}
                          >
                            Xóa
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Mobile Card Layout */}
          <div className="mobile-card-list">
            {classrooms.map((cr) => (
              <div key={cr.id} className="mobile-card">
                <div className="mobile-card-header">
                  <span className="mobile-card-title">{cr.name}</span>
                  <span className={`badge ${cr.is_active ? 'success' : 'danger'}`}>
                    {cr.is_active ? 'Hoạt động' : 'Bị khóa'}
                  </span>
                </div>
                <div className="mobile-card-row">
                  <span className="mobile-card-label">Khu nhà:</span>
                  <span className="mobile-card-value">{cr.building || '-'}</span>
                </div>
                <div className="mobile-card-row">
                  <span className="mobile-card-label">GPS:</span>
                  <span className="mobile-card-value" style={{ fontFamily: 'var(--mono)' }}>
                    {cr.gps_lat.toFixed(6)}, {cr.gps_lng.toFixed(6)}
                  </span>
                </div>
                <div className="mobile-card-row">
                  <span className="mobile-card-label">Bán kính:</span>
                  <span className="mobile-card-value">{cr.radius_meters} mét</span>
                </div>
                <div className="mobile-card-actions">
                  <button className="secondary" onClick={() => handleEditClassroom(cr)}>
                    Sửa
                  </button>
                  <button
                    style={{ background: 'rgba(244,63,94,.1)', color: 'var(--red)', border: '1px solid rgba(244,63,94,.2)' }}
                    onClick={() => handleDeleteClassroom(cr.id, cr.name)}
                  >
                    Xóa
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ==================== TAB 2: MÔN HỌC ==================== */}
      {activeTab === 'subjects' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="panel panel-pad">
            <h3 style={{ marginTop: 0, marginBottom: 12 }}>{sbEditingId ? 'Sửa học phần' : 'Thêm học phần mới'}</h3>
            <div className="form-grid" style={{ marginBottom: 12 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <input
                  placeholder="Mã học phần (vd: CNTT301)"
                  value={sbForm.subject_code}
                  onChange={(e) => setSbForm({ ...sbForm, subject_code: e.target.value })}
                />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <input
                  placeholder="Tên môn học (vd: Kiểm thử phần mềm)"
                  value={sbForm.subject_name}
                  onChange={(e) => setSbForm({ ...sbForm, subject_name: e.target.value })}
                />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <input
                  type="number"
                  placeholder="Số tín chỉ"
                  value={sbForm.credits}
                  onChange={(e) => setSbForm({ ...sbForm, credits: e.target.value })}
                />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <input
                  placeholder="Khoa phụ trách (vd: CNTT)"
                  value={sbForm.department}
                  onChange={(e) => setSbForm({ ...sbForm, department: e.target.value })}
                />
              </div>
            </div>
            <div className="toolbar">
              <button onClick={handleSaveSubject} disabled={sbLoading}>
                {sbLoading ? 'Đang xử lý...' : sbEditingId ? 'Cập nhật' : 'Thêm môn học'}
              </button>
              {sbEditingId && (
                <button
                  className="secondary"
                  onClick={() => {
                    setSbEditingId(null)
                    setSbForm({ subject_code: '', subject_name: '', credits: 3, department: '' })
                  }}
                >
                  Hủy
                </button>
              )}
            </div>
          </div>

          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Mã học phần</th>
                  <th>Tên môn học</th>
                  <th>Số tín chỉ</th>
                  <th>Khoa phụ trách</th>
                  <th>Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {subjects.length === 0 ? (
                  <tr>
                    <td colSpan={5} style={{ textAlign: 'center', color: 'var(--muted)', padding: 28 }}>
                      Chưa có môn học nào được tạo.
                    </td>
                  </tr>
                ) : (
                  subjects.map((sb) => (
                    <tr key={sb.id}>
                      <td style={{ fontFamily: 'var(--mono)', fontWeight: 700, color: 'var(--teal)' }}>{sb.subject_code}</td>
                      <td style={{ fontWeight: 500 }}>{sb.subject_name}</td>
                      <td>{sb.credits || '-'}</td>
                      <td>{sb.department || '-'}</td>
                      <td>
                        <div className="toolbar">
                          <button className="secondary" style={{ minHeight: 30 }} onClick={() => handleEditSubject(sb)}>
                            Sửa
                          </button>
                          <button
                            style={{ minHeight: 30, background: 'rgba(244,63,94,.1)', color: 'var(--red)', border: '1px solid rgba(244,63,94,.2)' }}
                            onClick={() => handleDeleteSubject(sb.id, sb.subject_name)}
                          >
                            Xóa
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Mobile Card Layout */}
          <div className="mobile-card-list">
            {subjects.map((sb) => (
              <div key={sb.id} className="mobile-card">
                <div className="mobile-card-header">
                  <span className="mobile-card-title" style={{ color: 'var(--teal)', fontFamily: 'var(--mono)' }}>
                    {sb.subject_code}
                  </span>
                  <span style={{ fontSize: '13px', fontWeight: '600' }}>{sb.credits} tín chỉ</span>
                </div>
                <div className="mobile-card-row">
                  <span className="mobile-card-label">Tên môn học:</span>
                  <span className="mobile-card-value" style={{ textAlign: 'right' }}>{sb.subject_name}</span>
                </div>
                <div className="mobile-card-row">
                  <span className="mobile-card-label">Khoa phụ trách:</span>
                  <span className="mobile-card-value">{sb.department || '-'}</span>
                </div>
                <div className="mobile-card-actions">
                  <button className="secondary" onClick={() => handleEditSubject(sb)}>
                    Sửa
                  </button>
                  <button
                    style={{ background: 'rgba(244,63,94,.1)', color: 'var(--red)', border: '1px solid rgba(244,63,94,.2)' }}
                    onClick={() => handleDeleteSubject(sb.id, sb.subject_name)}
                  >
                    Xóa
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ==================== TAB 3: LỚP HỌC PHẦN ==================== */}
      {activeTab === 'sections' && (
        <div className={`management-grid ${selectedSecId ? 'active' : ''}`}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div className="panel panel-pad">
              <h3 style={{ marginTop: 0, marginBottom: 12 }}>{secEditingId ? 'Sửa lớp học phần' : 'Thêm lớp học phần'}</h3>
              <div className="form-grid" style={{ marginBottom: 12 }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase' }}>
                    Mã học phần / Môn học phần
                  </label>
                  <select value={secForm.subject_id} onChange={(e) => setSecForm({ ...secForm, subject_id: e.target.value })}>
                    <option value="">-- Chọn mã học phần --</option>
                    {subjects.map((sb) => (
                      <option key={sb.id} value={sb.id}>
                        {sb.subject_code} - {sb.subject_name}
                      </option>
                    ))}
                  </select>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase' }}>
                    Lớp sinh viên
                  </label>
                  <select value={secForm.class_name} onChange={(e) => setSecForm({ ...secForm, class_name: e.target.value })}>
                    <option value="">-- Chọn Lớp sinh viên --</option>
                    {VALID_CLASSES.map((className) => (
                      <option key={className} value={className}>
                        {className}
                      </option>
                    ))}
                  </select>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase' }}>
                    Nhóm học phần
                  </label>
                  <input
                    placeholder="Nhóm học phần (vd: 01, 02, N01)"
                    maxLength={30}
                    value={secForm.section_group}
                    onChange={(e) => setSecForm({ ...secForm, section_group: e.target.value })}
                  />
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase' }}>
                    Học kỳ
                  </label>
                  <input
                    placeholder="Học kỳ (vd: 2026-1)"
                    value={secForm.semester}
                    onChange={(e) => setSecForm({ ...secForm, semester: e.target.value })}
                  />
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase' }}>
                    Năm học
                  </label>
                  <input
                    placeholder="Năm học (vd: 2025-2026)"
                    value={secForm.academic_year}
                    onChange={(e) => setSecForm({ ...secForm, academic_year: e.target.value })}
                  />
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase' }}>
                    Tên Giảng viên
                  </label>
                  <input
                    placeholder="Tên Giảng viên"
                    value={secForm.lecturer_name}
                    onChange={(e) => setSecForm({ ...secForm, lecturer_name: e.target.value })}
                  />
                </div>
              </div>
              <div className="toolbar">
                <button onClick={handleSaveSection} disabled={secLoading}>
                  {secLoading ? 'Đang xử lý...' : secEditingId ? 'Cập nhật' : 'Tạo lớp HP'}
                </button>
                {secEditingId && (
                  <button
                    className="secondary"
                    onClick={() => {
                      setSecEditingId(null)
                      setSecForm({ section_code: '', subject_id: '', class_name: '', semester: '', academic_year: '2025-2026', lecturer_name: '', status: 'open' })
                    }}
                  >
                    Hủy
                  </button>
                )}
              </div>
            </div>

            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Mã HP</th>
                    <th>Nhóm</th>
                    <th>Lớp</th>
                    <th>Môn học</th>
                    <th>Học kỳ / Năm học</th>
                    <th>Giảng viên</th>
                    <th>Sĩ số</th>
                    <th>Tuần học</th>
                    <th>Thao tác</th>
                  </tr>
                </thead>
                <tbody>
                  {sections.length === 0 ? (
                    <tr>
                      <td colSpan={9} style={{ textAlign: 'center', color: 'var(--muted)', padding: 28 }}>
                        Chưa có lớp học phần nào được tạo.
                      </td>
                    </tr>
                  ) : (
                    sections.map((sec) => (
                      <tr
                        key={sec.id}
                        style={selectedSecId === sec.id ? { background: 'rgba(0,201,167,.06)' } : {}}
                      >
                        <td style={{ fontWeight: 700, color: 'var(--white)' }}>
                          <span style={{ cursor: 'pointer', textDecoration: 'underline' }} onClick={() => setSelectedSecId(sec.id)}>
                            {sec.section_code}
                          </span>
                        </td>
                        <td style={{ fontWeight: 600, color: 'var(--teal)' }}>
                          {sec.section_group || '-'}
                        </td>
                        <td>
                          <span style={{ fontFamily: 'var(--mono)', fontWeight: 600 }}>{sec.class_name || '-'}</span>
                        </td>
                        <td>
                          <div style={{ fontWeight: 500 }}>{sec.subject_name}</div>
                          <div style={{ fontSize: 11, color: 'var(--muted)' }}>{sec.subject_code}</div>
                        </td>
                        <td>
                          Học kỳ {sec.semester} ({sec.academic_year})
                        </td>
                        <td>{sec.lecturer_name || '-'}</td>
                        <td>
                          <span style={{ fontFamily: 'var(--mono)', fontWeight: 600 }}>{sec.student_count} sv</span>
                        </td>
                        <td style={{ fontFamily: 'var(--mono)', letterSpacing: '0.12em', fontSize: '13px', color: 'var(--white2)' }}>
                          {sec.weeks_str || '-'}
                        </td>
                        <td>
                          <div className="toolbar">
                            <button className="secondary" style={{ minHeight: 30 }} onClick={() => setSelectedSecId(sec.id)}>
                              Xếp lớp
                            </button>
                            <button className="secondary" style={{ minHeight: 30 }} onClick={() => handleEditSection(sec)}>
                              Sửa
                            </button>
                            <button
                              style={{ minHeight: 30, background: 'rgba(244,63,94,.1)', color: 'var(--red)', border: '1px solid rgba(244,63,94,.2)' }}
                              onClick={() => handleDeleteSection(sec.id, sec.section_code)}
                            >
                              Xóa
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Mobile Card Layout */}
            <div className="mobile-card-list">
              {sections.map((sec) => (
                <div key={sec.id} className="mobile-card" style={selectedSecId === sec.id ? { borderColor: 'var(--teal)', background: 'rgba(0,201,167,.03)' } : {}}>
                  <div className="mobile-card-header">
                    <span className="mobile-card-title">{sec.section_code}</span>
                    <span style={{ fontSize: '13px', fontWeight: '700' }}>{sec.student_count} SV</span>
                  </div>
                  <div className="mobile-card-row">
                    <span className="mobile-card-label">Nhóm:</span>
                    <span className="mobile-card-value" style={{ fontWeight: 600, color: 'var(--teal)' }}>{sec.section_group || '-'}</span>
                  </div>
                  <div className="mobile-card-row">
                    <span className="mobile-card-label">Lớp:</span>
                    <span className="mobile-card-value" style={{ fontFamily: 'var(--mono)', fontWeight: 600 }}>{sec.class_name || '-'}</span>
                  </div>
                  <div className="mobile-card-row">
                    <span className="mobile-card-label">Môn học:</span>
                    <span className="mobile-card-value" style={{ textAlign: 'right' }}>{sec.subject_name}</span>
                  </div>
                  <div className="mobile-card-row">
                    <span className="mobile-card-label">Học kỳ:</span>
                    <span className="mobile-card-value">{sec.semester} ({sec.academic_year})</span>
                  </div>
                  <div className="mobile-card-row">
                    <span className="mobile-card-label">Giảng viên:</span>
                    <span className="mobile-card-value">{sec.lecturer_name || '-'}</span>
                  </div>
                  <div className="mobile-card-row">
                    <span className="mobile-card-label">Tuần học:</span>
                    <span className="mobile-card-value" style={{ fontFamily: 'var(--mono)', letterSpacing: '0.12em' }}>{sec.weeks_str || '-'}</span>
                  </div>
                  <div className="mobile-card-actions">
                    <button className="secondary" onClick={() => setSelectedSecId(sec.id)}>
                      Xếp lớp
                    </button>
                    <button className="secondary" onClick={() => handleEditSection(sec)}>
                      Sửa
                    </button>
                    <button
                      style={{ background: 'rgba(244,63,94,.1)', color: 'var(--red)', border: '1px solid rgba(244,63,94,.2)' }}
                      onClick={() => handleDeleteSection(sec.id, sec.section_code)}
                    >
                      Xóa
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Sidebar danh sách sinh viên xếp lớp */}
          {selectedSecId && (
            <div className="panel panel-pad enrollment-sidebar" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h4 style={{ margin: 0 }}>Xếp lớp học phần</h4>
                <button className="secondary" style={{ minHeight: 28, padding: '4px 8px' }} onClick={() => setSelectedSecId(null)}>
                  Đóng
                </button>
              </div>

              <div>
                <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', display: 'block', marginBottom: 4 }}>
                  Thêm sinh viên vào lớp
                </label>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <select
                    style={{ width: '100%' }}
                    value={enrollStudentId}
                    onChange={(e) => setEnrollStudentId(e.target.value)}
                  >
                    <option value="">-- Chọn sinh viên --</option>
                    {availableStudents.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.student_code} - {s.full_name}
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={handleAddEnrollment}
                    disabled={secLoading}
                    style={{ width: '100%', justifyContent: 'center' }}
                  >
                    Thêm vào lớp
                  </button>
                </div>
              </div>

              <div style={{ borderTop: '1px solid var(--bdr)', paddingTop: 10 }}>
                <h5 style={{ margin: '0 0 8px 0', fontSize: 13, color: 'var(--white2)' }}>
                  Danh sách sinh viên ({enrollments.length})
                </h5>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: '350px', overflowY: 'auto' }}>
                  {enrollments.length === 0 ? (
                    <div style={{ color: 'var(--muted)', fontSize: 12, textAlign: 'center', padding: 14 }}>
                      Chưa xếp sinh viên vào lớp.
                    </div>
                  ) : (
                    enrollments.map((en) => (
                      <div
                        key={en.student_id}
                        style={{
                          background: 'rgba(255,255,255,.02)',
                          border: '1px solid var(--bdr)',
                          borderRadius: 'var(--r-sm)',
                          padding: '8px 10px',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                        }}
                      >
                        <div>
                          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--white)' }}>
                            {en.full_name}
                          </div>
                          <div style={{ fontSize: 11, color: 'var(--muted)' }}>
                            {en.student_code} ({en.class_name})
                          </div>
                        </div>
                        <button
                          style={{
                            minHeight: 28,
                            padding: '3px 8px',
                            background: 'rgba(244,63,94,.08)',
                            color: 'var(--red)',
                            border: '1px solid rgba(244,63,94,.15)',
                            fontSize: 11,
                          }}
                          onClick={() => handleRemoveEnrollment(en.enrollment_id)}
                        >
                          Xóa
                        </button>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ==================== TAB 4: XẾP BUỔI HỌC ==================== */}
      {activeTab === 'schedule' && (
        <div style={{ maxWidth: 650, margin: '0 auto' }}>
          <div className="panel panel-pad" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <h3 style={{ marginTop: 0, marginBottom: 8 }}>📅 Xếp lịch và tạo buổi điểm danh</h3>
            <p style={{ color: 'var(--muted)', fontSize: 13, marginTop: 0 }}>
              Tạo một buổi học điểm danh mới bằng cách liên kết Lớp học phần đang học và Phòng học đã cấu hình định vị GPS.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase' }}>
                  Lớp học phần
                </label>
                <select
                  value={schedForm.section_id}
                  onChange={(e) => setSchedForm({ ...schedForm, section_id: e.target.value })}
                >
                  <option value="">-- Chọn lớp học phần --</option>
                  {sections.map((sec) => (
                    <option key={sec.id} value={sec.id}>
                      {sec.section_code} - Nhóm {sec.section_group || '--'} - {sec.subject_name} - Lớp {sec.class_name || '-'}
                    </option>
                  ))}
                </select>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase' }}>
                  Phòng học
                </label>
                <select
                  value={schedForm.classroom_id}
                  onChange={(e) => handleClassroomChange(e.target.value)}
                >
                  <option value="">-- Chọn phòng học đã lưu --</option>
                  {classrooms.filter(cr => cr.is_active).map((cr) => (
                    <option key={cr.id} value={cr.id}>
                      {getClassroomOptionLabel(cr)}
                    </option>
                  ))}
                </select>
                {selectedRoom ? (
                  <div style={{ fontSize: 12, color: 'var(--teal)', marginTop: 2, display: 'flex', alignItems: 'center', gap: 4 }}>
                    <span>📍 GPS: {selectedRoom.gps_lat}, {selectedRoom.gps_lng} (Bán kính {selectedRoom.radius_meters}m)</span>
                  </div>
                ) : null}
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase' }}>
                  Ngày học (Ngày bắt đầu)
                </label>
                <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                  <input
                    type="text"
                    placeholder="Chọn ngày học từ lịch"
                    value={formatDateForDisplay(schedForm.session_date)}
                    readOnly
                    onClick={() => {
                      try {
                        schedDateRef.current?.showPicker();
                      } catch (e) {
                        try {
                          schedDateRef.current?.focus();
                          schedDateRef.current?.click();
                        } catch (err) {}
                      }
                    }}
                    style={{ paddingRight: '40px', width: '100%', cursor: 'pointer' }}
                  />
                  <button
                    type="button"
                    onClick={() => {
                      try {
                        schedDateRef.current?.showPicker();
                      } catch (e) {
                        try {
                          schedDateRef.current?.focus();
                          schedDateRef.current?.click();
                        } catch (err) {}
                      }
                    }}
                    style={{
                      position: 'absolute',
                      right: '10px',
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      padding: 0,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: 'var(--muted)',
                      minHeight: 'auto',
                      fontSize: '16px',
                      zIndex: 2
                    }}
                    title="Chọn ngày từ lịch"
                  >
                    📅
                  </button>
                  <input
                    type="date"
                    ref={schedDateRef}
                    value={schedForm.session_date || ''}
                    onChange={(e) => setSchedForm(prev => ({ ...prev, session_date: e.target.value }))}
                    style={{
                      position: 'absolute',
                      right: '10px',
                      width: '24px',
                      height: '24px',
                      opacity: 0,
                      pointerEvents: 'none',
                      zIndex: 1
                    }}
                  />
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase' }}>
                  Số tuần học liên tiếp
                </label>
                <input
                  type="number"
                  min="1"
                  max="20"
                  value={schedForm.weeks}
                  onChange={(e) => setSchedForm({ ...schedForm, weeks: e.target.value })}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase' }}>
                    Giờ bắt đầu
                  </label>
                  <input
                    type="time"
                    value={schedForm.start_time}
                    onChange={(e) => setSchedForm({ ...schedForm, start_time: e.target.value })}
                  />
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase' }}>
                    Giờ kết thúc
                  </label>
                  <input
                    type="time"
                    value={schedForm.end_time}
                    onChange={(e) => setSchedForm({ ...schedForm, end_time: e.target.value })}
                  />
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase' }}>
                  Ghi chú buổi học
                </label>
                <textarea
                  placeholder="Ghi chú buổi học tuần 1, kiểm tra..."
                  value={schedForm.note}
                  onChange={(e) => setSchedForm({ ...schedForm, note: e.target.value })}
                />
              </div>
            </div>

            <div className="toolbar" style={{ marginTop: 8 }}>
              <button
                onClick={handleScheduleSession}
                disabled={schedLoading}
                style={{ width: '100%', justifyContent: 'center', minHeight: 48 }}
              >
                {schedLoading ? 'Đang xếp lịch...' : 'Tạo buổi học chính thức'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
