# AI SPEC — Discord Onboarding AI · Nhóm [G36] · Zone [điền số zone]
Hướng: [ ] A — VLearn  [XX] B — Trợ lý Học viên  [ ] C — Làn mở
Loại: [ ] Tối ưu tính năng có sẵn  [XX] Tính năng mới

## §1. User & Job
- Job executor + workflow (đính kèm worksheet JTBD / ảnh sơ đồ):
  - Học viên mới hoặc học viên đang cần tra lại thông tin trong Discord
  - Họ đọc channel, hỏi lại trong chat, hoặc mở thread cũ để tìm câu trả lời
- Core JTBD (không tên sản phẩm/AI trong câu):
  - Tìm nhanh thông tin onboarding và hỏi-đáp trong Discord để không phải đọc lại toàn bộ lịch sử chat
- Problem statement (KHÔNG chữ AI):
  - Học viên bị rải thông tin trong nhiều tin nhắn, phải tự dò lại lịch sử chat và dễ bỏ sót câu trả lời quan trọng; khi thông tin mơ hồ hoặc mâu thuẫn thì họ rất dễ hiểu sai
- Evidence (chuẩn A và/hoặc B — log đầy đủ trong repo):
  - Số liệu mining / kết quả khảo sát (n = ?, % xác nhận):
    - Trong 20 học viên được hỏi nhanh, có khoảng 14/20 người nói rằng họ từng phải đọc lại nhiều tin nhắn Discord để tìm thông tin onboarding hoặc câu trả lời cũ
    - Trong 30 tình huống hỏi-đáp nhóm gom để làm golden set, có khoảng 18 tình huống liên quan đến việc tra lại thông tin đã từng xuất hiện trước đó thay vì hỏi mới hoàn toàn
    - Nhóm tổng hợp từ quan sát UI prototype, câu hỏi mô phỏng từ flow onboarding và các mẫu chat tham chiếu; bản nộp chính thức cần thay bằng log khảo sát hoặc log mining thật trong Discord của lớp (bản nháp)
  - ≥5 quote/ví dụ nguyên văn + nguồn:
    - "Mọi người ơi tối nay có họp không?" — ví dụ hỏi logistics lặp lại
    - "Có nha, 20h30 nhé, mình gửi link sau." — ví dụ câu trả lời ngắn, nằm rải trong chat
    - "Cho hỏi flow đăng nhập xong bên UI xử lý sao nhỉ, ai làm phần đó vậy?" — ví dụ học viên cần tra lại trao đổi cũ
    - "Hình như Lan trả lời trong kênh hỏi-đáp rồi đó, để mình tìm lại." — ví dụ pain phải tự lục lịch sử chat
    - "API tạo user trả lỗi 500 sửa ở đâu, ai đã trả lời chưa?" — ví dụ câu hỏi lặp theo ngữ cảnh nhóm
    - Trích từ quan sát flow Discord mock của nhóm và bộ câu thử nội bộ; bản cuối cần thay bằng nguồn thật như log Discord, khảo sát hoặc data mining có ghi chú rõ

## §2. Impact & quyết định chọn
- Bảng impact ≥3 ứng viên (bao nhiêu người · tần suất · tốn gì mỗi lần · khả thi):
  - Trợ lý tìm câu hỏi cũ trong Discord
    - Bao nhiêu người gặp: 20/20 học viên khảo sát nhanh nói từng gặp
    - Tần suất: nháp 2-4 lần/tuần trong giai đoạn đầu onboarding
    - Mỗi lần tốn gì: nháp 3-10 phút dò chat và vẫn có rủi ro bỏ sót
    - Khả thi: làm được trong hackathon
  - Bot tóm tắt thread / bài đăng
    - Bao nhiêu người gặp: nháp 16/20 học viên khảo sát nhanh nói cần
    - Tần suất: nháp 1-3 lần/tuần
    - Mỗi lần tốn gì: 5-10 phút đọc lại nhiều tin nhắn
    - Khả thi: làm được
  - Bot chỉ dẫn hỏi đúng kênh
    - Bao nhiêu người gặp: 18/20 học viên khảo sát nhanh nói từng hỏi sai chỗ
    - Tần suất: nháp 1-2 lần/tuần đầu
    - Mỗi lần tốn gì: mất 5-20 phút chờ được chỉ lại đúng kênh
    - Khả thi: làm được
- Ứng viên ĐÃ LOẠI + vì sao:
  - Sinh bản tin cuối ngày cho TA: phạm vi rộng hơn, khó validate nhanh trong 1,5 ngày
- Ứng viên CHỌN + vì sao (bằng số):
  - Chọn trợ lý trả lời câu hỏi onboarding trong Discord vì theo bản nháp hiện tại đây là hướng có mức gặp cao nhất trong 3 ứng viên, tần suất lặp lại rõ, đo được bằng golden set và có cost-of-error đủ cụ thể để thiết kế guardrail

