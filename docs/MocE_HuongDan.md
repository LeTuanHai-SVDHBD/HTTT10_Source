# Mốc E — Tài liệu họp

Ngày 15/11/2026. Phiên bản 0.5.0, nhánh `dev`. Có 49 thao tác API thực tế, thêm 6 API tài liệu trên các bảng baseline hiện có; không có migration mới.

## 1. Cập nhật

Tại thư mục Compose đang dùng, mở PowerShell:

```powershell
git switch dev
git pull --ff-only origin dev
docker compose up -d --build
docker compose ps -a
```

Giữ nguyên `.env`, tên dự án Compose, volume MySQL và tài khoản cũ. Không bootstrap lại Admin. Mở [website](http://localhost:8080), `Ctrl+F5` rồi đăng nhập. `migrate` thoát mã 0 là bình thường. Nếu có chỉnh sửa cục bộ, lưu và đối chiếu trước khi pull.

API được gắn thêm volume `document_data:/app/data/documents`. Không dùng `docker compose down -v`: lệnh đó xóa cả dữ liệu lịch và tài liệu. Nginx nhận request tối đa 21 MiB, API vẫn giới hạn từng tệp chính xác 20 MiB (20 × 1024 × 1024 byte).

## 2. Dùng tài liệu

1. Người tạo mở **Hồ sơ lịch → Xem chi tiết**, hoặc **Yêu cầu của tôi → Xem chi tiết** với yêu cầu họp CREATE/CHANGE đang chờ.
2. Trong **Tài liệu họp**, chọn **Tạo tài liệu mới**, nhập tên, chọn tệp và **Lưu tài liệu**.
3. Muốn cập nhật: chọn **Phiên bản mới: [tên tài liệu]** trong **Lưu vào tài liệu**, chọn tệp rồi lưu. Phiên bản cũ vẫn giữ nguyên.
4. **Tải xuống v…** tải đúng phiên bản qua phiên đăng nhập. Không có liên kết tệp công khai.
5. **Ẩn tài liệu** yêu cầu lý do và kiểm tra phiên bản mới nhất. **Hiện tài liệu đã ẩn** cho phép tra cứu/tải lịch sử trong phạm vi được phép. Tệp đã ẩn không được thêm phiên bản; chưa có khôi phục hoặc xóa vật lý qua API.

Nhận PDF, DOCX, PPTX, XLSX, JPG, JPEG, PNG, từ 1 byte đến 20 MiB/tệp. API kiểm tra nội dung định dạng, cấu trúc ZIP/XML của Office, kích thước ảnh/giải nén; không chỉ tin phần mở rộng hoặc MIME do trình duyệt gửi. Tệp hỏng, Office có macro VBA, ZIP mã hóa hoặc vượt giới hạn xử lý bị từ chối. Đây không phải dịch vụ quét virus; chưa xác minh mở tệp bằng Microsoft Office hay mọi biến thể tài liệu thực tế.

Nếu mất mạng/phản hồi sau khi lưu, giao diện yêu cầu **Tải lại tài liệu** và đối chiếu trước khi gửi lại. Upload không có cơ chế idempotency; không bấm gửi lại mù. Nếu có người vừa cập nhật, API trả 409 khi `expected_latest_version_id` đã cũ.

## 3. Quyền và ngữ cảnh

| Người/ngữ cảnh | Hành vi |
|---|---|
| Người tạo lịch họp | Thêm tài liệu/phiên bản vào bản hiện tại hoặc phương án CREATE/CHANGE đang chờ, chưa hết hạn |
| Cuộc họp đã bắt đầu/kết thúc | Người tạo vẫn bổ sung biên bản vào bản hiện tại |
| Người tham gia hoặc người duyệt đúng phạm vi | Đọc/tải những phiên bản tệp gắn bản lịch họ được xem |
| Admin chỉ có vai trò quản trị | Không mặc nhiên đọc hoặc quản lý tài liệu họp |
| Bản lịch cũ đã thay thế; đề nghị bị rút/từ chối/hết hạn | Giữ lịch sử, không thêm tệp vào ngữ cảnh đó |
| Lịch họp đã hủy | Toàn bộ tài liệu chỉ đọc theo quyền lịch sử |
| Công tác | Không có tài liệu họp |

Ví dụ đổi phòng A101 sang B201, đồng thời thay người tham gia: tệp gắn bản A101 không tự hiện cho người mới của B201. Tệp gắn phương án B201 không lộ cho người chỉ có quyền A101. Tên tài liệu gốc cũng không được dùng khi người xem chỉ có quyền với phiên bản mới; API dùng tên tệp được phép thay thế.

Mặc định danh sách lọc theo bản lịch đang xem. Chọn **Xem tài liệu các bản lịch được phép** để tìm tài liệu cũ và thêm phiên bản mới vào ngữ cảnh hiện tại. Backend vẫn lọc từng phiên bản. Khi bộ lọc đang giấu phiên bản mới nhất, tài liệu không hiện thao tác thay/ẩn; bật tùy chọn xem các bản lịch để đối chiếu phiên bản mới nhất trước khi ghi. Mục xem lịch sử không có biểu mẫu ghi. Nếu phiên bản mới nhất của tài liệu thuộc ngữ cảnh chỉ đọc thì không ẩn tài liệu từ ngữ cảnh đó.

Thêm tệp/ẩn tệp không đổi nội dung, phòng, người tham gia hoặc `row_version` của lịch; không cần duyệt lại lịch. Thao tác ghi khóa lịch → tài liệu → người thao tác, kiểm tra lại phiên/quyền rồi ghi metadata/audit trong transaction.

## 4. API

| Phương thức | Đường dẫn sau `/api/v1` | Kết quả |
|---|---|---|
| GET | `/schedules/{id}/documents` | Trang tài liệu, lọc `context_revision_id`, `include_hidden` |
| POST | `/schedules/{id}/documents` | Tạo tài liệu + phiên bản 1, trả `DocumentVersionView` (201) |
| GET | `/documents/{id}/versions` | Trang phiên bản được phép, lọc ngữ cảnh |
| POST | `/documents/{id}/versions` | Thêm phiên bản, trả `DocumentVersionView` (201) |
| POST | `/documents/{id}/hides` | Ẩn mềm (204) |
| GET | `/documents/{id}/versions/{version_id}/content` | Nội dung nhị phân attachment, no-store/nosniff |

Upload dùng multipart: `metadata` là JSON (chuỗi hoặc part JSON), `file` là một tệp. Tạo mới dùng `{context_revision_id, display_name}`; thêm phiên bản dùng `{context_revision_id, expected_latest_version_id}`. Ẩn gửi JSON `{expected_latest_version_id, reason}`. Đọc danh sách hỗ trợ `page`, `page_size` tối đa 100. Tải xuống dùng Authorization Bearer, không đưa JWT vào URL. Swagger: [API docs](http://localhost:8080/api/docs).

## 5. Kho tệp, sao lưu và dọn orphan

`DOCUMENT_STORAGE_DIR` mặc định `backend/data/documents` khi chạy Python; Compose dùng `/app/data/documents`. Các thư mục/tệp riêng tư có quyền 0700/0600 trong Linux. Tên vật lý được sinh ngẫu nhiên, không dùng tên do người dùng gửi; chỉ metadata nằm trong MySQL. API kiểm tra SHA-256/kích thước trước khi tải; tệp thiếu/hỏng trả lỗi an toàn 503 để quản trị viên khôi phục từ bản sao.

Tệp được staging, kiểm tra, publish nguyên tử trong cùng filesystem rồi commit metadata. Nếu lỗi trước commit, metadata rollback và byte không được tham chiếu được dọn. Nếu tiến trình chết hoặc commit không rõ kết quả, có thể còn orphan; thao tác bù chỉ xóa khi xác nhận DB không tham chiếu. Cơ chế khóa MySQL theo khóa tệp phối hợp upload với dọn orphan.

Xem trước orphan cũ hơn 24 giờ:

```powershell
docker compose exec api python -m app.cli document-storage-cleanup
```

Sau khi đối chiếu và sao lưu, áp dụng:

```powershell
docker compose exec api python -m app.cli document-storage-cleanup --apply
```

Chỉ xóa staging/orphan quá hạn, bỏ qua upload đang khóa và giữ tất cả đối tượng có tham chiếu DB, kể cả phiên bản cũ/tài liệu ẩn. Không dùng lệnh này thay quy trình lưu trữ nghiệp vụ.

Sao lưu/khôi phục phải gồm **MySQL + volume document_data** cùng thời điểm, cùng cấu hình `.env`. Dừng API trong lúc lấy bản sao nhất quán; tệp ẩn vẫn cần sao lưu. Chưa tự động hóa backup/restore hoặc thử khôi phục trên Docker Desktop Windows.

## 6. Kiểm tra và phần còn lại

Bộ backend dùng MySQL thật, bao gồm kiểm thử A–D và `backend/test_documents.py`. Với Docker Desktop đã cài:

```powershell
docker compose -p httt10-tests -f compose.test.yaml up --build --abort-on-container-exit --exit-code-from tests
docker compose -p httt10-tests -f compose.test.yaml down -v
```

Lệnh `down -v` trên chỉ dành cho project test riêng `httt10-tests`, không dùng cho project dữ liệu thật. Báo cáo JSON được ghi vào `verification/`. Đã chạy kiểm thử Python/MySQL và React DOM+HTTP tại môi trường phát triển; chưa chạy chính stack Docker/Nginx, Windows, trình duyệt thật hoặc LAN. Xem [bằng chứng kiểm tra](../verification/KetQuaKiemTraMocE.md).

Còn worker SMTP thật/thử lại, báo cáo sử dụng và nghiệm thu tổng thể. Mốc E chưa phải xác nhận dự án hoàn tất triển khai thực tế.
