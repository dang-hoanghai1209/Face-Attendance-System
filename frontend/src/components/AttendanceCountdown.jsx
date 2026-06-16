import { useEffect, useState } from 'react'

const EARLY_CHECKIN_MINUTES = 15
const LATE_CHECKIN_MINUTES = 10

function getSessionTimes(sessionDate, startTimeStr) {
  if (!sessionDate || !startTimeStr) return null

  const dateParts = String(sessionDate).split('-').map(Number)
  const timeParts = String(startTimeStr).split(':').map(Number)
  if (dateParts.length !== 3 || timeParts.length < 2) return null

  const [year, month, day] = dateParts
  const [hours, minutes, seconds = 0] = timeParts
  const start = new Date(year, month - 1, day, hours || 0, minutes || 0, seconds || 0, 0)
  const openAt = new Date(start.getTime() - EARLY_CHECKIN_MINUTES * 60 * 1000)
  const closeAt = new Date(start.getTime() + LATE_CHECKIN_MINUTES * 60 * 1000)

  return { start, openAt, closeAt }
}

function formatClock(date) {
  if (!date) return '--:--'
  return date.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
}

function formatDuration(ms) {
  const safeMs = Math.max(0, ms)
  const hours = Math.floor(safeMs / (3600 * 1000))
  const minutes = Math.floor((safeMs % (3600 * 1000)) / (60 * 1000))
  const seconds = Math.floor((safeMs % (60 * 1000)) / 1000)

  if (hours > 0) return `${hours}g ${minutes}p ${seconds}s`
  return `${minutes}p ${seconds}s`
}

export default function AttendanceCountdown({ sessionDate, startTime, onStatusChange }) {
  const [timeLeft, setTimeLeft] = useState('')
  const [status, setStatus] = useState('not_started')
  const [sessionTimes, setSessionTimes] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!sessionDate || !startTime) {
      setSessionTimes(null)
      setLoading(false)
      return
    }

    const updateTimer = () => {
      const times = getSessionTimes(sessionDate, startTime)
      if (!times) return

      const now = new Date()
      const { openAt, closeAt } = times

      let currentStatus = 'not_started'
      let displayText = ''

      if (now < openAt) {
        currentStatus = 'not_started'
        displayText = `Còn ${formatDuration(openAt - now)} để mở điểm danh`
      } else if (now <= closeAt) {
        currentStatus = 'open'
        displayText = 'Đang trong thời gian điểm danh'
      } else {
        currentStatus = 'closed'
        displayText = 'Đã kết thúc điểm danh'
      }

      setStatus(currentStatus)
      setTimeLeft(displayText)
      setSessionTimes(times)
      setLoading(false)

      if (onStatusChange) {
        onStatusChange(currentStatus)
      }
    }

    updateTimer()

    const intervalId = setInterval(updateTimer, 1000)
    return () => clearInterval(intervalId)
  }, [sessionDate, startTime, onStatusChange])

  if (loading) {
    return (
      <div style={{
        background: 'var(--card)',
        border: '1px solid var(--bdr)',
        borderRadius: 'var(--r-sm)',
        padding: '12px',
        textAlign: 'center',
        color: 'var(--muted)',
        fontSize: '13px'
      }}>
        Đang kiểm tra thời gian...
      </div>
    )
  }

  let bg = 'var(--card)'
  let border = 'var(--bdr)'
  let color = 'var(--white)'
  let badgeText = 'Chưa bắt đầu'
  let badgeClass = 'warning'

  if (status === 'open') {
    bg = 'rgba(0,201,167,.06)'
    border = 'rgba(0,201,167,.2)'
    color = 'var(--teal)'
    badgeText = 'Đang điểm danh'
    badgeClass = 'success'
  } else if (status === 'closed') {
    bg = 'rgba(244,63,94,.04)'
    border = 'rgba(244,63,94,.15)'
    color = 'var(--red)'
    badgeText = 'Đã kết thúc'
    badgeClass = 'danger'
  }

  return (
    <div style={{
      background: bg,
      border: `1px solid ${border}`,
      borderRadius: 'var(--r)',
      padding: '16px',
      marginBottom: '14px',
      display: 'flex',
      flexDirection: 'column',
      gap: '8px',
      animation: 'fadeUp 0.35s ease both'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <span style={{ fontSize: '13px', fontWeight: '700', color: 'var(--white2)', textTransform: 'uppercase', letterSpacing: '.06em' }}>
          Thời gian điểm danh
        </span>
        <span className={`badge ${badgeClass}`} style={{ fontSize: '11px', fontWeight: '700' }}>
          {badgeText}
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <div style={{ fontSize: '16px', fontWeight: '800', color: color }}>
          {timeLeft}
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 12px', fontSize: '12px', color: 'var(--white2)' }}>
          <span>Mở điểm danh: {formatClock(sessionTimes?.openAt)}</span>
          <span>Kết thúc điểm danh: {formatClock(sessionTimes?.closeAt)}</span>
        </div>
        <div style={{ fontSize: '12px', color: 'var(--muted)' }}>
          Quy định: Điểm danh mở trước giờ học 15 phút và kết thúc sau giờ bắt đầu 10 phút.
        </div>
      </div>
    </div>
  )
}
