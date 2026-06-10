# Backend Tasks Cho Codex

Mục tiêu: mở rộng backend theo hướng quản lý học phần, enrollment, GPS và mobile attendance mà không phá logic cũ.

## Thứ Tự Ưu Tiên

1. Đóng băng hành vi hiện tại bằng test tối thiểu cho students, sessions, faces, attendance, reports và model evaluation.
2. Chuẩn hóa tài liệu API trong `API_CONTRACT.md` trước khi thêm endpoint mới.
3. Thêm migration có kiểm soát, ưu tiên Alembic thay vì tiếp tục mở rộng `schema_sync.py` cho schema lớn.
4. Thêm model database mới: `classrooms`, `subjects`, `course_sections`, `enrollments`.
5. Mở rộng `sessions` để liên kết `course_section_id` và `classroom_id`, vẫn giữ `subject` và `class_name` trong giai đoạn tương thích.
6. Thêm service kiểm tra enrollment: sinh viên phải có enrollment active trong course section của session.
7. Thêm service kiểm tra thời gian: chỉ cho phép check-in từ `start_time` đến `start_time + 15 phút`.
8. Thêm service kiểm tra GPS bằng khoảng cách Haversine, bán kính lấy từ `classrooms.radius_meters`.
9. Thêm endpoint mobile check-in mới, không thay thế ngay endpoint `/attendance/checkin` hiện tại.
10. Cập nhật report để hỗ trợ cả session cũ theo `class_name` và session mới theo `course_section_id`.
11. Viết test cho migration, enrollment, GPS, time window và duplicate attendance.

## File Backend Hiện Tại Cần Nắm

- `backend/main.py`: bootstrap FastAPI, CORS, startup schema, `/recognize`, include routers.
- `backend/database.py`: SQLAlchemy engine, session, Base, `DATABASE_URL`.
- `backend/face_service.py`: MTCNN, FaceNet, embedding, threshold kép, matching.
- `backend/schema_sync.py`: vá schema cũ khi startup, cần hạn chế mở rộng thêm cho migration phức tạp.
- `backend/models/*.py`: ORM hiện tại cho students, sessions, attendance, face embeddings, recognition attempts, users.
- `backend/routes/*.py`: API cho auth, students, sessions, faces, attendance, reports.
- `backend/services/attendance_service.py`: nghiệp vụ check-in/check-out/manual hiện tại.
- `backend/services/report_service.py`: thống kê dashboard/report.
- `backend/services/timezone_service.py`: xử lý múi giờ Việt Nam.

## Model Mới Đề Xuất

- `Classroom`: tên phòng, tòa nhà, GPS, bán kính, trạng thái hoạt động.
- `Subject`: mã học phần, tên học phần, số tín chỉ, khoa/bộ môn.
- `CourseSection`: lớp học phần theo kỳ/năm học, học phần, giảng viên, trạng thái.
- `Enrollment`: liên kết sinh viên với lớp học phần, trạng thái enrollment.

## Service Mới Đề Xuất

- `gps_service.py`: tính khoảng cách, kiểm tra độ chính xác GPS, kiểm tra bán kính.
- `enrollment_service.py`: kiểm tra sinh viên thuộc course section.
- `attendance_window_service.py`: kiểm tra khung thời gian điểm danh.
- `mobile_attendance_service.py`: phối hợp auth, enrollment, time, GPS, face recognition và ghi attendance.

## Ràng Buộc Không Được Phá

- Không đổi format embedding hiện tại trong `face_embeddings.embedding_data`.
- Không bỏ endpoint `/attendance/checkin`, `/attendance/checkout`, `/attendance/manual`.
- Không dùng dữ liệu demo/Kaggle/LFW cho điểm danh chính thức.
- Không hard-code bán kính GPS.
- Không để frontend tự quyết định điểm danh hợp lệ.

## Trạng Thái MVP 1

- CRUD classroom/subject/course section/enrollment: đã triển khai.
- Session from section: đã triển khai.
- Enrollment, GPS, time window và report theo enrollment: đã triển khai.
- `GET /students/me/active-sessions?student_id=...`: đã triển khai cho dev mode.
- Check-in success/error contract cho mobile frontend: đã có test.
- Backend test: `45` test pass.
