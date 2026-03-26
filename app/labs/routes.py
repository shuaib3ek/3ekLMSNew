from flask import render_template, request, flash, redirect, url_for, abort
from flask_login import login_required, current_user
from . import labs_bp
from app.core.extensions import db
from app.training_management.models import ProgramConfig, ProgramParticipant
from app.labs.models import ProgramLab, LabAssignment
from app.crm_client.client import fetch_pulse_program_detail
from datetime import datetime

@labs_bp.route('/')
@login_required
def list_labs():
    """List all programs that have labs enabled."""
    configs = ProgramConfig.query.filter_by(labs_enabled=True).all()
    enabled_ids = [c.crm_engagement_id for c in configs]
    
    from app.crm_client.client import fetch_pulse_programs
    all_programs = fetch_pulse_programs()
    programs = [p for p in all_programs if p.get('id') in enabled_ids]
    
    return render_template('labs/list.html', programs=programs)

@labs_bp.route('/<int:crm_engagement_id>/')
@login_required
def detail(crm_engagement_id):
    """View and manage labs for a specific program."""
    config = ProgramConfig.query.filter_by(crm_engagement_id=crm_engagement_id, labs_enabled=True).first()
    if not config:
        flash("Labs are not enabled for this program.", "warning")
        return redirect(url_for('labs.list_labs'))
        
    program = fetch_pulse_program_detail(crm_engagement_id)
    if not program:
        abort(404)
        
    labs = ProgramLab.query.filter_by(crm_engagement_id=crm_engagement_id).all()
    participants = ProgramParticipant.query.filter_by(crm_engagement_id=crm_engagement_id).all()
    
    # Pre-fetch assignments
    assignments = LabAssignment.query.join(ProgramLab).filter(ProgramLab.crm_engagement_id == crm_engagement_id).all()
    
    return render_template('labs/detail.html', program=program, labs=labs, participants=participants, assignments=assignments)

@labs_bp.route('/<int:crm_engagement_id>/create', methods=['POST'])
@login_required
def create_lab(crm_engagement_id):
    """Create a new virtual lab entry."""
    title = request.form.get('title')
    lab_url = request.form.get('lab_url')
    access_start = request.form.get('access_start')
    access_end = request.form.get('access_end')
    
    if not title or not lab_url:
        flash('Title and URL are required.', 'error')
        return redirect(url_for('labs.detail', crm_engagement_id=crm_engagement_id))
        
    # Optional date parsing
    start_dt = None
    end_dt = None
    try:
        if access_start: start_dt = datetime.strptime(access_start, '%Y-%m-%dT%H:%M')
        if access_end: end_dt = datetime.strptime(access_end, '%Y-%m-%dT%H:%M')
    except ValueError:
        pass # ignore format errors for now
        
    lab = ProgramLab(
        crm_engagement_id=crm_engagement_id,
        title=title,
        lab_url=lab_url,
        access_start=start_dt,
        access_end=end_dt
    )
    db.session.add(lab)
    db.session.commit()
    flash('Lab environment configured successfully.', 'success')
        
    return redirect(url_for('labs.detail', crm_engagement_id=crm_engagement_id))

@labs_bp.route('/<int:crm_engagement_id>/assign', methods=['POST'])
@login_required
def assign_lab(crm_engagement_id):
    """Assign a lab environment to selected participants."""
    lab_id = request.form.get('lab_id')
    participant_ids = request.form.getlist('participant_ids')
    
    if not lab_id or not participant_ids:
        flash('Please select a lab and at least one participant.', 'error')
        return redirect(url_for('labs.detail', crm_engagement_id=crm_engagement_id))
        
    for pid in participant_ids:
        existing = LabAssignment.query.filter_by(lab_id=lab_id, participant_id=pid).first()
        if not existing:
            assignment = LabAssignment(
                lab_id=lab_id,
                participant_id=pid
            )
            db.session.add(assignment)
            
    db.session.commit()
    flash(f'Lab environment assigned to {len(participant_ids)} participants.', 'success')
    return redirect(url_for('labs.detail', crm_engagement_id=crm_engagement_id))
