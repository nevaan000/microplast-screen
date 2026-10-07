import json

from backend.app.ml import model


def test_model_status_does_not_report_metrics_for_a_missing_model(tmp_path, monkeypatch):
    """Metadata on disk must never describe a classifier that cannot predict."""
    meta_path = tmp_path / "microplast_rf.json"
    meta_path.write_text(json.dumps({
        "source": "stale metadata", "trained_at": "2020-01-01T00:00:00+00:00",
        "classes": model.CLASS_NAMES, "feature_names": model.FEATURE_NAMES,
        "sample_count": 1, "metrics": {"accuracy": 0.9, "confusion_matrix": []},
    }), encoding="utf-8")
    model_path = tmp_path / "absent.joblib"
    monkeypatch.setattr(model, "META_PATH", meta_path)
    monkeypatch.setattr(model, "MODEL_PATH", model_path)

    status = model.model_status()

    assert status["source"] == "starter model trained on synthetic data"
    assert model_path.exists()
    assert len(status["metrics"]["confusion_matrix"]) == len(model.CLASS_NAMES)
    assert status["metrics"]["accuracy"] != 0.9
