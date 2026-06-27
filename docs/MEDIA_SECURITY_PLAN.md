# Media Security Plan

Tai lieu nay dinh nghia ke hoach bao ve media nhay cam trong Face Attendance System (FAS).
Pham vi tai lieu chi la security architecture va migration plan; khong thay doi code, database schema hoac business logic.

## 1. Current State

Backend hien mount public static media trong `backend/main.py`:

```python
MEDIA_DIR = Path(BASE_DIR) / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")
```

Tat ca file nam duoi `backend/media` co the duoc truy cap qua URL `/media/...` ma khong can JWT/RBAC.

### File Dang Duoc Luu Duoi `backend/media`

Code hien tai co the ghi cac nhom file sau:

- `media/recognition_attempts/{YYYYMMDD}/{time}_{uuid}.jpg`
  - Anh upload khi goi `/recognize`.
  - Luu qua `save_recognition_capture`.
  - Path duoc ghi vao `recognition_attempts.image_path`.
- `media/alerts/{session_id}/{timestamp}_{uuid}.jpg`
  - Anh bang chung cho canh bao `SPOOF`, `UNKNOWN_FACE`, `NOT_ENROLLED`, `LATE_ENTRY`.
  - Path duoc ghi vao `security_alerts.captured_img`.
- `media/security_snapshots/{session_id}/{timestamp}_{reason_code}.jpg`
  - Anh bang chung cho canh bao `FACE_UNCLEAR`.
  - Path duoc ghi vao `security_alerts.captured_img`.
- `attendance.check_in_img`
  - Co the chua path anh check-in/capture tu recognition flow.
- `students.avatar_path`
  - Field ton tai trong model; neu duoc dung thi la private user media.

### API Dang Tra Media Path

- `POST /recognize`
  - Tra `capture_path`.
  - Co the tra `snapshot_path` voi `FACE_UNCLEAR`.
- `GET /alerts/session/{session_id}`
  - Tra `captured_img`.
- `GET /alerts/session/{session_id}/active`
  - Tra `captured_img`.
- Attendance/check-in response
  - Co the tra `captured_img` hoac `check_in_img`.
- CSV export
  - Attendance CSV co cot `check_in_img`.
  - Alerts CSV co cot `captured_img`.
- Reports/model evaluation
  - Co `image_path` cho evaluation dataset, admin-only.

### Frontend Dang Phu Thuoc `/media`

`frontend/src/pages/Sessions.jsx` dung alert evidence image:

- `getImageUrl(path)` build URL tu `VITE_API_BASE_URL` + `media/...`.
- `AlertImage` render `<img src={url}>`.
- Click image mo public URL bang `window.open(url, "_blank", ...)`.

Neu tat `/media` ngay, alert image UI se bi vo.

## 2. Risk

Risk level: High.

Ly do:

- URL possession la du de xem anh nhay cam.
- StaticFiles bypass JWT/RBAC hoan toan.
- Anh khuon mat, attendance capture, spoof evidence va recognition attempts la biometric/sensitive media.
- Filename co UUID lam giam kha nang doan URL nhung khong phai access control.
- URL/path co the leak qua:
  - API response.
  - CSV export.
  - Audit/debug log.
  - Browser history.
  - Screenshots.
  - Shared links.
  - Frontend open image in new tab.
- Neu `/media` duoc expose tren production domain, bat ky ai co link co the tai anh.

## 3. Target Architecture

Muc tieu la tach public static asset va sensitive media.

### Public Media

`/media` chi nen dung cho asset that su public:

- Logo.
- Placeholder images.
- Static documentation/demo asset da duoc phe duyet.

Khong dat face capture, attendance image, alert evidence, recognition attempt hoac biometric sample trong public media root.

### Private Media

Sensitive images chuyen sang private storage:

```text
backend/private_media/
  recognition_attempts/
  alerts/
  security_snapshots/
  attendance/
```

