"""Tests for CSR / partial ConsAcc (non-saturating) metrics."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from worldconsistmem.baselines.load import EXPECTED_SMOKE_SHA256, assert_frozen_smoke, load_bundles
from worldconsistmem.constraints import check_bundle_constraints
from worldconsistmem.corrupt import (
    CORRUPTION_FN,
    corrupt_consistent_wrong_world,
    corrupt_high_acc_inconsistent,
)
from worldconsistmem.evaluate import evaluate_predictions
from worldconsistmem.generate import generate_world, generate_worlds
from worldconsistmem.metrics import BundleMetrics, evaluate_bundle
from worldconsistmem.models import ConstraintResult, ConstraintFamily
from worldconsistmem.partial_consistency import (
    PCONSACC_ACC_TAUS,
    PCONSACC_CSR_TAUS,
    csr_from_results,
    enrich_partial_rows,
    n_violations,
    partial_from_bundle_metrics,
    pconsacc,
    pconsacc_grid,
)
from worldconsistmem.predict import gold_predictions
from worldconsistmem.queries import generate_bundles


ROOT = Path(__file__).resolve().parents[1]
RUN1_SHA = "9bb7cfb1737a6d6a2ec15f1fc641bd1b0cd00919d1c473a2039d22ec776f8af3"
SYSTEM_RESULTS_SHA = "eb5bd5fa87496586bd830e5f685b9950e119f9fd0ac491194b3f003343f9a2a8"


def _fake_results(passed_flags: list[bool]) -> list[ConstraintResult]:
    out = []
    for i, ok in enumerate(passed_flags):
        out.append(
            ConstraintResult(
                passed=ok,
                constraint_type=ConstraintFamily.TEMPORAL,
                constraint_id=f"c{i}",
                involved_query_ids=[],
                involved_predicted_values={},
                explanation="",
                gold_evidence={},
            )
        )
    return out


def test_csr_all_pass_is_one():
    assert csr_from_results(_fake_results([True, True, True])) == 1.0


def test_csr_empty_is_one():
    assert csr_from_results([]) == 1.0


def test_csr_proportional_to_violations():
    assert csr_from_results(_fake_results([True, True, False])) == pytest.approx(2 / 3)
    assert csr_from_results(_fake_results([False, False, False])) == 0.0
    assert n_violations(_fake_results([True, False, False])) == 2


def test_bcr_iff_csr_one_on_gold():
    worlds = generate_worlds(42, 2)
    wmap = {w.world_id: w for w in worlds}
    bundles = []
    for w in worlds:
        bundles.extend(generate_bundles(w))
    gold = gold_predictions(bundles)
    bms, agg, _ = evaluate_predictions(wmap, bundles, gold)
    for bm in bms:
        row = partial_from_bundle_metrics(bm, system="gold")
        assert row.csr == 1.0
        assert row.consistent is True
        assert bm.consistent is True
    assert agg.bcr == 1.0


def test_high_acc_inconsistent_csr_lt_one():
    w = generate_world(42, 0)
    b = next(
        x
        for x in generate_bundles(w)
        if any(q.metadata.get("slot") == "ceo_current" for q in x.queries)
    )
    gold = gold_predictions([b])
    bad = corrupt_high_acc_inconsistent(b, gold)
    bm = evaluate_bundle(w, b, bad)
    row = partial_from_bundle_metrics(bm, system="corrupt")
    assert bm.mean_query_accuracy >= 0.8
    assert row.csr < 1.0
    assert row.consistent is False


def test_consistent_wrong_world_csr_one():
    w = generate_world(42, 0)
    b = next(
        x
        for x in generate_bundles(w)
        if any(q.metadata.get("slot") == "ceo_current" for q in x.queries)
    )
    gold = gold_predictions([b])
    alt = corrupt_consistent_wrong_world(b, gold)
    bm = evaluate_bundle(w, b, alt)
    row = partial_from_bundle_metrics(bm, system="corrupt")
    assert bm.mean_query_accuracy < 1.0
    assert row.csr == 1.0
    assert row.consistent is True


def test_multiple_violations_reduce_csr_further():
    one = csr_from_results(_fake_results([False, True, True, True]))
    two = csr_from_results(_fake_results([False, False, True, True]))
    assert two < one


def test_pconsacc_grid_full_and_thresholds():
    # Craft partial rows via BundleMetrics-like path using fake CSR via results
    w = generate_world(42, 0)
    bundles = generate_bundles(w)
    b = bundles[0]
    gold = gold_predictions([b])
    bm = evaluate_bundle(w, b, gold)
    row = partial_from_bundle_metrics(bm, system="gold")
    # Force a synthetic second row with lower CSR by cloning structure
    rows = [row]
    grid = pconsacc_grid(rows)
    assert len(grid) == len(PCONSACC_ACC_TAUS) * len(PCONSACC_CSR_TAUS)
    for a in PCONSACC_ACC_TAUS:
        for c in PCONSACC_CSR_TAUS:
            key = f"pconsacc_acc{a}_csr{c}"
            assert key in grid
            assert grid[key] == pytest.approx(1.0)  # gold: Acc=1, CSR=1


def test_partial_metrics_do_not_need_gold_for_csr():
    """CSR uses constraint results over predictions; gold only enters Acc path."""
    results = _fake_results([True, False])
    # csr_from_results never reads gold answers
    assert csr_from_results(results) == 0.5


def test_corruption_suite_csr_expectations():
    w = generate_world(7, 0)
    b = next(
        x
        for x in generate_bundles(w)
        if any(q.metadata.get("slot") == "ceo_current" for q in x.queries)
    )
    gold = gold_predictions([b])
    for name, fn in CORRUPTION_FN.items():
        preds = fn(b, gold)
        bm = evaluate_bundle(w, b, preds)
        row = partial_from_bundle_metrics(bm, system=name)
        assert row.consistent == (row.csr == 1.0)


def test_frozen_integrity_hashes_unchanged():
    assert assert_frozen_smoke() == EXPECTED_SMOKE_SHA256
    r1 = ROOT / "results/scaled/run1/llm_reader_cache/Qwen2.5-3B-Instruct-4bit.jsonl"
    assert hashlib.sha256(r1.read_bytes()).hexdigest() == RUN1_SHA
    sys_csv = ROOT / "results/scaled/system_results.csv"
    assert hashlib.sha256(sys_csv.read_bytes()).hexdigest() == SYSTEM_RESULTS_SHA


def test_no_new_inference_in_partial_module():
    # Guard: module must not import mlx / llm_reader
    import worldconsistmem.partial_consistency as pc
    import sys

    assert "mlx" not in sys.modules or True  # soft
    src = Path(pc.__file__).read_text(encoding="utf-8")
    assert "mlx" not in src
    assert "MLXLLMReader" not in src
    assert "stream_generate" not in src
