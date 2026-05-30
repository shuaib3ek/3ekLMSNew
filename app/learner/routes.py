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
from app.core.tenancy import scoped_query


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
    return scoped_query(Learner).filter_by(id=current_user.id).first()


# ─── Dashboard ────────────────────────────────────────────────────────────────

@learner_portal_bp.route('/')
@learner_required
def dashboard():
    learner = _get_learner()
    if not learner:
        flash('Learner account not found.', 'danger')
        return redirect(url_for('auth.logout'))

    registrations = (
        scoped_query(WorkshopRegistration)
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

    certificates = scoped_query(Certificate).filter_by(learner_id=learner.id).all()

    # ── Phase 3: Program Assignments (Labs & Assessments) ──
    from app.training_management.models import ProgramParticipant
    program_assignments = ProgramParticipant.query.filter_by(learner_id=learner.id).all()

    return render_template(
        'learner/dashboard.html',
        learner=learner,
        upcoming=upcoming,
        past=past,
        certificates=certificates,
        program_assignments=program_assignments
    )


# ─── Workshop Detail (Learner View) ───────────────────────────────────────────

@learner_portal_bp.route('/workshop/<int:workshop_id>')
@learner_required
def workshop_detail(workshop_id):
    learner = _get_learner()
    registration = scoped_query(WorkshopRegistration).filter_by(
        learner_id=learner.id, workshop_id=workshop_id
    ).first_or_404()

    workshop = registration.workshop
    # Note: WorkshopDocument doesn't have organization_id yet, but it's linked to Workshop which IS scoped.
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
    certs = scoped_query(Certificate).filter_by(learner_id=learner.id).all()
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
            if '_lms_user' in session:
                u = session['_lms_user']
                name_parts = learner.name.split(' ', 1) if learner.name else ['', '']
                u['first_name'] = name_parts[0]
                u['last_name'] = name_parts[1] if len(name_parts) > 1 else ''
                session['_lms_user'] = u
                session.modified = True

            flash('Profile updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating profile: {str(e)}', 'danger')

        return redirect(url_for('learner_portal.profile'))

    return render_template('learner/profile.html', learner=learner)


@learner_portal_bp.route('/assessment/submit/<int:assignment_id>', methods=['POST'])
@learner_required
def submit_assessment(assignment_id):
    from app.assessments.models import AssessmentAssignment
    assignment = AssessmentAssignment.query.get_or_404(assignment_id)
    
    # Security Check: Ensure assignment belongs to this learner
    from app.training_management.models import ProgramParticipant
    participant = ProgramParticipant.query.get(assignment.participant_id)
    if not participant or participant.learner_id != current_user.id:
        abort(403)
        
    assignment.status = 'submitted'
    try:
        db.session.commit()
        flash(f'Assessment submitted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error submitting assessment: {str(e)}', 'danger')
        
    return redirect(url_for('learner_portal.dashboard'))
