# Phase 1.5 Verification Plan

Tai lieu nay dinh nghia ke hoach xac minh sau Phase 1 Production Hardening cho Face Attendance System (FAS).
Pham vi Phase 1.5 la validate moi truong production-like, migration tren ban copy, thiet bi that, security smoke test va quy trinh du lieu nhay cam. Khong thay doi code hoac business logic trong qua trinh thuc hien checklist nay neu chua co issue duoc phan loai va phe duyet.

## 1. Muc Tieu Phase 1.5

- Xac nhan backend/frontend co the build va chay trong cau hinh production-like.
- Xac nhan Alembic migration an toan tren ban copy cua database hien huu.
- Xac nhan luong diem danh chinh thuc hoat dong voi camera, GPS, liveness va check-in/check-out tren thiet bi that.
- Xac nhan JWT/RBAC, audit log va route protection van dung sau deploy.
- Xac nhan khong dua secret, file `.env`, database local, anh khuon mat that hoac artifact rieng tu vao repo.
- Ghi nhan ro pass/fail, bang chung test va rui ro con lai truoc khi chuyen Phase 2.

## 2. Checklist Docker Production Verification

- [ ] Tao file `.env.prod` tu `.env.prod.example` tren may deploy/test, khong commit file nay.
- [ ] Dat cac bien bat buoc:
  - `POSTGRES_DB`
  - `POSTGRES_USER`
  - `POSTGRES_PASSWORD`
  - `DATABASE_URL`
  - `SECRET_KEY`
  - `JWT_EXPIRE_MINUTES`
  - `CORS_ORIGINS`
  - `AUTH_BOOTSTRAP_ADMIN_USERNAME`
  - `AUTH_BOOTSTRAP_ADMIN_PASSWORD`
  - `VITE_API_BASE_URL`
- [ ] Xac minh `SECRET_KEY`, `POSTGRES_PASSWORD`, `AUTH_BOOTSTRAP_ADMIN_PASSWORD` khong con gia tri placeholder.
- [ ] Chay validate compose config tren moi truong co Docker, khong build:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml config
```

- [ ] Build image production tren moi truong verification duoc phep build:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml build
```

- [ ] Start PostgreSQL, chay migration, sau do start backend/frontend theo README production deploy.
- [ ] Xac minh backend container dung Gunicorn voi Uvicorn worker, khong dung `uvicorn --reload`.
- [ ] Xac minh frontend duoc build bang Vite va serve static qua Nginx.
- [ ] Kiem tra health endpoint backend:

```text
GET /health
```

- [ ] Kiem tra frontend truy cap duoc public URL va goi dung `VITE_API_BASE_URL`.
- [ ] Kiem tra CORS chi cho phep origin production da cau hinh.
- [ ] Kiem tra volume `backend_media` va `postgres_data` duoc mount dung.
- [ ] Kiem tra restart container khong mat du lieu PostgreSQL va media.

## 3. Checklist Alembic Migration Verification Tren DB Copy

- [ ] Tao backup database hien huu truoc moi thao tac.
- [ ] Restore backup vao database test/staging rieng, khong thao tac truc tiep tren production.
- [ ] Ghi lai schema version hien tai, so bang, so row cac bang chinh:
  - `students`
  - `face_embeddings`
  - `sessions`
  - `attendance`
  - `users`
  - `audit_logs`
  - `classrooms`
  - `subjects`
  - `course_sections`
  - `enrollments`
  - `security_alerts`
- [ ] Neu DB copy da co schema tu code hien tai nhung chua co Alembic version, chay:

```bash
alembic -c alembic.ini stamp 0001_current_schema_with_audit
alembic -c alembic.ini upgrade head
```

- [ ] Neu DB copy moi hoan toan, chay:

```bash
alembic -c alembic.ini upgrade head
```

- [ ] Xac minh `alembic_version` o head revision.
- [ ] Xac minh app startup khong tao/sua schema tu dong:
  - Khong goi `Base.metadata.create_all` trong startup.
  - Khong goi `sync_schema(engine)` trong startup.
- [ ] Xac minh cac constraint quan trong:
  - users role chi gom `admin`, `teacher`, `student`.
  - attendance unique theo `student_id + session_id` neu schema ho tro.
  - enrollment unique theo session/section va student.
