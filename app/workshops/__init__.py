from flask import Blueprint

workshops_bp = Blueprint('workshops', __name__)

from app.workshops import routes  # noqa: F401, E402
