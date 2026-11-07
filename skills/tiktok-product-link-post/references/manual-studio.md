---
name: tiktok-product-link-post
description: Đăng ảnh hoặc video lên TikTok Studio và gắn sản phẩm TikTok Shop bằng ID ở đầu tên file; hỗ trợ caption, thêm nhạc TikTok tùy chọn, đăng ngay hoặc hẹn giờ. Dùng khi người dùng yêu cầu đăng TikTok gắn sản phẩm.
---

# TikTok Product Link Post

Đăng ảnh hoặc video qua TikTok Studio, gắn sản phẩm theo ID trong tên file. Quy trình dưới đây dựa trên thao tác người dùng cung cấp; đọc giao diện thực tế ở mỗi bước vì nhãn và vị trí có thể thay đổi.

## Đầu vào và phạm vi

- Nhận file hoặc thư mục nguồn, caption nếu có, chế độ đăng ngay/hẹn giờ và tùy chọn âm thanh. Không tự lấy toàn bộ thư mục để đăng hàng loạt khi người dùng chưa yêu cầu.
- Nếu chưa có nguồn media, hỏi vị trí file. Nếu người dùng yêu cầu soạn caption, xem ảnh/video rồi viết tiếng Việt tự nhiên theo nội dung thực tế; không bịa giá, ưu đãi, chất liệu hay công dụng.
- Yêu cầu tạo/chỉnh skill không phải yêu cầu đăng bài thử. Khi người dùng đã yêu cầu đăng hoặc hẹn giờ cụ thể, thực hiện trong phạm vi đó mà không hỏi lại ở mỗi nút Next/Post.
- Nếu đã chọn hẹn giờ nhưng thiếu ngày/giờ, hỏi thông tin còn thiếu trước khi xác nhận lịch. Dùng múi giờ người dùng; mặc định Asia/Ho_Chi_Minh và đối chiếu với múi giờ hiển thị trên TikTok Studio.
- Nếu chỉ yêu cầu chuẩn bị bản nháp, dừng ở bản nháp. Không tự chọn nhạc khi người dùng chưa yêu cầu; giữ âm thanh hiện tại theo mặc định.

## Lấy ID sản phẩm

- Lấy basename của file, bỏ phần đường dẫn. ID là toàn bộ chuỗi chữ số ở đầu tên, ngay trước dấu gạch dưới `_` đầu tiên: mẫu `^([0-9]+)_`.
- Ví dụ `1736928691345393356_bas.....jpg` → ID `1736928691345393356`.
- Giữ ID dưới dạng chuỗi, không chuyển sang số thực/JavaScript Number vì có thể mất độ chính xác với ID dài.
- Không dùng mã phía sau `_`, tên thư mục hoặc URL Shopee thay cho ID này.
- Tên không khớp quy tắc: yêu cầu ID đúng; không đoán hoặc tự chọn sản phẩm gần giống.
- Với nhiều ảnh cùng một bài, xác minh chúng có cùng ID. Nếu có nhiều ID, tách thành các bài riêng trong phạm vi người dùng yêu cầu; nếu người dùng muốn một bài duy nhất, làm rõ sản phẩm cần gắn trước khi tiếp tục. Giữ thứ tự người dùng chỉ định; nếu có chỉ số ảnh thì sắp theo chỉ số số học.
- Không tự trộn video và ảnh vào một bài khi trình tải lên không hỗ trợ; xử lý theo loại media và giao diện hiện có.

## Trình duyệt và tải lên

