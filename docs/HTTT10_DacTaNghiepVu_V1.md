# HTTT10 - Đặc tả chức năng, phân quyền và Use Case - Bản chốt 1.3

**Tên đề tài:** Ứng dụng kiến trúc Client–Server và RESTful API trong xây dựng hệ thống quản lý lịch công tác và đặt phòng họp nội bộ.

**Học phần:** Phát triển ứng dụng hướng đối tượng (INF1043).

**Ngày ghi nhận:** 14/11/2026.

**Cập nhật phiên bản 1.1:** Chốt quy trình hủy lịch và quyền xem lịch theo ủy quyền lựa chọn nghiệp vụ của người thực hiện đề tài. Bổ sung các quy tắc xử lý liên quan để thống nhất với cơ chế sửa lịch đã duyệt.

**Cập nhật dự thảo 1.2:** Hoàn thiện danh mục chức năng, ma trận quyền, 20 đặc tả Use Case và kịch bản nghiệm thu. UC-11 được làm rõ là quản lý tài khoản; quản lý phòng ban/phòng họp tách thành UC-17/UC-18; bổ sung UC-19 đăng xuất và UC-20 đổi mật khẩu.

**Xác nhận phiên bản 1.3:** Người thực hiện đề tài đã chốt toàn bộ DP-01 đến DP-09 trong trao đổi ngày 14/11/2026. Các quy tắc QD-01 đến QD-28, BR-01 đến BR-08 và chính sách bổ sung DP-01 đến DP-09 là căn cứ chính thức cho bộ UML và triển khai.

**Cách đọc:** Các Use Case, ma trận quyền và 44 kịch bản nghiệm thu áp dụng theo toàn bộ quy tắc đã chốt. Mã DP được giữ để truy vết quyết định, không còn là mục chờ duyệt. Các kịch bản nghiệm thu là yêu cầu cần kiểm chứng trong tương lai, chưa phải kết quả chạy thử ứng dụng.

## 1. Mục tiêu và căn cứ

Hệ thống hỗ trợ một đơn vị giả lập có nhiều phòng ban quản lý lịch họp, đặt phòng họp và đăng ký lịch công tác. Sản phẩm phục vụ báo cáo và demo học phần; không giả định đang triển khai cho một cơ quan thực tế cụ thể.

Căn cứ chính là file DS_Tieu luan_OOP_App(2).pdf, trang 1 và trang 3: sử dụng ngôn ngữ chính Python, xây dựng RESTful API có xác thực, kết nối frontend với backend; có sơ đồ Use Case, Lớp, Tuần tự, Hoạt động; có báo cáo và demo. HTTT10 gồm đặt phòng họp, đăng ký lịch công tác, thông báo email, tài liệu họp và thống kê sử dụng phòng.

Các nội dung OOP, SOLID, mẫu thiết kế, kiến trúc phân tầng, ORM, xử lý ngoại lệ, ghi log và kiểm thử được đối chiếu với đề cương và các chủ đề môn học đã gửi. Không tự bổ sung yêu cầu AI hoặc số lượng mẫu thiết kế cố định.

## 2. Các quyết định đã thống nhất

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

## 3. Nhóm quyền và phạm vi phê duyệt

### 3.1. Nhân viên

Nhân viên tạo yêu cầu họp/đặt phòng, đăng ký lịch công tác, xem chi tiết lịch mình tạo hoặc tham gia, xem bận/rảnh của các lịch khác và đề nghị chỉnh sửa lịch của mình. Người tạo được hủy lịch họp trước giờ bắt đầu; hủy lịch công tác đã duyệt cần người phụ trách phê duyệt. Quy trình cụ thể tại BR-07 và BR-08.

### 3.2. Người phê duyệt

Người phê duyệt được phân công một hoặc cả hai nhiệm vụ sau:

| Nhiệm vụ | Phạm vi | Ví dụ người đảm nhận |
|---|---|---|
| Duyệt đặt phòng họp | Các phòng họp được phân công quản lý | Cán bộ hành chính/văn phòng |
| Duyệt lịch công tác | Các phòng ban được phân công | Trưởng phòng hoặc người được ủy quyền |

Trưởng phòng không mặc nhiên được duyệt mọi phòng họp. Người phụ trách phòng họp không mặc nhiên được duyệt công tác của mọi phòng ban. Một tài khoản có thể được giao cả hai nhiệm vụ. Người phê duyệt được thực hiện chức năng nhân viên nếu được cấp quyền tương ứng.

### 3.3. Admin

Admin quản lý tài khoản, phòng ban, danh mục phòng họp, cấu hình phòng và phân công quyền duyệt. Quyền quản trị kỹ thuật không tự động tạo quyền phê duyệt nghiệp vụ; muốn duyệt phải được phân công quyền tương ứng.

## 4. Quy tắc kiểm tra lịch

### BR-01. Khoảng thời gian hợp lệ

Thời điểm bắt đầu phải trước thời điểm kết thúc. Giờ phục vụ, thời lượng và thời hạn đặt áp dụng theo DP-01 và DP-02 đã chốt.

### BR-02. Xung đột phòng và thời gian chuyển tiếp

Phòng được xem là chưa sẵn sàng cho cuộc họp kế tiếp trong suốt cuộc họp đã xác nhận và khoảng chuyển tiếp sau đó. Khoảng chuyển tiếp mặc định là 15 phút, cấu hình theo phòng. Khi kiểm tra một yêu cầu, phải bảo đảm khoảng cách phù hợp với cả lịch trước và lịch sau, không chỉ kiểm tra hai giờ bắt đầu có bằng nhau hay không.

Ví dụ phòng A đã có lịch 09:00–10:00, với khoảng chuyển tiếp 15 phút:

| Yêu cầu mới | Kết quả kiểm tra phòng |
|---|---|
| 09:30–10:30 | Xung đột giờ họp |
| 10:00–11:00 | Xung đột khoảng chuyển tiếp |
| 10:10–11:00 | Chưa đủ khoảng chuyển tiếp |
| 10:15–11:00 | Không xung đột với lịch trên; vẫn phải kiểm tra các điều kiện khác |

Không cộng thành hai khoảng 15 phút trước và sau để bắt buộc giãn 30 phút giữa cùng một cặp cuộc họp. Thời lượng họp và thời gian chuyển tiếp phải được phân biệt khi thống kê.

### BR-03. Yêu cầu chờ duyệt chưa giữ chỗ

Khi gửi yêu cầu, kiểm tra phòng và các lịch đã xác nhận. Nếu đã có xung đột thì báo lỗi để người gửi chọn lại. Các yêu cầu chờ duyệt có thể trùng nhau; hệ thống cảnh báo rõ rằng yêu cầu chưa giữ phòng. Gửi sớm hơn không tự động bảo đảm được duyệt trước.

Khi duyệt, phải kiểm tra lại dữ liệu hiện tại. Chỉ sau khi duyệt thành công, lượt đặt phòng mới có hiệu lực. Nếu hai thao tác duyệt cạnh tranh cùng một phòng trong khoảng thời gian xung đột, chỉ một thao tác được xác nhận thành công.

### BR-04. Xung đột người tham gia

Kiểm tra theo danh tính người tham gia, độc lập với kiểm tra phòng. Ví dụ Hải được xếp họp tại phòng A lúc 09:00–10:00 và phòng B lúc 09:30–10:30: hai phòng khác nhau nhưng Hải bị trùng lịch 09:30–10:00.

Lịch công tác bên ngoài cũng được tính khi kiểm tra xung đột. Ví dụ Hải có lịch công tác đã duyệt 08:00–11:00 thì một cuộc họp 09:00–10:00 có Hải là người bắt buộc tham gia sẽ xung đột.

