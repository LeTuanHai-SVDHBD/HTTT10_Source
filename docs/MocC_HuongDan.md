# Mốc C — Gửi và phê duyệt yêu cầu tạo lịch

Ngày 15/11/2026. Phiên bản 0.3.0. Nhánh `dev`.

## 1. Cập nhật từ mốc A/B đang chạy

Mở PowerShell tại thư mục có `compose.yaml`:

```powershell
git switch dev
git pull --ff-only origin dev
docker compose up -d --build
docker compose ps -a
```

Mở lại [website](http://localhost:8080), nhấn `Ctrl+F5` và đăng nhập bằng tài khoản hiện tại. Giữ nguyên `.env` và volume MySQL. Không bootstrap lại Admin, không xóa volume, không tạo lại CSDL. Mốc C sử dụng các bảng baseline đã có, không có migration mới. `migrate` kết thúc `Exited (0)` là trạng thái thành công, không phải chưa chạy.

Nếu thư mục cũ còn là bản giải nén ZIP, xem cách sao chép code mới vào đúng thư mục đang chạy ở `MocB_HuongDan.md`. Không đổi sang thư mục Compose mới rồi nhầm volume mới với dữ liệu cũ bị mất.

Nếu Git báo có thay đổi cục bộ, giữ lại và đối chiếu trước khi pull; không dùng `reset --hard`. Nếu stack lỗi, lấy log:

```powershell
docker compose logs --tail 100 migrate api web
```

## 2. Chuẩn bị tài khoản/phạm vi để demo

Dùng Admin ở mốc B:

1. Tạo tài khoản A có quyền **Nhân viên**.
2. Tạo tài khoản B có quyền **Người phê duyệt**; thêm quyền Nhân viên nếu B cũng cần gửi yêu cầu.
3. Mở **Phòng họp → Người duyệt**, phân công B cho phòng dùng để demo.
4. Mở **Phòng ban → Người duyệt**, phân công B cho phòng ban của A nếu thử công tác.
5. A và B phải hoạt động và đã đổi mật khẩu tạm.

Người duyệt phải khác người gửi. Nếu B tự gửi, cần người C được phân công duyệt thay. Admin không tự nhận quyền tạo lịch, xem nội dung riêng hoặc duyệt chỉ vì có vai trò quản trị.

Có thể dùng hai trình duyệt/cửa sổ riêng tư để demo A và B. HTTT10 giữ token trong bộ nhớ từng trang; tải lại trang sẽ cần đăng nhập lại.

## 3. Gửi yêu cầu họp

Đăng nhập A, chọn **Tạo yêu cầu lịch**:

1. Chọn loại **Họp tại phòng nội bộ**.
2. Nhập tiêu đề, mục đích, thời gian bắt đầu/kết thúc và phòng họp.
3. Thêm người tham gia, chọn bắt buộc/tùy chọn; chủ trì luôn nằm trong nhóm bắt buộc.
4. Chọn **Kiểm tra phương án**.
5. Nếu có xung đột, điều chỉnh phương án rồi kiểm tra lại. Nếu có cảnh báo, đọc và đánh dấu xác nhận.
6. Chọn **Gửi yêu cầu chờ duyệt**.

Cuộc họp dài 15 phút–4 giờ, bắt đầu sau ít nhất 30 phút và trong 90 ngày tới; nằm trọn trong một khoảng phục vụ. Ví dụ chọn một ngày làm việc tương lai 09:00–10:00 theo múi giờ Việt Nam. Sức chứa tính cả người tùy chọn.

Gửi thành công chỉ tạo **Chờ duyệt**; chưa giữ phòng/người. Hệ thống kiểm tra lại tại lúc gửi, không tin kết quả kiểm tra trước đó nếu dữ liệu đã đổi. Nếu cảnh báo đổi, hộp xác nhận mới xuất hiện; phải đọc và xác nhận lại.

## 4. Gửi công tác cá nhân/nhóm

Chọn loại **Công tác cá nhân / nhóm**, nhập thời gian đã gồm di chuyển, địa điểm, trong/ngoài đơn vị và thành viên cùng phòng ban của người gửi.

Mọi người đi công tác đều bắt buộc. Khoảng công tác liên tục có thể qua đêm/nhiều ngày; không áp giới hạn 4 giờ hoặc giờ phục vụ phòng họp. Không gộp người thuộc nhiều phòng ban trong một yêu cầu. Hệ thống vẫn kiểm tra trùng thời gian của người và người duyệt thay.

## 5. Duyệt hoặc từ chối

Đăng nhập B, mở **Chờ tôi duyệt → Xem chi tiết**:

- Đọc phương án và thành phần. Chọn **Duyệt và xác nhận lịch** để chấp thuận.
- Khi từ chối, nhập lý do rồi chọn **Từ chối**.
- Nếu xuất hiện cảnh báo mới, đọc và xác nhận trước khi tiếp tục.
- Khi dữ liệu đã đổi, dùng **Tải trạng thái mới**, xem lại rồi chủ động thao tác; không tự duyệt lại bằng phiên bản vừa tải.

Khi duyệt, server đọc lại quyền/phân công, trạng thái phòng, giờ phục vụ, sức chứa, thành viên và lịch hiệu lực. Không áp lại yêu cầu gửi trước 30 phút cho thời gian người duyệt đã chờ; nhưng phải còn trước giờ bắt đầu.

| Tình huống | Kết quả |
|---|---|
| Phòng đã có lịch được duyệt, kể cả phần đệm | Chặn chấp thuận; yêu cầu còn chờ nếu chưa hết hạn |
| Người bắt buộc trùng với lịch bắt buộc | Chặn chấp thuận |
| Ít nhất một bên là người tùy chọn | Cảnh báo và yêu cầu xác nhận |
| Chỉ có yêu cầu khác còn chờ | Cảnh báo; chưa coi tài nguyên đã giữ |
| Người duyệt không đúng phạm vi hoặc tự duyệt | Server từ chối |
| Hai người duyệt hai yêu cầu trùng cùng lúc | Chỉ một lịch được giữ thành công |

Lưu hiệu lực lịch, quyết định, phiên bản, audit, hàng chờ email và biên nhận chống lặp trong cùng giao dịch. Lỗi ghi dữ liệu hoàn tác toàn bộ; không có lịch được giữ một nửa.

## 6. Theo dõi và rút yêu cầu

- **Yêu cầu của tôi:** lọc “Do tôi gửi” hoặc “Tôi được xem”; chọn trạng thái cần tìm. Mặc định là Chờ duyệt; chọn Đã duyệt/Tất cả để xem hồ sơ vừa được xử lý.
- **Rút yêu cầu:** chỉ người gửi, khi còn chờ và chưa đến giờ bắt đầu. Rút xong không giữ phòng/người. Đã được duyệt/từ chối/hết hạn thì không báo rút thành công.
- **Hồ sơ lịch:** lịch liên quan, phiên bản hiệu lực và lịch sử xử lý. Hồ sơ chưa xác nhận không có bản lịch hiệu lực.
- **Lịch công tác:** chọn đúng ngày của cuộc họp vừa được duyệt. Lịch chờ/từ chối/rút/hết hạn không tạo bận.

Người tạo/người tham gia/người duyệt đúng phạm vi được xem nội dung theo từng bản. Người khác chỉ xem bận/rảnh của lịch đã có hiệu lực; không lấy được tiêu đề, thành phần, nội dung, proposal hoặc lịch sử riêng qua UUID.

## 7. Hết hạn, cảnh báo và mất kết nối

API tự quét yêu cầu đến hạn mỗi 30 giây; nhiều tiến trình vẫn dùng khóa và kiểm tra trạng thái trong MySQL. Có thể chạy một lượt thủ công:

```powershell
docker compose exec api python -m app.cli expire-proposals
```

Nếu bấm duyệt/rút sau hạn nhưng trước lượt quét, server ghi EXPIRED rồi trả lỗi có `expiration_committed=true`. Đây là kết quả hết hạn đã được lưu, không phải lịch được duyệt. Khoảng tối đa một lượt quét trước khi giao diện thấy trạng thái DB mới là bình thường; tải lại danh sách để lấy trạng thái mới.

Cảnh báo có token xác nhận 5 phút gắn người thao tác, phương án và tập cảnh báo. Token không giữ chỗ và không thay token đăng nhập.

Một ý định gửi/duyệt/rút giữ nguyên `Idempotency-Key` khi thử lại. Nếu server đã lưu nhưng phản hồi bị mất, chọn **Thử lại cùng thao tác**; server trả ID cũ, không tạo lịch hoặc email lần nữa. Giao diện giữ ý định trong bộ nhớ khi chuyển các tab nội bộ. Nếu tải lại trang/đăng xuất trước khi nhận kết quả, đăng nhập rồi kiểm tra hồ sơ của mình trước khi tạo lại. Key có hạn 24 giờ; hết hạn cần đọc lại hồ sơ, không âm thầm tạo thao tác mới.

Mã tạo key dùng `crypto.getRandomValues` để hoạt động cả khi demo LAN qua HTTP, không phụ thuộc `crypto.randomUUID` chỉ có trong secure context.

## 8. Email ở mốc C

Mốc C ghi `outbox_events` và `email_deliveries` trong cùng giao dịch nghiệp vụ. Đây là hàng chờ, chưa có worker SMTP gửi thư thật. “Chờ gửi” và “SMTP tiếp nhận” là hai kết quả khác nhau; không báo đã gửi email khi chưa có SMTP. Sau này worker sẽ gửi/thử lại ngoài giao dịch, không thay đổi kết quả duyệt đã lưu.

## 9. Chạy bộ kiểm tra trên Docker, không cần cài PyMySQL vào Windows

Chỉ thực hiện nếu muốn tự chạy kiểm thử. Bộ test tạo các CSDL `*_test` trong MySQL test riêng, không dùng DB/volume của website. Chạy ở thư mục dự án:

```powershell
docker compose -p httt10-tests -f compose.test.yaml up --build --abort-on-container-exit --exit-code-from tests
```

Kết quả ghi vào `verification/auth-result.json`, `catalog-result.json`, `scheduling-result.json`. Xong có thể dọn stack test riêng:

```powershell
docker compose -p httt10-tests -f compose.test.yaml down
```

Giữ đúng `-p httt10-tests` và `-f compose.test.yaml`; file test không publish cổng MySQL, dùng dữ liệu tạm trong tmpfs. Mật khẩu trong file test chỉ dành cho DB thử tách biệt, không phải mật khẩu DB website.

Nếu chạy bằng Python trực tiếp trên Windows, cần `py -m pip install -r backend\requirements.txt`, MySQL test riêng và MYSQL_TEST_HOST/PORT/USER/PASSWORD phù hợp. Không chạy `py test_auth.py` khi chưa cài dependencies hoặc khi chỉ có MySQL Docker chưa publish cổng test. Chạy website qua Compose không cần cài dependencies vào Python Windows.

File Compose test đã kiểm tra tĩnh; việc chạy Docker Desktop Windows vẫn cần thực hiện trên máy bạn. Kết quả và giới hạn thực tế xem `verification/KetQuaKiemTraMocC.md`.

## 10. Phạm vi còn lại

Mốc C cài yêu cầu tạo lịch CREATE, chấp thuận/từ chối/rút/hết hạn và tra cứu. Sửa lịch đã duyệt, hủy họp trực tiếp, đề nghị/duyệt hủy công tác sẽ làm ở mốc D theo nghiệp vụ đã chốt. Chưa có tài liệu họp, gửi SMTP thật hoặc báo cáo. Không tự thêm nút sửa/hủy làm mất lịch cũ trước khi hoàn thành quy trình đó.