1. Dùng công cụ trình duyệt/computer use hiện có, đọc hướng dẫn công cụ trước khi điều khiển. Ưu tiên tab TikTok đã đăng nhập và xác minh tài khoản đích. Nếu có nhiều tài khoản mà chưa xác định được tài khoản cần đăng, hỏi người dùng.
2. Truy cập [TikTok Studio photo upload](https://www.tiktok.com/tiktokstudio/upload/post/photo).
3. Upload đúng ảnh hoặc video đã chọn. Nếu trang ảnh không nhận video, chuyển sang mục upload video của TikTok Studio qua giao diện hiện tại, không đoán URL khác.
4. Chờ upload/xử lý hoàn tất, kiểm tra preview, số lượng và thứ tự media. Điền caption người dùng cung cấp hoặc bản đã được yêu cầu soạn.
5. Nếu người dùng yêu cầu thêm nhạc, thực hiện phần Âm thanh tùy chọn trước khi đăng.

Dùng nhãn và trạng thái quan sát được để tìm nút. Không dựa vào tọa độ cũ hoặc bấm hàng loạt các nút Next mà chưa xác định bước hiện tại. Nếu cần đăng nhập, gặp CAPTCHA hoặc thiếu quyền gắn sản phẩm, dừng phần bị chặn và báo đúng nguyên nhân.

## Gắn sản phẩm

Thực hiện theo trình tự người dùng cung cấp, đối chiếu từng màn hình thực tế:

1. Chọn **Add link**; nếu xuất hiện loại liên kết, chọn loại **Product / sản phẩm** tương ứng, rồi **Next**.
2. Nhập nguyên chuỗi ID đã lấy từ tên file vào ô tìm kiếm sản phẩm, thực hiện tìm kiếm và chờ kết quả.
3. Nếu có kết quả đúng ID, đối chiếu thêm hình/tên sản phẩm với media để phát hiện sai liên kết. Chọn sản phẩm bằng nút tròn (radio) bên cạnh kết quả. Kiểm tra trạng thái đã chọn trước khi tiếp tục.
4. Chọn **Next**. Ở bước tên hiển thị sản phẩm, **giữ nguyên tên mặc định**, không thay bằng caption hay tên file.
5. Chọn **Next** để hoàn tất gắn sản phẩm. Kiểm tra sản phẩm/tên liên kết đã xuất hiện trên bài.

Không có kết quả, ID không khớp, media mâu thuẫn rõ với sản phẩm, hoặc không có tùy chọn Add link: dừng trước Post/Schedule, giữ bản nháp nếu có thể và báo ID cùng lý do. Không tự chuyển sang đăng không gắn sản phẩm, chọn sản phẩm tương tự hoặc dán URL vào caption để thay thế.

## Âm thanh tùy chọn

Chỉ làm khi người dùng yêu cầu thêm sound:

1. Chọn **SOUND** để mở phần âm thanh.
2. Với video có âm thanh gốc, tìm biểu tượng loa/điều khiển **Original sound** của video và tắt âm thanh gốc. Xác minh trạng thái mute hoặc âm lượng 0; nếu là ảnh hoặc không có âm gốc thì bỏ qua bước này.
3. Chọn nút **+ màu đỏ** để thêm sound từ TikTok. Ưu tiên bài/đoạn nhạc người dùng chỉ định. Nếu người dùng giao tự chọn, chọn bản nhạc phù hợp nội dung từ thư viện khả dụng của tài khoản.
4. Chọn **Save**. Kiểm tra tên sound đã áp dụng; với video, kiểm tra âm gốc vẫn tắt.

Nếu bản nhạc yêu cầu không khả dụng hoặc không được phép dùng với bài gắn sản phẩm, báo trở ngại để người dùng chọn hướng xử lý. Không tự bỏ yêu cầu âm thanh và đăng tiếp.

## Bắt buộc bật AI-generated content

Áp dụng cho mọi bài ảnh/video được chuẩn bị bằng skill này, cả đăng ngay và hẹn giờ.

1. Trong phần Settings, chọn **Show more** (Hiển thị thêm). Chờ phần cài đặt mở rộng tải và hiện đầy đủ.
2. Tìm **AI-generated content** (Nội dung do AI tạo) và bật công tắc. Nếu đã bật, giữ nguyên; không bấm lại làm tắt.
3. Nếu TikTok hiện thông báo giải thích về nhãn AI, đọc và xác nhận để hoàn tất bật nhãn theo yêu cầu người dùng.
4. Đọc lại trạng thái công tắc và xác minh **On / bật** trước khi bấm **Post** hoặc xác nhận **Schedule**. Nếu đóng/mở lại bản nháp hoặc thay media, kiểm tra lại nhãn trước thao tác cuối.

Nếu không tìm thấy mục này, công tắc bị vô hiệu hóa hoặc không xác minh được đã bật, giữ bản nháp khi có thể và báo trở ngại; không đăng/hẹn giờ khi chưa hoàn thành bước bắt buộc. Việc cập nhật skill không tự cho phép sửa các bài đã đăng trước đó.

## Đăng hoặc hẹn giờ và xác minh

- Trước thao tác cuối, đối chiếu tài khoản, media, caption, sản phẩm đúng ID và tên mặc định, sound nếu được yêu cầu; bắt buộc xác minh **AI-generated content đã bật** theo phần trên.
- Đăng ngay: chọn **Post** theo yêu cầu người dùng.
- Hẹn giờ: chọn **Schedule**, đặt đúng ngày/giờ và múi giờ; kiểm tra lịch hợp lệ theo giao diện TikTok hiện tại rồi xác nhận hẹn giờ. Không tự đổi sang đăng ngay nếu giờ không hợp lệ.
- Chỉ báo thành công khi có xác nhận từ TikTok và kiểm tra được bài mới hoặc mục Scheduled tương ứng. Kiểm tra caption/media và liên kết sản phẩm khi giao diện cho phép; nói rõ phần nào chưa xác minh được.
- Phân biệt **đã đăng**, **đã hẹn giờ**, **đang xử lý/kiểm duyệt**, **bản nháp**, và **chưa xác minh**. Một click Post không đủ để khẳng định đã đăng.
- Nếu timeout/lỗi sau thao tác cuối, kiểm tra danh sách nội dung/bài hẹn giờ trước khi thử lại. Nếu vẫn không xác định được kết quả, báo chưa xác minh và dừng; không bấm Post/Schedule lần nữa để tránh trùng bài.
- Trả về ID sản phẩm, trạng thái, link bài nếu có, hoặc lịch đăng kèm múi giờ. Không di chuyển/xóa file nguồn hay sửa trạng thái của skill đăng mạng xã hội khác.


## Tự động dọn file tạm

- Mỗi lần chạy, tạo một thư mục tạm riêng bằng `tempfile.mkdtemp(prefix="tiktok-post-")` nếu cần bản sao ảnh để upload, contact sheet, thumbnail hoặc frame trích từ video. Ghi lại chính xác các đường dẫn do lần chạy này tạo; ưu tiên đặt tất cả trong thư mục đó.
- Trước khi kết thúc lần chạy, tự xóa các file/thư mục tạm đã ghi nhận, không hỏi lại. Áp dụng cả khi đăng/hẹn giờ thành công, lưu nháp, không tìm thấy sản phẩm, lỗi công cụ hoặc bị chặn. Khi dùng script, đặt việc dọn trong `finally`; khi thao tác bằng công cụ, thực hiện bước dọn trước câu trả lời cuối.
- Chỉ dọn khi thao tác đọc/upload đang dùng các file đó đã kết thúc. Nếu đang mở hộp thoại chọn file, hủy hộp thoại khi có thể trước khi dọn; lần thử lại phải tạo lại bản sao tạm từ nguồn. Dọn file cục bộ không đồng nghĩa xóa bài hoặc bản nháp trên TikTok.
- Chỉ xóa đúng file và thư mục tạm do lần chạy này tạo. Không quét/xóa theo wildcard toàn bộ `/tmp` hoặc `/private/tmp`; không xóa file gốc, thư mục nguồn, skill đã cài, nhật ký/trạng thái chống đăng trùng hoặc dữ liệu do tác vụ khác tạo. Không đi theo symlink để xóa nội dung ở đích.
- Kiểm tra các đường dẫn tạm đã không còn tồn tại. Nếu xóa thất bại, báo đúng đường dẫn và lỗi; không nói đã dọn xong. Nếu tác vụ bị ngắt trước bước dọn, lần tiếp tục dọn các đường dẫn đã ghi nhận từ lần trước khi kết thúc.