Người chủ trì là người bắt buộc. Người được đăng ký đi công tác là người bắt buộc. Người được mời họp có thể thuộc diện bắt buộc hoặc tùy chọn. Nếu một người bắt buộc tham gia cả hai lịch đã xác nhận bị chồng giờ, không cho duyệt lịch mới. Nếu có ít nhất một bên là tùy chọn, hiển thị cảnh báo. Lịch đang chờ duyệt chỉ tạo cảnh báo. Kiểm tra lại khi duyệt và khi duyệt thay đổi.

Khoảng đệm phòng không tự động được áp dụng thành khoảng đệm di chuyển cá nhân; vấn đề di chuyển giữa các địa điểm được ghi tại mục 8.

### BR-05. Lưu dữ liệu và gửi email

Việc xác nhận lịch và các dữ liệu liên quan phải được lưu nhất quán. Chỉ gửi thông báo xác nhận sau khi dữ liệu đã được ghi thành công. Email thất bại không làm mất lịch đã lưu; phải ghi nhận tình trạng lỗi để gửi lại. Không được thông báo gửi email thành công khi thực tế mới đưa yêu cầu vào hàng chờ gửi.

### BR-06. Thống kê phòng

Thống kê dựa trên lịch đặt đã xác nhận, tách số lượt đã hủy và không cộng toàn bộ thời lượng của một lượt đặt đã hủy trước khi diễn ra vào tổng thời lượng họp đã lên lịch. Thời gian chuyển tiếp được tách khỏi thời lượng họp. Số liệu phản ánh kế hoạch đặt phòng; chưa đo được việc có người thực sự sử dụng phòng hay không. Công thức áp dụng tại DP-09, sử dụng giờ phục vụ DP-01 đã chốt.

### BR-07. Hủy lịch và rút yêu cầu

**Lịch họp đã duyệt:** Người tạo được hủy toàn bộ lịch trước giờ bắt đầu, nhập lý do và xác nhận thao tác. Không cần một lượt duyệt hủy vì cần giải phóng phòng kịp thời. Hệ thống lưu trạng thái đã hủy, giải phóng lượt giữ phòng cùng khoảng chuyển tiếp của lượt đặt đó và bỏ trạng thái bận do chính lịch này tạo ra. Những lịch khác của cùng người hoặc phòng vẫn được giữ nguyên. Email được gửi đến các bên liên quan sau khi lưu thành công. Việc một người tham dự không tham gia không được coi là quyền hủy toàn bộ cuộc họp.

**Lịch công tác đã duyệt:** Người tạo gửi đề nghị hủy có lý do. Trong lúc chờ, lịch công tác gốc vẫn có hiệu lực và vẫn được tính khi kiểm tra lịch bận. Người phụ trách phòng ban đúng phạm vi được duyệt hoặc từ chối, tuân thủ nguyên tắc không tự duyệt yêu cầu của mình. Duyệt hủy thành công mới chuyển lịch gốc sang đã hủy và bỏ trạng thái bận do lịch này tạo ra. Từ chối hoặc rút đề nghị hủy thì lịch gốc không thay đổi.

Trong phiên bản đầu, luồng hủy toàn bộ chỉ áp dụng trước khi lịch gốc bắt đầu; kiểm tra thời điểm này cả khi gửi lẫn khi duyệt. Lịch đã bắt đầu hoặc kết thúc không bị xóa/hủy hồi tố bằng luồng này. Các trường hợp chấm dứt công tác đang diễn ra thuộc phạm vi cần đặc tả riêng nếu bổ sung sau.

**Yêu cầu đang chờ duyệt:** Người gửi được rút yêu cầu tạo lịch chưa được duyệt, hoặc rút đề nghị sửa/hủy của mình. Rút một yêu cầu chờ không cần duyệt. Rút yêu cầu tạo lịch làm yêu cầu đó hết hiệu lực, không giải phóng bất kỳ phòng nào của lịch khác. Rút đề nghị sửa/hủy giữ nguyên lịch gốc đã duyệt.

