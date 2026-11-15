# Mốc D — Sửa và hủy lịch đã duyệt

Ngày 15/11/2026. Phiên bản 0.4.0, nhánh `dev`.

## 1. Cập nhật dự án đang chạy

Mở PowerShell tại thư mục có `compose.yaml`:

```powershell
git switch dev
git pull --ff-only origin dev
docker compose up -d --build
docker compose ps -a
```

Mở lại [website](http://localhost:8080), nhấn `Ctrl+F5` rồi đăng nhập bằng tài khoản cũ. Giữ nguyên `.env`, volume MySQL và Admin đã tạo; không bootstrap lại hoặc dùng `down -v`. Mốc D sử dụng các bảng baseline hiện có, không có migration SQL mới. Service `migrate` ở `Exited (0)` là đã hoàn tất thành công.

Nếu thư mục cũ còn là ZIP chưa có Git, xem hướng dẫn sao chép code vào đúng thư mục Compose đang dùng trong `MocB_HuongDan.md`. Giữ nguyên tên/thư mục dự án Compose để tránh nhầm dữ liệu cũ với một volume mới. Nếu có chỉnh sửa cục bộ, giữ lại và đối chiếu trước khi pull; không dùng `reset --hard` để bỏ qua.

## 2. Điều kiện và tài khoản demo

Mốc D quản lý lịch **đã được duyệt** từ mốc C. Cần:

- Người tạo A: đã tạo lịch họp hoặc công tác và lịch đó đã được duyệt, chưa bắt đầu.
- Người duyệt: tài khoản hoạt động, có vai trò Người phê duyệt và đúng phạm vi, khác người gửi.
- Khi thử đổi từ phòng A101 sang B201: phân công người duyệt cho **B201**. Người phụ trách A101 không mặc nhiên được duyệt B201.
- Công tác dùng người duyệt được phân công cho phòng ban của lịch gốc.

Chỉ người tạo quản lý sửa/hủy toàn lịch. Người tham gia, người chủ trì hoặc Admin không có quyền hủy/sửa hộ chỉ từ các vai trò đó. Chưa có cơ chế Admin hủy khẩn cấp thay người tạo.

## 3. Đề nghị sửa lịch họp hoặc công tác

1. Đăng nhập người tạo → **Hồ sơ lịch → Xem chi tiết**.
2. Chọn **Đề nghị sửa lịch**. Biểu mẫu lấy dữ liệu từ phiên bản đang có hiệu lực.
3. Sửa thời gian, phòng, nội dung hoặc thành phần phù hợp loại lịch. Không đổi họp thành công tác; không đổi phòng ban của lịch công tác.
4. Chọn **Kiểm tra phương án**, xem xung đột/cảnh báo. Việc kiểm tra loại trừ chính lịch gốc để không tự báo trùng với bản cũ.
5. Xác nhận cảnh báo nếu có → **Gửi đề nghị sửa lịch**.

Chỉ có tối đa một đề nghị sửa/hủy đang chờ trên mỗi lịch. Muốn thay nội dung một đề nghị chờ, mở **Yêu cầu của tôi**, rút đề nghị đó rồi gửi bản mới. Giao diện không tự thay phiên bản mới vào biểu mẫu cũ để ghi đè.

**Trong lúc chờ:** lịch gốc, phòng cũ và bận của thành viên cũ vẫn có hiệu lực. Phòng/giờ mới chưa được giữ. Khi đổi phòng, đề nghị đi tới người phụ trách phòng mới. Người tham gia mới được xem đề nghị liên quan, không tự được đọc nội dung riêng của bản gốc.

Công tác vẫn giới hạn nhóm cùng phòng ban, mọi người đều bắt buộc và thời gian gồm di chuyển. Điều chuyển tài khoản/danh mục không tự đổi phòng ban đã lưu trên revision lịch sử.

## 4. Duyệt hoặc từ chối bản sửa

Người duyệt đúng phạm vi mới → **Chờ tôi duyệt → Xem chi tiết**:

1. Xem phương án mới và phần so sánh: giờ/phòng/phòng ban gốc cùng tên nhóm trường thay đổi.
2. Chọn **Duyệt bản sửa lịch**, xác nhận các cảnh báo hiện tại nếu có.
3. Hoặc nhập lý do và chọn **Từ chối**.

So sánh gốc không trả tiêu đề, mô tả hoặc danh sách thành viên gốc riêng tư cho người chỉ có quyền ở bản mới. Có thể xem đầy đủ một bản lịch qua danh sách phiên bản chỉ khi API cho phép trên bản đó.

| Tình huống | Kết quả |
|---|---|
| Bản sửa hợp lệ và được duyệt | Đổi current sang revision mới, chỉ một bản có hiệu lực; giải phóng lượt cũ trong cùng giao dịch |
| Bị từ chối hoặc người gửi rút | Lịch gốc không đổi |
| Chỗ mới đã được một lịch khác giữ khi gửi | Chặn gửi đề nghị, yêu cầu chọn lại |
| Khi gửi trống nhưng trong lúc chờ có lịch khác được duyệt | Chặn chấp thuận, giữ đề nghị PENDING nếu còn hạn; giữ nguyên lịch gốc |
| Có người bắt buộc bận ở lịch khác | Chặn; nếu ít nhất một bên tùy chọn thì cảnh báo |
| Lịch gốc đã bắt đầu hoặc base/version đã đổi | Không áp quyết định cũ |

Khi thay thế, lịch cũ và mới đều được khóa theo hợp tài nguyên: root/proposal → phòng tăng dần → phòng ban tăng dần → người tăng dần. Lỗi ghi dữ liệu hoàn tác toàn bộ; không giải phóng lịch cũ trước commit. Bản sửa thua khi hai người tranh cùng chỗ mới vẫn giữ lịch cũ.

## 5. Hủy lịch họp trực tiếp

1. Người tạo → **Hồ sơ lịch → Xem chi tiết → Hủy lịch họp**.
2. Đọc tác động, nhập lý do → **Xác nhận hủy lịch họp**.
3. Server kiểm tra lại chủ lịch, phiên bản và điều kiện chưa bắt đầu.

Hủy hợp lệ giải phóng phòng, phần đệm và bận do chính cuộc họp tạo ra. Nếu có đề nghị sửa chờ, đề nghị đó đồng thời chuyển EXPIRED với lý do lịch gốc bị hủy. Không được duyệt bản sửa cũ để khôi phục lịch đã hủy. Không có thêm cấp phê duyệt hủy họp.

Hủy họp trả `CommandReceipt.proposal_id=null`: đây là thao tác trực tiếp, không tạo yêu cầu hủy giả. Lịch hủy vẫn giữ current revision để tra cứu lịch sử; các view hiệu lực không còn tính lịch đó. Người ngoài quyền không đọc được nội dung/lý do hủy.

## 6. Đề nghị và duyệt hủy công tác

1. Người tạo → **Hồ sơ lịch → Xem chi tiết → Đề nghị hủy công tác**.
2. Nhập lý do → **Gửi đề nghị hủy công tác**.
3. Lịch công tác và bận vẫn có hiệu lực trong lúc chờ.
4. Người phụ trách phòng ban → **Chờ tôi duyệt**, xem đề nghị → **Chấp thuận hủy công tác**, hoặc từ chối kèm lý do.

Chấp thuận mới hủy lịch và giải phóng bận. Từ chối/rút/hết hạn giữ lịch gốc. CANCEL dùng base revision, không tạo revision nội dung giả; `candidate=null` trong chi tiết đề nghị là đúng. Lý do ban đầu của đề nghị được giữ trong audit theo quyền, kể cả sau khi đề nghị bị từ chối hoặc rút và người dùng gửi đề nghị khác.

Nếu công tác đang có bản sửa chờ, phải rút bản sửa trước khi gửi hủy và ngược lại. Người gửi không tự duyệt/từ chối đề nghị của mình. Không dùng API hủy họp để hủy công tác trực tiếp.

## 7. Hạn xử lý và cạnh tranh

- CREATE hết hạn ở giờ bắt đầu phương án.
- CHANGE hết hạn ở mốc **sớm hơn giữa giờ bắt đầu gốc và giờ bắt đầu mới**.
- CANCEL công tác hết hạn khi lịch gốc bắt đầu.

Lượt quét 30 giây và lệnh `python -m app.cli expire-proposals` đã mở rộng cho cả ba loại. Bản sửa/hủy hết hạn không thay current gốc. Thao tác duyệt/rút tới hạn có thể lưu EXPIRED rồi trả 409 với `expiration_committed=true`.

Nếu duyệt sửa và hủy họp cạnh tranh bằng cùng phiên bản root, chỉ một thao tác được áp dụng. Thao tác còn lại phải tải trạng thái mới. Hai đề nghị sửa cho một root không thể cùng chờ; hai bản sửa tranh một chỗ mới không thể cùng được giữ.

## 8. Phiên bản, thông báo và quyền lịch sử

**Hồ sơ lịch → Các phiên bản được phép xem** cho xem lại nội dung bất biến đã lưu. Người tạo xem các bản của lịch mình; người khác chỉ thấy các revision mà họ được tham gia/phụ trách. Người chỉ có quyền trên bản cũ có thể xem lịch sử cũ, còn root hiện tại chỉ trả bận/rảnh nếu bản mới ngoài phạm vi. Không suy quyền toàn bộ root từ một revision đã từng được xem.

Thông báo bản sửa cho đối tượng của bản mới. Khi bản sửa được duyệt, sự kiện giải phóng riêng gắn **revision cũ** để thông báo cho người cũ/người phụ trách phòng cũ mà không lộ nội dung mới. Audit cũng gắn revision và được lọc riêng. Chưa có worker SMTP gửi thư thật; hàng chờ không phải bằng chứng đã nhận email.

Mọi command D tiếp tục dùng idempotency. Nếu mất phản hồi sau khi server đã lưu, **Thử lại cùng thao tác** giữ nguyên key/body, kể cả hủy họp có proposal_id null. Không tạo lại bằng key mới khi chưa kiểm tra kết quả. Tải lại trang/đăng xuất làm mất ý định lưu trong bộ nhớ trình duyệt: đăng nhập và đọc hồ sơ trước khi gửi lại.

## 9. Kiểm thử

Không cần cài dependencies vào Python Windows để chạy bộ test Docker riêng:

```powershell
docker compose -p httt10-tests -f compose.test.yaml up --build --abort-on-container-exit --exit-code-from tests
```

Bộ test chạy lần lượt A/B/C/D, kết quả ghi `verification/auth-result.json`, `catalog-result.json`, `scheduling-result.json`, `amendments-result.json`. DB test tách biệt, không publish cổng và không dùng volume website. Xong dọn riêng stack test:

```powershell
docker compose -p httt10-tests -f compose.test.yaml down
```

Nếu tự chạy Python, cài `backend/requirements.txt`, thiết lập MySQL test riêng cùng MYSQL_TEST_HOST/PORT/USER/PASSWORD rồi chạy `test_amendments.py` từ `backend`. Script tự tạo CSDL `httt10_amendments_*_test`, không ghi fixture vào DB website. `TEST_RESULT_DIR` tùy chọn định vị thư mục báo cáo.

Kết quả và giới hạn thực tế xem `verification/KetQuaKiemTraMocD.md`. Kiểm tra React/JSDOM không thay cho bố cục trình duyệt thật, Docker Desktop Windows, Nginx hoặc LAN hai máy. File Compose test đã được kiểm tra tĩnh; không báo đã chạy Docker khi môi trường chưa hỗ trợ.

## 10. Phần còn lại

Mốc D hoàn thành nhóm sửa/hủy đã chốt. Chưa có quản lý tài liệu họp, worker SMTP gửi thật/thử lại hoặc báo cáo mức độ đặt phòng theo kế hoạch. Các phần này và kiểm thử tổng thể Windows/Docker/LAN tiếp tục ở các mốc sau.