Thu muc private khong duoc mount bang `StaticFiles`.

### Authenticated Media Endpoint

Backend tao endpoint doc file nhay cam sau khi xac thuc JWT va kiem tra object-level scope.

Endpoint tra binary image qua `FileResponse` hoac streaming response, kem header an toan:

- `Cache-Control: private, no-store`
- `Content-Type` dung theo file.
- Khong expose absolute filesystem path.
- Khong cho path traversal.

### Object-Level Scope

Truoc khi tra file, backend phai query object lien quan:

- Alert image -> `security_alerts.id` -> `session_id`.
- Attendance check-in image -> `attendance.id` -> `session_id`, `student_id`.
- Recognition attempt image -> `recognition_attempts.id`.

Sau do kiem tra role/scope theo policy trong `docs/READ_ACCESS_POLICY.md`.

## 4. Proposed Endpoints

Endpoint de xuat:

```text
GET /media-private/alerts/{alert_id}/image
GET /media-private/attendance/{attendance_id}/check-in-image
GET /media-private/recognition-attempts/{attempt_id}/image
```

Alternative neu muon route gan voi resource domain:

```text
GET /alerts/{alert_id}/image
GET /attendance/{attendance_id}/check-in-image
GET /recognition-attempts/{attempt_id}/image
```

Khuyen nghi ban dau:

- Dung prefix `/media-private` de ro y nghia security boundary.
- Khong nhan raw path tu client.
- Client chi truyen object id.
- Backend tu lay path tu DB sau khi authorize.

## 5. Authorization Policy

### Admin

- Duoc xem toan bo sensitive media.
- Bao gom alert evidence, attendance image va recognition attempt image.

### Teacher

- Chi duoc xem media thuoc session/lop hoc phan minh phu trach.
- Scope nen dung logic thong nhat:
  - `sessions.created_by` khop `user.username` hoac `user.full_name`.
  - `course_sections.lecturer_name` khop `user.username` hoac `user.full_name`.
  - Session co `section_id` thuoc section teacher phu trach.
- Teacher khong duoc xem recognition attempts ngoai session/lop minh phu trach.
- Neu recognition attempt khong co `session_id`, mac dinh teacher khong duoc xem.

### Student

- Mac dinh khong duoc xem alert/security evidence.
- Co the duoc xem attendance check-in image cua chinh minh neu product policy cho phep.
- Khong duoc xem anh cua sinh vien khac.
- Khong duoc xem recognition attempts admin/audit unless co endpoint self-specific va policy ro.

### Recognition Attempts

Default policy:

- Admin-only.
- Teacher chi duoc xem neu attempt co `session_id` va session thuoc scope cua teacher.
- Student khong expose mac dinh.

Neu recognition attempts chua can UI, khong tao frontend access cho loai nay trong phase dau.

## 6. Migration Strategy

### Phase 1: Authenticated Endpoint Doc Duoc Path Cu

- Tao endpoint private doc file dua tren object id.
- Endpoint co the doc path cu dang bat dau bang `media/...`.
- Backend resolve path an toan trong `backend/media` hoac `backend/private_media`.
- Them auth va object-level scope.
- Khong tat `/media` trong phase nay de tranh pha UI.

### Phase 2: Frontend Chuyen Sang Authenticated Blob Endpoint

- `AlertImage` khong build public `/media/...` nua.
- Frontend goi authenticated endpoint bang Axios voi `responseType: "blob"`.
- Dung `URL.createObjectURL(blob)` de render image.
- Click image mo modal/blob URL, khong mo public static path.
- Xu ly 401/403/404 bang fallback UI.

### Phase 3: Luu File Moi Vao `private_media/`

- Doi writer:
  - `save_recognition_capture`
  - `save_alert_capture`
  - `save_face_unclear_snapshot`
  - any future attendance capture writer
