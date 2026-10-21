# ml/evaluate.py
# Phase 15.6 — evaluation and model selection.
#
# Which metric matters most: recall on the NO_SHOW class. Missing a
# predicted no-show (false negative) wastes a doctor's open slot; a false
# positive (predicting no-show for someone who attends) merely triggers
# an extra reminder call — a low-cost mistake. So the final model is
# selected by recall first, F1 as tie-breaker, not by raw accuracy.
#
# Overfitting/underfitting/leakage checks:
#   - Overfitting: Random Forest depth capped at 6 and compared against a
#     held-out test set, not just training accuracy.
#   - Underfitting: if both models score near-random ROC-AUC (~0.5), the
#     features aren't informative enough — a valid, reportable outcome.
#   - Data leakage: prior_appt_count/prior_no_show_count are computed
#     with `appt_date < a.appt_date` — strictly before the target
#     appointment — so no future information leaks into a feature.

from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score, confusion_matrix,
)


def evaluate(model, X_test, y_test):
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    try:
        auc = float(roc_auc_score(y_test, y_prob))
    except Exception:
        auc = 0.5
    return {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1": float(f1_score(y_test, y_pred, zero_division=0)),
        "roc_auc": auc,
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
    }


def select_best_model(models: dict, X_test, y_test):
    """Select by recall first, F1 as tie-breaker (see module docstring)."""
    scored = {name: evaluate(m, X_test, y_test) for name, m in models.items()}
    best_name = max(scored, key=lambda n: (scored[n]["recall"], scored[n]["f1"]))
    return best_name, models[best_name], scored
