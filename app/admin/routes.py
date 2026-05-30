from flask import render_template, abort
from flask_login import login_required, current_user
from . import admin_bp
from app.workshops.models import Workshop, Learner
from app.organizations.models import Organization
from app.crm_client.client import fetch_pulse_programs

@admin_bp.before_request
@login_required
def require_admin():
    if current_user.role not in ['admin', 'super_admin']:
        abort(403)

@admin_bp.route('/dashboard')
def dashboard():
    # Gather high-level metrics for the Enterprise Air Traffic Control view
    active_workshops = Workshop.query.filter(Workshop.status.in_(['published', 'draft'])).order_by(Workshop.start_date.desc()).all()
    active_workshops_count = len(active_workshops)
    completed_workshops_count = Workshop.query.filter_by(status='completed').count()
    
    learners_count = Learner.query.count()
    orgs_count = Organization.query.count()
    
    # External Training Management Cohorts from Pulse CRM (excluding those converted to standalone LMS workshops)
    pulse_programs = fetch_pulse_programs()
    lms_managed_crm_ids = {w.crm_engagement_id for w in Workshop.query.filter(Workshop.crm_engagement_id.isnot(None)).all()}
    cohort_programs = [p for p in pulse_programs if p.get('id') not in lms_managed_crm_ids]
    
    active_programs = [p for p in cohort_programs if p.get('status', '').upper() not in ['CLOSED', 'DEAD']]
    completed_programs = [p for p in cohort_programs if p.get('status', '').upper() in ['COMPLETED', 'DELIVERED', 'CLOSED']]
    
    # Aggregations for Chart 1: Program Status Distribution
    program_statuses = {}
    for p in cohort_programs:
        st = p.get('status', 'Active').title()
        program_statuses[st] = program_statuses.get(st, 0) + 1
        
    # Aggregations for Chart 2: Infrastructure Requirements (Labs vs Assessments)
    labs_count = sum(1 for p in cohort_programs if p.get('requires_lab'))
    assessments_count = sum(1 for p in cohort_programs if p.get('requires_assessment'))
    both_count = sum(1 for p in cohort_programs if p.get('requires_lab') and p.get('requires_assessment'))
    
    return render_template(
        'admin/dashboard.html',
        active_workshops=active_workshops[:6], # Top 6 for the live operations precision table
        active_workshops_count=active_workshops_count,
        completed_workshops_count=completed_workshops_count,
        learners_count=learners_count,
        orgs_count=orgs_count,
        active_programs=active_programs[:6], # Top 6 for the active cohorts precision table
        active_programs_count=len(active_programs),
        completed_programs_count=len(completed_programs),
        labs_count=labs_count,
        assessments_count=assessments_count,
        both_count=both_count,
        program_statuses=program_statuses
    )
