# Kế Hoạch Migration Database

Mục tiêu: mở rộng schema để hỗ trợ phòng học GPS, học phần, lớp học phần và enrollment mà vẫn giữ dữ liệu điểm danh hiện tại.

## Schema Hiện Tại

### students

- `id`
- `student_code`
- `full_name`
- `class_name`
- `face_status`
- `data_source`
- `registration_method`
- `is_demo`
- `avatar_path`
- `created_at`

### sessions

- `id`
- `subject`
- `class_name`
- `session_date`
- `start_time`
- `end_time`
- `created_by`
- `created_at`

### attendance

- `id`
- `student_id`
- `session_id`
- `check_in_at`
- `check_out_at`
- `check_in_conf`
- `check_out_conf`
- `check_in_img`
- `status`
- `note`
- `created_at`

### face_embeddings

- `id`
- `student_id`
- `embedding_data`
- `source`
- `created_at`

## Schema Mới Đề Xuất

### classrooms

- `id`
- `name`
- `building`
- `gps_lat`
- `gps_lng`
- `radius_meters`
- `is_active`
- `created_at`
- `updated_at`

### subjects

- `id`
- `subject_code`
- `subject_name`
- `credits`
- `department`
- `created_at`
- `updated_at`

### course_sections

- `id`
- `section_code`
- `subject_id`
- `semester`
- `academic_year`
- `lecturer_user_id`
- `lecturer_name`
- `min_students`
- `max_students`
- `status`
- `created_at`
- `updated_at`

### enrollments

- `id`
- `course_section_id`
- `student_id`
- `status`
- `created_at`
- `updated_at`

Ràng buộc đề xuất: unique `course_section_id + student_id`.

### sessions mở rộng

- Giữ các cột cũ: `subject`, `class_name`, `session_date`, `start_time`, `end_time`, `created_by`, `created_at`.
- Thêm `course_section_id` nullable.
- Thêm `classroom_id` nullable.
- Có thể thêm `attendance_open_at` và `attendance_close_at`, nhưng giai đoạn đầu nên tính từ `session_date + start_time + 15 phút` để tránh lệch logic.

### attendance mở rộng

- `check_in_lat`
- `check_in_lng`
- `gps_accuracy_m`
- `distance_meters`
- `gps_status`
- `attendance_source`
- `device_info`
- `mobile_check_in_at`

Không thay thế ngay `check_in_at`, `check_out_at`, `status` hiện tại.

## Các Giai Đoạn Migration

### Giai Đoạn 1: Chuẩn Bị

- Backup database thật.
- Ghi nhận row count của `students`, `sessions`, `attendance`, `face_embeddings`.
- Thêm Alembic hoặc migration script có version rõ ràng.
- Không xóa `schema_sync.py` ngay; chỉ hạn chế thêm logic phức tạp vào đó.

### Giai Đoạn 2: Tạo Bảng Mới

- Tạo `classrooms`, `subjects`, `course_sections`, `enrollments`.
- Thêm index cho mã học phần, mã lớp học phần, enrollment và khóa ngoại.
- Chưa ép `sessions.course_section_id` hoặc `sessions.classroom_id` là NOT NULL.

### Giai Đoạn 3: Backfill Dữ Liệu

- Tạo subject từ `sessions.subject` nếu có dữ liệu cũ.
- Tạo course section tạm từ tổ hợp `subject + class_name`.
- Gán `sessions.course_section_id` theo mapping tạm.
- Tạo enrollment từ `students.class_name` và session class nếu cần, nhưng phải đánh dấu là dữ liệu chuyển đổi để giảng viên kiểm tra.

### Giai Đoạn 4: Mở Rộng Attendance

- Thêm các cột GPS/mobile nullable vào `attendance`.
- Endpoint mobile mới ghi thêm GPS và source.
- Endpoint cũ vẫn hoạt động khi các cột mới null.

### Giai Đoạn 5: Siết Ràng Buộc

- Sau khi dữ liệu đã được rà soát, mới cân nhắc NOT NULL cho `course_section_id`, `classroom_id` trên session mới.
- Không áp ràng buộc quá sớm lên dữ liệu lịch sử.

## Rủi Ro Migration

- Chưa có Alembic, hiện đang dùng `schema_sync.py`; migration lớn dễ khó rollback nếu làm trực tiếp trong startup.
- `sessions.subject` và `sessions.class_name` là text tự do, có thể không map sạch sang subject/course section.
- `students.class_name` không tương đương enrollment; không nên suy luận enrollment chính thức nếu chưa được xác nhận.
- Attendance đang unique theo `student_id + session_id`; cần giữ ràng buộc này để tránh trùng điểm danh.
- Timestamp hiện có thể là naive datetime; khi thêm GPS/mobile cần chuẩn hóa Asia/Ho_Chi_Minh.
- Dữ liệu demo/Kaggle có thể lẫn trong students; phải lọc khỏi điểm danh chính thức.
- GPS trong nhà sai số lớn; radius quá nhỏ sẽ tạo nhiều false reject.
- Thêm khóa ngoại NOT NULL quá sớm có thể làm hỏng dữ liệu cũ.
- Report hiện dựa nhiều vào `class_name`; khi chuyển sang course section cần hỗ trợ song song trong một thời gian.

## Migration Backend MVP 1

Project hiện chưa có Alembic. Backend MVP 1 dùng cơ chế an toàn hiện có:

1. SQLAlchemy model mới được thêm vào metadata.
2. Khi backend startup, `Base.metadata.create_all(bind=engine)` tạo các bảng mới nếu chưa tồn tại.
3. `schema_sync(engine)` bổ sung các cột nullable mới cho bảng cũ.
4. Không xóa dữ liệu cũ.
5. Không đổi tên cột cũ.

### Cách Chạy Migration MVP 1

1. Backup database thật trước khi chạy.
2. Cập nhật code backend.
3. Khởi động backend:

```bash
cd backend
python main.py
```

Khi startup, backend sẽ tạo/bổ sung:

- Bảng `classrooms`.
- Bảng `subjects`.
- Bảng `course_sections`.
- Bảng `enrollments`.
- Cột `sessions.section_id`.
- Cột `sessions.classroom_id`.
- Cột `sessions.note`.
- Cột `attendance.gps_lat`.
- Cột `attendance.gps_lng`.
- Cột `attendance.gps_accuracy`.
- Cột `attendance.distance_meters`.
- Cột `attendance.liveness_passed`.

### Seed MVP 1

Có thể tạo dữ liệu thử nghiệm tối thiểu bằng:

```bash
cd backend
python seed_mvp1.py
```

Script tạo:

- 1 classroom.
- 1 subject.
- 1 course_section.
- 3 students/enrollments.
- 1 session gắn với section và classroom.

Script không tạo attendance giả và không tạo embedding giả.

### Lưu Ý

- Với PostgreSQL hiện tại, foreign key cho cột mới trên bảng cũ không được thêm bằng `ALTER TABLE` trong MVP 1 để tránh rủi ro với dữ liệu lịch sử. Model SQLAlchemy vẫn khai báo FK cho database tạo mới.
- Khi chuyển sang migration chuẩn, nên đưa phần này vào Alembic revision riêng.
- Startup và schema sync đã được kiểm tra trên database hiện tại; các bảng/cột MVP 1 đều tồn tại.
- Dependency test hiện dùng `pytest` và `httpx`, đã được ghi trong `backend/requirements.txt`.
