# Mốc B — Hướng dẫn cập nhật và kiểm tra

Ngày: 15/11/2026. Phiên bản ứng dụng: 0.2.0. Nhánh làm việc: `dev`.

## 1. Cập nhật dự án đang chạy trên Windows

Mở PowerShell trong thư mục có `compose.yaml` và chạy:

```powershell
git switch dev
git pull --ff-only origin dev
docker compose up -d --build
docker compose ps -a
```

Nếu `git switch` hoặc `git pull` báo có thay đổi cục bộ, xem `git status` và giữ lại các chỉnh sửa trước khi tiếp tục. Không dùng `reset --hard` để bỏ qua lỗi. Mốc B dùng nguyên cấu trúc baseline, không cần tạo lại CSDL hoặc tạo Admin lần nữa. Giữ nguyên `.env` và volume `mysql_data`. Service `migrate` kết thúc với `Exited (0)` là bình thường.

Nếu thư mục hiện tại được giải nén từ ZIP nên chưa có `.git`, clone repo vào thư mục tạm để lấy code mới:

```powershell
cd ..
git clone --branch dev --single-branch https://github.com/LeTuanHai-SVDHBD/HTTT10_Source.git HTTT10_Source_dev
```

Sau đó sao chép `backend`, `frontend`, `docs`, `scripts`, `verification`, `README.md`, `compose.yaml` từ thư mục mới vào **thư mục dự án cũ**. Thực hiện `docker compose up -d --build` từ thư mục cũ như trước. Cách này giữ tên dự án Compose và volume đang dùng. Không chạy stack từ thư mục mới ngay: Docker có thể tạo một volume mới nên bạn sẽ tưởng dữ liệu/tài khoản cũ bị mất.