**Phối hợp sửa và hủy:** Với lịch công tác, chỉ tồn tại tối đa một đề nghị sửa hoặc hủy đang chờ cho cùng lịch; muốn đổi loại đề nghị phải rút đề nghị hiện tại. Với lịch họp, khi người tạo hủy cuộc họp, mọi đề nghị sửa đang chờ của lịch đó hết hiệu lực trong cùng thao tác lưu. Không được duyệt một bản sửa cũ để làm lịch đã hủy có hiệu lực trở lại. Mọi thao tác rút/duyệt/hủy đều kiểm tra lại trạng thái mới nhất; không áp dụng quyết định trên phiên bản đã thay đổi.

**Lưu lịch sử:** Giữ bản ghi lịch đã hủy, lý do, người thao tác và thời điểm. Không dùng xóa dữ liệu để thay thế cho hủy nghiệp vụ. Email thất bại không khôi phục một lịch đã hủy thành công. Các quyền hủy khẩn cấp thay người tạo của Admin/người quản lý chưa nằm trong phạm vi đã thống nhất; cần đặc tả riêng trước khi bổ sung.

### BR-08. Quyền xem lịch và thông tin bận/rảnh

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

## 5. Đề nghị sửa lịch đã duyệt

### 5.1. Nguyên tắc hiệu lực

Lịch đang có hiệu lực và đề nghị sửa là hai thông tin cần phân biệt. Việc gửi đề nghị sửa không làm mất phòng cũ, không đổi lịch đang công bố và không tự giữ phòng mới. Những người bắt buộc của lịch cũ vẫn được tính là bận theo lịch cũ.

### 5.2. Luồng xử lý

1. Người tạo chọn lịch đã duyệt, còn chưa bắt đầu, rồi nhập nội dung đề nghị sửa.
2. Hệ thống kiểm tra phương án mới với lịch hiện có. Khi kiểm tra bản sửa phải loại trừ bản gốc của chính lịch đó để không báo xung đột với chính mình.
3. Nếu phương án mới đã xung đột với một lịch có hiệu lực, báo lỗi để người dùng chọn lại; lịch gốc không thay đổi.
4. Nếu kiểm tra hợp lệ, ghi nhận đề nghị sửa ở trạng thái chờ duyệt. Phương án mới chưa giữ phòng.
5. Người có quyền duyệt xem đề nghị và thực hiện duyệt hoặc từ chối theo phạm vi được phân công.
6. Trước khi chấp thuận, hệ thống kiểm tra lại thời điểm bắt đầu của lịch gốc, phòng mới, khoảng chuyển tiếp và người tham gia.
7. Nếu phát sinh xung đột trong lúc chờ, không cho thao tác duyệt thành công. Người gửi có thể chọn phương án khác để đề nghị lại; lịch gốc vẫn có hiệu lực.
8. Khi duyệt thành công, thay thế phiên bản lịch và giải phóng lượt giữ chỗ cũ trong một giao dịch nhất quán. Sau khi lưu thành công mới gửi email cập nhật.
9. Nếu đề nghị bị từ chối hoặc được rút theo quy trình tương ứng, lịch gốc vẫn giữ nguyên.

### 5.3. Các trường hợp đổi phòng/giờ

| Tình huống | Cách xử lý | Lịch gốc |
|---|---|---|
| Phòng/giờ mới đã có lịch khác được duyệt | Báo không khả dụng ngay khi kiểm tra; người dùng chọn lại | Giữ nguyên |
| Phòng/giờ mới chỉ có yêu cầu khác đang chờ | Cảnh báo; đề nghị sửa vẫn có thể được gửi | Giữ nguyên |
| Lúc gửi còn trống, lúc duyệt đã có lịch khác được xác nhận | Không cho duyệt bản sửa | Giữ nguyên |
| Phòng/giờ mới hợp lệ và bản sửa được duyệt | Xác nhận lịch mới, giải phóng lịch cũ đồng thời | Được thay thế |
| Bản sửa bị từ chối | Không áp dụng phương án sửa | Giữ nguyên |

