"""Leakage-safe NSL-KDD preprocessing for SageMaker Processing or local checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler, OneHotEncoder

SEED = 42
CATEGORICAL_COLS = ["protocol_type", "service", "flag"]
NSL_KDD_COLUMNS = [
    "duration", "protocol_type", "service", "flag", "src_bytes", "dst_bytes",
    "land", "wrong_fragment", "urgent", "hot", "num_failed_logins",
    "logged_in", "num_compromised", "root_shell", "su_attempted", "num_root",
    "num_file_creations", "num_shells", "num_access_files", "num_outbound_cmds",
    "is_host_login", "is_guest_login", "count", "srv_count", "serror_rate",
    "srv_serror_rate", "rerror_rate", "srv_rerror_rate", "same_srv_rate",
    "diff_srv_rate", "srv_diff_host_rate", "dst_host_count", "dst_host_srv_count",
    "dst_host_same_srv_rate", "dst_host_diff_srv_rate",
    "dst_host_same_src_port_rate", "dst_host_srv_diff_host_rate",
    "dst_host_serror_rate", "dst_host_srv_serror_rate", "dst_host_rerror_rate",
    "dst_host_srv_rerror_rate", "label",
]
NUMERIC_COLS = [c for c in NSL_KDD_COLUMNS if c not in CATEGORICAL_COLS + ["label"]]


def load_split(path: Path) -> tuple[pd.DataFrame, np.ndarray]:
    frame = pd.read_csv(path, header=None, names=NSL_KDD_COLUMNS + ["difficulty"])
    if len(frame.columns) != 43 or frame["label"].isna().any():
        raise ValueError(f"Unexpected NSL-KDD schema: {path}")
    labels = (frame["label"].str.strip().str.lower() != "normal").astype(np.int8).to_numpy()
    features = frame[NUMERIC_COLS + CATEGORICAL_COLS].copy()
    for column in NUMERIC_COLS:
        features[column] = pd.to_numeric(features[column], errors="raise")
    for column in CATEGORICAL_COLS:
        features[column] = features[column].astype(str)
    return features, labels


def transform(
    features: pd.DataFrame,
    scaler: MinMaxScaler,
    encoder: OneHotEncoder,
    selected_indices: np.ndarray,
) -> np.ndarray:
    numeric = scaler.transform(features[NUMERIC_COLS]).astype(np.float32)
    categorical = encoder.transform(features[CATEGORICAL_COLS]).astype(np.float32)
    return np.concatenate([numeric, categorical], axis=1)[:, selected_indices]


def save_split(path: Path, x: np.ndarray, y: np.ndarray) -> None:
    path.mkdir(parents=True, exist_ok=True)
    np.save(path / "X.npy", x)
    np.save(path / "y.npy", y)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=Path("/opt/ml/processing/input"))
    parser.add_argument("--output-dir", type=Path, default=Path("/opt/ml/processing/output"))
    parser.add_argument("--ordered-split", action="store_true",
                        help="Preserve NSL-KDD file order for the LSTM sequence experiment")
    args = parser.parse_args()

    train_features, train_labels = load_split(args.input_dir / "KDDTrain+.txt")
    test_features, test_labels = load_split(args.input_dir / "KDDTest+.txt")
    if args.ordered_split:
        cutoff = int(len(train_labels) * 0.8)
        x_train_raw, x_val_raw = train_features.iloc[:cutoff], train_features.iloc[cutoff:]
        y_train, y_val = train_labels[:cutoff], train_labels[cutoff:]
        split_strategy = "ordered 80/20 by file row from KDDTrain+; official KDDTest+ held out"
    else:
        x_train_raw, x_val_raw, y_train, y_val = train_test_split(
            train_features, train_labels, test_size=0.2, random_state=SEED, stratify=train_labels
        )
        split_strategy = "stratified 80/20 from KDDTrain+; official KDDTest+ held out"

    scaler = MinMaxScaler().fit(x_train_raw[NUMERIC_COLS])
    encoder = OneHotEncoder(handle_unknown="ignore", sparse_output=False, dtype=np.float32).fit(
        x_train_raw[CATEGORICAL_COLS]
    )
    all_names = NUMERIC_COLS + list(encoder.get_feature_names_out(CATEGORICAL_COLS))
    x_train_all = np.concatenate(
        [
            scaler.transform(x_train_raw[NUMERIC_COLS]).astype(np.float32),
            encoder.transform(x_train_raw[CATEGORICAL_COLS]).astype(np.float32),
        ],
        axis=1,
    )

    selector = RandomForestClassifier(n_estimators=80, max_depth=15, n_jobs=-1, random_state=SEED)
    selector.fit(x_train_all, y_train)
    selected_indices = np.sort(np.argsort(selector.feature_importances_)[-25:])
    x_train = x_train_all[:, selected_indices]
    x_val = transform(x_val_raw, scaler, encoder, selected_indices)
    x_test = transform(test_features, scaler, encoder, selected_indices)

    save_split(args.output_dir / "train", x_train, y_train)
    save_split(args.output_dir / "validation", x_val, y_val)
    save_split(args.output_dir / "test", x_test, test_labels)
    preprocessor_dir = args.output_dir / "preprocessor"
    preprocessor_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "scaler": scaler,
            "encoder": encoder,
            "selected_indices": selected_indices,
            "numeric_cols": NUMERIC_COLS,
            "categorical_cols": CATEGORICAL_COLS,
            "all_feature_names": all_names,
            "selected_feature_names": [all_names[i] for i in selected_indices],
            "dataset_id": "nsl-kdd",
            "dataset_version": "v1",
            "seed": SEED,
        },
        preprocessor_dir / "preprocessor.joblib",
    )
    report = {
        "dataset_id": "nsl-kdd",
        "dataset_version": "v1",
        "split_strategy": split_strategy,
        "train_rows": len(y_train),
        "validation_rows": len(y_val),
        "test_rows": len(test_labels),
        "feature_count": x_train.shape[1],
        "selected_features": [all_names[i] for i in selected_indices],
    }
    (preprocessor_dir / "split_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "selected_features"}))


if __name__ == "__main__":
    main()
