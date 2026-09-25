"""
models.py
=========
ML Model Implementations for ML-IDS Zero Trust Cloud Research

Paper: "Machine Learning-Based Intrusion Detection for Cloud Network Security:
        A Zero Trust Architecture Approach"
Author: Dingaan Mahlatse Machethe
Institution: EC-Council University — ECCU500: Managing Secure Network Systems

Five model classes — each with train() / predict() / predict_proba() interface:
  1. RandomForestIDS  — 200 trees, Gini, no max depth, n_jobs=-1, random_state=42
  2. SVMIDS           — RBF kernel, C=10, gamma=0.001, probability=True
  3. LSTMIDS          — 2-layer 128 units, dropout=0.3, Adam, 50 epochs, patience=5
                        Input: sequences of 20 network flows; softmax output
  4. AutoencoderIDS   — 41→32→16→8 encoder, symmetric decoder, 95th-pct threshold
                        Trained exclusively on normal traffic (label=0)
  5. XGBoostIDS       — 500 est, lr=0.05, depth=6, subsample=0.8, colsample_bytree=0.8

10-fold stratified cross-validation available for RandomForestIDS and XGBoostIDS.
"""

from __future__ import annotations

import os
import time
import logging
import numpy as np
import joblib

from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
from sklearn.model_selection import StratifiedKFold, cross_validate

logger = logging.getLogger(__name__)

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(ROOT_DIR, "results", "models")
TIMESTEPS = 20  # paper §5.3: sequences of 20 consecutive network flows


# ---------------------------------------------------------------------------
# Lazy TensorFlow / Keras loader
# ---------------------------------------------------------------------------

def _keras():
    try:
        import tensorflow as tf
        return tf.keras
    except ImportError as exc:
        raise ImportError(
            "TensorFlow is required for LSTM and Autoencoder. "
            "Install: pip install tensorflow"
        ) from exc


# ---------------------------------------------------------------------------
# 1. RandomForestIDS
# Paper §5.3: 200 trees, Gini impurity, max depth unrestricted, n_jobs=-1
# ---------------------------------------------------------------------------

class RandomForestIDS:
    """Random Forest intrusion detector — paper §5.3."""

    def __init__(self, random_state: int = 42):
        self.model = RandomForestClassifier(
            n_estimators=200,
            criterion="gini",
            max_depth=None,
            n_jobs=-1,
            random_state=random_state,
        )
        self.training_time: float = 0.0

    def train(self, X_train: np.ndarray, y_train: np.ndarray) -> "RandomForestIDS":
        t0 = time.time()
        self.model.fit(X_train, y_train)
        self.training_time = time.time() - t0
        logger.info("RandomForest trained in %.2fs", self.training_time)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.model.predict(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        return self.model.predict_proba(X)

    @property
    def feature_importances_(self) -> np.ndarray:
        return self.model.feature_importances_

    def cross_validate_10fold(self, X: np.ndarray, y: np.ndarray) -> dict:
        """10-fold stratified cross-validation. Returns mean and std of accuracy."""
        cv = StratifiedKFold(n_splits=10, shuffle=True, random_state=42)
        scores = cross_validate(
            self.model, X, y,
            cv=cv, scoring=["accuracy", "f1_weighted"], n_jobs=-1,
        )
        return {
            "accuracy_mean": float(scores["test_accuracy"].mean()),
            "accuracy_std":  float(scores["test_accuracy"].std()),
            "f1_mean":       float(scores["test_f1_weighted"].mean()),
            "f1_std":        float(scores["test_f1_weighted"].std()),
            "n_folds": 10,
        }

    def save(self, name: str = "random_forest", output_dir: str = MODELS_DIR) -> str:
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, f"{name}.pkl")
        joblib.dump(self.model, path)
        return path

    @classmethod
    def load(cls, name: str = "random_forest", model_dir: str = MODELS_DIR) -> "RandomForestIDS":
        obj = cls()
        obj.model = joblib.load(os.path.join(model_dir, f"{name}.pkl"))
        return obj


