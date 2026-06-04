import { useEffect, useMemo, useRef, useState } from 'react'

import api from '../../api/axios.js'
import { useAuth } from '../auth/auth-context.js'
import { getApiErrorMessage } from '../utils/apiError.js'

const actionOptions = [
  { value: 'checkin',  label: 'Vào lớp' },
  { value: 'checkout', label: 'Ra về'   },
]

const actionLabels = { checkin: 'vào lớp', checkout: 'ra về' }

const statusLabels = {
  present: 'Có mặt',
  late:    'Đi trễ',
  manual:  'Thủ công',
  absent:  'Vắng',
}

const recognitionMessages = {
  success:  'Nhận diện thành công.',
  uncertain:'Khuôn mặt cần được xác nhận thủ công.',
  unknown:  'Không nhận diện được sinh viên.',
  no_face:  'Không phát hiện khuôn mặt trong ảnh.',
}
const OFFICIAL_BLOCK_MESSAGE = 'Mẫu này thuộc dữ liệu demo/Kaggle, không được ghi nhận điểm danh chính thức.'

const isOfficialStudent = (student) =>
  student?.data_source === 'real' && !student?.is_demo && student?.face_status === 'registered'

const getStyle = (status) => {
  if (status === 'blocked')   return { bg: 'rgba(245,158,11,.14)', border: 'rgba(245,158,11,.45)', accent: '#fbbf24', text: '#f8fafc', muted: '#fde68a', label: 'Cần xác nhận thủ công' }
  if (status === 'success')   return { bg: 'rgba(0,201,167,.14)', border: 'rgba(0,201,167,.45)', accent: '#2dd4bf', text: '#f8fafc', muted: '#99f6e4', label: 'Nhận diện thành công' }
  if (status === 'uncertain') return { bg: 'rgba(245,158,11,.14)', border: 'rgba(245,158,11,.45)', accent: '#fbbf24', text: '#f8fafc', muted: '#fde68a', label: 'Cần xác nhận' }
  if (status === 'no_face')   return { bg: 'rgba(244,63,94,.14)', border: 'rgba(244,63,94,.45)', accent: '#fb7185', text: '#f8fafc', muted: '#fecdd3', label: 'Không phát hiện khuôn mặt' }
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
  `Sinh viên thuộc lớp ${student?.class_name || '-'}, khác lớp chính của buổi học ${session?.class_name || '-'}. Nếu sinh viên có đăng ký/học ghép buổi này, giảng viên có thể xác nhận thủ công để ghi nhận điểm danh.`

export default function Attendance() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'
  const canDeleteAttendance = user?.role === 'admin' || user?.role === 'teacher'
  const videoRef  = useRef(null)
  const canvasRef = useRef(null)

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
  const selectedSession = useMemo(
    () => sessions.find((session) => String(session.id) === String(sessionId)),
    [sessions, sessionId],
  )

  // ── Load dữ liệu ban đầu ──────────────────────────────────────── //
  const loadBaseData = async () => {
    try {
      const sessionRes = await api.get('/sessions/')
      setSessions(sessionRes.data)
      if (!sessionId && sessionRes.data.length > 0)
        setSessionId(String(sessionRes.data[0].id))
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
        const sessionRes = await api.get('/sessions/')
        if (!mounted) return
        setSessions(sessionRes.data)
        if (sessionRes.data.length > 0)
          setSessionId((cur) => cur || String(sessionRes.data[0].id))
      } catch (err) {
        if (mounted) setMessage(getApiErrorMessage(err, 'Không tải được dữ liệu điểm danh.'))
      }
    }
    init()
    return () => { mounted = false }
  }, [])

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

  // ── Camera ────────────────────────────────────────────────────── //
  const startCamera = async () => {
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' },
      })
      videoRef.current.srcObject = mediaStream
      setStream(mediaStream)
      setMessage('Camera đã sẵn sàng.')
    } catch (err) {
      setMessage(`Không mở được camera: ${err.message}`)
    }
  }

  const stopCamera = () => {
    stream?.getTracks().forEach((t) => t.stop())
    setStream(null)
  }

  // ── Điểm danh ────────────────────────────────────────────────── //
  const postAttendanceAction = (studentCode, confidence, act = action) =>
    api.post(act === 'checkout' ? '/attendance/checkout' : '/attendance/checkin', {
      student_code: studentCode,
      session_id:   Number(sessionId),
      confidence,
    })

  const confirmPendingRecognition = async () => {
    if (!pendingRecognition) return
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
  }

  const captureAndProcess = async () => {
    if (!sessionId) { setMessage('Hãy chọn buổi học trước.'); return }
    if (!stream || !videoRef.current) { setMessage('Hãy bật camera trước.'); return }

    setLoading(true)
    setPendingRecognition(null)

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
        } = recRes.data
        const recognizedStudent = student || null
        const recognizedCode = recognizedStudent?.student_code || student_code
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
          return
        }

        if (recognizedCode && official_attendance_allowed === false && blockMessage) {
          setResult({ success: false, status: 'blocked', studentCode: recognizedCode, student: recognizedStudent,
            confidence, message: blockMessage })
          setMessage(blockMessage)
          return
        }

        if (status === 'success' && recognizedCode) {
          await postAttendanceAction(recognizedCode, confidence)
          setResult({ success: true, status, studentCode: recognizedCode, student: recognizedStudent, confidence, action,
            message: `Đã ghi nhận ${actionLabels[action]} cho ${recognizedCode}.` })
          setMessage(`Đã ghi nhận ${actionLabels[action]} cho ${recognizedCode}.`)
          await loadSessionAttendance(sessionId)

        } else if (status === 'uncertain' && recognizedCode) {
          setPendingRecognition({ studentCode: recognizedCode, student: recognizedStudent, confidence, action })
          setResult({ success: false, status, studentCode: recognizedCode, student: recognizedStudent, confidence,
            message: `${recognitionMessages[status]} Vui lòng xác nhận trước khi ghi nhận ${actionLabels[action]}.` })
          setMessage('Kết quả cần xác nhận. Kiểm tra thông tin sinh viên trước khi ghi nhận.')

        } else {
          setResult({ success: false, status, studentCode: recognizedCode || 'Không xác định', student: recognizedStudent,
            confidence, message: recognitionMessages[status] || msg })
          setMessage(recognitionMessages[status] || msg)
        }
      } catch (err) {
        setResult(null)
        setMessage(getApiErrorMessage(err, 'Không xử lý được nhận diện.'))
      } finally {
        setLoading(false)
      }
    }, 'image/jpeg', 0.95)
  }

  const deleteAttendanceRecord = async (record) => {
    if (!record?.record_id) return

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

  // ── Render ────────────────────────────────────────────────────── //
  const runModelTest = async () => {
    if (!testFile) {
      setMessage('Hay chon mot anh de kiem thu.')
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

  return (
    <div>
      <div className="page-header">
        <div>
          <p className="eyebrow">Điểm danh</p>
          <h1 className="page-title">Điểm danh và theo dõi buổi học</h1>
          <p className="page-subtitle">
            Chọn buổi học và nhận diện khuôn mặt để ghi vào lớp/ra về. Trường hợp khác lớp sẽ được xác nhận ngay sau khi quét mặt.
          </p>
        </div>
      </div>

      <div className="toolbar" style={{ marginBottom: 16 }}>
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
          >
            Kiểm thử mô hình
          </button>
        )}
      </div>

      {message && <p className="status-message">{message}</p>}

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
              <p>Trạng thái: {testResult.status}</p>
              <p>Mã mẫu: {testResult.sample_code || testResult.student?.student_code || testResult.student_code || '-'}</p>
              <p>Tên mẫu: {testResult.full_name || testResult.student?.full_name || '-'}</p>
              <p>Nguồn dữ liệu: {testResult.data_source || testResult.student?.data_source || '-'}</p>
              <p>Demo: {(testResult.is_demo ?? testResult.student?.is_demo) ? 'Có' : 'Không'}</p>
              <p>Phương thức đăng ký: {testResult.registration_method || testResult.student?.registration_method || '-'}</p>
              <p>Similarity: {formatConf(testResult.confidence)}</p>
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
                <option key={s.id} value={s.id}>
                  #{s.id} — {s.class_name} — {s.subject} — {s.session_date}
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

      {message && <p className="status-message">{message}</p>}

      <div style={{ maxWidth: 920 }}>
        {/* Camera + nhận diện */}
        <div className="panel panel-pad">
          <video
            ref={videoRef} autoPlay playsInline
            style={{ width: '100%', maxWidth: 760, background: '#000', borderRadius: 8, display: 'block' }}
          />
          <canvas ref={canvasRef} style={{ display: 'none' }} />

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
              <p>Lớp chính của buổi học: {selectedSession?.class_name || '-'}</p>
              <p>Độ tin cậy: {formatConf(result.confidence)}</p>
              {result.success && result.action && (
                <p>Trạng thái ghi nhận: Đã ghi nhận {actionLabels[result.action]}</p>
              )}
              <p style={{ color: getStyle(result.status).muted }}>{result.message}</p>

              {pendingRecognition && (
                <div className="toolbar" style={{ marginTop: 12 }}>
                  <button onClick={confirmPendingRecognition} disabled={loading}>
                    {pendingRecognition.requiresManualConfirmation ? 'Xác nhận thủ công' : `Xác nhận ${actionLabels[pendingRecognition.action]}`}
                  </button>
                  <button className="secondary" onClick={rejectPendingRecognition} disabled={loading}>
                    Hủy kết quả
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
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
                  {['Mã SV', 'Họ tên', 'Trạng thái', 'Vào lớp', 'Ra về', 'Tin cậy vào', 'Tin cậy ra', 'Xóa'].map((h) => (
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
                        {statusLabels[record.status] || record.status}
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
    </div>
  )
}
