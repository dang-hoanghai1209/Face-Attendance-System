import { useEffect, useState, useCallback } from 'react'
import api from '../../api/axios.js'
import { getApiErrorMessage } from '../utils/apiError.js'
import { getDisplayLabel, roleLabels } from '../utils/displayLabels.js'

export default function AuditLogs() {
  const [logs, setLogs] = useState([])
  const [search, setSearch] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)

  const fetchLogs = useCallback(async () => {
    setLoading(true)
    setMessage('')
    try {
      const res = await api.get('/auth/audit-logs')
      setLogs(res.data)
    } catch (e) {
      setMessage(getApiErrorMessage(e, 'Không tải được lịch sử hoạt động.'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchLogs()
  }, [fetchLogs])

  const formatDate = (isoStr) => {
    if (!isoStr) return '-'
    const d = new Date(isoStr)
    if (isNaN(d)) return isoStr
    return d.toLocaleString('vi-VN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  }

  const filtered = logs.filter(log => {
    const kw = search.trim().toLowerCase()
    return !kw ||
      log.actor_username?.toLowerCase().includes(kw) ||
      log.action?.toLowerCase().includes(kw) ||
      log.target_type?.toLowerCase().includes(kw) ||
      JSON.stringify(log.details || {}).toLowerCase().includes(kw)
  })

  return (
    <div>
      <div className="page-header">
        <div>
          <p className="eyebrow">Hệ thống</p>
          <h1 className="page-title">Lịch sử hoạt động</h1>
          <p className="page-subtitle">Nhật ký các thao tác đăng nhập, tạo, sửa, xóa và điểm danh trên hệ thống.</p>
        </div>
        <button className="secondary" onClick={fetchLogs} disabled={loading}>
          {loading ? 'Đang tải...' : '🔄 Tải lại'}
        </button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div className="toolbar">
          <input
            placeholder="Tìm theo tài khoản, hành động, chi tiết..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ minWidth: 320 }}
          />
        </div>

        {message && <p className="status-message error">⚠️ {message}</p>}

        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: '160px' }}>Thời gian</th>
                <th>Người thực hiện</th>
                <th>Vai trò</th>
                <th>Hành động</th>
                <th>Đối tượng</th>
                <th>Mã đối tượng</th>
                <th>Chi tiết</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan="7" className="empty-state" style={{ textAlign: 'center', padding: '24px 0' }}>
                    {loading ? 'Đang tải dữ liệu...' : 'Không có nhật ký hoạt động phù hợp.'}
                  </td>
                </tr>
              ) : (
                filtered.map(log => (
                  <tr key={log.id}>
                    <td style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{formatDate(log.created_at)}</td>
                    <td style={{ fontWeight: 600 }}>{log.actor_username || 'Hệ thống'}</td>
                    <td>
                      {log.actor_role ? (
                        <span className={`badge ${log.actor_role === 'admin' ? 'danger' : log.actor_role === 'teacher' ? 'info' : 'success'}`}>
                          {getDisplayLabel(roleLabels, log.actor_role, log.actor_role)}
                        </span>
                      ) : '-'}
                    </td>
                    <td>
                      <span className="badge muted" style={{ textTransform: 'uppercase', fontSize: 11 }}>
                        {log.action}
                      </span>
                    </td>
                    <td>{log.target_type || '-'}</td>
                    <td>{log.target_id || '-'}</td>
                    <td style={{ fontSize: 12, color: 'var(--white2)', maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={JSON.stringify(log.details)}>
                      {log.details ? JSON.stringify(log.details) : '-'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