# ---------------------------------------------------------------------------
# 2. SVMIDS
# Paper §5.3: RBF kernel, C=10, gamma=0.001, probability=True
# ---------------------------------------------------------------------------

class SVMIDS:
    """Support Vector Machine intrusion detector — paper §5.3."""

    def __init__(self):
        self.model = SVC(
            kernel="rbf",
            C=10,
            gamma=0.001,
            probability=True,
            random_state=42,
        )
        self.training_time: float = 0.0

    def train(self, X_train: np.ndarray, y_train: np.ndarray) -> "SVMIDS":
        t0 = time.time()
        self.model.fit(X_train, y_train)
        self.training_time = time.time() - t0
        logger.info("SVM trained in %.2fs", self.training_time)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.model.predict(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        return self.model.predict_proba(X)

    def save(self, name: str = "svm", output_dir: str = MODELS_DIR) -> str:
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, f"{name}.pkl")
        joblib.dump(self.model, path)
        return path

    @classmethod
    def load(cls, name: str = "svm", model_dir: str = MODELS_DIR) -> "SVMIDS":
        obj = cls()
        obj.model = joblib.load(os.path.join(model_dir, f"{name}.pkl"))
        return obj


# ---------------------------------------------------------------------------
# 3. LSTMIDS
# Paper §5.3: 2-layer 128 units, dropout=0.3, Adam, 50 epochs, patience=5
#             Input: sequences of 20 flows; softmax output (multi-class)
# ---------------------------------------------------------------------------

class LSTMIDS:
    """Two-layer LSTM intrusion detector — paper §5.3."""

    def __init__(self, n_classes: int = 2, timesteps: int = TIMESTEPS):
        self.n_classes = n_classes
        self.timesteps = timesteps
        self.model = None
        self.history = None
        self.training_time: float = 0.0

    def _build(self, n_features: int):
        keras = _keras()
        n_out = 1 if self.n_classes == 2 else self.n_classes
        act_out = "sigmoid" if self.n_classes == 2 else "softmax"
        loss = (
            "binary_crossentropy"
            if self.n_classes == 2
            else "sparse_categorical_crossentropy"
        )
        model = keras.Sequential([
            keras.layers.LSTM(
                128, return_sequences=True,
                input_shape=(self.timesteps, n_features),
                name="lstm_1",
            ),
            keras.layers.Dropout(0.3, name="drop_1"),
            keras.layers.LSTM(128, return_sequences=False, name="lstm_2"),
            keras.layers.Dropout(0.3, name="drop_2"),
            keras.layers.Dense(64, activation="relu", name="dense_1"),
            keras.layers.Dense(n_out, activation=act_out, name="output"),
        ])
        model.compile(optimizer="adam", loss=loss, metrics=["accuracy"])
        return model

    @staticmethod
    def reshape(X: np.ndarray, timesteps: int = TIMESTEPS):
        """Reshape (N, F) → (N//t, t, F). Returns (X_seq, n_used)."""
        n, f = X.shape
        n_seq = n // timesteps
        return X[: n_seq * timesteps].reshape(n_seq, timesteps, f), n_seq * timesteps

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        validation_split: float = 0.1,
        batch_size: int = 256,
        epochs: int = 50,
    ) -> "LSTMIDS":
        keras = _keras()
        X_seq, n = self.reshape(X_train, self.timesteps)
        y_seq = y_train[: n : self.timesteps]
        self.model = self._build(n_features=X_seq.shape[2])
        callbacks = [
            keras.callbacks.EarlyStopping(
                monitor="val_loss", patience=5,
                restore_best_weights=True, verbose=1,
            ),
            keras.callbacks.ReduceLROnPlateau(
                monitor="val_loss", factor=0.5, patience=3, verbose=1,
            ),
        ]
        t0 = time.time()
        self.history = self.model.fit(
            X_seq, y_seq,
            epochs=epochs, batch_size=batch_size,
            validation_split=validation_split,
            callbacks=callbacks, verbose=1,
        )
        self.training_time = time.time() - t0
        logger.info("LSTM trained in %.2fs", self.training_time)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        X_seq, _ = self.reshape(X, self.timesteps)
        proba = self.model.predict(X_seq, verbose=0)
        if self.n_classes == 2:
            return (proba.flatten() >= 0.5).astype(int)
        return np.argmax(proba, axis=1)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        X_seq, _ = self.reshape(X, self.timesteps)
        proba = self.model.predict(X_seq, verbose=0)
        if self.n_classes == 2:
            p = proba.flatten()
            return np.column_stack([1 - p, p])
        return proba

    def save(self, name: str = "lstm", output_dir: str = MODELS_DIR) -> str:
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, f"{name}.h5")
        self.model.save(path)
        return path

    @classmethod
    def load(cls, name: str = "lstm", model_dir: str = MODELS_DIR, n_classes: int = 2) -> "LSTMIDS":
        keras = _keras()
        obj = cls(n_classes=n_classes)
        obj.model = keras.models.load_model(os.path.join(model_dir, f"{name}.h5"))
        return obj


