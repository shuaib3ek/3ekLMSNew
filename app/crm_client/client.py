"""
CRM Client — HTTP API wrapper for the 4 shared CRM entities.

The LMS NEVER imports from 3EK-Pulse (CRM) directly.
All cross-references (User Login, Clients, Contacts, Trainers)
go through this module via REST API calls only.
"""
import requests
from flask import current_app


def _headers():
    return {
        'X-Service-Token': current_app.config.get('CRM_SERVICE_TOKEN', ''),
        'Content-Type': 'application/json',
    }


def _base():
    return current_app.config.get('CRM_API_URL', 'http://localhost:8013')


# ─── User Login ───────────────────────────────────────────────────────────────

def get_user(user_id: int) -> dict | None:
    """Resolve a CRM staff user by ID."""
    try:
        r = requests.get(f'{_base()}/api/v1/crm/users/{user_id}', headers=_headers(), timeout=5)
        return r.json().get('data') if r.ok else None
    except Exception:
        return None


# ─── Clients ─────────────────────────────────────────────────────────────────

def get_client(client_id: int) -> dict | None:
    """Resolve a CRM client (company) by ID."""
    try:
        r = requests.get(f'{_base()}/api/v1/crm/clients/{client_id}', headers=_headers(), timeout=5)
        return r.json().get('data') if r.ok else None
    except Exception:
        return None


def list_clients() -> list:
    """Return all active CRM clients."""
    try:
        r = requests.get(f'{_base()}/api/v1/crm/clients', headers=_headers(), timeout=5)
        return r.json().get('data', []) if r.ok else []
    except Exception:
        return []


# ─── Contacts ────────────────────────────────────────────────────────────────

def get_contact(contact_id: int) -> dict | None:
    """Resolve a CRM contact by ID."""
    try:
        r = requests.get(f'{_base()}/api/v1/crm/contacts/{contact_id}', headers=_headers(), timeout=5)
        return r.json().get('data') if r.ok else None
    except Exception:
        return None


def list_contacts() -> list:
    """Return all active CRM contacts for invitation."""
    try:
        r = requests.get(f'{_base()}/api/v1/crm/contacts', headers=_headers(), timeout=5)
        return r.json().get('data', []) if r.ok else []
    except Exception:
        return []


# ─── Trainers ────────────────────────────────────────────────────────────────

def get_trainer(trainer_id: int) -> dict | None:
    """Resolve a CRM trainer by ID."""
    try:
        r = requests.get(f'{_base()}/api/v1/crm/trainers/{trainer_id}', headers=_headers(), timeout=5)
        return r.json().get('data') if r.ok else None
    except Exception:
        return None


def lookup_trainer_by_email(email: str) -> dict | None:
    """Check if a trainer exists by email in the CRM."""
    try:
        r = requests.get(f'{_base()}/api/v1/crm/trainers/lookup', params={'email': email}, headers=_headers(), timeout=5)
        return r.json().get('data') if r.ok else None
    except Exception:
        return None


def list_trainers(status: str = 'active') -> list:
    """Return CRM trainers, optionally filtered by status."""
    try:
        r = requests.get(
            f'{_base()}/api/v1/crm/trainers',
            headers=_headers(),
            params={'status': status},
            timeout=5
        )
        return r.json().get('data', []) if r.ok else []
    except Exception:
        return []


# ─── LMS → CRM Event Callbacks ───────────────────────────────────────────────

def lookup_contact_by_email(email: str) -> dict | None:
    """Check if a contact (client) exists by email in the CRM."""
    try:
        r = requests.get(f'{_base()}/api/v1/crm/contacts/lookup', params={'email': email}, headers=_headers(), timeout=5)
        return r.json().get('data') if r.ok else None
    except Exception:
        return None


def notify_completion(crm_contact_id: int, workshop_id: int, certificate_url: str = None):
    """Push a course completion event to the CRM for engagement tracking."""
    payload = {
        'event': 'learner_completed_course',
        'crm_contact_id': crm_contact_id,
        'workshop_id': workshop_id,
        'certificate_url': certificate_url,
    }
    try:
        requests.post(
            f'{_base()}/api/v1/crm/events/lms-completion',
            json=payload,
            headers=_headers(),
            timeout=5
        )
    except Exception:
        pass  # Non-blocking — CRM notification is best-effort


# ─── Client Portal Data ───────────────────────────────────────────────────────

def get_programs_for_client(client_id: int) -> list:
    """Return all CRM Engagements (programs) for a client company."""
    try:
        r = requests.get(
            f'{_base()}/api/v1/crm/programs',
            params={'client_id': client_id},
            headers=_headers(),
            timeout=8
        )
        return r.json().get('data', []) if r.ok else []
    except Exception:
        return []


def get_program_detail(engagement_id: int) -> dict | None:
    """Return a single CRM Engagement with invoices and documents."""
    try:
        r = requests.get(f'{_base()}/api/v1/crm/programs/{engagement_id}', headers=_headers(), timeout=8)
        return r.json().get('data') if r.ok else None
    except Exception:
        return None


def get_open_requests(client_id: int) -> list:
    """Return open training Inquiries for a client company."""
    try:
        r = requests.get(
            f'{_base()}/api/v1/crm/requests',
            params={'client_id': client_id},
            headers=_headers(),
            timeout=8
        )
        return r.json().get('data', []) if r.ok else []
    except Exception:
        return []


def get_account_manager(client_id: int) -> dict | None:
    """Return the 3EK account manager assigned to this client."""
    try:
        r = requests.get(f'{_base()}/api/v1/crm/clients/{client_id}/account-manager', headers=_headers(), timeout=5)
        return r.json().get('data') if r.ok else None
    except Exception:
        return None


def verify_contact_password(email: str, password: str) -> dict | None:
    """Verify contact credentials against CRM. Returns contact data dict or None."""
    try:
        r = requests.post(
            f'{_base()}/api/v1/crm/contacts/verify',
            json={'email': email, 'password': password},
            headers=_headers(),
            timeout=5
        )
        if r.ok:
            resp = r.json()
            if resp.get('valid'):
                return resp.get('data')
        return None
    except Exception:
        return None

