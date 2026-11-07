---
name: tiktok-product-link-post
description: Đăng/hẹn từng video TikTok bằng tiktok-tool, gắn TikTok Shop theo ID đầu tên file, bật nhãn AI và xác minh kết quả; ảnh hoặc thêm nhạc dùng Studio thủ công.
---

# TikTok Product Link Post

Với video giữ sound gốc, dùng `scripts/tiktok_tool.sh` trong thư mục skill này.
Đây là launcher cho `tiktok-tool` trong fork
[vinhlng98/tiktok-uploader](https://github.com/vinhlng98/tiktok-uploader).
Không dùng lệnh upstream `tiktok-uploader`: luồng đó chưa có các kiểm chứng của fork.
Đọc [hướng dẫn tool](references/tool.md) khi cần cài đặt, đăng nhập hoặc xử lý lỗi.

## Phạm vi

- Tạo/chỉnh tool hoặc skill không phải yêu cầu đăng thử. Chỉ gọi `--submit` khi
  người dùng đã yêu cầu đăng/hẹn nội dung cụ thể; không hỏi lại ở từng nút.
- Xác định đúng tài khoản, file, số lượng, caption, lịch. Giao thư mục không có
  nghĩa đăng toàn bộ thư mục ngoài số lượng được yêu cầu. Mỗi video một bài riêng.
- Xem media trước khi viết caption và đối chiếu sản phẩm; không bịa giá, chất
  liệu hay ưu đãi. Tool kiểm tra ID, không tự đánh giá được trang phục có khớp.
- ID là toàn bộ chuỗi số trước `_` đầu tiên của basename; không dùng số thực.
- Đọc status/nhật ký trước khi lập batch. Không đăng lại chỉ vì file còn ở nguồn.
- Tool dùng Asia/Ho_Chi_Minh, mốc cách 5 phút, 20 phút–10 ngày tới. Nếu cần làm
  tròn giờ tương đối, nêu lịch cụ thể; không tự đổi lịch đã chốt.

## Quy trình video

1. `scripts/tiktok_tool.sh status` đọc nhật ký chống trùng.
2. Khi cần: `login --account USERNAME`, người dùng tự đăng nhập/CAPTCHA trong
   cửa sổ riêng. `doctor --account USERNAME` kiểm tra tài khoản. Không trích
   cookie từ trình duyệt thường và không đưa secret vào chat.
3. Tạo kế hoạch với từng file cụ thể, caption tương ứng:

```sh
scripts/tiktok_tool.sh plan '/absolute/path/1731234556640856114_video.mp4' \
  --account USERNAME --caption 'Caption đã chuẩn bị' \
  --start '2026-11-09T10:30:00+07:00' --interval 30 \
  --product-policy required --out '/absolute/private/path/batch.json'
```

Ngày giờ trên chỉ là ví dụ. Nhiều caption: lặp `--caption` hoặc dùng
`--captions-json` với JSON array đúng số file. Nhãn AI luôn bật; giữ sound gốc.

- `required` mặc định: thiếu đúng sản phẩm thì dừng.
- `if-available` chỉ khi người dùng nói “nếu có”: bỏ gắn sau khi tìm kiếm ổn định
  không có kết quả; timeout và lỗi gắn sản phẩm vẫn dừng.
- `none` chỉ khi được yêu cầu không gắn sản phẩm.

4. Đọc kế hoạch hoặc `run PLAN` (không submit, offline) để đối chiếu file, tài
   khoản, caption, ID và lịch. Trong phạm vi đã được phép đăng, `run PLAN --submit`.
   Theo dõi phiên terminal tới kết quả; không bỏ mặc job đang chạy.
5. Chỉ báo thành công khi status là `scheduled`/`published`, có URL và lịch xác
   minh trong danh sách TikTok. Một click hoặc toast không đủ.

## Lỗi và tiếp tục

- `failed_before_submit`: chưa bấm đăng; sửa lỗi, kiểm tra lịch rồi mới thử lại.
- `submitting`/`unverified`: dùng `reconcile PLAN`, không upload lại. Không xóa
  ledger, đổi state directory hoặc chuyển sang CUA để né chống đăng trùng.
- `external_draft`: nháp từ quy trình trước; mở/kiểm tra riêng, không tạo bài mới
  từ cùng file. Giữ những bài người dùng đã yêu cầu giữ nguyên.
- Checks pending: tiếp tục theo dõi trong tác vụ, giữ lịch; không tắt kiểm tra
  hoặc chấp nhận “Post now” thay lịch. Nếu giờ hết hợp lệ, hỏi giờ thay thế.
- Selector đổi: giữ bằng chứng cục bộ, sửa adapter và kiểm thử; không ép bấm bằng
  tọa độ đoán. Không tự bỏ yêu cầu sản phẩm, sound hoặc AI để đi qua lỗi.
- Reconcile không xác định được kết quả thì cần đối chiếu TikTok/làm rõ với người
  dùng trước mọi lần gửi lại. Không báo nháp hay unverified thành đã hẹn.

## Nguồn và file tạm

Chỉ thêm `--done-dir '/absolute/path/VIDEO/DONE TIKTOK'` khi người dùng yêu cầu.
Tool chỉ chuyển sau khi xác minh bài/lịch và SHA-256; không ghi đè. Chuyển lỗi
không làm mất trạng thái đã đăng, nên không đăng lại để sửa lỗi chuyển file.
Không sửa nhật ký của nền tảng khác.

Nếu trích frame/contact sheet, tạo tempdir riêng, ghi đúng path, dọn trong
`finally` ở mọi kết quả và kiểm tra đã hết. Không xóa nguồn, profile, ledger,
kế hoạch, evidence còn cần điều tra hoặc file tạm của tác vụ khác.

## Ảnh hoặc thêm nhạc TikTok

Tool hiện chỉ hỗ trợ video giữ sound gốc. Với ảnh hoặc thêm nhạc, đọc
[quy trình Studio thủ công](references/manual-studio.md) và dùng CUA theo hướng
dẫn công cụ. Vẫn xác minh AI, đúng sản phẩm và lịch. Không chuyển một bài đang
unverified sang quy trình thủ công để đăng lại.