# ---------------------------------------------------------------------------
# 4. AutoencoderIDS
# Paper §5.3: Encoder input→32→16→8, symmetric decoder, ReLU hidden,
#             Sigmoid output, MSE loss, threshold = 95th percentile,
#             trained exclusively on normal traffic (label=0)
# ---------------------------------------------------------------------------

class AutoencoderIDS:
    """Autoencoder anomaly detector for zero-day detection — paper §5.3."""

    def __init__(self, input_dim: int = 25):
        self.input_dim = input_dim
        self.model = None
        self.threshold: float = 0.0
        self.training_time: float = 0.0

    def _build(self):
        keras = _keras()
        inp = keras.Input(shape=(self.input_dim,))
        x = keras.layers.Dense(32, activation="relu")(inp)
        x = keras.layers.Dense(16, activation="relu")(x)
        encoded = keras.layers.Dense(8, activation="relu")(x)
        x = keras.layers.Dense(16, activation="relu")(encoded)
        x = keras.layers.Dense(32, activation="relu")(x)
        decoded = keras.layers.Dense(self.input_dim, activation="sigmoid")(x)
        ae = keras.Model(inp, decoded, name="autoencoder")
        ae.compile(optimizer="adam", loss="mse")
        return ae

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        epochs: int = 50,
        batch_size: int = 256,
    ) -> "AutoencoderIDS":
        self.input_dim = X_train.shape[1]
        self.model = self._build()
        X_normal = X_train[y_train == 0]
        logger.info("Autoencoder: training on %d normal samples only.", len(X_normal))
        t0 = time.time()
        self.model.fit(
            X_normal, X_normal,
            epochs=epochs, batch_size=batch_size,
            validation_split=0.1, verbose=1,
        )
        self.training_time = time.time() - t0
        recon = self.model.predict(X_normal, verbose=0)
        errors = np.mean(np.square(X_normal - recon), axis=1)
        self.threshold = float(np.percentile(errors, 95))
        logger.info(
            "Autoencoder trained in %.2fs | 95th-pct threshold: %.6f",
            self.training_time, self.threshold,
        )
        return self

    def _errors(self, X: np.ndarray) -> np.ndarray:
        recon = self.model.predict(X, verbose=0)
        return np.mean(np.square(X - recon), axis=1)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return (self._errors(X) > self.threshold).astype(int)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        errors = self._errors(X)
        norm = np.clip(errors / (self.threshold * 2 + 1e-9), 0, 1)
        return np.column_stack([1 - norm, norm])

    def save(self, name: str = "autoencoder", output_dir: str = MODELS_DIR) -> str:
        os.makedirs(output_dir, exist_ok=True)
        self.model.save(os.path.join(output_dir, f"{name}.h5"))
        joblib.dump(self.threshold, os.path.join(output_dir, f"{name}_threshold.pkl"))
        return os.path.join(output_dir, f"{name}.h5")

    @classmethod
    def load(cls, name: str = "autoencoder", model_dir: str = MODELS_DIR) -> "AutoencoderIDS":
        keras = _keras()
        obj = cls()
        obj.model = keras.models.load_model(os.path.join(model_dir, f"{name}.h5"))
        obj.threshold = joblib.load(os.path.join(model_dir, f"{name}_threshold.pkl"))
        return obj


