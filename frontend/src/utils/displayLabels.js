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
  absent: 'Vắng mặt',
}

export const dataSourceLabels = {
  real: 'Dữ liệu thật',
  demo: 'Dữ liệu demo',
  kaggle: 'Dữ liệu đánh giá Kaggle',
  lfw: 'Dữ liệu đánh giá LFW',
  evaluation: 'Dữ liệu đánh giá',
}

export const registrationMethodLabels = {
  camera: 'Đăng ký bằng camera',
  upload: 'Tải ảnh lên',
  import: 'Nhập từ bộ dữ liệu',
  face_register: 'Đăng ký khuôn mặt',
  evaluation_import: 'Nhập dữ liệu đánh giá',
  demo_seed: 'Dữ liệu demo/seed',
  webcam_mean: 'Đăng ký bằng camera',
  lfw_folder_mean: 'Nhập từ bộ dữ liệu LFW',
  lfw_import: 'Nhập dữ liệu LFW',
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
