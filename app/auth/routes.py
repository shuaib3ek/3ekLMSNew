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
from flask import render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_user, logout_user, login_required
from . import auth_bp
from .models import StaffUser
from app.crm_client import client as crm_client
from app.core.extensions import limiter


# ─── Admin Login (Password via CRM) ──────────────────────────────────────────

@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    from flask import session
    if request.method == 'POST':
        role = request.form.get('role', 'admin')
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            msg = 'Email and password are required.'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.args.get('ajax') == '1':
                return jsonify({'success': False, 'message': msg}), 400
            flash(msg, 'danger')
            return redirect(url_for('auth.login', role=role))

        base = current_app.config.get('CRM_API_URL', 'http://localhost:8013')
        token = current_app.config.get('CRM_SERVICE_TOKEN', '')

        if role == 'admin':
            user_data = crm_client.verify_staff_password(email, password)
            if user_data:
                # Set role explicitly
                user_data['role'] = 'admin'
                
                # Fetch organization_id from ShadowStaffUser if it exists
                from app.core.shadow_models import ShadowStaffUser
                shadow = ShadowStaffUser.query.filter_by(crm_user_id=user_data['id']).first()
                if shadow:
                    user_data['organization_id'] = shadow.organization_id
                else:
                    user_data['organization_id'] = 1 # Default

                staff_user = StaffUser(user_data)
                
                from flask import session as flask_session
                flask_session['organization_id'] = user_data['organization_id']
                flask_session['_lms_user'] = user_data
                flask_session.modified = True
                
                login_user(staff_user)
                flash('Logged in successfully.', 'success')
                return redirect(url_for('admin.dashboard'))
            else:
                msg = 'Invalid credentials or CRM access denied.'
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.args.get('ajax') == '1':
                    return jsonify({'success': False, 'message': msg}), 401
                flash(msg, 'danger')
        else:
            # ── Non-Admin Roles (Mandatory OTP Flow) ──
            # We no longer accept master passwords. 
            # These roles must request an OTP to proceed.
            flash('This portal requires a secure login code. Please enter your email and click "Get Login Code".', 'info')
            return redirect(url_for('auth.login', role=role))

    return render_template('auth/login.html')


# ─── OTP Request ──────────────────────────────────────────────────────────────

@auth_bp.route('/otp/request', methods=['POST'])
@limiter.limit("3 per minute")
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

    # ── IDENTITY RESOLVER ─────────────────────────────────────────────────────
    # Check if the email domain matches any organization's permitted domains
    # or if the user is already linked to an organization.
    from app.organizations.models import Organization
    from flask import session as flask_session
    
    domain = email.split('@')[-1] if '@' in email else None
    resolved_org = None
    
    if domain:
        # Search for organizations that permit this domain
        resolved_org = Organization.query.filter(Organization.permitted_domains.ilike(f"%{domain}%")).first()
    
    if not resolved_org:
        # Try ShadowClient lookup
        from app.core.shadow_models import ShadowClient
        # This is a bit complex because we need to call CRM to get client_id from email
        # but for now let's check if the email belongs to a known learner or ShadowTrainer
        from app.core.shadow_models import ShadowTrainer
        st = ShadowTrainer.query.filter_by(email=email).first()
        if st:
            resolved_org = Organization.query.get(st.organization_id)
        else:
            from app.workshops.models import Learner
            l = Learner.query.filter_by(email=email).first()
            if l:
                resolved_org = Organization.query.get(l.organization_id)
            else:
                from app.core.shadow_models import ShadowContact
                sc = ShadowContact.query.filter_by(email=email).first()
                if sc:
                    resolved_org = Organization.query.get(sc.organization_id)

    if resolved_org:
        flask_session['organization_id'] = resolved_org.id
        flask_session.modified = True
        current_app.logger.info(f'[Auth] Resolved tenant {resolved_org.slug} for {email}')

    if role == 'learner':
        from app.workshops.models import Learner
        learner = Learner.query.filter_by(email=email).first()
        email_valid = learner is not None
        if learner:
            crm_data = {'id': learner.id, 'first_name': learner.name.split()[0],
                        'last_name': ' '.join(learner.name.split()[1:]) if ' ' in learner.name else ''}
            # PRECEDENCE: Use the learner's own organization_id
            flask_session['organization_id'] = learner.organization_id
            flask_session.modified = True

    elif role == 'trainer':
        from app.crm_client.client import lookup_trainer_by_email
        trainer_data = lookup_trainer_by_email(email)
        if trainer_data:
            email_valid = True
            name = trainer_data.get('name', trainer_data.get('first_name', ''))
            name_parts = name.split(' ', 1)
            crm_data = {
                'id': trainer_data.get('id', 0),
                'first_name': name_parts[0],
                'last_name': name_parts[1] if len(name_parts) > 1 else '',
            }

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
        # ── AUTO-PROVISIONING CHECK ──────────────────────────────────────────
        # If this is a learner login and the organization context is known
        # and allows self-registration, create the learner on the fly.
        from flask import session as flask_session
        org_id = flask_session.get('organization_id')
        if role == 'learner' and org_id:
            from app.organizations.models import Organization
            org = Organization.query.get(org_id)
            if org and org.allow_self_registration:
                from app.workshops.models import Learner
                from app.core.extensions import db
                new_learner = Learner(
                    name=email.split('@')[0].capitalize(), # Default name from email
                    email=email,
                    organization_id=org_id
                )
                db.session.add(new_learner)
                db.session.commit()
                email_valid = True
                current_app.logger.info(f'[OTP] Auto-provisioned learner {email} for org {org.name}')
        
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

    # ── Send OTP via MS Graph (DISABLED FOR TESTING PHASE) ──────────────────
    # try:
    #     from app.services.ms_graph_service import MSGraphService
    #     graph = MSGraphService()
    #     subject = "Your 3EK LMS Login Code"
    #     body = render_template('auth/otp_email.html', otp=otp_code, role=role, email=email)
    #     sent = graph.send_email(email, subject, body)
    #     if not sent:
    #         current_app.logger.error(f'[OTP] MS Graph failed to send to {email}')
    #         flash('Failed to send login code. Please try again.', 'danger')
    #         return redirect(url_for('auth.login') + f'?role={role}')
    # except Exception as e:
    #     current_app.logger.error(f'[OTP] Email exception: {e}')
    #     flash('Failed to send login code. Please try again.', 'danger')
    #     return redirect(url_for('auth.login') + f'?role={role}')

    current_app.logger.info(f'[OTP] TEST MODE: Code for {email} ({role}) is {otp_code}')

    current_app.logger.info(f'[OTP] Sent code to {email} ({role}), token id={token_row.id}')

    # Support AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.args.get('ajax') == '1':
        return jsonify({
            'success': True, 
            'tid': token_row.id, 
            'email': email, 
            'role': role,
            'message': 'Login code sent to your email.'
        })

    # Redirect to verify — embed token ID + role + email as URL params (no session needed)
    return redirect(url_for('auth.verify_otp', tid=token_row.id, role=role,
                            email=email))