# ---------------------------------------------------------------------------
# 5. XGBoostIDS
# Paper §5.3: 500 estimators, lr=0.05, max_depth=6, subsample=0.8,
#             colsample_bytree=0.8, eval_metric='mlogloss'
# ---------------------------------------------------------------------------

class XGBoostIDS:
    """XGBoost ensemble intrusion detector — paper §5.3."""

    def __init__(self, random_state: int = 42):
        import xgboost as xgb

        self.model = xgb.XGBClassifier(
            n_estimators=500,
            learning_rate=0.05,
            max_depth=6,
            subsample=0.8,
            colsample_bytree=0.8,
            use_label_encoder=False,
            eval_metric="mlogloss",
            random_state=random_state,
            n_jobs=-1,
        )
        self.training_time: float = 0.0

    def train(self, X_train: np.ndarray, y_train: np.ndarray) -> "XGBoostIDS":
        t0 = time.time()
        self.model.fit(X_train, y_train, verbose=False)
        self.training_time = time.time() - t0
        logger.info("XGBoost trained in %.2fs", self.training_time)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.model.predict(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        return self.model.predict_proba(X)

    @property
    def feature_importances_(self) -> np.ndarray:
        return self.model.feature_importances_

    def cross_validate_10fold(self, X: np.ndarray, y: np.ndarray) -> dict:
        """10-fold stratified cross-validation. Returns mean and std of accuracy."""
        cv = StratifiedKFold(n_splits=10, shuffle=True, random_state=42)
        scores = cross_validate(
            self.model, X, y,
            cv=cv, scoring=["accuracy", "f1_weighted"], n_jobs=-1,
        )
        return {
            "accuracy_mean": float(scores["test_accuracy"].mean()),
            "accuracy_std":  float(scores["test_accuracy"].std()),
            "f1_mean":       float(scores["test_f1_weighted"].mean()),
            "f1_std":        float(scores["test_f1_weighted"].std()),
            "n_folds": 10,
        }

    def save(self, name: str = "xgboost", output_dir: str = MODELS_DIR) -> str:
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, f"{name}.pkl")
        joblib.dump(self.model, path)
        return path

    @classmethod
    def load(cls, name: str = "xgboost", model_dir: str = MODELS_DIR) -> "XGBoostIDS":
        obj = cls()
        obj.model = joblib.load(os.path.join(model_dir, f"{name}.pkl"))
        return obj


# ---------------------------------------------------------------------------
# Legacy functional helpers — backwards compatible with notebooks
# ---------------------------------------------------------------------------

def build_random_forest(random_state: int = 42) -> RandomForestClassifier:
    return RandomForestIDS(random_state).model


def build_svm() -> SVC:
    return SVMIDS().model


def build_xgboost(random_state: int = 42) -> xgb.XGBClassifier:
    return XGBoostIDS(random_state).model


def reshape_for_lstm(X: np.ndarray, timesteps: int = TIMESTEPS) -> np.ndarray:
    X_seq, _ = LSTMIDS.reshape(X, timesteps)
    return X_seq


def get_lstm_callbacks(patience: int = 5):
    keras = _keras()
    return [
        keras.callbacks.EarlyStopping(
            monitor="val_loss", patience=patience,
            restore_best_weights=True, verbose=1,
        ),
        keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss", factor=0.5, patience=3, verbose=1,
        ),
    ]


def save_sklearn_model(model, name: str, output_dir: str = MODELS_DIR) -> str:
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{name}.pkl")
    joblib.dump(model, path)
    return path


def load_sklearn_model(name: str, model_dir: str = MODELS_DIR):
    return joblib.load(os.path.join(model_dir, f"{name}.pkl"))


def save_keras_model(model, name: str, output_dir: str = MODELS_DIR) -> str:
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{name}.h5")
    model.save(path)
    return path


def predict_autoencoder(autoencoder, X: np.ndarray, threshold: float) -> np.ndarray:
    recon = autoencoder.predict(X, verbose=0)
    errors = np.mean(np.square(X - recon), axis=1)
    return (errors > threshold).astype(int)
