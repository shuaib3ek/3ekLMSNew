import re
from flask import Blueprint, request, jsonify, current_app

internal_bp = Blueprint('internal', __name__)


def _slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return re.sub(r'^-+|-+$', '', text)


def _verify_crm_token():
    """Validate that calls to this endpoint come from the CRM service."""
    token = request.headers.get('X-Service-Token', '')
    expected = current_app.config.get('CRM_SERVICE_TOKEN', '')
    if not expected or token != expected:
        return False
    return True


@internal_bp.route('/health')
def health():
    return jsonify({'status': 'ok', 'service': '3ek-lms'})


@internal_bp.route('/enrollments', methods=['POST'])
def enroll_learner():
    """
    CRM triggers a learner enrollment into an LMS workshop.
    Expects: { workshop_id, crm_contact_id, name, email, source }
    """
    if not _verify_crm_token():
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    workshop_id = data.get('workshop_id')
    email = data.get('email', '').strip().lower()

    if not workshop_id or not email:
        return jsonify({'error': 'workshop_id and email are required'}), 400

    from app.workshops.models import Workshop, WorkshopRegistration
    from app.core.extensions import db
    import secrets

    workshop = Workshop.query.get(workshop_id)
    if not workshop:
        return jsonify({'error': 'Workshop not found'}), 404

    existing = WorkshopRegistration.query.filter_by(workshop_id=workshop_id, email=email).first()
    if existing:
        return jsonify({'message': 'Already registered', 'registration_id': existing.id}), 200

    reg = WorkshopRegistration(
        workshop_id=workshop_id,
        crm_contact_id=data.get('crm_contact_id'),
        name=data.get('name', email),
        email=email,
        company=data.get('company', ''),
        status='confirmed',
        payment_status='free',
        source=data.get('source', 'crm_assignment'),
        confirmation_token=secrets.token_urlsafe(32),
    )
    db.session.add(reg)
    db.session.commit()
    return jsonify({'message': 'Enrolled', 'registration_id': reg.id}), 201


@internal_bp.route('/program-handover', methods=['POST'])
def program_handover():
    """
    Pulse triggers a "Program Takeover" in the LMS.
    Expects: { crm_engagement_id, topic, start_date, end_date, crm_client_id, trainer_id }
    """
    if not _verify_crm_token():
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    crm_id = data.get('crm_engagement_id')

    if not crm_id:
        return jsonify({'error': 'crm_engagement_id is required'}), 400

    from app.workshops.models import Workshop
    from app.core.extensions import db
    from datetime import datetime

    # Find or create workshop shell
    workshop = Workshop.query.filter_by(crm_engagement_id=crm_id).first()
    if not workshop:
        workshop = Workshop(
            crm_engagement_id=crm_id,
            is_lms_managed=True,
            admin_ready=False,  # Wait for Admin to upload roster
            status='draft'
        )
        db.session.add(workshop)

    # Sync Metadata from Pulse
    workshop.title = data.get('topic', workshop.title or f"Engagement #{crm_id}")
    if not workshop.slug:
        workshop.slug = _slugify(workshop.title) + f"-{crm_id}"

    # Dates (Pulled live from data payload, or will be pulled from CRM client)
    # Here we store them for initial listing, but logic will pull live-from-CRM later.
    start_str = data.get('start_date')
    end_str = data.get('end_date')

    if start_str:
        try:
            workshop.start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
        except Exception:
            pass
    if end_str:
        try:
            workshop.end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
        except Exception:
            pass

    workshop.crm_client_id = data.get('crm_client_id')

    db.session.commit()

    return jsonify({
        'message': 'Program Handover Successful',
        'workshop_id': workshop.id,
        'slug': workshop.slug
    }), 201
@internal_bp.route('/workshops/<int:workshop_id>/ready', methods=['POST'])
def set_workshop_ready(workshop_id):
    """
    Manually activate a workshop (Admin Workspace).
    Expects: { ready: true }
    """
    # Note: This is a restricted endpoint. In production, ensure session or token check.
    # For now, we allow the request if it comes with the CRM token as a shortcut for the Admin UI call
    # but the Admin UI call uses fetch from same domain - so we need a different check or allow it for Admins.
    
    from app.workshops.models import Workshop
    from app.core.extensions import db
    
    workshop = Workshop.query.get_or_404(workshop_id)
    data = request.get_json(silent=True) or {}
    
    if data.get('ready'):
        workshop.admin_ready = True
        workshop.status = 'published'
        db.session.commit()
        
        # Trigger any Background Tasks: Invitation emails, Credential Provisioning etc.
        # current_app.task_queue.push(provision_workshop, workshop_id)
        
    return jsonify({'success': True})
