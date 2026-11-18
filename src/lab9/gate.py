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
    problems: list[str] = []
    rows = pr.get("rows") or []

    # 1. a metric value that is NaN / inf: `nan < min` is False, so a naive gate lets it through
    for k, v in (pr.get("metrics") or {}).items():
        if isinstance(v, float) and not math.isfinite(v):
            problems.append(f"metric {k} is {v}")

    # 2. dropped or duplicated rows: len(rows) must be items x seeds, every item has every seed once
    m = pr.get("manifest") or {}
    want_rows = int(m.get("items", 0)) * len(m.get("seeds") or [])
    if len(rows) != want_rows:
        problems.append(f"{len(rows)} rows, manifest says {m.get('items')} items x {len(m.get('seeds') or [])} seeds = {want_rows}")
    pairs = Counter((r.get("item_id"), r.get("seed")) for r in rows)
    problems += [f"row {i}@{s} appears {n} times" for (i, s), n in sorted(pairs.items(), key=str) if n > 1]
    seeds = set(m.get("seeds") or [])
    for item in sorted({r.get("item_id") for r in rows}, key=str):
        have = {r.get("seed") for r in rows if r.get("item_id") == item}
        if have != seeds:
            problems.append(f"item {item} has seeds {sorted(have)}, manifest lists {sorted(seeds)}")

    # 3. the (item, seed) set must be the baseline's: no cherry-picked seeds or items
    base_pairs = {(r.get("item_id"), r.get("seed")) for r in base.get("rows") or []}
    if set(pairs) != base_pairs:
        gone = sorted(base_pairs - set(pairs), key=str)
        extra = sorted(set(pairs) - base_pairs, key=str)
        problems.append(f"(item, seed) set differs from the baseline: {len(gone)} missing, {len(extra)} extra")

    # 4. a crashed grader must not silently drop out of the mean
    if pr.get("evaluator_failures"):
        problems.append(f"{len(pr['evaluator_failures'])} evaluator failure(s): {pr['evaluator_failures'][0]}")
    graded = [x["id"] for x in spec.get("metrics", []) if x["id"] in GRADERS]
    for mid in graded:
        n_none = sum(1 for r in rows if r.get(mid) is None)
        if n_none:
            problems.append(f"{n_none} row(s) have no value for graded metric {mid}")

    # 5. the reported metrics must be what the rows say (a hand-edited number is not evidence)
    if rows and not problems:
        try:
            again = aggregate(rows, graded, k_values=spec.get("pass_k", []))
        except (KeyError, TypeError, ValueError):
            again = {}                      # a minimal report without every column: nothing to recompute
        for k, v in again.items():
            if k in (pr.get("metrics") or {}) and not _same_number(pr["metrics"][k], v):
                problems.append(f"metric {k} = {pr['metrics'][k]} but its rows give {v}")

    # 6. relabelling an item out of a slice hides its regression from the slice gate
    def tags(rep: dict) -> dict:
        out: dict = {}
        for r in rep.get("rows") or []:
            out.setdefault(r.get("item_id"), set()).add(tuple(sorted(r.get("slices") or [])))
        return out
    mine, theirs = tags(pr), tags(base)
    for item, t in sorted(mine.items(), key=str):
        if len(t) > 1:
            problems.append(f"item {item} carries different slice tags on different rows")
        elif item in theirs and t != theirs[item]:
            problems.append(f"item {item} slice tags {sorted(next(iter(t)))} differ from the baseline's {sorted(next(iter(theirs[item])))}")

    # 7. ratchet: on the same eval-set version a threshold may only get stricter
    if base_spec is not None and base_spec.get("eval_set_version") == spec.get("eval_set_version"):
        problems += _ratchet(spec, base_spec)
    return problems


def _same_number(a, b) -> bool:
    if a is None or b is None:
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= 1e-9
    return a == b


def _looser(new: dict, old: dict, what: str) -> list[str]:
    """Problems when `new` (threshold + flags of one metric or slice) is laxer than `old`."""
    out = []
    nt, ot = new.get("threshold", new), old.get("threshold", old)
    if "max" in ot and ("max" not in nt or nt["max"] > ot["max"]):
        out.append(f"{what}: max {ot['max']} -> {nt.get('max')} (looser)")
    if "min" in ot and ("min" not in nt or nt["min"] < ot["min"]):
        out.append(f"{what}: min {ot['min']} -> {nt.get('min')} (looser)")
    if "max_increase" in ot and ("max_increase" not in nt or nt["max_increase"] > ot["max_increase"]):
        out.append(f"{what}: max_increase {ot['max_increase']} -> {nt.get('max_increase')} (looser)")
    if ot.get("no_significant_drop") and not nt.get("no_significant_drop"):
        out.append(f"{what}: no_significant_drop dropped")
    if old.get("blocking") and not new.get("blocking"):
        out.append(f"{what}: blocking -> non-blocking")
    return out


def _ratchet(spec: dict, base_spec: dict) -> list[str]:
    out: list[str] = []
    have = {m["id"]: m for m in spec.get("metrics", [])}
    for m in base_spec.get("metrics", []):
        if m["id"] not in have:
            out.append(f"metric {m['id']} disappeared from the spec")
        else:
            out += _looser(have[m["id"]], m, f"metric {m['id']}")
    have_s = {s["name"]: s for s in spec.get("slices") or []}
    for s in base_spec.get("slices") or []:
        if s["name"] not in have_s:
            out.append(f"slice {s['name']} disappeared from the spec")
        else:
            if have_s[s["name"]].get("metric") != s.get("metric"):
                out.append(f"slice {s['name']}: metric {s.get('metric')} -> {have_s[s['name']].get('metric')}")
            out += _looser(have_s[s["name"]], s, f"slice {s['name']}")
    # the statistics that decide "significant" must not be shopped either
    nb, ob = spec.get("bootstrap", {}), base_spec.get("bootstrap", {})
    for key in ("rng", "n_resamples", "confidence"):
        if key in ob and nb.get(key) != ob[key]:
            out.append(f"bootstrap {key}: {ob[key]} -> {nb.get(key)}")
    if set(base_spec.get("seeds") or []) - set(spec.get("seeds") or []):
        out.append(f"spec seeds {base_spec.get('seeds')} -> {spec.get('seeds')} (seeds removed)")
    return out


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked: list[str] = []
    lines: list[str] = []
    bs = spec.get("bootstrap", {})
    for sl in spec.get("slices") or []:
        name, metric = sl["name"], sl["metric"]
        ident = f"slice:{name}/{metric}"
        a = per_item(pr, metric, slice_name=name)
        b = per_item(base, metric, slice_name=name)
        th = {k: sl[k] for k in ("min", "no_significant_drop") if k in sl}
        value, verdict, note = None, "ok", ""
        if not a:
            verdict = "missing"           # no rows carry this slice tag: the slice cannot be judged
        else:
            value = round(sum(a.values()) / len(a), 4)
            if "min" in sl and value < sl["min"]:
                verdict = "fail"
            keys = sorted(set(a) & set(b))
            if sl.get("no_significant_drop") and len(keys) >= 2:
                d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                                   n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
                note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0:
                    verdict = "fail"
        if verdict != "ok" and sl.get("blocking"):
            blocked.append(ident)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if sl.get("blocking") else "warn")
        if verdict == "missing" and not sl.get("blocking"):
            label = "warn"
        lines.append(f"  {ident:<22} {value!s:<8} {json.dumps(th):<40} {note:<28} {label}")
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
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
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
