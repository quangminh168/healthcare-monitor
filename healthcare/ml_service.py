import logging
import os
import joblib
import pandas as pd
from flask import current_app
from healthcare.models import Post, HeartRateData

logger = logging.getLogger(__name__)

_model = None
_model_loaded = False


def get_model():
    """Lazy-load the ML model. Returns the model or None if unavailable."""
    global _model, _model_loaded
    if not _model_loaded:
        _model_loaded = True
        try:
            model_path = os.environ.get('MODEL_PATH', 'patient_model.pkl')
            _model = joblib.load(model_path)
        except FileNotFoundError:
            logger.warning("patient_model.pkl not found. Risk predictions disabled.")
        except Exception as e:
            logger.warning("Failed to load model: %s. Risk predictions disabled.", e)
    return _model


def encode_gender(gender):
    g = gender.lower()
    if g in ["nam", "male", "m"]:
        return 1
    return 0


def calculate_features(post_id):
    """Build feature DataFrame from patient record and recent sensor data."""
    post = Post.query.get(post_id)
    if not post or not post.device_id:
        return pd.DataFrame([{
            "age": post.age if post else 0,
            "gender": encode_gender(post.gender) if post else 0,
            "heart_rate_avg": 0,
            "spo2_avg": 0
        }])

    hr_data = HeartRateData.query \
        .filter_by(device_id=post.device_id) \
        .order_by(HeartRateData.timestamp.desc()) \
        .limit(50) \
        .all()

    if not hr_data:
        hr_avg = 0
        spo2_avg = 0
    else:
        hr_avg = sum(d.heart_rate for d in hr_data) / len(hr_data)
        spo2_avg = sum(d.spo2 for d in hr_data) / len(hr_data)

    X = pd.DataFrame([{
        "age": post.age,
        "gender": encode_gender(post.gender),
        "heart_rate_avg": hr_avg,
        "spo2_avg": spo2_avg
    }])

    return X


def predict_risk(post_id):
    """Predict risk score for a patient post. Returns float 0.0-1.0, or 0.0 if model unavailable."""
    X = calculate_features(post_id)
    model = get_model()
    if model is None:
        return 0.0
    return float(model.predict_proba(X)[0][1])
