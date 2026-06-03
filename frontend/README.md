# Frontend

Frontend cua Face Attendance System duoc build bang React 19 va Vite.

## Commands

```bash
npm install
npm run dev
npm run build
npm run lint
npm run preview
```

## Configuration

Mac dinh frontend goi backend tai:

```text
http://127.0.0.1:8000
```

Neu backend chay dia chi khac, tao `frontend/.env`:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Axios client nam o:

```text
frontend/api/axios.js
```

## Routes

- `/`: Dashboard, goi `/reports/dashboard/stats`.
- `/students`: quan ly sinh vien, them/sua/xoa va tim kiem sinh vien.
- `/sessions`: tao/sua/xoa, tim kiem va xem danh sach buoi hoc.
- `/faces/register`: dang ky khuon mat bang webcam, chup thu cong hoac tu dong theo quality heuristic, gui `/faces/register`.
- `/attendance`: nhan dien bang camera, check-in/check-out, confirm ket qua uncertain, diem danh manual.
- `/reports`: bao cao tong hop theo lop, canh bao, bao cao theo buoi hoc va xuat file.

## Backend endpoints dang phu thuoc

- `GET /students/`
- `POST /students/`
- `PUT /students/{student_id}`
- `DELETE /students/{student_id}`
- `GET /sessions/`
- `POST /sessions/`
- `PUT /sessions/{session_id}`
- `DELETE /sessions/{session_id}`
- `POST /faces/register`
- `GET /faces/student/{student_code}`
- `POST /recognize`
- `POST /attendance/checkin`
- `POST /attendance/checkout`
- `POST /attendance/manual`
- `GET /attendance/session/{session_id}`
- `GET /reports/dashboard/stats`
- `GET /reports/summary/{class_name}`
- `GET /reports/warnings/{class_name}`
- `GET /reports/session/{session_id}`
- `GET /reports/export/excel/{class_name}`
- `GET /reports/export/pdf/{class_name}`
- `GET /reports/export/excel/warnings/{class_name}`
- `GET /reports/export/excel/session/{session_id}`
- `GET /reports/export/pdf/session/{session_id}`

## Ghi chu hien tai

- UI con dung nhieu inline styles.
- `Students.jsx` va `Sessions.jsx` da co them/sua/xoa/tim kiem.
- `FaceRegister.jsx` co auto capture theo brightness/sharpness heuristic tren frontend, chua phai MTCNN confidence tu backend.
- `Attendance.jsx` auto post khi `/recognize` tra `success`; voi `uncertain`, UI cho xac nhan hoac huy truoc khi ghi attendance.
- Mot so text trong source dang khong dau, can don dep khi refactor UI.
