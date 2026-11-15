# Mốc B — Kết quả kiểm tra

Ngày 15/11/2026. Ứng dụng 0.2.0, FastAPI 0.141.1, Pydantic 2.13.4, SQLAlchemy 2.0.44, MySQL Community 8.4.0.

**API: 111/111 đạt** — 28 kiểm tra hồi quy mốc A và 83 kiểm tra mốc B. Tất cả chạy với MySQL thật trong CSDL test riêng; không dùng SQLite hoặc ghi dữ liệu thử vào CSDL ứng dụng.

Frontend React 19.1.1 / Vite 6.3.6: `npm run build` thành công. `tzdata==2025.2` cung cấp dữ liệu múi giờ khi Docker/Windows không có zoneinfo hệ điều hành; đã kiểm tra Asia/Ho_Chi_Minh với PYTHONTZPATH rỗng.

## Phạm vi kiểm chứng

- Mật khẩu tạm, phân quyền Admin, dữ liệu duy nhất và phiên bản chống ghi đè.
- Cấp/khóa/đặt lại mật khẩu, thu hồi phiên và bảo vệ Admin cuối cùng, gồm hai thao tác đồng thời.
- Phân công duyệt phòng/phòng ban, thu hồi quyền và cập nhật phiên bản phạm vi bị ảnh hưởng.
- Cấu hình phòng theo phiên bản, giờ Việt Nam, ngày ngoại lệ, sức chứa và khoảng chuyển tiếp.
- Calendar DETAIL/BUSY_ONLY, chỉ phiên bản có hiệu lực, không lộ title/ID ngoài quyền; bộ lọc AND và đệm riêng.
- Availability: đủ thiết bị AND/sức chứa, giờ phục vụ, hai phía đệm, thời hạn, exclude theo chủ lịch, cảnh báo yêu cầu chờ không giữ phòng.
- Không làm sai lịch đã duyệt khi giảm sức chứa/đổi giờ/tăng đệm; rollback giữ nguyên phiên bản cấu hình.

## Giới hạn còn lại

Chromium thử nghiệm không khởi chạy do môi trường chặn Unix socket; chưa có kết quả kiểm thử hoặc xác nhận bố cục/thao tác trên trình duyệt cho mốc B. Không tạo file browser-result PASS. Kiểm tra trực tiếp theo `docs/MocB_HuongDan.md`.

Chưa chạy Docker Desktop Windows, build image Docker, Nginx end-to-end hoặc LAN hai máy. Không coi build React/API ASGI là bằng chứng của các phần đó.

Các lịch đã xác nhận/chờ/hủy trong test B là fixture ghi trực tiếp vào CSDL test để kiểm chứng truy vấn và bảo vệ cấu hình. Chưa triển khai/kiểm chứng luồng người dùng nộp/duyệt lịch của mốc C, tài liệu, SMTP hay báo cáo. Baseline nghiệp vụ vẫn 24 bảng và 3 view; không thay schema/migrate lại dữ liệu mốc A.

## Danh sách kiểm tra mốc B

| STT | Kiểm tra | Kết quả |
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
| 83 | OpenAPI công bố 28 thao tác đã cài | PASS |
