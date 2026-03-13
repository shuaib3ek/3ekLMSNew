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
            for c in data:
                update_shadow_contact(c)
            return data
    except Exception:
        pass
    
    contacts = ShadowContact.query.all()
    return [{
        'id': c.crm_contact_id,
        'name': c.name,
        'email': c.email,
        'client_id': c.crm_client_id
    } for c in contacts]

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
            for t in data:
                update_shadow_trainer(t)
            return data
    except Exception:
        pass

    trainers = ShadowTrainer.query.all()
    return [{
        'id': t.crm_trainer_id,
        'name': t.name,
        'email': t.email,
        'photo_url': t.photo_url
    } for t in trainers]

def lookup_trainer_by_email(email: str) -> dict | None:
    try:
        r = requests.get(f'{_base()}/api/v1/crm/trainers/lookup', params={'email': email}, headers=_headers(), timeout=2)
        if r.ok:
            data = r.json().get('data')
            if data:
                update_shadow_trainer(data)
                return data
    except Exception:
        pass
    
    trainer = ShadowTrainer.query.filter_by(email=email).first()
    return {'id': trainer.crm_trainer_id, 'name': trainer.name} if trainer else None

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
        current_app.logger.warning(f"[Pulse Integration] Failed to fetch historical programs: {e}")
    
    # If Pulse is offline, return an empty list for the read-only view.
    return []

