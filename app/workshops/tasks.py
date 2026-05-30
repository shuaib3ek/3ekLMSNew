"""
LMS Background Tasks — MS Teams recording pipeline + invitation email queue.
"""
import json
from datetime import datetime, timedelta
from flask import current_app
from celery import shared_task
from app.core.extensions import db
from app.workshops.models import WorkshopSession, SystemTask, GraphSubscription


@shared_task(bind=True, max_retries=3)
def process_msteams_tasks(self):
    """Poll queued tasks: MS Teams recording fetch + invitation email batches."""
    now = datetime.utcnow()
    tasks = SystemTask.query.filter(
        SystemTask.status == 'queued',
        SystemTask.next_run_at <= now,
    ).order_by(SystemTask.next_run_at).limit(10).all()

    if tasks:
        current_app.logger.info(f'[LMS] Task Processor: Found {len(tasks)} tasks to process.')

    for task in tasks:
        task.status = 'running'
        db.session.commit()
        try:
            payload = json.loads(task.payload or '{}')
            if task.task_type == 'poll_teams_recording':
                _poll_recording(task, payload)
            elif task.task_type == 'send_invitation_batch':
                _send_invitation_batch(task, payload)
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


def _send_invitation_batch(task, payload):
    """
    Send one batch of invitation emails (up to 10 recipients).
    Updates WorkshopInviteContact status as sent/failed per recipient.
    """
    from app.workshops.models import Workshop, WorkshopInviteContact
    from app.services.ms_graph_service import MSGraphService
    from flask import render_template

    workshop_id = payload.get('workshop_id')
    recipients = payload.get('recipients', [])
    email_type = payload.get('email_type', 'individual')
    sender_email = payload.get('sender_email')

    if not workshop_id or not recipients:
        return

    workshop = Workshop.query.get(workshop_id)
    if not workshop:
        current_app.logger.error(f'[LMS] send_invitation_batch: Workshop {workshop_id} not found')
        return

    graph = MSGraphService()

    for r in recipients:
        send_status = 'failed'
        try:
            subject = f"Invitation: {workshop.title}"
            html_body = render_template(
                'workshops/email_invitation_client.html',
                workshop=workshop,
                recipient=r,
                email_type=email_type,
                now=datetime.utcnow()
            )
            sent = graph.send_email(
                r['email'], subject, html_body,
                sender_email=sender_email
            )
            if sent:
                send_status = 'sent'
                current_app.logger.info(f'[LMS] Invite sent to {r["email"]} (workshop {workshop_id})')
            else:
                current_app.logger.warning(f'[LMS] Invite not sent to {r["email"]} — MS Graph returned falsy')
        except Exception as e:
            current_app.logger.error(f'[LMS] Invite exception for {r["email"]}: {e}')

        # Upsert the tracking row
        if r.get('id'):
            existing = WorkshopInviteContact.query.filter_by(
                workshop_id=workshop_id,
                crm_contact_id=r['id'],
                email_type='invitation'
            ).first()
            if existing:
                existing.status = send_status
                existing.sent_at = datetime.utcnow()
            else:
                db.session.add(WorkshopInviteContact(
                    workshop_id=workshop_id,
                    crm_contact_id=r['id'],
                    name=r['name'],
                    email=r['email'],
                    status=send_status,
                    email_type='invitation',
                    sent_at=datetime.utcnow()
                ))

    db.session.commit()
