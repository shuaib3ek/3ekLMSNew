"""
Workshops Module — Admin & Public Routes
LMS-owned. No imports from 3EK-Pulse (CRM).
Trainer/Contact resolution uses crm_client HTTP calls.
"""
import os
import requests
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
    WorkshopRegistration, WorkshopEmailLog, WorkshopDocument, Learner
)
from app.core.extensions import db, csrf
from app.crm_client import get_trainer, list_trainers, get_contact, list_contacts
from app.services.ai_workshop_service import generate_workshop_content, extract_text_from_file


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

    # Email Preview Logic
    if request.args.get('preview_email'):
        # Just a placeholder recipient for preview
        dummy_recipient = {'first_name': 'Learning', 'last_name': 'Professional', 'email': 'test@example.com'}
        return render_template(
            'workshops/email_invitation_client.html',
            workshop=workshop,
            recipient=dummy_recipient,
            now=datetime.utcnow()
        )

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
        if 'mode' in request.form:
            workshop.mode = request.form.get('mode')
        if 'venue' in request.form:
            workshop.venue = request.form.get('venue')
        if 'meeting_link' in request.form:
            workshop.meeting_link = request.form.get('meeting_link')
        workshop.total_seats = int(request.form.get('total_seats') or 30)
        workshop.fee_per_person = float(fee)
        workshop.is_free = (float(fee) == 0)
        workshop.early_bird_fee = float(early_bird_fee) if early_bird_fee else None
        workshop.early_bird_deadline = datetime.strptime(early_bird_deadline_str, '%Y-%m-%d').date() if early_bird_deadline_str else None
        if 'banner_image_url' in request.form:
            workshop.banner_image_url = request.form.get('banner_image_url')
        if 'brochure_url' in request.form:
            workshop.brochure_url = request.form.get('brochure_url')
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

@workshops_bp.route('/<int:workshop_id>/generate-meeting', methods=['POST'])
@login_required
def generate_meeting(workshop_id):
    _admin_required()
    workshop = Workshop.query.get_or_404(workshop_id)
    
    if workshop.mode not in ['online', 'hybrid']:
        return jsonify({'error': 'Meeting generation is only for online/hybrid workshops.'}), 400

    if workshop.meeting_link:
        return jsonify({
            'success': True,
            'join_url': workshop.meeting_link,
            'message': 'Meeting already generated.'
        })

    from app.services.ms_graph_service import MSGraphService
    graph = MSGraphService()
    
    # Calculate start and end datetimes
    try:
        # Expected formats: '09:00 AM IST' or '17:00'
        def parse_time_str(ts):
            parts = ts.split(' ')
            if len(parts) >= 2 and parts[1].upper() in ['AM', 'PM']:
                return datetime.strptime(f"{parts[0]} {parts[1]}", '%I:%M %p').time()
            return datetime.strptime(parts[0], '%H:%M').time()

        start_dt = datetime.combine(workshop.start_date, parse_time_str(workshop.start_time))
        end_dt = datetime.combine(workshop.end_date, parse_time_str(workshop.end_time))
    except Exception as e:
        return jsonify({'error': f'Failed to parse workshop times: {e}'}), 400

    meeting = graph.create_online_meeting(workshop.title, start_dt, end_dt)
    
    if meeting and 'joinWebUrl' in meeting:
        workshop.meeting_link = meeting['joinWebUrl']
        db.session.commit()
        return jsonify({
            'success': True,
            'join_url': meeting['joinWebUrl']
        })
    else:
        return jsonify({
            'error': 'Failed to generate meeting link via MS Graph.',
            'hint': 'Check MS Graph logs or ensure MS_SENDER_EMAIL has a valid license.'
        }), 500


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


# ─── AI Generation ────────────────────────────────────────────────────────────

