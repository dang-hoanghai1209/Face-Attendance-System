# Project Request / Working Notes

File nay tong hop trang thai hien tai cua Face Attendance System sau khi doc lai code trong repo.

## Muc tieu san pham

He thong diem danh sinh vien bang khuon mat:

1. Quan ly danh sach sinh vien.
2. Tao buoi hoc theo lop, mon, ngay va gio hoc.
3. Dang ky mau khuon mat tu webcam.
4. Nhan dien khuon mat tu anh camera.
5. Ghi nhan check-in, check-out hoac diem danh manual.
6. Tong hop ty le chuyen can va canh bao sinh vien co nguy co vang qua muc.
7. Xuat bao cao Excel/PDF theo lop.

## Stack thuc te trong repo

- Backend: FastAPI, SQLAlchemy, Pydantic, Uvicorn.
- Database: PostgreSQL, cau hinh qua `DATABASE_URL`.
- AI: PyTorch, `facenet-pytorch`, MTCNN, InceptionResnetV1 pretrained `vggface2`.
- Image: Pillow.
- Report: Pandas, OpenPyXL, ReportLab.
- Frontend: React 19, Vite, React Router, Axios, Recharts.

## Cau truc chinh

```text
backend/
  database.py
  face_service.py
  main.py
  schema_sync.py
  seed.py
  models/
    attendance.py
    face_embedding.py
    session.py
    student.py
  routes/
    attendance.py
    faces.py
    reports.py
    sessions.py
    students.py

frontend/
  api/axios.js
  src/App.jsx
  src/components/
    AttendanceChart.jsx
    Navbar.jsx
    WarningTable.jsx
  src/pages/
    Attendance.jsx
    Dashboard.jsx
    FaceRegister.jsx
    Reports.jsx
    Sessions.jsx
    Students.jsx
```

## Backend files

### `backend/main.py`

- Khoi tao FastAPI app.
- Cau hinh CORS cho Vite dev server.
- Startup tao bang va goi `sync_schema(engine)`.
- Load legacy embeddings neu `ENABLE_LEGACY_EMBEDDINGS=true`.
- Cung cap `/`, `/health`, `/recognize`.
- Include routers: students, attendance, sessions, reports, faces.

### `backend/database.py`

- Load `.env`.
- Yeu cau `DATABASE_URL`.
- Tao SQLAlchemy `engine`, `SessionLocal`, `Base`.
- Cung cap dependency `get_db()`.

### `backend/face_service.py`

- Khoi tao device `cuda` neu co, nguoc lai `cpu`.
- Khoi tao MTCNN va InceptionResnetV1.
- Chuyen image bytes thanh embedding.
- Serialize/deserialize embedding bang pickle.
- Tinh cosine similarity.
- Match embedding voi DB va tuy chon legacy pickle.
- Nguong:
  - `THRESHOLD_CONFIRM`, default `0.75`
  - `THRESHOLD_UNCERTAIN`, default `0.60`
  - `ENABLE_LEGACY_EMBEDDINGS`, default `false`

### `backend/schema_sync.py`

- Migration ad-hoc khi startup.
- Bo sung cot moi cho `students`, `sessions`, `attendance` hoac `attendance_log`.
- Copy du lieu cu tu `checked_in_at` sang `check_in_at`.
- Copy `confidence` sang `check_in_conf`.
- Set default cho `face_status`, `created_at`, `status`.

Day chi la co che tam thoi, chua thay the duoc migration versioned nhu Alembic.

## Models hien tai

### Student

Table: `students`

- `id`
- `student_code`
- `full_name`
- `class_name`
- `face_status`
- `avatar_path`
- `created_at`

### FaceEmbedding

Table: `face_embeddings`

- `id`
- `student_id`
- `embedding_data`
- `source`
- `created_at`

Embedding hien tai luu bang `LargeBinary`, noi dung la pickle cua list float.

### Session

Table: `sessions`

- `id`
- `subject`
- `class_name`
- `session_date`
- `start_time`
- `end_time`
- `created_by`
- `created_at`

### Attendance

Table: `attendance`

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

## API da implement

### Root/health

- `GET /`
- `GET /health`

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

### Faces

- `POST /faces/register`
- `GET /faces/student/{student_code}`

### Recognition

- `POST /recognize`

### Attendance

- `POST /attendance/`
- `POST /attendance/checkin`
- `POST /attendance/checkout`
- `POST /attendance/manual`
- `GET /attendance/session/{session_id}`
- `GET /attendance/summary/{class_name}`

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

## Frontend pages

### Dashboard

- File: `frontend/src/pages/Dashboard.jsx`
- Goi `GET /reports/dashboard/stats`.
- Hien card tong quan va pie chart bang Recharts.

### Students

- File: `frontend/src/pages/Students.jsx`
- Them sinh vien.
- Sua sinh vien.
- Xoa sinh vien.
- Tim kiem va hien danh sach sinh vien.

### Sessions

