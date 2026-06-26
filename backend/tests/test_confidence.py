import pytest

from agents.confidence import compute_confidence


def test_escalate_confidence_is_indicator_coverage():
    assert compute_confidence(4, 5, "escalate", verifier_flagged=False) == pytest.approx(0.8)


def test_dismiss_confidence_is_inverse_coverage():
    # a clean dismiss (no indicators fired) is HIGH confidence
    assert compute_confidence(0, 5, "dismiss", verifier_flagged=False) == pytest.approx(1.0)
    # a dismiss that nonetheless fired every indicator is LOW confidence
    assert compute_confidence(5, 5, "dismiss", verifier_flagged=False) == pytest.approx(0.0)


def test_verifier_flag_caps_a_dismiss_below_review_threshold():
    # A flagged DISMISS is the call the Queue Agent could otherwise auto-clear, so the
    # flag pulls it below the review line — it can never auto-clear a contested benign call.
    capped = compute_confidence(0, 5, "dismiss", verifier_flagged=True)
    assert capped < 0.6
    assert capped == pytest.approx(0.59)


def test_verifier_flag_does_not_cap_an_escalate():
    # An escalate never auto-clears, so a flag does NOT depress its confidence — it keeps
    # its true coverage and the flag itself routes it to a human (the hero-case behaviour).
    assert compute_confidence(5, 5, "escalate", verifier_flagged=True) == pytest.approx(1.0)
    assert compute_confidence(3, 4, "escalate", verifier_flagged=True) == pytest.approx(0.75)


def test_zero_indicator_card_edge():
    assert compute_confidence(0, 0, "escalate", verifier_flagged=False) == pytest.approx(0.0)
    assert compute_confidence(0, 0, "dismiss", verifier_flagged=False) == pytest.approx(1.0)
