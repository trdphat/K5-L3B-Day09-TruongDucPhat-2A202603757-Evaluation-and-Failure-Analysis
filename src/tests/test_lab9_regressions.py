"""Regressions missing from the public vectors, including a reply-only FM-08 bug."""

import copy
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.student


def test_eval_set_sha_is_stable_across_git_line_endings(tmp_path):
    from lab9.evalset import sha12

    lf = tmp_path / "linux.jsonl"
    crlf = tmp_path / "windows.jsonl"
    lf.write_bytes(b'{"item_id":"A"}\n{"item_id":"B"}\n')
    crlf.write_bytes(lf.read_bytes().replace(b"\n", b"\r\n"))
    assert sha12(lf) == sha12(crlf)
    crlf.write_bytes(b'{"item_id":"different"}\n')
    assert sha12(lf) != sha12(crlf)


def test_pre_deduction_is_detected_when_the_host_writes_nothing():
    from lab9.graders import ProposalAmountCorrect, RefundAmountCorrect

    ctx = SimpleNamespace(output={"snapshot": {"refund_vnd": 0}, "result": {"proposal_amount": 0}},
                          expected_output={"refund_vnd": 0, "proposal_amount": 35000})
    assert RefundAmountCorrect().evaluate(ctx).value is True
    assert ProposalAmountCorrect().evaluate(ctx).value is False


def test_fm08_detects_reply_mismatch_on_unchanged_ledger(tmp_path, monkeypatch):
    from lab8.shapes import SHAPES
    from lab9.eval import load_spec, load_world, make_task
    from lab9.graders import ReplyLedgerConsistent
    from lab9.variant_agent import make_shape

    spec = load_spec()
    world, claims = load_world(spec)
    labels = {claim["claim_id"]: claim["expected"] for claim in claims}
    trials = []
    for name, bugs in (("correct_reply", {"no_override"}), ("wrong_reply", {"no_override", "misreport"})):
        monkeypatch.setitem(SHAPES, name, make_shape(name, bugs))
        trial = make_task(name, world, claims, labels, tmp_path)({"claim_id": "C-008", "seed": 11})
        trials.append(trial)
        assert trial["lab8_pass"] is True
        assert trial["snapshot"]["refund_vnd"] == 20000
    grader = ReplyLedgerConsistent()
    assert grader.evaluate(SimpleNamespace(output=trials[0])).value is True
    assert grader.evaluate(SimpleNamespace(output=trials[1])).value is False


def test_ticket_override_is_first_wrong_step_and_fixed_passes(tmp_path, monkeypatch):
    from lab8.shapes import SHAPES
    from lab9.eval import load_spec, load_world, make_task
    from lab9.graders import DbFactKept, RefundAmountCorrect
    from lab9.variant_agent import make_shape
    from lab9.variants import VARIANTS

    world, claims = load_world(load_spec())
    labels = {claim["claim_id"]: claim["expected"] for claim in claims}
    for name, expected in (("seeded_regression", False), ("fixed", True)):
        monkeypatch.setitem(SHAPES, name, make_shape(name, VARIANTS[name]))
        trial = make_task(name, world, claims, labels, tmp_path)({"claim_id": "C-002", "seed": 11})
        ctx = SimpleNamespace(output=trial, expected_output=labels["C-002"])
        assert trial["lab8_pass"] is expected
        assert DbFactKept().evaluate(ctx).value is expected
        assert RefundAmountCorrect().evaluate(ctx).value is expected
        assert trial["events"][1]["payload"]["lookup_order"]["order"]["delay_days"] == 2
        if not expected:
            assert trial["events"][2] == {"kind": "model_override", "payload": {"delay_days": 5}}


@pytest.mark.parametrize("text", ["Đã hoàn 35.000đ", "Đã hoàn 35,000 VND", "Đã hoàn 35000 đồng", "Đã hoàn 35 000 ₫"])
def test_fm08_accepts_currency_formats(text):
    from lab9.graders import ReplyLedgerConsistent

    trial = {"snapshot": {"refund_vnd": 35000},
             "result": {"status": "resolved", "refund_effects": [{"amount_vnd": 35000}]},
             "events": [{"kind": "reply", "payload": {"text": text}}]}
    assert ReplyLedgerConsistent().evaluate(SimpleNamespace(output=trial)).value is True


def _report():
    rows = [{"item_id": item, "seed": seed, "pass_rate": True, "slices": ["money_movement"]}
            for item in ("A", "B") for seed in (11, 22)]
    return {"manifest": {"eval_set_sha": "x", "items": 2, "seeds": [11, 22]},
            "metrics": {"pass_rate": 1.0}, "rows": rows, "evaluator_failures": []}


SPEC = {"eval_set_version": "v2", "metrics": [{"id": "pass_rate", "blocking": True,
        "threshold": {"min": 0.8, "no_significant_drop": True}}],
        "slices": [{"name": "money_movement", "metric": "pass_rate", "min": 0.8,
                    "blocking": True, "no_significant_drop": True}]}


@pytest.mark.parametrize("trap", ["duplicate", "evaluator_error", "relabel", "missing_score", "forged_aggregate"])
def test_integrity_rejects_hidden_evidence(trap):
    from lab9.gate import integrity_check

    base = _report()
    pr = copy.deepcopy(base)
    if trap == "duplicate":
        pr["rows"][-1] = copy.deepcopy(pr["rows"][0])
    elif trap == "evaluator_error":
        pr["evaluator_failures"] = ["grader crashed on an otherwise green run"]
    elif trap == "relabel":
        for row in pr["rows"]:
            row["slices"] = []
    elif trap == "missing_score":
        pr["rows"][0]["pass_rate"] = None
    else:
        pr["rows"][0]["pass_rate"] = False
    assert integrity_check(pr, base, SPEC)


@pytest.mark.parametrize("change", ["drop_metric", "unblock", "drop_ci", "drop_slice", "relax_slice"])
def test_ratchet_preserves_release_requirements(change):
    from lab9.gate import integrity_check

    current = copy.deepcopy(SPEC)
    if change == "drop_metric":
        current["metrics"] = []
    elif change == "unblock":
        current["metrics"][0]["blocking"] = False
    elif change == "drop_ci":
        current["metrics"][0]["threshold"].pop("no_significant_drop")
    elif change == "drop_slice":
        current["slices"] = []
    else:
        current["slices"][0]["min"] = 0.5
    base = _report()
    assert integrity_check(base, base, current, SPEC)


@pytest.mark.parametrize("args", [(0, 0, 1), (5, -1, 1), (5, 6, 1), (5, 2, 6), (5.0, 2, 1), (True, 1, 1)])
def test_pass_k_rejects_invalid_counts(args):
    from lab9.stats import pass_at_k, pass_hat_k

    for estimator in (pass_at_k, pass_hat_k):
        with pytest.raises(ValueError):
            estimator(*args)
