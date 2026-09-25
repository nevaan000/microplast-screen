from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support
from sklearn.model_selection import train_test_split

from ..config import config

FEATURE_NAMES = [
    "area_px", "perimeter_px", "length_px", "width_px", "aspect_ratio", "circularity", "solidity", "extent",
    "mean_r", "mean_g", "mean_b", "mean_h", "mean_s", "mean_v", "texture_std",
]
CLASS_NAMES = ["fiber", "fragment", "film", "pellet", "non_plastic"]
MODEL_PATH = config.root_dir / "backend" / "app" / "ml" / "models" / "microplast_rf.joblib"
META_PATH = config.root_dir / "backend" / "app" / "ml" / "models" / "microplast_rf.json"


def _feature_vector(particle: dict[str, Any]) -> list[float]:
    return [float(particle.get(name, 0) or 0) for name in FEATURE_NAMES]


def synthetic_training_rows(per_class: int = 320, seed: int = 20260924) -> tuple[list[list[float]], list[str]]:
    rng = np.random.default_rng(seed)
    rows: list[list[float]] = []
    labels: list[str] = []
    for class_name in CLASS_NAMES:
        for _ in range(per_class):
            if class_name == "fiber":
                length = rng.uniform(55, 320); width = rng.uniform(3, 11); aspect = length / width
                circularity, solidity, saturation, texture = rng.uniform(.08, .38), rng.uniform(.72, .99), rng.uniform(45, 230), rng.uniform(3, 22)
            elif class_name == "pellet":
                width = length = rng.uniform(10, 55); aspect = rng.uniform(1, 1.35)
                circularity, solidity, saturation, texture = rng.uniform(.80, .98), rng.uniform(.88, 1), rng.uniform(20, 220), rng.uniform(2, 18)
            elif class_name == "film":
                length = rng.uniform(40, 260); width = rng.uniform(20, max(21, length * .7)); aspect = length / width
                circularity, solidity, saturation, texture = rng.uniform(.18, .75), rng.uniform(.30, .75), rng.uniform(5, 95), rng.uniform(2, 25)
            elif class_name == "fragment":
                length = rng.uniform(10, 100); width = rng.uniform(6, length); aspect = length / width
                circularity, solidity, saturation, texture = rng.uniform(.25, .80), rng.uniform(.55, .95), rng.uniform(35, 240), rng.uniform(5, 35)
            else:
                length = rng.uniform(5, 120); width = rng.uniform(4, max(5, length)); aspect = length / width
                circularity, solidity, saturation, texture = rng.uniform(.05, .72), rng.uniform(.25, .85), rng.uniform(5, 100), rng.uniform(25, 75)
            area = max(12, length * width * rng.uniform(.35, .82))
            perimeter = max(4, 2 * (length + width) * rng.uniform(.7, 1.2))
            extent = np.clip(area / max(1, length * width), .05, 1)
            hue = rng.uniform(0, 180)
            value = rng.uniform(45, 230)
            bgr = rng.uniform(max(0, value - saturation / 3), min(255, value + saturation / 3), 3)
            rows.append([area, perimeter, length, width, aspect, circularity, solidity, extent, bgr[2], bgr[1], bgr[0], hue, saturation, value, texture])
            labels.append(class_name)
    return rows, labels


def _fit(rows: list[list[float]], labels: list[str], source: str) -> dict[str, Any]:
    x = np.asarray(rows, dtype=float)
    y = np.asarray(labels)
    if len(set(labels)) < 2:
        raise ValueError("Training requires at least two classes")
    x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=0.2, random_state=42, stratify=y)
    classifier = RandomForestClassifier(n_estimators=240, random_state=42, n_jobs=-1, class_weight="balanced")
    classifier.fit(x_train, y_train)
    predicted = classifier.predict(x_test)
    precision, recall, f1, _ = precision_recall_fscore_support(y_test, predicted, labels=CLASS_NAMES, zero_division=0)
    metadata = {
        "source": source,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "classes": CLASS_NAMES,
        "feature_names": FEATURE_NAMES,
        "sample_count": int(len(labels)),
        "metrics": {
            "accuracy": round(float(accuracy_score(y_test, predicted)), 4),
            "precision": {name: round(float(value), 4) for name, value in zip(CLASS_NAMES, precision)},
            "recall": {name: round(float(value), 4) for name, value in zip(CLASS_NAMES, recall)},
            "f1": {name: round(float(value), 4) for name, value in zip(CLASS_NAMES, f1)},
            "confusion_matrix": confusion_matrix(y_test, predicted, labels=CLASS_NAMES).tolist(),
            "feature_importance": {name: round(float(value), 5) for name, value in zip(FEATURE_NAMES, classifier.feature_importances_)},
        },
    }
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(classifier, MODEL_PATH)
    META_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    load_model.cache_clear()
    return metadata


def ensure_starter_model() -> dict[str, Any]:
    if MODEL_PATH.exists() and META_PATH.exists():
        return model_status()
    rows, labels = synthetic_training_rows()
    return _fit(rows, labels, "starter model trained on synthetic data")


@lru_cache(maxsize=1)
def load_model() -> RandomForestClassifier:
    ensure_starter_model()
    return joblib.load(MODEL_PATH)


def model_status() -> dict[str, Any]:
    if not META_PATH.exists():
        return ensure_starter_model()
    return json.loads(META_PATH.read_text(encoding="utf-8"))


def predict_particle(particle: dict[str, Any]) -> dict[str, Any] | None:
    if not MODEL_PATH.exists():
        ensure_starter_model()
    classifier = load_model()
    probabilities = classifier.predict_proba([_feature_vector(particle)])[0]
    probability_by_class = {name: float(value) for name, value in zip(classifier.classes_, probabilities)}
    shape = max(probability_by_class, key=probability_by_class.get)
    plastic_score = 1 - probability_by_class.get("non_plastic", 0.0)
    predicted_probability = probability_by_class[shape]
    return {
        "shape_class": shape,
        "label": "non_plastic" if shape == "non_plastic" else "suspected_plastic",
        "confidence": round(predicted_probability, 4),
        "plastic_score": round(plastic_score, 4),
    }


def train_model(verified_particles: list[dict[str, Any]] | None = None, include_synthetic: bool = True) -> dict[str, Any]:
    rows: list[list[float]] = []
    labels: list[str] = []
    if include_synthetic:
        rows, labels = synthetic_training_rows()
    for particle in verified_particles or []:
        label = particle.get("user_verified_class")
        if label in CLASS_NAMES:
            rows.append(_feature_vector(particle))
            labels.append(label)
    source_parts = []
    if include_synthetic:
        source_parts.append("synthetic data")
    if verified_particles:
        source_parts.append("user-verified particles")
    return _fit(rows, labels, " + ".join(source_parts) or "training data")
