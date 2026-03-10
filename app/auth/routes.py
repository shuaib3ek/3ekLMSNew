"""
Auth Routes
- Admin: email + password verified against CRM
- Trainer / Client / Learner: passwordless OTP via MS Graph email
  OTPs are stored in the LMS database (OtpToken model), NOT in Flask session,
  so they survive server restarts and debug-mode reloads.
"""
import secrets
import requests as http_requests
from datetime import datetime, timedelta
from flask import render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required
from . import auth_bp
from .models import StaffUser


# ─── Admin Login (Password via CRM) ──────────────────────────────────────────

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    from flask import session
    if request.method == 'POST':
        role = request.form.get('role', 'admin')
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Email and password are required.', 'danger')
            return redirect(url_for('auth.login', role=role))

        base = current_app.config.get('CRM_API_URL', 'http://localhost:8013')
        token = current_app.config.get('CRM_SERVICE_TOKEN', '')

        if role == 'admin':
            try:
                current_app.logger.info(f"Auth attempt for {email} via CRM")
                r = http_requests.post(
                    f'{base}/api/v1/crm/auth/verify',
                    json={'email': email, 'password': password},
                    headers={'X-Service-Token': token, 'Content-Type': 'application/json'},
                    timeout=5
                )
                data = r.json()
                if r.ok and data.get('valid') and data.get('user'):
                    user_data = data.get('user')
                    staff_user = StaffUser(user_data)
                    login_user(staff_user)
                    flash('Logged in successfully.', 'success')
                    return redirect(url_for('workshops.list_workshops'))
                else:
                    flash('Invalid credentials or CRM access denied.', 'danger')
            except Exception as e:
                current_app.logger.error(f'[LMS Auth] Gateway error: {e}')
                flash('Failed to reach authentication gateway.', 'danger')
        else:
            # ── Trainer / Client / Learner (Demo Password Mode) ──
            # Accept a default master password for these roles
            if password not in ('password', '3ek2026', 'Password123!', '123456'):
                flash('Invalid password. Hint: Try "3ek2026".', 'danger')
                return redirect(url_for('auth.login', role=role))

            email_valid = False
            user_data = {}

            if role == 'learner':
                from app.workshops.models import Learner
                learner = Learner.query.filter_by(email=email).first()
                if learner:
                    email_valid = True
                    user_data = {
                        'id': learner.id,
                        'email': email,
                        'first_name': learner.name.split()[0] if learner.name else 'Learner',
                        'last_name': ' '.join(learner.name.split()[1:]) if learner.name and ' ' in learner.name else '',
                        'role': 'learner'
                    }
            elif role == 'trainer':
                try:
                    r = http_requests.get(f'{base}/api/v1/crm/trainers', headers={'X-Service-Token': token}, timeout=5)
                    if r.ok:
                        trainers = r.json()
                        if isinstance(trainers, dict) and 'data' in trainers:
                            trainers = trainers['data']
                        data = next((t for t in trainers if t.get('email', '').strip().lower() == email), None)
                        if data:
                            email_valid = True
                            user_data = {
                                'id': data.get('id', 0),
                                'email': email,
                                'first_name': data.get('first_name', data.get('name', '').split()[0] if data.get('name') else 'Trainer'),
                                'last_name': data.get('last_name', ''),
                                'role': 'trainer',
                                'crm_trainer_id': data.get('id')
                            }
                except Exception:
                    pass
            elif role == 'client':
                try:
                    # First: try real CRM Contact password (Werkzeug hash)
                    from app.crm_client.client import verify_contact_password
                    contact_data = verify_contact_password(email, password)
                    if contact_data:
                        email_valid = True
                        name_parts = contact_data.get('name', 'Client').split(' ', 1)
                        user_data = {
                            'id': contact_data.get('id', 0),
                            'email': email,
                            'first_name': name_parts[0],
                            'last_name': name_parts[1] if len(name_parts) > 1 else '',
                            'role': 'client',
                            'crm_client_id': contact_data.get('client_id'),
                            'job_title': contact_data.get('job_title'),
                        }
                    else:
                        # Fallback: check email exists in CRM then allow master password
                        r = http_requests.get(f'{base}/api/v1/crm/contacts', headers={'X-Service-Token': token}, timeout=5)
                        if r.ok:
                            contacts_list = r.json()
                            if isinstance(contacts_list, dict) and 'data' in contacts_list:
                                contacts_list = contacts_list['data']
                            data = next((c for c in contacts_list if c.get('email', '').strip().lower() == email), None)
                            if data:
                                email_valid = True
                                user_data = {
                                    'id': data.get('id', 0),
                                    'email': email,
                                    'first_name': data.get('name', 'Client').split()[0],
                                    'last_name': '',
                                    'role': 'client',
                                    'crm_client_id': data.get('client_id'),
                                }
                except Exception:
                    pass

            if not email_valid:
                flash(f'No {role} account found for {email}.', 'danger')
                return redirect(url_for('auth.login', role=role))

            session['_lms_user'] = user_data
            staff_user = StaffUser(user_data)
            login_user(staff_user)
            flash(f'Welcome back!', 'success')
            
            if role == 'learner':
                return redirect(url_for('learner_portal.dashboard'))
            elif role == 'trainer':
                return redirect(url_for('trainer_portal.dashboard'))
            elif role == 'client':
                return redirect(url_for('client_portal.dashboard'))

    return render_template('auth/login.html')


