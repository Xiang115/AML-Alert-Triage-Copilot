import pandas as pd
import pytest

from synthaml_loader import aggregate_features, stratified_split


def _labels(n_report=20, n_dismiss=80):
    rows = [{"AlertID": i, "Outcome": "Report"} for i in range(n_report)]
    rows += [{"AlertID": 1000 + i, "Outcome": "Dismiss"} for i in range(n_dismiss)]
    return pd.DataFrame(rows)


def _txns():
    return pd.DataFrame(
        [
            # AlertID 100: 3 txns over 4 days, mixed direction/type
            {"AlertID": 100, "Timestamp": "2026-06-01 09:00:00", "Entry": "Credit", "Type": "Wire", "Size": 1.0},
            {"AlertID": 100, "Timestamp": "2026-06-01 10:00:00", "Entry": "Debit", "Type": "Wire", "Size": 0.5},
            {"AlertID": 100, "Timestamp": "2026-06-05 09:00:00", "Entry": "Credit", "Type": "Cash", "Size": 2.0},
            # AlertID 200: single txn (edge case)
            {"AlertID": 200, "Timestamp": "2026-06-02 12:00:00", "Entry": "Debit", "Type": "Card", "Size": -1.0},
        ]
    )


def test_aggregate_features_one_row_per_alert():
    feats = aggregate_features(_txns())
    assert set(feats.index) == {100, 200}


def test_aggregate_features_volume_and_channel():
    f = aggregate_features(_txns()).loc[100]
    assert f["txnCount"] == 3
    assert f["creditCount"] == 2
    assert f["debitCount"] == 1
    assert f["cashFrac"] == pytest.approx(1 / 3)
    assert f["wireFrac"] == pytest.approx(2 / 3)
    assert f["cardFrac"] == 0.0
    assert f["intlFrac"] == 0.0


def test_aggregate_features_temporal_and_size():
    f = aggregate_features(_txns()).loc[100]
    assert f["spanDays"] == pytest.approx(4.0)
    assert f["maxDormancyGapDays"] == pytest.approx(3 + 23 / 24, abs=1e-3)
    assert f["burstFrac"] == pytest.approx(2 / 3)  # 2 of 3 txns on 1 June
    assert f["sizeMean"] == pytest.approx((1.0 + 0.5 + 2.0) / 3)
    assert f["sizeMax"] == pytest.approx(2.0)
    assert f["netFlow"] == pytest.approx(2.5)  # +1.0 - 0.5 + 2.0


def test_aggregate_features_single_txn_edges():
    f = aggregate_features(_txns()).loc[200]
    assert f["txnCount"] == 1
    assert f["spanDays"] == 0.0
    assert f["maxDormancyGapDays"] == 0.0
    assert f["burstFrac"] == 1.0
    assert f["sizeStd"] == 0.0  # single value -> 0, not NaN


def test_split_sizes_disjoint_and_cover():
    working, holdout = stratified_split(_labels(), holdout_frac=0.8, seed=42)
    assert len(holdout) == 80
    assert len(working) == 20
    assert set(working).isdisjoint(holdout)
    assert set(working) | set(holdout) == set(_labels()["AlertID"])


def test_split_preserves_report_ratio():
    labels = _labels()
    working, holdout = stratified_split(labels, holdout_frac=0.8, seed=42)
    reported = set(labels[labels["Outcome"] == "Report"]["AlertID"])
    assert len(set(holdout) & reported) == 16  # 80% of 20
    assert len(set(working) & reported) == 4


def test_split_is_deterministic_by_seed():
    a_work, a_hold = stratified_split(_labels(), 0.8, 7)
    b_work, b_hold = stratified_split(_labels(), 0.8, 7)
    assert list(a_hold) == list(b_hold)
    c_work, c_hold = stratified_split(_labels(), 0.8, 99)
    assert list(c_hold) != list(b_hold)  # different seed -> different split
