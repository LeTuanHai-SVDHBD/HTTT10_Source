# HTTT10 - Mã nguồn mốc B (0.2.0)

Mã nguồn FastAPI + ReactJS + SQLAlchemy + JWT + MySQL đã hoàn thành mốc A và B: xác thực, quản trị tài khoản/quyền, phòng ban, phòng họp, cấu hình giờ phục vụ/ngày nghỉ, phân công người duyệt, xem lịch theo quyền và tìm phòng trống. Nộp/duyệt lịch, tài liệu, SMTP và báo cáo sẽ được bổ sung ở mốc C–F.

**Đang chạy mốc A:** xem [hướng dẫn cập nhật và kiểm tra mốc B](docs/MocB_HuongDan.md). Giữ nguyên `.env`, tài khoản và volume hiện có; không bootstrap lại Admin hoặc xóa volume.

## 1. Chạy trên Windows bằng Docker Desktop

Giải nén vào thư mục mới, ví dụ `C:\Projects\HTTT10_Source`. Mở Docker Desktop với Linux containers, sau đó mở PowerShell tại thư mục có compose.yaml. Cần Python để sinh cấu hình cục bộ (không cần cài thư viện Python riêng cho bước này).

```powershell
py scripts\setup_env.py
docker compose up -d --build
docker compose ps
```

Script tạo `.env` chứa mật khẩu MySQL và khóa JWT ngẫu nhiên, không ghi đè file đã có. Khi chạy lại dự án, giữ nguyên `.env`; không xóa/tạo lại mật khẩu khi volume DB đã chứa dữ liệu. File `.env` được loại khỏi Git/gói source. Nếu đã có `.env` thì bỏ qua lệnh tạo và dùng file đó.

Stack gồm db, migrate (chạy xong thoát code 0 là bình thường), api và web. API đợi migration xong; web đợi API healthy. Lần đầu tải image/cài thư viện có thể lâu. Nếu chưa healthy:

```powershell
docker compose logs --tail 80 migrate api web
```

Không gửi `.env`, mật khẩu hoặc JWT khi nhờ kiểm tra lỗi.

## 2. Tạo Admin đầu tiên

Sau khi stack chạy, nhập lệnh:

```powershell
docker compose exec api python -m app.cli bootstrap
```

Chương trình hỏi email và mật khẩu tạm hai lần; mật khẩu không hiện khi gõ. Dùng mật khẩu 12-128 ký tự. Admin đầu tiên chỉ có ADMIN, không tự nhận quyền Nhân viên/Người duyệt. Nếu đã có Admin hoạt động, bootstrap từ chối tạo thêm.

