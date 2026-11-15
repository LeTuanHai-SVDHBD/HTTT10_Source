# Mốc A - Kết quả kiểm tra

14/11/2026. FastAPI ASGI TestClient + MySQL Community 8.4.0: **28/28 kiểm tra đạt**.

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
| 27 | API thật chỉ công bố 6 operation mốc A | PASS |
| 28 | Lưu audit của các thao tác tài khoản | PASS |

Frontend: npm install và npm run build thành công (React 19.1.1, Vite 6.3.6). Màn hình login đã mở và kiểm tra trực quan trong browser preview. Preview chỉ phục vụ giao diện; kiểm tra auth dùng ASGI với DB riêng, chưa kiểm tra một luồng trình duyệt đi xuyên Nginx/Docker.

Compose YAML đã parse và kiểm tra các service/port/volume ở mức tĩnh; chưa chạy Docker Desktop Windows, image build hoặc LAN hai máy trong môi trường tạo gói. Chưa triển khai lịch/duyệt/SMTP, không coi mốc A là toàn bộ website đã hoàn tất. Cần chạy theo README trên Windows để kiểm chứng thực tế.
