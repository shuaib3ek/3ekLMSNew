"""
LMS Background Tasks (MS Teams recording pipeline only).
No CRM business logic here.
"""
import json
from datetime import datetime, timedelta
from flask import current_app
from app.core.extensions import db
from app.workshops.models import WorkshopSession, SystemTask, GraphSubscription


def process_msteams_tasks():
    """Poll queued MS Teams tasks (recording fetch, AI processing)."""
    now = datetime.utcnow()
    tasks = SystemTask.query.filter(
        SystemTask.status == 'queued',
        SystemTask.next_run_at <= now,
    ).order_by(SystemTask.next_run_at).limit(10).all()

    for task in tasks:
        task.status = 'running'
        db.session.commit()
        try:
            payload = json.loads(task.payload or '{}')
            if task.task_type == 'poll_teams_recording':
                _poll_recording(task, payload)
            task.status = 'completed'
        except Exception as e:
            task.retries += 1
            task.error_log = str(e)
            if task.retries >= task.max_retries:
                task.status = 'failed'
            else:
                task.status = 'queued'
                delay = min(2 ** task.retries, 3600)
                task.next_run_at = datetime.utcnow() + timedelta(seconds=delay)
        db.session.commit()


def renew_msteams_subscriptions():
    """Renew MS Graph webhook subscriptions before they expire."""
    from app.services.ms_graph_service import MSGraphService
    threshold = datetime.utcnow() + timedelta(hours=24)
    expiring = GraphSubscription.query.filter(
        GraphSubscription.status == 'active',
        GraphSubscription.expiration_date <= threshold,
    ).all()

    if not expiring:
        return

    svc = MSGraphService()
    for sub in expiring:
        try:
            sub.status = 'renewing'
            db.session.commit()
            new_expiry = svc.renew_subscription(sub.id)
            if new_expiry:
                sub.expiration_date = new_expiry
                sub.status = 'active'
            else:
                sub.status = 'expired'
            db.session.commit()
        except Exception as e:
            current_app.logger.error(f'[LMS] Subscription renewal failed for {sub.id}: {e}')
            sub.status = 'expired'
            db.session.commit()


def _poll_recording(task, payload):
    session_id = payload.get('session_id')
    if not session_id:
        return
    session = WorkshopSession.query.get(session_id)
    if not session:
        return
    from app.services.ms_graph_service import MSGraphService
    svc = MSGraphService()
    recording_url = svc.get_recording_url(session.graph_drive_id, session.graph_item_id)
    if recording_url:
        session.recording_status = 'ready'
        db.session.commit()
