import { useEffect, useState } from 'react'

// Hàm chuyển ngày và giờ của buổi học thành đối tượng Date cục bộ
function getSessionTimes(sessionDate, startTimeStr) {
  if (!sessionDate || !startTimeStr) return null
  
  const timeParts = startTimeStr.split(':')
  const hours = parseInt(timeParts[0], 10)
  const minutes = parseInt(timeParts[1], 10)
  const seconds = timeParts[2] ? parseInt(timeParts[2], 10) : 0
  
  const start = new Date(sessionDate)
  start.setHours(hours, minutes, seconds, 0)
  
  const deadline = new Date(start.getTime() + 15 * 60 * 1000) // 15 phút sau giờ bắt đầu
  
  return { start, deadline }
}

export default function AttendanceCountdown({ sessionDate, startTime, onStatusChange }) {
  const [timeLeft, setTimeLeft] = useState('')
  const [status, setStatus] = useState('not_started') // not_started, open, closed
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!sessionDate || !startTime) {
      setLoading(false)
      return
    }

    const updateTimer = () => {
      const times = getSessionTimes(sessionDate, startTime)
      if (!times) return

      const now = new Date()
      const { start, deadline } = times

      let currentStatus = 'not_started'
      let displayText = ''

      if (now < start) {
        currentStatus = 'not_started'
        const diffMs = start - now
        const diffHrs = Math.floor(diffMs / (3600 * 1000))
        const diffMins = Math.floor((diffMs % (3600 * 1000)) / (60 * 1000))
        const diffSecs = Math.floor((diffMs % (60 * 1000)) / 1000)
        
        if (diffHrs > 0) {
          displayText = `Còn ${diffHrs}g ${diffMins}p ${diffSecs}s để bắt đầu học`
        } else {
          displayText = `Còn ${diffMins}p ${diffSecs}s để bắt đầu học`
        }
      } else if (now >= start && now <= deadline) {
        currentStatus = 'open'
        const diffMs = deadline - now
        const diffMins = Math.floor(diffMs / (60 * 1000))
        const diffSecs = Math.floor((diffMs % (60 * 1000)) / 1000)
        displayText = `Điểm danh đóng sau: ${diffMins} phút ${diffSecs} giây`
      } else {
        currentStatus = 'closed'
        displayText = 'Hết thời gian điểm danh'
      }

      setStatus(currentStatus)
      setTimeLeft(displayText)
      setLoading(false)
      
      if (onStatusChange) {
        onStatusChange(currentStatus)
      }
    }

    // Chạy kiểm tra ngay lập tức
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

  // Tùy biến kiểu hiển thị dựa trên trạng thái
  let bg = 'var(--card)'
  let border = 'var(--bdr)'
  let color = 'var(--white)'
  let badgeText = 'Chưa bắt đầu'
  let badgeClass = 'warning'

  if (status === 'open') {
    bg = 'rgba(0,201,167,.06)'
    border = 'rgba(0,201,167,.2)'
    color = 'var(--teal)'
    badgeText = 'Đang mở điểm danh'
    badgeClass = 'success'
  } else if (status === 'closed') {
    bg = 'rgba(244,63,94,.04)'
    border = 'rgba(244,63,94,.15)'
    color = 'var(--red)'
    badgeText = 'Đã quá giờ điểm danh'
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
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: '13px', fontWeight: '700', color: 'var(--white2)', textTransform: 'uppercase', letterSpacing: '.06em' }}>
          Thời gian điểm danh
        </span>
        <span className={`badge ${badgeClass}`} style={{ fontSize: '11px', fontWeight: '700' }}>
          {badgeText}
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        <div style={{ fontSize: '16px', fontWeight: '800', color: color }}>
          {timeLeft}
        </div>
        <div style={{ fontSize: '12px', color: 'var(--muted)' }}>
          Quy định: Điểm danh hợp lệ chỉ diễn ra trong vòng 15 phút đầu kể từ giờ bắt đầu học ({startTime?.slice(0, 5)}).
        </div>
      </div>
    </div>
  )
}