- File: `frontend/src/pages/Sessions.jsx`
- Tao/sua/xoa session voi subject, class, date, start/end time, created_by.
- Tim kiem va hien danh sach session.

### FaceRegister

- File: `frontend/src/pages/FaceRegister.jsx`
- Chon sinh vien.
- Bat/tat camera.
- Chup mau thu cong bang nut.
- Co auto capture tren frontend dua vao brightness/sharpness heuristic.
- Yeu cau it nhat 5 mau truoc khi gui.
- Goi `POST /faces/register`.
- Hien so registered embeddings.

### Attendance

- File: `frontend/src/pages/Attendance.jsx`
- Chon session.
- Chon action `checkin` hoac `checkout`.
- Bat camera, chup anh, goi `/recognize`.
- Neu recognition `success`, tu dong goi `/attendance/checkin` hoac `/attendance/checkout`.
- Neu `uncertain`, hien ket qua va cho xac nhan/huy truoc khi ghi attendance.
- Neu `unknown` hoac `no_face`, hien ket qua va khong ghi attendance.
- Co manual attendance form.
- Hien bang attendance cua session.

### Reports

- File: `frontend/src/pages/Reports.jsx`
- Nhap class name.
- Goi `/reports/summary/{className}` va `/reports/warnings/{className}`.
- Hien chart, bang canh bao, report theo buoi hoc.
- Xuat Excel/PDF tong hop theo lop, Excel canh bao, Excel/PDF theo buoi hoc.

## Business logic hien co

### Face registration

Hien tai khong co `/register/start`, `/register/capture`, `/register/finalize`.

Flow dang dung:

```text
POST /faces/register
```

- Input: `student_code`, `files[]`.
- Toi thieu 5 file.
- Anh khong detect duoc mat bi loai.
- Toi thieu 5 embedding hop le.
- Luu mot mean embedding cho sinh vien.
- Cap nhat `face_status="registered"`.

### Recognition

`POST /recognize` tra:

```json
{
  "status": "success | uncertain | unknown | no_face",
  "student_code": "SV001",
  "confidence": 0.87,
  "confidence_percent": "87%",
  "message": "..."
}
```

Khac voi dac ta ban dau: chua tra object `student` day du.

### Check-in

- Neu da co record cho `student_id + session_id`, API khong tao trung.
- Neu chua co, tao record moi.
- `status` tu dong:
  - khong co `start_time`: `present`
  - trong 15 phut sau gio bat dau: `present`
  - sau 15 phut: `late`

### Check-out

- Can co record check-in truoc.
- Neu da checkout, tra lai record hien co.
- Neu chua checkout, cap nhat `check_out_at` va `check_out_conf`.

### Manual

- Tao moi hoac cap nhat record hien co.
- Set `status="manual"`.
- Luu `note`.

### Attendance rate

- Counted statuses: `present`, `late`, `manual`.
- `absent = total_sessions - attended`.
- `rate = attended / total_sessions`.
- Warning khi `rate < 0.8`.

## Cau hinh

### Backend `.env`

Nen dung:

```env
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/face_attendance
THRESHOLD_CONFIRM=0.75
THRESHOLD_UNCERTAIN=0.60
ENABLE_LEGACY_EMBEDDINGS=false
```

`SECRET_KEY` hien co trong example nhung chua duoc dung vi chua co auth.

### Frontend `.env`

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## Viec can lam tiep

Muc uu tien cao:

- Quyet dinh chuan luu embedding: tiep tuc `face_embeddings.embedding_data LargeBinary` hoac chuyen sang `FLOAT8[]`.
- Dong nhat response format neu bat buoc theo `{ status, data, message }`.
- Chuan hoa text tieng Viet trong source frontend neu can hien thi co dau.
- Tao file `docker-compose.yml` that neu can Docker Compose.

Muc core con thieu so voi dac ta:

- Flow `/register/start`, `/register/capture`, `/register/finalize`.
- Backend/AI-driven auto capture theo face confidence MTCNN thay vi heuristic brightness/sharpness tren frontend.
- Luu anh capture vao `backend/media/captures/`.
- `/recognize` tra day du thong tin student.
- Endpoint `/dashboard/stats` neu muon dung path rieng thay vi `/reports/dashboard/stats`.

Muc engineering:

- Them Alembic migrations.
- Them test backend cho attendance/recognition/report logic.
- Tach frontend UI components, giam inline styles.
- Lam UX rieng cho `uncertain` recognition neu can quy trinh xac nhan chat hon hien tai.
- Them auth/JWT khi core flow on dinh.
- Them liveness detection sau khi recognition/attendance da chay on dinh.

## Known issues

- Repo khong co `.git`, nen khong co git diff/status chuan de review thay doi.
- `docker-compose.yml` la thu muc.
- Text trong repo chu yeu dang khong dau; can thong nhat encoding/noi dung tieng Viet neu refactor tai lieu va UI.
- `backend/.venv` dang nam trong project; khi quet file can exclude thu muc nay.
- Chua co test suite.
