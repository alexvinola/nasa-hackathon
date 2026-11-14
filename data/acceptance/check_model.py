"""G2 acceptance check: the fatigue model and its metrics, as `make model` leaves them.

Run by `make check-G2` from `data/` after `make model`. Protected: it is not edited to make it pass.
It checks what goals/G2-fatigue-model.md "Done when" asks for, and nothing about how good the model is
beyond "better than chance": there is no F1 target to chase.

- data/out/metrics.json: macro F1, AUC, a 3-class confusion matrix, the score vs PVT correlation (a number,
  or null when DROZY is not available) and the subjects of each fold, with no subject in both train and test.
- data/fatigue_model.json: features, mean, std, coef, intercept and trainedOn, with consistent shapes.
- AUC > 0.5.
"""

import json
import math
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent
METRICS = DATA / "out" / "metrics.json"
MODEL = DATA / "fatigue_model.json"
CLASSES = 3

failures: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        failures.append(message)


def number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def load(path: Path) -> dict:
    if not path.exists():
        print(f"FAIL: {path.relative_to(DATA)} does not exist (run `make model`)")
        sys.exit(1)
    return json.loads(path.read_text(encoding="utf-8"))


metrics = load(METRICS)
model = load(MODEL)

# --- metrics.json -------------------------------------------------------------------------------------------
check(number(metrics.get("macro_f1")) and 0 <= metrics["macro_f1"] <= 1, "metrics.macro_f1 must be a number in [0, 1]")
check(number(metrics.get("auc")) and 0 <= metrics["auc"] <= 1, "metrics.auc must be a number in [0, 1]")
check(number(metrics.get("auc")) and metrics["auc"] > 0.5, f"metrics.auc must beat chance (> 0.5), got {metrics.get('auc')}")

labels = metrics.get("labels")
check(isinstance(labels, list) and len(labels) == CLASSES, f"metrics.labels must name the {CLASSES} classes")

matrix = metrics.get("confusion_matrix")
square = (
    isinstance(matrix, list)
    and len(matrix) == CLASSES
    and all(isinstance(row, list) and len(row) == CLASSES for row in matrix)
)
check(square, f"metrics.confusion_matrix must be {CLASSES}x{CLASSES}")
if square:
    cells = [cell for row in matrix for cell in row]
    check(all(isinstance(c, int) and not isinstance(c, bool) and c >= 0 for c in cells), "confusion_matrix cells must be counts")
    check(sum(cells) > 0, "confusion_matrix is empty: nothing was evaluated")

check("pvt_correlation" in metrics, "metrics.pvt_correlation must be present (null when DROZY is not available)")
check(metrics.get("pvt_correlation") is None or number(metrics["pvt_correlation"]), "metrics.pvt_correlation must be a number or null")

folds = metrics.get("folds")
check(isinstance(folds, list) and len(folds) >= 2, "metrics.folds must list at least 2 folds")
if isinstance(folds, list):
    tested: list[str] = []
    for i, fold in enumerate(folds):
        train = fold.get("train_subjects") if isinstance(fold, dict) else None
        test = fold.get("test_subjects") if isinstance(fold, dict) else None
        if not (isinstance(train, list) and isinstance(test, list) and train and test):
            check(False, f"fold {i}: train_subjects and test_subjects must be non-empty lists")
            continue
        overlap = set(train) & set(test)
        check(not overlap, f"fold {i}: subjects in both train and test: {sorted(overlap)}")
        tested += test
    check(len(tested) == len(set(tested)), "a subject is tested in more than one fold")

# --- fatigue_model.json -------------------------------------------------------------------------------------
features = model.get("features")
check(
    isinstance(features, list) and features and all(isinstance(f, str) and f for f in features) and len(set(features)) == len(features),
    "model.features must be a non-empty list of distinct names",
)
n = len(features) if isinstance(features, list) else 0


def vector(name: str, length: int) -> list | None:
    value = model.get(name)
    ok = isinstance(value, list) and len(value) == length and all(number(v) for v in value)
    check(ok, f"model.{name} must be {length} numbers")
    return value if ok else None


vector("mean", n)
std = vector("std", n)
if std is not None:
    check(all(s > 0 for s in std), "model.std must be positive (a zero std cannot standardise a feature)")

coef = model.get("coef")
rows = CLASSES if isinstance(coef, list) and len(coef) == CLASSES else 1
coef_ok = isinstance(coef, list) and (
    (len(coef) == CLASSES and all(isinstance(r, list) and len(r) == n and all(number(v) for v in r) for r in coef))
    or (len(coef) == 1 and isinstance(coef[0], list) and len(coef[0]) == n and all(number(v) for v in coef[0]))
)
check(coef_ok, f"model.coef must be {CLASSES} rows (or 1 row) of {n} numbers")
vector("intercept", rows)

check(isinstance(model.get("trainedOn"), str) and model["trainedOn"].strip() != "", "model.trainedOn must say what it was trained on")

# --- result -------------------------------------------------------------------------------------------------
if failures:
    for message in failures:
        print(f"FAIL: {message}")
    sys.exit(1)
print(
    f"G2 ok: macro F1 {metrics['macro_f1']:.3f}, AUC {metrics['auc']:.3f}, {len(folds)} folds, "
    f"{n} features ({', '.join(features)}), trained on {model['trainedOn']}"
)
