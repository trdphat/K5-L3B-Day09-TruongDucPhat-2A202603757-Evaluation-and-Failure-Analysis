# Eval card — LogiX-VN refund agent

Ngày đo 18/11/2026. Eval owner là Trương Đức Phát, MSSV 2A202603757. Code và grader tại commit `13a9d8a`. Backend MockLLM chạy offline. Toàn bộ số dưới đây lấy từ các report do `lab9.eval` sinh và output của `scripts/check_lab9.py`.

## Eval set v1 và phiên bản

V1 có 14 item × 5 seed = 70 trial, nguồn `lab8_public`, nhãn tách trong `data/eval/labels_v1.json`. Seeds là 11, 22, 33, 44, 55. Eval set SHA `67d90820539b`, metric spec `1.1`. Baseline run ID `E-swarm-20261118-67d9`. Bản đối chứng sửa lỗi có run ID `E-fixed-20261118-67d9`, bản regression có run ID `E-seeded_regression-20261118-67d9`.

Fingerprint chuẩn hóa CRLF thành LF trước khi tính SHA-256 để cùng nội dung eval set có cùng SHA trên Windows và Linux. Regression test kiểm tra cả hai kiểu xuống dòng và xác nhận thay đổi nội dung vẫn đổi fingerprint.

| Metric | Ngưỡng v1 | Blocking | Swarm baseline | Fixed | Seeded regression |
|---|---|---|---|---|---|
| approval_bypass | max 0 | Có | 0 | 0 | 0 |
| secret_leak | max 0 | Có | 0 | 0 | 0 |
| db_fact_kept | min 0.95 | Theo dõi | 0.9857 | 1.0000 | 0.9286 |
| refund_amount_correct | min 0.95, paired CI | Có | 0.9857 | 1.0000 | 0.8571 |
| pass_rate | min 0.85, paired CI | Có | 0.9857 | 1.0000 | 0.7143 |
| reply_ledger_consistent | min 1.00, paired CI | Có | 1.0000 | 1.0000 | 0.7857 |
| proposal_amount_correct | min 0.95, paired CI | Có | 0.9857 | 1.0000 | 0.7857 |
| pass_5 | min 0.80 | Theo dõi | 0.9286 | 1.0000 | 0.7143 |
| cost_per_success | tăng tối đa 10% | Theo dõi | 49.5670 | 48.7157 | 81.2020 |

Chi phí là VND mô phỏng từ `pricing.yaml`. Baseline có một trial lỗi C-002@55. `ApprovalBypass` đo side effect trái phép. FM-02 còn được bắt bằng status, reply và `TrialPass`, vì host vẫn có thể chặn khoản hoàn trong khi agent nói đã trả tiền.

## Paired bootstrap và gate Core

Đơn vị resample là item, sau khi lấy trung bình trên năm seed của item đó. So PR − baseline với `scipy.stats.bootstrap`, `paired=True`, `method=percentile`, 1000 resample, RNG 2027 và confidence 95%.

| So sánh | Metric | Δ | CI 95% | Gate |
|---|---|---|---|---|
| Swarm so với chính nó | pass_rate | 0.000 | [0.000, 0.000] | exit 0 |
| Fixed − swarm | pass_rate | +0.014 | [0.000, +0.043] | exit 0 |
| Seeded regression − swarm | pass_rate | −0.271 | [−0.500, −0.057] | exit 1 |
| Seeded regression − swarm | refund_amount_correct | −0.129 | [−0.315, 0.000] | Vi phạm sàn 0.95 |
| Seeded regression − swarm | reply_ledger_consistent | −0.214 | [−0.429, 0.000] | Vi phạm sàn 1.00 |
| Seeded regression − swarm | proposal_amount_correct | −0.200 | [−0.414, 0.000] | Vi phạm sàn 0.95 |

Detection của các grader giải thích được 100% trial lỗi của seeded_regression, với 0% false alarm trên fixed. `ProposalAmountCorrect` phát hiện cả tình huống pre-deducted khiến proposal sai nhưng ledger và nhãn cùng bằng 0. Kiểm tra `lab9.ci_check` xác nhận baseline là swarm, cùng eval set và cùng metric với run swarm tái lập. [Báo cáo v1](../src/reports/baseline_v1.json), [output kiểm chứng](../src/reports/checkpoints.json)

## Judge và trace case

Tone đạt κ 0.757, precision 0.857, recall 0.800. Helpful có κ 0.375 và recall 0.300, bị loại khỏi gate vì bỏ sót 21/30 lỗi. Audit gồm 13 bất đồng và đề xuất sửa rubric. [Judge audit](judge_audit.md)

Case chính C-002@11 xác định bước 3 `model_override` là bước sai đầu tiên. Case FM-08 C-008@11 chứng minh reply sai tiền vẫn có thể đi cùng ledger đúng. Hai regression test chạy cả bản lỗi lẫn đối chứng fixed. [Trace case](trace_case.md)

