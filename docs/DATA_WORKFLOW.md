# Quy trình dữ liệu Face Attendance System

Tài liệu này mô tả cách hệ thống sử dụng dữ liệu sinh viên thật và dữ liệu Kaggle/LFW trong đồ án. Hai nhóm dữ liệu này được tách biệt để tránh nhầm lẫn giữa điểm danh chính thức và đánh giá mô hình.

## 1. Quy trình dữ liệu thật

Dữ liệu thật là dữ liệu dùng cho điểm danh chính thức của sinh viên.

Quy trình sử dụng:

1. Tạo sinh viên trên giao diện **Sinh viên**.
2. Vào màn hình **Đăng ký khuôn mặt**.
3. Chọn sinh viên và chụp mẫu khuôn mặt bằng camera.
4. Backend detect khuôn mặt, tạo embedding và lưu vào bảng `face_embeddings`.
5. Vào màn hình **Điểm danh**.
6. Chọn buổi học, chọn chế độ **vào lớp** hoặc **ra về**.
7. Bật camera và nhận diện sinh viên.
8. Nếu sinh viên hợp lệ, hệ thống ghi nhận check-in/check-out vào bảng `attendance`.

Điều kiện để được ghi nhận điểm danh chính thức:

- `data_source = "real"`
- `is_demo = false`
- đã đăng ký khuôn mặt

## 2. Vai trò dữ liệu Kaggle/LFW

Dữ liệu Kaggle/LFW chỉ dùng để kiểm thử và đánh giá mô hình nhận diện khuôn mặt.

Dữ liệu này:

- không dùng cho điểm danh chính thức;
- không đại diện cho sinh viên thật trong lớp;
- không được ghi vào bảng điểm danh chính thức;
- chỉ nên dùng trong chức năng **Kiểm thử mô hình** hoặc script đánh giá.

Khi import dữ liệu Kaggle/LFW, hệ thống gắn:

- `data_source = "kaggle"`
- `is_demo = true`
- `registration_method = "import"`

Nếu hệ thống nhận diện ra mẫu Kaggle/LFW trong luồng điểm danh chính thức, hệ thống sẽ chặn ghi nhận điểm danh.

## 3. Ý nghĩa các trường phân loại dữ liệu

`data_source` cho biết nguồn dữ liệu của sinh viên hoặc mẫu khuôn mặt:

- `real`: sinh viên thật, dùng cho điểm danh chính thức.
- `kaggle`: dữ liệu import từ Kaggle/LFW, chỉ dùng đánh giá mô hình.
- `demo`: dữ liệu demo khác, không dùng cho điểm danh chính thức.

`is_demo` cho biết bản ghi có phải dữ liệu demo hay không:

- `false`: dữ liệu thật.
- `true`: dữ liệu demo/Kaggle.

`registration_method` cho biết cách tạo embedding khuôn mặt:

- `camera`: đăng ký bằng camera trên giao diện.
- `upload`: đăng ký bằng ảnh upload nếu hệ thống có hỗ trợ.
- `import`: import từ thư mục/script.
- `null`: sinh viên chưa đăng ký khuôn mặt.

## 4. Cách demo với 10 sinh viên thật

Có thể tạo nhanh 10 sinh viên thật bằng script:

```bash
cd backend
python seed_real_demo_students.py
```

Sau khi tạo sinh viên, quy trình demo bảo vệ:

1. Mở giao diện **Sinh viên** để kiểm tra danh sách 10 sinh viên.
2. Vào **Đăng ký khuôn mặt**.
3. Chọn từng sinh viên và đăng ký bằng camera thật.
4. Vào **Buổi học** và tạo buổi học cho lớp tương ứng nếu chưa có.
5. Vào **Điểm danh**.
6. Chọn buổi học.
7. Chọn chế độ **vào lớp**.
8. Bật camera.
9. Bấm nhận diện để ghi nhận check-in.
10. Chọn chế độ **ra về** và nhận diện lại để ghi nhận check-out nếu cần.

Script chỉ tạo thông tin sinh viên. Script không tạo embedding giả và không thêm ảnh khuôn mặt, vì vậy vẫn phải đăng ký khuôn mặt thật bằng camera.

## 5. Kiểm thử mô hình với Kaggle/LFW

Nếu đã có dữ liệu Kaggle/LFW trong `backend/enrollment_data`, có thể import bằng:

```bash
cd backend
python register_faces_from_folder.py
```

Script sẽ:

- đọc ảnh trong từng thư mục mẫu;
- bỏ qua ảnh lỗi, ảnh không có mặt hoặc ảnh có nhiều hơn một mặt;
- tạo embedding từ ảnh hợp lệ;
- lưu embedding vào bảng `face_embeddings`;
- đánh dấu dữ liệu là Kaggle/demo.

Để kiểm thử trên giao diện:

1. Vào màn hình **Điểm danh**.
2. Chuyển sang tab **Kiểm thử mô hình**.
3. Upload một ảnh cần kiểm thử.
4. Bấm **Kiểm thử nhận diện**.
5. Xem kết quả gồm mã mẫu, tên mẫu, nguồn dữ liệu, độ tương đồng và thời gian xử lý.

Chức năng này chỉ dùng để đánh giá mô hình, không ghi nhận điểm danh.