Mở [trang đăng nhập trên máy này](http://localhost:8080). Nhập email/mật khẩu vừa tạo. Hệ thống yêu cầu đổi mật khẩu tạm; đổi xong đăng nhập lại bằng mật khẩu mới. Có thể xem hồ sơ, đổi mật khẩu tiếp hoặc đăng xuất.

Mật khẩu không được lưu dưới dạng văn bản: backend dùng Argon2id. JWT có thời hạn 30 phút; token chỉ giữ trong bộ nhớ trang, tải lại trang cần đăng nhập lại. Logout thu hồi phiên hiện tại; đổi mật khẩu thu hồi tất cả phiên. Khóa tài khoản hoặc đổi auth_version được kiểm tra lại ở server.

## 3. Kiểm tra API

Mở [Swagger trên máy này](http://localhost:8080/api/docs). Swagger hiện đúng 28 operation đã cài, gồm 6 thao tác nền bên dưới và 22 thao tác mốc B:

| API | Ý nghĩa |
|---|---|
| POST /api/v1/auth/login | Email/password JSON -> Bearer JWT |
| GET /api/v1/auth/me | Người dùng và quyền hiện hành |
| POST /api/v1/auth/logout | Thu hồi sid hiện tại, trả 204 |
| PUT /api/v1/auth/password | Đổi mật khẩu, thu hồi phiên, trả 204 |
| GET /api/v1/health/live | Process đang hoạt động |
| GET /api/v1/health/ready | MySQL và migration đã sẵn sàng |

Ở Swagger: gọi login, copy access_token vào Authorize (chỉ nhập token, không thêm Bearer nếu công cụ đã tự gắn), rồi gọi me/password/logout. Không dán token thật vào ảnh báo cáo. Hợp đồng `docs/target-openapi.yaml` gồm 50 operation mục tiêu; Swagger thực tế chỉ công bố 28 operation đã cài.

| Nhóm mốc B | Thao tác |
|---|---|
| /directory/users | Directory ACTIVE, chỉ UserRef, phân trang và tìm kiếm |
| /users, /users/{id}, /users/{id}/temporary-password | Admin cấp/sửa/khóa/đặt lại mật khẩu |
| /departments, /departments/{id} | Tra cứu; Admin thêm/sửa/ngừng nhận mới |
| /rooms, /rooms/{id} | Tra cứu; Admin thêm/sửa phòng và thiết bị |
| /rooms/{id}/policies | Admin xem lịch sử/thêm phiên bản cấu hình |
| /rooms/{id}/approvers, /departments/{id}/approvers | Admin xem/thay tập người duyệt theo phạm vi |
| /rooms/availability | Tìm phòng theo thời gian/sức chứa/thiết bị, không giữ chỗ |
| /calendar | Lịch hiệu lực, phân biệt DETAIL/BUSY_ONLY và đệm |

## 4. Demo LAN

Máy Windows chạy Docker và máy demo cùng mạng. Dùng `ipconfig` tìm IPv4 LAN của Windows. Trên máy còn lại mở `http://<IPv4-của-máy-Windows>:8080` (thay phần trong ngoặc bằng IP thật). Nếu bị firewall chặn, cho phép TCP 8080 ở mạng Private theo cấu hình máy của bạn.

Frontend dùng URL tương đối `/api/v1`, Nginx chuyển tiếp đến API, API kết nối host db:3306 trong Docker. Không hard-code localhost vào trình duyệt máy khác. Không publish cổng MySQL ra LAN. Đây là demo mạng nội bộ; khi triển khai ngoài môi trường demo cần cấu hình HTTPS.

## 5. CSDL và migration

Baseline SQL đã chốt được đưa vào Alembic revision 001_baseline, giữ 24 bảng và 3 view, kèm danh mục 2 phòng ban/2 phòng họp. Alembic thêm bảng kỹ thuật alembic_version: tổng số bảng vật lý sau migrate là 25, không phải thêm nghiệp vụ.

Compose mới tạo volume riêng của dự án; không trỏ vào CSDL dự án đấu giá sách hoặc SQL Server. Không mount lại SQL init từ gói MySQL cũ vào stack này, vì migrate đã chịu trách nhiệm tạo baseline. Không dùng Base.metadata.create_all để tạo song song cấu trúc khác.

Nếu bạn chủ động dùng CSDL baseline cũ đã có dữ liệu, phải sao lưu trước và cấu hình kết nối chính xác; chạy `python -m app.cli adopt-baseline` từ backend để kiểm tra tên cột, PK/UNIQUE/FK/CHECK và view trước khi stamp. Adoption không thay thế kiểm tra toàn bộ định nghĩa/type của mọi đối tượng và không dùng cho một DB bất kỳ có tên gần giống. Nếu cấu trúc khác, dừng để làm migration phù hợp; không xóa volume để sửa lỗi.

## 6. Cấu trúc mã nguồn

| Vị trí | Nội dung đã có |
|---|---|
| backend/app/main.py | Router auth/health, middleware request ID, lỗi đã lược input |
| backend/app/services.py | AuthService và transaction ghi lịch sử |
| backend/app/dependencies.py | Xác thực chung cho router auth và mốc B |
| backend/app/catalog_routes.py | 22 adapter HTTP mốc B, response DTO và phân quyền |
| backend/app/catalog.py | Service danh mục/quyền/cấu hình, calendar riêng tư và availability |
| backend/app/security.py | Argon2id, JWT HS256, expiry/issuer/audience |
| backend/app/models.py | ORM User/UserRole/AuthSession phục vụ mốc A |
| backend/app/db.py | Engine, Session riêng, READ COMMITTED và timezone UTC |
| backend/app/cli.py | Migration, adoption, bootstrap bằng prompt |
| backend/app/schemas.py | DTO từ hợp đồng; DTO cho auth, danh mục, calendar và tìm phòng |
| backend/db/ | SQL baseline và metadata đã thiết kế |
| backend/alembic/ | Migration 001 |
| backend/test_auth.py, backend/test_catalog.py | Integration FastAPI ASGI + MySQL thật, DB test riêng |
| frontend/src/ | Auth, api.js và workspace quản trị/lịch/tìm phòng, CSS responsive |
| frontend/package-lock.json | Khóa các phiên bản npm đã build |
| compose.yaml | DB/migrate/API/web, volume bền vững và healthcheck |
| verification/ | Bằng chứng kiểm tra và giới hạn |

ORM ở mốc A chỉ ánh xạ các bảng đang dùng, không có nghĩa các bảng còn lại bị bỏ khỏi DB. API dùng layer Service, không gửi model ORM/password hash ra client. Rate limit login hiện là bộ nhớ một process, tối đa 10 lượt/phút theo IP; khi mở rộng nhiều replica phải thay bằng cơ chế chia sẻ. Không dùng lockout toàn tài khoản để người khác dễ khóa hộ tài khoản.

## 7. Tái chạy kiểm tra

`backend/test_auth.py` tự tạo DB `httt10_auth_<mã>_test`, không xóa hoặc ghi vào DB httt10. Cần một tài khoản MySQL dành cho kiểm tra có quyền CREATE DATABASE và Python 3.12 đã cài backend/requirements.txt. Thiết lập MYSQL_TEST_HOST, MYSQL_TEST_PORT (mặc định 43307), MYSQL_TEST_USER và MYSQL_TEST_PASSWORD trên máy bạn rồi chạy từ thư mục backend:

```powershell
py test_auth.py
```

Không dùng tài khoản ứng dụng giới hạn schema httt10 để tạo DB test. Chạy thêm `py test_catalog.py` để kiểm tra mốc B. Kết quả ghi `verification/auth-result.json` và `verification/catalog-result.json`. Bộ kiểm chứng dùng FastAPI ASGI TestClient với MySQL thật; không thay cho kiểm thử trình duyệt đi xuyên Nginx/Docker/Windows.

Kiểm tra build frontend: vào frontend, chạy `npm ci`, rồi `npm run build`. Bản gửi đã build thành công; Docker Desktop Windows và LAN vẫn cần chạy thực tế theo hướng dẫn trên.

## 8. Mốc tiếp theo

Mốc B đã cài quản trị tài khoản/quyền/phòng ban/phòng họp/cấu hình, calendar và tìm phòng. Lịch mới cài A–B có thể trống vì chưa có nộp/duyệt lịch. Mốc C sẽ cài nộp/duyệt và chống đặt trùng bằng transaction/khóa phòng/người. Bộ test B dùng fixture lịch trong DB test riêng để kiểm tra truy vấn và bảo vệ cấu hình; chưa chứng minh luồng duyệt của mốc C. Xem [kết quả kiểm tra mốc B](verification/KetQuaKiemTraMocB.md).
