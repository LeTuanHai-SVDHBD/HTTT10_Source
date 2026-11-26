# HTTT10 — Hệ thống lịch công tác và đặt phòng họp

**Phiên bản source 1.0.0 · Nhánh `dev` · Cập nhật 15/11/2026.** FastAPI, ReactJS, SQLAlchemy, JWT và MySQL.

Đã triển khai đủ 50 thao tác API trong hợp đồng mục tiêu: tài khoản/quyền, danh mục/phân công, xem lịch và tìm phòng, gửi/duyệt/từ chối/rút/sửa/hủy lịch, tài liệu theo phiên bản, worker email SMTP và báo cáo đặt phòng. Source dùng chung một schema, một stack Compose và một bộ tài liệu này. Các hướng dẫn/kết quả theo mốc cũ đã được hợp nhất; quyết định nghiệp vụ và Use Case được giữ tại phụ lục.

**Trạng thái nghiệm thu:** mã nguồn và kiểm tra tự động đã hoàn tất trong phạm vi nêu dưới đây. Chưa xác nhận chạy thực tế Docker Desktop Windows/Nginx, trình duyệt thật, LAN hai máy hoặc nhận email ở hộp thư ngoài. Làm phần kiểm thử thủ công để nghiệm thu môi trường của bạn; không đồng nhất kết quả test thành phần với việc triển khai đã thành công.

## Mục lục