Mở lại [website](http://localhost:8080) rồi nhấn `Ctrl+F5`. Đăng nhập bằng Admin và mật khẩu bạn đã đổi ở mốc A. Nếu có lỗi khởi động:

```powershell
docker compose logs --tail 100 migrate api web
```

Không chạy `docker compose down -v`. Không sinh lại `.env` cho DB đã có dữ liệu.

## 2. Tài khoản và nhóm quyền

1. Chọn **Tài khoản → Cấp tài khoản**.
2. Nhập mã nhân viên, họ tên, email, phòng ban, trạng thái và mật khẩu tạm 12–128 ký tự.
3. Chọn một hoặc nhiều vai trò: Nhân viên, Người phê duyệt, Quản trị viên.
4. Lưu, sau đó đăng nhập tài khoản vừa cấp trong trình duyệt khác hoặc cửa sổ riêng tư.
5. Người dùng phải đổi mật khẩu tạm rồi đăng nhập lại.

Admin được sửa thông tin, khóa/mở khóa, đặt lại mật khẩu tạm và thay tập vai trò. Không có xóa tài khoản làm mất lịch sử. Hệ thống chặn khóa hoặc gỡ quyền Admin hoạt động cuối cùng, kể cả khi hai Admin thao tác đồng thời.

Đổi vai trò, trạng thái, email hoặc phòng ban sẽ thu hồi các phiên của tài khoản đó. Chỉ đổi tên/mã nhân viên không thu hồi phiên. Đặt lại mật khẩu cũng thu hồi phiên và buộc đổi lại mật khẩu tạm. Không hiển thị lại mật khẩu/hash từ API.

Admin không tự có vai trò Nhân viên hoặc Người phê duyệt. Có thể cấp kết hợp khi có nhu cầu, nhưng quyền duyệt còn cần phân công phạm vi.

## 3. Phòng ban và người duyệt công tác

1. **Phòng ban → Thêm phòng ban**: nhập mã duy nhất, tên và trạng thái nhận yêu cầu mới.
2. Muốn cập nhật: chọn **Sửa**. Ngừng nhận mới giữ nguyên dữ liệu và lịch sử.
3. Để phân công: tài khoản đích cần có vai trò **Người phê duyệt** và trạng thái **Hoạt động**.
4. Chọn **Người duyệt**, đánh dấu tài khoản và **Lưu phân công**.

Hộp phân công hiển thị số yêu cầu đang chờ có thể bị ảnh hưởng, không hiển thị nội dung riêng của các yêu cầu. Có thể chủ động thu hồi hết phân công; giao diện cảnh báo khi không còn người duyệt. Nên có hai người để xử lý khi người được phân công cũng là người gửi yêu cầu. Không cho tự duyệt và không tự chuyển quyền nghiệp vụ cho Admin; việc nộp/duyệt thực tế được triển khai ở mốc C.

## 4. Phòng họp, thiết bị và giờ phục vụ

Danh mục baseline có A101 và B201. Admin có các thao tác:

- **Thêm phòng họp:** nhập mã, tên, vị trí, trạng thái, thiết bị và cấu hình ban đầu. Tạo phòng và cấu hình trong cùng giao dịch.
- **Sửa thông tin:** thay metadata/thiết bị và trạng thái nhận mới.
- **Cấu hình giờ:** thêm phiên bản sức chứa, đệm và giờ phục vụ/ngày ngoại lệ.
- **Người duyệt:** phân công người duyệt riêng cho phòng đó.
- **Lịch sử cấu hình:** xem toàn bộ phiên bản, gồm các cấu hình chưa tới ngày hiệu lực.

Giờ mặc định: thứ Hai–thứ Sáu, 08:00–12:00 và 13:00–17:00; đệm 15 phút sau họp. Có thể thêm/xóa từng khoảng phục vụ, ngày nghỉ cả ngày hoặc ngày mở cửa theo các khoảng riêng. Tất cả giờ phục vụ thuộc múi giờ Việt Nam. Không có khoảng phục vụ của một ngày thì ngày đó nghỉ.

Cấu hình mới có hiệu lực ở hiện tại/tương lai; không ghi đè bản cũ. Khi xét lịch, chọn cấu hình hiệu lực tại lúc bắt đầu cuộc họp. Phiên bản ban đầu của phòng mới có thể bắt đầu trước hiện tại để phòng sử dụng được ngay.

Hệ thống từ chối cấu hình mới nếu nó làm một lịch đã duyệt vượt sức chứa, nằm ngoài giờ phục vụ, hoặc chồng lịch do tăng đệm. Khoảng đệm có thể chạy vào giờ nghỉ: cuộc họp kết thúc 12:00 vẫn hợp lệ, phòng bị chặn tới 12:15.

Ngừng nhận mới không tự hủy các lịch đã duyệt. Khi thu hồi vai trò Người phê duyệt/khóa tài khoản, các phân công hiện có bị vô hiệu và phiên bản phòng/phòng ban liên quan được tăng để chặn ghi đè từ màn hình cũ.

## 5. Xem lịch

1. Chọn **Lịch công tác**.
2. Chọn ngày/giờ bắt đầu–kết thúc, phòng họp và/hoặc người dùng.
3. Bấm **Xem lịch**.

Bộ lọc phòng và người dùng kết hợp theo AND. Để xem toàn bộ lịch của một phòng, chọn phòng đó và chọn **Không lọc người**. Khi không chọn phòng/người, hệ thống mặc định lịch cá nhân. Khoảng truy vấn tối đa 93 ngày.

Chỉ lịch đã xác nhận, chưa hủy và phiên bản đang có hiệu lực xuất hiện. Chờ duyệt không tạo bận. Người tạo/người tham gia/người duyệt đúng phạm vi được xem tiêu đề; người khác chỉ nhận khoảng bận. Admin không tự có quyền xem chi tiết. API bận/rảnh không trả mã lịch, mã phiên bản, tiêu đề, mô tả hoặc danh sách người tham gia. Đệm hiển thị thành một khoảng riêng khi xem phòng, không tạo bận cho người.

Nếu mới hoàn thành mốc A–B, lịch trống là bình thường: mốc C mới có chức năng tạo và duyệt lịch. Không thêm lịch mẫu đã duyệt vào DB của bạn để giả lập chức năng đó. Dữ liệu lịch trong bộ kiểm thử chỉ nằm ở các CSDL test riêng.

## 6. Tìm phòng trống

1. Chọn **Tìm phòng trống**.
2. Nhập khoảng thời gian, số người (gồm cả người tùy chọn), các thiết bị cần có.
3. Bấm **Tìm phòng**.

Cuộc họp dài 15 phút–4 giờ, bắt đầu sau ít nhất 30 phút, trong 90 ngày tới và nằm trọn trong một khoảng phục vụ. Thiết bị lọc theo AND, phòng phải đủ sức chứa và đang nhận mới. Xét cả đệm của lịch trước và đệm của lượt đang tìm so với lịch tiếp.

Kết quả không giữ phòng. Nếu có yêu cầu chờ cho cùng khoảng thời gian thì vẫn có thể tìm thấy phòng, kèm cảnh báo; không tiết lộ tiêu đề của yêu cầu đó. Khi có API nộp/duyệt ở mốc C, hệ thống sẽ kiểm tra lại dữ liệu hiện tại trước khi giữ chỗ.

Ô nhập ngày/giờ dùng múi giờ máy đang mở trình duyệt và ghi rõ trên nhãn; giờ phục vụ và thời gian hiển thị kết quả theo Việt Nam. Nên đặt múi giờ Windows là UTC+07:00 để demo thuận tiện.

## 7. Khi có người khác sửa trước

Thao tác sửa tài khoản, phòng ban, phòng, cấu hình và phân công phải gửi phiên bản dữ liệu đã đọc. Nếu nhận “Dữ liệu đã thay đổi”, đóng biểu mẫu và bấm **Tải lại**, kiểm tra thông tin mới rồi thao tác lại. Không tự gửi lại bản cũ bằng phiên bản vừa đọc để ghi đè thay đổi của người khác.

## 8. Kiểm thử và phạm vi

Kết quả API tự động xem `verification/KetQuaKiemTraMocB.md`, `auth-result.json`, `catalog-result.json`. Hai script backend tự tạo CSDL tên `httt10_auth_*_test` và `httt10_catalog_*_test`, không ghi dữ liệu thử vào `httt10`. Chạy từ `backend` sau khi cài requirements, với MySQL test riêng và MYSQL_TEST_HOST/PORT/USER/PASSWORD. Tài khoản test phải được cấp quyền tạo CSDL test:

```powershell
py test_auth.py
py test_catalog.py
```

Thử trực tiếp trên Windows: tạo phòng ban/tài khoản, đăng nhập nhân viên và đổi mật khẩu, phân công người duyệt, thêm cấu hình phòng, tìm phòng ở giờ hợp lệ và giờ nghỉ. Kiểm tra nhân viên không có nút quản trị và Swagger từ chối API quản trị khi dùng token nhân viên. Không chụp mật khẩu/JWT thật trong báo cáo.

Chưa cài trong mốc B: nộp/duyệt/sửa/hủy lịch, tài liệu họp, email SMTP thật, báo cáo. Docker Desktop Windows, Nginx và LAN cần kiểm chứng trên máy bạn. Không coi kết quả ASGI/trình duyệt với proxy thử nghiệm là bằng chứng đã kiểm tra Docker/LAN.
