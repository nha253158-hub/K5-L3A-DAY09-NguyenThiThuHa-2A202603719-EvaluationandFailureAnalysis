# Trace case: C-014@11, từ trace tới quyết định sai đầu tiên

Tái hiện:

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-014 --seed 11
python -m lab9.trace_case --shape fixed --claim C-014 --seed 11   # đối chứng
```

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-014@11`, run `E-seeded_regression-20261117-69f5` (eval set `69f58f4deef6`). Cả 5 seed (11/22/33/44/55) của C-014 đều lỗi giống hệt nhau. |
| Triệu chứng | Lab 8 grader FAIL (`proposal_mismatch`). Ledger ghi **90.000đ**, nhãn là **120.000đ**. Reply lại nói "Dạ, LogiX đã hoàn **120.000đ** cho đơn O-515", tức khách được báo nhiều hơn số thực nhận 30.000đ. |
| Bước sai đầu tiên | **Event 5, `proposal`**: `{"amount_vnd": 120000}`. Quote ở event 3 là 150.000; shape tự trừ 30.000 đã hoàn rồi mới đưa cho host, thay vì truyền đủ 150.000. |
| Vì sao là bước *đầu tiên* | Event 1–3 cùng kind và cùng kết quả với `fixed` (handoff, investigator tra đơn O-515, quote 150.000 từ SHIP-LATE-03 + DMG-04). Event 4 `refund_history` = `{refund_count: 1, refunded_vnd: 30000}` là dữ liệu đúng, chỉ là một lần tra cứu. Event 5 là giá trị đầu tiên lệch khỏi quote. Event 6 (reply 120.000đ) chỉ là hậu quả: shape báo số nó tự đề xuất chứ không báo số host ghi. |
| Failure mode | **FM-05 pre_deducted** (nguyên nhân gốc, event 5), kéo theo **FM-08 misreport** (event 6). |
| Đối chứng | `fixed C-014@11` (run `E-fixed-20261117-69f5`): trace chỉ có 4 event, không có `refund_history` hay `proposal`. Shape đưa đủ quote 150.000 cho host, host tự trừ 30.000 đã hoàn, ledger = **120.000** = nhãn. Reply "đã hoàn 120.000đ" khớp ledger. Lab 8 PASS. |
| Regression test | `src/tests/test_lab9_fm08.py`. Nhắm đúng bước sai (event 5): `test_c014_proposal_120k_but_quote_150k` (grader `ProposalIsQuote`, step level, metric `proposal_is_quote`). Nhắm hậu quả (event 6): `test_c014_pre_deducted_reply_says_120k_but_ledger_holds_90k` (grader `ReplyMatchesLedger`, metric `reply_matches_ledger`), kèm đối chứng `test_fixed_c014_reply_matches_ledger`. Các test lấy reply và event thật từ trace trên. Chạy end-to-end: C-014 trên `seeded_regression` có `refund_amount_correct`, `reply_matches_ledger`, `proposal_is_quote` đều **False** ở 5/5 seed; trên `fixed` đều **True** ở 5/5 seed. |
| Chưa chắc chắn | (1) Trace không có event nào cho thấy phép trừ phía host. "Host trừ thêm 30.000" được suy ra từ số học 120.000 − 30.000 = 90.000 và từ chú thích FM-05 trong code variant, không nhìn thấy trực tiếp trong event. (2) MockLLM và lỗi do code xác định, nên 5 seed giống nhau không nói được gì về độ ổn định trên model thật. (3) `approval_bypass` = 0 nên safety gate không thấy case này: không có khoản hoàn vượt quyền, chỉ là sai số tiền. Case này chỉ bị chặn nhờ `pass_rate`, `refund_amount_correct`, `reply_matches_ledger`. (4) C-014 còn dính FM-04 ở `slice_regression`, đó là cơ chế khác (cộng thay vì max) và không thuộc case này. |

## Cách đọc (ledger trước reply)

Nhìn riêng reply thì không có gì sai: câu lịch sự, đúng định dạng "đã hoàn N đồng", số 120.000đ đúng bằng số khách đáng nhận. Chỉ khi đọc ledger (90.000đ) mới thấy khoản hoàn sai, và chỉ khi đọc event 5 mới thấy nguyên nhân. Vì vậy metric `reply_matches_ledger` so reply với **ledger**, không so với nhãn, còn `proposal_is_quote` bắt thẳng bước sai ngay khi nó xảy ra.