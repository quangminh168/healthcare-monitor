from datetime import timezone
from flask import Blueprint, request, jsonify, current_app
from healthcare import db, limiter
from healthcare.models import Post, HeartRateData, DeviceApiKey, is_critical_reading
from healthcare.ml_service import predict_risk

api_bp = Blueprint("api", __name__)


def verify_api_key(device_id):
    """Verify X-API-Key header matches the device_id. Returns None on success, error response on failure."""
    key = request.headers.get("X-API-Key")
    if not key:
        return jsonify({"error": "Missing X-API-Key header"}), 401
    entry = DeviceApiKey.query.filter_by(device_id=device_id, api_key=key).first()
    if not entry:
        return jsonify({"error": "Invalid API key"}), 401
    return None


@api_bp.route("/api/heartbeat", methods=["POST"], endpoint="receive_heartbeat")
@limiter.limit(lambda: current_app.config.get("RATELIMIT_HEARTBEAT", "60/minute"))
def receive_heartbeat():
    try:
        data = request.get_json()

        if not data or "device_id" not in data or \
           "heart_rate" not in data or "spo2" not in data:
            return jsonify({"error": "Invalid data"}), 400

        auth_error = verify_api_key(data["device_id"])
        if auth_error:
            return auth_error

        print("Received from ESP:", data)

        hr = float(data["heart_rate"])
        spo2 = float(data["spo2"])

        new_data = HeartRateData(
            device_id=data["device_id"],
            heart_rate=hr,
            spo2=spo2,
            is_critical=is_critical_reading(hr, spo2),
        )
        db.session.add(new_data)
        db.session.flush()

        if hr > 0 and spo2 > 0:
            post = (
                Post.query.filter_by(device_id=data["device_id"])
                .order_by(Post.date_posted.desc())
                .first()
            )

            if post:
                post.risk = predict_risk(post.id)

        db.session.commit()
        return jsonify({"message": "Data saved"}), 201

    except Exception as e:
        db.session.rollback()
        print("Error saving data:", e)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/heartbeat/latest/<string:device_id>", endpoint="heartbeat_latest")
def heartbeat_latest(device_id):
    last_data = (
        HeartRateData.query.filter_by(device_id=device_id)
        .order_by(HeartRateData.timestamp.desc())
        .first()
    )
    print(f"Sending latest data for {device_id}")
    if last_data:
        ts = last_data.timestamp.astimezone(timezone.utc)
        return jsonify({
            "timestamp_iso": ts.isoformat(),
            "timestamp_ms": int(ts.timestamp() * 1000),
            "bpm": last_data.heart_rate,
            "spo2": last_data.spo2,
        })
    else:
        return jsonify({"timestamp_iso": None, "timestamp_ms": 0, "bpm": 0, "spo2": 0})


@api_bp.route("/heartbeat/all/<string:device_id>", endpoint="heartbeat_all")
def heartbeat_all(device_id):
    post = Post.query.filter_by(device_id=device_id).first()

    if post and post.device_id == "esp8266-01":
        data_rows = (
            HeartRateData.query.filter_by(device_id=device_id)
            .order_by(HeartRateData.timestamp.desc())
            .limit(50)
            .all()[::-1]
        )
    else:
        data_rows = (
            HeartRateData.query.filter_by(device_id=device_id)
            .order_by(HeartRateData.timestamp.asc())
            .all()
        )

    result = []
    for row in data_rows:
        ts = row.timestamp.astimezone(timezone.utc)
        result.append({
            "timestamp_ms": int(ts.timestamp() * 1000),
            "bpm": row.heart_rate,
            "spo2": row.spo2,
        })
    return jsonify(result)
