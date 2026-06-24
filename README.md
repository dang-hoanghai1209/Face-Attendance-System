# Face Attendance System

Face Attendance System la he thong diem danh sinh vien bang nhan dien khuon mat. Project hien tai gom backend FastAPI, database PostgreSQL, pipeline FaceNet/MTCNN va frontend React/Vite.

Tai lieu nay da duoc cap nhat theo code hien co trong repo, khong phai theo dac ta mong muon ban dau.

## Trang thai hien tai

- Backend da co CRUD sinh vien, quan ly buoi hoc, dang ky khuon mat, nhan dien, diem danh, dashboard va report co ban.
- Frontend da co cac man hinh Dashboard, Students, Sessions, Face Register, Attendance va Reports.
- Production flow hien tai la webcam-first: tao sinh vien, chup mau mat tu camera, luu mean embedding vao PostgreSQL, sau do nhan dien de check-in/check-out.
- Legacy embeddings trong `backend/data/embedding_db.pkl` chi nen dung cho dev/bootstrap va chi duoc load khi bat `ENABLE_LEGACY_EMBEDDINGS=true`.
- Da co JWT/RBAC, audit log, Alembic migration va test suite co ban.
- Chua co realtime feed.

## Cong nghe

Backend:

- Python 3.10+
- FastAPI
- SQLAlchemy
- PostgreSQL thong qua `psycopg2-binary`
- Uvicorn
- Pydantic

AI/ML:

- PyTorch
- `facenet-pytorch`
- MTCNN face detector
- InceptionResnetV1 pretrained `vggface2`
- Pillow

Frontend:

- React 19
- Vite
- React Router
- Axios
- Recharts

Reporting:

- Pandas
- OpenPyXL
- ReportLab

## Cau truc project

```text
Face_Attendance_System/
+-- AGENTS.md
+-- README.md
+-- Request.md
+-- backend/
|   +-- data/
|   |   +-- embedding_db.pkl
|   +-- models/
|   |   +-- attendance.py
|   |   +-- face_embedding.py
|   |   +-- session.py
|   |   +-- student.py
|   +-- routes/
|   |   +-- attendance.py
|   |   +-- faces.py
|   |   +-- reports.py
|   |   +-- sessions.py
|   |   +-- students.py
|   +-- database.py
|   +-- face_service.py
|   +-- main.py
|   +-- requirements.txt
|   +-- schema_sync.py
|   +-- seed.py
+-- frontend/
|   +-- api/
|   |   +-- axios.js
|   +-- src/
|   |   +-- components/
|   |   +-- pages/
|   |   +-- App.jsx
|   |   +-- App.css
|   |   +-- index.css
|   |   +-- main.jsx
|   +-- package.json
|   +-- vite.config.js
+-- docker-compose.yml
+-- docker-compose.prod.yml
```

## Tai lieu workflow du lieu

Xem `docs/DATA_WORKFLOW.md` de biet quy trinh du lieu that, vai tro du lieu Kaggle/LFW, y nghia `data_source`/`is_demo`/`registration_method`, cach demo voi 10 sinh vien that va cach kiem thu mo hinh.

## Backend

### Chay backend

```bash
cd backend
pip install -r requirements.txt
alembic -c alembic.ini upgrade head
python main.py
```

Backend mac dinh chay tai:

```text
http://127.0.0.1:8000
```

Can tao `backend/.env` voi bien bat buoc:

```env
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/face_attendance
THRESHOLD_CONFIRM=0.75
THRESHOLD_UNCERTAIN=0.60
ENABLE_LEGACY_EMBEDDINGS=false
```

`backend/.env.example` nen dung `THRESHOLD_CONFIRM`, `THRESHOLD_UNCERTAIN` va `ENABLE_LEGACY_EMBEDDINGS` de khop code hien tai.

### Migration database

App khong tu tao hoac tu sua schema database khi startup nua. Tat ca thay doi schema phai di qua Alembic.

Database moi:

```bash
cd backend
alembic -c alembic.ini upgrade head
```

Database da ton tai va schema hien tai da khop code:

```bash
cd backend
alembic -c alembic.ini stamp 0001_current_schema_with_audit
alembic -c alembic.ini upgrade head
```

Lenh `stamp` chi ghi nhan baseline Alembic, khong sua du lieu. Neu database cu thieu cot/bang, can kiem tra tren ban copy truoc khi chay production migration.

Tao migration moi:

```bash
cd backend
alembic -c alembic.ini revision --autogenerate -m "short_description"
alembic -c alembic.ini upgrade head
```

`schema_sync.py` la legacy/deprecated, chi giu lai cho test tuong thich va khong duoc goi tu startup.

### Startup

Khi startup, `backend/main.py`:

- Khong goi `Base.metadata.create_all(bind=engine)`.
- Khong goi `sync_schema(engine)`.
- Bootstrap admin user neu DB da duoc migrate va bien `AUTH_BOOTSTRAP_ADMIN_*` duoc cau hinh.
- Load legacy embeddings neu `ENABLE_LEGACY_EMBEDDINGS=true`.
- Dang ky route modules: students, attendance, sessions, reports, faces.

