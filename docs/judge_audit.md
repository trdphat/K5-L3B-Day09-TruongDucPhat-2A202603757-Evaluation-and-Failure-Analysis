# Judge audit

Đo trên hai CSV replay công khai, mỗi CSV 100 dòng. `FAIL` là lớp dương. Precision đo tỷ lệ lỗi thật trong các dòng judge báo lỗi, recall đo tỷ lệ lỗi người gắn nhãn được judge tìm thấy. Ngưỡng theo đề bài là κ ≥ 0.6, precision ≥ 0.8 và recall ≥ 0.7.

| Tiêu chí | n | TP | FP | FN | TN | κ | Precision | Recall | Đạt FLOORS | Quyết định |
|---|---|---|---|---|---|---|---|---|---|---|
| tone_ok | 100 | 24 | 4 | 6 | 66 | 0.757 | 0.857 | 0.800 | Có | Dùng cho tone, giữ audit bất đồng |
| helpful | 100 | 9 | 0 | 21 | 70 | 0.375 | 1.000 | 0.300 | Thiếu κ và recall | Loại khỏi release gate |

Tone có observed failure rate 0.280, sensitivity 0.800 và specificity 66/70. Rogan–Gladen hiệu chỉnh thành 0.300. Helpful có observed rate 0.090, sensitivity 0.300 và specificity 1.000, hiệu chỉnh thành 0.300. Hiệu chỉnh prevalence cần sensitivity và specificity ổn định trên population đích. Kappa không xác định trên bộ nhãn hằng được xử lý thành calibration FAIL.

## Audit các bất đồng

Các quyết định dưới đây đối chiếu rubric trên dữ liệu replay. Nhãn người trong CSV và model replay được giữ nguyên.

| Case | Judge | Người | Phán quyết audit và bằng chứng | Sửa rubric |
|---|---|---|---|---|
| H-008 | PASS | FAIL | Đồng ý người. Xưng “em”, gọi “anh”, dùng “nha” quá suồng sã. | Yêu cầu xưng hô CSKH thống nhất, tránh suồng sã khi thiếu ngữ cảnh khách. |
| H-017 | PASS | FAIL | Đồng ý người. “bạn ơi…rồi nha” vi phạm chuẩn xưng hô của bộ tone. | Thêm ví dụ FAIL có lời mở đầu lịch sự nhưng xưng hô thiếu phù hợp. |
| H-029 | PASS | FAIL | Đồng ý người. “không cần nhắn thêm” mang tính ra lệnh. | Chấm toàn câu, thêm tiêu chí tránh ngăn cản khách hỏi tiếp. |
| H-042 | FAIL | PASS | Đồng ý người. Câu ngắn có thông tin hoàn tiền và thời gian, giọng lịch sự. | Cho phép trả lời ngắn và nêu khi nào cần xin lỗi. |
| H-051 | FAIL | PASS | Đồng ý người. Từ “refund” được CS LogiX cho phép và câu vẫn lịch sự. | Thêm refund vào danh sách thuật ngữ được dùng. |
| H-063 | PASS | FAIL | Đồng ý người theo rubric replay. Lời hứa “sẽ hoàn thêm” vượt kết quả hệ thống. | Đánh dấu lời hứa tài chính thiếu căn cứ, chuyển xác minh số tiền sang code. |
| H-088 | FAIL | PASS | Đồng ý người. Lặp “Dạ” là lỗi gõ nhẹ, thông điệp vẫn lịch sự. | Chấp nhận lỗi gõ nhỏ khi ý nghĩa và sự tôn trọng vẫn rõ. |
| H-094 | PASS | FAIL | Đồng ý người theo chuẩn tiếng Việt của tập tone. Câu thiếu dấu toàn bộ. | Nêu yêu cầu tiếng Việt có dấu và ví dụ tương ứng. |
| HL-015 | PASS | FAIL | Đồng ý người. Reply 55000, ledger 40000. | Code đối chiếu reply với ledger trước khi đánh giá helpfulness. |
| HL-016 | PASS | FAIL | Đồng ý người. Nhiều lời xin lỗi che việc nói 55000 thay vì 35000. | Tách tính đúng tài chính và phép lịch sự thành tiêu chí đo riêng. |
| HL-020 | PASS | FAIL | Đồng ý người. Reply 90000, ledger 120000. | Yêu cầu evidence tiền từ ledger, áp dụng metric FM-08. |
| HL-028 | PASS | FAIL | Đồng ý người. Reply 50000, ledger 35000, phần xin lỗi dài. | Giới hạn ảnh hưởng độ dài lời xin lỗi khi chấm khả năng giải quyết yêu cầu. |
| HL-035 | PASS | FAIL | Đồng ý người. Reply 50000, ledger 35000. | Chỉ chấp nhận con số khớp effect đã commit. |

Helpful bỏ sót 21/30 lỗi thật. Precision 1.000 đi cùng recall 0.300 khiến nhiều câu sai tiền vẫn qua. Gate dùng `ReplyLedgerConsistent`, `RefundAmountCorrect` và `ProposalAmountCorrect` cho nội dung tài chính. Tone đạt sàn calibration và được dùng trong phạm vi đánh giá tone, với human review khi cần.

## Tái lập và giới hạn

Chạy trong `src` bằng `python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 5` và lệnh tương tự với `judge_helpful_public.csv`. Lệnh helpful trả exit 1 đúng kỳ vọng. Output thật được lưu trong `reports/checkpoints.json` bằng `scripts/check_lab9.py`.

Cả hai CSV đã công khai và dùng replay. Chưa có holdout do người gắn nhãn mới hoặc đánh giá judge trên LLM thật. Các thay đổi rubric cần được kiểm định lại trên holdout mới trước khi dùng vào release thực tế.
