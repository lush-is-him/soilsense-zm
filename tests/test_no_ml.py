"""Spec 0 rule 6, 10: no machine learning anywhere in the product."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRODUCT_DIRS = ["backend", "engine", "dashboard", "scripts", "bridge", "firmware"]
ML = re.compile(r"\b(sklearn|scikit-learn|tensorflow|torch|keras|joblib|xgboost|lightgbm)\b|model\.fit|\.pkl\b")


def test_no_ml_code_or_dependencies():
    hits = []
    for folder in PRODUCT_DIRS:
        for path in (ROOT / folder).rglob("*"):
            if path.is_file() and path.suffix in {".py", ".js", ".html", ".txt", ".ino", ".cpp", ".h"}:
                for n, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
                    if ML.search(line):
                        hits.append(f"{path.relative_to(ROOT)}:{n}")
    assert not hits, f"ML references found: {hits}"


def test_no_model_files():
    assert not list(ROOT.glob("**/*.pkl"))
