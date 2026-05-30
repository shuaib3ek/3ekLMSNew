from flask import render_template, abort, request
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from app.workshops.models import Learner, WorkshopRegistration, Certificate
from app.training_management.models import ProgramParticipant, ProgramConfig
from app.assessments.models import AssessmentAssignment
from app.organizations.models import Organization
from app.core.tenancy import scoped_query
from app.crm_client.client import fetch_pulse_programs

from . import learners_bp


@learners_bp.before_request
@login_required
def require_admin():
    if current_user.role not in ['admin', 'super_admin']:
        abort(403)


@learners_bp.route('/')
def list_learners():
    """Global Learner Roster with High-Scale Pagination & Advanced Filtering."""
    q = request.args.get('q', '').strip()
    org_id = request.args.get('org', '')
    program_id = request.args.get('program', '')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)

    query = scoped_query(Learner).options(
        joinedload(Learner.registrations).joinedload(WorkshopRegistration.workshop)
    )

    if q:
        query = query.filter(Learner.name.ilike(f'%{q}%') | Learner.email.ilike(f'%{q}%') | Learner.company.ilike(f'%{q}%'))
    
    if org_id and org_id != 'all':
        query = query.filter_by(organization_id=org_id)

    if program_id and program_id != 'all':
        query = query.join(ProgramParticipant, Learner.id == ProgramParticipant.learner_id).filter(
            ProgramParticipant.crm_engagement_id == int(program_id)
        )

    # Server-side pagination
    pagination = query.order_by(Learner.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    learners = pagination.items
    
    # Get all organizations for the filter dropdown
    organizations = Organization.query.order_by(Organization.name).all()

    # Fetch active training programs where Virtual Labs or Assessments are enabled
    configs = ProgramConfig.query.filter((ProgramConfig.labs_enabled == True) | (ProgramConfig.assessments_enabled == True)).all()
    enabled_ids = {c.crm_engagement_id for c in configs}
    
    all_programs = fetch_pulse_programs()
    training_programs = [p for p in all_programs if p.get('id') in enabled_ids]

    return render_template(
        'learners/list.html', 
        learners=learners, 
        pagination=pagination,
        organizations=organizations,
        training_programs=training_programs,
        search_query=q,
        selected_org=org_id,
        selected_program=program_id,
        per_page=per_page
    )


@learners_bp.route('/<int:learner_id>/')
def learner_profile(learner_id):
    """Admin view of a single learner's full profile."""
    learner = scoped_query(Learner).options(
        joinedload(Learner.registrations).joinedload(WorkshopRegistration.workshop)
    ).filter_by(id=learner_id).first_or_404()

    certificates = scoped_query(Certificate).filter_by(learner_id=learner_id).all()

    # Program assignments (Labs & Assessments via ProgramParticipant)
    program_assignments = ProgramParticipant.query.filter_by(learner_id=learner_id).all()

    # Assessment results
    assessment_results = (
        AssessmentAssignment.query
        .join(ProgramParticipant, AssessmentAssignment.participant_id == ProgramParticipant.id)
        .filter(ProgramParticipant.learner_id == learner_id)
        .all()
    )

    return render_template(
        'learners/profile.html',
        learner=learner,
        certificates=certificates,
        program_assignments=program_assignments,
        assessment_results=assessment_results
    )