# ─── OTP Request ──────────────────────────────────────────────────────────────

@auth_bp.route('/otp/request', methods=['POST'])
def request_otp():
    """
    Receives email + role from login form.
    Verifies the email exists for that role, generates a 6-digit OTP,
    saves it to the DB, emails it, and redirects to the verify page.
    OTP state lives in the DB — no Flask session dependency.
    """
    role = request.form.get('role', '').strip()
    email = request.form.get('email', '').strip().lower()

    if not email or role not in ('trainer', 'client', 'learner'):
        flash('Invalid request. Please select your role and enter your email.', 'danger')
        return redirect(url_for('auth.login'))

    # ── Verify email exists for this role ─────────────────────────────────────
    email_valid = False
    crm_data = {}

    if role == 'learner':
        from app.workshops.models import Learner
        learner = Learner.query.filter_by(email=email).first()
        email_valid = learner is not None
        if learner:
            crm_data = {'id': learner.id, 'first_name': learner.name.split()[0],
                        'last_name': ' '.join(learner.name.split()[1:]) if ' ' in learner.name else ''}

    elif role == 'trainer':
        base = current_app.config.get('CRM_API_URL', 'http://localhost:8013')
        token = current_app.config.get('CRM_SERVICE_TOKEN', '')
        try:
            r = http_requests.get(f'{base}/api/v1/crm/trainers/lookup',
                                  params={'email': email},
                                  headers={'X-Service-Token': token}, timeout=5)
            if r.ok and r.json().get('data'):
                email_valid = True
                crm_data = r.json().get('data', {})
        except Exception as e:
            current_app.logger.error(f'[OTP] Trainer lookup failed: {e}')

    elif role == 'client':
        base = current_app.config.get('CRM_API_URL', 'http://localhost:8013')
        token = current_app.config.get('CRM_SERVICE_TOKEN', '')
        try:
            r = http_requests.get(f'{base}/api/v1/crm/contacts/lookup',
                                  params={'email': email},
                                  headers={'X-Service-Token': token}, timeout=5)
            if r.ok and r.json().get('data'):
                email_valid = True
                crm_data = r.json().get('data', {})
        except Exception as e:
            current_app.logger.error(f'[OTP] Contact lookup failed: {e}')

    if not email_valid:
        flash(f'No {role} account found for {email}. Please check your email address.', 'danger')
        return redirect(url_for('auth.login') + f'?role={role}')

    # ── Generate & persist OTP in DB ──────────────────────────────────────────
    from app.workshops.models import OtpToken
    from app.core.extensions import db

    # Expire any old OTPs for this email+role
    old_tokens = OtpToken.query.filter_by(email=email, role=role, used=False).all()
    for t in old_tokens:
        t.used = True

    otp_code = str(secrets.randbelow(900000) + 100000)   # 6-digit
    token_row = OtpToken(
        email=email,
        role=role,
        code=otp_code,
        expires_at=datetime.utcnow() + timedelta(minutes=10)
    )
    db.session.add(token_row)
    db.session.commit()

    # ── Send OTP via MS Graph ─────────────────────────────────────────────────
    try:
        from app.services.ms_graph_service import MSGraphService
        graph = MSGraphService()
        subject = "Your 3EK LMS Login Code"
        body = render_template('auth/otp_email.html', otp=otp_code, role=role, email=email)
        sent = graph.send_email(email, subject, body)
        if not sent:
            current_app.logger.error(f'[OTP] MS Graph failed to send to {email}')
            flash('Failed to send login code. Please try again.', 'danger')
            return redirect(url_for('auth.login') + f'?role={role}')
    except Exception as e:
        current_app.logger.error(f'[OTP] Email exception: {e}')
        flash('Failed to send login code. Please try again.', 'danger')
        return redirect(url_for('auth.login') + f'?role={role}')

    current_app.logger.info(f'[OTP] Sent code to {email} ({role}), token id={token_row.id}')

    # Redirect to verify — embed token ID + role + email as URL params (no session needed)
    return redirect(url_for('auth.verify_otp', tid=token_row.id, role=role,
                            email=email))