- [ ] Chay backend pytest voi DB test neu pipeline staging ho tro.
- [ ] Smoke test login, list dashboard, tao session, dang ky mat, check-in/check-out tren DB copy.
- [ ] So sanh row count truoc/sau voi cac bang khong du kien bi thay doi.
- [ ] Ghi lai bat ky data fix nao can lam truoc production migration.

## 4. Checklist Real-Device Test

### Camera

- [ ] Trinh duyet xin quyen camera dung cach.
- [ ] Camera laptop/desktop hoat dong voi HTTPS hoac localhost.
- [ ] Camera mobile hoat dong tren Chrome/Edge/Safari muc tieu.
- [ ] Anh chup dang ky khuon mat du sang, khong bi xoay sai huong.
- [ ] Dang ky khuon mat yeu cau toi thieu 5 mau hop le.
- [ ] Anh khong co mat hoac mat qua mo bi reject dung cach.

### GPS

- [ ] Trinh duyet xin quyen GPS dung cach.
- [ ] Check-in bi chan khi khong cap quyen GPS.
- [ ] Check-in pass khi o trong ban kinh lop hoc.
- [ ] Check-in bi chan khi ngoai ban kinh lop hoc.
- [ ] GPS accuracy duoc hien thi/ghi nhan de debug.
- [ ] Test tren it nhat 1 laptop va 1 mobile device.

### Liveness

- [ ] Mat that pass liveness trong dieu kien anh sang binh thuong.
- [ ] Anh chup man hinh/anh in bi chan la spoof neu model ho tro.
- [ ] Anh qua toi/qua mo duoc reject hoac canh bao dung.
- [ ] Liveness score va label duoc tra ve/ghi nhan de audit/debug.
- [ ] Khong ghi attendance chinh thuc khi liveness fail.

### Multi-Face Overlay

- [ ] Recognition hien overlay dung khi co 1 khuon mat.
- [ ] Anh co nhieu khuon mat duoc hien thi/phan loai dung theo luong hien co.
- [ ] Model-test reject multi-face neu route/flow yeu cau.
- [ ] Overlay khong che UI quan trong tren desktop va mobile.
- [ ] Bounding box khop vi tri khuon mat trong cac kich thuoc viewport chinh.

### Check-in / Check-out

- [ ] Student hop le, da dang ky mat, dung lop/session co the check-in.
- [ ] Student khong thuoc enrollment bi chan va tao security alert neu flow hien co quy dinh.
- [ ] Demo/Kaggle/LFW sample khong duoc ghi attendance chinh thuc.
- [ ] Check-in lap lai khong tao record trung.
- [ ] Check-out sau check-in cap nhat dung record.
- [ ] Check-out lap lai khong tao record moi.
- [ ] Late/present tinh dung theo cua so thoi gian hien tai.
- [ ] Bao cao session hien thi ca present, late, chua check-out va absent dung.

## 5. Checklist Security Smoke Test

### 401 / 403

- [ ] Khong token truy cap route private tra 401.
- [ ] Token sai/het han tra 401.
- [ ] User inactive tra 401.
- [ ] Role khong du quyen tra 403.
- [ ] Frontend logout local state khi API tra 401.

### Role Admin / Teacher / Student

- [ ] Admin truy cap duoc user management, audit logs, students, sessions, course management, face register, attendance, reports.
- [ ] Teacher khong truy cap user management/audit logs/students create-delete neu backend yeu cau admin.
- [ ] Teacher truy cap duoc sessions/course management/face register neu route backend cho phep.
- [ ] Student chi thay menu phu hop va khong truy cap duoc admin/teacher routes.
- [ ] Student chi check-in/check-out cho chinh student profile cua minh.
- [ ] Legacy role `lecturer/viewer` bi reject hoac duoc normalize qua migration compatibility.

### Audit Log

- [ ] Login success ghi audit log.
- [ ] Login fail ghi audit log.
- [ ] User create/update role/status ghi audit log.
- [ ] Student create/update/delete ghi audit log.
- [ ] Session create/update/delete ghi audit log.
- [ ] Face registration ghi audit log.
- [ ] Attendance check-in/check-out/delete ghi audit log.
- [ ] Classroom/subject/course_section/enrollment changes ghi audit log.
- [ ] Security alert dismiss ghi audit log.
- [ ] Audit details co `old_value`, `new_value`, `ip_address`, `user_agent` khi lay duoc.
- [ ] Teacher/student khong doc duoc `/auth/audit-logs`.