### Tao 10 sinh vien that de demo bao ve

Script `backend/seed_real_demo_students.py` tao 10 sinh vien that, khong tao embedding gia va khong luu anh khuon mat. Sau khi chay script, vao man hinh **Dang ky khuon mat** de dang ky camera that cho tung sinh vien.

```bash
cd backend
python seed_real_demo_students.py
```

Script co the chay nhieu lan ma khong tao trung vi kiem tra theo `student_code`. Sinh vien duoc tao voi:

- `data_source="real"`
- `is_demo=false`
- `registration_method=null`
- `face_status="unregistered"`

### Import du lieu Kaggle/LFW de kiem thu mo hinh

Script `backend/register_faces_from_folder.py` import anh trong `backend/enrollment_data/<ma_mau>/`. Du lieu nay chi dung cho danh gia mo hinh va tab **Kiem thu mo hinh**, khong dung cho diem danh chinh thuc.

```bash
cd backend
python register_faces_from_folder.py
```

Khi import, moi mau duoc gan:

- `data_source="kaggle"`
- `is_demo=true`
- `registration_method="import"`
- `face_status="registered"` neu co du embedding hop le

Script tao embedding bang pipeline MTCNN/FaceNet hien co va luu vao `face_embeddings.embedding_data` cung dinh dang production. Script bo qua anh khong detect duoc mat, anh co nhieu hon mot khuon mat, anh loi va log thong ke thanh cong/that bai. Khong co attendance record nao duoc tao boi script nay.

### CORS

Backend doc danh sach origin tu bien moi truong `CORS_ORIGINS`, phan tach bang dau phay. Neu khong cau hinh, backend cho phep dev origins:

- `http://localhost:5173`
- `http://127.0.0.1:5173`

Production nen dat `CORS_ORIGINS` dung frontend public URL, vi du `https://your-frontend.example.com`.

## Database schema hien tai

### `students`

- `id`
- `student_code`
- `full_name`
- `class_name`
- `face_status`
- `avatar_path`
- `created_at`

### `face_embeddings`

- `id`
- `student_id`
- `embedding_data` (`LargeBinary`)
- `source`
- `created_at`

Embedding hien duoc serialize bang `pickle.dumps(embedding_tensor.tolist())` va luu vao `face_embeddings.embedding_data`. Code hien tai chua luu embedding dang `FLOAT8[]` trong bang `students`.

### `sessions`

- `id`
- `subject`
- `class_name`
- `session_date`
- `start_time`
- `end_time`
- `created_by`
- `created_at`

### `attendance`

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

`absent` khong duoc luu cung trong bang attendance. Report tinh vang mat bang cach lay tong so session cua lop tru di so ban ghi co status `present`, `late`, `manual`.

## AI pipeline

### Dang ky khuon mat

Endpoint hien tai:

```text
POST /faces/register
```

Request:

- `multipart/form-data`
- `student_code`
- `files`: danh sach anh

Logic:

1. Kiem tra sinh vien ton tai.
2. Yeu cau it nhat 5 file anh.
3. Moi anh duoc dua qua MTCNN va InceptionResnetV1 de lay embedding.
4. Anh khong detect duoc mat se bi loai.
5. Neu co it nhat 5 embedding hop le, tinh mean embedding.
6. Xoa embedding cu cua sinh vien va luu mot embedding moi voi `source="webcam_mean"`.
7. Cap nhat `students.face_status = "registered"`.

Response thanh cong:

```json
{
  "status": "success",
  "student_code": "SV001",
  "accepted_samples": 8,
  "rejected_samples": 0,
  "rejected_files": [],
  "total_registered_embeddings": 1,
  "message": "Face samples registered successfully."
}
```

### Nhan dien khuon mat

Endpoint:

```text
POST /recognize
```

Request:

- `multipart/form-data`
- `file`: anh can nhan dien

Logic:

1. Doc anh bang Pillow va convert RGB.
2. Detect/crop face bang MTCNN.
3. Trich embedding bang InceptionResnetV1.
4. So cosine similarity voi tat ca embeddings trong DB.
5. Neu bat legacy, so them voi `backend/data/embedding_db.pkl`.
6. Phan loai theo nguong kep.

Nguong:

```env
THRESHOLD_CONFIRM=0.75
THRESHOLD_UNCERTAIN=0.60
```

Ket qua:

- `success`: score >= `THRESHOLD_CONFIRM`
- `uncertain`: `THRESHOLD_UNCERTAIN` <= score < `THRESHOLD_CONFIRM`
- `unknown`: score < `THRESHOLD_UNCERTAIN`
- `no_face`: khong detect duoc mat

Response hien tai:

```json
{
  "status": "success",
  "student_code": "SV001",
  "confidence": 0.87,
  "confidence_percent": "87%",
  "message": "Face matched successfully."
}
```

Code hien tai chua tra ve object `student` day du trong `/recognize`.

## API endpoints hien tai

### Health

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

Body tao session:

