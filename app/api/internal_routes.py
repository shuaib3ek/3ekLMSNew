from flask import Blueprint, request, jsonify, current_app

internal_bp = Blueprint('internal', __name__)


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
