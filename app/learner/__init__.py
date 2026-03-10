"""
Learner Portal Blueprint
Web-based portal for learners to view their workshops, materials,
recordings, and certificates. Authenticated via OTP (see auth/routes.py).
"""
from flask import Blueprint

learner_portal_bp = Blueprint('learner_portal', __name__, template_folder='templates')

from app.learner import routes  # noqa: F401, E402
