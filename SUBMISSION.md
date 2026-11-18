# Nộp bài (bài cá nhân, hạn nộp theo ca làm bài)
1. Commit các report sinh bằng script: trong `src/` chạy `git add -f reports/*.json` (`.gitignore` bỏ qua `src/reports/`, không có `-f` thì report không lên repo).
2. Mở PR `starter/d09` → `main` **trong bản fork của bạn**, không mở vào repo gốc. Dán output gate exit 1 của `seeded_regression` vào mô tả PR.
3. Job `eval-gate` xanh thì **merge PR vào `main`**. Giảng viên chấm nhánh `main` của bản fork; commit sau hạn của ca không tính.
4. Dán **link repo fork** (`K5-L3A-DAY09-HoVaTen-MSSV-EvaluationandFailureAnalysis`) lên LMS.

Làm thêm Advanced/Expert sau buổi: tiếp tục trên nhánh, mở PR mới rồi merge lại trước hạn.

## Core (nên xong trước 17:00)
- [x] `src/lab9/{stats,graders,evalset}.py` đã hoàn thành TODO M1–M4
- [x] `src/data/eval/eval_set_v1.jsonl` có `failure_modes`, `labels_v1.json` tách riêng
- [x] `docs/failure_taxonomy.md`, `docs/trace_case.md` (1 case + regression test), `docs/judge_audit.md`, `docs/eval_card.md`, `docs/PRD_v1.1.md`
- [x] `src/reports/baseline_v1.json`, `eval_fixed.json`, `eval_seeded_regression.json` sinh bằng script
- [x] `src/harness_map.yaml` có section `eval` (mẫu: `src/harness_map.eval.yaml`)
- [x] Job `eval-gate` xanh; output gate exit 1 của `seeded_regression` đã có trong mô tả PR

## Advanced / Expert (tới hạn nộp)
- [x] `src/config/fm_map.yaml`, `src/config/metric_spec_v2.yaml` (slices, `pass_hat_5`, metric FM-08), `stats.pass_at_k/pass_hat_k`, `gate.slice_check`, `gate.integrity_check`
- [x] `src/data/eval/eval_set_v2.jsonl` + `labels_v2.json` sinh bằng `evalset --v2 --build`
- [x] `src/reports/baseline_v2.json` sinh bằng script
- [x] Job `eval-gate-v2` xanh trên PR
- [x] Mô tả PR có output `lab9.mutation`, A/A và bốn dòng exit 1 của trap
- [x] `docs/eval_card.md` thêm mục v2 gồm ngưỡng từ A/A, slice và giới hạn cỡ mẫu

## Bằng chứng và bước nộp

Kiểm chứng local ngày 18/11/2026 đạt 57 test nền, 47 test Lab9 và 28 lệnh checkpoint đúng exit code mong đợi. `python scripts/check_lab9.py` chạy lại toàn bộ và ghi `reports/checkpoints.json`. Code tại commit `13a9d8a`, các report và tài liệu nộp được lưu trên nhánh `starter/d09`.

- [x] Commit code, tài liệu và report sinh bằng script, force-add các report bị gitignore.

- [x] Push nhánh `starter/d09` lên fork.
- [x] Mở PR `starter/d09` → `main` trong fork và dán bằng chứng bên dưới.
- [x] CI Core và Advanced xanh tại run `44235070790`, commit `d47be97`.
- [ ] Dán link fork lên LMS của ca.

PR #1 nằm trong bản fork cá nhân. Cả ba job detect, eval-gate và eval-gate-v2 đã hoàn thành thành công, gồm các bước test và mutation v2. Trạng thái merge và CI của commit mới nhất được xem trực tiếp trên PR. [PR #1](https://github.com/trdphat/K5-L3B-Day09-TruongDucPhat-2A202603757-Evaluation-and-Failure-Analysis/pull/1), [CI Linux đã xác nhận](https://github.com/trdphat/K5-L3B-Day09-TruongDucPhat-2A202603757-Evaluation-and-Failure-Analysis/actions/runs/44235070790)

Tóm tắt bằng chứng dùng cho mô tả PR lấy từ các lệnh kiểm chứng.

```text
pass_rate 0.7143 Δ -0.271 CI [-0.500, -0.057] BLOCK
exit 1 — blocked: refund_amount_correct, pass_rate, reply_ledger_consistent, proposal_amount_correct
detection 100.00% (target >=80%) · false alarms 0.00% (target <=10%)
mutation score 3/3 · false alarms 0
```

A/A trên seeds 11/22/33/44/55 và 66/77/88/99/110 cho mọi metric Δ +0.0000. Baseline pass_hat_5 là 0.8929 ở cả hai lượt. Mỗi lệnh gate trap dưới đây đã được chạy riêng và đều in `INTEGRITY` rồi `exit 1 — blocked: integrity`.

```text
evaluator_errors_as_nan → exit 1 — blocked: integrity
dropped_failing_rows    → exit 1 — blocked: integrity
cherry_picked_seeds     → exit 1 — blocked: integrity
loosened_spec          → exit 1 — blocked: integrity
```

Output đầy đủ và command tương ứng nằm trong `src/reports/checkpoints.json`. Chấm điểm hidden và kiểm tra anchor key thuộc repo riêng của giảng viên.