Trace Lab8 cũ chưa có sự kiện reply. Với các trial này, metric mới kiểm tra `refund_effects` so với ledger. Phần đối chiếu câu trả lời có bằng chứng trên các variant có event reply. Bộ parser hỗ trợ tiền VND dạng số nguyên với dấu chấm, dấu phẩy, khoảng trắng và ký hiệu đ/đồng/VND/₫. Câu trả lời có nhiều số tiền hoặc diễn đạt tiền bằng chữ cần mở rộng contract và thêm dữ liệu kiểm định.

## V2, slice và độ ổn định

V2 có 28 item × 5 seed = 140 trial, gồm 14 item v1 và 14 item adversarial. SHA `57a7653f56f8`, metric spec `2.1`, baseline `E-swarm-20261118-57a7`. Nhãn nằm ở `labels_v2.json`. Tám cơ chế tấn công đều có map và mỗi FM bị tấn công có ít nhất ba item.

Baseline v2 có pass_rate 0.9786, refund_amount_correct 0.9786, reply_ledger_consistent 1.0000, pass_hat_5 0.8929 và cost_per_success 50.8077. `pass_at_k = 1 − C(n−c,k)/C(n,k)` và `pass_hat_k = C(c,k)/C(n,k)` được tính theo từng item rồi lấy trung bình.

A/A dùng seed 11/22/33/44/55 và 66/77/88/99/110. Mọi metric có Δ 0.0000, gồm pass_hat_5 cùng bằng 0.8929. Khoảng biến thiên thực nghiệm của metric này là [0.8929, 0.8929]. Sàn blocking 0.80 cách giá trị quan sát 0.0929 và đáp ứng yêu cầu M6/M7. Với LLM thật cần đo phân phối giữa các lần chạy trên holdout, chọn sàn có khoảng cách với dải nhiễu và kiểm tra lại false alarm.

| Slice | Sàn pass_rate | No significant drop | Blocking |
|---|---|---|---|
| denial | 0.90 | Có | Có |
| money_movement | 0.90 | Có | Có |
| adversarial | 0.90 | Có | Có |

`slice_regression` có pass_rate chung 0.9357, Δ −0.043 và CI [−0.121, +0.029], vượt sàn chung 0.85. Slice money_movement chỉ đạt 0.8500, Δ −0.150 và CI [−0.300, 0.000], nên bị chặn bởi sàn 0.90. Gate trả đúng `exit 1 — blocked: slice:money_movement/pass_rate`. [Baseline v2](../src/reports/baseline_v2.json), [slice regression](../src/reports/eval_slice_regression.json)

Scorecard đạt 3/3 regression bị chặn, 0 false alarm trên fixed và honest_refactor. Flaky regression bị chặn bởi pass_hat_5 cùng các metric chất lượng khác. Bốn trap công khai đều bị integrity chặn. Kiểm tra bổ sung bao phủ dòng bị trùng, evaluator_failures trên run xanh, slice bị đổi nhãn và aggregate mâu thuẫn rows. Ratchet giữ sàn, trần, blocking và no_significant_drop của metric và slice khi eval-set version giữ nguyên.

## Phạm vi pilot, trách nhiệm và giới hạn

Pilot trong sandbox offline cho yêu cầu hoàn tiền một đơn, dữ liệu order có cấu trúc, policy hiện hành và approval do host cung cấp. Host giới hạn quyền truy cập theo principal, số tiền theo approval và tổng entitlement của đơn. Eval owner xử lý gate đỏ bằng trace, ledger và regression test, sau đó chạy lại toàn bộ kiểm chứng.

MockLLM, 14 item v1, 28 item v2 và judge replay chưa đại diện cho người dùng thật. Với 5 seed, lỗi hiếm xuất hiện khoảng 1/3 seed có thể bị bỏ sót hoặc cho CI rộng. Các lỗi có tương quan giữa item làm giảm lượng thông tin độc lập. Hidden tests và anchor key thuộc repo giảng viên. Provenance và integrity nội bộ vẫn cần baseline cùng spec lấy từ nhánh được bảo vệ để ngăn sửa đồng thời cả hai phía.

Tăng eval-set version khi thêm hoặc đổi item, label, slice semantics hay nguồn dữ liệu. Tăng metric-spec version khi thêm metric hoặc đổi cách chấm, rồi tái sinh baseline tương ứng. Trong cùng eval-set version, ngưỡng chỉ được siết chặt theo ratchet. Run lại toàn bộ bằng `python scripts/check_lab9.py` từ `src`. Trạng thái CI, PR và nộp LMS được theo dõi trong `SUBMISSION.md`.

CI Linux tại commit `d47be97` đã chạy thành công detect, Core eval-gate và Advanced eval-gate-v2, xác nhận baseline Windows tái lập được trên CI sau khi chuẩn hóa fingerprint. [Bằng chứng CI](https://github.com/trdphat/K5-L3B-Day09-TruongDucPhat-2A202603757-Evaluation-and-Failure-Analysis/actions/runs/44235070790)
