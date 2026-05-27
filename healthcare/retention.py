"""HeartRateData retention service.

Three jobs, designed to run periodically (e.g. via APScheduler or cron):
  1. aggregate_hourly()  — roll up raw data into hourly summaries
  2. aggregate_daily()   — roll up hourly data into daily summaries
  3. cleanup()           — delete old raw and aggregated data

Safety rules:
  - Never delete raw rows where is_critical = True
  - Never delete raw rows linked to the last 50 readings of an active device
  - Aggregated rows with has_critical/critical_count > 0 are kept longer
"""

import os
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, and_

from healthcare import db
from healthcare.models import HeartRateData, HeartRateHourly, HeartRateDaily, Post


# ---------------------------------------------------------------------------
# Retention windows (in days) — configurable via environment variables
# ---------------------------------------------------------------------------
RAW_RETENTION_DAYS = int(os.environ.get('RETENTION_RAW_DAYS', 7))
HOURLY_RETENTION_DAYS = int(os.environ.get('RETENTION_HOURLY_DAYS', 90))
DAILY_RETENTION_DAYS = int(os.environ.get('RETENTION_DAILY_DAYS', 365))


def _utcnow():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# 1. Aggregate raw -> hourly
# ---------------------------------------------------------------------------
def aggregate_hourly():
    """Aggregate raw HeartRateData into HeartRateHourly for hours that ended."""
    now = _utcnow()
    cutoff_hour = now.replace(minute=0, second=0, microsecond=0)  # current incomplete hour

    # Find distinct device_ids that have raw data
    device_ids = [
        r[0] for r in db.session.query(HeartRateData.device_id).distinct().all()
    ]

    created = 0
    for device_id in device_ids:
        # Find hours that have raw data but no hourly aggregate yet
        raw_hours = (
            db.session.query(
                func.date_format(HeartRateData.timestamp, '%Y-%m-%d %H:00:00').label('hour')
            )
            .filter(HeartRateData.device_id == device_id)
            .filter(HeartRateData.timestamp < cutoff_hour)
            .group_by('hour')
            .all()
        )

        for (hour_str,) in raw_hours:
            hour_dt = datetime.strptime(hour_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)

            # Skip if aggregate already exists
            exists = HeartRateHourly.query.filter_by(
                device_id=device_id, hour=hour_dt
            ).first()
            if exists:
                continue

            rows = (
                HeartRateData.query
                .filter(HeartRateData.device_id == device_id)
                .filter(
                    HeartRateData.timestamp >= hour_dt,
                    HeartRateData.timestamp < hour_dt + timedelta(hours=1),
                )
                .all()
            )

            if not rows:
                continue

            hr_vals = [r.heart_rate for r in rows]
            spo2_vals = [r.spo2 for r in rows]

            agg = HeartRateHourly(
                device_id=device_id,
                hour=hour_dt,
                hr_avg=sum(hr_vals) / len(hr_vals),
                hr_min=min(hr_vals),
                hr_max=max(hr_vals),
                spo2_avg=sum(spo2_vals) / len(spo2_vals),
                spo2_min=min(spo2_vals),
                spo2_max=max(spo2_vals),
                reading_count=len(rows),
                has_critical=any(r.is_critical for r in rows),
            )
            db.session.add(agg)
            created += 1

    db.session.commit()
    return created


# ---------------------------------------------------------------------------
# 2. Aggregate hourly -> daily
# ---------------------------------------------------------------------------
def aggregate_daily():
    """Aggregate HeartRateHourly into HeartRateDaily for days that ended."""
    now = _utcnow()
    cutoff_day = now.date()  # current incomplete day

    device_ids = [
        r[0] for r in db.session.query(HeartRateHourly.device_id).distinct().all()
    ]

    created = 0
    for device_id in device_ids:
        raw_days = (
            db.session.query(func.date(HeartRateHourly.hour).label('day'))
            .filter(HeartRateHourly.device_id == device_id)
            .filter(func.date(HeartRateHourly.hour) < cutoff_day)
            .group_by('day')
            .all()
        )

        for (day_date,) in raw_days:
            if isinstance(day_date, str):
                day_date = datetime.strptime(day_date, '%Y-%m-%d').date()

            exists = HeartRateDaily.query.filter_by(
                device_id=device_id, day=day_date
            ).first()
            if exists:
                continue

            rows = (
                HeartRateHourly.query
                .filter(HeartRateHourly.device_id == device_id)
                .filter(
                    func.date(HeartRateHourly.hour) == day_date,
                )
                .all()
            )

            if not rows:
                continue

            hr_avgs = [r.hr_avg for r in rows if r.hr_avg is not None]
            hr_mins = [r.hr_min for r in rows if r.hr_min is not None]
            hr_maxs = [r.hr_max for r in rows if r.hr_max is not None]
            spo2_avgs = [r.spo2_avg for r in rows if r.spo2_avg is not None]
            spo2_mins = [r.spo2_min for r in rows if r.spo2_min is not None]
            spo2_maxs = [r.spo2_max for r in rows if r.spo2_max is not None]
            total_count = sum(r.reading_count for r in rows)
            crit_count = sum(1 for r in rows if r.has_critical)

            agg = HeartRateDaily(
                device_id=device_id,
                day=day_date,
                hr_avg=sum(hr_avgs) / len(hr_avgs) if hr_avgs else None,
                hr_min=min(hr_mins) if hr_mins else None,
                hr_max=max(hr_maxs) if hr_maxs else None,
                spo2_avg=sum(spo2_avgs) / len(spo2_avgs) if spo2_avgs else None,
                spo2_min=min(spo2_mins) if spo2_mins else None,
                spo2_max=max(spo2_maxs) if spo2_maxs else None,
                reading_count=total_count,
                critical_count=crit_count,
            )
            db.session.add(agg)
            created += 1

    db.session.commit()
    return created


