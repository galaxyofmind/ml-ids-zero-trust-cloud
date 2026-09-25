"""SageMaker Scikit-learn inference contract for one raw NSL-KDD flow."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd


def model_fn(model_dir: str) -> dict:
    root = Path(model_dir)
    return {
        "model": joblib.load(root / "model.pkl"),
        "preprocessor": joblib.load(root / "preprocessor.joblib"),
    }


def input_fn(request_body: str | bytes, content_type: str) -> dict:
    if content_type != "application/json":
        raise ValueError("Content-Type must be application/json")
    payload = json.loads(request_body)
    if not isinstance(payload, dict) or not isinstance(payload.get("record"), dict):
        raise ValueError("Expected JSON object with a record object")
    return payload["record"]


def predict_fn(record: dict, bundle: dict) -> dict:
    prep = bundle["preprocessor"]
    required = set(prep["numeric_cols"] + prep["categorical_cols"])
    if set(record) != required:
        raise ValueError(f"Record requires exactly {len(required)} raw NSL-KDD features")
    frame = pd.DataFrame([record])
    for column in prep["numeric_cols"]:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    numeric = prep["scaler"].transform(frame[prep["numeric_cols"]]).astype(np.float32)
    categorical = prep["encoder"].transform(frame[prep["categorical_cols"]]).astype(np.float32)
    features = np.concatenate([numeric, categorical], axis=1)[:, prep["selected_indices"]]
    if not np.isfinite(features).all():
        raise ValueError("Record contains non-finite numeric values")
    prediction = int(bundle["model"].predict(features)[0])
    probability = float(bundle["model"].predict_proba(features)[0, 1])
    return {
        "prediction": prediction,
        "attack_probability": probability,
        "dataset_id": prep["dataset_id"],
        "dataset_version": prep["dataset_version"],
    }


def output_fn(prediction: dict, accept: str) -> str:
    if accept not in ("application/json", "*/*"):
        raise ValueError("Accept must be application/json")
    return json.dumps(prediction)
