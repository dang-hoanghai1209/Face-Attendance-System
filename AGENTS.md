# AGENTS.md - Face Attendance System

Tai lieu nay danh cho AI coding agent lam viec trong repo `D:\Face_Attendance_System`.

Doc file nay va `README.md` truoc khi sua code.

## Tong quan

Project: Face Attendance System

Muc tieu: diem danh sinh vien bang nhan dien khuon mat qua camera, ghi nhan check-in/check-out, tinh chuyen can va xuat bao cao.

Stack thuc te:

- Backend: Python, FastAPI, SQLAlchemy, PostgreSQL.
- AI: PyTorch, `facenet-pytorch`, MTCNN, InceptionResnetV1.
- Frontend: React, Vite, Axios, React Router, Recharts.
- Report: Pandas, OpenPyXL, ReportLab.

## Nguyen tac khi lam viec

- Doc code thuc te truoc khi sua, vi tai lieu cu tung bi lech voi implementation.
- Khong dung Kaggle/LFW hoac pickle legacy lam production flow.
- Khong dung nguong don cho face recognition. Luon giu nguong kep:
  - `THRESHOLD_CONFIRM=0.75`
  - `THRESHOLD_UNCERTAIN=0.60`
- Khong bo qua check-out. Attendance phai co du check-in, check-out, manual va trang thai chua check-out.
- Khong hardcode backend base URL trong frontend. Dung `VITE_API_BASE_URL`.
- Khong hardcode `DATABASE_URL`. Dung `.env`.
- Khong revert thay doi cua user neu khong duoc yeu cau.

## Kien truc hien tai

```text
Browser camera
  -> React/Vite frontend
  -> Axios HTTP
  -> FastAPI backend
  -> SQLAlchemy
  -> PostgreSQL
```

Routes chinh hien co:

- `/students`
- `/sessions`
- `/faces`
- `/recognize`
- `/attendance`
- `/reports`

Dashboard hien nam o:

```text
GET /reports/dashboard/stats
```

Khong co endpoint `/dashboard/stats` trong code hien tai.

## Backend files quan trong

- `backend/main.py`: app bootstrap, CORS, startup table creation/schema sync, `/recognize`.
- `backend/database.py`: SQLAlchemy engine/session/base, doc `DATABASE_URL`.
- `backend/face_service.py`: MTCNN, InceptionResnetV1, embedding, cosine matching, threshold logic.
- `backend/schema_sync.py`: startup schema patching cho DB cu.
- `backend/models/*.py`: ORM models.
- `backend/routes/*.py`: business API.

## Frontend files quan trong

- `frontend/api/axios.js`: Axios client, base URL tu `VITE_API_BASE_URL`.
- `frontend/src/App.jsx`: React routes.
- `frontend/src/pages/FaceRegister.jsx`: dang ky khuon mat.
- `frontend/src/pages/Attendance.jsx`: recognition, check-in/check-out, manual attendance.
- `frontend/src/pages/Reports.jsx`: summary/warnings.
- `frontend/src/pages/Dashboard.jsx`: dashboard stats.

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
- `embedding_data`
- `source`
- `created_at`

Important: code hien tai luu embedding trong `face_embeddings.embedding_data` dang `LargeBinary`, serialize bang pickle cua list float. Khong co cot `students.embedding FLOAT8[]` trong implementation hien tai.

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

`absent` duoc tinh trong report, khong luu cung cho moi sinh vien/session.

## Face registration hien tai

Endpoint:

```text
POST /faces/register
```

Request:

- `student_code` trong form-data.
- `files` la danh sach anh.

Logic:

1. Yeu cau sinh vien ton tai.
2. Yeu cau it nhat 5 file.
3. Detect/crop tung anh bang MTCNN.
4. Trich embedding bang InceptionResnetV1.
5. Loai anh khong detect duoc mat.
6. Can it nhat 5 embedding hop le.
7. Tinh mean embedding.
8. Xoa embedding cu, luu mean embedding voi source `webcam_mean`.
9. Set `face_status="registered"`.

Chua co:

