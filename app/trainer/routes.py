"""
Trainer Portal Routes
Views are protected by @trainer_required.
Trainers are authenticated via CRM and have a session object.
"""
from functools import wraps
from flask import render_template, redirect, url_for, flash, abort, request, session
from flask_login import login_required, current_user
from app.trainer import trainer_portal_bp
from app.workshops.models import (
    Workshop, WorkshopRegistration, WorkshopTrainer,
    WorkshopSession, WorkshopDocument
)
from app.core.extensions import db
from app.crm_client import client as crm

def trainer_required(f):
    """Guard: only trainers can access these views."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        user_data = session.get('_lms_user', {})
        if user_data.get('role') != 'trainer':
            flash('Access restricted to trainers.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

def _get_crm_trainer():
    """Fetch the Trainer data from CRM using the cached ID in session."""
    user_data = session.get('_lms_user', {})
    trainer_id = user_data.get('crm_trainer_id')
    if not trainer_id:
        return None
    return crm.get_trainer(trainer_id)

@trainer_portal_bp.route('/')
@trainer_required
def dashboard():
    user_data = session.get('_lms_user', {})
    trainer_id = user_data.get('crm_trainer_id')
    
    # If no ID, return empty lists to avoid DB query errors
    if not trainer_id:
        return render_template('trainer/dashboard.html', upcoming=[], past=[])

    # Find workshops where this trainer is assigned
    workshop_ids = [wt.workshop_id for wt in WorkshopTrainer.query.filter_by(crm_trainer_id=trainer_id).all()]
    workshops = Workshop.query.filter(Workshop.id.in_(workshop_ids)).order_by(Workshop.start_date.desc()).all()
    
    # Split into upcoming and past
    from datetime import date
    today = date.today()
    upcoming = [w for w in workshops if w.start_date >= today]
    past = [w for w in workshops if w.start_date < today]
    
    return render_template(
        'trainer/dashboard.html',
        upcoming=upcoming,
        past=past
    )

@trainer_portal_bp.route('/workshop/<int:workshop_id>')
@trainer_required
def workshop_detail(workshop_id):
    user_data = session.get('_lms_user', {})
    trainer_id = user_data.get('crm_trainer_id')
    # Verify assignment
    assignment = WorkshopTrainer.query.filter_by(workshop_id=workshop_id, crm_trainer_id=trainer_id).first()
    if not assignment:
        abort(403)
        
    workshop = Workshop.query.get_or_404(workshop_id)
    registrations = WorkshopRegistration.query.filter_by(workshop_id=workshop_id).all()
    documents = WorkshopDocument.query.filter_by(workshop_id=workshop_id).all()
    
    return render_template(
        'trainer/workshop_detail.html',
        workshop=workshop,
        registrations=registrations,
        documents=documents
    )

@trainer_portal_bp.route('/workshop/<int:workshop_id>/attendance', methods=['POST'])
@trainer_required
def update_attendance(workshop_id):
    user_data = session.get('_lms_user', {})
    trainer_id = user_data.get('crm_trainer_id')
    # Verify assignment
    assignment = WorkshopTrainer.query.filter_by(workshop_id=workshop_id, crm_trainer_id=trainer_id).first()
    if not assignment:
        abort(403)
        
    registration_id = request.form.get('registration_id')
    status = request.form.get('status') # confirmed, attended, cancelled
    
    reg = WorkshopRegistration.query.get_or_404(registration_id)
    if reg.workshop_id != workshop_id:
        abort(400)
        
    reg.status = status
    db.session.commit()
    
    flash(f'Attendance updated for {reg.name}.', 'success')
    return redirect(url_for('trainer_portal.workshop_detail', workshop_id=workshop_id))

@trainer_portal_bp.route('/profile')
@trainer_required
def profile():
    trainer = _get_crm_trainer()
    if not trainer:
        flash('Trainer profile not found in CRM.', 'danger')
        return redirect(url_for('trainer_portal.dashboard'))
        
    return render_template('trainer/profile.html', trainer=trainer)
