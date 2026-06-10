# Đặc Tả Mobile GPS Attendance

Mục tiêu: cho phép sinh viên điểm danh bằng điện thoại với camera và GPS, trong thời gian giới hạn, có kiểm tra enrollment ở backend.

## Nguyên Tắc

- Backend quyết định điểm danh hợp lệ hay không.
- Frontend chỉ lấy GPS, camera, gửi request và hiển thị kết quả.
- Bán kính hợp lệ lấy từ `classrooms.radius_meters`, không hard-code 5m.
- Chỉ cho phép check-in từ `start_time` đến `start_time + 15 phút`.
- Sinh viên phải có enrollment active trong `course_section` của session.
- Không dùng dữ liệu demo/Kaggle/LFW cho điểm danh chính thức.

## Luồng Người Dùng

1. Sinh viên đăng nhập trên mobile.
2. Ứng dụng hiển thị các buổi học liên quan đến sinh viên.
3. Sinh viên chọn buổi học đang mở điểm danh.
4. Ứng dụng xin quyền vị trí.
5. Ứng dụng xin quyền camera.
6. Sinh viên chụp ảnh khuôn mặt.
7. Ứng dụng gửi request điểm danh.
8. Backend trả kết quả.
9. Ứng dụng hiển thị kết quả bằng tiếng Việt.

## Request Mobile Check-In

Endpoint đề xuất: `POST /attendance/mobile/checkin`.

Trong MVP hiện tại, frontend sử dụng `POST /attendance/checkin`. Endpoint mobile riêng chưa được triển khai để tránh phá API cũ.

Danh sách buổi học cho dev mode:

```text
GET /students/me/active-sessions?student_id={student_id}
```

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

## Thứ Tự Kiểm Tra Ở Backend

1. Kiểm tra token đăng nhập.
2. Xác định sinh viên từ tài khoản đăng nhập.
3. Kiểm tra session tồn tại.
4. Kiểm tra session có `course_section_id` và `classroom_id`.
5. Kiểm tra sinh viên có enrollment active trong course section.
6. Kiểm tra thời gian hiện tại không trước `start_time`.
7. Kiểm tra thời gian hiện tại không sau `start_time + 15 phút`.
8. Kiểm tra phòng học có tọa độ GPS và `radius_meters`.
9. Kiểm tra request có GPS.
10. Kiểm tra `gps_accuracy_m` nằm trong ngưỡng chấp nhận được.
11. Tính khoảng cách Haversine giữa sinh viên và phòng học.
12. So sánh khoảng cách với `classroom.radius_meters`.
13. Kiểm tra sinh viên đã đăng ký khuôn mặt.
14. Nhận diện khuôn mặt bằng pipeline hiện tại.
15. Nếu nhận diện đúng sinh viên đăng nhập và đạt ngưỡng xác nhận, ghi attendance.
16. Nếu đã có attendance cho `student_id + session_id`, trả trạng thái đã điểm danh.

## Chính Sách Khuôn Mặt

- `success` đúng sinh viên đăng nhập: cho phép ghi điểm danh.
- `success` nhưng ra sinh viên khác: từ chối, ghi audit nếu có.
- `uncertain`: không ghi điểm danh tự động; hướng dẫn liên hệ giảng viên.
- `unknown`: không ghi điểm danh.
- `no_face`: không ghi điểm danh.
- `multiple_faces`: không ghi điểm danh.

## Chính Sách GPS

- `gps_lat`, `gps_lng` bắt buộc cho mobile check-in.
- `gps_accuracy_m` cần được gửi nếu trình duyệt cung cấp.
- Nếu độ chính xác GPS quá thấp, backend trả `gps_accuracy_low` thay vì ghi điểm danh.
- Bán kính phòng học là cấu hình theo phòng, không hard-code.
- Nên lưu `distance_meters` và `gps_accuracy_m` để phục vụ audit.

## Trạng Thái Trả Về

- `success`: Điểm danh thành công.
- `already_checked_in`: Bạn đã điểm danh buổi học này.
- `not_started`: Buổi học chưa bắt đầu.
- `attendance_closed`: Đã quá thời gian điểm danh.
- `not_enrolled`: Bạn không có trong danh sách đăng ký của lớp học phần này.
- `gps_missing`: Chưa nhận được dữ liệu vị trí.
- `gps_accuracy_low`: Độ chính xác GPS chưa đủ tin cậy.
- `gps_out_of_range`: Bạn đang ở ngoài phạm vi điểm danh.
- `face_not_registered`: Bạn chưa đăng ký khuôn mặt.
- `unknown`: Không nhận diện được khuôn mặt.
- `uncertain`: Kết quả nhận diện chưa đủ độ tin cậy.
- `no_face`: Không phát hiện khuôn mặt.
- `multiple_faces`: Phát hiện nhiều khuôn mặt.

## Check-Out

Flow hiện tại có check-out. Giai đoạn đầu không nên bỏ check-out. Nếu mobile cần check-out, nên tạo endpoint riêng hoặc mở rộng endpoint hiện tại với policy rõ ràng. Check-out không nhất thiết dùng cùng cửa sổ 15 phút của check-in; cần quyết định riêng theo yêu cầu nghiệp vụ.

## Bảo Mật Và Riêng Tư

- Chỉ lưu GPS phục vụ audit điểm danh.
- Không hiển thị tọa độ chi tiết cho người không có quyền.
- Không lưu ảnh khuôn mặt thô nếu không có nhu cầu audit rõ ràng.
- Nếu lưu ảnh audit, cần cấu hình retention và quyền truy cập.
