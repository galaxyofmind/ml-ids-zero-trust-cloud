"""Train the upstream two-layer LSTM in SageMaker Processing and evaluate KDDTest+.

NSL-KDD has no trustworthy event timestamp. Non-overlapping windows use file row
order as a demo proxy, with the last flow in each window as its target label.
This is deliberately different from the upstream first-flow label rule.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

import numpy as np


def make_windows(x: np.ndarray, y: np.ndarray, timesteps: int) -> tuple[np.ndarray, np.ndarray, int]:
    if timesteps < 2:
        raise ValueError("timesteps must be at least 2")
    if len(x) != len(y):
        raise ValueError("feature and label row counts differ")
    used = (len(y) // timesteps) * timesteps
    if not used:
        raise ValueError("not enough rows for a sequence")
    return x[:used].reshape(-1, timesteps, x.shape[1]), y[:used].reshape(-1, timesteps)[:, -1], used


def score(y: np.ndarray, predicted: np.ndarray) -> dict[str, float | dict[str, int]]:
    tn = int(np.sum((y == 0) & (predicted == 0)))
    fp = int(np.sum((y == 0) & (predicted == 1)))
    fn = int(np.sum((y == 1) & (predicted == 0)))
    tp = int(np.sum((y == 1) & (predicted == 1)))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "accuracy": (tp + tn) / len(y),
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "fpr": fp / (fp + tn) if fp + tn else 0.0,
        "confusion_matrix": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-dir", type=Path, default=Path("/opt/ml/processing/train"))
    parser.add_argument("--validation-dir", type=Path, default=Path("/opt/ml/processing/validation"))
    parser.add_argument("--test-dir", type=Path, default=Path("/opt/ml/processing/test"))
    parser.add_argument("--preprocessor-dir", type=Path, default=Path("/opt/ml/processing/preprocessor"))
    parser.add_argument("--model-dir", type=Path, default=Path("/opt/ml/processing/model"))
    parser.add_argument("--evaluation-dir", type=Path, default=Path("/opt/ml/processing/evaluation"))
    parser.add_argument("--max-train-flows", type=int, default=40000)
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--timesteps", type=int, default=20)
    args = parser.parse_args()

    if args.max_train_flows < args.timesteps * 100 or args.epochs < 1:
        raise ValueError("need at least 100 training windows and one epoch")
    x_train = np.load(args.train_dir / "X.npy")
    y_train = np.load(args.train_dir / "y.npy")
    x_val = np.load(args.validation_dir / "X.npy")
    y_val = np.load(args.validation_dir / "y.npy")
    x_test = np.load(args.test_dir / "X.npy")
    y_test = np.load(args.test_dir / "y.npy")
    train_limit = min(len(y_train), args.max_train_flows)
    train_x, train_y, train_used = make_windows(x_train[:train_limit], y_train[:train_limit], args.timesteps)
    val_x, val_y, val_used = make_windows(x_val, y_val, args.timesteps)
    test_x, test_y, test_used = make_windows(x_test, y_test, args.timesteps)

    # The TensorFlow DLC does not guarantee scikit-learn, which models.py imports.
    try:
        import sklearn  # noqa: F401
        import joblib  # noqa: F401
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--no-cache-dir",
                               "scikit-learn==1.4.2", "joblib==1.4.2"])

    import tensorflow as tf
    from models import LSTMIDS

    np.random.seed(42)
    tf.random.set_seed(42)
    tf.config.threading.set_inter_op_parallelism_threads(2)
    tf.config.threading.set_intra_op_parallelism_threads(2)
    model = LSTMIDS(n_classes=2, timesteps=args.timesteps)._build(n_features=train_x.shape[2])
    callbacks = [tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=3,
                                                  restore_best_weights=True)]
    start = time.monotonic()
    history = model.fit(train_x, train_y, validation_data=(val_x, val_y),
                        epochs=args.epochs, batch_size=256, callbacks=callbacks, verbose=2)
    training_seconds = time.monotonic() - start
    val_pred = (model.predict(val_x, verbose=0).reshape(-1) >= 0.5).astype(np.int8)
    test_pred = (model.predict(test_x, verbose=0).reshape(-1) >= 0.5).astype(np.int8)
    validation = score(val_y, val_pred)
    evaluation = {
        "model_name": "lstm",
        "dataset_id": "nsl-kdd",
        "dataset_version": "v1",
        "test_split": "official KDDTest+ file-order windows",
        "sequence_rule": "non-overlapping 20-row windows; target is the last flow label",
        "sequence_order_caveat": "NSL-KDD file order is not verified network time order",
        "train_flows_used": train_used,
        "train_sequences": len(train_y),
        "validation_flows_used": val_used,
        "validation_sequences": len(val_y),
        "validation_f1": validation["f1"],
        "test_flows_used": test_used,
        "test_sequences": len(test_y),
        "epochs_completed": len(history.history["loss"]),
        "training_time_seconds": training_seconds,
        "seed": 42,
        **score(test_y, test_pred),
    }
    args.model_dir.mkdir(parents=True, exist_ok=True)
    args.evaluation_dir.mkdir(parents=True, exist_ok=True)
    model.save(args.model_dir / "model.keras")
    model.export(args.model_dir / "1")
    shutil.copy2(args.preprocessor_dir / "preprocessor.joblib", args.model_dir / "preprocessor.joblib")
    (args.model_dir / "training_metadata.json").write_text(json.dumps(evaluation, indent=2), encoding="utf-8")
    (args.evaluation_dir / "evaluation.json").write_text(json.dumps(evaluation, indent=2), encoding="utf-8")
    with tarfile.open(args.model_dir / "model.tar.gz", "w:gz") as archive:
        for name in ("model.keras", "preprocessor.joblib", "training_metadata.json"):
            archive.add(args.model_dir / name, arcname=name)
        archive.add(args.model_dir / "1", arcname="1")
    print(json.dumps(evaluation))


if __name__ == "__main__":
    main()
