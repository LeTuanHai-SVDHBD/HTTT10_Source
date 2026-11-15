# Mốc D — Kết quả kiểm tra

Ngày 15/11/2026. Phiên bản 0.4.0, MySQL Community 8.4.0.

**Backend: 327/327 đạt** — A: 28, B: 83, C: 105, D: 111. Cả bốn suite chạy trên MySQL thật, dùng CSDL test riêng; D tạo/duyệt lịch gốc và sửa/hủy bằng API/Service thật.

**React DOM: 24/24 đạt** — 10 luồng hồi quy C và 14 luồng D. React 19.1.1 + JSDOM 26.1.0 gọi HTTP proxy thử nghiệm/FastAPI/Uvicorn/MySQL thật. Có giả lập mất phản hồi sau commit của gửi sửa và hủy họp; kiểm tra retry cùng key, receipt proposal_id null và lịch sử cũ ngoài quyền bản mới.

React/Vite production build thành công. OpenAPI thực tế có 43 thao tác, ba command D bắt buộc Idempotency-Key. Python compile/format và git diff --check đạt. Compose test đã kiểm tra tĩnh, giữ DB thử trong tmpfs, không publish cổng hoặc dùng volume website.

## Phạm vi và kết quả chính

- CHANGE PENDING giữ current gốc, phòng/người cũ; APPROVED chỉ đổi current sau khi kiểm tra lại và commit.
- REJECTED/WITHDRAWN/EXPIRED, mất chỗ mới, lỗi sau UPDATE và thua cạnh tranh đều giữ lịch gốc phù hợp.
- Thứ tự khóa hợp phòng/phòng ban/người cũ/mới; hai đổi phòng ngược chiều hợp lệ cùng hoàn thành, hai bản sửa tranh một chỗ mới chỉ một thắng.
- Hủy họp chỉ người tạo trước giờ bắt đầu; giải phóng phòng, đệm/người và vô hiệu CHANGE chờ trong cùng transaction.
- CANCEL công tác không tạo revision giả; chờ/từ chối/rút/hết hạn giữ công tác, chỉ APPROVED mới hủy. Lý do yêu cầu ban đầu được giữ trong audit theo quyền.
- Deadline CHANGE là min(giờ bắt đầu gốc, giờ mới); CANCEL dùng giờ gốc. Sweep hỗ trợ cả ba loại.
- Phạm vi duyệt theo phương án mới, không tự duyệt/từ chối. Người cũ không đọc nội dung mới; lịch sử và audit lọc từng revision, kể cả khi bản mới riêng tư đã hủy.
- Event giải phóng lịch cũ gắn revision và danh sách người nhận cũ riêng; không đưa nội dung mới vào payload của người cũ.
- Idempotency replay sau trạng thái/phiên bản đã đổi không ghi thêm revision/quyết định/event. Receipt hủy họp trực tiếp có proposal_id=null được UI xử lý.

## Giới hạn kiểm chứng

- JSDOM là mô phỏng DOM, không kiểm tra CSS/bố cục hoặc hành vi trình duyệt thật. Chromium ở môi trường này chưa khởi chạy được do Unix socket bị chặn.
- Chưa build/chạy Docker image, Docker Desktop Windows, Nginx end-to-end hoặc LAN hai máy trong môi trường kiểm tra. Compose test chỉ được kiểm tra cấu hình tĩnh.
- Chưa gửi SMTP thật. Outbox/email_deliveries được ghi trong transaction, không coi PENDING là thư đã gửi.
- Chưa có quản lý tài liệu họp và báo cáo. Mốc D không có quyền Admin hủy hộ hoặc khôi phục lịch đã hủy.
- Baseline 24 bảng/3 view không đổi, không có migration mới. CSDL thử được tách khỏi CSDL website.

## Luồng React DOM mốc D

| STT | Luồng | Kết quả |
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

## Kiểm tra API/transaction mốc D

| STT | Kiểm tra | Kết quả |
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
| 111 | OpenAPI mốc D công bố 43 thao tác | PASS |
