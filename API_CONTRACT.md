# API Contract

Trạng thái: bản nháp kỹ thuật cho giai đoạn mở rộng Mobile-First + GPS + giới hạn thời gian + enrollment. Những endpoint đã có trong code được ghi là "hiện tại". Những endpoint mới là "đề xuất" và chưa được xem là đã triển khai.

## Quy Ước Chung

- Backend trả message tiếng Việt có dấu cho mọi lỗi/thành công có thể hiển thị trên giao diện.
- Frontend không tự quyết định GPS/time/enrollment; frontend chỉ gửi dữ liệu và hiển thị kết quả backend trả về.
- Không hard-code bán kính 5m. Giá trị hợp lệ lấy từ `classrooms.radius_meters`.
- Cửa sổ điểm danh: `start_time <= now <= start_time + 15 phút` theo múi giờ Việt Nam.
- Sinh viên chỉ được điểm danh nếu có enrollment hợp lệ trong `course_section` của session.
- Response lỗi nên giữ cấu trúc dễ hiển thị:

```json
{
  "status": "attendance_closed",
  "message": "Đã quá thời gian điểm danh. Hệ thống chỉ cho phép điểm danh trong 15 phút đầu buổi học."
}
```

## Endpoint Hiện Tại

### Auth

- `POST /auth/login`
- `GET /auth/me`

### Students

- `GET /students/`
- `POST /students/`
- `PUT /students/{student_id}`
- `DELETE /students/{student_id}`

### Sessions

- `GET /sessions/`
- `POST /sessions/`
- `PUT /sessions/{session_id}`
- `DELETE /sessions/{session_id}`

Session hiện tại vẫn dùng `subject`, `class_name`, `session_date`, `start_time`, `end_time`, `created_by`.

### Faces

- `POST /faces/register`
- `GET /faces/student/{student_code}`

### Recognition

- `POST /recognize`
- `POST /recognize/model-test`

### Attendance

- `POST /attendance/`
- `POST /attendance/checkin`
- `POST /attendance/checkout`
- `POST /attendance/manual`
- `GET /attendance/session/{session_id}`
- `GET /attendance/summary/{class_name}`
- `DELETE /attendance/{attendance_id}`

### Reports

- `GET /reports/dashboard/stats`
- `GET /reports/summary/{class_name}`
- `GET /reports/warnings/{class_name}`
- `GET /reports/session/{session_id}`
- `GET /reports/export/excel/{class_name}`
- `GET /reports/export/pdf/{class_name}`
- `GET /reports/export/excel/warnings/{class_name}`
- `GET /reports/export/excel/session/{session_id}`
- `GET /reports/export/pdf/session/{session_id}`
- `GET /reports/model-evaluation/stats`
- `GET /reports/model-evaluation/details`
- `GET /reports/model-evaluation/export`

## Endpoint Đề Xuất

### Classrooms

#### GET /classrooms

```json
[
  {
    "id": 1,
    "name": "Phòng 101",
    "building": "Khu A",
    "gps_lat": 12.238912,
    "gps_lng": 109.196748,
    "radius_meters": 15,
    "is_active": true
  }
]
```

#### POST /classrooms

```json
{
  "name": "Phòng 101",
  "building": "Khu A",
  "gps_lat": 12.238912,
  "gps_lng": 109.196748,
  "radius_meters": 15,
  "is_active": true
}
```

### Subjects

#### GET /subjects

```json
[
  {
    "id": 1,
    "subject_code": "CNTT301",
    "subject_name": "Kiểm thử phần mềm",
    "credits": 3,
    "department": "Công nghệ thông tin"
  }
]
```

### Course Sections

#### GET /course-sections

Query hỗ trợ: `semester`, `academic_year`, `subject_id`, `status`.

```json
[
  {
    "id": 1,
    "section_code": "CNTT301-64CNTT-2026",
    "subject_id": 1,
    "subject_name": "Kiểm thử phần mềm",
    "semester": "2026-1",
    "academic_year": "2025-2026",
    "lecturer_name": "Nguyễn Văn A",
    "status": "open",
    "student_count": 35
  }
]
```

#### POST /course-sections

```json
{
  "section_code": "CNTT301-64CNTT-2026",
  "subject_id": 1,
  "semester": "2026-1",
  "academic_year": "2025-2026",
  "lecturer_name": "Nguyễn Văn A",
  "min_students": 10,
  "max_students": 60,
  "status": "open"
}
```

### Enrollments

#### GET /course-sections/{course_section_id}/students

```json
[
  {
    "student_id": 10,
    "student_code": "63133870",
    "full_name": "Nguyễn Văn B",
    "class_name": "64CNTT",
    "face_status": "registered",
    "enrollment_status": "active"
  }
]
```

#### POST /enrollments

```json
{
  "course_section_id": 1,
  "student_id": 10,
  "status": "active"
}
```

### Sessions From Course Section

#### POST /sessions/from-section