1. [Cài lần đầu trên Windows](#setup)
2. [Cập nhật source đang chạy](#update)
3. [Tài khoản, phân quyền và dữ liệu demo](#accounts)
4. [Hướng dẫn sử dụng theo chức năng](#usage)
5. [Cấu hình và kiểm tra email](#email)
6. [Báo cáo sử dụng phòng](#reports)
7. [Chạy kiểm thử tự động](#automated-tests)
8. [Kiểm thử thủ công và chụp bằng chứng](#manual-tests)
9. [Cấu trúc source, API và CSDL](#source)
10. [Vận hành và xử lý lỗi](#operations)
11. [Kết quả kiểm chứng tổng hợp](#verification)
12. [Phụ lục đặc tả nghiệp vụ, phân quyền và Use Case](#business)

<a id="setup"></a>
## 1. Cài lần đầu trên Windows

Cần Git, Python 3.12 để chạy script sinh cấu hình, và Docker Desktop đang chạy **Linux containers**. Không cần cài MySQL, Node.js hoặc thư viện Python trực tiếp vào Windows khi dùng Docker.

Nếu chưa có source, mở PowerShell:

```powershell
git clone --branch dev --single-branch https://github.com/LeTuanHai-SVDHBD/HTTT10_Source.git
cd HTTT10_Source
py scripts\setup_env.py
docker compose up -d --build
docker compose ps -a
```

Nếu đã có source/dữ liệu từ trước, dùng phần **Cập nhật**, không tạo lại cấu hình hay Admin.

Script `setup_env.py` tạo `.env` chứa mật khẩu MySQL và khóa JWT ngẫu nhiên; không ghi đè file đã có. Không đưa `.env`, mật khẩu hoặc JWT lên GitHub. Stack chính gồm:

| Service | Nhiệm vụ | Trạng thái bình thường |
|---|---|---|
| `db` | MySQL 8.4, dữ liệu trong volume `mysql_data` | Up, healthy |
| `migrate` | Alembic tạo/kiểm tra baseline và danh mục ban đầu | **Exited (0)** sau khi xong |
| `api` | FastAPI và quét yêu cầu hết hạn mỗi 30 giây | Up, healthy |
| `worker` | Đọc outbox, gửi SMTP/thử lại khi đã cấu hình | Up; mặc định báo SMTP disabled |
| `web` | React build, Nginx chuyển tiếp `/api/v1` đến API | Up, cổng 8080 |

`migrate` là công việc chạy một lần rồi kết thúc. **Exited (0) không phải lỗi hoặc dấu hiệu dự án chưa hoàn thiện.** API chỉ khởi động sau khi migration thành công.

Mở [website](http://localhost:8080) và [Swagger](http://localhost:8080/api/docs). Tạo Admin **chỉ ở lần cài đầu**:

```powershell
docker compose exec api python -m app.cli bootstrap
```

Nhập email, mật khẩu tạm 12–128 ký tự và nhập lại. Mật khẩu không hiện khi gõ. Đăng nhập website, đổi mật khẩu tạm rồi đăng nhập lại. Nếu đã có Admin hoạt động, bootstrap từ chối tạo thêm.

Nếu dịch vụ chưa sẵn sàng:

```powershell
docker compose logs --tail 100 db migrate api worker web
```

<a id="update"></a>
## 2. Cập nhật source đang chạy

Mở PowerShell **đúng thư mục Compose cũ** có `.env` và chạy:

```powershell
git status
git switch dev
git pull --ff-only origin dev
docker compose up -d --build
docker compose ps -a
```

Giữ `.env`, tài khoản và các volume `mysql_data`, `document_data`. Không bootstrap lại. Không dùng `docker compose down -v` cho stack website. Mở website, `Ctrl+F5`, đăng nhập bằng tài khoản cũ.

Nếu Git báo chỉnh sửa cục bộ, lưu/đối chiếu trước khi pull; không dùng `reset --hard` để bỏ qua. Source 1.0.0 không đổi schema nghiệp vụ so với baseline: không cần xóa hoặc tạo lại DB.

**Nếu thư mục cũ từ ZIP và chưa có Git:** clone nhánh `dev` vào thư mục tạm, sao chép source mới vào thư mục Compose đang sử dụng, giữ `.env` và tên dự án Compose. Không chạy ngay từ thư mục mới vì Docker có thể tạo volume mới khiến bạn tưởng tài khoản cũ bị mất. Dùng `docker compose ls` để kiểm tra tên stack đang có. Source cũ không còn các `.md` theo mốc; sau khi đối chiếu, dùng bộ tài liệu thống nhất `README.md` này.

<a id="accounts"></a>
## 3. Tài khoản, phân quyền và dữ liệu demo

Admin đầu tiên chỉ có quyền **Quản trị viên**, không tự có Nhân viên/Người phê duyệt hoặc quyền xem nội dung lịch riêng.

Để kiểm thử, Admin vào **Tài khoản → Cấp tài khoản**, tạo các tài khoản sau; tự đặt mật khẩu tạm rồi đăng nhập từng tài khoản để đổi mật khẩu. Các địa chỉ dưới đây chỉ là dữ liệu demo, không phải thông tin đăng nhập có sẵn.

| Tài khoản gợi ý | Email demo | Phòng ban | Vai trò | Phân công |
|---|---|---|---|---|
| Admin | Email đã bootstrap | HC | Quản trị viên | Quản trị danh mục; xem báo cáo tổng hợp |
| Nhân viên A | `a@example.com` | HC | Nhân viên | Tạo và quản lý lịch của mình |
| Nhân viên B | `b@example.com` | HC | Nhân viên | Người tham gia cũ, kiểm tra lịch bận |
| Nhân viên C | `c@example.com` | HC | Nhân viên | Người tham gia mới khi thử sửa lịch |
| Người duyệt P1 | `p1@example.com` | HC | Người phê duyệt | Phòng A101 và phòng ban HC |
| Người duyệt P2 | `p2@example.com` | HC | Người phê duyệt | Phòng B201 và phòng ban HC |

Phân công ở **Phòng họp → Người duyệt** và **Phòng ban → Người duyệt**. Cần vai trò Người phê duyệt **và** phạm vi; chỉ có vai trò chưa đủ. Nếu P1/P2 cũng tạo yêu cầu, cấp thêm Nhân viên và cần một người khác duyệt thay. Không tự duyệt/từ chối yêu cầu của mình.

Dùng cửa sổ riêng tư hoặc trình duyệt khác cho người tạo/người duyệt trên cùng máy. Các tab cùng dùng một địa chỉ website sẽ dùng chung cookie phiên. F5 giữ đăng nhập khi phiên còn hợp lệ. Đăng xuất thu hồi phiên hiện tại. Đổi mật khẩu thu hồi mọi phiên. Đổi vai trò/trạng thái/email/phòng ban cũng thu hồi phiên. Chỉ đổi tên/mã nhân viên không thu hồi phiên. Admin không thể khóa hoặc gỡ quyền của Admin hoạt động cuối cùng.

Thời hạn mặc định là 30 phút kể từ lúc đăng nhập. Khi test local hoặc LAN, thêm `ACCESS_TOKEN_MINUTES=480` vào `.env` trên máy chạy Compose để đặt phiên mới thành 8 giờ. Nếu stack đang chạy, dùng `docker compose up -d` để nạp cấu hình và `docker compose restart web` để Nginx kết nối lại với API. Đăng xuất và đăng nhập lại trên mỗi trình duyệt cần test. Giá trị hợp lệ từ 1 đến 1440 phút.

Danh mục ban đầu có phòng ban HC/KT, phòng A101/B201. Giờ phục vụ: thứ Hai–thứ Sáu, 08:00–12:00 và 13:00–17:00, đệm 15 phút sau họp. Lịch còn trống sau cài mới là bình thường: cần gửi và duyệt yêu cầu để tạo lịch có hiệu lực.

<a id="usage"></a>
## 4. Hướng dẫn sử dụng theo chức năng

### 4.1. Danh mục và cấu hình

Admin dùng **Tài khoản**, **Phòng ban**, **Phòng họp** để cấp/sửa/ngừng nhận mới và phân công. Phòng họp có thiết bị, sức chứa, đệm, giờ phục vụ theo tuần và ngày ngoại lệ. Cấu hình giờ được thêm thành phiên bản có ngày hiệu lực; không ghi đè lịch sử.

Ngừng nhận mới không tự hủy lịch đã duyệt. Cấu hình mới bị từ chối nếu làm lịch tương lai đã xác nhận vượt sức chứa, nằm ngoài giờ hoặc chồng lịch do tăng đệm. Khi dữ liệu đã bị người khác sửa, tải trạng thái mới, đọc lại rồi chủ động thao tác; không gửi lại nội dung cũ bằng phiên bản mới để ghi đè.

### 4.2. Xem lịch và tìm phòng

**Lịch công tác:** chọn khoảng ngày/giờ, phòng và/hoặc người → **Xem lịch**. Bộ lọc kết hợp AND; muốn xem toàn bộ lịch của phòng, chọn **Không lọc người**. Không lọc phòng/người mặc định là lịch cá nhân. Tối đa 93 ngày/lượt.

Chỉ bản lịch hiện tại đã xác nhận, chưa hủy tạo bận. Người tạo/người tham gia/người duyệt đúng phạm vi xem nội dung; người khác chỉ nhận bận/rảnh. API bận/rảnh không trả ID lịch/bản lịch, tiêu đề hay thành phần. Đệm là khoảng riêng khi xem phòng, không tạo bận cho người.

**Tìm phòng trống:** nhập thời gian, số người gồm cả tùy chọn, thiết bị cần có → **Tìm phòng**. Kết quả không giữ chỗ; kiểm tra lại lúc gửi và duyệt. Yêu cầu chờ cùng giờ chỉ tạo cảnh báo, chưa giữ phòng.

Ô ngày/giờ nhập theo múi giờ máy mở trình duyệt; kết quả và giờ phục vụ theo Việt Nam. Đặt múi giờ Windows UTC+07:00 để demo thuận tiện.

### 4.3. Gửi, duyệt, từ chối và rút

1. Nhân viên A → **Tạo yêu cầu lịch** → Họp tại phòng nội bộ.
2. Nhập tiêu đề, mục đích, ngày làm việc tương lai 09:00–10:00, phòng A101, chủ trì và thành phần bắt buộc/tùy chọn.
3. Chọn **Kiểm tra phương án**, xử lý xung đột, xác nhận cảnh báo nếu có → **Gửi yêu cầu chờ duyệt**.
4. P1 → **Chờ tôi duyệt → Xem chi tiết** → **Duyệt và xác nhận lịch**; hoặc nhập lý do và **Từ chối**.
5. A theo dõi ở **Yêu cầu của tôi**, đổi bộ lọc trạng thái để tìm hồ sơ đã xử lý. **Hồ sơ lịch** cho xem bản hiệu lực và lịch sử.

Họp dài 15 phút–4 giờ, gửi trước ít nhất 30 phút và trong 90 ngày tới, nằm trọn một khoảng phục vụ. Chủ trì phải là người tham gia bắt buộc. Sức chứa tính cả người tùy chọn. Lúc duyệt chỉ cần còn trước giờ bắt đầu; không bắt người duyệt phải xử lý trước 30 phút.

Công tác cá nhân/nhóm dùng khoảng thời gian gồm di chuyển, địa điểm và thành viên cùng phòng ban người gửi. Có thể qua đêm/nhiều ngày; tất cả thành viên bắt buộc; không áp giờ phục vụ phòng hay giới hạn 4 giờ. Công tác cần người phụ trách phòng ban duyệt.

| Trạng thái/thao tác | Hiệu lực |
|---|---|
| CREATE đang chờ | Chưa giữ phòng/người |
| CREATE được duyệt | Tạo lịch có hiệu lực |
| Từ chối/rút/hết hạn CREATE | Không tạo bận |
| Người gửi rút yêu cầu còn chờ, chưa đến hạn | Lưu rút và giữ lịch sử |
| Phòng hoặc hai người bắt buộc đã bận | Chặn gửi/duyệt xung đột |
| Ít nhất một bên là người tùy chọn | Cảnh báo và cần xác nhận |

Cảnh báo có token xác nhận 5 phút gắn đúng người/phương án/tập cảnh báo; không giữ chỗ. Một ý định gửi/duyệt/rút/sửa/hủy giữ nguyên `Idempotency-Key` khi retry; sau mất phản hồi, chọn **Thử lại cùng thao tác**. Không tự tạo lại với key mới khi chưa đối chiếu hồ sơ. Key có hạn 24 giờ. Tải lại trang hoặc đăng xuất làm mất ý định trong bộ nhớ. Mở hồ sơ để kiểm tra trước khi tạo lại.

### 4.4. Sửa và hủy lịch

**Sửa:** người tạo → **Hồ sơ lịch → Xem chi tiết → Đề nghị sửa lịch** → sửa phương án → kiểm tra → gửi. Lịch gốc vẫn có hiệu lực trong khi chờ. Đổi từ A101 sang B201 do người phụ trách B201 duyệt. Duyệt thành công mới chuyển hiệu lực nguyên tử; từ chối/rút/hết hạn hoặc thua tranh chỗ mới đều giữ lịch gốc.

Mỗi lịch tối đa một đề nghị sửa/hủy chờ; muốn thay nội dung thì rút và gửi bản mới. Không đổi loại họp/công tác hoặc phòng ban của công tác. Người chỉ có quyền bản mới chỉ được thông tin gốc tối thiểu để so sánh, không tự thấy nội dung/thành phần riêng của bản cũ.

**Hủy họp:** người tạo hủy trực tiếp trước giờ bắt đầu, nhập lý do; giải phóng phòng/đệm/người và vô hiệu bản sửa chờ trong cùng giao dịch. Người tham gia/Admin không tự có quyền hủy hộ. Hủy không tạo proposal giả; `proposal_id=null` là đúng.

**Hủy công tác:** người tạo gửi đề nghị, người phụ trách phòng ban duyệt. Trong lúc chờ/từ chối/rút/hết hạn, lịch gốc vẫn tạo bận. `candidate=null` ở đề nghị CANCEL là đúng, vì dùng bản lịch gốc.

API quét hết hạn mỗi 30 giây. CREATE hết hạn lúc bắt đầu phương án; CHANGE lấy mốc sớm hơn giữa giờ bắt đầu gốc và mới; CANCEL công tác lấy giờ bắt đầu gốc. Duyệt/rút tới hạn có thể lưu EXPIRED rồi trả 409 với `expiration_committed=true`.

### 4.5. Tài liệu họp

Người tạo mở hồ sơ hoặc yêu cầu họp CREATE/CHANGE đang chờ → **Tài liệu họp**:

1. Chọn tạo tài liệu mới, nhập tên, chọn tệp → **Lưu tài liệu**.
2. Thay tệp: chọn **Phiên bản mới: [tên]**, chọn tệp và lưu. Phiên bản cũ giữ nguyên.
3. **Tải xuống v…** tải đúng phiên bản qua Bearer của phiên đăng nhập, không có URL tệp công khai.
4. **Ẩn tài liệu** yêu cầu lý do; **Hiện tài liệu đã ẩn** cho tra cứu/tải lịch sử trong quyền. Tệp đã ẩn không nhận phiên bản mới; chưa có khôi phục/xóa vật lý qua API.

Nhận PDF, DOCX, PPTX, XLSX, JPG, JPEG, PNG; 1 byte–20 MiB/tệp. Kiểm tra nội dung, cấu trúc ZIP/XML và giới hạn ảnh/giải nén, không chỉ tin MIME/phần mở rộng. Tệp hỏng, VBA, ZIP mã hóa/quá giới hạn bị từ chối. Chưa tích hợp antivirus hoặc xác minh mở mọi biến thể Office thực tế.

Cho bổ sung biên bản vào bản hiện tại sau cuộc họp. Bản cũ đã thay thế, yêu cầu rút/từ chối/hết hạn, lịch hủy chỉ đọc. Người tạo quản lý; người tham gia/người duyệt đọc theo **từng bản lịch gắn tệp**. Đổi phòng/người không tự chuyển quyền tệp cũ sang bản mới; tên tài liệu gốc cũng không được lộ cho người chỉ thấy bản mới.

Chọn **Xem tài liệu các bản lịch được phép** để tìm tài liệu cũ và thêm phiên bản vào ngữ cảnh hiện tại. Bộ lọc giấu phiên bản mới nhất thì không hiện thao tác thay/ẩn; bật xem các bản lịch để đối chiếu latest trước khi ghi. Nếu latest thuộc ngữ cảnh chỉ đọc thì không ẩn từ ngữ cảnh đó.

Upload không có idempotency. Mất phản hồi sau lưu: **Tải lại tài liệu**, đối chiếu trước khi gửi lại. Cập nhật cạnh tranh trả 409 nếu `expected_latest_version_id` cũ. Ghi tài liệu không đổi phòng/thành phần/`row_version` lịch và không cần duyệt lại đặt phòng.

<a id="email"></a>
## 5. Cấu hình và kiểm tra email

Mặc định `SMTP_ENABLED=false`: API vẫn lưu outbox cùng giao dịch; worker không gửi thư cho tới khi cấu hình. Lỗi email không làm rollback hoặc khôi phục lịch.

### 5.1. Kiểm thử nội bộ bằng Mailpit

Đây là hộp thư thử, không chuyển tiếp ra hộp thư thật. Tại thư mục source:

```powershell
docker compose -f compose.yaml -f compose.mailpit.yaml up -d --build
docker compose -f compose.yaml -f compose.mailpit.yaml logs --tail 60 worker
```

Mở [hộp thư thử](http://localhost:8025). Tạo/duyệt/từ chối/rút/sửa/hủy lịch; tải lại hộp thư để xem thông báo. Mailpit chỉ mở UI trên loopback Windows; SMTP cổng 1025 chỉ dùng giữa container. Image `axllent/mailpit:latest` dành cho môi trường thử; có thể cố định digest sau khi tải để tái lập môi trường.

Nguồn cấu hình image/cổng: [tài liệu Docker chính thức Mailpit](https://mailpit.axllent.org/docs/install/docker/). Dùng cùng hai tham số `-f` khi quản lý stack Mailpit. Muốn chuyển lại cấu hình SMTP trong `.env`, dùng `docker compose up -d --build worker` với Compose chính để tạo lại worker theo cấu hình chính; Mailpit là service thử riêng có thể dừng.

### 5.2. SMTP đến hộp thư thật

Chỉnh `.env` **cục bộ**, theo thông số nhà cung cấp của bạn:

```dotenv
SMTP_ENABLED=true
SMTP_HOST=smtp.your-provider.example
SMTP_PORT=587
SMTP_MODE=starttls
SMTP_FROM=your-verified-sender@your-domain.example
SMTP_USERNAME=your-smtp-user
SMTP_PASSWORD=replace-with-your-provider-credential
APP_BASE_URL=http://YOUR-LAN-IP:8080
```

Các giá trị trên là placeholder, không chạy nguyên xi. Với SMTP qua SSL trực tiếp, dùng `SMTP_MODE=ssl` và cổng do nhà cung cấp hướng dẫn (thường 465). Có kiểm tra chứng chỉ TLS; không tắt xác minh. Plain chỉ dành cho hộp thư thử nội bộ với `SMTP_ALLOW_PLAIN=true` ở override Mailpit, không phải mặc định của stack thật. `SMTP_USERNAME`/`SMTP_PASSWORD` phải cùng có hoặc cùng trống theo máy chủ SMTP.

Áp dụng:

```powershell
docker compose up -d --build worker
docker compose logs --tail 60 worker
```

Nếu demo qua LAN, thay `APP_BASE_URL` bằng địa chỉ máy chủ mà người nhận truy cập được. Link email không chứa JWT; mở link sẽ cần đăng nhập và API kiểm tra lại quyền. Để nghiệm thu hộp thư thật, dùng địa chỉ bạn sở hữu/đã được phép nhận thư, tạo một yêu cầu mới rồi kiểm tra Inbox/Spam và trạng thái của hồ sơ. Không dùng email demo `@example.com` để chứng minh gửi ra ngoài thành công.

Worker dùng lease/khóa hàng chờ để nhiều tiến trình không cùng claim một delivery. Trước SMTP, kiểm tra lại người nhận đang hoạt động, email hiện tại, phạm vi và tình trạng sự kiện. Sự kiện lỗi thời/mất quyền được SKIPPED. Thư chỉ có tóm tắt sự kiện và link đăng nhập, không chứa nội dung/tệp riêng hoặc bí mật.

Một lần gửi đầu và tối đa ba lần thử lại tại **1, 5, 15 phút kể từ thất bại đầu**. Hết bốn attempt thì FAILED; giữ mã lỗi an toàn. Lease hết hạn đánh dấu attempt đang dở là UNKNOWN, sau đó xử lý lại có giới hạn. Nếu tiến trình chết sau SMTP chấp nhận nhưng trước ghi nhận SQL, có thể gửi trùng; Message-ID ổn định hỗ trợ đối chiếu, không đảm bảo exactly-once.

**SMTP_ACCEPTED chỉ nghĩa máy chủ SMTP chấp nhận**, không tự chứng minh thư vào Inbox. Người gửi xem tổng trạng thái thông báo trong chi tiết yêu cầu; không công khai địa chỉ hay nhật ký gửi của người khác.

<a id="reports"></a>
## 6. Báo cáo sử dụng phòng

Admin hoặc người phụ trách phòng → **Báo cáo phòng** → chọn từ ngày, đến ngày và phòng → **Xem báo cáo**. Mốc cuối không tính vào kỳ; không chọn phòng nghĩa là toàn phạm vi được phép; tối đa 366 ngày. Nhân viên không có báo cáo toàn đơn vị.

| Chỉ số | Cách tính |
|---|---|
| Đã xác nhận | Root họp có bản hiện tại chưa hủy, thời gian họp giao kỳ; không đếm bản bị thay thế/chờ |
| Đã hủy | Root họp có bản đã xác nhận rồi hủy, thời gian họp giao kỳ; không cộng vào giờ họp |
| Giờ họp | Phần thời gian họp đã xác nhận nằm trong kỳ |
| Giờ chuyển tiếp | Phần đệm sau họp giao kỳ, dùng cấu hình có hiệu lực lúc bắt đầu từng cuộc họp |
| Giờ phục vụ | Hợp các khoảng phục vụ theo lịch sử cấu hình/ngày ngoại lệ, cắt theo kỳ và thời điểm đổi cấu hình |
| Tỷ lệ theo kế hoạch | Giờ họp xác nhận trong giờ phục vụ và trong kỳ / giờ phục vụ của kỳ × 100%; không cộng đệm; mẫu số 0 → Không áp dụng |

Tổng nhiều phòng cộng tử/mẫu số rồi chia, không lấy trung bình các phần trăm. Ngừng nhận đặt mới không xóa số liệu/giờ phục vụ lịch sử. Báo cáo lọc quyền trước tổng hợp, đọc snapshot nhất quán; chỉ trả số, ID phòng và thời điểm, không tiêu đề/người/tài liệu hay ID lịch riêng. Đây là **kế hoạch đặt phòng**, không chứng minh đã diễn ra cuộc họp hoặc sử dụng thực tế.

<a id="automated-tests"></a>
## 7. Chạy kiểm thử tự động

### 7.1. Cách khuyến nghị trên Windows: dùng Docker

Mở Docker Desktop (Linux containers), PowerShell ở thư mục source:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test.ps1
```

Script build image frontend để kiểm tra build, sau đó chạy 7 suite backend trong project **`httt10-tests`** riêng. Kết quả được ghi vào `verification/`; script dọn đúng stack test khi xong, không đụng stack website. Không cần chạy `pip install` trên Windows; tránh lỗi thiếu PyMySQL khi chạy trực tiếp `test_auth.py`.

Nếu vừa build frontend xong và chỉ muốn chạy backend:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test.ps1 -SkipFrontendBuild
```

Hoặc chạy trực tiếp (lệnh này chỉ kiểm tra backend/SMTP thử, chưa build frontend):

```powershell
docker compose -p httt10-tests -f compose.test.yaml up --build --abort-on-container-exit --exit-code-from tests
docker compose -p httt10-tests -f compose.test.yaml down -v
```

Giữ đúng `-p httt10-tests -f compose.test.yaml` ở lệnh dọn: đây là stack thử riêng dùng tmpfs, không publish MySQL ra host và không dùng volume website. Không đổi lệnh đó thành `docker compose down -v` ở stack dữ liệu thật.

`verification/summary.json` chỉ được tạo khi tất cả suite chạy thành công. Khi một suite lỗi, runner dừng, trả exit code khác 0 và xóa summary cũ để tránh báo nhầm PASS. Xem dòng FAIL/traceback đầu tiên và log stack test; không sửa số PASS thủ công. Báo cáo JSON đang có trong Git là bằng chứng lần chạy được ghi, không tự chứng minh máy bạn vừa chạy thành công.

### 7.2. Chạy trực tiếp bằng Python, dành cho môi trường phát triển

Chỉ dùng với **MySQL test riêng**, tài khoản có quyền tạo DB test. Không dùng mật khẩu DB thật hoặc trỏ test vào dịch vụ ngoài phạm vi của bạn. Bộ test tạo các DB `httt10_*_test`, không tạo fixture trong schema website `httt10`.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
$env:MYSQL_TEST_HOST = "127.0.0.1"
$env:MYSQL_TEST_PORT = "43307"
$env:MYSQL_TEST_USER = "your_test_user"
$env:MYSQL_TEST_PASSWORD = "your_test_password"
.\.venv\Scripts\python.exe backend\run_tests.py
```

Thay các placeholder theo MySQL thử bạn đã chuẩn bị; cổng 43307 chỉ là mặc định của bộ test, không phải cổng đã publish sẵn từ Compose website. Không cần `pip install --upgrade pip`; luôn dùng `py -m pip` hoặc Python của venv, không gọi `pip` để tự nâng cấp chính nó trên Windows.

Các suite: auth, catalog, scheduling, amendments, documents, reports, notifications. `notifications` dựng SMTP nhận thử trên loopback TCP, không gửi ra Internet. `TEST_RESULT_DIR` tùy chọn thư mục JSON. Nếu phát triển frontend ngoài Docker, cài Node phù hợp Dockerfile rồi chạy `npm ci` và `npm run build` trong `frontend`.

<a id="manual-tests"></a>
## 8. Kiểm thử thủ công và chụp bằng chứng

### 8.1. Chuẩn bị

1. Cài/cập nhật stack theo phần 1–2; xác nhận `db/api` healthy, `web/worker` Up, `migrate` Exited (0).
2. Tạo các tài khoản và phân công ở phần 3; dùng các cửa sổ đăng nhập riêng.
3. Đặt Windows UTC+07:00. Chọn **ngày làm việc trong tương lai, trước giờ bắt đầu ít nhất 30 phút**; ví dụ D sau 2–7 ngày, A101 09:00–10:00. Không dùng một ngày cố định đã qua.
4. Bật Mailpit nếu kiểm tra email. Chuẩn bị một PDF/PNG hợp lệ dưới 20 MiB, một tệp khác để làm v2 và một tệp quá 20 MiB.
5. Dùng dữ liệu demo riêng: kiểm thử thủ công tạo dữ liệu trong website đang mở; ưu tiên môi trường demo/backup, không lẫn lịch thật.

Với mỗi ca, ghi: **mã ca — tài khoản — đầu vào — bước làm — kết quả mong đợi — kết quả thực tế — PASS/FAIL — ảnh/log — commit đang chạy**. Chỉ đánh PASS sau khi tự quan sát. Không chụp mật khẩu, JWT hoặc `.env`.

### 8.2. Kịch bản theo thứ tự thực hiện

| Mã | Thao tác kiểm thử | Kết quả phải quan sát |
|---|---|---|
| TC-01 | Cài stack, mở website và Swagger | Trang đăng nhập, health ready, 50 thao tác API; migrate Exited (0) |
| TC-02 | Bootstrap lần đầu rồi thử bootstrap lần nữa | Lần đầu tạo Admin; lần sau từ chối khi có Admin hoạt động |
| TC-03 | Đăng nhập tài khoản mới, đổi mật khẩu tạm rồi đăng nhập lại | Buộc đổi mật khẩu; mật khẩu/token cũ không còn dùng được |
| TC-04 | A thử mở quản trị bằng UI và gọi API `/users` qua Swagger với token A | Không có chức năng quản trị; API từ chối 403 |
| TC-05 | Admin khóa B khi B đang đăng nhập; sau đó mở khóa | Phiên B bị thu hồi; B không truy cập khi khóa, phải đăng nhập lại sau mở khóa |
| TC-06 | Admin thử khóa/gỡ quyền Admin hoạt động cuối cùng | Bị chặn, vẫn còn Admin quản trị được |
| TC-07 | Tạo/phân công P1 cho A101 và HC; P2 cho B201 | Chỉ người có vai trò và phạm vi tương ứng được duyệt |
| TC-08 | A tìm A101 ngày D 09:00–10:00, đủ người/thiết bị | Có phòng phù hợp; kết quả không giữ chỗ |
| TC-09 | Tìm phòng ở giờ nghỉ 12:15–12:45 hoặc sức chứa vượt phòng | Không nhận phương án/phòng không phù hợp |
| TC-10 | A gửi họp A101 D 09:00–10:00, có A và B bắt buộc | Yêu cầu Chờ duyệt; calendar chưa bị giữ chỗ |
| TC-11 | A tự gọi API quyết định trên yêu cầu của mình | Server từ chối tự duyệt, kể cả tài khoản được cấp thêm Người phê duyệt |
| TC-12 | P2 chỉ phụ trách B201 thử xem/duyệt yêu cầu A101 không liên quan | Không có quyền quyết định; không lộ chi tiết qua ID |
| TC-13 | P1 duyệt yêu cầu TC-10 | Lịch có hiệu lực; A/B thấy hồ sơ và calendar; SMTP/outbox có trạng thái riêng |
| TC-14 | Một người ngoài phạm vi xem calendar cùng phòng/giờ | Chỉ bận/rảnh, không thấy tiêu đề/thành phần riêng |
| TC-15 | A gửi họp chồng lịch đã duyệt; rồi thử 10:00–11:00 | Bị chặn vì trùng/đệm; 10:15 mới hết đệm 15 phút |
| TC-16 | Gửi hai yêu cầu cùng phòng/giờ khác; mở hai cửa sổ người duyệt, bấm chấp thuận gần đồng thời | Chỉ một được giữ phòng; yêu cầu còn lại bị chặn nếu còn hạn, không có hai lịch hiệu lực chồng nhau |
| TC-17 | Thử người bắt buộc bận ở lịch khác; sau đó đổi thành tùy chọn | Bắt buộc–bắt buộc bị chặn; có tùy chọn thì cảnh báo cần xác nhận |
| TC-18 | Gửi yêu cầu riêng rồi người tạo rút khi còn chờ | Chuyển Đã rút, không giữ phòng/người; không rút lại như một thao tác mới thành công |
| TC-19 | Gửi yêu cầu riêng; P1 từ chối và nhập lý do | Đã từ chối, người gửi xem được lý do; không tạo lịch hiệu lực |
| TC-20 | A gửi công tác A+B cùng HC, thời gian gồm di chuyển; P1 duyệt | Bận công tác đúng toàn khoảng; thử thêm người phòng ban khác phải bị từ chối |
| TC-21 | A sửa cuộc họp đã duyệt từ A101 sang B201 và thay B bằng C | Trong lúc chờ A101 vẫn bị giữ; P2 duyệt bản mới thì mới giải phóng A101 và giữ B201 |
| TC-22 | Thử từ chối/rút bản sửa riêng | Lịch gốc không đổi; không giải phóng chỗ cũ trước khi bản sửa được duyệt |
| TC-23 | Khi chờ sửa, cho lịch khác được duyệt vào chỗ mới rồi thử duyệt bản sửa | Chặn bản sửa, giữ lịch gốc; không mất lịch gốc do tranh chỗ mới |
| TC-24 | Người tạo hủy một cuộc họp chưa bắt đầu, có lý do | Giải phóng phòng/đệm/người; bản sửa chờ hết hiệu lực; giữ lịch sử |
| TC-25 | B hoặc Admin chỉ quản trị thử hủy họp của A; A thử hủy lịch đã bắt đầu | Bị từ chối đúng quyền/thời hạn |
| TC-26 | A đề nghị hủy công tác đã duyệt, P1 chấp thuận | Lúc chờ vẫn bận; chỉ khi duyệt hủy mới giải phóng; từ chối/rút giữ lịch gốc |
| TC-27 | Tạo yêu cầu theo giờ ngắn nhất hợp lệ, chưa xử lý đến giờ bắt đầu; tải lại sau lượt quét | Chuyển Hết hạn, không tạo hiệu lực; không sửa đồng hồ hệ thống/DB thật để thử |
| TC-28 | A thêm PDF/ảnh vào họp, thêm v2, tải v1 và v2 | Hai phiên bản được giữ, nội dung tải đúng; lịch không đổi phiên bản nghiệp vụ |
| TC-29 | Thử tệp rỗng, `.exe`, đổi đuôi tệp giả, tệp quá 20 MiB | Bị từ chối; không có metadata/byte nửa chừng |
| TC-30 | A ẩn tài liệu có lý do, bật Hiện tài liệu đã ẩn | Mặc định không hiện; lịch sử vẫn tải trong quyền; không thêm v mới vào tài liệu ẩn |
| TC-31 | Gắn tệp vào bản A101 có B; sửa sang B201 có C và thêm tệp cho bản mới | B không thấy/tải tệp mới; C không thấy/tải tệp cũ; Admin không tự có quyền |
| TC-32 | Người tạo thêm biên bản vào bản hiện tại sau họp; thử thêm vào bản cũ/họp đã hủy | Sau họp được phép; bản cũ/hủy chỉ đọc |
| TC-33 | Sau gửi/duyệt/hủy, mở Mailpit; bấm link thư rồi đăng nhập đúng người | Có tóm tắt đúng ngữ cảnh và mở hồ sơ được phép; không có tệp/bí mật/nội dung riêng |
| TC-34 | Với SMTP thật đã cấu hình, tạo sự kiện mới và kiểm tra hộp thư do bạn kiểm soát | Phân biệt SMTP_ACCEPTED với thư thực nhận; ghi rõ Inbox/Spam, thời gian và người nhận đã che bớt |
| TC-35 | Cấu hình SMTP thử không kết nối được, phát sinh sự kiện mới, theo dõi sau 1/5/15 phút | Có RETRY rồi FAILED sau tối đa 4 attempt; lịch đã duyệt vẫn không đổi; khôi phục cấu hình sau thử |
| TC-36 | P1 mở Báo cáo phòng và chọn kỳ; nhân viên A thử truy cập API báo cáo | P1 chỉ có A101; A bị từ chối 403; Admin có số liệu tổng hợp, không nội dung riêng |
| TC-37 | Kỳ một ngày A101 phục vụ 8 giờ, có một họp 1 giờ đã duyệt, đệm 15 phút và một họp đã hủy | Giờ họp 1; đệm 0,25; phục vụ 8; tỷ lệ 12,5%; lượt hủy tách riêng. Dùng kỳ/phòng sạch để số khớp |
| TC-38 | Báo cáo ngày nghỉ/không có giờ phục vụ, rồi nhập khoảng ngày ngược | Mẫu số 0 → Không áp dụng; khoảng sai bị từ chối và không giữ bảng cũ như kết quả mới |
| TC-39 | Mở bản lịch sử của người chỉ được tham gia bản cũ, kể cả khi bản mới riêng tư đã hủy | Chỉ nội dung/tệp/audit bản được phép; không hiện quyền ghi của bản mới |
| TC-40 | Mất phản hồi sau thao tác: đọc hồ sơ trước khi gửi lại; với upload dùng Tải lại tài liệu | Không tạo lặp mù; command retry giữ nguyên ý định/key, upload đối chiếu danh sách |
| TC-41 | Đăng xuất, thử dùng token phiên cũ qua Swagger | Server từ chối 401; không chỉ ẩn giao diện |
| TC-42 | Máy thứ hai cùng LAN mở `http://IP-MAY-CHU:8080`, đăng nhập và tạo/duyệt thử | API dùng URL tương đối, kết nối DB bên trong Docker; không cần mở MySQL ra LAN |

TC-16/TC-40 khó tạo đúng thời điểm bằng tay: bộ tự động đã có kết nối cạnh tranh và chèn lỗi mất phản hồi/rollback. Khi test tay chưa tái hiện được, ghi “chưa thực hiện”, không đổi thành PASS dựa trên suy đoán. TC-27 có thể cần đợi thực tế; bộ tự động dùng DB/thời gian fixture riêng để kiểm tra hết hạn.

### 8.3. Bằng chứng nên chụp

- Ảnh stack `docker compose ps -a`: thấy db/api healthy và migrate Exited (0).
- Ảnh tài khoản demo/phân công đã che thông tin nhạy cảm; không chụp ô mật khẩu.
- Yêu cầu chờ và lịch chưa giữ chỗ; sau duyệt thấy lịch đã xác nhận.
- Thông báo xung đột/đệm; hai yêu cầu cạnh tranh và chỉ một được xác nhận.
- Sửa đổi phòng/thành phần: bản cũ khi chờ, bản mới sau duyệt, lịch sử đúng quyền.
- Tài liệu có v1/v2 và trạng thái ẩn; kết quả từ chối tải ngoài quyền.
- Hộp thư Mailpit hoặc hộp thư thật đã che địa chỉ, kèm trạng thái SMTP của hồ sơ.
- Bảng báo cáo có kỳ, phòng và tỷ lệ đúng ví dụ; kết quả tự động trong `summary.json`.
- Website trên máy thứ hai cùng LAN, thanh địa chỉ và thời điểm kiểm tra.

<a id="source"></a>
## 9. Cấu trúc source, API và CSDL

| Vị trí | Nội dung |
|---|---|
| `README.md` | Tài liệu thống nhất: cài đặt, dùng, kiểm thử, kết quả và đặc tả |
| `backend/app/main.py`, `services.py`, `security.py`, `dependencies.py` | Auth, JWT/phiên DB, lỗi chuẩn hóa và middleware |
| `backend/app/catalog.py`, `catalog_routes.py` | Quản trị/danh mục/phân công, calendar và tìm phòng |
| `backend/app/scheduling.py`, `scheduling_routes.py`, `schedule_jobs.py` | CREATE/CHANGE/CANCEL, khóa tài nguyên, idempotency, audit, hết hạn |
| `backend/app/documents.py`, `document_storage.py`, `document_routes.py` | Kho tệp riêng và quyền theo context revision |
| `backend/app/email_worker.py` | SMTP, lease, recheck quyền, retry và lưu attempt |
| `backend/app/reports.py` | Snapshot chỉ đọc và báo cáo kế hoạch theo phạm vi |
| `backend/app/schemas.py`, `models.py`, `db.py` | DTO, ORM auth, engine/session; SQL baseline giữ vai trò canonical |
| `backend/alembic/`, `backend/db/` | Migration, schema, seed, metadata kiểm tra adoption |
| `backend/test_*.py`, `backend/run_tests.py` | 7 suite MySQL thật, SMTP loopback và runner tổng |
| `frontend/src/` | React auth, workspace, scheduling, documents và reports |
| `compose.yaml`, `compose.mailpit.yaml`, `compose.test.yaml` | Website, hộp thư thử tùy chọn và stack kiểm thử riêng |
| `scripts/` | Sinh `.env` và chạy kiểm thử Windows |
| `verification/*.json` | Kết quả máy đọc theo nhóm chức năng; không còn các báo cáo `.md` theo mốc |
| `docs/target-openapi.yaml` | Hợp đồng 50 thao tác mục tiêu; Swagger là schema runtime thực tế |

Có 24 bảng nghiệp vụ và 3 view; Alembic thêm bảng kỹ thuật `alembic_version`, tổng 25 bảng vật lý. Không dùng `Base.metadata.create_all` để tạo mô hình DB song song. Mọi giá trị SQL được bind; dữ liệu riêng được chiếu DTO sau kiểm tra quyền. Migration baseline chạy trên DB mới và giữ dữ liệu khi cập nhật. `adopt-baseline` chỉ dành cho DB đã đúng baseline, không dùng để stamp một DB bất kỳ; cần sao lưu/đối chiếu metadata trước.

### Nhóm API

Tất cả dưới `/api/v1`. Swagger có 50 thao tác: 6 nền, 22 danh mục/quản trị, 15 lịch/yêu cầu, 6 tài liệu, 1 báo cáo. Giao diện web sử dụng cookie phiên HttpOnly cùng địa chỉ website. Swagger và các API client vẫn dùng JWT qua Authorization Bearer. Login nhận JSON email/password. Dùng Authorize trong Swagger với token vừa nhận và tránh chụp token thật.

| Nhóm | Đường dẫn chính |
|---|---|
| Auth/health | `/auth/login`, `/auth/me`, `/auth/logout`, `/auth/password`, `/health/live`, `/health/ready` |
| Danh mục/quyền | `/directory/users`, `/users`, `/departments`, `/rooms`, policies/approvers |
| Tra cứu | `/calendar`, `/rooms/availability`, `/availability/check` |
| Yêu cầu | `/meeting-proposals`, `/work-proposals`, `/proposals`, decisions/withdrawals |
| Lịch | `/schedules`, revisions/audit, change-proposals, meeting-cancellations, work-cancellation-proposals |
| Tài liệu | `/schedules/{id}/documents`, `/documents/{id}/versions`, hides, versions/{id}/content |
| Báo cáo | `GET /reports/room-usage?from=...&to=...&room_ids=...` |

Command lịch yêu cầu `Idempotency-Key` 16–128 ký tự. Upload dùng multipart `metadata` JSON + `file`; tạo mới `{context_revision_id,display_name}`, thêm phiên bản `{context_revision_id,expected_latest_version_id}`; trả `DocumentVersionView` 201. Ẩn gửi JSON `{expected_latest_version_id,reason}`, trả 204. Danh sách phân trang `page`, `page_size` tối đa 100; selectors/UI đi hết trang, không âm thầm cắt ở 100 bản ghi.

<a id="operations"></a>
## 10. Vận hành và xử lý lỗi

### 10.1. Kho tài liệu và sao lưu

Compose gắn `document_data:/app/data/documents`; chạy Python trực tiếp mặc định `backend/data/documents`, có thể đổi bằng `DOCUMENT_STORAGE_DIR`. Tên tệp vật lý ngẫu nhiên, không dùng tên người dùng gửi; thư mục/tệp riêng tư 0700/0600 trên Linux. Nginx nhận request tối đa 21 MiB để đủ multipart, API vẫn giới hạn payload 20 MiB.

Tệp staging/kiểm tra/publish nguyên tử trong cùng filesystem rồi commit metadata. File và SQL không chung một giao dịch ACID: khi lỗi, chỉ dọn byte nếu xác nhận DB không tham chiếu; khi tiến trình chết/commit mơ hồ có thể còn orphan. SHA-256/kích thước được kiểm tra trước tải; thiếu/hỏng trả 503 an toàn.

Xem trước orphan quá 24 giờ:

```powershell
docker compose exec api python -m app.cli document-storage-cleanup
```

Sau đối chiếu/sao lưu, dùng thêm `--apply` để dọn. Giữ mọi tệp có tham chiếu DB, kể cả v cũ/tài liệu ẩn; bỏ qua upload đang khóa. Không dùng cleaner làm xóa lịch sử nghiệp vụ.

Sao lưu đồng bộ **MySQL + volume document_data + cấu hình `.env`**. Dừng `api` và `worker` trong lúc lấy bản sao nhất quán; giữ tệp ẩn. Chưa tự động hóa hoặc kiểm thử khôi phục volume trên Windows. Đổi tên/thư mục dự án Compose có thể trỏ sang volume khác; đối chiếu stack trước khi kết luận dữ liệu mất.

### 10.2. Lỗi thường gặp

| Hiện tượng | Cách kiểm tra/xử lý |
|---|---|
| migrate Exited (0) | Thành công, không cần giữ nó Up; xem api/db healthy |
| migrate Exited khác 0, api không lên | Xem `docker compose logs migrate db`; đối chiếu `.env` với volume đang dùng, không xóa volume để sửa |
| `ModuleNotFoundError: pymysql` khi chạy test trên Windows | Dùng script Docker phần 7; nếu chạy Python thì cài requirements vào đúng venv trước |
| pip yêu cầu `python.exe -m pip` | Dùng `py -m pip`/Python venv, không nâng pip bằng chính lệnh `pip` |
| Đăng nhập cần đổi mật khẩu | Tài khoản mới/reset mật khẩu phải đổi mật khẩu tạm rồi đăng nhập lại |
| 401 khi khôi phục phiên hoặc sau đổi quyền/đổi mật khẩu | Kiểm tra địa chỉ website, cookie trình duyệt và thời hạn phiên. Đăng nhập lại nếu phiên đã hết hạn hoặc bị thu hồi |
| 429 khi thử đăng nhập nhiều | Tối đa 10 lượt/phút/IP trong một process; đợi ít nhất một phút, không thử liên tục |
| Không thấy yêu cầu vừa duyệt | Đổi lọc từ Chờ duyệt sang Đã duyệt/Tất cả; calendar chọn đúng ngày/phòng/người |
| Không thấy nút tạo/duyệt/báo cáo | Kiểm tra vai trò và phân công; Admin không tự nhận quyền nghiệp vụ |
| 409 dữ liệu đã thay đổi | Tải trạng thái mới và đọc lại trước khi chủ động thao tác; không ghi đè mù |
| Worker báo SMTP disabled | Chưa bật/cấu hình SMTP; hàng chờ được giữ, không phải email đã gửi |
| Thư FAILED hoặc chưa thấy Inbox | Kiểm tra cấu hình SMTP/địa chỉ, trạng thái attempt và Inbox/Spam; SMTP_ACCEPTED không chứng minh đã nhận |
| Tệp vượt giới hạn/trả 413 | Payload tối đa 20 MiB, request qua Nginx 21 MiB; không tăng riêng Nginx để lách API |
| Tệp thiếu/hỏng trả 503 | Đối chiếu volume document_data và bản sao; không sửa hash/metadata để bỏ kiểm tra |
| LAN không mở được website | Cùng mạng, đúng IPv4 máy chủ từ `ipconfig`, firewall cho TCP 8080 mạng Private; không publish MySQL |

Thử quét hết hạn thủ công: `docker compose exec api python -m app.cli expire-proposals`. Rate limit login hiện trong bộ nhớ một process; nếu mở rộng nhiều replica phải dùng cơ chế chia sẻ. Khi triển khai ngoài demo mạng nội bộ cần HTTPS và quy trình vận hành/backup phù hợp.

<a id="verification"></a>
## 11. Kết quả kiểm chứng tổng hợp

Ngày kiểm tra: 15/11/2026, môi trường phát triển Linux/Python 3.12, MySQL Community 8.4.0, FastAPI 0.141.1 / Starlette 1.10.0, React 19.1.1 / JSDOM 26.1.0.

| Nhóm | Đạt/tổng | Phạm vi |
|---|---|---|
| Xác thực và phiên | 28/28 | MySQL thật + ASGI; email dùng SMTP loopback TCP |
| Danh mục và phân quyền | 83/83 | MySQL thật + ASGI; email dùng SMTP loopback TCP |
| Tạo/gửi/duyệt lịch | 105/105 | MySQL thật + ASGI; email dùng SMTP loopback TCP |
| Sửa/hủy và lịch sử | 111/111 | MySQL thật + ASGI; email dùng SMTP loopback TCP |
| Tài liệu họp | 104/104 | MySQL thật + ASGI; email dùng SMTP loopback TCP |
| Báo cáo phòng | 43/43 | MySQL thật + ASGI; email dùng SMTP loopback TCP |
| Worker email | 64/64 | MySQL thật + ASGI; email dùng SMTP loopback TCP |
| React: Gửi/duyệt/rút | 10/10 | DOM mô phỏng + HTTP/API/MySQL thật |
| React: Sửa/hủy/lịch sử | 14/14 | DOM mô phỏng + HTTP/API/MySQL thật |
| React: Tài liệu | 15/15 | DOM mô phỏng + HTTP/API/MySQL thật |
| React: Báo cáo và link email | 10/10 | DOM mô phỏng + HTTP/API/MySQL thật |
| Frontend production build | PASS | `npm run build --prefix frontend` |
| Compose/SMTP override/script Windows | Kiểm tra tĩnh | Parse YAML, kiểm tra tách volume/port/config; chưa chạy Docker/PowerShell Windows |

**Backend: 538/538. React DOM: 49/49.** Có 50 thao tác API runtime. Bảng này thay các báo cáo theo mốc; JSON giữ nguyên từng kiểm tra theo chức năng.

### Giới hạn kiểm chứng

- Chưa chạy Docker image/Nginx end-to-end, Docker Desktop Windows, script PowerShell thực tế hoặc LAN hai máy trong môi trường này. Cần làm phần 8 trên máy triển khai.
- JSDOM không kiểm tra bố cục CSS, hộp thoại tải tệp hệ điều hành hoặc trình duyệt thật. Kiểm tra upload dùng submit mô phỏng vì native required-file validation của JSDOM không đồng bộ với FileList được mô phỏng.
- SMTP đã trao đổi qua TCP với máy chủ nhận thử nội bộ; chưa xác nhận TLS với nhà cung cấp ngoài hay nhận ở Inbox thật. Không gắn nhãn SMTP_ACCEPTED thành thư thực nhận.
- Đã mô phỏng lỗi/rollback/lease/crash sau SMTP; chưa thử mất điện/hỏng đĩa/restore volume hoặc COMMIT mơ hồ trên mạng thật. Gửi lại sau crash có thể trùng, byte lưu trữ và SQL không chung ACID.
- Mẫu Office kiểm tra cấu trúc/giới hạn và quyền, không thay thử mở tài liệu thực tế bằng Microsoft Office; chưa có antivirus, quota tổng hoặc backup tự động.
- Không tuyên bố đã nghiệm thu 44 tiêu chí nghiệp vụ chỉ từ số kiểm tra thành phần. Dùng bảng ghi kết quả thực tế phần 8 để chốt nghiệm thu.

### Chi tiết tự động đã chạy

Các bảng dưới có thể thu gọn trên GitHub. Mỗi dòng tương ứng một kiểm tra trong JSON cùng nhóm.

<details>
<summary>Xác thực và phiên — backend: 28/28</summary>

Nguồn: [verification/auth-result.json](verification/auth-result.json).

| STT | Nội dung | Kết quả |
|---|---|---|
| 1 | Migration baseline và adoption chạy được trên MySQL | PASS |
| 2 | Health live | PASS |
| 3 | Không Bearer -> 401 | PASS |
| 4 | Sai mật khẩu -> 401 | PASS |
| 5 | Email không tồn tại cùng lỗi chung | PASS |
| 6 | Validation không lộ input mật khẩu | PASS |
| 7 | Login cấp JWT và cờ mật khẩu tạm | PASS |
| 8 | Admin không tự có quyền Nhân viên | PASS |
| 9 | Me không trả hash/token | PASS |
| 10 | JWT giả bị từ chối | PASS |
| 11 | Response có request ID/no-store | PASS |
| 12 | Đổi mật khẩu sai xác nhận -> 422 | PASS |
| 13 | Đổi mật khẩu sai hiện tại -> 422 | PASS |
| 14 | Đổi mật khẩu tạm -> 204 | PASS |
| 15 | Token cũ hết hiệu lực sau đổi mật khẩu | PASS |
| 16 | Mật khẩu cũ không đăng nhập được | PASS |
| 17 | Bỏ cờ mật khẩu tạm sau đổi | PASS |
| 18 | Logout -> 204 không body | PASS |
| 19 | Token logout không dùng lại được | PASS |
| 20 | Logout chỉ thu hồi đúng phiên | PASS |
| 21 | Khóa tài khoản vô hiệu token ngay ở server | PASS |
| 22 | Tài khoản khóa không login được | PASS |
| 23 | auth_version đổi vô hiệu token | PASS |
| 24 | JWT hết hạn bị chặn | PASS |
| 25 | Mật khẩu được băm Argon2, không plain text | PASS |
| 26 | Rate limit lần 11 trả 429 và Retry-After | PASS |
| 27 | API giữ đủ 6 operation nền mốc A | PASS |
| 28 | Lưu audit của các thao tác tài khoản | PASS |

</details>

<details>
<summary>Danh mục và phân quyền — backend: 83/83</summary>

Nguồn: [verification/catalog-result.json](verification/catalog-result.json).

| STT | Nội dung | Kết quả |
|---|---|---|
| 1 | Mật khẩu tạm không được truy cập danh mục | PASS |
| 2 | Admin không tự nhận vai trò nhân viên | PASS |
| 3 | Không có phiên -> 401 | PASS |
| 4 | UUID sai -> 422 | PASS |
| 5 | Phân trang vượt giới hạn -> 422 | PASS |
| 6 | Danh mục baseline giữ nguyên | PASS |
| 7 | Tạo phòng ban | PASS |
| 8 | Mã phòng ban trùng trả 409 | PASS |
| 9 | Chặn sửa phòng ban bằng phiên bản cũ | PASS |
| 10 | Sửa phòng ban tăng phiên bản | PASS |
| 11 | Cấp tài khoản không trả mật khẩu/hash | PASS |
| 12 | Nhân viên không được đọc tài khoản quản trị | PASS |
| 13 | Nhân viên không được tạo phòng ban | PASS |
| 14 | Directory chỉ trả UserRef | PASS |
| 15 | Tìm kiếm tài khoản phân trang | PASS |
| 16 | Tìm kiếm không coi ký tự % là wildcard | PASS |
| 17 | Email duy nhất không phân biệt hoa thường | PASS |
| 18 | Chỉ đổi tên không thu hồi phiên | PASS |
| 19 | Đổi vai trò thu hồi token hiện có | PASS |
| 20 | Khóa tài khoản vô hiệu phiên | PASS |
| 21 | Directory không trả người bị khóa | PASS |
| 22 | Đặt lại mật khẩu thu hồi phiên | PASS |
| 23 | Đặt lại mật khẩu bắt buộc đổi | PASS |
| 24 | Không khóa Admin hoạt động cuối cùng | PASS |
| 25 | Không gỡ quyền Admin hoạt động cuối cùng | PASS |
| 26 | Tạo phòng đồng thời cấu hình và thiết bị | PASS |
| 27 | Chặn khoảng phục vụ chồng nhau | PASS |
| 28 | Chỉ gán người có APPROVER và ACTIVE | PASS |
| 29 | Phân công phòng cập nhật phiên bản | PASS |
| 30 | Me tải phạm vi duyệt từ server | PASS |
| 31 | Phân công từ màn hình cũ bị chặn | PASS |
| 32 | Phân công công tác theo phòng ban | PASS |
| 33 | Người duyệt không được quản lý phân công | PASS |
| 34 | Ngoài phạm vi chỉ thấy bận và chuyển tiếp | PASS |
| 35 | Busy DTO không lộ title/ID/nội dung | PASS |
| 36 | Entry key che mã revision gốc | PASS |
| 37 | Calendar không hiện chờ duyệt hoặc đã hủy | PASS |
| 38 | Người tham gia được xem tiêu đề | PASS |
| 39 | Admin chưa có phạm vi không xem chi tiết | PASS |
| 40 | Bộ lọc phòng và người dùng là AND | PASS |
| 41 | Khoảng đệm hiện riêng khi xem phòng | PASS |
| 42 | Calendar cá nhân không tính đệm của phòng | PASS |
| 43 | Calendar mặc định trả cả công tác của mình | PASS |
| 44 | Calendar chỉ phần đệm vẫn có kết quả | PASS |
| 45 | Calendar buộc múi giờ RFC3339 | PASS |
| 46 | Calendar chặn khoảng quá rộng | PASS |
| 47 | Đường availability được nhận trước UUID động | PASS |
| 48 | Tìm phòng chặn lịch đã xác nhận | PASS |
| 49 | Tìm phòng tính đệm sau lịch trước | PASS |
| 50 | Đệm của lịch mới cũng không đè lịch tiếp | PASS |
| 51 | Đúng mép đệm cho phép | PASS |
| 52 | Giờ nghỉ trưa không được đặt | PASS |
| 53 | Đệm được chạy qua giờ nghỉ | PASS |
| 54 | Không bỏ qua giây khi kiểm tra giờ đóng | PASS |
| 55 | Sức chứa tính toàn bộ người | PASS |
| 56 | Thiết bị lọc AND | PASS |
| 57 | Thiếu một thiết bị thì loại | PASS |
| 58 | Yêu cầu chờ không giữ phòng | PASS |
| 59 | Yêu cầu chờ có cảnh báo an toàn | PASS |
| 60 | Cảnh báo không lộ tiêu đề yêu cầu | PASS |
| 61 | Người tạo được loại trừ chính lịch cũ | PASS |
| 62 | Không được loại trừ lịch người khác | PASS |
| 63 | Loại trừ UUID không tồn tại -> 404 | PASS |
| 64 | Thời lượng dưới 15 phút -> 422 | PASS |
| 65 | Bắt đầu dưới 30 phút -> 422 | PASS |
| 66 | Quá 90 ngày -> 422 | PASS |
| 67 | Giảm sức chứa không làm sai lịch đã duyệt | PASS |
| 68 | Đổi giờ không làm lịch đã duyệt ngoài giờ | PASS |
| 69 | Tăng đệm không gây chồng lịch đã duyệt | PASS |
| 70 | Cấu hình bị từ chối không tăng phiên bản/không lưu | PASS |
| 71 | Không sửa ngược cấu hình lịch sử | PASS |
| 72 | Thêm cấu hình hợp lệ giữ lịch sử cũ | PASS |
| 73 | Ngày nghỉ riêng loại khỏi tìm phòng | PASS |
| 74 | Ngừng nhận mới không còn được tìm thấy | PASS |
| 75 | Ngừng nhận mới giữ lịch đã duyệt | PASS |
| 76 | Phân công hiển thị số yêu cầu chờ | PASS |
| 77 | Thu hồi phạm vi có hiệu lực ngay | PASS |
| 78 | Gỡ APPROVER vô hiệu phân công công tác | PASS |
| 79 | Thu hồi vai trò tăng phiên bản phạm vi bị ảnh hưởng | PASS |
| 80 | Hai Admin gỡ quyền đồng thời chỉ một thành công | PASS |
| 81 | Sau cạnh tranh vẫn còn đúng một Admin hoạt động | PASS |
| 82 | Mốc B lưu audit nhưng không ghi mật khẩu | PASS |
| 83 | OpenAPI giữ API quản trị và tra cứu mốc B | PASS |

</details>

<details>
<summary>Tạo/gửi/duyệt lịch — backend: 105/105</summary>

Nguồn: [verification/scheduling-result.json](verification/scheduling-result.json).

| STT | Nội dung | Kết quả |
|---|---|---|
| 1 | Không có phiên không được kiểm tra lịch | PASS |
| 2 | Admin kỹ thuật không tự có quyền đăng ký | PASS |
| 3 | Thiếu Idempotency-Key bị từ chối | PASS |
| 4 | Key không hợp lệ bị từ chối | PASS |
| 5 | Không nhận trạng thái/người gửi do client tự gán | PASS |
| 6 | Chủ trì phải tham gia bắt buộc | PASS |
| 7 | Preflight không giữ tài nguyên | PASS |
| 8 | Preflight không tạo root | PASS |
| 9 | Gửi yêu cầu trả 201 | PASS |
| 10 | Biên nhận chỉ có ID không giả xác nhận giữ phòng | PASS |
| 11 | Yêu cầu mới PENDING / root chưa có lịch hiệu lực | PASS |
| 12 | Người gửi chỉ được rút, chưa có nút duyệt | PASS |
| 13 | Lưu outbox và delivery cùng yêu cầu | PASS |
| 14 | Email vẫn chờ, chưa có SMTP giả thành công | PASS |
| 15 | Yêu cầu chờ không xuất hiện trong calendar | PASS |
| 16 | Người ngoài không đọc yêu cầu chờ | PASS |
| 17 | Admin kỹ thuật không đọc yêu cầu riêng | PASS |
| 18 | Root chờ ngoài quyền trả 404 | PASS |
| 19 | Danh sách theo người gửi không rò toàn bộ yêu cầu | PASS |
| 20 | Người duyệt đúng phạm vi thấy yêu cầu | PASS |
| 21 | Người duyệt ngoài phạm vi không thấy yêu cầu | PASS |
| 22 | Retry cùng key trả cùng ID | PASS |
| 23 | Retry có header Idempotency-Replayed | PASS |
| 24 | Retry không nhân đôi root hoặc outbox | PASS |
| 25 | Key thành công không được đổi payload | PASS |
| 26 | Không tự duyệt yêu cầu | PASS |
| 27 | Không tự từ chối yêu cầu | PASS |
| 28 | Không có scope bị chặn ở server | PASS |
| 29 | Duyệt phiên bản cũ bị chặn | PASS |
| 30 | Duyệt hợp lệ trả 200 | PASS |
| 31 | Chỉ sau duyệt mới có hiệu lực | PASS |
| 32 | Duyệt tăng phiên bản root và proposal | PASS |
| 33 | Lưu người phê duyệt thật | PASS |
| 34 | Replay quyết định được xét trước phiên bản cũ | PASS |
| 35 | Replay quyết định không tạo event mới | PASS |
| 36 | Yêu cầu đã xử lý không rút được | PASS |
| 37 | Root hiệu lực ngoài quyền chỉ BUSY_ONLY | PASS |
| 38 | Busy không lộ title/ID/người tham gia | PASS |
| 39 | Người tạo xem chi tiết bản hiệu lực | PASS |
| 40 | Người ngoài không lấy được revision | PASS |
| 41 | Người tạo xem lịch sử revision | PASS |
| 42 | Người tạo có audit nghiệp vụ | PASS |
| 43 | Audit không trả raw metadata | PASS |
| 44 | Lịch liên quan lọc đúng quyền | PASS |
| 45 | Admin không tự có lịch chi tiết toàn đơn vị | PASS |
| 46 | Đã giữ phòng thì preflight không bookable | PASS |
| 47 | Xung đột không tiết lộ title/root đối thủ | PASS |
| 48 | Phương án cứng xung đột không được gửi | PASS |
| 49 | Phòng không đủ sức chứa trả conflict | PASS |
| 50 | Không có người duyệt thay chặn gửi | PASS |
| 51 | Chỉ có chính người gửi làm người duyệt thì chặn | PASS |
| 52 | Hai yêu cầu chờ cùng phòng cần xác nhận cảnh báo | PASS |
| 53 | Chưa xác nhận cảnh báo không chiếm key | PASS |
| 54 | Token xác nhận không chứa UUID lịch đối thủ | PASS |
| 55 | Token cảnh báo không dùng làm token đăng nhập | PASS |
| 56 | Token cảnh báo gắn người thao tác | PASS |
| 57 | Token cảnh báo gắn payload | PASS |
| 58 | Xác nhận cảnh báo cho phép lưu yêu cầu thứ hai | PASS |
| 59 | Hai yêu cầu chờ vẫn không giữ phòng | PASS |
| 60 | Duyệt cũng phải xác nhận warning hiện tại | PASS |
| 61 | Yêu cầu thứ nhất được duyệt | PASS |
| 62 | Yêu cầu thứ hai không được duyệt khi phòng đã giữ | PASS |
| 63 | Xung đột giữ PENDING, không tự từ chối | PASS |
| 64 | Người bắt buộc bận chặn dù phòng khác | PASS |
| 65 | Một bên tùy chọn chỉ cảnh báo | PASS |
| 66 | Xác nhận tùy chọn được gửi | PASS |
| 67 | Tùy chọn vẫn được duyệt sau xác nhận | PASS |
| 68 | Lịch cũ tùy chọn, lịch mới bắt buộc vẫn chỉ cảnh báo | PASS |
| 69 | Công tác qua đêm nhiều ngày không bị giới hạn giờ phòng | PASS |
| 70 | Người duyệt công tác theo phòng ban chấp thuận | PASS |
| 71 | Công tác không trộn người khác phòng ban | PASS |
| 72 | Người gửi không đăng ký thay phòng ban khác | PASS |
| 73 | Công tác nhiều ngày chặn trùng người với họp | PASS |
| 74 | Từ chối bắt buộc có lý do | PASS |
| 75 | Từ chối hợp lệ lưu quyết định | PASS |
| 76 | Từ chối không giữ chỗ | PASS |
| 77 | Người khác không rút hộ yêu cầu | PASS |
| 78 | Người gửi được rút yêu cầu | PASS |
| 79 | Retry rút không bị phiên bản cũ chặn | PASS |
| 80 | Yêu cầu rút không thể được duyệt | PASS |
| 81 | Đến hạn trả PROPOSAL_EXPIRED | PASS |
| 82 | Lỗi hết hạn nói rõ đã commit | PASS |
| 83 | EXPIRED được lưu thật | PASS |
| 84 | Sweep tự hết hạn xử lý hồ sơ chờ | PASS |
| 85 | Sweep lặp không ghi event lần hai | PASS |
| 86 | Duyệt sát giờ không áp lại điều kiện 30 phút | PASS |
| 87 | Duyệt kiểm tra lại thành viên bị khóa | PASS |
| 88 | Quyền duyệt bị thu hồi có hiệu lực tại server | PASS |
| 89 | Lỗi sau UPDATE hoàn tác current và trạng thái | PASS |
| 90 | Lỗi sau UPDATE không ghi event quyết định | PASS |
| 91 | Có thể duyệt lại sau rollback | PASS |
| 92 | Duyệt đọc lại trạng thái phòng nhận mới | PASS |
| 93 | Phòng ngừng nhận không tự từ chối hồ sơ chờ | PASS |
| 94 | Tập cảnh báo đổi bắt buộc xác nhận lại | PASS |
| 95 | Token xác nhận hết hạn không được dùng | PASS |
| 96 | Key hết hạn yêu cầu đọc lại hồ sơ trước khi tạo mới | PASS |
| 97 | Hai POST cùng key đồng thời đều nhận receipt | PASS |
| 98 | Hai POST cùng key chỉ tạo một lịch | PASS |
| 99 | Hai duyệt cùng phòng chỉ một được chấp thuận | PASS |
| 100 | Cùng phòng không có hai lịch hiệu lực | PASS |
| 101 | Duyệt khác phòng nhưng chung người bắt buộc chỉ một thắng | PASS |
| 102 | Người bắt buộc không bị giữ ở hai lịch cùng giờ | PASS |
| 103 | Duyệt và rút cạnh tranh chỉ một thành công | PASS |
| 104 | Kết quả duyệt/rút nhất quán với hiệu lực | PASS |
| 105 | OpenAPI giữ đủ API gửi/duyệt mốc C | PASS |

</details>

<details>
<summary>Sửa/hủy và lịch sử — backend: 111/111</summary>

Nguồn: [verification/amendments-result.json](verification/amendments-result.json).

| STT | Nội dung | Kết quả |
|---|---|---|
| 1 | Chủ lịch có các thao tác sửa và hủy họp | PASS |
| 2 | Người tham gia không được quản lý lịch | PASS |
| 3 | Người ngoài không gửi đề nghị sửa | PASS |
| 4 | Không gửi sửa bằng phiên bản root cũ | PASS |
| 5 | Không gửi sửa bằng base revision sai | PASS |
| 6 | Đề nghị sửa được lưu PENDING | PASS |
| 7 | Gửi sửa giữ current revision cũ | PASS |
| 8 | Gửi sửa chưa giữ phòng mới | PASS |
| 9 | Gửi sửa tăng phiên bản aggregate | PASS |
| 10 | Chỉ một đề nghị chờ cho mỗi lịch | PASS |
| 11 | Lịch có bản sửa chờ vẫn được hủy họp | PASS |
| 12 | Retry gửi sửa không tạo revision mới | PASS |
| 13 | Retry gửi sửa chỉ có hai revision | PASS |
| 14 | Người duyệt phòng cũ không đọc bản sửa phòng mới | PASS |
| 15 | Người tham gia cũ không đọc bản sửa riêng | PASS |
| 16 | Người duyệt phòng mới đọc bản sửa | PASS |
| 17 | So sánh gốc không lộ mô tả/thành phần cũ | PASS |
| 18 | So sánh đánh dấu đúng nhóm thay đổi | PASS |
| 19 | Người mới chỉ thấy root bận trước duyệt | PASS |
| 20 | Người mới được xem đề nghị liên quan | PASS |
| 21 | Phòng cũ không thấy bản sửa trong hộp duyệt | PASS |
| 22 | Phòng cũ không được duyệt thay phòng mới | PASS |
| 23 | Người duyệt phòng mới chấp thuận | PASS |
| 24 | Duyệt đổi current nguyên tử sang bản mới | PASS |
| 25 | Chỉ còn một phiên bản hiệu lực của root | PASS |
| 26 | Phòng cũ được giải phóng sau duyệt | PASS |
| 27 | Người cũ mất bận do lịch này | PASS |
| 28 | Người mới có bận sau duyệt | PASS |
| 29 | Người cũ không đọc root chi tiết sau thay đổi | PASS |
| 30 | Người duyệt phòng cũ không lấy revision mới | PASS |
| 31 | Người duyệt phòng cũ vẫn xem được bản lịch sử cũ | PASS |
| 32 | Audit phòng cũ chỉ thông báo giải phóng chỗ | PASS |
| 33 | Audit phòng cũ không lộ nội dung hoặc revision mới | PASS |
| 34 | Thông báo giải phóng gắn revision cũ | PASS |
| 35 | Thông báo giải phóng đến người cũ/phòng cũ | PASS |
| 36 | Thông báo giải phóng không cấp nội dung mới cho người mới | PASS |
| 37 | Retry duyệt sửa không tạo thông báo lần nữa | PASS |
| 38 | Mỗi đề nghị chỉ một event giải phóng | PASS |
| 39 | Bản mới bị hủy không mở root riêng tư cho người cũ | PASS |
| 40 | Người cũ vẫn tra cứu được revision cũ sau hủy bản mới | PASS |
| 41 | Từ chối bản sửa được xử lý | PASS |
| 42 | Từ chối bản sửa giữ current cũ | PASS |
| 43 | Rút bản sửa được xử lý | PASS |
| 44 | Rút bản sửa giữ lịch gốc | PASS |
| 45 | Revision không tái dùng số sau bản sửa bị từ chối/rút | PASS |
| 46 | Không chuyển họp thành công tác khi sửa | PASS |
| 47 | Chỗ mới bị duyệt giữ trong lúc chờ chặn sửa | PASS |
| 48 | Xung đột không tự từ chối đề nghị sửa | PASS |
| 49 | Mất chỗ mới vẫn giữ chỗ gốc | PASS |
| 50 | Có đề nghị chờ không nhận bản sửa khác | PASS |
| 51 | Ngay lúc gửi cũng chặn nếu chỗ mới đã giữ | PASS |
| 52 | Đổi sang sớm hơn hết hạn theo giờ mới | PASS |
| 53 | Đổi sang muộn hơn vẫn hết hạn theo giờ gốc | PASS |
| 54 | Duyệt bản sửa đến hạn ghi EXPIRED | PASS |
| 55 | Bản sửa hết hạn không bỏ lịch gốc | PASS |
| 56 | Người tham gia không hủy họp thay người tạo | PASS |
| 57 | Hủy họp cần lý do | PASS |
| 58 | Hủy họp trả receipt không có proposal mới | PASS |
| 59 | Hủy họp giữ current cho lịch sử | PASS |
| 60 | Hủy họp giải phóng phòng và đệm | PASS |
| 61 | Hủy họp giải phóng bận của người | PASS |
| 62 | Hủy họp đồng thời vô hiệu bản sửa chờ | PASS |
| 63 | Không duyệt lại bản sửa để khôi phục lịch hủy | PASS |
| 64 | Root đã hủy ngoài quyền trả 404 | PASS |
| 65 | Lịch hủy không còn thao tác sửa/hủy | PASS |
| 66 | Retry hủy họp trả lại receipt cũ | PASS |
| 67 | Retry hủy không nhân đôi event | PASS |
| 68 | Lý do hủy họp được lưu | PASS |
| 69 | Công tác có đề nghị hủy, không hủy trực tiếp | PASS |
| 70 | Không dùng đường hủy họp cho công tác | PASS |
| 71 | Gửi hủy công tác trả 201 | PASS |
| 72 | Chờ hủy công tác vẫn có hiệu lực | PASS |
| 73 | Đề nghị hủy không tạo revision giả | PASS |
| 74 | CANCEL trả candidate null và base comparison | PASS |
| 75 | Đề nghị hủy và sửa loại trừ nhau | PASS |
| 76 | Không tự duyệt hủy công tác | PASS |
| 77 | Không có phạm vi không duyệt hủy công tác | PASS |
| 78 | Từ chối hủy giữ công tác hoạt động | PASS |
| 79 | Sau từ chối hủy công tác vẫn hiệu lực | PASS |
| 80 | Rút hủy công tác không vi phạm CHECK reason | PASS |
| 81 | Rút hủy không giải phóng công tác | PASS |
| 82 | Lý do hủy ban đầu có lịch sử riêng không bị ghi đè | PASS |
| 83 | Chấp thuận hủy công tác thành công | PASS |
| 84 | Chấp thuận hủy mới giải phóng bận | PASS |
| 85 | Lý do hủy công tác lấy từ đề nghị đã gửi | PASS |
| 86 | Retry duyệt hủy không bị lịch đã hủy chặn | PASS |
| 87 | Retry gửi hủy sau khi lịch đã hủy vẫn trả ID cũ | PASS |
| 88 | Sửa công tác cũng giữ nguyên bản gốc trong lúc chờ | PASS |
| 89 | Duyệt sửa công tác thành công | PASS |
| 90 | Sửa công tác áp dụng địa điểm mới sau duyệt | PASS |
| 91 | Không tự chuyển phòng ban của lịch sử công tác | PASS |
| 92 | Sweep hết hạn xử lý cả CHANGE và CANCEL | PASS |
| 93 | CHANGE hết hạn giữ lịch gốc | PASS |
| 94 | CANCEL hết hạn không hủy công tác | PASS |
| 95 | CANCEL hết hạn có reason hợp lệ | PASS |
| 96 | Không hủy họp đã bắt đầu | PASS |
| 97 | Không sửa lịch gốc đã bắt đầu dù giờ mới còn xa | PASS |
| 98 | Lỗi khi duyệt sửa giữ current gốc | PASS |
| 99 | Lỗi khi duyệt sửa giữ PENDING | PASS |
| 100 | Lỗi hủy họp hoàn tác trạng thái hủy | PASS |
| 101 | Lỗi hủy họp hoàn tác cả việc vô hiệu bản sửa | PASS |
| 102 | Hai gửi sửa đồng thời chỉ một đề nghị được lưu | PASS |
| 103 | Hai gửi sửa không tạo hai revision mới | PASS |
| 104 | Duyệt sửa và hủy họp cạnh tranh chỉ một thắng | PASS |
| 105 | Không khôi phục lịch đã hủy bằng bản sửa cạnh tranh | PASS |
| 106 | Hai đổi phòng ngược chiều hợp lệ cùng hoàn thành | PASS |
| 107 | Cả hai root chỉ có một current revision | PASS |
| 108 | Hai bản sửa tranh cùng chỗ mới chỉ một được duyệt | PASS |
| 109 | Bản sửa thua vẫn giữ lịch cũ | PASS |
| 110 | Không mất bất kỳ lịch gốc nào ngoài bản thay thế | PASS |
| 111 | OpenAPI hiện công bố 50 thao tác | PASS |

</details>

<details>
<summary>Tài liệu họp — backend: 104/104</summary>

Nguồn: [verification/documents-result.json](verification/documents-result.json).

| STT | Nội dung | Kết quả |
|---|---|---|
| 1 | Tải lên/xuống đúng byte định dạng pdf | PASS |
| 2 | Không lộ storage key/hash pdf | PASS |
| 3 | Tải lên/xuống đúng byte định dạng docx | PASS |
| 4 | Không lộ storage key/hash docx | PASS |
| 5 | Tải lên/xuống đúng byte định dạng pptx | PASS |
| 6 | Không lộ storage key/hash pptx | PASS |
| 7 | Tải lên/xuống đúng byte định dạng xlsx | PASS |
| 8 | Không lộ storage key/hash xlsx | PASS |
| 9 | Tải lên/xuống đúng byte định dạng jpg | PASS |
| 10 | Không lộ storage key/hash jpg | PASS |
| 11 | Tải lên/xuống đúng byte định dạng jpeg | PASS |
| 12 | Không lộ storage key/hash jpeg | PASS |
| 13 | Tải lên/xuống đúng byte định dạng png | PASS |
| 14 | Không lộ storage key/hash png | PASS |
| 15 | Tệp không đổi phiên bản lịch | PASS |
| 16 | MIME tải xuống an toàn | PASS |
| 17 | Tải xuống dạng attachment | PASS |
| 18 | nosniff và no-store | PASS |
| 19 | Tải xuống cần đăng nhập | PASS |
| 20 | Quyền đọc ADMIN | PASS |
| 21 | Quyền đọc ROGUE | PASS |
| 22 | Quyền đọc EMP2 | PASS |
| 23 | Quyền đọc LEAD2 | PASS |
| 24 | Chỉ chủ lịch tải lên SHARED | PASS |
| 25 | Chỉ chủ lịch tải lên LEAD1 | PASS |
| 26 | Chỉ chủ lịch tải lên ADMIN | PASS |
| 27 | Danh sách không lộ lịch ngoài quyền | PASS |
| 28 | Phân trang đúng số lượng | PASS |
| 29 | Chặn tệp bad.exe | PASS |
| 30 | Chặn tệp bad.pdf | PASS |
| 31 | Chặn tệp bad.png | PASS |
| 32 | Chặn tệp empty.pdf | PASS |
| 33 | Chặn tệp bad.docx | PASS |
| 34 | Chặn tệp aaaaaaaaaaaaaaaaaaaa | PASS |
| 35 | Làm sạch đường dẫn và ký tự tên tệp | PASS |
| 36 | Chặn JSON thay multipart | PASS |
| 37 | Chặn metadata sai | PASS |
| 38 | Chặn metadata quá dài | PASS |
| 39 | Chặn hai payload file | PASS |
| 40 | Chấp nhận đúng 20 MiB | PASS |
| 41 | Chặn hơn 20 MiB | PASS |
| 42 | Chặn chunked vượt giới hạn | PASS |
| 43 | Chặn zip traversal | PASS |
| 44 | Chặn XML entity | PASS |
| 45 | Chặn macro | PASS |
| 46 | Chặn zip bomb | PASS |
| 47 | Bộ lọc giấu latest không cấp thao tác dùng expected cũ | PASS |
| 48 | Xem mọi ngữ cảnh cho chủ lịch quản lý latest | PASS |
| 49 | Người cũ không thấy tên/tệp mới | PASS |
| 50 | Người mới không thấy nhãn/tệp cũ | PASS |
| 51 | Nhãn an toàn dùng tên phiên bản được phép | PASS |
| 52 | Phiên bản mới chỉ thấy một tệp | PASS |
| 53 | Người cũ không tải được v2 | PASS |
| 54 | Người mới không tải được v1 | PASS |
| 55 | Người duyệt phòng cũ không tải được v2 | PASS |
| 56 | Người duyệt phòng mới tải v2 | PASS |
| 57 | Version endpoint lọc trước phân trang | PASS |
| 58 | Không gắn phiên bản sang lịch khác | PASS |
| 59 | Chặn expected latest cũ | PASS |
| 60 | Duyệt đổi lịch có tài liệu | PASS |
| 61 | Bản cũ chỉ đọc | PASS |
| 62 | Bản mới giữ tài liệu | PASS |
| 63 | Không tự chuyển tệp cũ | PASS |
| 64 | Thêm version từ tài liệu cũ vào bản lịch mới | PASS |
| 65 | Cho bổ sung biên bản sau cuộc họp | PASS |
| 66 | Hai phiên bản đồng thời chỉ một thắng | PASS |
| 67 | Ẩn kiểm tra latest | PASS |
| 68 | Chủ lịch ẩn tài liệu | PASS |
| 69 | Danh sách mặc định loại tệp đã ẩn | PASS |
| 70 | Lịch sử vẫn tải được tệp ẩn | PASS |
| 71 | Không thêm version vào tệp ẩn | PASS |
| 72 | Tệp ẩn có thể tra cứu lịch sử | PASS |
| 73 | Audit tài liệu không lộ tên riêng | PASS |
| 74 | Audit có sự kiện tài liệu | PASS |
| 75 | WITHDRAWN không ghi thêm tài liệu | PASS |
| 76 | WITHDRAWN vẫn đọc lịch sử | PASS |
| 77 | REJECTED không ghi thêm tài liệu | PASS |
| 78 | REJECTED vẫn đọc lịch sử | PASS |
| 79 | EXPIRED không ghi thêm tài liệu | PASS |
| 80 | EXPIRED vẫn đọc lịch sử | PASS |
| 81 | Hủy họp đã có tài liệu | PASS |
| 82 | Họp đã hủy chỉ đọc | PASS |
| 83 | Tệp vẫn đọc sau hủy | PASS |
| 84 | Không tải tệp lên công tác | PASS |
| 85 | Hủy đồng thời upload vẫn hoàn tất | PASS |
| 86 | Upload cạnh tranh hủy chỉ commit trước hoặc bị chặn | PASS |
| 87 | Sau hủy không ghi thêm tệp | PASS |
| 88 | Kiểm tra lại quyền sau khi đã nhận tệp | PASS |
| 89 | Phiên bị hạn chế không để byte staging | PASS |
| 90 | Metadata JSON dạng part có Content-Type | PASS |
| 91 | Lỗi sau publish được chuẩn hóa | PASS |
| 92 | Lỗi lưu rollback metadata | PASS |
| 93 | Lỗi lưu dọn byte chưa commit | PASS |
| 94 | Không còn tệp staging | PASS |
| 95 | Không xóa byte có tham chiếu DB | PASS |
| 96 | Tệp hỏng trả lỗi an toàn | PASS |
| 97 | Tệp thiếu trả lỗi an toàn | PASS |
| 98 | Cleanup mặc định chỉ xem trước | PASS |
| 99 | Cleanup bỏ qua upload đang khóa | PASS |
| 100 | Cleanup dọn orphan quá hạn | PASS |
| 101 | Cleanup giữ byte có DB và tệp mới | PASS |
| 102 | Cleanup không xóa lịch sử ẩn | PASS |
| 103 | OpenAPI đủ 50 thao tác | PASS |
| 104 | OpenAPI upload trả DocumentVersionView | PASS |

</details>

<details>
<summary>Báo cáo phòng — backend: 43/43</summary>

Nguồn: [verification/reports-result.json](verification/reports-result.json).

| STT | Nội dung | Kết quả |
|---|---|---|
| 1 | Không phiên không đọc báo cáo | PASS |
| 2 | Nhân viên không có quyền báo cáo | PASS |
| 3 | Người duyệt không được phân công có báo cáo rỗng | PASS |
| 4 | Người duyệt chỉ thấy phòng được giao | PASS |
| 5 | Admin tổng hợp được cả hai phòng | PASS |
| 6 | Bộ lọc gồm phòng ngoài quyền từ chối cả yêu cầu | PASS |
| 7 | Phòng không tồn tại không suy ra dữ liệu | PASS |
| 8 | Khoảng ngược | PASS |
| 9 | Bằng nhau | PASS |
| 10 | Thiếu offset | PASS |
| 11 | Quá 366 ngày | PASS |
| 12 | Lặp phòng chỉ tính một lần | PASS |
| 13 | Báo cáo rỗng vẫn tính giờ phục vụ | PASS |
| 14 | Chưa có đặt phòng cho tỷ lệ 0 | PASS |
| 15 | Đếm chỉ current, không đếm bản cũ và pending | PASS |
| 16 | Số lượt hủy tách riêng | PASS |
| 17 | Giờ họp loại hủy và bản cũ | PASS |
| 18 | Giờ chuyển tiếp tách riêng | PASS |
| 19 | Tổng giờ phục vụ theo từng phòng | PASS |
| 20 | Tỷ lệ tổng dùng trọng số | PASS |
| 21 | Tỷ lệ từng phòng | PASS |
| 22 | Không trả lịch/nội dung/người/tệp riêng | PASS |
| 23 | Nhãn là kế hoạch | PASS |
| 24 | Cắt giờ họp theo kỳ | PASS |
| 25 | Không đếm hủy bắt đầu đúng mốc cuối | PASS |
| 26 | Cắt giờ phục vụ theo kỳ | PASS |
| 27 | Kỳ chỉ có đệm không tính thêm lượt họp | PASS |
| 28 | Cắt đệm vào kỳ | PASS |
| 29 | Đệm không vào tử số | PASS |
| 30 | Offset tương đương cho cùng kết quả | PASS |
| 31 | Giờ phục vụ dùng lịch sử cấu hình, chia giữa ngày | PASS |
| 32 | Giờ đặt vẫn báo riêng phần ngoài giờ phục vụ | PASS |
| 33 | Tử số chỉ lấy phần trong giờ phục vụ | PASS |
| 34 | Đệm lấy cấu hình tại giờ bắt đầu từng họp | PASS |
| 35 | Ngừng nhận mới không xóa mẫu số lịch sử | PASS |
| 36 | Ngày đóng không có giờ phục vụ | PASS |
| 37 | Mẫu số 0 trả null | PASS |
| 38 | Ngày ngoại lệ thay giờ tuần | PASS |
| 39 | Họp trong giờ ngoại lệ tính tỷ lệ đúng | PASS |
| 40 | Snapshot không trộn bản ghi vừa commit | PASS |
| 41 | Lần báo cáo sau thấy cập nhật mới | PASS |
| 42 | Thu hồi phạm vi có hiệu lực ngay | PASS |
| 43 | OpenAPI hoàn thành 50 thao tác | PASS |

</details>

<details>
<summary>Worker email — backend: 64/64</summary>

Nguồn: [verification/notifications-result.json](verification/notifications-result.json).

| STT | Nội dung | Kết quả |
|---|---|---|
| 1 | SMTP mặc định không gửi thư | PASS |
| 2 | Thiếu host | PASS |
| 3 | URL không hợp lệ | PASS |
| 4 | Không chấp nhận plain ngầm | PASS |
| 5 | Mật khẩu không có trong repr cấu hình | PASS |
| 6 | Disable giữ nguyên hàng chờ | PASS |
| 7 | Không đổi trạng thái khi disabled | PASS |
| 8 | SMTP thật TCP ngoài transaction khóa SQL | PASS |
| 9 | Một delivery gửi đúng một thư | PASS |
| 10 | Một địa chỉ người nhận | PASS |
| 11 | Email có liên kết đăng nhập đúng hồ sơ | PASS |
| 12 | Email không có nội dung lịch riêng | PASS |
| 13 | Email không đính kèm tệp | PASS |
| 14 | Attempt được ghi SMTP_ACCEPTED | PASS |
| 15 | Không gửi lại delivery đã được nhận | PASS |
| 16 | Không tạo SMTP lần hai | PASS |
| 17 | Lỗi SMTP lần 1 | PASS |
| 18 | Số lần gửi 1 | PASS |
| 19 | Chỉ lưu mã lỗi an toàn 1 | PASS |
| 20 | Hẹn lại từ lỗi đầu 1 | PASS |
| 21 | Chưa đến hạn không gửi 1 | PASS |
| 22 | Lỗi SMTP lần 2 | PASS |
| 23 | Số lần gửi 2 | PASS |
| 24 | Chỉ lưu mã lỗi an toàn 2 | PASS |
| 25 | Hẹn lại từ lỗi đầu 2 | PASS |
| 26 | Chưa đến hạn không gửi 2 | PASS |
| 27 | Lỗi SMTP lần 3 | PASS |
| 28 | Số lần gửi 3 | PASS |
| 29 | Chỉ lưu mã lỗi an toàn 3 | PASS |
| 30 | Hẹn lại từ lỗi đầu 3 | PASS |
| 31 | Chưa đến hạn không gửi 3 | PASS |
| 32 | Lỗi SMTP lần 4 | PASS |
| 33 | Số lần gửi 4 | PASS |
| 34 | Chỉ lưu mã lỗi an toàn 4 | PASS |
| 35 | Bốn lần lỗi kết thúc FAILED | PASS |
| 36 | Không lộ phản hồi SMTP vào DB | PASS |
| 37 | Đủ bốn attempt lưu vết | PASS |
| 38 | Không gửi lần thứ năm | PASS |
| 39 | Không gửi thông báo chờ đã bị rút | PASS |
| 40 | Bỏ qua stale có mã lý do | PASS |
| 41 | Bỏ qua trước gửi không tạo attempt | PASS |
| 42 | Không gửi cho tài khoản khóa | PASS |
| 43 | Thu hồi scope ngăn gửi | PASS |
| 44 | Lý do ngoài quyền không có dữ liệu riêng | PASS |
| 45 | Kiểm tra lại người nhận ngay trước SMTP | PASS |
| 46 | Đổi email sau claim không gửi địa chỉ cũ | PASS |
| 47 | Hai worker chỉ một claim delivery | PASS |
| 48 | Không gửi trùng khi hai worker cạnh tranh | PASS |
| 49 | QUIT lỗi sau DATA accepted không tạo retry | PASS |
| 50 | QUIT lỗi vẫn lưu accepted | PASS |
| 51 | Crash sau SMTP giữ attempt chưa rõ kết quả | PASS |
| 52 | Lease hết hạn được thu hồi | PASS |
| 53 | Attempt cũ được đánh dấu UNKNOWN | PASS |
| 54 | Thử lại sau crash có thể gửi lại | PASS |
| 55 | Message-ID ổn định qua lần thử lại | PASS |
| 56 | Ghi nhận giới hạn có thể trùng sau crash | PASS |
| 57 | Worker cũ không ghi đè lease mới | PASS |
| 58 | Đúng audience SCHEDULE_RELEASED | PASS |
| 59 | Không lộ thông tin phòng/người mới trong email SCHEDULE_RELEASED | PASS |
| 60 | Đúng audience PROPOSAL_APPROVED | PASS |
| 61 | Không lộ thông tin phòng/người mới trong email PROPOSAL_APPROVED | PASS |
| 62 | SMTP không thay đổi trạng thái lịch | PASS |
| 63 | Tóm tắt thư đã gửi chỉ cho người gửi | PASS |
| 64 | Lỗi được phân loại không có raw text | PASS |

</details>

<details>
<summary>Gửi/duyệt/rút — React DOM: 10/10</summary>

Nguồn: [verification/scheduling-dom-result.json](verification/scheduling-dom-result.json).

| STT | Nội dung | Kết quả |
|---|---|---|
| 1 | Nhân viên thấy nút tạo yêu cầu và không có tab quản trị | PASS |
| 2 | Kiểm tra phương án qua HTTP/MySQL thật | PASS |
| 3 | Mất phản hồi sau commit hiện thao tác thử lại | PASS |
| 4 | Thử lại giữ nguyên khóa chống lặp | PASS |
| 5 | Hồ sơ đã lưu vẫn chờ duyệt | PASS |
| 6 | Người duyệt xác nhận lịch bằng giao diện | PASS |
| 7 | Lịch đã duyệt xuất hiện ở hồ sơ lịch | PASS |
| 8 | Hồ sơ hiện lịch sử xử lý | PASS |
| 9 | HTTP 503 sau commit cũng giữ nguyên key khi thử lại | PASS |
| 10 | Người gửi rút yêu cầu trên giao diện | PASS |

</details>

<details>
<summary>Sửa/hủy/lịch sử — React DOM: 14/14</summary>

Nguồn: [verification/amendments-dom-result.json](verification/amendments-dom-result.json).

| STT | Nội dung | Kết quả |
|---|---|---|
| 1 | Chủ lịch mở biểu mẫu sửa từ phiên bản hiện tại | PASS |
| 2 | Retry gửi sửa giữ nguyên key sau commit | PASS |
| 3 | Đề nghị sửa hiển thị so sánh gốc | PASS |
| 4 | Bản sửa chờ vẫn giữ phòng gốc | PASS |
| 5 | Người duyệt chấp thuận bản sửa qua giao diện | PASS |
| 6 | Chủ lịch xem lại nội dung phiên bản cũ | PASS |
| 7 | Receipt hủy họp proposal null được xử lý đúng | PASS |
| 8 | Retry hủy họp giữ nguyên key | PASS |
| 9 | Lịch đã hủy không còn nút sửa hoặc hủy | PASS |
| 10 | Đề nghị hủy công tác hiển thị base khi candidate null | PASS |
| 11 | Chờ duyệt hủy vẫn giữ công tác | PASS |
| 12 | Người duyệt chấp thuận hủy công tác qua giao diện | PASS |
| 13 | Người cũ vẫn xem lịch sử khi bản mới riêng tư đã hủy | PASS |
| 14 | Lịch sử không lộ bản mới hoặc quyền sửa hủy | PASS |

</details>

<details>
<summary>Tài liệu — React DOM: 15/15</summary>

Nguồn: [verification/documents-dom-result.json](verification/documents-dom-result.json).

| STT | Nội dung | Kết quả |
|---|---|---|
| 1 | Chủ lịch tải tài liệu lên qua FormData thật | PASS |
| 2 | Thêm phiên bản giữ cả tệp cũ | PASS |
| 3 | Tải xuống dùng Bearer fetch và đúng byte | PASS |
| 4 | Tên tải xuống giữ tiếng Việt/định dạng | PASS |
| 5 | URL tạm được thu hồi | PASS |
| 6 | Ẩn tài liệu với lý do, danh sách mặc định bỏ tệp | PASS |
| 7 | Lịch sử tệp ẩn vẫn xem và tải được | PASS |
| 8 | Mất phản hồi không cho gửi lặp mù | PASS |
| 9 | Tải lại đối chiếu đúng một bản đã commit | PASS |
| 10 | Người tham gia đọc tài liệu, không có biểu mẫu ghi | PASS |
| 11 | Họp đã hủy chỉ xem tài liệu | PASS |
| 12 | Người cũ tải tệp cũ khi bản mới riêng tư vẫn đang có hiệu lực | PASS |
| 13 | Không lộ nội dung bản mới đang hoạt động | PASS |
| 14 | Người cũ tải tài liệu khi chỉ còn quyền bản lịch sử | PASS |
| 15 | Tài liệu lịch sử không cấp lại quyền ghi | PASS |

</details>

<details>
<summary>Báo cáo và link email — React DOM: 10/10</summary>

Nguồn: [verification/reports-dom-result.json](verification/reports-dom-result.json).

| STT | Nội dung | Kết quả |
|---|---|---|
| 1 | Nhân viên không có mục báo cáo | PASS |
| 2 | Người phụ trách xem được báo cáo trong phạm vi | PASS |
| 3 | Giao diện hiển thị một xác nhận và một hủy | PASS |
| 4 | Giờ họp và giờ đệm tách riêng | PASS |
| 5 | Nhãn báo cáo không khẳng định sử dụng thực tế | PASS |
| 6 | Khoảng sai không giữ kết quả cũ | PASS |
| 7 | Admin thấy số liệu tổng hợp, không có nội dung lịch | PASS |
| 8 | Liên kết email mở đúng đề nghị sau đăng nhập | PASS |
| 9 | Liên kết không giữ token hoặc ID trên URL sau mở | PASS |
| 10 | Liên kết lịch kiểm tra quyền người tham gia | PASS |

</details>


<a id="business"></a>
## 12. Phụ lục: đặc tả nghiệp vụ, phân quyền và Use Case

Đặc tả nghiệp vụ bản chốt 1.3 được hợp nhất nguyên các quyết định QD/BR/DP, ma trận quyền, 20 Use Case và 44 tiêu chí nghiệm thu dưới đây. Số phiên bản đặc tả 1.3 khác số phiên bản source 1.0.0. Các tiêu chí nghiệp vụ không tự trở thành PASS; kết quả đã chạy và giới hạn nằm ở phần 11.

### 1. Mục tiêu và căn cứ

Hệ thống hỗ trợ một đơn vị giả lập có nhiều phòng ban quản lý lịch họp, đặt phòng họp và đăng ký lịch công tác. Sản phẩm phục vụ báo cáo và demo học phần; không giả định đang triển khai cho một cơ quan thực tế cụ thể.

Căn cứ chính là file DS_Tieu luan_OOP_App(2).pdf, trang 1 và trang 3: sử dụng ngôn ngữ chính Python, xây dựng RESTful API có xác thực, kết nối frontend với backend; có sơ đồ Use Case, Lớp, Tuần tự, Hoạt động; có báo cáo và demo. HTTT10 gồm đặt phòng họp, đăng ký lịch công tác, thông báo email, tài liệu họp và thống kê sử dụng phòng.

Các nội dung OOP, SOLID, mẫu thiết kế, kiến trúc phân tầng, ORM, xử lý ngoại lệ, ghi log và kiểm thử được đối chiếu với đề cương và các chủ đề môn học đã gửi. Không tự bổ sung yêu cầu AI hoặc số lượng mẫu thiết kế cố định.

### 2. Các quyết định đã thống nhất

| Mã | Nội dung | Quyết định |
|---|---|---|
| QD-01 | Backend | Python + FastAPI |
| QD-02 | Frontend | ReactJS, kết nối backend qua RESTful API |
| QD-03 | Truy cập dữ liệu | SQLAlchemy |
| QD-04 | Xác thực | JWT |
| QD-05 | Cơ sở dữ liệu | MySQL |
| QD-06 | Môi trường | Windows, có Docker, demo qua mạng LAN |
| QD-07 | Email | Gửi đến hộp thư thật |
| QD-08 | Phòng bị đặt đồng thời | Không cho hai lịch có hiệu lực chồng lấn trong cùng phòng |
| QD-09 | Thời gian chuyển tiếp | Mặc định 15 phút giữa hai cuộc họp trong cùng phòng, cấu hình riêng theo phòng |
| QD-10 | Yêu cầu chờ duyệt | Chưa giữ phòng; chỉ giữ sau khi được duyệt |
| QD-11 | Phân quyền | Ba nhóm: Nhân viên, Người phê duyệt, Admin; người duyệt có phạm vi phân công |
| QD-12 | Cấp duyệt | Mỗi loại yêu cầu một cấp duyệt |
| QD-13 | Tự duyệt | Người gửi không tự duyệt yêu cầu của mình; cần người duyệt thay được phân công |
| QD-14 | Xung đột người tham gia | Chặn nếu một người bắt buộc tham gia cả hai lịch chồng giờ; cảnh báo nếu người đó chỉ tham gia tùy chọn ở ít nhất một lịch |
| QD-15 | Lịch chờ và người tham gia | Chỉ cảnh báo, chưa coi là đã giữ lịch người tham gia |
| QD-16 | Sửa lịch đã duyệt | Phải duyệt lại; lịch cũ tiếp tục có hiệu lực trong lúc chờ |
| QD-17 | Duyệt bản sửa | Chỉ thay thế lịch cũ và giải phóng phòng cũ khi bản sửa được duyệt thành công |
| QD-18 | Thời điểm sửa | Chỉ áp dụng quy trình sửa này khi lịch gốc chưa bắt đầu; kiểm tra lại lúc duyệt |
| QD-19 | Email thất bại | Giữ kết quả lưu lịch thành công; ghi nhận lỗi để gửi lại |
| QD-20 | Thống kê | Dựa trên lịch đặt đã xác nhận; không coi đây là bằng chứng sử dụng phòng thực tế |
| QD-21 | Hủy lịch họp đã duyệt | Người tạo được hủy trước giờ bắt đầu; giải phóng phòng và gửi thông báo sau khi lưu thành công |
| QD-22 | Hủy lịch công tác đã duyệt | Phải được người phụ trách đúng phạm vi duyệt; lịch gốc còn hiệu lực trong lúc chờ |
| QD-23 | Rút yêu cầu chờ duyệt | Người gửi được rút; nếu rút đề nghị sửa/hủy thì giữ nguyên lịch gốc |
| QD-24 | Xem chi tiết lịch | Người tạo, người tham gia và người duyệt đúng phạm vi được xem chi tiết; người khác chỉ xem bận/rảnh |
| QD-25 | Admin và nội dung lịch | Quyền quản trị kỹ thuật không tự cấp quyền xem toàn bộ chi tiết lịch |
| QD-26 | Lưu vết hủy | Giữ lịch đã hủy, người thực hiện, thời điểm và lý do; không xóa hẳn lịch sử |
| QD-27 | Đề nghị sửa và hủy công tác | Mỗi lịch chỉ có một đề nghị thay đổi hoặc hủy đang chờ; rút đề nghị cũ trước khi gửi loại khác |
| QD-28 | Hủy họp đang có đề nghị sửa | Hủy lịch họp đồng thời làm đề nghị sửa đang chờ hết hiệu lực |

### 3. Nhóm quyền và phạm vi phê duyệt

#### 3.1. Nhân viên

Nhân viên tạo yêu cầu họp/đặt phòng, đăng ký lịch công tác, xem chi tiết lịch mình tạo hoặc tham gia, xem bận/rảnh của các lịch khác và đề nghị chỉnh sửa lịch của mình. Người tạo được hủy lịch họp trước giờ bắt đầu; hủy lịch công tác đã duyệt cần người phụ trách phê duyệt. Quy trình cụ thể tại BR-07 và BR-08.

#### 3.2. Người phê duyệt

Người phê duyệt được phân công một hoặc cả hai nhiệm vụ sau:

| Nhiệm vụ | Phạm vi | Ví dụ người đảm nhận |
|---|---|---|
| Duyệt đặt phòng họp | Các phòng họp được phân công quản lý | Cán bộ hành chính/văn phòng |
| Duyệt lịch công tác | Các phòng ban được phân công | Trưởng phòng hoặc người được ủy quyền |

Trưởng phòng không mặc nhiên được duyệt mọi phòng họp. Người phụ trách phòng họp không mặc nhiên được duyệt công tác của mọi phòng ban. Một tài khoản có thể được giao cả hai nhiệm vụ. Người phê duyệt được thực hiện chức năng nhân viên nếu được cấp quyền tương ứng.

#### 3.3. Admin

Admin quản lý tài khoản, phòng ban, danh mục phòng họp, cấu hình phòng và phân công quyền duyệt. Quyền quản trị kỹ thuật không tự động tạo quyền phê duyệt nghiệp vụ; muốn duyệt phải được phân công quyền tương ứng.

### 4. Quy tắc kiểm tra lịch

#### BR-01. Khoảng thời gian hợp lệ

Thời điểm bắt đầu phải trước thời điểm kết thúc. Giờ phục vụ, thời lượng và thời hạn đặt áp dụng theo DP-01 và DP-02 đã chốt.

#### BR-02. Xung đột phòng và thời gian chuyển tiếp

Phòng được xem là chưa sẵn sàng cho cuộc họp kế tiếp trong suốt cuộc họp đã xác nhận và khoảng chuyển tiếp sau đó. Khoảng chuyển tiếp mặc định là 15 phút, cấu hình theo phòng. Khi kiểm tra một yêu cầu, phải bảo đảm khoảng cách phù hợp với cả lịch trước và lịch sau, không chỉ kiểm tra hai giờ bắt đầu có bằng nhau hay không.

Ví dụ phòng A đã có lịch 09:00–10:00, với khoảng chuyển tiếp 15 phút:

| Yêu cầu mới | Kết quả kiểm tra phòng |
|---|---|
| 09:30–10:30 | Xung đột giờ họp |
| 10:00–11:00 | Xung đột khoảng chuyển tiếp |
| 10:10–11:00 | Chưa đủ khoảng chuyển tiếp |
| 10:15–11:00 | Không xung đột với lịch trên; vẫn phải kiểm tra các điều kiện khác |

Không cộng thành hai khoảng 15 phút trước và sau để bắt buộc giãn 30 phút giữa cùng một cặp cuộc họp. Thời lượng họp và thời gian chuyển tiếp phải được phân biệt khi thống kê.

#### BR-03. Yêu cầu chờ duyệt chưa giữ chỗ

Khi gửi yêu cầu, kiểm tra phòng và các lịch đã xác nhận. Nếu đã có xung đột thì báo lỗi để người gửi chọn lại. Các yêu cầu chờ duyệt có thể trùng nhau; hệ thống cảnh báo rõ rằng yêu cầu chưa giữ phòng. Gửi sớm hơn không tự động bảo đảm được duyệt trước.

Khi duyệt, phải kiểm tra lại dữ liệu hiện tại. Chỉ sau khi duyệt thành công, lượt đặt phòng mới có hiệu lực. Nếu hai thao tác duyệt cạnh tranh cùng một phòng trong khoảng thời gian xung đột, chỉ một thao tác được xác nhận thành công.

#### BR-04. Xung đột người tham gia

Kiểm tra theo danh tính người tham gia, độc lập với kiểm tra phòng. Ví dụ Hải được xếp họp tại phòng A lúc 09:00–10:00 và phòng B lúc 09:30–10:30: hai phòng khác nhau nhưng Hải bị trùng lịch 09:30–10:00.

Lịch công tác bên ngoài cũng được tính khi kiểm tra xung đột. Ví dụ Hải có lịch công tác đã duyệt 08:00–11:00 thì một cuộc họp 09:00–10:00 có Hải là người bắt buộc tham gia sẽ xung đột.

Người chủ trì là người bắt buộc. Người được đăng ký đi công tác là người bắt buộc. Người được mời họp có thể thuộc diện bắt buộc hoặc tùy chọn. Nếu một người bắt buộc tham gia cả hai lịch đã xác nhận bị chồng giờ, không cho duyệt lịch mới. Nếu có ít nhất một bên là tùy chọn, hiển thị cảnh báo. Lịch đang chờ duyệt chỉ tạo cảnh báo. Kiểm tra lại khi duyệt và khi duyệt thay đổi.

Khoảng đệm phòng không tự động được áp dụng thành khoảng đệm di chuyển cá nhân; vấn đề di chuyển giữa các địa điểm được ghi tại mục 8.

#### BR-05. Lưu dữ liệu và gửi email

Việc xác nhận lịch và các dữ liệu liên quan phải được lưu nhất quán. Chỉ gửi thông báo xác nhận sau khi dữ liệu đã được ghi thành công. Email thất bại không làm mất lịch đã lưu; phải ghi nhận tình trạng lỗi để gửi lại. Không được thông báo gửi email thành công khi thực tế mới đưa yêu cầu vào hàng chờ gửi.

#### BR-06. Thống kê phòng

Thống kê dựa trên lịch đặt đã xác nhận, tách số lượt đã hủy và không cộng toàn bộ thời lượng của một lượt đặt đã hủy trước khi diễn ra vào tổng thời lượng họp đã lên lịch. Thời gian chuyển tiếp được tách khỏi thời lượng họp. Số liệu phản ánh kế hoạch đặt phòng; chưa đo được việc có người thực sự sử dụng phòng hay không. Công thức áp dụng tại DP-09, sử dụng giờ phục vụ DP-01 đã chốt.

#### BR-07. Hủy lịch và rút yêu cầu

**Lịch họp đã duyệt:** Người tạo được hủy toàn bộ lịch trước giờ bắt đầu, nhập lý do và xác nhận thao tác. Không cần một lượt duyệt hủy vì cần giải phóng phòng kịp thời. Hệ thống lưu trạng thái đã hủy, giải phóng lượt giữ phòng cùng khoảng chuyển tiếp của lượt đặt đó và bỏ trạng thái bận do chính lịch này tạo ra. Những lịch khác của cùng người hoặc phòng vẫn được giữ nguyên. Email được gửi đến các bên liên quan sau khi lưu thành công. Việc một người tham dự không tham gia không được coi là quyền hủy toàn bộ cuộc họp.

**Lịch công tác đã duyệt:** Người tạo gửi đề nghị hủy có lý do. Trong lúc chờ, lịch công tác gốc vẫn có hiệu lực và vẫn được tính khi kiểm tra lịch bận. Người phụ trách phòng ban đúng phạm vi được duyệt hoặc từ chối, tuân thủ nguyên tắc không tự duyệt yêu cầu của mình. Duyệt hủy thành công mới chuyển lịch gốc sang đã hủy và bỏ trạng thái bận do lịch này tạo ra. Từ chối hoặc rút đề nghị hủy thì lịch gốc không thay đổi.

Trong phiên bản đầu, luồng hủy toàn bộ chỉ áp dụng trước khi lịch gốc bắt đầu; kiểm tra thời điểm này cả khi gửi lẫn khi duyệt. Lịch đã bắt đầu hoặc kết thúc không bị xóa/hủy hồi tố bằng luồng này. Các trường hợp chấm dứt công tác đang diễn ra thuộc phạm vi cần đặc tả riêng nếu bổ sung sau.

**Yêu cầu đang chờ duyệt:** Người gửi được rút yêu cầu tạo lịch chưa được duyệt, hoặc rút đề nghị sửa/hủy của mình. Rút một yêu cầu chờ không cần duyệt. Rút yêu cầu tạo lịch làm yêu cầu đó hết hiệu lực, không giải phóng bất kỳ phòng nào của lịch khác. Rút đề nghị sửa/hủy giữ nguyên lịch gốc đã duyệt.

**Phối hợp sửa và hủy:** Với lịch công tác, chỉ tồn tại tối đa một đề nghị sửa hoặc hủy đang chờ cho cùng lịch; muốn đổi loại đề nghị phải rút đề nghị hiện tại. Với lịch họp, khi người tạo hủy cuộc họp, mọi đề nghị sửa đang chờ của lịch đó hết hiệu lực trong cùng thao tác lưu. Không được duyệt một bản sửa cũ để làm lịch đã hủy có hiệu lực trở lại. Mọi thao tác rút/duyệt/hủy đều kiểm tra lại trạng thái mới nhất; không áp dụng quyết định trên phiên bản đã thay đổi.

**Lưu lịch sử:** Giữ bản ghi lịch đã hủy, lý do, người thao tác và thời điểm. Không dùng xóa dữ liệu để thay thế cho hủy nghiệp vụ. Email thất bại không khôi phục một lịch đã hủy thành công. Các quyền hủy khẩn cấp thay người tạo của Admin/người quản lý chưa nằm trong phạm vi đã thống nhất; cần đặc tả riêng trước khi bổ sung.

#### BR-08. Quyền xem lịch và thông tin bận/rảnh

| Người truy cập | Phạm vi được xem |
|---|---|
| Chưa đăng nhập | Không truy cập lịch nội bộ |
| Người tạo lịch hoặc người có tên trong danh sách tham gia | Xem chi tiết lịch liên quan đến mình |
| Nhân viên không thuộc lịch | Xem khoảng thời gian bận/rảnh, không xem nội dung riêng của lịch |
| Người duyệt phòng họp | Xem chi tiết yêu cầu/lịch sử xử lý của các lượt đặt thuộc phòng được phân công |
| Người duyệt công tác | Xem chi tiết yêu cầu/lịch sử xử lý thuộc phòng ban được phân công |
| Admin chỉ có quyền quản trị kỹ thuật | Quản lý danh mục/cấu hình và xem bận/rảnh; không tự động xem toàn bộ nội dung lịch |

Một người có nhiều quyền được áp dụng các quyền tương ứng trong phạm vi được cấp. Lịch do mình tạo hoặc tham gia vẫn được xem chi tiết dù nằm ngoài phòng ban của mình. Người duyệt không được truy cập chi tiết lịch ngoài phạm vi chỉ bằng việc biết mã lịch.

Với nhân viên không liên quan, lịch hiển thị là “Bận” hoặc “Phòng đã được đặt” kèm thời gian, không trả tiêu đề, mô tả, danh sách tham gia, địa điểm công tác hay tài liệu của lịch đó. Phòng họp và các thuộc tính công khai của phòng vẫn có thể được xem để đặt phòng. Khoảng chuyển tiếp được thể hiện riêng là chưa sẵn sàng. Cảnh báo về yêu cầu chờ chỉ hiển thị thông tin tối thiểu, không công khai nội dung của yêu cầu khác.

Cả giao diện và API phải thực thi cùng chính sách. Đổi bộ lọc, tìm kiếm, truy cập URL trực tiếp, xem lịch sử hay mở thông báo không được làm lộ thông tin ngoài quyền. Quyền xem chi tiết lịch không tự động xác định quyền thêm/xóa/tải tài liệu. Quyền tài liệu áp dụng theo DP-06 và UC-09 đã chốt.

### 5. Đề nghị sửa lịch đã duyệt

#### 5.1. Nguyên tắc hiệu lực

Lịch đang có hiệu lực và đề nghị sửa là hai thông tin cần phân biệt. Việc gửi đề nghị sửa không làm mất phòng cũ, không đổi lịch đang công bố và không tự giữ phòng mới. Những người bắt buộc của lịch cũ vẫn được tính là bận theo lịch cũ.

#### 5.2. Luồng xử lý

1. Người tạo chọn lịch đã duyệt, còn chưa bắt đầu, rồi nhập nội dung đề nghị sửa.
2. Hệ thống kiểm tra phương án mới với lịch hiện có. Khi kiểm tra bản sửa phải loại trừ bản gốc của chính lịch đó để không báo xung đột với chính mình.
3. Nếu phương án mới đã xung đột với một lịch có hiệu lực, báo lỗi để người dùng chọn lại; lịch gốc không thay đổi.
4. Nếu kiểm tra hợp lệ, ghi nhận đề nghị sửa ở trạng thái chờ duyệt. Phương án mới chưa giữ phòng.
5. Người có quyền duyệt xem đề nghị và thực hiện duyệt hoặc từ chối theo phạm vi được phân công.
6. Trước khi chấp thuận, hệ thống kiểm tra lại thời điểm bắt đầu của lịch gốc, phòng mới, khoảng chuyển tiếp và người tham gia.
7. Nếu phát sinh xung đột trong lúc chờ, không cho thao tác duyệt thành công. Người gửi có thể chọn phương án khác để đề nghị lại; lịch gốc vẫn có hiệu lực.
8. Khi duyệt thành công, thay thế phiên bản lịch và giải phóng lượt giữ chỗ cũ trong một giao dịch nhất quán. Sau khi lưu thành công mới gửi email cập nhật.
9. Nếu đề nghị bị từ chối hoặc được rút theo quy trình tương ứng, lịch gốc vẫn giữ nguyên.

#### 5.3. Các trường hợp đổi phòng/giờ

| Tình huống | Cách xử lý | Lịch gốc |
|---|---|---|
| Phòng/giờ mới đã có lịch khác được duyệt | Báo không khả dụng ngay khi kiểm tra; người dùng chọn lại | Giữ nguyên |
| Phòng/giờ mới chỉ có yêu cầu khác đang chờ | Cảnh báo; đề nghị sửa vẫn có thể được gửi | Giữ nguyên |
| Lúc gửi còn trống, lúc duyệt đã có lịch khác được xác nhận | Không cho duyệt bản sửa | Giữ nguyên |
| Phòng/giờ mới hợp lệ và bản sửa được duyệt | Xác nhận lịch mới, giải phóng lịch cũ đồng thời | Được thay thế |
| Bản sửa bị từ chối | Không áp dụng phương án sửa | Giữ nguyên |

“Không cho duyệt do xung đột” là kết quả kiểm tra của thao tác chấp thuận; không đồng nghĩa hệ thống đã tự thực hiện một quyết định từ chối nghiệp vụ hoặc hủy lịch gốc. Tên trạng thái và cách rút/gửi lại áp dụng theo mục 9, DP-07 và UC-07/UC-08/UC-13 đã chốt.

### 6. Danh mục chức năng và phạm vi phiên bản đầu

Các chức năng trong bảng là bản phân rã để thiết kế. Những chi tiết có mã DP áp dụng chính sách tại mục 8 đã chốt. Chức năng email và kiểm tra xung đột là xử lý hỗ trợ, không tự biến thành những mục tiêu người dùng độc lập chỉ để tăng số lượng Use Case.

| Mã | Chức năng | Use Case | Căn cứ/trạng thái |
|---|---|---|---|
| FR-01 | Đăng nhập bằng tài khoản nội bộ và lấy quyền hiện hành | UC-01 | JWT đã chốt; chi tiết DP-05 |
| FR-02 | Kết thúc phiên hiện tại, dọn trạng thái giao diện | UC-19 | Đã chốt DP-05 |
| FR-03 | Đổi mật khẩu, đổi mật khẩu tạm lần đầu | UC-20 | Đã chốt DP-05 |
| FR-04 | Xem lịch cá nhân/phòng, lọc ngày và trạng thái theo quyền | UC-02 | BR-08; giờ phục vụ DP-01 |
| FR-05 | Tìm phòng theo thời gian, sức chứa và thiết bị | UC-02 | Khung đặt phòng; chi tiết DP-01/DP-04 |
| FR-06 | Tạo yêu cầu họp, chọn phòng và người bắt buộc/tùy chọn | UC-03 | BR-01 đến BR-04; DP-01/DP-02/DP-04 |
| FR-07 | Duyệt/từ chối yêu cầu đặt phòng và kiểm tra lại trước xác nhận | UC-04 | QD-08 đến QD-15; DP-07 |
| FR-08 | Đăng ký lịch công tác của cá nhân/nhóm | UC-05 | Đăng ký công tác đã chốt; phạm vi DP-03 |
| FR-09 | Duyệt/từ chối lịch công tác trong phạm vi phòng ban | UC-06 | Một cấp duyệt đã chốt; DP-03/DP-07 |
| FR-10 | Đề nghị sửa lịch đã duyệt, giữ lịch gốc trong lúc chờ | UC-07 | QD-16 đến QD-18; DP-07 |
| FR-11 | Duyệt/từ chối bản sửa, thay hiệu lực nhất quán | UC-08 | Mục 5; DP-07 |
| FR-12 | Rút yêu cầu tạo lịch/sửa/hủy đang chờ | UC-13 | QD-23; DP-07 |
| FR-13 | Hủy lịch họp trước giờ bắt đầu và giải phóng phòng | UC-14 | QD-21, QD-26, QD-28 |
| FR-14 | Gửi đề nghị hủy công tác, giữ lịch gốc trong lúc chờ | UC-15 | QD-22, QD-27 |
| FR-15 | Duyệt/từ chối đề nghị hủy công tác | UC-16 | QD-22, QD-26 |
| FR-16 | Quản lý và tải tài liệu họp theo quyền | UC-09 | Yêu cầu HTTT10; chi tiết DP-06 |
| FR-17 | Báo cáo mức độ đặt phòng theo kỳ | UC-10 | QD-20; chỉ số/quyền/công thức DP-09 |
| FR-18 | Cấp/cập nhật/khóa/đặt lại mật khẩu tài khoản | UC-11 | Quản lý tài khoản; chi tiết DP-05 |
| FR-19 | Quản lý danh mục phòng ban | UC-17 | Hỗ trợ phân công theo phòng ban |
| FR-20 | Quản lý phòng họp, sức chứa, thiết bị và cấu hình phục vụ | UC-18 | Khoảng đệm đã chốt; chính sách đổi cấu hình DP-01 |
| FR-21 | Giao/thu hồi phạm vi duyệt phòng họp và công tác | UC-12 | QD-11 đến QD-13, QD-25 |
| FR-22 | Gửi email thật, theo dõi lỗi và thử lại sau khi lưu | UC-03 đến UC-08; UC-13 đến UC-16 | QD-07, QD-19; chi tiết DP-08 |
| FR-23 | Routing/State, trạng thái tải/lỗi, lịch sử xử lý và dữ liệu mới từ API | Các Use Case liên quan | Mục tiêu Routing/State của HTTT10; BR-08 |

Phạm vi cơ bản không bao gồm thanh toán, chi phí công tác, quyết định tài chính, chấm công hay đo người có mặt thực tế. Những phần mở rộng như lịch lặp, họp trực tuyến, khách ngoài đơn vị, check-in và xuất Excel/PDF chưa được yêu cầu; chưa tính thành tiêu chí bắt buộc của phiên bản này.

### 7. Ma trận phân quyền

Ba nhóm quyền chính vẫn là Nhân viên, Người phê duyệt và Admin. Hai cột Người duyệt dưới đây là hai phạm vi phân công của cùng nhóm Người phê duyệt, không phải thêm hai nhóm vai trò mới. Một người có thể được phân công cả hai.

Ký hiệu: “Của mình” là người tạo; “Liên quan” là người tạo hoặc người tham gia; “Phạm vi” là các phòng/phòng ban được phân công. “Theo NV” chỉ có khi tài khoản được cấp thêm quyền Nhân viên; chính sách cấp kết hợp tại DP-05. Tên vai trò không thay thế kiểm tra quyền trên từng bản ghi. Các hàng tài liệu và báo cáo áp dụng DP-06/DP-09 đã chốt.

| Chức năng | Nhân viên | Người duyệt phòng | Người duyệt công tác | Admin kỹ thuật |
|---|---|---|---|---|
| Đăng nhập/đăng xuất/đổi mật khẩu của mình | Có | Có | Có | Có |
| Xem chi tiết lịch liên quan đến mình | Có | Có | Có | Có |
| Xem bận/rảnh của lịch khác | Có | Có | Có | Có |
| Xem chi tiết yêu cầu để duyệt | Không | Phạm vi phòng | Phạm vi phòng ban | Chỉ khi được phân công thêm |
| Tạo yêu cầu họp/công tác | Có | Theo NV | Theo NV | Theo NV |
| Đề nghị sửa/rút yêu cầu của mình | Của mình | Của mình khi có yêu cầu | Của mình khi có yêu cầu | Của mình khi có yêu cầu |
| Duyệt yêu cầu họp/bản sửa phòng | Không | Phạm vi, không tự duyệt | Chỉ khi có phân công phòng | Chỉ khi có phân công phòng |
| Duyệt công tác/bản sửa/hủy công tác | Không | Chỉ khi có phân công công tác | Phạm vi, không tự duyệt | Chỉ khi có phân công công tác |
| Hủy cuộc họp | Của mình, trước giờ bắt đầu | Không hủy thay người tạo | Không hủy thay người tạo | Không hủy thay chỉ bằng quyền kỹ thuật |
| Đề nghị hủy công tác | Của mình | Của mình khi có yêu cầu | Của mình khi có yêu cầu | Của mình khi có yêu cầu |
| Thêm/thay/gỡ tài liệu | Của mình theo DP-06 | Không sửa thay chỉ vì được duyệt | Không sửa thay chỉ vì được duyệt | Không tự có quyền nội dung |
| Xem/tải tài liệu họp | Liên quan theo DP-06 | Đúng phạm vi theo DP-06 | Chỉ khi liên quan hoặc được phân công đúng loại yêu cầu | Chỉ khi có quyền tương ứng |
| Báo cáo đặt phòng | Không có báo cáo chi tiết toàn đơn vị | Phạm vi phòng theo DP-09 | Chỉ khi có phân công phòng | Tổng hợp, không kèm nội dung riêng, theo DP-09 |
| Quản lý tài khoản/phòng ban/phòng họp | Không | Không | Không | Có |
| Phân công và thu hồi quyền duyệt | Không | Không | Không | Có |

Không dùng “ẩn nút” làm cơ chế phân quyền duy nhất. API, tra cứu, lịch sử, báo cáo và đường dẫn tệp đều phải kiểm tra quyền. Người không liên quan chỉ biết khoảng bận, không nhận tiêu đề, danh sách tham gia, địa điểm công tác hay lý do hủy của lịch khác.

### 8. Chính sách bổ sung đã chốt

**Trạng thái toàn bộ DP-01 đến DP-09: ĐÃ CHỐT.** Các giá trị áp dụng cho đơn vị giả lập của đề tài. Chúng là cấu hình nghiệp vụ của dự án, không được trình bày như quy định bắt buộc chung cho mọi cơ quan.

| Mã | Nội dung | Quy định áp dụng | Lý do |
|---|---|---|---|
| DP-01 | Giờ phục vụ và cấu hình phòng | Mặc định thứ Hai–thứ Sáu, 08:00–12:00 và 13:00–17:00; ngày nghỉ cấu hình riêng. Cuộc họp nằm trọn trong một khoảng phục vụ. Khoảng chuyển tiếp có thể rơi vào giờ nghỉ/ngoài giờ, nhưng vẫn chặn lịch khác nếu có. Thay đổi giờ phục vụ hoặc tăng khoảng đệm phải kiểm tra các lịch tương lai đã duyệt; không áp dụng thay đổi làm các lịch đó trở nên xung đột. Ngừng nhận đặt mới không hủy lịch đã duyệt. | Đủ rõ để demo lịch trống, giữ thời gian chuẩn bị và tính báo cáo; tránh thay đổi cấu hình làm hỏng lịch đã xác nhận. |
| DP-02 | Thời lượng và thời hạn đặt | Lịch họp dài từ 15 phút đến 4 giờ; gửi yêu cầu hoặc phương án sửa trước thời điểm bắt đầu mới ít nhất 30 phút, trong 90 ngày tới. Khi duyệt chỉ yêu cầu còn trước giờ bắt đầu, không áp lại điều kiện 30 phút cho thời gian người duyệt đã xử lý. Lịch công tác không áp giới hạn 4 giờ/giờ phục vụ phòng. | Hạn chế yêu cầu quá gấp hoặc giữ chỗ quá xa; tách cuộc họp khỏi công tác nhiều ngày. |
| DP-03 | Phạm vi lịch công tác | Cho cá nhân hoặc nhóm cùng một phòng ban, trong/ngoài đơn vị, một hoặc nhiều ngày liên tục. Người tạo thuộc phòng ban phụ trách yêu cầu. Khoảng bắt đầu–kết thúc do người đăng ký nhập đã bao gồm thời gian di chuyển; coi toàn bộ khoảng là bận. Công tác nhóm nhiều phòng ban tách thành các yêu cầu theo phòng ban. | Giữ được một cấp duyệt theo phòng ban; chưa cần suy đoán hành trình hoặc tính thời gian đi lại. |
| DP-04 | Phạm vi lịch họp và thành phần | Phiên bản đầu làm họp trực tiếp, mỗi lịch một phòng nội bộ, lập từng lần và chọn người tham gia từ tài khoản nội bộ. Chủ trì bắt buộc nằm trong danh sách tham gia. Người tạo có thể là người tổ chức thay và không bắt buộc tham dự. Đếm người không trùng, gồm cả người được mời tùy chọn, để kiểm tra sức chứa. Tài khoản tham gia phải đang hoạt động. | Bao phủ đúng bài toán đặt phòng và kiểm tra lịch người tham gia; giữ quy mô demo rõ ràng. |
| DP-05 | Tài khoản nội bộ | Admin cấp, khóa và đặt lại mật khẩu tài khoản; người dùng có đăng nhập, đăng xuất và đổi mật khẩu. Tài khoản có email duy nhất, phòng ban và nhóm quyền phù hợp. Tài khoản được cấp mật khẩu tạm phải đổi ở lần đầu. Admin/người duyệt được giao thêm quyền Nhân viên khi cần tạo yêu cầu; không có đăng ký tài khoản công khai. | Phù hợp ứng dụng nội bộ; nhân viên không tự nhận vai trò hay tự chọn phòng ban để vượt quyền. |
| DP-06 | Tài liệu họp | Cho PDF, DOCX, PPTX, XLSX, JPG/JPEG, PNG; tối đa 20 MB/tệp (20 × 1024 × 1024 byte). Người tạo quản lý tài liệu; người tham gia và người duyệt đúng phạm vi được xem/tải. Cho bổ sung tài liệu/biên bản trước hoặc sau cuộc họp; bổ sung tài liệu không tự thay đổi lịch/phòng/thành phần và không yêu cầu duyệt lại việc đặt phòng. Thay tệp bằng phiên bản mới hoặc gỡ hiển thị có lưu vết; lịch bị hủy hoặc yêu cầu đã rút/từ chối chỉ đọc tài liệu cũ. | Đáp ứng cả tài liệu chuẩn bị và biên bản sau họp; không làm mất dấu vết tài liệu đã dùng. |
| DP-07 | Vòng đời yêu cầu và gửi lại | Mỗi lịch có tối đa một đề nghị sửa hoặc hủy đang chờ. Muốn sửa nội dung một yêu cầu đang chờ thì rút và gửi bản mới. Thao tác duyệt gặp xung đột báo lỗi, yêu cầu vẫn chưa được duyệt; người gửi rút và chọn lại. Yêu cầu tạo lịch chưa được xử lý đến giờ bắt đầu thì hết hiệu lực. Đề nghị sửa hết hiệu lực khi đến thời điểm sớm hơn giữa giờ bắt đầu lịch gốc và giờ bắt đầu mới; đề nghị hủy công tác hết hiệu lực khi lịch gốc bắt đầu. Đổi phòng thì người phụ trách phòng mới duyệt bản sửa, một cấp duyệt. | Không có hồ sơ chờ vô hạn hoặc quyết định áp lên bản cũ; giải thích rõ trường hợp mất phòng mới trong lúc chờ. |
| DP-08 | Email và thử lại | Dùng SMTP cấu hình được. Gửi thông báo có yêu cầu cần duyệt cho người duyệt phù hợp; kết quả duyệt/từ chối/rút/sửa/hủy cho người tạo và các bên liên quan đúng quyền. Email chủ yếu có tóm tắt và liên kết yêu cầu đăng nhập; không gửi tệp đính kèm hay nội dung lịch ngoài quyền. Một lần gửi ban đầu, tối đa ba lần thử lại ở các mốc 1, 5, 15 phút sau lần thất bại đầu; sau đó ghi thất bại để xử lý. Lịch gốc không bị đổi do lỗi gửi. Chưa thêm nhắc lịch theo giờ trước họp. | Đủ chứng minh gửi đến hộp thư thật và xử lý lỗi; tránh mở rộng thêm chức năng nhắc lịch khi chưa cần. |
| DP-09 | Báo cáo và quyền xem | Có số lượt đã xác nhận/đã hủy, tổng giờ đặt họp, tổng thời gian chuyển tiếp và tỷ lệ thời gian đặt theo kế hoạch, lọc theo phòng và khoảng ngày. Người phụ trách phòng xem trong phạm vi được giao; Admin xem số liệu tổng hợp không kèm nội dung lịch riêng. Nhân viên xem lịch của mình, không có quyền báo cáo chi tiết toàn đơn vị. Tỷ lệ lấy giờ họp đã xác nhận nằm trong giờ phục vụ chia tổng giờ phục vụ theo cấu hình có hiệu lực trong kỳ; loại phần ngoài kỳ và lịch hủy, không cộng thời gian chuyển tiếp; mẫu số bằng 0 thì hiển thị không áp dụng. | Đủ yêu cầu thống kê mức độ sử dụng phòng, có mẫu số rõ ràng và không biến số liệu kế hoạch thành sử dụng thực tế. |

#### 8.1. Những cách hiểu cần giữ nhất quán

- **Giờ phục vụ và khoảng chuyển tiếp:** Nếu một cuộc họp kết thúc lúc 12:00, khoảng chuyển tiếp có thể chạy đến 12:15 trong giờ nghỉ; lịch tiếp theo vẫn phải tuân thủ cả giờ phục vụ và khoảng đệm. Không mặc nhiên bắt cuộc họp cuối buổi kết thúc sớm 15 phút. Thời gian chuyển tiếp báo cáo theo phần thực tế của khoảng đặt trong kỳ, tách khỏi giờ họp; khi tính công suất phục vụ thì chỉ lấy phần thuộc giờ phục vụ.
- **Cấu hình phòng:** Ngừng nhận đặt mới không đồng nghĩa phòng bị hỏng và mọi lịch cũ không thể diễn ra. Xử lý phòng hỏng khẩn cấp và hủy thay người tạo là một phạm vi khác, chưa tự thêm vào phiên bản này. Thay đổi giờ phục vụ/đệm/sức chứa phải kiểm tra tính hợp lệ của lịch tương lai đã xác nhận và không âm thầm làm chúng mất hiệu lực. Giữ lịch sử cấu hình có hiệu lực để báo cáo không bị tính ngược bằng một cấu hình mới.
- **Công tác nhiều ngày:** Chưa tự suy đoán giờ làm việc mỗi ngày hay bỏ qua ban đêm. Nếu đăng ký một khoảng công tác liên tục, toàn bộ khoảng đó được coi là bận; người đăng ký đưa cả thời gian di chuyển vào khoảng. Chưa tích hợp bản đồ/tính hành trình.
- **Đổi phòng khi sửa:** Người phụ trách phòng mới là người có thẩm quyền duyệt bản sửa. Chỉ cấp phần thông tin lịch gốc cần để so sánh bản sửa; không cấp quyền xem mọi lịch ngoài phạm vi. Sau khi duyệt, người phụ trách phòng cũ nhận thông tin phần chỗ cũ đã giải phóng theo đúng quyền của mình. Người phụ trách phòng cũ chỉ có quyền lịch sử đối với lượt đặt/phiên bản cũ thuộc phạm vi của mình, không tự được xem mọi nội dung của phiên bản mới tại phòng khác.
- **Tài liệu:** Bổ sung biên bản sau họp là cập nhật tài liệu; thay giờ/phòng/nội dung lịch/thành phần vẫn phải qua quy trình sửa lịch đã duyệt. Cách tách trách nhiệm tại DP-06 đã được người thực hiện đề tài chấp thuận. Tệp không được công khai chỉ vì có một URL.
- **Email:** “Đã gửi” chỉ được hiểu là máy chủ SMTP đã chấp nhận gửi, không tự chứng minh thư vào hộp thư đến. Khi nghiệm thu phải kiểm tra nhận ở hộp thư thật. Không ghi mật khẩu, JWT hay bí mật SMTP vào email/log/tài liệu. Một email gửi lúc dữ liệu đã thay đổi phải kiểm tra lại quyền người nhận và tình trạng hiện tại; tránh phát thông tin lỗi thời hoặc sai phạm vi.
- **Thông tin cảnh báo:** Có thể báo một người bận ở khoảng giờ được phép xem, nhưng không chèn tiêu đề hay nội dung lịch riêng đó vào thông báo lỗi xung đột.
- **Lịch đã qua giờ:** Việc thời gian kết thúc đã qua không chứng minh đã diễn ra cuộc họp/công tác. Giao diện có thể ghi “đã qua thời gian”, không dùng làm bằng chứng tham dự hoặc công suất thực tế.
- **Người duyệt thay:** Nếu người được phân công chính là người tạo, hệ thống cần một người khác đủ quyền. Thiếu người duyệt thay thì yêu cầu phân công; không bỏ quy tắc cấm tự duyệt.

#### 8.2. Công thức báo cáo (DP-09)

**Tỷ lệ thời gian đặt theo kế hoạch = (Tổng giờ họp đã xác nhận trong giờ phục vụ và trong kỳ / Tổng giờ phục vụ theo cấu hình có hiệu lực trong kỳ) × 100%.**

Tính theo từng phòng trước khi tổng hợp. Tổng hợp nhiều phòng phải cộng tử số và mẫu số rồi chia, không lấy trung bình đơn giản các tỷ lệ của những phòng có giờ phục vụ khác nhau. Loại lịch hủy, không đếm hai lần bản cũ và bản sửa. Thời gian chuyển tiếp là chỉ số riêng, không cộng vào tử số giờ họp. Phòng ngừng nhận đặt mới không mặc nhiên bị loại mọi giờ phục vụ/hồ sơ lịch sử khỏi mẫu số. Mẫu số bằng 0 hiển thị “Không áp dụng”.

Ví dụ một phòng phục vụ 8 giờ trong kỳ, có 3 giờ họp đã xác nhận, thì tỷ lệ theo kế hoạch là 37,5%; nếu có thêm 30 phút chuyển tiếp thì vẫn báo 3 giờ họp và 0,5 giờ chuyển tiếp riêng.

### 9. Mô hình trạng thái nghiệp vụ

Phải phân biệt bản ghi lịch gốc đang có hiệu lực, yêu cầu phê duyệt và thời gian hiện tại. Không dùng trạng thái của đề nghị sửa để ghi đè trạng thái đã duyệt của lịch gốc.

| Đối tượng | Trạng thái/ngữ nghĩa | Hiệu lực |
|---|---|---|
| Yêu cầu tạo lịch | Chờ duyệt | Chưa giữ phòng/chưa tạo bận bắt buộc |
| Yêu cầu tạo lịch | Đã duyệt | Tạo lịch có hiệu lực |
| Yêu cầu tạo lịch | Bị từ chối | Không tạo hiệu lực |
| Yêu cầu tạo lịch | Đã rút | Người gửi đã rút, không được duyệt tiếp |
| Yêu cầu chưa xử lý | Hết hiệu lực (DP-07) | Đã tới mốc thời gian cho phép xử lý; không được duyệt muộn |
| Lịch đã xác nhận | Có hiệu lực | Là cơ sở kiểm tra xung đột |
| Lịch đã xác nhận | Đã hủy | Không tiếp tục giữ phòng/tạo bận; còn lịch sử |
| Đề nghị sửa/hủy | Chờ duyệt | Lịch gốc còn nguyên; phương án mới chưa có hiệu lực |
| Đề nghị sửa | Được chấp thuận | Thay phiên bản có hiệu lực, chỉ tính bản mới |
| Đề nghị hủy công tác | Được chấp thuận | Lịch gốc chuyển sang đã hủy |
| Đề nghị sửa/hủy | Bị từ chối hoặc đã rút | Lịch gốc giữ nguyên |
| Đề nghị sửa chờ của cuộc họp bị hủy | Hết hiệu lực theo QD-28 | Không được làm cuộc họp sống lại |

Hết hiệu lực do mốc thời gian áp dụng DP-07 đã chốt. Chặn thao tác chấp thuận vì phát sinh xung đột không tự đổi yêu cầu thành “Bị từ chối”. Các nhãn nghiệp vụ được ánh xạ sang enum kỹ thuật trong bộ UML; ý nghĩa và điều kiện chuyển không thay đổi.

Cơ chế kiểm tra phiên bản áp dụng khi duyệt, rút, hủy hoặc thay đổi một bản ghi. Hai quyết định cạnh tranh phải được tuần tự hóa/kiểm tra trạng thái mới nhất để không vừa rút vừa duyệt, không hủy một nửa, không giữ đồng thời hai phiên bản và không khôi phục một lịch đã hủy bằng đề nghị cũ.

### 10. Danh mục và đặc tả 20 Use Case

#### 10.1. Danh mục

| Mã | Use Case | Tác nhân chính | Phụ thuộc đề xuất |
|---|---|---|---|
| UC-01 | Đăng nhập | Người có tài khoản nội bộ | DP-05 |
| UC-02 | Xem lịch và tìm phòng phù hợp | Người dùng đã đăng nhập | DP-01, DP-04 |
| UC-03 | Gửi yêu cầu họp và đặt phòng | Người dùng có quyền Nhân viên | DP-01, DP-02, DP-04, DP-07, DP-08 |
| UC-04 | Duyệt hoặc từ chối yêu cầu đặt phòng | Người phê duyệt được phân công phòng | DP-01, DP-02, DP-07, DP-08 |
| UC-05 | Đăng ký lịch công tác | Người dùng có quyền Nhân viên | DP-03, DP-07, DP-08 |
| UC-06 | Duyệt hoặc từ chối lịch công tác | Người phê duyệt được phân công phòng ban | DP-03, DP-07, DP-08 |
| UC-07 | Gửi đề nghị sửa lịch đã duyệt | Người tạo lịch | DP-01, DP-04, DP-07 |
| UC-08 | Duyệt hoặc từ chối đề nghị sửa lịch | Người duyệt đúng phạm vi của phương án mới | DP-07, DP-08 |
| UC-09 | Quản lý tài liệu họp | Người tạo lịch; người tham gia/người duyệt đúng phạm vi ở quyền xem | DP-06 |
| UC-10 | Xem báo cáo mức độ đặt phòng | Người phụ trách phòng; Admin ở số liệu tổng hợp | DP-01, DP-09 |
| UC-11 | Quản lý tài khoản nội bộ | Admin | DP-05 |
| UC-12 | Phân công quyền phê duyệt | Admin | Quy tắc nền tảng đã chốt |
| UC-13 | Rút yêu cầu đang chờ duyệt | Người gửi yêu cầu | DP-07, DP-08 |
| UC-14 | Hủy lịch họp đã duyệt | Người tạo lịch họp | Quy tắc nền tảng đã chốt |
| UC-15 | Đề nghị hủy lịch công tác đã duyệt | Người tạo lịch công tác | DP-07, DP-08 |
| UC-16 | Duyệt hoặc từ chối hủy lịch công tác | Người phê duyệt công tác đúng phạm vi phòng ban | DP-07, DP-08 |
| UC-17 | Quản lý phòng ban | Admin | DP-03, DP-05 |
| UC-18 | Quản lý phòng họp và giờ phục vụ | Admin | DP-01, DP-02 |
| UC-19 | Đăng xuất | Người dùng đang có phiên | DP-05 |
| UC-20 | Đổi mật khẩu | Người dùng đã xác thực hoặc đang đổi mật khẩu tạm | DP-05 |

#### 10.2. Quy ước đặc tả

Luồng chính mô tả mục tiêu thành công. Luồng thay thế là các nhánh hợp lệ; ngoại lệ nêu các tình huống không thể tiếp tục. Mọi thao tác ghi chỉ báo thành công sau khi dữ liệu được lưu. Email là tác vụ sau lưu và không quyết định việc phòng có được giữ hay không. Các chức năng có mã DP được cài theo phương án đã chốt.

Không vẽ “đăng nhập” như một include bắt buộc lặp lại bên trong mọi Use Case đã có điều kiện phiên hợp lệ. Kiểm tra xung đột là hành vi dùng chung bắt buộc của các luồng gửi/duyệt tương ứng; quan hệ include/extend sẽ được thể hiện theo đúng ngữ nghĩa khi dựng sơ đồ.

#### UC-01. Đăng nhập

- **Tác nhân chính:** Người có tài khoản nội bộ.
- **Điều kiện trước:** Tài khoản đã được Admin cấp, đang hoạt động; người dùng chưa có phiên hợp lệ hoặc cần đăng nhập lại.
- **Điều kiện sau:** Thành công: có phiên xác thực JWT và quyền hiện hành; thất bại: không tạo phiên.
- **Căn cứ:** QD-04; DP-05; FR-01.

**Luồng chính**

1. Người dùng mở màn hình đăng nhập, nhập email và mật khẩu.
2. Hệ thống kiểm tra dữ liệu, tài khoản và mật khẩu đã băm.
3. Hệ thống tạo phiên xác thực, lấy nhóm quyền và phạm vi được phân công.
4. Chuyển tới màn hình phù hợp; tài khoản mật khẩu tạm thực hiện UC-20 trước các chức năng nghiệp vụ theo DP-05.

**Luồng thay thế**

- A1. Đã có phiên hợp lệ: lấy lại quyền hiện hành rồi mở trang; không tin dữ liệu quyền cũ lưu ở trình duyệt.

**Luồng ngoại lệ**

- E1. Sai thông tin, tài khoản bị khóa hoặc dữ liệu không hợp lệ: thông báo phù hợp, không tiết lộ mật khẩu hay chi tiết nội bộ.

#### UC-02. Xem lịch và tìm phòng phù hợp

- **Tác nhân chính:** Người dùng đã đăng nhập.
- **Điều kiện trước:** Có phiên hợp lệ; truy vấn theo khoảng ngày/người/phòng phù hợp.
- **Điều kiện sau:** Hiển thị đúng trạng thái mới nhất mà API trả về, che chi tiết ngoài quyền; thao tác xem không giữ phòng.
- **Căn cứ:** BR-02, BR-03, BR-08; DP-01, DP-04; FR-04, FR-05, FR-23.

**Luồng chính**

1. Chọn ngày/tuần/tháng hoặc danh sách; chọn bộ lọc phòng, người, thời gian.
2. Hệ thống lấy các khoảng đã giữ phòng, khoảng chuyển tiếp và lịch bận phù hợp.
3. Với từng lịch, trả chi tiết nếu là người tạo/tham gia/người duyệt đúng phạm vi; còn lại chỉ trả khoảng bận.
4. Khi tìm phòng, lọc theo thời gian, sức chứa và thiết bị; hiển thị kết quả sẵn sàng cùng cảnh báo yêu cầu chờ đã được lược bỏ nội dung riêng.

**Luồng thay thế**

- A1. Không có kết quả: đề nghị đổi bộ lọc/thời gian; không tự thay đổi yêu cầu.
- A2. Mở URL chi tiết ngoài quyền: chỉ cung cấp thông tin bận/rảnh được phép, không trả nội dung riêng.

**Luồng ngoại lệ**

- E1. Phiên hết hạn hoặc mất kết nối: hiển thị lỗi/trạng thái tải lại; không coi dữ liệu cũ là bảo đảm giữ phòng.

#### UC-03. Gửi yêu cầu họp và đặt phòng

- **Tác nhân chính:** Người dùng có quyền Nhân viên.
- **Điều kiện trước:** Đã đăng nhập; có phòng và người duyệt đủ quyền khác người gửi; lịch bắt đầu trong tương lai.
- **Điều kiện sau:** Tạo yêu cầu chờ duyệt và thông báo cho người duyệt; phòng và người tham gia chưa bị giữ bởi yêu cầu này.
- **Căn cứ:** BR-01 đến BR-05; DP-01, DP-02, DP-04, DP-07, DP-08; FR-06, FR-22.

**Luồng chính**

1. Nhập tiêu đề, nội dung, thời gian, phòng, chủ trì và danh sách bắt buộc/tùy chọn; thêm tài liệu theo UC-09 khi được phép.
2. Kiểm tra phòng còn nhận đặt, giờ phục vụ, thời lượng và thời hạn theo DP-01/DP-02.
3. Kiểm tra sức chứa, người tham gia không trùng và các khoảng đã xác nhận, gồm khoảng chuyển tiếp.
4. Nếu không có xung đột cứng, hiển thị cảnh báo tùy chọn/yêu cầu chờ để người gửi xem.
5. Người gửi xác nhận; hệ thống lưu yêu cầu và ghi nhận email cần gửi đến người duyệt đúng phòng.

**Luồng thay thế**

- A1. Có yêu cầu khác đang chờ: cho gửi sau cảnh báo, không hứa ưu tiên được giữ chỗ.
- A2. Cần đổi nội dung yêu cầu đã gửi: thực hiện UC-13 rồi gửi yêu cầu mới theo DP-07.

**Luồng ngoại lệ**

- E1. Phòng/người bắt buộc xung đột, vượt sức chứa hoặc thiếu người duyệt phù hợp: báo lý do để sửa, không lưu một yêu cầu hợp lệ giả.
- E2. Lỗi lưu: không tạo dữ liệu một phần. Email lỗi: yêu cầu vẫn tồn tại, áp dụng BR-05.

#### UC-04. Duyệt hoặc từ chối yêu cầu đặt phòng

- **Tác nhân chính:** Người phê duyệt được phân công phòng.
- **Điều kiện trước:** Yêu cầu đang chờ, chưa hết hiệu lực; người thao tác có quyền tại phòng và không là người gửi.
- **Điều kiện sau:** Chấp thuận: lịch họp được xác nhận và giữ phòng/người bắt buộc. Từ chối: đóng yêu cầu, không giữ chỗ.
- **Căn cứ:** QD-08 đến QD-15; BR-02 đến BR-05; DP-01, DP-02, DP-07, DP-08; FR-07.

**Luồng chính**

1. Mở danh sách cần duyệt trong phạm vi; xem nội dung yêu cầu và các cảnh báo.
2. Chọn chấp thuận; hệ thống kiểm tra lại quyền, phiên bản yêu cầu, thời điểm và dữ liệu phòng/người hiện tại.
3. Kiểm tra giờ phục vụ, sức chứa, khoảng chuyển tiếp và các xung đột theo quy tắc được áp dụng.
4. Trong thao tác lưu nhất quán, xác nhận yêu cầu và tạo hiệu lực đặt phòng/lịch bận.
5. Ghi lịch sử người duyệt và thời điểm; ghi nhận email thông báo kết quả.

**Luồng thay thế**

- A1. Chọn từ chối: nhập lý do, kiểm tra lại trạng thái rồi lưu từ chối và thông báo.
- A2. Xung đột phát sinh trong lúc chờ: không duyệt được; yêu cầu vẫn chưa được chấp thuận, người gửi có thể rút và gửi lại theo DP-07.

**Luồng ngoại lệ**

- E1. Ngoài phạm vi, tự duyệt, yêu cầu đã rút/đã xử lý/hết hiệu lực: không áp dụng quyết định.
- E2. Hai lượt duyệt cạnh tranh: chỉ một kết quả giữ phòng xung đột được thành công. Lỗi lưu hoàn tác; lỗi email không đổi kết quả đã lưu.

#### UC-05. Đăng ký lịch công tác

- **Tác nhân chính:** Người dùng có quyền Nhân viên.
- **Điều kiện trước:** Đã đăng nhập; có phòng ban phụ trách và người duyệt đủ quyền khác người gửi; thời gian chưa bắt đầu.
- **Điều kiện sau:** Tạo yêu cầu công tác chờ duyệt; chưa tạo lịch bận có hiệu lực.
- **Căn cứ:** BR-01, BR-03, BR-04; DP-03, DP-07, DP-08; FR-08.

**Luồng chính**

1. Nhập mục đích, địa điểm, bắt đầu/kết thúc và người đi công tác.
2. Theo DP-03, chọn cá nhân hoặc nhóm cùng phòng ban; thời gian nhập bao gồm di chuyển.
3. Kiểm tra dữ liệu, nhân sự, phạm vi phòng ban và lịch đã xác nhận của người bắt buộc.
4. Hiển thị cảnh báo liên quan đến lịch tùy chọn hoặc yêu cầu đang chờ.
5. Người gửi xác nhận; lưu yêu cầu, xác định người duyệt phòng ban và ghi nhận thông báo.

**Luồng thay thế**

- A1. Nhóm nhiều phòng ban: chia thành các yêu cầu theo từng phòng ban theo DP-03.
- A2. Công tác nhiều ngày: dùng một khoảng bắt đầu/kết thúc liên tục; toàn bộ khoảng được kiểm tra lịch bận.

**Luồng ngoại lệ**

- E1. Thời gian không hợp lệ, nhân sự không đúng phạm vi hoặc trùng lịch bắt buộc đã xác nhận: không cho gửi.
- E2. Thiếu người duyệt khác người gửi: yêu cầu Admin phân công; không tự xác nhận công tác.

#### UC-06. Duyệt hoặc từ chối lịch công tác

- **Tác nhân chính:** Người phê duyệt được phân công phòng ban.
- **Điều kiện trước:** Yêu cầu còn chờ và chưa bắt đầu; đúng phạm vi phòng ban, không tự duyệt.
- **Điều kiện sau:** Duyệt: lịch công tác có hiệu lực và tạo bận cho người đi. Từ chối: yêu cầu không có hiệu lực.
- **Căn cứ:** QD-12 đến QD-15; BR-04, BR-05; DP-03, DP-07, DP-08; FR-09.

**Luồng chính**

1. Mở yêu cầu trong phạm vi, kiểm tra mục đích, địa điểm, thành phần và thời gian.
2. Chọn duyệt; hệ thống đọc lại phiên bản, trạng thái, quyền và lịch người tham gia.
3. Kiểm tra xung đột bắt buộc với các lịch họp/công tác đã xác nhận.
4. Lưu quyết định, hiệu lực lịch bận và lịch sử nhất quán; ghi nhận email kết quả.

**Luồng thay thế**

- A1. Từ chối: nhập lý do và lưu quyết định khi yêu cầu vẫn còn chờ.
- A2. Nếu phát sinh xung đột: báo không thể duyệt, không tự hủy lịch khác hoặc tự bỏ thành viên.

**Luồng ngoại lệ**

- E1. Yêu cầu đã rút/hết hiệu lực, nhân sự không còn hợp lệ theo yêu cầu, ngoài quyền hoặc tự duyệt: không thực hiện.
- E2. Lỗi lưu hoàn tác; lỗi email áp dụng BR-05.

#### UC-07. Gửi đề nghị sửa lịch đã duyệt

- **Tác nhân chính:** Người tạo lịch.
- **Điều kiện trước:** Lịch gốc đang có hiệu lực, chưa bắt đầu; người thao tác là người tạo; chưa có đề nghị khác đang chờ theo DP-07.
- **Điều kiện sau:** Lưu đề nghị sửa chờ duyệt; lịch gốc, phòng cũ và lịch bận cũ vẫn có hiệu lực; phương án mới chưa giữ chỗ.
- **Căn cứ:** QD-16 đến QD-18, QD-27; mục 5; DP-01 đến DP-04, DP-07; FR-10.

**Luồng chính**

1. Mở lịch gốc và nhập bản sửa về thời gian/phòng/nội dung/thành phần theo loại lịch.
2. Kiểm tra phương án mới theo các quy tắc tương ứng, loại trừ chính bản gốc khi so xung đột.
3. Nếu đổi phòng, xác định người duyệt của phòng mới; với công tác vẫn theo phòng ban phụ trách yêu cầu.
4. Cho xem so sánh trước/sau và các cảnh báo; người gửi xác nhận.
5. Lưu bản đề nghị gắn với phiên bản gốc và ghi nhận thông báo cho người duyệt.

**Luồng thay thế**

- A1. Chỗ mới đã có lịch được duyệt: báo không khả dụng, cho người gửi chọn lại, không đổi lịch gốc.
- A2. Chỗ mới chỉ có yêu cầu chờ: cảnh báo và cho gửi.

**Luồng ngoại lệ**

- E1. Lịch gốc đã bắt đầu/đã hủy hoặc thay đổi phiên bản; thời gian mới không hợp lệ; thiếu người duyệt: không nhận bản sửa.
- E2. Có đề nghị đang chờ: rút đề nghị đó trước khi gửi bản mới theo DP-07.

#### UC-08. Duyệt hoặc từ chối đề nghị sửa lịch

- **Tác nhân chính:** Người duyệt đúng phạm vi của phương án mới.
- **Điều kiện trước:** Đề nghị còn chờ, lịch gốc còn hiệu lực và chưa bắt đầu; đúng quyền, không là người gửi.
- **Điều kiện sau:** Duyệt: chỉ phiên bản mới có hiệu lực; phần giữ chỗ/bận cũ được thay thế nhất quán. Từ chối/lỗi: lịch gốc giữ nguyên.
- **Căn cứ:** Mục 5; BR-02 đến BR-05, BR-07; DP-07, DP-08; FR-11.

**Luồng chính**

1. Mở bản so sánh gốc và đề nghị trong phạm vi được phân công; chỉ cấp thông tin gốc cần cho xét bản sửa.
2. Kiểm tra lại phiên bản gốc, trạng thái, quyền và điều kiện thời gian.
3. Kiểm tra phòng/giờ/người mới với dữ liệu hiện tại, gồm khoảng chuyển tiếp và loại trừ bản gốc.
4. Lưu chấp thuận và đồng thời thay hiệu lực lịch, phòng và người tham gia trong một giao dịch.
5. Lưu lịch sử và ghi nhận email cập nhật cho người liên quan; người phụ trách phòng cũ được biết phần chỗ cũ đã giải phóng.

**Luồng thay thế**

- A1. Từ chối kèm lý do: đóng đề nghị, giữ nguyên lịch gốc.
- A2. Phát sinh xung đột: chặn thao tác chấp thuận; người gửi rút và chọn lại theo DP-07.

**Luồng ngoại lệ**

- E1. Lịch gốc đã hủy/bắt đầu/được sửa bởi quyết định khác, đề nghị đã rút/hết hiệu lực hoặc ngoài quyền: không áp dụng quyết định cũ.
- E2. Lỗi lưu không làm mất phòng cũ hoặc giữ đồng thời hai phiên bản; email lỗi không hoàn tác kết quả đã lưu.

#### UC-09. Quản lý tài liệu họp

- **Tác nhân chính:** Người tạo lịch; người tham gia/người duyệt đúng phạm vi ở quyền xem.
- **Điều kiện trước:** Đã đăng nhập và có quyền trên cuộc họp/tệp; áp dụng DP-06 đã chốt.
- **Điều kiện sau:** Lưu/tải đúng tệp theo quyền; thêm phiên bản hoặc gỡ hiển thị có lịch sử; không tự đổi lịch đặt phòng.
- **Căn cứ:** BR-08; DP-06; FR-16.

**Luồng chính**

1. Mở danh sách tài liệu của cuộc họp mà mình được phép xem.
2. Người tạo chọn tải lên; hệ thống kiểm tra loại tệp, nội dung định dạng, dung lượng và quyền theo DP-06.
3. Lưu tệp bằng tên nội bộ, lưu metadata và liên kết cuộc họp; không công khai đường dẫn lưu trữ.
4. Người được quyền chọn xem/tải; API kiểm tra lại quyền rồi cung cấp tệp.
5. Khi bổ sung biên bản hoặc thay tệp, lưu bản mới cùng người/thời điểm thực hiện.

**Luồng thay thế**

- A1. Người tạo gỡ một tệp: gỡ hiển thị có lưu vết; không xóa sạch lịch sử.
- A2. Cuộc họp đã hủy hoặc yêu cầu đã rút/từ chối: chỉ xem/tải tài liệu cũ theo quyền.

**Luồng ngoại lệ**

- E1. Không đủ quyền, tệp vượt giới hạn, sai định dạng hoặc không tìm thấy: từ chối thao tác.
- E2. Lưu nội dung thất bại: không tạo metadata giả; không trả tệp của lịch khác khi đổi mã URL.

#### UC-10. Xem báo cáo mức độ đặt phòng

- **Tác nhân chính:** Người phụ trách phòng; Admin ở số liệu tổng hợp.
- **Điều kiện trước:** Đã đăng nhập, có quyền báo cáo theo DP-09; chọn khoảng ngày hợp lệ.
- **Điều kiện sau:** Trả các chỉ số theo đúng phạm vi và cùng công thức; không tiết lộ nội dung riêng hoặc kết luận phòng đã được dùng thực tế.
- **Căn cứ:** QD-20; BR-06, BR-08; DP-01, DP-09; FR-17.

**Luồng chính**

1. Chọn phòng hoặc nhóm phòng được phép và khoảng ngày.
2. Hệ thống lấy các phiên bản lịch có hiệu lực, lượt hủy và giờ phục vụ có hiệu lực trong kỳ.
3. Tính số lượt, giờ đặt họp, thời gian chuyển tiếp và tỷ lệ theo DP-09; cắt phần ngoài kỳ báo cáo.
4. Hiển thị bảng/biểu đồ có nhãn rõ là số liệu theo lịch đặt; không kèm tiêu đề/người tham gia ngoài quyền.

**Luồng thay thế**

- A1. Không có dữ liệu: hiển thị số 0 với phần tỷ lệ hợp lệ; mẫu số giờ phục vụ bằng 0 thì ghi không áp dụng.
- A2. Admin xem tổng hợp toàn đơn vị, không mở được lịch chi tiết chỉ nhờ quyền xem số liệu.

**Luồng ngoại lệ**

- E1. Chọn phòng ngoài phạm vi hoặc khoảng ngày sai: từ chối/đề nghị chọn lại.
- E2. Lỗi truy vấn: không hiển thị kết quả cũ như một báo cáo mới thành công.

#### UC-11. Quản lý tài khoản nội bộ

- **Tác nhân chính:** Admin.
- **Điều kiện trước:** Có quyền quản trị tài khoản; áp dụng DP-05 đã chốt cho các chi tiết cấp tài khoản.
- **Điều kiện sau:** Tài khoản được cấp/cập nhật/khóa đúng yêu cầu; giữ các tham chiếu và lịch sử nghiệp vụ.
- **Căn cứ:** QD-11, QD-25; DP-05; FR-18.

**Luồng chính**

1. Mở danh sách, tìm tài khoản hoặc chọn tạo mới.
2. Nhập/cập nhật mã nhân viên, họ tên, email duy nhất, phòng ban, trạng thái và nhóm quyền phù hợp.
3. Hệ thống kiểm tra dữ liệu, email trùng và danh mục được tham chiếu.
4. Lưu thay đổi, ghi lịch sử; cấp mật khẩu tạm theo quy trình DP-05.
5. Khi khóa hoặc đổi quyền, các lần truy cập tiếp theo kiểm tra trạng thái/quyền mới.

**Luồng thay thế**

- A1. Đặt lại mật khẩu khi cần: tạo cơ chế mật khẩu tạm và yêu cầu đổi lần đầu; không xem lại mật khẩu cũ.
- A2. Tài khoản có lịch sử: khóa/ngừng sử dụng thay cho xóa sạch.

**Luồng ngoại lệ**

- E1. Email trùng, phòng ban không hợp lệ hoặc ngoài quyền: không lưu.
- E2. Không cho thao tác làm mất tài khoản quản trị hoạt động cuối cùng; không tự hủy lịch đã duyệt khi khóa người dùng.

#### UC-12. Phân công quyền phê duyệt

- **Tác nhân chính:** Admin.
- **Điều kiện trước:** Có quyền quản lý phân công; người nhận quyền đang hoạt động; có phòng/phòng ban tương ứng.
- **Điều kiện sau:** Lưu loại quyền, người được phân công và phạm vi; không tạo quyết định duyệt tự động.
- **Căn cứ:** QD-11 đến QD-13, QD-25; mục 3; FR-21.

**Luồng chính**

1. Chọn người nhận và loại phân công: duyệt phòng họp hoặc duyệt công tác.
2. Chọn các phòng/phòng ban cụ thể; một người có thể có nhiều phân công.
3. Kiểm tra dữ liệu, hiển thị các yêu cầu đang chờ có thể bị ảnh hưởng nếu thay đổi phân công.
4. Lưu phân công cùng lịch sử; các lần duyệt sau kiểm tra quyền mới và nguyên tắc không tự duyệt.

**Luồng thay thế**

- A1. Thu hồi phân công: không xóa lịch sử quyết định trước đây; yêu cầu đang chờ do người khác đủ quyền xử lý.
- A2. Nếu không còn người duyệt khác người gửi, thông báo cần phân công thay; không chuyển quyền nghiệp vụ mặc nhiên sang Admin.

**Luồng ngoại lệ**

- E1. Phạm vi không tồn tại hoặc người nhận bị khóa: không cấp.
- E2. Thao tác duyệt bằng quyền đã bị thu hồi bị từ chối dù màn hình cũ vẫn còn nút duyệt.

#### UC-13. Rút yêu cầu đang chờ duyệt

- **Tác nhân chính:** Người gửi yêu cầu.
- **Điều kiện trước:** Đã đăng nhập; là người gửi; yêu cầu tạo lịch/đề nghị sửa/đề nghị hủy còn đang chờ.
- **Điều kiện sau:** Yêu cầu được rút và không còn được duyệt. Nếu là đề nghị sửa/hủy thì lịch gốc giữ nguyên.
- **Căn cứ:** QD-23; BR-07; DP-07, DP-08; FR-12.

**Luồng chính**

1. Mở yêu cầu của mình và chọn Rút yêu cầu.
2. Hệ thống hiển thị loại yêu cầu và tác động; người gửi xác nhận.
3. Kiểm tra lại trạng thái/phiên bản để bảo đảm yêu cầu chưa được người khác xử lý.
4. Lưu rút yêu cầu và lịch sử; ghi nhận thông báo cần thiết.

**Luồng thay thế**

- A1. Cần nội dung mới: sau khi rút có thể tạo/gửi yêu cầu mới theo DP-07.
- A2. Rút đề nghị sửa/hủy: không giải phóng lịch gốc đã duyệt.

**Luồng ngoại lệ**

- E1. Yêu cầu đã được duyệt/từ chối/rút/hết hiệu lực hoặc không thuộc người gửi: từ chối thao tác.
- E2. Duyệt và rút cùng lúc: chỉ một chuyển trạng thái hợp lệ thắng, không vừa rút vừa xác nhận lịch.

#### UC-14. Hủy lịch họp đã duyệt

- **Tác nhân chính:** Người tạo lịch họp.
- **Điều kiện trước:** Đã đăng nhập; là người tạo; lịch đã được duyệt, chưa bắt đầu và chưa bị hủy.
- **Điều kiện sau:** Lịch đã hủy; phòng, phần đệm của lượt đặt và bận do chính lịch này tạo ra được giải phóng; giữ lịch sử.
- **Căn cứ:** QD-21, QD-26, QD-28; BR-05, BR-07; FR-13.

**Luồng chính**

1. Mở lịch họp, chọn Hủy lịch và nhập lý do.
2. Xác nhận; hệ thống đọc lại trạng thái, phiên bản, quyền và giờ bắt đầu.
3. Lưu hủy lịch, giải phóng các hiệu lực liên quan và vô hiệu đề nghị sửa đang chờ nhất quán.
4. Ghi lịch sử cùng email cần gửi; trả kết quả hủy thành công.

**Luồng thay thế**

- A1. Nếu có đề nghị sửa, thông báo rõ đề nghị đó sẽ hết hiệu lực.
- A2. Các lịch khác của cùng phòng/người vẫn được giữ nguyên.

**Luồng ngoại lệ**

- E1. Người tham gia không phải người tạo không được hủy toàn bộ cuộc họp.
- E2. Lịch đã bắt đầu, đã hủy hoặc phiên bản thay đổi: không áp dụng thao tác cũ. Lỗi lưu hoàn tác; lỗi email không khôi phục lịch.

#### UC-15. Đề nghị hủy lịch công tác đã duyệt

- **Tác nhân chính:** Người tạo lịch công tác.
- **Điều kiện trước:** Đã đăng nhập; lịch gốc đã duyệt và chưa bắt đầu; chưa có đề nghị sửa/hủy đang chờ.
- **Điều kiện sau:** Đề nghị hủy ở trạng thái chờ; lịch công tác và bận của người đi vẫn có hiệu lực.
- **Căn cứ:** QD-22, QD-27; BR-07; DP-07, DP-08; FR-14.

**Luồng chính**

1. Mở lịch công tác, chọn Đề nghị hủy và nhập lý do.
2. Hệ thống kiểm tra người tạo, thời gian, trạng thái và đề nghị đang chờ.
3. Xác định người duyệt phòng ban khác người gửi.
4. Lưu đề nghị gắn phiên bản gốc, ghi lịch sử và thông báo đến người duyệt.

**Luồng thay thế**

- A1. Có đề nghị sửa đang chờ: rút đề nghị đó bằng UC-13 rồi mới gửi yêu cầu hủy.
- A2. Người tạo rút đề nghị hủy trước khi xử lý: lịch gốc giữ nguyên.

**Luồng ngoại lệ**

- E1. Lịch đã bắt đầu/bị hủy, ngoài quyền hoặc không có người duyệt phù hợp: không tạo đề nghị hợp lệ.
- E2. Lỗi email không làm mất đề nghị đã lưu hoặc hủy lịch gốc.

#### UC-16. Duyệt hoặc từ chối hủy lịch công tác

- **Tác nhân chính:** Người phê duyệt công tác đúng phạm vi phòng ban.
- **Điều kiện trước:** Đề nghị còn chờ; lịch gốc còn hiệu lực, chưa bắt đầu; người thao tác đủ quyền và không tự duyệt.
- **Điều kiện sau:** Chấp thuận: lịch gốc đã hủy và không còn tạo bận. Từ chối: lịch gốc giữ nguyên.
- **Căn cứ:** QD-22, QD-26; BR-05, BR-07; DP-07, DP-08; FR-15.

**Luồng chính**

1. Xem lịch gốc, lý do đề nghị hủy và phiên bản được tham chiếu.
2. Chọn chấp thuận; kiểm tra lại quyền, trạng thái đề nghị, lịch gốc và giờ bắt đầu.
3. Lưu quyết định hủy, bỏ bận do lịch gốc và đóng đề nghị nhất quán.
4. Ghi lịch sử và thông báo cho người tạo, người đi công tác và người liên quan đúng quyền.

**Luồng thay thế**

- A1. Từ chối: nhập lý do, đóng đề nghị và giữ nguyên lịch gốc.

**Luồng ngoại lệ**

- E1. Đề nghị đã rút/đã xử lý/hết hiệu lực hoặc lịch gốc thay đổi/bắt đầu: không duyệt bằng dữ liệu cũ.
- E2. Ngoài phạm vi hoặc tự duyệt: từ chối thao tác. Lỗi email không đảo ngược hủy đã lưu.

#### UC-17. Quản lý phòng ban

- **Tác nhân chính:** Admin.
- **Điều kiện trước:** Có quyền quản lý danh mục phòng ban.
- **Điều kiện sau:** Danh mục được cập nhật hợp lệ; không làm mất lịch sử hoặc tự chuyển chủ thể nghiệp vụ của lịch cũ.
- **Căn cứ:** Mục 3; DP-03, DP-05; FR-19.

**Luồng chính**

1. Xem/tìm phòng ban, chọn thêm hoặc sửa.
2. Nhập mã, tên và trạng thái nhận yêu cầu mới.
3. Kiểm tra mã duy nhất và các tham chiếu liên quan.
4. Lưu thay đổi và lịch sử; danh mục được dùng khi cấp tài khoản và phân công duyệt.

**Luồng thay thế**

- A1. Phòng ban đã có tài khoản/lịch sử: ngừng dùng cho yêu cầu mới thay cho xóa sạch.
- A2. Xóa bản ghi nhập nhầm chỉ khi không có tham chiếu và được phép theo thiết kế dữ liệu.

**Luồng ngoại lệ**

- E1. Trùng mã, dữ liệu sai hoặc ràng buộc tham chiếu: không lưu/xóa.
- E2. Không được thay đổi phòng ban của một lịch cũ chỉ vì đổi danh mục hay điều chuyển tài khoản.

#### UC-18. Quản lý phòng họp và giờ phục vụ

- **Tác nhân chính:** Admin.
- **Điều kiện trước:** Có quyền quản lý phòng họp; áp dụng chính sách DP-01 đã chốt.
- **Điều kiện sau:** Lưu danh mục/cấu hình hợp lệ, giữ lịch sử và không tự hủy các lịch đã duyệt.
- **Căn cứ:** QD-09; BR-02; DP-01, DP-02; FR-20.

**Luồng chính**

1. Mở danh sách phòng và chọn thêm/sửa.
2. Nhập mã/tên, vị trí, sức chứa, thiết bị, trạng thái nhận đặt, giờ phục vụ và khoảng chuyển tiếp.
3. Kiểm tra dữ liệu; nếu thay đổi giờ/đệm thì đối chiếu lịch tương lai đã duyệt.
4. Lưu cấu hình cùng thời điểm có hiệu lực để tra cứu và báo cáo.
5. Các yêu cầu gửi/duyệt sau đó kiểm tra cấu hình hiện hành.

**Luồng thay thế**

- A1. Ngừng nhận đặt mới: không tiếp nhận/duyệt lượt đặt mới vào phòng đó; không tự hủy lịch đã duyệt.
- A2. Thay đổi cấu hình làm xung đột lịch đã duyệt: từ chối áp dụng, yêu cầu giải quyết lịch liên quan trước.

**Luồng ngoại lệ**

- E1. Sức chứa không hợp lệ, giờ phục vụ chồng nhau, mã trùng hoặc khoảng đệm sai: không lưu.
- E2. Không xóa phòng đã có lịch sử. Nếu giảm sức chứa làm một cuộc họp tương lai đã duyệt vượt sức chứa mới thì chưa áp dụng thay đổi đó, yêu cầu giải quyết lịch liên quan trước; không âm thầm làm sai điều kiện của lịch đã duyệt.

#### UC-19. Đăng xuất

- **Tác nhân chính:** Người dùng đang có phiên.
- **Điều kiện trước:** Có phiên hoặc dữ liệu phiên ở trình duyệt.
- **Điều kiện sau:** Phiên hiện tại được kết thúc theo cơ chế thu hồi; giao diện trở về đăng nhập; không còn dùng được quyền từ phiên đã kết thúc.
- **Căn cứ:** DP-05; FR-02.

**Luồng chính**

1. Người dùng chọn Đăng xuất.
2. Backend kết thúc phiên hiện tại; frontend xóa dữ liệu xác thực và nội dung riêng khỏi trạng thái giao diện.
3. Chuyển về đăng nhập; các lần gọi tiếp theo phải xác thực lại.

**Luồng thay thế**

- A1. Phiên đã hết hạn: xóa dữ liệu cục bộ và trở về đăng nhập.

**Luồng ngoại lệ**

- E1. Mất kết nối khi yêu cầu thu hồi: vẫn dọn trạng thái cục bộ, báo chưa xác nhận được thu hồi phía server; không giả báo đã hoàn tất phần server.

#### UC-20. Đổi mật khẩu

- **Tác nhân chính:** Người dùng đã xác thực hoặc đang đổi mật khẩu tạm.
- **Điều kiện trước:** Có phiên hợp lệ; cung cấp mật khẩu hiện tại/mật khẩu tạm.
- **Điều kiện sau:** Lưu băm mật khẩu mới, bỏ cờ mật khẩu tạm nếu có và kết thúc các phiên cần thu hồi theo thiết kế xác thực.
- **Căn cứ:** DP-05; FR-03.

**Luồng chính**

1. Mở chức năng, nhập mật khẩu hiện tại, mật khẩu mới và xác nhận.
2. Kiểm tra mật khẩu hiện tại, dữ liệu mới và chính sách mật khẩu được áp dụng.
3. Lưu mật khẩu đã băm; kết thúc phiên cũ phù hợp để yêu cầu đăng nhập lại.
4. Thông báo kết quả; không gửi hoặc ghi mật khẩu vào email/log.

**Luồng thay thế**

- A1. Đổi mật khẩu tạm lần đầu: hoàn thành bước này rồi mới cho dùng chức năng nghiệp vụ.

**Luồng ngoại lệ**

- E1. Mật khẩu hiện tại sai, xác nhận không khớp, mật khẩu mới không đạt hoặc lỗi lưu: không đổi mật khẩu.
- E2. Người khác hoặc Admin không xem lại được mật khẩu hiện tại qua chức năng này.

### 11. Yêu cầu phi chức năng và cách thể hiện OOP

| Mã | Yêu cầu | Cách đánh giá dự kiến |
|---|---|---|
| NFR-01 | Backend Python/FastAPI, frontend React qua RESTful API; mô tả API có thể kiểm tra | Đối chiếu mã nguồn và demo gọi API |
| NFR-02 | JWT có thời hạn; mật khẩu được băm; khóa tài khoản/thu hồi quyền có tác dụng ở server | Kiểm thử xác thực, khóa tài khoản và thay quyền; không chỉ nhìn nút UI |
| NFR-03 | Quyền trên từng lịch/tài liệu; không lộ nội dung qua bộ lọc, lỗi, URL, lịch sử hoặc báo cáo | Kiểm thử chéo vai trò, ngoài phạm vi, đổi ID trực tiếp và chỉ nhận bận/rảnh |
| NFR-04 | Xác nhận phòng/người và thay phiên bản/hủy nhất quán trong MySQL | Kiểm thử nhiều yêu cầu cạnh tranh bằng MySQL thật; giả lập lỗi giữa giao dịch |
| NFR-05 | Ghi log kỹ thuật và lịch sử quyết định; không ghi mật khẩu/token/bí mật SMTP | Kiểm tra log và lịch sử trong các luồng thành công/thất bại |
| NFR-06 | Gửi mail sau lưu; ghi trạng thái đợi/gửi được SMTP chấp nhận/lỗi; thử lại theo DP-08 | Thử SMTP lỗi và nhận thư thật; kết quả lưu lịch không bị đảo ngược |
| NFR-07 | Routing và State đồng bộ với kết quả API, có tải/lỗi/rỗng và chống gửi lặp thao tác | Demo đổi bộ lọc/trang, tải lại, mở trang từ URL, phiên hết hạn và dữ liệu đã bị người khác thay đổi |
| NFR-08 | Windows + Docker + LAN; dữ liệu MySQL và tệp được lưu bền qua khởi động lại container | Demo hai máy/trình duyệt qua IP LAN và khởi động lại stack; không hard-code localhost vào trình duyệt máy khác |

#### 11.1. Tổ chức theo hướng đối tượng

- **Đóng gói:** Đối tượng/Service quản lý quy tắc thời gian, chuyển trạng thái, đề nghị sửa và hủy; không để UI tự ghi trạng thái CSDL.
- **Trừu tượng và đa hình:** Repository và dịch vụ gửi email có giao diện rõ ràng; thay bộ gửi SMTP/repository bằng bản kiểm thử mà không sửa logic đặt phòng.
- **Kế thừa:** Dùng lớp trừu tượng/giao diện ở điểm có hành vi chung thật sự. Vai trò Nhân viên/Người duyệt/Admin là quyền và phạm vi phân công, không ép thành một cây kế thừa làm mất khả năng kiêm nhiệm.
- **SOLID:** Tách tiếp nhận API, nghiệp vụ lịch, truy cập dữ liệu, email và báo cáo. Truyền phụ thuộc để kiểm thử nghiệp vụ độc lập.
- **Mẫu thiết kế ứng viên:** Repository và Unit of Work phục vụ dữ liệu/giao dịch; cơ chế phát sự kiện sau lưu để kích hoạt email; xử lý trạng thái chỉ tách thành State Pattern nếu độ phức tạp thực tế cần đến. Không đặt chỉ tiêu phải nhét đủ một số lượng pattern cố định.
- **Kiểm thử:** Unit test kiểm tra quy tắc thời gian/trạng thái bằng phụ thuộc giả; integration test kiểm tra ràng buộc và cạnh tranh thao tác trên MySQL thật. Không dùng chỉ một test bộ nhớ làm bằng chứng chống đặt trùng khi triển khai.

#### 11.2. Tài liệu tải lên

Thiết kế dự kiến theo DP-06 dùng danh sách định dạng cho phép, giới hạn dung lượng và kiểm tra định dạng cơ bản; không chỉ tin tên mở rộng/Content-Type do client gửi. Lưu tên nội bộ, giữ tên hiển thị như metadata và phục vụ qua API kiểm tra quyền. Không đặt tệp nội bộ thành thư mục công khai của web. Cơ chế này giảm rủi ro nhưng không được tuyên bố “đã quét virus” nếu chưa có công cụ và kiểm chứng tương ứng.

### 12. Trường dữ liệu nghiệp vụ dự kiến

Đây là danh sách dữ liệu để đặc tả form/API về sau, chưa phải thiết kế bảng, khóa hay sơ đồ CSDL cuối cùng. Mỗi trường viện dẫn DP tuân thủ quyết định tương ứng đã chốt; chi tiết ánh xạ bảng/khóa sẽ được thiết kế ở bước CSDL.

| Nhóm | Thông tin cần quản lý |
|---|---|
| Tài khoản | Mã nhân viên, họ tên, email duy nhất, phòng ban, trạng thái, nhóm quyền, thông tin xác thực được bảo vệ |
| Phòng ban | Mã, tên, trạng thái dùng cho yêu cầu mới |
| Phòng họp | Mã/tên, vị trí, sức chứa, thiết bị, trạng thái nhận đặt, giờ phục vụ/ngày nghỉ, khoảng chuyển tiếp và lịch sử cấu hình |
| Yêu cầu họp | Tiêu đề, nội dung, phòng, bắt đầu/kết thúc, người tạo, chủ trì, thành phần và bắt buộc/tùy chọn |
| Yêu cầu công tác | Mục đích, địa điểm, phòng ban phụ trách, bắt đầu/kết thúc, người đi theo DP-03 |
| Quyết định/đề nghị | Loại tạo/sửa/hủy, bản gốc và phiên bản, nội dung đề nghị, trạng thái, người xử lý, lý do, thời điểm |
| Tài liệu | Tên hiển thị/tên lưu, định dạng, dung lượng, người tải, cuộc họp, phiên bản, tình trạng hiển thị và thời điểm |
| Email | Sự kiện nghiệp vụ, người nhận phù hợp, trạng thái gửi, số lần thử, lỗi được lược bỏ bí mật và thời điểm thử lại |
| Lịch sử | Ai thực hiện, hành động, đối tượng, phiên bản và thời điểm; nội dung chỉ đọc theo quyền |

Múi giờ hiển thị thống nhất theo Việt Nam (Asia/Ho_Chi_Minh); backend phải dùng cách lưu và chuyển đổi nhất quán, không dùng múi giờ máy chủ một cách ngầm định. Lịch cũ đã duyệt được giữ như lịch sử khi thay đổi tài khoản/danh mục, không tự dịch thời gian hoặc tự đổi chủ thể nghiệp vụ.

### 13. Kịch bản nghiệm thu

Bảng là tiêu chí để viết kiểm thử và tổ chức demo ở giai đoạn cài đặt. **Chưa nghiệm thu 44 kịch bản này trên website FastAPI/React hoàn chỉnh. Các kết quả kiểm chứng CSDL và hợp đồng/DTO ở mức thành phần được ghi riêng tại mục 15, không thay thế nghiệm thu ứng dụng.**

| Mã | Tình huống | Kết quả mong đợi | Căn cứ |
|---|---|---|---|
| KT-01 | Hai thao tác duyệt cùng phòng và chồng giờ | Chỉ một lượt đặt được xác nhận | Quy tắc đã chốt |
| KT-02 | Cuộc họp trước kết thúc 10:00, cuộc sau bắt đầu 10:00 | Chặn nếu phòng có khoảng đệm 15 phút | Quy tắc đã chốt |
| KT-03 | Cuộc họp trước kết thúc 10:00, cuộc sau bắt đầu 10:15 | Không báo xung đột với cuộc trước nếu các điều kiện khác hợp lệ | Quy tắc đã chốt |
| KT-04 | Hai yêu cầu chờ duyệt trùng phòng/giờ | Có cảnh báo, chưa yêu cầu nào giữ phòng | Quy tắc đã chốt |
| KT-05 | Một yêu cầu đã được duyệt sau khi yêu cầu khác được gửi | Kiểm tra lại và chặn thao tác duyệt yêu cầu xung đột | Quy tắc đã chốt |
| KT-06 | Hải là người bắt buộc của hai lịch chồng giờ | Không duyệt được lịch mới | Quy tắc đã chốt |
| KT-07 | Hải chỉ tham gia tùy chọn ở một trong hai lịch | Hiển thị cảnh báo xung đột | Quy tắc đã chốt |
| KT-08 | Người duyệt thao tác ngoài phạm vi hoặc tự duyệt yêu cầu của mình | Từ chối thao tác | Quy tắc đã chốt |
| KT-09 | Đề nghị đổi sang phòng đã được giữ | Báo lỗi; lịch cũ giữ nguyên | Quy tắc đã chốt |
| KT-10 | Đề nghị sửa đang chờ thì phòng mới được lịch khác giữ | Không duyệt được bản sửa; lịch cũ giữ nguyên | Quy tắc đã chốt |
| KT-11 | Bản sửa được duyệt hợp lệ | Lịch mới có hiệu lực và giải phóng lượt đặt cũ nhất quán | Quy tắc đã chốt |
| KT-12 | Lưu bản sửa gặp lỗi giữa chừng | Hoàn tác; lịch cũ và dữ liệu liên quan không bị mất | Quy tắc đã chốt |
| KT-13 | Email gửi thất bại sau khi duyệt | Lịch vẫn được xác nhận; tình trạng email được ghi nhận đúng | Quy tắc đã chốt |
| KT-14 | Người tạo hủy lịch họp hợp lệ trước giờ bắt đầu | Lịch đã hủy; phòng và khoảng chuyển tiếp của lượt đặt đó được giải phóng | Quy tắc đã chốt |
| KT-15 | Lịch họp bị hủy khi có đề nghị sửa đang chờ | Đề nghị sửa hết hiệu lực; không thể duyệt để khôi phục lịch cũ | Quy tắc đã chốt |
| KT-16 | Hủy một cuộc họp có người đang bận ở lịch khác | Chỉ bỏ bận do cuộc họp bị hủy; giữ nguyên lịch khác | Quy tắc đã chốt |
| KT-17 | Đề nghị hủy công tác còn chờ duyệt | Lịch công tác gốc vẫn được tính là bận | Quy tắc đã chốt |
| KT-18 | Đề nghị hủy công tác được chấp thuận | Lịch gốc đã hủy; bỏ bận do lịch này; giữ lịch sử | Quy tắc đã chốt |
| KT-19 | Đề nghị hủy công tác bị từ chối hoặc rút | Lịch gốc giữ nguyên | Quy tắc đã chốt |
| KT-20 | Rút yêu cầu tạo lịch chưa duyệt | Yêu cầu hết hiệu lực, không ảnh hưởng lịch đã duyệt khác | Quy tắc đã chốt |
| KT-21 | Nhân viên xem lịch không liên quan qua lịch chung, tìm kiếm hoặc URL/API | Chỉ nhận bận/rảnh, không nhận tiêu đề/nội dung riêng | Quy tắc đã chốt |
| KT-22 | Người duyệt xem lịch ngoài phạm vi hoặc Admin chỉ có quyền kỹ thuật xem chi tiết bất kỳ | Không cho truy cập chi tiết ngoài quyền | Quy tắc đã chốt |
| KT-23 | Người tham gia ở phòng ban khác mở lịch mình được mời | Được xem chi tiết theo quyền tham gia | Quy tắc đã chốt |
| KT-24 | Email hủy thất bại sau khi đã lưu hủy | Lịch vẫn đã hủy; lỗi email được ghi nhận để gửi lại | Quy tắc đã chốt |
| KT-25 | Đổi từ phòng A sang B do hai người khác nhau phụ trách | Người phụ trách phòng B duyệt bản sửa; chỗ A chỉ giải phóng sau khi duyệt thành công | DP-07 |
| KT-26 | Gửi trước 30 phút nhưng người duyệt xử lý khi còn 10 phút | Được xét nếu chưa bắt đầu và còn hợp lệ; không áp lại 30 phút vì thời gian chờ xử lý | DP-02 |
| KT-27 | Cuộc họp kết thúc 12:00 với khoảng đệm 15 phút | Đệm tới 12:15 có thể trùng giờ nghỉ; lịch tiếp theo vẫn theo giờ phục vụ và khoảng đệm | DP-01 |
| KT-28 | Tăng đệm từ 15 lên 30 phút làm hai lịch đã duyệt bị xung đột | Không áp dụng cấu hình làm hỏng các lịch đã duyệt; không tự hủy lịch | DP-01 |
| KT-29 | Nhóm công tác có thành viên ở hai phòng ban | Hướng dẫn tách yêu cầu theo phòng ban; không để một người duyệt ngoài phạm vi | DP-03 |
| KT-30 | Công tác nhiều ngày có khoảng ban đêm ở giữa | Kiểm tra toàn bộ khoảng đăng ký, không tự bỏ qua phần thời gian | DP-03 |
| KT-31 | Người tạo tổ chức thay, không tham gia; chủ trì và người mời có bản ghi trùng | Đếm người tham gia không trùng; chủ trì là bắt buộc; không tính người tạo nếu không tham gia | DP-04 |
| KT-32 | Một đề nghị sửa/hủy khác đang chờ cho cùng lịch | Yêu cầu rút đề nghị trước khi gửi loại/nội dung mới | DP-07 |
| KT-33 | Duyệt yêu cầu tạo lịch khi đã tới giờ bắt đầu | Yêu cầu hết hiệu lực, không tạo lịch bận có hiệu lực muộn | DP-07 |
| KT-34 | Gửi lại bản sửa bị mất chỗ trong lúc chờ | Rút đề nghị cũ rồi gửi phương án khác; lịch gốc không thay đổi | DP-07 |
| KT-35 | Tải tệp sai định dạng hoặc lớn hơn 20 MB | Từ chối tải; không có metadata giả hoặc tệp công khai ngoài quyền | DP-06 |
| KT-36 | Người không tham gia đổi mã tệp trên URL | API không trả nội dung tệp riêng | BR-08 và DP-06 |
| KT-37 | Người tạo bổ sung biên bản sau họp | Lưu phiên bản/lịch sử tài liệu, không sửa hiệu lực đặt phòng | DP-06 |
| KT-38 | SMTP không hoạt động sau lần gửi ban đầu | Lịch vẫn lưu đúng; thực hiện tối đa ba lần thử lại; sau đó ghi thất bại | DP-08 |
| KT-39 | SMTP chấp nhận nhưng chưa quan sát được thư ở hộp thư thật | Không coi đó là bằng chứng thư đã vào hộp thư đến; nghiệm thu kiểm tra hộp thư thật | DP-08 |
| KT-40 | Phòng có 8 giờ phục vụ, 3 giờ họp và 0,5 giờ chuyển tiếp | Tỷ lệ giờ họp theo kế hoạch 37,5%; chuyển tiếp báo riêng | DP-09 |
| KT-41 | Kỳ báo cáo không có giờ phục vụ | Tỷ lệ hiển thị không áp dụng; không chia cho 0 | DP-09 |
| KT-42 | Tổng hợp các phòng có số giờ phục vụ khác nhau | Cộng tổng giờ họp và tổng giờ phục vụ rồi chia, không trung bình đơn giản các tỷ lệ | DP-09 |
| KT-43 | Đăng xuất/khóa tài khoản nhưng màn hình cũ còn dữ liệu quyền | Các lần truy cập tiếp theo bị kiểm tra lại, không sử dụng quyền cũ để duyệt | DP-05 và NFR-02 |
| KT-44 | Hai máy trên LAN cùng xem rồi cùng thao tác giữ phòng | Backend kiểm tra lại lúc xác nhận; chỉ một lịch xung đột được giữ; UI máy còn lại nhận lỗi đúng | QD-08 và NFR-08 |

### 14. Đối chiếu với yêu cầu HTTT10 và tài liệu học phần

| Yêu cầu | Nội dung đáp ứng trong đặc tả | Bằng chứng dự kiến khi cài đặt |
|---|---|---|
| Đặt phòng họp | UC-02, UC-03, UC-04; BR-02/BR-03 | Tìm phòng, gửi/duyệt, cạnh tranh giữ chỗ và khoảng đệm |
| Đăng ký lịch công tác | UC-05, UC-06; UC-15, UC-16 | Công tác được duyệt và kiểm tra xung đột người tham gia |
| Email | FR-22, BR-05; DP-08 | Hộp thư thật và tình huống SMTP lỗi |
| Tài liệu họp | UC-09; DP-06 | Tải lên, tải theo quyền, lưu phiên bản |
| Thống kê mức độ sử dụng phòng | UC-10, BR-06; DP-09 | Bảng/biểu đồ theo lịch đặt với công thức được chốt |
| Routing và State nhiều phòng ban | FR-23, NFR-07, UC-02 | Lọc lịch/điều hướng và trạng thái cập nhật theo API |
| Python và RESTful API có xác thực | QD-01 đến QD-05; UC-01 | Backend FastAPI, JWT, tài liệu API và React kết nối |
| UML | Mã UC và luồng tại mục 10; bộ UML theo bản chốt 1.3 | Đã có 56 sơ đồ thiết kế; kiểm chứng sự phù hợp với mã nguồn ở giai đoạn cài đặt |
| OOP/SOLID/phân tầng/ORM/kiểm thử | Mục 11 | Mã nguồn, sơ đồ lớp, unit/integration test phù hợp |

#### 14.1. Nguồn đối chiếu

- File môn học **DS_Tieu luan_OOP_App(2).pdf**, trang PDF 1 và 3: yêu cầu chung, công nghệ và phạm vi HTTT10.
- File **INF1043_ĐCCT_PTUDHDT_2026(1).pdf**, trang PDF 3, 8–10: chuẩn đầu ra, ngoại lệ/log/kiểm thử và sản phẩm cuối kỳ.
- File **Chu de 1_Phan tich Tk voi UML(1).pdf**, trang PDF 1: cấu trúc đặc tả Use Case; các trang còn lại hướng dẫn sơ đồ.
- Các chủ đề SOLID, Design Pattern, OOP, kiến trúc đa tầng, xây dựng chương trình, UI/UX và lưu trữ dữ liệu đã được gửi; dùng làm hướng dẫn thiết kế, không coi các ví dụ tình nguyện/bán hàng là yêu cầu nghiệp vụ của HTTT10.
- [Microsoft Learn - Manage resource mailboxes](https://learn.microsoft.com/en-us/exchange/recipients-in-exchange-online/manage-resource-mailboxes): ví dụ mô hình duyệt tài nguyên, giờ phục vụ và giới hạn đặt; không dùng các giá trị mặc định của dịch vụ đó làm quy định của đề tài.
- [Google Calendar - Access permissions](https://support.google.com/calendar/answer/15716974): ví dụ tách quyền xem bận/rảnh và xem chi tiết.
- [OWASP - File Upload](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html): căn cứ kỹ thuật cho kiểm tra tệp, quyền truy cập và cách lưu tệp nội bộ; giá trị 20 MB trong DP-06 là giới hạn đã chốt riêng cho dự án.