“Không cho duyệt do xung đột” là kết quả kiểm tra của thao tác chấp thuận; không đồng nghĩa hệ thống đã tự thực hiện một quyết định từ chối nghiệp vụ hoặc hủy lịch gốc. Tên trạng thái và cách rút/gửi lại áp dụng theo mục 9, DP-07 và UC-07/UC-08/UC-13 đã chốt.

## 6. Danh mục chức năng và phạm vi phiên bản đầu

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

## 7. Ma trận phân quyền

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

## 8. Chính sách bổ sung đã chốt

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

### 8.1. Những cách hiểu cần giữ nhất quán

- **Giờ phục vụ và khoảng chuyển tiếp:** Nếu một cuộc họp kết thúc lúc 12:00, khoảng chuyển tiếp có thể chạy đến 12:15 trong giờ nghỉ; lịch tiếp theo vẫn phải tuân thủ cả giờ phục vụ và khoảng đệm. Không mặc nhiên bắt cuộc họp cuối buổi kết thúc sớm 15 phút. Thời gian chuyển tiếp báo cáo theo phần thực tế của khoảng đặt trong kỳ, tách khỏi giờ họp; khi tính công suất phục vụ thì chỉ lấy phần thuộc giờ phục vụ.
- **Cấu hình phòng:** Ngừng nhận đặt mới không đồng nghĩa phòng bị hỏng và mọi lịch cũ không thể diễn ra. Xử lý phòng hỏng khẩn cấp và hủy thay người tạo là một phạm vi khác, chưa tự thêm vào phiên bản này. Thay đổi giờ phục vụ/đệm/sức chứa phải kiểm tra tính hợp lệ của lịch tương lai đã xác nhận và không âm thầm làm chúng mất hiệu lực. Giữ lịch sử cấu hình có hiệu lực để báo cáo không bị tính ngược bằng một cấu hình mới.
- **Công tác nhiều ngày:** Chưa tự suy đoán giờ làm việc mỗi ngày hay bỏ qua ban đêm. Nếu đăng ký một khoảng công tác liên tục, toàn bộ khoảng đó được coi là bận; người đăng ký đưa cả thời gian di chuyển vào khoảng. Chưa tích hợp bản đồ/tính hành trình.
- **Đổi phòng khi sửa:** Người phụ trách phòng mới là người có thẩm quyền duyệt bản sửa. Chỉ cấp phần thông tin lịch gốc cần để so sánh bản sửa; không cấp quyền xem mọi lịch ngoài phạm vi. Sau khi duyệt, người phụ trách phòng cũ nhận thông tin phần chỗ cũ đã giải phóng theo đúng quyền của mình. Người phụ trách phòng cũ chỉ có quyền lịch sử đối với lượt đặt/phiên bản cũ thuộc phạm vi của mình, không tự được xem mọi nội dung của phiên bản mới tại phòng khác.
- **Tài liệu:** Bổ sung biên bản sau họp là cập nhật tài liệu; thay giờ/phòng/nội dung lịch/thành phần vẫn phải qua quy trình sửa lịch đã duyệt. Cách tách trách nhiệm tại DP-06 đã được người thực hiện đề tài chấp thuận. Tệp không được công khai chỉ vì có một URL.
- **Email:** “Đã gửi” chỉ được hiểu là máy chủ SMTP đã chấp nhận gửi, không tự chứng minh thư vào hộp thư đến. Khi nghiệm thu phải kiểm tra nhận ở hộp thư thật. Không ghi mật khẩu, JWT hay bí mật SMTP vào email/log/tài liệu. Một email gửi lúc dữ liệu đã thay đổi phải kiểm tra lại quyền người nhận và tình trạng hiện tại; tránh phát thông tin lỗi thời hoặc sai phạm vi.
- **Thông tin cảnh báo:** Có thể báo một người bận ở khoảng giờ được phép xem, nhưng không chèn tiêu đề hay nội dung lịch riêng đó vào thông báo lỗi xung đột.
- **Lịch đã qua giờ:** Việc thời gian kết thúc đã qua không chứng minh đã diễn ra cuộc họp/công tác. Giao diện có thể ghi “đã qua thời gian”, không dùng làm bằng chứng tham dự hoặc công suất thực tế.
- **Người duyệt thay:** Nếu người được phân công chính là người tạo, hệ thống cần một người khác đủ quyền. Thiếu người duyệt thay thì yêu cầu phân công; không bỏ quy tắc cấm tự duyệt.