```json
{
  "course_section_id": 1,
  "classroom_id": 1,
  "session_date": "2026-06-09",
  "start_time": "07:00",
  "end_time": "09:30",
  "note": "Buổi học tuần 1"
}
```

Response:

```json
{
  "id": 5,
  "course_section_id": 1,
  "classroom_id": 1,
  "subject_name": "Kiểm thử phần mềm",
  "section_code": "CNTT301-64CNTT-2026",
  "classroom_name": "Phòng 101",
  "session_date": "2026-06-09",
  "start_time": "07:00",
  "end_time": "09:30",
  "attendance_deadline": "2026-06-09T07:15:00+07:00"
}
```

### Mobile Attendance

#### GET /students/me/active-sessions

MVP dev mode dùng query `student_id` trong khi chưa có liên kết tài khoản sinh viên hoàn chỉnh:

```text
GET /students/me/active-sessions?student_id=52
```

Chỉ trả các buổi học thuộc lớp học phần mà sinh viên có enrollment `active`. Thời gian được tính theo `Asia/Ho_Chi_Minh`.

```json
[
  {
    "session_id": 5,
    "course_section_id": 1,
    "subject_name": "Kiểm thử phần mềm",
    "section_code": "CNTT301-64CNTT-2026",
    "classroom_name": "Phòng 101",
    "session_date": "2026-06-09",
    "start_time": "07:00",
    "end_time": "09:30",
    "attendance_deadline": "07:15",
    "status": "open_for_attendance"
  }
]
```

Giá trị `status`:

- `not_started`: chưa tới `start_time`.
- `open_for_attendance`: từ `start_time` đến hết `start_time + 15 phút`.
- `closed`: đã quá hạn điểm danh.

#### POST /attendance/mobile/checkin

Request:

```json
{
  "session_id": 5,
  "gps_lat": 12.238912,
  "gps_lng": 109.196748,
  "gps_accuracy_m": 8.5,
  "image_base64": "...",
  "device_info": {
    "platform": "mobile-web",
    "user_agent": "Mozilla/5.0"
  }
}
```

Response thành công:

```json
{
  "status": "success",
  "message": "Điểm danh thành công.",
  "attendance_id": 100,
  "student_code": "63133870",
  "full_name": "Nguyễn Văn B",
  "confidence": 0.86,
  "distance_meters": 12.4,
  "allowed_radius_meters": 15,
  "check_in_time": "2026-06-09T07:05:12+07:00"
}
```

Response lỗi GPS:

```json
{
  "status": "gps_out_of_range",
  "message": "Bạn đang ở ngoài phạm vi điểm danh của phòng học.",
  "distance_meters": 42.8,
  "allowed_radius_meters": 15
}
```

Response lỗi thời gian:

```json
{
  "status": "attendance_closed",
  "message": "Đã quá thời gian điểm danh. Hệ thống chỉ cho phép điểm danh trong 15 phút đầu buổi học."
}
```

Response chưa tới giờ:

```json
{
  "status": "not_started",
  "message": "Buổi học chưa bắt đầu. Vui lòng quay lại khi đến giờ học."
}
```

Response chưa đăng ký học phần:

```json
{
  "status": "not_enrolled",
  "message": "Bạn không có trong danh sách đăng ký của lớp học phần này."
}
```

Response nhận diện chưa đạt:

```json
{
  "status": "uncertain",
  "message": "Kết quả nhận diện chưa đủ độ tin cậy. Vui lòng liên hệ giảng viên để xác nhận.",
  "confidence": 0.68
}
```

## Mã Trạng Thái Cần Chuẩn Hóa

- `success`: thành công.
- `not_started`: buổi học chưa bắt đầu.
- `attendance_closed`: đã quá thời gian điểm danh.
- `not_enrolled`: sinh viên không thuộc lớp học phần.
- `gps_missing`: thiếu dữ liệu GPS.
- `gps_accuracy_low`: độ chính xác GPS không đủ tin cậy.
- `gps_out_of_range`: ngoài phạm vi phòng học.
- `face_not_registered`: sinh viên chưa đăng ký khuôn mặt.
- `unknown`: không nhận diện được.
- `uncertain`: chưa đủ độ tin cậy.
- `no_face`: không phát hiện khuôn mặt.
- `multiple_faces`: phát hiện nhiều khuôn mặt.
- `already_checked_in`: đã điểm danh trước đó.

## Backend MVP 1 Đã Triển Khai

### Models/Tables

- `classrooms`: phòng học, tọa độ GPS và `radius_meters`.
- `subjects`: học phần.
- `course_sections`: lớp học phần.
- `enrollments`: danh sách sinh viên đăng ký lớp học phần.
- `sessions` bổ sung `section_id`, `classroom_id`, `note` dạng nullable.
- `attendance` bổ sung `gps_lat`, `gps_lng`, `gps_accuracy`, `distance_meters`, `liveness_passed` dạng nullable/default an toàn.
- `users.role` chấp nhận: `admin`, `teacher`, `lecturer`, `student`, `viewer`.

