# Mốc C — Kết quả kiểm tra

Ngày 15/11/2026. Phiên bản ứng dụng 0.3.0; FastAPI 0.141.1, SQLAlchemy 2.0.44, MySQL Community 8.4.0.

**Backend: 216/216 kiểm tra đạt** (28 mốc A, 83 mốc B, 105 mốc C). Cả ba suite dùng CSDL MySQL test tách biệt; các luồng C gửi và phê duyệt qua API/Service thật.

**React DOM: 10/10 luồng đạt** bằng React 19.1.1 + JSDOM 26.1.0 + HTTP proxy thử nghiệm + FastAPI/Uvicorn + MySQL thật. Có giả lập mất phản hồi và HTTP 503 sau commit để kiểm tra giữ nguyên idempotency key khi thử lại. Đây là mô phỏng DOM, không phải kiểm thử Chromium hay xác nhận CSS/bố cục.

React/Vite production build thành công. Khóa thao tác tạo bằng getRandomValues và đã kiểm tra định dạng/không phụ thuộc randomUUID cho HTTP LAN. Compose test đã parse/kiểm tra tách service/network project, DB tmpfs không publish cổng, thư mục kết quả cấu hình được. Chưa chạy Docker image/Compose thực tế trong môi trường này.

## Những tình huống chính đã kiểm chứng

- CREATE PENDING chưa giữ tài nguyên; chỉ APPROVED mới có current revision/bận phòng và người.
- Cùng phòng và khoảng đệm; người bắt buộc trùng ở hai phòng; ít nhất một bên tùy chọn thì cảnh báo.
- Công tác liên tục qua đêm/nhiều ngày, đúng phòng ban; người duyệt thay khác người gửi.
- Quyền mới được đọc tại server; không tự duyệt/từ chối, không suy quyền nghiệp vụ từ Admin.
- Header idempotency bắt buộc, replay trước kiểm tra phiên bản cũ, key khác payload/target bị chặn, key hết hạn không tự tạo lịch mới.
- Token cảnh báo gắn actor/payload/tập cảnh báo/hạn dùng, không thay token đăng nhập; cảnh báo đổi buộc xác nhận lại.
- Quyết định, hiệu lực, phiên bản, audit, outbox/delivery và receipt cùng giao dịch; lỗi sau UPDATE rollback toàn bộ.
- EXPIRED có thể được commit rồi trả 409 với expiration_committed=true; sweep lặp không nhân đôi event.
- Hai POST cùng key cạnh tranh chỉ tạo một root; hai duyệt cùng phòng/chung người và duyệt/rút cạnh tranh chỉ một kết quả thắng.
- DTO che title/ID/revision/thành phần/lịch sử ngoài quyền; quyền đọc được xét theo từng revision.

## Giới hạn và việc cần thử trên máy người dùng

- Chưa xác nhận bố cục hoặc thao tác bằng trình duyệt thật; Chromium không khởi chạy trong môi trường kiểm tra vì Unix socket bị chặn. JSDOM không kiểm tra layout/CSS, hành vi mạng của trình duyệt hoặc tương thích thiết bị.
- Chưa chạy Docker Desktop Windows, build image, Nginx end-to-end hay LAN hai máy. File compose.test.yaml được kiểm tra tĩnh, không báo đã chạy thành công Docker.
- Chưa gửi SMTP thật, chưa có Worker email. Số bản ghi PENDING trong email_deliveries không phải số email đã gửi.
- Mốc C chỉ CREATE và các quyết định/từ chối/rút/hết hạn của CREATE; CHANGE/CANCEL thuộc mốc D. Chưa có tài liệu hoặc báo cáo.
- Giới hạn chờ khóa MySQL là 10 giây mỗi lượt, thử lại toàn transaction tối đa 3 lượt khi deadlock/lock timeout; không giả báo thành công khi hết lượt.

## Kiểm tra React DOM

| STT | Luồng | Kết quả |
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

## Kiểm tra API/transaction mốc C

| STT | Kiểm tra | Kết quả |
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
| 105 | OpenAPI mốc C có 40 operation thật | PASS |
