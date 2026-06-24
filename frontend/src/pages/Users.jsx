import { useEffect, useState, useCallback } from 'react'
import api from '../../api/axios.js'
import { getApiErrorMessage } from '../utils/apiError.js'
import { getDisplayLabel, roleLabels } from '../utils/displayLabels.js'

const emptyForm = { username: '', password: '', full_name: '', role: 'teacher', is_active: true }

export default function Users() {
  const [users, setUsers] = useState([])
  const [form, setForm] = useState(emptyForm)
  const [editingId, setEditingId] = useState(null)
  const [search, setSearch] = useState('')
  const [message, setMessage] = useState('')
  const [msgType, setMsgType] = useState('ok')
  const [loading, setLoading] = useState(false)

  const fetchUsers = useCallback(async () => {
    try {
      const res = await api.get('/auth/users')
      setUsers(res.data)
    } catch (e) {
      setMessage(getApiErrorMessage(e, 'Không tải được danh sách người dùng.'))
      setMsgType('error')
    }
  }, [])

  useEffect(() => {
    fetchUsers()
  }, [fetchUsers])

  const handleEdit = (u) => {
    setEditingId(u.id)
    setForm({
      username: u.username,
      password: '',
      full_name: u.full_name || '',
      role: u.role || 'teacher',
      is_active: u.is_active ?? true
    })
    setMessage('')
  }

  const handleCancel = () => {
    setEditingId(null)
    setForm(emptyForm)
    setMessage('')
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setMessage('')
    try {
      if (editingId) {
        const payload = {
          username: form.username.trim(),
          full_name: form.full_name.trim() || null,
          role: form.role,
          is_active: form.is_active
        }
        if (form.password) {
          payload.password = form.password
        }
        await api.put(`/auth/users/${editingId}`, payload)
        setMessage('Cập nhật người dùng thành công.')
        setMsgType('ok')
      } else {
        if (!form.password || form.password.length < 8) {
          setMessage('Mật khẩu phải từ 8 ký tự trở lên.')
          setMsgType('error')
          setLoading(false)
          return
        }
        const payload = {
          username: form.username.trim(),
          password: form.password,
          full_name: form.full_name.trim() || null,
          role: form.role,
          is_active: form.is_active
        }
        await api.post('/auth/users', payload)
        setMessage('Thêm người dùng mới thành công.')
        setMsgType('ok')
      }
      setForm(emptyForm)
      setEditingId(null)
      fetchUsers()
    } catch (err) {
      setMessage(getApiErrorMessage(err, 'Không lưu được thông tin người dùng.'))
      setMsgType('error')
    } finally {
      setLoading(false)
    }
  }

  const filtered = users.filter(u => {
    const kw = search.trim().toLowerCase()
    return !kw || 
      u.username?.toLowerCase().includes(kw) || 
      u.full_name?.toLowerCase().includes(kw) || 
      u.role?.toLowerCase().includes(kw)
  })

  return (
    <div>
      <div className="page-header">
        <div>
          <p className="eyebrow">Hệ thống</p>
          <h1 className="page-title">Quản lý tài khoản</h1>
          <p className="page-subtitle">Thêm, sửa và phân quyền tài khoản truy cập hệ thống.</p>
        </div>
      </div>

      <div className="grid two" style={{ gridTemplateColumns: 'minmax(0, 1.2fr) minmax(320px, 0.8fr)', gap: 20 }}>
        {/* Left column: List of Users */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="toolbar">
            <input
              placeholder="Tìm theo tài khoản, tên..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ minWidth: 260 }}
            />
            <button className="secondary" onClick={fetchUsers}>🔄 Tải lại</button>
          </div>

          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Tài khoản</th>
                  <th>Họ tên</th>
                  <th>Vai trò</th>
                  <th>Trạng thái</th>
                  <th style={{ textAlign: 'right' }}>Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan="5" className="empty-state" style={{ textAlign: 'center', padding: '24px 0' }}>Không tìm thấy tài khoản.</td>
                  </tr>
                ) : (
                  filtered.map(u => (
                    <tr key={u.id}>
                      <td style={{ fontWeight: 600 }}>{u.username}</td>
                      <td>{u.full_name || '-'}</td>
                      <td>
                        <span className={`badge ${u.role === 'admin' ? 'danger' : u.role === 'teacher' ? 'info' : 'success'}`}>
                          {getDisplayLabel(roleLabels, u.role, u.role)}
                        </span>
                      </td>
                      <td>
                        <span className={`badge ${u.is_active ? 'success' : 'muted'}`}>
                          {u.is_active ? 'Hoạt động' : 'Khóa'}
                        </span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <button className="secondary" onClick={() => handleEdit(u)} style={{ minHeight: 30, padding: '4px 10px', fontSize: 12 }}>
                          Sửa
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right column: Form */}
        <div>
          <form onSubmit={handleSubmit} className="panel panel-pad" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <h2 style={{ fontSize: 16, margin: '0 0 4px', color: 'var(--white)' }}>
              {editingId ? 'Sửa thông tin tài khoản' : 'Thêm tài khoản mới'}
            </h2>

            {message && (
              <p className={`status-message ${msgType}`} style={{ margin: '0 0 10px', padding: 8, borderRadius: 6, fontSize: 13 }}>
                {message}
              </p>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase' }}>Tên đăng nhập</label>
              <input
                value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
                required
                disabled={Boolean(editingId)}
                placeholder="Ví dụ: teacher1"
                style={{ width: '100%' }}
              />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase' }}>
                {editingId ? 'Mật khẩu mới (để trống nếu không đổi)' : 'Mật khẩu'}
              </label>
              <input
                type="password"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                required={!editingId}
                placeholder={editingId ? "Không thay đổi" : "Tối thiểu 8 ký tự"}
                style={{ width: '100%' }}
              />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase' }}>Họ tên</label>
              <input
                value={form.full_name}
                onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                placeholder="Họ tên đầy đủ"
                style={{ width: '100%' }}
              />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase' }}>Vai trò</label>
              <select
                value={form.role}
                onChange={(e) => setForm({ ...form, role: e.target.value })}
                style={{ width: '100%', minHeight: 38 }}
              >
                <option value="admin">Quản trị viên (Admin)</option>
                <option value="teacher">Giảng viên (Teacher)</option>
                <option value="student">Sinh viên (Student)</option>
              </select>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
              <input
                type="checkbox"
                id="is_active_chk"
                checked={form.is_active}
                onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                style={{ width: 18, height: 18, cursor: 'pointer' }}
              />
              <label htmlFor="is_active_chk" style={{ fontSize: 13, fontWeight: 600, color: 'var(--white)', cursor: 'pointer' }}>
                Trạng thái hoạt động (Active)
              </label>
            </div>

            <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
              {editingId && (
                <button type="button" className="secondary" onClick={handleCancel} style={{ flex: 1 }}>
                  Hủy
                </button>
              )}
              <button type="submit" disabled={loading} style={{ flex: 2, justifyContent: 'center' }}>
                {loading ? 'Đang lưu...' : editingId ? 'Cập nhật' : 'Thêm tài khoản'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
