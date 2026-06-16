import { useEffect, useState } from 'react'

const DEFAULT_GPS_RADIUS_METERS = 30
const DEMO_MIN_GPS_RADIUS_METERS = 50

// Công thức Haversine tính khoảng cách giữa hai điểm tọa độ (mét)
function calculateDistance(lat1, lon1, lat2, lon2) {
  if (!lat1 || !lon1 || !lat2 || !lon2) return null
  const R = 6371e3 // Bán kính Trái Đất (mét)
  const dLat = (lat2 - lat1) * (Math.PI / 180)
  const dLon = (lon2 - lon1) * (Math.PI / 180)
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(lat1 * (Math.PI / 180)) *
      Math.cos(lat2 * (Math.PI / 180)) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2)
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
  return R * c
}

export default function GPSStatus({ targetLocation, onLocationChange }) {
  const [position, setPosition] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!navigator.geolocation) {
      setError('Trình duyệt không hỗ trợ xác định vị trí GPS.')
      setLoading(false)
      return
    }

    const options = {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 0,
    }

    const watchId = navigator.geolocation.watchPosition(
      (pos) => {
        const { latitude, longitude, accuracy } = pos.coords
        const currentLoc = { lat: latitude, lng: longitude, accuracy }
        setPosition(currentLoc)
        setError(null)
        setLoading(false)
        if (onLocationChange) {
          onLocationChange(currentLoc)
        }
      },
      (err) => {
        let errorMsg = 'Lỗi không rõ khi định vị.'
        switch (err.code) {
          case err.PERMISSION_DENIED:
            errorMsg = 'Quyền truy cập vị trí bị từ chối. Hãy mở cài đặt để cho phép.'
            break
          case err.POSITION_UNAVAILABLE:
            errorMsg = 'Thông tin vị trí không khả dụng.'
            break
          case err.TIMEOUT:
            errorMsg = 'Quá thời gian lấy vị trí GPS.'
            break
          default:
            break
        }
        setError(errorMsg)
        setLoading(false)
        if (onLocationChange) {
          onLocationChange(null)
        }
      },
      options
    )

    return () => {
      navigator.geolocation.clearWatch(watchId)
    }
  }, [onLocationChange])

  // Tính khoảng cách tương đối đến phòng học
  const distance =
    position && targetLocation?.gps_lat && targetLocation?.gps_lng
      ? calculateDistance(
          position.lat,
          position.lng,
          targetLocation.gps_lat,
          targetLocation.gps_lng
        )
      : null

  const configuredRadius = targetLocation?.radius_meters || DEFAULT_GPS_RADIUS_METERS
  const allowedRadius =
    targetLocation?.allowed_radius_meters || Math.max(configuredRadius, DEMO_MIN_GPS_RADIUS_METERS)

  // Xác định trạng thái hiển thị
  let statusText = 'Đang lấy vị trí...'
  let statusClass = 'warning'
  let isWithinRange = false

  if (error) {
    statusText = error
    statusClass = 'danger'
  } else if (position) {
    if (targetLocation?.gps_lat && targetLocation?.gps_lng) {
      if (distance !== null && distance <= allowedRadius) {
        statusText = 'Đang ở trong lớp học'
        statusClass = 'success'
        isWithinRange = true
      } else {
        statusText = 'Ngoài phạm vi điểm danh'
        statusClass = 'danger'
      }
    } else {
      statusText = 'Buổi học chưa cấu hình tọa độ GPS'
      statusClass = 'warning'
      isWithinRange = true // Xem như hợp lệ để quét nếu phòng học không cấu hình tọa độ
    }
  }

  return (
    <div style={{
      background: 'var(--card)',
      border: '1px solid var(--bdr)',
      borderRadius: 'var(--r)',
      padding: '16px',
      marginBottom: '14px',
      animation: 'fadeUp 0.35s ease both'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
        <h4 style={{ margin: 0, fontSize: '13px', textTransform: 'uppercase', color: 'var(--white2)', letterSpacing: '.06em' }}>
          Định vị vị trí (GPS)
        </h4>
        <span className={`badge ${statusClass}`} style={{ fontSize: '11px', fontWeight: '700' }}>
          {statusText}
        </span>
      </div>

      {loading && (
        <div style={{ color: 'var(--muted)', fontSize: '13px', animation: 'blink 2s infinite' }}>
          Đang quét GPS thiết bị của bạn...
        </div>
      )}

      {position && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '13px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--muted)' }}>Tọa độ của bạn:</span>
            <span style={{ fontFamily: 'var(--mono)', color: 'var(--white)' }}>
              {position.lat.toFixed(6)}, {position.lng.toFixed(6)}
            </span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--muted)' }}>Độ chính xác GPS:</span>
            <span style={{ color: position.accuracy <= 15 ? 'var(--teal)' : 'var(--amber)', fontWeight: '600' }}>
              ± {position.accuracy.toFixed(1)} mét
            </span>
          </div>

          {targetLocation?.name && (
            <div style={{ borderTop: '1px solid var(--bdr)', marginTop: '8px', paddingTop: '8px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                <span style={{ color: 'var(--muted)' }}>Phòng học:</span>
                <span style={{ color: 'var(--white)', fontWeight: '600' }}>
                  {targetLocation.name} ({targetLocation.building || 'Khu học tập'})
                </span>
              </div>
              {distance !== null && (
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <span style={{ color: 'var(--muted)' }}>Khoảng cách đến phòng:</span>
                  <span style={{ color: isWithinRange ? 'var(--teal)' : 'var(--red)', fontWeight: '700' }}>
                    {distance.toFixed(1)} mét
                  </span>
                </div>
              )}
              {allowedRadius && (
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--muted)' }}>Bán kính cho phép:</span>
                  <span style={{ color: 'var(--white2)' }}>{allowedRadius} mét</span>
                </div>
                )}
              {allowedRadius >= DEMO_MIN_GPS_RADIUS_METERS && configuredRadius < DEMO_MIN_GPS_RADIUS_METERS && (
                <div style={{ color: 'var(--muted)', fontSize: '12px', marginTop: '6px', lineHeight: 1.4 }}>
                  Bán kính GPS demo: tối thiểu 50m do laptop có thể sai số vị trí cao.
                </div>
              )}
              </div>
          )}
        </div>
      )}

      {error && (
        <div style={{ color: 'var(--red)', fontSize: '12px', marginTop: '6px' }}>
          ⚠️ Hệ thống yêu cầu bật định vị trên điện thoại để hoàn tất điểm danh chính thức.
        </div>
      )}
    </div>
  )
}
