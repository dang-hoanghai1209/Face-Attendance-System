import { useEffect, useMemo, useRef, useState } from 'react'

import api from '../../api/axios.js'
import { useAuth } from '../auth/auth-context.js'
import { VALID_CLASSES } from '../constants/classes.js'
import { getApiErrorMessage } from '../utils/apiError.js'

// ------------------------------------------------------------------ //
// Hằng số
// ------------------------------------------------------------------ //
const initialForm = {
  subject:      '',
  class_name:   '',
  section_group: '',
  session_date: '',
  start_time:   '',
  end_time:     '',
}
const initialModalForm = {
  ...initialForm,
  classroom_id: '',
  latitude: '',
  longitude: '',
  radius_meters: '',
  room_name: '',
  note: '',
}
const emptyErrors = {
  subject:    '',
  class_name: '',
  section_group: '',
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
const formatDateForDisplay = (dateStr) => {
  if (!dateStr) return ''
  if (/^\d{2}\/\d{2}\/\d{4}$/.test(dateStr)) return dateStr
  const parts = dateStr.split('-')
  if (parts.length === 3) {
    return `${parts[2]}/${parts[1]}/${parts[0]}`
  }
  return dateStr
}
const formatDateStr = formatDateForDisplay

const getSessionDateValue = (session) => session.session_date || session.date || ''
const getSessionSubjectValue = (session) => session.subject_name || session.subject || ''
const getSessionCodeValue = (session) => (
  session.section_code ||
  session.subject_code ||
  session.course_section?.section_code ||
  session.course_section?.subject_code ||
  session.subject?.subject_code ||
  ''
)

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
  const t = (type || '').toUpperCase()
  if (t === 'SPOOF') {
    return {
      border: '1px solid rgba(239, 68, 68, 0.3)',
      background: 'rgba(239, 68, 68, 0.06)',
      color: '#fca5a5',
      badgeBg: 'rgba(239, 68, 68, 0.15)',
      badgeColor: '#ef4444',
      label: 'Giả mạo khuôn mặt (SPOOF)'
    }
  }
  if (t === 'UNKNOWN_FACE' || t === 'UNKNOWN') {
    return {
      border: '1px solid rgba(249, 115, 22, 0.3)',
      background: 'rgba(249, 115, 22, 0.06)',
      color: '#ffedd5',
      badgeBg: 'rgba(249, 115, 22, 0.15)',
      badgeColor: '#f97316',
      label: 'Khuôn mặt lạ (UNKNOWN)'
    }
  }
  if (t === 'FACE_UNCLEAR') {
    return {
      border: '1px solid rgba(245, 158, 11, 0.3)',
      background: 'rgba(245, 158, 11, 0.06)',
      color: '#fef3c7',
      badgeBg: 'rgba(245, 158, 11, 0.15)',
      badgeColor: '#f59e0b',
      label: 'Khuôn mặt chưa rõ (FACE_UNCLEAR)'
    }
  }
  if (t === 'NOT_ENROLLED') {
    return {
      border: '1px solid rgba(168, 85, 247, 0.3)',
      background: 'rgba(168, 85, 247, 0.06)',
      color: '#f3e8ff',
      badgeBg: 'rgba(168, 85, 247, 0.15)',
      badgeColor: '#a855f7',
      label: 'Không thuộc lớp HP (NOT_ENROLLED)'
    }
  }
  if (t === 'GPS_FAILED' || t === 'GPS_OUT_OF_RANGE') {
    return {
      border: '1px solid rgba(59, 130, 246, 0.3)',
      background: 'rgba(59, 130, 246, 0.06)',
      color: '#dbeafe',
      badgeBg: 'rgba(59, 130, 246, 0.15)',
      badgeColor: '#3b82f6',
      label: t === 'GPS_OUT_OF_RANGE' ? 'GPS ngoài bán kính' : 'Lỗi định vị GPS'
    }
  }
  if (t === 'LATE_ENTRY') {
    return {
      border: '1px solid rgba(59, 130, 246, 0.3)',
      background: 'rgba(59, 130, 246, 0.06)',
      color: '#dbeafe',
      badgeBg: 'rgba(59, 130, 246, 0.15)',
      badgeColor: '#3b82f6',
      label: 'Đi học muộn (LATE_ENTRY)'
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

const parseNoteSafely = (note) => {
  if (!note) return null
  try {
    if (typeof note === 'string') {
      const parsed = JSON.parse(note)
      if (parsed && typeof parsed === 'object') return parsed
    }
  } catch (e) {}
  return null
}

const renderConfidence = (alert) => {
  let confidenceVal = alert.confidence
  let label = 'Độ tin cậy'
  
  const type = (alert.alert_type || '').toUpperCase()
  if (type === 'FACE_UNCLEAR') {
    label = 'Độ tin cậy phát hiện khuôn mặt'
    const parsed = parseNoteSafely(alert.note)
    if ((confidenceVal === null || confidenceVal === undefined) && parsed && parsed.detection_confidence !== undefined) {
      confidenceVal = parsed.detection_confidence
    }
  } else if (type === 'UNKNOWN_FACE' || type === 'UNKNOWN') {
    label = 'Độ tin cậy khớp danh tính'
  } else if (type === 'SPOOF') {
    label = 'Độ tin cậy cảnh báo'
  }

  if (confidenceVal === null || confidenceVal === undefined) return null
  return (
    <span>
      {label}: {(confidenceVal * 100).toFixed(0)}%
    </span>
  )
}

const AlertImage = ({ path }) => {
  const [hasError, setHasError] = useState(false)
  const url = getImageUrl(path)
  
  if (hasError || !url) {
    return (
      <div
        style={{
          width: 72,
          height: 72,
          borderRadius: 6,
          background: 'rgba(244,63,94,0.08)',
          border: '1px solid rgba(244,63,94,0.2)',
          color: '#fb7185',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 10,
          textAlign: 'center',
          padding: 4
        }}
      >
        Không tải được ảnh
      </div>
    )
  }
  
  return (
    <img
      src={url}
      alt="Captured alert"
      style={{
        width: 72,
        height: 72,
        borderRadius: 6,
        objectFit: 'cover',
        border: '1px solid rgba(255,255,255,0.1)',
        cursor: 'pointer'
      }}
      onClick={() => window.open(url, '_blank', 'noopener,noreferrer')}
      onError={() => setHasError(true)}
    />
  )
}

// ------------------------------------------------------------------ //
// Helpers for Session Status
// ------------------------------------------------------------------ //
const getSessionStatus = (session) => {
  const sessionDate = getSessionDateValue(session)
  if (!sessionDate || !session.start_time || !session.end_time) {
    return { label: 'Không rõ', badgeClass: 'badge' }
  }
  const now = new Date()
  const [year, month, day] = sessionDate.split('-').map(Number)
  const parseTime = (timeStr) => {
    const parts = timeStr.split(':').map(Number)
    return { h: parts[0] || 0, m: parts[1] || 0 }
  }
  const startParts = parseTime(session.start_time)
  const endParts = parseTime(session.end_time)
  const start = new Date(year, month - 1, day, startParts.h, startParts.m, 0)
  const end = new Date(year, month - 1, day, endParts.h, endParts.m, 0)

  if (now < start) {
    return { label: 'Sắp diễn ra', badgeClass: 'badge info' }
  } else if (now > end) {
    return { label: 'Đã kết thúc', badgeClass: 'badge muted' }
  } else {
    return { label: 'Đang diễn ra', badgeClass: 'badge success' }
  }
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

const groupSessionsBySection = (sessionsList) => {
  const groups = new Map()

  sessionsList.forEach((session) => {
    const key = getSessionGroupKey(session)
    if (!groups.has(key)) {
      groups.set(key, {
        key,
        section_id: session.section_id ?? null,
        section_code: getSessionCodeValue(session),
        subject_name: getSessionSubjectValue(session),
        section_group: session.section_group || '',
        class_name: session.class_name || '',
        sessions: [],
      })
    }
    groups.get(key).sessions.push(session)
  })

  return Array.from(groups.values()).sort((a, b) => {
    const left = `${a.section_code} ${a.subject_name} ${a.section_group} ${a.class_name}`
    const right = `${b.section_code} ${b.subject_name} ${b.section_group} ${b.class_name}`
    return left.localeCompare(right, 'vi')
  })
}

// ------------------------------------------------------------------ //
// Component
// ------------------------------------------------------------------ //
export default function Sessions() {
  const { user } = useAuth()
  const [sessions,  setSessions]  = useState([])
  const [form,      setForm]      = useState(initialForm)
  const [errors,    setErrors]    = useState(emptyErrors)
  const [editingId, setEditingId] = useState(null)
  const editDateRef = useRef(null)
  const [search,    setSearch]    = useState('')
  const [message,   setMessage]   = useState('')
  const [loading,   setLoading]   = useState(false)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [subjects, setSubjects] = useState([])
  const [classrooms, setClassrooms] = useState([])
  const [editModalTarget, setEditModalTarget] = useState(null)
  const [editModalForm, setEditModalForm] = useState(initialModalForm)
  const [editModalErrors, setEditModalErrors] = useState(emptyErrors)
  const [editModalMessage, setEditModalMessage] = useState('')
  const [editModalSaving, setEditModalSaving] = useState(false)

  // State variables for course section grouping
  const [viewMode, setViewMode] = useState('grouped')
  const [selectedGroupKey, setSelectedGroupKey] = useState(null)
  const [drawerFilter, setDrawerFilter] = useState('all')

  const getGroupMetrics = (group) => {
    let ongoing = 0;
    let upcoming = 0;
    let finished = 0;
    group.sessions.forEach((s) => {
      const status = getSessionStatus(s);
      if (status.label === 'Đang diễn ra') ongoing++;
      else if (status.label === 'Sắp diễn ra') upcoming++;
      else if (status.label === 'Đã kết thúc') finished++;
    });
    return { ongoing, upcoming, finished, total: group.sessions.length };
  };

  const sortSessionsForDetail = (sessionsList) => {
    const getSessionDateTime = (s) => {
      const sessionDate = getSessionDateValue(s)
      if (!sessionDate || !s.start_time) return new Date(0);
      const [year, month, day] = sessionDate.split('-').map(Number);
      const [h, m] = s.start_time.split(':').map(Number);
      return new Date(year, month - 1, day, h, m, 0);
    };

    return [...sessionsList].sort((a, b) => {
      const statusA = getSessionStatus(a).label;
      const statusB = getSessionStatus(b).label;

      const priority = {
        'Đang diễn ra': 1,
        'Sắp diễn ra': 2,
        'Đã kết thúc': 3,
        'Không rõ': 4
      };

      const pA = priority[statusA] || 4;
      const pB = priority[statusB] || 4;

      if (pA !== pB) {
        return pA - pB;
      }

      const timeA = getSessionDateTime(a).getTime();
      const timeB = getSessionDateTime(b).getTime();

      if (statusA === 'Sắp diễn ra') {
        return timeA - timeB;
      } else if (statusA === 'Đã kết thúc') {
        return timeB - timeA;
      }
      return timeA - timeB;
    });
  };

  const groupedSessions = useMemo(() => {
    return groupSessionsBySection(sessions);
  }, [sessions]);

  const filteredGroupedSessions = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    if (!keyword) return groupedSessions;
    return groupedSessions.filter((g) =>
      g.subject_name.toLowerCase().includes(keyword) ||
      g.section_code.toLowerCase().includes(keyword) ||
      g.section_group.toLowerCase().includes(keyword) ||
      g.class_name.toLowerCase().includes(keyword)
    );
  }, [groupedSessions, search]);

  const selectedGroup = useMemo(() => {
    if (!selectedGroupKey) return null;
    return groupedSessions.find(g => g.key === selectedGroupKey) || null;
  }, [groupedSessions, selectedGroupKey]);

  const selectedGroupTitle = useMemo(() => {
    if (!selectedGroup) return ''
    return [
      selectedGroup.section_code,
      selectedGroup.subject_name,
      selectedGroup.section_group ? `Nhóm ${selectedGroup.section_group}` : '',
      selectedGroup.class_name ? `Lớp ${selectedGroup.class_name}` : '',
    ].filter(Boolean).join(' - ')
  }, [selectedGroup])

  const displaySessions = useMemo(() => {
    if (!selectedGroup) return [];
    const sorted = sortSessionsForDetail(selectedGroup.sessions);
    return sorted.filter((s) => {
      if (drawerFilter === 'all') return true;
      const statusLabel = getSessionStatus(s).label;
      if (drawerFilter === 'ongoing') return statusLabel === 'Đang diễn ra';
      if (drawerFilter === 'upcoming') return statusLabel === 'Sắp diễn ra';
      if (drawerFilter === 'finished') return statusLabel === 'Đã kết thúc';
      return true;
    });
  }, [selectedGroup, drawerFilter]);

  const activeClassrooms = useMemo(() => (
    classrooms.filter((classroom) => classroom.is_active)
  ), [classrooms])

  const selectedEditModalRoom = useMemo(() => {
    if (!editModalForm.classroom_id) return null
    return classrooms.find((classroom) => classroom.id === parseInt(editModalForm.classroom_id, 10)) || null
  }, [editModalForm.classroom_id, classrooms])

  const getClassroomOptionLabel = (classroom) => {
    if (!classroom) return ''
    return classroom.building ? `${classroom.building} - ${classroom.name}` : classroom.name
  }

  const openGroupDetails = (groupKey) => {
    setDrawerFilter('all')
    setSelectedGroupKey(groupKey)
  }

  // Alert states
  const [alertCounts,       setAlertCounts]       = useState({})
  const [alertModalTarget,  setAlertModalTarget]  = useState(null)
  const [activeAlerts,      setActiveAlerts]      = useState([])
  const [alertLoading,      setAlertLoading]      = useState(false)
  const [alertMessage,      setAlertMessage]      = useState('')
  const [alertFilter,       setAlertFilter]       = useState('active')
  const [exportingSessionId, setExportingSessionId] = useState(null)
  const [exportType,         setExportType]         = useState(null)

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
      loadAlertsSilent(alertModalTarget.id, alertFilter)
    }, 5000)
    return () => clearInterval(id)
  }, [alertModalTarget, alertFilter])

  const loadSessions = async () => {
    try {
      const [resSessions, resSubjects, resClassrooms] = await Promise.all([
        api.get('/sessions/'),
        api.get('/subjects/'),
        api.get('/classrooms/')
      ])
      setSessions(resSessions.data)
      setSubjects(resSubjects.data)
      setClassrooms(resClassrooms.data)
      loadAlertCounts(resSessions.data)
    } catch (error) {
      setMessage(getApiErrorMessage(error, 'Không tải được danh sách dữ liệu.'))
    }
  }

  useEffect(() => {
    let mounted = true
    const load = async () => {
      try {
        const [resSessions, resSubjects, resClassrooms] = await Promise.all([
          api.get('/sessions/'),
          api.get('/subjects/'),
          api.get('/classrooms/')
        ])
        if (mounted) {
          setSessions(resSessions.data)
          setSubjects(resSubjects.data)
          setClassrooms(resClassrooms.data)
          loadAlertCounts(resSessions.data)
        }
      } catch (error) {
        if (mounted) setMessage(getApiErrorMessage(error, 'Không tải được danh sách dữ liệu.'))
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
      getSessionSubjectValue(s).toLowerCase().includes(keyword) ||
      getSessionCodeValue(s).toLowerCase().includes(keyword) ||
      s.class_name?.toLowerCase().includes(keyword) ||
      s.section_group?.toLowerCase().includes(keyword) ||
      getSessionDateValue(s).includes(keyword)
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

  const handleEditModalChange = (field, value) => {
    setEditModalForm((prev) => ({ ...prev, [field]: value }))
    setEditModalErrors((prev) => ({ ...prev, [field]: '' }))
    setEditModalMessage('')
  }

  const buildSessionPayload = (source) => {
    const payload = {
      subject:      source.subject.trim(),
      class_name:   source.class_name,
      section_group: source.section_group ? source.section_group.trim() : null,
      session_date: source.session_date,
      start_time:   source.start_time,
      end_time:     source.end_time,
      created_by:   null,
    }
    if (Object.prototype.hasOwnProperty.call(source, 'room_name')) {
      payload.room_name = source.room_name ? source.room_name.trim() : null
    }
    if (Object.prototype.hasOwnProperty.call(source, 'classroom_id')) {
      payload.classroom_id = source.classroom_id ? Number(source.classroom_id) : null
    }
    if (Object.prototype.hasOwnProperty.call(source, 'latitude')) {
      payload.latitude = source.latitude !== '' && source.latitude !== null && source.latitude !== undefined
        ? Number(source.latitude)
        : null
    }
    if (Object.prototype.hasOwnProperty.call(source, 'longitude')) {
      payload.longitude = source.longitude !== '' && source.longitude !== null && source.longitude !== undefined
        ? Number(source.longitude)
        : null
    }
    if (Object.prototype.hasOwnProperty.call(source, 'radius_meters')) {
      payload.radius_meters = source.radius_meters !== '' && source.radius_meters !== null && source.radius_meters !== undefined
        ? Number(source.radius_meters)
        : null
    }
    if (Object.prototype.hasOwnProperty.call(source, 'note')) {
      payload.note = source.note ? source.note.trim() : null
    }
    return payload
  }

  const validateSessionForm = (source, setErrorState) => {
    const validationErrors = validateForm(source)
    if (hasErrors(validationErrors)) {
      setErrorState(validationErrors)
      return false
    }

    if (!/^\d{4}-\d{2}-\d{2}$/.test(source.session_date)) {
      setErrorState((prev) => ({ ...prev, session_date: 'Ngày học không hợp lệ. Vui lòng chọn ngày từ lịch.' }))
      return false
    }
    return true
  }

  const handleSubmit = async () => {
    if (!validateSessionForm(form, setErrors)) return

    const payload = buildSessionPayload(form)

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
      subject:      getSessionSubjectValue(session),
      class_name:   session.class_name   || '',
      section_group: session.section_group || '',
      session_date: session.session_date || '',
      start_time:   toTimeInput(session.start_time),
      end_time:     toTimeInput(session.end_time),
    })
    setErrors(emptyErrors)
    setMessage('')
  }

  const openEditModal = (session) => {
    setEditModalTarget(session)
    setEditModalForm({
      subject: getSessionSubjectValue(session),
      class_name: session.class_name || '',
      section_group: session.section_group || '',
      session_date: getSessionDateValue(session),
      start_time: toTimeInput(session.start_time),
      end_time: toTimeInput(session.end_time),
      classroom_id: session.classroom_id ? String(session.classroom_id) : '',
      latitude: session.latitude ?? '',
      longitude: session.longitude ?? '',
      radius_meters: session.radius_meters ?? '',
      room_name: session.room_name || '',
      note: session.note || '',
    })
    setEditModalErrors(emptyErrors)
    setEditModalMessage('')
  }

  const closeEditModal = () => {
    setEditModalTarget(null)
    setEditModalForm(initialModalForm)
    setEditModalErrors(emptyErrors)
    setEditModalMessage('')
  }

  const handleEditModalClassroomChange = (classroomId) => {
    const selectedClassroom = activeClassrooms.find((classroom) => classroom.id === parseInt(classroomId, 10))

    setEditModalForm((prev) => ({
      ...prev,
      classroom_id: selectedClassroom ? String(selectedClassroom.id) : '',
      room_name: selectedClassroom ? selectedClassroom.name : prev.room_name,
      latitude: selectedClassroom ? selectedClassroom.gps_lat : prev.latitude,
      longitude: selectedClassroom ? selectedClassroom.gps_lng : prev.longitude,
      radius_meters: selectedClassroom ? selectedClassroom.radius_meters : prev.radius_meters,
    }))
    setEditModalMessage('')
  }

  const submitEditModal = async () => {
    if (!editModalTarget) return
    if (!validateSessionForm(editModalForm, setEditModalErrors)) return

    setEditModalSaving(true)
    setEditModalMessage('')
    try {
      const payload = buildSessionPayload(editModalForm)
      const response = await api.put(`/sessions/${editModalTarget.id}`, payload)
      const updatedSession = {
        ...editModalTarget,
        ...response.data,
        classroom_id: response.data.classroom_id ?? editModalForm.classroom_id,
        latitude: response.data.latitude ?? editModalForm.latitude,
        longitude: response.data.longitude ?? editModalForm.longitude,
        radius_meters: response.data.radius_meters ?? editModalForm.radius_meters,
        room_name: response.data.room_name ?? editModalForm.room_name,
        note: response.data.note ?? editModalForm.note,
      }
      setSessions((prev) => prev.map((session) => (
        session.id === editModalTarget.id ? { ...session, ...updatedSession } : session
      )))
      setMessage('Cập nhật buổi học thành công.')
      closeEditModal()
    } catch (error) {
      setEditModalMessage(getApiErrorMessage(error, 'Không cập nhật được buổi học.'))
    } finally {
      setEditModalSaving(false)
    }
  }

  const handleDelete = (session) => {
    const label = `#${session.id} - ${session.class_name} - ${getSessionSubjectValue(session)}`
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


  const handleOpenAlerts = (session) => {
    setAlertModalTarget(session)
    setAlertFilter('active')
    setAlertMessage('')
    loadAlerts(session.id, 'active')
  }

  const loadAlerts = async (sid, filterType = alertFilter) => {
    setAlertLoading(true)
    setAlertMessage('')
    try {
      const endpoint = filterType === 'active' ? `/alerts/session/${sid}/active` : `/alerts/session/${sid}`
      const response = await api.get(endpoint)
      setActiveAlerts(response.data)
    } catch (error) {
      setAlertMessage(getApiErrorMessage(error, 'Không tải được danh sách cảnh báo.'))
    } finally {
      setAlertLoading(false)
    }
  }

  const loadAlertsSilent = async (sid, filterType = alertFilter) => {
    try {
      const endpoint = filterType === 'active' ? `/alerts/session/${sid}/active` : `/alerts/session/${sid}`
      const response = await api.get(endpoint)
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
        dismissed_by: user?.username || 'admin'
      })
      setAlertMessage('✅ Đã tắt cảnh báo bảo mật.')
      await loadAlerts(alertModalTarget.id, alertFilter)
      const countRes = await api.get(`/alerts/session/${alertModalTarget.id}/count`)
      setAlertCounts(prev => ({ ...prev, [alertModalTarget.id]: countRes.data.total_active }))
    } catch (error) {
      setAlertMessage(getApiErrorMessage(error, 'Không xử lý được cảnh báo.'))
    } finally {
      setAlertLoading(false)
    }
  }

  const handleExportCSV = async (sessionId, type) => {
    setExportingSessionId(sessionId)
    setExportType(type)
    try {
      const endpoint = type === 'attendance'
        ? `/reports/export/csv/session/${sessionId}`
        : `/reports/export/csv/session/${sessionId}/alerts`
      
      const response = await api.get(endpoint, {
        responseType: 'blob'
      })
      
      let filename = type === 'attendance'
        ? `attendance_session_${sessionId}.csv`
        : `security_alerts_session_${sessionId}.csv`
        
      const contentDisposition = response.headers['content-disposition'] || response.headers['Content-Disposition']
      if (contentDisposition) {
        const filenameStarMatch = contentDisposition.match(/filename\*=utf-8''([^;\n]+)/i)
        if (filenameStarMatch && filenameStarMatch[1]) {
          filename = decodeURIComponent(filenameStarMatch[1])
        } else {
          const filenameMatch = contentDisposition.match(/filename=["']?([^"';\n]+)["']?/i)
          if (filenameMatch && filenameMatch[1]) {
            filename = filenameMatch[1].replace(/['"]/g, '')
          }
        }
      }
      
      const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8;' })
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', filename)
      document.body.appendChild(link)
      link.click()
      link.removeAttribute('download')
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    } catch (error) {
      console.error('Export CSV error:', error)
      window.alert('Không thể xuất báo cáo. Vui lòng thử lại.')
    } finally {
      setExportingSessionId(null)
      setExportType(null)
    }
  }

  const getWeeksStr = (session) => {
    if (!session.section_id) return '-'
    const group = sessions.filter(s => s.section_id === session.section_id)
    if (group.length === 0) return '-'
    const sorted = [...group].sort((a, b) => new Date(getSessionDateValue(a)) - new Date(getSessionDateValue(b)))
    const minDate = new Date(getSessionDateValue(sorted[0]))
    const weekNumbers = group.map(s => {
      const diffTime = new Date(getSessionDateValue(s)) - minDate
      const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24))
      return Math.floor(diffDays / 7) + 1
    })
    const maxWeek = Math.max(20, ...weekNumbers)
    const chars = Array(maxWeek).fill('-')
    weekNumbers.forEach(w => {
      if (w >= 1 && w <= maxWeek) {
        chars[w - 1] = String(w % 10)
      }
    })
    return chars.join('')
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

      {editingId && (
        <div className="panel panel-pad" style={{ marginBottom: 18 }}>
          <h3 style={{ marginTop: 0, marginBottom: 14, fontSize: 16 }}>Chỉnh sửa buổi học</h3>
          <div className="form-grid" style={{ marginBottom: 12 }}>
            {/* Môn học */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <select
                value={form.subject}
                onChange={(e) => handleChange('subject', e.target.value)}
                style={errors.subject ? { borderColor: '#e53e3e' } : {}}
              >
                <option value="">-- Chọn môn học --</option>
                {form.subject && !subjects.some((sb) => sb.subject_name === form.subject) && (
                  <option value={form.subject}>
                    {form.subject} (Hiện tại)
                  </option>
                )}
                {subjects.map((sb) => (
                  <option key={sb.id} value={sb.subject_name}>
                    {sb.subject_name} ({sb.subject_code})
                  </option>
                ))}
              </select>
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
                {form.class_name && !VALID_CLASSES.includes(form.class_name) && (
                  <option value={form.class_name}>
                    {form.class_name} (Hiện tại)
                  </option>
                )}
                {VALID_CLASSES.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
              {errors.class_name && (
                <span style={{ fontSize: 12, color: '#e53e3e' }}>{errors.class_name}</span>
              )}
            </div>

            {/* Nhóm học phần — readonly */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <input
                type="text"
                value={form.section_group}
                placeholder="Nhóm học phần (Đọc từ Lớp HP)"
                readOnly
                style={{ opacity: 0.7, cursor: 'not-allowed', background: 'rgba(255,255,255,0.05)' }}
              />
              <span style={{ fontSize: 11, color: 'var(--muted)' }}>
                Nhóm học phần (Chỉ đọc)
              </span>
            </div>

            {/* Ngày học */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                <input
                  type="text"
                  placeholder="Chọn ngày học từ lịch"
                  value={formatDateStr(form.session_date)}
                  readOnly
                  onClick={() => {
                    try {
                      editDateRef.current?.showPicker();
                    } catch (e) {
                      try {
                        editDateRef.current?.focus();
                        editDateRef.current?.click();
                      } catch (err) {}
                    }
                  }}
                  style={errors.session_date ? { borderColor: '#e53e3e', paddingRight: '40px', width: '100%', cursor: 'pointer' } : { paddingRight: '40px', width: '100%', cursor: 'pointer' }}
                />
                <button
                  type="button"
                  onClick={() => {
                    try {
                      editDateRef.current?.showPicker();
                    } catch (e) {
                      try {
                        editDateRef.current?.focus();
                        editDateRef.current?.click();
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
                  ref={editDateRef}
                  value={form.session_date || ''}
                  onChange={(e) => handleChange('session_date', e.target.value)}
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
              {loading ? 'Đang lưu...' : 'Cập nhật buổi học'}
            </button>
            <button className="secondary" onClick={resetForm} disabled={loading}>
              Hủy
            </button>
          </div>
        </div>
      )}

      {/* Toolbar tìm kiếm & tải dữ liệu luôn hiển thị */}
      <div className="sessions-controls">
        <div className="sessions-view-toggle" role="group" aria-label="Chế độ xem buổi học">
          <button
            className={viewMode === 'grouped' ? 'active' : ''}
            onClick={() => { setViewMode('grouped'); setSelectedGroupKey(null); }}
          >
            Theo lớp HP
          </button>
          <button
            className={viewMode === 'all' ? 'active' : ''}
            onClick={() => { setViewMode('all'); setSelectedGroupKey(null); }}
          >
            Tất cả buổi
          </button>
        </div>

        <div className="sessions-search-row">
          <input
            placeholder={viewMode === 'grouped' ? "Tìm mã HP, môn học, nhóm..." : "Tìm buổi, môn học, lớp..."}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <button className="secondary sessions-refresh-button" onClick={loadSessions} disabled={loading}>
            Tải lại
          </button>
        </div>
      </div>

      {message && <p className="status-message">{message}</p>}

      {viewMode === 'grouped' ? (
        <>
          {/* Grouped Table View */}
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  {['Mã HP', 'Môn học', 'Nhóm', 'Lớp', 'Tổng số buổi', 'Đang diễn ra', 'Sắp diễn ra', 'Đã kết thúc', 'Thao tác'].map((h) => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredGroupedSessions.length === 0 ? (
                  <tr>
                    <td colSpan="9" style={{ textAlign: 'center', padding: '24px 0', color: 'var(--muted)' }}>
                      Không có lớp học phần nào phù hợp.
                    </td>
                  </tr>
                ) : (
                  filteredGroupedSessions.map((group) => {
                    const metrics = getGroupMetrics(group);
                    return (
                      <tr key={group.key}>
                        <td style={{ fontFamily: 'var(--mono)', fontWeight: 700 }}>{group.section_code || '-'}</td>
                        <td style={{ fontWeight: 600 }}>{group.subject_name || '-'}</td>
                        <td style={{ fontWeight: 600, color: 'var(--teal)' }}>
                          {group.section_group || '-'}
                        </td>
                        <td>{group.class_name}</td>
                        <td>{metrics.total}</td>
                        <td>
                          <span className="badge success">{metrics.ongoing} đang diễn ra</span>
                        </td>
                        <td>
                          <span className="badge info">{metrics.upcoming} sắp diễn ra</span>
                        </td>
                        <td>
                          <span className="badge muted">{metrics.finished} đã kết thúc</span>
                        </td>
                        <td>
                          <button
                            className="secondary"
                            onClick={() => openGroupDetails(group.key)}
                          >
                            Chi tiết
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* Grouped Mobile View */}
          <div className="mobile-card-list">
            {filteredGroupedSessions.length === 0 ? (
              <div className="empty-state">Không có lớp học phần nào phù hợp.</div>
            ) : (
              filteredGroupedSessions.map((group) => {
                const metrics = getGroupMetrics(group);
                return (
                  <div key={group.key} className="mobile-card session-mobile-card" style={{ border: '1px solid var(--bdr)' }}>
                    <div className="mobile-card-header">
                      <span className="mobile-card-title" style={{ color: 'var(--teal)', fontWeight: 700 }}>
                        {group.section_code ? `${group.section_code} - ` : ''}{group.subject_name || '-'}
                      </span>
                    </div>
                    <div className="mobile-card-row">
                      <span className="mobile-card-label">Mã HP:</span>
                      <span className="mobile-card-value" style={{ fontFamily: 'var(--mono)' }}>
                        {group.section_code || '-'}
                      </span>
                    </div>
                    <div className="mobile-card-row">
                      <span className="mobile-card-label">Nhóm:</span>
                      <span className="mobile-card-value" style={{ fontWeight: 600, color: 'var(--teal)' }}>
                        {group.section_group || '-'}
                      </span>
                    </div>
                    <div className="mobile-card-row">
                      <span className="mobile-card-label">Lớp:</span>
                      <span className="mobile-card-value" style={{ fontFamily: 'var(--mono)' }}>
                        {group.class_name}
                      </span>
                    </div>
                    <div className="mobile-card-row session-metrics-row">
                      <span className="mobile-card-label">Số buổi học:</span>
                      <span className="mobile-card-value">
                        {metrics.total} buổi ({metrics.ongoing} đang, {metrics.upcoming} sắp, {metrics.finished} xong)
                      </span>
                    </div>
                    <div className="mobile-card-actions">
                      <button
                        style={{ width: '100%', justifyContent: 'center' }}
                        onClick={() => openGroupDetails(group.key)}
                      >
                        Chi tiết
                      </button>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </>
      ) : (
        <>
          {/* Original List Table View */}
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  {['Mã buổi', 'Môn học', 'Nhóm', 'Lớp', 'Trạng thái', 'Ngày', 'Bắt đầu', 'Kết thúc', 'Tuần học', 'Thao tác'].map((h) => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredSessions.map((session) => {
                  const status = getSessionStatus(session)
                  return (
                    <tr key={session.id}>
                      <td>#{session.id}</td>
                      <td>{getSessionSubjectValue(session)}{session.session_number ? ` (Buổi ${session.session_number})` : ''}</td>
                      <td style={{ fontWeight: 600, color: 'var(--teal)' }}>{session.section_group || '-'}</td>
                      <td>{session.class_name}</td>
                      <td>
                        <span className={status.badgeClass}>
                          {status.label}
                        </span>
                      </td>
                      <td>{formatDateForDisplay(getSessionDateValue(session))}</td>
                      <td>{formatTime(session.start_time)}</td>
                      <td>{formatTime(session.end_time)}</td>
                      <td style={{ fontFamily: 'var(--mono)', letterSpacing: '0.12em', fontSize: '13px', color: 'var(--white2)' }}>
                        {session.week_pattern || session.week_display || getWeeksStr(session)}
                      </td>
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
                            <button
                              className="secondary"
                              onClick={() => handleExportCSV(session.id, 'attendance')}
                              disabled={exportingSessionId === session.id}
                              title="Xuất điểm danh CSV"
                              style={{ minWidth: 'auto', padding: '0 8px' }}
                            >
                              {exportingSessionId === session.id && exportType === 'attendance' ? '...' : '📥 Điểm danh'}
                            </button>
                            <button
                              className="secondary"
                              onClick={() => handleExportCSV(session.id, 'alerts')}
                              disabled={exportingSessionId === session.id}
                              title="Xuất cảnh báo CSV"
                              style={{ minWidth: 'auto', padding: '0 8px' }}
                            >
                              {exportingSessionId === session.id && exportType === 'alerts' ? '...' : '📥 Cảnh báo'}
                            </button>
                            <button className="secondary" onClick={() => handleEdit(session)} disabled={loading}>
                              Sửa
                            </button>
                            <button
                              className="secondary"
                              style={{ background: 'rgba(244,63,94,.1)', border: '1px solid rgba(244,63,94,.25)', color: 'var(--red)' }}
                              onClick={() => handleDelete(session)}
                              disabled={loading}
                            >
                              Xóa
                            </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* Original Mobile Card Layout */}
          <div className="mobile-card-list">
            {filteredSessions.length === 0 ? (
              <div className="empty-state">Không có buổi học phù hợp.</div>
            ) : (
              filteredSessions.map((session) => {
                const status = getSessionStatus(session)
                return (
                  <div key={session.id} className="mobile-card session-mobile-card">
                    <div className="mobile-card-header">
                      <span className="mobile-card-title" style={{ color: 'var(--teal)', fontWeight: 700 }}>
                        {getSessionSubjectValue(session)}{session.session_number ? ` (Buổi ${session.session_number})` : ''}
                      </span>
                      <span className="badge success" style={{ fontFamily: 'var(--mono)', fontSize: '11px' }}>
                        #{session.id}
                      </span>
                    </div>
                    <div className="mobile-card-row">
                      <span className="mobile-card-label">Nhóm:</span>
                      <span className="mobile-card-value" style={{ fontWeight: 600, color: 'var(--teal)' }}>{session.section_group || '-'}</span>
                    </div>
                    <div className="mobile-card-row">
                      <span className="mobile-card-label">Lớp:</span>
                      <span className="mobile-card-value" style={{ fontFamily: 'var(--mono)' }}>{session.class_name}</span>
                    </div>
                    <div className="mobile-card-row">
                      <span className="mobile-card-label">Trạng thái:</span>
                      <span className="mobile-card-value">
                        <span className={status.badgeClass}>
                          {status.label}
                        </span>
                      </span>
                    </div>
                    <div className="mobile-card-row">
                      <span className="mobile-card-label">Ngày học:</span>
                      <span className="mobile-card-value">{formatDateForDisplay(getSessionDateValue(session))}</span>
                    </div>
                    <div className="mobile-card-row">
                      <span className="mobile-card-label">Thời gian:</span>
                      <span className="mobile-card-value">
                        {formatTime(session.start_time)} - {formatTime(session.end_time)}
                      </span>
                    </div>
                    <div className="mobile-card-row">
                      <span className="mobile-card-label">Tuần học:</span>
                      <span className="mobile-card-value" style={{ fontFamily: 'var(--mono)', letterSpacing: '0.12em' }}>
                        {session.week_pattern || session.week_display || getWeeksStr(session)}
                      </span>
                    </div>
                    <div style={{ display: 'flex', gap: 6, marginTop: 8, marginBottom: 4, alignItems: 'center', flexWrap: 'wrap', borderTop: '1px dashed var(--bdr)', paddingTop: 8, paddingLeft: 12, paddingRight: 12 }}>
                      <span style={{ fontSize: 11, color: 'var(--muted)', fontWeight: 600 }}>Xuất báo cáo:</span>
                      <button
                        className="secondary"
                        style={{ fontSize: 11, minHeight: 28, padding: '0 8px', borderRadius: 4 }}
                        onClick={() => handleExportCSV(session.id, 'attendance')}
                        disabled={exportingSessionId === session.id}
                      >
                        {exportingSessionId === session.id && exportType === 'attendance' ? 'Đang xuất...' : '📥 Điểm danh CSV'}
                      </button>
                      <button
                        className="secondary"
                        style={{ fontSize: 11, minHeight: 28, padding: '0 8px', borderRadius: 4 }}
                        onClick={() => handleExportCSV(session.id, 'alerts')}
                        disabled={exportingSessionId === session.id}
                      >
                        {exportingSessionId === session.id && exportType === 'alerts' ? 'Đang xuất...' : '📥 Cảnh báo CSV'}
                      </button>
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
                )
              })
            )}
          </div>
        </>
      )}

      {/* Detail Drawer (Right-aligned Slide-in Panel) */}
      {selectedGroup && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,.55)',
            zIndex: 990,
            display: 'flex',
            justifyContent: 'flex-end',
            animation: 'fadeIn 0.25s ease'
          }}
          onClick={() => setSelectedGroupKey(null)}
        >
          <div
            style={{
              width: 'min(520px, 100%)',
              height: '100vh',
              background: 'var(--navy2)',
              borderLeft: '1px solid var(--bdr2)',
              boxShadow: 'var(--shadow)',
              display: 'flex',
              flexDirection: 'column',
              animation: 'slideInRight 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--bdr)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h2 style={{ margin: 0, fontSize: 18, color: 'var(--white)', fontWeight: 800 }}>
                  {selectedGroupTitle || 'Chi tiết các buổi học'}
                </h2>
                <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--muted)' }}>
                  Tổng số buổi: {selectedGroup.sessions.length}
                </p>
              </div>
              <button
                className="secondary"
                onClick={() => setSelectedGroupKey(null)}
                style={{ minHeight: 32, padding: '0 8px', fontSize: 18 }}
              >
                ✕
              </button>
            </div>

            {/* Tabs Filter */}
            <div style={{ display: 'flex', gap: 6, padding: '12px 24px', borderBottom: '1px solid var(--bdr)', flexWrap: 'wrap' }}>
              {[
                { key: 'all', label: 'Tất cả' },
                { key: 'ongoing', label: 'Đang diễn ra' },
                { key: 'upcoming', label: 'Sắp diễn ra' },
                { key: 'finished', label: 'Đã kết thúc' }
              ].map(tab => (
                <button
                  key={tab.key}
                  onClick={() => setDrawerFilter(tab.key)}
                  style={{
                    padding: '6px 12px',
                    fontSize: 12,
                    minHeight: 'auto',
                    borderRadius: '20px',
                    background: drawerFilter === tab.key ? 'rgba(0, 201, 167, 0.15)' : 'transparent',
                    borderColor: drawerFilter === tab.key ? 'rgba(0, 201, 167, 0.35)' : 'transparent',
                    color: drawerFilter === tab.key ? 'var(--teal)' : 'var(--muted)',
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Sessions list */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '16px 24px', display: 'flex', flexDirection: 'column', gap: 12 }}>
              {displaySessions.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--muted)' }}>
                  Không có buổi học nào ở trạng thái này.
                </div>
              ) : (
                displaySessions.map((s) => {
                  const status = getSessionStatus(s);
                  const alertCount = alertCounts[s.id] || 0;
                  return (
                    <div
                      key={s.id}
                      style={{
                        background: 'var(--card)',
                        border: '1px solid var(--bdr)',
                        borderRadius: 10,
                        padding: 16,
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 10,
                        transition: 'border-color 0.2s',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontWeight: 700, color: 'var(--white)' }}>
                          {s.session_number ? `Buổi số ${s.session_number}` : `Buổi học #${s.id}`}
                        </span>
                        <span className={status.badgeClass} style={{ fontSize: 11 }}>
                          {status.label}
                        </span>
                      </div>
                      
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13, color: 'var(--white2)' }}>
                        <div>Ngày học: {formatDateForDisplay(getSessionDateValue(s))}</div>
                        <div>⏰ Khung giờ: {formatTime(s.start_time)} - {formatTime(s.end_time)}</div>
                        <div>📍 Phòng học: {s.room_name || '-'}</div>
                        {s.note && <div style={{ fontSize: 12, color: 'var(--muted)', fontStyle: 'italic' }}>📝 Ghi chú: {s.note}</div>}
                        <div style={{ fontFamily: 'var(--mono)', letterSpacing: '0.12em', fontSize: '12px', marginTop: 4 }}>
                        Tuần học: {s.week_pattern || s.week_display || getWeeksStr(s)}
                        </div>
                        <div style={{ display: 'flex', gap: 6, marginTop: 8, alignItems: 'center', flexWrap: 'wrap', borderTop: '1px dashed var(--bdr)', paddingTop: 8 }}>
                          <span style={{ fontSize: 11, color: 'var(--muted)', fontWeight: 600 }}>Xuất báo cáo:</span>
                          <button
                            className="secondary"
                            style={{ fontSize: 11, minHeight: 28, padding: '0 8px', borderRadius: 4 }}
                            onClick={() => handleExportCSV(s.id, 'attendance')}
                            disabled={exportingSessionId === s.id}
                          >
                            {exportingSessionId === s.id && exportType === 'attendance' ? 'Đang xuất...' : '📥 Điểm danh CSV'}
                          </button>
                          <button
                            className="secondary"
                            style={{ fontSize: 11, minHeight: 28, padding: '0 8px', borderRadius: 4 }}
                            onClick={() => handleExportCSV(s.id, 'alerts')}
                            disabled={exportingSessionId === s.id}
                          >
                            {exportingSessionId === s.id && exportType === 'alerts' ? 'Đang xuất...' : '📥 Cảnh báo CSV'}
                          </button>
                        </div>
                      </div>

                      <div style={{ display: 'flex', gap: 8, borderTop: '1px solid var(--bdr)', paddingTop: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                        <button
                          className="secondary"
                          onClick={() => handleOpenAlerts(s)}
                          disabled={loading}
                          style={{
                            position: 'relative',
                            fontSize: 12,
                            minHeight: 32,
                            padding: '0 10px',
                            borderColor: alertCount > 0 ? 'var(--red)' : 'var(--bdr)'
                          }}
                        >
                          ⚠️ Cảnh báo
                          {alertCount > 0 && (
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
                              {alertCount}
                            </span>
                          )}
                        </button>
                        <button
                          className="secondary"
                          style={{ fontSize: 12, minHeight: 32, padding: '0 10px' }}
                          onClick={() => openEditModal(s)}
                          disabled={loading}
                        >
                          Sửa
                        </button>
                        <button
                          style={{
                            fontSize: 12,
                            minHeight: 32,
                            padding: '0 10px',
                            background: 'rgba(244,63,94,.1)',
                            border: '1px solid rgba(244,63,94,.25)',
                            color: 'var(--red)',
                            marginLeft: 'auto'
                          }}
                          onClick={() => handleDelete(s)}
                          disabled={loading}
                        >
                          Xóa
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      )}

      {editModalTarget && (
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
            zIndex: 1005,
            padding: 12,
            animation: 'fadeIn 0.2s ease'
          }}
        >
          <div
            style={{
              width: 'min(680px, 100%)',
              maxHeight: '92vh',
              background: 'var(--navy2)',
              border: '1px solid var(--bdr2)',
              borderRadius: 12,
              padding: '20px 16px',
              boxShadow: 'var(--shadow)',
              display: 'flex',
              flexDirection: 'column',
              gap: 16,
              overflowY: 'auto'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid var(--bdr)', paddingBottom: 10, gap: 12 }}>
              <div>
                <h3 style={{ margin: 0, fontSize: 16, color: 'var(--white)' }}>Chỉnh sửa buổi học</h3>
                <p style={{ margin: '4px 0 0', fontSize: 12, color: 'var(--muted)' }}>
                  {[
                    editModalTarget.session_number ? `Buổi số ${editModalTarget.session_number}` : `Buổi #${editModalTarget.id}`,
                    getSessionSubjectValue(editModalTarget),
                    editModalTarget.section_group ? `Nhóm ${editModalTarget.section_group}` : '',
                    editModalTarget.class_name ? `Lớp ${editModalTarget.class_name}` : ''
                  ].filter(Boolean).join(' - ')}
                </p>
              </div>
              <button
                className="secondary"
                onClick={closeEditModal}
                disabled={editModalSaving}
                style={{ minHeight: 32, padding: '0 8px', fontSize: 18 }}
              >
                ✕
              </button>
            </div>

            {editModalMessage && (
              <p
                style={{
                  margin: 0,
                  padding: '8px 12px',
                  borderRadius: 6,
                  fontSize: 12,
                  background: 'rgba(244, 63, 94, 0.08)',
                  border: '1px solid rgba(244, 63, 94, 0.2)',
                  color: 'var(--red)',
                  lineHeight: 1.4
                }}
              >
                {editModalMessage}
              </p>
            )}

            <div className="form-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label style={{ fontSize: 12, color: 'var(--muted)', fontWeight: 700 }}>Môn học / Lớp học phần</label>
                <input
                  value={editModalForm.subject}
                  readOnly
                  style={{ opacity: 0.78, cursor: 'not-allowed', background: 'rgba(255,255,255,0.05)' }}
                />
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label style={{ fontSize: 12, color: 'var(--muted)', fontWeight: 700 }}>Lớp sinh viên</label>
                <input
                  value={editModalForm.class_name}
                  readOnly
                  style={{ opacity: 0.78, cursor: 'not-allowed', background: 'rgba(255,255,255,0.05)' }}
                />
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label style={{ fontSize: 12, color: 'var(--muted)', fontWeight: 700 }}>Nhóm học phần</label>
                <input
                  value={editModalForm.section_group}
                  readOnly
                  style={{ opacity: 0.78, cursor: 'not-allowed', background: 'rgba(255,255,255,0.05)' }}
                />
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label style={{ fontSize: 12, color: 'var(--muted)', fontWeight: 700 }}>Ngày học</label>
                <input
                  type="date"
                  value={editModalForm.session_date || ''}
                  onChange={(e) => handleEditModalChange('session_date', e.target.value)}
                  style={editModalErrors.session_date ? { borderColor: '#e53e3e' } : {}}
                />
                <span style={{ fontSize: 11, color: 'var(--muted)' }}>
                  Hiển thị: {formatDateForDisplay(editModalForm.session_date) || '-'}
                </span>
                {editModalErrors.session_date && (
                  <span style={{ fontSize: 12, color: '#e53e3e' }}>{editModalErrors.session_date}</span>
                )}
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label style={{ fontSize: 12, color: 'var(--muted)', fontWeight: 700 }}>Giờ bắt đầu</label>
                <input
                  type="time"
                  value={editModalForm.start_time}
                  onChange={(e) => handleEditModalChange('start_time', e.target.value)}
                  style={editModalErrors.start_time ? { borderColor: '#e53e3e' } : {}}
                />
                {editModalErrors.start_time && (
                  <span style={{ fontSize: 12, color: '#e53e3e' }}>{editModalErrors.start_time}</span>
                )}
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label style={{ fontSize: 12, color: 'var(--muted)', fontWeight: 700 }}>Giờ kết thúc</label>
                <input
                  type="time"
                  value={editModalForm.end_time}
                  onChange={(e) => handleEditModalChange('end_time', e.target.value)}
                  style={editModalErrors.end_time ? { borderColor: '#e53e3e' } : {}}
                />
                {editModalErrors.end_time && (
                  <span style={{ fontSize: 12, color: '#e53e3e' }}>{editModalErrors.end_time}</span>
                )}
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label style={{ fontSize: 12, color: 'var(--muted)', fontWeight: 700 }}>Phòng học</label>
                <select
                  value={editModalForm.classroom_id}
                  onChange={(e) => handleEditModalClassroomChange(e.target.value)}
                >
                  <option value="">-- Chọn phòng học đã lưu --</option>
                  {activeClassrooms.map((classroom) => (
                    <option key={classroom.id} value={classroom.id}>
                      {getClassroomOptionLabel(classroom)}
                    </option>
                  ))}
                </select>
                {!editModalForm.classroom_id && editModalForm.room_name && (
                  <span style={{ fontSize: 11, color: 'var(--muted)' }}>
                    Phòng hiện tại: {editModalForm.room_name}
                  </span>
                )}
                {(selectedEditModalRoom || editModalForm.latitude || editModalForm.longitude) && (
                  <div style={{ fontSize: 11, color: 'var(--muted)', lineHeight: 1.5 }}>
                    <div>Tọa độ: {editModalForm.latitude || '-'}, {editModalForm.longitude || '-'}</div>
                    <div>Bán kính cho phép: {editModalForm.radius_meters || '-'} mét</div>
                  </div>
                )}
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, gridColumn: '1 / -1' }}>
                <label style={{ fontSize: 12, color: 'var(--muted)', fontWeight: 700 }}>Ghi chú</label>
                <textarea
                  value={editModalForm.note}
                  onChange={(e) => handleEditModalChange('note', e.target.value)}
                  placeholder="Ghi chú buổi học"
                  style={{ minHeight: 80 }}
                />
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, borderTop: '1px solid var(--bdr)', paddingTop: 12, flexWrap: 'wrap' }}>
              <button className="secondary" onClick={closeEditModal} disabled={editModalSaving}>
                Hủy / Đóng
              </button>
              <button onClick={submitEditModal} disabled={editModalSaving}>
                {editModalSaving ? 'Đang cập nhật...' : 'Cập nhật buổi học'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Dynamic Keyframes Injection */}
      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes slideInRight {
          from { transform: translateX(100%); }
          to { transform: translateX(0); }
        }
      `}</style>

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
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--bdr2)', paddingBottom: '8px' }}>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    onClick={() => {
                      setAlertFilter('active');
                      if (alertModalTarget) loadAlerts(alertModalTarget.id, 'active');
                    }}
                    style={{
                      padding: '4px 10px',
                      fontSize: '11px',
                      minHeight: 'auto',
                      borderRadius: '4px',
                      background: alertFilter === 'active' ? 'rgba(0, 201, 167, 0.15)' : 'transparent',
                      borderColor: alertFilter === 'active' ? 'rgba(0, 201, 167, 0.35)' : 'rgba(255,255,255,0.1)',
                      color: alertFilter === 'active' ? 'var(--teal)' : 'var(--muted)',
                    }}
                  >
                    Chưa xử lý
                  </button>
                  <button
                    onClick={() => {
                      setAlertFilter('all');
                      if (alertModalTarget) loadAlerts(alertModalTarget.id, 'all');
                    }}
                    style={{
                      padding: '4px 10px',
                      fontSize: '11px',
                      minHeight: 'auto',
                      borderRadius: '4px',
                      background: alertFilter === 'all' ? 'rgba(0, 201, 167, 0.15)' : 'transparent',
                      borderColor: alertFilter === 'all' ? 'rgba(0, 201, 167, 0.35)' : 'rgba(255,255,255,0.1)',
                      color: alertFilter === 'all' ? 'var(--teal)' : 'var(--muted)',
                    }}
                  >
                    Tất cả
                  </button>
                </div>
                <span style={{ fontSize: '12px', color: 'var(--white2)', fontWeight: 'bold' }}>
                  Số lượng: {activeAlerts.length}
                </span>
              </div>

              {alertLoading && activeAlerts.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--muted)', fontSize: 13 }}>
                  Đang tải danh sách cảnh báo...
                </div>
              ) : activeAlerts.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--muted)', fontSize: 13, border: '1px dashed var(--bdr)', borderRadius: 8 }}>
                  Không có cảnh báo phù hợp.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {activeAlerts.map((al) => {
                    const style = getAlertCardStyle(al.alert_type)
                    const parsedNote = parseNoteSafely(al.note)
                    const reasonCode = parsedNote?.reason_code || null
                    const noteText = parsedNote ? null : al.note
                    
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
                        <AlertImage path={al.captured_img} />

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
                              {al.created_at ? new Date(al.created_at).toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit', day: '2-digit', month: '2-digit', year: 'numeric' }) : ''}
                            </span>
                            {al.dismissed && (
                              <span style={{ fontSize: 10, color: 'var(--muted)', background: 'rgba(255,255,255,0.05)', padding: '2px 6px', borderRadius: 4 }}>
                                Đã xử lý bởi {al.dismissed_by || 'system'}
                              </span>
                            )}
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

                          {reasonCode && (
                            <div style={{ fontSize: 11, color: 'var(--white2)' }}>
                              Mã lý do: <strong style={{ color: style.badgeColor }}>{reasonCode}</strong>
                            </div>
                          )}
                          {parsedNote?.quality !== undefined && (
                            <div style={{ fontSize: 11, color: 'var(--white2)' }}>
                              Chất lượng: <strong>{typeof parsedNote.quality === 'number' && parsedNote.quality <= 1 ? (parsedNote.quality * 100).toFixed(0) + '%' : parsedNote.quality}</strong>
                            </div>
                          )}
                          {parsedNote?.detection_confidence !== undefined && (
                            <div style={{ fontSize: 11, color: 'var(--white2)' }}>
                              Độ tin cậy phát hiện: <strong>{(parsedNote.detection_confidence * 100).toFixed(0)}%</strong>
                            </div>
                          )}

                          {noteText && (
                            <div style={{ fontSize: 11, color: 'var(--muted)', fontStyle: 'italic' }}>
                              Ghi chú: {noteText}
                            </div>
                          )}

                          <div style={{ fontSize: 11, color: 'var(--muted)', display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 2 }}>
                            {renderConfidence(al)}
                            {al.liveness_score !== null && al.liveness_score !== undefined && (
                              <span>Điểm kiểm tra khuôn mặt thật: {(al.liveness_score * 100).toFixed(0)}%</span>
                            )}
                            {al.gps_lat !== null && al.gps_lat !== undefined && (
                              <span>GPS: {al.gps_lat.toFixed(5)}, {al.gps_lng.toFixed(5)}</span>
                            )}
                          </div>
                        </div>

                        {/* Dismiss action */}
                        {!al.dismissed && (
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
                            Duyệt cảnh báo
                          </button>
                        )}
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
