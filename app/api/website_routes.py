"""
app/api/website_routes.py
Public-facing JSON API consumed by the 3ek-website (Next.js).
Auth: X-Service-Token header must match LMS_SERVICE_TOKEN env var.
Mounted at: /pulse-api   (keeps the existing website call-sites unchanged)
"""
from flask import Blueprint, request, jsonify, current_app
from app.workshops.models import Workshop, WorkshopRegistration, Learner
from app.core.extensions import db
import secrets

website_bp = Blueprint('website', __name__)


def _verify_token():
    """Validate that calls come from the 3ek-website service."""
    token = request.headers.get('X-Service-Token', '')
    expected = current_app.config.get('LMS_SERVICE_TOKEN', '')
    if not expected or token != expected:
        return False
    return True


def _workshop_to_dict(w: Workshop) -> dict:
    """Serialize a Workshop model to the shape the website expects."""
    return {
        'id': w.id,
        'title': w.title,
        'slug': w.slug,
        'subtitle': w.subtitle or '',
        'description': w.description or w.subtitle or '',
        'start_date': w.start_date.isoformat() if w.start_date else None,
        'end_date': w.end_date.isoformat() if w.end_date else None,
        'start_time': w.start_time or '',
        'end_time': w.end_time or '',
        'duration_display': w.duration_display or '',
        'mode': w.mode or 'online',
        'venue': w.venue or '',
        'total_seats': w.total_seats or 0,
        'seats_booked': w.seats_booked,
        'fee_per_person': float(w.fee_per_person) if w.fee_per_person else 0,
        'early_bird_fee': float(w.early_bird_fee) if w.early_bird_fee else None,
        'early_bird_deadline': w.early_bird_deadline.isoformat() if w.early_bird_deadline else None,
        'currency': w.currency or 'INR',
        'level': w.category or 'Intermediate',
        'category': w.category or 'General',
        'banner_image_url': w.banner_image_url or '',
        'outcomes': w.outcomes_list,
        'learning_outcomes': w.outcomes_list,
        'target_audience': w.target_audience or '',
        'agenda': w.agenda or '',
        'status': w.status,
        'is_public': w.is_public,
    }


# ── Workshop Listing ──────────────────────────────────────────────────────────

@website_bp.route('/workshops')
def list_workshops():
    """Return all public, published workshops."""
    if not _verify_token():
        return jsonify({'error': 'Unauthorized'}), 401

    workshops = Workshop.query.filter_by(is_public=True, status='published').order_by(Workshop.start_date).all()
    return jsonify({'workshops': [_workshop_to_dict(w) for w in workshops]})


# ── Workshop Detail ───────────────────────────────────────────────────────────

@website_bp.route('/workshops/<slug>')
def get_workshop(slug):
    """Return a single public workshop by slug."""
    if not _verify_token():
        return jsonify({'error': 'Unauthorized'}), 401

    w = Workshop.query.filter_by(slug=slug, is_public=True).first()
    if not w:
        return jsonify({'error': 'Workshop not found'}), 404

    return jsonify(_workshop_to_dict(w))


# ── Dashboard Stats ──────────────────────────────────────────────────────────

@website_bp.route('/stats')
def get_stats():
    """Return consolidated stats for the admin dashboard."""
    if not _verify_token():
        return jsonify({'error': 'Unauthorized'}), 401

    total_workshops = Workshop.query.filter_by(status='published').count()
    total_registrations = WorkshopRegistration.query.count()
    
    # Revenue: sum of amount_paid for all successful registrations
    from sqlalchemy import func
    total_revenue = db.session.query(func.sum(WorkshopRegistration.amount_paid)).scalar() or 0

    return jsonify({
        'totalWorkshops': total_workshops,
        'totalRegistrations': total_registrations,
        'totalRevenue': float(total_revenue)
    })


# ── Registration Listing ──────────────────────────────────────────────────────

@website_bp.route('/registrations')
def list_registrations():
    """Return recent registrations with workshop titles."""
    if not _verify_token():
        return jsonify({'error': 'Unauthorized'}), 401

    limit = request.args.get('limit', 50, type=int)
    regs = (WorkshopRegistration.query
            .order_by(WorkshopRegistration.registered_at.desc())
            .limit(limit)
            .all())

    result = []
    for r in regs:
        result.append({
            'id': r.id,
            'name': r.name,
            'email': r.email,
            'status': r.status.upper(),
            'createdAt': r.registered_at.isoformat() if r.registered_at else None,
            'workshop': {
                'title': r.workshop.title if r.workshop else 'Unknown Workshop'
            }
        })

    return jsonify({'registrations': result})


# ── Registration (Existing) ──────────────────────────────────────────────────

@website_bp.route('/workshops/<slug>/register', methods=['POST'])
def register_for_workshop(slug):
    """
    Public registration from the 3ek-website.
    Expects JSON: { name, email, phone?, company?, job_title? }
    """
    if not _verify_token():
        return jsonify({'error': 'Unauthorized'}), 401

    w = Workshop.query.filter_by(slug=slug, is_public=True).first()
    if not w:
        return jsonify({'error': 'Workshop not found'}), 404

    if w.is_full:
        return jsonify({'error': 'Workshop is fully booked'}), 409

    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip().lower()
    name = data.get('name', '').strip()

    if not email or not name:
        return jsonify({'error': 'name and email are required'}), 400

    # Upsert learner
    learner = Learner.query.filter_by(email=email).first()
    if not learner:
        learner = Learner(
            name=name,
            email=email,
            phone=data.get('phone', ''),
            company=data.get('company', ''),
            job_title=data.get('job_title', ''),
        )
        db.session.add(learner)
        db.session.flush()

    # Prevent duplicate registration
    existing = WorkshopRegistration.query.filter_by(
        workshop_id=w.id, email=email
    ).first()
    if existing:
        return jsonify({'message': 'Already registered', 'registration_id': existing.id}), 200

    reg = WorkshopRegistration(
        workshop_id=w.id,
        learner_id=learner.id,
        name=name,
        email=email,
        phone=data.get('phone', ''),
        company=data.get('company', ''),
        job_title=data.get('job_title', ''),
        status='pending',
        payment_status='free' if w.is_free else 'pending',
        source='website',
        confirmation_token=secrets.token_urlsafe(32),
    )
    db.session.add(reg)
    db.session.commit()

    return jsonify({
        'message': 'Registration successful',
        'registration_id': reg.id,
        'confirmation_token': reg.confirmation_token,
    }), 201
