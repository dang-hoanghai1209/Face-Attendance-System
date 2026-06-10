# Quy Tắc Dự Án

Tài liệu này là nền tảng kỹ thuật cho giai đoạn mở rộng Face Attendance System theo hướng Mobile-First, GPS, giới hạn thời gian điểm danh và quản lý học phần/enrollment.

## Nguyên Tắc Bắt Buộc

1. Không phá logic cũ đang hoạt động: sinh viên, buổi học, đăng ký khuôn mặt, nhận diện, check-in, check-out, điểm danh thủ công và báo cáo hiện tại phải tiếp tục chạy.
2. Không đổi tên biến, bảng, cột, endpoint hoặc response cũ nếu chưa có kế hoạch tương thích ngược.
3. Backend là nơi quyết định cuối cùng về GPS, thời gian điểm danh, enrollment, nhận diện khuôn mặt và quyền truy cập.
4. Frontend chỉ thu thập dữ liệu thiết bị, gửi request và hiển thị kết quả backend trả về; không tự quyết định hợp lệ/không hợp lệ cho điểm danh chính thức.
5. Toàn bộ text hiển thị cho người dùng phải dùng tiếng Việt có dấu, tự nhiên và thống nhất.
6. Không hard-code bán kính 5m trong logic. Bán kính hợp lệ phải lấy từ `classrooms.radius_meters`.
7. Chỉ cho phép điểm danh trong khoảng `session.start_time <= now <= session.start_time + 15 phút`.
8. Sinh viên chỉ được điểm danh nếu có enrollment hợp lệ trong `course_section` của buổi học.
9. Không dùng dữ liệu demo, Kaggle, LFW hoặc sample test để ghi nhận điểm danh chính thức.
10. Migration database phải có kế hoạch backup, rollback và kiểm tra dữ liệu trước/sau migration.

## Quy Tắc Backend

- Giữ `DATABASE_URL` trong `.env`, không hard-code connection string.
- Giữ ngưỡng kép nhận diện: `THRESHOLD_CONFIRM` và `THRESHOLD_UNCERTAIN`.
- Không chuyển đổi format embedding nếu chưa có migration riêng và script kiểm chứng.
- Không bỏ qua check-out của flow hiện tại.
- Mọi endpoint mới phải được mô tả trong `API_CONTRACT.md` trước khi frontend tích hợp.
- Mọi message có khả năng hiển thị lên UI phải là tiếng Việt có dấu.

## Quy Tắc Frontend

- Không hard-code backend base URL; dùng `VITE_API_BASE_URL`.
- Không tự tính quyết định nghiệp vụ quan trọng như GPS hợp lệ, còn thời gian điểm danh hay có enrollment.
- Hiển thị nguyên nhân backend trả về cho người dùng bằng tiếng Việt.
- Thiết kế mobile-first, nhưng không làm hỏng màn hình desktop hiện tại.
- Các trạng thái kỹ thuật như `success`, `unknown`, `no_face`, `attendance_closed` phải được map sang tiếng Việt khi hiển thị.

## Luồng Điểm Danh Mobile Mục Tiêu

1. Sinh viên đăng nhập.
2. Frontend gọi API lấy buổi học đang mở cho sinh viên.
3. Sinh viên cấp quyền GPS và camera.
4. Frontend gửi `session_id`, tọa độ GPS, độ chính xác GPS, ảnh khuôn mặt và thông tin thiết bị.
5. Backend kiểm tra auth, enrollment, thời gian, GPS, khuôn mặt và duplicate attendance.
6. Backend ghi nhận điểm danh nếu hợp lệ và trả kết quả tiếng Việt.
7. Frontend hiển thị trạng thái, thời gian điểm danh, khoảng cách GPS, độ tin cậy nhận diện và hướng dẫn tiếp theo.

## Điều Kiện Điểm Danh Hợp Lệ

- Tài khoản sinh viên hợp lệ.
- Sinh viên thuộc enrollment đang hoạt động của lớp học phần.
- Buổi học đã bắt đầu và chưa quá 15 phút đầu.
- Buổi học có phòng học được cấu hình GPS.
- Tọa độ sinh viên nằm trong `classrooms.radius_meters`.
- Ảnh khuôn mặt hợp lệ và nhận diện đạt ngưỡng xác nhận.
- Chưa có bản ghi điểm danh trùng cho cùng `student_id + session_id`.

## Ghi Chú Tương Thích

Các trường hiện tại như `sessions.subject`, `sessions.class_name`, `attendance.status`, `students.class_name` vẫn cần được giữ trong giai đoạn chuyển tiếp. Khi thêm `course_sections`, `classrooms` và `enrollments`, cần hỗ trợ cả dữ liệu cũ và dữ liệu mới cho tới khi migration hoàn tất.

## Phân Công Tích Hợp

- Codex phụ trách model SQLAlchemy, migration/schema sync, FastAPI, auth/role, GPS, time window, enrollment, attendance và report.
- Antigravity phụ trách React/Vite, mobile-first, PWA, GPS UI, countdown, quản lý học phần/enrollment và tích hợp theo `API_CONTRACT.md`.
- Backend hoặc mock API contract phải ổn định trước khi frontend tích hợp.

## Bảo Mật

- Không lưu mật khẩu dạng plain text.
- API quản trị phải kiểm tra role.
- Sinh viên chỉ được xem và điểm danh các buổi thuộc enrollment hợp lệ của mình.
- Không mở CORS wildcard khi bật credentials.
- Không đưa `.env`, khóa bí mật hoặc dữ liệu khuôn mặt thật vào tài liệu/commit.

## Checklist Trước Khi Commit

- Backend khởi động và test pass.
- Frontend build pass.
- API contract và migration plan đã cập nhật.
- Text hiển thị cho người dùng là tiếng Việt có dấu.
- Không thay đổi thuật toán nhận diện hoặc dữ liệu thật ngoài phạm vi yêu cầu.
