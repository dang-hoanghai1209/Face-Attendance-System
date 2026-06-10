# Integration Checklist

Checklist này dùng trước khi triển khai Mobile-First + GPS + enrollment vào code thật.

## Backend

- [ ] API contract đã được cập nhật trước khi code endpoint mới.
- [ ] Có migration version rõ ràng cho bảng mới.
- [ ] Có backup database trước migration.
- [ ] `classrooms.radius_meters` được dùng trong GPS validation, không hard-code 5m.
- [ ] Enrollment được kiểm tra ở backend trước khi ghi attendance.
- [x] Time window được kiểm tra ở backend: `start_time` đến `start_time + 15 phút`.
- [x] Endpoint cũ `/attendance/checkin`, `/attendance/checkout`, `/attendance/manual` vẫn chạy.
- [x] Report cũ theo `class_name` vẫn chạy trong giai đoạn chuyển tiếp.
- [x] Message backend trả về tiếng Việt có dấu cho luồng MVP mới.
- [x] Test cho GPS, time window, enrollment, face mismatch và duplicate attendance đã có.
- [x] `GET /students/me/active-sessions?student_id=...` đã sẵn sàng cho dev mode.
- [x] CORS cho phép `http://localhost:5173` và `http://127.0.0.1:5173`.

Ngrok chưa được mở tự động. Khi cần test HTTPS, thêm chính xác origin ngrok đang dùng vào cấu hình CORS thay vì dùng wildcard.

## Database

- [ ] Tạo bảng `classrooms`.
- [ ] Tạo bảng `subjects`.
- [ ] Tạo bảng `course_sections`.
- [ ] Tạo bảng `enrollments`.
- [ ] Thêm `course_section_id` và `classroom_id` vào `sessions` dạng nullable.
- [ ] Thêm cột GPS/mobile vào `attendance` dạng nullable.
- [ ] Có index cho enrollment và các khóa ngoại chính.
- [ ] Có script kiểm tra row count trước/sau migration.
- [ ] Có kế hoạch rollback.

## Frontend

- [ ] Frontend dùng `VITE_API_BASE_URL`.
- [ ] Giao diện mobile-first không làm vỡ desktop.
- [ ] Có màn hình danh sách buổi học đang mở cho sinh viên.
- [ ] Có xử lý quyền GPS bằng tiếng Việt.
- [ ] Có xử lý quyền camera bằng tiếng Việt.
- [ ] Có countdown đến hạn điểm danh backend trả về.
- [ ] Không tự quyết định điểm danh hợp lệ ở client.
- [ ] Hiển thị message lỗi/thành công backend trả về.
- [ ] Các status kỹ thuật được map sang tiếng Việt.

## Kiểm Thử Tích Hợp

- [ ] Sinh viên có enrollment, đúng giờ, đúng GPS, đúng mặt: điểm danh thành công.
- [ ] Sinh viên không có enrollment: bị từ chối.
- [ ] Trước giờ học: bị từ chối `not_started`.
- [ ] Sau `start_time + 15 phút`: bị từ chối `attendance_closed`.
- [ ] Ngoài bán kính phòng học: bị từ chối `gps_out_of_range`.
- [ ] GPS độ chính xác thấp: bị từ chối `gps_accuracy_low`.
- [ ] Chưa đăng ký khuôn mặt: bị từ chối `face_not_registered`.
- [ ] Nhận diện ra sinh viên khác: bị từ chối và ghi audit.
- [ ] Điểm danh trùng: không tạo thêm record.
- [ ] Check-out cũ vẫn hoạt động.
- [ ] Báo cáo cũ vẫn tính đúng dữ liệu lịch sử.

## Triển Khai

- [ ] Chạy migration trên database staging trước.
- [ ] So sánh số lượng bản ghi trước/sau migration.
- [ ] Test smoke backend.
- [ ] Test build frontend.
- [ ] Kiểm tra luồng mobile trên Chrome Android hoặc trình duyệt mobile thật.
- [ ] Kiểm tra quyền HTTPS nếu dùng GPS trên trình duyệt.
- [ ] Có phương án rollback database và backend.

## Trạng Thái Backend MVP 1

- [x] Model mới đã được thêm.
- [x] Schema sync tạo được bảng/cột mới.
- [x] Seed MVP 1 chạy được và idempotent.
- [x] Test backend hiện tại pass.
- [x] API cũ vẫn còn và tiếp tục chạy.
