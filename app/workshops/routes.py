"""
Workshops Module — Admin & Public Routes
LMS-owned. No imports from 3EK-Pulse (CRM).
Trainer/Contact resolution uses crm_client HTTP calls.
"""
import json
import re
import uuid
import secrets
import csv
import io
from datetime import datetime, date, timedelta
from flask import (
    render_template, request, redirect, url_for, flash,
    jsonify, Response, current_app, abort
)
from flask_login import login_required, current_user

from . import workshops_bp
from .models import (
    Workshop, WorkshopTrainer, WorkshopSession,
    WorkshopRegistration, WorkshopEmailLog, WorkshopDocument
)
from app.core.extensions import db
from app.crm_client import get_trainer, list_trainers, get_contact


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return re.sub(r'^-+|-+$', '', text)


def _make_slug(title):
    base = _slugify(title)
    slug = base
    counter = 1
    while Workshop.query.filter_by(slug=slug).first():
        slug = f'{base}-{counter}'
        counter += 1
    return slug


def _admin_required():
    if current_user.role not in ['admin', 'super_admin']:
        abort(403)


# ─── List ─────────────────────────────────────────────────────────────────────

@workshops_bp.route('/')
@login_required
def list_workshops():
    status_filter = request.args.get('status', 'all')
    query = Workshop.query.order_by(Workshop.start_date.asc())
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    workshops = query.all()
    return render_template('workshops/list.html', workshops=workshops, status_filter=status_filter)


# ─── Create ───────────────────────────────────────────────────────────────────

@workshops_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_workshop():
    _admin_required()
    # Trainers come from CRM via HTTP — no direct DB import
    trainers = list_trainers(status='active')

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('Workshop title is required.', 'danger')
            return render_template('workshops/form.html', workshop=None, trainers=trainers)

        try:
            start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
            end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
        except (ValueError, TypeError):
            flash('Invalid date format.', 'danger')
            return render_template('workshops/form.html', workshop=None, trainers=trainers)

        reg_deadline_str = request.form.get('registration_deadline')
        early_bird_deadline_str = request.form.get('early_bird_deadline')
        outcomes_list = [o.strip() for o in request.form.get('outcomes', '').split('\n') if o.strip()]
        fee = request.form.get('fee_per_person') or 0
        early_bird_fee = request.form.get('early_bird_fee') or None

        workshop = Workshop(
            title=title,
            slug=_make_slug(title),
            subtitle=request.form.get('subtitle', ''),
            category=request.form.get('category', 'General'),
            description=request.form.get('description', ''),
            outcomes=json.dumps(outcomes_list),
            target_audience=request.form.get('target_audience', ''),
            agenda=request.form.get('agenda', ''),
            start_date=start_date,
            end_date=end_date,
            start_time=request.form.get('start_time', '09:00 AM IST'),
            end_time=request.form.get('end_time', '05:00 PM IST'),
            duration_display=request.form.get('duration_display', ''),
            registration_deadline=datetime.strptime(reg_deadline_str, '%Y-%m-%d').date() if reg_deadline_str else None,
            mode=request.form.get('mode', 'online'),
            venue=request.form.get('venue', ''),
            meeting_link=request.form.get('meeting_link', ''),
            total_seats=int(request.form.get('total_seats') or 30),
            fee_per_person=float(fee),
            is_free=(float(fee) == 0),
            early_bird_fee=float(early_bird_fee) if early_bird_fee else None,
            early_bird_deadline=datetime.strptime(early_bird_deadline_str, '%Y-%m-%d').date() if early_bird_deadline_str else None,
            banner_image_url=request.form.get('banner_image_url', ''),
            brochure_url=request.form.get('brochure_url', ''),
            status='draft',
            crm_owner_id=current_user.id,
        )
        db.session.add(workshop)
        db.session.flush()
        _sync_sessions(workshop, request.form)
        db.session.commit()
        flash(f'Workshop "{workshop.title}" created successfully.', 'success')
        return redirect(url_for('workshops.detail_workshop', workshop_id=workshop.id))

    return render_template('workshops/form.html', workshop=None, trainers=trainers)


# ─── Detail ───────────────────────────────────────────────────────────────────

