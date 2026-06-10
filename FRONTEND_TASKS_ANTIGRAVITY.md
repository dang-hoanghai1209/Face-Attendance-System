# Frontend Tasks Cho Antigravity

Mục tiêu: chuẩn bị frontend React/Vite theo hướng mobile-first, GPS và enrollment, nhưng chỉ tích hợp theo API backend đã công bố trong `API_CONTRACT.md`.

## Nguyên Tắc

1. Không tự triển khai logic nghiệp vụ quyết định điểm danh hợp lệ ở client.
2. Không hard-code backend URL, dùng `VITE_API_BASE_URL`.
3. Không hard-code bán kính GPS, deadline hay danh sách enrollment ở frontend.
4. Toàn bộ nội dung hiển thị phải là tiếng Việt có dấu.
5. Giao diện mobile-first nhưng vẫn dùng tốt trên desktop.
6. Luôn hiển thị message từ backend nếu backend trả về message cụ thể.

## File Frontend Hiện Tại Cần Nắm

- `frontend/src/App.jsx`: định nghĩa route và layout chính.
- `frontend/api/axios.js`: cấu hình Axios, base URL, token interceptor.
- `frontend/src/pages/Attendance.jsx`: nhận diện, check-in/check-out, điểm danh thủ công, tab kiểm thử mô hình.
- `frontend/src/pages/FaceRegister.jsx`: đăng ký khuôn mặt bằng camera.
- `frontend/src/pages/Reports.jsx`: thống kê, báo cáo, kiểm thử mô hình.
- `frontend/src/pages/Students.jsx`: quản lý sinh viên.
- `frontend/src/pages/Sessions.jsx`: quản lý buổi học.
- `frontend/src/pages/Dashboard.jsx`: tổng quan hệ thống.
- `frontend/src/pages/Login.jsx`: đăng nhập.
- `frontend/src/components/Navbar.jsx`: menu/sidebar.
- `frontend/src/utils/apiError.js`: chuẩn hóa lỗi API.
- `frontend/src/utils/displayLabels.js`: map trạng thái kỹ thuật sang tiếng Việt.

## Màn Hình Mobile Đề Xuất

### Trang Sinh Viên Mobile

- Danh sách buổi học hôm nay.
- Trạng thái từng buổi: chưa bắt đầu, đang mở điểm danh, đã đóng, đã điểm danh.
- Countdown đến hạn điểm danh.
- Nút "Điểm danh" chỉ hiển thị khi backend cho phép mở flow.

### Flow Điểm Danh Mobile

1. Chọn buổi học.
2. Hiển thị thông tin học phần, phòng học, thời gian, hạn điểm danh.
3. Xin quyền GPS.
4. Hiển thị trạng thái GPS: đang lấy vị trí, độ chính xác thấp, đã sẵn sàng.
5. Xin quyền camera.
6. Chụp ảnh khuôn mặt.
7. Gửi request mobile check-in.
8. Hiển thị kết quả backend trả về.

### Quản Trị

- Quản lý phòng học và tọa độ GPS.
- Quản lý học phần.
- Quản lý lớp học phần.
- Quản lý danh sách sinh viên đăng ký học phần.
- Tạo buổi học từ lớp học phần và phòng học.

## Component Đề Xuất

- `MobileAttendanceHome`: danh sách buổi học đang liên quan đến sinh viên.
- `GPSStatusCard`: trạng thái quyền GPS, tọa độ, độ chính xác.
- `AttendanceCountdown`: countdown đến `attendance_deadline` backend trả về.
- `MobileCameraCapture`: chụp ảnh gửi check-in.
- `AttendanceResultSheet`: hiển thị kết quả thành công/thất bại.
- `ClassroomForm`: nhập phòng học, GPS và bán kính.
- `CourseSectionForm`: tạo/sửa lớp học phần.
- `EnrollmentManager`: thêm/xóa sinh viên trong lớp học phần.

## Trạng Thái Cần Hiển Thị Tiếng Việt

- `open_for_attendance`: Đang mở điểm danh.
- `not_started`: Buổi học chưa bắt đầu.
- `attendance_closed`: Đã hết thời gian điểm danh.
- `not_enrolled`: Không thuộc lớp học phần này.
- `gps_missing`: Chưa có dữ liệu GPS.
- `gps_accuracy_low`: Độ chính xác GPS chưa đủ tin cậy.
- `gps_out_of_range`: Ngoài phạm vi điểm danh.
- `face_not_registered`: Chưa đăng ký khuôn mặt.
- `success`: Điểm danh thành công.
- `uncertain`: Chưa đủ độ tin cậy.
- `unknown`: Không nhận diện được.
- `no_face`: Không phát hiện khuôn mặt.
- `multiple_faces`: Phát hiện nhiều khuôn mặt.

## Việc Không Làm Ở Frontend

- Không tự tính sinh viên có được điểm danh hay không dựa trên enrollment cache.
- Không tự quyết định GPS trong/ngoài lớp để ghi nhận chính thức.
- Không tự sửa status attendance nếu backend không xác nhận.
- Không che message lỗi cụ thể của backend bằng lỗi chung chung.

## Backend Sẵn Sàng Tích Hợp

- Dùng `GET /students/me/active-sessions?student_id={id}` cho danh sách session mobile.
- Dùng `POST /attendance/checkin` với `gps_lat`, `gps_lng`, `gps_accuracy`.
- Success check-in trả field top-level và vẫn giữ object `data` tương thích cũ.
- Lỗi GPS/time/enrollment trả `status` và `message` top-level.
- CORS hiện cho phép Vite tại `http://localhost:5173` và `http://127.0.0.1:5173`.