- File moi luu duoi `backend/private_media`.
- DB co the tiep tuc luu relative path, vi endpoint se resolve ca private/public legacy roots.
- Khong doi schema neu chua can.

### Phase 4: Migrate File Cu Khoi `backend/media`

- Viet script migration rieng.
- Copy/move file cu:
  - `backend/media/recognition_attempts` -> `backend/private_media/recognition_attempts`
  - `backend/media/alerts` -> `backend/private_media/alerts`
  - `backend/media/security_snapshots` -> `backend/private_media/security_snapshots`
- Cap nhat DB path neu quyet dinh doi prefix.
- Chay tren staging truoc.
- Backup file va database truoc khi chay production.

### Phase 5: Gioi Han Hoac Bo `/media`

Lua chon A:

- Giu `/media`, nhung chi mount `backend/public_media`.
- Khong mount `backend/media` nua.

Lua chon B:

- Bo mount `/media` neu khong con public asset.

Sau phase nay, direct sensitive URL nhu `/media/alerts/...` phai tra 404.

## 7. Backward Compatibility

Trong migration:

- Khong pha alert image UI ngay.
- Khong xoa file cu.
- Khong doi database schema neu chua can.
- Private endpoint phase 1 phai doc duoc path cu `media/...`.
- CSV/API co the tam thoi van tra path cu, nhung frontend khong nen dung path do lam public URL sau phase 2.
- Sau khi frontend da chuyen sang endpoint theo object id, co the an/hardening path fields trong response neu can.

## 8. Test Strategy

Backend tests can co:

- Anonymous request vao private image endpoint tra `401`.
- Student khong xem duoc alert image cua nguoi khac/session khac: `403`.
- Student khong xem duoc alert image mac dinh: `403`.
- Student chi xem duoc check-in image cua minh neu policy cho phep.
- Teacher xem duoc alert/attendance image cua session minh phu trach.
- Teacher khong xem duoc session khong phu trach: `403`.
- Admin xem duoc sensitive image: `200`.
- Old path `media/...` van duoc private endpoint doc neu object scope hop le.
- Path traversal bi chan:
  - `../`
  - absolute path
  - encoded traversal
- Missing DB object tra `404`.
- DB object co path nhung file mat tra `404`.
- Sau migration phase 5, direct `/media/...` sensitive URL tra `404`.

Frontend/E2E tests can co:

- Alert modal hien image qua authenticated endpoint.
- 403 image response hien fallback.
- Student UI khong request alert evidence neu khong co quyen.

## 9. Implementation Backlog

Thu tu de xuat:

1. **B1: Tao private media endpoint**
   - Them route `/media-private/...`.
   - Doc object id, authorize, resolve file path an toan.
   - Ho tro legacy path `media/...`.

2. **B2: Them tests**
   - Backend auth/scope tests cho alert image, attendance image, recognition attempt image.
   - Tests cho anonymous, student, teacher, admin.

3. **B3: Sua frontend `AlertImage`**
   - Dung authenticated blob endpoint.
   - Bo build public `/media/...` cho sensitive image.

4. **B4: Doi save path moi sang `private_media`**
   - `save_recognition_capture`.
   - `save_alert_capture`.
   - `save_face_unclear_snapshot`.
   - Future attendance capture writer.

5. **B5: Migration/don static media**
   - Copy/move file cu.
   - Validate DB references.
   - Doi `/media` sang `public_media` hoac bo mount.

6. **B6: Update docs/tests**
   - Cap nhat README.
   - Cap nhat `READ_ACCESS_POLICY.md` neu policy thay doi.
   - Cap nhat tests static media cu.

## 10. Non-Goals

- Khong implement code trong task tao tai lieu nay.
- Khong doi API contract ngay.
- Khong xoa file cu.
- Khong chay migration.
- Khong tat `/media` ngay.
- Khong giai quyet object-level read policy ngoai pham vi media; xem `docs/READ_ACCESS_POLICY.md`.