@workshops_bp.route('/generate', methods=['POST'])
@login_required
def generate_content():
    _admin_required()
    
    # Mode 1: From Topic (JSON)
    if request.is_json:
        data = request.get_json()
        topic = data.get('topic')
        duration = data.get('duration')
        
        if not topic:
            return jsonify({'error': 'Topic is required.'}), 400
            
        result = generate_workshop_content(topic=topic, duration=duration)
        if 'error' in result:
            return jsonify(result), 400
        return jsonify(result)
        
    # Mode 2: From Document (Multipart)
    else:
        file = request.files.get('file')
        duration = request.form.get('duration')
        
        if not file:
            return jsonify({'error': 'File is required.'}), 400
            
        # Save temp file
        temp_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        file_path = os.path.join(temp_dir, f"{uuid.uuid4()}_{file.filename}")
        file.save(file_path)
        
        try:
            text, error = extract_text_from_file(file_path, file.filename)
            if error:
                return jsonify({'error': error}), 400
                
            result = generate_workshop_content(file_text=text, duration=duration)
            if 'error' in result:
                return jsonify(result), 400
            return jsonify(result)
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)


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

    phone = request.form.get('phone', '')
    company = request.form.get('company', '')
    job_title = request.form.get('job_title', '')

    learner = Learner.query.filter_by(email=email).first()
    if not learner:
        learner = Learner(name=name, email=email, phone=phone, company=company, job_title=job_title)
        db.session.add(learner)
        db.session.flush()

    reg = WorkshopRegistration(
        workshop_id=workshop_id,
        learner_id=learner.id,
        name=name,
        email=email,
        phone=phone,
        company=company,
        job_title=job_title,
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

        learner = Learner.query.filter_by(email=email).first()
        if not learner:
            learner = Learner(name=name, email=email, phone=phone, company=company, job_title=job_title)
            db.session.add(learner)
            db.session.flush()

        token = secrets.token_urlsafe(32)
        reg = WorkshopRegistration(
            workshop_id=workshop.id,
            learner_id=learner.id,
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
        from app.services.ms_graph_service import MSGraphService
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


def _send_payment_receipt_email(workshop, registration):
    try:
        from app.services.ms_graph_service import MSGraphService
        graph = MSGraphService()
        subject = f'Payment Receipt: {workshop.title}'
        html_body = render_template(
            'workshops/email_payment_received.html',
            workshop=workshop, registration=registration, now=datetime.utcnow()
        )
        graph.send_email(registration.email, subject, html_body)
    except Exception as e:
        current_app.logger.error(f'[LMS] Payment receipt email failed: {e}')


# ─── Document Management ──────────────────────────────────────────────────────

@workshops_bp.route('/<int:workshop_id>/documents/upload', methods=['POST'])
@login_required
def upload_document(workshop_id):
    _admin_required()
    workshop = Workshop.query.get_or_404(workshop_id)
    file = request.files.get('document')
    doc_type = request.form.get('document_type', 'Handout')

    if not file:
        flash('No file selected.', 'danger')
        return redirect(url_for('workshops.detail_workshop', workshop_id=workshop_id))

    # Save file
    workshop_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'workshops', str(workshop_id))
    os.makedirs(workshop_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex[:8]}_{file.filename}"
    file_path = os.path.join(workshop_dir, filename)
    file.save(file_path)

    # In a real app, this might be a S3 URL. For now, local path or relative web path.
    # Assuming /static/uploads/ mapping or similar. 
    # For standalone LMS, let's use a placeholder URL for now or relative path.
    file_url = f"/workshops/docs/{workshop_id}/{filename}"

    doc = WorkshopDocument(
        workshop_id=workshop.id,
        filename=file.filename,
        file_url=file_url,
        document_type=doc_type,
        size_bytes=os.path.getsize(file_path),
        crm_uploaded_by_id=current_user.id
    )
    db.session.add(doc)
    db.session.commit()
    flash(f'Document "{file.filename}" uploaded.', 'success')
    return redirect(url_for('workshops.detail_workshop', workshop_id=workshop_id))


@workshops_bp.route('/<int:workshop_id>/documents/<int:document_id>/delete', methods=['POST'])
@login_required
def delete_document(workshop_id, document_id):
    _admin_required()
    doc = WorkshopDocument.query.get_or_404(document_id)
    db.session.delete(doc)
    db.session.commit()
    flash('Document deleted.', 'success')
    return redirect(url_for('workshops.detail_workshop', workshop_id=workshop_id))


# ─── Lifecycle & Communications ───────────────────────────────────────────────

@workshops_bp.route('/<int:workshop_id>/delete', methods=['POST'])
@login_required
def delete_workshop(workshop_id):
    _admin_required()
    workshop = Workshop.query.get_or_404(workshop_id)
    title = workshop.title
    db.session.delete(workshop)
    db.session.commit()
    flash(f'Workshop "{title}" and all related data deleted.', 'success')
    return redirect(url_for('workshops.list_workshops'))


@workshops_bp.route('/<int:workshop_id>/invite', methods=['GET', 'POST'])
@login_required
def send_invite(workshop_id):
    _admin_required()
    workshop = Workshop.query.get_or_404(workshop_id)
    contacts = list_contacts()

    if request.method == 'POST':
        filter_type = request.form.get('filter_type')
        email_type = request.form.get('email_type', 'individual')
        preview_only = request.form.get('preview_only') == 'true'

        recipients = []

        if filter_type == 'all_active':
            recipients = [{'id': c['id'], 'name': c['name'], 'email': c['email']} for c in contacts if c.get('email')]
        elif filter_type == 'contacts':
            selected_ids = request.form.getlist('contact_ids')
            recipients = []
            for c in contacts:
                if str(c['id']) in selected_ids and c.get('email'):
                    recipients.append({'id': c['id'], 'name': c['name'], 'email': c['email']})
        elif filter_type == 'custom':
            custom_list = request.form.get('custom_emails', '').split('\n')
            for line in custom_list:
                line = line.strip()
                if not line: continue
                if ',' in line:
                    email, name = map(str.strip, line.split(',', 1))
                else:
                    email, name = line, 'Colleague'
                if email and '@' in email:
                    recipients.append({'id': None, 'name': name, 'email': email})

        if preview_only:
            return jsonify({
                'count': len(recipients),
                'sample': recipients[:3]
            })

        # Process sending
        count = 0
        errors = 0
        from app.services.ms_graph_service import MSGraphService
        graph = MSGraphService()

        # Create a single log entry for this blast
        log = WorkshopEmailLog(
            workshop_id=workshop.id,
            email_type='invitation',
            subject=f"Invitation: {workshop.title}",
            filter_description=filter_type,
            sent_at=datetime.utcnow(),
            crm_sent_by_id=current_user.id if hasattr(current_user, 'id') else None
        )
        db.session.add(log)

        for r in recipients:
            try:
                subject = f"Invitation: {workshop.title}"
                html_body = render_template(
                    'workshops/email_invitation_client.html',
                    workshop=workshop,
                    recipient=r,
                    email_type=email_type,
                    now=datetime.utcnow()
                )
                sent = graph.send_email(r['email'], subject, html_body)
                if sent:
                    count += 1
                else:
                    errors += 1
                    current_app.logger.warning(f"[LMS] Email not sent to {r['email']} — check MS Graph config.")
            except Exception as e:
                errors += 1
                current_app.logger.error(f"[LMS] Exception sending invite to {r['email']}: {e}")

        # Update log with final counts
        log.recipient_count = count
        if errors:
            log.notes = f"Failed to send to {errors} recipients. Check logs."
            
        db.session.commit()
        
        if errors:
            flash(f'Sent {count} invitations. {errors} failed — check the server logs and MS Graph config.', 'warning')
        else:
            flash(f'Successfully sent {count} invitations.', 'success')
            
        return redirect(url_for('workshops.detail_workshop', workshop_id=workshop_id))

    return render_template('workshops/send_invite.html', workshop=workshop, contacts=contacts)


@workshops_bp.route('/<int:workshop_id>/send-joining-details', methods=['POST'])
@login_required
def send_joining_details(workshop_id):
    _admin_required()
    workshop = Workshop.query.get_or_404(workshop_id)
    
    # Process modal data
    meeting_link = request.form.get('meeting_link')
    venue = request.form.get('venue')
    extra_notes = request.form.get('extra_notes', '')

    if workshop.mode == 'online' and meeting_link:
        workshop.meeting_link = meeting_link
    elif workshop.mode != 'online' and venue:
        workshop.venue = venue
    
    db.session.commit()
    
    # Fetch confirmed participants
    participants = [r for r in workshop.registrations if r.status == 'confirmed' or r.payment_status == 'paid']
    
    if not participants:
        flash('No confirmed participants found to send details to.', 'warning')
        return redirect(url_for('workshops.detail_workshop', workshop_id=workshop_id))

    from app.services.ms_graph_service import MSGraphService
    import base64
    from datetime import timedelta
    
    graph = MSGraphService()
    
    # Generate Calendar Invite (.ics) if online
    attachments = []
    if workshop.mode == 'online' and workshop.meeting_link:
        try:
            # Basic manual ICS generation to avoid dependency issues
            start_dt = datetime.combine(workshop.start_date, datetime.strptime(workshop.start_time.split(' ')[0], '%H:%M').time())
            # Simple assumption: Workshop ends at end_time on end_date
            end_dt = datetime.combine(workshop.end_date, datetime.strptime(workshop.end_time.split(' ')[0], '%H:%M').time())
            
            ics_content = [
                "BEGIN:VCALENDAR",
                "VERSION:2.0",
                "PRODID:-//3EK LMS//Workshop Calendar//EN",
                "BEGIN:VEVENT",
                f"SUMMARY:{workshop.title}",
                f"DTSTART:{start_dt.strftime('%Y%m%dT%H%M%S')}",
                f"DTEND:{end_dt.strftime('%Y%m%dT%H%M%S')}",
                f"LOCATION:{workshop.meeting_link}",
                f"DESCRIPTION:Workshop: {workshop.title}\\nLink: {workshop.meeting_link}\\n\\n{extra_notes}",
                "STATUS:CONFIRMED",
                "SEQUENCE:0",
                "BEGIN:VALARM",
                "TRIGGER:-PT15M",
                "ACTION:DISPLAY",
                "DESCRIPTION:Reminder",
                "END:VALARM",
                "END:VEVENT",
                "END:VCALENDAR"
            ]
            ics_text = "\r\n".join(ics_content)
            attachments.append({
                'name': 'invite.ics',
                'content_bytes': base64.b64encode(ics_text.encode('utf-8')).decode('utf-8'),
                'content_type': 'text/calendar'
            })
        except Exception as e:
            current_app.logger.error(f"[LMS] Failed to generate ICS: {e}")

    # Create email log
    log = WorkshopEmailLog(
        workshop_id=workshop.id,
        email_type='joining_instructions',
        subject=f"Joining Instructions: {workshop.title}",
        recipient_count=0,
        sent_at=datetime.utcnow(),
        crm_sent_by_id=current_user.id
    )
    db.session.add(log)

    count = 0
    errors = 0
    for p in participants:
        try:
            subject = f"Joining Instructions: {workshop.title}"
            html_body = render_template(
                'workshops/email_joining_instructions.html',
                workshop=workshop,
                recipient=p,
                extra_notes=extra_notes,
                now=datetime.utcnow()
            )
            # Send with attachments
            sent = graph.send_email(p.email, subject, html_body, attachments=attachments)
            if sent:
                count += 1
            else:
                errors += 1
        except Exception as e:
            errors += 1
            current_app.logger.error(f"[LMS] Failed to send joining details to {p.email}: {e}")

    log.recipient_count = count
    if errors:
        log.notes = f"Failed to send to {errors} recipients."
    
    db.session.commit()
    
    if errors:
        flash(f'Sent {count} joining instructions. {errors} failed.', 'warning')
    else:
        flash(f'Successfully sent joining instructions to {count} participants.', 'success')
        
    return redirect(url_for('workshops.detail_workshop', workshop_id=workshop_id))


@workshops_bp.route('/<int:workshop_id>/registrations/<int:reg_id>/invite-lms', methods=['POST'])
@login_required
def invite_lms(workshop_id, reg_id):
    _admin_required()
    reg = WorkshopRegistration.query.get_or_404(reg_id)
    # Placeholder for LMS access logic
    flash(f'LMS access granted to {reg.name}.', 'success')
    return redirect(url_for('workshops.detail_workshop', workshop_id=workshop_id))


@workshops_bp.route('/<int:workshop_id>/registrations/<int:reg_id>/send-payment-link', methods=['POST'])
@login_required
def send_payment_link_email(workshop_id, reg_id):
    _admin_required()
    reg = WorkshopRegistration.query.get_or_404(reg_id)
    
    if reg.payment_status == 'paid':
        flash('This registration is already paid.', 'warning')
        return redirect(url_for('workshops.detail_workshop', workshop_id=workshop_id))
        
    payment_link = url_for('workshops.payment_checkout', token=reg.confirmation_token, _external=True)
    
    try:
        from app.services.ms_graph_service import MSGraphService
        graph = MSGraphService()
        subject = f'Complete your Registration: {reg.workshop.title}'
        html_body = render_template(
            'workshops/email_payment_link.html',
            workshop=reg.workshop,
            recipient=reg,
            payment_link=payment_link,
            now=datetime.utcnow()
        )
        graph.send_email(reg.email, subject, html_body)
        flash(f'Payment reminder sent to {reg.name}.', 'success')
    except Exception as e:
        current_app.logger.error(f"[LMS] Failed to send payment reminder to {reg.email}: {e}")
        flash(f'Failed to send payment reminder to {reg.name}. Check logs.', 'danger')
        
    return redirect(url_for('workshops.detail_workshop', workshop_id=workshop_id))


# ─── Recordings & Analysis ────────────────────────────────────────────────────

@workshops_bp.route('/session/<int:session_id>/recording')
@login_required
def view_recording(session_id):
    session = WorkshopSession.query.get_or_404(session_id)
    # Placeholder for recording viewer
    flash(f'Recording viewer for session "{session.topic}" not yet implemented.', 'info')
    return redirect(url_for('workshops.detail_workshop', workshop_id=session.workshop_id))


@workshops_bp.route('/session/<int:session_id>/compliance')
@login_required
def session_compliance(session_id):
    _admin_required()
    session = WorkshopSession.query.get_or_404(session_id)
    # Placeholder for compliance/audit view
    flash(f'AI Pedagogical Audit for session "{session.topic}" not yet implemented.', 'info')
    return redirect(url_for('workshops.detail_workshop', workshop_id=session.workshop_id))


# ─── Payments ─────────────────────────────────────────────────────────────────

@workshops_bp.route('/checkout/<token>')
def payment_checkout(token):
    reg = WorkshopRegistration.query.filter_by(confirmation_token=token).first_or_404()
    
    if reg.payment_status == 'paid':
        flash('Payment already completed for this registration.', 'info')
        return render_template('workshops/register_confirmed.html', registration=reg, workshop=reg.workshop)
        
    amount = int(reg.workshop.fee_per_person * 100) # Amount in paise
    currency = "INR"
    
    # Initialize Razorpay Client
    rzp_key_id = current_app.config.get('RAZORPAY_KEY_ID')
    rzp_key_secret = current_app.config.get('RAZORPAY_KEY_SECRET')
    
    if not rzp_key_id or not rzp_key_secret:
        return "Payment gateway is not fully configured.", 500
        
    import razorpay
    client = razorpay.Client(auth=(rzp_key_id, rzp_key_secret))
    
    try:
        # Create Razorpay Order if not exists
        if not reg.razorpay_order_id:
            order_data = {
                "amount": amount,
                "currency": currency,
                "receipt": f"receipt_{reg.id}",
                "notes": {"registration_token": reg.confirmation_token}
            }
            order = client.order.create(data=order_data)
            reg.razorpay_order_id = order['id']
            db.session.commit()
    except Exception as e:
        current_app.logger.error(f"[LMS] Razorpay Order Error: {e}")
        return "Error creating payment order. Please try again later.", 500
        
    return render_template(
        'workshops/checkout.html',
        registration=reg,
        key_id=rzp_key_id,
        amount=amount,
        currency=currency,
        order_id=reg.razorpay_order_id
    )

@workshops_bp.route('/payment-callback', methods=['POST'])
@csrf.exempt
def payment_callback():
    razorpay_payment_id = request.form.get('razorpay_payment_id')
    razorpay_order_id = request.form.get('razorpay_order_id')
    razorpay_signature = request.form.get('razorpay_signature')
    
    if not (razorpay_payment_id and razorpay_order_id and razorpay_signature):
        return abort(400, "Missing payment details.")
        
    reg = WorkshopRegistration.query.filter_by(razorpay_order_id=razorpay_order_id).first()
    if not reg:
        return abort(404, "Order not found.")
        
    rzp_key_id = current_app.config.get('RAZORPAY_KEY_ID')
    rzp_key_secret = current_app.config.get('RAZORPAY_KEY_SECRET')
    
    import razorpay
    client = razorpay.Client(auth=(rzp_key_id, rzp_key_secret))
    
    try:
        params_dict = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        }
        client.utility.verify_payment_signature(params_dict)
        
        # Payment is verified
        reg.payment_status = 'paid'
        reg.status = 'confirmed'
        reg.razorpay_payment_id = razorpay_payment_id
        
        # Track the actual amount paid
        try:
            payment = client.payment.fetch(razorpay_payment_id)
            reg.amount_paid = float(payment['amount']) / 100
        except Exception as e:
            current_app.logger.warning(f"[LMS] Could not fetch payment amount from Razorpay: {e}")
            # Fallback to workshop fee if fetch fails
            reg.amount_paid = float(reg.workshop.fee_per_person or 0)

        db.session.commit()
        
        # Send receipt email
        _send_payment_receipt_email(reg.workshop, reg)
        
        return render_template('workshops/register_success.html', registration=reg, workshop=reg.workshop)
        
    except razorpay.errors.SignatureVerificationError:
        current_app.logger.error(f"[LMS] Razorpay Signature mismatch for order {razorpay_order_id}")
        return abort(400, "Payment verification failed.")
    except Exception as e:
        current_app.logger.error(f"[LMS] Razorpay Callback Error: {e}")
        return abort(500, "An error occurred handling payment callback.")
