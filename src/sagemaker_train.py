"""Train one upstream IDS model in a SageMaker Scikit-learn training job."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split

from models import RandomForestIDS, SVMIDS, XGBoostIDS


MODELS = {
    "random_forest": RandomForestIDS,
    "svm": SVMIDS,
    "xgboost": XGBoostIDS,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-name", choices=MODELS, default="random_forest")
    parser.add_argument("--max-train-rows", type=int, default=30000)
    parser.add_argument("--train-dir", type=Path, default=Path(os.environ.get("SM_CHANNEL_TRAIN", "data/aws-processed/train")))
    parser.add_argument("--validation-dir", type=Path, default=Path(os.environ.get("SM_CHANNEL_VALIDATION", "data/aws-processed/validation")))
    parser.add_argument("--preprocessor-dir", type=Path, default=Path(os.environ.get("SM_CHANNEL_PREPROCESSOR", "data/aws-processed/preprocessor")))
    parser.add_argument("--model-dir", type=Path, default=Path(os.environ.get("SM_MODEL_DIR", "results/models/aws")))
    parser.add_argument("--inference-script", type=Path, default=None)
    args = parser.parse_args()

    x_train = np.load(args.train_dir / "X.npy")
    y_train = np.load(args.train_dir / "y.npy")
    x_val = np.load(args.validation_dir / "X.npy")
    y_val = np.load(args.validation_dir / "y.npy")
    if args.max_train_rows < 100 or args.max_train_rows > len(y_train):
        raise ValueError("max-train-rows must be between 100 and the train split size")
    if args.max_train_rows < len(y_train):
        selected, _ = train_test_split(
            np.arange(len(y_train)),
            train_size=args.max_train_rows,
            random_state=42,
            stratify=y_train,
        )
        x_train, y_train = x_train[selected], y_train[selected]

    if args.model_name == "xgboost":
        try:
            import xgboost
            installed = xgboost.__version__
        except ImportError:
            installed = None
        if installed != "2.1.4":
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--no-cache-dir", "xgboost-cpu==2.1.4"])

    model = MODELS[args.model_name]()
    model.train(x_train, y_train)
    predictions = model.predict(x_val)
    metrics = {
        "model_name": args.model_name,
        "dataset_id": "nsl-kdd",
        "dataset_version": "v1",
        "train_rows_used": int(len(y_train)),
        "validation_rows": int(len(y_val)),
        "validation_accuracy": float(accuracy_score(y_val, predictions)),
        "validation_f1": float(f1_score(y_val, predictions, zero_division=0)),
        "training_time_seconds": float(model.training_time),
        "seed": 42,
    }
    args.model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model.model, args.model_dir / "model.pkl")
    shutil.copy2(args.preprocessor_dir / "preprocessor.joblib", args.model_dir / "preprocessor.joblib")
    (args.model_dir / "validation_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    if args.inference_script:
        code_dir = args.model_dir / "code"
        code_dir.mkdir(exist_ok=True)
        shutil.copy2(args.inference_script, code_dir / "ids_inference.py")
        with tarfile.open(args.model_dir / "model.tar.gz", "w:gz") as archive:
            for file_name in ("model.pkl", "preprocessor.joblib", "validation_metrics.json"):
                archive.add(args.model_dir / file_name, arcname=file_name)
            archive.add(code_dir / "ids_inference.py", arcname="code/ids_inference.py")
    print(json.dumps(metrics))


if __name__ == "__main__":
    main()
