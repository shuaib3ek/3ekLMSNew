import requests
from flask import current_app
from app.core.extensions import db
from app.core.shadow_models import ShadowStaffUser, ShadowTrainer, ShadowClient, ShadowContact
from app.crm_client.shadow_sync import (
    update_shadow_staff_user, update_shadow_trainer, 
    update_shadow_client, update_shadow_contact
)

def _headers():
    return {
        'X-Service-Token': current_app.config.get('CRM_SERVICE_TOKEN', ''),
        'Content-Type': 'application/json',
    }

def _base():
    return current_app.config.get('CRM_API_URL', 'http://localhost:8013')

# ─── Auth / User Login ───────────────────────────────────────────────────────

def verify_staff_password(email: str, password: str) -> dict | None:
    """Verify staff credentials against CRM with shadow fallback."""
    try:
        # 1. Primary path: CRM API
        r = requests.post(
            f'{_base()}/api/v1/crm/auth/verify',
            json={'email': email, 'password': password},
            headers=_headers(),
            timeout=2 # 2s for fast fallback
        )
        if r.ok:
            data = r.json()
            if data.get('valid') and data.get('user'):
                user_data = data.get('user')
                # Update Shadow Table & Cache Password
                update_shadow_staff_user(user_data)
                # Cache password hash
                from werkzeug.security import generate_password_hash
                user = ShadowStaffUser.query.filter_by(crm_user_id=user_data['id']).first()
                if user:
                    user.password_hash = generate_password_hash(password)
                    db.session.commit()
                return user_data
    except Exception as e:
        current_app.logger.warning(f"[LMS] CRM Auth Gateway offline: {e}")

    # 2. Fallback path: Shadow Database
    user = ShadowStaffUser.query.filter_by(email=email).first()
    if user and user.password_hash:
        from werkzeug.security import check_password_hash
        if check_password_hash(user.password_hash, password):
            current_app.logger.info(f"[LMS] Authenticated {email} via Shadow Database fallback.")
            return {
                'id': user.crm_user_id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': user.role
            }
    return None

def get_user(user_id: int) -> dict | None:
    """Resolve a CRM staff user by ID with shadow fallback."""
    try:
        r = requests.get(f'{_base()}/api/v1/crm/users/{user_id}', headers=_headers(), timeout=2)
        if r.ok:
            data = r.json().get('data')
            if data:
                update_shadow_staff_user(data)
                return data
    except Exception:
        pass
    
    # Fallback
    user = ShadowStaffUser.query.filter_by(crm_user_id=user_id).first()
    return {
        'id': user.crm_user_id,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'role': user.role
    } if user else None

# ─── Clients ─────────────────────────────────────────────────────────────────

def get_client(client_id: int) -> dict | None:
    """Resolve a CRM client (company) by ID with shadow fallback."""
    try:
        r = requests.get(f'{_base()}/api/v1/crm/clients/{client_id}', headers=_headers(), timeout=2)
        if r.ok:
            data = r.json().get('data')
            if data:
                update_shadow_client(data)
                return data
    except Exception:
        pass

    client = ShadowClient.query.filter_by(crm_client_id=client_id).first()
    return {
        'id': client.crm_client_id,
        'name': client.name,
        'domain': client.domain,
        'logo': client.logo
    } if client else None

def get_account_manager(client_id: int) -> dict | None:
    """Fetch the account manager for a specific client from CRM."""
    try:
        r = requests.get(f'{_base()}/api/v1/crm/clients/{client_id}/account-manager', headers=_headers(), timeout=2)
        if r.ok:
            return r.json().get('data')
    except Exception:
        pass
    return None

def list_clients() -> list:
    """Return all active CRM clients with shadow fallback."""
    try:
        r = requests.get(f'{_base()}/api/v1/crm/clients', headers=_headers(), timeout=2)
        if r.ok:
            data = r.json().get('data', [])
            for c in data:
                update_shadow_client(c)
            return data
    except Exception:
        pass
    
    clients = ShadowClient.query.all()
    return [{
        'id': c.crm_client_id,
        'name': c.name,
        'domain': c.domain,
        'logo': c.logo
    } for c in clients]

def get_programs_for_client(client_id: int) -> list:
    """Fetch programs (engagements) for a specific client from CRM."""
    all_programs = fetch_pulse_programs()
    
    # Get client name for fuzzy matching fallback
    c_data = get_client(client_id)
    c_name = (c_data.get('name') or '').lower() if c_data else ''
    
    result = []
    for p in all_programs:
        if p.get('client_id') == client_id:
            result.append(p)
        elif p.get('client_id') in (None, '') and c_name and p.get('client_name'):
            p_name = p.get('client_name').lower()
            if c_name in p_name or p_name in c_name:
                result.append(p)
                
    return result