```json
{
  "subject": "AI",
  "class_name": "CNTT01",
  "session_date": "2026-04-23",
  "start_time": "07:30:00",
  "end_time": "09:30:00",
  "created_by": "admin"
}
```

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

`POST /attendance/` la alias cua check-in.

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

Chua co trong code hien tai:

- `GET /dashboard/stats`
- `GET /reports/export/excel/semester/{class_name}`

## Attendance logic

### Check-in

Endpoint:

```text
POST /attendance/checkin
```

Body:

```json
{
  "student_code": "SV001",
  "session_id": 1,
  "confidence": 0.87,
  "image_path": null
}
```

Neu chua co ban ghi `student + session`, backend tao record moi. Neu da co record, backend tra record hien co va khong tao trung.

Status:

- Khong co `session.start_time`: `present`
- `check_in_at <= session_date + start_time + 15 phut`: `present`
- Sau nguong tren: `late`

Timestamp attendance dung timezone `Asia/Ho_Chi_Minh` roi luu dang naive datetime vao DB.

### Check-out

Endpoint:

```text
POST /attendance/checkout
```

Body:

```json
{
  "student_code": "SV001",
  "session_id": 1,
  "confidence": 0.82
}
```

Chi checkout duoc khi da co record check-in. Neu da checkout roi, backend tra ve record hien co.

### Manual

Endpoint:

```text
POST /attendance/manual
```

Body:

```json
{
  "student_code": "SV001",
  "session_id": 1,
  "note": "Xac nhan boi giang vien"
}
```

Neu record da ton tai, status duoc cap nhat thanh `manual`. Neu chua co, backend tao record moi voi `status="manual"`.

## Frontend

### Chay frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend mac dinh goi API tai:

```text
http://127.0.0.1:8000
```

Co the doi bang `frontend/.env`:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## Production deploy bang Docker

Khong commit file `.env` that. Dung file example de tao file cau hinh local/production:

```bash
copy .env.prod.example .env.prod
copy backend\.env.production.example backend\.env.production
copy frontend\.env.production.example frontend\.env.production
```

Tao secret manh cho production:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Cap nhat cac gia tri bat buoc trong `.env.prod`:

- `POSTGRES_PASSWORD`
- `DATABASE_URL`
- `SECRET_KEY`
- `AUTH_BOOTSTRAP_ADMIN_PASSWORD`
- `CORS_ORIGINS`
- `VITE_API_BASE_URL`

Build image production:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml build
```

Chay database truoc:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d postgres
```

Chay migration khi deploy:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm backend alembic -c alembic.ini upgrade head
```

Chay backend/frontend production:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
```

Backend image dung Gunicorn voi Uvicorn worker, khong dung `uvicorn --reload`. Frontend duoc build bang Vite production va serve bang Nginx.

### Pages

- `/`: Dashboard, goi `/reports/dashboard/stats`.
- `/students`: them/sua/xoa, tim kiem va hien danh sach sinh vien.
- `/sessions`: tao/sua/xoa, tim kiem va hien danh sach buoi hoc.
- `/faces/register`: chon sinh vien, bat camera, chup mau thu cong hoac tu dong theo heuristic brightness/sharpness, gui `/faces/register`.
- `/attendance`: chon session, check-in/check-out bang camera, confirm ket qua `uncertain`, diem danh manual, xem bang attendance cua session.
- `/reports`: xem summary/warnings theo lop, bao cao theo buoi hoc va xuat Excel/PDF.

Frontend hien con nhieu inline styles va nhieu chu tieng Viet khong dau.

## Report/dashboard

`GET /reports/dashboard/stats` tra ve:

```json
{
  "total_students": 45,
  "registered_faces": 40,
  "unregistered_faces": 5,
  "total_sessions": 12,
  "avg_attendance_rate": 0.75,
  "warning_count": 3,
  "pie_data": [
    { "name": "Present", "value": 75 },
    { "name": "Absent", "value": 25 }
  ]
}
```

`GET /reports/session/{session_id}` tra danh sach day du sinh vien trong lop cua session, gom ca sinh vien vang voi `status="absent"`.

`GET /reports/summary/{class_name}` tinh:

- `present`
- `late`
- `manual`
- `absent`
- `attended`
- `total_sessions`
- `rate`
- `warning`

Nguong warning hien tai: `rate < 0.8`.

## Diem lech can xu ly tiep

- `/recognize` chua tra object `student` day du nhu dac ta ban dau.
- Dang ky khuon mat hien la `/faces/register`, chua co flow `/register/start`, `/register/capture`, `/register/finalize`.
- Frontend Face Register co auto capture theo brightness/sharpness heuristic, chua auto capture theo confidence MTCNN tu backend.
- Anh capture chua duoc luu vao `backend/media/captures/`.
- Embedding production hien luu `LargeBinary`, khong phai `FLOAT8[]`.
- Response format chua dong nhat 100% theo `{ "status": "...", "data": {...}, "message": "..." }`.
- Alembic migration da thay the startup schema sync; can tiep tuc viet migration moi cho moi thay doi schema.
- Da co automated tests backend va Playwright smoke test frontend cho auth/RBAC.
