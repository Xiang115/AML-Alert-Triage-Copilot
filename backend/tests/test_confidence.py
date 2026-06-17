import pytest

from agents.confidence import compute_confidence


def test_escalate_confidence_is_indicator_coverage():
    assert compute_confidence(4, 5, "escalate", verifier_flagged=False) == pytest.approx(0.8)


def test_dismiss_confidence_is_inverse_coverage():
    # a clean dismiss (no indicators fired) is HIGH confidence
    assert compute_confidence(0, 5, "dismiss", verifier_flagged=False) == pytest.approx(1.0)
    # a dismiss that nonetheless fired every indicator is LOW confidence
    assert compute_confidence(5, 5, "dismiss", verifier_flagged=False) == pytest.approx(0.0)


def test_verifier_flag_caps_below_review_threshold():
    capped = compute_confidence(5, 5, "escalate", verifier_flagged=True)
    assert capped < 0.6
    assert capped == pytest.approx(0.59)


def test_zero_indicator_card_edge():
    assert compute_confidence(0, 0, "escalate", verifier_flagged=False) == pytest.approx(0.0)
    assert compute_confidence(0, 0, "dismiss", verifier_flagged=False) == pytest.approx(1.0)
