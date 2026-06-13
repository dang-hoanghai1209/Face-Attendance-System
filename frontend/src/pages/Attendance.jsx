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
  spoof: 'Phát hiện ảnh giả mạo hoặc không hợp lệ (Spoof).',
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
  if (status === 'spoof')     return { bg: 'rgba(244,63,94,.14)', border: 'rgba(244,63,94,.45)', accent: '#fb7185', text: '#f8fafc', muted: '#fecdd3', label: 'Xác thực ảnh thật thất bại (Spoof)' }
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
  const [pendingRecognition, setPendingRecognition] = useState(null)
  const [loading,            setLoading]            = useState(false)
  const [deletingRecordId,    setDeletingRecordId]    = useState(null)
  const [message,            setMessage]            = useState('')
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

  const selectedSession = useMemo(
    () => sessions.find((session) => String(session.id || session.session_id) === String(sessionId)),
    [sessions, sessionId],
  )

  const selectedClassroom = useMemo(() => {
    if (!selectedSession) return null
    // Nếu active-sessions trả về trực tiếp thông tin phòng học, ưu tiên sử dụng
    if (selectedSession.classroom_gps_lat !== undefined && selectedSession.classroom_gps_lng !== undefined) {
      return {
        id: selectedSession.classroom_id,
        name: selectedSession.classroom_name || 'Phòng học',
        gps_lat: selectedSession.classroom_gps_lat,
        gps_lng: selectedSession.classroom_gps_lng,
        radius_meters: selectedSession.radius_meters || 15
      }
    }
    if (!selectedSession.classroom_id) return null
    return classrooms.find((c) => String(c.id) === String(selectedSession.classroom_id))
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

  // ── Load dữ liệu ban đầu ──────────────────────────────────────── //
  const loadBaseData = async () => {
    try {
      const data = await fetchSessionsForUser(user)
      setSessions(data)
      if (!sessionId && data.length > 0) {
        const firstSession = data[0]
        setSessionId(String(firstSession.id || firstSession.session_id))
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
          const firstSession = data[0]
          setSessionId((cur) => cur || String(firstSession.id || firstSession.session_id))
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
      const conf = face.confidence ? ` (${(face.confidence * 100).toFixed(0)}%)` : ''
      const labelText = `${name}${conf}`

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

  const confirmPendingRecognition = async () => {
    if (!pendingRecognition) return
    if (!isLecturerOrAdmin) {
      setMessage('Lỗi: Bạn không có quyền thực hiện xác nhận thủ công.')
      return
    }
    setLoading(true)
    try {
      if (pendingRecognition.requiresManualConfirmation) {
        const manualPayload = {
          student_code: pendingRecognition.studentCode,
          session_id: Number(sessionId),
          audit_id: pendingRecognition.auditId,
          note: 'Xác nhận thủ công sau khi quét mặt khác lớp.',
        }
        if (import.meta.env.DEV) {
          console.debug('manual class mismatch confirmation payload', manualPayload)
        }
        await api.post('/attendance/manual', manualPayload)
      } else {
        await postAttendanceAction(
          pendingRecognition.studentCode,
          pendingRecognition.confidence,
          pendingRecognition.action,
        )
      }
      const successMessage = pendingRecognition.requiresManualConfirmation
        ? `Đã xác nhận thủ công cho ${pendingRecognition.studentCode}.`
        : `Đã ghi nhận ${actionLabels[pendingRecognition.action]} cho ${pendingRecognition.studentCode}.`
      setResult({
        success: true, status: 'success',
        studentCode: pendingRecognition.studentCode,
        student: pendingRecognition.student,
        confidence:  pendingRecognition.confidence,
        action: pendingRecognition.action,
        message: successMessage,
      })
      setMessage(successMessage)
      setPendingRecognition(null)
      await loadSessionAttendance(sessionId)
    } catch (err) {
      setMessage(getApiErrorMessage(err, 'Không ghi nhận được điểm danh.'))
    } finally {
      setLoading(false)
    }
  }

  const rejectPendingRecognition = () => {
    setPendingRecognition(null)
    setMessage('Đã hủy. Có thể quét lại để ghi nhận điểm danh.')
    if (window.innerWidth < 768) setMobileStep(3)
  }

  const captureAndProcess = async () => {
    if (!sessionId) { setMessage('Hãy chọn buổi học trước.'); return }
    if (!stream || !videoRef.current) { setMessage('Hãy bật camera trước.'); return }

    setLoading(true)
    setPendingRecognition(null)

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
          bbox: null
        }] : [])

        if (activeResults.length > 0) {
          drawBoundingBoxes(activeResults)
        }

        if (status === 'spoof') {
          setResult({ success: false, status, studentCode: recognizedCode || 'Không xác định', student: recognizedStudent,
            confidence: confidence || 0, message: msg || 'Xác thực sinh trắc học (ảnh thật) thất bại.' })
          setMessage(msg || 'Xác thực sinh trắc học thất bại. Vui lòng thử lại với camera trực tiếp.')
          if (window.innerWidth < 768) setMobileStep(4)
          return
        }

        const classMismatch = isClassMismatchRecognition({
          reason,
          official_attendance_warning_code,
          requires_manual_confirmation,
        })
        const classMismatchMessage = getClassMismatchMessage(recognizedStudent, selectedSession)
        const blockMessage = official_attendance_warning ||
          (recognizedStudent && !isOfficialStudent(recognizedStudent) ? OFFICIAL_BLOCK_MESSAGE : '')

        if (recognizedCode && classMismatch && audit_id) {
          setPendingRecognition({
            studentCode: recognizedCode,
            student: recognizedStudent,
            confidence,
            action,
            auditId: audit_id,
            requiresManualConfirmation: true,
          })
          setResult({ success: false, status: 'blocked', studentCode: recognizedCode, student: recognizedStudent,
            confidence, message: classMismatchMessage })
          setMessage(classMismatchMessage)
          if (window.innerWidth < 768) setMobileStep(4)
          return
        }

        if (recognizedCode && official_attendance_allowed === false && blockMessage) {
          setResult({ success: false, status: 'blocked', studentCode: recognizedCode, student: recognizedStudent,
            confidence, message: blockMessage })
          setMessage(blockMessage)
          if (window.innerWidth < 768) setMobileStep(4)
          return
        }

        if (status === 'success' && recognizedCode) {
          await postAttendanceAction(recognizedCode, confidence)
          setResult({ success: true, status, studentCode: recognizedCode, student: recognizedStudent, confidence, action,
            message: `Đã ghi nhận ${actionLabels[action]} cho ${recognizedCode}.` })
          setMessage(`Đã ghi nhận ${actionLabels[action]} cho ${recognizedCode}.`)
          await loadSessionAttendance(sessionId)
          if (window.innerWidth < 768) setMobileStep(4)

        } else if (status === 'uncertain' && recognizedCode) {
          setPendingRecognition({ studentCode: recognizedCode, student: recognizedStudent, confidence, action })
          setResult({ success: false, status, studentCode: recognizedCode, student: recognizedStudent, confidence,
            message: `${recognitionMessages[status]} Vui lòng xác nhận trước khi ghi nhận ${actionLabels[action]}.` })
          setMessage('Kết quả cần xác nhận. Kiểm tra thông tin sinh viên trước khi ghi nhận.')
          if (window.innerWidth < 768) setMobileStep(4)

        } else {
          setResult({ success: false, status, studentCode: recognizedCode || 'Không xác định', student: recognizedStudent,
            confidence, message: recognitionMessages[status] || msg })
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
              <h2 className="page-title" style={{ fontSize: '20px' }}>Chọn buổi học</h2>
              <p className="page-subtitle">Chọn một buổi học diễn ra để tiến hành điểm danh.</p>
            </div>
            
            {sessions.length === 0 ? (
              <div className="empty-state">Chưa có buổi học nào được lên lịch hôm nay.</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {sessions.map((s) => (
                  <div
                    key={s.id || s.session_id}
                    className="mobile-card"
                    style={{ cursor: 'pointer', border: sessionId === String(s.id || s.session_id) ? '1px solid var(--teal)' : '1px solid var(--bdr)' }}
                    onClick={() => {
                      setSessionId(String(s.id || s.session_id))
                      setMobileStep(2)
                      setPendingRecognition(null)
                      setResult(null)
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontWeight: 800, color: 'var(--white)' }}>{s.subject || s.subject_name}</span>
                      <span className="badge success" style={{ fontSize: '10px' }}>#{s.id || s.session_id}</span>
                    </div>
                    <div style={{ fontSize: '13px', color: 'var(--white2)' }}>
                      Lớp: <span style={{ fontFamily: 'var(--mono)' }}>{s.class_name || s.section_code}</span>
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--muted)', display: 'flex', justifyContent: 'space-between' }}>
                      <span>📅 {s.session_date}</span>
                      <span>⏰ {s.start_time?.slice(0, 5)} - {s.end_time?.slice(0, 5)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
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
                <div style={{ fontWeight: 800, color: 'var(--white)' }}>{selectedSession.subject || selectedSession.subject_name}</div>
                <div style={{ fontSize: '13px', color: 'var(--muted)' }}>
                  Lớp học phần: {selectedSession.class_name || selectedSession.section_code}
                </div>
              </div>
            )}

            <AttendanceCountdown
              sessionDate={selectedSession?.session_date}
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
                  {result.action && <div><strong>Hình thức:</strong> Điểm danh {actionLabels[result.action]}</div>}
                </div>
              )}

              <p style={{ fontSize: '13px', color: style.muted, margin: '8px 0 0 0' }}>
                {!isLecturerOrAdmin && (result?.status === 'uncertain' || result?.status === 'blocked')
                  ? 'Kết quả cần giảng viên xác nhận. Vui lòng liên hệ giảng viên phụ trách.'
                  : (result?.message || message)}
              </p>

              {pendingRecognition && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '10px', borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '12px' }}>
                  {isLecturerOrAdmin ? (
                    <button onClick={confirmPendingRecognition} disabled={loading} style={{ minHeight: 48, width: '100%', justifyContent: 'center' }}>
                      {pendingRecognition.requiresManualConfirmation ? 'Xác nhận thủ công' : `Xác nhận ${actionLabels[pendingRecognition.action]}`}
                    </button>
                  ) : (
                    <div style={{ padding: '10px', background: 'rgba(245,158,11,.1)', border: '1px solid rgba(245,158,11,.3)', color: 'var(--amber)', borderRadius: 'var(--r-sm)', fontSize: '13px', textAlign: 'center', fontWeight: '500' }}>
                      Kết quả cần giảng viên xác nhận. Vui lòng liên hệ giảng viên phụ trách.
                    </div>
                  )}
                  <button className="secondary" onClick={rejectPendingRecognition} disabled={loading} style={{ minHeight: 48, width: '100%', justifyContent: 'center' }}>
                    {isLecturerOrAdmin ? 'Hủy kết quả & Quét lại' : 'Quét lại'}
                  </button>
                </div>
              )}

              {!pendingRecognition && (
                <button
                  style={{ marginTop: '14px', minHeight: 48, width: '100%', justifyContent: 'center' }}
                  onClick={() => {
                    stopCamera()
                    setResult(null)
                    setPendingRecognition(null)
                    setMobileStep(1)
                  }}
                >
                  Hoàn tất & Quay lại
                </button>
              )}
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
              <div className="form-grid">
                {sessions.length === 0 ? (
                  <p style={{ color: 'var(--color-text-secondary)', fontSize: 13 }}>
                    Chưa có buổi học. Vui lòng tạo buổi học tại mục <strong>Buổi học</strong> trước.
                  </p>
                ) : (
                  <select value={sessionId} onChange={(e) => setSessionId(e.target.value)}>
                    <option value="">Chọn buổi học</option>
                    {sessions.map((s) => (
                      <option key={s.id || s.session_id} value={s.id || s.session_id}>
                        #{s.id || s.session_id} — {s.class_name || s.section_code} — {s.subject || s.subject_name} — {s.session_date}
                      </option>
                    ))}
                  </select>
                )}

                <select value={action} onChange={(e) => setAction(e.target.value)}>
                  {actionOptions.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>

                <button onClick={loadBaseData}>Tải lại dữ liệu</button>
                <button onClick={() => loadSessionAttendance(sessionId)} disabled={!sessionId}>
                  Tải lại bảng điểm danh
                </button>
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
                    {result.success && result.action && (
                      <p>Trạng thái ghi nhận: Đã ghi nhận {actionLabels[result.action]}</p>
                    )}
                    <p style={{ color: getStyle(result.status).muted }}>
                      {!isLecturerOrAdmin && (result.status === 'uncertain' || result.status === 'blocked')
                        ? 'Kết quả cần giảng viên xác nhận. Vui lòng liên hệ giảng viên phụ trách.'
                        : result.message}
                    </p>

                    {pendingRecognition && (
                      <div className="toolbar" style={{ marginTop: 12 }}>
                        {isLecturerOrAdmin ? (
                          <>
                            <button onClick={confirmPendingRecognition} disabled={loading}>
                              {pendingRecognition.requiresManualConfirmation ? 'Xác nhận thủ công' : `Xác nhận ${actionLabels[pendingRecognition.action]}`}
                            </button>
                            <button className="secondary" onClick={rejectPendingRecognition} disabled={loading}>
                              Hủy kết quả
                            </button>
                          </>
                        ) : (
                          <div style={{ padding: '8px 12px', background: 'rgba(245,158,11,.1)', border: '1px solid rgba(245,158,11,.3)', color: 'var(--amber)', borderRadius: 'var(--r-sm)', fontSize: '13px', fontWeight: '500' }}>
                            Kết quả cần giảng viên xác nhận. Vui lòng liên hệ giảng viên phụ trách.
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Vùng GPSStatus & Countdown cho màn hình lớn (nếu chọn buổi học) */}
              {selectedSession && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <AttendanceCountdown
                    sessionDate={selectedSession.session_date}
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