# ─── OTP Verify ───────────────────────────────────────────────────────────────

@auth_bp.route('/otp/verify', methods=['GET', 'POST'])
def verify_otp():
    """
    Step 2: user enters 6-digit code.
    Looks up the OtpToken by ID from query params — no session required.
    """
    tid = request.args.get('tid') or request.form.get('tid')
    otp_email = request.args.get('email') or request.form.get('email', '')
    otp_role  = request.args.get('role')  or request.form.get('role', '')

    if not tid or not otp_email or not otp_role:
        flash('Invalid or missing verification link. Please try again.', 'warning')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        entered = request.form.get('otp', '').strip()

        from app.workshops.models import OtpToken
        from app.core.extensions import db

        token_row = OtpToken.query.get(int(tid))

        if not token_row or token_row.email != otp_email or token_row.role != otp_role:
            flash('Verification link is invalid. Please request a new code.', 'danger')
            return redirect(url_for('auth.login') + f'?role={otp_role}')

        if not token_row.is_valid():
            flash('Your login code has expired. Please request a new one.', 'warning')
            return redirect(url_for('auth.login') + f'?role={otp_role}')

        if entered != token_row.code:
            flash('Incorrect code. Please check your email and try again.', 'danger')
            return render_template('auth/otp_verify.html',
                                   email=otp_email, role=otp_role, tid=tid)

        # ── Valid OTP — mark used ─────────────────────────────────────────────
        token_row.used = True
        db.session.commit()

        # ── Build session user ────────────────────────────────────────────────
        if otp_role == 'learner':
            from app.workshops.models import Learner
            learner = Learner.query.filter_by(email=otp_email).first()
            if not learner:
                flash('Account not found.', 'danger')
                return redirect(url_for('auth.login'))
            name_parts = (learner.name or '').split(' ', 1)
            user_data = {
                'id': learner.id,
                'email': learner.email,
                'first_name': name_parts[0],
                'last_name': name_parts[1] if len(name_parts) > 1 else '',
                'role': 'learner',
            }
        elif otp_role in ('trainer', 'client'):
            # Re-fetch CRM data for name (non-critical)
            base = current_app.config.get('CRM_API_URL', 'http://localhost:8013')
            svc_token = current_app.config.get('CRM_SERVICE_TOKEN', '')
            endpoint = 'trainers' if otp_role == 'trainer' else 'contacts'
            crm_data = {}
            try:
                r = http_requests.get(f'{base}/api/v1/crm/{endpoint}/lookup',
                                      params={'email': otp_email},
                                      headers={'X-Service-Token': svc_token}, timeout=5)
                if r.ok:
                    crm_data = r.json().get('data', {})
            except Exception:
                pass
            user_data = {
                'id': crm_data.get('id', 0),
                'email': otp_email,
                'first_name': crm_data.get('first_name', ''),
                'last_name': crm_data.get('last_name', ''),
                'role': otp_role,
            }
            if otp_role == 'client':
                user_data['crm_client_id'] = crm_data.get('client_id')
        else:
            flash('Unknown role.', 'danger')
            return redirect(url_for('auth.login'))

        staff_user = StaffUser(user_data)

        # Cache full user_data in session so user_loader can restore role correctly
        from flask import session as flask_session
        flask_session['_lms_user'] = user_data
        flask_session.modified = True

        login_user(staff_user)
        flash(f'Welcome, {staff_user.full_name or otp_email}!', 'success')

        if otp_role == 'learner':
            return redirect(url_for('learner_portal.dashboard'))
        elif otp_role == 'trainer':
            return redirect(url_for('trainer_portal.dashboard'))
        elif otp_role == 'client':
            return redirect(url_for('client_portal.dashboard'))
        else:
            return redirect(url_for('workshops.list_workshops'))

    return render_template('auth/otp_verify.html',
                           email=otp_email, role=otp_role, tid=tid)


# ─── Logout ───────────────────────────────────────────────────────────────────

@auth_bp.route('/logout')
@login_required
def logout():
    from flask import session as flask_session
    flask_session.pop('_lms_user', None)
    logout_user()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('auth.login'))
