from healthcare import db, login_manager
from datetime import datetime, timezone
from flask_login import UserMixin
import secrets


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
class User(db.Model,UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    image_file = db.Column(db.String(20), nullable=False, default='default.jpg')
    password = db.Column(db.String(60), nullable=False)
    posts = db.relationship('Post', backref='author', lazy=True)
    def __repr__(self):
        return f"User('{self.username}', '{self.email}', '{self.image_file}')"

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    condition = db.Column(db.String(200), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    device_id = db.Column(db.String(50), nullable=False, index=True)
    date_posted = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    risk = db.Column(db.Float, default=0.0)  # xác suất mắc bệnh từ mô hình AI

def is_critical_reading(heart_rate, spo2):
    """Check if a reading represents a critical medical event."""
    return heart_rate < 40 or heart_rate > 180 or spo2 < 85


class HeartRateData(db.Model):
    __table_args__ = (
        db.Index('idx_hrd_device_timestamp', 'device_id', 'timestamp'),
    )

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(50))
    heart_rate = db.Column(db.Float)
    spo2 = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_critical = db.Column(db.Boolean, default=False, nullable=False)

    def __repr__(self):
        return f"<HRData {self.device_id} {self.heart_rate} bpm>"


class HeartRateHourly(db.Model):
    """Hourly aggregation of heart rate data. Retained for 90 days."""
    __table_args__ = (
        db.Index('idx_hrh_device_hour', 'device_id', 'hour'),
        db.UniqueConstraint('device_id', 'hour', name='uq_hrh_device_hour'),
    )

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(50), nullable=False)
    hour = db.Column(db.DateTime, nullable=False)
    hr_avg = db.Column(db.Float)
    hr_min = db.Column(db.Float)
    hr_max = db.Column(db.Float)
    spo2_avg = db.Column(db.Float)
    spo2_min = db.Column(db.Float)
    spo2_max = db.Column(db.Float)
    reading_count = db.Column(db.Integer, nullable=False, default=0)
    has_critical = db.Column(db.Boolean, default=False, nullable=False)


class HeartRateDaily(db.Model):
    """Daily aggregation of heart rate data. Retained for 365 days."""
    __table_args__ = (
        db.Index('idx_hrd_device_day', 'device_id', 'day'),
        db.UniqueConstraint('device_id', 'day', name='uq_hrd_device_day'),
    )

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(50), nullable=False)
    day = db.Column(db.Date, nullable=False)
    hr_avg = db.Column(db.Float)
    hr_min = db.Column(db.Float)
    hr_max = db.Column(db.Float)
    spo2_avg = db.Column(db.Float)
    spo2_min = db.Column(db.Float)
    spo2_max = db.Column(db.Float)
    reading_count = db.Column(db.Integer, nullable=False, default=0)
    critical_count = db.Column(db.Integer, nullable=False, default=0)

class DeviceApiKey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(50), unique=True, nullable=False)
    api_key = db.Column(db.String(64), unique=True, nullable=False, default=lambda: secrets.token_hex(32))