# ---------------------------------------------------------------------------
# 3. Cleanup old data
# ---------------------------------------------------------------------------
def _active_device_ids():
    """Device IDs that have an active (non-deleted) Post."""
    return [
        r[0] for r in db.session.query(Post.device_id).distinct().all()
        if r[0]
    ]


def cleanup():
    """Delete expired data. Returns dict of deletion counts."""
    now = _utcnow()
    active_devices = _active_device_ids()
    counts = {"raw": 0, "raw_critical_kept": 0, "hourly": 0, "daily": 0}

    # --- Raw data older than RAW_RETENTION_DAYS ---
    raw_cutoff = now - timedelta(days=RAW_RETENTION_DAYS)
    old_raw = (
        HeartRateData.query
        .filter(HeartRateData.timestamp < raw_cutoff)
        .all()
    )

    for row in old_raw:
        # Never delete critical readings
        if row.is_critical:
            counts["raw_critical_kept"] += 1
            continue

        # Never delete if it's within the last 50 readings of an active device
        if row.device_id in active_devices:
            count_after = (
                HeartRateData.query
                .filter(HeartRateData.device_id == row.device_id)
                .filter(HeartRateData.timestamp > row.timestamp)
                .count()
            )
            if count_after < 50:
                counts["raw_critical_kept"] += 1
                continue

        db.session.delete(row)
        counts["raw"] += 1

    db.session.commit()

    # --- Hourly aggregates older than HOURLY_RETENTION_DAYS ---
    hourly_cutoff = now - timedelta(days=HOURLY_RETENTION_DAYS)
    # Keep hourly rows that contain critical events (extend by 3x)
    critical_hourly_cutoff = now - timedelta(days=HOURLY_RETENTION_DAYS * 3)
    old_hourly = HeartRateHourly.query.filter(
        HeartRateHourly.hour < hourly_cutoff,
        HeartRateHourly.has_critical == False,
    ).delete(synchronize_session=False)
    # Delete critical hourly rows only after extended window
    old_critical_hourly = HeartRateHourly.query.filter(
        HeartRateHourly.hour < critical_hourly_cutoff,
        HeartRateHourly.has_critical == True,
    ).delete(synchronize_session=False)
    counts["hourly"] = old_hourly + old_critical_hourly
    db.session.commit()

    # --- Daily aggregates older than DAILY_RETENTION_DAYS ---
    daily_cutoff = (now - timedelta(days=DAILY_RETENTION_DAYS)).date()
    critical_daily_cutoff = (now - timedelta(days=DAILY_RETENTION_DAYS * 3)).date()
    old_daily = HeartRateDaily.query.filter(
        HeartRateDaily.day < daily_cutoff,
        HeartRateDaily.critical_count == 0,
    ).delete(synchronize_session=False)
    old_critical_daily = HeartRateDaily.query.filter(
        HeartRateDaily.day < critical_daily_cutoff,
        HeartRateDaily.critical_count > 0,
    ).delete(synchronize_session=False)
    counts["daily"] = old_daily + old_critical_daily
    db.session.commit()

    return counts


# ---------------------------------------------------------------------------
# Run all retention jobs
# ---------------------------------------------------------------------------
def run_retention():
    """Execute full retention pipeline. Returns summary dict."""
    hourly_created = aggregate_hourly()
    daily_created = aggregate_daily()
    deleted = cleanup()
    return {
        "hourly_aggregated": hourly_created,
        "daily_aggregated": daily_created,
        "deleted_raw": deleted["raw"],
        "critical_raw_kept": deleted["raw_critical_kept"],
        "deleted_hourly": deleted["hourly"],
        "deleted_daily": deleted["daily"],
    }