### 8.2. Công thức báo cáo (DP-09)

**Tỷ lệ thời gian đặt theo kế hoạch = (Tổng giờ họp đã xác nhận trong giờ phục vụ và trong kỳ / Tổng giờ phục vụ theo cấu hình có hiệu lực trong kỳ) × 100%.**

Tính theo từng phòng trước khi tổng hợp. Tổng hợp nhiều phòng phải cộng tử số và mẫu số rồi chia, không lấy trung bình đơn giản các tỷ lệ của những phòng có giờ phục vụ khác nhau. Loại lịch hủy, không đếm hai lần bản cũ và bản sửa. Thời gian chuyển tiếp là chỉ số riêng, không cộng vào tử số giờ họp. Phòng ngừng nhận đặt mới không mặc nhiên bị loại mọi giờ phục vụ/hồ sơ lịch sử khỏi mẫu số. Mẫu số bằng 0 hiển thị “Không áp dụng”.

Ví dụ một phòng phục vụ 8 giờ trong kỳ, có 3 giờ họp đã xác nhận, thì tỷ lệ theo kế hoạch là 37,5%; nếu có thêm 30 phút chuyển tiếp thì vẫn báo 3 giờ họp và 0,5 giờ chuyển tiếp riêng.

## 9. Mô hình trạng thái nghiệp vụ

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

## 10. Danh mục và đặc tả 20 Use Case

### 10.1. Danh mục

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

### 10.2. Quy ước đặc tả

Luồng chính mô tả mục tiêu thành công. Luồng thay thế là các nhánh hợp lệ; ngoại lệ nêu các tình huống không thể tiếp tục. Mọi thao tác ghi chỉ báo thành công sau khi dữ liệu được lưu. Email là tác vụ sau lưu và không quyết định việc phòng có được giữ hay không. Các chức năng có mã DP được cài theo phương án đã chốt.

Không vẽ “đăng nhập” như một include bắt buộc lặp lại bên trong mọi Use Case đã có điều kiện phiên hợp lệ. Kiểm tra xung đột là hành vi dùng chung bắt buộc của các luồng gửi/duyệt tương ứng; quan hệ include/extend sẽ được thể hiện theo đúng ngữ nghĩa khi dựng sơ đồ.

### UC-01. Đăng nhập

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

### UC-02. Xem lịch và tìm phòng phù hợp

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

### UC-03. Gửi yêu cầu họp và đặt phòng

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

### UC-04. Duyệt hoặc từ chối yêu cầu đặt phòng

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

### UC-05. Đăng ký lịch công tác

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

### UC-06. Duyệt hoặc từ chối lịch công tác

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

### UC-07. Gửi đề nghị sửa lịch đã duyệt

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

### UC-08. Duyệt hoặc từ chối đề nghị sửa lịch

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

### UC-09. Quản lý tài liệu họp

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

### UC-10. Xem báo cáo mức độ đặt phòng

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

### UC-11. Quản lý tài khoản nội bộ

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

### UC-12. Phân công quyền phê duyệt

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

### UC-13. Rút yêu cầu đang chờ duyệt

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

### UC-14. Hủy lịch họp đã duyệt

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

### UC-15. Đề nghị hủy lịch công tác đã duyệt

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

### UC-16. Duyệt hoặc từ chối hủy lịch công tác

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

### UC-17. Quản lý phòng ban

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

