import json

from backend.app.config import config
from backend.app.ml import model
from backend.app.storage import asset_exists, put_asset


def test_model_artefacts_are_stored_as_assets_not_in_the_code_tree():
    """A retrained classifier has to survive a redeploy, so it lives in asset storage."""
    assert not config.blob_enabled, "this test asserts where the local asset backend writes"
    assert model.MODEL_KEY.startswith("models/")
    assert model.META_KEY.startswith("models/")

    status = model.ensure_starter_model()

    assert asset_exists(model.MODEL_KEY)
    assert asset_exists(model.META_KEY)
    assert (config.data_dir / model.MODEL_KEY).is_file()
    assert status["sample_count"] > 0
    assert len(status["metrics"]["confusion_matrix"]) == len(model.CLASS_NAMES)


def test_model_status_does_not_report_metrics_for_a_missing_model(monkeypatch):
    """Stored metadata must never describe a classifier that cannot predict."""
    monkeypatch.setattr(model, "META_KEY", "models/test-stale.json")
    monkeypatch.setattr(model, "MODEL_KEY", "models/test-absent.joblib")
    model.load_model.cache_clear()
    put_asset("models/test-stale.json", json.dumps({
        "source": "stale metadata", "trained_at": "2020-01-01T00:00:00+00:00",
        "classes": model.CLASS_NAMES, "feature_names": model.FEATURE_NAMES,
        "sample_count": 1, "metrics": {"accuracy": 0.9, "confusion_matrix": []},
    }).encode("utf-8"), "application/json")

    status = model.model_status()

    assert status["source"] == "starter model trained on synthetic data"
    assert asset_exists(model.MODEL_KEY)
    assert len(status["metrics"]["confusion_matrix"]) == len(model.CLASS_NAMES)
    assert status["metrics"]["accuracy"] != 0.9
