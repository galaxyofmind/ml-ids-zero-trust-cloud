"""Evaluate a SageMaker model artifact on the untouched official KDDTest+ split."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tarfile
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-tar", type=Path, default=Path("/opt/ml/processing/model/model.tar.gz"))
    parser.add_argument("--test-dir", type=Path, default=Path("/opt/ml/processing/test"))
    parser.add_argument("--output-dir", type=Path, default=Path("/opt/ml/processing/evaluation"))
    args = parser.parse_args()

    with tarfile.open(args.model_tar, "r:gz") as archive:
        metrics_file = archive.extractfile("validation_metrics.json")
        if metrics_file is None:
            raise ValueError("validation_metrics.json missing from model artifact")
        validation = json.load(metrics_file)
        if validation["model_name"] == "xgboost":
            try:
                import xgboost
                installed = xgboost.__version__
            except ImportError:
                installed = None
            if installed != "2.1.4":
                subprocess.check_call([sys.executable, "-m", "pip", "install", "--no-cache-dir", "xgboost-cpu==2.1.4"])
        model_file = archive.extractfile("model.pkl")
        if model_file is None:
            raise ValueError("model.pkl missing from model artifact")
        model = joblib.load(model_file)

    x_test = np.load(args.test_dir / "X.npy")
    y_test = np.load(args.test_dir / "y.npy")
    predicted = model.predict(x_test)
    matrix = confusion_matrix(y_test, predicted, labels=[0, 1])
    tn, fp, fn, tp = matrix.ravel()
    metrics = {
        "model_name": validation["model_name"],
        "dataset_id": "nsl-kdd",
        "dataset_version": "v1",
        "test_split": "official KDDTest+",
        "train_rows_used": validation["train_rows_used"],
        "test_rows": int(len(y_test)),
        "accuracy": float(accuracy_score(y_test, predicted)),
        "precision": float(precision_score(y_test, predicted, zero_division=0)),
        "recall": float(recall_score(y_test, predicted, zero_division=0)),
        "f1": float(f1_score(y_test, predicted, zero_division=0)),
        "fpr": float(fp / (fp + tn)) if fp + tn else 0.0,
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "evaluation.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics))


if __name__ == "__main__":
    main()
