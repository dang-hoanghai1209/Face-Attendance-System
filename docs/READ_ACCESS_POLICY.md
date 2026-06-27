# Read Access Policy

Tai lieu nay dinh nghia object-level read access policy de ap dung cho Face Attendance System (FAS).
Pham vi tai lieu chi la policy va migration plan; khong thay doi code hay business logic.

## 1. Nguyen Tac Chung

FAS xu ly du lieu sinh vien, diem danh, anh khuon mat, canh bao bao mat va du lieu sinh trac hoc. Read access phai duoc cap theo nguyen tac least privilege:

- `admin`: duoc xem toan bo du lieu van hanh, audit, bao cao, cau hinh hoc phan va media nhay cam khi can quan tri he thong.
- `teacher`: chi duoc xem du lieu thuoc lop hoc phan, buoi hoc, danh sach sinh vien, diem danh, canh bao va bao cao ma teacher phu trach.
- `student`: chi duoc xem du lieu ca nhan cua minh va cac buoi hoc/lop hoc phan ma minh dang enroll. Khong duoc xem du lieu ca nhan, diem danh, canh bao bao mat hoac face status cua sinh vien khac.

Object ownership/scope nen duoc xac dinh bang:

- `sessions.created_by` khop `user.username` hoac `user.full_name`.
- `course_sections.lecturer_name` khop `user.username` hoac `user.full_name`.
- `enrollments.student_id` khop student profile cua user role `student`.
- Quan he `session.section_id -> course_sections.id -> enrollments.course_section_id`.
- Fallback theo `session.class_name` chi nen dung neu khong co section/enrollment va da duoc phe duyet ro.

## 2. Student Visibility

Student khong nen co broad read access.

| Cau hoi | Policy de xuat |
|---|---|
| Student co duoc xem danh sach student toan he thong khong? | Khong. |
| Student co duoc xem roster lop/session khong? | Khong mac dinh. Neu can hien thi lop hoc, chi hien thi danh sach toi thieu va phai co phe duyet san pham. |
| Student co duoc xem attendance cua nguoi khac khong? | Khong. Chi xem attendance cua chinh minh. |
| Student co duoc xem alert/security warning khong? | Khong. Security alerts la du lieu nhay cam va co the chua anh khuon mat nguoi khac. |
| Student co duoc xem face status cua nguoi khac khong? | Khong. Chi xem face status cua chinh minh neu can hien thi trang thai dang ky. |

Student co the xem:

- Profile auth cua minh qua `/auth/me`.
- Active sessions cua minh qua `/students/me/active-sessions`.
- Dashboard/report ca nhan neu service da filter theo student.
- Attendance record cua minh trong session minh enroll, neu endpoint duoc scope ro.

## 3. Teacher Visibility

Teacher la role van hanh lop hoc, khong phai admin he thong.

| Cau hoi | Policy de xuat |
|---|---|
| Teacher duoc xem tat ca student khong? | Khong. Chi xem student thuoc course section/session minh phu trach. |
| Teacher duoc xem alert cua session nao? | Chi session minh phu trach. |
| Teacher duoc export report nao? | Chi report cua class/session minh phu trach. |
| Teacher duoc xem media/capture nao? | Chi media lien quan session minh phu trach, qua endpoint authenticated. |
| Teacher duoc xem enrollment nao? | Chi enrollment cua section/session minh phu trach. |

Teacher co the xem:

- Sessions do minh tao hoac thuoc course section minh phu trach.
- Roster cua course section/session minh phu trach.
- Attendance va alerts cua session minh phu trach.
- Reports/export cua class/session minh phu trach.

Teacher khong nen duoc xem:

- User management, audit logs toan he thong.
- Student toan truong/lop khong phu trach.
- Model evaluation data admin-only.

## 4. Route Policy De Xuat

| Route | Current style | Policy de xuat |
|---|---|---|
| `GET /students/` | Authenticated broad read | `admin`: all. `teacher`: only students in owned sections/sessions. `student`: deny or return self only via separate `/students/me`. |
| `GET /attendance/session/{session_id}` | Authenticated broad read | `admin`: all. `teacher`: owned session. `student`: only own record if enrolled. |
| `GET /attendance/summary/{class_name}` | Authenticated broad read | `admin`: all. `teacher`: class with owned sessions/sections. `student`: deny; use personal summary endpoint if needed. |
| `GET /alerts/session/{session_id}` | Authenticated broad read | `admin`: all. `teacher`: owned session. `student`: deny. |
| `GET /alerts/session/{session_id}/active` | Authenticated broad read | `admin`: all. `teacher`: owned session. `student`: deny. |
| `GET /course-sections/{section_id}/students` | Authenticated broad read | `admin`: all. `teacher`: owned section. `student`: deny by default. |
| `GET /sessions/{session_id}/enrollments` | Authenticated broad read | `admin`: all. `teacher`: owned session. `student`: deny by default. |
| `GET /students/{student_id}/enrollments` | Authenticated broad read | `admin`: all. `teacher`: only if student is in owned section/session. `student`: only if `student_id` is self. |
| `GET /faces/student/{student_code}` | Authenticated broad read | `admin`: all. `teacher`: only students in owned section/session. `student`: only self. |