- `/register/start/{student_code}`
- `/register/capture/{student_code}`
- `/register/finalize/{student_code}`
- Backend auto capture theo confidence MTCNN
- Luu anh vao `backend/media/captures/`

Frontend `FaceRegister.jsx` hien da co auto capture dua tren heuristic brightness/sharpness cuc bo, nhung khong phai confidence MTCNN tu backend.

## Recognition hien tai

Endpoint:

```text
POST /recognize
```

Response hien tai:

```json
{
  "status": "success | uncertain | unknown | no_face",
  "student_code": "SV001",
  "confidence": 0.87,
  "confidence_percent": "87%",
  "message": "Face matched successfully."
}
```

Response nay chua co object `student` day du. Neu sua, can cap nhat frontend `Attendance.jsx`.

Status rules:

- `success`: score >= `THRESHOLD_CONFIRM`
- `uncertain`: score >= `THRESHOLD_UNCERTAIN` va < `THRESHOLD_CONFIRM`
- `unknown`: score < `THRESHOLD_UNCERTAIN`
- `no_face`: MTCNN khong detect duoc mat

## Attendance hien tai

Endpoints:

- `POST /attendance/`
- `POST /attendance/checkin`
- `POST /attendance/checkout`
- `POST /attendance/manual`
- `GET /attendance/session/{session_id}`
- `GET /attendance/summary/{class_name}`

`POST /attendance/` la alias cho check-in.

Check-in:

- Neu chua co record `student_id + session_id`, tao record moi.
- Neu da co, tra ve record hien co, khong tao trung.
- Tinh `present` hoac `late` theo `session.start_time + 15 minutes`.

Check-out:

- Can co record truoc.
- Cap nhat `check_out_at` va `check_out_conf`.
- Neu da checkout, tra ve record hien co.

Manual:

- Tao moi hoac cap nhat record.
- Set `status="manual"`.

Timezone:

- Attendance dung `Asia/Ho_Chi_Minh` trong `routes/attendance.py`.
- Model defaults con dung `datetime.utcnow` hoac DB `now()` o mot so noi, nen neu can strict timezone thi phai chuan hoa them.

## Reports hien tai

Endpoints:

- `GET /reports/dashboard/stats`
- `GET /reports/summary/{class_name}`
- `GET /reports/warnings/{class_name}`
- `GET /reports/session/{session_id}`
- `GET /reports/export/excel/{class_name}`
- `GET /reports/export/pdf/{class_name}`
- `GET /reports/export/excel/warnings/{class_name}`
- `GET /reports/export/excel/session/{session_id}`
- `GET /reports/export/pdf/session/{session_id}`

Attendance rate:

```text
attended = count(status in ["present", "late", "manual"])
absent = total_sessions - attended
rate = attended / total_sessions
warning = rate < 0.8
```

## Setup

Backend:

```bash
cd backend
pip install -r requirements.txt
python main.py
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Backend env nen co:

```env
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/face_attendance
THRESHOLD_CONFIRM=0.75
THRESHOLD_UNCERTAIN=0.60
ENABLE_LEGACY_EMBEDDINGS=false
```

Frontend env:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## Diem can can than

- `docker-compose.yml` hien la thu muc, khong phai file Docker Compose.
- `backend/.env.example` hien da duoc cap nhat sang threshold kep va `ENABLE_LEGACY_EMBEDDINGS`.
- Repo khong co `.git` trong workspace hien tai.
- `backend/.venv` nam trong project, tranh quet/sua dependency files.
- Chua co automated tests.
- Chua co Alembic migrations.
- Frontend con inline styles va nhieu text khong dau.

## Uu tien tiep theo

1. Sua config drift con lai: Docker Compose va response docs.
2. Hoan thien face registration theo flow session/capture/finalize neu can dung dung dac ta.
3. Them object student day du cho `/recognize`.
4. Luu capture image neu can audit attendance.
5. Them Alembic migrations.
6. Them tests cho attendance/report logic.
7. Cai thien UX cho `uncertain` recognition va manual confirmation neu can luong xac nhan chat hon.
8. Sau core moi them JWT, liveness detection va realtime feed.
