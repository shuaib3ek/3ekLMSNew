from flask import render_template, abort, flash, request, redirect, url_for
from werkzeug.security import generate_password_hash
from flask_login import login_required, current_user
from . import training_bp
from app.crm_client.client import fetch_pulse_programs

@training_bp.before_request
@login_required
def require_admin():
    if current_user.role not in ['admin', 'super_admin']:
        abort(403)

@training_bp.route('/')
def list_pulse_programs():
    """Fetches read-only historical program data from 3ek-pulse and cross-references with local LMS takeover."""
    programs = fetch_pulse_programs()
    
    from app.workshops.models import Workshop
    
    # Enrich programs with local workshop IDs if they exist
    # 1. Collect all CRM IDs from the fetched programs
    crm_ids = [p['id'] for p in programs if p.get('id')]
    
    # 2. Bulk fetch workshops that match any of these IDs
    workshops = Workshop.query.filter(Workshop.crm_engagement_id.in_(crm_ids)).all()
    workshop_map = {w.crm_engagement_id: w.id for w in workshops}
    
    for p in programs:
        crm_id = p.get('id')
        p['lms_workshop_id'] = workshop_map.get(crm_id)
        p['is_lms_managed'] = crm_id in workshop_map

    # Only surface programs that require LMS-managed labs or assessments
    programs = [p for p in programs if p.get('requires_lab') or p.get('requires_assessment')]

    return render_template('training_management/list.html', programs=programs)

@training_bp.route('/<int:crm_engagement_id>/')
def program_detail(crm_engagement_id):
    """Internal Program View inside LMS showing read-only CRM data."""
    from app.crm_client.client import fetch_pulse_program_detail
    from app.training_management.models import ProgramConfig, ProgramParticipant
    
    program = fetch_pulse_program_detail(crm_engagement_id)
    if not program:
        abort(404, description="Program not found in CRM.")
        
    config = ProgramConfig.query.filter_by(crm_engagement_id=crm_engagement_id).first()
    if not config:
        from app.core.extensions import db
        config = ProgramConfig(crm_engagement_id=crm_engagement_id)
        db.session.add(config)
        db.session.commit()
    
    participants = ProgramParticipant.query.filter_by(crm_engagement_id=crm_engagement_id).all()
    
    return render_template('training_management/detail.html', program=program, config=config, participants=participants)

@training_bp.route('/<int:crm_engagement_id>/toggle/<string:feature>', methods=['POST'])
def toggle_feature(crm_engagement_id, feature):
    """Toggle Assessments or Labs for a program."""
    from flask import jsonify
    from app.core.extensions import db
    from app.training_management.models import ProgramConfig
    
    if feature not in ['assessments', 'labs']:
        return jsonify({'error': 'Invalid feature'}), 400
        
    config = ProgramConfig.query.filter_by(crm_engagement_id=crm_engagement_id).first()
    if not config:
        config = ProgramConfig(crm_engagement_id=crm_engagement_id)
        db.session.add(config)
        
    if feature == 'assessments':
        config.assessments_enabled = not config.assessments_enabled
        enabled = config.assessments_enabled
    else:
        config.labs_enabled = not config.labs_enabled
        enabled = config.labs_enabled
        
    db.session.commit()
    
    return jsonify({'enabled': enabled})

@training_bp.route('/<int:crm_engagement_id>/participants/add', methods=['POST'])
def add_participant(crm_engagement_id):
    from flask import request, redirect, url_for, flash
    from app.core.extensions import db
    from app.training_management.models import ProgramParticipant
    
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    org = request.form.get('organization')
    
    if not name or not email:
        flash('Name and Email are required.', 'error')
        return redirect(url_for('training_management.program_detail', crm_engagement_id=crm_engagement_id))
        
    # Check duplicate
    existing = ProgramParticipant.query.filter_by(crm_engagement_id=crm_engagement_id, email=email).first()
    if existing:
        flash(f'Participant {email} already exists.', 'warning')
        return redirect(url_for('training_management.program_detail', crm_engagement_id=crm_engagement_id))

    # ── Phase 2: Auto-create Learner account ──
    from app.workshops.models import Learner
    learner = Learner.query.filter_by(email=email).first()
    if not learner:
        learner = Learner(
            name=name,
            email=email,
            password_hash=generate_password_hash('3eks@learn')
        )
        db.session.add(learner)
        db.session.flush() # Get ID before commit

    participant = ProgramParticipant(
        crm_engagement_id=crm_engagement_id,
        name=name,
        email=email,
        phone=phone,
        organization=org,
        source='manual',
        learner_id=learner.id
    )
    db.session.add(participant)
    db.session.commit()
    
    flash('Participant added successfully.', 'success')
    return redirect(url_for('training_management.program_detail', crm_engagement_id=crm_engagement_id))

@training_bp.route('/<int:crm_engagement_id>/participants/upload', methods=['POST'])
def upload_participants(crm_engagement_id):
    from flask import request, redirect, url_for, flash
    from app.core.extensions import db
    from app.training_management.models import ProgramParticipant
    import csv
    import io

    if 'file' not in request.files:
        flash('No file provided.', 'error')
        return redirect(url_for('training_management.program_detail', crm_engagement_id=crm_engagement_id))
        
    file = request.files['file']
    if file.filename == '':
        flash('No file selected.', 'error')
        return redirect(url_for('training_management.program_detail', crm_engagement_id=crm_engagement_id))
        
    if not file.filename.endswith('.csv'):
        flash('Please upload a valid CSV file.', 'error')
        return redirect(url_for('training_management.program_detail', crm_engagement_id=crm_engagement_id))

    try:
        stream = io.StringIO(file.stream.read().decode("utf-8-sig"), newline=None)
        csv_input = csv.DictReader(stream)
        
        # normalize headers
        headers = [h.strip().lower() for h in csv_input.fieldnames or []]
        csv_input.fieldnames = headers
        
        added_count = 0
        for row in csv_input:
            email = row.get('email', '').strip()
            name = row.get('name', '').strip()
            
            if not email or not name:
                continue
                
            # deduplicate
            existing = ProgramParticipant.query.filter_by(crm_engagement_id=crm_engagement_id, email=email).first()
            if not existing:
                # ── Phase 2: Auto-create Learner account ──
                from app.workshops.models import Learner
                learner = Learner.query.filter_by(email=email).first()
                if not learner:
                    new_l = Learner(
                        name=name,
                        email=email,
                        password_hash=generate_password_hash('3eks@learn')
                    )
                    db.session.add(new_l)
                    db.session.flush()
                    learner = new_l
                
                p = ProgramParticipant(
                    crm_engagement_id=crm_engagement_id,
                    name=name,
                    email=email,
                    phone=row.get('phone', '').strip(),
                    organization=row.get('organization', '').strip(),
                    source='excel_upload',
                    learner_id=learner.id
                )
                db.session.add(p)
                added_count += 1
                
        db.session.commit()
        flash(f'Successfully imported {added_count} participants.', 'success')
    except Exception as e:
        flash(f'Error processing file: {str(e)}', 'error')
        
    return redirect(url_for('training_management.program_detail', crm_engagement_id=crm_engagement_id))
