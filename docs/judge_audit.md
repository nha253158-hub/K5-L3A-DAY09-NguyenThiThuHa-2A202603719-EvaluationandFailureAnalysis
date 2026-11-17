# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Có | dùng |
| helpful | 100 | 0.375 | 1.000 | 0.300 | Không (κ < 0.6 và R < 0.7) | loại |

Ma trận nhầm lẫn (FAIL là lớp dương):

| Tiêu chí | tp | fp | fn | tn | Tỉ lệ FAIL quan sát | Sau Rogan-Gladen |
|---|---|---|---|---|---|---|
| tone_ok | 24 | 4 | 6 | 66 | 0.28 | 0.30 |
| helpful | 9 | 0 | 21 | 70 | 0.09 | 0.30 |

## ≥5 case audit thủ công

Toàn bộ 10 bất đồng của `tone_ok` (4 judge FAIL nhầm, 6 judge PASS nhầm). Cột "Ai đúng?" dựa trên cột `note` của file CSV.

| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú / sửa rubric |
|---|---|---|---|---|---|
| 1 | H-008 "Em đã hoàn tiền cho anh rồi nha, anh check giúp em." | PASS | FAIL | Người | Xưng "em" và "nha" quá suồng sã; judge hiểu thành thân thiện. Sửa rubric: "nha/nhé/nè" và xưng "em/anh" là FAIL; chỉ dùng "Dạ ... anh/chị ... ạ". |
| 2 | H-017 "Dạ, bạn ơi LogiX đã hoàn 25.000đ ... rồi nha." | PASS | FAIL | Người | Xưng "bạn" với khách lớn tuổi. Sửa rubric: bắt buộc "anh/chị"; có "Dạ" mở đầu không bù được xưng hô sai. |
| 3 | H-029 "Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm." | PASS | FAIL | Người | Câu "không cần nhắn thêm" là ra lệnh; judge chỉ thấy "Dạ, vui lòng". Sửa rubric: câu yêu cầu khách ngừng liên hệ là FAIL dù mở đầu lịch sự. |
| 4 | H-063 "Dạ, LogiX đã hoàn 20.000đ và sẽ hoàn thêm cho anh/chị ạ." | PASS | FAIL | Người | Hứa "sẽ hoàn thêm" ngoài kết quả hệ thống. Đây không thuần là giọng điệu; chuyển thành kiểm tra bằng code (không hứa hành động ngoài kết quả host). |
| 5 | H-070 "Dạ, LogiX đã hoàn 90.000đ cho đơn O-909 ạ 😂😂" | PASS | FAIL | Người | Emoji không phù hợp ngữ cảnh khiếu nại. Sửa rubric: cấm emoji, và kiểm bằng regex thay vì judge. |
| 6 | H-094 "Da, LogiX da hoan 40.000đ cho don O-341, xin loi ..." | PASS | FAIL | Người | Mất dấu tiếng Việt (dịch máy). Sửa rubric: reply phải đủ dấu tiếng Việt; kiểm bằng code (tỉ lệ ký tự có dấu). |
| 7 | H-042 "Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ." | FAIL | PASS | Người | Ngắn nhưng đủ ý; judge phạt vì "thiếu xin lỗi". Sửa rubric: không yêu cầu xin lỗi khi thông báo đã hoàn tiền; xin lỗi chỉ cần khi có sự cố do LogiX. |
| 8 | H-051 "Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ." | FAIL | PASS | Người | "refund" được CS LogiX cho phép; judge phạt vì tiếng Anh. Sửa rubric: liệt kê "refund" là từ mượn hợp lệ. |
| 9 | H-081 "Dạ, đơn O-107 chưa đủ điều kiện hoàn theo chính sách hiện hành ạ." | FAIL | PASS | **Judge** | Theo `note`, nhãn người sai (đọc nhầm ticket). Hành động: ghi nhận nhãn cần sửa thành FAIL. Không sửa trực tiếp file CSV công khai vì test tham chiếu (κ≈0.757) dựa trên nó. Nếu sửa, số liệu thành P=0.893, R=0.806, κ=0.784: tone_ok vẫn đạt và tốt hơn. |
| 10 | H-088 "Dạ, dạ, LogiX đã hoàn 40.000đ cho đơn O-233 ạ." | FAIL | PASS | Người | Lặp "Dạ" là lỗi gõ, không phải giọng điệu. Sửa rubric: lỗi chính tả/gõ lặp không bị tính là FAIL ở tone_ok. |

Mẫu chung: 9/10 bất đồng là do judge, 1/10 (H-081) là nhãn người sai. Judge sai theo hai hướng: bỏ sót (xưng hô, ra lệnh, emoji, mất dấu) và phạt thừa (thiếu xin lỗi, từ mượn "refund", lỗi gõ). Cả ba mục bỏ sót cuối (hứa ngoài hệ thống, emoji, mất dấu) kiểm bằng code rẻ và chắc hơn judge.

## Kết luận
- **Tiêu chí bị loại: `helpful`.** κ = 0.375 (< 0.6) và recall = 0.300 (< 0.7). Precision = 1.000 chỉ vì judge báo FAIL đúng 9 lần, không có ý nghĩa khi nó bỏ sót 21/30 lỗi thật (fn = 21, tn = 70, fp = 0). Judge bắt đủ 9/9 lỗi hình thức (lạc đề 2, không hỏi lại mã đơn 3, giọng cụt 4) nhưng bỏ sót 18/18 reply sai số tiền và 3/3 lỗi xưng hô. Lý do: judge chỉ thấy reply, không thấy ledger (số đúng nằm ở cột `note`), nên không thể kiểm số tiền. Tỉ lệ FAIL quan sát 0.09 trong khi tỉ lệ thật 0.30 (Rogan-Gladen với sens = 0.3, spec = 1.0 chỉnh về đúng 0.30). Dùng judge này làm gate sẽ cho qua 70% bản lỗi. Số tiền luôn chấm bằng code (`RefundAmountCorrect`, `reply_matches_ledger`).
- **Tiêu chí dùng được: `tone_ok`** (κ = 0.757, P = 0.857, R = 0.800, đạt cả ba floor). Dùng như chấm mềm hoặc cảnh báo, không làm safety gate. Cần áp dụng 10 chỉnh sửa rubric ở bảng trên, trong đó các lỗi kiểm được bằng quy tắc (emoji, mất dấu, hứa ngoài hệ thống) chuyển sang code.
- **Rủi ro còn lại:** judge chỉ được kiểm trên dữ liệu replay đã công khai; cần nhãn người mới để có held-out thật. Có ít nhất một nhãn người sai (H-081), nên chất lượng nhãn cũng cần được kiểm.
