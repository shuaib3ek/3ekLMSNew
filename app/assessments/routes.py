import os
from flask import render_template, request, flash, redirect, url_for, current_app, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from . import assessments_bp
from app.core.extensions import db
from app.training_management.models import ProgramConfig, ProgramParticipant
from app.assessments.models import ProgramAssessment, AssessmentAssignment
from app.crm_client.client import fetch_pulse_program_detail

@assessments_bp.route('/')
@login_required
def list_assessments():
    """List all programs that have assessments enabled."""
    configs = ProgramConfig.query.filter_by(assessments_enabled=True).all()
    enabled_ids = [c.crm_engagement_id for c in configs]
    
    # We fetch all pulse programs and filter, or fetch individually.
    from app.crm_client.client import fetch_pulse_programs
    all_programs = fetch_pulse_programs()
    programs = [p for p in all_programs if p.get('id') in enabled_ids]
    
    return render_template('assessments/list.html', programs=programs)

@assessments_bp.route('/<int:crm_engagement_id>/')
@login_required
def detail(crm_engagement_id):
    """View and manage assessments for a specific program."""
    config = ProgramConfig.query.filter_by(crm_engagement_id=crm_engagement_id, assessments_enabled=True).first()
    if not config:
        flash("Assessments are not enabled for this program.", "warning")
        return redirect(url_for('assessments.list_assessments'))
        
    program = fetch_pulse_program_detail(crm_engagement_id)
    if not program:
        abort(404)
        
    assessments = ProgramAssessment.query.filter_by(crm_engagement_id=crm_engagement_id).all()
    participants = ProgramParticipant.query.filter_by(crm_engagement_id=crm_engagement_id).all()
    
    # Pre-fetch assignments
    assignments = AssessmentAssignment.query.join(ProgramAssessment).filter(ProgramAssessment.crm_engagement_id == crm_engagement_id).all()
    
    return render_template('assessments/detail.html', program=program, assessments=assessments, participants=participants, assignments=assignments)

@assessments_bp.route('/<int:crm_engagement_id>/upload', methods=['POST'])
@login_required
def upload_assessment(crm_engagement_id):
    """Upload a new assessment file."""
    title = request.form.get('title')
    a_type = request.form.get('type', 'document')
    
    if 'file' not in request.files:
        flash('No file part', 'error')
        return redirect(url_for('assessments.detail', crm_engagement_id=crm_engagement_id))
        
    file = request.files['file']
    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(url_for('assessments.detail', crm_engagement_id=crm_engagement_id))
        
    if file:
        filename = secure_filename(file.filename)
        upload_path = os.path.join(current_app.root_path, 'static', 'uploads', 'assessments')
        os.makedirs(upload_path, exist_ok=True)
        file.save(os.path.join(upload_path, filename))
        
        file_url = url_for('static', filename=f'uploads/assessments/{filename}')
        
        assessment = ProgramAssessment(
            crm_engagement_id=crm_engagement_id,
            title=title,
            file_url=file_url,
            type=a_type
        )
        db.session.add(assessment)
        db.session.commit()
        flash('Assessment uploaded successfully.', 'success')
        
    return redirect(url_for('assessments.detail', crm_engagement_id=crm_engagement_id))

@assessments_bp.route('/<int:crm_engagement_id>/assign', methods=['POST'])
@login_required
def assign_assessment(crm_engagement_id):
    """Assign an assessment to selected participants."""
    assessment_id = request.form.get('assessment_id')
    participant_ids = request.form.getlist('participant_ids')
    
    if not assessment_id or not participant_ids:
        flash('Please select an assessment and at least one participant.', 'error')
        return redirect(url_for('assessments.detail', crm_engagement_id=crm_engagement_id))
        
    for pid in participant_ids:
        # Check if already assigned
        existing = AssessmentAssignment.query.filter_by(assessment_id=assessment_id, participant_id=pid).first()
        if not existing:
            assignment = AssessmentAssignment(
                assessment_id=assessment_id,
                participant_id=pid
            )
            db.session.add(assignment)
            
    db.session.commit()
    flash(f'Assessment assigned to {len(participant_ids)} participants.', 'success')
    return redirect(url_for('assessments.detail', crm_engagement_id=crm_engagement_id))