## 5. Route Priority

Tighten truoc cac route co du lieu nhay cam hoac co the leak du lieu sinh trac hoc:

1. `GET /alerts/session/{session_id}`
2. `GET /alerts/session/{session_id}/active`
3. `GET /attendance/session/{session_id}`
4. `GET /faces/student/{student_code}`
5. `GET /students/`
6. `GET /course-sections/{section_id}/students`
7. `GET /sessions/{session_id}/enrollments`
8. `GET /students/{student_id}/enrollments`
9. `GET /attendance/summary/{class_name}`

## 6. Migration Plan

### Buoc 1: Document Policy

- Hoan thanh tai lieu nay.
- Chot voi product owner cac cau hoi con mo:
  - Student co duoc xem roster lop khong?
  - Teacher scope dua tren `created_by`, `lecturer_name`, hay assignment table rieng?
  - Co can endpoint self-service moi cho student khong?

### Buoc 2: Add Tests

Them backend tests truoc khi sua behavior:

- Student khong xem duoc roster, alerts, attendance cua nguoi khac.
- Student chi xem duoc enrollment/face status cua minh.
- Teacher chi xem duoc session/class/section minh phu trach.
- Admin van xem duoc all.
- Unauthorized request tra `401`.
- Authenticated but out-of-scope request tra `403`.

Nen them test o cac nhom:

- `test_auth_rbac.py`
- `test_attendance_report_services.py`
- `test_alert_routes.py`
- `test_session_enrollment_routes.py`
- `test_student_routes.py`

### Buoc 3: Tighten Backend Scope

Them helper scope dung chung, tranh copy/paste logic:

- `user_owns_session(db, user, session_id)`
- `user_owns_section(db, user, section_id)`
- `student_is_self(db, user, student_id/student_code)`
- `require_session_read_access(db, user, session_id)`
- `require_student_read_access(db, user, student_id/student_code)`

Sau do ap dung vao routes theo priority o muc 5.

Khong thay doi response schema neu khong can. Neu student dang goi endpoint broad, uu tien:

- Tra `403` cho endpoint broad.
- Tao/giu endpoint self-specific rieng neu frontend can.

### Buoc 4: Adjust Frontend

Sau khi backend tighten:

- Hide menu/button ma role khong duoc dung.
- Dung endpoint self-specific cho student.
- Dung scoped endpoint cho teacher.
- Hien thi error 403 than thien.
- Cap nhat E2E smoke tests cho admin/teacher/student.

## 7. Risk Neu Khong Xu Ly

Neu tiep tuc de broad read access:

- Student co the xem danh sach sinh vien, roster, face status hoac attendance cua nguoi khac.
- Student co the xem security alerts cua session, co kha nang lo anh khuon mat/capture nhay cam.
- Teacher co the xem du lieu lop/session khong phu trach.
- Bao cao/export da duoc harden nhung API read JSON van co the leak du lieu tuong tu.
- Rui ro vi pham privacy, quy che bao ve du lieu sinh vien va du lieu sinh trac hoc.
- Khi them authenticated media endpoint, neu route metadata van broad thi van co the suy ra/lay du lieu nhay cam.

## 8. Routes Co The Giu Nguyen

Cac route sau co the giu policy hien tai neu khong co yeu cau moi:

- `GET /auth/me`: self profile.
- `GET /reports/dashboard/stats`: service da co logic theo role.
- `GET /reports/session/{session_id}`: service da co scope va student-only row.
- `GET /reports/summary/{class_name}` va `/warnings/{class_name}`: service da block student va scope teacher.
- CSV export session routes: da gioi han admin/teacher va scope theo session.
- Model evaluation routes: admin-only.
- Write/delete routes: tiep tuc dung `require_admin` hoac `require_role` nhu hien tai.

## 9. Non-Goals

- Khong implement code trong tai lieu nay.
- Khong thay doi API contract trong buoc document.
- Khong thay doi frontend trong buoc document.
- Khong giai quyet media static security truc tiep; media nen co policy rieng va phu thuoc read scope trong tai lieu nay.