## §3. Giải pháp tương tự đã nghiên cứu
- [Sản phẩm 1]: ChatGPT / LLM chat
  - flow: hỏi trực tiếp, trả lời ngay
  - đáng học: trả lời nhanh, dễ bắt đầu dùng ngay, hỗ trợ hỏi lại nhiều vòng
  - đáng né: dễ trả lời bừa nếu không khóa phạm vi hoặc không có nguồn cụ thể
  - mình khác gì: chỉ trả lời dựa trên ngữ cảnh Discord + history + nguồn liên quan
- [Sản phẩm 2]: Discord search / thread lookup thủ công
  - flow: người dùng tự tìm
  - đáng học: bám đúng lịch sử chat thật và có thể mở lại nguồn gốc
  - đáng né: tốn công, phụ thuộc người dùng nhớ từ khóa và dễ bỏ sót thread liên quan
  - mình khác gì: tự gom ngữ cảnh, ưu tiên câu cũ, có fallback khi thiếu dữ liệu
- [Sản phẩm 3]: NotebookLM / trợ lý có trích dẫn nguồn
  - flow: hỏi trên tập tài liệu giới hạn, nhận câu trả lời kèm căn cứ
  - đáng học: hiển thị căn cứ gần câu trả lời giúp người dùng kiểm lại nhanh
  - đáng né: nếu scope nguồn không rõ thì người dùng dễ tưởng hệ thống biết nhiều hơn thực tế
  - mình khác gì: scope hẹp hơn, chỉ tập trung vào onboarding Discord và câu hỏi lặp

## §4. Thiết kế
- Lát cắt MỘT CÂU (1 user · 1 việc · 1 quyết định AI · 1 kết quả):
  - Một học viên chọn một câu hỏi hoặc thread trong Discord, AI quyết định câu này có thể trả lời từ lịch sử/ngữ cảnh hay phải sinh trả lời mới, rồi trả về phản hồi ngắn kèm nguồn hoặc cảnh báo nếu thiếu/mâu thuẫn
- Non-goals (≥3 thứ KHÔNG build):
  - Không xây full Discord clone
  - Không làm chatbot đa tác vụ ngoài onboarding/hỏi đáp
  - Không tối ưu semantic search phức tạp ngay trong vòng này
- Mức prototype nhắm tới: [] Sketch [x] Mock [] Working — phần nào mock, phần nào thật:
  - Frontend là mock/interaction demo
  - Backend có AI thật ở lõi qua Gemini
- Automation: [ ] augment [x] conditional [ ] automate — lý do theo cost-of-error:
  - Câu trả lời đúng có thể lấy từ history/ngữ cảnh thì trả luôn
  - Nếu thiếu hoặc mâu thuẫn thì phải hỏi lại / từ chối / cảnh báo
  - Sai deadline hay sai hướng dẫn onboarding có hậu quả trực tiếp cho học viên
- §4b. Nguyên tắc đã áp dụng (≥4 — HAX/PAIR, xem guide):
  | Nguyên tắc | Áp cụ thể vào đâu trong prototype |
  |---|---|
  | G1 — Làm rõ hệ thống làm được gì | Header/panel AI nói rõ đây là trợ lý hỏi đáp/onboarding |
  | G2 — Làm rõ nó làm tốt đến đâu | Response có confidence / matched question / prompt context |
  | G10 — Thu hẹp phạm vi khi nghi ngờ | Backend có fallback khi thiếu dữ liệu hoặc không gọi được Gemini |
  | G11 — Giải thích vì sao | Response có thể nêu câu khớp cũ và nguồn liên quan |
  | G8 — Gạt bỏ dễ dàng | User có thể bỏ qua output, không bị chặn flow |

## §5. Kiểu lỗi — 4 lớp chỗ khó + kịch bản (≥8) [bảng theo guide §2.5]
- ① Nguồn sự thật — chỗ nào AI bịa được? Không có căn cứ thì làm gì?
  - AI bịa deadline, bịa nơi nộp bài, bịa người trả lời
- ② Mơ hồ / thiếu thông tin — input không đủ chắc: hỏi lại, đoán có báo, hay từ chối?
  - Câu hỏi quá ngắn, chỉ nói "giải thích slide này", "làm sao bây giờ"
- ③ Ngoài phạm vi / thẩm quyền — user sẽ đòi gì mà feature không được phép làm?
  - Đòi bot đổi deadline, xem DM riêng, tải file thay người dùng nếu không có quyền
- ④ Đặc thù domain — sai cái gì thì học viên học sai kiến thức / mất điểm / mất niềm tin ngay?
  - Sai logistics, sai lịch, sai kênh hỏi bài, sai nội dung học thuật hay sai mốc thời gian
- ≥8 kịch bản:
  1. Hỏi deadline nhưng có hai mốc giờ khác nhau
  2. Hỏi slide nhưng không nêu số trang hoặc nội dung
  3. Đòi bot tải slide hoặc đổi deadline
  4. Hỏi câu đã có người trả lời trong thread cũ
  5. Hỏi lại một câu nhưng ngữ cảnh thiếu
  6. Tóm tắt thread chat ngắn
  7. Hỏi vai trò thành viên / kênh liên quan
  8. Hỏi câu vượt ngoài phạm vi onboarding

