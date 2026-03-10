"""
Learner Portal Routes
All views are protected by @learner_required.
Only users with role='learner' in their session can access these.
"""
from functools import wraps
from flask import render_template, redirect, url_for, flash, abort, request
from flask_login import login_required, current_user
from app.learner import learner_portal_bp
from app.workshops.models import (
    Learner, WorkshopRegistration, Workshop,
    WorkshopDocument, WorkshopVideoProgress, Certificate
)
from app.core.extensions import db


def learner_required(f):
    """Guard: only learners can access these views."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role != 'learner':
            flash('Access restricted to learners.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def _get_learner():
    """Fetch the Learner DB row for the current logged-in learner."""
    return Learner.query.get(current_user.id)


# ─── Dashboard ────────────────────────────────────────────────────────────────

@learner_portal_bp.route('/')
@learner_required
def dashboard():
    learner = _get_learner()
    if not learner:
        flash('Learner account not found.', 'danger')
        return redirect(url_for('auth.logout'))

    registrations = (
        WorkshopRegistration.query
        .filter_by(learner_id=learner.id)
        .join(Workshop)
        .order_by(Workshop.start_date.desc())
        .all()
    )

    # Split into upcoming and past
    from datetime import date
    today = date.today()
    upcoming = [r for r in registrations if r.workshop.start_date >= today and r.status != 'cancelled']
    past     = [r for r in registrations if r.workshop.start_date < today or r.status == 'cancelled']

    certificates = Certificate.query.filter_by(learner_id=learner.id).all()

    return render_template(
        'learner/dashboard.html',
        learner=learner,
        upcoming=upcoming,
        past=past,
        certificates=certificates,
    )


# ─── Workshop Detail (Learner View) ───────────────────────────────────────────

@learner_portal_bp.route('/workshop/<int:workshop_id>')
@learner_required
def workshop_detail(workshop_id):
    learner = _get_learner()
    registration = WorkshopRegistration.query.filter_by(
        learner_id=learner.id, workshop_id=workshop_id
    ).first_or_404()

    workshop = registration.workshop
    documents = WorkshopDocument.query.filter_by(workshop_id=workshop_id).all()

    # Sessions with video progress
    sessions_data = []
    for session in workshop.sessions:
        progress = WorkshopVideoProgress.query.filter_by(
            learner_id=learner.id, session_id=session.id
        ).first()
        sessions_data.append({
            'session': session,
            'progress': progress,
        })

    return render_template(
        'learner/workshop_detail.html',
        learner=learner,
        registration=registration,
        workshop=workshop,
        documents=documents,
        sessions_data=sessions_data,
    )


# ─── Certificates ─────────────────────────────────────────────────────────────

@learner_portal_bp.route('/certificates')
@learner_required
def certificates():
    learner = _get_learner()
    certs = Certificate.query.filter_by(learner_id=learner.id).all()
    return render_template('learner/certificates.html', learner=learner, certificates=certs)


# ─── Profile ──────────────────────────────────────────────────────────────────

@learner_portal_bp.route('/profile', methods=['GET', 'POST'])
@learner_required
def profile():
    learner = _get_learner()
    if not learner:
        flash('Learner account not found.', 'danger')
        return redirect(url_for('auth.logout'))

    if request.method == 'POST':
        # Update details
        learner.name = request.form.get('name', learner.name)
        learner.phone = request.form.get('phone', learner.phone)
        learner.company = request.form.get('company', learner.company)
        learner.job_title = request.form.get('job_title', learner.job_title)

        try:
            db.session.commit()
            
            # Also update session cache if it exists (for the header chip)
            from flask import session
            if 'user_data' in session: # Check current cached_user key used in auth/routes.py
                u = session['user_data']
                u['full_name'] = learner.name
                u['first_name'] = learner.name.split()[0] if learner.name else '?'
                session['user_data'] = u
            
            # Check for alternate session key 'cached_user'
            if 'cached_user' in session:
                u = session['cached_user']
                u['full_name'] = learner.name
                u['first_name'] = learner.name.split()[0] if learner.name else '?'
                session['cached_user'] = u

            flash('Profile updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating profile: {str(e)}', 'danger')

        return redirect(url_for('learner_portal.profile'))

    return render_template('learner/profile.html', learner=learner)
