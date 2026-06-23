"""evaluate.compute_metrics — pure metric math, no data/LLM (no tokens).

Positive class = escalate (label Report). Definitions per ADR-0004:
  accuracyVsLabels       = share of alerts where recommendation == label
  falsePositiveReduction = of alerts recommended Dismiss, share truly benign
                           (label Dismiss) = TN / (TN + FN)
  recall (catch-rate)    = TP / (TP + FN)   — true Reports the copilot escalates
  precision (escalate)   = TP / (TP + FP)
  specificity            = TN / (TN + FP)
  baselineAccuracy       = always-dismiss accuracy = share of actuals = dismiss
                           (the "accuracy is a trap" reference point)
"""

from eval.evaluate import compute_metrics, drop_error_predictions
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


# A fixed worked example exercised across the classification metrics:
#   esc/esc=TP, esc/dis=FP, dis/esc=FN, dis/dis=TN  ->  TP1 FP2 FN1 TN2 (n=6)
_PREDS = ["escalate", "escalate", "dismiss", "dismiss", "escalate", "dismiss"]
_ACTUALS = ["escalate", "dismiss", "escalate", "dismiss", "dismiss", "dismiss"]


def test_confusion_matrix_counts():
    m = compute_metrics(_PREDS, _ACTUALS)
    assert m["confusionMatrix"] == {"tp": 1, "fp": 2, "fn": 1, "tn": 2}
    Metrics.model_validate(m)  # the widened wire contract still holds


def test_recall_precision_specificity():
    m = compute_metrics(_PREDS, _ACTUALS)
    assert m["recall"] == round(1 / 2, 4)
    assert m["precision"] == round(1 / 3, 4)
    assert m["specificity"] == round(2 / 4, 4)


def test_baseline_accuracy_is_always_dismiss_rate():
    # 4 of 6 actuals are Dismiss → a do-nothing model scores 4/6 on accuracy.
    m = compute_metrics(_PREDS, _ACTUALS)
    assert m["baselineAccuracy"] == round(4 / 6, 4)


def test_classification_rates_never_divide_by_zero():
    # all predicted+actual dismiss: no positives, no escalations → rates are 0.0
    m = compute_metrics(["dismiss", "dismiss"], ["dismiss", "dismiss"])
    assert m["recall"] == 0.0
    assert m["precision"] == 0.0
    assert m["specificity"] == 1.0  # every actual-dismiss correctly not-escalated
    assert m["baselineAccuracy"] == 1.0


def test_drop_error_predictions_excludes_failed_calls():
    # An "error" (failed LLM call) is missing data — excluded, not scored as a dismiss.
    preds = ["escalate", "error", "dismiss", "error"]
    actuals = ["escalate", "escalate", "dismiss", "dismiss"]
    kept_p, kept_a, n_excluded = drop_error_predictions(preds, actuals)
    assert kept_p == ["escalate", "dismiss"]
    assert kept_a == ["escalate", "dismiss"]
    assert n_excluded == 2


def test_dropping_errors_does_not_manufacture_false_negatives():
    # Old bug: the errored actual-escalate row would have been scored dismiss => a FN,
    # tanking recall. Excluding it keeps recall honest (here: perfect on what was scored).
    preds = ["escalate", "error"]
    actuals = ["escalate", "escalate"]
    kept_p, kept_a, _ = drop_error_predictions(preds, actuals)
    m = compute_metrics(kept_p, kept_a)
    assert m["recall"] == 1.0  # not 0.5 — the failed call isn't a false negative