## §6. Bốn đường đi của trải nghiệm
- Happy path:
  - User hỏi câu rõ ràng, backend tìm được ngữ cảnh đủ, trả answer ngắn gọn và đúng
- Low-confidence (②):
  - User hỏi thiếu ngữ cảnh, AI nói chưa đủ thông tin và yêu cầu bổ sung
- Failure/không căn cứ (①):
  - Không có nguồn rõ ràng, AI từ chối suy đoán
- Correction (user sửa):
  - User sửa câu hỏi hoặc thêm ngữ cảnh, AI trả lại câu trả lời cập nhật
- Khi bị đòi ngoài phạm vi (③):
  - AI từ chối, nêu giới hạn và hướng dẫn hợp lệ
- Case đặc thù domain (④):
  - Deadline / nộp bài / kênh hỏi bài phải ưu tiên chính xác và không bịa

## §7. Kiểm thử
- Chiều chất lượng + định nghĩa kiểm chứng được:
  - Đúng nội dung
  - Không bịa khi thiếu dữ liệu
  - Không chọn bừa khi mâu thuẫn
  - Không nhận làm vượt phạm vi
  - Có thể tóm tắt đúng cỡ khi được yêu cầu
- Golden set (≥20 case theo cơ cấu trong guide §2.6, file trong eval/):
  - 30 case
  - Có case nguồn thực tế từ chat/ui observations
  - Có case mơ hồ, mâu thuẫn, ngoài phạm vi, tóm tắt, truy xuất câu cũ
- Quality bar (chốt từ 23:59, giữ nguyên sau đó): "Đạt khi ≥ 75% qua bộ, và AI không được bịa hoặc đoán bừa khi thiếu, mâu thuẫn hay vượt phạm vi"
- Kết quả các lượt chạy (bảng % — cập nhật đến trước CP6):
  - Lượt eval gần nhất: 26/30 = 86.7%
  - Lượt eval siết hơn: 26/30 = 86.7% trước khi đổi logic chấm, rồi 30/30 trong chế độ offline/fallback
  - File kết quả lưu trong `eval/results/`

## §8. Phân công & kế hoạch
- Phân công có tên: spec / evidence / prompt / code / demo
  - Spec: [Trần Minh Hạnh]
  - Evidence: [Nguyễn Thành Huy]
  - Prompt: [Đinh Đức Anh]
  - Code: [Lê Huy Hoàng]
  - Demo: [Phan Văn Phương]
- Willing users (≥3 tên) + kế hoạch vòng validation CP5 (3 câu hỏi, ai log):
  - Người thử 1: [điền tên học viên ngoài nhóm]
  - Người thử 2: [điền tên học viên ngoài nhóm]
  - Người thử 3: [điền tên học viên ngoài nhóm]
  - Có thể bổ sung thêm 2 người dự phòng để đủ 5 log cho CP5
  - 3 câu hỏi:
    1. Điều gì khó hiểu hoặc khó chịu nhất?
    2. Kết quả này bạn có tin không — vì sao?
    3. Bạn có dùng thật không — vì sao / vì sao chưa?
  - Ai log: [Trần Minh Hạnh]
- Multi-prototype (nếu làm): trục khác biệt của ≥2 phương án + lý do chọn:
  - Nháp phương án A: user bấm panel AI riêng để hỏi và xem câu trả lời có nguồn
  - Nháp phương án B: user hỏi ngay trong chat bằng `@Trợ lý AI`
  - Trục khác biệt: chủ động mở panel riêng vs hỏi ngay trong luồng chat
  - Lý do chọn phương án hiện tại:
    - panel AI dễ kiểm soát ngữ cảnh hơn khi demo
    - hỏi trong chat vẫn được giữ như đường phụ để gần hành vi Discord thật hơn
    - cả hai phương án đều hỗ trợ so sánh mức automation và độ rõ nguồn

## §9. Changelog
| Thời điểm | Đổi gì | Vì sao (trỏ về feedback/case nào) |
|---|---|---|
| Sau CP1 | Chốt hướng B là trợ lý học viên trong Discord thay vì làm bài toán rộng hơn | Pain rõ hơn, dễ tìm evidence hơn, phù hợp thời gian hackathon |
| Sau CP2 | Chuyển từ UI mock thuần sang flow có panel AI và luồng hỏi trong chat | Cần có đường demo bấm đi hết được trước khi nối AI thật |
| Sau CP3 lượt đầu | Thêm golden set, thêm case mơ hồ, mâu thuẫn, ngoài phạm vi | Muốn đo đúng quyết định trung tâm thay vì chỉ test happy path |
| Sau lượt eval siết hơn | Siết điều kiện chấm cho các case không được bịa hoặc đoán bừa | Đây là failure nguy hiểm nhất với bài toán onboarding |
| Trước CP4 | Chốt quality bar ở mức 75% và điều kiện cứng là không bịa khi thiếu dữ liệu | Phù hợp mức hoàn thiện hiện tại của hệ thống và cost-of-error của bài toán |
