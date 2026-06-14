import { useEffect, useMemo, useRef, useState } from 'react'

import api from '../../api/axios.js'
import { useAuth } from '../auth/auth-context.js'
import { getApiErrorMessage } from '../utils/apiError.js'
import {
  attendanceStatusLabels,
  dataSourceLabels,
  getDisplayLabel,
  recognitionStatusLabels,
  registrationMethodLabels,
} from '../utils/displayLabels.js'
import GPSStatus from '../components/GPSStatus'
import AttendanceCountdown from '../components/AttendanceCountdown'

const actionOptions = [
  { value: 'checkin',  label: 'Vào lớp' },
  { value: 'checkout', label: 'Ra về'   },
]

const actionLabels = { checkin: 'vào lớp', checkout: 'ra về' }

const statusLabels = attendanceStatusLabels

const recognitionMessages = {
  success:  'Nhận diện thành công.',
  uncertain:'Khuôn mặt cần được xác nhận thủ công.',
  unknown:  'Không nhận diện được sinh viên.',
  no_face:  'Không phát hiện khuôn mặt trong ảnh.',
  multiple_faces: 'Phát hiện nhiều khuôn mặt trong ảnh.',
  spoof: 'Phát hiện giả mạo khuôn mặt. Vui lòng dùng khuôn mặt thật.',
}
const OFFICIAL_BLOCK_MESSAGE = 'Mẫu này thuộc dữ liệu demo/Kaggle, không được ghi nhận điểm danh chính thức.'

const isOfficialStudent = (student) =>
  student?.data_source === 'real' && !student?.is_demo && student?.face_status === 'registered'

const getStyle = (status) => {
  if (status === 'blocked')   return { bg: 'rgba(245,158,11,.14)', border: 'rgba(245,158,11,.45)', accent: '#fbbf24', text: '#f8fafc', muted: '#fde68a', label: 'Cần xác nhận thủ công' }
  if (status === 'success')   return { bg: 'rgba(0,201,167,.14)', border: 'rgba(0,201,167,.45)', accent: '#2dd4bf', text: '#f8fafc', muted: '#99f6e4', label: 'Nhận diện thành công' }
  if (status === 'uncertain') return { bg: 'rgba(245,158,11,.14)', border: 'rgba(245,158,11,.45)', accent: '#fbbf24', text: '#f8fafc', muted: '#fde68a', label: 'Chưa đủ độ tin cậy' }
  if (status === 'no_face')   return { bg: 'rgba(244,63,94,.14)', border: 'rgba(244,63,94,.45)', accent: '#fb7185', text: '#f8fafc', muted: '#fecdd3', label: 'Không phát hiện khuôn mặt' }
  if (status === 'multiple_faces') return { bg: 'rgba(244,63,94,.14)', border: 'rgba(244,63,94,.45)', accent: '#fb7185', text: '#f8fafc', muted: '#fecdd3', label: 'Phát hiện nhiều khuôn mặt' }
  if (status === 'spoof')     return { bg: 'rgba(244,63,94,.14)', border: 'rgba(244,63,94,.45)', accent: '#fb7185', text: '#f8fafc', muted: '#fecdd3', label: 'Phát hiện giả mạo khuôn mặt' }
  return                             { bg: 'rgba(244,63,94,.14)', border: 'rgba(244,63,94,.45)', accent: '#fb7185', text: '#f8fafc', muted: '#fecdd3', label: 'Không nhận diện được' }
}

