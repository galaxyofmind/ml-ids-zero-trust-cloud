"""Create comparable PSI reports for stable, synthetic shift, and KDDTest+ windows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np


def psi(reference: np.ndarray, current: np.ndarray) -> float:
    reference = np.asarray(reference, dtype=float)
    current = np.asarray(current, dtype=float)
    if not np.isfinite(reference).all() or not np.isfinite(current).all():
        raise ValueError("PSI inputs must be finite")
    unique = np.unique(reference)
    if len(unique) <= 10:
        categories = np.union1d(unique, np.unique(current))
        ref_counts = np.array([(reference == x).sum() for x in categories], dtype=float)
        cur_counts = np.array([(current == x).sum() for x in categories], dtype=float)
    else:
        edges = np.unique(np.quantile(reference, np.linspace(0, 1, 11)))
        if len(edges) < 2:
            return 0.0
        edges[0], edges[-1] = -np.inf, np.inf
        ref_counts = np.histogram(reference, bins=edges)[0].astype(float)
        cur_counts = np.histogram(current, bins=edges)[0].astype(float)
    ref_prop = (ref_counts + 1e-6) / (len(reference) + 1e-6 * len(ref_counts))
    cur_prop = (cur_counts + 1e-6) / (len(current) + 1e-6 * len(cur_counts))
    return float(np.sum((cur_prop - ref_prop) * np.log(cur_prop / ref_prop)))


def report(reference: np.ndarray, current: np.ndarray, feature_names: list[str], window: str) -> dict:
    features = [
        {"feature": name, "psi": round(psi(reference[:, i], current[:, i]), 6)}
        for i, name in enumerate(feature_names)
    ]
    features.sort(key=lambda item: item["psi"], reverse=True)
    drifted = sum(item["psi"] > 0.25 for item in features)
    return {
        "dataset_id": "nsl-kdd",
        "dataset_version": "v1",
        "window": window,
        "reference_rows": len(reference),
        "current_rows": len(current),
        "max_psi": features[0]["psi"],
        "critical_feature_count": drifted,
        "critical_feature_share": round(drifted / len(features), 4),
        "threshold": 0.25,
        "synthetic": window == "synthetic_shift",
        "features": features,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data/aws-processed"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/aws-processed/drift"))
    args = parser.parse_args()
    x_train = np.load(args.data_dir / "train/X.npy")
    x_test = np.load(args.data_dir / "test/X.npy")
    names = joblib.load(args.data_dir / "preprocessor/preprocessor.joblib")["selected_feature_names"]
    rng = np.random.default_rng(42)
    indices = rng.choice(len(x_train), size=10000, replace=False)
    reference, stable = x_train[indices[:5000]], x_train[indices[5000:]]
    shifted = stable.copy()
    shifted[:, 0] += 1.0
    windows = {
        "stable": stable,
        "synthetic_shift": shifted,
        "official_test": x_test,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, current in windows.items():
        result = report(reference, current, names, name)
        (args.output_dir / f"{name}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps({k: v for k, v in result.items() if k != "features"}))


if __name__ == "__main__":
    main()