# ─── Contacts ────────────────────────────────────────────────────────────────

def get_contact(contact_id: int) -> dict | None:
    """Resolve a CRM contact by ID with shadow fallback."""
    try:
        r = requests.get(f'{_base()}/api/v1/crm/contacts/{contact_id}', headers=_headers(), timeout=2)
        if r.ok:
            data = r.json().get('data')
            if data:
                update_shadow_contact(data)
                return data
    except Exception:
        pass

    contact = ShadowContact.query.filter_by(crm_contact_id=contact_id).first()
    return {
        'id': contact.crm_contact_id,
        'name': contact.name,
        'email': contact.email,
        'client_id': contact.crm_client_id
    } if contact else None

def list_contacts() -> list:
    """Return all active CRM contacts with shadow fallback."""
    try:
        r = requests.get(f'{_base()}/api/v1/crm/contacts', headers=_headers(), timeout=2)
        if r.ok:
            data = r.json().get('data', [])
            current_app.logger.warning(f"[LMS] CRM API list_contacts SUCCESS: fetched {len(data)} contacts")
            try:
                # Attempt shadow sync, but don't let it block the live data return
                for c in data:
                    try:
                        update_shadow_contact(c)
                    except Exception as loop_e:
                        current_app.logger.error(f"[LMS] Per-contact shadow sync error for {c.get('email', 'unknown')}: {loop_e}")
            except Exception as sync_e:
                current_app.logger.error(f"[LMS] Major shadow sync error for contacts: {sync_e}")
            return data
        else:
            current_app.logger.warning(f"[LMS] CRM API list_contacts non-ok response ({r.status_code}): {r.text}")
    except Exception as e:
        current_app.logger.warning(f"[LMS] CRM API list_contacts critical failure: {e}")
    
    # Fallback to local cache if API is UNREACHABLE or returns Error
    contacts = ShadowContact.query.all()
    return [{
        'id': c.crm_contact_id,
        'name': c.name,
        'email': c.email,
        'client_id': c.crm_client_id
    } for c in contacts]

def get_open_requests(client_id: int) -> list:
    """Fetch open training requests (inquiries) for a specific client from CRM."""
    try:
        r = requests.get(f'{_base()}/api/v1/crm/requests?client_id={client_id}', headers=_headers(), timeout=2)
        if r.ok:
            return r.json().get('data', [])
    except Exception:
        pass
    return []

def verify_contact_password(email: str, password: str) -> dict | None:
    """Verify contact credentials with shadow fallback."""
    try:
        r = requests.post(
            f'{_base()}/api/v1/crm/contacts/verify',
            json={'email': email, 'password': password},
            headers=_headers(),
            timeout=2
        )
        if r.ok:
            resp = r.json()
            if resp.get('valid') and resp.get('data'):
                contact_data = resp.get('data')
                update_shadow_contact(contact_data, password=password)
                return contact_data
    except Exception:
        pass
    
    # Fallback
    contact = ShadowContact.query.filter_by(email=email).first()
    if contact and contact.password_hash:
        from werkzeug.security import check_password_hash
        if check_password_hash(contact.password_hash, password):
            return {
                'id': contact.crm_contact_id,
                'name': contact.name,
                'email': contact.email,
                'client_id': contact.crm_client_id
            }
    return None

# ─── Trainers ────────────────────────────────────────────────────────────────

def get_trainer(trainer_id: int) -> dict | None:
    """Resolve a CRM trainer with shadow fallback."""
    try:
        r = requests.get(f'{_base()}/api/v1/crm/trainers/{trainer_id}', headers=_headers(), timeout=2)
        if r.ok:
            data = r.json().get('data')
            if data:
                update_shadow_trainer(data)
                return data
    except Exception:
        pass

    trainer = ShadowTrainer.query.filter_by(crm_trainer_id=trainer_id).first()
    return {
        'id': trainer.crm_trainer_id,
        'name': trainer.name,
        'email': trainer.email,
        'bio': trainer.bio,
        'photo_url': trainer.photo_url,
        'expertise': trainer.expertise
    } if trainer else None

