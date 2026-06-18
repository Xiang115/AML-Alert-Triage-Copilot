"""evaluate.compute_metrics — pure metric math, no data/LLM (no tokens).

Definitions per ADR-0004:
  accuracyVsLabels       = share of alerts where recommendation == label
  falsePositiveReduction = of alerts recommended Dismiss, share truly benign
                           (label Dismiss) = TN / (TN + FN)
"""

from eval.evaluate import compute_metrics
from schemas import Metrics


def test_all_correct_gives_perfect_accuracy():
    m = compute_metrics(["escalate", "dismiss"], ["escalate", "dismiss"])
    assert m["accuracyVsLabels"] == 1.0
    assert m["totalAlerts"] == 2
    Metrics.model_validate(m)  # conforms to the wire contract


def test_all_wrong_gives_zero_accuracy():
    m = compute_metrics(["escalate", "dismiss"], ["dismiss", "escalate"])
    assert m["accuracyVsLabels"] == 0.0


def test_false_positive_reduction_is_dismiss_precision():
    # predicted dismiss x3 → two truly benign, one was actually Report (a miss)
    preds = ["dismiss", "dismiss", "dismiss", "escalate"]
    actuals = ["dismiss", "dismiss", "escalate", "escalate"]
    m = compute_metrics(preds, actuals)
    assert m["falsePositiveReduction"] == round(2 / 3, 4)  # TN/(TN+FN), rounded


def test_no_dismissals_does_not_divide_by_zero():
    m = compute_metrics(["escalate", "escalate"], ["escalate", "dismiss"])
    assert m["falsePositiveReduction"] == 0.0


def test_time_numbers_pass_through():
    m = compute_metrics(["escalate"], ["escalate"], baseline_min=14.0, copilot_min=4.5)
    assert m["avgReviewTimeBaselineMin"] == 14.0
    assert m["avgReviewTimeWithCopilotMin"] == 4.5