### Endpoint Mới

- `GET /classrooms/`
- `POST /classrooms/`
- `PUT /classrooms/{classroom_id}`
- `DELETE /classrooms/{classroom_id}`
- `GET /subjects/`
- `POST /subjects/`
- `PUT /subjects/{subject_id}`
- `DELETE /subjects/{subject_id}`
- `GET /course-sections/`
- `POST /course-sections/`
- `PUT /course-sections/{section_id}`
- `DELETE /course-sections/{section_id}`
- `GET /course-sections/{section_id}/students`
- `POST /enrollments`
- `DELETE /enrollments/{enrollment_id}`
- `GET /students/{student_id}/enrollments`
- `POST /sessions/from-section`

### POST /sessions/from-section

Request:

```json
{
  "section_id": 1,
  "classroom_id": 1,
  "session_date": "2026-06-10",
  "start_time": "07:00:00",
  "end_time": "09:00:00",
  "note": "Buổi học tuần 1"
}
```

Response: object session hiện tại, có thêm `section_id`, `classroom_id`, `note`.

### POST /attendance/checkin

Request cũ vẫn dùng được. Request mới có thể gửi thêm GPS:

```json
{
  "student_code": "64100001",
  "session_id": 1,
  "confidence": 0.91,
  "image_path": null,
  "gps_lat": 12.238912,
  "gps_lng": 109.196748,
  "gps_accuracy": 5.5
}
```

Response thành công:

```json
{
  "status": "success",
  "message": "Điểm danh thành công.",
  "student_code": "64100001",
  "full_name": "Sinh viên MVP 1",
  "confidence": 0.86,
  "distance_meters": 3.2,
  "allowed_radius_meters": 20,
  "check_in_time": "2026-06-10T07:05:00",
  "data": {}
}
```

Các lỗi nghiệp vụ của endpoint trả JSON top-level gồm `status`, `message` và dữ liệu bổ sung nếu có:

- `gps_missing`
- `gps_out_of_range`
- `not_enrolled`
- `not_started`
- `attendance_closed`

Các trạng thái nhận diện `no_face`, `multiple_faces`, `uncertain`, `unknown` được trả bởi `/recognize` trước bước `/attendance/checkin`.

## Dữ Liệu Seed MVP 1 Hiện Tại

- `classroom_id`: `1`
- `classroom_name`: `Phòng MVP 101`
- `gps_lat`: `12.238912`
- `gps_lng`: `109.196748`
- `radius_meters`: `20`
- `subject_id`: `1`
- `subject_name`: `Học phần kiểm thử MVP`
- `section_id`: `1`
- `section_code`: `MVP101-64CNTT-2026`
- Sinh viên: `(52, 64100001)`, `(53, 64100002)`, `(54, 64100003)`
- `session_id`: `12`
- `session_date`: `2026-06-10`
- `start_time`: `07:00`
- `end_time`: `09:00`

## Request Mẫu E2E

Các API quản trị/check-in hiện yêu cầu Bearer token:

```bash
curl "http://127.0.0.1:8000/students/me/active-sessions?student_id=52"
```

GPS gần phòng:

```bash
curl -X POST "http://127.0.0.1:8000/attendance/checkin" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"student_code":"64100001","session_id":12,"confidence":0.86,"gps_lat":12.238912,"gps_lng":109.196748,"gps_accuracy":5}'
```

GPS xa phòng:

```bash
curl -X POST "http://127.0.0.1:8000/attendance/checkin" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"student_code":"64100001","session_id":12,"confidence":0.86,"gps_lat":13.0,"gps_lng":109.0,"gps_accuracy":5}'
```

Session seed `12` chỉ mở điểm danh từ `07:00` đến `07:15` ngày `2026-06-10`. Muốn test GPS gần/xa thành công đúng nhánh GPS, hãy tạo một session mới bằng `/sessions/from-section` với `start_time` nằm trong 15 phút hiện tại. Nếu dùng session `12` sau `07:15`, backend sẽ trả `attendance_closed` trước khi kiểm tra GPS.

Nếu session có `section_id`, backend kiểm tra sinh viên có enrollment `active`. Nếu không có enrollment:

```json
{
  "detail": "Bạn không có trong danh sách đăng ký của lớp học phần này."
}
```

Nếu session có `classroom_id`, backend tính khoảng cách GPS theo Haversine và so sánh với `classrooms.radius_meters`. Nếu ngoài phạm vi:

```json
{
  "detail": "Bạn đang ở ngoài phạm vi điểm danh của phòng học."
}
```

Nếu chưa tới giờ:

```json
{
  "detail": "Buổi học chưa bắt đầu. Vui lòng quay lại khi đến giờ học."
}
```

Nếu quá 15 phút đầu:

```json
{
  "detail": "Đã quá thời gian điểm danh. Hệ thống chỉ cho phép điểm danh trong 15 phút đầu buổi học."
}
```
