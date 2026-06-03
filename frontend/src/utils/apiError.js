export function getApiErrorMessage(error, fallback = 'Có lỗi xảy ra.') {
  if (error.response) {
    const detail = error.response.data?.detail
    if (error.response.status === 401) {
      return detail || 'Bạn cần đăng nhập lại để tiếp tục.'
    }
    if (error.response.status === 403) {
      return detail || 'Tài khoản không có quyền thực hiện thao tác này.'
    }
    if (Array.isArray(detail)) {
      return detail.map((item) => item.msg || JSON.stringify(item)).join(' ')
    }
    if (detail && typeof detail === 'object') {
      return detail.message || JSON.stringify(detail)
    }
    return detail || error.response.data?.message || fallback
  }

  if (error.request) {
    return 'Không kết nối được backend. Kiểm tra backend đã chạy và VITE_API_BASE_URL đúng.'
  }

  return error.message || fallback
}
