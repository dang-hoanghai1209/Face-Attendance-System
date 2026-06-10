export const recognitionStatusLabels = {
  success: 'Nhận diện thành công',
  uncertain: 'Chưa đủ độ tin cậy',
  unknown: 'Không nhận diện được',
  no_face: 'Không phát hiện khuôn mặt',
  multiple_faces: 'Phát hiện nhiều khuôn mặt',
  class_mismatch: 'Khác lớp chính của buổi học',
  invalid_image: 'Ảnh không hợp lệ',
}

export const attendanceStatusLabels = {
  present: 'Có mặt',
  late: 'Đi trễ',
  manual: 'Thủ công',
  absent: 'Vắng mặt',
}

export const dataSourceLabels = {
  real: 'Dữ liệu thật',
  demo: 'Dữ liệu minh họa',
  kaggle: 'Dữ liệu kiểm thử Kaggle',
  lfw: 'Dữ liệu kiểm thử LFW',
}

export const registrationMethodLabels = {
  camera: 'Đăng ký bằng camera',
  upload: 'Tải ảnh lên',
  import: 'Nhập từ bộ dữ liệu',
  webcam_mean: 'Đăng ký bằng camera',
  lfw_folder_mean: 'Nhập từ bộ dữ liệu LFW',
}

export const roleLabels = {
  admin: 'Quản trị viên',
  teacher: 'Giảng viên',
  lecturer: 'Giảng viên',
  student: 'Sinh viên',
  viewer: 'Người xem',
}

export const getDisplayLabel = (labels, value, fallback = '-') =>
  labels[value] || value || fallback
