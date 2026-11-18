"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, aggregate, load_spec, per_item
from lab9.graders import GRADERS


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems = []
    graded = [m["id"] for m in spec["metrics"] if m["id"] in GRADERS]
    report_keys = []
    slice_tags = []
    for name, report in (("PR", pr), ("baseline", base)):
        manifest = report.get("manifest", {})
        rows = report.get("rows", [])
        seeds = manifest.get("seeds", [])
        items = manifest.get("items", 0)
        if (not isinstance(items, int) or isinstance(items, bool) or items < 1
                or not seeds or any(type(s) is not int for s in seeds) or len(set(seeds)) != len(seeds)):
            problems.append(f"{name}: invalid manifest item count or seeds")
            return problems
        if len(rows) != items * len(seeds):
            problems.append(f"{name}: row count differs from items x seeds")
        if report.get("evaluator_failures"):
            problems.append(f"{name}: evaluator_failures is non-empty")
        for mid, value in report.get("metrics", {}).items():
            if value is not None and (not isinstance(value, (int, float)) or not math.isfinite(value)):
                problems.append(f"{name}: metric {mid} is not finite")
        for metric in spec["metrics"]:
            if report.get("metrics", {}).get(metric["id"]) is None:
                problems.append(f"{name}: metric {metric['id']} is missing")
        keys = []
        tags = {}
        for row in rows:
            item_id, seed = row.get("item_id"), row.get("seed")
            if not isinstance(item_id, str) or not item_id or type(seed) is not int:
                problems.append(f"{name}: invalid item_id or seed in row")
                return problems
            keys.append((item_id, seed))
            row_tags = row.get("slices", [])
            if not isinstance(row_tags, list) or any(not isinstance(tag, str) for tag in row_tags):
                problems.append(f"{name}: invalid slice tags on {item_id}")
                return problems
            current_tags = frozenset(row_tags)
            if item_id in tags and tags[item_id] != current_tags:
                problems.append(f"{name}: inconsistent slice tags on {item_id}")
            tags[item_id] = current_tags
            for mid in graded:
                if type(row.get(mid)) is not bool:
                    problems.append(f"{name}: {item_id}@{seed} has a missing or invalid {mid} score")
            if "cost" in row and (not isinstance(row["cost"], (int, float))
                                  or not math.isfinite(row["cost"]) or row["cost"] < 0):
                problems.append(f"{name}: invalid cost on {item_id}@{seed}")
        counts = Counter(keys)
        expected = {(item_id, seed) for item_id in tags for seed in seeds}
        if len(tags) != items or set(keys) != expected or any(n != 1 for n in counts.values()):
            problems.append(f"{name}: rows must cover every item x seed exactly once")
        report_keys.append(set(keys))
        slice_tags.append(tags)
        # Recalculate from rows so a forged aggregate cannot hide a failed trial.
        if not problems:
            normalized = [dict(row, cost=row.get("cost", 0.0)) for row in rows]
            recomputed = aggregate(normalized, graded, k_values=spec.get("pass_k", []))
            for mid, value in report["metrics"].items():
                expected_value = recomputed.get(mid)
                if mid in recomputed and (value is None or expected_value is None or
                                          not math.isclose(value, expected_value, abs_tol=1e-9)):
                    problems.append(f"{name}: metric {mid} disagrees with rows")
    if report_keys[0] != report_keys[1]:
        problems.append("PR and baseline have different (item_id, seed) sets")
    if slice_tags[0] != slice_tags[1]:
        problems.append("PR and baseline have different item slice tags")
    if (set(pr.get("manifest", {}).get("seeds", [])) != set(base.get("manifest", {}).get("seeds", []))
            or pr.get("manifest", {}).get("items") != base.get("manifest", {}).get("items")):
        problems.append("PR and baseline have different sampling manifests")
    if base_spec is not None and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        for section, identity in (("metrics", "id"), ("slices", "name")):
            current = {(entry[identity], entry.get("metric")): entry for entry in spec.get(section, [])}
            for old in base_spec.get(section, []):
                key = (old[identity], old.get("metric"))
                new = current.get(key)
                if new is None:
                    problems.append(f"ratchet: removed {section} {key}")
                    continue
                if old.get("blocking") and not new.get("blocking"):
                    problems.append(f"ratchet: disabled blocking on {key}")
                old_th = old.get("threshold", {}) if section == "metrics" else old
                new_th = new.get("threshold", {}) if section == "metrics" else new
                for bound in ("min", "max", "max_increase"):
                    if bound not in old_th:
                        continue
                    value = new_th.get(bound)
                    if (not isinstance(value, (int, float)) or not math.isfinite(value)
                            or (bound == "min" and value < old_th[bound])
                            or (bound != "min" and value > old_th[bound])):
                        problems.append(f"ratchet: loosened {bound} on {key}")
                if old_th.get("no_significant_drop") and not new_th.get("no_significant_drop"):
                    problems.append(f"ratchet: removed no_significant_drop on {key}")
        if spec.get("seeds") != base_spec.get("seeds") or spec.get("eval_set") != base_spec.get("eval_set"):
            problems.append("ratchet: changed sampling or eval-set path without a version bump")
    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked, lines = [], []
    bootstrap = spec.get("bootstrap", {})
    for entry in spec.get("slices", []):
        name, metric = entry["name"], entry["metric"]
        mid = f"slice:{name}/{metric}"
        current = per_item(pr, metric, slice_name=name)
        previous = per_item(base, metric, slice_name=name)
        if not current or current.keys() != previous.keys():
            if entry.get("blocking"):
                blocked.append(mid)
            lines.append(f"  {mid} MISSING or mismatched slice items")
            continue
        value = sum(current.values()) / len(current)
        failed = value < entry.get("min", float("-inf"))
        note = ""
        if entry.get("no_significant_drop"):
            keys = sorted(current)
            delta, lo, hi = stats.paired_bootstrap(
                [current[k] for k in keys], [previous[k] for k in keys],
                n_resamples=bootstrap.get("n_resamples", 1000), rng=bootstrap.get("rng", 2027),
                confidence=bootstrap.get("confidence", 0.95))
            note = f"Δ {delta:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            failed = failed or hi < 0
        if failed and entry.get("blocking"):
            blocked.append(mid)
        verdict = "BLOCK" if failed and entry.get("blocking") else ("warn" if failed else "ok")
        lines.append(f"  {mid:<38} {value:.4f} {note} {verdict}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027),
                                               confidence=bs.get("confidence", 0.95))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
