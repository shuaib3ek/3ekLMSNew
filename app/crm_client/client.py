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
    return current_app.config.get('CRM_API_URL', 'http://localhost:5000')


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
    """Resolve a CRM contact (learner) by ID."""
    try:
        r = requests.get(f'{_base()}/api/v1/crm/contacts/{contact_id}', headers=_headers(), timeout=5)
        return r.json().get('data') if r.ok else None
    except Exception:
        return None


# ─── Trainers ────────────────────────────────────────────────────────────────

def get_trainer(trainer_id: int) -> dict | None:
    """Resolve a CRM trainer by ID."""
    try:
        r = requests.get(f'{_base()}/api/v1/crm/trainers/{trainer_id}', headers=_headers(), timeout=5)
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