## 6. Checklist Du Lieu Nhay Cam

- [ ] `git status --short` sach truoc release.
- [ ] `git ls-files` khong co `.env`, `.env.prod`, `backend/.env`, `frontend/.env`.
- [ ] Repo khong track local DB: `*.db`, `*.sqlite`, `*.sqlite3`.
- [ ] Repo khong track `backend/media/`, `backend/uploads/`, `backend/enrollment_data/`, `backend/evaluation_data/`.
- [ ] Repo khong track embedding pickle production hoac face data that.
- [ ] File docs/README khong chua secret that, chi co placeholder.
- [ ] Backup DB duoc ma hoa va luu ngoai repo.
- [ ] Restore DB da duoc test tren staging.
- [ ] Co quy trinh xoa/retention du lieu biometric theo yeu cau nha truong/phap ly.
- [ ] Media capture trong production co quyen truy cap phu hop va khong public ngoai nhu cau ung dung.

## 7. Tieu Chi Pass / Fail

### Pass

- Docker production config validate thanh cong va build/run thanh cong trong moi truong verification.
- Alembic migration chay thanh cong tren DB copy va app startup khong sua schema tu dong.
- Backend health, frontend load, login va route private hoat dong dung.
- Real-device check-in/check-out pass voi camera + GPS + liveness trong dieu kien test.
- Security smoke test pass cho 401/403 va role admin/teacher/student.
- Audit log du cac action nhay cam da liet ke.
- Khong co secret/face data/private DB/artifact bi track trong Git.

### Fail

- Bat ky secret that nao bi track trong Git.
- Migration lam mat du lieu, sai schema hoac khong rollback/restore duoc tren DB copy.
- Production Docker image khong build/run duoc.
- App startup tu dong tao/sua schema bang `create_all` hoac `schema_sync`.
- Student sai role co the diem danh thay nguoi khac.
- Check-in/cham cong chinh thuc duoc ghi khi liveness fail hoac sample demo/Kaggle/LFW.
- Audit log thieu cho action nhay cam bat buoc.

## 8. Rui Ro Con Lai

- Do chinh xac face recognition phu thuoc dieu kien anh sang, camera, goc mat va chat luong mau dang ky.
- GPS tren browser/mobile co the sai so lon trong nha hoac khi nguoi dung tu choi quyen.
- Liveness co the can tinh chinh threshold sau test thiet bi that.
- Docker build/run production chua duoc bao dam neu chi review file ma chua test tren host thuc.
- Migration production van can maintenance window, backup va ke hoach rollback.
- Audit log hien chua append-only/tamper-evident o muc database policy.
- Tai lieu privacy/legal cho du lieu sinh trac hoc can hoan thien truoc khi van hanh rong.
- Multi-tenant, billing, HA, centralized logging va monitoring chua thuoc Phase 1.

## 9. Thu Tu Thuc Hien Khuyen Nghi

1. Freeze commit Phase 1 va xac nhan worktree sach.
2. Chuan bi `.env.prod` tren staging/verification host, khong commit.
3. Validate Docker compose config.
4. Tao backup production-like DB va restore sang DB copy.
5. Chay Alembic migration tren DB copy, ghi log ket qua.
6. Build va run Docker production stack tren staging.
7. Chay backend pytest va frontend build/E2E neu staging pipeline ho tro.
8. Thuc hien security smoke test 401/403/RBAC/audit.
9. Thuc hien real-device test camera/GPS/liveness/multi-face/check-in/check-out.
10. Review du lieu nhay cam, backup/restore va quyen truy cap media.
11. Tong hop defect, phan loai Blocker/High/Medium/Low.
12. Chi approve Phase 2 khi khong con Blocker/High va tat ca pass criteria bat buoc dat.

## 10. Ghi Chu Pham Vi

Tai lieu nay chi la ke hoach verification. Khong yeu cau thay doi code, business logic, Dockerfile, compose file, migration hay frontend UI trong khi tao/cap nhat tai lieu nay.