@workshops_bp.route('/<int:workshop_id>')
@login_required
def detail_workshop(workshop_id):
    workshop = Workshop.query.get_or_404(workshop_id)
    # Trainers from CRM via HTTP
    all_trainers = list_trainers(status='active')
    assigned_trainer_ids = {wt.crm_trainer_id for wt in workshop.trainers}
    return render_template(
        'workshops/detail.html',
        workshop=workshop,
        all_trainers=all_trainers,
        assigned_trainer_ids=assigned_trainer_ids,
    )


# ─── Edit ─────────────────────────────────────────────────────────────────────

@workshops_bp.route('/<int:workshop_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_workshop(workshop_id):
    _admin_required()
    workshop = Workshop.query.get_or_404(workshop_id)
    trainers = list_trainers(status='active')

    if request.method == 'POST':
        outcomes_list = [o.strip() for o in request.form.get('outcomes', '').split('\n') if o.strip()]
        fee = request.form.get('fee_per_person') or 0
        early_bird_fee = request.form.get('early_bird_fee') or None
        reg_deadline_str = request.form.get('registration_deadline')
        early_bird_deadline_str = request.form.get('early_bird_deadline')

        try:
            start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
            end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
        except (ValueError, TypeError):
            flash('Invalid date format.', 'danger')
            return render_template('workshops/form.html', workshop=workshop, trainers=trainers)

        workshop.title = request.form.get('title', '').strip()
        workshop.subtitle = request.form.get('subtitle', '')
        workshop.category = request.form.get('category', 'General')
        workshop.description = request.form.get('description', '')
        workshop.outcomes = json.dumps(outcomes_list)
        workshop.target_audience = request.form.get('target_audience', '')
        workshop.agenda = request.form.get('agenda', '')
        workshop.start_date = start_date
        workshop.end_date = end_date
        workshop.start_time = request.form.get('start_time', '09:00 AM IST')
        workshop.end_time = request.form.get('end_time', '05:00 PM IST')
        workshop.duration_display = request.form.get('duration_display', '')
        workshop.registration_deadline = datetime.strptime(reg_deadline_str, '%Y-%m-%d').date() if reg_deadline_str else None
        workshop.mode = request.form.get('mode', 'online')
        workshop.venue = request.form.get('venue', '')
        workshop.meeting_link = request.form.get('meeting_link', '')
        workshop.total_seats = int(request.form.get('total_seats') or 30)
        workshop.fee_per_person = float(fee)
        workshop.is_free = (float(fee) == 0)
        workshop.early_bird_fee = float(early_bird_fee) if early_bird_fee else None
        workshop.early_bird_deadline = datetime.strptime(early_bird_deadline_str, '%Y-%m-%d').date() if early_bird_deadline_str else None
        workshop.banner_image_url = request.form.get('banner_image_url', '')
        workshop.brochure_url = request.form.get('brochure_url', '')
        workshop.is_public = bool(request.form.get('is_public'))
        workshop.featured = bool(request.form.get('featured'))

        WorkshopSession.query.filter_by(workshop_id=workshop.id).delete()
        db.session.flush()
        _sync_sessions(workshop, request.form)
        db.session.commit()
        flash('Workshop updated successfully.', 'success')
        return redirect(url_for('workshops.detail_workshop', workshop_id=workshop.id))

    return render_template('workshops/form.html', workshop=workshop, trainers=trainers)


# ─── Status Change ────────────────────────────────────────────────────────────

@workshops_bp.route('/<int:workshop_id>/status', methods=['GET', 'POST'])
@login_required
def change_status(workshop_id):
    if request.method == 'GET':
        return redirect(url_for('workshops.detail_workshop', workshop_id=workshop_id))
    _admin_required()
    workshop = Workshop.query.get_or_404(workshop_id)
    new_status = request.form.get('status')
    valid = ['draft', 'published', 'completed', 'cancelled']
    if new_status not in valid:
        flash('Invalid status.', 'danger')
        return redirect(url_for('workshops.detail_workshop', workshop_id=workshop_id))
    if new_status == 'published':
        workshop.is_public = True
    elif new_status in ['cancelled', 'completed']:
        workshop.is_public = False
    workshop.status = new_status
    db.session.commit()
    flash(f'Workshop status updated to "{new_status}".', 'success')
    return redirect(url_for('workshops.detail_workshop', workshop_id=workshop_id))


# ─── Trainer Assignment ───────────────────────────────────────────────────────

@workshops_bp.route('/<int:workshop_id>/trainers/add', methods=['POST'])
@login_required
def add_trainer(workshop_id):
    _admin_required()
    workshop = Workshop.query.get_or_404(workshop_id)
    crm_trainer_id = request.form.get('trainer_id', type=int)
    role = request.form.get('role', 'lead')
    fee = request.form.get('trainer_fee') or None

    if not crm_trainer_id:
        flash('No trainer selected.', 'danger')
        return redirect(url_for('workshops.detail_workshop', workshop_id=workshop_id))

    existing = WorkshopTrainer.query.filter_by(
        workshop_id=workshop_id, crm_trainer_id=crm_trainer_id
    ).first()
    if existing:
        flash('Trainer already assigned to this workshop.', 'warning')
        return redirect(url_for('workshops.detail_workshop', workshop_id=workshop_id))

    wt = WorkshopTrainer(
        workshop_id=workshop_id,
        crm_trainer_id=crm_trainer_id,
        role=role,
        trainer_fee=float(fee) if fee else None,
    )
    db.session.add(wt)
    db.session.commit()
    flash('Trainer assigned to workshop.', 'success')
    return redirect(url_for('workshops.detail_workshop', workshop_id=workshop_id))


@workshops_bp.route('/<int:workshop_id>/trainers/<int:wt_id>/remove', methods=['POST'])
@login_required
def remove_trainer(workshop_id, wt_id):
    _admin_required()
    wt = WorkshopTrainer.query.get_or_404(wt_id)
    db.session.delete(wt)
    db.session.commit()
    flash('Trainer removed from workshop.', 'success')
    return redirect(url_for('workshops.detail_workshop', workshop_id=workshop_id))


@workshops_bp.route('/<int:workshop_id>/trainers/<int:wt_id>/confirm', methods=['POST'])
@login_required
def confirm_trainer(workshop_id, wt_id):
    _admin_required()
    wt = WorkshopTrainer.query.get_or_404(wt_id)
    wt.confirmed = not wt.confirmed
    db.session.commit()
    status = 'confirmed' if wt.confirmed else 'unconfirmed'
    flash(f'Trainer marked as {status}.', 'success')
    return redirect(url_for('workshops.detail_workshop', workshop_id=workshop_id))


# ─── Registrations ────────────────────────────────────────────────────────────

@workshops_bp.route('/<int:workshop_id>/registrations')
@login_required
def registrations(workshop_id):
    workshop = Workshop.query.get_or_404(workshop_id)
    return render_template('workshops/registrations.html', workshop=workshop)


@workshops_bp.route('/<int:workshop_id>/registrations/add', methods=['POST'])
@login_required
def add_registration(workshop_id):
    _admin_required()
    workshop = Workshop.query.get_or_404(workshop_id)
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip().lower()

    if not name or not email:
        flash('Name and email are required.', 'danger')
        return redirect(url_for('workshops.detail_workshop', workshop_id=workshop_id))

    existing = WorkshopRegistration.query.filter_by(workshop_id=workshop_id, email=email).first()
    if existing:
        flash(f'{email} is already registered for this workshop.', 'warning')
        return redirect(url_for('workshops.detail_workshop', workshop_id=workshop_id))

    reg = WorkshopRegistration(
        workshop_id=workshop_id,
        name=name,
        email=email,
        phone=request.form.get('phone', ''),
        company=request.form.get('company', ''),
        job_title=request.form.get('job_title', ''),
        status='confirmed',
        payment_status=request.form.get('payment_status', 'free'),
        source='manual',
        confirmation_token=secrets.token_urlsafe(32),
    )
    db.session.add(reg)
    db.session.commit()
    flash(f'{name} manually registered for workshop.', 'success')
    return redirect(url_for('workshops.detail_workshop', workshop_id=workshop_id))


@workshops_bp.route('/<int:workshop_id>/registrations/<int:reg_id>/status', methods=['GET', 'POST'])
@login_required
def update_registration_status(workshop_id, reg_id):
    if request.method == 'GET':
        return redirect(url_for('workshops.detail_workshop', workshop_id=workshop_id))
    _admin_required()
    reg = WorkshopRegistration.query.get_or_404(reg_id)
    new_status = request.form.get('status')
    if new_status in ['pending', 'confirmed', 'attended', 'cancelled']:
        reg.status = new_status
        db.session.commit()
        flash(f'Registration status updated to {new_status}.', 'success')
    return redirect(url_for('workshops.detail_workshop', workshop_id=workshop_id))


@workshops_bp.route('/<int:workshop_id>/registrations/export')
@login_required
def export_registrations(workshop_id):
    workshop = Workshop.query.get_or_404(workshop_id)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Name', 'Email', 'Phone', 'Company', 'Job Title', 'Status', 'Payment', 'Source', 'Registered At'])
    for r in workshop.registrations:
        writer.writerow([
            r.name, r.email, r.phone or '', r.company or '', r.job_title or '',
            r.status, r.payment_status, r.source,
            r.registered_at.strftime('%Y-%m-%d %H:%M') if r.registered_at else '',
        ])
    output.seek(0)
    return Response(
        output,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=registrations_{workshop.slug}.csv'},
    )


# ─── Public Registration Page ─────────────────────────────────────────────────

@workshops_bp.route('/register/<slug>', methods=['GET', 'POST'])
def register_public(slug):
    workshop = Workshop.query.filter_by(slug=slug).first_or_404()
    if workshop.status != 'published':
        abort(404)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        company = request.form.get('company', '').strip()
        job_title = request.form.get('job_title', '').strip()

        if not name or not email:
            return render_template('workshops/register_public.html', workshop=workshop,
                                   error='Name and email are required.')

        if workshop.is_full:
            return render_template('workshops/register_public.html', workshop=workshop,
                                   error='This workshop is fully booked.')

        existing = WorkshopRegistration.query.filter_by(workshop_id=workshop.id, email=email).first()
        if existing:
            return render_template('workshops/register_public.html', workshop=workshop,
                                   error='You are already registered. Check your inbox.')

        # Optionally link to a CRM contact — resolved via HTTP, never via DB join
        crm_contact = get_contact(email)  # stub: client can search by email if CRM supports it
        crm_contact_id = crm_contact.get('id') if crm_contact else None

        token = secrets.token_urlsafe(32)
        reg = WorkshopRegistration(
            workshop_id=workshop.id,
            crm_contact_id=crm_contact_id,
            name=name,
            email=email,
            phone=phone,
            company=company,
            job_title=job_title,
            status='pending',
            payment_status='free' if workshop.is_free else 'pending',
            source='website',
            confirmation_token=token,
        )
        db.session.add(reg)
        db.session.commit()
        _send_confirmation_email(workshop, reg)
        return render_template('workshops/register_success.html', workshop=workshop, registration=reg)

    return render_template('workshops/register_public.html', workshop=workshop)


@workshops_bp.route('/confirm/<token>')
def confirm_registration(token):
    reg = WorkshopRegistration.query.filter_by(confirmation_token=token).first_or_404()
    if reg.status == 'pending':
        reg.status = 'confirmed'
        reg.confirmation_sent = True
        reg.confirmation_sent_at = datetime.utcnow()
        db.session.commit()
    return render_template('workshops/register_confirmed.html', registration=reg, workshop=reg.workshop)


# ─── Session & Session Helper ─────────────────────────────────────────────────

def _sync_sessions(workshop, form):
    """Auto-create one WorkshopSession per day in the date range."""
    start = workshop.start_date
    end = workshop.end_date
    delta = (end - start).days
    for i in range(delta + 1):
        session_date = start + timedelta(days=i)
        session = WorkshopSession(
            workshop_id=workshop.id,
            session_date=session_date,
            start_time=workshop.start_time,
            end_time=workshop.end_time,
            topic=form.get(f'session_topic_{i}', f'Day {i + 1}'),
            session_number=i + 1,
        )
        db.session.add(session)


# ─── Email Helpers ────────────────────────────────────────────────────────────

def _send_confirmation_email(workshop, registration):
    try:
        from app.services.ms_graph import MSGraphService
        graph = MSGraphService()
        subject = f'Registration Received: {workshop.title}'
        html_body = render_template(
            'workshops/email_registration_received.html',
            workshop=workshop, registration=registration, now=datetime.utcnow()
        )
        # Use LMS-level service account token (no CRM user token dependency)
        ms_token = current_app.config.get('MS_SERVICE_ACCESS_TOKEN')
        if ms_token:
            graph.send_email(ms_token, registration.email, subject, html_body, is_html=True)
    except Exception as e:
        current_app.logger.error(f'[LMS] Confirmation email failed: {e}')
