# AI SPEC — Discord Onboarding AI · Nhóm [XX] · Zone [X]
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
    - Cần bổ sung log khảo sát thực tế trong Discord để đạt chuẩn A/B đầy đủ
    - Bộ quan sát ban đầu hiện có từ chat pattern trong workspace và golden set mô phỏng
  - ≥5 quote/ví dụ nguyên văn + nguồn:
    - "Mọi người ơi tối nay có họp không?"
    - "Có nha, 20h30 nhé, mình gửi link sau"
    - "Cho hỏi flow đăng nhập xong bên UI xử lý sao nhỉ, ai làm phần đó vậy?"
    - "Hình như Lan trả lời trong kênh hỏi-đáp rồi đó, để mình tìm lại"
    - "API tạo user trả lỗi 500 sửa ở đâu, ai đã trả lời chưa?"

## §2. Impact & quyết định chọn
- Bảng impact ≥3 ứng viên (bao nhiêu người · tần suất · tốn gì mỗi lần · khả thi):
  - Trợ lý tìm câu hỏi cũ trong Discord
    - Bao nhiêu người gặp: nhiều học viên trong nhóm demo / onboarding
    - Tần suất: cao ở giai đoạn đầu vào lớp
    - Mỗi lần tốn gì: vài phút dò chat + rủi ro bỏ sót
    - Khả thi: làm được trong hackathon
  - Bot tóm tắt thread / bài đăng
    - Bao nhiêu người gặp: học viên cần đọc lại topic cũ
    - Tần suất: trung bình-cao
    - Mỗi lần tốn gì: đọc nhiều tin nhắn
    - Khả thi: làm được
  - Bot chỉ dẫn hỏi đúng kênh
    - Bao nhiêu người gặp: học viên mới
    - Tần suất: cao
    - Mỗi lần tốn gì: hỏi sai kênh, chờ trả lời
    - Khả thi: làm được
- Ứng viên ĐÃ LOẠI + vì sao:
  - Sinh bản tin cuối ngày cho TA: phạm vi rộng hơn, khó validate nhanh trong 1,5 ngày
- Ứng viên CHỌN + vì sao (bằng số):
  - Chọn trợ lý trả lời câu hỏi onboarding trong Discord vì pain rõ, demo được nhanh, có thể đo bằng golden set và có rủi ro rõ ràng khi AI đoán sai

## §3. Giải pháp tương tự đã nghiên cứu
- [Sản phẩm 1]: ChatGPT / LLM chat
  - flow: hỏi trực tiếp, trả lời ngay
  - đáng học: nhanh
  - đáng né: dễ trả lời bừa nếu không có ngữ cảnh
  - mình khác gì: chỉ trả lời dựa trên ngữ cảnh Discord + history + nguồn liên quan
- [Sản phẩm 2]: Discord search / thread lookup thủ công
  - flow: người dùng tự tìm
  - đáng học: dùng lịch sử và thread thật
  - đáng né: tốn công, dễ bỏ sót
  - mình khác gì: tự gom ngữ cảnh, ưu tiên câu cũ, có fallback khi thiếu dữ liệu

## §4. Thiết kế
- Lát cắt MỘT CÂU (1 user · 1 việc · 1 quyết định AI · 1 kết quả):
  - Một học viên chọn một câu hỏi hoặc thread trong Discord, AI quyết định câu này có thể trả lời từ lịch sử/ngữ cảnh hay phải sinh trả lời mới, rồi trả về phản hồi ngắn kèm nguồn hoặc cảnh báo nếu thiếu/mâu thuẫn
- Non-goals (≥3 thứ KHÔNG build):
  - Không xây full Discord clone
  - Không làm chatbot đa tác vụ ngoài onboarding/hỏi đáp
  - Không tối ưu semantic search phức tạp ngay trong vòng này
- Mức prototype nhắm tới: [x] Sketch [x] Mock [ ] Working — phần nào mock, phần nào thật:
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
  - Spec: [Nguyễn Thành Huy]
  - Evidence: [Phan Văn Phương]
  - Prompt: [Đinh Đức Anh]
  - Code: [Lê Huy Hoàng]
  - Demo: [Trần Minh Hạnh]
- Willing users (≥3 tên) + kế hoạch vòng validation CP5 (3 câu hỏi, ai log):
  - 
  - 3 câu hỏi:
    1. Điều gì khó hiểu hoặc khó chịu nhất?
    2. Kết quả này bạn có tin không — vì sao?
    3. Bạn có dùng thật không — vì sao / vì sao chưa?
  - Ai log: [điền tên]
- Multi-prototype (nếu làm): trục khác biệt của ≥2 phương án + lý do chọn:
  - Nếu làm, trục khác biệt nên là:
    - hỏi trước vs làm luôn
    - tóm tắt ngắn vs trả lời có nguồn
    - thread-detail vs inbox summary
  - Lý do chọn phương án hiện tại:
    - giảm cost-of-error, dễ demo, dễ validate

## §9. Changelog
| Thời điểm | Đổi gì | Vì sao (trỏ về feedback/case nào) |
|---|---|---|
| ... | ... | ... |