/** "2025-05-15T08:32:11" → "15/05 08:32" */
const formatDT = (iso) => {
  if (!iso) return '-'
  const d = new Date(iso)
  if (isNaN(d)) return iso
  const dd  = String(d.getDate()).padStart(2, '0')
  const mm  = String(d.getMonth() + 1).padStart(2, '0')
  const hh  = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
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

const isClassMismatchRecognition = (recognition) =>
  recognition?.reason === 'class_mismatch' ||
  recognition?.official_attendance_warning_code === 'class_mismatch' ||
  recognition?.requires_manual_confirmation === true

const getClassMismatchMessage = (student, session) =>
  `Sinh viên thuộc lớp ${student?.class_name || '-'}, khác lớp chính của buổi học ${session?.class_name || session?.section_code || '-'}. Nếu sinh viên có đăng ký/học ghép buổi này, giảng viên có thể xác nhận thủ công để ghi nhận điểm danh.`

export default function Attendance() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'
  const isLecturerOrAdmin = user?.role === 'admin' || user?.role === 'teacher' || user?.role === 'lecturer'
  const canDeleteAttendance = isLecturerOrAdmin
  const videoRef  = useRef(null)
  const canvasRef = useRef(null)
  const overlayCanvasRef = useRef(null)

  const [stream,             setStream]             = useState(null)
  const [sessions,           setSessions]           = useState([])
  const [sessionId,          setSessionId]          = useState('')
  const [action,             setAction]             = useState('checkin')
  const [sessionAttendance,  setSessionAttendance]  = useState([])
  const [result,             setResult]             = useState(null)
  const [loading,            setLoading]            = useState(false)
  const [deletingRecordId,    setDeletingRecordId]    = useState(null)
  const [message,            setMessage]            = useState('')
  const [alertToast,         setAlertToast]         = useState(null)
  const [mode,               setMode]               = useState('official')
  const [testFile,           setTestFile]           = useState(null)
  const [testPreviewUrl,     setTestPreviewUrl]     = useState('')
  const [testResult,         setTestResult]         = useState(null)
  const [testLoading,        setTestLoading]        = useState(false)

  // Mobile states
  const [isMobile,           setIsMobile]           = useState(window.innerWidth < 768)
  const [mobileStep,         setMobileStep]         = useState(1) // 1: Chọn buổi học, 2: GPS/Countdown, 3: Camera/Quét, 4: Kết quả
  const [gpsCoords,          setGpsCoords]          = useState(null)
  const [timeStatus,         setTimeStatus]         = useState('not_started')
  const [classrooms,         setClassrooms]         = useState([])

  // Section grouping states
  const [selectedSectionKey, setSelectedSectionKey] = useState('')
  const [activeMobileGroup,  setActiveMobileGroup]  = useState(null)

  const selectedSession = useMemo(
    () => sessions.find((session) => String(session.id || session.session_id) === String(sessionId)),
    [sessions, sessionId],
  )

  const selectedClassroom = useMemo(() => {
    if (!selectedSession) return null

    // 1. Ưu tiên lấy tọa độ GPS động trực tiếp từ session
    if (selectedSession.latitude !== undefined && selectedSession.latitude !== null &&
        selectedSession.longitude !== undefined && selectedSession.longitude !== null) {
      return {
        id: null,
        name: selectedSession.room_name || 'Phòng học (Session GPS)',
        gps_lat: selectedSession.latitude,
        gps_lng: selectedSession.longitude,
        radius_meters: selectedSession.radius_meters || 15
      }
    }

    // 2. Thử với trường classroom_gps_lat/lng nếu active-sessions trả về
    if (selectedSession.classroom_gps_lat !== undefined && selectedSession.classroom_gps_lat !== null &&
        selectedSession.classroom_gps_lng !== undefined && selectedSession.classroom_gps_lng !== null) {
      return {
        id: selectedSession.classroom_id,
        name: selectedSession.classroom_name || 'Phòng học',
        gps_lat: selectedSession.classroom_gps_lat,
        gps_lng: selectedSession.classroom_gps_lng,
        radius_meters: selectedSession.radius_meters || 15
      }
    }

    // 3. Fallback lấy từ classrooms tĩnh
    const classroom = selectedSession.classroom_id
      ? classrooms.find((c) => String(c.id) === String(selectedSession.classroom_id))
      : null

    if (classroom) {
      return {
        id: classroom.id,
        name: classroom.name || 'Phòng học',
        gps_lat: classroom.gps_lat,
        gps_lng: classroom.gps_lng,
        radius_meters: classroom.radius_meters || 15
      }
    }

    // 4. Nếu hoàn toàn không có tọa độ GPS nào, vẫn trả về đối tượng có room_name / classroom_name
    return {
      id: selectedSession.classroom_id || null,
      name: selectedSession.room_name || selectedSession.classroom_name || 'Chưa xác định phòng học',
      gps_lat: null,
      gps_lng: null,
      radius_meters: selectedSession.radius_meters || null
    }
  }, [classrooms, selectedSession])

  // Responsive listener
  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768)
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  // Tải danh sách phòng học để lấy tọa độ GPS của phòng học
  useEffect(() => {
    api.get('/classrooms/').then(res => setClassrooms(res.data)).catch(console.error)
  }, [])

  // ── Giải quyết student_id từ user để tải active sessions ───────── //
  const fetchSessionsForUser = async (currentUser) => {
    if (currentUser?.role === 'student') {
      try {
        // Ưu tiên gọi thẳng endpoint active-sessions không truyền student_id khi đã có JWT
        const activeRes = await api.get('/students/me/active-sessions')
        return activeRes.data
      } catch (err) {
        console.warn('Không gọi được active-sessions không tham số, thử với student_id fallback:', err)
        const studentIdFallback = currentUser?.student_id || currentUser?.id
        if (studentIdFallback) {
          try {
            const fallbackRes = await api.get(`/students/me/active-sessions?student_id=${studentIdFallback}`)
            return fallbackRes.data
          } catch (fbErr) {
            console.warn('Fallback active-sessions với student_id thất bại:', fbErr)
          }
        }
        // Fallback cuối cùng sang sessions chính
        console.warn('Tự động fallback sang sessions chính')
        const fallbackRes = await api.get('/sessions/')
        return fallbackRes.data
      }
    } else {
      const res = await api.get('/sessions/')
      return res.data
    }
  }

  // ── Helpers for Session Status & Grouping ─────────────────────── //
  const getSessionDateValue = (session) => session.session_date || session.date || ''
  const getSessionSubjectValue = (session) => session.subject_name || session.subject || ''
  const getSessionIdValue = (session) => session.id || session.session_id

  const formatDateForDisplay = (dateStr) => {
    if (!dateStr) return ''
    if (/^\d{2}\/\d{2}\/\d{4}$/.test(dateStr)) return dateStr
    const parts = String(dateStr).split('-')
    if (parts.length === 3) {
      return `${parts[2]}/${parts[1]}/${parts[0]}`
    }
    return dateStr
  }

  const getSessionDateTime = (session, timeField = 'start_time') => {
    const sessionDate = getSessionDateValue(session)
    const timeValue = session[timeField]
    if (!sessionDate || !timeValue) return null
    const [year, month, day] = sessionDate.split('-').map(Number)
    const [hour, minute] = String(timeValue).split(':').map(Number)
    return new Date(year, month - 1, day, hour || 0, minute || 0, 0)
  }

  const getSessionStatus = (session) => {
    const start = getSessionDateTime(session, 'start_time')
    const end = getSessionDateTime(session, 'end_time')
    if (!start || !end) {
      return { label: 'Không rõ', badgeClass: 'badge' }
    }
    const now = new Date()

    if (now < start) {
      return { label: 'Sắp diễn ra', badgeClass: 'badge info' }
    } else if (now > end) {
      return { label: 'Đã kết thúc', badgeClass: 'badge muted' }
    } else {
      return { label: 'Đang diễn ra', badgeClass: 'badge success' }
    }
  }

  const getSessionGroupKey = (s) => {
    if (s.section_id !== null && s.section_id !== undefined) return `section:${s.section_id}`
    return [
      s.section_code || '',
      s.section_group || '',
      s.class_name || '',
      getSessionSubjectValue(s),
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
    sessionsList.forEach((s) => {
      const key = getSessionGroupKey(s)
      if (!groups.has(key)) {
        groups.set(key, {
          key,
          section_id: s.section_id ?? null,
          section_code: s.section_code || s.subject_code || '',
          subject_name: getSessionSubjectValue(s),
          section_group: s.section_group || '',
          class_name: s.class_name || '',
          sessions: [],
        })
      }
      groups.get(key).sessions.push(s)
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

  const groupedSections = useMemo(() => {
    return groupSessionsBySection(sessions);
  }, [sessions]);

  const selectedSection = useMemo(
    () => groupedSections.find(g => g.key === selectedSectionKey) || null,
    [groupedSections, selectedSectionKey],
  )

  const selectedSectionSessions = selectedSection?.sessions || []

  const handleSectionChange = (sectionKey) => {
    setSelectedSectionKey(sectionKey);
    const group = groupedSections.find(g => g.key === sectionKey);
    if (group && group.sessions.length > 0) {
      const bestSession = pickBestSessionInGroup(group.sessions);
      setSessionId(bestSession ? String(getSessionIdValue(bestSession)) : '');
    } else {
      setSessionId('');
    }
  };

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

  // ── Load dữ liệu ban đầu ──────────────────────────────────────── //
  const loadBaseData = async () => {
    try {
      const data = await fetchSessionsForUser(user)
      setSessions(data)
      if (data.length > 0) {
        const best = pickBestInitialGroup(groupSessionsBySection(data))
        if (best) {
          const sId = String(getSessionIdValue(best.session))
          setSessionId(sId)
          setSelectedSectionKey(best.group.key)
        }
      } else {
        setSessionId('')
        setSelectedSectionKey('')
      }
    } catch (err) {
      setMessage(getApiErrorMessage(err, 'Không tải được dữ liệu điểm danh.'))
    }
  }

  const loadSessionAttendance = async (sid) => {
    if (!sid) { setSessionAttendance([]); return }
    try {
      const res = await api.get(`/reports/session/${sid}`)
      setSessionAttendance(res.data)
    } catch (err) {
      setMessage(getApiErrorMessage(err, 'Không tải được danh sách điểm danh.'))
    }
  }

  useEffect(() => {
    let mounted = true
    const init = async () => {
      try {
        const data = await fetchSessionsForUser(user)
        if (!mounted) return
        setSessions(data)
        if (data.length > 0) {
          const best = pickBestInitialGroup(groupSessionsBySection(data))
          if (best) {
            const sId = String(getSessionIdValue(best.session))
            setSessionId(sId)
            setSelectedSectionKey(best.group.key)
          }
        }
      } catch (err) {
        if (mounted) setMessage(getApiErrorMessage(err, 'Không tải được dữ liệu điểm danh.'))
      }
    }
    init()
    return () => { mounted = false }
  }, [user])

  useEffect(() => {
    let mounted = true
    const load = async () => {
      if (!sessionId) { setSessionAttendance([]); return }
      try {
        const res = await api.get(`/reports/session/${sessionId}`)
        if (mounted) setSessionAttendance(res.data)
      } catch (err) {
        if (mounted) setMessage(getApiErrorMessage(err, 'Không tải được danh sách điểm danh.'))
      }
    }
    load()
    return () => { mounted = false }
  }, [sessionId])

  useEffect(() => {
    return () => { stream?.getTracks().forEach((t) => t.stop()) }
  }, [stream])

  useEffect(() => {
    return () => {
      if (testPreviewUrl) URL.revokeObjectURL(testPreviewUrl)
    }
  }, [testPreviewUrl])

  // Cleanup canvas overlay on unmount
  useEffect(() => {
    return () => {
      const canvas = overlayCanvasRef.current
      if (canvas) {
        const ctx = canvas.getContext('2d')
        if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height)
      }
    }
  }, [])

  // Auto-hide camera alert toast after 4 seconds
  useEffect(() => {
    if (!alertToast) return
    const timer = setTimeout(() => {
      setAlertToast(null)
    }, 4000)
    return () => clearTimeout(timer)
  }, [alertToast])


  const drawBoundingBoxes = (results) => {
    const canvas = overlayCanvasRef.current
    if (!canvas || !videoRef.current) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // Set canvas internal resolution to match video native resolution
    canvas.width = videoRef.current.videoWidth || 640
    canvas.height = videoRef.current.videoHeight || 480

    ctx.clearRect(0, 0, canvas.width, canvas.height)
    if (!results || results.length === 0) return

    results.forEach((face) => {
      const bbox = face.bbox
      if (!bbox) return

      let color = '#9ca3af' // grey
      if (face.status === 'success') {
        color = '#00c9a7' // xanh (teal)
      } else if (face.status === 'uncertain') {
        color = '#fbbf24' // vàng (amber)
      } else if (face.status === 'spoof') {
        color = '#f43f5e' // đỏ (red)
      }

      ctx.strokeStyle = color
      ctx.lineWidth = Math.max(3, Math.round(canvas.width / 250))
      ctx.strokeRect(bbox.x, bbox.y, bbox.w, bbox.h)

      const name = face.full_name || face.student_code || 'Unknown'
      
      let details = []
      if (face.confidence) {
        details.push(`${(face.confidence * 100).toFixed(0)}%`)
      }
      
      if (face.liveness_score !== undefined && face.liveness_score !== null) {
        details.push(`Liveness: ${(face.liveness_score * 100).toFixed(0)}%`)
      } else if (face.liveness_score === null) {
        details.push('Liveness: disabled')
      }

      const detailsText = details.length > 0 ? ` (${details.join(', ')})` : ''
      const labelText = `${name}${detailsText}`

      ctx.fillStyle = color
      const fontSize = Math.max(14, Math.round(canvas.width / 35))
      ctx.font = `bold ${fontSize}px sans-serif`

      const textWidth = ctx.measureText(labelText).width
      const padding = 8
      const rectX = bbox.x
      const rectY = Math.max(0, bbox.y - fontSize - padding)
      const rectW = textWidth + padding * 2
      const rectH = fontSize + padding

      ctx.fillRect(rectX, rectY, rectW, rectH)

      ctx.fillStyle = '#ffffff'
      ctx.fillText(labelText, bbox.x + padding, rectY + fontSize - 2)
    })
  }

  const handleCheckinResult = (checkinData, recognizedCode, recognizedStudent, confidence, finalLivenessScore) => {
    const checkinStatus = (checkinData.status || '').toLowerCase()
    
    if (['spoof', 'unknown', 'not_enrolled', 'late_entry'].includes(checkinStatus)) {
      let alertMsg = ''
      if (checkinStatus === 'spoof') {
        alertMsg = 'Phát hiện giả mạo khuôn mặt.'
      } else if (checkinStatus === 'unknown') {
        alertMsg = 'Phát hiện khuôn mặt không xác định.'
      } else if (checkinStatus === 'not_enrolled') {
        const svNameOrCode = recognizedStudent?.full_name || recognizedCode || 'Sinh viên'
        alertMsg = `${svNameOrCode} không thuộc danh sách đăng ký buổi học.`
      } else if (checkinStatus === 'late_entry') {
        alertMsg = 'Sinh viên quét ngoài cửa sổ điểm danh.'
      }
      
      setAlertToast({
        type: checkinStatus,
        message: alertMsg,
        alertId: checkinData.alert_id,
        alertType: checkinData.alert_type,
      })
      
      setResult({
        success: false,
        status: checkinStatus,
        studentCode: recognizedCode || 'Không xác định',
        student: recognizedStudent,
        confidence,
        livenessScore: finalLivenessScore,
        message: alertMsg,
      })
      setMessage(alertMsg)
      if (window.innerWidth < 768) setMobileStep(4)
      return true
    }
    return false
  }

  const handleCheckinError = (err, recognizedCode, recognizedStudent, confidence, finalLivenessScore) => {
    const responseData = err.response?.data
    const status = responseData?.status || responseData?.detail?.status
    const msg = responseData?.message || responseData?.detail?.message
    
    if (status && ['spoof', 'unknown', 'not_enrolled', 'late_entry', 'insufficient_enrollments'].includes(status.toLowerCase())) {
      const mappedStatus = status.toLowerCase()
      let alertMsg = ''
      if (mappedStatus === 'spoof') {
        alertMsg = 'Phát hiện giả mạo khuôn mặt.'
      } else if (mappedStatus === 'unknown') {
        alertMsg = 'Phát hiện khuôn mặt không xác định.'
      } else if (mappedStatus === 'not_enrolled') {
        const svNameOrCode = recognizedStudent?.full_name || recognizedCode || 'Sinh viên'
        alertMsg = `${svNameOrCode} không thuộc danh sách đăng ký buổi học.`
      } else if (mappedStatus === 'late_entry') {
        alertMsg = 'Sinh viên quét ngoài cửa sổ điểm danh.'
      } else if (mappedStatus === 'insufficient_enrollments') {
        alertMsg = 'Buổi học chưa đủ tối thiểu 5 sinh viên đăng ký.'
      }
      
      setAlertToast({
        type: mappedStatus,
        message: alertMsg,
        alertId: responseData?.alert_id || responseData?.detail?.alert_id,
        alertType: responseData?.alert_type || responseData?.detail?.alert_type,
      })
      
      setResult({
        success: false,
        status: mappedStatus,
        studentCode: recognizedCode || 'Không xác định',
        student: recognizedStudent,
        confidence,
        livenessScore: finalLivenessScore,
        message: alertMsg,
      })
      setMessage(alertMsg)
      if (window.innerWidth < 768) setMobileStep(4)
      return true
    }
    return false
  }

  const renderAlertToast = () => {
    if (!alertToast) return null

    let bgColor = 'rgba(239, 68, 68, 0.95)'
    let borderColor = 'rgba(239, 68, 68, 0.4)'
    let icon = '🚨'
    let title = 'CẢNH BÁO BẢO MẬT'

    const typeLower = (alertToast.type || '').toLowerCase()
    if (typeLower === 'spoof') {
      bgColor = 'rgba(239, 68, 68, 0.95)'
      borderColor = 'rgba(239, 68, 68, 0.4)'
      icon = '🚨'
      title = 'PHÁT HIỆN GIẢ MẠO'
    } else if (typeLower === 'unknown' || typeLower === 'unknown_face') {
      bgColor = 'rgba(239, 68, 68, 0.95)'
      borderColor = 'rgba(239, 68, 68, 0.4)'
      icon = '❓'
      title = 'KHUÔN MẶT LẠ'
    } else if (typeLower === 'not_enrolled') {
      bgColor = 'rgba(249, 115, 22, 0.95)'
      borderColor = 'rgba(249, 115, 22, 0.4)'
      icon = '⚠️'
      title = 'CHƯA ĐĂNG KÝ BUỔI HỌC'
    } else if (typeLower === 'late_entry') {
      bgColor = 'rgba(234, 179, 8, 0.95)'
      borderColor = 'rgba(234, 179, 8, 0.4)'
      icon = '⏳'
      title = 'QUÉT NGOÀI KHUNG GIỜ'
    } else if (typeLower === 'insufficient_enrollments') {
      bgColor = 'rgba(234, 179, 8, 0.95)'
      borderColor = 'rgba(234, 179, 8, 0.4)'
      icon = '👥'
      title = 'THIẾU ĐĂNG KÝ TỐI THIỂU'
    }

    return (
      <div className="camera-alert-toast" style={{ background: bgColor, border: `1px solid ${borderColor}` }}>
        <span style={{ fontSize: '20px', lineHeight: 1 }}>{icon}</span>
        <div style={{ flex: 1, textAlign: 'left' }}>
          <div style={{ fontWeight: 800, fontSize: '11px', letterSpacing: '0.05em', marginBottom: '2px', opacity: 0.9 }}>
            {title}
          </div>
          <div style={{ fontSize: '13px', fontWeight: 500, lineHeight: 1.4 }}>
            {alertToast.message}
          </div>
          {(alertToast.alertId || alertToast.alertType) && (
            <div style={{ fontSize: '10px', marginTop: '4px', opacity: 0.85, fontFamily: 'monospace' }}>
              {alertToast.alertType && `Loại cảnh báo: ${alertToast.alertType}`}
              {alertToast.alertId && ` | Mã ID: #${alertToast.alertId}`}
            </div>
          )}
        </div>
        <button
          onClick={() => setAlertToast(null)}
          style={{
            background: 'none',
            border: 'none',
            color: '#ffffff',
            fontSize: '18px',
            cursor: 'pointer',
            padding: '2px',
            lineHeight: 1,
            opacity: 0.7,
            transition: 'opacity 0.2s',
          }}
          onMouseEnter={(e) => e.target.style.opacity = '1'}
          onMouseLeave={(e) => e.target.style.opacity = '0.7'}
        >
          &times;
        </button>
      </div>
    )
  }

  // ── Camera ────────────────────────────────────────────────────── //
  const startCamera = async () => {
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' },
      })
      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream
      }
      setStream(mediaStream)
      setMessage('Camera đã sẵn sàng.')
    } catch {
      setMessage('Không mở được camera. Vui lòng kiểm tra quyền truy cập camera và thử lại.')
    }
  }

  const stopCamera = () => {
    stream?.getTracks().forEach((t) => t.stop())
    setStream(null)
    const canvas = overlayCanvasRef.current
    if (canvas) {
      const ctx = canvas.getContext('2d')
      if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height)
    }
  }

  // ── Điểm danh ────────────────────────────────────────────────── //
  const postAttendanceAction = (studentCode, confidence, act = action) => {
    const payload = {
      student_code: studentCode,
      session_id:   Number(sessionId),
      confidence,
    }
    // Gửi kèm thông số GPS nếu có sẵn
    if (gpsCoords) {
      payload.gps_lat = gpsCoords.lat
      payload.gps_lng = gpsCoords.lng
      payload.gps_accuracy = gpsCoords.accuracy
    }
    return api.post(act === 'checkout' ? '/attendance/checkout' : '/attendance/checkin', payload)
  }

  const captureAndProcess = async () => {
    if (!sessionId) { setMessage('Hãy chọn buổi học trước.'); return }
    if (!stream || !videoRef.current) { setMessage('Hãy bật camera trước.'); return }

    setLoading(true)

    // Clear old bounding boxes
    const canvasOverlay = overlayCanvasRef.current
    if (canvasOverlay) {
      const ctx = canvasOverlay.getContext('2d')
      if (ctx) ctx.clearRect(0, 0, canvasOverlay.width, canvasOverlay.height)
    }

    const canvas  = canvasRef.current
    const context = canvas.getContext('2d')
    canvas.width  = videoRef.current.videoWidth
    canvas.height = videoRef.current.videoHeight
    context.drawImage(videoRef.current, 0, 0)

    canvas.toBlob(async (blob) => {
      if (!blob) { setMessage('Không thể chụp ảnh từ camera.'); setLoading(false); return }

      const formData = new FormData()
      formData.append('file', blob, 'capture.jpg')
      formData.append('session_id', String(sessionId))
      if (import.meta.env.DEV) {
        console.debug('recognize request payload', {
          selectedSessionId: sessionId,
          hasBlob: Boolean(blob),
          blobSize: blob.size,
        })
      }

      try {
        const recRes = await api.post('/recognize', formData)
        if (import.meta.env.DEV) {
          console.debug('recognize response payload', recRes.data)
        }
        const {
          status,
          student_code,
          student,
          confidence,
          message: msg,
          official_attendance_allowed,
          official_attendance_warning,
          audit_id,
          requires_manual_confirmation,
          reason,
          official_attendance_warning_code,
          results,
          face_count,
          liveness_score,
        } = recRes.data
        const recognizedStudent = student || null
        const recognizedCode = recognizedStudent?.student_code || student_code

        // Draw bounding boxes on overlay canvas (fallback compatible with legacy endpoints)
        const activeResults = results || (recognizedCode ? [{
          student_code: recognizedCode,
          full_name: recognizedStudent?.full_name || recRes.data.full_name,
          class_name: recognizedStudent?.class_name,
          confidence,
          status,
          bbox: null,
          liveness_score: liveness_score
        }] : [])

        if (activeResults.length > 0) {
          drawBoundingBoxes(activeResults)
        }

        const hasSpoof = status === 'spoof' || activeResults.some(r => r.status === 'spoof')

        if (hasSpoof) {
          const spoofItem = activeResults.find(r => r.status === 'spoof') || {}
          const finalScore = spoofItem.liveness_score !== undefined && spoofItem.liveness_score !== null
            ? spoofItem.liveness_score
            : liveness_score

          const alertMsg = 'Phát hiện giả mạo khuôn mặt.'
          setResult({
            success: false,
            status: 'spoof',
            studentCode: recognizedCode || 'Không xác định',
            student: recognizedStudent,
            confidence: finalScore || 0,
            livenessScore: finalScore,
            message: alertMsg
          })
          setMessage(alertMsg)
          setAlertToast({
            type: 'spoof',
            message: alertMsg,
            alertId: recRes.data.alert_id,
            alertType: recRes.data.alert_type || 'SPOOF',
          })
          if (window.innerWidth < 768) setMobileStep(4)
          return
        }

        const primaryResult = activeResults.find(r => r.student_code === recognizedCode) || activeResults[0]
        const finalLivenessScore = (primaryResult?.liveness_score !== undefined)
          ? primaryResult.liveness_score
          : liveness_score

        const classMismatch = isClassMismatchRecognition({
          reason,
          official_attendance_warning_code,
          requires_manual_confirmation,
        })
        const classMismatchMessage = getClassMismatchMessage(recognizedStudent, selectedSession)
        const blockMessage = official_attendance_warning ||
          (recognizedStudent && !isOfficialStudent(recognizedStudent) ? OFFICIAL_BLOCK_MESSAGE : '')

        if (recognizedCode && classMismatch && audit_id) {
          setResult({ success: false, status: 'blocked', studentCode: recognizedCode, student: recognizedStudent,
            confidence, livenessScore: finalLivenessScore, message: classMismatchMessage })
          setMessage(classMismatchMessage)
          if (window.innerWidth < 768) setMobileStep(4)
          return
        }

        if (recognizedCode && official_attendance_allowed === false && blockMessage) {
          setResult({ success: false, status: 'blocked', studentCode: recognizedCode, student: recognizedStudent,
            confidence, livenessScore: finalLivenessScore, message: blockMessage })
          setMessage(blockMessage)
          if (window.innerWidth < 768) setMobileStep(4)
          return
        }

        if ((status === 'success' || status === 'uncertain') && recognizedCode) {
          try {
            const checkinRes = await postAttendanceAction(recognizedCode, confidence)
            const checkinData = checkinRes.data
            const isAlert = handleCheckinResult(checkinData, recognizedCode, recognizedStudent, confidence, finalLivenessScore)
            if (isAlert) {
              return
            }
            setResult({ success: true, status, studentCode: recognizedCode, student: recognizedStudent, confidence, action,
              livenessScore: finalLivenessScore, message: `Đã ghi nhận ${actionLabels[action]} cho ${recognizedCode}.` })
            setMessage(`Đã ghi nhận ${actionLabels[action]} cho ${recognizedCode}.`)
            await loadSessionAttendance(sessionId)
            if (window.innerWidth < 768) setMobileStep(4)
          } catch (err) {
            const isAlert = handleCheckinError(err, recognizedCode, recognizedStudent, confidence, finalLivenessScore)
            if (isAlert) {
              return
            }
            throw err
          }

        } else {
          if (status === 'unknown' || status === 'unknown_face' || status === 'uncertain') {
            const alertMsg = 'Phát hiện khuôn mặt không xác định.'
            setAlertToast({
              type: 'unknown',
              message: alertMsg,
              alertId: recRes.data.alert_id,
              alertType: recRes.data.alert_type || 'UNKNOWN_FACE',
            })
          }
          setResult({ success: false, status, studentCode: recognizedCode || 'Không xác định', student: recognizedStudent,
            confidence, livenessScore: finalLivenessScore, message: recognitionMessages[status] || msg })
          setMessage(recognitionMessages[status] || msg)
          if (window.innerWidth < 768) setMobileStep(4)
        }
      } catch (err) {
        setResult(null)
        setMessage(getApiErrorMessage(err, 'Không xử lý được nhận diện.'))
        if (window.innerWidth < 768) setMobileStep(4)
      } finally {
        setLoading(false)
      }
    }, 'image/jpeg', 0.95)
  }

  const deleteAttendanceRecord = async (record) => {
    if (!record?.record_id) return
    if (!canDeleteAttendance) {
      setMessage('Lỗi: Bạn không có quyền xóa bản ghi điểm danh.')
      return
    }

    const studentLabel = `${record.student_code || '-'} - ${record.full_name || '-'}`
    const confirmed = window.confirm(
      `Bạn có chắc muốn xóa bản ghi điểm danh của sinh viên ${studentLabel} khỏi buổi học này không?`,
    )
    if (!confirmed) return

    setDeletingRecordId(record.record_id)
    try {
      await api.delete(`/attendance/${record.record_id}`)
      setMessage(`Đã xóa bản ghi điểm danh của ${studentLabel}.`)
      await loadSessionAttendance(sessionId)
    } catch (err) {
      setMessage(getApiErrorMessage(err, 'Không xóa được bản ghi điểm danh.'))
    } finally {
      setDeletingRecordId(null)
    }
  }

  const runModelTest = async () => {
    if (!testFile) {
      setMessage('Vui lòng chọn một ảnh để kiểm thử.')
      return
    }
    const formData = new FormData()
    formData.append('file', testFile)
    setTestLoading(true)
    setTestResult(null)
    setMessage('')
    try {
      const response = await api.post('/recognize/model-test', formData)
      setTestResult(response.data)
    } catch (err) {
      setMessage(getApiErrorMessage(err, 'Không kiểm thử được mô hình.'))
    } finally {
      setTestLoading(false)
    }
  }

  const handleTestFileChange = (event) => {
    const file = event.target.files?.[0] || null
    if (testPreviewUrl) URL.revokeObjectURL(testPreviewUrl)
    setTestFile(file)
    setTestPreviewUrl(file ? URL.createObjectURL(file) : '')
    setTestResult(null)
    setMessage('')
  }

  const isDemoModelResult = testResult?.data_source === 'kaggle' ||
    testResult?.is_demo ||
    testResult?.student?.data_source === 'kaggle' ||
    testResult?.student?.is_demo

  // ── RENDER MOBILE FLOW ─────────────────────────────────────────── //
  const renderMobileFlow = () => {
    switch (mobileStep) {
      case 1:
        return (
          <div style={{ animation: 'fadeUp 0.35s ease both' }}>
            <div className="page-header" style={{ marginBottom: 12 }}>
              <p className="eyebrow">Bước 1 / 4</p>
              <h2 className="page-title" style={{ fontSize: '20px' }}>Chọn lớp học phần</h2>
              <p className="page-subtitle">Chọn một lớp học phần để tiến hành điểm danh.</p>
            </div>
            
            {groupedSections.length === 0 ? (
              <div className="empty-state">Chưa có lớp học phần nào được lên lịch hôm nay.</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {groupedSections.map((group) => {
                  const metrics = getGroupMetrics(group);
                  const bestSession = pickBestSessionInGroup(group.sessions);
                  return (
                    <div
                      key={group.key}
                      className="mobile-card"
                      style={{
                        cursor: 'pointer',
                        border: selectedSectionKey === group.key ? '1px solid var(--teal)' : '1px solid var(--bdr)'
                      }}
                      onClick={() => {
                        setSelectedSectionKey(group.key);
                        setActiveMobileGroup(group);
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontWeight: 800, color: 'var(--white)' }}>
                          {formatSectionLabel(group)}
                        </span>
                      </div>
                      <div className="mobile-card-row">
                        <span className="mobile-card-label">Mã học phần:</span>
                        <span className="mobile-card-value" style={{ fontFamily: 'var(--mono)' }}>{group.section_code || '-'}</span>
                      </div>
                      <div className="mobile-card-row">
                        <span className="mobile-card-label">Tên học phần:</span>
                        <span className="mobile-card-value">{group.subject_name || '-'}</span>
                      </div>
                      <div className="mobile-card-row">
                        <span className="mobile-card-label">Nhóm:</span>
                        <span className="mobile-card-value" style={{ color: 'var(--teal)' }}>{group.section_group || '-'}</span>
                      </div>
                      <div className="mobile-card-row">
                        <span className="mobile-card-label">Lớp:</span>
                        <span className="mobile-card-value" style={{ fontFamily: 'var(--mono)' }}>{group.class_name || '-'}</span>
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--white2)', marginTop: '4px' }}>
                        Buổi ưu tiên: {bestSession ? `${formatSessionOptionLabel(bestSession)}` : '-'}
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--muted)', marginTop: '4px' }}>
                        Tổng số buổi: {metrics.total} ({metrics.ongoing} đang, {metrics.upcoming} sắp, {metrics.finished} xong)
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Session selector Modal */}
            {activeMobileGroup && (
              <div
                role="dialog"
                aria-modal="true"
                style={{
                  position: 'fixed',
                  inset: 0,
                  background: 'rgba(0,0,0,.65)',
                  display: 'flex',
                  alignItems: 'flex-end',
                  zIndex: 1000,
                  animation: 'fadeIn 0.2s ease'
                }}
                onClick={() => setActiveMobileGroup(null)}
              >
                <div
                  style={{
                    width: '100%',
                    maxHeight: '75vh',
                    background: 'var(--navy2)',
                    borderTop: '1px solid var(--bdr2)',
                    borderTopLeftRadius: 16,
                    borderTopRightRadius: 16,
                    padding: '20px 16px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 16,
                    animation: 'slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
                  }}
                  onClick={(e) => e.stopPropagation()}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--bdr)', paddingBottom: 10 }}>
                    <div>
                      <h3 style={{ margin: 0, fontSize: 16, color: 'var(--white)' }}>Chọn buổi học</h3>
                      <p style={{ margin: '4px 0 0', fontSize: 12, color: 'var(--muted)' }}>
                        {formatSectionLabel(activeMobileGroup)}
                      </p>
                    </div>
                    <button
                      className="secondary"
                      onClick={() => setActiveMobileGroup(null)}
                      style={{ minHeight: 32, padding: '0 8px', fontSize: 18 }}
                    >
                      ✕
                    </button>
                  </div>

                  <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 10, paddingBottom: 20 }}>
                    {activeMobileGroup.sessions.map((s) => {
                      const status = getSessionStatus(s);
                      return (
                        <div
                          key={getSessionIdValue(s)}
                          className="mobile-card"
                          style={{
                            cursor: 'pointer',
                            border: sessionId === String(getSessionIdValue(s)) ? '1px solid var(--teal)' : '1px solid var(--bdr)',
                            padding: 12
                          }}
                          onClick={() => {
                            setSessionId(String(getSessionIdValue(s)));
                            setActiveMobileGroup(null);
                            setMobileStep(2);
                            setResult(null);
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ fontWeight: 700, color: 'var(--white)' }}>
                              Buổi {s.session_number || `#${getSessionIdValue(s)}`}
                            </span>
                            <span className={status.badgeClass} style={{ fontSize: 10 }}>
                              {status.label}
                            </span>
                          </div>
                          <div style={{ fontSize: '12px', color: 'var(--white2)', marginTop: 4 }}>
                            {formatDateForDisplay(getSessionDateValue(s))}
                          </div>
                          <div style={{ fontSize: '12px', color: 'var(--muted)' }}>
                            {s.start_time?.slice(0, 5)} - {s.end_time?.slice(0, 5)} {s.room_name ? ` - ${s.room_name}` : ''}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}
            
            <style>{`
              @keyframes slideUp {
                from { transform: translateY(100%); }
                to { transform: translateY(0); }
              }
            `}</style>
          </div>
        )
      
      case 2:
        return (
          <div style={{ animation: 'fadeUp 0.35s ease both' }}>
            <div className="page-header" style={{ marginBottom: 12 }}>
              <p className="eyebrow">Bước 2 / 4</p>
              <h2 className="page-title" style={{ fontSize: '20px' }}>Xác thực điều kiện</h2>
              <p className="page-subtitle">Kiểm tra tọa độ GPS và thời hạn điểm danh của buổi học.</p>
            </div>

            {selectedSession && (
              <div className="mobile-card" style={{ marginBottom: '14px', background: 'rgba(0, 201, 167, 0.03)' }}>
                <div style={{ fontWeight: 800, color: 'var(--white)' }}>{getSessionSubjectValue(selectedSession)}</div>
                <div style={{ fontSize: '13px', color: 'var(--muted)' }}>
                  Lớp học phần: {formatSectionLabel({
                    section_code: selectedSession.section_code || selectedSession.subject_code || '',
                    subject_name: getSessionSubjectValue(selectedSession),
                    section_group: selectedSession.section_group || '',
                    class_name: selectedSession.class_name || '',
                  })}
                </div>
              </div>
            )}

            <AttendanceCountdown
              sessionDate={selectedSession ? getSessionDateValue(selectedSession) : undefined}
              startTime={selectedSession?.start_time}
              onStatusChange={setTimeStatus}
            />

            <GPSStatus
              targetLocation={selectedClassroom}
              onLocationChange={setGpsCoords}
            />

            <div className="toolbar" style={{ marginTop: '16px', display: 'flex', gap: '10px' }}>
              <button
                className="secondary"
                style={{ flex: 1, minHeight: 48 }}
                onClick={() => setMobileStep(1)}
              >
                Quay lại
              </button>
              <button
                style={{ flex: 2, minHeight: 48 }}
                onClick={() => {
                  setMobileStep(3)
                  startCamera()
                }}
              >
                Tiếp tục (Quét mặt)
              </button>
            </div>
          </div>
        )

      case 3:
        return (
          <div style={{ animation: 'fadeUp 0.35s ease both' }}>
            <div className="page-header" style={{ marginBottom: 12 }}>
              <p className="eyebrow">Bước 3 / 4</p>
              <h2 className="page-title" style={{ fontSize: '20px' }}>Chụp ảnh khuôn mặt</h2>
              <p className="page-subtitle">Cân chỉnh khuôn mặt vào giữa khung hình camera và bấm nút điểm danh.</p>
            </div>

            <div className="panel panel-pad" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ display: 'flex', gap: '10px', marginBottom: '8px' }}>
                <select
                  style={{ flex: 1, minHeight: 48 }}
                  value={action}
                  onChange={(e) => setAction(e.target.value)}
                >
                  {actionOptions.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>

              <div style={{ position: 'relative', width: '100%', background: '#000', borderRadius: 8, overflow: 'hidden', aspectRatio: '4/3' }}>
                <video
                  ref={videoRef}
                  autoPlay
                  playsInline
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                />
                <canvas ref={canvasRef} style={{ display: 'none' }} />
                <canvas
                  ref={overlayCanvasRef}
                  style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', objectFit: 'cover', pointerEvents: 'none', zIndex: 10 }}
                />
                {renderAlertToast()}
                {!stream && (
                  <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.8)' }}>
                    <button onClick={startCamera} style={{ minHeight: 48 }}>Bật Camera</button>
                  </div>
                )}
              </div>

              <div className="toolbar" style={{ display: 'flex', gap: '8px' }}>
                <button
                  className="secondary"
                  style={{ flex: 1, minHeight: 48 }}
                  onClick={() => {
                    stopCamera()
                    setMobileStep(2)
                  }}
                >
                  Quay lại
                </button>
                <button
                  style={{ flex: 2, minHeight: 48 }}
                  onClick={captureAndProcess}
                  disabled={!stream || loading}
                >
                  {loading ? 'Đang xử lý...' : `Ghi nhận ${actionLabels[action]}`}
                </button>
              </div>
            </div>
          </div>
        )

      case 4:
        const style = result ? getStyle(result.status) : getStyle('error')
        return (
          <div style={{ animation: 'fadeUp 0.35s ease both' }}>
            <div className="page-header" style={{ marginBottom: 12 }}>
              <p className="eyebrow">Bước 4 / 4</p>
              <h2 className="page-title" style={{ fontSize: '20px' }}>Kết quả điểm danh</h2>
            </div>

            <div
              style={{
                padding: '20px',
                borderRadius: 'var(--r)',
                background: style.bg,
                border: `1px solid ${style.border}`,
                color: style.text,
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
              }}
            >
              <div style={{ fontSize: '18px', fontWeight: '800', color: style.accent }}>
                {style.label}
              </div>
              
              {result?.studentCode && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '14px', borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '10px' }}>
                  <div><strong>Mã SV:</strong> {result.studentCode}</div>
                  {result.student?.full_name && <div><strong>Tên SV:</strong> {result.student.full_name}</div>}
                  {result.student?.class_name && <div><strong>Lớp:</strong> {result.student.class_name}</div>}
                  <div><strong>Độ tương đồng:</strong> {formatConf(result.confidence)}</div>
                  {result.livenessScore !== undefined && (
                    <div>
                      <strong>Liveness:</strong> {result.livenessScore !== null ? `${(result.livenessScore * 100).toFixed(0)}%` : 'disabled'}
                    </div>
                  )}
                  {result.action && <div><strong>Hình thức:</strong> Điểm danh {actionLabels[result.action]}</div>}
                </div>
              )}

              <p style={{ fontSize: '13px', color: style.muted, margin: '8px 0 0 0' }}>
                {result?.message || message}
              </p>

              <button
                style={{ marginTop: '14px', minHeight: 48, width: '100%', justifyContent: 'center' }}
                onClick={() => {
                  stopCamera()
                  setResult(null)
                  setMobileStep(1)
                }}
              >
                Hoàn tất & Quay lại
              </button>
            </div>
          </div>
        )

      default:
        return null
    }
  }

  // ── RENDER DESKTOP FLOW ────────────────────────────────────────── //
  const renderDesktopFlow = () => {
    return (
      <>
        <div style={{ marginBottom: 16 }}>
          <button
            className={mode === 'official' ? '' : 'secondary'}
            onClick={() => setMode('official')}
          >
            Điểm danh chính thức
          </button>
          {isAdmin && (
            <button
              className={mode === 'model-test' ? '' : 'secondary'}
              onClick={() => setMode('model-test')}
              style={{ marginLeft: 8 }}
            >
              Kiểm thử mô hình
            </button>
          )}
        </div>

        {mode === 'model-test' && (
          <div className="panel panel-pad" style={{ marginBottom: 16 }}>
            <h3 style={{ marginTop: 0 }}>Kiểm thử mô hình</h3>
            <p style={{ color: 'var(--muted)', fontSize: 13 }}>
              Chức năng này chỉ dùng để đánh giá mô hình, không dùng cho điểm danh sinh viên thật.
            </p>
            <div className="toolbar" style={{ marginTop: 12 }}>
              <input
                type="file"
                accept="image/*"
                onChange={handleTestFileChange}
              />
              <button onClick={runModelTest} disabled={!testFile || testLoading}>
                {testLoading ? 'Đang kiểm thử...' : 'Kiểm thử nhận diện'}
              </button>
            </div>

            {testPreviewUrl && (
              <div style={{ marginTop: 14, maxWidth: 360 }}>
                <img
                  src={testPreviewUrl}
                  alt="Ảnh kiểm thử đã chọn"
                  style={{ width: '100%', borderRadius: 8, border: '1px solid var(--bdr)', display: 'block' }}
                />
              </div>
            )}

            {testResult && (
              <div style={{ marginTop: 16, padding: 16, borderRadius: 8, background: 'var(--card)', border: '1px solid var(--bdr)' }}>
                <p style={{ fontWeight: 700, marginTop: 0 }}>Kết quả</p>
                {isDemoModelResult && (
                  <p className="status-message" style={{ marginTop: 0 }}>
                    Đây là dữ liệu Kaggle/demo, chỉ dùng để đánh giá mô hình, không dùng để điểm danh chính thức.
                  </p>
                )}
                <p>Trạng thái: {getDisplayLabel(recognitionStatusLabels, testResult.status)}</p>
                <p>Mã mẫu: {testResult.sample_code || testResult.student?.student_code || testResult.student_code || '-'}</p>
                <p>Tên mẫu: {testResult.full_name || testResult.student?.full_name || '-'}</p>
                <p>Nguồn dữ liệu: {getDisplayLabel(dataSourceLabels, testResult.data_source || testResult.student?.data_source)}</p>
                <p>Dữ liệu minh họa: {(testResult.is_demo ?? testResult.student?.is_demo) ? 'Có' : 'Không'}</p>
                <p>Phương thức đăng ký: {getDisplayLabel(registrationMethodLabels, testResult.registration_method || testResult.student?.registration_method)}</p>
                <p>Độ tương đồng: {formatConf(testResult.confidence)}</p>
                <p>Thời gian xử lý: {testResult.processing_time_ms ?? testResult.processing_ms ?? '-'} ms</p>
                <p>{testResult.message}</p>
              </div>
            )}
          </div>
        )}

        {mode === 'official' && (
          <>
            <div style={{ marginBottom: 12 }}>
              <span className="badge success">Điểm danh chính thức</span>
            </div>
            <div className="panel panel-pad" style={{ marginBottom: 16 }}>
              <div className="form-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
                {sessions.length === 0 ? (
                  <p style={{ color: 'var(--color-text-secondary)', fontSize: 13, gridColumn: '1 / -1' }}>
                    Chưa có buổi học. Vui lòng tạo buổi học tại mục <strong>Buổi học</strong> trước.
                  </p>
                ) : (
                  <>
                    <select
                      value={selectedSectionKey}
                      onChange={(e) => handleSectionChange(e.target.value)}
                    >
                      <option value="">-- Chọn lớp học phần --</option>
                      {groupedSections.map((group) => (
                        <option key={group.key} value={group.key}>
                          {formatSectionLabel(group)}
                        </option>
                      ))}
                    </select>

                    <select
                      value={sessionId}
                      onChange={(e) => setSessionId(e.target.value)}
                      disabled={!selectedSectionKey}
                    >
                      <option value="">-- Chọn buổi học --</option>
                      {selectedSectionSessions.map((s) => (
                        <option key={getSessionIdValue(s)} value={getSessionIdValue(s)}>
                          {formatSessionOptionLabel(s)}
                        </option>
                      ))}
                    </select>
                  </>
                )}

                <select value={action} onChange={(e) => setAction(e.target.value)}>
                  {actionOptions.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>

                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={loadBaseData} style={{ flex: 1 }}>Tải lại dữ liệu</button>
                  <button onClick={() => loadSessionAttendance(sessionId)} disabled={!sessionId} style={{ flex: 1 }}>
                    Tải lại bảng điểm danh
                  </button>
                </div>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 0.8fr', gap: 16 }}>
              {/* Camera + nhận diện */}
              <div className="panel panel-pad">
                <div style={{ position: 'relative', width: '100%', maxWidth: 760, background: '#000', borderRadius: 8, overflow: 'hidden' }}>
                  <video
                    ref={videoRef} autoPlay playsInline
                    style={{ width: '100%', display: 'block' }}
                  />
                  <canvas ref={canvasRef} style={{ display: 'none' }} />
                  <canvas
                    ref={overlayCanvasRef}
                    style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 10 }}
                  />
                  {renderAlertToast()}
                </div>

                <div className="toolbar" style={{ marginTop: 12 }}>
                  <button onClick={startCamera}>Bật camera</button>
                  <button className="secondary" onClick={stopCamera}>Tắt camera</button>
                  <button onClick={captureAndProcess} disabled={!stream || loading || !sessionId}>
                    {loading ? 'Đang xử lý...' : `Nhận diện ${actionLabels[action]}`}
                  </button>
                </div>

                {result && (
                  <div style={{
                    marginTop: 16, padding: 16, borderRadius: 8,
                    background: getStyle(result.status).bg,
                    border: `1px solid ${getStyle(result.status).border}`,
                    color: getStyle(result.status).text,
                  }}>
                    <p style={{ fontWeight: 800, marginTop: 0, color: getStyle(result.status).accent }}>{getStyle(result.status).label}</p>
                    <p>Tên sinh viên: {result.student?.full_name || '-'}</p>
                    <p>Mã SV: {result.studentCode}</p>
                    <p>Lớp: {result.student?.class_name || '-'}</p>
                    <p>Lớp chính của buổi học: {selectedSession?.class_name || selectedSession?.section_code || '-'}</p>
                    <p>Độ tin cậy: {formatConf(result.confidence)}</p>
                    {result.livenessScore !== undefined && (
                      <p>Liveness: {result.livenessScore !== null ? `${(result.livenessScore * 100).toFixed(0)}%` : 'disabled'}</p>
                    )}
                    {result.success && result.action && (
                      <p>Trạng thái ghi nhận: Đã ghi nhận {actionLabels[result.action]}</p>
                    )}
                    <p style={{ color: getStyle(result.status).muted }}>
                      {result.message}
                    </p>
                  </div>
                )}
              </div>

              {/* Vùng GPSStatus & Countdown cho màn hình lớn (nếu chọn buổi học) */}
              {selectedSession && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <AttendanceCountdown
                    sessionDate={getSessionDateValue(selectedSession)}
                    startTime={selectedSession.start_time}
                  />
                  <GPSStatus
                    targetLocation={selectedClassroom}
                    onLocationChange={setGpsCoords}
                  />
                </div>
              )}
            </div>

            {/* Bảng điểm danh buổi học */}
            <div className="panel panel-pad" style={{ marginTop: 24 }}>
              <h3>Danh sách điểm danh của buổi học</h3>
              {!sessionId ? (
                <div className="empty-state">Chọn buổi học để xem danh sách điểm danh.</div>
              ) : !sessionAttendance.length ? (
                <div className="empty-state">Chưa có dữ liệu điểm danh cho buổi học này.</div>
              ) : (
                <div className="table-wrap">
                  <table className="data-table" style={{ minWidth: 820 }}>
                    <thead>
                      <tr>
                        {['Mã SV', 'Họ tên', 'Trạng thái', 'Vào lớp', 'Ra về', 'Độ tin cậy khi vào', 'Độ tin cậy khi ra', 'Xóa'].map((h) => (
                          <th key={h}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {sessionAttendance.map((record) => (
                        <tr key={record.record_id || record.student_code}>
                          <td>{record.student_code}</td>
                          <td>{record.full_name || '-'}</td>
                          <td>
                            <span className={`badge ${record.status === 'absent' ? 'danger' : record.status === 'late' ? 'warning' : 'success'}`}>
                              {getDisplayLabel(statusLabels, record.status)}
                            </span>
                          </td>
                          <td>{formatDT(record.check_in_at)}</td>
                          <td>{formatDT(record.check_out_at)}</td>
                          <td>{formatConf(record.check_in_conf)}</td>
                          <td>{formatConf(record.check_out_conf)}</td>
                          <td>
                            {record.record_id && canDeleteAttendance ? (
                              <button
                                className="secondary"
                                onClick={() => deleteAttendanceRecord(record)}
                                disabled={deletingRecordId === record.record_id}
                                style={{
                                  minHeight: 30,
                                  padding: '5px 10px',
                                  borderColor: 'rgba(244,63,94,.35)',
                                  color: '#fb7185',
                                }}
                              >
                                {deletingRecordId === record.record_id ? 'Đang xóa...' : 'Xóa'}
                              </button>
                            ) : (
                              <span style={{ color: 'var(--muted)' }}>-</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </>
        )}
      </>
    )
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <p className="eyebrow">Điểm danh</p>
          <h1 className="page-title">Điểm danh và theo dõi buổi học</h1>
          <p className="page-subtitle">
            Nhận diện khuôn mặt để ghi vào lớp/ra về. Quy trình điểm danh tự động kết hợp định vị tọa độ GPS và thời gian.
          </p>
        </div>
      </div>

      {isMobile ? renderMobileFlow() : renderDesktopFlow()}
    </div>
  )
}