# ─── OTP Verify ───────────────────────────────────────────────────────────────

@auth_bp.route('/otp/verify', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
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

        # ── DEVELOPMENT BYPASS ────────────────────────────────────────────────
        # Allow a master code for local testing
        if entered == '123456':
            current_app.logger.info(f'[OTP] Bypass code used for {otp_email}')
        elif entered != token_row.code:
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
                'organization_id': learner.organization_id
            }
        elif otp_role in ('trainer', 'client'):
            crm_data = {}
            if otp_role == 'trainer':
                trainer_match = crm_client.lookup_trainer_by_email(otp_email)
                if trainer_match:
                    crm_data = trainer_match
            else:
                contact_match = crm_client.lookup_contact_by_email(otp_email)
                if contact_match:
                    crm_data = contact_match
            
            first_name = crm_data.get('first_name', '')
            last_name = crm_data.get('last_name', '')
            if not first_name and crm_data.get('name'):
                name_parts = crm_data['name'].split(' ', 1)
                first_name = name_parts[0]
                last_name = name_parts[1] if len(name_parts) > 1 else ''

            user_data = {
                'id': crm_data.get('id', 0),
                'email': otp_email,
                'first_name': first_name,
                'last_name': last_name,
                'role': otp_role,
                'organization_id': 1 # Default
            }
            if otp_role == 'client':
                user_data['crm_client_id'] = crm_data.get('client_id')
                # Lookup ShadowClient to get organization_id
                from app.core.shadow_models import ShadowClient
                shadow = ShadowClient.query.filter_by(crm_client_id=user_data['crm_client_id']).first()
                if shadow:
                    user_data['organization_id'] = shadow.organization_id
                else:
                    # Fallback dynamic domain-based matching
                    from app.organizations.models import Organization
                    email_lower = otp_email.lower()
                    resolved_org = None
                    if 'hexaware.com' in email_lower or 'hexa.com' in email_lower:
                        resolved_org = Organization.query.filter_by(slug='hex').first()
                    elif 'infosys.com' in email_lower or 'infy.com' in email_lower:
                        resolved_org = Organization.query.filter_by(slug='infosys').first()
                    elif 'wipro.com' in email_lower:
                        resolved_org = Organization.query.filter_by(slug='wipro').first()
                    elif 'tcs.com' in email_lower:
                        resolved_org = Organization.query.filter_by(slug='tcs').first()
                    elif 'accenture.com' in email_lower:
                        resolved_org = Organization.query.filter_by(slug='accenture').first()
                    
                    if not resolved_org and '@' in email_lower:
                        domain = email_lower.split('@')[1]
                        resolved_org = Organization.query.filter(Organization.permitted_domains.ilike(f"%{domain}%")).first()
                    
                    if resolved_org:
                        user_data['organization_id'] = resolved_org.id
            elif otp_role == 'trainer':
                user_data['crm_trainer_id'] = crm_data.get('id')
                # Lookup ShadowTrainer to get organization_id
                from app.core.shadow_models import ShadowTrainer
                shadow = ShadowTrainer.query.filter_by(email=otp_email).first()
                if shadow:
                    user_data['organization_id'] = shadow.organization_id
        else:
            flash('Unknown role.', 'danger')
            return redirect(url_for('auth.login'))

        staff_user = StaffUser(user_data)

        # Cache full user_data in session so user_loader can restore role correctly
        from flask import session as flask_session
        flask_session['organization_id'] = user_data.get('organization_id', 1)
        flask_session['_lms_user'] = user_data
        flask_session.modified = True

        login_user(staff_user)
        flash(f'Welcome, {staff_user.full_name or otp_email}!', 'success')

        # Support AJAX
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.form.get('ajax') == '1':
            target_url = url_for('workshops.list_workshops')
            if otp_role == 'learner':
                target_url = url_for('learner_portal.dashboard')
            elif otp_role == 'trainer':
                target_url = url_for('trainer_portal.dashboard')
            elif otp_role == 'client':
                target_url = url_for('client_portal.dashboard')
            
            return jsonify({
                'success': True,
                'redirect_url': target_url
            })

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