### UC-18. Quản lý phòng họp và giờ phục vụ

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

### UC-19. Đăng xuất

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

### UC-20. Đổi mật khẩu

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

## 11. Yêu cầu phi chức năng và cách thể hiện OOP

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

### 11.1. Tổ chức theo hướng đối tượng

- **Đóng gói:** Đối tượng/Service quản lý quy tắc thời gian, chuyển trạng thái, đề nghị sửa và hủy; không để UI tự ghi trạng thái CSDL.
- **Trừu tượng và đa hình:** Repository và dịch vụ gửi email có giao diện rõ ràng; thay bộ gửi SMTP/repository bằng bản kiểm thử mà không sửa logic đặt phòng.
- **Kế thừa:** Dùng lớp trừu tượng/giao diện ở điểm có hành vi chung thật sự. Vai trò Nhân viên/Người duyệt/Admin là quyền và phạm vi phân công, không ép thành một cây kế thừa làm mất khả năng kiêm nhiệm.
- **SOLID:** Tách tiếp nhận API, nghiệp vụ lịch, truy cập dữ liệu, email và báo cáo. Truyền phụ thuộc để kiểm thử nghiệp vụ độc lập.
- **Mẫu thiết kế ứng viên:** Repository và Unit of Work phục vụ dữ liệu/giao dịch; cơ chế phát sự kiện sau lưu để kích hoạt email; xử lý trạng thái chỉ tách thành State Pattern nếu độ phức tạp thực tế cần đến. Không đặt chỉ tiêu phải nhét đủ một số lượng pattern cố định.
- **Kiểm thử:** Unit test kiểm tra quy tắc thời gian/trạng thái bằng phụ thuộc giả; integration test kiểm tra ràng buộc và cạnh tranh thao tác trên MySQL thật. Không dùng chỉ một test bộ nhớ làm bằng chứng chống đặt trùng khi triển khai.

### 11.2. Tài liệu tải lên

Thiết kế dự kiến theo DP-06 dùng danh sách định dạng cho phép, giới hạn dung lượng và kiểm tra định dạng cơ bản; không chỉ tin tên mở rộng/Content-Type do client gửi. Lưu tên nội bộ, giữ tên hiển thị như metadata và phục vụ qua API kiểm tra quyền. Không đặt tệp nội bộ thành thư mục công khai của web. Cơ chế này giảm rủi ro nhưng không được tuyên bố “đã quét virus” nếu chưa có công cụ và kiểm chứng tương ứng.

## 12. Trường dữ liệu nghiệp vụ dự kiến

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

## 13. Kịch bản nghiệm thu

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

## 14. Đối chiếu với yêu cầu HTTT10 và tài liệu học phần

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

### 14.1. Nguồn đối chiếu

