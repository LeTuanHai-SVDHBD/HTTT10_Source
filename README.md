# HTTT10 - Mã nguồn mốc C (0.3.0)

Mã nguồn FastAPI + ReactJS + SQLAlchemy + JWT + MySQL đã hoàn thành mốc A–C: xác thực, quản trị tài khoản/quyền, phòng ban, phòng họp, cấu hình giờ phục vụ/ngày nghỉ, phân công người duyệt, xem lịch theo quyền, tìm phòng trống, gửi/duyệt/từ chối/rút yêu cầu tạo lịch và tự hết hạn. Sửa/hủy lịch đã duyệt, tài liệu, SMTP và báo cáo sẽ được bổ sung ở các mốc tiếp theo.

**Đang chạy mốc A/B:** xem [hướng dẫn cập nhật và kiểm tra mốc C](docs/MocC_HuongDan.md). Giữ nguyên `.env`, tài khoản và volume hiện có; không bootstrap lại Admin hoặc xóa volume.

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

Mở [Swagger trên máy này](http://localhost:8080/api/docs). Swagger hiện đúng 40 operation đã cài: 6 nền mốc A, 22 mốc B và 12 mốc C:

| API | Ý nghĩa |
|---|---|
| POST /api/v1/auth/login | Email/password JSON -> Bearer JWT |
| GET /api/v1/auth/me | Người dùng và quyền hiện hành |
| POST /api/v1/auth/logout | Thu hồi sid hiện tại, trả 204 |
| PUT /api/v1/auth/password | Đổi mật khẩu, thu hồi phiên, trả 204 |
| GET /api/v1/health/live | Process đang hoạt động |
| GET /api/v1/health/ready | MySQL và migration đã sẵn sàng |

Ở Swagger: gọi login, copy access_token vào Authorize (chỉ nhập token, không thêm Bearer nếu công cụ đã tự gắn), rồi gọi me/password/logout. Không dán token thật vào ảnh báo cáo. Hợp đồng `docs/target-openapi.yaml` gồm 50 operation mục tiêu; Swagger thực tế chỉ công bố 40 operation đã cài.

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

| Nhóm mốc C | Thao tác |
|---|---|
| POST /availability/check | Kiểm tra phương án đầy đủ, không giữ chỗ |
| POST /meeting-proposals, /work-proposals | Lưu yêu cầu CREATE chờ duyệt |
| GET /proposals, /proposals/{id} | Hộp yêu cầu và chi tiết theo quyền |
| POST /proposals/{id}/decisions | Người duyệt đúng phạm vi chấp thuận/từ chối |
| POST /proposals/{id}/withdrawals | Người gửi rút yêu cầu còn chờ |
| GET /schedules, /schedules/{id} | Hồ sơ lịch liên quan hoặc bận/rảnh |
| GET /schedules/{id}/revisions, /revisions/{revision_id} | Các bản lịch được xem |
| GET /schedules/{id}/audit | Lịch sử nghiệp vụ đã lọc quyền |

Command lịch bắt buộc `Idempotency-Key` 16–128 ký tự. Retry sau mất mạng giữ nguyên key và body; biên nhận CREATE chỉ xác nhận yêu cầu đã lưu, chưa phải đã giữ phòng. Hàng chờ email được lưu cùng giao dịch; chưa có SMTP gửi thư thật. Xem quy trình demo trong hướng dẫn mốc C.

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
| backend/app/scheduling.py | Service gửi/duyệt/rút, khóa tài nguyên, cảnh báo, chống lặp, tra cứu theo quyền |
| backend/app/scheduling_routes.py | 12 adapter API mốc C |
| backend/app/schedule_jobs.py | Lifespan quét yêu cầu hết hạn mỗi 30 giây |
| backend/app/catalog.py | Service danh mục/quyền/cấu hình, calendar riêng tư và availability |
| backend/app/security.py | Argon2id, JWT HS256, expiry/issuer/audience |
| backend/app/models.py | ORM User/UserRole/AuthSession phục vụ mốc A |
| backend/app/db.py | Engine, Session riêng, READ COMMITTED và timezone UTC |
| backend/app/cli.py | Migration, adoption, bootstrap và expire-proposals |
| backend/app/schemas.py | DTO từ hợp đồng; DTO cho auth, danh mục, calendar và tìm phòng |
| backend/db/ | SQL baseline và metadata đã thiết kế |
| backend/alembic/ | Migration 001 |
| backend/test_auth.py, backend/test_catalog.py, backend/test_scheduling.py | Integration FastAPI ASGI + MySQL thật, DB test riêng |
| frontend/src/ | Auth, workspace quản trị và scheduling.jsx gửi/duyệt/rút/tra cứu hồ sơ, CSS responsive |
| frontend/package-lock.json | Khóa các phiên bản npm đã build |
| compose.yaml | DB/migrate/API/web, volume bền vững và healthcheck |
| compose.test.yaml | Stack MySQL/tests tách biệt, không dùng volume website |
| verification/ | Bằng chứng kiểm tra và giới hạn |

ORM ở mốc A chỉ ánh xạ các bảng đang dùng, không có nghĩa các bảng còn lại bị bỏ khỏi DB. API dùng layer Service, không gửi model ORM/password hash ra client. Rate limit login hiện là bộ nhớ một process, tối đa 10 lượt/phút theo IP; khi mở rộng nhiều replica phải thay bằng cơ chế chia sẻ. Không dùng lockout toàn tài khoản để người khác dễ khóa hộ tài khoản.

## 7. Tái chạy kiểm tra

`backend/test_auth.py` tự tạo DB `httt10_auth_<mã>_test`, không xóa hoặc ghi vào DB httt10. Cần một tài khoản MySQL dành cho kiểm tra có quyền CREATE DATABASE và Python 3.12 đã cài backend/requirements.txt. Thiết lập MYSQL_TEST_HOST, MYSQL_TEST_PORT (mặc định 43307), MYSQL_TEST_USER và MYSQL_TEST_PASSWORD trên máy bạn rồi chạy từ thư mục backend:

```powershell
py test_auth.py
```

Không dùng tài khoản ứng dụng giới hạn schema httt10 để tạo DB test. Chạy thêm `py test_catalog.py`, `py test_scheduling.py` để kiểm tra mốc B/C. Kết quả ghi các file `*-result.json` trong `verification` (hoặc `TEST_RESULT_DIR` nếu đặt). Có thể chạy bằng Docker riêng, không cần cài PyMySQL vào Windows, theo hướng dẫn mốc C. Bộ kiểm chứng dùng FastAPI ASGI TestClient với MySQL thật; không thay cho kiểm thử trình duyệt đi xuyên Nginx/Docker/Windows.

Kiểm tra build frontend: vào frontend, chạy `npm ci`, rồi `npm run build`. Bản gửi đã build thành công; Docker Desktop Windows và LAN vẫn cần chạy thực tế theo hướng dẫn trên.

## 8. Mốc tiếp theo

Mốc C đã cài gửi và duyệt CREATE, từ chối/rút/hết hạn, phiên bản, cảnh báo và idempotency. Kiểm tra mốc C dùng API/transaction thật trên MySQL, gồm các kết nối duyệt cạnh tranh; không dùng fixture đã duyệt để thay cho luồng CREATE. Xem [kết quả mốc C](verification/KetQuaKiemTraMocC.md).

Mốc D tiếp theo sẽ cài sửa/hủy lịch đã duyệt: giữ bản cũ khi đề nghị sửa/hủy công tác chờ; đổi hiệu lực nhất quán khi duyệt bản sửa; hủy họp trực tiếp trước giờ bắt đầu. Tài liệu, SMTP thật và báo cáo tiếp tục ở các mốc sau.
