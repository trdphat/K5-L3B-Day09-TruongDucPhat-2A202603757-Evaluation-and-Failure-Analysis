# Trace case: từ trace tới quyết định sai đầu tiên

Case chính là `seeded_regression C-002@11`, run ID `E-seeded_regression-20261118-67d9`, thuộc eval set SHA `67d90820539b`. Agent đổi số ngày trong DB từ 2 thành 5 theo ticket, dẫn tới hoàn sai 20000 VND. Bước sai đầu tiên là sự kiện thứ 3 `model_override`.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Phân tích case

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`, row E-002/seed 11 trong `src/reports/eval_seeded_regression.json` |
| Triệu chứng | `pass_rate`, `refund_amount_correct`, `proposal_amount_correct` và `db_fact_kept` đều false. Reply nói đã hoàn 20000, ledger ghi 20000, nhãn yêu cầu denied và 0 VND. |
| Bước sai đầu tiên | Event 3, `model_override`, payload `{"delay_days": 5}` |
| Vì sao là bước đầu tiên | Event 1 handoff giới hạn read-only và bỏ secret. Event 2 investigator trả đơn O-202 có `delay_days=2`, policy_count=1. Chỉ đến event 3 dữ kiện DB mới bị thay. |
| Failure mode | FM-03, `ticket_trust`, layer model/prompt |
| Đối chứng | `fixed C-002@11` giữ delay 2. Event 3 `quote` amount 0, reason `no_entitlement`. Event 4 reply từ chối, ledger 0 và pass_rate true. |
| Regression test | `test_ticket_override_is_first_wrong_step_and_fixed_passes` kiểm tra cùng claim/seed, trial lỗi bị cả `DbFactKept` và `RefundAmountCorrect` phát hiện, fixed qua cả hai. Test khẳng định event 2 trả delay 2 và event 3 của bản lỗi đổi thành 5. |
| Chưa chắc chắn | MockLLM và các bug switch được cài có chủ đích. Trace thể hiện luồng dữ kiện nhưng chưa đo tần suất lỗi trên một model thật hoặc người dùng thật. |

## Chuỗi sự kiện quan sát được

| Bước | seeded_regression | fixed |
|---|---|---|
| 1 | handoff read-only | handoff read-only |
| 2 | investigator đọc delay 2 từ DB | investigator đọc delay 2 từ DB |
| 3 | model_override đổi thành 5 | quote 0, no_entitlement |
| 4 | quote 20000 | reply từ chối |
| 5 | refund_history 0 | Đã kết thúc |
| 6 | reply nói đã hoàn 20000 | Đã kết thúc |

Chạy lại các lệnh ở trên để tái tạo trace gốc. Các đối chứng theo từng FM được sinh bằng `python scripts/check_lab9.py --trace-only`. [Báo cáo regression](../src/reports/eval_seeded_regression.json), [bằng chứng trace](../src/reports/trace_evidence.json), [regression tests](../src/tests/test_lab9_regressions.py)

## Case bổ sung FM-08

`evidence_misreport C-008@11` có quote 35000 và approval cap 20000. Host ghi 20000, `refund_effects` cũng báo 20000, nhưng event 4 `reply` nói đã hoàn 35000. Lab8 `trial_pass` vẫn true. `ReplyLedgerConsistent` phát hiện sai lệch này bằng cách đọc câu trả lời và ledger. Đối chứng fixed nói đúng 20000. Test `test_fm08_detects_reply_mismatch_on_unchanged_ledger` tái tạo cả hai trial với cùng ledger và kiểm tra metric mới fail/pass tương ứng.

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