- File môn học **DS_Tieu luan_OOP_App(2).pdf**, trang PDF 1 và 3: yêu cầu chung, công nghệ và phạm vi HTTT10.
- File **INF1043_ĐCCT_PTUDHDT_2026(1).pdf**, trang PDF 3, 8–10: chuẩn đầu ra, ngoại lệ/log/kiểm thử và sản phẩm cuối kỳ.
- File **Chu de 1_Phan tich Tk voi UML(1).pdf**, trang PDF 1: cấu trúc đặc tả Use Case; các trang còn lại hướng dẫn sơ đồ.
- Các chủ đề SOLID, Design Pattern, OOP, kiến trúc đa tầng, xây dựng chương trình, UI/UX và lưu trữ dữ liệu đã được gửi; dùng làm hướng dẫn thiết kế, không coi các ví dụ tình nguyện/bán hàng là yêu cầu nghiệp vụ của HTTT10.
- [Microsoft Learn - Manage resource mailboxes](https://learn.microsoft.com/en-us/exchange/recipients-in-exchange-online/manage-resource-mailboxes): ví dụ mô hình duyệt tài nguyên, giờ phục vụ và giới hạn đặt; không dùng các giá trị mặc định của dịch vụ đó làm quy định của đề tài.
- [Google Calendar - Access permissions](https://support.google.com/calendar/answer/15716974): ví dụ tách quyền xem bận/rảnh và xem chi tiết.
- [OWASP - File Upload](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html): căn cứ kỹ thuật cho kiểm tra tệp, quyền truy cập và cách lưu tệp nội bộ; giá trị 20 MB trong DP-06 là giới hạn đã chốt riêng cho dự án.

## 15. Trạng thái hoàn thành và bước kế tiếp

Bước 1 đã hoàn thành với 23 chức năng, ma trận quyền, 20 Use Case, 9 nhóm chính sách bổ sung đã được chốt và 44 kịch bản nghiệm thu. Mọi thay đổi nghiệp vụ sau này cần cập nhật đồng thời quyết định, Use Case, sơ đồ và kịch bản có liên quan.

Bước 2 đã hoàn thành bộ 56 sơ đồ: 5 góc nhìn Use Case, 6 sơ đồ Lớp, 20 Tuần tự theo UC, 20 Hoạt động theo UC, 2 Tuần tự kỹ thuật, 2 Trạng thái và 1 Triển khai. Mỗi UC-01 đến UC-20 có một sơ đồ tuần tự và một sơ đồ hoạt động tương ứng. Có PDF tổng hợp, ảnh SVG/PNG, nguồn PlantUML và bảng đối chiếu UC với sơ đồ. Kiểm tra cú pháp và render sơ đồ đã hoàn tất; đây chưa phải bằng chứng ứng dụng đã chạy.

Bước 3 đã hoàn thành thiết kế MySQL 1.0: 24 bảng, 3 view, 5 góc nhìn ERD, từ điển dữ liệu, SQL baseline, dữ liệu danh mục giả lập và giao thức transaction/khóa. Bộ kiểm chứng cấu trúc và giao thức khóa tối thiểu đã đạt 34/34 kiểm tra trên MySQL 8.4.0; đây chưa phải kiểm thử ApprovalService FastAPI, UI, SMTP thật hay Docker trên Windows. Chi tiết và giới hạn nằm trong gói HTTT10_MySQL.

Bước 4 đã hoàn thành hợp đồng REST API/DTO 1.0: 50 HTTP operation trên 39 đường dẫn, 88 schema, đối chiếu đủ 20 Use Case; có OpenAPI YAML/JSON, Pydantic DTO, 15 ví dụ dữ liệu giả, cấu trúc backend/frontend và các route/màn hình dự kiến. Bộ kiểm chứng hợp đồng và DTO đạt 69/69 kiểm tra. Đây chưa phải HTTP server, UI, MySQL integration hoặc SMTP của website đã triển khai; các đường dẫn chương trình trong tài liệu kiến trúc vẫn là cấu trúc dự kiến.

Mốc A đã có mã nguồn 0.1.0: FastAPI/React, SQLAlchemy/Alembic baseline, Compose DB/migrate/API/web, bootstrap Admin qua CLI, JWT/phiên DB, login/me/logout/đổi mật khẩu và UI tương ứng. Kiểm tra FastAPI ASGI + MySQL 8.4.0 đạt 28/28; frontend build đạt và màn hình login đã kiểm tra trực quan. Compose được kiểm tra tĩnh; chưa chạy Docker Desktop Windows, Nginx end-to-end hoặc LAN hai máy trong môi trường tạo gói. Baseline giữ 24 bảng; Alembic thêm bảng kỹ thuật alembic_version.

Bước kế tiếp là mốc B: quản trị tài khoản/quyền, danh mục phòng ban/phòng họp/cấu hình, lịch và tìm phòng. Các API lịch, phê duyệt, tài liệu, email và báo cáo chưa được cài đặt trong mốc A. Không tự xuất hiện thêm chức năng nghiệp vụ, cấp duyệt hoặc quyền xem riêng tư khi chuyển sang code.
