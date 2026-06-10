const translateValidationMessage = (message) => {
  const translations = {
    'Field required': 'Vui lòng nhập đầy đủ thông tin bắt buộc.',
    'Input should be a valid string': 'Giá trị nhập vào phải là chuỗi hợp lệ.',
    'Input should be a valid integer': 'Giá trị nhập vào phải là số nguyên hợp lệ.',
    'Input should be a valid date': 'Ngày nhập vào không hợp lệ.',
    'Input should be in a valid time format': 'Thời gian nhập vào không hợp lệ.',
  }
  return translations[message] || message
}

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
      return detail.map((item) => translateValidationMessage(item.msg) || JSON.stringify(item)).join(' ')
    }
    if (detail && typeof detail === 'object') {
      return detail.message || JSON.stringify(detail)
    }
    return detail || error.response.data?.message || fallback
  }

  if (error.request) {
    return 'Không thể kết nối đến máy chủ. Vui lòng kiểm tra máy chủ đã chạy và cấu hình địa chỉ API.'
  }

  return error.message === 'Network Error' ? 'Không thể kết nối đến máy chủ.' : fallback
}
