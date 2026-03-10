"""
Client / Corporate Point-of-Contact Portal Routes
Views are protected by @client_required.
Clients authenticate via CRM (Contact model) with real passwords.

Data sources:
  - CRM Pulse:  programs (engagements), open requests (inquiries), account manager, company profile
  - LMS:        public discovery workshops, enrolled learners per workshop
"""
from functools import wraps
from datetime import date
from flask import render_template, redirect, url_for, flash, abort, request, session, jsonify
from flask_login import login_required
from app.client import client_portal_bp
from app.workshops.models import Workshop, WorkshopRegistration, WorkshopDocument, Learner
from app.core.extensions import db
from app.crm_client import client as crm


# ─── Auth Guard ───────────────────────────────────────────────────────────────

def client_required(f):
    """Guard: only authenticated corporate clients can access these views."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        user_data = session.get('_lms_user', {})
        if user_data.get('role') != 'client':
            flash('Access restricted to corporate clients.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _user():
    return session.get('_lms_user', {})


def _client_id():
    return _user().get('crm_client_id')


def _client_data():
    cid = _client_id()
    return crm.get_client(cid) if cid else {}


# ─── Dashboard ────────────────────────────────────────────────────────────────

@client_portal_bp.route('/')
@client_required
def dashboard():
    client_id = _client_id()
    if not client_id:
        flash('Your account is not linked to a company profile.', 'warning')
        return redirect(url_for('auth.logout'))

    client_data = _client_data() or {}
    company_name = client_data.get('name', 'Your Company')

    # CRM programs — split active vs past
    all_programs = crm.get_programs_for_client(client_id)
    active_programs = [p for p in all_programs if p.get('status') in ('SCHEDULED', 'IN PROGRESS', 'DRAFT')]
    past_programs = [p for p in all_programs if p.get('status') in ('COMPLETED', 'AWAITING FINANCIALS', 'CLOSED', 'CANCELLED')]

    # CRM open training requests
    open_requests = crm.get_open_requests(client_id)

    # Account manager
    account_manager = crm.get_account_manager(client_id)

    # Summary stats
    total_programs = len(all_programs)
    unique_topics = len({p.get('topic') for p in all_programs if p.get('topic')})
    total_participants = sum((p.get('participants') or 0) for p in past_programs)

    return render_template(
        'client/dashboard.html',
        company_name=company_name,
        active_programs=active_programs,
        past_programs=past_programs,
        open_requests=open_requests,
        account_manager=account_manager,
        stats={
            'total_programs': total_programs,
            'active': len(active_programs),
            'past': len(past_programs),
            'unique_topics': unique_topics,
            'total_participants': total_participants,
            'open_requests': len(open_requests),
        }
    )


# ─── Programs List ────────────────────────────────────────────────────────────

@client_portal_bp.route('/programs')
@client_required
def programs():
    client_id = _client_id()
    if not client_id:
        abort(403)

    client_data = _client_data() or {}
    company_name = client_data.get('name', 'Your Company')

    all_programs = crm.get_programs_for_client(client_id)
    scheduled = [p for p in all_programs if p.get('status') in ('SCHEDULED', 'DRAFT')]
    active = [p for p in all_programs if p.get('status') == 'IN PROGRESS']
    past = [p for p in all_programs if p.get('status') in ('COMPLETED', 'AWAITING FINANCIALS', 'CLOSED', 'CANCELLED')]

    return render_template(
        'client/programs.html',
        company_name=company_name,
        scheduled_programs=scheduled,
        active_programs=active,
        past_programs=past,
    )


# ─── Program Detail (CRM Engagement) ─────────────────────────────────────────

@client_portal_bp.route('/programs/<int:engagement_id>')
@client_required
def program_detail(engagement_id):
    client_id = _client_id()
    if not client_id:
        abort(403)

    program = crm.get_program_detail(engagement_id)
    if not program:
        abort(404)

    return render_template('client/program_detail.html', program=program)


# ─── Open Training Requests ───────────────────────────────────────────────────

@client_portal_bp.route('/requests')
@client_required
def open_requests():
    client_id = _client_id()
    if not client_id:
        abort(403)

    client_data = _client_data() or {}
    company_name = client_data.get('name', 'Your Company')
    requests_list = crm.get_open_requests(client_id)

    return render_template(
        'client/requests.html',
        company_name=company_name,
        requests=requests_list,
    )


# ─── Discover Public Workshops ────────────────────────────────────────────────

@client_portal_bp.route('/workshops')
@client_required
def discover():
    today = date.today()
    public_workshops = (
        Workshop.query
        .filter_by(is_public=True, status='published')
        .filter(Workshop.start_date >= today)
        .order_by(Workshop.start_date.asc())
        .all()
    )
    return render_template('client/discover.html', workshops=public_workshops)


# ─── LMS Workshop Detail (Enrollment Roster) ─────────────────────────────────

@client_portal_bp.route('/workshop/<int:workshop_id>')
@client_required
def workshop_detail(workshop_id):
    client_id = _client_id()
    if not client_id:
        abort(403)

    workshop = Workshop.query.get_or_404(workshop_id)
    client_data = _client_data() or {}
    company_name = client_data.get('name', 'Your Company')

    is_bespoke = (workshop.crm_client_id == client_id)

    if is_bespoke:
        registrations = workshop.registrations
    else:
        learners_in_company = Learner.query.filter_by(crm_client_id=client_id).all()
        learner_ids = {l.id for l in learners_in_company}
        registrations = [
            r for r in workshop.registrations
            if r.learner_id in learner_ids or (r.company and company_name.lower() in (r.company or '').lower())
        ]

    if not is_bespoke and not registrations:
        abort(403)

    # Progress stats
    total = len(registrations)
    attended = len([r for r in registrations if r.status in ('attended', 'completed')])
    progress = int(attended / total * 100) if total > 0 else 0

    documents = WorkshopDocument.query.filter_by(workshop_id=workshop_id).all() if is_bespoke else []

    return render_template(
        'client/workshop_detail.html',
        workshop=workshop,
        registrations=registrations,
        documents=documents,
        is_bespoke=is_bespoke,
        stats={'total': total, 'attended': attended, 'progress': progress}
    )


# ─── Profile & Account Manager ────────────────────────────────────────────────

@client_portal_bp.route('/profile')
@client_required
def profile():
    client_id = _client_id()
    user = _user()
    client_data = _client_data() if client_id else {}
    account_manager = crm.get_account_manager(client_id) if client_id else None
    return render_template(
        'client/profile.html',
        client=client_data,
        account_manager=account_manager,
        contact=user,
    )
