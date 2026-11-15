# Kiểm chứng mốc E — Tài liệu họp

Ngày 15/11/2026. FastAPI 0.141.1 / Starlette 1.10.0, Python 3.12, MySQL 8.4.0; React 19.1.1 / JSDOM 26.1.0. Nhánh `dev`, ứng dụng 0.5.0.

## Kết quả

| Nhóm | Đạt/tổng | Cách kiểm tra |
|---|---|---|
| Backend auth | 28/28 | MySQL thật + FastAPI ASGI TestClient |
| Backend catalog | 83/83 | MySQL thật + FastAPI ASGI TestClient |
| Backend scheduling | 105/105 | MySQL thật + FastAPI ASGI TestClient |
| Backend amendments | 111/111 | MySQL thật + FastAPI ASGI TestClient |
| Backend documents | 104/104 | MySQL thật + FastAPI ASGI TestClient |
| React scheduling | 10/10 | DOM mô phỏng + HTTP/API/MySQL thật |
| React amendments | 14/14 | DOM mô phỏng + HTTP/API/MySQL thật |
| React documents | 13/13 | DOM mô phỏng + HTTP/API/MySQL thật |
| Frontend production build | PASS | `npm run build --prefix frontend` |
| Compose và volume tài liệu | PASS | Parse YAML/kiểm tra cấu hình tĩnh |

React DOM đạt **37/37** kiểm tra. Backend đạt **431/431**; riêng tài liệu **104/104**. API thực tế có **49 thao tác**, khớp 6 API tài liệu trong hợp đồng mục tiêu 50 thao tác. Baseline 24 bảng/3 view giữ nguyên; không có migration mới.

## Nội dung đã kiểm chứng

- Upload/download đủ 7 phần mở rộng, đúng byte; tải xuống attachment/no-store/nosniff, không lộ storage_key/SHA-256.
- Người tạo quản lý, người tham gia/người duyệt đúng phạm vi đọc; Admin không tự có quyền. Tên nhãn, tên tệp, danh sách và tải xuống đều lọc theo context_revision_id.
- Đổi phòng/thành phần không chuyển quyền tệp cũ; phương án đang chờ có tài liệu riêng. Ngữ cảnh cũ/rút/từ chối/hết hạn/hủy chỉ đọc. Cho phép biên bản sau họp.
- Đúng 20 MiB được nhận; hơn giới hạn, chunked quá cỡ, file rỗng/giả định dạng, metadata sai, ZIP traversal/entity/macro/bomb bị chặn.
- Hai version cùng expected_latest chỉ một thắng; upload cạnh tranh hủy được tuần tự hóa bằng khóa root; ghi tài liệu không tăng row_version lịch.
- Kiểm tra lại phiên/quyền sau staging; lỗi sau publish rollback metadata, dọn byte chưa commit. Byte có tham chiếu không bị dọn; thiếu/hỏng byte trả 503 an toàn.
- Cleanup mặc định xem trước, giữ tệp mới/lịch sử và bỏ qua upload đang khóa.
- Giao diện gửi multipart, lưu version, tải blob đúng byte, thu hồi Object URL, ẩn có lý do và đối chiếu sau mất phản hồi. Người chỉ còn quyền lịch sử vẫn tải được tài liệu cũ, không có biểu mẫu ghi.

## Giới hạn

- JSDOM mô phỏng DOM; kiểm tra upload gửi sự kiện submit vì JSDOM không đồng bộ native required-file validation với FileList mô phỏng. Chưa xác minh bố cục CSS, hộp thoại lưu tệp hệ điều hành hoặc thao tác trên trình duyệt thật.
- Chưa build/chạy Docker image, Nginx end-to-end, Docker Desktop Windows, LAN hai máy hoặc thử backup/restore volume trong môi trường triển khai. Compose được kiểm tra tĩnh.
- Mẫu Office kiểm tra ZIP/XML và quyền truy cập, không thay kiểm tra mở bằng Microsoft Office với bộ tài liệu thực tế. Chưa có antivirus, quota tổng hoặc tự động sao lưu.
- File bytes và metadata không cùng một giao dịch ACID. Đã kiểm tra bù lỗi và dọn orphan; chưa mô phỏng mất điện/hỏng đĩa hoặc kết quả COMMIT mơ hồ ở tầng mạng thật.
- Chưa gửi SMTP thật hoặc làm báo cáo sử dụng. Không xem đây là nghiệm thu hoàn tất dự án.

## Kiểm tra tài liệu qua API

| STT | Kiểm tra | Kết quả |
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
| 103 | OpenAPI đủ 49 thao tác | PASS |
| 104 | OpenAPI upload trả DocumentVersionView | PASS |

## Luồng React tài liệu

| STT | Luồng | Kết quả |
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
| 12 | Người cũ tải tài liệu khi chỉ còn quyền bản lịch sử | PASS |
| 13 | Tài liệu lịch sử không cấp lại quyền ghi | PASS |

Tái chạy backend: xem [hướng dẫn mốc E](../docs/MocE_HuongDan.md). Các JSON kết quả trong thư mục này chứa từng kiểm tra và phạm vi tương ứng.