def list_trainers(status: str = 'active') -> list:
    """Return CRM trainers with shadow fallback."""
    try:
        r = requests.get(
            f'{_base()}/api/v1/crm/trainers',
            headers=_headers(),
            params={'status': status},
            timeout=2
        )
        if r.ok:
            data = r.json().get('data', [])
            current_app.logger.warning(f"[LMS] CRM API list_trainers SUCCESS: fetched {len(data)} trainers (status: {status})")
            try:
                for t in data:
                    try:
                        update_shadow_trainer(t)
                    except Exception as loop_e:
                        current_app.logger.error(f"[LMS] Per-trainer shadow sync error for {t.get('name', 'unknown')}: {loop_e}")
            except Exception as sync_e:
                 current_app.logger.error(f"[LMS] Major shadow sync error for trainers: {sync_e}")
            return data
        else:
            current_app.logger.warning(f"[LMS] CRM API list_trainers non-ok response ({r.status_code}): {r.text}")
    except Exception as e:
        current_app.logger.warning(f"[LMS] CRM API list_trainers critical failure: {e}")

    trainers = ShadowTrainer.query.all()
    return [{
        'id': t.crm_trainer_id,
        'name': t.name,
        'email': t.email,
        'photo_url': t.photo_url
    } for t in trainers]

def lookup_trainer_by_email(email: str) -> dict | None:
    """Find a trainer by email. Falls back to full list scan when /lookup is unavailable."""
    email = email.strip().lower()

    # 1. Try the dedicated lookup endpoint (may not exist in all CRM versions)
    try:
        r = requests.get(f'{_base()}/api/v1/crm/trainers/lookup', params={'email': email}, headers=_headers(), timeout=2)
        if r.ok:
            data = r.json().get('data')
            if data:
                update_shadow_trainer(data)
                return data
    except Exception:
        pass

    # 2. Fall back: search the full trainer list (both active and vetted)
    for status in ('active', 'vetted'):
        try:
            r = requests.get(f'{_base()}/api/v1/crm/trainers',
                             params={'status': status}, headers=_headers(), timeout=3)
            if r.ok:
                trainers = r.json().get('data', [])
                match = next((t for t in trainers if t.get('email', '').strip().lower() == email), None)
                if match:
                    try:
                        update_shadow_trainer(match)
                    except Exception:
                        pass
                    return match
        except Exception:
            pass

    # 3. Shadow DB fallback
    trainer = ShadowTrainer.query.filter_by(email=email).first()
    if trainer:
        return {
            'id': trainer.crm_trainer_id,
            'name': trainer.name,
            'email': trainer.email,
            'first_name': trainer.name.split()[0] if trainer.name else '',
            'last_name': ' '.join(trainer.name.split()[1:]) if trainer.name and ' ' in trainer.name else '',
        }
    return None

def lookup_contact_by_email(email: str) -> dict | None:
    try:
        r = requests.get(f'{_base()}/api/v1/crm/contacts/lookup', params={'email': email}, headers=_headers(), timeout=2)
        if r.ok:
            data = r.json().get('data')
            if data:
                update_shadow_contact(data)
                return data
    except Exception:
        pass
    
    contact = ShadowContact.query.filter_by(email=email).first()
    return {'id': contact.crm_contact_id, 'name': contact.name} if contact else None

# ─── Best Effort Event Notifications ────────────────────────────────────────

def notify_completion(crm_contact_id: int, workshop_id: int, certificate_url: str = None):
    payload = {
        'event': 'learner_completed_course',
        'crm_contact_id': crm_contact_id,
        'workshop_id': workshop_id,
        'certificate_url': certificate_url,
    }
    try:
        requests.post(f'{_base()}/api/v1/crm/events/lms-completion', json=payload, headers=_headers(), timeout=2)
    except Exception:
        pass

# ─── Training Management (External Pulse Data) ──────────────────────────────
def fetch_pulse_programs() -> list:
    """
    Retrieves read-only historical and ongoing programs directly from 3ek-pulse.
    This data lives entirely outside of the LMS Workshop engine.
    """
    try:
        r = requests.get(f'{_base()}/api/v1/crm/programs', headers=_headers(), timeout=2)
        if r.ok:
            return r.json().get('data', [])
    except Exception as e:
        current_app.logger.error(f"[LMS] Failed to fetch programs: {e}")
    return []

def fetch_pulse_program_detail(program_id: int) -> dict | None:
    """
    Retrieves a single program detail from 3ek-pulse.
    """
    try:
        r = requests.get(f'{_base()}/api/v1/crm/programs/{program_id}', headers=_headers(), timeout=2)
        if r.ok:
            data = r.json().get('data')
            if data:
                # The detail API currently omits client_name, enrich it from the list API if needed
                if not data.get('client_name'):
                    for p in fetch_pulse_programs():
                        if p.get('id') == program_id:
                            data['client_name'] = p.get('client_name')
                            break
            return data
    except Exception as e:
        current_app.logger.error(f"[LMS] Failed to fetch program {program_id}: {e}")
    
    # Fallback to fetching all and filtering if individual endpoint doesn't exist
    for p in fetch_pulse_programs():
        if p.get('id') == program_id:
            return p
    return None

get_program_detail = fetch_pulse_program_detail
