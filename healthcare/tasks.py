"""Celery tasks for background processing."""
import logging

from celery_worker import celery

logger = logging.getLogger(__name__)


@celery.task(name='healthcare.tasks.send_reset_email_task')
def send_reset_email_task(user_id, token):
    """Send password reset email asynchronously."""
    from flask import url_for
    from flask_mail import Message
    from healthcare import db, mail
    from healthcare.models import User

    user = db.session.get(User, user_id)
    if not user:
        logger.error("send_reset_email_task: user %s not found", user_id)
        return

    msg = Message(
        "Reset Your Password",
        sender=None,  # uses MAIL_DEFAULT_SENDER or MAIL_USERNAME
        recipients=[user.email],
    )
    msg.body = f'''Để đặt lại mật khẩu, click vào link sau:
{url_for('auth.reset_token', token=token, _external=True)}

Nếu bạn không yêu cầu, hãy bỏ qua email này.
'''
    try:
        mail.send(msg)
        logger.info("Reset email sent to %s", user.email)
    except Exception:
        logger.exception("Failed to send reset email to %s", user.email)
        raise


@celery.task(name='healthcare.tasks.run_retention_task')
def run_retention_task():
    """Run data retention pipeline (aggregate + cleanup)."""
    from healthcare.retention import run_retention

    try:
        result = run_retention()
        logger.info("Retention completed: %s", result)
        return result
    except Exception:
        logger.exception("Retention task failed")
        raise
